#!/usr/bin/env python3
"""Compatibility module and CLI launcher for RDF 1.2 Turtle to Cypher."""

import sys

from rdf12_to_neo4j_lib import convert, convert_large, parse_turtle_rdf12
from rdf12_to_neo4j_lib.converter import main

__all__ = ["convert", "convert_large", "parse_turtle_rdf12"]


if __name__ == "__main__":
    sys.argv[0] = "rdf12_to_neo4j"
    raise SystemExit(main())
