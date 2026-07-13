CREATE
  (`asserts`:`IRI` {`referenceId`: "asserts"}),
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`reifies`:`IRI` {`referenceId`: "rdf:reifies"}),
  (`tt_1`:`TripleTerm` {`referenceId`: "tt_1"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: false, `referenceProperty`: "said_by", `references`: "bob"}]->(`cheese`),
  (`moon`)-[`e2`:`made_of` {`asserted`: false, `referenceProperty`: "asserts", `references`: "tt_1"}]->(`cheese`),
  (`asserts`)-[`e3`:`rdfs:subPropertyOf` {`asserted`: true}]->(`reifies`);
