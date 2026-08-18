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

REUSABLE SURFACE (added 2026-08-18, for mac_checks_structure.py). The bundle ENUMERATION and the
per-file VALIDATION are the two facts this file owns, and the diagnostic compiler needs both. They are
exposed as `enumerate_bundle()` and `validate_files()`; `main()` is now a renderer over them and holds
no selection logic of its own. A second enumerator would be a second answer to "what does MAC define",
and the first bundle where the two disagreed would be unarguable — which is the defect this whole gate
exists to catch.
"""
import sys, os, glob, json, argparse, fnmatch
from dataclasses import dataclass, field
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
    # basename-EXACT: only the canonical ontology files are Rules/Edges docs. A data-plane
    # descriptor for a VIEW that happens to be named *_rules/*_edges (fpl.meta_rules,
    # fpl.meta_edges) is a TableFile and fell through this suffix match before.
    base = os.path.basename(p)
    if base == 'mac.project.yaml':
        return 'ProjectFile'
    # v0.1.14 — the nine artifacts that were MAC001 on every bundle that had them. Routed by their
    # canonical location/basename, the same way rules.yaml and edges.yaml are.
    _BY_BASE = {
        'properties.yaml': 'PropertiesFile',
        'ledger.yaml': 'InterventionLedgerFile',
        'vanilla_delta.yaml': 'VanillaDeltaFile',
        'data_quality_register.yaml': 'DataQualityRegisterFile',
        'impurity_resolution_map.yaml': 'ImpurityResolutionMapFile',
        'PHASE.yaml': 'PhaseFile',
        'shapes.yaml': 'ShapesFile',
    }
    if base in _BY_BASE:
        return _BY_BASE[base]
    if base.endswith('.sections.yaml'):
        return 'KnowledgeSectionsFile'
    if '/protosql/' in p:
        return 'ProtoSqlFile'
    if base == 'rules.yaml':
        return 'RulesFile'
    if base == 'edges.yaml':
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


# ── the shared surface: ENUMERATION and VALIDATION ────────────────────────────────────────────────
# Both were inline in main() until 2026-08-18. They are lifted out unchanged so the diagnostic compiler
# (tools/mac_checks_structure.py) reads the SAME answer this gate prints, rather than re-deriving it.

SKIP = {'.git', 'node_modules', '.venv', '__pycache__', 'projections'}  # projections/ = generated exports, not source
CURRENT = '0.1.13'                        # current MAC schema version = mac_vocabulary.yaml `version` (0.1.13 added the OPTIONAL typed-rule `subject` field + the vocab's aggregation_effect.averageable / MeasureType.Intensive; additive over 0.1.12's relationAliasBlock + business-edge shared_attribute + edge.resolved_by/aliases)
RECOGNIZED = {CURRENT, '0.1.12', '0.1.11', '0.1.10', '0.1.9'} # TRANSITIONAL: each bump is additive, so older content stays checked during
                                          # migration (not orphaned). Drop older versions once all content reconforms —
                                          # that finish is dev-only, not for main.

# REGISTERS ARE NOT VERSIONED CONTENT. The schema_version gate exists so a CONCEPT file written against
# an older grammar is not judged by a newer one during migration. A register (a ledger, a DQ list, a
# phase switch, a knowledge extraction) has no such evolution story and carries no stamp — gold's own
# sme_ledger.yaml says so in its header: "No schema_version (registry, not a concept file)".
# Without this exemption the nine definitions added in v0.1.14 would be DECORATIVE: routed, matched to
# a definition, and then skipped for having no version — coverage that reads as 0 undefined while
# nothing is actually checked. Measured: it hid a real defect (a DQ finding using the properties
# severity vocabulary) until --all was passed.
UNVERSIONED_DEFS = {
    'PropertiesFile', 'InterventionLedgerFile', 'VanillaDeltaFile', 'DataQualityRegisterFile',
    'ImpurityResolutionMapFile', 'KnowledgeSectionsFile', 'PhaseFile', 'ShapesFile', 'ProtoSqlFile',
    'ProjectFile',
}



def _skipped(p):
    return any(part in SKIP for part in p.split(os.sep))


@dataclass(frozen=True)
class Enumeration:
    """What the bundle CONTAINS vs what MAC DEFINES — the deny-unknown answer, as data."""
    root: str
    layout: object
    routed: tuple = ()        # abs paths MAC has a schema definition for (the allowlist)
    all_yaml: tuple = ()      # abs paths of every yaml in the bundle (SKIP dirs and dotfiles excluded)
    declared: tuple = ()      # mac.project.yaml#conformance.out_of_scope path patterns, verbatim
    unknown: tuple = ()       # bundle-relative: no definition, not declared out of scope
    waived: tuple = ()        # bundle-relative: no definition, declared out of scope

    def rel(self, abspath):
        return os.path.relpath(abspath, self.root)


def out_of_scope_patterns(root):
    """The bundle's declared escape hatch. A broken manifest yields NONE — it must not silently widen
    coverage by making every unknown file look waived."""
    proj = os.path.join(root, 'mac.project.yaml')
    if not os.path.exists(proj):
        return []
    try:
        pd = _load_yaml_str_dates(proj) or {}
    except Exception:
        return []
    return [str(e.get('path', '')) for e
            in ((pd.get('conformance') or {}).get('out_of_scope') or []) if isinstance(e, dict)]


def enumerate_bundle(root, layout=None):
    """THE enumeration. Everything above `main` builds an ALLOWLIST of glob patterns and validates only
    what matches. A file outside those patterns was never rejected and never skipped — it was never
    looked at, while the summary printed "N/N checked file(s) clean", which reads as complete coverage.
    Measured on a live bundle: 218 yaml files, 61 matched, 156 invisible — including a 142-file
    acceptance plane and seven artifacts invented on top of the standard.

    An allowlist validator cannot detect invention: you cannot violate a pattern you do not match.
    CONFORMANCE.md §2 already rules that the only legal way to add something the core does not define is
    a DECLARED extension — "an x- key with no profile entry is undeclared debt, not license". Nothing
    implemented the enumeration that makes that rule enforceable. This does.

    A bundle may still own files MAC does not define — but it must SAY SO, in mac.project.yaml:
        conformance:
          out_of_scope:
            - path: acceptance/**
              reason: "testing plane; MAC has no schema for it — see decisions/00NN"
    Declared debt is visible and arguable. Silent debt is how a standard stops being one."""
    layout = layout if layout is not None else resolve(root)
    files = []
    for pat in ('**/concepts/**/*.yaml', '**/rules.yaml', '**/edges.yaml', '**/tables/*.yaml'):
        files += [f for f in glob.glob(os.path.join(root, pat), recursive=True) if not _skipped(f)]
    files += [f for f in glob.glob(str(layout.descriptors / '*.yaml')) if not _skipped(f)]  # two-plane: data/datasets/
    for extra in (getattr(layout, 'transforms', None), getattr(layout, 'sources', None)):   # data/transforms/, data/sources/
        if extra:
            files += [f for f in glob.glob(str(extra / '*.yaml')) if not _skipped(f)]
    proj = os.path.join(root, 'mac.project.yaml')                                     # the bundle MANIFEST
    if os.path.exists(proj) and not _skipped(proj):
        files.append(proj)
    # v0.1.14 — the nine artifacts MAC gained definitions for. COLLECTED here, routed in _pick_def.
    # Both halves are needed: a definition nothing enumerates is a definition nothing applies.
    for pat in ('acceptance/properties.yaml', 'interventions/ledger.yaml',
                'interventions/vanilla_delta.yaml', 'data/quality/data_quality_register.yaml',
                'data/quality/impurity_resolution_map.yaml', 'knowledge/*.sections.yaml',
                'ontology/PHASE.yaml', 'ontology/shapes.yaml', 'ontology/protosql/*.yaml'):
        files += [f for f in glob.glob(os.path.join(root, pat)) if not _skipped(f)]
    files = sorted(set(files))

    all_yaml = sorted(set(f for f in glob.glob(os.path.join(root, '**', '*.yaml'), recursive=True)
                          if not _skipped(f) and not os.path.basename(f).startswith('.')))
    declared = out_of_scope_patterns(root)

    def is_declared(relpath):
        return any(fnmatch.fnmatch(relpath, d) or relpath.startswith(d.rstrip('*').rstrip('/') + '/')
                   for d in declared if d)

    known = {os.path.realpath(f) for f in files}
    unknown, waived = [], []
    for f in all_yaml:
        # NO SPECIAL CASES. mac.project.yaml used to be exempted here by basename, which meant the
        # one file where a bundle declares its own conformance was the one file nobody checked. It is
        # now routed to $defs/ProjectFile above and arrives in `known` like everything else.
        if os.path.realpath(f) in known:
            continue
        rel = os.path.relpath(f, root)
        (waived if is_declared(rel) else unknown).append(rel)
    return Enumeration(root=root, layout=layout, routed=tuple(files), all_yaml=tuple(all_yaml),
                       declared=tuple(declared), unknown=tuple(unknown), waived=tuple(waived))


@dataclass(frozen=True)
class FileVerdict:
    """One routed file's L1 outcome. `errors` carry the jsonschema keyword and schema path so a caller
    can GROUP by violation kind instead of printing one line per file."""
    path: str
    definition: str                  # the $defs name it was routed to
    schema_version: str
    parse_error: str = None
    skipped: bool = False            # schema_version not recognized (and --all not given)
    errors: tuple = ()               # (yaml_path, message, keyword, schema_path)
    warnings: tuple = ()             # verbatim strings from _edge_enrichment_warnings


def load_schema(path=None):
    """The schema, checked. Raises on a broken schema — that is programmer/setup error, not content."""
    from jsonschema import Draft202012Validator
    p = path or os.path.join(os.path.dirname(__file__), '..', 'mac.schema.json')
    with open(p) as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return schema


def validate_files(enum, schema=None, all_versions=False):
    """Validate every ROUTED file against its definition. Returns one FileVerdict per file, in
    enumeration order. No printing, no exit code — the callers differ on both."""
    from jsonschema import Draft202012Validator
    schema = schema if schema is not None else load_schema()

    def sub(name):
        s = {k: v for k, v in schema.items() if k != 'oneOf'}
        s['$ref'] = f'#/$defs/{name}'
        return s

    out = []
    for f in enum.routed:
        try:
            doc = _load_yaml_str_dates(f)
        except Exception as e:
            out.append(FileVerdict(path=f, definition='', schema_version='', parse_error=str(e)))
            continue
        if not isinstance(doc, dict):
            continue
        sv = str((doc.get('metadata') or {}).get('schema_version', ''))
        which = _pick_def(f, enum.layout)
        if not all_versions and which not in UNVERSIONED_DEFS and sv not in RECOGNIZED:
            out.append(FileVerdict(path=f, definition=which, schema_version=sv, skipped=True))
            continue
        errs = sorted(Draft202012Validator(sub(which)).iter_errors(doc), key=lambda e: list(e.path))
        warns = tuple(_edge_enrichment_warnings(f, doc)) if which == 'EdgesFile' else ()
        out.append(FileVerdict(
            path=f, definition=which, schema_version=sv, warnings=warns,
            errors=tuple(('/'.join(map(str, e.path)) or '(root)', e.message, e.validator,
                          '/'.join(map(str, e.absolute_schema_path))) for e in errs)))
    return out


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
        import jsonschema  # noqa: F401
    except ImportError as e:
        print(f"[setup] missing dependency '{e.name}'. Install:  pip install jsonschema pyyaml",
              file=sys.stderr)
        sys.exit(2)

    try:
        schema = load_schema(args.schema)
    except Exception as e:
        print(f"[setup] could not load/validate schema at {args.schema}: {e}", file=sys.stderr)
        sys.exit(2)

    enum = enumerate_bundle(args.root)              # flat, or two-plane (mac.project.yaml)
    files, unknown, waived = enum.routed, list(enum.unknown), len(enum.waived)

    errors, warnings, clean, skipped = [], [], 0, 0
    for v in validate_files(enum, schema, all_versions=args.all):
        if v.parse_error:
            errors.append(f"ERROR  {v.path}: YAML parse failed: {v.parse_error}")
            continue
        if v.skipped:
            skipped += 1   # legacy / not-yet-migrated — incremental adoption (use --all to force)
            continue
        warnings += list(v.warnings)
        if not v.errors:
            clean += 1
            continue
        for loc, msg, _kw, _sp in v.errors:
            errors.append(f"ERROR  {v.path} [{v.definition}] @{loc}: {msg}")

    # Deny-unknown reports as a ROOT plus witnesses, never one line per file: a gate that emits 157
    # identical lines is muted within a week and its root cause dies with it.
    if unknown:
        import collections as _c
        by_dir = _c.Counter(os.path.dirname(u) or '.' for u in unknown)
        errors.append(f"ERROR  {len(unknown)} file(s) carry no MAC definition and are not declared "
                      f"out of scope — MAC cannot validate, track or enforce them")
        for d, n in sorted(by_dir.items(), key=lambda kv: -kv[1]):
            ex = next(u for u in unknown if (os.path.dirname(u) or '.') == d)
            errors.append(f"         {n:>4}  {d}/    e.g. {os.path.basename(ex)}")
        errors.append("         declare them in mac.project.yaml#conformance.out_of_scope with a "
                      "reason, or bring them under a schema definition")

    for w in warnings:
        print(w)
    for e in errors:
        print(e)
    checked = len(files) - skipped
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s); {clean}/{checked} checked file(s) clean, "
          f"{skipped} skipped (schema_version not recognized — current {CURRENT}; use --all to include); "
          f"{len(enum.all_yaml)} yaml in bundle, {len(unknown)} undefined, {waived} declared out of scope.  "
          f"(schema-driven L1 gate — not correctness; see CONFORMANCE.md.)")
    fail = bool(errors) or (args.strict and bool(warnings))
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
