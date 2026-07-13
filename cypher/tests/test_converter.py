import subprocess
import unittest
from pathlib import Path

from rdf12_to_neo4j import convert, convert_large


ROOT = Path(__file__).resolve().parents[1]


PREFIXES = """\
@prefix : <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
"""


class ConverterTests(unittest.TestCase):
    def test_variant_1_uses_reifier_nodes_and_updates_assertedness(self) -> None:
        cypher = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim2 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim1 :statedBy :alice .
:moon :made_of :cheese .
""",
            variant=1,
        )

        self.assertIn('(`claim1`:`Reifier` {`referenceId`: "_:claim1"})', cypher)
        self.assertIn('(`claim2`:`Reifier` {`referenceId`: "_:claim2"})', cypher)
        self.assertIn('{`asserted`: true, `reifiedBy`: "_:claim1"}', cypher)
        self.assertIn('{`asserted`: true, `reifiedBy`: "_:claim2"}', cypher)
        self.assertIn(
            "(`claim1`)-[`e3`:`statedBy` {`asserted`: true}]->(`alice`)",
            cypher,
        )
        self.assertNotIn(":`rdf:reifies`", cypher)
        self.assertNotIn(":`TripleTerm`", cypher)

    def test_variant_1_keeps_unasserted_triple_term_edge_false(self) -> None:
        cypher = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
""",
            variant=1,
        )

        self.assertIn(
            '{`asserted`: false, `reifiedBy`: "_:claim1"}',
            cypher,
        )

    def test_variant_2_fixed_folds_subject_annotations(self) -> None:
        cypher = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim1 :statedBy :alice .
_:claim1 :certainty 0.8 .
:bob :trusts _:claim1 .
:moon :made_of :cheese .
""",
            variant=2,
        )

        self.assertEqual(cypher.count("(`moon`)-["), 2)
        self.assertIn('`referenceProperty`: "statedBy"', cypher)
        self.assertIn('`references`: "alice"', cypher)
        self.assertIn('`referenceProperty`: "certainty"', cypher)
        self.assertIn("`asserted`: true", cypher)
        self.assertNotIn(":`trusts`", cypher)
        self.assertNotIn(":`statedBy`", cypher)
        self.assertNotIn("(`claim1`", cypher)

    def test_variant_2_open_folds_all_annotations_into_one_record(self) -> None:
        cypher = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim1 :statedBy :alice .
_:claim1 :certainty 0.8 .
""",
            variant=2,
            folding="open",
        )

        self.assertEqual(cypher.count("(`moon`)-["), 1)
        self.assertIn("`asserted`: false", cypher)
        self.assertIn('`certainty`: "lit_1"', cypher)
        self.assertIn('`statedBy`: "alice"', cypher)
        self.assertNotIn("`referenceProperty`", cypher)

    def test_variant_2_fixed_emits_bare_unasserted_edge(self) -> None:
        cypher = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
""",
            variant=2,
        )

        self.assertIn(
            "(`moon`)-[`e1`:`made_of` {`asserted`: false}]->(`cheese`)",
            cypher,
        )
        self.assertNotIn("`references`", cypher)

    def test_variant_3_nested_triple_terms(self) -> None:
        cypher = convert(
            """\
@prefix : <http://example.org/> .

:a :b <<(
    :s1 :p1 <<(
        :s2 :p2 <<(
            :s3 :p3 :o3
        )>>
    )>>
)>> .
""",
            variant=3,
        )

        self.assertIn('(`tt_1`:`TripleTerm` {`referenceId`: "tt_1"})', cypher)
        self.assertIn('(`tt_2`:`TripleTerm` {`referenceId`: "tt_2"})', cypher)
        self.assertIn('(`tt_3`:`TripleTerm` {`referenceId`: "tt_3"})', cypher)
        self.assertIn("(`a`)-[`e1`:`b`]->(`tt_1`)", cypher)
        self.assertIn('(`s3`)-[`e4`:`p3` {`in`: "tt_3"}]->(`o3`)', cypher)

    def test_variant_3_emits_shared_triple_term_once(self) -> None:
        cypher = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim2 rdf:reifies <<( :moon :made_of :cheese )>> .
""",
            variant=3,
        )

        self.assertEqual(cypher.count(":`TripleTerm`"), 1)
        self.assertEqual(cypher.count('{`in`: "tt_1"}'), 1)
        self.assertEqual(cypher.count(":`rdf:reifies`"), 2)

    def test_all_nodes_carry_reference_id(self) -> None:
        cypher = convert(
            PREFIXES + ':subject :predicate "value" .\n',
            variant=3,
        )

        node_entries = [
            line
            for line in cypher.splitlines()
            if line.startswith("  (`") and ")-[`" not in line
        ]
        self.assertTrue(node_entries)
        self.assertTrue(all("`referenceId`" in line for line in node_entries))

    def test_cypher_identifiers_are_escaped(self) -> None:
        cypher = convert(
            """\
@prefix ex: <http://example.org/> .

ex:subject ex:predicate ex:object .
""",
            variant=3,
        )

        self.assertIn('(`ex_subject`:`IRI` {`referenceId`: "ex:subject"})', cypher)
        self.assertIn("(`ex_subject`)-[`e1`:`ex:predicate`]->(`ex_object`)", cypher)

    def test_default_cli_output_matches_checked_in_examples(self) -> None:
        for ttl in sorted((ROOT / "examples" / "ttl").glob("*.ttl")):
            for variant in (1, 2, 3):
                expected = (
                    ROOT / "examples" / "cypher" / f"v{variant}" / f"{ttl.stem}.cypher"
                ).read_text(encoding="utf-8")
                actual = subprocess.check_output(
                    [
                        str(ROOT / "rdf12_to_neo4j"),
                        "--variant",
                        str(variant),
                        str(ttl),
                    ],
                    text=True,
                    cwd=ROOT,
                )
                self.assertEqual(expected, actual)

    def test_large_file_variant_1_uses_batched_cypher(self) -> None:
        cypher = convert_large(
            (ROOT / "examples" / "ttl" / "07-asserted-and-reified.ttl").read_text(
                encoding="utf-8"
            ),
            variant=1,
            batch_size=2,
        )

        assert cypher is not None
        self.assertIn("CREATE CONSTRAINT rdf12node_id IF NOT EXISTS", cypher)
        self.assertIn("UNWIND [", cypher)
        self.assertIn("MERGE (n:`RDF12Node` {`rdf12_id`: row.id})", cypher)
        self.assertIn("`asserted`: true", cypher)
        self.assertIn('`reifiedBy`: "_:claim1"', cypher)
        self.assertIn("SET n:`Reifier`", cypher)

    def test_large_file_variant_2_uses_batched_cypher(self) -> None:
        cypher = convert_large(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim1 :saidBy :bob .
""",
            variant=2,
            batch_size=2,
        )

        assert cypher is not None
        self.assertIn("UNWIND [", cypher)
        self.assertIn('`referenceProperty`: "saidBy"', cypher)
        self.assertIn('`references`: "bob"', cypher)
        self.assertIn("`asserted`: false", cypher)

    def test_large_file_variant_3_uses_batched_cypher(self) -> None:
        cypher = convert_large(
            PREFIXES
            + """
:bob :said <<( :moon :made_of :cheese )>> .
""",
            variant=3,
            batch_size=1,
        )

        assert cypher is not None
        self.assertIn("UNWIND [", cypher)
        self.assertIn("SET n:`TripleTerm`", cypher)
        self.assertIn("CREATE (s)-[r:`made_of`]->(o)", cypher)


if __name__ == "__main__":
    unittest.main()
