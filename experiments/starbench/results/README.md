# BKR/REF workload results

These CSV files are the canonical published conversion results for the migrated
BKR/REF samples used as a StarBench-shaped provenance workload.

| File | Contents |
| --- | --- |
| `datasets.csv` | Reifier count, relative input path, bytes, lines, and parsed graph triples |
| `conversion_raw.csv` | 450 individual converter runs |
| `conversion_summary.csv` | 45 conversion configurations aggregated over ten runs |

All recorded runs have exit code zero. This workload measures conversion only;
it does not include Neo4j loading, StarBench query execution, or full-dump
throughput. Generated `.cypher` and `.yarspg` files are omitted because they can
be reproduced from the checked-in samples.

The source attribution and modification notice are in
[`THIRD_PARTY_NOTICES.md`](../../../THIRD_PARTY_NOTICES.md).
