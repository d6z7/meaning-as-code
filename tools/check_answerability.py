#!/usr/bin/env python3
"""check_answerability — can a concept be USED without probing, and is that DERIVED rather than sworn?

WHY THIS EXISTS
---------------
mac.schema.json describes `contract.no_probe_guarantee` as "what an agent needs ONLY, to use this
concept without probing the data; if more is needed, the concept is incomplete (fix it, don't probe)."

That is a COMPLETENESS TEST. <domain>/<dataset> answered it the way every bundle does: by hand, in prose, once
per concept — twenty-two blocks reciting the steps an agent should take. Every step of every one of
them restates a declaration that already exists.

MEASURED on that bundle, 2026-08-19, walking one delivery measure clause by clause: the kpi codes
and the default are `values.aliases.map` + `contract.default_reading`; the role pin and the vintage
collapse are the Perspective concept + `grounding.snapshot_rule`; the name resolutions are the
referenced concepts' own lookup registers; the period reading is `semantics.measure_type` x
`axis_kinds` through mac.resolve.period_reading; the read is `grounding.sources[]`; and the closing
"no probing, no name literal" is mac.resolve.join_on_declared_key + mac.guarantee.never_guess.
Residue: NONE.

AND IT DRIFTS, which is the argument. In one working session, three separate sweeps were needed
inside those blocks alone: eight step-2 clauses repointed after a rule family was deleted, a model
resolution path that had gone missing entirely, then twelve dead rule citations and seventeen
resolution paths still naming a view the ontology had stopped using. Each time a declaration moved,
the prose swore to the old world — and nothing noticed, because a guarantee is prose and prose is not
checked.

WHAT THIS MODULE DOES
---------------------
`answer_path()` DERIVES the steps from the declarations. `check_answerability()` reports the steps it
cannot derive. The two are the same computation: a concept whose path cannot be derived is exactly the
concept mac.schema.json calls incomplete, and it is reported as MAC011 (a required completeness the
bundle does not reach) rather than asserted as satisfied by a sentence.

TWO EXEMPTIONS, both measured before they were trusted, both mirroring a distinction the ontology
already draws elsewhere:

  A DEDICATED RELATION NEEDS NO DISCRIMINATOR. A concept that is the sole user of its relation is
  selected BY that relation; demanding a discriminator would report a gap that cannot exist. Without
  this, <dataset>'s reach measure is reported incomplete — it is served from its own relation and
  its own file says so ("there is no `kpi` code here"). Measured: 1 false finding.

  A REFUSE-STUB IS AUTHORED TO BE UNANSWERABLE. `identity.kind = sme_pending` declares a concept that
  exists so a question about it gets a grounded refusal instead of a hallucination. Reporting it as
  incomplete argues for inventing the grounding it deliberately lacks. The ontology-quality projection
  already excludes these from connectivity for the same reason. Measured: 1 false finding.

  With both: 22 concepts, 0 underivable, 1 exempt.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import mac_diag as D
import mac_project as P

# The steps an agent needs to use ANY concept, and the declaration each is derived from. Ordered as an
# agent meets them. Kept here, once — the projection renders these, the check reports the unfillable.
STEPS = ("read", "select", "resolve", "grain", "period")


def _load(root):
    import yaml
    out = {}
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane
    # the project declares. This line used to glob `<root>/ontology/concepts/*.yaml` by hand and
    # found nothing on any foldered bundle, including the framework's own worked examples.
    for f in P.concept_files(root):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        if (d.get("concept") or {}).get("name"):
            out[d["concept"]["name"]] = (P.rel(root, f), d, f.read_text(encoding="utf-8"))
    return out


def answer_path(doc: dict, raw: str, shared: bool, registers: dict | None = None,
                registry: dict | None = None) -> dict:
    """The steps an agent needs, DERIVED. Each value is the declaration that supplies it, or None.

    `shared` says whether another concept grounds the same relation — the only fact that cannot be
    read off this document alone, because it is a property of the bundle."""
    c = doc.get("concept") or {}
    g = doc.get("grounding") or {}
    v = doc.get("values") or {}
    ct = doc.get("contract") or {}
    s = c.get("semantics") or {}
    ident = c.get("identity") or {}
    # `grounding.source` IS SINGULAR since 2026-10-07 — one concept, one relation.
    src = g.get("source") or {}
    cls = c.get("class")

    path: dict = {}
    path["read"] = (f"grounding.source: {src['relation']}"
                    if src.get("relation") and (src.get("columns") or src.get("key")) else None)

    if not shared:
        path["select"] = f"a dedicated relation — {src.get('relation')} is grounded by this concept alone"
    else:
        for slot, label in (("discriminator", "grounding.discriminator"),
                            ("value_filter", "grounding.value_filter")):
            if g.get(slot):
                path["select"] = f"{label}: {g[slot]}"
                break
        else:
            amap = (v.get("aliases") or {}).get("map") or {}
            if amap:
                path["select"] = f"values.aliases.map -> {', '.join(sorted(amap))}"
            elif P.canonical_key(doc):
                path["select"] = f"grounding.source.key: {P.canonical_key(doc)}"
            elif P.key_parts(doc):
                path["select"] = ("grounding.source.key (composite): "
                                  + ", ".join(P.key_parts(doc)))
            elif v.get("items"):
                path["select"] = f"values.items ({len(v['items'])} members)"
            else:
                path["select"] = None

    if cls in ("reference", "enumeration"):
        # `reference` RENAMED `entity` 2026-10-05 — a SEPARATE, earlier retirement than today's
        # column rename, and left AS IS rather than widened to `entity`: the two classes drew a
        # real distinction (a keyed dimension facts point at, vs a thing with its own life) that
        # `entity` alone cannot recover, and widening this to `entity` regresses every plain
        # entity (Widget here; Customer/Location/Store on contoso5) into a register-resolution
        # branch they were never meant to enter — measured: the shared Widget fixture's own
        # `resolve` step broke. `reference` is therefore dead code (unreachable by any bundle
        # that validates) rather than a live comparison; re-drawing the line is a human ruling
        # this task is not authorised to make, and is reported as a gap, not patched here.
        regs = sorted(set(re.findall(r"data/lookups/[\w.\-]+\.csv", raw)))
        # THE REGISTER'S HOME IS THE DATA-PLANE COLUMN. Grepping this file finds a register only when
        # someone also named it in prose here, which is the second home §2.1 removes. Region grounds
        # `State`, whose register was cut and declared on the column; nothing was missing but the read.
        if not regs and registers is not None:
            for _c in ([P.canonical_key(doc)] or []) + P.key_parts(doc):
                hit = registers.get((src.get("relation"), _c)) if _c else None
                if hit:
                    regs = [f"{hit} (declared on {src.get('relation')}.{_c})"]
                    break
        # A REFERENCE MAY RESOLVE THROUGH ITS ATTRIBUTES, and `resolvers()` below already computes
        # exactly that — it just fed the prose and never the step. A2 names Product as THE example
        # of `reference`, and Product is 2,517 surrogate-keyed SKUs: no register can exist on its
        # key, and none is needed, because nobody asks for "Contoso 4G MP3 Player E400 Green" —
        # they ask for green MP3 players, or Contoso audio. Measured 2026-09-29 on contoso5:
        # `resolvers(Product)` returned Brand, ProductCategory and Color, each with a register, and
        # the step still read None. Under the old rule a large keyed dimension could never be a
        # reference, which contradicts the procedure that decides the class.
        #
        # THE PATH IS STILL OFFLINE. brand -> register -> code, then filter the product rows: no
        # probe. And it is derived from the grounding, so a reference with no attribute that any
        # concept resolves still reads None — that is the mutant below.
        if not regs and not v.get("items") and registry is not None:
            via = resolvers(doc, registry)
            if via:
                regs = [f"through {n} ({r})" for n, r in via]
        # A CALENDAR RESOLVES ITSELF — the built-in reads it, and that IS a declaration.
        #
        # This check modelled exactly ONE resolve mechanism, a register, and the worked bundle's own
        # log said so at the time: "a date is self-resolving under ISO, and the gate has no notion of
        # that ... its own mutant is 'take the register away'". The conclusion drawn then was to cut
        # registers for the calendar words — `year_month` (132 members), `year_quarter` (44), the
        # month names, the weekdays — and the operator overturned it on 2026-09-30: "remove handling
        # dates and time with lookup tables ... refactor our ontology to use built in recognition for
        # time instead of lookups". Deleting those eight registers then left THIS step reading None,
        # so the bundle stopped compiling for doing the right thing.
        #
        # A temporal column needs no register and cannot have one
        # (guardrails/data/sources.yaml#TEMPORAL-AS-LOOKUP). The declaration that supplies the step is
        # the COLUMN'S OWN TYPE plus the framework's `mac_vocabulary.yaml#calendar_vocabulary`, read
        # by mac-runtime/temporal.py. This is not a waiver: a concept with no register AND no temporal
        # column still reads None, which is the mutant this check is built on.
        if not regs and not v.get("items"):
            calendar = _self_resolving(doc)
            if calendar:
                regs = [
                    f"the built-in calendar ({calendar}; "
                    f"mac_vocabulary.yaml#calendar_vocabulary, no register)"
                ]
        path["resolve"] = (", ".join(regs) if regs else
                           (f"values.items ({len(v['items'])} members, in-file)" if v.get("items") else None))
    else:
        path["resolve"] = "delegated — a measure resolves names through the concepts it references"

    # THE GRAIN IS THE KEY, and since 2026-10-07 `source.key` is its ONLY home. The prose
    # `grounding.grain` was retired first (operator ruling: a restatement of the key, in words no
    # reader could act on); the per-column `identity: canonical`/`composite` flag that then carried
    # it was retired in turn the SAME DAY, afternoon, for `source.key` itself — an ordered list, on
    # the source, because a column flag could not state the key's ORDER and the order reaches the
    # SQL (column_declaration.md rev 5). A snapshot relation still answers first: its grain is one
    # row per cell per cycle, which the key alone does not say.
    _canonical, _parts = P.canonical_key(doc), P.key_parts(doc)
    if g.get("snapshot_rule"):
        path["grain"] = f"grounding.snapshot_rule ({(g.get('realized_by') or {}).get('udf', 'prose')})"
    elif _canonical:
        path["grain"] = f"grounding.source.key: {_canonical}"
    elif _parts:
        path["grain"] = "grounding.source.key (composite): " + ", ".join(_parts)
    else:
        path["grain"] = None

    if cls == "measure":
        # THE FOLD LAW'S TWO INPUTS, BOTH ON THE COLUMN. `concept.semantics.{measure_type,
        # axis_kinds}` is what this read until 2026-10-07; `axis_kinds` was a map keyed by COLUMN
        # name sitting on the concept, which the runtime looked up by a lowercased CONCEPT name and
        # could never match — 47 entries, 0 reads. What the period reading actually needs is a
        # quantity whose kind is declared and an axis to resolve it over, and both are now stated
        # by the columns that ARE them.
        _folding = P.column_roles(doc, "aggregate")
        _kinds = {c: (m or {}).get("type") for c, m in _folding.items() if isinstance(m, dict)}
        _typed = {c: k for c, k in _kinds.items() if k}
        _axes = P.column_roles(doc, "axis")
        path["period"] = (
            f"columns {', '.join(sorted(_typed))} x axis on "
            f"{', '.join(sorted(_axes))} -> mac.resolve.period_reading"
            if _typed and _axes else None
        )
    else:
        path["period"] = "n/a — not a measure"

    if ct.get("default_reading"):
        path["default"] = "contract.default_reading"
    return path


#: The declared column types a calendar is measured in — the same set the runtime compares a date
#: against (mac-runtime/temporal.py TEMPORAL_COLUMN_TYPES). A string column holding date-shaped text
#: is NOT one: comparing a date to it is lexical and mis-orders without failing.
_TEMPORAL_TYPES = ("date", "timestamp", "datetime", "timestamptz")


def _self_resolving(doc: dict) -> str:
    """WHY this concept needs no register, from its own declarations — or `""` when it does need one.

    TWO DECLARATIONS, both authored and both already in the vocabulary:

      `identity.kind: iso` — mac_vocabulary.yaml#concept.identity.iso: "a universal external
        standard code. Identity = the standard code; local names/labels are aliases." A standard is
        not a bundle's word list: the reader knows it. CalendarDay has declared exactly this since it
        was written ("a calendar date is its own identity under the ISO calendar") and the step still
        read None, because this check modelled one mechanism — a register — and the bundle's own log
        said so at the time.

      a column declaring `type:` temporal, or `roles: {period_binding: true}` — a bundle saying
        which column is the date a question means. Either is enough; neither is sniffed from a name.

    NOT A WAIVER. A concept with no register, no inline values, no ISO identity and no declared date
    column still reads None — the mutant this check rests on.
    """
    # `concept.identity.kind` LEFT THE SCHEMA 2026-10-05 (two days before the column standard's own
    # rename) WITH NO REPLACEMENT DECLARED ANYWHERE — unlike every other address this file touches,
    # there is no current vocabulary term for "this concept's identity is a universal external
    # standard" to re-point this branch to. Reading it costs nothing (a document that validates
    # against the current schema never carries `concept.identity`, so this simply never matches),
    # and inventing a replacement mechanism is outside what this task is authorised to decide — left
    # as a known, reported gap rather than papered over.
    ident = (doc.get("concept") or {}).get("identity") or {}
    if str(ident.get("kind") or "").strip().lower() == "iso":
        return "identity.kind: iso"
    found = []
    # `grounding.source` IS SINGULAR since 2026-10-07.
    src = (doc.get("grounding") or {}).get("source")
    if isinstance(src, dict):
        columns = src.get("columns")
        if isinstance(columns, dict):
            for name, spec in columns.items():
                if not isinstance(spec, dict):
                    continue
                declared = str(spec.get("type") or "").strip().lower()
                # `offers.period_binding` since 2026-10-07 afternoon (`roles` -> `offers`, the same
                # revision as the column map's own rename); there is no bare `role: period` left to
                # fall back to — the column body's `additionalProperties: false` refuses it.
                offers = spec.get("offers") if isinstance(spec.get("offers"), dict) else {}
                binds = bool(offers.get("period_binding"))
                if declared in _TEMPORAL_TYPES or binds:
                    found.append(str(name))
        # THE LEGACY FORM IS A LIST OF NAMES, and it carries no type and no role — 21 concepts
        # were on it when the column standard landed. A list says nothing about a date, so it
        # supplies nothing here. Reading it as a mapping raised AttributeError and turned a
        # clean rejection into an unattributed crash: two of this gate's own mutants caught it
        # the minute it was written (2026-09-30), which is what they are for.
    return ", ".join(sorted(set(found)))


def check_answerability(root) -> list:
    concepts = _load(root)
    # ZERO IS NOT A SCORE. "0 of 0 concept(s) measured" is what this check printed on a foldered
    # bundle for as long as it globbed flat — a pass shape for a run that never happened.
    if not concepts:
        return [D.empty_denominator("MAC011", "check_answerability", P.concepts_dir(root))]
    users = collections.Counter()
    for _n, (_rel, d, _raw) in concepts.items():
        src = (d.get("grounding") or {}).get("source")
        if isinstance(src, dict) and src.get("relation"):
            users[src["relation"]] += 1

    registers = P.column_registers(root)
    # THE CONCEPT KEY-REGISTRY, computed once: which reference/enumeration concept owns which
    # canonical column, and the register that resolves a name to it. `answer_path` reads it so a
    # reference with no register of its own can resolve THROUGH the concepts it grounds — the path
    # `resolvers()` always computed and only ever rendered.
    registry = key_registry(concepts)
    gaps, stubs = [], []
    for name, (rel, d, raw) in sorted(concepts.items()):
        ident = (d.get("concept") or {}).get("identity") or {}
        if ident.get("kind") == "sme_pending":
            stubs.append(name)
            continue
        src = (d.get("grounding") or {}).get("source") or {}
        path = answer_path(d, raw, users.get(src.get("relation"), 0) > 1, registers=registers,
                           registry=registry)
        for step in STEPS:
            if path.get(step) is None:
                gaps.append(D.Witness(file=rel, path=f"answer_path.{step}",
                                      detail=f"{name}: no declaration supplies the `{step}` step"))
    # A CLEAN RESULT IS STILL A MEASUREMENT. Reporting nothing when nothing is wrong loses the two
    # facts a reader needs to trust the verdict: how many concepts were measured, and which were
    # exempted from measurement. A consumer that sees silence cannot tell "all derive" from "not run",
    # and a dashboard built on silence reports 100 % of an unknown denominator.
    derived = len(concepts) - len(stubs) - len({w.detail.split(":")[0] for w in gaps})
    if not gaps:
        return [D.Diagnostic(
            code="MAC011", severity=D.INFO, source="check_answerability",
            summary=f"every answer path derives — {derived} of {len(concepts) - len(stubs)} concept(s) "
                    f"measured, {len(stubs)} exempt",
            note="Each concept's read / select / resolve / grain / period step is supplied by a "
                 "declaration, so its no_probe_guarantee is derivable rather than sworn to."
                 + (f" Exempt as declared refuse-stubs: {', '.join(stubs)}." if stubs else ""))]
    return [D.Diagnostic(
        code="MAC011", severity=D.ERROR, source="check_answerability",
        summary=f"{len(gaps)} answer-path step(s) cannot be derived from any declaration",
        note="mac.schema.json on no_probe_guarantee: 'if more is needed, the concept is INCOMPLETE "
             "(fix it, don't probe)'. A step no declaration supplies is that incompleteness — and a "
             "hand-written guarantee asserting otherwise is a promise nothing keeps. Supply the "
             "declaration; the guarantee is then derivable rather than sworn."
             + (f" Exempt as declared refuse-stubs: {', '.join(stubs)}." if stubs else ""),
        witnesses=gaps)]


# ── the gate's OWN rule, seeded and mutated ───────────────────────────────────────────────────────
# The discovery fixtures prove this gate SEES a concept. They prove nothing about whether it can still
# REJECT one — the shared harness says so in its own docstring, and it printed `0 mutants of its own
# rule` here until the `select`/`resolve` derivation was rewritten to read the single home. A rule
# without a mutant is a rule nothing re-measures.

_SUBJECT_GADGET = """concept:
  name: Gadget
  label: Gadget
  class: entity
  semantics:
    definition: A second concept on the SAME relation, so `shared` is true and the select rule runs.
grounding:
  source:
    relation: widget_register
    key: gadget_code
    columns:
      gadget_code:
        offers: {}
"""

_SUBJECT_DESCRIPTOR = """table:
  name: widget_register
columns:
- name: widget_code
  register: data/lookups/widget.lookup.csv
- name: gadget_code
"""


def _subject(root):
    """Seed a NON-ZERO population for this gate's own rule, on top of the concept fixture.

    Two facts the bare fixture lacks. A SECOND concept on the same relation, because `select` is only
    demanded when a relation is shared — with one concept the gate takes the dedicated-relation
    exemption and the rule never runs. And an ENUMERATION with no register, because `resolve` for a
    reference/enumeration concept reads EITHER a register declared on the data-plane column OR an
    inline `values.items` block — Hue exercises the second address.

    DROPPED 2026-10-07: the Doodad/attribute-resolution pair. It demonstrated a `reference`-classed
    concept with NO register of its own resolving THROUGH an enumeration it grounds (Hue) — a real
    mechanism `resolvers()` still computes. `reference` was RENAMED `entity` 2026-10-05 (a SEPARATE,
    earlier retirement), which collapsed "a keyed dimension facts point at" into the SAME class word
    as "a thing with its own life" — so `answer_path`'s `cls in ("reference", "enumeration")` check
    can no longer be told to recognise Doodad's shape without ALSO recognising every plain entity
    (Widget here; Customer/Location/Store on contoso5), which regresses them into a register-
    resolution branch they were never meant to enter (measured: doing so broke Widget's own
    `resolve` step in this very fixture). Re-drawing that line is a human ruling outside today's
    task; the mechanism this pair tested is left AS A REPORTED GAP, not asserted here as working.
    """
    (Path(root) / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
    cdir = Path(root) / "ontology" / "concepts"
    if not cdir.is_dir() or not any(cdir.rglob("*.yaml")):
        cdir = Path(root) / "concepts"                      # the flat_layout fixture
    (cdir / "gadget.yaml").write_text(_SUBJECT_GADGET, encoding="utf-8")
    dd = Path(root) / "data" / "datasets"
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "widget_register.yaml").write_text(_SUBJECT_DESCRIPTOR, encoding="utf-8")
    (cdir / "hue.yaml").write_text(_SUBJECT_HUE, encoding="utf-8")


_SUBJECT_HUE = """metadata: {concept: Hue, schema_version: 0.1.16, status: draft, owner: t, confidence: I, provenance: authored}
concept:
  name: Hue
  class: enumeration
  definition: a colour word
values:
  closure: closed
  items:
    - {code: red, label: red, meaning: red}
    - {code: blue, label: blue, meaning: blue}
grounding:
  source:
    relation: hue_register
    key: hue
    columns:
      hue: {offers: {axis: categorical}}
"""


def _widget(root):
    for c in (Path(root) / "ontology" / "concepts", Path(root) / "concepts"):
        hit = next(iter(c.rglob("widget.yaml")), None) if c.is_dir() else None
        if hit:
            return hit
    raise AssertionError("fixture widget.yaml not found")


def _break_select(root):
    """Take away every declaration that can supply `select` on a SHARED relation.

    RE-POINTED 2026-10-07 AFTERNOON, the SAME DAY this was last re-pointed (morning: the flag moved
    from `concept.identity.canonical_key` to a column `roles: {identity: canonical}` flag). That flag
    is ALSO gone now: `source.key` is the one and only home for the grain (column_declaration.md
    rev 5), on the SOURCE rather than a column, so stripping a column's `offers` proves nothing —
    `widget_code` would still be the key via `source.key` regardless of what its `offers` says, and
    the old mutation text would have matched nothing (a mutant that cannot mutate). The live
    mutation removes `source.key` itself.

    THIS ALSO BREAKS `grain`, not only `select`, and that is not a loosening of the test: `select`
    and `grain` are BOTH derived from `source.key` now (there is no second, independent address for
    either), so a bundle that loses its key loses both truthfully. The assertion below only requires
    `answer_path.select` to be among the reported gaps, which it still is.
    """
    f = _widget(root)
    t = f.read_text(encoding="utf-8")
    broken = t.replace("    key: widget_code\n", "")
    assert broken != t, "the select mutation matched nothing — the fixture's key moved"
    f.write_text(broken, encoding="utf-8")


def _break_resolve(root):
    """Take away Hue's `values.items` — the only thing that turns a NAME into its code, now that
    it carries no register of its own either.

    RE-POINTED 2026-10-07: the old mutant removed WIDGET's data-plane register pointer, but Widget
    is class `entity`, which `answer_path` has never routed through the register-resolution branch
    (`cls in ("reference", "enumeration")` — `entity` is not in it, deliberately; see `_subject`'s
    docstring) — so that mutation was ALREADY inert, independent of today's rename. Hue IS an
    `enumeration`, the one class this branch still reaches, and stripping its inline `values` is
    the live equivalent: no register, no items, nothing left to resolve a name through.
    """
    for c in (Path(root) / "ontology" / "concepts", Path(root) / "concepts"):
        h = c / "hue.yaml"
        if h.exists():
            t = h.read_text(encoding="utf-8")
            broken = t.split("\ngrounding:", 1)
            assert len(broken) == 2, "fixture hue.yaml has no `grounding:` to split on"
            h.write_text("concept:\n  name: Hue\n  class: enumeration\n  definition: a colour word"
                         "\ngrounding:" + broken[1], encoding="utf-8")
            return
    raise AssertionError("fixture hue.yaml not found")


_MUTANTS = (
    ("select_gone",  _break_select,  "answer_path.select",
     "a concept sharing its relation, with nothing that discriminates it"),
    ("resolve_gone", _break_resolve, "answer_path.resolve",
     "an enumeration with no register and no inline values cannot resolve a name offline"),
)


def main() -> int:                                                      # pragma: no cover
    if "--self-test" in sys.argv[1:]:
        return P.selftest_discovery(__file__, subject=_subject, mutants=_MUTANTS)
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_answerability(root)
    print(D.render(d, root, show=D.INFO) or "check_answerability: every concept's answer path derives")
    # AN ERROR FINDING IS A FAILING EXIT. This returned 0 whatever it found, so the CLI could report
    # 13 underivable steps and still look green to anything reading the exit code — and no mutant of
    # its own rule could be written, because a rejection was indistinguishable from a pass.
    if any(D.UNKNOWN_MARK in x.summary for x in d):
        return D.EMPTY_EXIT
    return 1 if any(x.severity == D.ERROR for x in d) else 0


# ── the projection: the guarantee RENDERED from the path, so it cannot drift ──────────────────────

def resolvers(doc: dict, registry: dict) -> list:
    """Which OTHER concepts this one resolves names through, and the register each resolves in.

    DERIVED, not listed: a concept's grounding columns are matched against every other concept's
    canonical key. A measure grounding `<source>_model_code` is resolving models, whether or not anyone
    wrote that down — and the model concept already declares which register turns a name into that
    code. Enumerating it here is what keeps a generated guarantee from telling a one-shot agent to go
    and navigate three other files."""
    g = doc.get("grounding") or {}
    s = g.get("source") or {}
    cols = set(s.get("columns") or [])
    k = s.get("key")
    cols |= {k} if isinstance(k, str) else set(k or ())
    mine = ((doc.get("concept") or {}).get("name"))
    out = []
    for col in sorted(cols):
        hit = registry.get(col)
        if hit and hit[0] != mine:
            out.append(hit)
    seen, uniq = set(), []
    for cname, reg in out:
        if cname not in seen:
            seen.add(cname); uniq.append((cname, reg))
    return uniq


def key_registry(concepts: dict) -> dict:
    """canonical key column -> (concept name, the register that resolves a name to it)."""
    reg = {}
    for name, (_rel, d, raw) in concepts.items():
        c = d.get("concept") or {}
        if c.get("class") not in ("reference", "enumeration"):
            # `reference` is dead (see answer_path's matching comment) — left unwidened for the
            # same reason, same gap.
            continue
        ck = P.canonical_key(d)
        if not ck:
            continue
        csvs = sorted(set(re.findall(r"data/lookups/[\w.\-]+\.csv", raw)))
        v = d.get("values") or {}
        reg[ck] = (name, csvs[0] if csvs else
                   (f"values.items on {name} ({len(v['items'])} members)" if v.get("items") else None))
    return reg


def consumers(doc: dict, concepts: dict) -> list:
    """The relations that CONSUME this concept's canonical key — the outbound direction.

    A dimension's guarantee has to say how it is attached to a fact, not only how its own names
    resolve. Derived by scanning every other concept's grounding columns for this one's key, so it
    stays correct when a new fact starts using the dimension."""
    ck = P.canonical_key(doc)
    mine = (doc.get("concept") or {}).get("name")
    if not ck:
        return []
    out = set()
    for name, (_rel, d, _raw) in concepts.items():
        if name == mine:
            continue
        s = (d.get("grounding") or {}).get("source") or {}
        cols = set(s.get("columns") or [])
        k = s.get("key")
        cols |= {k} if isinstance(k, str) else set(k or ())
        if ck in cols and s.get("relation"):
            out.add(s["relation"])
    return sorted(out)


def edge_paths(name: str, edges: list) -> list:
    """The declared joins this concept takes part in — MAC's own home for a join is the EDGE layer.

    The first cut of this renderer derived the attach path from column overlap alone, which found the
    fact joins and missed every dimension reached through another dimension: PackageType is joined via
    dim_product, and its key never appears on the fact at all. Eleven concepts lost a relation that way.
    The edges were there the whole time, carrying `join_rule`."""
    out = []
    for e in edges or []:
        ep = e.get("endpoints") or {}
        a = (ep.get("from") or {}).get("concept")
        b = (ep.get("to") or {}).get("concept")
        if name not in (a, b):
            continue
        other = b if a == name else a
        out.append((other, e.get("join_rule") or e.get("edge_id") or "", e.get("level")))
    return sorted(set(out))


def load_edges(root):
    import yaml
    f = Path(root) / "ontology" / "edges.yaml"
    if not f.exists():
        return []
    try:
        return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("edges") or []
    except Exception:                                                    # noqa: BLE001
        return []


def render_guarantee(name: str, doc: dict, raw: str, shared: bool, registry: dict | None = None,
                     concepts: dict | None = None, edges: list | None = None) -> str:
    """The no_probe_guarantee as a VIEW of the declarations, not a second copy of them.

    Why render at all, when answer_path() already names every source: because a reader following
    "values.aliases.map" has to go and read it. The rendered form carries the VALUES as well as their
    addresses, which is what the hand-written blocks were for — minus the drift, because it is
    regenerated from the same declarations the check verifies."""
    c = doc.get("concept") or {}
    g = doc.get("grounding") or {}
    v = doc.get("values") or {}
    ct = doc.get("contract") or {}
    s = c.get("semantics") or {}
    src = g.get("source") or {}
    path = answer_path(doc, raw, shared, registry=registry)
    L = [f"GENERATED from this concept's declarations — do not edit; edit the declarations.",
         f"To use {c.get('label') or name} an agent needs ONLY:"]
    n = 0

    amap = (v.get("aliases") or {}).get("map") or {}
    if amap and shared:
        n += 1
        codes = ", ".join(sorted(amap))
        surf = sorted({s2 for e in amap.values()
                       for arr in (e.get("multilingual") or {}).values() for s2 in arr})
        L.append(f"  {n}. SELECT the rows: {path['select'].split(': ')[0] if ': ' in path['select'] else path['select']}"
                 f" — code {codes}"
                 + (f"; recognised as {', '.join(surf[:6])}" + (" ..." if len(surf) > 6 else "") if surf else ""))
    elif shared and path.get("select"):
        n += 1
        L.append(f"  {n}. SELECT the rows: {path['select']}")

    if ct.get("default_reading"):
        n += 1
        dr = " ".join(str(ct["default_reading"]).split())
        L.append(f"  {n}. WHEN THE QUESTION IS SILENT: {dr}")

    if c.get("class") in ("reference", "enumeration"):
        # `reference` is dead (see answer_path's matching comment) — left unwidened, same gap.
        n += 1
        L.append(f"  {n}. RESOLVE a name to its code OFFLINE: {path['resolve']}")
    else:
        n += 1
        rs = resolvers(doc, registry or {})
        if rs:
            L.append(f"  {n}. RESOLVE each named entity OFFLINE, never as a literal against the fact:")
            for cname, reg in rs:
                L.append(f"       {cname} -> {reg or 'NO OFFLINE REGISTER — this concept cannot refuse an unknown name'}")
        else:
            L.append(f"  {n}. RESOLVE any named entity through its own concept, which resolves it offline")

    if g.get("snapshot_rule"):
        n += 1
        udf = (g.get("realized_by") or {}).get("udf")
        L.append(f"  {n}. COLLAPSE to one row per cell: grounding.snapshot_rule"
                 + (f", realized by {udf}" if udf else ""))

    if c.get("class") == "measure" and s.get("measure_type"):
        n += 1
        L.append(f"  {n}. READ A BARE PERIOD as {str(s['measure_type']).split('.')[-1]} dictates"
                 f" (mac.resolve.period_reading)")

    cons = consumers(doc, concepts or {})
    eps = edge_paths(name, edges or [])
    if cons or eps:
        n += 1
        L.append(f"  {n}. ATTACH to other objects by the DECLARED joins:")
        for r in cons:
            L.append(f"       {r} — joins on the key above")
        for other, rule, lvl in eps:
            L.append(f"       {other} ({lvl}) — {rule}")
    n += 1
    L.append(f"  {n}. READ from {src.get('relation')}"
             + (f", keyed on {', '.join(src['key']) if isinstance(src.get('key'), list) else src.get('key')}"
                if src.get("key") else ""))
    L.append("Never probe, and never filter a NAME literal against the fact — every name resolves to a "
             "code first (mac.resolve.join_on_declared_key, mac.guarantee.never_guess).")
    return "\n".join(L) + "\n"


# THE ENTRY POINT IS LAST, AND IT WAS NOT. It sat at line 391 of 570 with `key_registry` defined
# at 424 and `render_guarantee` at 494 — so a script run fired main() before those names
# existed. Latent for as long as nothing above the guard needed a name below it; the first
# patch that did (answer_path reading the concept key-registry) crashed every layout fixture
# and every mutant with a NameError the harness reported as "rejection unattributed".
# Measured 2026-09-29. An import never sees it, which is why the in-process proof passed.
if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
