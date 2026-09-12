#!/usr/bin/env python3
"""Validate ONE MAC concept YAML against the fork's mac.schema.json. Reports every
schema error (or PASS). Run with system python3 (has jsonschema + yaml)."""

import sys
from pathlib import Path

import yaml
from jsonschema import validators as jsv

from sdk.grammar.resolve import load_schema as _load_schema  # ONE schema home

SCHEMA = _load_schema()
V = jsv.validator_for(SCHEMA)(SCHEMA)


def main():
    if len(sys.argv) < 2:
        print("usage: validate_one.py <concept.yaml>", file=sys.stderr)
        return 2
    p = Path(sys.argv[1])
    try:
        obj = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        print(f"FAIL — not valid YAML: {e}")
        return 1
    errs = sorted(V.iter_errors(obj), key=lambda e: list(e.path))
    if not errs:
        top = list(obj.keys()) if isinstance(obj, dict) else type(obj).__name__
        rules = len(((obj or {}).get("contract") or {}).get("rules") or [])
        print(f"PASS — valid MAC concept · top-level keys: {top} · contract.rules: {rules}")
        return 0
    print(f"FAIL — {len(errs)} schema error(s):")
    for e in errs[:20]:
        loc = "/".join(str(x) for x in e.path) or "(root)"
        print(f"  · at {loc}: {e.message[:200]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
