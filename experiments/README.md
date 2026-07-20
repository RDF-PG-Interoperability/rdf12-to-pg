# Experimental evaluation

This directory contains the complete measurement harness, evaluated input
samples, and canonical CSV results for the synthetic and BKR/REF workloads.
Measurement reports are written exclusively as CSV files.

## Contents

| Path | Purpose |
| --- | --- |
| `run_experiments.py` | Synthetic dataset generation, conversion measurements, Neo4j loading, and CSV summaries |
| `generate_starbench_samples.py` | Deterministic sampling and RDF-star-to-RDF-1.2 migration of BKR/REF records |
| `run_starbench_experiments.py` | Conversion-only measurements over the migrated BKR/REF samples |
| `validate_results.py` | Read-only validation of the checked-in datasets and result CSVs |
| `data/` | Five deterministic synthetic Turtle inputs |
| `results/` | Synthetic conversion and Neo4j raw/summary CSVs |
| `starbench/data/` | Five migrated BKR/REF Turtle samples |
| `starbench/results/` | BKR/REF conversion raw/summary CSVs |

Downloaded Neo4j files, the full BKR dump, generated Cypher/YARS-PG, logs, and
temporary files are intentionally ignored by Git.

## Published measurement protocol

### Environment

The checked-in results were collected on:

- Intel Core Ultra 7 265, 20 cores and 20 hardware threads;
- 30 GiB RAM;
- Linux kernel `6.17.0-1028-oem`;
- Python 3.12.3;
- OpenJDK 21.0.11;
- Neo4j Community 2026.06.0.

Processes were not pinned to cores. Swap was available but remained unused
during the campaign.

### Conversion measurements

Each conversion starts a fresh CLI process through GNU `time`:

```text
/usr/bin/time -f "TIME\t%e\t%M" ...
```

`time_s` is elapsed wall-clock time and covers parsing, translation,
serialization, and writing the output file. `peak_kb` is GNU `time`'s maximum
resident-set value, reported in KiB on Linux. It measures the converter process,
not Neo4j.

For each workload, the harness measures:

- five input sizes;
- three mapping variants;
- YARS-PG, monolithic Cypher, and batched Cypher;
- ten runs per configuration;
- a 3,600-second per-process timeout;
- batch size 1,000 for batched Cypher;
- fixed and open folding, measured separately for variant 2.

This yields 600 conversion rows per workload.

### Neo4j loading measurements

Neo4j loading is evaluated only for the synthetic inputs. The harness:

- downloads Neo4j Community 2026.06.0 from the official distribution server;
- verifies SHA-256
  `1dcf62e7e8035e71732b86532b9f8e3219ce8956bd06940d5a0024696727192a`;
- binds Bolt and HTTP to `127.0.0.1`;
- disables authentication;
- configures an 8 GiB initial and maximum heap;
- times `cypher-shell`, excluding Cypher generation and database clearing;
- runs every batched size/configuration combination five times, with fixed and
  open folding measured separately for variant 2;
- runs one monolithic baseline: Maxime at 0.5 MB.

The `peak_kb` field for these rows belongs to `cypher-shell`; it is not Neo4j
server memory.

Before each load, the harness executes `MATCH (n) DETACH DELETE n`. This removes
nodes and relationships but retains schema and page cache. The batched script's
uniqueness constraint therefore remains after its first creation. Load order is
fixed and caches are not flushed, so the repetitions are not fully independent.

**Safety:** authentication is disabled only for the harness-managed instance,
which listens on loopback. Do not expose its ports to an untrusted network.

## Validate the published artifacts

This command is read-only and does not run benchmarks:

```bash
python3 experiments/validate_results.py
```

It checks dataset paths and sizes, successful exit codes, configuration counts,
repetition counts, stable serialized sizes, and agreement between raw and
summary groups. During the result refresh, it accepts either the complete
fixed-only matrix or the complete fixed/open matrix; partial combinations are
rejected.

## Generate LaTeX charts

The chart generator treats fixed and open folding as separate series. A full
fixed/open summary CSV contains 60 rows. Generate standalone LaTeX sources and,
when `pdflatex` is installed, PDF charts with:

```bash
python3 experiments/generate_latex_chart_from_csv_data.py \
  experiments/results/conversion_summary.csv \
  --output-dir experiments/charts/synthetic \
  --title "Synthetic workload" \
  --compile
```

By default it creates charts for conversion time, peak RSS, and output size.
The generator requires the complete fixed/open matrix and reports missing
combinations instead of silently merging folding forms.

## Reproduce the synthetic workload

Prerequisites are Python 3.10+, GNU `time`, `tar`, a compatible Java 21 runtime,
at least 8 GiB available for the configured Neo4j heap, and free local ports
7474 and 7687.

The following commands **overwrite the corresponding CSV files**.

Conversions only (`n=10`):

```bash
python3 experiments/run_experiments.py \
  --phase convert --runs 10 --batch-size 1000 --timeout 3600
```

Neo4j loading (`n=5` batched, one monolithic baseline):

```bash
python3 experiments/run_experiments.py \
  --phase neo4j --batch-size 1000 --timeout 3600
```

Rebuild summary CSVs without running measurements:

```bash
python3 experiments/run_experiments.py --phase summarize
```

`--phase all` executes conversions followed by Neo4j loading. `--runs` controls
conversion repetitions only; Neo4j repetitions are deliberately fixed by the
published protocol.

## Reproduce the BKR/REF workload

The full source dump is not committed. Download version 0.2 from
[Zenodo 10.5281/zenodo.4148888](https://doi.org/10.5281/zenodo.4148888), save
`BKR-star-fullKGdump.ttls.gz` under `experiments/starbench/source/`, and verify
MD5 `eb91d948b94c3d7607c4f07650433e16`.

Regenerate the five samples:

```bash
python3 experiments/generate_starbench_samples.py
```

The source uses earlier RDF-star syntax in which an embedded triple appears in
subject position. The sampler rewrites each selected record to a fresh,
deterministically named reifier with an `rdf:reifies` triple term in object
position. This mechanically retains the proposition terms and provenance
values, but changes graph structure and query patterns; no general query
equivalence is claimed.

Samples are built independently by scanning source-ordered complete records and
skipping a record when adding it would exceed the target byte limit. They are
deterministic but are not nested prefixes of one another.

Run conversion measurements (`n=10`):

```bash
python3 experiments/run_starbench_experiments.py \
  --phase convert --runs 10 --batch-size 1000 --timeout 3600
```

Rebuild only the BKR summary CSV:

```bash
python3 experiments/run_starbench_experiments.py --phase summarize
```

This workload does not execute StarBench queries, measure Neo4j loading, or
measure full-dump throughput.

## Result files and units

Synthetic results are documented in [`results/README.md`](results/README.md).
BKR/REF results are documented in
[`starbench/results/README.md`](starbench/results/README.md).

File sizes are bytes in the CSVs (decimal MB in the paper). `peak_kb` is KiB as
reported by GNU `time`; divide by 1,024 for MiB. Summary files contain arithmetic
mean, minimum, maximum, and sample standard deviation. The historical `avg` and
`mean` columns are aliases with the same value.
