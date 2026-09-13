#!/usr/bin/env python3
"""Suite history — the trend line a unit-test runner gives you and this bundle did not.

Operator, verbatim: "i need mechnism to trigger and refresh tests myself. currently is reported that
4 are still failing. we also need historical trend ... increasing decreasing in diagram like unit
tests in java pysthon etc"

Both halves were missing for the same reason: each run OVERWRITES acceptance/*_runs.json, so the
bundle has always known its current state and never its direction. "4 failing" cannot be read as
good or bad news without knowing whether it was 2 yesterday or 9.

HISTORY IS RECONSTRUCTED, NOT STARTED. `--from-git` replays every version of the run records that
git holds and recovers the real dates and the real per-property outcomes. That matters more than
convenience: a trend seeded today would be one point, and a chart with one point invites the reader
to imagine the slope.

── THE CLAIM THAT WAS HERE, AND WHAT IT ACTUALLY MEASURED ─────────────────────────────────────

This file used to assert, flatly: *"The run records are committed."* Measured on 2026-09-13, that
sentence is true in exactly one place and false everywhere it matters:

    <SOURCES>              7 records · 44 committed versions · 61 history rows replayed from them
                           — AND NO GIT REMOTE. Nothing here can ever be published or pulled.
    <LIVE>                 0 records in all of history   (the bundle the operator actually opens)
    meaning-as-code        0 records in all of history   (this framework)
    mac-platform           0 records in all of history   (the console that reads them)

So `--from-git` worked, once, in the one repository that cannot publish — and the estate-wide sweep
that reported ZERO was also right. The claim was not a lie; it was a claim with an undeclared
denominator, which is this bundle's own recurring defect turned on itself.

BOTH HALVES WERE FIXED, and the behaviour matters more than the wording. `--from-records` replays
the dated, append-only records that `tools/suite_record.py` now writes beside the overwritten one,
and `--record` reads the commit the RECORD carries instead of stamping the string "working-tree" —
so history no longer depends on a repository having been committed, or existing at all.

Records are APPEND-ONLY and keyed on (suite, run_at, commit) so replaying git twice cannot
double-count, and a re-run recorded by hand cannot silently displace one recovered from history.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_record as _rec  # noqa: E402

HIST = "acceptance/suite_history.jsonl"
# Discovered, not hardcoded. The list was tier1/tier2 and stayed that way while two new suites
# landed carrying 11.378 cases — the trend would have gone on charting the old pair and silently
# omitted the ones that matter, which is the same defect as a silently capped sweep.
#
# THE ALIAS MAP NOW LIVES IN ONE PLACE (`suite_record.HISTORY_ALIASES`) because a second writer
# arrived. `run_suite.py` keyed its rows off the suite FILENAME, which produced "properties"
# alongside the existing "tier1" — the same suite as two half-length series. Re-exported here so
# anything importing SUITE_NAMES from this module keeps working.
SUITE_NAMES = _rec.HISTORY_ALIASES


def _suites(root: str) -> dict:
    import glob as _g
    out = {}
    for f in sorted(_g.glob(os.path.join(root, "acceptance", "*_runs.json"))):
        b = os.path.basename(f)
        out[os.path.join("acceptance", b)] = _rec.suite_key(b)
    return out or {"acceptance/property_runs.json": "tier1"}


def _tally(doc: dict) -> dict:
    """Per-status counts plus the per-property outcome map, from one runs document."""
    res = (doc or {}).get("results") or []
    out = {"pass": 0, "fail": 0, "accepted": 0, "error": 0}
    props = {}
    for r in res:
        st = str(r.get("status", "")).lower()
        if st in out:
            out[st] += 1
        props[r.get("id")] = r.get("status")
    cases = sum(len(r.get("rows") or []) for r in res)
    # THE DENOMINATOR COMES FROM THE RECORD WHEN THE RECORD HAS ONE. `len(res)` is the number of
    # results the run happened to write, which for a filtered run is the size of the filter — so
    # "1/1 pass" was a true sentence about `--id`. `declared` is the population the SUITE declares.
    total = doc.get("declared") if isinstance((doc or {}).get("declared"), int) else len(res)
    extra = {k: doc[k] for k in ("examined", "skipped") if isinstance((doc or {}).get(k), int)}
    return {**out, "total": total, "cases": cases, **extra, "properties": props}


def _git(root: str, *args: str) -> str:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True).stdout


def from_git(root: str) -> list[dict]:
    """Every committed version of every runs file, oldest first."""
    top = _git(root, "rev-parse", "--show-toplevel").strip()
    if not top:
        return []
    rows = []
    for rel, suite in _suites(root).items():
        path = os.path.relpath(os.path.join(os.path.abspath(root), rel), top)
        log = _git(top, "log", "--follow", "--format=%H\t%cI", "--", path).strip()
        for line in [l for l in log.split("\n") if l.strip()]:
            sha, iso = line.split("\t")
            blob = _git(top, "show", f"{sha}:{path}")
            if not blob.strip():
                continue
            try:
                doc = json.loads(blob)
            except json.JSONDecodeError:
                continue
            rows.append({"suite": suite, "run_at": iso, "commit": sha[:10],
                         "subject": _git(top, "log", "-1", "--format=%s", sha).strip()[:90],
                         **_tally(doc)})
    return sorted(rows, key=lambda r: r["run_at"])


def _stamp(doc: dict) -> tuple[str, str]:
    """``(commit, subject)`` taken from the RECORD, with the old behaviour as the fallback.

    It used to be the constant ``("working-tree", "uncommitted run")``, because the record carried
    no commit — 0 of 7 did. Two runs against two different ontologies therefore produced two rows
    with the SAME dedup key, so the second silently displaced the first, and the trend could not
    tell a re-run from a re-measurement. A record that names its own commit fixes both.
    """
    commit = doc.get("commit")
    if not commit:
        return "working-tree", "uncommitted run (record carries no commit)"
    if doc.get("commit_dirty"):
        commit += "-dirty"
    eng = (doc.get("engine") or {}).get("kind")
    subject = f"{doc.get('bundle', '?')} · {doc.get('suite', '?')}" + (f" ({eng})" if eng else "")
    if (doc.get("engine") or {}).get("synthetic"):
        subject += " [SYNTHETIC]"
    return commit, subject[:90]


def current(root: str) -> list[dict]:
    """The runs sitting on disk right now — a re-run the operator just triggered."""
    rows = []
    for rel, suite in _suites(root).items():
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue
        doc = json.load(open(p, encoding="utf-8"))
        ts = doc.get("run_at") or __import__("datetime").datetime.fromtimestamp(
            os.path.getmtime(p)).astimezone().isoformat(timespec="seconds")
        commit, subject = _stamp(doc)
        rows.append({"suite": suite, "run_at": ts, "commit": commit,
                     "subject": subject, **_tally(doc)})
    return rows


def from_records(root: str) -> list[dict]:
    """Every DATED run record on disk — history that does not need a repository.

    `acceptance/runs/<UTC>-<suite>.json` is append-only: one file per run, never overwritten. This
    is the half that makes the trend independent of git, which matters because the only bundle
    holding run records has no remote, and because `<LIVE>`'s 21 dated records are the only run
    evidence in the estate that survived its own suite's overwrite.

    Dedup is the SAME key as everywhere else — (suite, run_at, commit) — so a dated record and its
    committed twin are one row, and replaying both sources twice cannot double-count.
    """
    import glob as _g
    rows = []
    for f in sorted(_g.glob(os.path.join(root, "acceptance", "runs", "*.json"))):
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(doc, dict) or "results" not in doc:
            continue        # dialect A keeps corpus runs in the same directory; skip what is not ours
        suite = _rec.suite_key(f)
        commit, subject = _stamp(doc)
        rows.append({"suite": suite, "run_at": doc.get("run_at") or "", "commit": commit,
                     "subject": subject, **_tally(doc)})
    return [r for r in rows if r["run_at"]]


def load(root: str) -> list[dict]:
    p = os.path.join(root, HIST)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def save(root: str, rows: list[dict]) -> int:
    """Append-only merge, deduped on (suite, run_at, commit)."""
    seen = {(r["suite"], r["run_at"], r["commit"]) for r in load(root)}
    fresh = [r for r in rows if (r["suite"], r["run_at"], r["commit"]) not in seen]
    p = os.path.join(root, HIST)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        for r in sorted(fresh, key=lambda r: r["run_at"]):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(fresh)


BAR = {"pass": "█", "accepted": "▓", "fail": "░", "error": "!"}


def chart(rows: list[dict], suite: str | None = None) -> str:
    rows = [r for r in rows if not suite or r["suite"] == suite]
    if not rows:
        return "  (no history)"
    out = []
    for r in sorted(rows, key=lambda r: r["run_at"]):
        bar = (BAR["pass"] * r["pass"] + BAR["accepted"] * r["accepted"]
               + BAR["fail"] * r["fail"] + BAR["error"] * r["error"])
        out.append(f"  {r['run_at'][:16]}  {r['suite']}  {bar:<26} "
                   f"{r['pass']:>2}/{r['total']:<2} pass · {r['fail']} fail"
                   + (f" · {r['cases']:>6} cases" if r.get("cases") else "")
                   + (f" · {r['accepted']} accepted" if r["accepted"] else "")
                   + f"   {r['commit']}")
    return "\n".join(out)


def deltas(rows: list[dict]) -> list[str]:
    """What CHANGED between consecutive runs of a suite — the thing a tally cannot show."""
    out = []
    for suite in sorted({r["suite"] for r in rows}):
        seq = sorted([r for r in rows if r["suite"] == suite], key=lambda r: r["run_at"])
        for a, b in zip(seq, seq[1:]):
            moved = [(k, a["properties"].get(k), v) for k, v in b["properties"].items()
                     if a["properties"].get(k) != v]
            new = [k for k in b["properties"] if k not in a["properties"]]
            gone = [k for k in a["properties"] if k not in b["properties"]]
            if not (moved or new or gone):
                continue
            out.append(f"  {a['run_at'][:16]} → {b['run_at'][:16]}  [{suite}]  {b['subject']}")
            for k, was, now in moved:
                out.append(f"      {k:<14} {was} → {now}")
            for k in new:
                out.append(f"      {k:<14} + added ({b['properties'][k]})")
            for k in gone:
                out.append(f"      {k:<14} − removed")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--from-git", action="store_true", help="replay committed run records into history")
    ap.add_argument("--from-records", action="store_true",
                    help="replay the dated acceptance/runs/*.json records (no repository needed)")
    ap.add_argument("--record", action="store_true", help="append the runs currently on disk")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    added = 0
    if a.from_git:
        added += save(a.root, from_git(a.root))
    if a.__dict__["from_records"]:
        added += save(a.root, from_records(a.root))
    if a.record:
        added += save(a.root, current(a.root))

    rows = load(a.root)

    # THE PROJECTION IS WRITTEN HERE, not by a shell wrapper. It was in run-tests.sh, so recording
    # by calling this tool directly left the chart showing yesterday's slope while the log was
    # current — a stale graph is worse than no graph, because it is read as fact.
    if rows:
        proj = os.path.join(a.root, "acceptance", "suite_history.json")
        os.makedirs(os.path.dirname(proj), exist_ok=True)
        with open(proj, "w", encoding="utf-8") as fh:
            json.dump({"history": rows}, fh, indent=1, ensure_ascii=False)
    if a.json:
        print(json.dumps({"history": rows}, indent=1, ensure_ascii=False))
        return 0

    if added:
        print(f"  recorded {added} new run(s)\n")
    print(chart(rows))
    d = deltas(rows)
    if d:
        print("\n  WHAT MOVED\n" + "\n".join(d))
    if not rows:
        print("  run the suites first, then --record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
