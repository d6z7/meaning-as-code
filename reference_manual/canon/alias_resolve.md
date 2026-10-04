---
title: "Canon — alias_resolve"
part_of: reference_manual/canon
status: SHIPPED — implemented in mac-runtime (`canons/alias_resolve.py`) and honoured today; no bundle in the estate declares it yet, which is a separate fact and was conflated with this one
scope: GENERIC — domain-neutral
---

# Canon — `mac.canon.alias_resolve`

## Serves

The [`competing_definitions`](../patterns/competing_definitions.md) pattern — one surface word,
several defensible meanings.

## Contract

Resolve a surface token to a canonical value code, in tiers:

1. **scope-relative** — the meaning valid in the current scope
2. **multilingual** — the same member's surfaces in other languages

**Guarantee:** more than one hit, or a token unknown in a **closed** set, produces an **ASK** —
never a silent pick.

## How it differs from `resolve_by_register`

| | `resolve_by_register` | `alias_resolve` |
|---|---|---|
| matches against | register columns named by `search` | tiered alias blocks, scope-relative first |
| several hits | binds **all** the codes | **ASKS** |
| serves | name → code | one word, several **meanings** |

The difference is what several hits *mean*. Five countries under `Europe` is a **set** and binding
all five is right. Two meanings of *"revenue"* is an **ambiguity** and binding both is wrong.

## Limits

- **Not implemented**, and nothing in the estate declares it.
- Overlaps [`ambiguity_gate`](ambiguity_gate.md), which is the ASK half without the tiered lookup.
  If either is built, decide first whether they are one canon.
