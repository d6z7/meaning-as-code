#!/usr/bin/env python3
"""check_rule_lock.py — BUILD/TUNE drift lock over one source's ontology plane.

Parameterized by --content-root (a `sources/<domain>/<dataset>` dir), so ONE gate serves
every source — unlike the FPL gate, which derived its paths from its own __file__ location.

It hashes every `ontology/**/*.yaml` file AND each typed rule (`contract.rules[].id`) into
`<content-root>/ontology/rules.lock`. `<content-root>/ontology/PHASE.yaml` sets the phase:
  * BUILD — rule CRUD is free; drift only WARNS (exit 0).
  * TUNE  — default-DENY: any un-blessed file/rule delta REDS the gate (exit 1).
`--bless` recomputes the lock (an operator action).

HONEST LIMIT (identical to the FPL gate it mirrors): in a single-identity repo the author
can run `--bless`, so this DETECTS-and-BLOCKS drift; it does not cryptographically AUTHORIZE.
The only unforgeable authorization is out-of-repo (branch protection + required CI) — see
boundaries.yaml:authorization_out_of_band. Exit 0 clean/build, 1 on TUNE drift or error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

from sdk.gate import contract

_RESERVED = {"rules.lock", "PHASE.yaml"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _phase(ontology: Path) -> str:
    p = ontology / "PHASE.yaml"
    if not p.exists():
        return "BUILD"
    return str((yaml.safe_load(p.read_text()) or {}).get("phase", "BUILD")).upper()


def _scan(ontology: Path) -> dict:
    """Return {files:{rel:sha}, rules:{'rel::id':sha}} over ontology/**/*.yaml."""
    files, rules = {}, {}
    for p in sorted(ontology.rglob("*.yaml")):
        if p.name in _RESERVED:
            continue
        rel = str(p.relative_to(ontology))
        text = p.read_text()
        files[rel] = _sha(text)
        try:
            obj = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        for rule in ((obj or {}).get("contract") or {}).get("rules") or []:
            rid = rule.get("id")
            if rid:
                rules[f"{rel}::{rid}"] = _sha(json.dumps(rule, sort_keys=True, default=str))
    return {"files": files, "rules": rules}


def _lock_path(ontology: Path) -> Path:
    return ontology / "rules.lock"


def bless(ontology: Path) -> int:
    snap = _scan(ontology)
    lock = {
        "_meta": {
            "generated_by": "sdk/gate/check_rule_lock.py --bless",
            "phase_at_bless": _phase(ontology),
            "file_count": len(snap["files"]),
            "rule_count": len(snap["rules"]),
            "note": "GENERATED — do not hand-edit",
        },
        "files": snap["files"],
        "rules": snap["rules"],
    }
    _lock_path(ontology).write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(
        f"blessed: {len(snap['files'])} files, {len(snap['rules'])} rules "
        f"(phase={lock['_meta']['phase_at_bless']}) -> {_lock_path(ontology)}"
    )
    return 0


def check(ontology: Path) -> int:
    phase = _phase(ontology)
    lp = _lock_path(ontology)
    if not lp.exists():
        print(f"NO LOCK at {lp} — run --bless first. (phase={phase})")
        return 0 if phase == "BUILD" else 1
    lock = json.loads(lp.read_text())
    cur = _scan(ontology)
    drift = []
    for kind in ("files", "rules"):
        old, new = lock.get(kind, {}), cur[kind]
        for k in sorted(set(old) | set(new)):
            if old.get(k) != new.get(k):
                state = "added" if k not in old else "removed" if k not in new else "changed"
                drift.append(f"{kind[:-1]} {state}: {k}")
    print(f"check_rule_lock [phase={phase}] {ontology}")
    if not drift:
        print(
            f"PASS: check_rule_lock — 0 drift over {len(cur['files'])} file(s) / "
            f"{len(cur['rules'])} rule(s) examined"
        )
        return 0
    for d in drift:
        print(f"  DRIFT {d}")
    if phase == "TUNE":
        print(
            f"FAIL — {len(drift)} un-blessed change(s) in TUNE (default-DENY). Re-bless (operator) to accept."
        )
        return 1
    print(f"WARN — {len(drift)} change(s) in BUILD (allowed; will lock at bless).")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--content-root", help="a sources/<domain>/<dataset> dir")
    ap.add_argument("--bless", action="store_true", help="recompute the lock (operator action)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()
    if not a.content_root:
        return contract.could_not_run("check_rule_lock", "--content-root is required")

    ontology = Path(a.content_root).resolve() / "ontology"
    # Was `return 1`. A missing ontology/ is not a DRIFT FINDING, it is the gate being unable to
    # look -- and publish.py:82 reads a non-zero check() as drift, which is why this belongs here in
    # main() and why 1 was the wrong code.
    if not ontology.exists():
        return contract.could_not_run(
            "check_rule_lock", f"no ontology/ under {a.content_root} — nothing to compare to a lock"
        )
    if not _scan(ontology)["files"]:
        return contract.could_not_run(
            "check_rule_lock",
            f"{ontology} holds no rule file — 0 examined is not the same as in step with the lock",
        )
    return bless(ontology) if a.bless else check(ontology)


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------

# The shape _scan actually reads: contract.rules, NOT a top-level `rules:` key. The
# first fixture used the latter and locked "1 files, 0 RULES" -- the mutants passed on
# file-hash drift alone and the rule dimension was never exercised.
_RULE = "concept:\n  name: Thing\ncontract:\n  rules:\n    - id: r1\n      then: do the thing\n"


def _rl_clean(root: Path) -> None:
    ont = root / "ontology"
    contract.write(ont / "PHASE.yaml", "phase: TUNE\n")
    contract.write(ont / "rules.yaml", _RULE)
    bless(ont)


def _rl_run(root: Path):
    import contextlib
    import io as _io

    ont = root / "ontology"
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = check(ont)
    scan = _scan(ont)
    return contract.Outcome(1 if code else 0, len(scan["files"]))


def _self_test() -> int:
    c = contract.GateContract(
        name="check_rule_lock",
        clean=_rl_clean,
        mutants={
            # TUNE is default-DENY, so any un-blessed change must fail.
            "rule-changed-without-bless": lambda r: contract.write(
                r / "ontology" / "rules.yaml", _RULE.replace("do the thing", "do SOMETHING ELSE")
            ),
            "rule-added-without-bless": lambda r: contract.write(
                r / "ontology" / "extra.yaml", _RULE.replace("r1", "r2")
            ),
        },
        run=_rl_run,
        extra={
            "the lock must cover RULES, not only file hashes": lambda base: (
                ""
                if _scan(base / "clean" / "ontology")["rules"]
                else "the clean fixture locked 0 rules — the rule dimension is untested"
            ),
        },
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
