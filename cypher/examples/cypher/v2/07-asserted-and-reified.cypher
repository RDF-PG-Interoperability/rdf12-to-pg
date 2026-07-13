CREATE
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: true}]->(`cheese`);
