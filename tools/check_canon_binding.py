#!/usr/bin/env python3
"""check_canon_binding — a bound rule's prose must still say what its canon renders.

WHY THIS SHAPE, and not the obvious one
---------------------------------------
`realized_by` names the canon that governs a rule. The v0.1.9 contract keeps the authored prose
BESIDE it as the human twin, which raises the question this check answers: what stops the twin
drifting from the canon it claims to be governed by?

The obvious check — compare the strings — was MEASURED and rejected. Across <dataset>'s 13 copies of
`exclusion.no_evidence` the mean similarity to the rendered canon is 0,88, and chasing it higher made
things WORSE: reordering one clause to match `country` dropped `brand` from 0,93 to 0,77. The copies
disagree on clause ORDER and on label wording ("ActProd" vs "Units Produced") — differences that
carry no meaning. A gate on string similarity fires on rewording as loudly as on redefinition, which
is the exact defect canon binding exists to remove.

So this checks MEANING: every semantic element the author wrote must survive in the render.

    REFUSE · no-guess · no-zero-fill · substitution ban · the null branch · each named confusable

BOTH DIRECTIONS. The prose losing an element the canon renders is drift (the twin stopped saying what
governs it); the prose carrying one the canon cannot render is a missing parameter. The first cut
checked only the second, and a probe that stripped a confusable out of a delivery measure's `never`
passed clean.

Measured on the same 13: string fit 0,88, meaning preserved 13/13. That gap is the whole argument.

WHAT IT WOULD FALSELY FIRE ON, and a legitimate case that must not fire
----------------------------------------------------------------------
* A rule whose prose says MORE than its canon can render — e.g. an author adds a source-specific
  caveat. LEGITIMATE, and this check catches it deliberately: the canon then needs a parameter, or the
  binding is wrong. That is a finding, not noise. Three such gaps were found this way and closed with
  `via`, `ban_in_then` and `substitute_kind` rather than by weakening the check.
* Probe words appearing in unrelated prose. `substitut` in a `when` clause about substitute models
  would read as the substitution ban. Not observed on this corpus; the probes are deliberately narrow
  and each maps to a clause the canons actually emit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import mac_diag as D
import mac_project as P

# Each probe is a SET of spellings for one semantic element. A single literal was too narrow and
# produced a false positive on the first real run: a reach measure writes "substituting 0 for a
# null reach" where the canon renders "coercing ... to 0" — same ban, and `zero` matched neither.
_PROBES = [("REFUSE", ("refuse",)),
           ("no-guess", ("guess", "estimat")),
           ("no-zero-fill", ("zero", " 0 ", "to 0", "coerc")),
           ("substitution ban", ("substitut",)),
           ("null branch", ("null",))]


def _has(text: str, spellings) -> bool:
    return any(s in text for s in spellings)


def _flat(rule, keys=("when", "then", "never")) -> str:
    return " ".join(" ".join(str(rule.get(k) or "").split()) for k in keys).lower()


class VocabularyMalformed(RuntimeError):
    """The canon registry could not be read as declared. Never swallowed into an empty result."""


def _declared_canons() -> set[str]:
    """Every canon the VOCABULARY declares, as `mac.canon.<name>` — the authority on what exists.

    WHY THIS SPLIT MATTERS. Rendering fails for two completely different reasons and this gate used
    to report both as `MAC008 reference-unresolved`, which blames the bundle:

      * the udf names nothing — an author's typo, genuinely the bundle's defect, an ERROR;
      * the udf names a REAL canon that `tools/canon/rules.py` has no prose face for. The binding is
        valid, the canon is implemented in the runtime, and the gap is in the FRAMEWORK's renderer.

    MEASURED once the list-form walk above started seeing bindings: all 11 of contoso5's land in the
    second class. `canon.terms` declares 22 canons and `rules.py` renders 3, so eleven valid bindings
    were about to be reported as unresolved references to canons that demonstrably run. Telling an
    author their declaration is broken when the renderer is the thing missing sends them to rewrite
    working YAML.
    """
    import yaml
    f = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
    try:
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise VocabularyMalformed(f"{f.name} could not be parsed: {exc}") from exc
    return {f"mac.canon.{n}" for n in ((doc.get("canon") or {}).get("terms") or {})}


def _params_from() -> dict:
    """{canon: {param: dotted concept path}} — READ from the registry, never listed here.

    A MALFORMED REGISTRY IS NEWS, NOT AN EMPTY DICT. This read used to sit inside a bare
    `except Exception: return {}`, and that is not a conservative default -- it is the same result as
    a registry that declares no `params_from` at all, so the two are indistinguishable to every
    caller. MEASURED 2026-10-04: `canon.terms.ratio_select` was authored as a bare STRING where its
    twenty siblings are mappings, so `.get("params_from")` raised AttributeError at the seventeenth
    term. Three entries had already been collected -- refuse_measure_no_row, refuse_unresolvable_name
    and snapshot_collapse -- and the except discarded them. The attached-vs-declared parameter check
    was therefore DEAD FOR EVERY CANON IN THE ESTATE, silently, and the gate still printed a verdict.

    So a term whose body is not a mapping now RAISES and names itself. A reader that cannot read its
    own registry has verified nothing, which is the one thing it must not report as clean.
    """
    import yaml
    f = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
    try:
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise VocabularyMalformed(f"{f.name} could not be parsed: {exc}") from exc
    terms = (doc.get("canon") or {}).get("terms") or {}
    out = {}
    for name, m in terms.items():
        if m is not None and not isinstance(m, dict):
            raise VocabularyMalformed(
                f"canon.terms.{name} is a {type(m).__name__}, not a mapping. A canon term declares "
                f"`serves`, `needs_sqlglot` and `doc`; written as a bare string it carries none of "
                f"them, and nothing that asks the term a question can read it."
            )
        pf = (m or {}).get("params_from")
        if pf:
            out["mac.canon." + name] = pf
    return out


#: THE CANONICAL KEY IS NO LONGER A DOTTED PATH. It left `concept.identity.canonical_key` on
#: 2026-10-05 and is now the column carrying `identity: canonical`, which lives inside a LIST of
#: sources — `_dig` walks mappings and cannot reach it. Declared as this literal in the canon
#: registry's `params_from` and resolved here through the one helper that reads it. Without this the
#: dig returns None, `declared` is empty, and the gate stops reporting the restatement it exists to
#: catch: a quiet gate, not a passing one.
_CANONICAL_COLUMN = "concept.grounding.columns[identity=canonical]"


def _dig(doc: dict, dotted: str):
    if dotted == _CANONICAL_COLUMN:
        import mac_project as P
        return P.canonical_key(doc)
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def check_canon_binding(root) -> list:
    try:
        import yaml
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from canon import rules as CR
        import canon as CANON
    except Exception as exc:                                            # noqa: BLE001
        return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_canon_binding",
                             summary=f"the canon library could not be loaded, so bindings are "
                                     f"UNVERIFIED, not clean: {exc!r}")]
    unresolved, drifted, restated, contradicted = [], [], [], []
    #: A VALID BINDING THE FRAMEWORK CANNOT RENDER — the framework's gap, not the bundle's.
    unrenderable: list = []
    #: A CLAUSE BESIDE A BODY — the second home STATE-AS-PROSE forbids.
    prose_beside: list = []
    declared_canons = _declared_canons()
    PF = _params_from()
    files = P.concept_files(root)
    # ZERO IS NOT A SCORE — a run that found no concept has verified no binding.
    if not files:
        return [D.empty_denominator("MAC008", "check_canon_binding", P.concepts_dir(root))]
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane
    # the project declares (mac_project.concept_files). Globbing `ontology/concepts/*.yaml` by hand
    # measured ZERO on every foldered bundle and printed a clean verdict.
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        for r in ((doc.get("contract") or {}).get("rules") or []):
            #: WALK A LIST BINDING. `canonBinding` is `oneOf [canonRef, array of canonRef]` and
            #: every population/ratio/column rule authored so far uses the ARRAY form, so this
            #: loop read `isinstance(rb, dict)` and skipped 11 of 11 contoso5 bindings in silence —
            #: the gate printed "no findings" over a population of ZERO, which is the one thing
            #: `D.empty_denominator` exists to prevent, routed around by a type check. The slot
            #: loop below has always handled both spellings; this is the same idiom.
            #:
            #: OWED BY NAME. guardrails/ontology/concepts.yaml#STATE-AS-PROSE cites this line and
            #: says what is owed: "walk a list binding, and REFUSE a `when`/`then`/`never` sitting
            #: beside a body." This is the first half.
            raw_rb = r.get("realized_by")
            for rb in ([raw_rb] if isinstance(raw_rb, dict) else (raw_rb or [])):
                if not isinstance(rb, dict) or not rb.get("udf"):
                    continue
                rel = P.rel(root, f)
                # A PARAMETER THAT HAS A DECLARED HOME MUST NOT BE ATTACHED. If it agrees with the
                # declaration it is a restatement; if it disagrees, the binding and the concept are
                # saying different things and the binding is the one that RUNS. Measured: two <dataset>
                # bindings attached `code` and both disagreed with identity.canonical_key.
                for prm, path in (PF.get(rb.get("udf")) or {}).items():
                    if prm not in (rb.get("params") or {}):
                        continue
                    attached = str((rb["params"] or {}).get(prm) or "").strip()
                    declared = str(_dig(doc, path) or "").strip()
                    if declared and attached and attached.lower() != declared.lower():
                        contradicted.append(D.Witness(
                            file=rel, path=str(r.get("id")),
                            detail=f"{prm}={attached!r} but {path}={declared!r}"))
                    elif declared:
                        restated.append(D.Witness(
                            file=rel, path=str(r.get("id")),
                            detail=f"{prm} repeats {path} ({declared!r}) — read it, do not attach it"))
                #: THE SECOND HALF OF WHAT STATE-AS-PROSE ASKS FOR, verbatim: "REFUSE a
                #: `when`/`then`/`never` sitting beside a body." Operator ruling, 2026-10-01: "i
                #: believe there is no reason anymore for when then never". Prose beside a body is a
                #: second home for one fact and the prose home is the one that rots — measured on the
                #: rule this mechanism was built for, whose `never` was true when written and FALSE
                #: hours later after an impurity fix, corrected only because a person re-read it. No
                #: gate caught it, because there is nothing in prose to catch.
                #:
                #: A WARNING, NOT YET AN ERROR, and the reason is measured: 9 of contoso5's 20 rules
                #: carry NO body, so their prose IS the rule and deleting it deletes the rule. Five of
                #: those need a canon that does not exist yet. The ratchet closes BEHIND the migration
                #: — this flips to ERROR when the last bodyless rule is bound, not before, or it
                #: demands work that is not yet possible and gets declared standing instead of done.
                beside = [k for k in ("when", "then", "never") if str(r.get(k) or "").strip()]
                if beside:
                    prose_beside.append(D.Witness(
                        file=rel, path=str(r.get("id")),
                        detail=f"carries {', '.join(beside)} beside {rb.get('udf')}"))
                try:
                    out = CR.render(rb["udf"], rb.get("params") or {}, concept=doc)
                except Exception as exc:                                    # noqa: BLE001
                    #: WHICH LIST depends on whether the canon EXISTS. See _declared_canons.
                    bucket = (unrenderable if str(rb.get("udf")) in declared_canons
                              else unresolved)
                    bucket.append(D.Witness(file=rel, path=r.get("id", ""),
                                            detail=f'{rb.get("udf")} — {str(exc)[:100]}'))
                    continue
                authored, rendered = _flat(r), _flat(out)
                # NOTHING WRITTEN, NOTHING TO DRIFT. A bound rule may omit when/then/never entirely —
                # the schema permits it precisely because the canon renders them — and then there is no
                # second home and no comparison to make. Reporting "prose lacks REFUSE" for a rule that
                # deliberately carries no prose inverts the check: it would push authors back toward the
                # hand-written copies this whole mechanism exists to remove.
                if not authored.strip():
                    continue
                # SYMMETRIC, and it took a failed probe to notice. The first cut only asked "does the
                # render lose something the author wrote", which misses the direction that matters more:
                # PROSE DRIFTING AWAY FROM ITS CANON. Stripping `Market Size` and the substitution
                # ban out of a delivery measure's `never` passed cleanly, because the element was then
                # absent from BOTH sides. A one-directional check on a two-directional relationship
                # reports the half it was built to see.
                miss = [f"render lacks {label}" for label, sp in _PROBES
                        if _has(authored, sp) and not _has(rendered, sp)]
                miss += [f"prose lacks {label}" for label, sp in _PROBES
                         if _has(rendered, sp) and not _has(authored, sp)]
                miss += [f"prose no longer names {c}" for c in (rb.get("params", {}).get("confusable") or [])
                         if str(c).lower() not in authored]
                if miss:
                    drifted.append(D.Witness(file=rel, path=r.get("id", ""),
                                             detail="; ".join(map(str, miss))))

        # ── SLOT bindings, which nothing walked until 2026-08-19 ──────────────────────────────────
        # `realized_by` is legal on a behaviour-bearing SLOT too — grounding (a snapshot_rule, a
        # value_filter) and semantics (an additivity guard) — not only on a rule. This loop read
        # contract.rules[] alone, so a slot binding was checked by nothing at all.
        #
        # MEASURED, and it is why this exists: an <dataset> binding of mac.canon.snapshot_collapse passed a
        # FOUR-column partition where the relation's verified cell key is SEVEN, and rendered
        # `PARTITION BY ['<source>_scoped_market_code', ...]` — a Python list repr, not SQL. It shipped, and
        # the compile reported clean, because no phase rendered it. Omitting `role` from that partition
        # folds six reporting perspectives into one arbitrary row, silently.
        for slot in ("grounding", "semantics"):
            holder = doc.get(slot) if slot == "grounding" else (doc.get("concept") or {}).get(slot)
            rb = (holder or {}).get("realized_by") if isinstance(holder, dict) else None
            for b in ([rb] if isinstance(rb, dict) else (rb or [])):
                if not isinstance(b, dict) or not b.get("udf"):
                    continue
                rel = str(f.relative_to(root))
                try:
                    CANON.render_sql(b["udf"], b.get("params") or {}, concept=doc, root=root)
                except Exception as exc:                                # noqa: BLE001
                    unresolved.append(D.Witness(file=rel, path=f"{slot}.realized_by",
                                                detail=f"{b['udf']}: {str(exc)[:130]}"))
                for prm, path in (PF.get(b.get("udf")) or {}).items():
                    if prm in (b.get("params") or {}):
                        restated.append(D.Witness(
                            file=rel, path=f"{slot}.realized_by",
                            detail=f"{prm} is attached but declared at {path} — read it, do not retype it"))
    out = []
    if unresolved:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.ERROR, source="check_canon_binding",
            summary=f"{len(unresolved)} rule(s) name a canon THIS VOCABULARY DOES NOT DECLARE",
            note="an unknown udf, or a parameter the canon's signature does not accept",
            witnesses=unresolved))
    if prose_beside:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.WARNING, source="check_canon_binding",
            summary=(f"{len(prose_beside)} bound rule(s) keep a when/then/never BESIDE the body — "
                     f"guardrails/ontology/concepts.yaml#STATE-AS-PROSE"),
            note=("the body decides; the clause is a second home that cannot be checked and will "
                  "rot. Drop when/then/never and keep `why:`. ERROR once no bodyless rule is left"),
            witnesses=prose_beside))
    if unrenderable:
        #: A WARNING, AND IT NAMES ITS OWN DENOMINATOR. Every witness here is a VALID binding to a
        #: canon that exists and runs; what is missing is a prose face in tools/canon/rules.py, which
        #: covers 3 of the 22 canons the vocabulary declares. So the by-meaning comparison this gate
        #: performs is simply unavailable for them — not failed, unavailable. Reporting that as an
        #: ERROR would tell an author to rewrite working YAML to fix a gap in the framework.
        #:
        #: It is a WARNING rather than silence because the denominator is the point: before the
        #: list-form walk this gate printed "no findings" over a population of zero, and the honest
        #: replacement for a false PASS is a stated gap, not a quieter one.
        renderable = len(CR.CANONS) if hasattr(CR, "CANONS") else 3
        out.append(D.Diagnostic(
            code="MAC008", severity=D.WARNING, source="check_canon_binding",
            summary=(f"{len(unrenderable)} valid binding(s) cannot be held against their canon: "
                     f"no prose renderer ({renderable} of {len(declared_canons)} canons render)"),
            note=("the canon exists and runs; tools/canon/rules.py has no prose face for it, so the "
                  "by-meaning check is unavailable for these rules rather than failing"),
            witnesses=unrenderable))
    if contradicted:
        out.append(D.Diagnostic(
            code="MAC004", severity=D.ERROR, source="check_canon_binding",
            summary=f"{len(contradicted)} canon parameter(s) contradict the declaration they are "
                    f"readable from",
            note="The binding is the one that RUNS, so a disagreement here is a wrong answer waiting. "
                 "Delete the parameter — the canon reads it from the concept.",
            witnesses=contradicted))
    if restated:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_canon_binding",
            summary=f"{len(restated)} canon parameter(s) repeat a fact the concept already declares",
            note="Agreeing today is not a defence — nothing keeps the two in step. "
                 "mac_vocabulary.yaml#canon.terms[].params_from names where each is read from.",
            witnesses=restated))
    if drifted:
        out.append(D.Diagnostic(
            code="MAC004", severity=D.ERROR, source="check_canon_binding",
            summary=f"{len(drifted)} bound rule(s) say something their canon does not render",
            note="The prose and the binding disagree about the rule. Either the canon needs a "
                 "parameter to carry what the author wrote — three were added this way — or the "
                 "binding is wrong. Do not weaken the prose to match a canon that cannot say it.",
            witnesses=drifted))
    return out


def main() -> int:                                                      # pragma: no cover
    if "--self-test" in sys.argv[1:]:
        return P.selftest_discovery(__file__)
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_canon_binding(root)
    print(D.render(d, root, show=D.INFO) or "check_canon_binding: no findings")
    if any(D.UNKNOWN_MARK in x.summary for x in d):
        return D.EMPTY_EXIT
    return 1 if any(x.severity == D.ERROR for x in d) else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
