---
when: 2026-09-13T08:00:45
what: ran the suite in a fresh-clone shape and found two gates that were right on this machine and wrong everywhere else
topics: [gates, denominators, harness]
kind: defect
track: core
repo: meaning-as-code
commits: [cadb2bd]
---

## WHAT FORCED IT

Found by running the suite in a FRESH-CLONE shape — no registers, no framework installed, no
environment — **which is the shape every defect in this consolidation actually lived in.** Two gates
were wrong there and right on this machine, which is precisely the failure mode that let the vendored
fork govern.

## EVIDENCE

`git show -s cadb2bd` (meaning-as-code):

> `check_bundle_secrets` invoked bare (no root), it reached `Path(None)` and died with a TypeError. A
> traceback is not a verdict: a runner reading exit codes cannot tell a crash from a refusal. It now
> reports could-not-run and exits 2.

> `check_source_coupling` with no token register it printed a tick and a NOTE underneath saying the
> token class had examined nothing. A note is not a refusal — a runner grepping PASS/FAIL reads it as
> green. It now exits 2. This gate lost its subject once before and reported a tick; that is the
> whole reason the could-not-run path exists.

```
pytest sdk (fresh-clone env)   88 passed
SDK gate self-tests             9 / 9
bare check_bundle_secrets      exit 2   (was: TypeError)
check_source_coupling, no reg  exit 2   (was: exit 0, green)
run_framework_gates  tpch      30 / 34, 13s   (baseline — unchanged)
run_framework_gates  shop      30 / 34, 13s   (baseline — unchanged)
```

The suite itself IS hermetic: 88 passed with every register pointed at `/nonexistent` and every
framework environment variable unset.

## WHAT CHANGED

Two files, +17 lines. Both gates gained a could-not-run path for the condition that used to read as
green.

## WHAT IT DOES NOT PROVE

Two gates were tested in that shape, not all of them. "The suite is hermetic" is a property of the
88 tests that exist, and the fresh-clone environment was simulated by unsetting variables and
repointing registers — not by cloning into an empty machine. The class this finds is exactly the
class nobody can find from the machine the work was done on, which is the argument for testing it
this way and the reason a simulation is not the same as the real thing.
