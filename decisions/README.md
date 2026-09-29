# decisions/ — the record

Records here are written by agents as `PROPOSED` and ratified by the operator as `RULED` (CORE §3).
A record stays until it is superseded or describes only retired shapes; then it is removed with
`git rm` so history keeps it, and the removal is listed here so a pointer that still names it has
somewhere to land.

## Retired records

| retired | file | why |
|---|---|---|
| 2026-09-29 | `PROPOSED-2026-09-13_testing-strategy.md` | 1 517-line analysis; its two rulings are carried, self-contained, in `RULED-2026-09-13_testing-strategy.md` |
| 2026-09-29 | `PROPOSED-2026-09-24_acceptance-is-the-home.md` | superseded by `PROPOSED-2026-09-25_one-runner-one-home-one-trace.md`, itself retired the same day |
| 2026-09-29 | `PROPOSED-2026-09-24_execution-tracing-and-testing-ux.md` | as above |
| 2026-09-29 | `PROPOSED-2026-09-24_orphan-inventory.md` | as above |
| 2026-09-29 | `PROPOSED-2026-09-25_one-runner-one-home-one-trace.md` | uncited; all five of its targets live in `mac-platform`, not here |
| 2026-09-29 | `PROTOCOL-2026-09-25_session.md` | session log presenting `field_roles` as the authored form; that shape was retired for the column map (`grounding.sources[].columns`) — the durable content is in `DNA-2026-09-25_ontology-design-requirements.md` and `reference_manual/column_specification.md` |

Retained but marked **designed, not enforced**: `PROPOSED-2026-09-13_connector-plugin-architecture.md`
(cited as `RECORD:` by `sdk/connector/` and two `sdk/gate/*_floor.txt` baselines, so it cannot go),
`PROPOSED-2026-09-29_ontology-idiom.md`. `PROPOSED-2026-09-29_delivery-manifest.md` is SUPERSEDED by
`PROPOSED-2026-09-29_guardrails.md`.

Paths inside `DELIVERABLES-*`, `DNA-*` and `PROTOCOL-2026-09-29_guardrails.md` are bundle-relative
(`data/…`, `ontology/…`, `acceptance/…` of an applied ontology), not paths in this repository.
