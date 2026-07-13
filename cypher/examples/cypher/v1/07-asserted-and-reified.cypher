CREATE
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`claim1`:`Reifier` {`referenceId`: "_:claim1"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: true, `reifiedBy`: "_:claim1"}]->(`cheese`),
  (`bob`)-[`e2`:`said` {`asserted`: true}]->(`claim1`);
