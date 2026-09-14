#!/usr/bin/env python3
"""check_dq_resolution_sync.py — the DATA-QUALITY ↔ TRANSFORM ↔ RESOLUTION-MAP ↔ ACCEPTANCE gate.

The four data-plane planes must never drift:
  * data/quality/data_quality_register.yaml   — the DEFECTS (issues[].id + status + finding)
  * data/transforms/<t>.yaml                   — the TRANSFORM rules that dissolve defects
  * data/quality/impurity_resolution_map.yaml  — the CROSS-LINK (finding_id -> resolving_transforms)
  * acceptance/*.yaml                          — the TESTS excused against a defect (accepted.dq_id)

A transform that "dissolves an impurity" (a rule with an `impurity_class`) must SAY which registered
defect it resolves — `resolves: [DQ-id, ...]` on the rule — and the resolution map must link that
finding back to this transform. Otherwise the wiki's Cleaning tab (rules) and Quality tab (register)
tell different stories: a fix that isn't recorded as a problem, or a problem claimed fixed by nothing.

WHAT WAS MISSING, found by the 2026-09-12 framework-gate review
-----------------------------------------------------------------
Every population here comes from files under `<root>/data`, read with a loader that treats "missing"
and "unreadable" alike as an empty document. A NONEXISTENT root therefore produced the exact same
"in sync" verdict, exit 0, as a real bundle that legitimately has no DQ register yet — there was no
argument parsing at all, and no path this gate could exit 2 from except calling it with the wrong
argument COUNT. A root that does not exist, or that carries no `data/` plane at all, is now its own
refusal; a root whose `data/` plane is real but genuinely empty of all four registers still prints a
verdict — with an explicit, honest zero — rather than being indistinguishable from "could not find
the bundle".

WHAT WAS MISSING, measured 2026-09-14 (protocol/2026-09-14/003)
-----------------------------------------------------------------
The loop above closes the REGISTER↔TRANSFORM half and nothing else, and three measured defects kept
it from closing at all. All three are joins on an id this gate was already reading.

1. NO `status` ON AN ISSUE. The register's keys were `confidence, current_handling, finding, id,
   residual_risk, severity, sme_owner, table, title`. `metadata.status: open` sits at the REGISTER
   level and says nothing about any one issue. So "still open" was INFERRED by joining to the
   resolution map and TREATING ABSENCE AS OPEN — which makes an issue a named human examined and
   deliberately tolerated indistinguishable from an issue nobody has ever read. Those are the two
   most different things in the register. ABSENCE IS NOT A STATE. The closed set lives in
   mac_vocabulary.yaml#dq_status (`open | accepted | resolved | wont_fix`), and `accepted`/`wont_fix`
   REQUIRE a `ruled_by` and a `reason` because they are the two terms that CLAIM a human acted.

2. 44 ENTRIES, 43 DISTINCT IDS. One id appeared twice, and every join in this loop runs on that id,
   so one pair of issues was unaddressable by the very mechanism meant to resolve them. A register
   that cannot be keyed by its own id has no working joins, only lucky ones.

3. `dq_id` IN THE ACCEPTANCE PLANE WAS NEVER CHECKED TO RESOLVE — the testing plane's own notes said
   so in prose ("Nothing checks that accepted.dq_id resolves to a real DQ register entry") while the
   plane's contract said it "must resolve in data/quality/". A test could therefore be excused
   against a defect that does not exist. Now checked in BOTH directions, because they are different
   failures: an `accepted:` naming no registered issue is a FAILURE (the excuse is fictional), and a
   `resolved` issue still named by an `accepted:` block is REPORTED (the excuse is stale — the defect
   was fixed and the test is still being let off for it).

THE LAW IS READ, NEVER RESTATED. Membership comes from mac_vocabulary.yaml#dq_status, and the
per-term evidence burden comes from that term's own `requires:` list. Nothing here re-lists the
members — a closed vocabulary hand-copied into code is the exact drift check_vocabulary_drift was
built to catch. The vocabulary path is a parameter so the self-test can prove the refusal fires
without touching the real vocabulary.

OFFLINE + pure-structural (files on disk, no AWS).
Usage:  python3 tools/check_dq_resolution_sync.py [bundle-root] [--vocabulary PATH]
    exit 0 = the four planes are in sync
    exit 1 = a drift (error) was found
    exit 2 = could not run (root missing, its data/ plane does not exist, no population at all,
             or the dq_status law could not be read)
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from pathlib import Path

import yaml

COVERAGE = {"resolved", "partial", "gap"}
NAME = "check_dq_resolution_sync"
VOCAB_DEFAULT = pathlib.Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"

# ── THE REJECT CLASSES. Every finding is printed under one of these names, which is what turns
#    "something was rejected" into "THIS class was rejected" — the difference between a gate that
#    refuses and a gate that teaches. The self-test seeds one mutant per class and asserts each is
#    both rejected AND attributed, and that the name does not also fire on the clean fixture.
DUPLICATE_ID = "duplicate-id"
STATUS_MISSING = "status-missing"
STATUS_UNKNOWN = "status-unknown"
RULING_MISSING = "ruling-missing"
ACCEPTED_DANGLING = "accepted-dq-id-dangling"
ACCEPTED_STALE = "accepted-dq-id-resolved"
RESOLUTION_DANGLING = "resolution-dangling"
RESOLUTION_TRANSFORM = "resolution-transform-missing"
COVERAGE_INVALID = "coverage-invalid"
RESOLVES_UNREGISTERED = "resolves-unregistered"
RESOLVES_UNLINKED = "resolves-unlinked"
IMPURITY_UNREGISTERED = "impurity-unregistered"   # the one WARN class, warn-first by design


class LawUnavailable(RuntimeError):
    """The dq_status vocabulary could not be read. A gate that cannot state its law must not judge."""


def dq_status_law(vocab_path: Path) -> dict:
    """{term: {requires: [...], ...}} from mac_vocabulary.yaml#dq_status.

    READ, never restated. The `requires` list on each term carries that term's own evidence burden,
    so the rule "accepted and wont_fix need a ruled_by and a reason" lives in the vocabulary beside
    the terms it governs rather than in a second home here."""
    try:
        doc = yaml.safe_load(vocab_path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        raise LawUnavailable(f"cannot read {vocab_path}: {e}") from e
    block = (doc or {}).get("dq_status")
    if not isinstance(block, dict):
        raise LawUnavailable(f"{vocab_path.name} declares no `dq_status` block — the disposition "
                             f"axis has no law, so no issue's status can be judged")
    terms = block.get("terms") or {}
    if not terms:
        raise LawUnavailable(f"{vocab_path.name}#dq_status declares no terms — an empty closed set "
                             f"would reject every issue in the register, which is not a measurement")
    return {str(k): (v if isinstance(v, dict) else {}) for k, v in terms.items()}


def _load(p: Path):
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] cannot parse {p}: {e}")
        return None


def _ids(rule):
    declared = rule.get("resolves") or rule.get("finding_id")
    return [declared] if isinstance(declared, str) else list(declared or [])


def _accepted_blocks(root: Path):
    """[(file, property_id, accepted_dict)] over acceptance/*.yaml.

    The acceptance plane is the fourth population and the one nothing has ever joined. A bundle with
    no acceptance plane yields an honest empty list — that is a zero, reported as one, not a pass."""
    out = []
    adir = root / "acceptance"
    if not adir.is_dir():
        return out
    for f in sorted(adir.glob("*.yaml")):
        doc = _load(f) or {}
        if not isinstance(doc, dict):
            continue
        for prop in (doc.get("properties") or []):
            if not isinstance(prop, dict):
                continue
            acc = prop.get("accepted")
            if isinstance(acc, dict):
                out.append((f.name, str(prop.get("id", "?")), acc))
    return out


def scan(root: Path, law: dict) -> dict:
    """The four populations plus every finding, each attributed to a reject class."""
    data = root / "data"
    qdir = data / "quality"
    tdir = data / "transforms"

    reg = _load(qdir / "data_quality_register.yaml") or {}
    issues = [i for i in (reg.get("issues") or reg.get("findings") or []) if isinstance(i, dict)]
    issue_ids = {i.get("id") for i in issues if i.get("id")}
    resmap = _load(qdir / "impurity_resolution_map.yaml") or {}
    resolutions = resmap.get("resolutions") or []
    transforms = {p.stem: (_load(p) or {}) for p in sorted(tdir.glob("*.yaml"))} if tdir.exists() else {}
    accepted = _accepted_blocks(root)

    errors: list[tuple[str, str]] = []     # (class, message)
    warnings: list[tuple[str, str]] = []

    # ── 1 · THE REGISTER MUST BE KEYABLE BY ITS OWN ID. Every join below runs on it.
    seen: dict = {}
    for pos, i in enumerate(issues, 1):
        iid = i.get("id")
        if iid is None:
            continue
        seen.setdefault(iid, []).append(pos)
    for iid, positions in sorted(seen.items()):
        if len(positions) > 1:
            errors.append((DUPLICATE_ID,
                           f"register id '{iid}' appears {len(positions)} times (entries "
                           f"{', '.join(str(p) for p in positions)}) — every join in this loop is on "
                           f"that id, so these entries are unaddressable by the mechanism meant to "
                           f"resolve them"))

    # ── 2 · EVERY ISSUE MUST CARRY A DISPOSITION, and a ruling must carry its evidence.
    by_status: dict = {}
    status_of: dict = {}
    for pos, i in enumerate(issues, 1):
        iid = i.get("id") or f"<entry {pos}, no id>"
        st = i.get("status")
        if st is None:
            errors.append((STATUS_MISSING,
                           f"issue '{iid}' declares no `status` — absence is not a state, and it is "
                           f"the one that makes 'deliberately accepted' and 'nobody has looked' "
                           f"identical. Write one of: {', '.join(sorted(law))}"))
            continue
        st = str(st)
        if st not in law:
            errors.append((STATUS_UNKNOWN,
                           f"issue '{iid}' status '{st}' is not a member of mac.dq_status "
                           f"({', '.join(sorted(law))})"))
            continue
        by_status[st] = by_status.get(st, 0) + 1
        if i.get("id"):
            status_of[i["id"]] = st
        for need in (law[st].get("requires") or []):
            if not str(i.get(need) or "").strip():
                errors.append((RULING_MISSING,
                               f"issue '{iid}' is '{st}' but carries no `{need}` — '{st}' CLAIMS a "
                               f"human acted, so it must name the evidence that one did"))

    # ── 3 · THE RESOLUTION MAP must point at real issues and real transforms.
    res_by_finding: dict = {}
    for r in resolutions:
        fid = r.get("finding_id")
        res_by_finding.setdefault(fid, []).append(r)
        if fid not in issue_ids:
            errors.append((RESOLUTION_DANGLING,
                           f"resolution finding_id '{fid}' is not in the DQ register (dangling)"))
        for t in (r.get("resolving_transforms") or []):
            if t not in transforms:
                errors.append((RESOLUTION_TRANSFORM,
                               f"resolution '{fid}' names resolving_transform '{t}' — no such "
                               f"transform descriptor"))
        cov = r.get("coverage")
        if cov not in COVERAGE:
            errors.append((COVERAGE_INVALID,
                           f"resolution '{fid}' coverage '{cov}' not in {sorted(COVERAGE)}"))

    # ── 4 · A TRANSFORM THAT DISSOLVES A DEFECT must name it, and be named back.
    for tstem, tr in transforms.items():
        for rule in (tr.get("transforms") or []):
            rid = rule.get("id", "?")
            ids = _ids(rule)
            if rule.get("impurity_class") and not ids:
                warnings.append((IMPURITY_UNREGISTERED,
                                 f"transform '{tstem}' rule '{rid}' dissolves impurity_class "
                                 f"'{rule.get('impurity_class')}' but declares no `resolves` — "
                                 f"register the DQ issue"))
                continue
            for fid in ids:
                if fid not in issue_ids:
                    errors.append((RESOLVES_UNREGISTERED,
                                   f"transform '{tstem}' rule '{rid}' resolves '{fid}' — not in the "
                                   f"DQ register"))
                    continue
                linked = any(tstem in (r.get("resolving_transforms") or [])
                             for r in res_by_finding.get(fid, []))
                if not linked:
                    errors.append((RESOLVES_UNLINKED,
                                   f"transform '{tstem}' rule '{rid}' resolves '{fid}' but the "
                                   f"resolution map has no entry linking '{fid}' back to '{tstem}'"))
        # OPEN proposals are not applied yet — only validate a declared id exists.
        for rule in (tr.get("open_transforms") or []):
            for fid in _ids(rule):
                if fid not in issue_ids:
                    errors.append((RESOLVES_UNREGISTERED,
                                   f"transform '{tstem}' open item '{rule.get('id', '?')}' "
                                   f"references '{fid}' — not in the DQ register"))

    # ── 5 · `dq_id` MUST RESOLVE, BOTH DIRECTIONS. The join nothing has ever run.
    for fname, pid, acc in accepted:
        did = acc.get("dq_id")
        if not did:
            errors.append((ACCEPTED_DANGLING,
                           f"{fname}: property '{pid}' has an `accepted:` block with no `dq_id` — an "
                           f"unsigned excuse is not an acceptance"))
            continue
        if did not in issue_ids:
            errors.append((ACCEPTED_DANGLING,
                           f"{fname}: property '{pid}' is accepted against '{did}', which is not in "
                           f"the DQ register — the test is excused for a defect that does not exist"))
            continue
        if status_of.get(did) == "resolved":
            warnings.append((ACCEPTED_STALE,
                             f"{fname}: property '{pid}' is still accepted against '{did}', which the "
                             f"register now marks resolved — the defect was fixed and the test is "
                             f"still being let off for it; regenerate or retire the acceptance"))

    return {"issues": issues, "issue_ids": issue_ids, "resolutions": resolutions,
            "transforms": transforms, "accepted": accepted, "by_status": by_status,
            "errors": errors, "warnings": warnings}


def _progress(by_status: dict, law: dict, n_issues: int) -> str:
    """`N issues · M resolved · K accepted · J open` — the denominator the estate never published."""
    bits = [f"{n_issues} issue(s)"]
    for term in sorted(law):
        bits.append(f"{by_status.get(term, 0)} {term}")
    undeclared = n_issues - sum(by_status.values())
    if undeclared:
        bits.append(f"{undeclared} WITH NO STATUS AT ALL")
    return " · ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--vocabulary", default=str(VOCAB_DEFAULT),
                    help="path to mac_vocabulary.yaml (the closed dq_status law)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    if not (root / "data").is_dir():
        print(f"could not run: {root} has no data/ plane at all, so dq-resolution-sync has nothing "
              f"to compare", file=sys.stderr)
        return 2
    try:
        law = dq_status_law(Path(a.vocabulary))
    except LawUnavailable as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2

    res = scan(root, law)
    issues, resolutions = res["issues"], res["resolutions"]
    transforms, accepted = res["transforms"], res["accepted"]
    errors, warnings = res["errors"], res["warnings"]

    print(f"── dq-resolution-sync gate ── {len(issues)} registered issue(s), {len(resolutions)} "
          f"resolution(s), {len(transforms)} transform(s), {len(accepted)} accepted test(s) "
          f"under {root} ──\n")

    if not issues and not resolutions and not transforms:
        print(f"could not run: {root} carries no DQ register, resolution map, or transform — "
              f"0 of 3 planes present, nothing to check", file=sys.stderr)
        return 2

    for cls, w in warnings:
        print(f"  [WARN]  {cls}: {w}")
    for cls, e in errors:
        print(f"  [ERROR] {cls}: {e}")
    print()
    print(f"  PROGRESS: {_progress(res['by_status'], law, len(issues))}")
    print()

    examined = (f"{len(transforms)} transform(s), {len(issues)} issue(s), {len(resolutions)} "
                f"resolution(s), {len(accepted)} accepted test(s) examined")
    if errors:
        print(f"FAIL: {NAME} — {len(errors)} drift(s) over {examined} ({len(warnings)} warning(s))")
        return 1
    print(f"PASS: {NAME} — 0 drift(s) over {examined} ({len(warnings)} warning(s))")
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# SELF-TEST — a clean fixture that must PASS over a non-zero denominator, the three refusal paths,
# and ONE MUTANT PER REJECT CLASS, each asserted to be (a) rejected, (b) attributed BY CLASS NAME in
# the output, and (c) discriminating — the class name must NOT also appear on the clean run, or it
# attributes nothing. Fixtures are domain-neutral on purpose: this repo is public.
#
# The fixture's statuses are READ FROM THE VOCABULARY, never typed, so the corpus cannot drift from
# the law it exercises. `_ruled` and `_plain` pick a term BY ITS EVIDENCE BURDEN rather than by name,
# so adding a fifth term to mac.dq_status does not silently stop exercising a class.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _ruled(law: dict) -> str:
    """A term that REQUIRES evidence — the accepted/wont_fix class."""
    for t in sorted(law):
        if law[t].get("requires"):
            return t
    raise RuntimeError("mac.dq_status declares no term requiring evidence to mutate with")


def _plain(law: dict, *, exclude=()) -> str:
    """A term that requires no evidence — the open/resolved class."""
    for t in sorted(law):
        if not law[t].get("requires") and t not in exclude:
            return t
    raise RuntimeError("mac.dq_status declares no evidence-free term to seed with")


def _seed(root: Path, *, register=None, resmap=None, transforms=None, acceptance=None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if register is not None or resmap is not None:
        (root / "data" / "quality").mkdir(parents=True, exist_ok=True)
    if register is not None:
        (root / "data" / "quality" / "data_quality_register.yaml").write_text(
            yaml.safe_dump(register, sort_keys=False), encoding="utf-8")
    if resmap is not None:
        (root / "data" / "quality" / "impurity_resolution_map.yaml").write_text(
            yaml.safe_dump(resmap, sort_keys=False), encoding="utf-8")
    if transforms is not None:
        d = root / "data" / "transforms"
        d.mkdir(parents=True, exist_ok=True)
        for stem, doc in transforms.items():
            (d / f"{stem}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    if acceptance is not None:
        d = root / "acceptance"
        d.mkdir(parents=True, exist_ok=True)
        (d / "properties.yaml").write_text(yaml.safe_dump(acceptance, sort_keys=False),
                                           encoding="utf-8")


def _clean(law: dict) -> dict:
    """The whole loop, closed: two issues, one resolved-and-linked, one ruled-and-evidenced."""
    plain = _plain(law)                       # 'open' — no evidence required
    ruled = _ruled(law)                       # 'accepted' — ruled_by + reason required
    reg = {"issues": [
        {"id": "DQ-001", "title": "duplicate rows", "finding": "1 duplicate row measured",
         "status": plain},
        {"id": "DQ-002", "title": "tolerated skew", "finding": "2 skewed rows measured",
         "status": ruled, "ruled_by": "quality-owner", "reason": "the source cannot restate it"},
    ]}
    for need in (law[ruled].get("requires") or []):
        reg["issues"][1].setdefault(need, "declared")
    return {
        "register": reg,
        "resmap": {"resolutions": [{"finding_id": "DQ-001", "resolving_transforms": ["dedupe"],
                                    "coverage": "resolved"}]},
        "transforms": {"dedupe": {"transforms": [{"id": "T1", "impurity_class": "duplicate",
                                                  "resolves": ["DQ-001"]}]}},
        "acceptance": {"properties": [{"id": "P-1", "accepted": {
            "dq_id": "DQ-002", "by": "operator", "on": "2026-09-14",
            "reason": "the skew is real and tolerated"}}]},
    }


def _mutate(base: dict, fn) -> dict:
    import copy
    d = copy.deepcopy(base)
    fn(d)
    return d


def _self_test() -> int:
    import subprocess
    import tempfile

    try:
        law = dq_status_law(VOCAB_DEFAULT)
    except LawUnavailable as e:
        print(f"FAIL: {NAME} self-test — the law it enforces is unreadable: {e}")
        return 1

    plain = _plain(law)
    ruled = _ruled(law)
    resolved_like = _plain(law, exclude=(plain,))   # the second evidence-free term ('resolved')
    base = _clean(law)
    me = str(Path(__file__).resolve())

    def run(r, *extra):
        p = subprocess.run([sys.executable, me, str(r), *extra],
                           capture_output=True, text=True, timeout=300)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    # ── the non-finding cases: one clean pass and the three ways this gate refuses ──────────────
    # (name, seed, extra argv, expected exit, marker, why)
    cases = [
        ("clean", lambda r: _seed(r, **base), (), 0, "PASS:",
         "a closed loop over a real denominator passes — 2 issues, 1 resolution, 1 accepted test"),
        ("not-a-directory", lambda r: None, (), 2, "not a directory",
         "a root that does not exist is a refusal, never a tick"),
        ("no-data-plane", lambda r: r.mkdir(parents=True, exist_ok=True), (), 2, "no data/ plane",
         "a real directory with no data/ plane has nothing to compare"),
        ("empty-data-plane", lambda r: (r / "data" / "sources").mkdir(parents=True), (), 2,
         "0 of 3 planes present",
         "a data/ plane carrying none of the registers is could-not-run, not 'in sync'"),
        ("law-unavailable", lambda r: _seed(r, **base), ("--vocabulary", "/nonexistent.yaml"), 2,
         "could not run",
         "a gate that cannot read its own closed vocabulary must refuse, not judge"),
    ]

    # ── ONE MUTANT PER REJECT CLASS ─────────────────────────────────────────────────────────────
    def dup(d):
        d["register"]["issues"].append(dict(d["register"]["issues"][0]))

    def no_status(d):
        d["register"]["issues"][0].pop("status", None)

    def bad_status(d):
        d["register"]["issues"][0]["status"] = "mostly_fine"

    def no_ruling(d):
        for need in (law[ruled].get("requires") or []):
            d["register"]["issues"][1].pop(need, None)

    def acc_dangling(d):
        d["acceptance"]["properties"][0]["accepted"]["dq_id"] = "DQ-NOPE"

    def acc_stale(d):
        d["register"]["issues"][1]["status"] = resolved_like
        for need in (law[ruled].get("requires") or []):
            d["register"]["issues"][1].pop(need, None)

    def res_dangling(d):
        d["resmap"]["resolutions"][0]["finding_id"] = "DQ-NOPE"

    def res_transform(d):
        d["resmap"]["resolutions"][0]["resolving_transforms"] = ["ghost"]

    def bad_coverage(d):
        d["resmap"]["resolutions"][0]["coverage"] = "mostly"

    def unregistered(d):
        d["transforms"]["dedupe"]["transforms"][0]["resolves"] = ["DQ-NOPE"]

    def unlinked(d):
        d["resmap"]["resolutions"] = []

    def unregistered_impurity(d):
        d["transforms"]["dedupe"]["transforms"][0].pop("resolves", None)

    mutants = [
        (DUPLICATE_ID, dup, 1,
         "44 entries / 43 distinct ids — one id twice makes both entries unaddressable by every "
         "join in this loop"),
        (STATUS_MISSING, no_status, 1,
         "an issue with no disposition — the defect that made ABSENCE stand in for 'open'"),
        (STATUS_UNKNOWN, bad_status, 1,
         "a spelling outside mac.dq_status — the class a closed vocabulary exists for"),
        (RULING_MISSING, no_ruling, 1,
         f"'{ruled}' without its required evidence — a ruling nobody signed is not a ruling"),
        (ACCEPTED_DANGLING, acc_dangling, 1,
         "a test excused against a defect that does not exist — direction one of the dq_id join"),
        (ACCEPTED_STALE, acc_stale, 0,
         "a test still excused against a defect the register marks resolved — direction two, "
         "REPORTED not failed, because the excuse is stale rather than fictional"),
        (RESOLUTION_DANGLING, res_dangling, 1,
         "the resolution map names a finding the register never declared"),
        (RESOLUTION_TRANSFORM, res_transform, 1,
         "the resolution map names a transform descriptor that does not exist"),
        (COVERAGE_INVALID, bad_coverage, 1,
         "a coverage outside the closed set"),
        (RESOLVES_UNREGISTERED, unregistered, 1,
         "a transform claims to fix a defect nobody registered"),
        (RESOLVES_UNLINKED, unlinked, 1,
         "a transform resolves a real defect and the map never links it back — the original "
         "two-stories drift"),
        (IMPURITY_UNREGISTERED, unregistered_impurity, 0,
         "a rule dissolving an impurity_class with no `resolves` — WARN-first by design, so "
         "existing sources migrate without a hard break"),
    ]

    bad = 0
    clean_out = ""
    all_classes = [c for c, *_ in mutants]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, seed, extra, want_rc, marker, why) in enumerate(cases):
            r = Path(tmp) / f"case_{i}"
            if name != "not-a-directory":
                r.mkdir(parents=True, exist_ok=True)
            if seed:
                seed(r)
            rc, out = run(r, *extra)
            ok = rc == want_rc and (marker is None or marker in out)
            if name == "clean":
                clean_out = out
                # a class marker on the clean run would attribute nothing later
                stray = [c for c in all_classes if c in out]
                if stray:
                    ok = False
                    why += f"  [STRAY CLASS ON CLEAN RUN: {', '.join(stray)}]"
            if "Traceback (most recent call last)" in out:
                ok = False
            bad += 0 if ok else 1
            print(f"  {'✓' if ok else '✗'} {name:<26} exit {rc:<2} expected {want_rc} — {why}")

        for i, (cls, fn, want_rc, why) in enumerate(mutants):
            r = Path(tmp) / f"mutant_{i}"
            r.mkdir(parents=True, exist_ok=True)
            mutated = _mutate(base, fn)
            if mutated == base:
                print(f"  ✗ MUTANT {cls:<18} fixture did not actually mutate the clean loop")
                bad += 1
                continue
            _seed(r, **mutated)
            rc, out = run(r)
            rejected = rc == want_rc
            attributed = cls in out
            discriminates = cls not in clean_out
            ok = rejected and attributed and discriminates
            bad += 0 if ok else 1
            verdict = "FAIL" if want_rc == 1 else "WARN"
            if ok:
                detail = f"{verdict}ed as its own class (exit {rc}, {cls!r})"
            else:
                bits = [f"exit {rc}"]
                if not rejected:
                    bits.append(f"expected exit {want_rc}")
                if not attributed:
                    bits.append(f"class name {cls!r} absent — unattributed")
                if not discriminates:
                    bits.append(f"class name {cls!r} also fires on the clean fixture")
                detail = ", ".join(bits)
            print(f"  {'✓' if ok else '✗'} {('MUTANT ' + cls):<26} {detail} — {why}")

    n = len(cases) + len(mutants)
    if bad:
        print(f"FAIL: {NAME} self-test — {bad} of {n} assertion(s) failed "
              f"({len(cases)} fixture(s) + {len(mutants)} rule mutant(s))")
        return 1
    n_err = sum(1 for _, _, rc, _ in mutants if rc == 1)
    n_warn = len(mutants) - n_err
    print(f"PASS: {NAME} self-test — {n}/{n}: {len(cases)} fixture(s) (a closed loop passes; "
          f"a missing root, a missing data/ plane, an empty data/ plane and an unreadable "
          f"vocabulary all refuse on exit 2) + {len(mutants)} mutant(s) of its own rule, each "
          f"attributed by class name ({n_err} FAIL, {n_warn} REPORTED): "
          f"{', '.join(all_classes)} — statuses read from {VOCAB_DEFAULT.name}#dq_status "
          f"({len(law)} declared term(s): {', '.join(sorted(law))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
