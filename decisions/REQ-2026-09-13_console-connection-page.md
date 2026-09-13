# REQUIREMENT — the console's Connection page, under the connector model

**Status:** PROPOSED. Operator-stated, 2026-09-13. Feeds
`PROPOSED-2026-09-13_connector-plugin-architecture.md`; that spec did not cover the UI.

> "currently there is a page in console 'connection'. i think this should be integrated/refactored to
> show the new functionality about connection configuration. so what is connector and all the details
> around it."
>
> "and button test connection should also be present on this page"

## The defect, measured

`packages/mac-console/.../views/ConnectionView.jsx` (259 lines) hardcodes **thirteen fields of one
engine**: Engine, Region, Account, Workgroup, Output location, Catalog, View database, View schema,
Glue databases (Fact / Dimensions), Credentials (Mode, handle).

That is the same defect the connector architecture exists to remove, one layer up. The grammar is
being made to describe the connection *envelope* without knowing what any engine is; the console
must not then know. A second engine — DuckDB, already in this estate — would render as eleven empty
rows and two that mean nothing.

The page also states it is "read-only … no secrets are stored here", which is correct and must stay
true.

## Required

1. **The connector describes its own display.** The page renders the fields the connector declares,
   in the groups the connector declares, with the labels the connector supplies. The console learns
   nothing about any engine. A connector that declares three fields renders three rows.

2. **Show the connector itself**, which the page cannot show today:
   - which connector is named, and its version
   - first-party (`mac.connector.*`, framework canon) or third-party (any other namespace)
   - whether it is **installed on this host** — a bundle may name a connector nobody has

3. **Show the tier, not a boolean.** The page should state which of the three the connection has
   reached, because they mean different things:
   - `declared` — a connector is named
   - `resolvable` — installed, config valid, credentials resolve. **Offline and free.**
   - `reachable` — the source answered. **Costs money.**

4. **A "Test connection" button** — the `reachable` probe, and the ONLY way it ever runs. Never on
   page load, never on mount, never on a refresh. The estate's standing rule is that nothing reaches
   a billed service unprompted, and a page that probes when opened would break it every time someone
   clicked a tab.

5. **The probe result carries its timestamp.** A connection that answered an hour ago is evidence,
   not a guarantee, and the page must not let a stale green read as a live one.

6. **Secrets never render.** Handles only, as today. Whatever a connector declares for display is
   subject to the same redaction, and a connector cannot opt out of it.

## This is a REFACTOR, not a rewrite — measured

The operator's ruling: recycle the page. That is the right call and the file supports it better than
its hardcoded body suggests. `ConnectionView.jsx` is 259 lines; the parts that survive are the parts
that were already generic:

| part | lines | verdict |
|---|---|---|
| `Field({label, value, hint, mono})` | ~20 | **KEEP VERBATIM** — already data-driven, knows no engine |
| `Section({label, children})` | ~14 | **KEEP VERBATIM** — a labelled 2-column definition grid |
| identity card (domain / dataset) | ~45 | **KEEP** — connector-agnostic |
| load / refresh / loading / error | ~40 | **KEEP** |
| card shell, headers, copy | ~30 | **KEEP** — including "read-only … no secrets are stored here", which stays true |
| `dimsValue()` — joins `glue_databases.dims` | ~10 | **DELETE** — one engine's field shape |
| the 13 hardcoded `<Field>` call sites | ~50 | **REPLACE** with a loop over what the connector declares |

So the presentational primitives were always right — `Field` takes a label and a value and renders
them. The defect is entirely in the CALL SITES, which name one engine's fields in fixed order. The
refactor replaces roughly 50 lines with a map, and adds the connector identity block, the tier
indicator and the Test-connection button.

Around 200 of 259 lines survive. This is not a rewrite, and the page's visual language does not
change — a reader who knows it today will recognise it.

## Acceptance

* A DuckDB bundle and an Athena bundle both render correctly **with no console change between them**.
  If the console needs an edit to show a second engine, the seam is in the wrong place.
* Opening the page performs **zero** billed calls. Provable by inspection of the network trace.
* A bundle naming an uninstalled connector shows *could-not-run*, not an error and not a blank page.
