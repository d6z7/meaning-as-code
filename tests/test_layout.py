#!/usr/bin/env python3
"""
test_layout.py — the project-layout resolver: FLAT (no manifest, back-compatible) vs TWO-PLANE.

Proves the two-plane layout (data/ + ontology/, declared in mac.project.yaml) did NOT break the flat
default: a project with no manifest still resolves to concepts/ + tables/ at the root. tests/fixtures/
flat_project/ is the living back-compat example (the worked examples are all two-plane now).

Usage:  python3 tests/test_layout.py     ·     Exit: 0 = ok · 1 = a layout assertion failed
"""
import os
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from mac_project import resolve   # noqa: E402

REPO = Path(HERE).resolve().parent
flat = REPO / "tests" / "fixtures" / "flat_project"
shop = REPO / "example_shop_ontology"

fails = 0


def check(cond, msg):
    global fails
    print(("✓ " if cond else "✗ ") + msg)
    fails += 0 if cond else 1


L = resolve(flat)
check(not L.two_plane, "flat project (no mac.project.yaml) -> flat layout")
check(L.ontology == flat.resolve(), "flat: ontology root == project root")
check(L.descriptors.name == "tables", "flat: descriptors == tables/")

S = resolve(shop)
check(S.two_plane, "shop (mac.project.yaml) -> two-plane layout")
check(S.ontology.name == "ontology", "shop: ontology plane == ontology/")
check(S.descriptors.name == "datasets", "shop: descriptors == data/datasets/")

print(f"\n{'all layout assertions passed' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
