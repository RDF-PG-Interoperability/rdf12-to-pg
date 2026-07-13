# RDF 1.2 to Property Graph

[![Checks](https://github.com/domel/rdf12-to-pg/actions/workflows/checks.yml/badge.svg)](https://github.com/domel/rdf12-to-pg/actions/workflows/checks.yml)

Research implementations and reproducibility artifacts for translating RDF 1.2
Turtle into property-graph representations. This repository contains both
serializers used in the evaluation, the deterministic synthetic-data generator,
the Neo4j loading harness, the evaluated input samples, and the raw and
aggregated results.

## Repository contents

| Path | Purpose |
| --- | --- |
| [`cypher/`](cypher/) | RDF 1.2 Turtle to monolithic or batched Cypher |
| [`yarspg/`](yarspg/) | RDF 1.2 Turtle to textual YARS-PG |
| [`synthetic-generator/`](synthetic-generator/) | Deterministic synthetic RDF 1.2 Turtle generator |
| [`experiments/`](experiments/) | Conversion measurements, Neo4j loading, BKR/REF sampling, and published CSV results |

All runtime tools are implemented in Python and require Python 3.10 or newer.
The converters and generator have no third-party runtime dependencies.

## Mapping variants

The command-line option `--variant` uses the implementation numbering from the
evaluation artifact:

| CLI value | Translation | Summary |
| --- | --- | --- |
| `1` | Maxime | Interprets `rdf:reifies` and represents reifiers explicitly |
| `2` | Katja | Folds reifier annotations; fixed folding is the default |
| `3` | Ruben | Explicitly materializes triple terms and retains every parsed RDF triple |

## Quick start

Run directly from a checkout:

```bash
./cypher/rdf12_to_neo4j --variant 3 \
  cypher/examples/ttl/06-rdf-reifies.ttl -o /tmp/example.cypher

./yarspg/rdf12_to_yarspg --variant 3 \
  yarspg/examples/06-rdf-reifies.ttl -o /tmp/example.yarspg

./synthetic-generator/synthetic_gen --profile all --count 2 --seed 7 \
  -o /tmp/synthetic.ttl
```

Or install the three CLIs in editable mode:

```bash
python3 -m pip install -e ./cypher -e ./yarspg -e ./synthetic-generator
rdf12-to-cypher --help
rdf12-to-yarspg --help
rdf12-synthetic --help
```

## Published results

The repository includes the measurements used by the evaluation. No benchmark
needs to be rerun to inspect or validate them.

| Workload | Measurements | Repetitions |
| --- | ---: | --- |
| Synthetic conversion | 450 | 5 sizes × 9 configurations × 10 runs |
| BKR/REF conversion | 450 | 5 sizes × 9 configurations × 10 runs |
| Batched Neo4j loading | 75 | 5 sizes × 3 variants × 5 runs |
| Monolithic Neo4j baseline | 1 | Maxime, 0.5 MB |

Validate the checked-in datasets and CSV structure without running experiments:

```bash
python3 experiments/validate_results.py
```

See [`experiments/README.md`](experiments/README.md) for the measurement scope,
environment, result-file schema, and full reproduction commands.

## License and data attribution

Repository software is available under the [MIT License](LICENSE). The migrated
BKR/REF samples retain the source dataset's Apache-2.0 terms. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and
[`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt) for details.
