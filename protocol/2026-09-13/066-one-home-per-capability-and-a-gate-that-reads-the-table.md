---
when: 2026-09-13T13:40:00
what: declared the single home of each capability in a table a gate can read, and the gate found three of my own violations on its first run
topics: [method, harness, topology, denominators]
kind: build
track: core
repo: meaning-as-code
commits: [c0782f9]
---

## WHAT FORCED IT

The operator's words, and they are a correction of how I had been working: **"this can from my
perspective better be solved with topology diagram. eg. where exactly is the home of specific
functionality. i never seen you doing this."**

The context was my own finding that all fourteen of that day's defects lived at SEAMS — two
declarations of one fact with nothing reading both. I had proposed more testing. The operator's
reading is that a seam is a *topology* defect: if a fact has one home, there is no second
declaration to disagree with it. Testing finds the disagreement afterwards; single-homing prevents
it existing.

## EVIDENCE

`git show -s c0782f9`. The table is `| capability | THE home | and nowhere else |`, and the gate
`tools/check_topology.py` reads that table and asserts no capability's marker appears outside its
declared home. It is not prose about structure; it is the structure, parsed.

**THREE OF MY OWN BUGS, FOUND BY RUNNING IT — the first run was not green:**

The sharpest was `grammar-resolution`. My marker was `def schema_path`, which matched a second,
unrelated function that merely locates a file. The fix was to pin the POLICY, not the name:

    "grammar-resolution": ("sdk/grammar/", r'os\.environ\.get\("MAC_SCHEMA"\)', ...)

And the gate then proved the divergence was real, not theoretical, under `$MAC_SCHEMA`:

    meaning_as_code.schema_path() -> <the repo's own mac.schema.json>
    resolve.schema_path()         -> /tmp/other-schema.json
    DISAGREE — two answers to "which grammar governs"

Two answers to which grammar governs is the worst possible seam in a system whose whole claim is
that meaning is declared once.

## WHAT CHANGED

`TOPOLOGY.md` states BUILD TIME (meaning-as-code + mac-sdk), ANSWER TIME (mac-runtime) and THE SEAM
(`sdk/connector/`), and records the open question it exposed rather than hiding it:
`GroundingAdapter.execute` and `Connector.read` are **the same capability with two homes**. Homes
resolve across the estate (`ROOT` then `ROOT.parent`); per-bundle homes (`connection.yaml`,
`mac.project.yaml`, `registers/`) are counted as NOT-PATH-CHECKABLE and never silently dropped —
dropping them would be a zero-denominator pass over exactly the facts hardest to place.

## WHAT IT DOES NOT PROVE

The gate checks that a marker does not appear outside its declared home. It does **not** prove the
declared home is the right one, and it cannot see a capability nobody wrote a row for — the table is
authored, so the table can be incomplete and the gate will still be green. Self-test 6/6 attests the
gate rejects, not that the topology is correct.
