#!/usr/bin/env python3
"""Generate deterministic synthetic RDF 1.2 Turtle datasets.

The generator follows the same RDF 1.2 feature names used by the converter
example suites.  A selected profile emits Turtle that can be fed directly into
the standalone Cypher and YARS-PG converters.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path


PROFILES: tuple[str, ...] = (
    "basic",
    "predicate-object-list",
    "literals",
    "blank-nodes",
    "collections",
    "rdf-reifies",
    "asserted-and-reified",
    "triple-term-object",
    "nested-triple-terms",
    "reifier-label",
    "multiple-reifies",
    "one-reifier-many-propositions",
    "annotation-block",
    "irirefs",
    "mixed-rdf12",
)


PREFIXES: tuple[str, ...] = (
    "@prefix : <http://example.org/synthetic/> .",
    "@prefix ex: <http://example.org/synthetic/> .",
    "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
)


@dataclass(frozen=True)
class GeneratorConfig:
    """Configuration for a deterministic generator run."""

    profile: str = "all"
    count: int = 1
    seed: int = 0
    include_version: bool = False


class RDF12SyntheticGenerator:
    """Emit RDF 1.2 Turtle snippets for converter experiments."""

    def __init__(self, config: GeneratorConfig) -> None:
        if config.profile != "all" and config.profile not in PROFILES:
            raise ValueError(f"unknown profile: {config.profile}")
        if config.count < 1:
            raise ValueError("count must be at least 1")
        self.config = config
        self.random = random.Random(config.seed)
        self.lines: list[str] = []

    def generate(self) -> str:
        if self.config.include_version:
            self.lines.append('VERSION "1.2"')
        self.lines.extend(PREFIXES)
        self.lines.append("")

        profiles = PROFILES if self.config.profile == "all" else (self.config.profile,)
        for profile in profiles:
            self._emit_profile(profile)

        return "\n".join(self.lines).rstrip() + "\n"

    def _emit_profile(self, profile: str) -> None:
        method_name = "_emit_" + profile.replace("-", "_")
        method = getattr(self, method_name)
        self.lines.append(f"# profile: {profile}")
        for index in range(self.config.count):
            method(index)
        self.lines.append("")

    def _emit_basic(self, index: int) -> None:
        person = self._person(index)
        friend = self._person(index + 1)
        colleague = self._person(index + 2)
        self.lines.extend(
            (
                f":{person}_{index} :knows :{friend}_{index} .",
                f":{friend}_{index} :knows :{colleague}_{index} .",
                f":{person}_{index} a :Person .",
            )
        )

    def _emit_predicate_object_list(self, index: int) -> None:
        author_a = self._person(index)
        author_b = self._person(index + 3)
        title = self._string(f"Synthetic Property Graph {index}")
        self.lines.extend(
            (
                f":paper_{index} a :Article ;",
                f"    :title {title} ;",
                f"    :author :{author_a}_{index}, :{author_b}_{index} ;",
                f"    :publishedIn :journal_{index} .",
            )
        )

    def _emit_literals(self, index: int) -> None:
        person = self._person(index)
        direction = "ltr" if index % 2 == 0 else "rtl"
        lang = "en" if index % 2 == 0 else "pl"
        self.lines.extend(
            (
                f":literal_subject_{index} :name {self._string(person.title())}@{lang} ;",
                f"    :label {self._string(f'Directional label {index}')}@{lang}--{direction} ;",
                f"    :age {20 + index} ;",
                f"    :height {1.60 + index / 100:.2f} ;",
                f"    :score {7 + index}.5e1 ;",
                f"    :active {str(index % 2 == 0).lower()} ;",
                f"    :born {self._string(f'198{index % 10}-05-12')}^^xsd:date .",
            )
        )

    def _emit_blank_nodes(self, index: int) -> None:
        self.lines.extend(
            (
                f":blank_owner_{index} :address [",
                f"    :street {self._string(f'Main Street {index}')} ;",
                f"    :number {10 + index} ;",
                f"    :city :city_{index}",
                "] .",
                f"_:source_{index} :generatedBy :sensor_{index} .",
            )
        )

    def _emit_collections(self, index: int) -> None:
        keyword = self._pick(("RDF", "Cypher", "YARS-PG", "property graph"))
        self.lines.extend(
            (
                f":paper_{index} :keywords ( {self._string(keyword)} "
                f"{self._string('RDF 1.2')} {self._string(f'synthetic {index}')} ) .",
                f":author_group_{index} :members "
                f"( :{self._person(index)}_{index} :{self._person(index + 1)}_{index} "
                f":{self._person(index + 2)}_{index} ) .",
            )
        )

    def _emit_rdf_reifies(self, index: int) -> None:
        claim = f"_:claim_{index}"
        self.lines.extend(
            (
                f"{claim} rdf:reifies <<( :moon_{index} :made_of :cheese_{index} )>> .",
                f":{self._person(index)}_{index} :said {claim} .",
                f":{self._person(index)}_{index} :played :basketball_{index} .",
            )
        )

    def _emit_asserted_and_reified(self, index: int) -> None:
        claim = f"_:asserted_claim_{index}"
        self.lines.extend(
            (
                f"{claim} rdf:reifies <<( :asserted_moon_{index} "
                f":made_of :asserted_cheese_{index} )>> .",
                f":{self._person(index)}_{index} :said {claim} .",
                f":asserted_moon_{index} :made_of :asserted_cheese_{index} .",
            )
        )

    def _emit_triple_term_object(self, index: int) -> None:
        self.lines.extend(
            (
                f":observer_{index} :observed <<( :moon_{index} :made_of :cheese_{index} )>> .",
                f":reviewer_{index} :denied <<( :moon_{index} :made_of :cheese_{index} )>> .",
            )
        )

    def _emit_nested_triple_terms(self, index: int) -> None:
        self.lines.extend(
            (
                f":nested_root_{index} :contains <<(",
                f"    :nested_s1_{index} :nested_p1 <<(",
                f"        :nested_s2_{index} :nested_p2 <<(",
                f"            :nested_s3_{index} :nested_p3 :nested_o3_{index}",
                "        )>>",
                "    )>>",
                ")>> .",
            )
        )

    def _emit_reifier_label(self, index: int) -> None:
        confidence = self._decimal(60, 99)
        self.lines.extend(
            (
                f":report_{index} :mentions << :moon_{index} :made_of :cheese_{index} "
                f"~ :label_{index} >> .",
                f":label_{index} :confidence {confidence} .",
            )
        )

    def _emit_multiple_reifies(self, index: int) -> None:
        self.lines.extend(
            (
                f"_:claim_a_{index} :generatedBy :source_a_{index} .",
                f"_:claim_b_{index} :generatedBy :source_b_{index} .",
                f"_:claim_a_{index} rdf:reifies <<( :moon_{index} :made_of :cheese_{index} )>> .",
                f"_:claim_b_{index} rdf:reifies <<( :moon_{index} :made_of :cheese_{index} )>> .",
            )
        )

    def _emit_one_reifier_many_propositions(self, index: int) -> None:
        self.lines.extend(
            (
                f":speaker_{index} :says _:claim_set_{index} .",
                f"_:claim_set_{index} rdf:reifies <<( :moon_{index} :made_of :cheese_{index} )>> .",
                f"_:claim_set_{index} rdf:reifies <<( :sun_{index} :made_of :popcorn_{index} )>> .",
            )
        )

    def _emit_annotation_block(self, index: int) -> None:
        self.lines.extend(
            (
                f":{self._person(index)}_{index} :likes :pizza_{index} "
                f"{{| :certainty {self._decimal(70, 99)} ; :source :survey_{index} |}} .",
                f":{self._person(index + 1)}_{index} :likes :pasta_{index} "
                f"{{| :source :survey_{index + 1} |}} .",
            )
        )

    def _emit_irirefs(self, index: int) -> None:
        self.lines.extend(
            (
                f"<http://example.org/synthetic/full/bob_{index}> "
                f"ex:knows <http://example.org/synthetic/full/alice_{index}> .",
                f"<http://example.org/synthetic/full/bob_{index}> "
                f"ex:homepage <https://example.net/users/bob_{index}> .",
            )
        )

    def _emit_mixed_rdf12(self, index: int) -> None:
        self.lines.extend(
            (
                f":asserts_{index} rdfs:subPropertyOf rdf:reifies .",
                f"_:mixed_claim_{index} :said_by :{self._person(index)}_{index} .",
                f"_:mixed_claim_{index} :asserts_{index} "
                f"<<( :moon_{index} :made_of :cheese_{index} )>> .",
                f":report_{index} :mentions "
                f"<< :moon_{index} :made_of :cheese_{index} ~ _:mixed_claim_{index} >> .",
            )
        )

    def _person(self, index: int) -> str:
        names = ("alice", "bob", "carol", "dave", "erin", "frank")
        return names[index % len(names)]

    def _pick(self, values: tuple[str, ...]) -> str:
        return values[self.random.randrange(len(values))]

    def _decimal(self, minimum: int, maximum: int) -> str:
        value = self.random.randint(minimum, maximum)
        return f"0.{value}"

    def _string(self, value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def generate_turtle(
    profile: str = "all",
    count: int = 1,
    seed: int = 0,
    include_version: bool = False,
) -> str:
    """Return a deterministic Turtle document for the selected profile."""

    config = GeneratorConfig(
        profile=profile,
        count=count,
        seed=seed,
        include_version=include_version,
    )
    return RDF12SyntheticGenerator(config).generate()


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic RDF 1.2 Turtle datasets."
    )
    parser.add_argument(
        "--profile",
        choices=("all", *PROFILES),
        default="all",
        help="RDF 1.2 feature profile to generate (default: all).",
    )
    parser.add_argument(
        "--count",
        type=_positive_int,
        default=1,
        help="Number of examples per selected profile (default: 1).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for deterministic choices (default: 0).",
    )
    parser.add_argument(
        "--version-directive",
        action="store_true",
        help='Emit VERSION "1.2" before prefix declarations.',
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Print available profiles and exit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output Turtle file. Writes stdout when omitted.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_profiles:
        for profile in PROFILES:
            print(profile)
        return 0

    try:
        turtle = generate_turtle(
            profile=args.profile,
            count=args.count,
            seed=args.seed,
            include_version=args.version_directive,
        )
        if args.output:
            Path(args.output).write_text(turtle, encoding="utf-8")
        else:
            sys.stdout.write(turtle)
        return 0
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
