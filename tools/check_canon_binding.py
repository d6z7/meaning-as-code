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
disagree on clause ORDER and on label wording ("IstProd" vs "Actual Production") — differences that
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


def _params_from() -> dict:
    """{canon: {param: dotted concept path}} — READ from the registry, never listed here."""
    try:
        import yaml
        f = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
        out = {}
        for name, m in ((yaml.safe_load(f.read_text(encoding="utf-8")) or {})
                        .get("canon", {}).get("members", {}) or {}).items():
            pf = (m or {}).get("params_from")
            if pf:
                out["mac.canon." + name] = pf
        return out
    except Exception:                                                   # noqa: BLE001
        return {}


def _dig(doc: dict, dotted: str):
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
            rb = r.get("realized_by")
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
            try:
                out = CR.render(rb["udf"], rb.get("params") or {}, concept=doc)
            except Exception as exc:                                    # noqa: BLE001
                unresolved.append(D.Witness(file=rel, path=r.get("id", ""), detail=str(exc)[:140]))
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
            # PROSE DRIFTING AWAY FROM ITS CANON. Stripping `Total Market` and the substitution
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
        # `PARTITION BY ['<source>_brand_country_code', ...]` — a Python list repr, not SQL. It shipped, and
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
            summary=f"{len(unresolved)} rule(s) name a canon that cannot be rendered",
            note="an unknown udf, or a parameter the canon's signature does not accept",
            witnesses=unresolved))
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
                 "mac_vocabulary.yaml#canon.members[].params_from names where each is read from.",
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
