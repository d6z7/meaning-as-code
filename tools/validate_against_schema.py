#!/usr/bin/env python3
"""
validate_against_schema.py — the strict L1 structural gate for MAC v0.5.

Validates every MAC YAML file under --root against mac.schema.json (the closed-core schema).
File type is chosen by location: */rules.yaml -> RulesFile, */edges.yaml -> EdgesFile,
*/tables/*.yaml -> TableFile, anything under */concepts/ -> ConceptFile. Dates are loaded as
strings (PyYAML would otherwise yield date objects). Unknown keys outside the `x-` namespace are
rejected — that is the closed-core discipline.

L1 = well-formed against the schema. It does NOT prove correctness; L2 (execution validation) and
L3 (SME) remain mandatory — see CONFORMANCE.md.

This is an ADDITIVE companion to the hand-coded checks in validate_schema*.py (which do the
semantic checks a JSON Schema cannot: naming-contract heuristics, cross-file ref resolution). The
two are intended to converge once branch layout settles.

Usage:  python3 tools/validate_against_schema.py [--root .] [--schema <path to mac.schema.json>]
Exit:   0 = clean · 1 = schema violations · 2 = setup error (missing deps / unreadable schema)
"""
import sys, os, glob, json, argparse


def _load_yaml_str_dates(path):
    import yaml
    class _Loader(yaml.SafeLoader):
        pass
    # coerce YAML timestamps/dates to plain strings so date-bearing fields validate uniformly
    _Loader.add_constructor('tag:yaml.org,2002:timestamp',
                            lambda loader, node: loader.construct_scalar(node))
    with open(path) as fh:
        return yaml.load(fh, Loader=_Loader)


def _pick_def(path):
    p = path.replace(os.sep, '/')
    if p.endswith('rules.yaml'):
        return 'RulesFile'
    if p.endswith('edges.yaml'):
        return 'EdgesFile'
    if '/tables/' in p:
        return 'TableFile'
    return 'ConceptFile'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--schema',
                    default=os.path.join(os.path.dirname(__file__), '..', 'mac.schema.json'))
    args = ap.parse_args()

    try:
        import yaml  # noqa: F401
        from jsonschema import Draft202012Validator
    except ImportError as e:
        print(f"[setup] missing dependency '{e.name}'. Install:  pip install jsonschema pyyaml",
              file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.schema) as fh:
            schema = json.load(fh)
        Draft202012Validator.check_schema(schema)
    except Exception as e:
        print(f"[setup] could not load/validate schema at {args.schema}: {e}", file=sys.stderr)
        sys.exit(2)

    def sub(name):
        s = {k: v for k, v in schema.items() if k != 'oneOf'}
        s['$ref'] = f'#/$defs/{name}'
        return s

    SKIP = {'.git', 'node_modules', '.venv', '__pycache__'}
    skip = lambda p: any(part in SKIP for part in p.split(os.sep))

    files = []
    for pat in ('**/concepts/**/*.yaml', '**/rules.yaml', '**/edges.yaml', '**/tables/*.yaml'):
        files += [f for f in glob.glob(os.path.join(args.root, pat), recursive=True) if not skip(f)]
    files = sorted(set(files))

    total_err = clean = 0
    for f in files:
        try:
            doc = _load_yaml_str_dates(f)
        except Exception as e:
            print(f"ERROR  {f}: YAML parse failed: {e}")
            total_err += 1
            continue
        if not isinstance(doc, dict):
            continue
        which = _pick_def(f)
        errs = sorted(Draft202012Validator(sub(which)).iter_errors(doc), key=lambda e: list(e.path))
        if not errs:
            clean += 1
            continue
        for e in errs:
            loc = '/'.join(map(str, e.path)) or '(root)'
            print(f"ERROR  {f} [{which}] @{loc}: {e.message}")
            total_err += 1

    print(f"\n{total_err} schema error(s) across {len(files)} file(s); {clean} clean.  "
          f"(L1 strict-schema gate only — not correctness; see CONFORMANCE.md.)")
    sys.exit(1 if total_err else 0)


if __name__ == '__main__':
    main()
