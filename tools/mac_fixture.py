#!/usr/bin/env python3
"""
mac_fixture.py — EMIT the two-plane self-test bundle. The framework ships the GENERATOR, never the
instance.

WHY THIS FILE EXISTS, and it is the operator's ruling, not a convenience.

When example_shop_ontology was deleted (2026-10-05) it was the last two-plane bundle in this
repository, and five things resolve a bundle path through one: tests/test_layout.py,
tests/test_mac_model.py, tools/check_seam_contract.py's eight end-to-end cases,
sdk/gate/check_entry_points.py and sdk/gate/run_gates.sh. The replacement was committed as
`tests/fixtures/two_plane_project/` -- and that was the mistake. A committed bundle puts an
`ontology/` directory inside the framework, and the operator's ruling on 2026-10-08 was flat:

    "marker in MAC is absolute NO GO !!!!!  mac is generic framework"

They are right twice over. A generic framework must not ship an INSTANCE; and the moment it does,
the ontology guard classifies that instance as a live meaning plane -- because it identifies a plane
by the literal path segment `/ontology/` and never by `mac.project.yaml` -- so maintaining the
framework's own scaffolding needed an operator unlock inside the framework repository.

MEASURED THAT DAY, which is what makes the ruling more than taste. meaning-as-code held SIXTEEN
directories named `ontology`, FOURTEEN of them carrying concept files, 356 concept files in total:
350 in generated BIRD benchmark bundles, 4 in the authoring exemplar, 2 in the committed fixture.
Not one was meaning anyone had authored about a real business. Meanwhile contoso5 -- the one
authored meaning plane in the estate -- had `.ontology-unlocked` sitting in it since 2026-09-29,
gitignored, so no `git status` and no commit ever surfaced it. The guard was open where meaning was
and closed where it was not.

AND THE OBVIOUS FIX WAS WRONG. The first proposal was to rename the plane: the resolver reads
`planes.ontology: <dirname>` and the name can be anything, so `model/` would have passed. Measured
on one bundle with no marker, same manifest, same content, renaming only the directory:

    ontology/   DENY        model/   ALLOW        semantics/   ALLOW

There is no difference between those three words -- not to the resolver, not in meaning. Renaming
would have bought silence by spelling around a defect, and left a plane that is unprotected for the
same reason it is writable. Withdrawn.

So the bundle is GENERATED into a temp directory, per run, by this file. The framework then holds no
instance at all, there is no `/ontology/` in the tree, no marker is ever needed, and nothing is
being dodged: emitting disposable scaffolding into a temp directory is what
tests/test_mac_model.py's own `build_bundle()` has always done.

THE REFUSAL BELOW IS THE POINT. `emit()` walks up from its destination and REFUSES if it finds a
`.git`, so "the framework ships no instance" is enforced by the mechanism rather than remembered by
a person. That is the one thing a convention could not give us -- the committed fixture this file
replaces was itself written by someone (me) who believed the convention.

Usage:
    python3 tools/mac_fixture.py --emit <dir>     write the bundle, print its root
    python3 tools/mac_fixture.py --self-test      emit to a temp dir and prove it loads

Exit: 0 = ok · 1 = a self-test assertion failed · 2 = could not run (refused destination)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── THE BUNDLE, AS DATA ───────────────────────────────────────────────────────────────────────────
# Written to the CURRENT column surface (grounding.source · key · offers), which is the fifth
# revision of 2026-10-07. Deliberately the SMALLEST tree that still exercises all four descriptor
# families plus edges, because what the five consumers test is the RESOLVER and the SEAM, not the
# size of any bundle.

MANIFEST = """\
# EMITTED by tools/mac_fixture.py — do not commit this tree. The framework ships the generator.
spec_version: mac.container/1

metadata:
  project: tests/two_plane
  data_domain: tests
  dataset: two_plane
  label: Two-plane layout fixture

planes:
  data: data
  ontology: ontology
descriptors: data/datasets      # produced relations the ontology binds to (the seam)
transforms: data/transforms     # the pipelines: source -> dataset
sources: data/sources           # observed raw-input schema-of-record
"""

CUSTOMER = """\
# Two-plane fixture > sales > Customer. Synthetic; illustrates the `entity` class.

metadata:
  source: TWO_PLANE
  version: '1.0'
  schema_version: 0.1.19
  confidence: C
  provenance: authored

concept:
  name: Customer
  class: entity
  definition: >-
    A party who can place orders. Identified by customer_id; one row per customer.

grounding:
  kind: sql_table
  schema: two_plane_warehouse
  source:
    relation: customers
    key: [customer_id]
    columns:
      customer_id:
        offers: {}
      country_code:
        offers:
          axis: categorical
      created_at:
        offers:
          axis: time
"""

# NO `grain:` UNDER `grounding:`. It was there until 2026-10-08 and was a real schema error --
# GroundingBlock stopped admitting it in the fifth revision. `grain` did NOT retire, which is the
# part that matters: it kept two homes, TransformFile.produces.grain and
# ValueRegisterFile.register.grain, and the transform below still declares it correctly. Measuring
# zero `grain:` in contoso5's CONCEPTS and concluding "retired estate-wide" would have deleted a
# conforming declaration from the transform -- and nothing would have caught it, because a schema
# reports a key that is UNEXPECTED and never one that is MISSING.
REVENUE = """\
# Two-plane fixture > sales > Revenue. Synthetic; illustrates the `measure` class.

metadata:
  source: TWO_PLANE
  version: '1.0'
  schema_version: 0.1.19
  confidence: C
  provenance: authored

concept:
  name: Revenue
  class: measure
  definition: >-
    The amount billed on an order, net of nothing. One amount per order.
  semantics:
    measure_type: mac.concept.column.measure_type.flow
    unit: EUR
    axis_kinds:
      placed_at: mac.concept.axis.time
      customer_id: mac.concept.axis.categorical

grounding:
  kind: sql_table
  schema: two_plane_warehouse
  source:
    relation: orders
    key: [order_id]
    columns:
      order_id:
        offers: {}
      customer_id:
        offers: {}
        references: Customer
      placed_at:
        offers:
          axis: time
          period_binding: true
      amount:
        offers:
          aggregate:
            type: flow
            unit: EUR
"""

EDGES = """\
# Two-plane fixture — Edges layer: relations BETWEEN concepts.
# A relation between two concepts is an edge, never a property of either endpoint.

metadata:
  layer: edges
  source: TWO_PLANE
  schema_version: 0.1.19
  status: measured
  date: 2026-10-08

edges:

  - edge_id: revenue__placed_by__customer
    level: physical                       # a real FK join between the two grounded tables
    type: foreign_key
    endpoints:
      from: { source: TWO_PLANE, concept: Revenue,  ref: "ontology/concepts/sales/revenue.yaml#concept",  role: placedBy, cardinality: "0..N" }
      to:   { source: TWO_PLANE, concept: Customer, ref: "ontology/concepts/sales/customer.yaml#concept",                 cardinality: "1" }
    join_rule: "orders.customer_id = customers.customer_id"
    realized_by: "data/datasets/orders.yaml#columns.customer_id (role: foreign_key -> customers.customer_id)"
    notes: "The only join in the fixture — every per-customer aggregation goes through it."
    confidence: C
"""

CUSTOMERS_DS = """\
# Two-plane fixture — data plane / DATASET: the produced customers relation (the seam).

metadata:
  schema_version: 0.1.19
  status: measured
  kind: served_dataset

table:
  name: customers
  schema: two_plane_warehouse
  type: table
  description: "One row per customer. Grounding target for the Customer entity."

columns:
  - { name: customer_id,  type: string,    role: primary_key }
  - { name: country_code, type: string,    role: value }
  - { name: created_at,   type: timestamp, role: value }

grounded_by_concepts:
  - { concept: Customer, role: primary_table }
"""

ORDERS_DS = """\
# Two-plane fixture — data plane / DATASET: the produced orders relation (the seam).
# `customer_id` carries role `foreign_key` ON THE COLUMN — the table-level `foreign_keys:` block was
# retired 2026-10-05; a column states what it is, and nothing restates it one level up.

metadata:
  schema_version: 0.1.19
  status: measured
  kind: served_dataset

table:
  name: orders
  schema: two_plane_warehouse
  type: table
  description: "One row per order. Grounding target for the Revenue measure."

columns:
  - { name: order_id,    type: string,    role: primary_key }
  - { name: customer_id, type: string,    role: foreign_key, references: customers.customer_id }
  - { name: placed_at,   type: timestamp, role: value }
  - { name: amount,      type: decimal,   role: value }

grounded_by_concepts:
  - { concept: Revenue, role: primary_table }
"""

ORDERS_RAW = """\
# Two-plane fixture — data plane / SOURCE: the observed raw orders input (schema-of-record).
# What COMES IN, before cleansing. Not ontology-bound: concepts bind to the produced dataset.

metadata:
  schema_version: 0.1.19
  status: measured
  kind: raw_source
  observed: '2026-10-08'

table:
  name: orders_raw
  schema: two_plane_raw
  type: table
  description: "Raw upstream orders as they arrive (amount in integer cents)."

columns:
  - { name: order_id,    type: string,    role: primary_key }
  - { name: customer_id, type: string,    role: foreign_key }
  - { name: gross_cents, type: bigint,    role: value }
  - { name: placed_at,   type: timestamp, role: value }
"""

# `produces.grain` IS CONFORMING and stays — see the note above REVENUE.
ORDERS_TRANSFORM = """\
# Two-plane fixture — data plane / TRANSFORM: the `orders` pipeline (how the clean dataset is made).
# The consuming concept (Revenue) describes only the CLEAN result and carries no transform logic.

metadata:
  pipeline: orders
  layer: data-transformation
  schema_version: 0.1.19
  status: measured

produces:
  relation: two_plane_warehouse.orders
  grain: "one row per order_id"

inputs:
  - relation: two_plane_raw.orders_raw
    kind: raw_source
    role: raw_orders
    descriptor: data/sources/orders_raw.yaml
    consumes:
      gross_cents: amount-to-decimal
"""

FILES = {
    "mac.project.yaml": MANIFEST,
    "ontology/concepts/sales/customer.yaml": CUSTOMER,
    "ontology/concepts/sales/revenue.yaml": REVENUE,
    "ontology/edges.yaml": EDGES,
    "data/datasets/customers.yaml": CUSTOMERS_DS,
    "data/datasets/orders.yaml": ORDERS_DS,
    "data/sources/orders_raw.yaml": ORDERS_RAW,
    "data/transforms/orders.yaml": ORDERS_TRANSFORM,
}

#: What the emitted tree contains, so a consumer can assert on it without counting files itself.
COUNTS = {"concept": 2, "dataset": 2, "source": 1, "transform": 1, "edges": 1}


class RefusedDestination(Exception):
    """The destination is inside a git work tree — emitting there would ship an instance."""


def _git_root(path: Path) -> Path | None:
    """The nearest ancestor holding `.git`, or None. Walks the PARENTS of a not-yet-created dir."""
    p = path.resolve()
    for cand in (p, *p.parents):
        if (cand / ".git").exists():
            return cand
    return None


def emit(dest) -> Path:
    """Write the bundle under `dest` and return its root.

    REFUSES any destination inside a git work tree. The framework ships the generator, never the
    instance, and a rule a person has to remember is the rule that produced the committed fixture
    this file replaces.
    """
    root = Path(dest).resolve()
    owner = _git_root(root)
    if owner is not None:
        raise RefusedDestination(
            f"refusing to emit into a git work tree ({owner}). This bundle is SCAFFOLDING and the "
            f"framework ships no instance of it — emit to a temp directory instead. If you are "
            f"trying to commit a two-plane bundle into a repository, that is the decision "
            f"tools/mac_fixture.py exists to prevent; see its header."
        )
    for rel, text in FILES.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return root


def emit_temp(prefix: str = "mac_two_plane_") -> Path:
    """Emit into a fresh temp directory. The caller owns it and should shutil.rmtree it."""
    return emit(tempfile.mkdtemp(prefix=prefix))


# ── self-test ─────────────────────────────────────────────────────────────────────────────────────

def _self_test() -> int:
    fails = 0

    def case(cond, msg):
        nonlocal fails
        print(("✓ " if cond else "✗ ") + msg)
        fails += 0 if cond else 1

    tmp = emit_temp()
    try:
        case((tmp / "mac.project.yaml").is_file(), "emits a manifest")
        case(len(list(tmp.rglob("*.yaml"))) == len(FILES), f"emits {len(FILES)} file(s)")

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mac_model as M                                              # noqa: E402
        import mac_project as P                                            # noqa: E402

        L = P.resolve(tmp)
        case(L.two_plane, "resolves as TWO-PLANE")
        case(L.ontology.name == "ontology", "ontology plane is ontology/")
        case(L.descriptors.name == "datasets", "descriptors are data/datasets/")

        B = M.load(tmp)
        for kind, want in (("dataset", COUNTS["dataset"]), ("source", COUNTS["source"]),
                           ("transform", COUNTS["transform"])):
            got = len(B.docs(kind))
            case(got == want, f"{kind}: {got} (want {want})")
        case(len(B.concepts()) == COUNTS["concept"],
             f"concept: {len(B.concepts())} (want {COUNTS['concept']})")
        case(len(B.edges()) >= COUNTS["edges"], f"edges loaded ({len(B.edges())})")

        # THE REFUSAL IS A TESTED PROPERTY, not a comment. Emitting into this very repository must
        # fail, or the mechanism is decoration.
        try:
            emit(Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "nope")
            case(False, "REFUSES a destination inside a git work tree")
        except RefusedDestination:
            case(True, "REFUSES a destination inside a git work tree")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'all fixture assertions passed' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="emit the two-plane self-test bundle")
    ap.add_argument("--emit", metavar="DIR", help="write the bundle under DIR and print its root")
    ap.add_argument("--self-test", action="store_true", help="emit to a temp dir and prove it loads")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if a.emit:
        try:
            print(emit(a.emit))
        except RefusedDestination as e:
            print(f"could not run: mac_fixture — {e}", file=sys.stderr)
            return 2
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
