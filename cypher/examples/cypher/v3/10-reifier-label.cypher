CREATE
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`label`:`IRI` {`referenceId`: "label"}),
  (`lit_1`:`Literal` {`datatype`: "xsd:decimal", `referenceId`: "lit_1", `value`: "0.8"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`tt_1`:`TripleTerm` {`referenceId`: "tt_1"}),
  (`x`:`IRI` {`referenceId`: "x"}),
  (`label`)-[`e1`:`rdf:reifies`]->(`tt_1`),
  (`moon`)-[`e2`:`made_of` {`in`: "tt_1"}]->(`cheese`),
  (`x`)-[`e3`:`y`]->(`label`),
  (`label`)-[`e4`:`confidence`]->(`lit_1`);
