#!/usr/bin/env python3
"""Compatibility module and CLI launcher for the synthetic RDF 1.2 generator."""

import sys

from synthetic_gen_lib import GeneratorConfig, PROFILES, generate_turtle
from synthetic_gen_lib.generator import main

__all__ = ["GeneratorConfig", "PROFILES", "generate_turtle"]


if __name__ == "__main__":
    sys.argv[0] = "synthetic_gen"
    raise SystemExit(main())
