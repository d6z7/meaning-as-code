# The protocol — what we did, when we did it, and what forced it

Append-only. Entries are never edited, only superseded by later ones that say so. This is the RAW
record; nobody reads it end to end. The readable artefacts are the compiled topic pages in `wiki/`,
and they cite back to here.

## Why raw and compiled are separate

`sdk/project/knowledge.py` states the principle this borrows, for ontology source documents:

> **VERBATIM OR NOTHING.** Every span rendered here is quoted from the extraction, never paraphrased.
> That is not stylistic: it makes the register mechanically verifiable — a gate can assert that each
> span still appears in the source, which is impossible once someone has summarised it.

> Judgement about WHICH statements are normative belongs in a separate claims layer, so that
> extraction and interpretation never blur.

Applied to our own work: the protocol is extraction, the wiki is interpretation, and a gate can check
that the interpretation still quotes something real.

## Entry format

One file per entry, `protocol/YYYY-MM-DD/NNN-slug.md`, with front matter:

```yaml
---
when: 2026-09-13T10:42:00
what: one line, past tense, what was actually done
topics: [connectors, gates, public-boundary]     # drives wiki compilation
track: core | ontology | platform                # which builder needs this
kind: decision | build | measurement | defect | ruling
repo: meaning-as-code                            # WHERE the work landed — this estate is many repos
commits: [b780b48, efac30b]                      # what this entry accounts for — see ENFORCEMENT
supersedes: 2026-09-12/004-slug                  # optional
---
```

### `commits:` — three forms, and never an empty list

```yaml
commits: [b780b48, efac30b]                 # THIS repo. A bare short sha, as `git log --format=%h` prints it.
commits: [0a23934, mac-platform:393ad70]    # another repo. `<repo>:<sha>`, and the repo token is the
                                            # one this entry's own `repo:` field names.
commits: [none]                             # no commit ANYWHERE. Requires `commits_why:` beside it.
commits_why: a ruling; its only artefact is this entry
```

**Why a repo qualifier and not a bare sha everywhere.** One act of work routinely lands in two
repositories — `2026-09-12/018` fixed one detector here and its sibling in `mac-platform`,
`2026-09-12/025` shipped a generator here and ran it on a customer bundle — so an entry's commit list
is not single-repo and `repo:` alone cannot say which sha went where. A qualified sha also cannot be
mistaken for coverage: `check_protocol` compares against `git log` in THIS repository, a bare short
sha is the only thing that can match, and a qualifier makes an accidental collision with a foreign
repo's abbreviation impossible rather than unlikely.

**The consequence, stated rather than discovered later.** `check_protocol` judges only this repo's
commits. An entry whose work lives entirely elsewhere therefore accounts for NOTHING here, on
purpose — it is a record, not coverage — and the orphan count is a claim about this repository alone.
The sibling repos have their own history and, for now, no gate of this kind.

**Why `[none]` and not `[]`.** An empty list is indistinguishable from a field nobody filled in, and
this record exists because the untracked case is the one that goes missing. A ruling, a measurement
that changed nothing, an entry recording a decision not to build — all are legitimate and all must
say so in words, because "this work produced no commit" is a claim someone should be able to
disagree with. `commits_why:` is where they read it.

**What is NOT yet gated, and it should be.** `check_protocol` reads `commits:` only to collect shas;
it does not reject `[]`, does not require `commits_why:` beside a `[none]`, and does not check that a
qualifier matches the entry's `repo:`. Those three are conventions in this file and nothing enforces
them — which by this estate's own rule (*A CHECK THAT DOES NOT BLOCK IS NOT ENFORCEMENT*) means they
will be broken. They are named here so the gap is a known debt rather than a surprise.

Then the body, in this order, because it is the order that makes a claim checkable:

* **WHAT FORCED IT** — the measurement, the failure, the operator's words. Not "we decided to"; the
  thing that made deciding necessary.
* **EVIDENCE** — the command and its ACTUAL output, or `file:line`. A claim without one is an opinion.
* **WHAT CHANGED** — files, commits, gates, numbers before and after.
* **WHAT IT DOES NOT PROVE** — the honest boundary. This field is why the record is worth keeping.

## ENFORCEMENT — why `commits:` is not optional

The operator's diagnosis of working without this: *"the downside is that no ruling remains what we
did and why and what is requested and expected functionality."*

A protocol nobody is obliged to write is a protocol that gets written on good days. So
`check_protocol` measures the thing that matters — **is every code-bearing commit accounted for by
an entry?** — and prints its denominator: commits examined, commits covered, commits orphaned.

It carries a declared FLOOR, like every ratchet here, because it lands red on a history that
predates it. Lower it as the backlog is paid; never raise it. The estate's rule, from
`tools/mac_public_floor.txt`: *"LOWER this number as debt is paid. Never raise it."*

An entry with no `topics:` is invisible to the wiki compiler, so it is counted separately and
reported — coverage without compilation is a record nobody reads.

**The floor is declared against a NAMED RANGE, because the range is the real denominator.**
`check_protocol` takes the revision range from its caller and `protocol_floor.txt` holds one integer,
so the same tree measures 9 orphans over `HEAD~25..HEAD` and 24 over the gate's own default
`HEAD~40..HEAD`. A floor set high enough for the widest range is silent headroom at every narrower
one — the precise defect `2026-09-13/059` records, where 146 was declared while the count had fallen
to 4. So the floor is declared at the tightest measured number, the range it was measured over is
written beside it, and a wider range is expected to go RED over debt that is real.

### The one edit this record has ever taken, and why

Entries are append-only; this paragraph exists because 49 of them were amended anyway. `commits:`
was added to the contract AFTER those entries were written, by agents that had read an earlier
version of this file, so `check_protocol` reported *0 covered, 29 orphaned over 49 entries* — a
narrative accounting for nothing. The backfill added one `commits:` line to each entry's FRONT
MATTER and touched no body, no measurement and no wording. It was reconstructed from each entry's own
EVIDENCE section, which already named its commits (`git show -s 439f41e`), so the attribution is the
entry's own claim rather than a later guess; every bare sha was verified to resolve in this
repository and abbreviate to exactly the cited form, and every qualified sha to NOT resolve here.

This is the only licensed amendment class: a field the contract gained later, applied mechanically,
never touching what an entry says. Anything else is a new entry that supersedes.


## `claims.yaml` — the interpretation layer, beside the record and never inside it

An entry is never edited, so the judgement "this span is the rule" cannot be added to it later.
`protocol/claims.yaml` holds that judgement as an ADDRESS and a ROLE (`rule` or `boundary`), points
into the entry, and carries no prose of its own. `tools/mac_wiki.py` compiles the marked spans to
the top of the topic page, verbatim, and prints how many entries carry a mark. Nothing is ratified
by writing a claim: an agent may only propose, so every claim renders as UNRATIFIED until the
operator sets `ratified: true`.

## The rule that makes it worth having

Write the entry WHEN THE WORK HAPPENS, not at the end of the day. A protocol reconstructed from
memory is a summary, and a summary is exactly what the verbatim rule exists to prevent.
