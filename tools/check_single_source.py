#!/usr/bin/env python3
"""check_single_source — one fact, one home. The first SEMANTIC gate.

WHY THIS IS NOT ANOTHER SYNTAX CHECK
------------------------------------
Every other gate in this toolchain answers a question about ONE document: is the field present, is the
value in the enum, does the referenced name exist. That is syntax, and it is structurally blind to the
defect class that has cost the most: **the same fact asserted in two places, disagreeing.**

The motivating case, measured on a live bundle. A measure concept declares

    concept.semantics.additivity: {geography: additive, model: additive}   # authored

while the framework canon derives, from that concept's own declared measure_type and axis_kinds,

    MeasureType.Target.additivity.categorical: non_aggregable               # the law

Both statements are individually well-formed, so `validate_schema` passes, `check_shapes` passes, and
`check_measure_additivity_registry` prints OK — it validates registry ROWS, not the concepts against
them. The contradiction survived into `acceptance/anchors/`, where a ground-truth anchor summed a
non-aggregable measure across model and cited the registry as its justification.

A per-file validator cannot see this no matter how many rules it grows. It needs a model that holds
every statement of one fact at once, with provenance on each — which is what `mac_model.Fact` is.

WHAT IS CHECKED
  ERROR — a fact whose statements DISAGREE. It has already produced a wrong answer somewhere.
  WARN  — a fact stated more than once and AGREEING. Not wrong today; it is how tomorrow's
          disagreement gets made, because nothing keeps the copies in step.

WHY THE NAIVE VERSION IS WRONG, AND WHY THIS ONE IS NARROW
A first cut of this check fired NINE times on the same bundle where ONE defect exists. Eight were the
`variant` axis — declared non-additive and typed categorical, so the law appears to rule on it — but
`variant` selects WHICH measure is being read (actual / plan / budget); it is not an axis the measure
is aggregated over. The model classifies it `role='measure_selector'` and the law does not apply.
A gate that fires 9 times where 1 is real teaches its readers to ignore it, and that is worse than no
gate at all. Every exclusion here is of that kind: narrow, named, and justified — never a threshold.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import mac_model as M
    import mac_diagnostics as D
except ImportError as e:  # pragma: no cover
    sys.exit(f"check_single_source requires tools/mac_model.py + mac_diagnostics.py: {e}")


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_single_source.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    b = M.load(root)
    facts = b.facts("measure.additivity")
    findings = D.diagnose(b)
    conflicts = [d for d in findings if d["severity"] == "error"]
    drifting = [d for d in findings if d["severity"] == "warn"]
    restated = findings

    print(f"── single-source gate ── {len(facts)} fact(s), {len(restated)} stated more than once, "
          f"{len(conflicts)} contradicting under {root} ──\n")

    for d in drifting + conflicts:
        tag = "ERROR" if d["severity"] == "error" else "WARN "
        print(f"  [{tag}] {d['message']}")
        for s in d["sites"]:
            where = f"{s['file']}#{s['path']}" + (f":{s['line']}" if s.get("line") else "")
            print(f"            {s['value']}  <- {where}")

    home = {}
    for d in restated:
        for s in d["sites"]:
            home[s["file"]] = home.get(s["file"], 0) + 1
    if home:
        print("\n  where the restatements live:")
        for fname, n in sorted(home.items(), key=lambda kv: -kv[1]):
            print(f"    {M.de(n):>4}  {fname}")

    if conflicts:
        print(f"\n✗ {len(conflicts)} contradiction(s) — one fact, two answers, and no gate below this "
              f"one can see it ({len(drifting)} agreeing restatement(s) also reported)")
        return 1
    print(f"\n✓ OK — no fact contradicts itself ({len(drifting)} agreeing restatement(s) reported: "
          f"each is a copy that nothing keeps in step)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
