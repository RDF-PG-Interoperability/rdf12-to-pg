#!/usr/bin/env python3
"""Convert RDF 1.2 Turtle input to YARS-PG.

The converter implements three RDF 1.2 mapping variants and emits generated
nodes and edges in YARS-PG format.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Iterable

from . import rdf_converter as rdf12


# Namespace constants are used for semantic checks after the Turtle parser has
# expanded prefixes to absolute IRIs.
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"

RDF_REIFIES_IRI = RDF_NS + "reifies"
XSD_STRING_IRI = XSD_NS + "string"


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class Resource:
    value: str


@dataclass(frozen=True)
class Literal:
    value: str
    datatype: Resource | None = None
    lang: str | None = None
    direction: str | None = None


@dataclass(frozen=True)
class TripleTerm:
    subject: object
    predicate: Resource
    object: object
    reifier: object | None = None
    reified: bool = False


@dataclass(frozen=True)
class Triple:
    subject: object
    predicate: Resource
    object: object


class YarspgWriter:
    """Shared YARS-PG serialization helpers used by all mapping variants."""

    def __init__(self, prefixes: dict[str, str] | None = None) -> None:
        self.prefixes = {
            "rdf": RDF_NS,
            "rdfs": RDFS_NS,
            "xsd": XSD_NS,
        }
        if prefixes:
            self.prefixes.update(prefixes)
        self.nodes: dict[str, tuple[set[str], dict[str, str | bool]]] = {}
        self.edges: list[tuple[str, str, str, str, dict[str, str | bool]]] = []
        self.edge_counter = 0
        self.term_ids: dict[object, str] = {}
        self.id_terms: dict[str, object] = {}
        self.term_node_ids: dict[object, str] = {}
        self.node_id_terms: dict[str, object] = {}
        self.literal_counter = 0
        self.tripleterm_counter = 0

    def write(self, triples: Iterable[Triple]) -> str:
        for triple in triples:
            self._encode_triple(triple)
        return self._serialize()

    def _serialize(self) -> str:
        lines = ["# Nodes"]
        for node_id in sorted(self.nodes):
            labels, props = self.nodes[node_id]
            lines.append(self._format_node(node_id, labels, props))
        lines.append("")
        lines.append("# Edges")
        for edge_id, source, label, target, props in self.edges:
            lines.append(self._format_edge(edge_id, source, label, target, props))
        return "\n".join(lines) + "\n"

    def _encode_triple(
        self,
        triple: Triple,
        in_id: str | None = None,
        props: dict[str, str | bool] | None = None,
    ) -> None:
        source = self._node_for_term(triple.subject)
        target = self._node_for_term(triple.object)
        edge_props = dict(props or {})
        if in_id is not None:
            edge_props["in"] = in_id
        self._add_edge(
            source, self._label_for_resource(triple.predicate), target, edge_props
        )

    def _node_for_term(self, term: object) -> str:
        if not isinstance(term, (Resource, Literal, TripleTerm)):
            raise TypeError(f"Unsupported term: {term!r}")

        node_id = self._node_id_for_term(term)
        if node_id not in self.nodes:
            props: dict[str, str | bool] = {"referenceId": self._display_term(term)}
            if isinstance(term, Literal):
                props["value"] = term.value
                if term.datatype is not None:
                    props["datatype"] = self._display_resource(term.datatype)
                if term.lang is not None:
                    props["language"] = term.lang
                if term.direction is not None:
                    props["direction"] = term.direction
            self.nodes[node_id] = ({self._kind_for_term(term)}, props)
        return node_id

    def _kind_for_term(self, term: object) -> str:
        if isinstance(term, Resource):
            return self._node_label_for_resource(term)
        if isinstance(term, Literal):
            return "Literal"
        if isinstance(term, TripleTerm):
            return "TripleTerm"
        raise TypeError(f"Unsupported term: {term!r}")

    def _node_id_for_term(self, term: object) -> str:
        existing = self.term_node_ids.get(term)
        if existing is not None:
            return existing

        base = self._sanitize_id(self._display_term(term))
        node_id = base
        suffix = 2
        while node_id in self.node_id_terms and self.node_id_terms[node_id] != term:
            node_id = f"{base}_{suffix}"
            suffix += 1
        self.term_node_ids[term] = node_id
        self.node_id_terms[node_id] = term
        return node_id

    def _node_label_for_resource(self, resource: Resource) -> str:
        return "BNode" if resource.value.startswith("_:") else "IRI"

    def _label_for_resource(self, resource: Resource) -> str:
        return self._display_term(resource)

    def _display_term(self, term: object) -> str:
        existing = self.term_ids.get(term)
        if existing is not None:
            return existing

        if isinstance(term, Resource):
            candidate = self._display_resource(term)
        elif isinstance(term, Literal):
            self.literal_counter += 1
            candidate = f"lit_{self.literal_counter}"
        elif isinstance(term, TripleTerm):
            self.tripleterm_counter += 1
            candidate = f"tt_{self.tripleterm_counter}"
        else:
            raise TypeError(f"Unsupported term: {term!r}")

        identifier = candidate
        suffix = 2
        while identifier in self.id_terms and self.id_terms[identifier] != term:
            identifier = f"{candidate}_{suffix}"
            suffix += 1
        self.term_ids[term] = identifier
        self.id_terms[identifier] = term
        return identifier

    def _display_resource(self, resource: Resource) -> str:
        value = resource.value
        if value.startswith("<") and value.endswith(">"):
            inner = value[1:-1]
            # Prefer declared prefixes for readable node IDs and properties,
            # but keep default-prefix values as plain local names.
            for prefix, base in self.prefixes.items():
                if inner.startswith(base):
                    local = inner[len(base) :]
                    return local if prefix == "" else f"{prefix}:{local}"
            return inner.rsplit("/", 1)[-1].rsplit("#", 1)[-1] or inner
        return value

    def _resource_iri(self, resource: Resource) -> str | None:
        value = resource.value
        if value.startswith("<") and value.endswith(">"):
            return value[1:-1]
        if ":" in value and not value.startswith("_:"):
            prefix, local = value.split(":", 1)
            if prefix in self.prefixes:
                return self.prefixes[prefix] + local
        return None

    def _resource_is(self, resource: Resource, iri: str) -> bool:
        return self._resource_iri(resource) == iri

    def _sanitize_id(self, value: str) -> str:
        if value.startswith("_:"):
            value = "_" + value[2:]
        if ":" in value:
            prefix, local = value.split(":", 1)
            value = (
                local if prefix in {"", "rdf", "rdfs", "xsd"} else f"{prefix}_{local}"
            )
        value = re.sub(r"[^a-zA-Z0-9_]", "_", value)
        value = re.sub(r"_+", "_", value).strip("_")
        if not value:
            value = "node"
        if not re.match(r"[a-zA-Z_]", value):
            value = "_" + value
        return value

    def _format_node(
        self,
        node_id: str,
        labels: set[str],
        props: dict[str, str | bool],
    ) -> str:
        label_part = ""
        if labels:
            label_part = (
                " {" + ", ".join(self._q(label) for label in sorted(labels)) + "}"
            )
        prop_part = self._format_props(props)
        return f"({node_id}{label_part}{prop_part})"

    def _add_edge(
        self,
        source: str,
        label: str,
        target: str,
        props: dict[str, str | bool],
    ) -> None:
        self.edge_counter += 1
        self.edges.append((f"e{self.edge_counter}", source, label, target, props))

    def _format_edge(
        self,
        edge_id: str,
        source: str,
        label: str,
        target: str,
        props: dict[str, str | bool],
    ) -> str:
        return f"({source})-({edge_id} {{{self._q(label)}}}{self._format_props(props)})->({target})"

    def _format_props(self, props: dict[str, str | bool]) -> str:
        if not props:
            return ""
        pairs = [
            f"{self._q(key)}: {self._q(str(value).lower() if isinstance(value, bool) else value)}"
            for key, value in sorted(props.items())
        ]
        return "[" + ", ".join(pairs) + "]"

    def _unique_triples(self, triples: Iterable[Triple]) -> list[Triple]:
        return list(dict.fromkeys(triples))

    def _q(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'


class Variant1Writer(YarspgWriter):
    """Variant 1 (Maxime): interpreting translation with reifier nodes."""

    def write(self, triples: Iterable[Triple]) -> str:
        graph = self._unique_triples(triples)
        reifying = [
            triple
            for triple in graph
            if self._is_reifies(triple.predicate)
            and isinstance(triple.object, TripleTerm)
        ]
        self.reifiers = {triple.subject for triple in reifying}
        plain_triples = {
            triple for triple in graph if not isinstance(triple.object, TripleTerm)
        }
        triple_term_edges: set[Triple] = set()

        # Pass 1: every reifying triple creates its own triple-term edge.
        for triple in reifying:
            term = triple.object
            assert isinstance(term, TripleTerm)
            represented = Triple(term.subject, term.predicate, term.object)
            triple_term_edges.add(represented)
            self._add_reifier(triple.subject)
            self._create_edge(
                represented,
                {
                    "asserted": represented in plain_triples,
                    "reifiedBy": self._display_term(triple.subject),
                },
            )

        # Pass 2: a matching plain triple only asserts the pass-1 edges.
        for triple in graph:
            if isinstance(triple.object, TripleTerm):
                continue
            if triple in triple_term_edges:
                continue
            self._create_edge(triple, {"asserted": True})

        return self._serialize()

    def _kind_for_term(self, term: object) -> str:
        if term in getattr(self, "reifiers", set()):
            return "Reifier"
        return super()._kind_for_term(term)

    def _add_reifier(self, term: object) -> None:
        node_id = self._node_for_term(term)
        labels, _ = self.nodes[node_id]
        labels.clear()
        labels.add("Reifier")

    def _create_edge(
        self,
        triple: Triple,
        props: dict[str, str | bool],
    ) -> None:
        self._encode_triple(triple, props=props)

    def _is_reifies(self, predicate: Resource) -> bool:
        return self._resource_is(predicate, RDF_REIFIES_IRI)


class Variant2Writer(YarspgWriter):
    """Variant 2 (Katja): folded annotations without reifier nodes."""

    def __init__(
        self,
        prefixes: dict[str, str] | None = None,
        folding: str = "fixed",
    ) -> None:
        super().__init__(prefixes)
        if folding not in {"fixed", "open"}:
            raise ValueError("folding must be 'fixed' or 'open'")
        self.folding = folding

    def write(self, triples: Iterable[Triple]) -> str:
        graph = self._unique_triples(triples)
        reifying = [
            triple
            for triple in graph
            if self._is_reifies(triple.predicate)
            and isinstance(triple.object, TripleTerm)
        ]
        reifiers = {triple.subject for triple in reifying}
        annotations: dict[object, list[Triple]] = {reifier: [] for reifier in reifiers}
        for triple in graph:
            if triple.subject in reifiers and not self._is_reifies(triple.predicate):
                annotations[triple.subject].append(triple)

        eligible_plain = {
            triple
            for triple in graph
            if not isinstance(triple.object, TripleTerm)
            and triple.subject not in reifiers
            and triple.object not in reifiers
        }
        triple_term_edges: set[Triple] = set()

        # Pass 1: fold each reifier's annotations onto its represented triple.
        for triple in reifying:
            term = triple.object
            assert isinstance(term, TripleTerm)
            represented = Triple(term.subject, term.predicate, term.object)
            triple_term_edges.add(represented)
            anns = annotations[triple.subject]
            for annotation in anns:
                self._node_for_term(annotation.object)
            for props in self._fold(anns):
                props["asserted"] = represented in eligible_plain
                self._create_edge(represented, props)

        # Pass 2: triples touching a reifier are deliberately discarded.
        for triple in graph:
            if triple not in eligible_plain:
                continue
            if triple in triple_term_edges:
                continue
            self._create_edge(triple, {"asserted": True})

        return self._serialize()

    def _fold(self, annotations: list[Triple]) -> list[dict[str, str | bool]]:
        if self.folding == "open":
            props: dict[str, str | bool] = {"asserted": False}
            for annotation in annotations:
                props[self._display_term(annotation.predicate)] = self._display_term(
                    annotation.object
                )
            return [props]

        if not annotations:
            return [{"asserted": False}]
        return [
            {
                "asserted": False,
                "referenceProperty": self._display_term(annotation.predicate),
                "references": self._display_term(annotation.object),
            }
            for annotation in annotations
        ]

    def _create_edge(
        self,
        triple: Triple,
        props: dict[str, str | bool],
    ) -> None:
        self._encode_triple(triple, props=props)

    def _is_reifies(self, predicate: Resource) -> bool:
        return self._resource_is(predicate, RDF_REIFIES_IRI)


class Variant3Writer(YarspgWriter):
    """Variant 3 (Ruben): structural, recursive, lossless translation."""

    def write(self, triples: Iterable[Triple]) -> str:
        self.encoded: set[str] = set()
        for triple in self._unique_triples(triples):
            self._emit(triple, in_id=None)
        return self._serialize()

    def _emit(self, triple: Triple, in_id: str | None) -> None:
        self._encode_triple(triple, in_id=in_id)
        if not isinstance(triple.object, TripleTerm):
            return

        tripleterm_id = self._display_term(triple.object)
        if tripleterm_id in self.encoded:
            return
        self.encoded.add(tripleterm_id)
        self._emit(
            Triple(
                triple.object.subject,
                triple.object.predicate,
                triple.object.object,
            ),
            in_id=tripleterm_id,
        )


def parse_turtle_rdf12(
    text: str, source: str = "<string>"
) -> tuple[list[Triple], dict[str, str]]:
    # Use the full RDF 1.2 Turtle parser from rdf12conv, then adapt its typed
    # AST to the smaller internal model used by the YARS-PG writers.
    parser = rdf12.TurtleParser(text=text, source=source, base_iri=None)
    rdf_triples = parser.parse()
    triples = [
        Triple(
            _from_rdf12_resource(subject),
            _from_rdf12_resource(predicate),
            _from_rdf12_node(obj),
        )
        for subject, predicate, obj in rdf_triples
    ]
    prefixes = {
        "rdf": RDF_NS,
        "rdfs": RDFS_NS,
        "xsd": XSD_NS,
    }
    prefixes.update(parser.prefixes)
    return triples, prefixes


def _from_rdf12_node(node: object) -> object:
    if isinstance(node, rdf12.IRI):
        return Resource(f"<{node.value}>")
    if isinstance(node, rdf12.BNode):
        return Resource(f"_:{node.label}")
    if isinstance(node, rdf12.Literal):
        datatype = node.datatype or XSD_STRING_IRI
        return Literal(
            value=node.value,
            datatype=Resource(f"<{datatype}>"),
            lang=node.lang,
            direction=node.direction,
        )
    if isinstance(node, rdf12.TripleTerm):
        return TripleTerm(
            subject=_from_rdf12_node(node.subject),
            predicate=_from_rdf12_resource(node.predicate),
            object=_from_rdf12_node(node.object),
        )
    raise TypeError(f"Unsupported RDF 1.2 node: {node!r}")


def _from_rdf12_resource(node: object) -> Resource:
    if isinstance(node, rdf12.IRI):
        return Resource(f"<{node.value}>")
    if isinstance(node, rdf12.BNode):
        return Resource(f"_:{node.label}")
    raise TypeError(f"Expected RDF 1.2 IRI or blank node, got {node!r}")


def convert(
    text: str,
    variant: int = 3,
    source: str = "<string>",
    folding: str = "fixed",
) -> str:
    triples, prefixes = parse_turtle_rdf12(text, source=source)
    if variant == 1:
        writer: YarspgWriter = Variant1Writer(prefixes)
    elif variant == 2:
        writer = Variant2Writer(prefixes, folding=folding)
    elif variant == 3:
        writer = Variant3Writer(prefixes)
    else:
        raise ValueError(f"Unsupported mapping variant: {variant}")
    return writer.write(triples)


def main(argv: list[str] | None = None) -> int:
    argp = argparse.ArgumentParser(description="Convert RDF 1.2 Turtle to YARS-PG.")
    argp.add_argument(
        "input", nargs="?", help="Turtle input file. Reads stdin when omitted."
    )
    argp.add_argument(
        "-o", "--output", help="YARS-PG output file. Writes stdout when omitted."
    )
    argp.add_argument(
        "--variant",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="Mapping variant: 1, 2, or 3 (default: 3).",
    )
    argp.add_argument(
        "--folding",
        choices=("fixed", "open"),
        default="fixed",
        help="Variant 2 annotation folding form (default: fixed).",
    )
    args = argp.parse_args(argv)

    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            text = sys.stdin.read()
        source = args.input or "<stdin>"
        result = convert(text, args.variant, source=source, folding=args.folding)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
        else:
            sys.stdout.write(result)
        return 0
    except (ParseError, rdf12.ParseError, ValueError) as exc:
        prefix = (
            "Parse error"
            if isinstance(exc, (ParseError, rdf12.ParseError))
            else "Error"
        )
        print(f"{prefix}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
