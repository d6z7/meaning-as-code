---
when: 2026-09-12T18:01:56
what: made the grain gate deterministic, then discovered its 62 findings were 7 once parse failures stopped being counted as grain errors
topics: [gates, denominators, harness]
kind: measurement
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

The gate did not return the same verdict twice. Same commit, same input, different answer depending
on the interpreter's hash seed:

```
PYTHONHASHSEED=2          62 narrower-key collapses
PYTHONHASHSEED=0/1/3/7/11 66
```

`rels_in()` is annotated `-> set[str]` and the gate built a list from it and took element `[0]`.
String set iteration order is hash-seeded, so both the count and WHICH relation got blamed moved
between runs. A gate whose number changes cannot be ratcheted, cited in a record, or used as an
admission criterion — and this one had been cited in both.

Once the denominator was printed, the real defect appeared:

```
FAIL: ... 62 collapse(s) use a key NARROWER than the declared cell key
          over 11 collapse(s) examined
```

A numerator five times its denominator.

## EVIDENCE

`git show -s 9c63129 23758da` (meaning-as-code). 55 of the 62 were properties whose SQL never parsed,
appended to the same findings list with the same severity and reported under the narrower-key
sentence. Separated:

```
 7 narrower    over  11 collapse(s) examined
55 unreadable  over 293 propert(ies) attempted
```

> So the grain defect this gate exists to find is SEVEN, not sixty-two. Every review that quoted 62 as
> grain errors — including this estate's own records — inherited the conflation, and the "89% of SQL
> it cannot parse" framing was measuring the other population entirely.

The two cannot share a denominator: a collapse using a narrower key DOUBLE-COUNTS and the gate knows
which; a property whose SQL cannot be parsed is UNKNOWN. Both block, and they are now reported on one
line so neither can be quoted without the other.

`self-test 9/9 · framework tests pass · the same verdict under five hash seeds`, run in subprocesses
because `PYTHONHASHSEED` is fixed at interpreter start.

The worst pre-existing state is quoted in the commit: `✓ OK — no relation carries a measured key yet;
nothing to check`, exit 0, whose own adjacent text admitted the gate "went green by losing its
subject once already". That, a missing acceptance plane, a non-directory root, and zero collapses
landing on a declared key are all exit 2 now.

## WHAT CHANGED

Sorted iteration; a `PASS:`/`FAIL:` line where there had been a glyph (`grep -cE '^(PASS|FAIL):'`
over a full run returned 0 before); a printed denominator; and `--self-test` at 9/9 with four reject
classes, four assertions that each fixture really seeded its class, and the same verdict under five
seeds.

## WHAT IT DOES NOT PROVE

RECORDED, NOT FIXED, in the commit itself: a `GROUP BY` is only read as a grain claim when `HAVING`
references the COUNT's ALIAS. The idiomatic `HAVING COUNT(*) > 1` carries no Column node, so the test
cannot match.

```
HAVING <alias> <op>    4 propert(ies)  detected today
HAVING COUNT(*) <op>  16 propert(ies)  INVISIBLE today
```

The gate sees 4 of 20 uniqueness claims. Widening it is a behaviour change that would move the 7, so
it belongs in a deliberate step with a re-baselined ratchet. The gap surfaced only because the first
fixtures used the undetected form and every case came back "could not run".
