#!/usr/bin/env python3
"""check_canon_binding — a bound rule's prose must still say what its canon renders.

WHY THIS SHAPE, and not the obvious one
---------------------------------------
`realized_by` names the canon that governs a rule. The v0.1.9 contract keeps the authored prose
BESIDE it as the human twin, which raises the question this check answers: what stops the twin
drifting from the canon it claims to be governed by?

The obvious check — compare the strings — was MEASURED and rejected. Across fpl2's 13 copies of
`exclusion.no_evidence` the mean similarity to the rendered canon is 0,88, and chasing it higher made
things WORSE: reordering one clause to match `country` dropped `brand` from 0,93 to 0,77. The copies
disagree on clause ORDER and on label wording ("IstProd" vs "Actual Production") — differences that
carry no meaning. A gate on string similarity fires on rewording as loudly as on redefinition, which
is the exact defect canon binding exists to remove.

So this checks MEANING: every semantic element the author wrote must survive in the render.

    REFUSE · no-guess · no-zero-fill · substitution ban · the null branch · each named confusable

BOTH DIRECTIONS. The prose losing an element the canon renders is drift (the twin stopped saying what
governs it); the prose carrying one the canon cannot render is a missing parameter. The first cut
checked only the second, and a probe that stripped a confusable out of dtc's `never` passed clean.

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

# Each probe is a SET of spellings for one semantic element. A single literal was too narrow and
# produced a false positive on the first real run: ob_reach writes "substituting 0 for a null
# ob_reach" where the canon renders "coercing ... to 0" — same ban, and `zero` matched neither.
_PROBES = [("REFUSE", ("refuse",)),
           ("no-guess", ("guess", "estimat")),
           ("no-zero-fill", ("zero", " 0 ", "to 0", "coerc")),
           ("substitution ban", ("substitut",)),
           ("null branch", ("null",))]


def _has(text: str, spellings) -> bool:
    return any(s in text for s in spellings)


def _flat(rule, keys=("when", "then", "never")) -> str:
    return " ".join(" ".join(str(rule.get(k) or "").split()) for k in keys).lower()


def check_canon_binding(root) -> list:
    try:
        import yaml
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from canon import rules as CR
    except Exception as exc:                                            # noqa: BLE001
        return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_canon_binding",
                             summary=f"the canon library could not be loaded, so bindings are "
                                     f"UNVERIFIED, not clean: {exc!r}")]
    unresolved, drifted = [], []
    for f in sorted((Path(root) / "ontology" / "concepts").glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        for r in ((doc.get("contract") or {}).get("rules") or []):
            rb = r.get("realized_by")
            if not isinstance(rb, dict) or not rb.get("udf"):
                continue
            rel = str(f.relative_to(root))
            try:
                out = CR.render(rb["udf"], rb.get("params") or {})
            except Exception as exc:                                    # noqa: BLE001
                unresolved.append(D.Witness(file=rel, path=r.get("id", ""), detail=str(exc)[:140]))
                continue
            authored, rendered = _flat(r), _flat(out)
            # SYMMETRIC, and it took a failed probe to notice. The first cut only asked "does the
            # render lose something the author wrote", which misses the direction that matters more:
            # PROSE DRIFTING AWAY FROM ITS CANON. Stripping `Total Market` and the substitution ban
            # out of dtc's `never` passed cleanly, because the element was then absent from BOTH
            # sides. A one-directional check on a two-directional relationship reports the half it
            # was built to see.
            miss = [f"render lacks {label}" for label, sp in _PROBES
                    if _has(authored, sp) and not _has(rendered, sp)]
            miss += [f"prose lacks {label}" for label, sp in _PROBES
                     if _has(rendered, sp) and not _has(authored, sp)]
            miss += [f"prose no longer names {c}" for c in (rb.get("params", {}).get("confusable") or [])
                     if str(c).lower() not in authored]
            if miss:
                drifted.append(D.Witness(file=rel, path=r.get("id", ""),
                                         detail="; ".join(map(str, miss))))
    out = []
    if unresolved:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.ERROR, source="check_canon_binding",
            summary=f"{len(unresolved)} rule(s) name a canon that cannot be rendered",
            note="an unknown udf, or a parameter the canon's signature does not accept",
            witnesses=unresolved))
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
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_canon_binding(root)
    print(D.render(d, root, show=D.INFO) or "check_canon_binding: no findings")
    return 1 if any(x.severity == D.ERROR for x in d) else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
