#!/usr/bin/env python3
"""A preview must still be a preview OF ITS DESCRIPTOR — checked OFFLINE, from the header alone.

`data/samples/<stem>[.src].sample.csv` is the only artifact family in the data plane that had no
gate, and it had already rotted. MEASURED on the reference bundle, from the checked-in bytes and
with no query: 22 of its 25 previews matched their descriptor's `columns[]` exactly and in order,
and 3 did not — 15 header columns against 16 declared, another one short, and one carrying 12 of 22
while a decision record cites that exact file twice as proof the register was 'built + inspectable'.
Two more files carry 24 and 22 data rows against the documented ceiling of 20.

THE POPULATION IS THE DESCRIPTORS, NEVER THE SAMPLES DIRECTORY. A gate whose denominator is the
files it judges cannot see an absent one, and the absent one is half the defect: the console's
Sample tab is computed by globbing this directory, so a missing preview is silently no tab at all.
So the count is `N of M declared relation(s) carry a preview`, M being the source + dataset
descriptors, and BOTH denominators are printed on every verdict line.

WHY IT MUST NOT CONNECT TO ANYTHING. Two local files per descriptor, no engine, no credential, no
network — which is what let this gate be pointed at a cloud-warehouse bundle with no outward action
at all, and what keeps it runnable in CI. The DERIVER (`tools/mac_sample.py`) goes through the
connector seam; if the gate did too it would inherit the deriver's credentials and repeat the
hardwiring defect that made the whole family unproducible on a second engine.

WHAT IT MUST NOT DO, and each of these is a way to be green for the wrong reason:
  1. never re-cut or repair a preview. A gate that fixes its own finding destroys the evidence.
  2. NEVER COMPLETE A HEADER. Measured: padding the 3 drifted files with their missing columns as
     empty cells flips this gate from FAIL/3 to PASS/0 with no query run — a padded header passes
     forever while the preview previews nothing. The finding says so where the fix is read.
  3. never promote a sample value into a descriptor's `values:`, nor read an enumeration, a code
     pattern or a grain off one. It compares and reports.
  4. never exempt on `status:`. MEASURED: the worst file in the reference bundle is `status: draft`,
     and BOTH of that bundle's two drafts carry a defect. A draft exemption exempts exactly the
     files that need the gate.
  5. never use mtimes or `observed:` to tolerate a fresh descriptor. Timestamps are not in the
     contract and do not survive a clone.

THE ERROR CLASSES (exit 1)
    HEADER_DRIFT    the header is not `columns[]` as an ORDERED LIST. Reported as MISSING / EXTRA /
                    ORDER with names, never a bare count — and never as set equality or subsequence
                    tolerance, because in-order SUBSEQUENCE is precisely the measured rot shape and
                    any tolerance for it passes all three known defects.
    RAGGED          a data row whose field count is not the header's. Not the shape it claims.
    ORPHAN          a `*.csv` under data/samples that no descriptor claims.
    SUFFIX_CROSSED  a source's preview named `<stem>.sample.csv`, or a dataset's `<stem>.src.…`.
                    Its own class because the file exists, is correct inside, and is INVISIBLE.
    EMPTY_PREVIEW   zero bytes, or a header and zero data rows: a preview that previews nothing.
    MISSING_PREVIEW a declared relation with no preview, once the bundle HAS a samples plane.
    NO_COLUMNS      a descriptor declaring no columns, so the expected header is [] and every
                    measured column would read as EXTRA — the inverse fabrication.

THE WARNING CLASSES (reported with their denominator, never blocking; ERROR under --strict)
    OVER_CEILING    more than 20 data rows. `<=20` is a readability budget, not a correctness
                    claim — but a count that is neither 20 nor the relation's size is evidence of a
                    hand-assembled file.
    NULL_SENTINEL   a cell reading NULL / \\N / None / nan on a column that does not declare that
                    string. The contract says "empty cell for NULL"; a sentinel is a cut path.
    UNRECORDED      a preview with no entry in data/samples/samples.run.json — nothing attests
                    where its rows came from. A hand-typed file and a machine cut are
                    byte-indistinguishable on disk, so the run record is the only provenance the
                    shape can carry. Collapsed to ONE finding with its count, never one per file.
    PROPOSAL_PREVIEW  the run record says a preview was cut from a transform's SQL body because the
                    relation it names did not exist yet. That is honest and it is not the served
                    relation's output; it must be re-cut once the view is deployed.

THREE "NOTHING TO MEASURE" STATES, TOLD APART
    exit 2  the root is not a directory, or declares no sources plane
    exit 2  ZERO descriptors on either axis — refused per axis, because zero sources and zero
            datasets are different outages and a caller needs to know which
    exit 0  data/samples is ABSENT entirely — the GENUINE zero. Refusing here would block the
            ingestion that produces the previews. The line says the matching rule judged NOTHING
            and prints the coverage fraction; `--strict` makes it a failure.

    python3 tools/check_sample_matches_descriptor.py [root] [--json] [--strict] [--self-test]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path, PurePath

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mac_diag as D                                                             # noqa: E402
from mac_project import resolve                                                  # noqa: E402

NAME = "check_sample_matches_descriptor"

SRC_SUFFIX = ".src.sample.csv"
DS_SUFFIX = ".sample.csv"
RUN_RECORD = "samples.run.json"
CEILING = 20

#: A cut path's NULL sentinel, which the contract forbids ("empty cell for NULL"). Reachable on any
#: engine whose CLI writes a sentinel and unreachable on one whose rows are already text — so it is
#: a property of HOW a file was cut, and it is the only clause in the shape whose satisfaction
#: depends on that.
SENTINELS = ("NULL", "\\N", "None", "nan", "NaN", "\\\\N")

#: The COLLECTION-TYPE spellings this gate knows, per declared connector. A table and not a
#: `startswith("array(")` because a type name belongs to the ENGINE: the connector contract states
#: that a reported type is VERBATIM and never parsed by MAC, and MEASURED, two bundles in this
#: estate share no collection spelling — one declares `array(string)`, the other's catalog reports
#: `varchar[]`. A generic instrument once carried eleven type names of one dialect and the
#: connectors' own `orderable()` exists to undo exactly that.
COLLECTION_SPELLINGS = {
    "mac.connector.athena": ("array(", "map(", "row("),
    "mac.connector.duckdb": ("[]", "list(", "struct(", "map("),   # `[]` matched as a SUFFIX
}

ERRORS = ("HEADER_DRIFT", "RAGGED", "ORPHAN", "SUFFIX_CROSSED", "EMPTY_PREVIEW",
          "MISSING_PREVIEW", "NO_COLUMNS")
WARNINGS = ("OVER_CEILING", "NULL_SENTINEL", "UNRECORDED", "PROPOSAL_PREVIEW",
            "OUTSIDE_DECLARED_VALUES", "TYPE_SHAPE", "UNKNOWN_TYPE_VOCABULARY", "METADATA_TABLE")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# READING — every failure is a SETUP failure, never a drift
# ══════════════════════════════════════════════════════════════════════════════════════════════════

class CouldNotRun(Exception):
    pass


def _read_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:                                                    # noqa: BLE001
        raise CouldNotRun(f"{p}: unreadable or not YAML: {exc}") from exc


def _read_csv(p: Path):
    """(header, data_rows). `newline=''` belongs to open(), never to csv.reader.

    utf-8-sig so a BOM is not reported as a drifted first column name, and an all-empty row is not
    a data row (a trailing blank line is not a record).
    """
    try:
        with open(p, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
    except Exception as exc:                                                    # noqa: BLE001
        raise CouldNotRun(f"{p}: unreadable: {exc}") from exc
    if not rows:
        return [], []
    return rows[0], [r for r in rows[1:] if any(str(c).strip() for c in r)]


def _declared_header(doc: dict):
    """The expected header, defensively. A descriptor with no columns is its OWN class."""
    return [str(c.get("name")) if isinstance(c, dict) else str(c)
            for c in (doc.get("columns") or [])]


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE RULE — pure. Findings in, findings out.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _header_detail(header, declared):
    missing = [c for c in declared if c not in header]
    extra = [c for c in header if c not in declared]
    if not missing and not extra:
        return (f"{len(header)} column(s) in a different ORDER from the descriptor's "
                f"{len(declared)}: header {header} vs declared {declared} — the contract is "
                f"'EXACTLY the descriptor's columns[] IN ORDER'; re-cut with mac_sample.py")
    bits = [f"{len(header)} column(s) vs {len(declared)} declared"]
    if missing:
        bits.append(f"MISSING {len(missing)} of {len(declared)}: {missing}")
    if extra:
        bits.append(f"EXTRA {len(extra)}: {extra}")
    return ("; ".join(bits) + " — re-cut from the relation with `mac_sample.py`. Do NOT add the "
            "missing columns as empty cells: measured, padding a drifted header flips this gate to "
            "PASS with no query run, and a padded header passes forever while the preview previews "
            "nothing")


def _collection_spellings(connector_id):
    if not connector_id:
        return None
    for known, spellings in COLLECTION_SPELLINGS.items():
        if connector_id == known or connector_id.split("/")[0] == known:
            return spellings
    return None


def _is_collection(type_name, spellings) -> bool:
    t = (type_name or "").strip().lower()
    if not t or spellings is None:
        return False
    return t.endswith("[]") if "[]" in spellings and t.endswith("[]") else \
        t.startswith(tuple(s for s in spellings if s != "[]"))


def scan(root: Path, L, *, strict=False):                                       # noqa: C901
    """(findings, counts). PURE, OFFLINE: two local files per descriptor and one run record."""
    manifest = _read_yaml(root / "mac.project.yaml") if (root / "mac.project.yaml").is_file() else {}
    connector_id = ((manifest.get("runtime") or {}).get("connector"))
    spellings = _collection_spellings(connector_id)
    samples_dir = Path(L.samples)

    # POPULATION: descriptors, per axis, each glob SORTED — measured, glob is unsorted, so without
    # this the same bundle prints different bytes on a different checkout.
    planes = [("sources", Path(L.sources), SRC_SUFFIX), ("datasets", Path(L.descriptors), DS_SUFFIX)]
    targets = []
    for axis, d, suffix in planes:
        for f in sorted(glob.glob(str(d / "*.yaml"))):
            p = Path(f)
            targets.append((axis, p.stem, suffix, _read_yaml(p), str(p.relative_to(root))))

    run = {}
    rr = samples_dir / RUN_RECORD
    if rr.is_file():
        try:
            for s in (json.loads(rr.read_text(encoding="utf-8")) or {}).get("samples") or []:
                run[s.get("stem")] = s
        except Exception:                                                       # noqa: BLE001
            run = {}

    findings = []
    claimed = set()
    present = 0
    matched = 0
    unrecorded = []
    plane_present = {"sources": 0, "datasets": 0}
    plane_total = {"sources": 0, "datasets": 0}

    for axis, stem, suffix, doc, desc_rel in targets:
        plane_total[axis] += 1
        declared = _declared_header(doc)
        want = samples_dir / f"{stem}{suffix}"
        other = samples_dir / (f"{stem}{DS_SUFFIX}" if axis == "sources"
                               else f"{stem}{SRC_SUFFIX}")
        claimed.add(want.name)
        if not declared:
            findings.append({"kind": "NO_COLUMNS", "file": desc_rel, "severity": "error",
                             "detail": "the descriptor declares no columns[], so the expected "
                                       "header is [] and every real column in the preview would "
                                       "read as EXTRA — nothing is judged against it"})
            continue
        if not want.is_file():
            if other.is_file():
                claimed.add(other.name)
                findings.append({
                    "kind": "SUFFIX_CROSSED", "file": str(other.relative_to(root)),
                    "severity": "error",
                    "detail": f"a {axis[:-1]} descriptor's preview must be named "
                              f"{stem}{suffix}; this file exists, may be correct inside, and is "
                              f"INVISIBLE — the console keys the Sample tab on the plane's suffix "
                              f"and emits no tab and no error"})
            elif samples_dir.is_dir():
                findings.append({
                    "kind": "MISSING_PREVIEW", "file": f"{L.samples and 'data/samples'}/"
                                                       f"{stem}{suffix}",
                    "severity": "error",
                    "detail": f"{desc_rel} declares a relation with no preview, and this bundle "
                              f"HAS a samples plane; the console offers no Sample tab for it. Cut "
                              f"it with `mac_sample.py`"})
            elif strict:
                findings.append({
                    "kind": "MISSING_PREVIEW", "file": f"data/samples/{stem}{suffix}",
                    "severity": "error",
                    "detail": f"--strict: {desc_rel} carries no preview (this bundle has no "
                              f"samples plane at all)"})
            continue

        present += 1
        plane_present[axis] += 1
        rel = str(want.relative_to(root))
        header, rows = _read_csv(want)
        if not header:
            findings.append({"kind": "EMPTY_PREVIEW", "file": rel, "severity": "error",
                             "detail": "zero bytes: a preview that previews nothing"})
            continue
        if header != declared:
            findings.append({"kind": "HEADER_DRIFT", "file": rel, "severity": "error",
                             "detail": _header_detail(header, declared)})
        else:
            matched += 1
        if not rows:
            findings.append({"kind": "EMPTY_PREVIEW", "file": rel, "severity": "error",
                             "detail": "a header and zero data rows — it passes the header rule "
                                       "and shows no evidence"})
        for i, r in enumerate(rows):
            if len(r) != len(header):
                findings.append({"kind": "RAGGED", "file": rel, "severity": "error",
                                 "detail": f"data row {i + 1} carries {len(r)} field(s) for a "
                                           f"header of {len(header)}; the file is not the shape it "
                                           f"claims"})
                break
        if len(rows) > CEILING:
            findings.append({"kind": "OVER_CEILING", "file": rel, "severity": "warning",
                             "detail": f"{len(rows)} data row(s) > the documented ceiling of "
                                       f"{CEILING}; a count that is neither {CEILING} nor the "
                                       f"relation's size is evidence of a hand-assembled file"})

        # the per-column advisories, only on a header that actually joins
        cols = {str(c.get("name")): c for c in (doc.get("columns") or []) if isinstance(c, dict)}
        if header == declared:
            sentinel_hits = {}
            for r in rows:
                for i, name in enumerate(header):
                    v = (r[i] if i < len(r) else "").strip()
                    if not v:
                        continue
                    spec = cols.get(name) or {}
                    if v in SENTINELS and v not in (spec.get("values") or []):
                        sentinel_hits.setdefault(name, 0)
                        sentinel_hits[name] += 1
            for name, n in sorted(sentinel_hits.items()):
                findings.append({
                    "kind": "NULL_SENTINEL", "file": rel,
                    "severity": "error" if strict else "warning",
                    "detail": f"{name}: {n} of {len(rows)} cell(s) spell NULL as a sentinel string "
                              f"where the contract requires an EMPTY cell. That is a property of "
                              f"the cut path, not of the data; re-cut with `mac_sample.py`"})
            bracketed = {}
            for r in rows:
                for i, name in enumerate(header):
                    v = (r[i] if i < len(r) else "").strip()
                    if v.startswith("[") and v.endswith("]"):
                        bracketed.setdefault(name, 0)
                        bracketed[name] += 1
            for name, n in sorted(bracketed.items()):
                t = (cols.get(name) or {}).get("type")
                if spellings is None:
                    findings.append({
                        "kind": "UNKNOWN_TYPE_VOCABULARY", "file": rel, "severity": "warning",
                        "detail": f"{name}: {n} bracket-rendered cell(s) were NOT judged — this "
                                  f"gate knows collection spellings for "
                                  f"{sorted(COLLECTION_SPELLINGS)}, and this bundle declares "
                                  f"runtime.connector={connector_id!r}. A gate on a third engine "
                                  f"must announce its own blindness rather than emit findings in "
                                  f"another engine's grammar"})
                elif not _is_collection(t, spellings):
                    findings.append({
                        "kind": "TYPE_SHAPE", "file": rel, "severity": "warning",
                        "detail": f"{name}: {n} cell(s) render as [a, b] on a column the descriptor "
                                  f"types {t!r}, which is not a collection spelling of "
                                  f"{connector_id}. Either the descriptor's type is stale or the "
                                  f"value genuinely begins with '['"})
        meta_tbl = (doc.get("metadata") or {}).get("table")
        tbl_name = (doc.get("table") or {}).get("name")
        if meta_tbl and tbl_name and str(meta_tbl) != str(tbl_name):
            findings.append({
                "kind": "METADATA_TABLE", "file": desc_rel, "severity": "warning",
                "detail": f"metadata.table={meta_tbl!r} differs from table.name={tbl_name!r}. The "
                          f"relation a preview is cut from is table.schema.table.name and NEVER "
                          f"metadata.table — measured, on 9 of one bundle's 13 dataset descriptors "
                          f"metadata.table holds the UPSTREAM RAW name, so a cut that read it would "
                          f"preview the raw relation under the served stem"})
        entry = run.get(stem)
        if entry is None:
            unrecorded.append(rel)
        elif entry.get("derived_from") == "transform-body":
            findings.append({
                "kind": "PROPOSAL_PREVIEW", "file": rel, "severity": "warning",
                "detail": "the run record says this was cut from the transform's SQL body because "
                          "the relation the descriptor names did not exist. It previews a PROPOSAL, "
                          "not the served view's output, and must be re-cut once it is deployed"})

    if samples_dir.is_dir():
        for f in sorted(glob.glob(str(samples_dir / "*.csv"))):
            p = Path(f)
            if p.name not in claimed:
                findings.append({
                    "kind": "ORPHAN", "file": str(p.relative_to(root)), "severity": "error",
                    "detail": "no descriptor under data/sources or data/datasets claims this "
                              "preview — a stem typo, or the descriptor was deleted and its "
                              "preview outlived it"})
    if unrecorded:
        # FANOUT IS COLLAPSED: one finding with its count, never one line per file.
        findings.append({
            "kind": "UNRECORDED", "file": f"data/samples/{RUN_RECORD}",
            "severity": "error" if strict else "warning",
            "detail": f"{len(unrecorded)} of {present} preview(s) have no entry in the run record, "
                      f"so nothing attests where their rows came from. A hand-typed preview and a "
                      f"machine cut are byte-indistinguishable on disk — this record is the only "
                      f"provenance the shape can carry. First: {unrecorded[:3]}"})

    counts = {"descriptors": len(targets), "present": present, "matched": matched,
              "sources_present": plane_present["sources"], "sources": plane_total["sources"],
              "datasets_present": plane_present["datasets"], "datasets": plane_total["datasets"],
              "connector": connector_id}
    findings.sort(key=lambda f: (f["file"], f["kind"]))
    return findings, counts


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE COMMAND
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _emit(a, state, counts, findings, rc):
    errs = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warning"]
    if a.json:
        print(json.dumps({"state": state,
                          "measured_nothing": rc == D.EMPTY_EXIT,
                          "descriptors": counts.get("descriptors", 0),
                          "samples": counts.get("present", 0),
                          "matched": counts.get("matched", 0),
                          "errors": len(errs), "warnings": len(warns),
                          "findings": findings}, indent=1, ensure_ascii=False))
        return rc
    for f in findings:
        mark = "" if f["severity"] == "error" else " (warning)"
        print(f"  [{f['kind']}]{mark} {f['file']}\n          {f['detail']}")
    cov = (f"{counts.get('present', 0)}/{counts.get('descriptors', 0)} declared relation(s) carry "
           f"a preview ({counts.get('sources_present', 0)}/{counts.get('sources', 0)} source(s), "
           f"{counts.get('datasets_present', 0)}/{counts.get('datasets', 0)} dataset(s))")
    wtail = f" ({len(warns)} warning(s))" if warns else ""
    if state == "no-plane":
        print(f"PASS: {NAME} — no sample plane in this bundle, so the matching rule judged "
              f"NOTHING; {cov} (run with --strict to make that a failure){wtail}")
        return rc
    if errs:
        print(f"FAIL: {NAME} — {len(errs)} finding(s) over {counts['present']} preview(s); {cov}; "
              f"a header that has moved on from its descriptor is cited as evidence while "
              f"previewing a different relation{wtail}")
        return rc
    print(f"PASS: {NAME} — {counts['matched']}/{counts['present']} preview(s) match their "
          f"descriptor exactly and in order; {cov}{wtail}")
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="every declared relation must carry a preview, even in a bundle with no "
                         "samples plane; warning classes become errors")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    L = resolve(root)
    if L.sources is None or L.descriptors is None or getattr(L, "samples", None) is None:
        print(f"could not run: {root} declares no sources plane (a flat-layout project has no "
              f"data/sources by construction, so there is nothing to join a preview to)",
              file=sys.stderr)
        return 2

    try:
        n_src = len(glob.glob(str(Path(L.sources) / "*.yaml")))
        n_ds = len(glob.glob(str(Path(L.descriptors) / "*.yaml")))
        # REFUSED PER AXIS: zero sources and zero datasets are different outages and a caller needs
        # to know which. The sources axis is half the console's Sample tabs.
        if not n_src:
            if a.json:
                return _emit(a, "no-source-descriptors", {}, [], D.EMPTY_EXIT)
            return D.refuse_empty(NAME, L.sources, unit="source descriptor")
        if not n_ds:
            if a.json:
                return _emit(a, "no-dataset-descriptors", {}, [], D.EMPTY_EXIT)
            return D.refuse_empty(NAME, L.descriptors, unit="dataset descriptor")
        samples_dir = Path(L.samples)
        if samples_dir.is_dir() and not glob.glob(str(samples_dir / "*.csv")):
            if a.json:
                return _emit(a, "empty-plane", {}, [], D.EMPTY_EXIT)
            return D.refuse_empty(NAME, samples_dir, unit="preview")
        findings, counts = scan(root, L, strict=a.strict)
    except CouldNotRun as exc:
        print(f"could not run: {exc}", file=sys.stderr)
        return 2

    state = "ok" if samples_dir.is_dir() else "no-plane"
    errs = [f for f in findings if f["severity"] == "error"]
    return _emit(a, state, counts, findings, 1 if errs else 0)


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — one mutant per reject class, the three not-to-measure states, negative controls
# ══════════════════════════════════════════════════════════════════════════════════════════════════

_MANIFEST = ("planes:\n  data: data\n  ontology: ontology\ndescriptors: data/datasets\n"
             "sources: data/sources\nruntime:\n  connector: %s\n  connection: connection.yaml\n")


def _bundle(root: Path, *, connector="mac.connector.duckdb"):
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "mac.project.yaml").write_text(_MANIFEST % connector, encoding="utf-8")
    return root


def _desc(root: Path, axis: str, stem: str, columns, *, types=None, status=None, values=None,
          metadata_table=None):
    cols = []
    for c in columns:
        entry = {"name": c, "role": "value"}
        if types and c in types:
            entry["type"] = types[c]
        if values and c in values:
            entry["values"] = values[c]
        cols.append(entry)
    doc = {"metadata": {"table": metadata_table or stem}, "table": {"name": stem, "schema": "alpha"},
           "columns": cols}
    if status:
        doc["metadata"]["status"] = status
    (root / "data" / axis).mkdir(parents=True, exist_ok=True)
    (root / "data" / axis / f"{stem}.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")


def _sample(root: Path, name: str, header, rows, *, record=True, derived_from="relation"):
    d = root / "data" / "samples"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / name, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, dialect="excel")
        w.writerow(list(header))
        for r in rows:
            w.writerow(list(r))
    if record:
        stem = (name[:-len(SRC_SUFFIX)] if name.endswith(SRC_SUFFIX)
                else name[:-len(DS_SUFFIX)])
        rr = d / RUN_RECORD
        doc = json.loads(rr.read_text(encoding="utf-8")) if rr.is_file() else {"samples": []}
        doc["samples"].append({"stem": stem, "derived_from": derived_from})
        rr.write_text(json.dumps(doc), encoding="utf-8")


def _clean(root: Path):
    _bundle(root)
    _desc(root, "sources", "alpha", ["gamma_code", "beta_count"])
    _desc(root, "datasets", "dim_alpha", ["gamma_code", "beta_count"])
    _sample(root, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"], [("c1", "1"), ("c2", "2")])
    _sample(root, "dim_alpha" + DS_SUFFIX, ["gamma_code", "beta_count"], [("c1", "1")])
    return root


def _run(root, *args):
    import contextlib

    buf = __import__("io").StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = main([str(root)] + list(args))
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 2
    return rc, buf.getvalue()


def _self_test() -> int:                                                        # noqa: C901
    import tempfile

    bad, cases = [], []

    def case(label, ok, why=""):
        cases.append(label)
        if not ok:
            bad.append(f"{label}: {why}")

    def expect(label, root, want, marker=None, args=(), absent=None):
        rc, out = _run(root, *args)
        ok = rc == want and (marker is None or marker in out) \
            and (absent is None or absent not in out)
        why = f"exit {rc} (wanted {want})"
        if marker is not None and marker not in out:
            why += f"; marker {marker!r} absent"
        if absent is not None and absent in out:
            why += f"; {absent!r} should NOT be there"
        why += f" :: {out.strip().splitlines()[-1] if out.strip() else '<no output>'}"
        case(label, ok, why)
        return out

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        #  1 · not a directory at all
        expect("1 not-a-directory could-not-run", base / "nope", 2)

        #  2 · descriptors absent entirely — refused PER AXIS, with the verbatim outage phrase
        r = _bundle(base / "nosrc")
        _desc(r, "datasets", "dim_alpha", ["a"])
        expect("2 zero source descriptors refuses, naming the axis", r, 2,
               D.empty_mark("source descriptor"))
        r = _bundle(base / "nods")
        _desc(r, "sources", "alpha", ["a"])
        expect("3 zero dataset descriptors refuses, naming the axis", r, 2,
               D.empty_mark("dataset descriptor"))

        #  4 · descriptors present, no data/samples dir — the GENUINE zero
        r = _bundle(base / "noplane")
        _desc(r, "sources", "alpha", ["a"])
        _desc(r, "datasets", "dim_alpha", ["a"])
        case("4 fixture 'noplane' was not seeded with a samples dir",
             not (r / "data" / "samples").exists())
        out = expect("5 no samples plane at all is a genuine zero (exit 0)", r, 0, "judged "
                     "NOTHING", absent="0/0 preview(s) match")
        case("6 the no-plane line carries the coverage denominator", "0/2 declared relation(s)" in out,
             out)

        #  7 · --strict makes that zero falsifiable
        expect("7 --strict turns the plane-less zero red", r, 1, "MISSING_PREVIEW",
               args=("--strict",))

        #  8 · a samples dir holding no csv — a plane someone created and nothing wrote
        r2 = _bundle(base / "emptyplane")
        _desc(r2, "sources", "alpha", ["a"])
        _desc(r2, "datasets", "dim_alpha", ["a"])
        (r2 / "data" / "samples").mkdir(parents=True)
        expect("8 samples dir present but holds no preview refuses", r2, 2, D.empty_mark("preview"))

        #  9 · clean
        clean_out = expect("9 NEGATIVE CONTROL clean bundle passes", _clean(base / "clean"), 0,
                           "PASS: " + NAME)
        case("10 the PASS line's first clause is n/n",
             "2/2 preview(s) match" in clean_out, clean_out)

        # the ERROR mutants
        r = _clean(base / "m_missing")
        (r / "data" / "samples" / ("alpha" + SRC_SUFFIX)).unlink()
        expect("11 MUTANT HEADER: a deleted preview in a bundle WITH a plane", r, 1,
               "MISSING_PREVIEW")

        r = _clean(base / "m_drift_missing")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code"], [("c1",)], record=False)
        expect("12 MUTANT HEADER_DRIFT missing a column", r, 1, "MISSING 1 of 2")

        r = _clean(base / "m_drift_extra")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count", "delta"],
                [("c1", "1", "x")], record=False)
        expect("13 MUTANT HEADER_DRIFT an extra column", r, 1, "EXTRA 1")

        r = _clean(base / "m_order")
        _sample(r, "alpha" + SRC_SUFFIX, ["beta_count", "gamma_code"], [("1", "c1")], record=False)
        expect("14 MUTANT HEADER_DRIFT order-only permutation (the case a set comparison passes)",
               r, 1, "different ORDER")

        r = _clean(base / "m_ragged")
        p = r / "data" / "samples" / ("alpha" + SRC_SUFFIX)
        p.write_text("gamma_code,beta_count\r\nc1,1\r\nc2\r\n", encoding="utf-8")
        expect("15 MUTANT RAGGED row", r, 1, "RAGGED")

        r = _clean(base / "m_orphan")
        _sample(r, "ghost" + DS_SUFFIX, ["a"], [("1",)], record=False)
        expect("16 MUTANT ORPHAN preview", r, 1, "ORPHAN")

        r = _clean(base / "m_crossed")
        (r / "data" / "samples" / ("alpha" + SRC_SUFFIX)).rename(
            r / "data" / "samples" / ("alpha" + DS_SUFFIX))
        expect("17 MUTANT SUFFIX_CROSSED between planes", r, 1, "SUFFIX_CROSSED")

        r = _clean(base / "m_empty")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"], [], record=False)
        expect("18 MUTANT EMPTY_PREVIEW header and zero data rows", r, 1, "EMPTY_PREVIEW")

        r = _clean(base / "m_nocols")
        _desc(r, "sources", "alpha", [])
        expect("19 MUTANT NO_COLUMNS descriptor", r, 1, "NO_COLUMNS")

        # the WARNING classes must be visible and must NOT block
        r = _clean(base / "w_ceiling")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"],
                [(f"c{i}", str(i)) for i in range(21)], record=False)
        expect("20 W OVER_CEILING warns and does not block", r, 0, "OVER_CEILING")

        r = _clean(base / "w_sentinel")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"],
                [("c1", "NULL"), ("c2", "2")], record=False)
        expect("21 MUTANT NULL_SENTINEL warns, and --strict makes it an error", r, 0,
               "NULL_SENTINEL")
        expect("22 MUTANT NULL_SENTINEL under --strict is an error", r, 1, "NULL_SENTINEL",
               args=("--strict",))

        r = _clean(base / "n_sentinel_declared")
        _desc(r, "sources", "alpha", ["gamma_code", "beta_count"],
              values={"beta_count": ["NULL", "2"]})
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"],
                [("c1", "NULL")], record=False)
        expect("23 NEGATIVE CONTROL a column that genuinely declares the string NULL", r, 0,
               absent="NULL_SENTINEL")

        r = _clean(base / "w_unrecorded")
        (r / "data" / "samples" / RUN_RECORD).unlink()
        expect("24 W UNRECORDED provenance warns, collapsed with its count", r, 0,
               "2 of 2 preview(s) have no entry")

        r = _clean(base / "w_proposal")
        (r / "data" / "samples" / RUN_RECORD).unlink()
        _sample(r, "dim_alpha" + DS_SUFFIX, ["gamma_code", "beta_count"], [("c1", "1")],
                derived_from="transform-body")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"], [("c1", "1")])
        expect("25 W PROPOSAL_PREVIEW names a body-derived preview", r, 0, "PROPOSAL_PREVIEW")

        # type-vocabulary: the same rendering, two declared engines, and a third it must not judge
        r = _bundle(base / "n_array_athena", connector="mac.connector.athena")
        _desc(r, "sources", "alpha", ["members"], types={"members": "array(string)"})
        _desc(r, "datasets", "dim_alpha", ["members"], types={"members": "array(string)"})
        _sample(r, "alpha" + SRC_SUFFIX, ["members"], [("[a, b]",)])
        _sample(r, "dim_alpha" + DS_SUFFIX, ["members"], [("[a, b]",)])
        expect("26 NEGATIVE CONTROL array(string) rendered [a, b] on one engine", r, 0,
               absent="TYPE_SHAPE")

        r = _bundle(base / "n_array_duckdb", connector="mac.connector.duckdb")
        _desc(r, "sources", "alpha", ["members"], types={"members": "VARCHAR[]"})
        _desc(r, "datasets", "dim_alpha", ["members"], types={"members": "VARCHAR[]"})
        _sample(r, "alpha" + SRC_SUFFIX, ["members"], [("[a, b]",)])
        _sample(r, "dim_alpha" + DS_SUFFIX, ["members"], [("[a, b]",)])
        expect("27 NEGATIVE CONTROL varchar[] rendered [a, b] on the other engine", r, 0,
               absent="TYPE_SHAPE")

        r = _bundle(base / "m_typeshape", connector="mac.connector.duckdb")
        _desc(r, "sources", "alpha", ["members"], types={"members": "varchar"})
        _desc(r, "datasets", "dim_alpha", ["members"], types={"members": "varchar"})
        _sample(r, "alpha" + SRC_SUFFIX, ["members"], [("[a, b]",)])
        _sample(r, "dim_alpha" + DS_SUFFIX, ["members"], [("[a, b]",)])
        expect("28 MUTANT TYPE_SHAPE still fires when the vocabulary changes", r, 0, "TYPE_SHAPE")

        r = _bundle(base / "m_unknownvocab", connector="mac.connector.other")
        _desc(r, "sources", "alpha", ["members"], types={"members": "whatever"})
        _desc(r, "datasets", "dim_alpha", ["members"], types={"members": "whatever"})
        _sample(r, "alpha" + SRC_SUFFIX, ["members"], [("[a, b]",)])
        _sample(r, "dim_alpha" + DS_SUFFIX, ["members"], [("[a, b]",)])
        expect("29 MUTANT an undeclared engine announces its own blindness, never TYPE_SHAPE",
               r, 0, "UNKNOWN_TYPE_VOCABULARY", absent="TYPE_SHAPE")

        # status must never exempt, a short relation is not a defect, and metadata.table is a trap
        r = _clean(base / "n_draft")
        _desc(r, "sources", "alpha", ["gamma_code", "beta_count"], status="draft")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code"], [("c1",)], record=False)
        expect("30 NEGATIVE CONTROL status: draft never exempts a drifted header", r, 1,
               "HEADER_DRIFT")

        r = _clean(base / "n_short")
        _sample(r, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"],
                [(f"c{i}", str(i)) for i in range(5)], record=False)
        expect("31 NEGATIVE CONTROL 5 rows for a 5-row relation is not a defect", r, 0,
               absent="OVER_CEILING")

        r = _clean(base / "w_metatable")
        _desc(r, "sources", "alpha", ["gamma_code", "beta_count"], metadata_table="raw_alpha")
        expect("32 W METADATA_TABLE names the upstream-name trap", r, 0, "METADATA_TABLE")

        # byte idempotence of the VERDICT ITSELF, and the JSON branch on every non-ok state
        r = _clean(base / "idem")
        _, o1 = _run(r)
        _, o2 = _run(r)
        case("33 the verdict is byte-identical on a second run", o1 == o2, "output moved")
        r3 = base / "idem_rev"
        _bundle(r3)
        _desc(r3, "datasets", "dim_alpha", ["gamma_code", "beta_count"])
        _desc(r3, "sources", "alpha", ["gamma_code", "beta_count"])
        _sample(r3, "dim_alpha" + DS_SUFFIX, ["gamma_code", "beta_count"], [("c1", "1")])
        _sample(r3, "alpha" + SRC_SUFFIX, ["gamma_code", "beta_count"],
                [("c1", "1"), ("c2", "2")])
        _, o3 = _run(r3)
        case("34 the verdict does not depend on the order the files were created in",
             o1.replace(str(r), "") == o3.replace(str(r3), ""), "creation order changed the output")

        ok_json = True
        for label, root_, args in (("ok", base / "clean", ()), ("no-plane", base / "noplane", ()),
                                   ("empty-plane", base / "emptyplane", ()),
                                   ("no-source-descriptors", base / "nosrc", ()),
                                   ("drift", base / "m_order", ())):
            _, out = _run(root_, "--json", *args)
            try:
                json.loads(out)
            except Exception:                                                   # noqa: BLE001
                ok_json = False
        case("35 --json parses on every state, and the outage travels in it", ok_json)

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mut = len([c for c in cases if "MUTANT" in c])
    neg = len([c for c in cases if "NEGATIVE CONTROL" in c])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mut} mutant(s) of the rule "
          f"(missing preview, header MISSING/EXTRA/ORDER-only, ragged, orphan, suffix crossed, "
          f"empty preview, no columns, NULL sentinel with and without --strict, type shape, an "
          f"undeclared engine's blindness), 4 not-to-measure states (not a directory, zero sources, "
          f"zero datasets, a plane with no preview in it), and {neg} negative controls across 2 "
          f"declared connectors (array spellings array(string) and varchar[], a declared NULL "
          f"value, status never exempts, a short relation, and the plane-less zero)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
