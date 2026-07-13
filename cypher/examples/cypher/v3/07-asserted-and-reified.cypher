CREATE
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`claim1`:`BNode` {`referenceId`: "_:claim1"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`tt_1`:`TripleTerm` {`referenceId`: "tt_1"}),
  (`claim1`)-[`e1`:`rdf:reifies`]->(`tt_1`),
  (`moon`)-[`e2`:`made_of` {`in`: "tt_1"}]->(`cheese`),
  (`bob`)-[`e3`:`said`]->(`claim1`),
  (`moon`)-[`e4`:`made_of`]->(`cheese`);
