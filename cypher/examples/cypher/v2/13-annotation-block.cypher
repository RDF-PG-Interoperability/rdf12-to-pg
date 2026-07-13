CREATE
  (`alice`:`IRI` {`referenceId`: "alice"}),
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`lit_1`:`Literal` {`datatype`: "xsd:decimal", `referenceId`: "lit_1", `value`: "0.9"}),
  (`pasta`:`IRI` {`referenceId`: "pasta"}),
  (`pizza`:`IRI` {`referenceId`: "pizza"}),
  (`survey1`:`IRI` {`referenceId`: "survey1"}),
  (`survey2`:`IRI` {`referenceId`: "survey2"}),
  (`bob`)-[`e1`:`likes` {`asserted`: true, `referenceProperty`: "certainty", `references`: "lit_1"}]->(`pizza`),
  (`bob`)-[`e2`:`likes` {`asserted`: true, `referenceProperty`: "source", `references`: "survey1"}]->(`pizza`),
  (`alice`)-[`e3`:`likes` {`asserted`: true, `referenceProperty`: "source", `references`: "survey2"}]->(`pasta`);
