#!/usr/bin/env python3
"""check_answerability — can a concept be USED without probing, and is that DERIVED rather than sworn?

WHY THIS EXISTS
---------------
mac.schema.json describes `contract.no_probe_guarantee` as "what an agent needs ONLY, to use this
concept without probing the data; if more is needed, the concept is incomplete (fix it, don't probe)."

That is a COMPLETENESS TEST. gaps/fpl2 answered it the way every bundle does: by hand, in prose, once
per concept — twenty-two blocks reciting the steps an agent should take. Every step of every one of
them restates a declaration that already exists.

MEASURED on that bundle, 2026-08-19, walking DtC clause by clause: the kpi codes and the default are
`values.aliases.map` + `contract.default_reading`; the role pin and the vintage collapse are the
Perspective concept + `grounding.snapshot_rule`; the name resolutions are the referenced concepts'
own lookup registers; the period reading is `semantics.measure_type` x `axis_kinds` through
mac.resolve.period_reading; the read is `grounding.sources[]`; and the closing "no probing, no name
literal" is mac.resolve.join_on_declared_key + mac.guarantee.never_guess. Residue: NONE.

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
  this, fpl2's OBReach is reported incomplete — it is served from its own relation and its own file
  says so ("there is no `kpi` code here"). Measured: 1 false finding.

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


def answer_path(doc: dict, raw: str, shared: bool) -> dict:
    """The steps an agent needs, DERIVED. Each value is the declaration that supplies it, or None.

    `shared` says whether another concept grounds the same relation — the only fact that cannot be
    read off this document alone, because it is a property of the bundle."""
    c = doc.get("concept") or {}
    g = doc.get("grounding") or {}
    v = doc.get("values") or {}
    ct = doc.get("contract") or {}
    s = c.get("semantics") or {}
    ident = c.get("identity") or {}
    src = (g.get("sources") or [{}])[0]
    cls = c.get("class")

    path: dict = {}
    path["read"] = (f"grounding.sources[0]: {src['relation']}"
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
            elif ident.get("canonical_key"):
                path["select"] = f"concept.identity.canonical_key: {ident['canonical_key']}"
            elif v.get("items"):
                path["select"] = f"values.items ({len(v['items'])} members)"
            else:
                path["select"] = None

    if cls in ("reference", "enumeration"):
        regs = sorted(set(re.findall(r"data/lookups/[\w.\-]+\.csv", raw)))
        path["resolve"] = (", ".join(regs) if regs else
                           (f"values.items ({len(v['items'])} members, in-file)" if v.get("items") else None))
    else:
        path["resolve"] = "delegated — a measure resolves names through the concepts it references"

    path["grain"] = (f"grounding.snapshot_rule ({(g.get('realized_by') or {}).get('udf', 'prose')})"
                     if g.get("snapshot_rule") else
                     (f"grounding.sources[0].key: {src['key']}" if src.get("key") else None))

    if cls == "measure":
        path["period"] = (f"{s['measure_type']} x axis_kinds -> mac.resolve.period_reading"
                          if s.get("measure_type") and s.get("axis_kinds") else None)
    else:
        path["period"] = "n/a — not a measure"

    if ct.get("default_reading"):
        path["default"] = "contract.default_reading"
    return path


def check_answerability(root) -> list:
    concepts = _load(root)
    # ZERO IS NOT A SCORE. "0 of 0 concept(s) measured" is what this check printed on a foldered
    # bundle for as long as it globbed flat — a pass shape for a run that never happened.
    if not concepts:
        return [D.empty_denominator("MAC011", "check_answerability", P.concepts_dir(root))]
    users = collections.Counter()
    for _n, (_rel, d, _raw) in concepts.items():
        for src in ((d.get("grounding") or {}).get("sources") or []):
            if isinstance(src, dict) and src.get("relation"):
                users[src["relation"]] += 1

    gaps, stubs = [], []
    for name, (rel, d, raw) in sorted(concepts.items()):
        ident = (d.get("concept") or {}).get("identity") or {}
        if ident.get("kind") == "sme_pending":
            stubs.append(name)
            continue
        src = ((d.get("grounding") or {}).get("sources") or [{}])[0]
        path = answer_path(d, raw, users.get(src.get("relation"), 0) > 1)
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


def main() -> int:                                                      # pragma: no cover
    if "--self-test" in sys.argv[1:]:
        return P.selftest_discovery(__file__)
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_answerability(root)
    print(D.render(d, root, show=D.INFO) or "check_answerability: every concept's answer path derives")
    return D.EMPTY_EXIT if any(D.UNKNOWN_MARK in x.summary for x in d) else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())


# ── the projection: the guarantee RENDERED from the path, so it cannot drift ──────────────────────

def resolvers(doc: dict, registry: dict) -> list:
    """Which OTHER concepts this one resolves names through, and the register each resolves in.

    DERIVED, not listed: a concept's grounding columns are matched against every other concept's
    canonical key. A measure grounding `fpl_model_code` is resolving models, whether or not anyone
    wrote that down — and the model concept already declares which register turns a name into that
    code. Enumerating it here is what keeps a generated guarantee from telling a one-shot agent to go
    and navigate three other files."""
    g = doc.get("grounding") or {}
    cols = set()
    for s in (g.get("sources") or []):
        cols |= set(s.get("columns") or [])
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
            continue
        ck = (c.get("identity") or {}).get("canonical_key")
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
    ck = ((doc.get("concept") or {}).get("identity") or {}).get("canonical_key")
    mine = (doc.get("concept") or {}).get("name")
    if not ck:
        return []
    out = set()
    for name, (_rel, d, _raw) in concepts.items():
        if name == mine:
            continue
        for s in ((d.get("grounding") or {}).get("sources") or []):
            cols = set(s.get("columns") or [])
            k = s.get("key")
            cols |= {k} if isinstance(k, str) else set(k or ())
            if ck in cols and s.get("relation"):
                out.add(s["relation"])
    return sorted(out)


def edge_paths(name: str, edges: list) -> list:
    """The declared joins this concept takes part in — MAC's own home for a join is the EDGE layer.

    The first cut of this renderer derived the attach path from column overlap alone, which found the
    fact joins and missed every dimension reached through another dimension: BodyType is joined via
    dim_model, and its key never appears on the fact at all. Eleven concepts lost a relation that way.
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
    src = (g.get("sources") or [{}])[0]
    path = answer_path(doc, raw, shared)
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
