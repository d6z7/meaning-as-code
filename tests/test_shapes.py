#!/usr/bin/env python3
"""
test_shapes.py — the four first-class shape primitives (Track A) exercised red→green on a generic
mini-project (tests/fixtures/shapes_lab/, an orders/customers domain — no application specifics).

  A1 join_rule_grounded     — edges[].join_rule columns must resolve to grounded columns (check_shapes)
  A2 edge.verified_by       — a dangling verified_by ref is a referential error (check_references)
  A3 partition              — member_key values unique WITHIN each group, never globally (check_shapes)
  A4 no_predicate_restatement — a concept rule.then must not restate an edge join_rule (check_shapes)

Each primitive is asserted on a POSITIVE fixture (passes) and a NEGATIVE fixture (fails). A1 is also
run end-to-end through check_shapes.py main() (built-in shape + edges loading) via subprocess.

Usage:  python3 tests/test_shapes.py     ·     Exit: 0 = all assertions passed · 1 = a failure
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOOLS = REPO / "tools"
LAB = HERE / "fixtures" / "shapes_lab"
sys.path.insert(0, str(TOOLS))

from check_shapes import check              # noqa: E402
from check_references import ReferenceChecker  # noqa: E402

fails = 0


def ok(cond, msg):
    global fails
    print(("  ✓ " if cond else "  ✗ ") + msg)
    fails += 0 if cond else 1


def load(name):
    return yaml.safe_load((LAB / name).read_text())


def run_shape(shape, doc):
    out = []
    check(shape, doc, shape["id"], out, LAB)
    return out


def assemble(edges_fixture):
    """A temp flat project = shared concepts/tables/expectations + the chosen edges fixture as edges.yaml."""
    tmp = Path(tempfile.mkdtemp(prefix="mac_shapes_lab_"))
    for sub in ("concepts", "tables", "expectations"):
        shutil.copytree(LAB / sub, tmp / sub)
    shutil.copy(LAB / edges_fixture, tmp / "edges.yaml")
    return tmp


# ----------------------------------------------------------------- A1 · join_rule_grounded
print("A1 · join_rule_grounded")
A1 = {"id": "join-rule-grounded", "target": "edges", "constraint": {"kind": "join_rule_grounded"}}
good = run_shape(A1, load("good_join_rule_grounded.edges.yaml"))
ok(good == [], f"good_join_rule_grounded → no violations (got {good})")
bad = run_shape(A1, load("bad_join_rule_unresolved_col.edges.yaml"))
errs = [v for v in bad if v[0] == "error"]
ok(len(errs) == 1 and "custommer_id" in errs[0][3], f"bad_join_rule_unresolved_col → 1 error on custommer_id (got {bad})")

# end-to-end through check_shapes.py main() (built-in shape auto-loads; edges file is loaded by main)
for fx, want in [("good_join_rule_grounded.edges.yaml", 0), ("bad_join_rule_unresolved_col.edges.yaml", 1)]:
    root = assemble(fx)
    try:
        r = subprocess.run([sys.executable, str(TOOLS / "check_shapes.py"), str(root)],
                           capture_output=True, text=True)
        ok(r.returncode == want, f"check_shapes.py main() on {fx} → exit {r.returncode} (want {want})")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ----------------------------------------------------------------- A2 · edge.verified_by
print("A2 · edge.verified_by")


def verified_by_errors(edges_fixture):
    root = assemble(edges_fixture)
    try:
        chk = ReferenceChecker(root)
        chk._build_index()
        chk._resolve()
        return [f for f in chk.findings if f.severity == "ERROR" and "verified_by" in f.where]
    finally:
        shutil.rmtree(root, ignore_errors=True)


ge = verified_by_errors("good_edge_verified_by.edges.yaml")
ok(ge == [], f"good_edge_verified_by → no verified_by error (got {[f.message for f in ge]})")
be = verified_by_errors("bad_edge_verified_by_dangling.edges.yaml")
ok(len(be) == 1 and "no_such_id" in be[0].message,
   f"bad_edge_verified_by_dangling → 1 dangling verified_by error (got {[f.message for f in be]})")


# ----------------------------------------------------------------- A3 · partition
print("A3 · partition")
A3 = {"id": "partition-scheme", "target": "concept",
      "constraint": {"kind": "partition", "group_by_root": "members.definitions",
                     "group_key": "scheme", "member_key": "members"}}
gp = run_shape(A3, load("good_partition.concept.yaml"))
ok(gp == [], f"good_partition (member in two schemes) → no violations (got {gp})")
bp = run_shape(A3, load("bad_partition_global.concept.yaml"))
bpe = [v for v in bp if v[0] == "error"]
ok(len(bpe) == 1 and "member_1" in bpe[0][3] and "scheme_a" in bpe[0][3],
   f"bad_partition_global → 1 error (member_1 twice in scheme_a) (got {bp})")


# ----------------------------------------------------------------- A4 · no_predicate_restatement
print("A4 · no_predicate_restatement")
A4 = {"id": "no-predicate-restatement", "target": "concept",
      "constraint": {"kind": "no_predicate_restatement"}}
gr = run_shape(A4, load("good_predicate_cites_edge.concept.yaml"))
ok(gr == [], f"good_predicate_cites_edge (cites edge, no predicate) → no violations (got {gr})")
br = run_shape(A4, load("bad_predicate_restated_in_rule.concept.yaml"))
bre = [v for v in br if v[0] == "error"]
ok(len(bre) == 1 and "order__of_customer" in bre[0][3],
   f"bad_predicate_restated_in_rule → 1 error citing the restated edge (got {br})")


# ----------------------------------------------------------------- summary
print(f"\n{'all shape-primitive assertions passed' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
