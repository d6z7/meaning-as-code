#!/usr/bin/env python3
"""
test_negative.py — "test the validator": every fixture under tests/fixtures/ is INTENTIONALLY
malformed and MUST be rejected by mac.schema.json. Proves the gate rejects bad input (the good
example proves it accepts good input; this proves the other half).

Fixture file type is taken from the name: *.concept.yaml / *.edges.yaml / *.rules.yaml / *.table.yaml.
A fixture that the schema ACCEPTS is a test FAILURE (the gate has a hole).

Usage:  python3 tests/test_negative.py
Exit:   0 = all fixtures correctly rejected · 1 = a fixture slipped through · 2 = setup error
"""
import sys, os, json, glob

HERE = os.path.dirname(__file__)
SCHEMA = os.path.join(HERE, '..', 'mac.schema.json')
DEF = {'concept': 'ConceptFile', 'edges': 'EdgesFile', 'rules': 'RulesFile', 'table': 'TableFile',
       'transform': 'TransformFile'}

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as e:
    print(f"[setup] missing '{e.name}': pip install jsonschema pyyaml", file=sys.stderr); sys.exit(2)

schema = json.load(open(SCHEMA))
Draft202012Validator.check_schema(schema)

def sub(name):
    s = {k: v for k, v in schema.items() if k != 'oneOf'}; s['$ref'] = f'#/$defs/{name}'; return s

def kind(path):
    parts = os.path.basename(path).split('.')        # bad_x.concept.yaml -> ['bad_x','concept','yaml']
    return DEF.get(parts[-2]) if len(parts) >= 3 else None

ok = bad = 0
for f in sorted(glob.glob(os.path.join(HERE, 'fixtures', '*.yaml'))):
    which = kind(f)
    if not which:
        print(f"?  {os.path.basename(f)}: cannot infer file type from name — skip"); continue
    doc = yaml.safe_load(open(f))
    errs = list(Draft202012Validator(sub(which)).iter_errors(doc))
    name = os.path.basename(f)
    if errs:
        ok += 1
        print(f"✓ rejected  {name:34} [{which}]  → {errs[0].message[:60]}")
    else:
        bad += 1
        print(f"✗ ACCEPTED  {name:34} [{which}]  → SCHEMA HOLE: this should have been rejected")

print(f"\n{ok} correctly rejected, {bad} wrongly accepted.")
sys.exit(1 if bad else 0)
