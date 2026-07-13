CREATE
  (`basketball`:`IRI` {`referenceId`: "basketball"}),
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: false}]->(`cheese`),
  (`bob`)-[`e2`:`played` {`asserted`: true}]->(`basketball`);
