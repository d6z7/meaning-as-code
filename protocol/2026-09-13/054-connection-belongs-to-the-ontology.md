---
when: 2026-09-13T01:26:33
what: removed one estate's connection defaults from the tooling, because connection and identity are facts about the bundle being served and a module-level default cannot be bundle-aware
topics: [connectors, registers, the-public-boundary, containers]
kind: defect
track: ontology
repo: meaning-as-code
commits: [93ca8a6]
---

## WHAT FORCED IT

The previous commit neutralised the VALUES of some infra handles in the SDK. That was the wrong fix:
it laundered the strings and left the defect.

Connection details are a fact about the BUNDLE being served — `connection.yaml` says how to reach the
warehouse, the project manifest says what the source is called — and the SDK reads them per bundle.
**A module-level default cannot be bundle-aware by construction**, so every one of these was one
ontology's configuration compiled into the tooling that serves all of them, reachable by any caller
that passed nothing.

This is the entry the connector architecture is built on: the same argument, one layer up.

## EVIDENCE

`git show -s 93ca8a6` (meaning-as-code). Removed, not renamed:

> `harvest.py` — profile / region defaults. Now env-only; absent, they are None and the driver's
> ambient chain decides, which is exactly what `connection.yaml`'s `credentials.mode: aws-chain`
> already means.
> `materialize.py` — region + workgroup now read from the bundle's `connection.yaml` via the existing
> connection contract, and RAISE naming the file when undeclared rather than falling back to
> somebody's workgroup.
> `data_plane.py` — `profile_table(..., workgroup=)` is required and threaded from the caller.
> `dp_sys_prompt(source_label, view_schema)` no longer defaults to one source's identity — matching
> `edges.make_edges_file`, which has always required its `source` and has a test pinning that refusal.
> `data_plane.py` — `DP_SYS_PROMPT` deleted: a module constant that froze one source's rendering of
> the prompt at import time. Documented as "for external importers"; there were none.

```
pytest sdk                   83 passed
SDK gate self-tests           9 / 9
run_framework_gates  tpch    30 / 34   (baseline — unchanged)
run_framework_gates  shop    30 / 34   (baseline — unchanged)
real infra handles in tracked files: 0
```

## WHAT CHANGED

The handle register resolves at CALL time, not import, so CI — which has no gitignored register — can
name one via an environment override without committing it. `sdk/conftest.py` declares a SYNTHETIC
handle for the whole suite, so no test writes a real production profile into a fixture to prove a
detector fires. **Three did.**

## WHAT IT DOES NOT PROVE

The commit says it plainly: "Still not pushable: `sdk/` carries instance tokens in prose and one real
warehouse database name in a test fixture. This repository is public." Removing the defaults removes
the mechanism; it does not remove the strings. And `connection.yaml` is a portable contract, not a
connector — nothing yet reads a DECLARED connector, which is stage A2 (`2026-09-13/064`).
