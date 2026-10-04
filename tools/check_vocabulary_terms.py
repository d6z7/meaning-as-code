#!/usr/bin/env python3
"""check_vocabulary_terms.py — every notion mac_vocabulary.yaml defines has a chapter, and it is current.

WHY THIS FILE EXISTS AND IS NOT JUST A FLAG. `run_framework_gates.sh` discovers gates by globbing
`check_*.py`, and `gen_vocabulary_terms.py` checks itself behind `--check`, so the suite never ran it.
Measured 2026-10-04 it printed `notions defined: 24   documented: 20   UNDOCUMENTED: 4` and EXITED 0 —
`missing` was computed, printed, and never consulted by a return statement — while
`reference_manual/README.md` recorded the gate as failing "if a notion has no chapter" and as green at
"20 of 20". Three claims, three false, and nothing in the suite looking.

NOT THE SAME GATE AS `check_vocabulary_parity.py`. That one asks whether a SCHEMA ENUM lists the same
terms as its vocabulary block. This one asks whether the MANUAL has a chapter for every notion and
whether that chapter still says what the vocabulary says. Two surfaces, two questions.

Its five reject classes live in the generator and are proven by
`gen_vocabulary_terms.py --self-test`; this file forwards that too, so the suite's self-test arm counts it.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gen_vocabulary_terms as gen  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return gen.main(["--self-test"])
    # THE BUNDLE ROOT IS NOT ARGV[1] HERE. This gate's subject is THIS repository's reference_manual/
    # against THIS repository's mac_vocabulary.yaml; no bundle takes part. Declared in the runner's
    # REPO_SUBJECT_GATES, and refusing a positional argument is what keeps a calling-convention miss
    # from reading as a finding.
    positional = [a for a in argv if not a.startswith("-")]
    if positional:
        print(f"COULD NOT RUN: this gate takes no path argument (got {positional[0]!r}); its subject "
              f"is this repository's reference_manual/ chapters", file=sys.stderr)
        return 2
    return gen.main(["--check"] + [a for a in argv if a.startswith("-")])


if __name__ == "__main__":
    raise SystemExit(main())
