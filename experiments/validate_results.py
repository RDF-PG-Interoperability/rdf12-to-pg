#!/usr/bin/env python3
"""Validate fixed/open result CSVs."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SIZES = {"0.5mb", "1mb", "1.5mb", "2mb", "2.5mb"}
OPEN_CONVERSION_FORMS = {
    (tool, mode, str(variant), folding)
    for tool, mode in (
        ("yarspg", "normal"),
        ("cypher", "normal"),
        ("cypher", "large-file"),
    )
    for variant, folding in ((1, ""), (2, "fixed"), (2, "open"), (3, ""))
}
OPEN_NEO4J_BATCHED_FORMS = {
    ("large-file", str(variant), folding)
    for variant, folding in ((1, ""), (2, "fixed"), (2, "open"), (3, ""))
}


class ValidationError(RuntimeError):
    """Raised when a published result artifact is incomplete or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def read_rows(path: Path) -> list[dict[str, str]]:
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    require(path.is_file(), f"missing CSV: {display_path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_folding(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Normalize the folding field before validating the complete matrix."""
    normalized = []
    for row in rows:
        current = dict(row)
        require("folding" in current, "result CSV is missing the folding column")
        current["folding"] = current["folding"].strip().lower()
        normalized.append(current)
    return normalized


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
    raw = normalize_folding(read_rows(results_dir / "conversion_raw.csv"))
    require(all(row["exit_code"] == "0" for row in raw), f"{label}: failed run")
    dimensions = ("size", "tool", "mode", "variant", "folding")
    groups = grouped(raw, dimensions)
    actual_forms = {(key[1], key[2], key[3], key[4]) for key in groups}
    require(actual_forms == OPEN_CONVERSION_FORMS, f"{label}: incomplete fixed/open matrix")
    expected_groups = len(SIZES) * len(OPEN_CONVERSION_FORMS)
    expected_rows = expected_groups * 10
    require(len(raw) == expected_rows, f"{label}: expected {expected_rows} raw rows")
    require(len(groups) == expected_groups, f"{label}: expected {expected_groups} groups")
    for key, rows in groups.items():
        runs = sorted(int(row["run"]) for row in rows)
        require(runs == list(range(1, 11)), f"{label}: wrong repetitions for {key}")
        require(
            len({row["output_bytes"] for row in rows}) == 1,
            f"{label}: varying output size for {key}",
        )

    summary = normalize_folding(read_rows(results_dir / "conversion_summary.csv"))
    require(len(summary) == expected_groups, f"{label}: expected {expected_groups} summaries")
    summary_groups = grouped(summary, dimensions)
    require(set(summary_groups) == set(groups), f"{label}: summary groups differ")
    require(all(row["runs"] == "10" for row in summary), f"{label}: wrong summary runs")
    print(f"{label}: {expected_rows} runs in {expected_groups} fixed/open groups validated")


def validate_neo4j(results_dir: Path) -> None:
    raw = normalize_folding(read_rows(results_dir / "neo4j_load_raw.csv"))
    require(all(row["exit_code"] == "0" for row in raw), "Neo4j: failed load")
    dimensions = ("size", "mode", "variant", "folding")
    groups = grouped(raw, dimensions)
    normal_key = ("0.5mb", "normal", "1", "")
    batched = {key for key in groups if key[1] == "large-file"}
    actual_forms = {(key[1], key[2], key[3]) for key in batched}
    require(actual_forms == OPEN_NEO4J_BATCHED_FORMS, "Neo4j: incomplete fixed/open matrix")
    expected_keys = {normal_key} | {
        (size, mode, variant, folding)
        for size in SIZES
        for mode, variant, folding in actual_forms
    }
    require(set(groups) == expected_keys, "Neo4j: loading groups differ")
    expected_groups = len(expected_keys)
    expected_rows = (expected_groups - 1) * 5 + 1
    require(len(raw) == expected_rows, f"Neo4j: expected {expected_rows} rows")
    for key, rows in groups.items():
        expected = 1 if key == normal_key else 5
        require(len(rows) == expected, f"Neo4j: wrong repetitions for {key}")
        for field in ("cypher_bytes", "nodes", "relationships"):
            require(len({row[field] for row in rows}) == 1, f"Neo4j: varying {field} for {key}")

    summary = normalize_folding(read_rows(results_dir / "neo4j_load_summary.csv"))
    require(len(summary) == expected_groups, f"Neo4j: expected {expected_groups} summaries")
    require(set(grouped(summary, dimensions)) == set(groups), "Neo4j: summary groups differ")
    print(f"Neo4j: {expected_rows - 1} fixed/open batched loads plus baseline validated")


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
