# RDF 1.2 Turtle to YARS-PG

Standalone Python converter from RDF 1.2 Turtle to textual YARS-PG. It
implements the same three mapping variants as the Cypher converter and emits a
deterministic node-and-edge representation suitable for inspection and
comparison.

## Requirements and installation

- Python 3.10 or newer.
- No third-party runtime dependencies.

Run from a checkout:

```bash
./rdf12_to_yarspg --variant 3 examples/06-rdf-reifies.ttl
```

Install the CLI locally:

```bash
python3 -m pip install -e .
rdf12-to-yarspg --variant 3 examples/06-rdf-reifies.ttl
```

## Usage

Write output to a file:

```bash
rdf12-to-yarspg --variant 1 input.ttl -o output.yarspg
```

Read Turtle from standard input:

```bash
rdf12-to-yarspg --variant 2 < input.ttl
```

The compatibility entry point `python3 turtle_to_yarspg.py ...` remains
available.

Output contains `# Nodes` and `# Edges` sections. For example:

```text
# Nodes
(moon {"IRI"}["referenceId": "moon"])

# Edges
(moon)-(e1 {"made_of"})->(cheese)
```

## Mapping variants

| Value | Translation | Behaviour |
| --- | --- | --- |
| `1` | Maxime | Interprets `rdf:reifies`; reifiers become nodes and represented edges carry `reifiedBy` and `asserted` |
| `2` | Katja | Omits reifier nodes and folds annotations into represented edge properties |
| `3` | Ruben | Retains every parsed triple, creates `TripleTerm` nodes, and links represented edges with `in` |

Variant 3 is the default and most explicit representation. Variant 2 supports
`--folding fixed` (default) and `--folding open`.

Every generated node has the reserved `referenceId` property used by the
translation model. YARS-PG output has no batched mode: `--large-file` is a
Cypher-specific serialization and loading strategy.

## Examples

`examples/` contains 15 RDF 1.2 inputs. `out/` contains checked-in snapshots for
all three variants.

Regenerate the snapshots from the project directory:

```bash
for file in examples/*.ttl; do
  name=$(basename "$file" .ttl)
  for variant in 1 2 3; do
    ./rdf12_to_yarspg --variant "$variant" "$file" \
      -o "out/${name}-v${variant}.yarspg"
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
