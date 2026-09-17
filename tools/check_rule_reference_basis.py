#!/usr/bin/env python3
"""check_rule_reference_basis — a rule that NAMES another concept must have a reason to.

THE QUESTION THIS ANSWERS
-------------------------
Structure and cardinality are already checked: `binds` resolves to real columns
(rule-binds-grounded), pinned literals occur in the register they cite (MAC007), a shape written on
many concepts is reported (COOKBOOK C6). None of that can see whether a rule makes SENSE.

Measured case, <domain>/<dataset>. `new_orders.resolve.kpi_code` carried
"never confusing new orders with ... the delivery measure (deliveries, not placements)".
Structurally perfect. Semantically vacuous: an order PLACED and a unit DELIVERED are opposite ends of
one lifecycle, and nobody confuses them. It was machine-written (`provenance: harvested`) and
self-stamped `confidence: C`. Four of seven kpi_code rules warned against confusing something with deliveries —
a template reaching for a foil, not knowledge.

WHAT MAKES A REFERENCE LEGITIMATE
---------------------------------
A rule naming another concept is asserting a RELATIONSHIP with it. That assertion needs a basis the
ontology can show:

    an EDGE between the two                     the relationship is modelled
    THE SAME UNIT                               they measure the same kind of thing, so comparing,
                                                differencing or confusing them is meaningful
    a SHARED SURFACE TERM                       they answer to the same word (the residue the unit
                                                cannot settle — a production measure and a delivery
                                                measure are both `units` and still not confusable)

CO-GROUNDING IS NOT A BASIS, and this is the whole trick. 14 of <dataset>'s 22 concepts ground on
`v_<source>_kpi`; counting a shared fact table as a relationship makes every pair of measures look related
and hides exactly the case this check exists to find. An earlier cut did count it, and duly missed
the delivery-measure reference that prompted the check.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* A REAL relationship that the edge layer has not modelled yet. LEGITIMATE and common — the first run
  found a reach measure -> the order book it measures (reach IS a property of the order book) and a
  delivery measure -> total market (market share is their ratio), neither with an edge. These are
  findings about the EDGE layer, not about the rule, and the diagnostic says so: add the edge, or
  drop the reference.
* A concept name appearing as an ordinary English word. Guarded by requiring a word-boundary match on
  the concept NAME or its LABEL, not on fragments.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

import mac_diag as D
import mac_project as P

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sdk import registers as _registers                                 # noqa: E402

_STOP = {"the", "and", "for", "with", "per", "not", "its"}

# ─── the estate's KPI word stems ──────────────────────────────────────────────────────────────────
#
# WHY THESE ARE NOT TWO TUPLES IN THIS FILE ANY MORE. `_surface_terms` carried five stems and
# `_stems` carried six; `tools/check_mac_public.py` reported BOTH lines as leaks in this PUBLIC
# repository (2026-09-17, rule `kpi-stem-local`) — one estate's KPI vocabulary, published inside the
# framework applied to it. A rename would not do: these stems decide whether two concepts share a
# SURFACE TERM, which is one of the three bases this check accepts for a rule naming another
# concept, so they drive the check's verdict on a private corpus.
#
# THE TWO LISTS ARE NOW ONE. They differed by a single stem, nothing explained the difference, and
# nothing kept them in step — which is the two-homes-that-may-disagree defect THIS FILE exists to
# find between a rule's `binds:` and its prose. MEASURED on the bundle this instance guards before
# the move: MAC003 9 / MAC008 4 findings under either list, and under no list at all, so unifying
# them moves no finding there.
#
# ABSENT REGISTER: REDUCED SCOPE, DISCLOSED — NOT could-not-run. Justified:
#   · The stems only ever ADD a basis. With none, `_surface_terms` still returns every DECLARED
#     alias, name, label and german surface — the auditable evidence — and loses only the fallback
#     prose scrape and the stem expansion. So the absent-register direction is FAIL-SAFE: it can
#     only produce MORE unbased findings, never hide one. A check that over-reports loudly is a
#     different animal from a check that under-reports in silence, and only the second is the
#     empty-population defect.
#   · Exiting 2 would take MAC002, MAC003 and MAC008 binds-conformance — ERROR-severity classes that
#     never read this register — offline over an optional fallback vocabulary. A gate that refuses
#     to run for a reason unrelated to what it is checking is a gate that gets skipped.
#   · So it runs, and it SAYS SO: the stem denominator is on the verdict line of every run, and the
#     MAC008 diagnostic's own note warns that it may over-report when the vocabulary is empty.
_ESTATE_REGISTER = "estate_terms"
_ESTATE_GROUP = "kpi_surface_stem"


def _kpi_stems() -> tuple:
    """This estate's KPI word stems, lowercased, or () when none are declared.

    Read at CALL time, never snapshot at import: `$MAC_ESTATE_TERMS` is how CI and the self-test
    declare a register, and a module-level snapshot ignores an override set after this import.
    """
    return tuple(sorted({s.strip().lower() for s in
                         _registers.group(_ESTATE_REGISTER, _ESTATE_GROUP) if s.strip()}))


def _unit(concept: dict) -> str:
    """The measure's declared unit, normalised. THE PRIMARY BASIS — and it was sitting in
    `semantics.unit` on all 9 <dataset> measures while the first cut of this check scraped German nouns
    out of prose to guess the same thing, badly. MAC declared it; nothing read it."""
    u = ((concept.get("semantics") or {}).get("unit") or "")
    return re.sub(r"[^a-z0-9]", "", str(u).lower())


def _declared_aliases(doc: dict) -> set:
    """Every NL surface the concept DECLARES, from values.aliases.map[*].multilingual — the auditable
    trigger vocabulary (aliasBlock, mac.schema.json:840). Read before the prose heuristic below,
    because a declared surface is evidence and a scraped one is a guess."""
    out = set()
    for spec in (((doc.get("values") or {}).get("aliases") or {}).get("map") or {}).values():
        for arr in ((spec or {}).get("multilingual") or {}).values():
            if isinstance(arr, list):
                out |= {str(t) for t in arr}
        for arr in ((spec or {}).get("scope_relative") or {}).values():
            if isinstance(arr, list):
                out |= {str(t) for t in arr}
    return out


def _surface_terms(concept: dict, doc: dict, stems: tuple = ()) -> set:
    """Words this concept answers to: its DECLARED aliases first, then its name, label, german, and —
    only as a fallback — the capitalised German nouns its own prose uses.

    The prose scrape was written with the note "deliberately shallow — until `concept.aliases` exists
    these are scattered". They exist now: <domain>/<dataset> declares 38 surfaces across 7 measures, sourced
    from the gold ontology's SME-ratified map. A declared surface is evidence; a scraped one is a
    guess that happened to work, and the scrape is kept only for concepts that declare none."""
    out = _declared_aliases(doc) | {str(concept.get("name") or ""), str(concept.get("label") or ""),
                                    str(concept.get("german") or "")}
    # CONTAINS, not endswith. Compound nouns put the stem anywhere: a compound that merely CONTAINS a
    # stem does not end in it, and an endswith filter dropped it, which lost the one overlap that makes
    # the production pair a genuine confusion. The first cut of this check reported that real pair as
    # baseless for exactly that reason.
    # The capitalised-noun SHAPE stays in code: `[A-ZÄÖÜ][a-zäöüß]{5,}` describes how German writes
    # a noun, which is a property of the language, not of any estate. What the shape has to be
    # filtered THROUGH — which nouns are KPI words here — is the estate's, and comes from the
    # register. With no stems declared this loop adds nothing and the function returns declared
    # surfaces only; the caller discloses that.
    blob = str(doc)
    if stems:
        for w in re.findall(r"\b([A-ZÄÖÜ][a-zäöüß]{5,})\b", blob):
            if any(s in w.lower() for s in stems):
                out.add(w)
    return {o.lower() for o in out if o and o.lower() not in _STOP}


def _stems(terms: set, stems: tuple = ()) -> set:
    out = set()
    for t in terms:
        out.add(t)
        for s in stems:
            if s in t:
                out.add(s)
    return out



# ── binds conformance: the rule's DECLARED surface vs the one its prose actually uses ──────────────

_IDENT = __import__("re").compile(r"\b[a-z][a-z0-9_]{2,}\b")


def _prose(rule) -> str:
    return " ".join(str(rule.get(k) or "") for k in ("subject", "when", "then", "never"))


def _column_like(tok: str) -> bool:
    """A token distinguishable from an English word: it carries an underscore or a digit.

    CALIBRATED, not guessed. On <domain>/<dataset> (29 rules, 70 grounded columns): intersecting prose with the
    grounded column set alone flags 17 rules, of which 7 are false — `value` in "an empty result framed
    as a real zero ... substituting another measure's value" is the English word, not v_<source>_kpi.value,
    and `region` reads the same way. Requiring an underscore drops to 9, all genuine, but loses `iso2`
    in a market resolution rule ("resolve a localised name or iso2 -> market_code"), which is real.
    Underscore-OR-digit keeps that one and none of the false ones.

    THE HONEST BOUNDARY, stated rather than hidden: a single-word lowercase column — value, role,
    region, market, kpi — is indistinguishable from prose and is deliberately NOT flagged. This check
    under-reports on purpose. A gate that cried wolf on `value` in every refusal rule would be turned
    off within a day, and a check nobody runs enforces nothing."""
    return "_" in tok or any(c.isdigit() for c in tok)



# ── the reference marker: `{name}` — backtick-quoted, brace-enclosed ───────────────────────────────
#
# OPERATOR RULING 2026-08-19. A model identifier inside a rule's prose is a REFERENCE, not a word, and
# must look like one. Bare `market_code` is indistinguishable from English; `{market_code}` is not.
#
# I ARGUED AGAINST THIS and was overruled, so the reasoning is recorded rather than lost: `binds:`
# already lists a rule's columns, so marking them up puts one fact in two places. The ruling answers
# that objection instead of ignoring it — the interceptor checks BOTH directions, so the marked prose
# and `binds:` are forced into step rather than left free to drift. Two homes that must agree are not
# the same defect as two homes that may disagree.
#
# Backtick + brace, not one or the other: backticks alone are already used for emphasis throughout the
# corpus ("`role` is a discriminator"), so they cannot signal a reference; braces alone collide with
# the `{{ rules.X.template }}` injection MAC already has at check_references.py:74.

_MARKED = __import__("re").compile(r"`\{([a-z][a-z0-9_.]*)\}`")


def _bare_refs(prose: str, own: set, known_rel: set, known_schema: set) -> set:
    """Model identifiers sitting in prose UNMARKED — the thing the ruling forbids.

    Only identifiers this bundle can actually resolve are demanded: a column of the concept's own
    grounding, or a relation some concept grounds. An unresolvable token is a different finding
    (MAC008 below) and is not double-reported here."""
    marked = {m for m in _MARKED.findall(prose)}
    bare = {c for c in (set(_IDENT.findall(prose)) & own) if _column_like(c)} - marked
    for sch in known_schema:
        for tok in __import__("re").findall(rf"(?<![\w/`{{]){sch}\.([a-z_][a-z0-9_]*)\b", prose):
            if f"{sch}.{tok}" in known_rel and f"{sch}.{tok}" not in marked:
                bare.add(f"{sch}.{tok}")
    return bare


# ── a rule id named in prose that no longer exists ────────────────────────────────────────────────

_RULE_ID = __import__("re").compile(
    r"\b([a-z_]+\.(?:resolve|exclusion|exclude|guarantee|default|aggregate|read|classify)\.[a-z_]+)\b")


def _dangling_rule_ids(root, concepts: dict) -> list:
    """A concept's prose cites a sibling rule by id; the rule is later deleted; the citation stays.

    MEASURED on <domain>/<dataset>, 2026-08-19: TWELVE dangling citations across twelve files, accumulated over
    several sessions of consolidation — resolve.period_sum, resolve.stock_period, resolve.target_period,
    guarantee.unspecified_is_real. Every one of those deletions was correct and protocolled; the
    citations pointing at them were simply never swept, and no gate looked. A no_probe_guarantee that
    tells a reader to see a rule which does not exist is worse than one that says nothing: it reads as
    a promise that something else covers the case.

    `mac.*` resolves against the framework's common rules, and a FAMILY prefix is accepted — citing
    mac.exclusion.no_evidence when the leaves are .measure and .name is a reference to both, not a
    typo."""
    import yaml
    live = {rid for info in concepts.values()
            for rid in [str(r.get("id")) for r in ((info["doc"].get("contract") or {}).get("rules") or [])]}
    try:
        cf = Path(__file__).resolve().parent.parent / "mac_rules.yaml"
        common = {str(r.get("id")) for r in ((yaml.safe_load(cf.read_text(encoding="utf-8")) or {})
                                             .get("rules") or [])}
    except Exception:                                                   # noqa: BLE001
        common = set()

    def known(rid: str) -> bool:
        return rid in live or rid in common or any(c.startswith(rid + ".") for c in common)

    out = []
    for name, info in sorted(concepts.items()):
        rel = info["rel"]
        seen = set()
        for rid in _RULE_ID.findall(str(info["doc"])):
            if rid in seen or known(rid):
                continue
            seen.add(rid)
            out.append(D.Witness(file=rel, path="contract",
                                 detail=f"cites `{rid}`, which no concept in this bundle declares"))
    return out

def _binds_conformance(concepts: dict) -> list:
    """Three ways a rule's references can be wrong, none of which anything checked before.

    MEASURED on <domain>/<dataset> 2026-08-19, all three live: 9 of 29 rules named a grounded column in prose
    that `binds:` omitted; and a relation invented inside rule prose (<dataset>.dim_country_TOTAL_FICTION,
    injected as a probe) passed all eleven compile phases clean.

    WHY THIS RATHER THAN TEMPLATED PROSE. The operator asked whether rule prose should mark its
    identifiers in a jinja form — {{market_code}}, {{<dataset>.dim_market_register}}. It should not: `binds:`
    IS that declaration, sitting six lines above the sentence, and templating the prose would give one
    fact two homes that can disagree. What was missing was never the notation; it was anything checking
    that the two agree. Where a reference should genuinely be DEREFERENCED rather than marked, MAC
    already does it one layer down — ontology/protosql's `descriptor:@rel:fact#x-grain.cell_key` reads
    the key instead of restating it, which a template still would not."""
    known_rel, known_schema = set(), set()
    for info in concepts.values():
        for s in ((info["doc"].get("grounding") or {}).get("sources") or []):
            r = s.get("relation") if isinstance(s, dict) else None
            if isinstance(r, str) and "." in r:
                known_rel.add(r); known_schema.add(r.split(".", 1)[0])

    undeclared, unresolved, unmarked = [], [], []
    for name, info in concepts.items():
        rel = info["rel"]
        own = set()
        for s in ((info["doc"].get("grounding") or {}).get("sources") or []):
            own |= set(s.get("columns") or [])
            k = s.get("key")
            own |= {k} if isinstance(k, str) else set(k or ())
        for r in ((info["doc"].get("contract") or {}).get("rules") or []):
            rid, binds = str(r.get("id")), set(r.get("binds") or ())
            prose = _prose(r)

            marked = set(_MARKED.findall(prose))
            for gap in sorted(c for c in ((set(_IDENT.findall(prose)) | marked) & own) - binds
                              if _column_like(c)):
                undeclared.append(D.Witness(file=rel, path=rid,
                    detail=f"prose uses column `{gap}`; binds: does not list it"))
            for bare in sorted(_bare_refs(prose, own, known_rel, known_schema)):
                unmarked.append(D.Witness(file=rel, path=rid,
                    detail=f"`{bare}` is a model identifier written as bare prose — write it `{{{bare}}}`"))
            for sch in known_schema:
                for tok in __import__("re").findall(rf"(?<![\w/]){sch}\.([a-z_][a-z0-9_]*)\b", prose):
                    if f"{sch}.{tok}" not in known_rel:
                        unresolved.append(D.Witness(file=rel, path=rid,
                            detail=f"names relation `{sch}.{tok}` — no concept in this bundle grounds it"))

    out = []
    if undeclared:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_rule_reference_basis",
            summary=f"{len(undeclared)} rule(s) govern a column their `binds:` does not declare",
            note="What a rule operates on is stated twice — in `binds:` and in the sentence — and "
                 "nothing kept them in step. `binds:` is the machine-readable one: it is what a reader "
                 "filters, projects and impact-analyses on, so a column missing from it is invisible to "
                 "every consumer that does not read English. Add it there rather than marking up the "
                 "prose, which would make a third home for the same fact.",
            witnesses=undeclared))
    if unmarked:
        out.append(D.Diagnostic(
            code="MAC002", severity=D.ERROR, source="check_rule_reference_basis",
            summary=f"{len(unmarked)} model identifier(s) in rule prose are not marked as references",
            note="mac_rules.yaml#mac.authoring.reference_markup: a column, relation or concept named in "
                 "a rule's prose is a REFERENCE and must be written `{name}` — backtick-quoted, "
                 "brace-enclosed. Bare, it is indistinguishable from an English word, so nothing can "
                 "resolve it, rename it, or check it against `binds:`. MEASURED: an invented relation "
                 "(<dataset>.dim_country_TOTAL_FICTION) sat in rule prose through all eleven compile phases "
                 "before this existed.", witnesses=unmarked))
    if unresolved:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.ERROR, source="check_rule_reference_basis",
            summary=f"{len(unresolved)} rule prose reference(s) name a relation nothing grounds",
            note="A <schema>.<relation> token in a rule's prose that no concept in this bundle grounds. "
                 "MEASURED: an invented relation in rule prose passed all eleven compile phases clean "
                 "before this check existed — the grounding block was validated, the sentence beside it "
                 "was not.", witnesses=unresolved))
    return out

def check_rule_reference_basis(root) -> list:
    import yaml
    R = Path(root)
    concepts = {}
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane the
    # project declares. `rel` carries the ROOT-RELATIVE path (not just the file name) so a witness on
    # a foldered bundle addresses the file that actually holds the rule.
    files = P.concept_files(root)
    if not files:
        # ZERO IS NOT A SCORE — no concept read means no reference was resolved.
        return [D.empty_denominator("MAC008", "check_rule_reference_basis", P.concepts_dir(root))]
    # ONE read for the whole run, so every concept is judged against the same vocabulary. A
    # per-concept read would let an edit mid-run split the population into two populations.
    kpi_stems = _kpi_stems()
    for f in files:
        try:
            doc = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        c = doc.get("concept") or {}
        if c.get("name"):
            concepts[c["name"]] = {"doc": doc, "label": c.get("label"), "rel": P.rel(root, f),
                                   "unit": _unit(c),
                                   "surface": _stems(_surface_terms(c, doc, kpi_stems), kpi_stems)}
    edges = set()
    ef = R / "ontology" / "edges.yaml"
    if ef.exists():
        try:
            for x in ((yaml.safe_load(ef.read_text(encoding="utf-8")) or {}).get("edges") or []):
                ep = x.get("endpoints") or {}
                a, b = (ep.get("from") or {}).get("concept"), (ep.get("to") or {}).get("concept")
                if a and b:
                    edges.add(frozenset((a, b)))
        except Exception:                                               # noqa: BLE001
            pass

    # ── a surface term claimed by more than one code ─────────────────────────────────────────────
    # The aliasBlock contract is "a surface resolving to >1 code => ASK; never a silent bind". So a
    # collision is legal but expensive: every question using that token stalls for a disambiguation.
    # It is invisible without this check, because the two claims sit in two different files and
    # neither knows about the other — the exact cost of holding the map per-concept instead of in one
    # enumeration, and the reason that choice is affordable only with a gate on it.
    claims: dict = {}
    for name, info in concepts.items():
        for code, spec in ((((info["doc"].get("values") or {}).get("aliases") or {}).get("map")) or {}).items():
            for arr in ((spec or {}).get("multilingual") or {}).values():
                if isinstance(arr, list):
                    for term in arr:
                        claims.setdefault(str(term).strip().lower(), set()).add((name, code, info["rel"]))
    collisions = [D.Witness(
        file=sorted(v)[0][2], path=f"values.aliases.map",
        detail=f"surface `{k}` is claimed by {len(v)} codes: "
               + ", ".join(f"{c} ({n})" for n, c, _ in sorted(v)))
        for k, v in sorted(claims.items()) if len({c for _, c, _ in v}) > 1]

    seen, unbased = set(), []
    for name, info in concepts.items():
        for r in ((info["doc"].get("contract") or {}).get("rules") or []):
            txt = " ".join(str(r.get(k) or "") for k in ("when", "then", "never"))
            for other, oi in concepts.items():
                if other == name:
                    continue
                lbl = oi["label"] or other
                if not (re.search(r"\b" + re.escape(other) + r"\b", txt)
                        or (lbl and re.search(r"\b" + re.escape(lbl) + r"\b", txt))):
                    continue
                key = (name, other, r.get("id"))
                if key in seen:
                    continue
                seen.add(key)
                same_unit = bool(info["unit"]) and info["unit"] == oi["unit"]
                if frozenset((name, other)) in edges or same_unit or (info["surface"] & oi["surface"]):
                    continue
                why = f"units differ ({info['unit'] or '?'} vs {oi['unit'] or '?'})" if (
                    info["unit"] or oi["unit"]) else "neither declares a unit"
                unbased.append(D.Witness(
                    file=info["rel"], path=str(r.get("id")),
                    detail=f"names {other} — no edge, {why}, no shared surface term"))
    out = _binds_conformance(concepts)
    dangling = _dangling_rule_ids(root, concepts)
    if dangling:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.ERROR, source="check_rule_reference_basis",
            summary=f"{len(dangling)} prose citation(s) name a rule that does not exist",
            note="Consolidation deletes rules; the citations pointing at them are not swept, and until "
                 "now nothing looked. A guarantee that sends a reader to a rule which is gone reads as "
                 "a promise that the case is covered elsewhere.", witnesses=dangling))
    if collisions:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_rule_reference_basis",
            summary=f"{len(collisions)} alias surface(s) resolve to more than one code",
            note="The aliasBlock contract makes this legal — a surface hitting >1 code means ASK, "
                 "never a silent bind. But every question using that token then stalls for a "
                 "disambiguation, and the two claims live in different files, so nothing but this "
                 "check can see the pair. Either narrow one surface, or accept the ASK deliberately.",
            witnesses=collisions))
    if not unbased:
        return out
    # THE SHARED-SURFACE BASIS CARRIES ITS OWN DENOMINATOR INTO THE FINDING. Without the estate's
    # stem vocabulary this class over-reports — a compound noun that genuinely shares a stem with
    # another concept's is no longer seen to — and a reader who is not told that will read a
    # legitimate pair as a defect in the edge layer. The direction is safe (absence can only add
    # findings, never hide one) but it is not free, so it is stated rather than left to be inferred.
    reduced = "" if kpi_stems else (
        " NOTE — REDUCED SCOPE: 0 estate KPI word stem(s) are declared "
        f"({_registers.disclosed_path(_ESTATE_REGISTER)}), so the SHARED SURFACE TERM basis was "
        "judged on DECLARED aliases, names and labels only, with no compound-noun stem matching. "
        "This class may therefore OVER-report: a pair whose only overlap is a shared stem is listed "
        "here as baseless. Copy registers/estate_terms.example.txt, or set $MAC_ESTATE_TERMS.")
    return out + [D.Diagnostic(
        code="MAC008", severity=D.WARNING, source="check_rule_reference_basis",
        summary=f"{len(unbased)} rule reference(s) assert a relationship the ontology does not model",
        note="Each names another concept with no edge between them and no shared surface term. Two "
             "dispositions, and the ontology cannot tell them apart: the relationship is REAL and the "
             "edge layer is missing it (add the edge), or the reference is a machine-written foil "
             "(delete it). Co-grounding is deliberately NOT accepted as a basis — 14 <dataset> concepts "
             "share v_<source>_kpi, which would make every pair look related." + reduced,
        witnesses=unbased)]


def vocabulary_line() -> str:
    """The stem denominator, printed on EVERY run — healthy or not.

    A disclosure that only appears when something is wrong is one a reader learns to skim; a
    denominator that is always on the line is one a reader learns to read. This is the same reason
    `check_mac_public` prints its file count beside a PASS.
    """
    stems = _kpi_stems()
    if stems:
        return (f"  vocabulary: {len(stems)} estate KPI word stem(s) declared — the SHARED SURFACE "
                f"TERM basis is at full scope")
    return ("  vocabulary: 0 estate KPI word stem(s) declared "
            f"({_registers.disclosed_path(_ESTATE_REGISTER)} absent or empty) — REDUCED SCOPE: the "
            "SHARED SURFACE TERM basis ran on declared aliases, names and labels only, so MAC008 "
            "may OVER-report a pair whose only overlap is a shared compound-noun stem")


def main() -> int:                                                      # pragma: no cover
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_rule_reference_basis(root)
    print(D.render(d, root, show=D.INFO) or "check_rule_reference_basis: no findings")
    print(vocabulary_line())
    return D.EMPTY_EXIT if any(D.UNKNOWN_MARK in x.summary for x in d) else 0


# -------------------------------------------------------------------------------------------------
# self-test: one seeded mutant per reject class, plus the register-absent path.
#
# IN-PROCESS, AND DELIBERATELY NOT `selftest_discovery`'s mutant mechanism, which asserts exit 1.
# This check reports; it never exits 1 (its diagnostics are WARNINGs and its only non-zero code is
# the empty-denominator refusal), so a mutant routed through that mechanism would fail for the wrong
# reason and teach nobody anything. The layout/denominator property still goes through the shared
# harness below, so both denominators are printed, from the one place that owns each.
#
# Every token is SYNTHETIC (`zz...`): the estate register is gitignored, so a fresh checkout declares
# none, and a self-test reading the real one would exercise the stem class against an empty list and
# pass having checked nothing — the exact defect this change addresses.
# -------------------------------------------------------------------------------------------------

_SYN_STEM = "zzstemzz"


def _fixture(root: Path, docs: dict) -> Path:
    """A minimal flat-layout bundle: `concepts/<name>.yaml` per entry."""
    (root / "concepts").mkdir(parents=True, exist_ok=True)
    for stem, text in docs.items():
        (root / "concepts" / f"{stem}.yaml").write_text(text, encoding="utf-8")
    return root


def _concept(name: str, *, unit: str = "", cols=("zz_code", "zz_name"), relation="zzsch.zztab",
             rules: str = "", extra: str = "", noun: str = "") -> str:
    cols_s = ", ".join(cols)
    return (f"concept:\n  name: {name}\n  label: {name}\n  class: measure\n"
            + (f"  semantics:\n    unit: {unit}\n" if unit else "")
            + (f"  german: {noun}\n" if noun else "")
            + f"grounding:\n  sources:\n    - relation: {relation}\n      key: zz_code\n"
              f"      columns: [{cols_s}]\n"
            + (f"contract:\n  rules:\n{rules}" if rules else "")
            + extra)


def _self_test() -> int:
    import tempfile
    import os

    failures, checks = [], 0

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    def codes(root):
        """{(code, severity-ish label): witness count} for a fixture."""
        out = {}
        for d in check_rule_reference_basis(root):
            out[d.code] = out.get(d.code, 0) + len(d.witnesses)
        return out

    def details(root):
        return " | ".join(w.detail for d in check_rule_reference_basis(root) for w in d.witnesses)

    def notes(root):
        return " ".join(d.note for d in check_rule_reference_basis(root))

    env = _registers.REGISTERS[_ESTATE_REGISTER][1]
    saved = os.environ.get(env)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        try:
            def register(text):
                if text is None:
                    os.environ[env] = str(base / "absent" / "estate_terms.txt")
                else:
                    p = base / f"reg{len(list(base.glob('reg*.txt')))}.txt"
                    p.write_text(text, encoding="utf-8")
                    os.environ[env] = str(p)

            # ── THE REGISTER-ABSENT PATH, which is the new reject class ─────────────────────────
            # Two measures, different units, no edge, and no rule reference basis EXCEPT a compound
            # noun in each one's prose that shares a stem. That stem overlap is a legitimate basis,
            # and it exists only while the estate vocabulary is declared.
            pair = _fixture(base / "stems", {
                "zzalpha": _concept(
                    "Zzalpha", unit="widgets", noun=f"Z{_SYN_STEM[1:]}menge",
                    rules="    - id: zzalpha.exclude.not_zzbeta\n"
                          "      never: never confusing Zzalpha with Zzbeta\n"),
                "zzbeta": _concept("Zzbeta", unit="crates", noun=f"Z{_SYN_STEM[1:]}zahl"),
            })
            register(f"{_ESTATE_GROUP} | {_SYN_STEM}\n")
            with_stems = codes(pair)
            register(None)
            without = codes(pair)
            expect("MAC008" not in with_stems,
                   f"a shared compound-noun stem was NOT accepted as a basis with the register "
                   f"present: {with_stems}")
            expect(without.get("MAC008") == 1,
                   f"mutant not caught: with NO register the shared-stem basis should be invisible "
                   f"and the reference reported, got {without}")
            expect("REDUCED SCOPE" in notes(pair),
                   "the no-register MAC008 finding does not disclose that it may over-report")
            expect("REDUCED SCOPE" in vocabulary_line() and "0 estate KPI word stem" in
                   vocabulary_line(),
                   f"the no-register verdict line is not plain: {vocabulary_line()!r}")
            register(f"{_ESTATE_GROUP} | {_SYN_STEM}\n")
            expect("full scope" in vocabulary_line() and "1 estate KPI word stem" in
                   vocabulary_line(),
                   f"the healthy verdict line omits its denominator: {vocabulary_line()!r}")

            # AN EMPTY REGISTER, and a term filed under ANOTHER consumer's group, are both "absent".
            register("# nothing declared\n")
            expect(codes(pair).get("MAC008") == 1, "an EMPTY register was treated as a vocabulary")
            register(f"kpi_surface_name | {_SYN_STEM}\n")
            expect(codes(pair).get("MAC008") == 1,
                   "a stem declared under another group leaked into this check")

            # From here the register is irrelevant; keep it declared so the stem class is not the
            # thing under test.
            register(f"{_ESTATE_GROUP} | {_SYN_STEM}\n")

            # ── MAC008 unbased: a reference with no edge, no shared unit, no shared surface ─────
            unbased = _fixture(base / "unbased", {
                "zzalpha": _concept("Zzalpha", unit="widgets",
                                    rules="    - id: zzalpha.exclude.not_zzbeta\n"
                                          "      never: never confusing Zzalpha with Zzbeta\n"),
                "zzbeta": _concept("Zzbeta", unit="crates"),
            })
            expect(codes(unbased).get("MAC008") == 1 and "no edge" in details(unbased),
                   f"mutant not caught: an unbased rule reference: {codes(unbased)}")
            # AND THE BASES WORK: the same pair with the SAME unit is not reported. A rule that
            # fires on everything attributes nothing.
            based = _fixture(base / "based", {
                "zzalpha": _concept("Zzalpha", unit="widgets",
                                    rules="    - id: zzalpha.exclude.not_zzbeta\n"
                                          "      never: never confusing Zzalpha with Zzbeta\n"),
                "zzbeta": _concept("Zzbeta", unit="widgets"),
            })
            expect("MAC008" not in codes(based),
                   f"false positive: a SHARED UNIT is a declared basis and was not accepted: "
                   f"{codes(based)}")

            # ── MAC003 undeclared: prose governs a grounded column `binds:` omits ───────────────
            undeclared = _fixture(base / "undeclared", {
                "zzalpha": _concept("Zzalpha", rules="    - id: zzalpha.resolve.by_code\n"
                                                     "      binds: []\n"
                                                     "      then: resolve on `{zz_code}`\n"),
            })
            expect("binds: does not list it" in details(undeclared),
                   f"mutant not caught: a column in prose that binds: omits: {details(undeclared)}")

            # ── MAC002 unmarked: a model identifier written as bare prose ──────────────────────
            unmarked = _fixture(base / "unmarked", {
                "zzalpha": _concept("Zzalpha", rules="    - id: zzalpha.resolve.by_code\n"
                                                     "      binds: [zz_code]\n"
                                                     "      then: resolve on zz_code directly\n"),
            })
            expect("written as bare prose" in details(unmarked),
                   f"mutant not caught: an unmarked model identifier: {details(unmarked)}")

            # ── MAC008 unresolved: prose names a relation nothing grounds ───────────────────────
            unresolved = _fixture(base / "unresolved", {
                "zzalpha": _concept("Zzalpha", rules="    - id: zzalpha.resolve.by_code\n"
                                                     "      binds: []\n"
                                                     "      then: read zzsch.zzmissing instead\n"),
            })
            expect("no concept in this bundle grounds it" in details(unresolved),
                   f"mutant not caught: an invented relation in prose: {details(unresolved)}")

            # ── MAC008 dangling: prose cites a rule id that does not exist ─────────────────────
            dangling = _fixture(base / "dangling", {
                "zzalpha": _concept("Zzalpha", rules="    - id: zzalpha.resolve.by_code\n"
                                                     "      binds: []\n"
                                                     "      then: see zzalpha.resolve.gone\n"),
            })
            expect("which no concept in this bundle declares" in details(dangling),
                   f"mutant not caught: a dangling rule citation: {details(dangling)}")

            # ── MAC003 collision: one alias surface claimed by two codes ───────────────────────
            collision = _fixture(base / "collision", {
                "zzalpha": _concept("Zzalpha", extra=(
                    "values:\n  aliases:\n    map:\n"
                    "      ZZ1:\n        multilingual:\n          de: [zzshared]\n"
                    "      ZZ2:\n        multilingual:\n          de: [zzshared]\n")),
            })
            expect("is claimed by 2 codes" in details(collision),
                   f"mutant not caught: an alias surface claimed by two codes: {details(collision)}")

            # ── and a CLEAN bundle is clean, or none of the above attributes anything ──────────
            clean = _fixture(base / "clean", {"zzalpha": _concept("Zzalpha", unit="widgets")})
            expect(not codes(clean), f"false positive: a clean fixture produced findings: "
                                     f"{codes(clean)}")
        finally:
            if saved is None:
                os.environ.pop(env, None)
            else:
                os.environ[env] = saved

    if failures:
        print(f"FAIL: check_rule_reference_basis self-test — {len(failures)} failure(s) over "
              f"{checks} rule check(s)")
        for f in failures:
            print(f"  {f}")
        return 1
    # The layout/empty-denominator property is the shared harness's to own, and it prints its own
    # denominators. Both verdicts are required to pass, and the RULE verdict is printed LAST so the
    # harness's "0 mutants of its own rule" line — true of its slot, not of this file — is not the
    # last thing a reader sees.
    harness = P.selftest_discovery(__file__)
    print("  NOTE: the harness's mutant slot is empty BY DESIGN. It asserts exit 1, and this check "
          "REPORTS rather than blocks — its diagnostics are WARNINGs and its only non-zero code is "
          "the empty-denominator refusal — so a mutant routed through it would fail for the wrong "
          "reason. The rule mutants are the in-process ones counted on the next line.")
    print(f"PASS: check_rule_reference_basis self-test — {checks}/{checks} check(s) over 6 reject "
          f"class(es) (MAC002, MAC003 undeclared, MAC003 collision, MAC008 unresolved, MAC008 "
          f"dangling, MAC008 unbased) plus the register-absent, register-empty and wrong-group "
          f"paths, each attributed to its own class")
    return harness


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
