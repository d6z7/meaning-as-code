#!/usr/bin/env python3
"""mac_diagnostics — the compiler's findings, as data.

ONE IMPLEMENTATION, TWO RENDERERS. `check_single_source.py` prints these to a terminal; the wiki
projector serialises the same objects to JSON for the dashboard. Writing the analysis twice would
duplicate a fact in the very tool whose job is to find duplicated facts.

A finding is addressable. That is the whole point of a compiler diagnostic and the thing a prose
report cannot do: every one carries the exact sites — file, yaml path, line where known — so a reader
goes straight to the place rather than searching for it.

SEVERITY, and why "restated but agreeing" is not an error:
  error  — the statements DISAGREE. Something downstream is already reading the wrong one.
  warn   — the fact is written down more than once and the copies happen to agree. Nothing is wrong
           today and nothing keeps them in step; this is the state IdealStock was in before it drifted.
"""
from __future__ import annotations

from pathlib import Path

import mac_model as M

SCHEMA = "mac.diagnostics/1"


def _site(s) -> dict:
    return {"file": s.site.file, "path": s.site.path, "line": s.site.line, "value": s.value}


def diagnose(bundle) -> list[dict]:
    """Every finding the semantic phase can currently make. Ordered: errors first, then by subject."""
    out: list[dict] = []
    for f in bundle.facts("measure.additivity"):
        if len(f.statements) < 2:
            continue                      # stated once = it has a home; nothing to say
        subject, axis = f.key
        agrees = f.agrees()
        out.append({
            "code": "single-source/restated" if agrees else "single-source/contradiction",
            "severity": "warn" if agrees else "error",
            "family": "measure.additivity",
            "subject": subject,
            "axis": axis,
            "values": list(f.normalized),
            "message": (
                f"{subject}.{axis} is stated in {len(f.statements)} places and they agree "
                f"({f.normalized[0]}) — nothing keeps them in step"
                if agrees else
                f"{subject}.{axis} is stated in {len(f.statements)} places and they DISAGREE: "
                f"{' vs '.join(f.normalized)}"),
            "sites": [_site(s) for s in f.statements],
        })
    out.sort(key=lambda d: (d["severity"] != "error", d["subject"], d["axis"]))
    return out


def build(root) -> dict:
    """The dashboard document. Generated during projection, so it cannot go stale."""
    b = M.load(Path(root))
    facts = b.facts("measure.additivity")
    findings = diagnose(b)
    errors = [d for d in findings if d["severity"] == "error"]
    warns = [d for d in findings if d["severity"] == "warn"]

    by_file: dict[str, int] = {}
    for d in findings:
        for s in d["sites"]:
            by_file[s["file"]] = by_file.get(s["file"], 0) + 1

    return {
        "schema": SCHEMA,
        # The bundle's NAME, never its path. `str(root)` is an ABSOLUTE path on whoever ran the
        # projection, and this artifact is committed — it shipped an author's home directory into a
        # public example bundle. The name is the identity a reader needs; the path is theirs, not the
        # bundle's.
        "bundle": Path(root).name,
        "phase": "semantic",
        "stats": {
            # AN EMPTY FAMILY IS A RESULT, NOT A BLANK. This module compares the STATEMENTS of one
            # fact family (measure.additivity); a fact needs >= 2 of them to be comparable, and a
            # value the framework DERIVES is excluded by construction. So when every measure has
            # stopped writing `semantics.additivity` — the outcome this check exists to produce —
            # the family is empty and every counter is legitimately 0.
            #
            # Reported bare, that is indistinguishable from "the check did not run", and a reader
            # seeing five zeros reasonably concludes the page is broken. It happened on <domain>/<dataset> the
            # day the last authored additivity block was removed. `note` states the denominator so a
            # zero can be read as the success it is.
            "facts": len(facts),
            "restated": len(findings),
            "single_homed": len(facts) - len(findings),
            "errors": len(errors),
            "warnings": len(warns),
        },
        # WHY THIS NUMBER IS THE HEADLINE: every restated fact here is DERIVABLE — the framework canon
        # already determines it from the concept's own measure_type and axis_kind. The concepts write
        # it down again because mac_shapes.yaml#measure-declares-additivity REQUIRES them to. So the
        # framework mandates copies of a fact it can compute, and some have already drifted.
        "note": ("no measure writes `semantics.additivity`, so there is nothing stated twice to "
                 "compare — the family is empty because the restatement this check looks for has "
                 "been ELIMINATED, not because the check did not run"
                 if not facts else
                 f"{len(findings)} of {len(facts)} additivity fact(s) are stated in more than one home"),
        "derivable_but_restated": len(findings),
        "by_file": [{"file": k, "statements": v}
                    for k, v in sorted(by_file.items(), key=lambda kv: -kv[1])],
        "findings": findings,
    }
