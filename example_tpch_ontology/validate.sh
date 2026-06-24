#!/usr/bin/env bash
# validate.sh — run the three MAC gates against THIS example (structural · referential · constraint).
#
#   ./validate.sh            # from anywhere — it locates the repo root itself
#
# Exit 0 only if all three data-free L1 gates pass. They prove conformance, NOT correctness
# (a green run does not assert a column exists in a warehouse or a label means what you think) —
# see ../CONFORMANCE.md for what L1/L2/L3 each guarantee.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
EX="$(basename "$HERE")"
cd "$ROOT"

echo "── MAC validation · $EX · schema_version 0.1.9 ──"
echo "[1/3] structural  — validate_schema.py → mac.schema.json (closed vocabulary, required keys, naming, edge legality)"
python3 tools/validate_schema.py "$EX"
echo "[2/3] referential — check_references.py → every cross-file reference + mac.* term resolves"
python3 tools/check_references.py "$EX"
echo "[3/3] constraint  — check_shapes.py → built-in shapes (mac_shapes.yaml), incl. the cross-file rule-binds-grounded invariant"
python3 tools/check_shapes.py "$EX"
echo "✓ $EX — all three gates passed"
