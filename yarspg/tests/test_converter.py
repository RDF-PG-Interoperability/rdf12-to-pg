import subprocess
import unittest
from pathlib import Path

from rdf12_to_yarspg import convert


ROOT = Path(__file__).resolve().parents[1]


PREFIXES = """\
@prefix : <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
"""


class ConverterTests(unittest.TestCase):
    def test_variant_1_uses_reifier_nodes_and_updates_assertedness(self) -> None:
        yarspg = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim2 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim1 :statedBy :alice .
:moon :made_of :cheese .
""",
            variant=1,
        )

        self.assertIn('(claim1 {"Reifier"}["referenceId": "_:claim1"])', yarspg)
        self.assertIn('(claim2 {"Reifier"}["referenceId": "_:claim2"])', yarspg)
        self.assertIn(
            '["asserted": "true", "reifiedBy": "_:claim1"]',
            yarspg,
        )
        self.assertIn(
            '["asserted": "true", "reifiedBy": "_:claim2"]',
            yarspg,
        )
        self.assertIn(
            '(claim1)-(e3 {"statedBy"}["asserted": "true"])->(alice)',
            yarspg,
        )
        self.assertNotIn('"rdf:reifies"', yarspg)
        self.assertNotIn('"TripleTerm"', yarspg)

    def test_variant_1_keeps_unasserted_triple_term_edge_false(self) -> None:
        yarspg = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
""",
            variant=1,
        )

        self.assertIn(
            '["asserted": "false", "reifiedBy": "_:claim1"]',
            yarspg,
        )

    def test_variant_2_fixed_folds_subject_annotations(self) -> None:
        yarspg = convert(
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

        self.assertEqual(yarspg.count("(moon)-("), 2)
        self.assertIn('"referenceProperty": "statedBy"', yarspg)
        self.assertIn('"references": "alice"', yarspg)
        self.assertIn('"referenceProperty": "certainty"', yarspg)
        self.assertIn('"asserted": "true"', yarspg)
        self.assertNotIn('{"trusts"}', yarspg)
        self.assertNotIn('{"statedBy"}', yarspg)
        self.assertNotIn("(claim1 ", yarspg)

    def test_variant_2_open_folds_all_annotations_into_one_record(self) -> None:
        yarspg = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim1 :statedBy :alice .
_:claim1 :certainty 0.8 .
""",
            variant=2,
            folding="open",
        )

        self.assertEqual(yarspg.count("(moon)-("), 1)
        self.assertIn('"asserted": "false"', yarspg)
        self.assertIn('"certainty": "lit_1"', yarspg)
        self.assertIn('"statedBy": "alice"', yarspg)
        self.assertNotIn('"referenceProperty"', yarspg)

    def test_variant_2_fixed_emits_bare_unasserted_edge(self) -> None:
        yarspg = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
""",
            variant=2,
        )

        self.assertIn(
            '(moon)-(e1 {"made_of"}["asserted": "false"])->(cheese)',
            yarspg,
        )
        self.assertNotIn('"references"', yarspg)

    def test_variant_3_nested_triple_terms(self) -> None:
        yarspg = convert(
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

        self.assertIn('(tt_1 {"TripleTerm"}["referenceId": "tt_1"])', yarspg)
        self.assertIn('(tt_2 {"TripleTerm"}["referenceId": "tt_2"])', yarspg)
        self.assertIn('(tt_3 {"TripleTerm"}["referenceId": "tt_3"])', yarspg)
        self.assertIn('(a)-(e1 {"b"})->(tt_1)', yarspg)
        self.assertIn('(s3)-(e4 {"p3"}["in": "tt_3"])->(o3)', yarspg)

    def test_variant_3_emits_shared_triple_term_once(self) -> None:
        yarspg = convert(
            PREFIXES
            + """
_:claim1 rdf:reifies <<( :moon :made_of :cheese )>> .
_:claim2 rdf:reifies <<( :moon :made_of :cheese )>> .
""",
            variant=3,
        )

        self.assertEqual(yarspg.count('{"TripleTerm"}'), 1)
        self.assertEqual(yarspg.count('["in": "tt_1"]'), 1)
        self.assertEqual(yarspg.count('{"rdf:reifies"}'), 2)

    def test_all_nodes_carry_reference_id(self) -> None:
        yarspg = convert(
            PREFIXES + ':subject :predicate "value" .\n',
            variant=3,
        )

        node_lines = [line for line in yarspg.splitlines() if line.startswith("(")]
        node_lines = [line for line in node_lines if "-(e" not in line]
        self.assertTrue(node_lines)
        self.assertTrue(all('"referenceId"' in line for line in node_lines))

    def test_default_cli_output_matches_checked_in_examples(self) -> None:
        for ttl in sorted((ROOT / "examples").glob("*.ttl")):
            for variant in (1, 2, 3):
                expected = (ROOT / "out" / f"{ttl.stem}-v{variant}.yarspg").read_text(
                    encoding="utf-8"
                )
                actual = subprocess.check_output(
                    [
                        str(ROOT / "rdf12_to_yarspg"),
                        "--variant",
                        str(variant),
                        str(ttl),
                    ],
                    text=True,
                    cwd=ROOT,
                )
                self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
