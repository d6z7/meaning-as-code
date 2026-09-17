#!/usr/bin/env python3
"""Does every declared suite have a run record that can be TRUSTED — and can it be committed?

    PASS: check_run_records — 0 defect(s) over 7 record(s) for 7 declared suite(s)

── WHY THIS GATE EXISTS ───────────────────────────────────────────────────────────────────────

`decisions/PLAN.yaml` R16: *name the gate that exits 2 when this artifact is absent or stale, in
the same paragraph that proposes it, or do not create it.* `tools/suite_record.py` adds `commit`,
`declared`, `examined`, `skipped` and `total` to the run record. This is that gate — without it
those five fields are `authority: sme`, which was adopted 0 of 101 times, and `question_id`, 0 of
21. The counter-example is `accepted:`/`frozen:`, adopted 26 times, *because the runner refuses to
move a red without one.* A field is adopted when something refuses to proceed without it.

── THE REJECT CLASSES, each one a measured defect ─────────────────────────────────────────────

    NO_RECORD         a declared suite with no record at all — exit 2, never a green zero. Three
                      shipped example bundles are in exactly this state and render as healthy.
    NO_COMMIT         no `commit` on the record. 0 of 7 live records carry one, which is why
                      `suite_history.current()` had to stamp the string "working-tree" and why
                      `<LIVE>`'s 60-day-old verdict reads exactly like today's.
    NO_DENOMINATOR    no `declared`/`total`. The denominator was `len(results)`, i.e. whatever the
                      run selected — so `--id <one property>` wrote a record of 1 and "1/1 pass" was a
                      true sentence about a filter.
    HEADER_DISAGREES  the stored `total`/`examined`/`skipped` differ from what the record's own
                      evidence recomputes to. COMPUTE IT, NEVER ACCEPT IT — a runner writing
                      `examined = declared` regardless of what it looked at satisfies every schema
                      and every board while examining nothing.
    SHORT_POPULATION  `total` < `declared`: results are missing for declared properties. A declared
                      property with no result must be NOT_RUN, not absent, because absence reads
                      as nothing-to-report.
    BAD_STATUS        a status outside `PASS|FAIL|ACCEPTED|FROZEN|ERROR|NOT_RUN`.
    GITIGNORED        the record is written to a path git refuses to track. Written and
                      uncommittable is indistinguishable from never written, one week later.

Two things are REPORTED WITH THEIR COUNT and do not fail the gate — the phasing rule, *no key
becomes required in the generation it is invented*:

    STALE      the record's commit is not HEAD. Information, loudly; a 60-day-old record is not a
               gate failure, it is the number the operator could not see.
    SYNTHETIC  `engine.synthetic: true` — a dry run. A valid record and NOT a measurement, so it
               is never allowed to pass silently as evidence.

Usage
    python3 tools/check_run_records.py <bundle>
    python3 tools/check_run_records.py --self-test
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_record as _rec  # noqa: E402


def declared_suites(root: Path) -> dict[Path, list[str]]:
    """Suite file -> declared ids. A suite is any acceptance/*.yaml carrying `properties:`.

    DISCOVERED, NEVER HARDCODED. `suite_history.py` shipped a four-entry SUITE_NAMES map and two
    new suites carrying 11.378 cases landed beside it — the trend went on charting the old pair and
    silently omitted the ones that mattered, which is a silently capped sweep wearing a dict.
    """
    out = {}
    acc = root / "acceptance"
    if not acc.is_dir():
        return out
    for p in sorted(acc.glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("properties"), list) and doc["properties"]:
            out[p] = [q.get("id") for q in doc["properties"] if isinstance(q, dict)]
    return out


def _ignored(root: Path, path: Path) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", str(path)],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _head(root: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--short=10", "HEAD"],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def inspect(root: Path) -> tuple[list[tuple], list[str], int, int]:
    """``(defects, notes, n_records, n_suites)``. One pass, no side effects."""
    suites = declared_suites(root)
    head = _head(root)
    defects: list[tuple] = []
    notes: list[str] = []
    n_records = 0

    for suite_file, ids in suites.items():
        rel = _rec.runs_path(suite_file)
        path = root / rel
        if not path.exists():
            defects.append(("NO_RECORD", rel, f"{suite_file.name} declares {len(ids)} propert"
                                              f"{'y' if len(ids) == 1 else 'ies'} and has no record"))
            continue
        n_records += 1
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            defects.append(("HEADER_DISAGREES", rel, f"unparseable: {exc}"))
            continue
        if _ignored(root, path):
            defects.append(("GITIGNORED", rel, "git refuses to track this path"))

        if not doc.get("commit"):
            defects.append(("NO_COMMIT", rel, "no `commit` — staleness is undetectable from the record"))
        if doc.get("declared") is None or doc.get("total") is None:
            defects.append(("NO_DENOMINATOR", rel, "no `declared`/`total` — the denominator is "
                                                   "whatever the run selected"))
        c = _rec.recount(doc)
        for key in ("total", "examined", "skipped"):
            if doc.get(key) is not None and doc[key] != c[key]:
                defects.append(("HEADER_DISAGREES", rel,
                                f"header says {key}={doc[key]}, the record's own evidence "
                                f"recomputes to {c[key]}"))
        dec = doc.get("declared")
        if isinstance(dec, int) and c["total"] < dec:
            defects.append(("SHORT_POPULATION", rel,
                            f"{c['total']} result(s) for {dec} declared — "
                            f"{dec - c['total']} declared propert"
                            f"{'y is' if dec - c['total'] == 1 else 'ies are'} absent, "
                            f"not NOT_RUN"))
        bad = sorted({str(r.get("status")) for r in doc.get("results") or []
                      if str(r.get("status")) not in _rec.STATUSES})
        if bad:
            defects.append(("BAD_STATUS", rel, f"status outside the closed set: {', '.join(bad)}"))

        if (doc.get("engine") or {}).get("synthetic"):
            notes.append(f"SYNTHETIC  {rel} — engine {(doc.get('engine') or {}).get('kind')}: "
                         f"proves the write path, is NOT a measurement of the data")
        if head and doc.get("commit") and doc["commit"] != head:
            age = ""
            try:
                d = (_dt.datetime.now().astimezone()
                     - _dt.datetime.fromisoformat(doc["run_at"])).days
                age = f", {d} day(s) old"
            except (ValueError, TypeError, KeyError):
                pass
            notes.append(f"STALE      {rel} — run at {doc['commit']}, HEAD is {head}{age}")
        if doc.get("commit_dirty"):
            notes.append(f"DIRTY      {rel} — run against an uncommitted working tree; the commit "
                         f"names something nobody else can reproduce")
    return defects, notes, n_records, len(suites)


def report(root: Path) -> int:
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    defects, notes, n_records, n_suites = inspect(root)
    if n_suites == 0:
        # 0 DECLARED IS NOT 0 FAILURES. A gate that passes over an empty population reads exactly
        # like a clean result, which is the defect that had `check_no_fabricated_identifiers`
        # examining ZERO properties against both example bundles and exiting 0.
        print(f"could not run: {root} declares 0 suites under acceptance/ — "
              f"0 declared is not the same as clean", file=sys.stderr)
        return 2
    if n_records == 0:
        print(f"could not run: {root} declares {n_suites} suite(s) and holds 0 run record(s) — "
              f"an unrun suite is a claim, not evidence", file=sys.stderr)
        for cls, rel, why in defects:
            print(f"    [{cls}] {rel}: {why}", file=sys.stderr)
        return 2
    for n in notes:
        print(f"  {n}")
    if not defects:
        print(f"PASS: check_run_records — 0 defect(s) over {n_records} record(s) for "
              f"{n_suites} declared suite(s)"
              + (f"  [{len(notes)} note(s)]" if notes else ""))
        return 0
    for cls, rel, why in defects:
        print(f"  [{cls}] {rel}: {why}", file=sys.stderr)
    print(f"\nFAIL: check_run_records — {len(defects)} defect(s) over {n_records} record(s) for "
          f"{n_suites} declared suite(s)", file=sys.stderr)
    return 1


# ── self-test: one mutant per reject class ───────────────────────────────────────────────────
_SUITE = {"suite": "selftest", "version": "1.0", "properties": [
    {"id": "P-A-01", "family": "f", "severity": "blocker",
     "assertion": {"type": "must_be_zero", "columns": ["v"]}, "sql": "SELECT 0 AS v"},
    {"id": "P-B-01", "family": "f", "severity": "minor",
     "assertion": {"type": "must_be_zero", "columns": ["v"]}, "sql": "SELECT 0 AS v"},
]}


def _fixture(tmp: Path) -> Path:
    root = tmp / "bundle"
    (root / "acceptance").mkdir(parents=True)
    (root / "acceptance" / "properties.yaml").write_text(yaml.safe_dump(_SUITE), encoding="utf-8")
    doc = _rec.build(
        suite=_SUITE, suite_file=root / "acceptance" / "properties.yaml", root=root,
        engine={"kind": "sqlite", "billed": False, "synthetic": False},
        declared_ids=["P-A-01", "P-B-01"],
        results=[{"id": "P-A-01", "status": "PASS", "rows": [{"v": 0}], "notes": []},
                 {"id": "P-B-01", "status": "FAIL", "rows": [{"v": 3}], "notes": []}])
    doc["commit"] = "0123456789"          # no git in the fixture; the field is what is under test
    doc["commit_dirty"] = False
    (root / "acceptance" / "property_runs.json").write_text(
        json.dumps(doc, indent=1), encoding="utf-8")
    return root


def _load(root: Path) -> dict:
    return json.loads((root / "acceptance" / "property_runs.json").read_text(encoding="utf-8"))


def _save(root: Path, doc: dict) -> None:
    (root / "acceptance" / "property_runs.json").write_text(json.dumps(doc, indent=1),
                                                            encoding="utf-8")


def _self_test() -> int:
    import shutil
    import tempfile

    cases: list[tuple[str, callable, str, int]] = [
        ("baseline (no mutant)", lambda r: None, "", 0),
        ("NO_RECORD", lambda r: (r / "acceptance" / "property_runs.json").unlink(),
         "NO_RECORD", 2),                      # the only record -> cannot measure, exit 2
        ("NO_COMMIT", lambda r: _save(r, {**_load(r), "commit": None}), "NO_COMMIT", 1),
        ("NO_COMMIT (key absent)",
         lambda r: _save(r, {k: v for k, v in _load(r).items() if k != "commit"}),
         "NO_COMMIT", 1),
        ("NO_DENOMINATOR",
         lambda r: _save(r, {k: v for k, v in _load(r).items()
                             if k not in ("declared", "total")}), "NO_DENOMINATOR", 1),
        ("HEADER_DISAGREES (total)", lambda r: _save(r, {**_load(r), "total": 99}),
         "HEADER_DISAGREES", 1),
        ("HEADER_DISAGREES (examined = declared, examining nothing)",
         lambda r: _save(r, {**_load(r), "examined": 2,
                             "results": [{**x, "rows": None} for x in _load(r)["results"]]}),
         "HEADER_DISAGREES", 1),
        ("SHORT_POPULATION (the filtered run)",
         lambda r: _save(r, {**_load(r), "total": 1, "examined": 1,
                             "results": _load(r)["results"][:1]}), "SHORT_POPULATION", 1),
        ("BAD_STATUS", lambda r: _save(r, {**_load(r), "results": [
            {**_load(r)["results"][0], "status": "GREEN"}, _load(r)["results"][1]]}),
         "BAD_STATUS", 1),
        ("GITIGNORED", None, "GITIGNORED", 1),          # needs a real repo; built below
        ("NO_SUITE (0 declared is not clean)",
         lambda r: (r / "acceptance" / "properties.yaml").unlink(), "", 2),
    ]

    failures, total = [], 0
    for name, mutate, expect_cls, expect_rc in cases:
        total += 1
        tmp = Path(tempfile.mkdtemp())
        try:
            root = _fixture(tmp)
            if name == "GITIGNORED":
                subprocess.run(["git", "init", "-q", str(root)], capture_output=True)
                (root / ".gitignore").write_text("acceptance/*_runs.json\n", encoding="utf-8")
            elif mutate:
                mutate(root)
            defects, _notes, n_rec, n_suites = inspect(root)
            classes = {c for c, _, _ in defects}
            # The gate's own output is SWALLOWED here. A self-test that interleaves eleven FAIL
            # banners with its own verdict is unreadable, and an unreadable proof gets skipped.
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                rc = report(root)
            ok = rc == expect_rc and (not expect_cls or expect_cls in classes)
            if not ok:
                failures.append(f"{name}: exit {rc} (want {expect_rc}), "
                                f"classes {sorted(classes) or '[]'} (want {expect_cls or 'none'})")
            print(f"  {'ok  ' if ok else 'MISS'} {name}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"    {f}", file=sys.stderr)
        print(f"FAIL: check_run_records self-test — {len(failures)} of {total} failed",
              file=sys.stderr)
        return 1
    print(f"PASS: check_run_records self-test — {total}/{total} reject class(es) + baseline, "
          f"each proved on a seeded mutant")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    return report(Path(a.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
