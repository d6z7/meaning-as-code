---
when: 2026-09-13T09:44:20
what: took the public-hygiene count to zero and made zero the contract, after a verifier found four regressions the cleanse agents had introduced and reported clean
topics: [the-public-boundary, registers, ratchets, gates, denominators]
kind: defect
track: core
repo: meaning-as-code
commits: [b20c49a]
---

## WHAT FORCED IT

Ten agents over disjoint file sets, then an INDEPENDENT VERIFIER that measured rather than trusting
their self-reports. Every remaining token was from ONE instance; five other bundles measured zero
before this started.

And the floor was a ratchet in name only:

> 146 was measured after the first pass and nobody lowered it while the count fell to 4 — **141
> findings of silent headroom** in the instrument that keeps this estate's identity out of a public
> repository. The gate now reports its own slack, and prints its witnesses on the at-or-below-floor
> branch: it used to print the count alone, so the debt the floor exists to expose was the one thing
> it hid.

## EVIDENCE

`git show -s b20c49a` (meaning-as-code), 39 files.

```
check_mac_public   300 -> 146 -> 0 leak(s) over 487 tracked file(s)
pytest sdk                   88 passed
SDK gate self-tests           9 / 9
run_framework_gates  tpch    30 / 34   (baseline — unchanged)
run_framework_gates  shop    30 / 34   (baseline — unchanged)
```

**THE VERIFIER FOUND FOUR REGRESSIONS.** All four are fixed and re-verified, and all four were
introduced by the cleanse:

> * A BROKEN WIRE. A key was renamed in the CONSUMER (`tools/mac_to_meta.py`) and not the PRODUCER
>   (`tools/project_model.py`), so **every row's identity column silently became null.** Reverted and
>   proved end-to-end. The register rule that drove it is REMOVED with its reason recorded in place:
>   the key is a generic data key naming no brand, source or customer. It was listed because the
>   register began as "every string appearing in one bundle", which is a wider and different question
>   from "every string identifying it". **A denylist entry that forces the rename of a generic
>   identifier is a defect in the denylist.**
> * A SECOND HOME. A constant named the conformance flows separately from the golden file that
>   already declares them, and the two could disagree. They did: one entry became a string no relation
>   can equal, and the mismatch answered `[SKIP] ... not in golden` while leaving `ok=True`.
> * A BROKEN PATH: a default root became prose substituted into a filesystem path.
> * DEAD MATCH ENTRIES. A parameter-order table is matched against real column names; four
>   angle-bracket placeholders can never equal one, so those parameters fell silently into the
>   alphabetical tail.

Two self-inflicted faults are recorded again here because they recurred: an English word that is also
a live identifier was renamed by a word-boundary rule, and the sweep rewrote the gate's own detection
regexes — caught by its self-test within the minute.

## WHAT CHANGED

`tools/mac_public_floor.txt` reads `0`, with the reasoning written into the file:

> ZERO IS NOW THE CONTRACT. Any new finding fails the gate, which is the point: this is a PUBLIC
> repository and the instrument that keeps an estate's identity out of it should have no tolerance
> left to spend. If a genuine, reviewed use needs a token, the per-line escape hatch exists and is
> visible in the diff — raising this number is not the answer.

## WHAT IT DOES NOT PROVE

Four of the four regressions were found by a verifier, not by a gate — and one of them nulled a
production column while every agent that touched it reported success. So the honest claim is: **ten
agents self-reported clean and were wrong four times.** A parallel sweep without an independent
measurement pass is not a cleanse; it is ten unverified claims.

Zero is also zero AGAINST A GITIGNORED REGISTER of seventeen patterns. A token nobody has thought to
declare is not a finding, and the gate cannot tell you that.
