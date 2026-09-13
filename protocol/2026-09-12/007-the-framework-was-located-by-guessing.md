---
when: 2026-09-12T13:40:04
what: replaced the sibling-directory guess for the framework with declaration-driven resolution, and gated the case where the vendored fork wins
topics: [grammar, consolidation, gates]
kind: defect
track: core
repo: mac-platform
---

## WHAT FORCED IT

The SDK lived in a different repository from the grammar it validates against, so it located that
repository by guessing a sibling checkout. The guess broke when the packages layout absorbed the SDK,
and when it broke the resolver fell through IN SILENCE to a vendored copy of the schema.

Measured on the branch before changing anything (`git show -s 8cc3112`, mac-platform):

```
FRAMEWORK guess   packages/mac-sdk/meaning-as-code/mac.schema.json   absent
resolved to       sdk/grammar/mac.schema.json                        the fork
$defs in use      25                                                 (37 real)

reference concepts failing under the FORK       22 / 22
reference concepts failing under the FRAMEWORK   0 / 22
```

So the authoring path could not validate the bundle it had itself produced, and nothing told anyone
which schema had judged it.

## EVIDENCE

Two commits, one act. `5921a3b` (13:40) fixed the same class in `harvest.py`'s `_MAC_TOOLS` and is
explicit that the morning's earlier fix was not a fix:

> This morning's fix replaced a broken guess with a better guess; it was still a guess, and it broke
> again the moment a real install cloned the framework under a different directory name.

Verified on both layouts: `this machine -> <estate>/meaning-as-code/tools` and
`renamed estate -> <estate>/lang-core/tools`, compiler present in both.

`8cc3112` (18:05) fixed `resolve.py` the same way and added the gate, because a warning is not a
refusal: `check_grammar_home` reds when the shipped copy of the standard is in force, or when the
resolved grammar falls under a `$defs` floor. `Self-test 3/3 · run_gates 9/9 with $MEANING_AS_CODE set`.

## WHAT CHANGED

Resolution is by DECLARATION and nothing about it is positional: `$MEANING_AS_CODE`, then the
packaged `meaning_as_code.framework_root()` — identical in a checkout and in a wheel. That resolver
is deliberately NOT wrapped in try/except: catching it converts the framework's loud failure into a
silent wrong answer, which is the defect the resolver exists to prevent.

The fork itself was NOT deleted here. Operator ruling R4 withheld deletion authority; its five
importers were repointed instead, and the gate makes "inert" checkable rather than hoped for.

## WHAT IT DOES NOT PROVE

That one grammar governs. Two grammars still existed in the estate on this date, one of them inert by
measurement and by gate. Structural impossibility arrived only with the consolidation on
`2026-09-13/053`, which deleted the fork outright.
