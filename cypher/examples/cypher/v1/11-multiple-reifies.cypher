CREATE
  (`cheese`:`IRI` {`referenceId`: "cheese"}),
  (`claim1`:`Reifier` {`referenceId`: "_:claim1"}),
  (`claim2`:`Reifier` {`referenceId`: "_:claim2"}),
  (`moon`:`IRI` {`referenceId`: "moon"}),
  (`source1`:`IRI` {`referenceId`: "source1"}),
  (`source2`:`IRI` {`referenceId`: "source2"}),
  (`moon`)-[`e1`:`made_of` {`asserted`: false, `reifiedBy`: "_:claim1"}]->(`cheese`),
  (`moon`)-[`e2`:`made_of` {`asserted`: false, `reifiedBy`: "_:claim2"}]->(`cheese`),
  (`claim1`)-[`e3`:`generatedBy` {`asserted`: true}]->(`source1`),
  (`claim2`)-[`e4`:`generatedBy` {`asserted`: true}]->(`source2`);
