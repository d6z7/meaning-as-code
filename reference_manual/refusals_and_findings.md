---
title: Refusals, findings and gates — what the engine says when it will not answer
status: outcome_class and diagnostic_code are read; data_plane_gate is enforced by the gate chain
audience: anyone reading a refusal, a compiler finding, or a red gate
---

# Refusals, findings and gates

Three closed taxonomies, for three different moments:

| when | vocabulary | says |
|---|---|---|
| a question was asked | `mac.outcome_class` | what the engine **did** about it |
| a bundle was compiled | `mac.diagnostic_code` | what is **wrong with the ontology** |
| a bundle was promoted | `mac.data_plane_gate` | why the **data→ontology handoff** was refused |

**A refusal is a result, not a failure.** Three of the four canonical outcomes are non-answers, and
each is a different statement about the world. Collapsing them — treating "we asked", "the evidence
is absent" and "that is not ours to answer" as one — is what makes a system feel broken when it is
being careful.

---

## `mac.outcome_class` — what the engine did about a question

<!-- BEGIN GENERATED:vocabulary-terms:outcome_class (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> What the engine DID about a question — the disposition, never the channel it used. The four
`canonical` terms are the grading axis; every other term is a spelling measured in live use and
declared so the set can be closed without reddening a working bundle. A term's `status` says
which: `canonical` (one of the four), `deprecated` (a synonym whose canonical form is named in
`use`), `provisional` (a genuinely distinct intermediate state, not one of the four), and
`non_grading` (a real declared disposition that is NOT a judgement about the answer — a metadata
route, a composer decision, an outage). WHERE these are declared is the gate's business, not
this block's: tools/check_outcome_class_closure.py carries the outcome-carrying key list,
because the same key name carries a DIFFERENT axis in different bundles (`oracle_class` holds
this vocabulary in one bundle's run records and a question-FAMILY code in another's dashboard),
so membership cannot be judged by key name alone.

*`mac.outcome_class` · 10 terms · closed — these are all of them*

#### `mac.outcome_class.COMMIT`

THE ENGINE ANSWERED. A value was produced, and every declaration it rests on resolved — the
scope was pinned, the measure was legal at that grain, the names resolved to codes.

| field | value |
|---|---|
| `status` | canonical |

#### `mac.outcome_class.ASK`

A REQUIRED dimension was underspecified, so the engine asked instead of guessing. The question
is answerable; it is not yet fully stated. Never a silent default.

| field | value |
|---|---|
| `status` | canonical |

#### `mac.outcome_class.REFUSE`

THE EVIDENCE IS ABSENT. The question is legal and the engine can state precisely what was
missing — the scope with no row, the name that did not resolve — and says so rather than
returning a zero a reader takes for a measurement.

| field | value |
|---|---|
| `status` | canonical |

#### `mac.outcome_class.BLOCK`

OUTSIDE WHAT THE ONTOLOGY GOVERNS. Not a gap in the data but a question this model does not
undertake to answer, so answering it would be fabrication rather than retrieval.

| field | value |
|---|---|
| `status` | canonical |

#### `mac.outcome_class.DECLINE`

| field | value |
|---|---|
| `status` | deprecated |
| `use` | REFUSE |
| `why` | A pure synonym of REFUSE with no distinct meaning anyone has been able to state. It is the measured cost of leaving this axis ungoverned, and it is the larger of the two spellings: 1.049 declarations across 68 files at the moment of closure, against REFUSE's 1.347, so a reader searching either word sees well under half the population. NOT MIGRATED HERE — the bundle that carries it has no remote, and rewriting a thousand declarations in an unrecoverable tree is a separate, human-authorised act. Declared so the debt is countable.
 |
| `measured_at_close` | 1049 |
| `files_at_close` | 68 |

#### `mac.outcome_class.COMMIT_PENDING`

A COMMIT whose validation precondition has not yet passed — the answer is composed but not yet
cleared to be reported as one. Genuinely distinct from all four canonical terms, which is why it
is `provisional` rather than `deprecated`: collapsing it into COMMIT would report an unvalidated
answer as a validated one.

| field | value |
|---|---|
| `status` | provisional |
| `measured_at_close` | 247 |

#### `mac.outcome_class.ENUMERATE`

A dimension-member LIST — a metadata answer with no measure in it. A route stage, not a
judgement about an answer's correctness, so it does not belong on the grading axis even though
it is declared on the same keys.

| field | value |
|---|---|
| `status` | non_grading |
| `measured_at_close` | 119 |

#### `mac.outcome_class.MODEL_PROPERTY`

Routed to a property OF THE MODEL rather than to the warehouse — answered from declarations
alone. Like ENUMERATE, a route target rather than a grade.

| field | value |
|---|---|
| `status` | non_grading |
| `measured_at_close` | 74 |

#### `mac.outcome_class.DEFER`

The composer declined to compose — it could not build a statement it was willing to stand
behind, and said so instead of emitting SQL that would fabricate a shape.

| field | value |
|---|---|
| `status` | non_grading |
| `measured_at_close` | 59 |

#### `mac.outcome_class.ENGINE_ERR`

The engine raised. An OUTAGE, not a semantic outcome: nothing was judged, so it must never be
counted as a refusal the model chose to make.

| field | value |
|---|---|
| `status` | non_grading |
| `measured_at_close` | 3 |
<!-- END GENERATED:vocabulary-terms:outcome_class -->

### The four that grade

Only the `canonical` four are the grading axis. Read them as a decision:

```
Did a value come out?                          yes → COMMIT
Is the question ours to answer at all?          no → BLOCK
Is something REQUIRED underspecified?          yes → ASK
Otherwise — the question is legal, the
engine can express it, the evidence is absent → REFUSE
```

| outcome | the world | example |
|---|---|---|
| `COMMIT` | answered, every declaration honoured | *"how many female customers in Europe"* → **19 564** |
| `ASK` | the question is incomplete | *"'CO' is carried by 3 countries — Corse (FR), Como (IT), Colorado (US). Which?"* |
| `REFUSE` | the question is fine; the evidence is not | *"no continent named 'Africa' in contoso_country.lookup.csv: compared over 9 rows"* |
| `BLOCK` | outside what the ontology governs | grouping by `ZipCode`, which the bundle forbids on a measured privacy finding |

**`REFUSE` and `BLOCK` are the pair people conflate.** `REFUSE` is *"I cannot show you that"*;
`BLOCK` is *"that is not a thing I will do."* The first may become answerable when data arrives; the
second never will, because a ruling forbids it.

### The six that do not grade

`DECLINE` is **deprecated** — a synonym of `REFUSE` with no distinct meaning, kept so historical
records still join. `COMMIT_PENDING` is provisional. The remaining four are not semantic outcomes at
all: `ENUMERATE` is a metadata answer with no measure, `MODEL_PROPERTY` is a question about the
model rather than the warehouse, `DEFER` is the composer declining to compose, and `ENGINE_ERR` is
an **outage** — nothing was decided, so it must never be counted as a refusal.

> **Counting `ENGINE_ERR` as a semantic outcome is how a broken connection becomes "the ontology
> refused 11 questions".** That distinction is the reason the non-grading terms exist.

---

## `mac.diagnostic_code` — what is wrong with the ontology

Twelve findings in six groups. The **groups** are the useful part: each names a way a declaration
can be wrong, and they are exhaustive by construction.

| group | codes | the failure |
|---|---|---|
| what is **not defined** | MAC001 · MAC002 · MAC009 | a name with nothing behind it |
| what is defined **redundantly** | MAC003 · MAC004 | a fact with two homes — and MAC004 is when they **disagree** |
| what is **offered and not taken** | MAC005 | a capability the bundle could use and does not |
| what is **claimed without warrant** | MAC006 · MAC010 | a guarantee nothing earns |
| what **points at nothing** | MAC007 · MAC008 | a dead guard, an unresolved reference |
| what is **not covered** | MAC011 · MAC012 | a requirement with no implementation |

<!-- BEGIN GENERATED:vocabulary-terms:diagnostic_code (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The closed taxonomy of findings the MAC compiler can report.

*`mac.diagnostic_code` · 12 terms · closed — these are all of them*

#### `mac.diagnostic_code.MAC001`

present in the bundle, carries no MAC definition, not declared out of scope

| field | value |
|---|---|
| `kind` | undefined-artifact |
| `severity` | error |
| `group` | what is not defined |

#### `mac.diagnostic_code.MAC002`

has a MAC definition and does not satisfy it

| field | value |
|---|---|
| `kind` | invalid-artifact |
| `severity` | error |
| `group` | what is not defined |

#### `mac.diagnostic_code.MAC009`

an x- key with no profile entry — CONFORMANCE.md §2: undeclared debt, not license

| field | value |
|---|---|
| `kind` | undeclared-extension |
| `severity` | error |
| `group` | what is not defined |

#### `mac.diagnostic_code.MAC003`

one fact stated in more than one home; nothing keeps the copies in step

| field | value |
|---|---|
| `kind` | fact-restated |
| `severity` | warning |
| `group` | what is defined redundantly |

#### `mac.diagnostic_code.MAC004`

statements of one fact disagree — something downstream is reading the wrong one

| field | value |
|---|---|
| `kind` | fact-contradicted |
| `severity` | error |
| `group` | what is defined redundantly |

#### `mac.diagnostic_code.MAC005`

MAC offers a mechanism for this and the bundle does not use it

| field | value |
|---|---|
| `kind` | capability-unadopted |
| `severity` | warning |
| `group` | what is offered and not taken |

#### `mac.diagnostic_code.MAC006`

a conformance level or confidence asserted with no evidence behind it

| field | value |
|---|---|
| `kind` | claim-unearned |
| `severity` | warning |
| `group` | what is claimed without warrant |

#### `mac.diagnostic_code.MAC010`

an authored or tuned object with no entry in the change record

| field | value |
|---|---|
| `kind` | change-unprotocolled |
| `severity` | warning |
| `group` | what is claimed without warrant |

#### `mac.diagnostic_code.MAC007`

a rule or guard testing a value that cannot occur — it can never fire

| field | value |
|---|---|
| `kind` | guard-dead |
| `severity` | error |
| `group` | what points at nothing |

#### `mac.diagnostic_code.MAC008`

a reference that resolves to nothing

| field | value |
|---|---|
| `kind` | reference-unresolved |
| `severity` | error |
| `group` | what points at nothing |

#### `mac.diagnostic_code.MAC011`

a required completeness the bundle does not reach

| field | value |
|---|---|
| `kind` | coverage-missing |
| `severity` | error |
| `group` | what is not covered |

#### `mac.diagnostic_code.MAC012`

an `x-` extension key. Prohibited outright, because it sits BY CONSTRUCTION outside every gate
MAC has, so nothing can check what it holds. Measured the day x-grain was retired, TWO of four
declared cell keys were false — the main fact view claimed 0 multi-row against millions, and a
second fact view claimed 0 against nearly all of its cells. The two that HELD are the two that a
view enforces: a view that withholds ambiguous cells, and a current-snapshot view whose collapse
makes the key true by construction (its declared cell count reproduced to within a hundred-odd
cells). That is the shape of the defect: the declaration is false exactly where nothing makes it
true, and a field no gate can reach costs nothing to be wrong in. Three mechanical predicates
identify the duplicate case — same subject, same value shape, same closed domain with non-empty
overlap. Where there is NO core equivalent the finding is a MAC gap, not a shortcut: say what
the wall is and change MAC, rather than declaring beside it. Enforced by
tools/check_extension_keys.py, which exits non-zero, because a check that does not block is not
enforcement.

| field | value |
|---|---|
| `kind` | extension-duplicates-core |
| `severity` | error |
| `group` | what is not covered |
<!-- END GENERATED:vocabulary-terms:diagnostic_code -->

**MAC003 versus MAC004 is the distinction to learn.** Restating a fact that already has a home is a
*warning* — harmless duplication until someone edits one copy. Restating it **differently** is an
*error*, because nothing arbitrates which is true. That is the whole argument for `params_from` on a
canon binding: a parameter readable from a declaration should not be re-typed onto the binding.

**MAC008 is the one that catches an unresolved `mac.*` token** — and it only scans `*.yaml` and
`*.yml`. Markdown has never been checked, which is why the reference manual needed its own
[drift gate](../tools/gen_vocabulary_terms.py).

---

## `mac.data_plane_gate` — why a handoff was refused

Fourteen reject classes for one moment: **the data plane is signed off, and the ontology may now
bind to it.** A bundle declaring two pipelines must pass this gate before ontology work begins.

<!-- BEGIN GENERATED:vocabulary-terms:data_plane_gate (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The reject classes of the DATA→ONTOLOGY handoff, as a closed set. A bundle may declare TWO
pipelines (mac.schema.json#ProjectFile.reproduction.pipelines): a DATA pipeline whose declared
exit is ITS OWN REGISTER, FULLY DISPOSITIONED — every registered issue carrying a terminal
`mac.dq_status` term with that term's own evidence — and an ONTOLOGY pipeline that may not start
until that exit is reached. Three consumers read the same verdict — the PreToolUse guard that
refuses a write, the CLI that refuses to start the ontology pipeline, and the console page that
tells the operator what is blocking — so the code set lives HERE and not three times. TWO
MEMBERS ARE NOT BLOCKS. `not_declared`: a bundle that declares one pipeline is governed by the
operator's unlock marker alone, exactly as before. `approval_missing`: RETIRED 2026-09-18, when
the exit collapsed from a separate sign-off file onto the register it described — read its own
entry for the reason and for what the collapse costs (PREVENTION drops to ATTRIBUTION). Every
other `approval_*` member is still a block, because a sign-off file that IS present is honoured
rather than ignored. WHY A CODE AND NOT JUST A SENTENCE. The sentence is rendered to a human and
will be reworded; the code is joined on. A page grouping by sentence re-groups every time the
wording improves. WHAT THIS SET DELIBERATELY DOES NOT CONTAIN: a member for "too many issues",
for "severity too high", or for any count a bundle or a framework could declare as a threshold.
The gate reads no grading field. `severity` is machine-authored (capped at `confidence: I` by
CORE.md §4), so a gate reading it would grade the machine against its own opinion — and a
non-defect parked at `high` would block an ontology forever on bookkeeping rather than on data.
Measured 2026-09-18: a live register's entry was edited from `severity: high` to `severity: low`
the same day a severity-reading gate was proposed, its own inline comment naming the coming gate
as the reason. Goodhart arrived within hours. The threshold here is per-issue HUMAN COVERAGE,
and the only way to move it is for a person to name the specific thing.

*`mac.data_plane_gate` · 14 terms · closed — these are all of them*

#### `mac.data_plane_gate.not_declared`

The bundle declares no `reproduction.pipelines`, so the two-pipeline gate does not apply. EXIT
0, and not a block — the legacy affordance (the operator's `.ontology-unlocked` marker) governs
its ontology plane unchanged. The one member that is a PASS.

| field | value |
|---|---|
| `blocks` | False |

#### `mac.data_plane_gate.approval_missing`

RETIRED 2026-09-18, and kept as a member rather than deleted so a joined-on code does not vanish
from a closed set and so the reason survives where the code did. It used to mean: two pipelines
are declared and no sign-off file exists at the path the manifest names. WHY IT IS NO LONGER A
BLOCK. The separate sign-off file was the BUILD'S design choice, not the operator's requirement.
The operator's requirement, verbatim, was "we cannot automatically proceed with creating
ontology as long as we did not approve the configuration of datasets in full amount. this means
we did not reduce the # of issues to the acceptable minimum" — and that reduction is recorded in
the REGISTER, one argued disposition at a time, which the separate file then duplicated in a
LESS informative form: one date and one name against N individually-argued dispositions. So the
exit collapsed onto the register (`issue_undispositioned` is the blocker that carries it) and
the operator stopped being asked to sign a second artifact saying what the first one already
said. WHAT THE COLLAPSE COSTS, because it is not nothing: the sign-off was the one artifact an
agent provably cannot write — the guard denies that path unconditionally, marker or not — and
the register IS agent-writable. The guarantee therefore drops from PREVENTION to ATTRIBUTION:
git blame, the `ruled_by` name and the reason text, not a token no agent can reach. That is the
ceiling this estate had already reached and recorded in its own words, DETECTED-AND-BLOCKED,
AUTHORIZED OUT-OF-BAND, and a ceremony that buys nothing the operator wants is worse than an
honest ceiling. See PIPELINES.md §8 gap 11. AN APPROVAL FILE THAT IS PRESENT IS STILL HONOURED —
every `approval_*` member below stays a block — so a bundle that carries one does not silently
lose it.

| field | value |
|---|---|
| `blocks` | False |
| `retired` | 2026-09-18 |

#### `mac.data_plane_gate.approval_unreadable`

The sign-off exists and cannot be parsed. Counts as NO approval (deny — the safe direction), and
the refusal prints the offending line number so the operator can fix their own typo. A file no
agent may write is a file only the operator can un-break; that cost is disclosed rather than
eliminated.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.approval_unratified`

The sign-off exists but does not ratify: its `status` is not `applied`, its `verdict` is not
`confirmed`, or its `outcome` is not `ratified`. A draft is not an approval.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.approval_agent_stamped`

The sign-off's write stamp names an agent (`submitted_via: agent`) or an identity nobody
verified or declared (`identity_basis: imported`). An agent may write a DESCRIPTION; only a
human may write a DISPOSITION. Rejecting the honestly-stamped case is what makes the dishonest
one a lie rather than a shortcut.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.issue_uncovered`

A registered issue id the sign-off does not name. This is the threshold, and it is why no number
is invented: the count of uncovered ids must be 0, and it cannot move unless a human names the
specific thing. No wildcard is permitted — if per-issue naming is too many ids, the fix is a
coarser REGISTER, never a coarser gate.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.issue_undispositioned`

ANY registered issue carrying no terminal `mac.dq_status` term, or one whose term's own
`requires:` list is unmet. The law is READ from `mac.dq_status`, never restated here. THIS IS
THE DATA PIPELINE'S EXIT CONDITION since 2026-09-18, and it widened that day from graded defects
(`DQ-`) to EVERY id. Before, an `NS-` non-promotion needed only to be NAMED in a separate
sign-off, because acknowledging a disclosure is a different act from dispositioning a defect —
and the sign-off was where the acknowledgement lived. With the sign-off retired (see
`approval_missing`) there is nowhere else for an `NS-` entry's acknowledgement to be recorded,
so it is recorded in the register like everything else: a terminal disposition with a namer and
a reason. An `open` issue closes the pipeline and is named with its id and the denominator.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.resolved_on_non_defect`

A CATEGORY ERROR, and the one reject class that exists because a disposition can be written by a
machine. `mac.dq_status.resolved` requires NOTHING — its evidence is structural, the cross-link
in impurity_resolution_map.yaml — and both the register and that map are agent-writable, so a
gate reading "status is not open" is satisfiable with no human name anywhere. `resolved` means A
TRANSFORM DISSOLVED A DEFECT. An `NS-` entry is a relation MEASURED AND DELIBERATELY NOT SERVED:
it was never a defect and no transform dissolved it, so `resolved` cannot be true of it and is
refused. The honest disposition of a non-promotion is `accepted` or `wont_fix`, both of which
name a ruler. DISCLOSED GAP, not fixed here: `mac.dq_status` has no term meaning "measured, and
it is not a defect". Non-promotions are therefore dispositioned with defect-shaped words. Adding
a term to a closed vocabulary is a framework change with its own gate consequences; this member
refuses the one spelling that lets a machine clear the register, and names the gap.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.coverage_dangling`

The sign-off names an id the register no longer holds. Distinct from `issue_uncovered` and
reported separately, because they are opposite failures — a human approved something that has
since been renamed or deleted, versus something they never saw.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.plane_moved`

The sign-off's digest no longer matches the data plane as it stands. The ontology already
authored is NOT deleted and NOT invalidated — doing that would be the blanket lock's mistake in
a new costume. Further ontology authoring stops, the plane reads STALE with the date of the
sign-off it invalidates, and the moved files are named so the diff is the review.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.register_unrun`

Datasets are served and the register holds zero issues. That is a step that did not run, not a
clean bill of health, so the data plane cannot be approved from it. A gate that passes having
measured nothing is worse than none (CORE.md §2).

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.no_datasets`

Nothing is served, so there is nothing for an ontology to bind to. Vacuity, refused in the other
direction.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.stage_unassigned`

`pipelines` is declared and a `reproduction.stages[]` entry carries no `pipeline`, so a
half-migrated manifest cannot read as complete.

| field | value |
|---|---|
| `blocks` | True |

#### `mac.data_plane_gate.gate_unreachable`

An input could not be read — the manifest, the register, the vocabulary, or the framework itself
is absent beside the bundle. UNKNOWN => DENY, per the estate's own compile-gate rule:
unreachable means unknown means refuse. A gate that could not run must never read as an open
door. On the console this is the one state that is neither green nor red: it says the gate could
not judge.

| field | value |
|---|---|
| `blocks` | True |
<!-- END GENERATED:vocabulary-terms:data_plane_gate -->

### What the classes are really about

| theme | classes | what it protects |
|---|---|---|
| **the approval is not real** | `approval_unreadable` · `approval_unratified` · `approval_agent_stamped` | a sign-off nobody verified, or one **an agent stamped for itself** |
| **the issues are not settled** | `issue_uncovered` · `issue_undispositioned` · `resolved_on_non_defect` | promoting over a defect nobody dispositioned |
| **the approval no longer applies** | `plane_moved` · `coverage_dangling` | the data changed after it was signed |
| **a step did not run** | `register_unrun` · `no_datasets` · `stage_unassigned` | **vacuity** — a gate that passes because it examined nothing |
| **nothing to check** | `not_declared` · `gate_unreachable` | the honest exits |

**`register_unrun` and `no_datasets` are the two worth understanding.** Both describe a bundle where
everything looks clean because *nothing was examined*. A quality register holding zero issues over
served datasets is a step that did not run, not a clean bill of health — and a gate that reports
PASS on zero files is the failure mode the whole chain exists to prevent.

**`approval_agent_stamped` exists because of a specific risk**: a sign-off whose write stamp names
an agent rather than a person. An agent may prepare the evidence; it may not ratify its own work.

**`approval_missing` is RETIRED and kept as a member** rather than deleted — so a code joined on in
a historical record does not vanish. The vocabulary carries its own history; removing a term would
silently orphan every row that referenced it.
