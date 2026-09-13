---
when: 2026-09-13T10:58:29
what: fixed a live unbound name in the authoring path that could never fire, and landed a two-unit engine-coupling ratchet that measures what a module-level import scan cannot see
topics: [connectors, gates, ratchets, denominators, harness]
kind: defect
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

STAGE A1, both halves.

**THE CRASH.** `workgroup` was an UNBOUND NAME in `data_plane.process()` — a live NameError on the
line calling `profile_table`. It never fired because the path above it is dead in this repo, which is
exactly why nothing caught it.

**THE MEASUREMENT NOBODY HAD.** Four import-shaped reject classes would one day have printed `4 -> 0`,
and that zero would have been quoted as "MAC no longer knows the warehouse".

## EVIDENCE

`git show -s efac30b` (meaning-as-code), and re-run on this tree:

```
$ python3 sdk/gate/check_engine_coupling.py
FAIL: engine-coupling — 7 violation(s) over 130 tracked .py file(s) examined, 83 instrument file(s)
      judged for an engine noun — floor set of 4 path(s) carrying 7 driver coupling(s)
      — 0 module-level, 7 function-local, 0 shell-out, 0 dynamic, 0 relocated
      — SECOND UNIT: 17 file(s) carry an engine noun (string literal / prompt / persisted key) over
        83 instrument file(s), noun floor set of 17
      — 18 file(s) exempt (sdk/connector/, sdk/gate/) and never examined; population from git ls-files
```

**ALL of the driver coupling is function-local.** A conventional module-level import scan reports
ZERO and would be quoted as "MAC no longer knows this engine" while seven files construct engine
clients. The record predicted half of it was invisible; measured, it is all of it.

The guard for the crash is GENERAL rather than a check for one name, and the verifier proved that
with three mutations of its own choosing, none involving the fixed name:

> * an unrelated unbound name in `process()` — caught, denominator moved 76 -> 77, so the walk really
>   re-resolves rather than replaying
> * an unbound name inside a COMPREHENSION in a DIFFERENT function — caught; comprehension scope is
>   modelled correctly
> * the caller-side half: delete the kwarg from the call site — caught against the callee's LIVE
>   signature

`Self-test 55/55 with every mutant attributed to its own class — assertable only because A0 landed
first.`

## WHAT CHANGED

`workgroup` is threaded properly from the bundle's connection rather than a default.

Two floors, in two files, each with its own named OWNER and REVIEW BY date, because a floor with
neither is a permanent exemption and the gate refuses to enforce one — exit 2, not a shrug. The owner
is a ROLE rather than a person "because this repository is public and a colleague's name is one of
the things `check_mac_public`'s denylist was built to remove."

**WHY A SET AND NOT A NUMBER**, written into the floor file: the hygiene gate "reads its floor as an
int and passes on `len(hits) <= floor`, so 'lower it, never raise it' is a string in the PASS line
enforced by nobody. A number is identity-blind: remove one driver import, add another elsewhere in
the same commit, and the count never moves." The record's own staging schedules exactly that move.
`coupling-relocated` is the reject class that makes it a finding instead of free progress.

**WHY A STANDING COUNT AS WELL AS A SET**, also measured rather than assumed: compared by set
difference alone the gate reported "1 path added, 0 cleared" for the record's own scheduled
relocation and labelled it `lazy-import-evasion`. It failed — **with the wrong name on it, which for
a ratchet is most of the damage.**

## WHAT IT DOES NOT PROVE

The second unit's 17 files are mostly **deliberately out of scope** for the connector work and are
listed anyway, "because a floor that omits the population it cannot fix is a floor that
under-reports the debt". One of them pins a SQL dialect and is a live correctness defect on its own
axis. And the scan is over file TEXT: a literal-only scan of the same tree reports 13 and calls four
clean, because a function name, a parameter name and a method name carry the engine noun too. Text
matching means false positives are possible; the floor's inline column is where one gets recorded
with its reason rather than argued away.
