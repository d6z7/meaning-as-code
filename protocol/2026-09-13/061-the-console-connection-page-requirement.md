---
when: 2026-09-13T09:51:04
what: recorded the operator's requirement that the console's Connection page be driven by what the connector declares, and measured that it is a refactor rather than a rewrite
topics: [connectors, console, capabilities]
kind: decision
track: platform
repo: meaning-as-code
commits: [b20c49a]
---

## WHAT FORCED IT

The operator, verbatim:

> "currently there is a page in console 'connection'. i think this should be integrated/refactored to
> show the new functionality about connection configuration. so what is connector and all the details
> around it."
>
> "and button test connection should also be present on this page"

## EVIDENCE

`decisions/REQ-2026-09-13_console-connection-page.md`. The defect, measured: `ConnectionView.jsx`
(259 lines) hardcodes **thirteen fields of one engine** — Engine, Region, Account, Workgroup, Output
location, Catalog, View database, View schema, two Glue database groups, and two credential fields.

> That is the same defect the connector architecture exists to remove, one layer up. The grammar is
> being made to describe the connection *envelope* without knowing what any engine is; the console
> must not then know. A second engine — already in this estate — would render as eleven empty rows
> and two that mean nothing.

The refactor claim is measured line by line rather than asserted: `Field` and `Section` are
**KEEP VERBATIM** (already data-driven, know no engine), the identity card, load/refresh/error
handling and the card shell are KEEP, one helper joining one engine's field shape is DELETE, and the
13 hardcoded call sites (~50 lines) are REPLACE with a loop. **Around 200 of 259 lines survive.**

## WHAT CHANGED

The requirement is tracked, PROPOSED, as an addendum to the connector record, with six numbered
requirements. The two that constrain behaviour rather than layout:

* **Show the tier, not a boolean** — `declared` (a connector is named), `resolvable` (installed,
  config valid, credentials resolve; offline and free), `reachable` (the source answered; **costs
  money**).
* **A "Test connection" button is the ONLY way the `reachable` probe ever runs.** Never on page load,
  never on mount, never on a refresh. The estate's standing rule is that nothing reaches a billed
  service unprompted, and a page that probes when opened would break it every time someone clicked a
  tab.

Acceptance is stated as observable outcomes: two bundles on different engines render correctly **with
no console change between them** — if the console needs an edit to show a second engine, the seam is
in the wrong place — opening the page performs ZERO billed calls, provable by inspection of the
network trace, and a bundle naming an uninstalled connector shows *could-not-run*, not an error and
not a blank page.

## WHAT IT DOES NOT PROVE

`~200 of 259 lines survive` is a reading of the file, not a diff of a refactor that has happened. The
page also states it is "read-only … no secrets are stored here"; that is correct today and the
requirement says it must STAY true, which is a promise about a page nobody has written yet.
