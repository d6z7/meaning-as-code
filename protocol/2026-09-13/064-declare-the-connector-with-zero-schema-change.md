---
when: 2026-09-13T10:58:44
what: had two served bundles declare which connector they use, proving the declaration is free today by an A/B whose only differences were wall clock
topics: [connectors, containers, grammar]
kind: build
track: ontology
repo: customer-bundle (<domain>/<bundle>)
commits: [customer-bundle:47d5415]
---

## WHAT FORCED IT

STAGE A2 of the connector architecture. A bundle must NAME a connector for any of the rest to be
possible, and the cheapest possible version of that step is the one that changes nothing else.

## EVIDENCE

`git show -s 47d5415` (the customer-bundle repo). Both bundles now declare
`runtime.connector: mac.connector.athena`. Nothing else changes.

> This is free today because `ProjectFile.runtime` is literally `{"type": "object"}` in the grammar —
> no properties, no required, no additionalProperties — so the declaration validates immediately and
> can sit UNREAD for the whole soak period. It is the bundle's only forward commitment, and it is a
> namespaced identifier rather than a shape, so it survives whichever way the open rulings go.

THE NAMED CHECK WAS "validate_schema still green AND the compile verdict BYTE-IDENTICAL", run as a
clean A/B at one frozen framework head, then re-run independently by a verifier:

```
validate_schema.py   output byte-identical, both bundles, raw diff, no normalisation
compile payload      every differing line is WALL CLOCK — generated_at, duration_s, the timings map,
                     per-check duration. 40 differing lines on one bundle, 42 on the other, and
                     nothing else.
canonical payload    identical sha256 and byte count on both arms, verdict and error count unchanged
```

> The verifier diffed the RAW payloads BEFORE stripping anything, precisely so the normaliser could
> not hide a real difference behind a timestamp filter. That is the right order and it is why the
> claim is worth something.

Bundles left exactly as found; no projection was rewritten and no compile record overwritten.

## WHAT CHANGED

One key in each of two project manifests.

## WHAT IT DOES NOT PROVE

"Zero schema change" is true BECAUSE the grammar does not constrain `runtime` at all — the
declaration validates for the same reason any key would. So this proves the declaration is
**harmless**, not that it is **honoured**: nothing reads it, and the point of the soak period is
that nothing should for two calendar weeks. The moment the schema half lands and the tier is wired,
at least one currently-green bundle is expected to turn RED, and that is the intended outcome, not a
regression.
