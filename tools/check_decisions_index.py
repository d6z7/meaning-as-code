#!/usr/bin/env python3
"""check_decisions_index.py — the decision index still names every record, live and removed.

WHY THIS FILE EXISTS AND IS NOT JUST A FLAG. `run_framework_gates.sh` discovers gates by globbing
`check_*.py`, so a generator's own `gen_<x>.py --check` is invisible to the suite unless a `check_`
name delegates to it. Measured 2026-10-04 that left six of this repository's seven generators
unchecked by anything the suite runs, which is how a generated page held a stale schema version with
nothing red. The generator keeps its `gen_` name because its day job is to WRITE; its check gets the
name the suite can see, and the logic stays in one home.

Its four reject classes live in the generator and are proven by `gen_decisions_index.py --self-test`;
this file forwards that too, so the suite's self-test arm counts it.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gen_decisions_index as gen  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return gen.main(["--self-test"])
    # THE BUNDLE ROOT IS NOT ARGV[1] HERE. This gate's subject is THIS repository's own decisions/
    # directory and THIS repository's git history. It is declared in the runner's REPO_SUBJECT_GATES
    # for that reason, and refusing a positional argument is what keeps a calling-convention miss from
    # reading as a finding — the defect that once had `check_protocol` judge 7 commits against a floor
    # measured over 38.
    positional = [a for a in argv if not a.startswith("-")]
    if positional:
        print(f"COULD NOT RUN: this gate takes no path argument (got {positional[0]!r}); "
              f"its subject is this repository's decisions/ and its git history", file=sys.stderr)
        return 2
    return gen.main(["--check"] + [a for a in argv if a.startswith("-")])


if __name__ == "__main__":
    raise SystemExit(main())
