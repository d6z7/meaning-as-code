#!/usr/bin/env python3
"""check_manual_index.py — the reference manual's index still says what the manual says.

WHY THIS FILE EXISTS AND IS NOT JUST A FLAG. `run_framework_gates.sh` discovers gates by globbing
`check_*.py`. A generator checks itself behind `gen_<x>.py --check`, so NOT ONE generator is run by
the suite unless a `check_` name delegates to it — measured 2026-10-04, `check_key_reference.py` was
the only one that did, leaving `gen_schema_shapes`, `gen_slot_reference`, `gen_vocabulary_terms`,
`gen_column_bench`, `gen_grammar_map` and `gen_strategy` invisible. That is how
`reference_manual/shape_reference.md` came to claim `schema 0.1.14` against a schema at 0.1.16 with
nothing red: the only instrument that would have noticed is one nothing invokes.

So the generator keeps its `gen_` name, because its day job is to WRITE, and its check gets a
`check_` name, because that is the name the suite can see. Three lines of delegation and no second
home for the logic.

Its four reject classes live in the generator and are proven by `gen_manual_index.py --self-test`;
this file forwards that too, so the suite's self-test arm counts it.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gen_manual_index as gen  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return gen.main(["--self-test"])
    # THE BUNDLE ROOT IS NOT ARGV[1] HERE. This gate's subject is THIS repository's own manual; no
    # bundle contributes to it. It is declared in the runner's REPO_SUBJECT_GATES for that reason,
    # and refusing a positional argument is what keeps a calling-convention miss from reading as a
    # finding — the defect that once had `check_protocol` judge 7 commits against a floor of 38.
    positional = [a for a in argv if not a.startswith("-")]
    if positional:
        print(f"COULD NOT RUN: this gate takes no path argument (got {positional[0]!r}); "
              f"its subject is this repository's reference_manual/", file=sys.stderr)
        return 2
    return gen.main(["--check"] + [a for a in argv if a.startswith("-")])


if __name__ == "__main__":
    raise SystemExit(main())
