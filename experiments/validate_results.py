#!/usr/bin/env python3
"""Validate the shape and internal consistency of checked-in result CSVs."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SIZES = {"0.5mb", "1mb", "1.5mb", "2mb", "2.5mb"}


class ValidationError(RuntimeError):
    """Raised when a published result artifact is incomplete or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def read_rows(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing CSV: {path.relative_to(ROOT)}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def grouped(
    rows: Iterable[dict[str, str]], dimensions: tuple[str, ...]
) -> dict[tuple[str, ...], list[dict[str, str]]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in dimensions)].append(row)
    return groups


def validate_datasets(results_dir: Path) -> None:
    rows = read_rows(results_dir / "datasets.csv")
    require(len(rows) == 5, f"{results_dir}: expected five dataset rows")
    require({row["size"] for row in rows} == SIZES, f"{results_dir}: wrong sizes")
    for row in rows:
        path = ROOT / row["path"]
        require(path.is_file(), f"missing dataset: {row['path']}")
        require(path.stat().st_size == int(row["bytes"]), f"wrong size: {row['path']}")
        require(int(row["lines"]) > 0, f"invalid line count: {row['path']}")
        require(int(row["triples"]) > 0, f"invalid triple count: {row['path']}")


def validate_conversion(results_dir: Path, label: str) -> None:
    raw = read_rows(results_dir / "conversion_raw.csv")
    require(len(raw) == 450, f"{label}: expected 450 raw conversion rows")
    require(all(row["exit_code"] == "0" for row in raw), f"{label}: failed run")

    dimensions = ("size", "tool", "mode", "variant")
    groups = grouped(raw, dimensions)
    require(len(groups) == 45, f"{label}: expected 45 conversion groups")
    for key, rows in groups.items():
        runs = sorted(int(row["run"]) for row in rows)
        require(runs == list(range(1, 11)), f"{label}: wrong repetitions for {key}")
        output_sizes = {row["output_bytes"] for row in rows}
        require(len(output_sizes) == 1, f"{label}: varying output size for {key}")

    summary = read_rows(results_dir / "conversion_summary.csv")
    require(len(summary) == 45, f"{label}: expected 45 summary rows")
    summary_groups = grouped(summary, dimensions)
    require(set(summary_groups) == set(groups), f"{label}: summary groups differ")
    require(
        all(row["runs"] == "10" for row in summary),
        f"{label}: summary run count differs from ten",
    )
    print(f"{label}: 450 conversion runs in 45 groups validated")


def validate_neo4j(results_dir: Path) -> None:
    raw = read_rows(results_dir / "neo4j_load_raw.csv")
    require(len(raw) == 76, "Neo4j: expected 76 raw loading rows")
    require(all(row["exit_code"] == "0" for row in raw), "Neo4j: failed load")

    dimensions = ("size", "mode", "variant")
    groups = grouped(raw, dimensions)
    require(len(groups) == 16, "Neo4j: expected 16 configuration groups")
    normal_key = ("0.5mb", "normal", "1")
    require(set(groups) - {normal_key}, "Neo4j: batched groups are missing")
    require(len(groups[normal_key]) == 1, "Neo4j: baseline must have one run")
    for key, rows in groups.items():
        expected = 1 if key == normal_key else 5
        require(len(rows) == expected, f"Neo4j: wrong repetitions for {key}")
        for field in ("cypher_bytes", "nodes", "relationships"):
            require(
                len({row[field] for row in rows}) == 1,
                f"Neo4j: varying {field} for {key}",
            )

    batched = {key for key in groups if key[1] == "large-file"}
    require(len(batched) == 15, "Neo4j: expected 15 batched groups")
    require(
        all(len(groups[key]) == 5 for key in batched),
        "Neo4j: every batched group must contain five runs",
    )

    summary = read_rows(results_dir / "neo4j_load_summary.csv")
    require(len(summary) == 16, "Neo4j: expected 16 summary rows")
    summary_groups = grouped(summary, dimensions)
    require(set(summary_groups) == set(groups), "Neo4j: summary groups differ")
    print("Neo4j: 75 batched loads and one monolithic baseline validated")


def main() -> int:
    try:
        synthetic = ROOT / "experiments" / "results"
        bkr = ROOT / "experiments" / "starbench" / "results"
        validate_datasets(synthetic)
        validate_conversion(synthetic, "Synthetic workload")
        validate_neo4j(synthetic)
        validate_datasets(bkr)
        validate_conversion(bkr, "BKR/REF workload")
    except ValidationError as exc:
        print(f"result validation failed: {exc}", file=sys.stderr)
        return 1
    print("All checked-in result artifacts are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
