#!/usr/bin/env python3
"""
test_layout.py — the project-layout resolver: FLAT (no manifest, back-compatible) vs TWO-PLANE.

Proves the two-plane layout (data/ + ontology/, declared in mac.project.yaml) did NOT break the flat
default: a project with no manifest still resolves to concepts/ + tables/ at the root. tests/fixtures/
flat_project/ is the living back-compat example (tests/fixtures/two_plane_project is its two-plane sibling).

Usage:  python3 tests/test_layout.py     ·     Exit: 0 = ok · 1 = a layout assertion failed
"""
import os
import shutil
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from mac_project import resolve   # noqa: E402
import mac_fixture               # noqa: E402

REPO = Path(HERE).resolve().parent
flat = REPO / "tests" / "fixtures" / "flat_project"
# THE BUNDLE IS GENERATED, NEVER STORED. Operator ruling 2026-10-08 -- "mac is generic framework"
# -- so the framework ships tools/mac_fixture.py (the generator) and no instance. The committed
# fixture this replaces put an `ontology/` directory inside the framework, which the ontology guard
# then classified as a live meaning plane -- so maintaining the framework's own scaffolding needed
# an operator unlock IN the framework. mac_fixture.emit() refuses any destination inside a git work
# tree, so this cannot regress by anyone forgetting.
two_plane = mac_fixture.emit_temp()

fails = 0


def check(cond, msg):
    global fails
    print(("✓ " if cond else "✗ ") + msg)
    fails += 0 if cond else 1


L = resolve(flat)
check(not L.two_plane, "flat project (no mac.project.yaml) -> flat layout")
check(L.ontology == flat.resolve(), "flat: ontology root == project root")
check(L.descriptors.name == "tables", "flat: descriptors == tables/")

S = resolve(two_plane)
check(S.two_plane, "two-plane project (mac.project.yaml) -> two-plane layout")
check(S.ontology.name == "ontology", "two-plane: ontology plane == ontology/")
check(S.descriptors.name == "datasets", "two-plane: descriptors == data/datasets/")

shutil.rmtree(two_plane, ignore_errors=True)

print(f"\n{'all layout assertions passed' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
