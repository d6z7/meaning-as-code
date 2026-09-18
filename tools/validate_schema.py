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
import sys, os, glob, json, argparse, fnmatch, collections
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
    # descriptor for a VIEW that happens to be named *_rules/*_edges (<dataset>.meta_rules,
    # <dataset>.meta_edges) is a TableFile and fell through this suffix match before.
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
        'sme_ledger.yaml': 'SmeLedgerFile',
        # v0.1.19 — the data pipeline's declared exit. Routed by basename like its
        # siblings, so the sign-off is CHECKED rather than excused: without this it
        # would arrive as "carries no MAC definition" and a bundle would have to
        # declare its own governance artifact out of scope to go green.
        'data_plane_approval.yaml': 'DataPlaneApprovalFile',
    }
    if base in _BY_BASE:
        return _BY_BASE[base]
    # A SUITE IS A SHAPE, NOT A FILENAME. `properties.yaml` was routed by basename alone, so a bundle
    # could hold exactly ONE property suite — and MODELLERS_COOKBOOK B9 tells a modeller to add a
    # second (tier-1 warehouse invariants, tier-2 dimensional retrieval). <domain>/<dataset> did, named it
    # acceptance/retrieval.yaml, and it went MAC001: "carries no MAC definition". The framework asked
    # for the file and then could not classify it.
    if '/acceptance/' in p and base.endswith('.yaml'):
        return 'PropertiesFile'
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
    if layout is not None and getattr(layout, 'profiles', None) and d == str(layout.profiles):
        return 'ProfileFile'
    # v0.1.14 — the DATA plane's measured reference family (data/references/). Routed by directory
    # like its sibling profiles/, and deliberately NOT by the basename `references`: a bundle's
    # root-level `references/` directory holds PROJECTION OUTPUTS and is a different thing entirely.
    if layout is not None and getattr(layout, 'references', None) and d == str(layout.references):
        return 'ReferenceFile'
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
# CURRENT IS A LITERAL AND MUST STAY ONE. tools/version.py rewrites it by regex and applies the
# substitution with `subn`, whose zero-match result is swallowed by an `if n:` — so a COMPUTED
# CURRENT would make `--next` and `--release` quietly stop updating the validator, and `--check`
# quietly stop listing the claim. Nothing would say so. Derive RECOGNIZED; never derive this.
#
# The comment that stood here claimed CURRENT tracked "mac_vocabulary.yaml `version`". That was false
# twice over: version.py's own header records the field not existing at all when the claim was
# written, and today the field exists and says 0.1.13 while this says 0.1.14-develop. A comment
# naming a source is not a source — which is why what replaces it below is checkable instead.
CURRENT = '0.1.14-develop'

# ── THE RECOGNIZED SET IS DERIVED, NOT TYPED ──────────────────────────────────────────────────────
# What stood here was a hand-typed set literal holding CURRENT, its base spelling, and the five
# older patch numbers 0.1.13 down to 0.1.9 — deliberately NOT quoted verbatim here, because at least
# one downstream version pre-flight used to recover the set by REGEX-SCRAPING this file's source, and
# a commented-out example is exactly the kind of thing such a scraper reads as live. Consumers import
# the range from tools/version.py instead; scraping a gate's source was never a contract.
#
# The literal carried a standing obligation nobody could see: on every bump, remember to add the OUTGOING
# version to the set. That obligation was forgotten once already (eda1fae), and the failure mode is
# not a red — it is COVERAGE COLLAPSING BEHIND A PERFECT FRACTION. Measured on this tree with only
# CURRENT moved one generation:
#     a consuming bundle      32/32 checked file(s) clean  ->   4/4 checked file(s) clean, 28 skipped
#     example_tpch_ontology   40/40 checked file(s) clean  ->  26/26 checked file(s) clean, 14 skipped
# both still ending in "clean", tpch still exiting 0, and the headline error count not moving at all.
#
# Membership is now an ORDER, owned by tools/version.py: FLOOR <= base(version) <= base(CURRENT).
# A bump can only ever raise the ceiling, so the set CANNOT NARROW — the trap is unarmable rather
# than merely detected. The pre-release/base pair falls out of the rule (both spellings of every
# generation in range are members) instead of being a special case somebody has to maintain, which
# is the "63 files silently skipped, which is worse than a red" incident made structural.
#
# The floor and the rule live in tools/version.py, which already owns the version grammar and the
# successor rule; it imports only stdlib, so this costs no dependency weight.
from version import (SCHEMA_VERSION_FLOOR as FLOOR, recognized as recognized_for,  # noqa: E402
                     VersionLineError)

try:
    RECOGNIZED = recognized_for(CURRENT, FLOOR)
    RECOGNIZED_ERROR = None
except VersionLineError as _e:      # never raise at import: mac_checks_structure.py, mac_compile.py
    RECOGNIZED, RECOGNIZED_ERROR = None, _e   # and check_conformance.py all import this module.

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
    'ProjectFile', 'DataPlaneApprovalFile',
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
    for extra in (getattr(layout, 'transforms', None), getattr(layout, 'sources', None),
                  getattr(layout, 'profiles', None), getattr(layout, 'references', None)):
        # data/transforms/, data/sources/, data/profiles/, data/references/
        if extra:
            files += [f for f in glob.glob(str(extra / '*.yaml')) if not _skipped(f)]
    proj = os.path.join(root, 'mac.project.yaml')                                     # the bundle MANIFEST
    if os.path.exists(proj) and not _skipped(proj):
        files.append(proj)
    # v0.1.14 — the nine artifacts MAC gained definitions for. COLLECTED here, routed in _pick_def.
    # Both halves are needed: a definition nothing enumerates is a definition nothing applies.
    # BOTH LAYOUTS. <dataset> grew these across four homes (bundle root, ontology/, acceptance/,
    # interventions/); a source scaffolded from v0.1.16 puts them in one `governance/` plane. Routing
    # keys on BASENAME, so it already handled both — collection did not, and a definition nothing
    # enumerates is a definition nothing applies. Second time that half was the one missed.
    for pat in ('acceptance/*.yaml', 'interventions/ledger.yaml',
                'interventions/vanilla_delta.yaml', 'data/quality/data_quality_register.yaml',
                'data/quality/impurity_resolution_map.yaml', 'knowledge/*.sections.yaml',
                'ontology/PHASE.yaml', 'ontology/shapes.yaml', 'ontology/protosql/*.yaml',
                'governance/*.yaml', 'governance/protosql/*.yaml'):
        files += [f for f in glob.glob(os.path.join(root, pat)) if not _skipped(f)]
    # DEDUPE BY REALPATH, not by spelling. `set(files)` deduped the STRING, so a file reachable
    # through two globs under a RELATIVE root arrived twice — once absolute (the layout globs build
    # from layout.descriptors, which is absolute) and once relative (the pattern globs build from
    # `root` as given). Measured on a 4-file bundle addressed relatively: routed=5 over 4 yaml files,
    # the same file validated twice and counted twice. Harmless while `routed` was only a count of
    # work to do; not harmless now that `routed` is the DENOMINATOR the summary publishes.
    _seen, _files = set(), []
    for f in sorted(files):
        rp = os.path.realpath(f)
        if rp not in _seen:
            _seen.add(rp)
            _files.append(f)
    files = _files

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


# The three ways a ROUTED file can end up not validated. They are named, not folded into one boolean,
# because their remedies differ and a finding that cannot say which one it is cannot be acted on:
UNCHECKED_REASONS = {
    'stamp-not-recognized': 'metadata.schema_version is outside the recognized range — either the '
                            'file is a generation the framework no longer checks and must be '
                            'reconformed, or the range is missing a version that really exists',
    'no-stamp':             'no metadata.schema_version at all — add the stamp, or the file is '
                            'misrouted and the definition it was matched to is the wrong one',
    'not-a-mapping':        "the file's top level is a list or a scalar, so no definition could be "
                            'applied to it — restructure it, or route it somewhere that accepts it',
}


@dataclass(frozen=True)
class FileVerdict:
    """One routed file's L1 outcome. `errors` carry the jsonschema keyword and schema path so a caller
    can GROUP by violation kind instead of printing one line per file.

    EVERY routed file gets exactly one of these, unconditionally. It used to be possible for a routed
    file to produce none — `if not isinstance(doc, dict): continue` dropped it silently — and a file
    that produces no verdict vanishes from the numerator AND the denominator at once, which is the
    self-normalising defect this gate exists to catch, one layer down inside the gate itself."""
    path: str
    definition: str                  # the $defs name it was routed to
    schema_version: str
    parse_error: str = None
    unchecked_reason: str = None     # one of UNCHECKED_REASONS, or None if the file WAS validated
    stamp_error: str = None          # validated, but its stamp is wrong (see the exempt-register rule)
    errors: tuple = ()               # (yaml_path, message, keyword, schema_path)
    warnings: tuple = ()             # verbatim strings from _edge_enrichment_warnings

    @property
    def skipped(self) -> bool:
        """DERIVED, never stored. One fact, one field: a second boolean beside `unchecked_reason` is
        how the gate and the diagnostic compiler drift apart again. Kept as a property so
        mac_checks_structure.py's `if v.skipped` keeps working and picks up all three reasons free."""
        return self.unchecked_reason is not None


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

    if RECOGNIZED is None:          # a floor above its own ceiling — setup error, never a content red
        raise VersionLineError(str(RECOGNIZED_ERROR))

    out = []
    for f in enum.routed:
        which = _pick_def(f, enum.layout)          # hoisted: a file must be NAMED even when unreadable
        try:
            doc = _load_yaml_str_dates(f)
        except Exception as e:
            out.append(FileVerdict(path=f, definition=which, schema_version='', parse_error=str(e)))
            continue
        if not isinstance(doc, dict):
            # THE SILENT DROP, closed. This was a bare `continue`, so the file produced no verdict at
            # all: invisible to the clean count, to the skipped count, and to every consumer of this
            # list. Measured, one live file in the estate takes this branch.
            out.append(FileVerdict(path=f, definition=which, schema_version='',
                                   unchecked_reason='not-a-mapping'))
            continue
        sv = str((doc.get('metadata') or {}).get('schema_version', ''))
        exempt = which in UNVERSIONED_DEFS
        if not all_versions and not exempt and sv not in RECOGNIZED:
            out.append(FileVerdict(path=f, definition=which, schema_version=sv,
                                   unchecked_reason='no-stamp' if not sv else 'stamp-not-recognized'))
            continue
        # A REGISTER MAY OMIT THE STAMP. IT MAY NOT CARRY A WRONG ONE. The exemption above is from the
        # version GATE, not from the version being true — so an exempt file that stamps itself anyway
        # had its stamp read by nothing at all. Measured: one live register declares '0.1', a version
        # MAC has never had, and no gate anywhere said so.
        stamp_err = None
        if exempt and sv and sv not in RECOGNIZED:
            stamp_err = (f"register carries metadata.schema_version {sv!r}, which is outside the "
                         f"recognized range ({RECOGNIZED.describe()}) — registers may OMIT the stamp, "
                         f"they may not carry a wrong one; delete the key or correct it")
        errs = sorted(Draft202012Validator(sub(which)).iter_errors(doc), key=lambda e: list(e.path))
        warns = tuple(_edge_enrichment_warnings(f, doc)) if which == 'EdgesFile' else ()
        out.append(FileVerdict(
            path=f, definition=which, schema_version=sv, warnings=warns, stamp_error=stamp_err,
            errors=tuple(('/'.join(map(str, e.path)) or '(root)', e.message, e.validator,
                          '/'.join(map(str, e.absolute_schema_path))) for e in errs)))
    return out


# ── COVERAGE: ONE HOME FOR THE DENOMINATOR ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Coverage:
    """How much of the bundle was actually validated — the number the old summary could not express.

    `checked = len(files) - skipped` was the whole defect in one expression: a skipped file left the
    numerator AND the denominator together, so the fraction re-normalised to N/N at the exact moment
    it stopped meaning anything. THE DENOMINATOR IS `routed`, which is fixed by the enumeration and
    is invariant under any change to the recognized range. It is computed in exactly one place —
    here — so nobody can recompute it differently.
    """
    routed: int
    validated: int          # went through jsonschema
    gated: int              # validated AND version-gated
    exempt: int             # validated but exempt from the version gate (registers, the manifest)
    clean: int
    errored: int
    unchecked: int
    unparsed: int

    @property
    def unaccounted(self) -> int:
        return self.routed - (self.clean + self.errored + self.unchecked + self.unparsed)


def coverage(enum, verdicts) -> Coverage:
    """THE partition. `routed` comes from the enumeration, never from the verdict list — a verdict
    list cannot report the files that produced no verdict, which is precisely what used to go wrong."""
    routed = len(enum.routed)
    if len(verdicts) != routed:
        raise AssertionError(f"{routed - len(verdicts)} routed file(s) produced no verdict — they are "
                             f"invisible to every count this gate prints")
    unparsed = sum(1 for v in verdicts if v.parse_error)
    unchecked = sum(1 for v in verdicts if v.skipped)
    val = [v for v in verdicts if not v.parse_error and not v.skipped]
    errored = sum(1 for v in val if v.errors or v.stamp_error)
    # `checked` used to conflate version-GATED with version-EXEMPT. Every addition to UNVERSIONED_DEFS
    # lifts numerator and denominator together, pinning the fraction at 1.0 while version coverage
    # falls — a bundle whose only routed file is mac.project.yaml printed "1/1 checked file(s) clean".
    exempt = sum(1 for v in val if v.definition in UNVERSIONED_DEFS)
    cov = Coverage(routed=routed, validated=len(val), gated=len(val) - exempt, exempt=exempt,
                   clean=len(val) - errored, errored=errored, unchecked=unchecked, unparsed=unparsed)
    if cov.unaccounted:
        raise AssertionError(f"{cov.unaccounted} routed file(s) fell through every category")
    return cov


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
    try:
        verdicts = validate_files(enum, schema, all_versions=args.all)
    except VersionLineError as e:
        print(f"[setup] {e}", file=sys.stderr)      # exit 2, the documented "could not run"
        sys.exit(2)                                 # — never a content red, and never an empty range

    lines, code = report(enum, verdicts, strict=args.strict)
    for line in lines:
        print(line)
    sys.exit(code)


def report(enum, verdicts, strict=False):
    """Render the run. Returns (lines, exit_code) and prints nothing, so a test can assert on the
    numbers this gate publishes without scraping a terminal.

    FINDINGS ARE COUNTED SEPARATELY FROM PRINTED LINES. The old headline counted lines: a bundle with
    exactly ONE undefined file printed "3 error(s)", because that one file was reported as a root, a
    per-directory witness and an advice line. A new class appended to the same list would have
    inflated the same way, so the UNCHECKED block below adds ONE finding however many witnesses it has.
    """
    unknown, waived = list(enum.unknown), len(enum.waived)
    cov = coverage(enum, verdicts)

    findings, lines, warnings = 0, [], []
    unchecked_by = collections.defaultdict(list)
    for v in verdicts:
        rel = enum.rel(v.path)
        if v.parse_error:
            findings += 1
            lines.append(f"ERROR  {rel}: YAML parse failed: {v.parse_error}")
            continue
        if v.skipped:
            unchecked_by[v.unchecked_reason].append((rel, v.schema_version))
            continue
        warnings += list(v.warnings)
        if v.stamp_error:
            findings += 1
            lines.append(f"ERROR  {rel} [{v.definition}]: {v.stamp_error}")
        for loc, msg, _kw, _sp in v.errors:
            findings += 1
            lines.append(f"ERROR  {rel} [{v.definition}] @{loc}: {msg}")

    # Deny-unknown reports as a ROOT plus witnesses, never one line per file: a gate that emits 157
    # identical lines is muted within a week and its root cause dies with it. ONE finding, N lines.
    if unknown:
        findings += 1
        by_dir = collections.Counter(os.path.dirname(u) or '.' for u in unknown)
        lines.append(f"ERROR  {len(unknown)} file(s) carry no MAC definition and are not declared "
                     f"out of scope — MAC cannot validate, track or enforce them")
        for d, n in sorted(by_dir.items(), key=lambda kv: -kv[1]):
            ex = next(u for u in unknown if (os.path.dirname(u) or '.') == d)
            lines.append(f"         {n:>4}  {d}/    e.g. {os.path.basename(ex)}")
        lines.append("         declare them in mac.project.yaml#conformance.out_of_scope with a "
                     "reason, or bring them under a schema definition")

    # ── THE UNCHECKED BLOCK ───────────────────────────────────────────────────────────────────────
    # Its own block, above the summary, with its own denominator — never a clause mid-sentence. An
    # unrecognized stamp used to degrade to a silent skip mentioned in passing; it is a FINDING, and
    # a finding whose whole point is that it is impossible to read as success.
    if cov.unchecked:
        findings += 1
        lines.append('')
        lines.append(f"UNCHECKED  {cov.unchecked} of {cov.routed} routed file(s) were NOT validated "
                     f"— they claim a definition that nothing checked")
        for reason, items in sorted(unchecked_by.items()):
            lines.append(f"    {len(items):>4}  {reason}: {UNCHECKED_REASONS[reason]}")
            by_stamp = collections.defaultdict(list)
            for rel, sv in items:
                by_stamp[sv].append(rel)
            for sv, rels in sorted(by_stamp.items()):
                # A no-stamp / not-a-mapping file has no stamp to report, so naming one would be
                # noise. Witnesses, grouped, never one line per file.
                what = f"stamped {sv!r:18}" if sv else ' ' * 26
                lines.append(f"          {len(rels):>4}  {what} e.g. {sorted(rels)[0]}")
        lines.append(f"       recognized: {RECOGNIZED.describe()}, current {CURRENT}")
        lines.append("       an unrecognized stamp is a FINDING, not a skip: either the file is a "
                     "generation behind and must be")
        lines.append("       reconformed, or the recognized range is missing a version that exists. "
                     "Use --all to validate them anyway.")

    for w in warnings:
        lines.insert(0, w)

    # ── THE SUMMARY ───────────────────────────────────────────────────────────────────────────────
    # THE DENOMINATOR IS `routed`. The old `{clean}/{checked}` where `checked = routed - skipped` was
    # self-normalising: it re-normalised to N/N at the moment coverage collapsed. `routed` is fixed by
    # the enumeration and cannot be moved by the recognized range, so "4 of 32" stays 4 of 32.
    fail = bool(findings) or (strict and bool(warnings))
    if cov.routed == 0:
        # "N of N" stops self-normalising only when N cannot be zero. mac-integration-kit printed
        # "0/0 checked file(s) clean" and exited 0 over a repo that HAS a yaml file in it — the
        # estate's own PASS-on-zero-files failure mode, printed by this very gate.
        verdict, fail = 'EMPTY', True
        head = (f"EMPTY: validate_schema — 0 routed file(s); nothing was checked, so this run proves "
                f"nothing about the {len(enum.all_yaml)} yaml file(s) present")
    else:
        verdict = 'FAIL' if fail else 'PASS'
        head = (f"{verdict}: validate_schema — {cov.clean} of {cov.routed} routed file(s) clean, "
                f"{cov.errored} with finding(s), {cov.unchecked} UNCHECKED, {cov.unparsed} unparsed")
    lines.append('')
    lines.append(head + f"; {findings} finding(s), {len(warnings)} warning(s); "
                        f"{cov.validated} validated ({cov.gated} version-gated, {cov.exempt} exempt); "
                        f"{len(enum.all_yaml)} yaml in bundle, {len(unknown)} undefined, "
                        f"{waived} declared out of scope.  (L1 — not correctness; see CONFORMANCE.md.)")
    return lines, (1 if fail else 0)


if __name__ == '__main__':
    main()
