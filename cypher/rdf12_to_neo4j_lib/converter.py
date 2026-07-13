#!/usr/bin/env python3
"""Convert RDF 1.2 Turtle input to Cypher.

The converter implements three RDF 1.2 mapping variants and emits generated
nodes and relationships as Cypher CREATE clauses suitable for Neo4j.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable, Iterator, TextIO

from . import rdf_converter as rdf12


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


def _term_to_data(term: object) -> dict[str, object]:
    if isinstance(term, Resource):
        return {"type": "resource", "value": term.value}
    if isinstance(term, Literal):
        return {
            "type": "literal",
            "value": term.value,
            "datatype": _term_to_data(term.datatype) if term.datatype else None,
            "lang": term.lang,
            "direction": term.direction,
        }
    if isinstance(term, TripleTerm):
        return {
            "type": "tripleterm",
            "subject": _term_to_data(term.subject),
            "predicate": _term_to_data(term.predicate),
            "object": _term_to_data(term.object),
            "reifier": _term_to_data(term.reifier) if term.reifier else None,
            "reified": term.reified,
        }
    raise TypeError(f"Unsupported term: {term!r}")


def _term_from_data(data: dict[str, object]) -> object:
    kind = data["type"]
    if kind == "resource":
        return Resource(str(data["value"]))
    if kind == "literal":
        datatype_data = data.get("datatype")
        datatype = (
            _term_from_data(datatype_data) if isinstance(datatype_data, dict) else None
        )
        if datatype is not None and not isinstance(datatype, Resource):
            raise TypeError(f"Expected literal datatype resource, got {datatype!r}")
        return Literal(
            value=str(data["value"]),
            datatype=datatype,
            lang=data["lang"] if isinstance(data.get("lang"), str) else None,
            direction=data["direction"]
            if isinstance(data.get("direction"), str)
            else None,
        )
    if kind == "tripleterm":
        predicate = _term_from_data(data["predicate"])  # type: ignore[arg-type]
        if not isinstance(predicate, Resource):
            raise TypeError(
                f"Expected triple term predicate resource, got {predicate!r}"
            )
        reifier_data = data.get("reifier")
        return TripleTerm(
            subject=_term_from_data(data["subject"]),  # type: ignore[arg-type]
            predicate=predicate,
            object=_term_from_data(data["object"]),  # type: ignore[arg-type]
            reifier=(
                _term_from_data(reifier_data)
                if isinstance(reifier_data, dict)
                else None
            ),
            reified=bool(data.get("reified")),
        )
    raise TypeError(f"Unsupported serialized term: {data!r}")


def _triple_to_data(triple: Triple) -> dict[str, object]:
    return {
        "subject": _term_to_data(triple.subject),
        "predicate": _term_to_data(triple.predicate),
        "object": _term_to_data(triple.object),
    }


def _triple_from_data(data: dict[str, object]) -> Triple:
    predicate = _term_from_data(data["predicate"])  # type: ignore[arg-type]
    if not isinstance(predicate, Resource):
        raise TypeError(f"Expected triple predicate resource, got {predicate!r}")
    return Triple(
        subject=_term_from_data(data["subject"]),  # type: ignore[arg-type]
        predicate=predicate,
        object=_term_from_data(data["object"]),  # type: ignore[arg-type]
    )


def _stable_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _triple_parts_key(subject: object, predicate: Resource, obj: object) -> str:
    return _stable_json(
        {
            "subject": _term_to_data(subject),
            "predicate": _term_to_data(predicate),
            "object": _term_to_data(obj),
        }
    )


def _triple_key(triple: Triple) -> str:
    return _triple_parts_key(triple.subject, triple.predicate, triple.object)


def _write_spooled_triple(handle: TextIO, triple: Triple) -> None:
    handle.write(_stable_json(_triple_to_data(triple)) + "\n")


def _iter_spooled_triples(path: str) -> Iterator[Triple]:
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield _triple_from_data(json.loads(line))


class PartitionedDiskSet:
    """Disk-backed set used where pseudocode needs a set.

    Correspondence:
    1. `x in S` -> `contains(x)`.
    2. `S <- S union {x}` -> `add(x)`.
    3. `if x in S then skip else S <- S union {x}` -> `seen_or_add(x)`.
    """

    def __init__(
        self,
        directory: str,
        name: str,
        partitions: int = 128,
        cache_size: int = 8,
    ) -> None:
        self.directory = directory
        self.name = name
        self.partitions = partitions
        self.cache_size = cache_size
        self.cache: OrderedDict[int, set[str]] = OrderedDict()
        os.makedirs(directory, exist_ok=True)

    def add(self, key: str) -> None:
        partition = self._partition(key)
        if partition in self.cache:
            self.cache[partition].add(key)
        with open(self._path(partition), "a", encoding="utf-8") as handle:
            handle.write(key + "\n")

    def contains(self, key: str) -> bool:
        partition = self._partition(key)
        return key in self._load(partition)

    def seen_or_add(self, key: str) -> bool:
        partition = self._partition(key)
        values = self._load(partition)
        if key in values:
            return True
        values.add(key)
        with open(self._path(partition), "a", encoding="utf-8") as handle:
            handle.write(key + "\n")
        return False

    def _load(self, partition: int) -> set[str]:
        if partition in self.cache:
            self.cache.move_to_end(partition)
            return self.cache[partition]

        values: set[str] = set()
        path = self._path(partition)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                values = {line.rstrip("\n") for line in handle if line.rstrip("\n")}

        self.cache[partition] = values
        self.cache.move_to_end(partition)
        while len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return values

    def _partition(self, key: str) -> int:
        digest = hashlib.sha1(key.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % self.partitions

    def _path(self, partition: int) -> str:
        return os.path.join(self.directory, f"{self.name}-{partition:03d}.keys")


class CypherWriter:
    """Shared graph-building and Cypher serialization helpers."""

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
        if not self.nodes and not self.edges:
            return "RETURN 0 AS noop;\n"

        entries: list[str] = []
        for node_id in sorted(self.nodes):
            labels, props = self.nodes[node_id]
            entries.append("  " + self._format_node(node_id, labels, props))
        for edge_id, source, label, target, props in self.edges:
            entries.append(
                "  " + self._format_edge(edge_id, source, label, target, props)
            )
        return "CREATE\n" + ",\n".join(entries) + ";\n"

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
        label_part = "".join(f":{self._cypher_name(label)}" for label in sorted(labels))
        return f"({self._cypher_name(node_id)}{label_part}{self._format_props(props)})"

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
        return (
            f"({self._cypher_name(source)})-"
            f"[{self._cypher_name(edge_id)}:{self._cypher_name(label)}{self._format_props(props)}]"
            f"->({self._cypher_name(target)})"
        )

    def _format_props(self, props: dict[str, str | bool]) -> str:
        if not props:
            return ""
        pairs = [
            f"{self._cypher_name(key)}: {self._cypher_value(value)}"
            for key, value in sorted(props.items())
        ]
        return " {" + ", ".join(pairs) + "}"

    def _cypher_name(self, value: str) -> str:
        return f"`{value.replace('`', '``')}`"

    def _cypher_string(self, value: str) -> str:
        return json.dumps(value, ensure_ascii=True)

    def _cypher_value(self, value: str | bool) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return self._cypher_string(value)

    def _unique_triples(self, triples: Iterable[Triple]) -> list[Triple]:
        return list(dict.fromkeys(triples))


class Variant1Writer(CypherWriter):
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


class Variant2Writer(CypherWriter):
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


class Variant3Writer(CypherWriter):
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


class LargeWriterMixin:
    """Batch Cypher output shared by opt-in large-file strategies.

    Pseudocode correspondence with the paper:
    1. `CreateEdge` still appends a logical edge to current state.
    2. When `|E_batch| = batchSize`, `flush` serializes `N_batch` and
       `E_batch` as `UNWIND` statements.
    3. `finish` flushes the final partial batch.
    """

    def __init__(
        self,
        prefixes: dict[str, str] | None,
        output: TextIO,
        batch_size: int,
        **writer_options: str,
    ) -> None:
        super().__init__(prefixes, **writer_options)  # type: ignore[misc]
        self.output = output
        self.batch_size = batch_size
        self._wrote_statement = False
        self._wrote_preamble = False

    def _add_edge(
        self,
        source: str,
        label: str,
        target: str,
        props: dict[str, str | bool],
    ) -> None:
        self.edge_counter += 1
        self.edges.append((f"e{self.edge_counter}", source, label, target, props))
        if len(self.edges) >= self.batch_size:
            self.flush()

    def _serialize(self) -> str:
        self.finish()
        return ""

    def finish(self) -> None:
        self.flush()
        if not self._wrote_statement:
            self.output.write("RETURN 0 AS noop;\n")
            self._wrote_statement = True

    def flush(self) -> None:
        if not self.nodes and not self.edges:
            return

        self._write_preamble()
        nodes = self.nodes
        edges = self.edges
        self.nodes = {}
        self.edges = []

        if nodes:
            self._emit_node_batches(nodes)
        if edges:
            self._emit_edge_batches(edges)

    def _emit_node_batches(
        self,
        nodes: dict[str, tuple[set[str], dict[str, str | bool]]],
    ) -> None:
        groups: dict[tuple[str, ...], list[tuple[str, dict[str, str | bool]]]] = {}
        for node_id in sorted(nodes):
            labels, props = nodes[node_id]
            groups.setdefault(tuple(sorted(labels)), []).append((node_id, dict(props)))

        for labels, rows in sorted(groups.items()):
            for chunk in self._chunks(rows):
                self._write_node_statement(labels, chunk)

    def _emit_edge_batches(
        self,
        edges: list[tuple[str, str, str, str, dict[str, str | bool]]],
    ) -> None:
        groups: dict[str, list[tuple[str, str, dict[str, str | bool]]]] = {}
        for _, source, label, target, props in edges:
            groups.setdefault(label, []).append((source, target, dict(props)))

        for label, rows in sorted(groups.items()):
            for chunk in self._chunks(rows):
                self._write_edge_statement(label, chunk)

    def _chunks(self, rows: list[object]) -> Iterator[list[object]]:
        for index in range(0, len(rows), self.batch_size):
            yield rows[index : index + self.batch_size]

    def _write_preamble(self) -> None:
        if self._wrote_preamble:
            return
        self.output.write(
            "CREATE CONSTRAINT rdf12node_id IF NOT EXISTS "
            "FOR (n:`RDF12Node`) REQUIRE n.`rdf12_id` IS UNIQUE;\n\n"
        )
        self._wrote_preamble = True
        self._wrote_statement = True

    def _write_node_statement(
        self,
        labels: tuple[str, ...],
        rows: list[tuple[str, dict[str, str | bool]]],
    ) -> None:
        self.output.write("UNWIND [\n")
        for index, (node_id, props) in enumerate(rows):
            comma = "," if index < len(rows) - 1 else ""
            self.output.write(
                f"  {{id: {self._cypher_string(node_id)}, props: {self._cypher_map(props)}}}{comma}\n"
            )
        self.output.write("] AS row\n")
        self.output.write(
            f"MERGE (n:{self._cypher_name('RDF12Node')} "
            f"{{{self._cypher_name('rdf12_id')}: row.id}})\n"
        )
        if labels:
            label_part = "".join(f":{self._cypher_name(label)}" for label in labels)
            self.output.write(f"SET n{label_part}\n")
        self.output.write("SET n += row.props;\n\n")
        self._wrote_statement = True

    def _write_edge_statement(
        self,
        label: str,
        rows: list[tuple[str, str, dict[str, str | bool]]],
    ) -> None:
        self.output.write("UNWIND [\n")
        for index, (source, target, props) in enumerate(rows):
            comma = "," if index < len(rows) - 1 else ""
            self.output.write(
                "  {"
                f"source: {self._cypher_string(source)}, "
                f"target: {self._cypher_string(target)}, "
                f"props: {self._cypher_map(props)}"
                f"}}{comma}\n"
            )
        self.output.write("] AS row\n")
        self.output.write(
            f"MATCH (s:{self._cypher_name('RDF12Node')} "
            f"{{{self._cypher_name('rdf12_id')}: row.source}})\n"
        )
        self.output.write(
            f"MATCH (o:{self._cypher_name('RDF12Node')} "
            f"{{{self._cypher_name('rdf12_id')}: row.target}})\n"
        )
        self.output.write(f"CREATE (s)-[r:{self._cypher_name(label)}]->(o)\n")
        self.output.write("SET r += row.props;\n\n")
        self._wrote_statement = True

    def _cypher_map(self, props: dict[str, str | bool]) -> str:
        if not props:
            return "{}"
        pairs = [
            f"{self._cypher_name(key)}: {self._cypher_value(value)}"
            for key, value in sorted(props.items())
        ]
        return "{" + ", ".join(pairs) + "}"


class LargeVariant1Writer(LargeWriterMixin, Variant1Writer):
    """Disk-indexed, batched implementation of variant 1."""

    def write_from_spool(self, triples_path: str, index_dir: str) -> None:
        plain_triples = PartitionedDiskSet(index_dir, "plain")
        triple_term_edges = PartitionedDiskSet(index_dir, "triple-term")
        self.reifiers: set[object] = set()

        # Index pass computes the two membership tests used by the pseudocode.
        for triple in _iter_spooled_triples(triples_path):
            if isinstance(triple.object, TripleTerm):
                if self._is_reifies(triple.predicate):
                    self.reifiers.add(triple.subject)
                    term = triple.object
                    represented = Triple(term.subject, term.predicate, term.object)
                    triple_term_edges.add(_triple_key(represented))
                continue
            plain_triples.add(_triple_key(triple))

        seen_reifying = PartitionedDiskSet(index_dir, "seen-reifying")
        for triple in _iter_spooled_triples(triples_path):
            if not (
                self._is_reifies(triple.predicate)
                and isinstance(triple.object, TripleTerm)
            ):
                continue
            if seen_reifying.seen_or_add(_triple_key(triple)):
                continue
            term = triple.object
            represented = Triple(term.subject, term.predicate, term.object)
            self._add_reifier(triple.subject)
            self._create_edge(
                represented,
                {
                    "asserted": plain_triples.contains(_triple_key(represented)),
                    "reifiedBy": self._display_term(triple.subject),
                },
            )

        seen_plain = PartitionedDiskSet(index_dir, "seen-plain")
        for triple in _iter_spooled_triples(triples_path):
            if isinstance(triple.object, TripleTerm):
                continue
            key = _triple_key(triple)
            if seen_plain.seen_or_add(key) or triple_term_edges.contains(key):
                continue
            self._create_edge(triple, {"asserted": True})

        self.finish()


class LargeVariant2Writer(LargeWriterMixin, Variant2Writer):
    """Batched implementation of variant 2."""

    def write_from_spool(self, triples_path: str) -> None:
        # Folding needs all annotations grouped by reifier. Batching still
        # bounds the generated Cypher retained in memory.
        self.write(_iter_spooled_triples(triples_path))


class LargeVariant3Writer(LargeWriterMixin, Variant3Writer):
    """Disk-deduplicated, batched implementation of variant 3."""

    def write_from_spool(self, triples_path: str, index_dir: str) -> None:
        self.encoded = set()
        seen = PartitionedDiskSet(index_dir, "seen-graph")
        for triple in _iter_spooled_triples(triples_path):
            if seen.seen_or_add(_triple_key(triple)):
                continue
            self._emit(triple, in_id=None)
        self.finish()


def parse_turtle_rdf12(
    text: str, source: str = "<string>"
) -> tuple[list[Triple], dict[str, str]]:
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


def spool_turtle_rdf12(
    text: str, output: TextIO, source: str = "<string>"
) -> dict[str, str]:
    parser = rdf12.TurtleParser(text=text, source=source, base_iri=None)
    original_emit = parser.emit

    def emit_spooled(subject: object, predicate: object, obj: object) -> None:
        original_emit(subject, predicate, obj)  # Keep parser behavior unchanged.
        triple = Triple(
            _from_rdf12_resource(subject),
            _from_rdf12_resource(predicate),
            _from_rdf12_node(obj),
        )
        _write_spooled_triple(output, triple)
        parser.triples.clear()

    parser.emit = emit_spooled  # type: ignore[method-assign]
    parser.parse()
    prefixes = {
        "rdf": RDF_NS,
        "rdfs": RDFS_NS,
        "xsd": XSD_NS,
    }
    prefixes.update(parser.prefixes)
    return prefixes


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
        writer: CypherWriter = Variant1Writer(prefixes)
    elif variant == 2:
        writer = Variant2Writer(prefixes, folding=folding)
    elif variant == 3:
        writer = Variant3Writer(prefixes)
    else:
        raise ValueError(f"Unsupported mapping variant: {variant}")
    return writer.write(triples)


def convert_large(
    text: str,
    variant: int = 3,
    source: str = "<string>",
    output: TextIO | None = None,
    batch_size: int = 1000,
    folding: str = "fixed",
) -> str | None:
    if batch_size < 1:
        raise ValueError("batch_size must be greater than 0")

    owns_output = output is None
    if output is None:
        output = io.StringIO()

    with tempfile.TemporaryDirectory(prefix="rdf12-to-neo4j-") as temp_dir:
        triples_path = os.path.join(temp_dir, "triples.jsonl")
        with open(triples_path, "w", encoding="utf-8") as spool:
            prefixes = spool_turtle_rdf12(text, spool, source=source)

        if variant == 1:
            LargeVariant1Writer(prefixes, output, batch_size).write_from_spool(
                triples_path,
                os.path.join(temp_dir, "variant1-index"),
            )
        elif variant == 2:
            LargeVariant2Writer(
                prefixes,
                output,
                batch_size,
                folding=folding,
            ).write_from_spool(triples_path)
        elif variant == 3:
            LargeVariant3Writer(prefixes, output, batch_size).write_from_spool(
                triples_path,
                os.path.join(temp_dir, "variant3-index"),
            )
        else:
            raise ValueError(f"Unsupported mapping variant: {variant}")

    if owns_output:
        assert isinstance(output, io.StringIO)
        return output.getvalue()
    return None


def main(argv: list[str] | None = None) -> int:
    argp = argparse.ArgumentParser(description="Convert RDF 1.2 Turtle to Cypher.")
    argp.add_argument(
        "input", nargs="?", help="Turtle input file. Reads stdin when omitted."
    )
    argp.add_argument(
        "-o", "--output", help="Cypher output file. Writes stdout when omitted."
    )
    argp.add_argument(
        "--large-file",
        action="store_true",
        help="Generate batched Cypher using a disk-backed strategy selected for the variant.",
    )
    argp.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows per generated Cypher batch when --large-file is enabled (default: 1000).",
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
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                if args.large_file:
                    convert_large(
                        text,
                        args.variant,
                        source=source,
                        output=f,
                        batch_size=args.batch_size,
                        folding=args.folding,
                    )
                else:
                    f.write(
                        convert(
                            text,
                            args.variant,
                            source=source,
                            folding=args.folding,
                        )
                    )
        else:
            if args.large_file:
                convert_large(
                    text,
                    args.variant,
                    source=source,
                    output=sys.stdout,
                    batch_size=args.batch_size,
                    folding=args.folding,
                )
            else:
                sys.stdout.write(
                    convert(
                        text,
                        args.variant,
                        source=source,
                        folding=args.folding,
                    )
                )
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
