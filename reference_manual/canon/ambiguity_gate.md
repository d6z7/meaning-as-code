---
title: "Canon — ambiguity_gate"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `ambiguity_gate`

> A **decision** canon realizing `mac.rule_kind.ambiguity`: it *detects* ambiguity deterministically and
> returns either `RESOLVE(candidate)` or `ASK(options)` (the ⊥ / abstain outcome). **Detecting** ambiguity
> is mechanical; **choosing** among the options is interpretation — so the gate draws exactly the
> determinism border. Single-homed here.

## Serves

The [`competing_definitions`](../patterns/competing_definitions.md) pattern — and any concept where a term
resolves to several named candidate definitions and the system must ask rather than guess.

## Contract (the pluggable interface)

- **Signature:** `ambiguity_gate(term, *, candidates, pinned=None) -> Decision`
- **Params:** `candidates` (the named competing definitions), `pinned` (a candidate the question explicitly
  selected, if any).
- **Guarantee:** returns `RESOLVE(chosen)` when the question pinned a valid candidate **or** exactly one
  candidate exists; otherwise returns `ASK(candidates)` — it **never picks** among >1 unpinned candidates.
- **Returns:** a `Decision` (`action` ∈ {`resolve`, `ask`}, `chosen`, `options`).

## Reference implementation

```python
from dataclasses import dataclass

CANON = "ambiguity_gate"

@dataclass
class Decision:
    action: str            # "resolve" | "ask"
    chosen: str | None
    options: list[str]

def ambiguity_gate(term, *, candidates: list[str], pinned: str | None = None) -> Decision:
    """Deterministic ambiguity detection for competing_definitions.
    Resolve iff the question pinned a valid candidate, or exactly one candidate exists.
    Otherwise (0 or >1, unpinned) → ASK. Detecting ambiguity is mechanical; CHOOSING is interpretation."""
    if pinned and pinned in candidates:
        return Decision("resolve", pinned, candidates)
    if len(candidates) == 1:
        return Decision("resolve", candidates[0], candidates)
    return Decision("ask", None, candidates)
```

## How a concept plugs in

```yaml
realized_by:
  udf: ambiguity_gate
  params: { term: Europe, candidates: [continent_europe, eu_members, eu_sales_region] }
```

## Demonstration

```python
ambiguity_gate("Europe", candidates=["continent_europe", "eu_members", "eu_sales_region"])
# → Decision(action="ask", chosen=None, options=[...3...])         # >1 candidate, unpinned → ASK

ambiguity_gate("Europe", candidates=["continent_europe", "eu_members", "eu_sales_region"],
               pinned="eu_members")
# → Decision(action="resolve", chosen="eu_members", options=[...]) # the question pinned one → RESOLVE

ambiguity_gate("DACH", candidates=["dach_region"])
# → Decision(action="resolve", chosen="dach_region", options=[...])# exactly one candidate → RESOLVE
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic detection** — same `(candidates, pinned)` → same decision; the ⊥/ask outcome is a defined
  return value, not a failure.
- **Detects, does not resolve** — turning `ASK` into a chosen candidate is the human/agent step (the
  prose-fallback). Determining whether the question *pinned* a candidate is itself upstream interpretation.
- **Does not rank** candidates or apply a "house default". Reference, not finished.
