#!/usr/bin/env python3
"""check_guard_seam.py — the ontology guard and the framework gate must never disagree.

THE SEAM THIS STANDS OVER. The data→ontology handoff is decided TWICE, deliberately:

  • `tools/check_data_plane_approved.py#approval_state` — the framework's decision function. Reads
    the manifest and the register with PyYAML, and is what the CLI and the console call.
  • `<kit>/ontology/install/hooks/ontology_guard.py#gate_state` — the PreToolUse guard's own
    derivation. It CANNOT import the framework: it is copied into `.claude/hooks/` with no import
    path, and it FAILS CLOSED on a protected path, so a PyYAML import error would deny every edit
    in nine repositories. Its own docstring records that a missing script bricks the repo.

Two derivations of one rule is the ONLY arrangement in which either can be checked — a single home
cannot be cross-examined. It is also, unmanaged, exactly the "one fact, two homes" defect CORE.md §9
names and the seam gates exist to catch. This gate is the management.

WHAT IT PROVES, three pairings, each with its own predicate:

  1. THE PARSER. The guard's stdlib `parse_flat` and `yaml.safe_load` must agree on every sign-off
     it will ever read — every real one in the estate, plus a fixture set covering quoting, inline
     comments, blank lines and the malformed shapes. If they diverge, the guard could allow a write
     the framework would refuse, or refuse one it would allow, and nothing would say which was
     right.
  2. THE DIGEST. The guard inlines its own `data_plane_digest`. The two roll-ups must be
     byte-identical over the same bundle, or the plane is "moved" according to one and "current"
     according to the other — and `plane_moved` is the reject class that keeps an authored ontology
     from silently disagreeing with datasets that changed.
  3. THE VERDICT. Over a shared fixture set spanning every reject class, `gate_state(root)[0]` must
     name the same outcome as `approval_state(root)`. Fixture agreement is not agreement in flight,
     which is why `check_data_plane_approved.py --agree` also asserts it on the LIVE bundle; this
     gate is the mutant-covered half and that one is the live half.

  4. THE SURFACE COVERS WHAT THE MANIFEST DECLARES. The digest surface lives in framework code so a
     BUNDLE cannot shrink it to quiet the gate. A framework edit still can, and that edit would look
     like a cleanup — so this gate asserts the surface reaches every plane a manifest declares
     (`descriptors`, `transforms`, `sources`, `lookups`) and the register.

Usage:  python3 tools/check_guard_seam.py [bundle-root]
        python3 tools/check_guard_seam.py --self-test
        exit 0 = the two derivations agree · 1 = they do not · 2 = could not run
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

EXIT_PASS, EXIT_FAIL, EXIT_COULD_NOT_RUN = 0, 1, 2

# Where the guard lives. The kit is a sibling of the framework in this estate; the env var exists so
# this gate is not the thing that hardcodes an estate layout.
GUARD_CANDIDATES = [
    Path(os.environ.get("MAC_GUARD", "")) if os.environ.get("MAC_GUARD") else None,
    _ROOT.parent / "mac-integration-kit" / "ontology" / "install" / "hooks" / "ontology_guard.py",
]

# Sign-offs the parsers must agree on. The awkward ones are the point: a parser pair that agrees only
# on the happy path proves nothing about the day somebody quotes a date.
_FIXTURES = [
    ("plain", "id: s.data-plane.approved\nstatus: applied\nby: A. Operator\n"),
    ("quoted-date", "at: '2026-09-18'\nby: \"A. Operator\"\n"),
    ("inline-comment", "status: applied   # ratified in the review\nby: A. Operator\n"),
    ("full-line-comment", "# the sign-off\nstatus: applied\n#by: nobody\nby: A. Operator\n"),
    ("blank-lines", "status: applied\n\n\nby: A. Operator\n\n"),
    ("colon-in-value", "reason: it matched: exactly\nby: A. Operator\n"),
    ("empty-value", "covers:\nby: A. Operator\n"),
    ("trailing-space", "status: applied   \nby: A. Operator   \n"),
    ("comma-list", "covers: NS-A-01, DQ-A-01, DQ-A-02\n"),
    ("crlf", "status: applied\r\nby: A. Operator\r\n"),
]
# Shapes the guard MUST refuse rather than silently misread. `yaml.safe_load` accepts all of them;
# the guard's contract is that a sign-off it cannot read flatly is NO sign-off, which denies.
_MUST_REFUSE = [
    ("nested", "status: applied\nnested:\n  deep: 1\n"),
    ("list", "covers:\n  - NS-A-01\n"),
    ("flow-seq", "covers: [NS-A-01]\n"),
    ("flow-map", "stamp: {by: x}\n"),
    ("block-scalar", "reason: |\n  a long reason\n"),
    ("no-colon", "status applied\n"),
]


def _load_guard() -> tuple:
    for cand in GUARD_CANDIDATES:
        if cand and cand.is_file():
            spec = importlib.util.spec_from_file_location("ontology_guard_seam", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, cand
    return None, None


def _seed(tmp: Path, name: str, *, pipelines=True, issues=True) -> Path:
    import check_data_plane_approved as gate
    return gate._seed(tmp, name, pipelines=pipelines, issues=issues)


def run(bundle: Path | None) -> int:
    if yaml is None:
        print("could not run: check_guard_seam — PyYAML is not importable")
        return EXIT_COULD_NOT_RUN
    guard, guard_path = _load_guard()
    if guard is None:
        print("could not run: check_guard_seam — the ontology guard was not found beside this "
              "framework (set MAC_GUARD to its path). The seam cannot be checked from one side.")
        return EXIT_COULD_NOT_RUN
    try:
        import check_data_plane_approved as gate
    except Exception as exc:
        print(f"could not run: check_guard_seam — the framework gate is not importable ({exc})")
        return EXIT_COULD_NOT_RUN

    fails, pairs = [], 0

    # ---- 1 · THE PARSER
    for name, text in _FIXTURES:
        pairs += 1
        try:
            mine = guard.parse_flat(text)
        except Exception as exc:
            fails.append(f"parser/{name}: the guard refused a sign-off it must read ({exc})")
            continue
        try:
            theirs = gate.parse_flat(text)
        except Exception as exc:
            fails.append(f"parser/{name}: the framework refused a sign-off it must read ({exc})")
            continue
        if mine != theirs:
            fails.append(f"parser/{name}: guard {mine!r} != framework {theirs!r}")
            continue
        # …and both must agree with yaml.safe_load wherever yaml can read it flatly.
        try:
            ref = yaml.safe_load(text)
        except Exception:
            ref = None
        if isinstance(ref, dict):
            for k, v in mine.items():
                if k not in ref:
                    fails.append(f"parser/{name}: the pair invented the key {k!r}, "
                                 f"which yaml.safe_load does not see")
                elif str(ref[k] if ref[k] is not None else "") != v:
                    fails.append(f"parser/{name}: key {k!r} — the pair reads {v!r}, "
                                 f"yaml.safe_load reads {ref[k]!r}")

    for name, text in _MUST_REFUSE:
        pairs += 1
        gr = tr = None
        try:
            guard.parse_flat(text)
        except Exception:
            gr = "refused"
        try:
            gate.parse_flat(text)
        except Exception:
            tr = "refused"
        if gr != "refused":
            fails.append(f"refuse/{name}: the guard ACCEPTED a shape it must refuse — a sign-off it "
                         f"misreads is worse than one it cannot read")
        if tr != "refused":
            fails.append(f"refuse/{name}: the framework ACCEPTED a shape it must refuse")

    # ---- 2 · THE DIGEST and 3 · THE VERDICT, over one fixture per reject class
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases = []

        b = _seed(tmp, "approved"); gate._rule(b); gate._sign(b)
        cases.append(("approved", b, True))
        cases.append(("missing", _seed(tmp, "missing"), False))
        b = _seed(tmp, "uncovered"); gate._rule(b); gate._sign(b, covers="NS-ALPHA-01")
        cases.append(("uncovered", b, False))
        b = _seed(tmp, "moved"); gate._rule(b); gate._sign(b, digest="sha256:" + "0" * 64)
        cases.append(("moved", b, False))
        b = _seed(tmp, "agent"); gate._rule(b); gate._sign(b, submitted_via="agent")
        cases.append(("agent-stamped", b, False))
        b = _seed(tmp, "unratified"); gate._rule(b); gate._sign(b, verdict="rejected")
        cases.append(("unratified", b, False))
        b = _seed(tmp, "unrun", issues=False); gate._sign(b, covers="")
        cases.append(("register-unrun", b, False))
        cases.append(("legacy", _seed(tmp, "legacy", pipelines=False), None))

        for name, root, want_open in cases:
            pairs += 1
            mine, _ = guard.data_plane_digest(root)
            theirs, files = gate.data_plane_digest(root)
            if mine != theirs:
                fails.append(f"digest/{name}: guard {mine[:19]} != framework {theirs[:19]} — the "
                             f"two would disagree about whether the plane moved")
            if not files:
                fails.append(f"digest/{name}: the surface covered ZERO files, so the roll-up "
                             f"asserts nothing (a digest over nothing is not a digest)")

            pairs += 1
            code, _ = guard.gate_state(str(root))
            st = gate.approval_state(root)
            guard_open = (code == "approved")
            gate_open = st.approved
            if want_open is None:
                if code != "not_declared" or st.applies:
                    fails.append(f"verdict/{name}: a bundle declaring one pipeline must be "
                                 f"`not_declared` on both sides; guard said {code!r}, framework "
                                 f"applies={st.applies}")
            elif guard_open != gate_open or guard_open != want_open:
                fails.append(f"verdict/{name}: guard {'ALLOW' if guard_open else 'DENY'}, "
                             f"framework {'ALLOW' if gate_open else 'DENY'}, expected "
                             f"{'ALLOW' if want_open else 'DENY'}")

        # ---- 4 · THE SURFACE REACHES EVERY DECLARED PLANE
        pairs += 1
        b = _seed(tmp, "surface"); gate._rule(b); gate._sign(b)
        manifest = yaml.safe_load((b / "mac.project.yaml").read_text(encoding="utf-8")) or {}
        covered = {rel for rel, _ in gate._SURFACE}
        for key, default in (("descriptors", "data/datasets"), ("transforms", "data/transforms"),
                             ("sources", "data/sources"), ("lookups", "data/lookups")):
            declared = manifest.get(key) or default
            if declared.rstrip("/") not in covered:
                fails.append(f"surface/{key}: the manifest declares {declared!r} and the digest "
                             f"surface does not cover it — a plane outside the surface can be "
                             f"changed after a sign-off without staling it")
        if "data/quality/data_quality_register.yaml" not in gate._SURFACE_SINGLETONS:
            fails.append("surface/register: the register is NOT in the digest surface. It must be: "
                         "that is what makes a disposition written after the sign-off stale the "
                         "approval it was meant to satisfy, which is the only thing stopping an "
                         "agent clearing the register with `resolved` and no human name.")

        # The guard's surface must be the same enumeration, not merely a similar one.
        pairs += 1
        if tuple(guard._SURFACE) != tuple(gate._SURFACE):
            fails.append(f"surface/enumeration: guard {guard._SURFACE} != framework {gate._SURFACE}")
        if tuple(guard._SURFACE_SINGLETONS) != tuple(gate._SURFACE_SINGLETONS):
            fails.append("surface/singletons: the two enumerations differ")

    if fails:
        for f in fails:
            print(f"  {f}")
        print(f"FAIL: check_guard_seam — {len(fails)} disagreement(s) over {pairs} checked pairing(s) "
              f"between {guard_path.name} and check_data_plane_approved.py")
        return EXIT_FAIL
    print(f"PASS: check_guard_seam — {pairs}/{pairs} pairing(s) agree: the guard's stdlib parser and "
          f"yaml.safe_load over {len(_FIXTURES)} sign-off shapes and {len(_MUST_REFUSE)} refused "
          f"shapes; the two digest roll-ups and the two verdicts over 8 fixtures spanning the reject "
          f"classes; and the digest surface reaches all 4 declared planes plus the register")
    return EXIT_PASS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    # This gate's bundle run and its self-test are the same work: it seeds its own fixtures either
    # way, because what it judges is a relationship between two code paths and not a bundle's state.
    return run(Path(a.root) if a.root else None)


if __name__ == "__main__":
    sys.exit(main())
