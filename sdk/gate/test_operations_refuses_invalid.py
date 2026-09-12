#!/usr/bin/env python3
"""Fuzz/unit proof for adversary finding #1: an INVALID authored candidate must produce
ZERO files on disk; a gate-clean one persists. Run: python3 sdk/gate/test_operations_refuses_invalid.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root -> `sdk` importable
from sdk.authoring import operations


def _mk_result(status):
    return {
        "status": status,
        "obj": {"metadata": {"concept": "X"}},
        "yaml": "metadata:\n  concept: X\n",
    }


def main():
    failures = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "sources" / "gaps" / "fpl"
        concepts = base / "ontology" / "concepts"
        data = base / "data"

        # 1) invalid concept -> refused, zero files
        r = operations.persist_concept(concepts, "bad", _mk_result("invalid"))
        if r["written"] or (concepts / "bad.yaml").exists():
            failures.append("invalid concept was PERSISTED (must be refused)")

        # 2) valid concept -> written
        r = operations.persist_concept(concepts, "good", _mk_result("valid"))
        if not r["written"] or not (concepts / "good.yaml").exists():
            failures.append("valid concept was NOT persisted")

        # 3) 'fixed' concept -> written (autofixed is persistable)
        operations.persist_concept(concepts, "fixed", _mk_result("fixed"))
        if not (concepts / "fixed.yaml").exists():
            failures.append("fixed concept was NOT persisted")

        # 4) descriptors: only gate-clean kinds persist
        files = {
            "source": {"obj": {"a": 1}},
            "transform": {"obj": {"b": 2}},
            "dataset": {"obj": {"c": 3}},
        }
        statuses = {"source": "valid", "transform": "invalid", "dataset": "fixed"}
        operations.persist_descriptors(data, "t1", files, statuses)
        if not (data / "sources" / "t1.yaml").exists():
            failures.append("valid source descriptor not persisted")
        if (data / "transforms" / "t1.yaml").exists():
            failures.append("INVALID transform descriptor was persisted (must be refused)")
        if not (data / "datasets" / "t1.yaml").exists():
            failures.append("fixed dataset descriptor not persisted")

        # 5) containment: a write outside sources/ must raise Refused
        try:
            operations._write_ssot(Path(td) / "escape.yaml", "x")
            failures.append("write OUTSIDE sources/ was allowed (containment breach)")
        except operations.Refused:
            pass

        # 6) capture-oracle-from-ruling: value is RE-DERIVED by executing SQL; a divergent
        #    SME assertion is REFUSED (no-hallucination), a matching one is written.
        acc = base / "acceptance"
        ruling_ok = {
            "id": "ann_ok",
            "ruling": {
                "expected_outcome": "COMMIT",
                "expected_value": 5000,
                "tolerance": 1,
                "sql_contains": ["select 5000"],
            },
        }
        r = operations.capture_oracle_from_ruling(acc, ruling_ok, executor=lambda sql: 5000)
        if not r["written"] or not (acc / "oracle" / "ann_ok.yaml").exists():
            failures.append("capture-oracle: a matching ruling was not written")
        ruling_bad = {
            "id": "ann_bad",
            "ruling": {"expected_value": 5000, "tolerance": 1, "sql_contains": ["select 9999"]},
        }
        r = operations.capture_oracle_from_ruling(acc, ruling_bad, executor=lambda sql: 9999)
        if r["written"] or (acc / "oracle" / "ann_bad.yaml").exists():
            failures.append(
                "capture-oracle: a DIVERGENT SME assertion was written (no-hallucination breach)"
            )

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS — invalid/out-of-bounds candidates produce zero files; gate-clean ones persist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
