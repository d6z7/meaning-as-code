---
when: 2026-09-14T12:40:00
what: the operator's proposed data-quality loop already exists across three planes and a gate — measured half-run, with four specific defects that stop it closing
topics: [method, denominators, gates, harness]
kind: build
track: core
repo: meaning-as-code
commits: []
---

## WHAT FORCED IT

The operator proposed a process and suspected it was partly built:

> *"DQ process proposal: you profile the data, you discover DQ issues and you protocol them in a
> list. Operator goes through the list and solves them one by one. You mark and protocol the
> progress. Part of it is already somewhere there in ... if i am not utterly wrong."*

Not wrong. **Four of the five steps exist, plus a gate nobody mentioned.** What does not exist is
step four — the progress mark — and its absence is why the loop reads as stalled rather than
half-run.

## EVIDENCE — what is already built

    1 PROFILE         data/profiles/*.yaml                        25 census files
    2 REGISTER        data/quality/data_quality_register.yaml      44 issues, 525 lines
                      data/quality/DQ-<id>.md                      44 prose files
    3 SOLVE           data/transforms/*.yaml                       14 transforms (46 files)
    4 PROGRESS        data/quality/impurity_resolution_map.yaml    137 lines, 22 linked findings
    5 GATE            tools/check_dq_resolution_sync.py            enforces no drift across 1-4

The gate's own header states the contract, and it is exactly the operator's loop:

> *"A transform that 'dissolves an impurity' must SAY which registered defect it resolves —
> `resolves: [DQ-id, ...]` on the rule — and the resolution map must link that finding back to this
> transform. Otherwise the Cleaning tab and the Quality tab tell different stories: a fix that is not
> recorded as a problem, or a problem claimed fixed by nothing."*

A register issue carries `id · title · table · finding · severity · sme_owner · current_handling ·
residual_risk · confidence`. A resolution-map entry carries `finding_id · coverage · resolving_transforms
· guarantee`. **Both halves of the loop are modelled.**

## THE PROGRESS NUMBER, AND IT HAS NEVER BEEN PRINTED

    register issues                        44 entries
    distinct ids                           43          <- ONE DUPLICATE
    linked to a resolving transform        22
    NOT linked                             21
    severity                               high 12 · medium 20 · low 12

**Half the register is resolved and nothing anywhere says so.** The loop is not stalled; it is
un-reported, which is a different defect with a much cheaper fix.

## FOUR DEFECTS THAT STOP IT CLOSING

1. **THERE IS NO `status` ON AN ISSUE.** The register's keys are
   `confidence, current_handling, finding, id, residual_risk, severity, sme_owner, table, title` —
   **no status, no opened, no closed, no resolution state.** So "which issues are still open" is not
   a readable fact: it can only be INFERRED by joining the register to the resolution map and
   treating absence as open. Absence is not a state. An issue deliberately accepted-as-is and an
   issue nobody has looked at are indistinguishable, and they are the two most different things in
   the register.

2. **THE REGISTER CANNOT BE KEYED BY ITS OWN ID.** 44 entries, 43 distinct ids — one id appears
   twice. Every join in the loop is on that id, so one pair of issues is unaddressable by the very
   mechanism that is supposed to resolve them.

3. **21 UNLINKED ISSUES HAVE NO DECLARED REASON.** Unlinked means one of at least three things —
   not yet worked, deliberately won't-fix, or resolved by something that forgot to say so — and the
   register cannot express which. Defect 1 is why.

4. **THE ACCEPTANCE PLANE'S `dq_id` IS NOT RESOLVED.** A property red may be dispositioned with
   `accepted: {dq_id: ...}`, and the plane's own notes record that this id **is not checked to
   resolve**. So a test can be accepted against a defect that does not exist, and a defect can be
   closed while a test still points at it. This is the same class as defect 2, one plane over.

## THE FINDING THAT MAKES THIS URGENT RATHER THAN TIDY

A generated value-set property records the CURRENT member list as its expectation. In the measured
bundle, one such property's recorded set contains **both spellings of a near-duplicate member that
the register files as an open defect.** The property is GREEN. It is green BECAUSE the defect is
present, and it would turn RED the day someone fixed it.

> **A FITNESS green over a value set containing a registered defect does not mean CORRECT. It means
> ACCEPTED — and nothing in the estate currently distinguishes the two.**

That is the whole argument for closing the loop: not neatness, but that a repair currently reads as a
regression.

## WHAT CHANGED

Nothing at the time of writing — the entry was a measurement. Since then, and cited here so the two
are not read as independent: `mac_vocabulary.yaml` gained `dq_status` (`open | accepted | resolved |
wont_fix`, with `accepted` and `wont_fix` requiring `ruled_by` and `reason`), and
`check_dq_resolution_sync.py` was rebuilt to enforce it — 17/17 self-test over 5 fixtures and 12
mutants of its own rule. Both landed in `57b9106`, whose message names neither; see entry 004.

## WHAT TO NAIL DOWN — smallest change that closes it

- **`status:` on every register issue**, from a closed vocabulary — `open | accepted | resolved |
  wont_fix` — with `accepted` and `wont_fix` REQUIRING a ruled_by and a reason. Absence stops being a
  state.
- **Unique ids**, enforced by the gate that already reads the register.
- **`dq_id` must resolve**, both directions: an `accepted:` naming no registered issue FAILS, and a
  resolved issue still named by an `accepted:` block is reported.
- **A FITNESS property whose recorded expectation overlaps an OPEN issue renders as ACCEPTED, not
  GREEN** — and the day the issue closes, the property is regenerated rather than turning red.
- **Print the progress line**: `N issues · M resolved · K accepted · J open`, which is a two-command
  measurement today and a denominator the estate does not currently publish.

## CORRECTIONS TO THIS ENTRY, made the same day

**"46 transform declarations" was a FILE count.** `data/transforms/` holds 46 files — 14 `.yaml`,
14 `.sql`, 17 `.md`, 1 `.py` — which is **14 transforms**, each with a declaration, its SQL and its
prose. Conflating files with declarations is the same defect as every other denominator error here,
committed inside the entry that catalogues them.

**Defect 4 is unenforced but NOT currently violated.** All four planes were searched for dangling
`dq_id`s and there are none. The gate is still owed; the leak it guards against has not happened yet.

**And the acceptance plane cannot supply a DQ status in general.** An `accepted:` block dispositions
a PROPERTY'S RED and cites a `dq_id` as its justification — it is not a ruling on the defect itself.
It touches 2 of 44 issues. So closing the loop cannot be done from the acceptance plane; the status
has to live on the issue.

## WHAT IT DOES NOT PROVE

Whether the 44 prose `DQ-<id>.md` files and the 44 register entries agree — two homes for one fact,
unverified here. And the loop describes DATA defects only: the same shape is not declared for
mapping defects or semantic defects, which together are the larger share of recorded problems
(mapping 7 and semantics 10 of 30 non-PASS verdicts, against 2 for source data).
