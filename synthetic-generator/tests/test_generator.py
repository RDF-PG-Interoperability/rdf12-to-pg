import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from synthetic_gen_lib import PROFILES, generate_turtle


ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(__file__).resolve().parents[1]


class SyntheticGeneratorTests(unittest.TestCase):
    def test_all_profile_contains_all_rdf12_shapes(self) -> None:
        turtle = generate_turtle(profile="all", count=1, seed=3)

        for profile in PROFILES:
            self.assertIn(f"# profile: {profile}", turtle)
        self.assertIn("rdf:reifies", turtle)
        self.assertIn("<<(", turtle)
        self.assertIn("~", turtle)
        self.assertIn("{|", turtle)
        self.assertIn("@en--ltr", turtle)
        self.assertIn("^^xsd:date", turtle)

    def test_generation_is_seed_deterministic(self) -> None:
        first = generate_turtle(profile="all", count=2, seed=11)
        second = generate_turtle(profile="all", count=2, seed=11)
        different = generate_turtle(profile="all", count=2, seed=12)

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_cli_writes_requested_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "generated.ttl"
            subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "synthetic_gen.py"),
                    "--profile",
                    "literals",
                    "--count",
                    "2",
                    "--seed",
                    "5",
                    "--output",
                    str(output),
                ],
                cwd=PROJECT,
                check=True,
            )

            text = output.read_text(encoding="utf-8")
            self.assertIn("# profile: literals", text)
            self.assertIn(":literal_subject_1", text)

    def test_generated_all_profile_converts_with_cypher_and_yarspg(self) -> None:
        turtle = generate_turtle(profile="all", count=1, seed=17)

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "synthetic.ttl"
            input_path.write_text(turtle, encoding="utf-8")

            for converter in (
                ROOT / "cypher" / "rdf12_to_neo4j",
                ROOT / "yarspg" / "rdf12_to_yarspg",
            ):
                for variant in (1, 2, 3):
                    completed = subprocess.run(
                        [
                            str(converter),
                            "--variant",
                            str(variant),
                            str(input_path),
                        ],
                        cwd=converter.parent,
                        check=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.assertTrue(completed.stdout.strip())

    def test_each_named_profile_converts_with_variant_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for profile in PROFILES:
                input_path = Path(tmpdir) / f"{profile}.ttl"
                input_path.write_text(
                    generate_turtle(profile=profile, count=2, seed=23),
                    encoding="utf-8",
                )

                for converter in (
                    ROOT / "cypher" / "rdf12_to_neo4j",
                    ROOT / "yarspg" / "rdf12_to_yarspg",
                ):
                    completed = subprocess.run(
                        [
                            str(converter),
                            "--variant",
                            "3",
                            str(input_path),
                        ],
                        cwd=converter.parent,
                        check=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.assertTrue(completed.stdout.strip())


if __name__ == "__main__":
    unittest.main()
