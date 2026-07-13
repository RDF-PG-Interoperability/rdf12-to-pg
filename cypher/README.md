# RDF 1.2 Turtle to Cypher

Standalone Python converter from RDF 1.2 Turtle to Cypher for Neo4j. It
implements the three mapping variants evaluated in this repository and can emit
either one monolithic `CREATE` statement or a sequence of load-oriented batched
statements.

The converter generates Cypher; it does not connect to Neo4j itself. Database
loading and measurement are implemented by
[`experiments/run_experiments.py`](../experiments/run_experiments.py).

## Requirements and installation

- Python 3.10 or newer.
- No third-party runtime dependencies.

Run directly from a checkout:

```bash
./rdf12_to_neo4j --variant 3 examples/ttl/06-rdf-reifies.ttl
```

Install the CLI locally:

```bash
python3 -m pip install -e .
rdf12-to-cypher --variant 3 examples/ttl/06-rdf-reifies.ttl
```

## Usage

Write monolithic Cypher to a file:

```bash
rdf12-to-cypher --variant 1 input.ttl -o output.cypher
```

Read Turtle from standard input:

```bash
rdf12-to-cypher --variant 2 < input.ttl
```

Generate batched Cypher:

```bash
rdf12-to-cypher --variant 3 --large-file --batch-size 1000 \
  input.ttl -o output.cypher
```

Load a generated script into a running Neo4j instance:

```bash
cypher-shell -a bolt://127.0.0.1:7687 -f output.cypher
```

Authentication arguments may be required by your Neo4j configuration.

## Mapping variants

| Value | Translation | Behaviour |
| --- | --- | --- |
| `1` | Maxime | Interprets `rdf:reifies`; reifiers become `Reifier` nodes and represented relationships carry `reifiedBy` and `asserted` |
| `2` | Katja | Omits reifier nodes and folds annotations into represented relationships |
| `3` | Ruben | Retains every parsed triple, creates `TripleTerm` nodes, and links represented relationships with `in` |

Variant 3 is the default because it is the most explicit representation.
Variant 2 accepts `--folding fixed` (default) or `--folding open`. Fixed folding
creates one relationship record per annotation; open folding stores all
annotations in one relationship record.

Every generated node has the reserved `referenceId` property used by the
translation model.

## Output modes

### Monolithic mode

The default mode writes the complete graph as one `CREATE` statement. It is
compact and convenient for inspection, but large statements can be expensive
for Neo4j to parse, plan, and execute as one transaction.

### Batched mode

`--large-file` emits multiple `UNWIND` batches. It spools generated graph state
and uses on-disk indexes for variants 1 and 3, which reduced converter RSS in
the evaluated workloads. The Turtle source is still read as a complete text
value, so this is not an end-to-end streaming or bounded-memory parser.

Batched scripts add loader-specific schema that is not part of the conceptual
translations:

- label `RDF12Node`;
- property `rdf12_id`;
- uniqueness constraint `rdf12node_id`.

The property and constraint provide indexed node lookup while relationships are
created. The constraint remains in the database until explicitly removed.

## Examples

`examples/ttl/` contains 15 RDF 1.2 inputs. `examples/cypher/v1/`, `v2/`, and
`v3/` contain the corresponding generated snapshots.

Regenerate them from the project directory:

```bash
for file in examples/ttl/*.ttl; do
  name=$(basename "$file" .ttl)
  for variant in 1 2 3; do
    ./rdf12_to_neo4j --variant "$variant" "$file" \
      -o "examples/cypher/v${variant}/${name}.cypher"
  done
done
```

## Development checks

```bash
python3 -m pip install -e '.[dev]'
python3 -m ruff check .
python3 -m unittest discover -s tests
```

The bundled RDF 1.2 parser is based on
[rdf12conv 0.3.0](https://github.com/domel/rdf12conv); see the repository's
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
