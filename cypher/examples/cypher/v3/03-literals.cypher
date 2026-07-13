CREATE
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`lit_1`:`Literal` {`datatype`: "xsd:string", `language`: "en", `referenceId`: "lit_1", `value`: "Bob"}),
  (`lit_2`:`Literal` {`datatype`: "xsd:integer", `referenceId`: "lit_2", `value`: "42"}),
  (`lit_3`:`Literal` {`datatype`: "xsd:decimal", `referenceId`: "lit_3", `value`: "1.82"}),
  (`lit_4`:`Literal` {`datatype`: "xsd:double", `referenceId`: "lit_4", `value`: "7.5e1"}),
  (`lit_5`:`Literal` {`datatype`: "xsd:boolean", `referenceId`: "lit_5", `value`: "true"}),
  (`lit_6`:`Literal` {`datatype`: "xsd:date", `referenceId`: "lit_6", `value`: "1980-05-12"}),
  (`bob`)-[`e1`:`name`]->(`lit_1`),
  (`bob`)-[`e2`:`age`]->(`lit_2`),
  (`bob`)-[`e3`:`height`]->(`lit_3`),
  (`bob`)-[`e4`:`score`]->(`lit_4`),
  (`bob`)-[`e5`:`active`]->(`lit_5`),
  (`bob`)-[`e6`:`born`]->(`lit_6`);
