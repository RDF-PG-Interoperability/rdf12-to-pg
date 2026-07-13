CREATE
  (`Warsaw`:`IRI` {`referenceId`: "Warsaw"}),
  (`alice`:`IRI` {`referenceId`: "alice"}),
  (`genid0`:`BNode` {`referenceId`: "_:genid0"}),
  (`lit_1`:`Literal` {`datatype`: "xsd:string", `referenceId`: "lit_1", `value`: "Main Street"}),
  (`lit_2`:`Literal` {`datatype`: "xsd:integer", `referenceId`: "lit_2", `value`: "10"}),
  (`sensorA`:`IRI` {`referenceId`: "sensorA"}),
  (`source1`:`BNode` {`referenceId`: "_:source1"}),
  (`genid0`)-[`e1`:`street` {`asserted`: true}]->(`lit_1`),
  (`genid0`)-[`e2`:`number` {`asserted`: true}]->(`lit_2`),
  (`genid0`)-[`e3`:`city` {`asserted`: true}]->(`Warsaw`),
  (`alice`)-[`e4`:`address` {`asserted`: true}]->(`genid0`),
  (`source1`)-[`e5`:`generatedBy` {`asserted`: true}]->(`sensorA`);
