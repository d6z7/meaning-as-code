---
title: Testing and data quality — what an instrument did, and what a human ruled
status: both vocabularies are read; check_dq_resolution_sync enforces the DQ cross-links
audience: anyone reading a test result or a quality register
---

# Testing and data quality

Two dispositions that look alike and are not:

| | `mac.test_status` | `mac.dq_status` |
|---|---|---|
| records | what the **instrument did** about a claim | what a **human decided** about a defect |
| written by | the run | a person |
| green means | the claim held, over a non-empty population | the defect is gone, or somebody chose to live with it |

**Neither records what the data turned out to be.** `FAIL` is a statement about the data; every
other test status is a statement about the *instrument*. That separation is why a broken connection
cannot be read as a failing model.

---

## `mac.test_kind` — which question a property answers

<!-- BEGIN GENERATED:vocabulary-terms:test_kind (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> Which question a property answers. The two kinds have OPPOSITE rules about where their numbers
come from, and a property that tries to be both can be trusted for neither.

*`mac.test_kind` · 2 terms · closed — these are all of them*

#### `mac.test_kind.conformance`

DOES THE MODEL DO WHAT IT SAYS? Every value it asserts is READ from a declaration at run time
and never typed. A typed literal IS the defect here: a later author types a different one and
the test passes while checking something else. Render the key, the enumeration, the codes — and
REFUSE if they cannot be resolved, rather than substituting nothing into a PARTITION BY.

#### `mac.test_kind.ground_truth`

IS WHAT IT SAYS TRUE? Measures the world and compares it against the declaration, so it must NOT
be generated from the declaration's own claims — its entire purpose is to DISAGREE with the
descriptor when the descriptor has gone stale. It still READS the declaration, to know what to
test, but never inherits its assertions; a measured literal is acceptable where it is dated and
re-checkable. EXAMPLE — a grain property reads the relation's measured key to learn which
columns identify one figure, then asks the warehouse whether that still holds. It is the
property that caught v_<source>_kpi.yaml claiming "VERIFIED 2026-08-16 ... 0 multi-row" against
a warehouse that had reached millions of multi-row cells. A conformance test rendered from that
same declaration would have confirmed the claim rather than contradicted it — which is the
entire distinction between the two test kinds.
<!-- END GENERATED:vocabulary-terms:test_kind -->

**The two have opposite rules about where their numbers come from**, and a property mixing them is
broken in a way that still goes green:

| | `conformance` | `ground_truth` |
|---|---|---|
| asks | *does the model do what it says?* | *is what it says true?* |
| every asserted value | **READ from a declaration** at run time | **MEASURED from the world** |
| a hardcoded number is | a defect — the declaration could change beneath it | the point |

A conformance property with a literal `7` in it stops testing the model the moment the model says
`8`: it then tests that someone updated two places, which nobody does.

---

## `mac.test_status` — what the instrument did

<!-- BEGIN GENERATED:vocabulary-terms:test_status (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The disposition of ONE property run — what the INSTRUMENT did about the claim, never what the
data turned out to be. Written BARE on a run record's `results[].status` (like its siblings
`severity` and `family`), referenced as `mac.test_status.<term>`. Every term carries
`gradeable`: true where the run produced a verdict about the data, false where it did not, so a
surface can separate "the data is dirty" from "the test is broken" without hard-coding a list of
names. THREE OF SEVEN ARE NOT GRADEABLE, and a board that paints them like FAIL reports a broken
instrument as a data finding — measured at 9 of 18 on the suite this block was written against.
`ACCEPTED` and `VACUOUS` carry a `requires`, for the same reason `dq_status.accepted` does: they
are the terms that would otherwise be the cheapest way off a red board, so each must carry the
evidence that it was earned.

*`mac.test_status` · 7 terms · closed — these are all of them*

#### `mac.test_status.PASS`

THE INSTRUMENT RAN OVER A NON-EMPTY POPULATION AND THE CLAIM HELD. The population part is not
decoration: a PASS over zero subjects is the vacuous green this vocabulary's seventh term exists
to make unsayable.

| field | value |
|---|---|
| `gradeable` | True |
| `requires` | none |

#### `mac.test_status.FAIL`

THE INSTRUMENT RAN AND THE CLAIM DID NOT HOLD — a statement ABOUT THE DATA, which is what makes
it the one red a reader may act on directly. Today it is also the dumping ground for every run
that produced no verdict at all, and that is the defect `VACUOUS` removes.

| field | value |
|---|---|
| `gradeable` | True |
| `requires` | none |

#### `mac.test_status.ACCEPTED`

THE CLAIM DID NOT HOLD AND A NAMED RULING TOLERATES IT. Green because the defect is tolerated,
which is not the same claim as correct — the same distinction `dq_status.accepted` draws one
plane over. `run_suite.py` stamps the suite's `accepted:` block onto the result, so the ruling
travels WITH the verdict rather than being looked up beside it.

| field | value |
|---|---|
| `gradeable` | True |
| `requires` | accepted |

#### `mac.test_status.FROZEN`

THE CLAIM DID NOT HOLD AND THE FAILURE IS DELIBERATELY PARKED — neither repaired nor ruled
acceptable. Distinct from ACCEPTED, which asserts someone judged the finding; FROZEN asserts
only that someone decided not to today. NOTE, MEASURED: the `frozen:` block lives on the SUITE
and is not copied onto the result, so a FROZEN row carries no on-record evidence of who froze it
or when — the asymmetry with ACCEPTED is real, and is recorded here rather than papered over
with a `requires` no writer satisfies.

| field | value |
|---|---|
| `gradeable` | True |
| `requires` | none |

#### `mac.test_status.ERROR`

THE INSTRUMENT RAISED. An OUTAGE, not a judgement: a split that would not open, a connection
refused, a timeout. Nothing was judged, so it must never be counted as a finding about the data
— `tools/_plugin.py`'s founding rule ("could not run is the one honest answer available, and it
is never a finding") and `sdk/connector/base.py`'s `EXIT_COULD_NOT_RUN`, on this axis. Carries
`rows: null` — NOT `[]` — because an empty grid means the query ran and returned nothing, which
is evidence, and `null` means nothing was examined.

| field | value |
|---|---|
| `gradeable` | False |
| `requires` | notes |

#### `mac.test_status.NOT_RUN`

DECLARED, NEVER ATTEMPTED. The honest default for an id the suite declares and the run did not
reach, written by `carry_forward` so that a declared property with no result is NOT_RUN rather
than ABSENT — absence reads as nothing-to-report, which is the state this term was invented to
end. Excluded from `examined` and counted as `skipped`.

| field | value |
|---|---|
| `gradeable` | False |
| `requires` | none |

#### `mac.test_status.VACUOUS`

THE INSTRUMENT RAN CLEANLY AND HAD NOTHING TO JUDGE. The query compiled, reached the source and
returned — and the population it examined was ZERO, so the claim was neither satisfied nor
violated. A property over zero subjects cannot be satisfied vacuously AND CANNOT BE VIOLATED
VACUOUSLY EITHER; the runner already says the first half in its own note and then returns FAIL,
which asserts the second. DISTINCT FROM `ERROR` (which raised, and has no evidence) and from
`NOT_RUN` (which was never attempted): a VACUOUS run has a query, a byte count and a measured
zero, and every one of those is actionable — it means the scope, the filter or the fixture is
wrong, and the property is currently testing nothing. NOT AN ESCAPE HATCH: `requires` makes the
zero NAMEABLE and CHECKABLE rather than asserted, because a status that could be written without
evidence would be the cheapest way off a red board — the `corpus: none` failure mode, one plane
over. `examined` names the population column the instrument itself reported — the live spellings
are all of the form `<subject>_examined` or a bare count of the subject — and its value, which
MUST be 0. A non-zero `examined` with a null verdict column is a DIFFERENT instrument defect and
is NOT this term (measured live: one property, a non-empty base examined, derived columns null).

| field | value |
|---|---|
| `gradeable` | False |
| `requires` | examined, notes |
<!-- END GENERATED:vocabulary-terms:test_status -->

### Gradeable and not

Four statuses grade; three do not, and the split is the whole design:

| gradeable | `PASS` · `FAIL` · `ACCEPTED` · `FROZEN` | the instrument reached a judgement |
| **not gradeable** | `ERROR` · `NOT_RUN` · `VACUOUS` | **no judgement exists** |

**Counting a non-gradeable status as a result is how a suite reports health it never measured.**
`ERROR` is an outage — a connection that would not open. `NOT_RUN` is an id the suite declares and
the run never attempted. And `VACUOUS` is the dangerous one:

> **`VACUOUS` — the instrument ran cleanly and had nothing to judge.** The query compiled, reached
> the source, and matched zero rows. Every assertion over an empty set is trivially true, so a
> vacuous property looks exactly like a passing one.

That is why `VACUOUS` **requires `examined`** — a population count — and `notes`. A green result
with no denominator is not a result. It is the same law as *never quote a gate's PASS without its
denominator*.

**`ACCEPTED` requires a named `accepted` ruling**, so "green because someone tolerated it" can never
be confused with "green because it held". `FROZEN` is the honest third case: it did not hold, nobody
ruled on it, and the failure is parked deliberately rather than hidden.

---

## `mac.dq_status` — what a human ruled about a defect

<!-- BEGIN GENERATED:vocabulary-terms:dq_status (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The disposition of ONE registered data-quality issue — what a human decided about it, not what a
pipeline did to it. Written BARE on `issues[].status` (like its siblings `severity` and
`confidence`), referenced as `mac.dq_status.<term>`. `accepted` and `wont_fix` REQUIRE
`ruled_by` (the named person or role who ruled — never "the team", never a tool) and `reason`
(why the defect is real, and why it is being lived with rather than fixed), because those are
the two terms that CLAIM a human acted. The set is closed so that absence of a status is a
FINDING rather than a fourth, unnamed meaning.

*`mac.dq_status` · 4 terms · closed — these are all of them*

#### `mac.dq_status.open`

NOBODY HAS RULED ON IT YET. The honest default and the only one that may be written without
evidence — it asserts nothing except that the defect is recorded and undispositioned. This is
the state that absence was silently standing in for, and naming it is the entire point: an issue
is `open` because someone wrote `open`, not because a join missed.

| field | value |
|---|---|
| `requires` | none |

#### `mac.dq_status.accepted`

A NAMED HUMAN EXAMINED IT AND CHOSE TO LIVE WITH IT. The defect is real, it is not being fixed,
and that is a decision on the record rather than an omission. This is the term that makes a
FITNESS green legible: a property whose recorded expectation overlaps an accepted issue is GREEN
BECAUSE THE DEFECT IS TOLERATED, which is not the same claim as correct.

| field | value |
|---|---|
| `requires` | ruled_by, reason |

#### `mac.dq_status.resolved`

THE DEFECT IS GONE, dissolved by a transform that says so. Evidenced by the cross-link in
impurity_resolution_map.yaml rather than by a ruling, which is why it requires no `ruled_by`:
the evidence is structural and already gate-checked. A `resolved` issue still named by an
acceptance-plane `accepted:` block is a REPORTED drift — the test is being excused for a defect
that no longer exists.

| field | value |
|---|---|
| `requires` | none |

#### `mac.dq_status.wont_fix`

A NAMED HUMAN RULED THAT IT WILL NEVER BE FIXED. Distinct from `accepted`, which tolerates a
defect that could still be repaired: `wont_fix` closes the question. Carries the same evidence
burden for the same reason — it asserts a ruling, so it must name who ruled.

| field | value |
|---|---|
| `requires` | ruled_by, reason |
<!-- END GENERATED:vocabulary-terms:dq_status -->

### Only one may be written alone

| status | requires |
|---|---|
| `open` | — the honest default |
| `resolved` | evidenced by the cross-link to the transform that dissolved it |
| `accepted` | **`ruled_by` and `reason`** |
| `wont_fix` | **`ruled_by` and `reason`** |

**`accepted` and `wont_fix` are different rulings and the distinction matters.** `accepted`
tolerates a defect that is real and might one day be fixed; `wont_fix` says it never will. Writing
either without a named person and a reason turns a human decision into an anonymous one — and an
anonymous tolerance is indistinguishable from an oversight.

`ruled_by` names **a person or a role — never "the team", never a tool.**

### The four planes that must agree

`resolved` is the only status that makes a claim a pipeline can check, and
`check_dq_resolution_sync.py` checks it across four files: the **register** holds the defect, a
**transform** says it resolves that id, the **resolution map** cross-links them, and **acceptance**
tests excused against the defect name it. A fix not recorded as a problem, or a problem claimed
fixed by nothing, makes those planes tell different stories.
