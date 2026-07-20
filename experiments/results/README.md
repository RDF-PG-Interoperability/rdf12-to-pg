# Synthetic workload results

These CSV files are the canonical published results for the synthetic workload.

| File | Contents |
| --- | --- |
| `datasets.csv` | Scale factor, relative input path, bytes, lines, and parsed graph triples |
| `conversion_raw.csv` | 600 individual converter runs |
| `conversion_summary.csv` | 60 conversion configurations aggregated over ten runs |
| `neo4j_load_raw.csv` | 100 batched loads and one monolithic baseline |
| `neo4j_load_summary.csv` | 21 Neo4j loading configuration groups |

All recorded runs have exit code zero. `time_s` is elapsed wall-clock time.
`peak_kb` is maximum resident set size from GNU `time`; for Neo4j loading it
describes `cypher-shell`, not the Neo4j server. Generated `.cypher` and `.yarspg`
files are omitted because `output_bytes` records their sizes and they can be
regenerated from the checked-in inputs.

Validate these files without rerunning the experiments:

```bash
python3 experiments/validate_results.py
```
