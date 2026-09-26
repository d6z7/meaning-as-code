---
name: mac-ingest
description: "Ingest a warehouse into a MAC bundle: isolate, measure with mac_import, prepare every ruling, stamp the contract, enforce with the gates. Use as ingestion step I1-I5. Never reimplement a stage, never summarise the deliverable table in prose."
---

# INGESTION — the lifecycle for reading a warehouse, not for building the platform

The seven platform steps (`direction` → `integration-and-release`) are the lifecycle for **building
this system**. Ingesting a warehouse is a different lifecycle with different gates, and it had none —
which is why for months "the import delivered" was a sentence an agent wrote and an operator had no
way to check.

**This skill is not the enforcement.** `CORE.md §2`: *"A check that cannot fail is a report, not a
gate."* `gates-and-checks`: *"a rule is enforced only where a wrong version fails."* A skill is a
paragraph. Two gates do the enforcing, and this file exists to say which and when:

| | |
|---|---|
| `tools/mac_import.py --self-test` | 14 cases, 9 mutants — the reporting layer itself, no warehouse needed |
| `tools/check_first_run.py <bundle>` | the bundle against the contract it declares |
| `tools/run_framework_gates.sh <bundle>` | every `check_*.py`, each one's `--self-test`, with denominators |

## Why this lifecycle is worth writing down

Measured over one session on two bundles, **thirteen defects, and eight were in the reporting layer,
not in the measurement**: a deliverable probing a path its producer had abandoned; a stage declaring
one of the two planes it writes, so resume skipped and left a plane missing all run; "22 registers"
printed beside 17 files; "no column is both bounded and enumerable" printed beside 17 registers; a
complete measurement rendered `FAIL`; a refusal rendered `NEEDS YOU`; four stages crediting
deliverable ids the table no longer defined.

Every one was **a claim about the state that did not match the state**. That is the failure this
lifecycle is shaped against, and it is why step I2 forbids paraphrase.

---

## I1 · ISOLATE — the bundle owns its warehouse

Two bundles are prohibited from sharing anything (operator ruling, 2026-09-26). Not tidiness: a
shared warehouse makes a bundle's state unprovable, and it is how one bundle imported **another
ontology's 8 `meta_*` relations as its own data**, 32 artifacts deep, because one `connection.yaml`
named `../../../<sibling>/x.duckdb`.

- `connection.yaml` points inside the bundle; `build.sh` builds from the bundle's own bytes
- the one permitted cross-border act is a **human comparing an answer** between bundles
- enforced by `check_bundle_isolation.py` and `check_meaning_plane_not_imported.py`

## I2 · MEASURE — run the tool, print what it prints

**Never reimplement a stage.** `mac_import` runs 16 stages in dependency order and each knows what it
produces; a hand-run subset is how a stage-ordering defect hides.

**Never summarise the deliverable table in prose.** Print it. The table is the report, and an agent's
paraphrase of it is a fourteenth claim that can drift from the state. The deliverables have three
homes already — the DELIVERABLES decision record, the `DELIVERABLES` table in `mac_import.py`, and
each bundle's run output. Do not create a fourth: this file deliberately does not list them.

**Never quote a gate's PASS without its denominator.** `PASS: 4/4` over zero files is a green that
means "did not run", and three such were found in this estate.

## I3 · RULE — every NEEDS YOU arrives prepared

A free run ends with items only a person can settle. `CORE.md §6` sets their shape, and the reason is
economic: *"The scarcest resource is the operator's attention, and the commonest waste is a question
that starts a conversation instead of ending one."*

Each one carries: a **closed** question with its permitted answers · what was established, with
evidence · what only a human can settle, and why · the consequence of **each** answer · a
**recommendation**, so the cheapest reply is agreement.

*"If the human must ask a clarifying question, the ruling was not prepared."*

The measurers already emit this shape — `references_broken[].ruling` and the register's `ruling` —
with `status: open` and `ruled_by: null`. Carry it; never paraphrase it into a weaker sentence. A
ruling survives re-measurement: the measurement refreshes, the disposition does not.

## I4 · CONTRACT — the one human gate of this lifecycle  ⟨GI⟩

The bundle declares `acceptance/expected_first_run.yaml`: which deliverables must be present, which
must be absent, the sizes that are part of the claim, and **the findings that must be raised**.

**It is authored once and frozen, and that is deliberate.** `CORE.md §7` prefers derived tests — *"a
test generated from the artifact it tests cannot drift from it"* — and names this exception in the
next breath: *"Authored tests are for the claims no derivation can reach, and those are exactly the
ones needing a human authority stamp."* A contract regenerated from its own run re-records whatever
happened and proves nothing.

**An agent may draft it. Only the operator stamps it.** `scope-and-acceptance` states the reason for
the whole estate: *"An agent that writes its own acceptance criteria has marked its own exam."*

The `findings` list earns its keep in both directions, and both are measured:

- **lost** — before the referential family existed, **22 orphan foreign keys** sat in a warehouse
  while **31 of 31** DQ cases passed. A finding that stops being raised means the platform stopped
  detecting a defect it once caught.
- **extra** — one version of the broken-reference band raised **six absurd findings** on a clean
  bundle (square metres referencing a product key) against **one** true positive. Re-running that
  bundle against its contract is what caught it. A short `findings` list is a false-positive tripwire.

## I5 · ENFORCE — and never grade your own run

Run `tools/run_framework_gates.sh <bundle>`. It globs `tools/check_*.py`, so a new gate is picked up
by existing; it runs each gate's own `--self-test`, and it counts a gate's exit 2 **separately** from
pass and fail, because a could-not-run is not a verdict.

A gate whose self-test cannot pass is not evidence about the bundle, whatever its run said.

---

## The shape of the answer, and what it costs

13 of 20 deliverables from a manifest and a connection, twice, on two warehouses sharing no
convention. Of the 7 absent, **6 are derived from the 7th** — so exactly **one of twenty needs a
person**: the concepts. Everything else is measurement.

That one is a **ruling**, not an authoring task: the platform holds the references, keys, domains,
lineage and samples, so it can propose with evidence and the operator accepts, rejects or amends.

What is irreducibly human, and must never be mechanised: grain (*"one row per X"* is a claim about
meaning) · which of several equally-valid candidate references is *the* one · whether a domain is
truly closed or only closed today · whether an orphan set is a defect or expected · what business
notion the data carries.

## Where this file lives, and why it is not in `.claude/`

Tracked home: **`meaning-as-code/skills/mac-ingest/`** — the framework owns it, beside the tools it
describes. Discovery home: `meaning-as-code/.claude/skills/mac-ingest`, a **symlink** to it.

That is not fussiness. This repo's `.gitignore` ignores `.claude/` entirely, so a skill written there
is not part of the framework at all — it is a local file that vanishes on a fresh clone, while
`mac-platform` tracks its own 20 skills and looks like the precedent for putting it there. Either
choice produces a second copy of one fact, and `harvest.py` already exists twice in this estate as the
standing example of what that costs. A symlink cannot drift from its target, so it needs no hash gate
to keep it honest.
