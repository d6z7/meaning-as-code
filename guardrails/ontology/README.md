# guardrails/ontology/ — the ontology plane's rules.

`concepts.yaml` — the AUTHORED semantic model: concept definitions, the rules they bind, the edges
they join by, and the sample that proves each concept returns something real.

**WHAT CHANGED, 2026-09-29.** This directory was empty, deliberately, and the note here said so:
under UNSPECIFIED IS NOT RULED an empty directory meant the ontology plane was unruled and writing
to it was allowed — a statement rather than an oversight. It is no longer true. Twelve checkers
already governed this plane and no declaration named any of them, so what they rejected was
reachable only by reading their source.

**AND THE FILE COULD NOT BE WRITTEN.** The ontology guard denied it `gate_unreachable`: the path
holds `/ontology/` and no bundle manifest sits above it, so the rules that GOVERN the ontology plane
were blocked by the guard that protects it — the third time that guard has blocked its own
mechanism, and its own note on the first two reads "a guard that makes its own mechanism unfixable
protects nothing and costs a day".

The fix is `_is_guardrail_tree` in the kit: a POSITIVE identification, two conditions, neither
sufficient alone — `/guardrails/ontology/` under a root carrying `mac.schema.json`. Measured over
all twelve `ontology` directories in this estate, exactly one is exempt; the framework's own
a bundle's nested `ontology/` stays protected, which is why a root test alone would not do. The
operator installed it, because an agent that can edit a gate has no gate.

**WHAT IS STILL NOT RULED HERE.** The derived half of the plane — `<bundle>/ontology/vocabulary.json`, `<bundle>/ontology/edges.json`,
an ontology-quality report, an SME-questions page — and `ontology_conformance_suite`, which is still filed
under `unfiled.yaml` with `belongs_to: ontology` awaiting its move. Absence from this directory is
still permission, not oversight.
