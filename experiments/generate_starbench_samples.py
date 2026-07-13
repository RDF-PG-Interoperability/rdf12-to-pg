#!/usr/bin/env python3
"""Create deterministic RDF 1.2 samples from the BKR/REF RDF-star dump."""

from __future__ import annotations

import gzip
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/starbench/source/BKR-star-fullKGdump.ttls.gz"
OUTPUT_DIR = ROOT / "experiments/starbench/data"
SOURCE_MD5 = "eb91d948b94c3d7607c4f07650433e16"

TARGETS = (
    ("0.5mb", 500_000),
    ("1mb", 1_000_000),
    ("1.5mb", 1_500_000),
    ("2mb", 2_000_000),
    ("2.5mb", 2_500_000),
)

PREFIXES = """\
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix stardog: <tag:stardog:api:> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix : <http://api.stardog.com/> .

# Deterministic StarBench/BKR sample migrated from RDF-star to RDF 1.2.
"""

RDF_STAR_LINE = re.compile(
    r"^\s*<<\s*(?P<subject><[^>]+>)\s+"
    r"(?P<predicate><[^>]+>)\s+"
    r"(?P<object><[^>]+>)\s*>>\s+"
    r"(?P<meta_predicate><[^>]+>)\s+"
    r"(?P<meta_objects>.+)\s*\.\s*$"
)


def migrated_records() -> list[str]:
    records: list[str] = []
    pool_target = TARGETS[-1][1] * 2
    current_bytes = len(PREFIXES.encode("utf-8"))

    with gzip.open(SOURCE, "rt", encoding="utf-8") as source:
        for line in source:
            if "<<" not in line:
                continue
            match = RDF_STAR_LINE.match(line)
            if match is None:
                raise ValueError(f"Unsupported StarBench RDF-star statement: {line[:200]!r}")

            reifier = f"_:starbench_reifier_{len(records) + 1}"
            record = (
                f"{reifier} rdf:reifies <<( {match['subject']} "
                f"{match['predicate']} {match['object']} )>> .\n"
                f"{reifier} {match['meta_predicate']} {match['meta_objects']} .\n"
            )
            records.append(record)
            current_bytes += len(record.encode("utf-8"))
            if current_bytes >= pool_target:
                return records

    raise RuntimeError("The StarBench dump ended before the largest sample was built")


def file_md5(path: Path) -> str:
    """Return the MD5 digest published with the source dataset."""

    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"BKR/REF source dump not found: {SOURCE}. "
            "See experiments/README.md for download instructions."
        )
    actual_md5 = file_md5(SOURCE)
    if actual_md5 != SOURCE_MD5:
        raise RuntimeError(
            f"BKR/REF source checksum mismatch: expected {SOURCE_MD5}, got {actual_md5}"
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = migrated_records()

    for label, target_bytes in TARGETS:
        parts = [PREFIXES]
        current_bytes = len(PREFIXES.encode("utf-8"))
        for record in records:
            record_bytes = len(record.encode("utf-8"))
            if current_bytes + record_bytes <= target_bytes:
                parts.append(record)
                current_bytes += record_bytes
        output = OUTPUT_DIR / f"starbench-{label}.ttl"
        output.write_text("".join(parts), encoding="utf-8")
        print(f"{label}: {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
