---
when: 2026-09-12T12:57:53
what: put a genericity gate on the method repo itself and cleaned the 47 machine-local facts it had been copying onto every machine
topics: [the-public-boundary, gates, registers, method]
kind: build
track: core
repo: mac-integration-kit
commits: [mac-integration-kit:3ea9172]
---

## WHAT FORCED IT

Every consuming repo receives a PROJECTION of the method repo, so a local fact there is copied onto
every machine that installs the method. The downstream product repo enforced domain neutrality; the
upstream method enforced nothing — which is how `/Users/<someone>/dev/...` came to sit inside
`ontology/planes/serving.md` as a "Good example", fifteen times.

## EVIDENCE

`git show -s 3ea9172` (mac-integration-kit):

> MEASURED: 47 findings in 11 files, every one undercounted by hand greps
>   29 domain-identifier · 15 absolute-home-path · 2 cloud-account · 1 hardcoded-estate-root
>   serving.md was grepped as 5 sites and held 15; a grep on `gaps` claimed "13 files" of which most
>   were the ENGLISH PLURAL ("22 gaps", "minor gaps", "nulls read as gaps").

`run_gates.sh: 8 gates -> 10, PASS 10/10.`

## WHAT CHANGED

All 47 fixed using the placeholder style those documents already used (`<the program>`, `<a source>`,
`<reference-bundle>`): `/Users/<user>/dev/` became `<estate>/`, `~/dev/` became `$MAC_ESTATE_ROOT/`,
brand and region codes became `<domain>/<bundle>/<brand-A>/...`. Three STALE agent names in
`knowledge-base.json` were corrected on the way — they had been renamed off a source prefix and the
knowledge base still cited the old ones.

**The division of labour is the reusable part.** The first version of this gate also checked domain
identifiers and account ids, and the sibling doc gate immediately failed it, because a denylist has
to spell out the terms its sibling forbids. This gate was narrowed to the half nothing else watches —
facts local to a MACHINE, not to a customer. Its operator-handle mutant is assembled from string
parts so the file carries no such id itself.

The decision record was deliberately NOT rewritten. An ADR is the signed history of what was decided
when; editing it to satisfy a later gate falsifies the record. It is allowlisted with that reason —
grandfathered, not licensed.

## WHAT IT DOES NOT PROVE

That the method is generic. It proves 47 machine-local facts are gone and that a gate now watches
that class. The domain-identifier class is watched by a DIFFERENT gate reading a gitignored register,
so on a fresh clone with no register that half is weaker — stated here because the gate cannot state
it for you.
