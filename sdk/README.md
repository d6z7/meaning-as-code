# `sdk/` — the managed authoring framework (build-time, VSC only)

The **only** code that may write the ontology SSOT (`sources/**`). Disallowed operations are not merely discouraged — they are not exposed. See `../decisions/2026-08-12_three-plane-authoring-model.md` and `../boundaries.yaml`.

## Contract
- **May import:** `meaning-as-code` (the pinned grammar), other `sdk/` modules. **Never** `wiki/`.
- **Sole SSOT writer:** `sdk/authoring/operations.py`. No other module (here or anywhere) may write under `sources/**` — enforced by `sdk/gate/check_write_paths.py` (call-graph aware).
- **The harvest emits CANDIDATES only** (`sdk/engine/**` has zero write calls); every persist routes through an allowed op that refuses any object whose validation status ∉ {valid, fixed}.

## Layout (target — populated during Stages 1–4)
```
grammar/    pinned schema + closed vocab (no forked copy of mac.schema.json)
authoring/  operations.py (sole writer) · author_concept.py · data_plane.py · exemplars/
project/    mac_okf · project_data · objects · lineage   (deterministic, read-only over SSOT)
engine/     harvest/ okf_core/ okf_aws/ chat/            (AWS-touching; candidates only)
gate/       check_boundaries · check_write_paths · check_read_paths · check_rule_lock
            ruling_coverage · annotation_isolation · provenance · publish · run_checks.sh
cli/        harvest · project · bless · publish · ingest_signals   (VSC-only entrypoints)
```

## Allowed-operation set (closed)
`scaffold-source · author-source-descriptor · propose-transform · build-served-view · author-concept · classify-measure-type · bind-grounding · declare-edge · add-typed-rule · capture-oracle-from-ruling · bless · publish`. Plane-3 ops (`open/transition/link` annotation) write only `annotations/**` and are a separate ungated class.
