---
when: 2026-09-13T01:54:10
what: applied "no instance specifics live in MAC" as one rule rather than four judgement calls, and moved three detector registers out of the public repository
topics: [the-public-boundary, registers, gates, harness]
kind: build
track: core
repo: meaning-as-code
commits: [8def5f6]
---

## WHAT FORCED IT

The rule, stated by the operator: **a test in the SDK must be generic; anything specific belongs to
the ontology, not to the instrument.** That makes "is this particular value load-bearing?" the wrong
question — and it was the question being asked.

Three detectors held, inside a public repository, the exact strings they exist to keep out of it.

## EVIDENCE

`git show -s 8def5f6` (meaning-as-code):

> `infra_handles` was four literal production handles inside the secrets gate — an SSO profile, a
> workgroup family, a results bucket, another source's warehouse db, one carrying a person's name.
> `source_tokens` was a module constant inside the coupling gate: the instance names that gate exists
> to keep OUT of the instrument, listed in the instrument.
> `shared_schemas` was a literal set in `materialize.py` mixing generic names with one estate's own.
> Separated because they are DIFFERENT lists — a source's own name is precisely the schema it should
> materialize into, and conflating them made `assert_own_schema` refuse every source by its own name.

```
instance tokens in sdk/      0   (the 5 remaining hits are ordinary English words)
pytest sdk                  83 passed
SDK gate self-tests          9 / 9
check_source_coupling       OK, 4 token(s) declared, 4 pre-existing ratcheted with reasons
run_framework_gates tpch    30 / 34   (baseline — unchanged)
run_framework_gates shop    30 / 34   (baseline — unchanged)
```

## WHAT CHANGED

`sdk/registers.py` is the single loader. Each register is a gitignored file beside the gates, with an
`.example` tracked, an environment override so CI (which has no gitignored file) can name one, and
LIVE re-reading so an override set after import is honoured.

**Every register carries its count into the verdict line.** An absent register now reads
`0 handle(s) declared` / `0 token(s) declared`, never a bare PASS — a gate that examined nothing has
measured nothing.

Both self-tests stopped depending on the live registers. They had declared a REAL production handle
into a temp fixture to prove a detector fired; on a fresh checkout they would instead have exercised
the class against an empty list and passed, having checked nothing. Each now declares a SYNTHETIC
entry through the register's own environment override — the mechanism an estate uses, exercised
rather than bypassed.

The token sweep also found collateral no gate could: a bundle-path pattern hardcoding one estate's
domain segment, a display table special-casing one estate's acronym, and a test writing a real
warehouse database into a manifest fixture — an assertion that had become VACUOUS once the register
moved out, since the real name is no longer declared anywhere a test can see.

## WHAT IT DOES NOT PROVE

A gitignored register makes every one of these gates WEAKER on a fresh clone, and the `.example`
files ship the format with no values. The estate's own onboarding record already says one gate is
weaker on a fresh clone for exactly this reason. This trades a certain disclosure for a conditional
blindness, and the only thing holding the trade honest is that each gate now prints how many patterns
it actually had.
