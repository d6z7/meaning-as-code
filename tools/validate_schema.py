#!/usr/bin/env python3
"""
validate_schema.py — THE structural validator for MAC v0.1.9. Schema-driven.

Unlike the retired hand-coded validate_schema_v3.py (which encoded the v0.4 structural rules in
Python), this validator is driven by the FORMAL SCHEMA: it validates every MAC YAML file against
`mac.schema.json`. The schema is the single source of structural truth — closed core vocabulary,
class/level/type/role enums, required keys, render_kind↔payload, and the `x-` extension namespace.
Add a rule to the schema, not to this file.

It also runs the one structural check a JSON Schema cannot express — an edge-enrichment WARNING
(a physical edge that carries neither a `join_rule:` nor a concrete `realized_by:` FK is not yet
wired). Cross-file/referential checks (does `derived_by_rule` resolve, are grounding targets present)
are a SEPARATE concern — see the referential checker — and are intentionally not here.

File type is chosen by location: */rules.yaml→RulesFile, */edges.yaml→EdgesFile, */tables/*.yaml (and
the two-plane data/datasets/)→TableFile, data/transforms/→TransformFile, data/sources/→TableFile (raw
schema-of-record), */concepts/**→ConceptFile. Dates load as strings (PyYAML would otherwise yield dates).

A clean run (exit 0) means WELL-FORMED (L1), not CORRECT — L2 (execution validation) and L3 (SME)
remain mandatory; see CONFORMANCE.md.

Usage:  python3 tools/validate_schema.py [root] [--schema <mac.schema.json>] [--strict] [--all]
        --strict : warnings also fail the run.
Exit:   0 = clean · 1 = schema violations (or warnings under --strict) · 2 = setup error (deps/schema)
"""
import sys, os, glob, json, argparse
from mac_project import resolve


def _load_yaml_str_dates(path):
    import yaml
    class _Loader(yaml.SafeLoader):
        pass
    _Loader.add_constructor('tag:yaml.org,2002:timestamp',
                            lambda loader, node: loader.construct_scalar(node))
    with open(path) as fh:
        return yaml.load(fh, Loader=_Loader)


def _pick_def(path, layout=None):
    p = path.replace(os.sep, '/')
    if p.endswith('rules.yaml'):
        return 'RulesFile'
    if p.endswith('edges.yaml'):
        return 'EdgesFile'
    d = os.path.dirname(os.path.abspath(path))
    # two-plane data plane: transforms/ -> TransformFile; sources/ -> TableFile (raw schema-of-record)
    if layout is not None and getattr(layout, 'transforms', None) and d == str(layout.transforms):
        return 'TransformFile'
    if layout is not None and getattr(layout, 'sources', None) and d == str(layout.sources):
        return 'TableFile'
    descriptors_dir = getattr(layout, 'descriptors', None) if layout is not None else None
    if '/tables/' in p or (descriptors_dir and d == str(descriptors_dir)):
        return 'TableFile'
    return 'ConceptFile'


def _edge_enrichment_warnings(path, doc):
    """The one structural check JSON Schema can't do: a physical edge wired by nothing."""
    warns = []
    for e in (doc.get('edges') or []):
        if e.get('level') != 'physical':
            continue
        if e.get('join_rule'):
            continue
        rb = str(e.get('realized_by') or '')
        if (not rb) or ('TODO' in rb):
            eid = e.get('edge_id', '<no id>')
            warns.append(f"WARN   {path} [{eid}]: physical edge not yet enriched — "
                         f"no `join_rule:` and `realized_by:` is a TODO/absent")
    return warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default='.',
                    help='base dir to scan (positional, matching check_references.py); defaults to cwd')
    ap.add_argument('--schema',
                    default=os.path.join(os.path.dirname(__file__), '..', 'mac.schema.json'))
    ap.add_argument('--strict', action='store_true', help='warnings also fail the run')
    ap.add_argument('--all', action='store_true',
                    help='validate every file regardless of metadata.schema_version '
                         '(default: only enforce files at a recognized schema_version (current 0.1.9); others are skipped)')
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

    SKIP = {'.git', 'node_modules', '.venv', '__pycache__', 'projections'}  # projections/ = generated exports, not source
    skip = lambda p: any(part in SKIP for part in p.split(os.sep))

    layout = resolve(args.root)          # flat, or two-plane (mac.project.yaml)
    files = []
    for pat in ('**/concepts/**/*.yaml', '**/rules.yaml', '**/edges.yaml', '**/tables/*.yaml'):
        files += [f for f in glob.glob(os.path.join(args.root, pat), recursive=True) if not skip(f)]
    files += [f for f in glob.glob(str(layout.descriptors / '*.yaml')) if not skip(f)]  # two-plane: data/datasets/
    for extra in (getattr(layout, 'transforms', None), getattr(layout, 'sources', None)):  # data/transforms/, data/sources/
        if extra:
            files += [f for f in glob.glob(str(extra / '*.yaml')) if not skip(f)]
    files = sorted(set(files))

    CURRENT = '0.1.12'                        # current MAC schema version (0.1.12 added the relationAliasBlock + business-edge shared_attribute type + edge.resolved_by/aliases)
    RECOGNIZED = {CURRENT, '0.1.11', '0.1.10', '0.1.9'} # TRANSITIONAL: each bump is additive, so older content stays checked during
                                              # migration (not orphaned). Drop older versions once all content reconforms —
                                              # that finish is dev-only, not for main.
    errors, warnings, clean, skipped = [], [], 0, 0
    for f in files:
        try:
            doc = _load_yaml_str_dates(f)
        except Exception as e:
            errors.append(f"ERROR  {f}: YAML parse failed: {e}")
            continue
        if not isinstance(doc, dict):
            continue
        sv = str((doc.get('metadata') or {}).get('schema_version', ''))
        if not args.all and sv not in RECOGNIZED:
            skipped += 1   # legacy / not-yet-migrated — incremental adoption (use --all to force)
            continue
        which = _pick_def(f, layout)
        errs = sorted(Draft202012Validator(sub(which)).iter_errors(doc), key=lambda e: list(e.path))
        if which == 'EdgesFile':
            warnings += _edge_enrichment_warnings(f, doc)
        if not errs:
            clean += 1
            continue
        for e in errs:
            loc = '/'.join(map(str, e.path)) or '(root)'
            errors.append(f"ERROR  {f} [{which}] @{loc}: {e.message}")

    for w in warnings:
        print(w)
    for e in errors:
        print(e)
    checked = len(files) - skipped
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s); {clean}/{checked} checked file(s) clean, "
          f"{skipped} skipped (schema_version not recognized — current {CURRENT}; use --all to include).  "
          f"(schema-driven L1 gate — not correctness; see CONFORMANCE.md.)")
    fail = bool(errors) or (args.strict and bool(warnings))
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
