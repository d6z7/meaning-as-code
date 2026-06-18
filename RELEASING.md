# Releasing — one version, bumped everywhere, atomically

MAC has **one version number**. The git tag, the schema, the validator, and every model file carry it,
and they move **together**. A release whose tag does not match the files is a bug (it happened once —
`v0.1.7` was tagged while every file still said `0.1.6`; that release was pulled).

## The invariant

> The release tag **`vX.Y.Z`** ⇔ `mac.schema.json` title `vX.Y.Z` ⇔ `validate_schema.py` `CURRENT = 'X.Y.Z'`
> ⇔ `schema_version: 'X.Y.Z'` in **every** model file ⇔ a `CONFORMANCE.md` entry for `X.Y.Z`.

If any one of these disagrees, do not tag.

## When to bump

- **Any change to `mac.schema.json`** — a new/renamed/removed key, a tightened constraint (e.g. the
  `EdgeEndpoint` rule), a changed enum — **bumps `schema_version`.** The schema's meaning must never change
  silently under a fixed number.
- Tooling-only or docs-only changes (a new projector, a new article) do **not** require a bump on their
  own — but if they ship alongside a schema change, they go out under the bumped number.

## The release procedure (atomic)

1. **Bump the number in lockstep:**
   - `mac.schema.json` — the `title` (`… formal schema vX.Y.Z`).
   - `tools/validate_schema.py` — `CURRENT = 'X.Y.Z'` (and `RECOGNIZED`; keep it **strict** = `{CURRENT}`
     unless a migration grace is explicitly intended and documented).
   - **every** model file's `metadata.schema_version` (the worked examples; a repo-wide sweep).
   - `CONFORMANCE.md` — a changelog entry for `X.Y.Z` (what changed, and any migration note).
   - any prose that states the current version (`README.md` Status, `FRAMEWORK.md` front-matter companions).
2. **Verify** — no file disagrees, and everything still passes:
   ```bash
   grep -rho "schema_version: *'[^']*'" example_*_ontology | sort -u        # expect ONE value == the tag
   grep -m1 "formal schema v" mac.schema.json                               # title == the tag
   grep -n "CURRENT *=" tools/validate_schema.py                            # == the tag
   for ex in example_*_ontology; do bash "$ex/validate.sh"; done            # all gates green
   python3 tests/test_negative.py && python3 tests/test_layout.py
   ```
3. **Tag + release** — only after step 2 is clean:
   ```bash
   git tag -a vX.Y.Z -m "…"; git push origin vX.Y.Z
   gh release create vX.Y.Z --title "…" --notes-file <notes>
   ```

## Downstream applications pin (don't float)

Applications that consume this framework (e.g. a GAPS-style project running `validate_schema.py` from a
sibling clone) must **pin to a framework tag**, not track `main` — otherwise a framework bump silently
changes their gate. Pin by checking out the tag, or set `MEANING_AS_CODE=/path/to/clone@vX.Y.Z`. Migrate
the application deliberately: bump its files' `schema_version` and re-run its gates against the new tag.

## Visualization is part of the model

After any ontology change, the committed `projections/` (incl. the diagram) must be **regenerated**, not
left stale. A model whose picture no longer matches it is a release defect. *(Planned: a
`tools/check_projections.py` freshness gate — regenerate to a temp dir and diff against the committed
`projections/` — wired into `validate.sh`/CI.)*
