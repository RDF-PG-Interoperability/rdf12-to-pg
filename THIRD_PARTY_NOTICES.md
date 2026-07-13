# Third-party notices

## rdf12conv

The files `cypher/rdf12_to_neo4j_lib/rdf_converter.py` and
`yarspg/rdf12_to_yarspg_lib/rdf_converter.py` are based on
[rdf12conv 0.3.0](https://github.com/domel/rdf12conv), with local terminology
updates. rdf12conv is Copyright (c) 2026 Dominik Tomaszuk and is distributed
under the MIT License included in this repository.

## BKR/REF data

The files under `experiments/starbench/data/` are deterministic samples derived
from version 0.2 of the RDF-star representation of the Biomedical Knowledge
Repository in the REF benchmark dataset:

- Fabrizio Orlandi, Damien Graux, and Declan O'Sullivan, ADAPT Centre, Trinity
  College Dublin.
- Source: [Zenodo record 10.5281/zenodo.4148888](https://doi.org/10.5281/zenodo.4148888).
- Source file: `BKR-star-fullKGdump.ttls.gz`, MD5
  `eb91d948b94c3d7607c4f07650433e16`.
- License: Apache License 2.0; a copy is provided in
  `LICENSES/Apache-2.0.txt`.

The checked-in files are modified data. Source RDF-star records were sampled
deterministically and mechanically migrated to RDF 1.2 reifier records. This
migration changes the graph structure and associated query patterns; no general
query-equivalence claim is made.

## Neo4j

Neo4j is not redistributed in this repository. The experiment harness can
download a checksum-pinned Neo4j Community archive from the official Neo4j
distribution server. That download is governed by Neo4j's own license terms.
