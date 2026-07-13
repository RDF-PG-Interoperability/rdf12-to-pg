CREATE
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`popcorn`:`IRI` {`referenceId`: "popcorn"}),
  (`sun`:`IRI` {`referenceId`: "sun"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: false}]->(`cheese`),
  (`sun`)-[`e2`:`made_of` {`asserted`: false}]->(`popcorn`);
