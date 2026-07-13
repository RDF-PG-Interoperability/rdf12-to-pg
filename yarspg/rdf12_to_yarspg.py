#!/usr/bin/env python3
"""Compatibility module and CLI launcher for RDF 1.2 Turtle to YARS-PG."""

import sys

from rdf12_to_yarspg_lib import convert, parse_turtle_rdf12
from rdf12_to_yarspg_lib.converter import main

__all__ = ["convert", "parse_turtle_rdf12"]


if __name__ == "__main__":
    sys.argv[0] = "rdf12_to_yarspg"
    raise SystemExit(main())
