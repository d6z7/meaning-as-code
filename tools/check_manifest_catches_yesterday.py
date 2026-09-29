#!/usr/bin/env python3
"""check_manifest_catches_yesterday.py — THE ACCEPTANCE TEST FOR THE DELIVERY MANIFEST.

One question: if the five losses of 2026-09-28 happened again, would anything say so?

The manifest was built to end a specific failure — five re-ingests of one bundle in a day, each
losing a different deliverable, each reporting itself complete. Operator: "every new time you have
managed to forget someting ... this is maximal unreliability and it is unacceptable". A mechanism
that cannot be shown to catch the failures it was written for is a sentence, not a guard — which is
exactly what `NAME-MATCHES` was for as long as it existed.

So each loss is SEEDED as a mutant against an in-memory registry, and the invariant that must object
is named with it. A mutant that survives is a hole, and it is reported as one.

    python3 check_manifest_catches_yesterday.py
"""

from __future__ import annotations

import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_artifact_conformance as C  # noqa: E402

OK, BAD = "ok", "violation"


def _broke(items) -> bool:
    return any(i["verdict"] == BAD for i in items)


def _clean() -> dict:
    """One kind, fully declared — the shape every mutant is a deviation FROM."""
    return {
        "lineage": {
            "what": "where every served column came from",
            "phase": ["datasets"],
            "lifecycle": "re-derived",
            "population": {"of": "the artifact itself", "from": "«this artifact»", "empty_is": "EMPTY"},
            "path": "data/lineage/lineage.json",
            "shape": "mac.schema.json#/$defs/LineageFile",
            "producers": [{"tool": "tools/mac_lineage.py", "role": "measures"}],
            "consumers": [{"tool": "console_api.py", "role": "renders the Lineage pane",
                           "reads": ["columns[].view", "columns[].source_column"]}],
            "checkers": [{"tool": "tools/check_lineage_coverage.py", "rejects": ["coverage-missing"]}],
        }
    }


#: (name, what happened on 2026-09-28, how to seed it, which invariant must object)
MUTANTS = (
    ("LOSS 1 · lineage held by every delivery",
     "the stage carried no `part`, so `--part sources` AND `--part datasets` both held it and it "
     "ran only under `--part all`, which the operator's sequential rule forbids",
     lambda k: k["lineage"].pop("phase"),
     "PHASED"),

    ("LOSS 2 · the DQ assessment, same defect",
     "`dq-suite`, `dq-run` and `dq-findings` were tagged to no part either; a two-part delivery "
     "finished 6 of 6 and 9 of 9 with data/quality/ absent",
     lambda k: k["lineage"].update(phase="TODO   # no stage declares a part"),
     "PHASED"),

    ("LOSS 3 · a stage resuming on the previous phase's output",
     "once tagged, phase 2 RESUMED the DQ stages on phase 1's files: 0 of 8 served relations "
     "assessed, and the register still claimed eight landings fed no transformation",
     lambda k: k["lineage"].update(lifecycle="resumable-because-i-said-so"),
     "PHASED"),

    ("LOSS 4 · a reader on a field no producer writes",
     "SMEThread.jsx read `question.sme_owner` while mac_dq_findings writes `ruling.question`, and "
     "the pane rendered 'Every condition has been ruled' over seven open questions",
     lambda k: k["lineage"]["consumers"][0].pop("reads"),
     "CONSUMED"),

    ("LOSS 5 · an artifact nobody reads",
     "objects.json#lineage_graph was retired with three consumers still pointed at it, and two "
     "bundles' lineage views went blank",
     lambda k: k["lineage"].update(consumers=[]),
     "CONSUMED"),

    ("BONUS · an artifact on disk no kind declares",
     "the operator's ruling of 2026-09-29: undeclared is an ERROR, because a warning is how the "
     "DQ assessment went missing while every surface read green",
     None,                       # seeded on DISK, not in the registry
     "COVERED"),

    ("BONUS · two kinds claiming one artifact",
     "six homes for one glob, and mac_import's own comments record three resume bugs from it",
     lambda k: k.update(lineage_again=copy.deepcopy(k["lineage"])),
     "COVERED"),
)


def run() -> int:
    print("── does the manifest catch the five losses of 2026-09-28? ──\n")
    held = 0
    import tempfile

    for name, what, seed, invariant in MUTANTS:
        kinds = _clean()
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "data" / "lineage").mkdir(parents=True)
            (root / "data" / "lineage" / "lineage.json").write_text("{}", encoding="utf-8")
            if seed is None:
                # the undeclared artifact: a real file no kind claims
                (root / "data" / "quality").mkdir(parents=True)
                (root / "data" / "quality" / "data_quality_register.yaml").write_text("{}", encoding="utf-8")
            else:
                seed(kinds)
            caught = {
                "PHASED": lambda: _broke(C.inv_phased(kinds)),
                "CONSUMED": lambda: _broke(C.inv_consumed(kinds)),
                "COVERED": lambda: _broke(C.inv_covered(root, kinds)),
            }[invariant]()
        held += caught
        print(f"  [{'CAUGHT' if caught else 'ESCAPED'}] {name}")
        print(f"             {what}")
        print(f"             -> {invariant} {'objects' if caught else 'DOES NOT OBJECT — this is a hole'}\n")

    n = len(MUTANTS)
    print(f"{held} of {n} seeded loss(es) refused.")
    if held == n:
        print("\nPASS — every failure this manifest was written for is now refused by a named "
              "invariant. That is the whole claim, and it is the one thing a mechanism like this "
              "must be able to demonstrate rather than assert.")
        return 0
    print("\nFAIL — a loss this was built to prevent would happen again silently.")
    return 1


if __name__ == "__main__":
    sys.exit(run())
