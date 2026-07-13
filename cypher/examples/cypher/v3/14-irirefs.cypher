CREATE
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`ex_alice`:`IRI` {`referenceId`: "ex:alice"}),
  (`ex_bob`:`IRI` {`referenceId`: "ex:bob"}),
  (`ex_bob`)-[`e1`:`ex:knows`]->(`ex_alice`),
  (`ex_bob`)-[`e2`:`ex:homepage`]->(`bob`);
