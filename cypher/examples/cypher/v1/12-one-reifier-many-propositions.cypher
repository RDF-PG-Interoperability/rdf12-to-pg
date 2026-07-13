CREATE
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`claimSet`:`Reifier` {`referenceId`: "_:claimSet"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`popcorn`:`IRI` {`referenceId`: "popcorn"}),
  (`sun`:`IRI` {`referenceId`: "sun"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: false, `reifiedBy`: "_:claimSet"}]->(`cheese`),
  (`sun`)-[`e2`:`made_of` {`asserted`: false, `reifiedBy`: "_:claimSet"}]->(`popcorn`),
  (`bob`)-[`e3`:`says` {`asserted`: true}]->(`claimSet`);
