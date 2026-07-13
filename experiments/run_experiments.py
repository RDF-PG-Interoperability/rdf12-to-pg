#!/usr/bin/env python3
"""Run synthetic RDF 1.2 conversion and Neo4j loading experiments.

The script intentionally keeps the experiment harness outside the converter
packages.  It generates deterministic datasets once, then measures each CLI as
a separate process through GNU time so converter wall-clock time and peak RSS
are not mixed with the harness process.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import os
import re
import signal
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
DATA_DIR = EXPERIMENTS / "data"
RESULTS_DIR = EXPERIMENTS / "results"
TMP_DIR = RESULTS_DIR / "tmp"
TOOLS_DIR = EXPERIMENTS / "tools"

# The generator emits 67 parsed RDF triples per count for profile "all".
# The counts below target approximately 0.5 MB, 1 MB, 1.5 MB, 2 MB, and 2.5 MB
# Turtle files with the current deterministic generator.
SIZES: tuple[tuple[str, int], ...] = (
    ("0.5mb", 200),
    ("1mb", 400),
    ("1.5mb", 600),
    ("2mb", 800),
    ("2.5mb", 1_000),
)

NEO4J_VERSION = "2026.06.0"
NEO4J_ARCHIVE_URL = (
    f"https://dist.neo4j.org/neo4j-community-{NEO4J_VERSION}-unix.tar.gz"
)
NEO4J_ARCHIVE_SHA256 = (
    "1dcf62e7e8035e71732b86532b9f8e3219ce8956bd06940d5a0024696727192a"
)
NEO4J_BATCHED_RUNS = 5


@dataclass(frozen=True)
class Dataset:
    label: str
    count: int
    path: Path
    bytes: int
    lines: int
    triples: int


@dataclass(frozen=True)
class ConversionConfig:
    tool: str
    mode: str
    variant: int


CONVERSION_CONFIGS: tuple[ConversionConfig, ...] = tuple(
    [ConversionConfig("yarspg", "normal", variant) for variant in (1, 2, 3)]
    + [ConversionConfig("cypher", "normal", variant) for variant in (1, 2, 3)]
    + [ConversionConfig("cypher", "large-file", variant) for variant in (1, 2, 3)]
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        type=positive_int,
        default=10,
        help=(
            "Repetitions per conversion configuration (default: 10). "
            "Neo4j batched loads always use five repetitions."
        ),
    )
    parser.add_argument("--batch-size", type=positive_int, default=1000)
    parser.add_argument(
        "--sizes",
        nargs="*",
        choices=[label for label, _ in SIZES],
        default=[label for label, _ in SIZES],
        help="Dataset sizes to benchmark.",
    )
    parser.add_argument(
        "--phase",
        choices=("all", "convert", "neo4j", "summarize"),
        default="all",
        help="Which phase to execute.",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=3600,
        help="Per-process timeout in seconds.",
    )
    args = parser.parse_args(argv)

    ensure_dirs()
    datasets = prepare_datasets(args.sizes) if args.phase != "summarize" else []
    if args.phase in {"all", "convert"}:
        run_conversion_experiments(datasets, args.runs, args.batch_size, args.timeout)
    if args.phase in {"all", "neo4j"}:
        run_neo4j_experiments(datasets, args.batch_size, args.timeout)
    if args.phase in {"all", "convert", "neo4j", "summarize"}:
        write_summary_files()
    return 0


def positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def ensure_dirs() -> None:
    for directory in (DATA_DIR, RESULTS_DIR, TMP_DIR, TOOLS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def prepare_datasets(selected_sizes: Iterable[str]) -> list[Dataset]:
    selected = set(selected_sizes)
    sys.path.insert(0, str(ROOT / "synthetic-generator"))
    sys.path.insert(0, str(ROOT / "cypher"))
    from synthetic_gen_lib import generate_turtle
    from rdf12_to_neo4j import parse_turtle_rdf12

    datasets: list[Dataset] = []
    for label, count in SIZES:
        if label not in selected:
            continue
        path = DATA_DIR / f"synthetic-{label}.ttl"
        text = generate_turtle(profile="all", count=count, seed=7)
        path.write_text(text, encoding="utf-8")
        triples, _ = parse_turtle_rdf12(text, source=str(path))
        datasets.append(
            Dataset(
                label=label,
                count=count,
                path=path,
                bytes=path.stat().st_size,
                lines=len(text.splitlines()),
                triples=len(triples),
            )
        )
    write_dataset_metadata(datasets)
    return datasets


def write_dataset_metadata(datasets: list[Dataset]) -> None:
    path = RESULTS_DIR / "datasets.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("size", "count", "path", "bytes", "lines", "triples"),
            lineterminator="\n",
        )
        writer.writeheader()
        for dataset in datasets:
            writer.writerow(
                {
                    "size": dataset.label,
                    "count": dataset.count,
                    "path": str(dataset.path.relative_to(ROOT)),
                    "bytes": dataset.bytes,
                    "lines": dataset.lines,
                    "triples": dataset.triples,
                }
            )


def run_conversion_experiments(
    datasets: list[Dataset],
    runs: int,
    batch_size: int,
    timeout: int,
) -> None:
    raw_path = RESULTS_DIR / "conversion_raw.csv"
    fieldnames = (
        "timestamp",
        "size",
        "count",
        "input_bytes",
        "input_lines",
        "input_triples",
        "tool",
        "mode",
        "variant",
        "run",
        "exit_code",
        "time_s",
        "peak_kb",
        "output_bytes",
        "batch_size",
        "stderr",
    )
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for dataset in datasets:
            for config in CONVERSION_CONFIGS:
                for run_index in range(1, runs + 1):
                    print(
                        "conversion",
                        dataset.label,
                        config.tool,
                        config.mode,
                        f"v{config.variant}",
                        f"run={run_index}/{runs}",
                        file=sys.stderr,
                        flush=True,
                    )
                    row = run_one_conversion(dataset, config, run_index, batch_size, timeout)
                    writer.writerow(row)
                    handle.flush()
                    if int(row["exit_code"]) != 0:
                        for skipped_index in range(run_index + 1, runs + 1):
                            writer.writerow(
                                skipped_conversion_row(
                                    dataset,
                                    config,
                                    skipped_index,
                                    batch_size,
                                    row,
                                )
                            )
                        handle.flush()
                        break


def run_one_conversion(
    dataset: Dataset,
    config: ConversionConfig,
    run_index: int,
    batch_size: int,
    timeout: int,
) -> dict[str, object]:
    output = representative_cypher_path(dataset, config)
    if config.tool == "yarspg":
        output = TMP_DIR / f"{dataset.label}-{config.tool}-{config.mode}-v{config.variant}.yarspg"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    cmd = command_for_conversion(dataset.path, output, config, batch_size)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT / "cypher"),
            str(ROOT / "yarspg"),
            str(ROOT / "synthetic-generator"),
        ]
    )
    result = run_timed(cmd, env=env, timeout=timeout)
    output_bytes = output.stat().st_size if output.exists() else 0
    return {
        "timestamp": now_iso(),
        "size": dataset.label,
        "count": dataset.count,
        "input_bytes": dataset.bytes,
        "input_lines": dataset.lines,
        "input_triples": dataset.triples,
        "tool": config.tool,
        "mode": config.mode,
        "variant": config.variant,
        "run": run_index,
        "exit_code": result["exit_code"],
        "time_s": result["time_s"],
        "peak_kb": result["peak_kb"],
        "output_bytes": output_bytes,
        "batch_size": batch_size if config.mode == "large-file" else "",
        "stderr": result["stderr"],
    }


def skipped_conversion_row(
    dataset: Dataset,
    config: ConversionConfig,
    run_index: int,
    batch_size: int,
    failed_row: dict[str, object],
) -> dict[str, object]:
    return {
        "timestamp": now_iso(),
        "size": dataset.label,
        "count": dataset.count,
        "input_bytes": dataset.bytes,
        "input_lines": dataset.lines,
        "input_triples": dataset.triples,
        "tool": config.tool,
        "mode": config.mode,
        "variant": config.variant,
        "run": run_index,
        "exit_code": 125,
        "time_s": "",
        "peak_kb": "",
        "output_bytes": "",
        "batch_size": batch_size if config.mode == "large-file" else "",
        "stderr": (
            f"skipped after run {failed_row.get('run')} failed "
            f"with exit_code={failed_row.get('exit_code')}"
        ),
    }


def command_for_conversion(
    input_path: Path,
    output_path: Path,
    config: ConversionConfig,
    batch_size: int,
) -> list[str]:
    if config.tool == "yarspg":
        return [
            str(ROOT / "yarspg" / "rdf12_to_yarspg"),
            "--variant",
            str(config.variant),
            str(input_path),
            "-o",
            str(output_path),
        ]
    cmd = [
        str(ROOT / "cypher" / "rdf12_to_neo4j"),
        "--variant",
        str(config.variant),
    ]
    if config.mode == "large-file":
        cmd.extend(["--large-file", "--batch-size", str(batch_size)])
    cmd.extend([str(input_path), "-o", str(output_path)])
    return cmd


def run_neo4j_experiments(
    datasets: list[Dataset],
    batch_size: int,
    timeout: int,
) -> None:
    neo4j_home = ensure_neo4j()
    process = start_neo4j(neo4j_home)
    try:
        wait_for_neo4j(neo4j_home, timeout=120)
        raw_path = RESULTS_DIR / "neo4j_load_raw.csv"
        fieldnames = (
            "timestamp",
            "neo4j_version",
            "size",
            "count",
            "input_bytes",
            "input_triples",
            "mode",
            "variant",
            "run",
            "exit_code",
            "time_s",
            "peak_kb",
            "cypher_bytes",
            "batch_size",
            "nodes",
            "relationships",
            "stderr",
        )
        with raw_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                lineterminator="\n",
            )
            writer.writeheader()
            for dataset in datasets:
                for variant in (1, 2, 3):
                    for mode in ("normal", "large-file"):
                        if mode == "normal" and (variant != 1 or dataset.label != "0.5mb"):
                            continue
                        config = ConversionConfig("cypher", mode, variant)
                        cypher_path = representative_cypher_path(dataset, config)
                        row = run_one_conversion(
                            dataset,
                            config,
                            0,
                            batch_size,
                            timeout,
                        )
                        if int(row["exit_code"]) != 0:
                            writer.writerow(neo4j_failure_row(dataset, mode, variant, row))
                            continue
                        # Normal output is one monolithic CREATE statement;
                        # keep one baseline load while fully repeating the
                        # scalable large-file path.
                        mode_runs = 1 if mode == "normal" else NEO4J_BATCHED_RUNS
                        for run_index in range(1, mode_runs + 1):
                            print(
                                "neo4j-load",
                                dataset.label,
                                mode,
                                f"v{variant}",
                                f"run={run_index}/{mode_runs}",
                                file=sys.stderr,
                                flush=True,
                            )
                            clear_neo4j(neo4j_home)
                            row = run_one_neo4j_load(
                                neo4j_home,
                                dataset,
                                cypher_path,
                                mode,
                                variant,
                                run_index,
                                batch_size,
                                timeout,
                            )
                            writer.writerow(row)
                            handle.flush()
                            if int(row["exit_code"]) != 0:
                                for skipped_index in range(run_index + 1, mode_runs + 1):
                                    writer.writerow(
                                        skipped_neo4j_row(
                                            dataset,
                                            mode,
                                            variant,
                                            skipped_index,
                                            batch_size,
                                            cypher_path,
                                            row,
                                        )
                                    )
                                handle.flush()
                                process = restart_neo4j(neo4j_home, process)
                                break
    finally:
        stop_neo4j(neo4j_home, process)


def ensure_neo4j() -> Path:
    target = TOOLS_DIR / f"neo4j-community-{NEO4J_VERSION}"
    if target.exists():
        configure_neo4j(target)
        return target
    archive = TOOLS_DIR / f"neo4j-community-{NEO4J_VERSION}-unix.tar.gz"
    if not archive.exists():
        with urllib.request.urlopen(NEO4J_ARCHIVE_URL, timeout=60) as response:
            with archive.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    actual_sha256 = file_sha256(archive)
    if actual_sha256 != NEO4J_ARCHIVE_SHA256:
        archive.unlink(missing_ok=True)
        raise RuntimeError(
            "Neo4j archive checksum mismatch: "
            f"expected {NEO4J_ARCHIVE_SHA256}, got {actual_sha256}"
        )
    subprocess.run(["tar", "-xzf", str(archive), "-C", str(TOOLS_DIR)], check=True)
    configure_neo4j(target)
    return target


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configure_neo4j(neo4j_home: Path) -> None:
    conf = neo4j_home / "conf" / "neo4j.conf"
    text = conf.read_text(encoding="utf-8")
    settings = {
        "server.default_listen_address": "127.0.0.1",
        "server.bolt.listen_address": "127.0.0.1:7687",
        "server.http.listen_address": "127.0.0.1:7474",
        "dbms.security.auth_enabled": "false",
        "server.memory.heap.initial_size": "8G",
        "server.memory.heap.max_size": "8G",
    }
    for key, value in settings.items():
        line = f"{key}={value}"
        pattern = re.compile(rf"^#?{re.escape(key)}=.*$", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            text += f"\n{line}\n"
    conf.write_text(text, encoding="utf-8")


def start_neo4j(neo4j_home: Path) -> subprocess.Popen[str]:
    log_path = RESULTS_DIR / "neo4j-console.log"
    log_handle = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["NEO4J_HOME"] = str(neo4j_home)
    return subprocess.Popen(
        [str(neo4j_home / "bin" / "neo4j"), "console"],
        cwd=str(neo4j_home),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )


def wait_for_neo4j(neo4j_home: Path, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                str(neo4j_home / "bin" / "cypher-shell"),
                "-a",
                "bolt://127.0.0.1:7687",
                "RETURN 1;",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise TimeoutError("Neo4j did not become ready")


def clear_neo4j(neo4j_home: Path) -> None:
    subprocess.run(
        [
            str(neo4j_home / "bin" / "cypher-shell"),
            "-a",
            "bolt://127.0.0.1:7687",
            "MATCH (n) DETACH DELETE n;",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        check=True,
    )


def run_one_neo4j_load(
    neo4j_home: Path,
    dataset: Dataset,
    cypher_path: Path,
    mode: str,
    variant: int,
    run_index: int,
    batch_size: int,
    timeout: int,
) -> dict[str, object]:
    cmd = [
        str(neo4j_home / "bin" / "cypher-shell"),
        "-a",
        "bolt://127.0.0.1:7687",
        "-f",
        str(cypher_path),
    ]
    result = run_timed(cmd, env=os.environ.copy(), timeout=timeout)
    nodes, relationships = count_neo4j(neo4j_home) if result["exit_code"] == 0 else ("", "")
    return {
        "timestamp": now_iso(),
        "neo4j_version": NEO4J_VERSION,
        "size": dataset.label,
        "count": dataset.count,
        "input_bytes": dataset.bytes,
        "input_triples": dataset.triples,
        "mode": mode,
        "variant": variant,
        "run": run_index,
        "exit_code": result["exit_code"],
        "time_s": result["time_s"],
        "peak_kb": result["peak_kb"],
        "cypher_bytes": cypher_path.stat().st_size,
        "batch_size": batch_size if mode == "large-file" else "",
        "nodes": nodes,
        "relationships": relationships,
        "stderr": result["stderr"],
    }


def skipped_neo4j_row(
    dataset: Dataset,
    mode: str,
    variant: int,
    run_index: int,
    batch_size: int,
    cypher_path: Path,
    failed_row: dict[str, object],
) -> dict[str, object]:
    return {
        "timestamp": now_iso(),
        "neo4j_version": NEO4J_VERSION,
        "size": dataset.label,
        "count": dataset.count,
        "input_bytes": dataset.bytes,
        "input_triples": dataset.triples,
        "mode": mode,
        "variant": variant,
        "run": run_index,
        "exit_code": 125,
        "time_s": "",
        "peak_kb": "",
        "cypher_bytes": cypher_path.stat().st_size if cypher_path.exists() else "",
        "batch_size": batch_size if mode == "large-file" else "",
        "nodes": "",
        "relationships": "",
        "stderr": (
            f"skipped after run {failed_row.get('run')} failed "
            f"with exit_code={failed_row.get('exit_code')}"
        ),
    }


def count_neo4j(neo4j_home: Path) -> tuple[int, int]:
    result = subprocess.run(
        [
            str(neo4j_home / "bin" / "cypher-shell"),
            "-a",
            "bolt://127.0.0.1:7687",
            "--format",
            "plain",
            "MATCH (n) WITH count(n) AS nodes MATCH ()-[r]->() RETURN nodes, count(r) AS relationships;",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=True,
    )
    numbers = [int(value) for value in re.findall(r"\d+", result.stdout)]
    if len(numbers) >= 2:
        return numbers[-2], numbers[-1]
    return 0, 0


def neo4j_failure_row(
    dataset: Dataset,
    mode: str,
    variant: int,
    conversion_row: dict[str, object],
) -> dict[str, object]:
    return {
        "timestamp": now_iso(),
        "neo4j_version": NEO4J_VERSION,
        "size": dataset.label,
        "count": dataset.count,
        "input_bytes": dataset.bytes,
        "input_triples": dataset.triples,
        "mode": mode,
        "variant": variant,
        "run": 0,
        "exit_code": conversion_row["exit_code"],
        "time_s": "",
        "peak_kb": "",
        "cypher_bytes": conversion_row.get("output_bytes", ""),
        "batch_size": conversion_row.get("batch_size", ""),
        "nodes": "",
        "relationships": "",
        "stderr": f"conversion failed: {conversion_row.get('stderr', '')}",
    }


def stop_neo4j(neo4j_home: Path, process: subprocess.Popen[str]) -> None:
    subprocess.run(
        [str(neo4j_home / "bin" / "neo4j"), "stop"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)


def restart_neo4j(neo4j_home: Path, process: subprocess.Popen[str]) -> subprocess.Popen[str]:
    stop_neo4j(neo4j_home, process)
    restarted = start_neo4j(neo4j_home)
    wait_for_neo4j(neo4j_home, timeout=120)
    return restarted


def representative_cypher_path(dataset: Dataset, config: ConversionConfig) -> Path:
    return (
        RESULTS_DIR
        / "cypher"
        / f"{dataset.label}-{config.mode}-v{config.variant}.cypher"
    )


def run_timed(
    cmd: list[str],
    env: dict[str, str],
    timeout: int,
) -> dict[str, object]:
    timed_cmd = ["/usr/bin/time", "-f", "TIME\t%e\t%M", *cmd]
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            timed_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        _, stderr = process.communicate(timeout=timeout)
        stderr = stderr or ""
        time_s, peak_kb = parse_time_stderr(stderr)
        clean_stderr = "\n".join(
            line for line in stderr.splitlines() if not line.startswith("TIME\t")
        )
        return {
            "exit_code": process.returncode,
            "time_s": time_s,
            "peak_kb": peak_kb,
            "stderr": clean(clean_stderr),
        }
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        return {
            "exit_code": 124,
            "time_s": timeout,
            "peak_kb": "",
            "stderr": clean(f"timeout after {timeout}s: {exc.stderr or ''}"),
        }


def parse_time_stderr(stderr: str) -> tuple[str, str]:
    for line in reversed(stderr.splitlines()):
        if line.startswith("TIME\t"):
            _, seconds, peak = line.split("\t")
            return seconds, peak
    return "", ""


def clean(value: object) -> str:
    text = str(value).replace("\r", " ").strip()
    return re.sub(r"\s+", " ", text)[:1000]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def write_summary_files() -> None:
    conversion = read_csv(RESULTS_DIR / "conversion_raw.csv")
    neo4j = read_csv(RESULTS_DIR / "neo4j_load_raw.csv")
    write_stats_csv(
        RESULTS_DIR / "conversion_summary.csv",
        conversion,
        ("size", "tool", "mode", "variant"),
        ("time_s", "peak_kb", "output_bytes"),
    )
    write_stats_csv(
        RESULTS_DIR / "neo4j_load_summary.csv",
        neo4j,
        ("size", "mode", "variant"),
        ("time_s", "peak_kb", "cypher_bytes", "nodes", "relationships"),
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_stats_csv(
    path: Path,
    rows: list[dict[str, str]],
    dimensions: tuple[str, ...],
    measures: tuple[str, ...],
) -> None:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("exit_code") != "0":
            continue
        key = tuple(row[dimension] for dimension in dimensions)
        grouped.setdefault(key, []).append(row)

    fieldnames = [
        *dimensions,
        "runs",
        *[
            f"{measure}_{stat}"
            for measure in measures
            for stat in ("avg", "mean", "min", "max", "stddev")
        ],
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for key in sorted(grouped):
            group_rows = grouped[key]
            out: dict[str, object] = dict(zip(dimensions, key, strict=True))
            out["runs"] = len(group_rows)
            for measure in measures:
                values = [float(row[measure]) for row in group_rows if row.get(measure)]
                stats = numeric_stats(values)
                for stat_name, stat_value in stats.items():
                    out[f"{measure}_{stat_name}"] = stat_value
            writer.writerow(out)


def numeric_stats(values: list[float]) -> dict[str, str]:
    if not values:
        return {name: "" for name in ("avg", "mean", "min", "max", "stddev")}
    mean = statistics.mean(values)
    stddev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "avg": f"{mean:.6g}",
        "mean": f"{mean:.6g}",
        "min": f"{min(values):.6g}",
        "max": f"{max(values):.6g}",
        "stddev": f"{stddev:.6g}",
    }


if __name__ == "__main__":
    raise SystemExit(main())
