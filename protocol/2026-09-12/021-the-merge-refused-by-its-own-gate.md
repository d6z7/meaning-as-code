---
when: 2026-09-12T20:31:43
what: let the invariant gate refuse the 229-commit absorption merge, declared the retired answering paths with their measurements, and fixed the gate's two precision bugs rather than narrowing it
topics: [gates, capabilities, consolidation, harness]
kind: defect
track: platform
repo: mac-platform
---

## WHAT FORCED IT

The absorption merge was authorised, staged (229 commits, 430 files, 0 conflicts) and REFUSED by the
invariant gate: **40 violations over 66 runtime files** — 33 `model-client-on-answer-path`, 5
`sql-parameter-in-tool-schema`, 2 `model-output-to-sql-field`. The decisive three are in the stopgap,
which exposes `sql` in a tool schema for the model to fill and assigns model output into `sql`.

That is the sequencing working as designed: the gate landed on a green develop FIRST so it could
refuse the thing it was written for.

## EVIDENCE

`git show -s 8232c60 e63022a d93bfab` (mac-platform). Measuring WHY changed what the violations mean:

```
langchain  langgraph  chat  okf_aws  consumption_mcp   ALL ABSENT
```

> `packages/mac-chat/` ... imports a package that exists in no repository. Its 330 test functions
> cannot even be COLLECTED, it is absent from the Makefile's PACKAGES, and POST /ask returns 500
> unconditionally. 12 of the 15 offending files are here.

> So the invariant is not being breached in production; it is being breached in a corpse.

Then reading the remaining ten showed all ten were the gate being imprecise, and BOTH errors are
recorded because the second was caused by fixing the first:

1. Flagging ANY dict with a `sql` key fired on RESPONSE payloads that REPORT the SQL that ran. That
   is DISCLOSURE — the behaviour this estate wants — and the opposite of a model-fillable input. Ten
   false positives blocked a merge.
2. Then requiring the dict holding `sql` to LOOK like a schema went BLIND: in an `inputSchema`, the
   dict holding `sql` is the `properties` block, whose keys are just parameter NAMES; the schema-ness
   is in its PARENT. A planted probe went unreported and the gate's own mutant stopped being caught —
   caught by the self-test, which is the only reason it is known.

```
self-test 16/16 — 6 mutants each caught as their own class, 5 legitimate shapes stay clean
make check: all green · 1003 passed · run_gates 9/9 · run_all_gates 14/14
```

## WHAT CHANGED

Narrowing a gate's scope to make it pass is the move the phase argued against throughout, so the
exclusion is built to be AUDITED rather than trusted: `RETIRED` carries the MEASUREMENT for each
entry in the file, not in a changelog; the verdict NAMES the excluded files and their count; the
denominator says "live runtime file(s)" so a reader cannot mistake 43 for the whole surface; and
reviving a retired path makes its imports resolve again, at which point deleting its entry brings the
40 violations straight back.

`model-output-to-sql-field` narrowed to ATTRIBUTE assignment: a bare local `sql = tc["args"]["sql"]`
READS a tool call in order to disclose it, and flagging that told the reader the gate cannot tell
writing from reading.

## WHAT IT DOES NOT PROVE

The allowlist carries TWO DEFERRALS, and they are deferrals rather than exemptions. The advisor path
is a REAL breach: it constructs a SQL engine and hands tool-calling to a model, reachable at a live
endpoint. Ruling R3 scoped the ban to answer time on the grounds that authoring may draft SQL a gate
and a human seal — the advisor does not fit that, it executes live queries in response to a user's
question, so **R3 does NOT cover it and the gate is right to fire**. It is carried because its
dependencies are absent so it cannot run, and unlike the retired package it IS shipped, so this rests
on "cannot import" alone. That is weaker, and the file says so.
