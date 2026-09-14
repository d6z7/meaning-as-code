#!/usr/bin/env python3
"""The ONE writer and reader of a suite run record — the artifact that kept losing the answer.

── THE MEASURED DEFECT THIS FILE EXISTS TO FIX ────────────────────────────────────────────────

    acceptance/*_runs.json    0 blobs in every repo in the estate that HAS a git remote
                              7 files / 44 committed versions in the ONE repo that has none

The suites do not fail to persist. They persist into a repository that can never publish, written
by a BUNDLE-LOCAL runner that exists in no repo with a remote and in no
release of this framework. That is why the framework's own `suite_history.py` could assert *"The run
records are committed"* and a sweep of the publishable estate could measure ZERO, with both correct.

Four further defects were measured in that writer, and all four are repaired here:

  1. NO FINGERPRINT. The record carries `{suite, version, run_at, source_watermark, engine,
     results}` — and no commit. 0 of 7 records name the ontology they were run against, so
     staleness is undetectable from the record: `suite_history.current()` had to stamp the literal
     string ``"working-tree"``, and a commit could only ever be recovered by replaying git.
  2. NO DENOMINATOR. No `declared` / `total`. The implicit denominator is `len(results)`, which is
     the number of properties the run HAPPENED to select — so `--id P-NPROD-01` wrote a record of
     one, and "1 of 1 pass" is a true sentence about a filter. That is the authored-denominator
     defect at the top of every run record.
  3. PERSISTENCE WAS OPTIONAL. `--json` is a flag. `python3 tools/run_properties.py` — the first
     usage line in that file's own docstring — runs the whole billed suite and writes nothing at
     all. The money is spent and the only record is terminal scrollback.
  4. THE WRITE WAS NEITHER ATOMIC NOR DATED. `Path(p).write_text(...)` truncates in place while the
     console polls that exact file, and one filename per suite means every run overwrites the last.
     The bundle therefore knew its state and never its direction.

── WHAT A RECORD MUST CARRY, AND WHY EACH FIELD IS LOAD-BEARING ───────────────────────────────

`suite_history.jsonl` already carries the answer, because it was reconstructed from git and git
supplied what the record did not: `suite · run_at · commit · subject · pass · fail · accepted ·
error · total · properties`. A record that carries those itself needs no git, no replay, and no
reconstruction — which is the whole point, since the one repo holding the records cannot push.

  commit        WITHOUT IT, STALENESS IS UNDETECTABLE. `<LIVE>`'s last verdict is 60 days old and
                reads exactly like today's. A record that names its commit can be compared with
                HEAD by a machine; one that does not can only be trusted.
  commit_dirty  A sha alone LIES when the tree is modified. A run against uncommitted edits is
                honest evidence about nothing anybody else can reproduce, and must say so.
  declared      the population the SUITE declares — the denominator, taken from the suite file and
  total         never from the loop that happened to execute.
  examined      RECOMPUTED FROM EVIDENCE, NEVER ACCEPTED (see `recount`). A runner writing
                `examined = declared` regardless of what it looked at satisfies every schema and
                every board while examining nothing.
  skipped       a declared property with no fresh result is NOT absent and NOT green. Absence reads
                as nothing-to-report, which is how two split property families left stale results
                sitting on the page.

── PUBLIC SURFACE ─────────────────────────────────────────────────────────────────────────────

    runs_path(suite_file)                 -> the relative path a console READER looks at
    fingerprint(root, suite_file)         -> (commit, dirty, ontology_sha)
    recount(doc)                          -> the header recomputed from the record's own evidence
    build(...)                            -> a complete record
    carry_forward(prev, fresh, declared)  -> the merge that used to be a shell heredoc
    write(root, doc, runs_rel)            -> (current_path, dated_path), both written atomically
    history_row(doc)                      -> the suite_history.jsonl row, from the record ALONE

THE GATE THAT MAKES THIS STICK is `tools/check_run_records.py`: it exits 2 when a bundle declares
suites and no record can be measured, and exits 1 when a header disagrees with the evidence under
it. Naming it here is the admission test (`decisions/PLAN.yaml` R16) — a new field with no gate
behind it is `authority: sme`, adopted 0 of 101 times.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

# The suite-file -> runs-file map the console reader is hardcoded against
# (`PropertySuiteView.jsx:40-51`). It is NOT derivable: `properties.yaml` pairs with
# `property_runs.json`, singular, and four of the seven differ from their stem in some way. It
# lived as a hand-maintained bash array in one bundle's `run-tests.sh`, which is why a bundle whose
# suite file is named anything else writes to a path nothing reads.
#
# THIS MAP IS A STOPGAP AND SHOULD DIE. `decisions/PLAN.yaml` P1-dialect rules that the bundle
# declares its own suites in an `acceptance:` manifest in `mac.project.yaml`; when that lands, the
# manifest is the authority and this falls back to the derived name.
RUNS_BY_SUITE_STEM = {
    "properties": "property_runs.json",
    "retrieval": "retrieval_runs.json",
    "data_sanity": "data_sanity_runs.json",
    "data_sanity_generated": "data_sanity_generated_runs.json",
    "ontology": "ontology_runs.json",
    "ontology_generated": "ontology_generated_runs.json",
    "rules_generated": "rules_generated_runs.json",
}

STATUSES = ("PASS", "FAIL", "ACCEPTED", "FROZEN", "ERROR", "NOT_RUN")

# THE SUITE KEY IN THE TREND, and it is NOT free to choose. 61 history rows already exist under
# these names (tier1 19 · tier2 16 · ontology 11 · sanity 8 · the three generated suites by their
# own filenames). A new writer picking `properties`/`property` instead forks each suite into two
# series that both look short, which is the silently-capped-sweep defect drawn as a chart. So the
# key is derived from the RUNS FILENAME through the same alias map `suite_history.py` has always
# used, and every producer of a history row goes through `suite_key`.
HISTORY_ALIASES = {"property_runs.json": "tier1", "retrieval_runs.json": "tier2",
                   "data_sanity_runs.json": "sanity", "ontology_runs.json": "ontology"}


def suite_key(path: str | os.PathLike) -> str:
    """The trend's key for a suite, from its runs path, its dated record, or its suite yaml."""
    name = Path(path).name
    if name.endswith("_runs.json"):
        return HISTORY_ALIASES.get(name, name[: -len("_runs.json")])
    if name.endswith(".json"):                      # a dated record: <UTC>-<key>.json
        return HISTORY_ALIASES.get(name.split("-", 1)[-1][:-5] + "_runs.json",
                                   name.split("-", 1)[-1][:-5])
    return suite_key(runs_path(path))               # a suite yaml

# Dialect A's naming, adopted per P1-dialect ("A's runs/ IS adopted into B"). `<LIVE>` has 21 of
# these and they are the only dated run evidence in the estate that survived its own overwrite.
DATED_DIR = "runs"


def runs_path(suite_file: str | os.PathLike) -> str:
    """The bundle-relative path a console reader looks at for this suite's CURRENT state."""
    stem = Path(suite_file).stem
    return "acceptance/" + RUNS_BY_SUITE_STEM.get(stem, f"{stem}_runs.json")


def _git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def fingerprint(root: Path, suite_file: Path) -> tuple[str | None, bool, str]:
    """``(commit, dirty, ontology_sha)`` for the bundle this suite belongs to.

    ``commit`` is the short sha of the repo that HOLDS the bundle, so a record can be compared with
    HEAD by a machine rather than trusted by a reader. It is ``None`` when the bundle is not in a
    repository at all — which is an honest answer and, crucially, a DIFFERENT answer from "clean":
    the gate refuses a record whose commit is absent rather than treating the absence as fine.

    ``ontology_sha`` is a content hash over the suite file plus the bundle's declared meaning
    (``ontology/**/*.yaml``). It survives where ``commit`` cannot — an unversioned bundle, a
    published artifact, a copy — and it moves when the meaning moves even if nobody committed.
    """
    commit = _git(root, "rev-parse", "--short=10", "HEAD") or None
    dirty = bool(_git(root, "status", "--porcelain")) if commit else False
    h = hashlib.sha256()
    if suite_file.exists():
        h.update(suite_file.read_bytes())
    for p in sorted((root / "ontology").rglob("*.yaml")) if (root / "ontology").is_dir() else []:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return commit, dirty, "sha256:" + h.hexdigest()[:16]


def _has_evidence(r: dict) -> bool:
    """Did the engine actually LOOK at something for this result?

    Evidence is a row grid that exists (``[]`` is evidence — the query ran and returned nothing) or
    a non-zero byte count from the engine. It is NOT the presence of a status: a status is what the
    runner claims, and the point of recomputing `examined` is to stop taking the claim.
    """
    if r.get("carried_from") or r.get("status") == "NOT_RUN":
        return False
    if isinstance(r.get("rows"), list):
        return True
    eng = r.get("engine") or r.get("athena") or {}
    return bool(eng.get("bytes_scanned"))


def recount(doc: dict) -> dict:
    """The header RECOMPUTED from the record's own evidence. Compute it; never accept it.

    Returned so both the writer and the gate derive the same numbers from the same rule. The gate
    then FAILS on any disagreement with the stored header — the same discipline this estate applied
    to `derivation.agree` after finding an authored boolean asserting its own correctness.
    """
    res = doc.get("results") or []
    tally = {s: 0 for s in STATUSES}
    for r in res:
        st = str(r.get("status", "")).upper()
        if st in tally:
            tally[st] += 1
    examined = sum(1 for r in res if _has_evidence(r))
    skipped = sum(1 for r in res if r.get("carried_from") or r.get("status") == "NOT_RUN")
    return {"total": len(res), "examined": examined, "skipped": skipped,
            "errors": tally["ERROR"], "tally": tally}


def build(*, suite: dict, suite_file: Path, root: Path, engine: dict,
          results: list[dict], declared_ids: list[str],
          source_watermark: dict | None = None, run_at: str | None = None) -> dict:
    """A complete run record. Every derived number comes from `recount`, so the header cannot
    disagree with the body at the moment it is written."""
    commit, dirty, onto = fingerprint(root, suite_file)
    doc = {
        "suite": suite.get("suite") or Path(suite_file).stem,
        "version": str(suite.get("version", "")),
        "run_at": run_at or _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        # THE FIELD WHOSE ABSENCE IS THE FINDING.
        "commit": commit,
        "commit_dirty": dirty,
        "ontology_fingerprint": onto,
        "bundle": root.name,
        "suite_file": os.path.relpath(suite_file, root),
        "engine": engine,
        "source_watermark": source_watermark or {},
        # THE DENOMINATOR, taken from the suite and not from the loop.
        "declared": len(declared_ids),
        "results": results,
    }
    doc.update({k: v for k, v in recount(doc).items() if k != "errors"})
    return doc


def carry_forward(prev: dict | None, fresh: list[dict], declared_ids: list[str]) -> list[dict]:
    """Merge a filtered run into the full declared population — in ONE place, in Python.

    This logic existed as a 30-line heredoc inside `run-tests.sh`, and its own comments record two
    bugs it had already shipped: a partial run that replaced 22 results with 1, and a failing run
    whose merge never executed because `set -e` killed the script between the temp write and the
    merge, so every FAILED result was written to a temp file and thrown away.

    THE RULES, and each one is a defect that was measured:
      * every DECLARED id appears — a declared property with no result is not absent, it is NOT_RUN
      * a result not refreshed by this run is CARRIED FORWARD and STAMPED `carried_from` with the
        run_at it actually came from, so a board can age it instead of reading it as current
      * an id the suite no longer declares is PRUNED — two split families left their originals
        sitting green on the page for ever
    """
    prev_by = {r["id"]: r for r in (prev or {}).get("results") or []}
    prev_at = (prev or {}).get("run_at")
    fresh_by = {r["id"]: r for r in fresh}
    out = []
    for qid in declared_ids:
        if qid in fresh_by:
            out.append(fresh_by[qid])
        elif qid in prev_by:
            old = dict(prev_by[qid])
            old["carried_from"] = old.get("carried_from") or prev_at
            out.append(old)
        else:
            out.append({"id": qid, "status": "NOT_RUN", "rows": None,
                        "notes": ["declared, never run"]})
    return out


def _atomic(path: Path, text: str) -> None:
    """Temp file in the same directory + os.replace.

    The console polls these files every 2.5 s. A truncate-then-stream write hands that poll a
    partial document, and the run record was the one artifact in this bundle still written that
    way — `bundleio.atomic_write` existed for the corpus, and `run-tests.sh` hand-rolled temp-file
    staging for the cards and the trend, but not for the record itself.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(root: Path, doc: dict, runs_rel: str) -> tuple[Path, Path]:
    """Write the record to BOTH homes and return both paths.

    TWO HOMES, TWO DIFFERENT JOBS, and conflating them is what lost the history:

      * ``acceptance/<suite>_runs.json`` — CURRENT STATE, overwritten every run. This is the path
        the console reads (`PropertySuiteView.jsx` -> `readSourceFile`), so it must keep its name.
      * ``acceptance/runs/<UTC>-<suite>.json`` — APPEND-ONLY, one file per run, never overwritten.
        This is what makes the trend independent of git, and it is dialect A's own shape, which is
        the only reason 21 dated run records survived in `<LIVE>` while `<REF>` kept just the last.
    """
    text = json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n"
    cur = root / runs_rel
    _atomic(cur, text)
    stamp = _dt.datetime.fromisoformat(doc["run_at"]).astimezone(
        _dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = Path(runs_rel).name[: -len("_runs.json")]
    dated = root / "acceptance" / DATED_DIR / f"{stamp}-{key}.json"
    _atomic(dated, text)
    return cur, dated


def history_row(doc: dict) -> dict:
    """The `suite_history.jsonl` row, derived from the record ALONE.

    Field-for-field what the 61 existing entries carry, so the log's shape does not change and the
    dedup key (suite, run_at, commit) keeps working. The difference is the SOURCE: those 61 rows
    could only be produced by replaying git, because the record carried neither the commit nor the
    total. This one needs no repository.
    """
    c = recount(doc)
    t = c["tally"]
    commit = doc.get("commit") or "no-commit"
    if doc.get("commit_dirty"):
        commit += "-dirty"
    return {"suite": suite_key(doc.get("suite_file") or "x.yaml"),
            "run_at": doc["run_at"], "commit": commit,
            "subject": f"{doc.get('bundle', '?')} · {doc.get('suite', '?')} "
                       f"({(doc.get('engine') or {}).get('kind', '?')})"[:90],
            "pass": t["PASS"], "fail": t["FAIL"], "accepted": t["ACCEPTED"],
            "error": t["ERROR"], "total": c["total"],
            "declared": doc.get("declared"), "examined": c["examined"], "skipped": c["skipped"],
            "properties": {r.get("id"): r.get("status") for r in doc.get("results") or []}}
