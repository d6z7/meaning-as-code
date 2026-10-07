#!/usr/bin/env python3
"""mac_checks_referential.py — THE BUNDLE DOES NOT COMPILE WITH REFERENTIAL INTEGRITY BROKEN.

WHY THIS EXISTS, and it is the operator's words: "i want you to make referential integrity the traffic
lite of the system ... IT JUST DOES NOT COMPILE WITH REFERENTIAL INTEGRITY BROKEN AND YOU SHOULD REFUSE
TO EXECUTE."

WHAT WAS ALREADY THERE, so that nothing here is reinvented. The estate has ONE referential framework
and it works: `mac_pointers.yaml` (mac.pointers/1) is the catalogue of what may point at what, 37
pointer kinds over 17 object kinds; `tools/mac_pointers.py` is the one resolver, moved into this
repository on 2026-10-04 for exactly this reason — "the dependency runs platform -> framework, so a MAC
gate could not import a resolver living in the platform"; `mac-platform/tools/check_pointers.py` is its
aggregate CLI; `estate_graph.py build|verify|impact` persists the graph and answers "if I drop X, what
breaks" off a materialized transitive closure.

WHAT WAS MISSING WAS THE REFUSAL. `mac_compile.py` had eight phases — structure, semantic, adoption,
reproduction, vocabulary, canon_binding, common_rules, cookbook, reference_basis, answerability,
selfconform — and NOT ONE of them resolved a pointer. So a bundle whose references were broken
COMPILED, and the only thing standing between a dangling pointer and a published artifact was somebody
remembering to run a gate in another repository. Measured 2026-10-07: nobody remembered for a whole
session of edits, the estate graph drifted 8 of its 11 tables unnoticed, and three rules and four canon
terms were deleted without once asking the closure what pointed at them.

MAC008 IS NOT A NEW CODE. The taxonomy has always had it — "a reference that resolves to nothing" —
and five phases already declare ownership of it for their own narrower questions. This phase is the one
that asks it of the CATALOGUE, which is the only place the question is asked in general.

SEVERITY IS THE WHOLE POINT. A dangling pointer whose kind the catalogue marks `required: true` is an
ERROR, and an error fails the compile, and `sdk.cli.harvest --mode project` already refuses to publish a
bundle that does not compile. That is the chain the operator asked for: integrity breaks -> it does not
compile -> nothing downstream runs.

A DANGLING POINTER IN A GENERATED FILE IS NOT AN AUTHORED MISTAKE. `Ref.producer` carries the tool that
wrote the carrier, read from the file's own declaration, and the fix there is to re-run that producer
rather than to edit the artifact. Those are reported at WARNING with the producer named, because
blaming an author for a stale projection sends the fix to the wrong place — the lesson `check_canon_
binding` records in its own words about MAC008.
"""
from __future__ import annotations

import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
FRAMEWORK = _HERE.parent.parent
sys.path.insert(0, str(_HERE.parent))

#: LOCATE THE FRAMEWORK FROM THIS FILE'S OWN POSITION, BEFORE the resolver is imported. `mac_pointers`
#: resolves the catalogue through `MEANING_AS_CODE` or an importable `meaning_as_code`, because its other
#: callers live in the platform and must find a framework beside them — and it binds that default at
#: import time, inside `resolve()` as well as at the top. From here the framework is this file's own
#: grandparent and there is nothing to search for: asking the environment would let an unset or
#: mispointed variable decide which registry the compile gate judges against, which is a silent change
#: of subject rather than a missing file. `setdefault`, so an operator who HAS set it still wins.
os.environ.setdefault("MEANING_AS_CODE", str(FRAMEWORK))

import mac_diag as D  # noqa: E402
import mac_pointers as MP  # noqa: E402

SOURCE = "mac_checks_referential"

CATALOGUE = FRAMEWORK / "mac_pointers.yaml"


def _is_authored(ref) -> bool:
    """Whether a dangling pointer is an AUTHORED mistake rather than a stale copy.

    `Ref.producer` is read from the carrier's own `generated_by`, and a file is entitled to say its
    producer WAS a person. MEASURED 2026-10-07 on contoso5: `ontology/edges.yaml` declares
    `generated_by: "authored, from data/references_served/*.yaml (measured cardinality)"` — a true and
    useful sentence that names the method, not a tool. Treating any non-empty producer as "generated"
    filed a broken `resolved_by` anchor in the most hand-written file in the bundle as a stale
    projection to be re-derived, at WARNING, which would have told an author to re-run nothing and let
    the compile pass. A producer that says it is authored is an author.
    """
    producer = (getattr(ref, "producer", None) or "").strip().lower()
    return not producer or producer.startswith("authored") or producer.startswith("hand")


def check_referential(root: str | pathlib.Path) -> list:
    """Every pointer the catalogue declares, resolved. Dangling + required = MAC008 ERROR."""
    bundle = pathlib.Path(root).resolve()
    kinds = MP.load_registry(CATALOGUE)
    idx = MP.resolve(bundle, kinds)

    required = {n for n, k in kinds.items() if k.get("required")}
    dangling = [r for r in idx.refs if r.resolution == "dangling"]
    if not idx.refs:
        # A PASS OVER ZERO POINTERS IS THE FALSE GREEN THIS ESTATE MEASURES FOR.
        return [D.empty_denominator("MAC008", SOURCE, bundle, unit="pointer")]

    out: list = []
    authored = [r for r in dangling if _is_authored(r)]
    generated = [r for r in dangling if not _is_authored(r)]

    hard = [r for r in authored if r.reference_kind in required]
    soft = [r for r in authored if r.reference_kind not in required]

    def _w(rs: list) -> list:
        return [D.Witness(file=r.src_path, path=r.src_locator,
                          detail=f"{r.reference_kind} -> {r.raw_value!r} resolves to nothing")
                for r in rs]

    if hard:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.ERROR, source=SOURCE,
            summary=(f"{len(hard)} of {len(idx.refs)} declared pointer(s) resolve to nothing, and the "
                     f"catalogue marks their kind REQUIRED — the bundle is not internally whole"),
            witnesses=_w(hard),
            note=("mac_pointers.yaml declares each of these kinds `required: true`, which means a value "
                  "is mandatory AND must resolve. Fix the pointer or retire the declaration that "
                  "carries it; `estate_graph.py impact <object-id>` says what else would move with it."),
        ))
    if soft:
        out.append(D.Diagnostic(
            code="MAC008", severity=D.WARNING, source=SOURCE,
            summary=(f"{len(soft)} of {len(idx.refs)} declared pointer(s) resolve to nothing on a kind "
                     f"the catalogue does not mark required"),
            witnesses=_w(soft),
            note="optional by the catalogue, so it does not fail the compile — but it points nowhere.",
        ))
    if generated:
        by_producer: dict[str, list] = {}
        for r in generated:
            by_producer.setdefault(r.producer or "?", []).append(r)
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source=SOURCE,
            summary=(f"{len(generated)} dangling pointer(s) sit in GENERATED artifact(s) — the copy is "
                     f"out of step with what it was derived from, not an authored mistake"),
            witnesses=_w(generated),
            note=("re-run the producer: " + ", ".join(sorted(by_producer)) +
                  ". MAC003 rather than MAC008 because the reference was right when it was written and "
                  "the artifact is stale; editing the artifact would fix the symptom in the copy."),
        ))
    return out
