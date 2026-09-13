---
when: 2026-09-13T10:58:29
what: repaired the gate harness so it can tell a gate that implements its declared reject classes from one that does not, and proved it with a two-arm discriminator
topics: [harness, gates, denominators]
kind: defect
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

STAGE A0. `sdk/gate/contract.py` is the harness under every gate in this estate, and it **could not
attribute a finding to a reject class.** `Outcome` had no class field and the mutant assertion was
merely `if out.clean: fail` — so a gate declaring THREE reject classes and implementing ONE scored
full marks. Every mutant tripped the one class it did implement, and the harness could not tell.

**Every mutant table in the connector record was an unverified claim until this was fixed**, which is
why it lands first and alone.

## EVIDENCE

`git show -s b780b48` (meaning-as-code). THE PROOF IS ONE FILE AGAINST TWO HARNESSES —
`demo_wrong_gate` declares three classes and implements none of them properly:

```
old harness:  PASS: demo-gate self-test — 7/7   exit 0
new harness:  FAIL: demo-gate self-test — 12 of 33 assertions failed   exit 1
```

and the failure text NAMES each defect: must_pass fixtures rejected; "attributed NO class — a finding
of the wrong kind is not coverage for this class" (x3); "main() exited 1, expected 0" and "the
verdict does not disclose ..." (x5); "established 0 of 2 claimed" for no-op extras.

**THE CONTROL ARM IS WHAT MAKES IT A DISCRIMINATOR RATHER THAN A STRICTER RULE.** `demo_right_gate`
passes 35/35. It IMPORTS the wrong gate's declaration table — the same clean fixture, the same mutant
seeders, asserted by OBJECT IDENTITY in `test_the_two_arms_declare_the_same_classes` — so the two
arms differ in `run()` alone. A harness that failed everything would also fail the wrong gate and be
useless; this one separates them.

## WHAT CHANGED

Additive: `Outcome.classes`, `Outcome.secondary`, `GateContract.must_pass`, `GateContract.expect_line`,
and `extra` returning `(checked, total)`. The nine existing gate self-tests are unchanged and still
pass.

## WHAT IT DOES NOT PROVE

Nine existing self-tests passing unchanged means those nine were not re-scored against the new
assertion — they predate `classes`, so what the repaired harness proves about them is exactly what
the old one did. The discriminator is proved on two purpose-built arms, not on the estate's real
gates, and the estate-wide census measured the day before (`2026-09-12/009`) still stands: 29 of 41
gates have no self-test at all, and a harness cannot grade a test nobody wrote.
