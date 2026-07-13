CREATE
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`source1`:`IRI` {`referenceId`: "source1"}),
  (`source2`:`IRI` {`referenceId`: "source2"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: false, `referenceProperty`: "generatedBy", `references`: "source1"}]->(`cheese`),
  (`moon`)-[`e2`:`made_of` {`asserted`: false, `referenceProperty`: "generatedBy", `references`: "source2"}]->(`cheese`);
