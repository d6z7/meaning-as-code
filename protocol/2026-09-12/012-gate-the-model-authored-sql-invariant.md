---
when: 2026-09-12T17:17:35
what: made the no-model-authored-SQL invariant mechanically enforced on the answering path, with six reject classes and two asserted true negatives
topics: [gates, capabilities, harness, denominators]
kind: build
track: platform
repo: mac-platform
---

## WHAT FORCED IT

The invariant was already true by construction and nothing checked it. The runtime's own types state
it: `Plan.sql_preview` is "never executed", `to_executable()` is the only promotion,
`ExecutablePlan.sql` carries `:param` placeholders, and adapters take the typed plan rather than a
string. What was missing was anything that would notice if that stopped being true — and it had
already stopped once, in a stopgap that had a model write a statement and handed it to an executor.

## EVIDENCE

`git show -s e07d3ea` (mac-platform). Six reject classes, each with a mutant:

```
sql-parameter-in-tool-schema     a schema exposing `sql` for a model to fill
prompt-authors-sql               a prompt telling the model to write a query
model-client-on-answer-path      an answering module importing a model client
model-output-to-sql-field        a model-derived value assigned into `sql`
executor-receives-assembled-sql  SQL built from untyped parts, not bound
unparseable                      a file the gate cannot read is not clean
```

```
make check: all green
260 passed, 2 skipped · coverage 100% · secrets 145 files 0 · neutrality 136 files 0 ·
sql-invariant 0 over 43 runtime files / 5 executor calls / 261 strings · self-test 13/13
```

Two TRUE NEGATIVES are asserted alongside the mutants, because the first draft produced a false
positive: it flagged an adapter's `_run_query(f"EXPLAIN {plan.sql}", ...)`, which composes around a
plan produced deterministically upstream. The rule now distinguishes interpolating a TYPED PLAN FIELD
from interpolating an untyped part — a table name, a predicate — which is the shape a model's output
takes. A gate that cries wolf is a gate nobody reads, so the refinement is itself tested.

## WHAT CHANGED

The scope boundary is DATA, in `RUNTIME_ROOTS`, so it is reviewed in one place instead of re-inferred
per reader. The denominator is always printed; the population comes from `git ls-files`, never
`rglob`, so a finding in untracked build output cannot be reported as a defect. Exit 2 when the tree
is not a git repository or holds no runtime file: 0 examined is not clean.

The gate landed on a GREEN develop deliberately, so it could serve as the ADMISSION CRITERION for the
absorption merge rather than landing inside it.

## WHAT IT DOES NOT PROVE

Runtime-scoped by ruling R3, so it says nothing about authoring-time SQL. And "0 over 43 runtime
files" is the count on `develop` before the absorption; the same gate measured 40 violations over 66
files the moment the absorbed packages arrived (`2026-09-12/021`), which is what an admission
criterion is for.
