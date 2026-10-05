#!/usr/bin/env python3
"""check_page_home.py — EVERY DOCUMENTATION PAGE SITS IN A DECLARED HOME.

A THREE-LINE DELEGATE, and the reason is the runner's discovery rule, not a design preference:
`run_framework_gates.sh` finds gates by globbing `tools/check_*.py`, so `relocate_pages.py --check`
was invisible to it — the home declaration in `guardrails/document_home.yaml` would have kept holding
and nothing would have run it. `tools/check_structure_reference.py` exists for exactly this reason over
`gen_structure_reference.py --check`; this is the same shape, so it is the same solution.

The subject is THIS REPOSITORY, not a bundle, so the name belongs in the runner's
`REPO_SUBJECT_GATES`. A positional bundle root is refused with exit 2 rather than ignored: being
handed one means the runner's register has not been updated, and that is a could-not-run, never a
verdict about this repository's pages.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        print(f"could not run: check_page_home takes no bundle root (got {sys.argv[1]!r}); "
              f"add it to REPO_SUBJECT_GATES in tools/run_framework_gates.sh")
        raise SystemExit(2)
    import relocate_pages
    raise SystemExit(relocate_pages.main(["--check"] + sys.argv[1:]))
