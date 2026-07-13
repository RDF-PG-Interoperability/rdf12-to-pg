CREATE
  (`Person`:`IRI` {`referenceId`: "Person"}),
  (`alice`:`IRI` {`referenceId`: "alice"}),
  (`bob`:`IRI` {`referenceId`: "bob"}),
  (`carol`:`IRI` {`referenceId`: "carol"}),
  (`bob`)-[`e1`:`knows` {`asserted`: true}]->(`alice`),
  (`alice`)-[`e2`:`knows` {`asserted`: true}]->(`carol`),
  (`bob`)-[`e3`:`rdf:type` {`asserted`: true}]->(`Person`);
