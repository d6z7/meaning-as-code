#!/usr/bin/env python3
"""mac_checks_structure — the STRUCTURE phase of the MAC compiler: what IS and IS NOT defined.

WHAT THIS ANSWERS
-----------------
Five of the eleven codes in the frozen taxonomy (`mac_diag.py`) are structural — they are answerable
from the bundle's files and the framework's schema alone, with no semantics involved:

    MAC001  undefined-artifact     present, no MAC definition, not declared out of scope
    MAC002  invalid-artifact       has a definition and does not satisfy it
    MAC009  undeclared-extension   an x- key with no profile entry (CONFORMANCE.md §2)
    MAC008  reference-unresolved   a reference resolving to nothing
    MAC011  coverage-missing       a required completeness not reached

Each check is a plain function of (bundle, root) returning `list[Diagnostic]`. Nothing here prints,
exits, or decides policy: `run()` concatenates, and the caller renders. That is what lets the same
finding set reach a terminal and a persisted dashboard without being computed twice.

NOTHING HERE RE-DERIVES A FACT THAT HAS A HOME
----------------------------------------------
This module is the compiler's front end, and a front end that re-implements its own file selection,
its own JSON Schema validation or its own reference resolution would be the exact defect the taxonomy
exists to name — one fact in more than one home (MAC003). So:

  * the ENUMERATION and the per-file VALIDATION come from `validate_schema.enumerate_bundle()` /
    `validate_files()` — lifted out of that gate's `main()` on 2026-08-18 for this purpose, and proven
    output-identical on five bundles x three flag sets.
  * REFERENCE RESOLUTION comes from `mac_model`: a dangling reference is already an `Unresolved` value
    parked at the referring field, so this module HARVESTS them and never resolves anything itself.
  * the LINEAGE COMPLETENESS thresholds and coverage model come from `check_lineage_coverage` +
    `lineage_project`, imported — including the two threshold constants.

FANOUT IS COLLAPSED, ALWAYS
---------------------------
156 undefined files are ONE diagnostic with 156 witnesses, not 156 diagnostics. Witnesses are ordered
by directory (largest first) so a renderer that truncates still shows coherent groups, and the
per-directory tally is repeated in `note`, which renderers print after the truncation. A gate that
emits one line per file is muted within a week and its root cause dies with it — observed on this
toolchain, and the reason `Witness` exists.

WHAT EACH CHECK WOULD FALSELY FIRE ON — stated up front, because five plausible checks died on this
toolchain by being measured after they were written:

  MAC001  a bundle that legitimately owns yaml MAC has no business defining (CI config, editor state).
          The check CANNOT make that judgement and does not try: the bundle makes it, by declaring
          `conformance.out_of_scope`. Undeclared, every such file fires. That is the design — silence
          is what made 156 files invisible.
  MAC002  only where mac.schema.json is itself wrong (over-strict). Grouping merges two unrelated
          defects that happen to trip the same constraint at the same schema path; the witnesses keep
          each one individually addressable, which is why the merge is safe.
  MAC009  a bundle that declares its profile somewhere other than mac.project.yaml. Measured: the
          schema defines NO profile slot at all (grep of mac.schema.json: zero hits), so there is no
          rival home to miss; three spellings are accepted. Deliberately scoped to SCHEMA-ROUTED files
          — an `x-` key inside a file that has no definition is already MAC001, and reporting it again
          here would restate one fact in two homes.
  MAC008  cannot false-fire (it reports what the model already failed to resolve) but it CAN false-
          PASS: the model eagerly links three reference classes — grounding.relation, values.register,
          edge endpoints. A rule's `derived_by_rule` or a `mac.*` vocabulary term is check_references'
          territory. Zero here means "no dangling binding", never "no dangling reference".
  MAC011  a genuinely pivot-heavy or aggregate-heavy served view: below-100% column coverage is normal
          and is never an error. Only the degenerate cases are (a view that explains NOTHING while
          declaring lineage parents; an output column accounted for by neither an edge nor `derived[]`).
          A seed-only view is exempt by construction and the imported gate already rules it so.

Usage:  python3 tools/mac_checks_structure.py <bundle-root> [--show error|warning|info] [--json]
Exit:   0 = no error-severity diagnostic · 1 = the bundle does not conform · 2 = setup error
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mac_model as M  # noqa: E402
import validate_schema as VS  # noqa: E402
from mac_diag import ERROR, INFO, WARNING, Diagnostic, Witness  # noqa: E402
from mac_model import Unresolved, de  # noqa: E402

SOURCE = "mac_checks_structure"

# The enumeration is globbed once per root per process: five checks ask for it and the bundle does not
# change underneath them. Same contract as mac_model.load's memo, same reason.
_ENUM_CACHE: dict = {}


def enumeration(root):
    key = os.path.abspath(str(root))
    if key not in _ENUM_CACHE:
        _ENUM_CACHE[key] = VS.enumerate_bundle(key)
    return _ENUM_CACHE[key]


def clear_cache() -> None:
    _ENUM_CACHE.clear()


def _rel(path, root) -> str:
    try:
        return os.path.relpath(str(path), str(root)).replace(os.sep, "/")
    except ValueError:
        return str(path)


def _pct(fraction) -> str:
    """A percentage the way this estate shows numbers to humans — de-DE, via mac_model's one home."""
    return f"{de(float(fraction) * 100, 0)} %"


def _oneline(text) -> str:
    """A witness detail is a LINE. A PyYAML parse error is four lines with absolute paths in it, and
    pasted verbatim it breaks every renderer that assumes one finding is one line."""
    return " ".join(str(text).split())


def _by_directory(relpaths):
    """Witness order + the tally line. Largest directory first, then alphabetical inside it — so a
    renderer that shows the first twelve shows one coherent group rather than twelve unrelated files."""
    groups = defaultdict(list)
    for r in relpaths:
        groups[os.path.dirname(r) or "."].append(r)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [(d, sorted(files)) for d, files in ordered]


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# MAC001 — undefined-artifact
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def check_undefined_artifacts(bundle, root) -> list:
    """Every yaml in the bundle that carries no MAC definition and no out-of-scope declaration.

    The enumeration is validate_schema's, verbatim. An allowlist validator cannot detect invention:
    you cannot violate a pattern you do not match, so before that enumeration existed these files were
    not rejected and not skipped — they were never looked at, while the summary line read as complete
    coverage."""
    enum = enumeration(root)
    out = []

    if enum.unknown:
        groups = _by_directory(enum.unknown)
        witnesses = [Witness(file=r, detail="") for _d, files in groups for r in files]
        tally = "; ".join(f"{de(len(files))} in {d}/" for d, files in groups)
        out.append(Diagnostic(
            code="MAC001", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(enum.unknown))} of {de(len(enum.all_yaml))} yaml file(s) in the bundle "
                     f"carry no MAC definition and are not declared out of scope — MAC cannot validate, "
                     f"track, project or enforce them"),
            witnesses=witnesses,
            note=(f"by directory: {tally}. Either bring each under a schema definition, or declare it "
                  f"in mac.project.yaml#conformance.out_of_scope with a reason — declared debt is "
                  f"visible and arguable, silent debt is how a standard stops being one")))

    # Declared debt is conformant, and it is still debt: a reader of the dashboard must be able to see
    # how much of the bundle the standard has been excused from, without re-running anything.
    if enum.waived:
        groups = _by_directory(enum.waived)
        out.append(Diagnostic(
            code="MAC001", severity=INFO, source=SOURCE,
            summary=(f"{de(len(enum.waived))} file(s) carry no MAC definition and are DECLARED out of "
                     f"scope — conformant, and outside every gate"),
            witnesses=[Witness(file=r) for _d, files in groups for r in files],
            note=("declared via mac.project.yaml#conformance.out_of_scope: "
                  + ", ".join(enum.declared))))
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# MAC002 — invalid-artifact
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _yaml_path(loc: str) -> str:
    """jsonschema's 'a/b/0/c' -> mac_model's 'a.b[0].c', so Doc.line_of can find the line."""
    out = ""
    for part in str(loc).split("/"):
        if part in ("", "(root)"):
            continue
        out += f"[{part}]" if part.isdigit() else (f".{part}" if out else part)
    return out


def check_invalid_artifacts(bundle, root) -> list:
    """A file that HAS a MAC definition and does not satisfy it — L1, straight from mac.schema.json.

    Validation is validate_schema's `validate_files`; this function only groups. The grouping key is
    (definition, failing keyword, schema path): one constraint broken in N files is ONE diagnostic
    with N witnesses. Grouping on the MESSAGE instead was tried first and split a single
    additionalProperties violation into one group per offending key name."""
    enum = enumeration(root)
    try:
        verdicts = VS.validate_files(enum)
    except Exception as exc:  # a broken schema/env is setup error, not a bundle finding
        return [Diagnostic(code="MAC002", severity=ERROR, source=SOURCE,
                           summary=f"the schema could not be loaded, so no file could be validated: {exc}",
                           witnesses=[Witness(file="mac.schema.json")])]

    out, groups = [], defaultdict(list)
    unparsed, skipped = [], []
    for v in verdicts:
        rel = _rel(v.path, root)
        if v.parse_error:
            unparsed.append((rel, _oneline(v.parse_error).replace(str(root) + os.sep, "")))
            continue
        if v.skipped:
            skipped.append((rel, v.schema_version))
            continue
        doc = bundle.doc(rel)
        for loc, msg, keyword, schema_path in v.errors:
            line = doc.line_of(_yaml_path(loc)) if doc else None
            groups[(v.definition, keyword, schema_path)].append(
                Witness(file=rel, path=loc, line=line, detail=_oneline(msg)))

    if unparsed:
        out.append(Diagnostic(
            code="MAC002", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(unparsed))} routed file(s) do not parse as YAML, so the definition they "
                     f"carry cannot be checked at all"),
            witnesses=[Witness(file=r, detail=e) for r, e in sorted(unparsed)]))

    for (definition, keyword, schema_path), ws in sorted(groups.items()):
        ws.sort(key=lambda w: (w.file, w.path))
        first = ws[0]
        # the schema path is only worth printing when it says more than the keyword already does
        where = f"`{keyword}` at {schema_path}" if schema_path != keyword else f"`{keyword}`"
        out.append(Diagnostic(
            code="MAC002", severity=ERROR, source=SOURCE,
            summary=(f"{first.file}#{first.path} [{definition}] does not satisfy the schema: {first.detail}"
                     if len(ws) == 1 else
                     f"{de(len(ws))} {definition} site(s) break the same constraint ({where}) "
                     f"— e.g. {first.detail}"),
            witnesses=ws,
            note=f"mac.schema.json#/$defs/{definition} · failing keyword `{keyword}`"))

    # A file whose schema_version the framework does not recognize is NOT validated. That is a hole in
    # coverage wearing a green tick, so it is reported — as a warning, because incremental migration is
    # the documented intent of the RECOGNIZED set.
    if skipped:
        out.append(Diagnostic(
            code="MAC002", severity=WARNING, source=SOURCE,
            summary=(f"{de(len(skipped))} routed file(s) were NOT validated — their "
                     f"metadata.schema_version is outside the recognized set, so they claim a definition "
                     f"nothing checked"),
            witnesses=[Witness(file=r, path="metadata.schema_version",
                               detail=f"declares {sv!r}") for r, sv in sorted(skipped)],
            note=(f"recognized: {', '.join(sorted(VS.RECOGNIZED))} (current {VS.CURRENT}); "
                  f"becomes an error when the migration these versions are transitional for is done")))
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# MAC009 — undeclared-extension  (CONFORMANCE.md §2)
# ══════════════════════════════════════════════════════════════════════════════════════════════════

_PROFILE_KEYS = ("profile", "x_profile", "extensions")


def _profile(root) -> dict:
    """CONFORMANCE §2: 'a project declares a PROFILE: the list of x- keys it uses and what each means.'
    The standard names the construct and gives it no schema home, so the only project-level document
    there is gets searched, under every spelling in use."""
    proj = os.path.join(str(root), "mac.project.yaml")
    if not os.path.exists(proj):
        return {}
    try:
        doc = VS._load_yaml_str_dates(proj) or {}
    except Exception:
        return {}
    for key in _PROFILE_KEYS:
        block = doc.get(key)
        if isinstance(block, dict):
            return block
    return {}


def _walk_keys(node, path=""):
    """Every (yaml path, key) in a document, ROOT LEVEL INCLUDED. The root level is the whole point:
    measured on fpl2, three of the four `x-` sites are top-level keys on dataset descriptors
    (`x-grain`), which a walker that descends before it yields never sees."""
    if isinstance(node, dict):
        for k, v in node.items():
            child = f"{path}.{k}" if path else str(k)
            yield child, k
            yield from _walk_keys(v, child)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_keys(v, f"{path}[{i}]")


def check_undeclared_extensions(bundle, root) -> list:
    """`x-` keys in use against the profile that is supposed to declare them.

    Scoped to SCHEMA-ROUTED files: `^x-` is a mac.schema.json patternProperty, so the namespace only
    means anything where the schema applies. An `x-` key in a file with no definition is MAC001.

    The profile's ABSENCE is reported separately from the individual keys, because they are different
    facts with different fixes: one is 'the bundle never said which extensions it owns', the other is
    'these specific keys are not in the list'."""
    enum = enumeration(root)
    profile = _profile(root)
    declared = set(profile.get("x_keys") or profile.get("keys") or profile) if profile else set()

    used: dict[str, list] = defaultdict(list)
    for abspath in enum.routed:
        rel = _rel(abspath, root)
        doc = bundle.doc(rel)
        data = doc.data if doc else None
        if not isinstance(data, dict):
            continue
        for ypath, key in _walk_keys(data):
            if isinstance(key, str) and key.startswith("x-"):
                used[key].append(Witness(file=rel, path=ypath, line=doc.line_of(ypath)))

    out = []
    if not profile and used:
        out.append(Diagnostic(
            code="MAC009", severity=ERROR, source=SOURCE,
            summary=(f"the bundle declares no profile, so all {de(len(used))} `x-` key(s) it uses "
                     f"({de(sum(len(v) for v in used.values()))} site(s)) are undeclared by construction"),
            witnesses=[Witness(file="mac.project.yaml", path=" | ".join(_PROFILE_KEYS),
                               detail="no profile block under any accepted spelling")],
            note=("CONFORMANCE.md §2 — an x- key with no profile entry is undeclared debt, not license. "
                  "Undeclared, nobody can tell an experiment from a promotion candidate and §2's "
                  "promotion path ('invent under x-, prove it, promote it') has no input. FRAMEWORK "
                  "SIDE: mac.schema.json defines no profile slot, so the construct §2 requires has no "
                  "schema home — the bundle can only declare it in the ungoverned manifest")))

    undeclared = {k: v for k, v in sorted(used.items()) if k not in declared}
    if undeclared:
        witnesses = [w for k in sorted(undeclared) for w in undeclared[k]]
        out.append(Diagnostic(
            code="MAC009", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(undeclared))} `x-` key(s) are in use at {de(len(witnesses))} site(s) "
                     f"with no profile entry: " + ", ".join(sorted(undeclared))),
            witnesses=witnesses,
            note=("declare each in mac.project.yaml#profile.x_keys with what it means; a key that "
                  "recurs, an agent reads, and projects onto all three target families is a promotion "
                  "candidate (CONFORMANCE §2)")))
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# MAC008 — reference-unresolved
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def check_unresolved_references(bundle, root) -> list:
    """Harvest the `Unresolved` values mac_model already parked at their referring fields.

    Nothing is re-resolved here. mac_model's contract is that a dangling reference is a VALUE and
    never an exception, stored AT the field that referred — which makes this a walk of the linked
    graph, and makes the finding addressable to the referring site rather than to the missing target.

    The linked classes are grounding.relation, values.register and edge endpoints. Collapsed BY CLASS,
    not by file: 'nine concepts ground on a relation that does not exist' is one defect."""
    found: dict[str, list] = defaultdict(list)

    for c in bundle.concepts():
        name = c.name or c.stem
        for g in c.groundings:
            if isinstance(g.relation, Unresolved):
                found["grounding.relation"].append((
                    Witness(file=g.site.file, path=g.site.path, line=g.site.line,
                            detail=f"{name} grounds on {g.relation_ref!r}"), g.relation))
        vs = c.values
        if vs is not None and vs.register_ref is not None and isinstance(vs.register, Unresolved):
            site = vs.register_ref.site
            found["values.register"].append((
                Witness(file=site.file, path=site.path, line=site.line,
                        detail=f"{name} draws its members from {vs.register_ref.value!r}"), vs.register))

    for e in bundle.edges():
        for endpoint, resolved in zip(e.endpoints, e.concepts):
            if isinstance(resolved, Unresolved):
                found["edge.endpoint"].append((
                    Witness(file=e.site.file, path=e.site.path, line=e.site.line,
                            detail=f"edge {e.edge_id} names concept {endpoint!r}"), resolved))

    out = []
    for kind, pairs in sorted(found.items()):
        witnesses = [w for w, _u in pairs]
        searched = next((u.searched for _w, u in pairs if u.searched), ())
        out.append(Diagnostic(
            code="MAC008", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(witnesses))} `{kind}` reference(s) resolve to nothing — the model links "
                     f"the field to a target that is not in the bundle"),
            witnesses=witnesses,
            note=(f"searched: {', '.join(searched)}" if searched else "")))
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# MAC011 — coverage-missing
# ══════════════════════════════════════════════════════════════════════════════════════════════════
#
# WHAT BELONGS HERE, and what deliberately does not.
#
# "Required completeness" is not a thing this module gets to invent. CONFORMANCE.md names exactly one
# structural completeness — the LINEAGE-COMPLETE profile, gated on a declared data plane: the
# data-plane graph must be total and connected, and under it the lineage projection is a guaranteed
# derivation rather than a best effort. `check_lineage_coverage.py` is the gate that measures it, and
# its model, its two thresholds and its severity rulings are IMPORTED here, not restated.
#
# Deliberately NOT here:
#   * L1 reach (61 of 218 files) — that is MAC001's fact. Counting it again under another code is one
#     fact in two homes, in the tool whose job is to find exactly that.
#   * the chain gate (check_ontology_grounds_on_datasets) and the DQ-sync gate — both own real
#     completeness rules, and both express them only as prints inside `main()`. Reimplementing their
#     rules to reach them would duplicate the rule; the honest fix is to give those gates a findings()
#     surface, and that is the recorded follow-on, not a thing to fake here.
#
# ONE BRANCH BELOW IS MEASURED UNREACHABLE, and is kept deliberately. `unaccounted` — an output column
# explained by neither an incoming edge nor `derived[]` — cannot fire against lineage_project as it
# stands, because `derived[]` is that projector's TOTAL fallback: measured 2026-08-18 by inserting a
# column named by no rule and no upstream into a dataset descriptor, the projector filed it under
# derived and `unaccounted` came back empty. So this branch is a tripwire on the PROJECTOR (it fires
# the day the fallback stops being total), not a check on bundles. It is left in rather than deleted
# because deleting it would silently drop the only guard on that regression — but nobody should read a
# green `unaccounted` as evidence that every column is explained.

def check_coverage(bundle, root) -> list:
    """The lineage completeness CONFORMANCE.md requires of a bundle with a data plane."""
    try:
        from check_lineage_coverage import MAX_COVERAGE_ERROR, MIN_COVERAGE_WARN, coverage_rows
        from lineage_project import project
    except ImportError as exc:  # pragma: no cover - environment, not content
        return [Diagnostic(code="MAC011", severity=WARNING, source=SOURCE,
                           summary=f"lineage completeness could not be measured: {exc}")]

    model, unclassifiable = project([str(root)])   # raises on a malformed descriptor — run() reports it
    rows = coverage_rows(model)
    if not rows:
        return []                        # no data plane: nothing to be complete about

    # the transform descriptor a flow came from, so a witness addresses a FILE and not a bare name
    file_of = {}
    for doc in bundle.docs("transform"):
        file_of[Path(doc.relpath).stem] = doc.relpath

    def witness(row, detail):
        name = str(row["dataset"])
        return Witness(file=file_of.get(name.split(".")[-1], name), detail=detail)

    no_columns, explains_nothing, unaccounted, thin, seed_only = [], [], [], [], []
    for r in rows:
        if r["total"] == 0:
            no_columns.append(witness(r, "the produced dataset declares no columns at all"))
            continue
        if r["coverage"] <= MAX_COVERAGE_ERROR and r["parents"] == 0:
            seed_only.append(witness(r, f"seed-only view — all {de(r['total'])} column(s) are declared "
                                        f"seeds/consts, none descends from an upstream column"))
        elif r["coverage"] <= MAX_COVERAGE_ERROR:
            explains_nothing.append(witness(r, f"0 of {de(r['total'])} column(s) descend from an "
                                               f"upstream column, though {de(r['parents'])} lineage "
                                               f"parent(s) are declared"))
        elif r["coverage"] < MIN_COVERAGE_WARN:
            thin.append(witness(r, f"only {de(r['covered'])}/{de(r['total'])} column(s) "
                                   f"({_pct(r['coverage'])}) descend from an upstream column"))
        if r["unaccounted"]:
            unaccounted.append(witness(r, "neither edge-covered nor declared in derived[]: "
                                          + ", ".join(r["unaccounted"])))

    covered_total = sum(r["covered"] for r in rows)
    col_total = sum(r["total"] for r in rows)
    overall = (covered_total / col_total) if col_total else 0.0
    scale = (f"measured over {de(len(rows))} flow(s); overall column coverage "
             f"{de(covered_total)}/{de(col_total)} ({_pct(overall)})")

    out = []
    if no_columns:
        out.append(Diagnostic(
            code="MAC011", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(no_columns))} served dataset(s) declare no columns, so nothing about "
                     f"them can be explained or covered"),
            witnesses=no_columns, note=f"check produces.relation. {scale}"))
    if explains_nothing:
        out.append(Diagnostic(
            code="MAC011", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(explains_nothing))} served dataset(s) explain none of their columns "
                     f"while declaring lineage parents — the lineage renders and says nothing"),
            witnesses=explains_nothing,
            note=(f"a raw_source|dataset input needs a `consumes` map naming columns its descriptor "
                  f"actually declares, and the rules' `sql` must resolve them onto the served column "
                  f"names. {scale}")))
    if unaccounted:
        out.append(Diagnostic(
            code="MAC011", severity=ERROR, source=SOURCE,
            summary=(f"{de(len(unaccounted))} served dataset(s) carry output column(s) accounted for by "
                     f"neither an incoming edge nor `derived[]`"),
            witnesses=unaccounted, note=scale))
    if thin:
        out.append(Diagnostic(
            code="MAC011", severity=WARNING, source=SOURCE,
            summary=(f"{de(len(thin))} served dataset(s) have thin lineage — under "
                     f"{_pct(MIN_COVERAGE_WARN)} of their columns descend from an upstream column"),
            witnesses=thin,
            note=(f"below 100% is legitimate (pivots, aggregates, literal constants); this band is "
                  f"where an under-declared `consumes` map hides. {scale}")))
    if seed_only:
        out.append(Diagnostic(
            code="MAC011", severity=WARNING, source=SOURCE,
            summary=(f"{de(len(seed_only))} served dataset(s) are assembled purely from authored seeds "
                     f"— legitimate by construction, and outside lineage"),
            witnesses=seed_only,
            note=f"becomes an error the moment such a view declares a raw_source|dataset parent. {scale}"))
    if unclassifiable:
        out.append(Diagnostic(
            code="MAC011", severity=WARNING, source=SOURCE,
            summary=(f"{de(len(unclassifiable))} `consumes` entr(y/ies) name a rule instead of a column, "
                     f"so they produce no lineage edge"),
            witnesses=[Witness(file=file_of.get(str(u[0]).split(".")[-1], str(u[0])),
                               detail=f"consumes column {u[1]!r} names rule {u[2]!r} — {u[3]}")
                       for u in unclassifiable],
            note=scale))
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# the phase
# ══════════════════════════════════════════════════════════════════════════════════════════════════

# (check, the taxonomy code it owns). The pairing is explicit because `run` needs it: when a check
# CRASHES, the compiler must say which class of finding is now unknown — reporting the outage under an
# arbitrary code would be a lie about what was and was not checked. Measured on a mutated bundle: a
# single unparseable descriptor takes lineage_project down, and without this the outage surfaced as an
# MAC002.
CHECKS = (
    (check_undefined_artifacts, "MAC001"),
    (check_invalid_artifacts, "MAC002"),
    (check_undeclared_extensions, "MAC009"),
    (check_unresolved_references, "MAC008"),
    (check_coverage, "MAC011"),
)


def run(bundle, root) -> list:
    """Every structural diagnostic, in taxonomy order.

    A check that raises is itself a finding. A compiler phase that dies quietly reports a CLEAN bundle,
    which is worse than reporting nothing — so the outage is emitted as a warning under the code whose
    findings are now unknown, and the other four checks still run."""
    out = []
    for check, code in CHECKS:
        try:
            out += check(bundle, root)
        except Exception as exc:  # noqa: BLE001
            out.append(Diagnostic(
                code=code, severity=WARNING, source=f"{SOURCE}.{check.__name__}",
                summary=(f"{check.__name__} could not run, so every {code} finding in this bundle is "
                         f"UNKNOWN — not absent: {exc!r}"),
                note=("usually an upstream parse failure: fix the MAC002 parse error first, then re-run. "
                      "A phase that crashes silently reports a clean bundle; this makes the hole visible")))
    return out


def _as_dict(d: Diagnostic) -> dict:
    return {"code": d.code, "kind": d.kind, "severity": d.severity, "summary": d.summary,
            "note": d.note, "source": d.source,
            "witnesses": [{"file": w.file, "path": w.path, "line": w.line, "detail": w.detail}
                          for w in d.witnesses]}


def main(argv=None) -> int:
    import argparse
    import json

    from mac_diag import ORDER, render, summarise

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", help="bundle root (a MAC source container)")
    ap.add_argument("--show", default=WARNING, choices=[ERROR, WARNING, INFO],
                    help="least severity printed (default: warning)")
    ap.add_argument("--json", action="store_true", help="emit the finding set as JSON")
    args = ap.parse_args(argv)

    root = str(Path(args.root).resolve())
    if not os.path.isdir(root):
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    bundle = M.load(root)
    diags = run(bundle, root)
    stats = summarise(diags)

    if args.json:
        print(json.dumps({"schema": "mac.diagnostics/structure/1", "bundle": root,
                          "phase": "structure", "stats": stats,
                          "diagnostics": [_as_dict(d) for d in diags]}, indent=2))
        return 1 if stats["errors"] else 0

    codes = ", ".join(c for _f, c in CHECKS)
    print(f"── structure phase ── {de(len(CHECKS))} checks ({codes}) over {root} ──\n")
    body = render(diags, root, show=args.show)
    if body:
        print(body + "\n")
    by_code = ", ".join(f"{c} x{de(n)}" for c, n in sorted(stats["by_code"].items()))
    print(f"{de(stats['errors'])} error(s), {de(stats['warnings'])} warning(s) over "
          f"{de(stats['total'])} diagnostic(s) carrying {de(stats['witnesses'])} witness(es)"
          + (f"  [{by_code}]" if by_code else ""))
    hidden = [d for d in diags if ORDER.get(d.severity, 2) > ORDER.get(args.show, 1)]
    if hidden:
        print(f"({de(len(hidden))} diagnostic(s) below --show {args.show} not printed)")
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
