---
when: 2026-09-13T02:06:33
what: moved the public-hygiene gate's own pattern table out of the public repository, de-instanced the four normative files, and ratcheted the floor 300 -> 146
topics: [the-public-boundary, registers, gates, ratchets]
kind: defect
track: core
repo: meaning-as-code
commits: [aacc1e1]
---

## WHAT FORCED IT

THE WORST INSTANCE. `tools/check_mac_public.py` is the gate that keeps this estate's identity out of
a PUBLIC repository. Its `PATTERNS` table held that identity in full — every brand, the operator's
systems, an infra bucket, a colleague's name — **seventeen patterns, in the public repository.** The
instrument was the densest concentration in the tree of exactly what it scans for.

## EVIDENCE

`git show -s aacc1e1` (meaning-as-code), 50 files.

A DELIMITER BUG, caught on the way, in the fix itself:

> the register splits `label | regex | flags`, and a naive 3-way split silently DROPPED every pattern
> containing regex alternation — three brand patterns among them. It now splits on the first and last
> delimiter only. A gate going quietly blind is the failure mode this whole exercise is about, and it
> nearly shipped inside the fix for it.

TWO SELF-INFLICTED FAULTS, both from blanket substitution, both caught by the gates rather than by
review:

> * one denylisted token is an ENGLISH WORD and a real identifier here. A word-boundary rule renamed
>   identifiers and broke two modules. It is now substituted only where the surrounding syntax makes
>   it a domain reference.
> * the substitution rewrote `check_mac_public`'s own detection REGEXES, so it hunted for the literal
>   `<source>`. Its self-test caught it: "mutant not caught: a token in a tracked file".

```
pytest sdk                   83 passed
SDK gate self-tests           9 / 9
check_mac_public            146 leak(s) over 484 tracked file(s), floor 146
run_framework_gates  tpch    30 / 34   (baseline — unchanged)
run_framework_gates  shop    30 / 34   (baseline — unchanged)
all four registers gitignored, each with a tracked .example
```

## WHAT CHANGED

The gate loads `registers/public_tokens.txt`, gitignored, with an environment override for CI. **With
no register the gate reports COULD NOT RUN and exits 2**: zero patterns means zero examined, and a
tree it did not scan is not a tree it found clean.

THE NORMATIVE FILES matter most and were de-instanced here: the schema, the rules file, the
vocabulary and the shapes file. The diagnostic-code taxonomy in the vocabulary is copied into EVERY
bundle's compile record, so its prose propagates to every consumer — which is how one instance's
names reached an unrelated public example bundle.

42 files under `tools/` were de-instanced the same way: placeholders where a name did no work, a
neutral stand-in where the example's shape carried the lesson, and incidents keeping their lesson
without the name.

## WHAT IT DOES NOT PROVE

146 is not a clean tree; it is a floor with the instruction to lower it. And the floor itself was the
next defect: **nobody lowered it while the count fell to 4**, which left 141 findings of silent
headroom inside the instrument that keeps this estate's identity out of a public repository
(`2026-09-13/059`).
