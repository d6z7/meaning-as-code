# QUALITY.md — the pre-offer change checklist for MAC

Quality over speed. Before a change to this framework is offered as **ready for review**, every point
below must be satisfied and reported item-by-item. This list is **maintained and append-only** — when a
new failure mode is found, a new point is added here (do not delete points; supersede with a note).

> Scope: changes to the MAC framework (`mac.schema.json`, the `tools/`, the conformance/design docs, the
> worked examples). The companion to [RELEASING.md](RELEASING.md) (the release procedure) and
> [CONFORMANCE.md](CONFORMANCE.md) (what conformance means). RELEASING covers tag/push; this covers the
> change itself, *before* any release is even discussed.

**Working mode — co-develop with the applied instance.** When a change is driven by an applied ontology,
keep the feature branch open as a long-lived integration branch: applied-instance work
keeps surfacing new framework requirements (point 7), each of which re-runs this whole checklist. Don't
push per-finding — accumulate, re-gate locally, and push **once** when the applied instance has stabilized
against the change. The framework branch and the applied-instance migration that exercises it move together.

## The checklist

1. **Both worked examples.** Apply the FULL change to **shop AND tpch**. A construct exercised in only
   one example is not done — both must carry it (and, where it adds value, exercise different facets, e.g.
   shop demonstrates `kind: raw_source`, tpch additionally `kind: dataset`).

2. **Projections regenerated on both examples.** Every projector affected by the change is re-run for
   **both** examples and the outputs committed — including any NEW projector. The examples must *show* the
   change in `projections/`; a change that adds a construct but leaves the example projections stale or
   missing is incomplete. (This point exists because the data-plane transform construct first shipped with
   no lineage projection in the examples.) **Rendered companions:** when a Mermaid renderer (`mmdc`) is
   available, emit the `.svg` next to each `.mmd` so reviewers see the picture without a toolchain; when
   absent, skip gracefully (the `.mmd` is the source of truth and renders inline on GitHub).

3. **Version bumped atomically — if the change warrants it.** A new `$def`, a new/changed key, a changed
   enum, or a promotion bumps `schema_version`. Then it must move **everywhere, in lockstep** (per
   [RELEASING.md](RELEASING.md)): schema `title` + `$comment`, `tools/validate_schema.py` `CURRENT`/`RECOGNIZED`,
   **every** model file's `metadata.schema_version` (repo-wide sweep), `mac_vocabulary.yaml`, a new
   `CONFORMANCE.md` changelog entry, and version-stating prose in `README.md`/`FRAMEWORK.md`. Verify a
   single version value remains (`grep -rho "schema_version: *'[^']*'" example_*_ontology | sort -u`).

4. **All gates green on both examples, plus the test suites.** structural (`validate_schema.py`) ·
   referential (`check_references.py`) · constraint (`check_shapes.py`) for shop AND tpch, then
   `tests/test_negative.py` + `tests/test_layout.py`. **Any new closed vocabulary (a new enum / required
   key / file type) gets a matching negative fixture** proving the gate rejects violations.

5. **Docs reflect the change; nothing stale.** `CONFORMANCE.md` and the relevant `design/` docs are
   updated, and any statement the change contradicts is corrected (e.g. a doc line that said the new files
   are "not gate-scanned"). Tool docstrings updated where routing/behaviour changed.

6. **Cross-projector impact.** A change to `mac.schema.json` or to ONE projector can silently shift
   another. After the change, **regenerate ALL projections** (every projector, both examples) and `git
   diff` — only the intended outputs may change; any other projector whose output moved must be explained
   or fixed. The structural reason is not enough on its own: prove it empirically.

7. **Validate on an applied instance, not only the examples.** Before a change is pushable, exercise it on
   a real applied ontology (a production deployment, not a toy example): regenerate its projections and run its gates against the
   changed framework. The worked examples are small and friendly; the applied instance is where omissions
   surface (incomplete `inputs[]`, scale, real impurities).

8. **Offer as "ready for review" and WAIT.** Present a per-item PASS/GAP status for this checklist, then
   stop. Do not proceed past review on your own.

9. **Never offer to push, tag, or release.** The maintainer initiates push and release themselves, once
   satisfied. Stop at "ready for review."

## How to report

When offering a change, render this checklist as a status table (✅ / ❌ per point) with one line of
evidence each, and call out every ❌ explicitly. A change with any ❌ is **not** ready for review.
