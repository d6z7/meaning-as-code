#!/usr/bin/env python3
"""check_slot_reference.py — the per-slot reference pages still say what the schema and vocabulary say.

WHY THIS FILE EXISTS AND IS NOT JUST A FLAG. `run_framework_gates.sh` discovers gates by globbing
`check_*.py`, and `gen_slot_reference.py` checks itself behind `--check`, so the suite never ran it.
Measured 2026-10-04: `reference_manual/column_map.generated.md` carried FIVE raw Python dict reprs in
its TERM MEANINGS section — `- **`key`** — {'query_use': ['identity'], 'definition': …` — while
`--check` reported `2 page(s) current`, and nothing in the suite asked the question at all.

So the generator keeps its `gen_` name, because its day job is to WRITE, and its check gets a `check_`
name, because that is the name the suite can see. Its five reject classes live in the generator and are
proven by `gen_slot_reference.py --self-test`; this file forwards that too, so the suite's self-test arm
counts it.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gen_slot_reference as gen  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return gen.main(["--self-test"])
    # THE BUNDLE ROOT IS NOT ARGV[1] HERE. This gate's subject is THIS repository's generated pages
    # against THIS repository's mac.schema.json and mac_vocabulary.yaml; no bundle takes part. Declared
    # in the runner's REPO_SUBJECT_GATES, and refusing a positional argument is what keeps a
    # calling-convention miss from reading as a finding.
    positional = [a for a in argv if not a.startswith("-")]
    if positional:
        print(f"COULD NOT RUN: this gate takes no path argument (got {positional[0]!r}); its subject "
              f"is this repository's reference_manual/*.generated.md", file=sys.stderr)
        return 2
    return gen.main(["--check"] + [a for a in argv if a.startswith("-")])


if __name__ == "__main__":
    raise SystemExit(main())
