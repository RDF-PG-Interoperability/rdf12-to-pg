#!/usr/bin/env python3
"""Run conversion-only experiments on RDF 1.2-migrated BKR samples."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
STAR_DIR = EXPERIMENTS / "starbench"
DATA_DIR = STAR_DIR / "data"
RESULTS_DIR = STAR_DIR / "results"
TMP_DIR = RESULTS_DIR / "tmp"

SIZES = ("0.5mb", "1mb", "1.5mb", "2mb", "2.5mb")


def positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def load_harness():
    """Load the shared synthetic experiment harness as a module."""

    path = EXPERIMENTS / "run_experiments.py"
    spec = importlib.util.spec_from_file_location("rdf12_experiment_harness", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import experiment harness from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.RESULTS_DIR = RESULTS_DIR
    module.TMP_DIR = TMP_DIR
    module.SIZES = tuple((label, 0) for label in SIZES)
    return module


def build_datasets(harness):
    """Read the checked-in samples and refresh their metadata CSV."""

    sys.path.insert(0, str(ROOT / "cypher"))
    from rdf12_to_neo4j import parse_turtle_rdf12

    datasets = []
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = RESULTS_DIR / "datasets.csv"
    with metadata_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("size", "count", "path", "bytes", "lines", "triples"),
            lineterminator="\n",
        )
        writer.writeheader()
        for label in SIZES:
            path = DATA_DIR / f"starbench-{label}.ttl"
            text = path.read_text(encoding="utf-8")
            triples, _ = parse_turtle_rdf12(text, source=str(path))
            lines = len(text.splitlines())
            reifiers = text.count(" rdf:reifies ")
            dataset = harness.Dataset(
                label=label,
                count=reifiers,
                path=path,
                bytes=path.stat().st_size,
                lines=lines,
                triples=len(triples),
            )
            datasets.append(dataset)
            writer.writerow(
                {
                    "size": label,
                    "count": reifiers,
                    "path": str(path.relative_to(ROOT)),
                    "bytes": dataset.bytes,
                    "lines": lines,
                    "triples": len(triples),
                }
            )
    return datasets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("convert", "summarize"),
        default="convert",
        help="Run conversions or only rebuild summaries from existing CSVs.",
    )
    parser.add_argument("--runs", type=positive_int, default=10)
    parser.add_argument("--batch-size", type=positive_int, default=1000)
    parser.add_argument("--timeout", type=positive_int, default=3600)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    harness = load_harness()
    datasets = build_datasets(harness)
    if args.phase == "convert":
        harness.run_conversion_experiments(
            datasets,
            runs=args.runs,
            batch_size=args.batch_size,
            timeout=args.timeout,
        )
    conversion = harness.read_csv(RESULTS_DIR / "conversion_raw.csv")
    harness.write_stats_csv(
        RESULTS_DIR / "conversion_summary.csv",
        conversion,
        ("size", "tool", "mode", "variant"),
        ("time_s", "peak_kb", "output_bytes"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
