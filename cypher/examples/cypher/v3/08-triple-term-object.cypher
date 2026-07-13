CREATE
  (`alice`:`IRI` {`referenceId`: "alice"}),
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`tt_1`:`TripleTerm` {`referenceId`: "tt_1"}),
  (`bob`)-[`e1`:`said`]->(`tt_1`),
  (`moon`)-[`e2`:`made_of` {`in`: "tt_1"}]->(`cheese`),
  (`alice`)-[`e3`:`denied`]->(`tt_1`);
