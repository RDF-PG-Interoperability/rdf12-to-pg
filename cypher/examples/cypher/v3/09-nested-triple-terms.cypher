CREATE
  (`a`:`IRI` {`referenceId`: "a"}),
  (`o3`:`IRI` {`referenceId`: "o3"}),
  (`s1`:`IRI` {`referenceId`: "s1"}),
  (`s2`:`IRI` {`referenceId`: "s2"}),
  (`s3`:`IRI` {`referenceId`: "s3"}),
  (`tt_1`:`TripleTerm` {`referenceId`: "tt_1"}),
  (`tt_2`:`TripleTerm` {`referenceId`: "tt_2"}),
  (`tt_3`:`TripleTerm` {`referenceId`: "tt_3"}),
  (`a`)-[`e1`:`b`]->(`tt_1`),
  (`s1`)-[`e2`:`p1` {`in`: "tt_1"}]->(`tt_2`),
  (`s2`)-[`e3`:`p2` {`in`: "tt_2"}]->(`tt_3`),
  (`s3`)-[`e4`:`p3` {`in`: "tt_3"}]->(`o3`);
