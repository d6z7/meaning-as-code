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
commits: [b780b48, efac30b]                      # what this entry accounts for — see ENFORCEMENT
supersedes: 2026-09-12/004-slug                  # optional
---
```

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

Then the body, in this order, because it is the order that makes a claim checkable:

* **WHAT FORCED IT** — the measurement, the failure, the operator's words. Not "we decided to"; the
  thing that made deciding necessary.
* **EVIDENCE** — the command and its ACTUAL output, or `file:line`. A claim without one is an opinion.
* **WHAT CHANGED** — files, commits, gates, numbers before and after.
* **WHAT IT DOES NOT PROVE** — the honest boundary. This field is why the record is worth keeping.

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
