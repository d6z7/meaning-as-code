#!/usr/bin/env python3
"""A measured reference must be DRAWABLE, KEYED BY RELATION AND COLUMN, and carry its denominator.

    python3 tools/check_physical_references.py <root> [--json] [--self-test]

WHAT THIS GATE IS FOR
---------------------
`data/references/*.yaml` is the data plane's own picture of how relations point at each other, and
it is consumed by a DIAGRAM. That consumer fails silently in a specific, measured way: a renderer
drops any line whose endpoint is not a box, with no error, no callback and no mark on the page
(@reactflow/core returns null for an edge whose source or target node is absent). So a reference
naming a relation the diagram has no box for does not draw WRONG — it does not draw at all, and the
picture then reads as "this warehouse has fewer references than it has". Absence rendering as
completeness is this estate's recurring defect, and there is no way to see it from the screen.

This gate is the thing that sees it. It runs OFFLINE — three local file families, no engine, no
credential, no network — so it is runnable in CI and against a cloud-warehouse bundle with no
outward action at all. The DERIVER (`tools/mac_references.py`) goes through the connector seam; a
gate that did too would inherit its credentials for no gain.

THE VOCABULARY IS PART OF THE CONTRACT, and it is checked. This family exists because the physical
half of an ER picture was being read out of the ontology's relationship file, keyed BY CONCEPT, with
the relations and columns flattened into a `join_rule` string. A data-plane file that says `concept`
or `edge`, or that carries a join as a string instead of two {relation, column} pairs, has re-made
that conflation, and the gate says so by name.

WHAT IT MUST NOT DO, each a way to be green for the wrong reason:
  1. never repair an artifact. A gate that fixes its own finding destroys the evidence.
  2. NEVER TREAT AN ABSENT NUMBER AS A ZERO. `parent_unreferenced` absent is not "none"; a verdict
     whose evidence block has no denominator has not been measured, whatever its `verdict:` says.
  3. never accept a dangling entry with a target. `to: null` is the whole point of the class: the
     moment a dangling reference acquires a parent it is a claim, and claims are measured.
  4. never let an ambiguity go unmarked. Two parents that measure identically is a RULING to make,
     and an entry recording one without `needs_ruling` has quietly made it.
  5. never exempt on `status:` or a timestamp. Neither is in this contract.

THE ERROR CLASSES (exit 1)
    ENDPOINT_UNRESOLVED   a reference names a relation with no source descriptor. THE SILENT ONE.
    COLUMN_UNDECLARED     a reference names a column its relation's descriptor does not declare.
    ID_COLLISION          two references share an id, so a renderer cannot tell them apart. Ids are
                          keyed by RELATION AND COLUMN on both ends precisely to prevent this: two
                          date-like columns of one relation pointing at one calendar collide on any
                          id derived from the relation pair alone, and one line silently stops
                          responding to selection. That has already happened once in this estate.
    ONTOLOGY_VOCABULARY   a data-plane file speaking the meaning plane's words, or carrying a join
                          as a string.
    EVIDENCE_MISSING      an entry whose verdict turns on numbers the entry does not carry.
    ADMISSION_MISSING     a file with no `admission:` block, or two files that disagree about one.
                          A reader opens ONE file; an entry must not be readable without the floors
                          that judged it, and two different floors in one family means two rules.
    DANGLING_INVENTED     a dangling entry with a target, or with no `basis`.
    VOCABULARY_CLOSED     a cardinality or participation value outside its closed set.
    PARTICIPATION_MISSING a drawn reference with no participation block. Keys alone draw every
                          relationship mandatory; participation is the measured half that does not
                          come from a key, and an entry without it cannot be drawn honestly.
    AMBIGUITY_HIDDEN      `ambiguous_with` without `needs_ruling`.
    UNMEASURED_RELATION   a relation with a source descriptor AND a profile but no references file.
                          THE POPULATION IS THE DESCRIPTORS, never the directory being judged: a
                          gate whose denominator is the files it reads cannot see an absent one.

EXIT CODES. 0 clean · 1 a finding about the bundle · 2 could not run (no plane, an EMPTY
POPULATION). Every verdict line carries BOTH denominators.
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import io
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:                                                        # noqa: E402
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mac_diag as D                                                             # noqa: E402

NAME = "check_physical_references"

# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE TWO PHYSICAL PLANES. Read from the deriver rather than restated — `tools/mac_references.py`
# owns which descriptor plane pairs with which artifact directory, and a gate that kept its own copy
# of that pairing is exactly the two-homes-for-one-fact shape this family exists to undo. If the
# deriver cannot be imported the gate refuses (exit 2) rather than judging one plane and calling it
# the bundle: a gate that silently checks half a bundle reports absence as completeness, which is
# this estate's recurring defect and the reason this file exists.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
from mac_references import PLANES                                                # noqa: E402

#: The SOURCES plane's artifact directory, named once for the self-test's fixtures (which seed that
#: plane). Every production path reads `PLANES[plane]["out"]` — this is not a second home for it.
REFS_DIR = PLANES["sources"]["out"]

#: The meaning plane's words. A data-plane reference file that uses one has re-made the conflation
#: this family exists to undo. `join_rule` is here too: a join expressed as a STRING is the shape
#: that had to be re-parsed with a regular expression to find the columns it actually named.
ONTOLOGY_WORDS = ("concept", "edge_id", "endpoints", "join_rule", "realized_by", "edges")

#: Closed. A value outside these cannot be turned into a crow's-foot terminal, and a terminal that
#: is not drawn is an ER diagram that has stopped saying the one thing it exists to say.
CARDINALITY_VALUES = ("one", "many")
PARTICIPATION_VALUES = ("mandatory", "optional")

#: Every number a `real` verdict turns on. Absent is NOT zero.
REQUIRED_EVIDENCE = ("child_rows", "child_nonnull", "orphan_rows", "orphan_distinct",
                     "parent_rows", "parent_distinct", "parent_used", "inclusion")


class Finding:
    def __init__(self, cls, where, detail):
        self.cls, self.where, self.detail = cls, where, detail

    def __str__(self):
        return f"  [{self.cls:<21}] {self.where}\n          {self.detail}"

    def as_dict(self):
        return {"class": self.cls, "where": self.where, "detail": self.detail}


def _load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}, None
    except yaml.YAMLError as exc:                                                # pragma: no cover
        return {}, " ".join(str(exc).split())


def declared_relations(root: Path, plane: str = "sources"):
    """{stem: {columns}} from this plane's descriptors — the ENTITY population a diagram can box.

    THE POPULATION IS THE DESCRIPTOR PLANE, NEVER THE ARTIFACT DIRECTORY. An absent references file
    is invisible to a gate that counts only what it reads, which is how "fewer references than this
    warehouse has" comes to read as a clean measurement.
    """
    out = {}
    for p in sorted(glob.glob(str(root / PLANES[plane]["descriptors"] / "*.yaml"))):
        doc, _err = _load(Path(p))
        stem = doc.get("of") or Path(p).stem
        out[stem] = {c.get("name") for c in (doc.get("columns") or []) if c.get("name")}
    return out


def profiled_relations(root: Path):
    return {Path(p).stem for p in glob.glob(str(root / "data" / "profiles" / "*.yaml"))}


def _endpoint_ok(ep):
    return isinstance(ep, dict) and set(ep) == {"relation", "column"} and ep["relation"] \
        and ep["column"]


def check(root: Path, plane: str = "sources"):                                  # noqa: C901
    """(findings, counts). PURE over the files. Never repairs, never completes, never exempts."""
    findings = []
    ddir = PLANES[plane]["descriptors"]
    refs_dir = PLANES[plane]["out"]
    relations = declared_relations(root, plane)
    profiled = profiled_relations(root)
    files = sorted(glob.glob(str(root / refs_dir / "*.yaml")))
    seen_ids, admissions, counts = defaultdict(list), {}, Counter()
    counts["relations_declared"] = len(relations)
    counts["files"] = len(files)

    for fp in files:
        rel_path = os.path.relpath(fp, root)
        doc, err = _load(Path(fp))
        if err:
            findings.append(Finding("EVIDENCE_MISSING", rel_path, f"will not parse: {err}"))
            continue
        raw = Path(fp).read_text(encoding="utf-8")
        # MATCHED AT A KEY POSITION, not as a substring. A bare `"endpoints:" in raw` also fires on
        # `parent_endpoints:` — a legitimate DENOMINATOR in the measurement block — and a gate whose
        # first real run is 8 false positives is a gate an operator learns to ignore. Measured: that
        # is exactly what it did.
        keys = {ln.split(":", 1)[0].strip().lstrip("- ")
                for ln in raw.splitlines() if ":" in ln}
        for word in ONTOLOGY_WORDS:
            if word in keys:
                findings.append(Finding(
                    "ONTOLOGY_VOCABULARY", rel_path,
                    f"carries the key {word!r}. A PHYSICAL reference is keyed by RELATION AND "
                    f"COLUMN as two fields on each end — never through a business object and never "
                    f"as a join string to be re-parsed. That conflation is what this family "
                    f"replaced, and a file that re-introduces it re-introduces the defect"))
        adm = doc.get("admission")
        if not isinstance(adm, dict) or not adm:
            findings.append(Finding(
                "ADMISSION_MISSING", rel_path,
                "carries no `admission:` block. A reader opens ONE file, and an entry whose "
                "verdict depends on a floor must not be readable without that floor"))
        else:
            admissions[rel_path] = adm

        entries = doc.get("references") or []
        dangling = doc.get("references_dangling") or []
        rejected = doc.get("candidates_rejected") or []
        counts["references"] += len(entries)
        counts["dangling"] += len(dangling)
        counts["rejected"] += len(rejected)
        counts["drawn"] += sum(1 for e in entries if e.get("drawn"))

        for e in entries:
            eid = e.get("id") or "<no id>"
            where = f"{rel_path}#references.{eid}"
            seen_ids[eid].append(rel_path)
            for side in ("from", "to"):
                ep = e.get(side)
                if not _endpoint_ok(ep):
                    findings.append(Finding(
                        "ONTOLOGY_VOCABULARY", where,
                        f"`{side}` is {ep!r}; a physical endpoint is exactly "
                        f"{{relation, column}}"))
                    continue
                if ep["relation"] not in relations:
                    findings.append(Finding(
                        "ENDPOINT_UNRESOLVED", where,
                        f"`{side}` names relation {ep['relation']!r}, which has no descriptor under "
                        f"{ddir}/ ({len(relations)} declared). A diagram has no box for it, "
                        f"and the renderer DROPS such a line with no error and no mark — the "
                        f"reference would vanish rather than be wrong"))
                elif ep["column"] not in relations[ep["relation"]]:
                    findings.append(Finding(
                        "COLUMN_UNDECLARED", where,
                        f"`{side}` names column {ep['column']!r} of {ep['relation']!r}, which that "
                        f"relation's descriptor does not declare"))
            card = e.get("cardinality") or {}
            part = e.get("participation") or {}
            if not part:
                findings.append(Finding(
                    "PARTICIPATION_MISSING", where,
                    "carries no `participation:` block. Keys alone draw every relationship "
                    "mandatory; participation is the measured half a key cannot supply"))
            for k in ("child", "parent"):
                if card.get(k) and card[k] not in CARDINALITY_VALUES:
                    findings.append(Finding("VOCABULARY_CLOSED", where,
                                            f"cardinality.{k} is {card[k]!r}, outside "
                                            f"{CARDINALITY_VALUES}"))
                if part.get(k) and part[k] not in PARTICIPATION_VALUES:
                    findings.append(Finding("VOCABULARY_CLOSED", where,
                                            f"participation.{k} is {part[k]!r}, outside "
                                            f"{PARTICIPATION_VALUES}"))
            ev = e.get("evidence") or {}
            missing = [k for k in REQUIRED_EVIDENCE if ev.get(k) is None]
            if missing:
                findings.append(Finding(
                    "EVIDENCE_MISSING", where,
                    f"verdict {e.get('verdict')!r} but the evidence block carries no {missing}. An "
                    f"absent count is NOT a zero: it means the reference was not measured"))
            if e.get("ambiguous_with") and not e.get("needs_ruling"):
                findings.append(Finding(
                    "AMBIGUITY_HIDDEN", where,
                    f"names {e['ambiguous_with']} as measuring identically but carries no "
                    f"`needs_ruling`. Two parents that cannot be separated by value inclusion is a "
                    f"ruling to make, and recording one without saying so has quietly made it"))

        for d in dangling:
            did = d.get("id") or "<no id>"
            where = f"{rel_path}#references_dangling.{did}"
            seen_ids[did].append(rel_path)
            if d.get("to") is not None:
                findings.append(Finding(
                    "DANGLING_INVENTED", where,
                    f"carries a target {d['to']!r}. A dangling reference has NO parent relation — "
                    f"that is the whole class. The moment it acquires one it is a claim, and a "
                    f"claim belongs in `references:` with the measurement that admitted it"))
            if not d.get("basis"):
                findings.append(Finding(
                    "DANGLING_INVENTED", where,
                    "carries no `basis`. Dangling detection is weaker evidence than a measurement "
                    "against a parent, and a reader must be able to see on what"))
            if not _endpoint_ok(d.get("from")):
                findings.append(Finding("ONTOLOGY_VOCABULARY", where,
                                        f"`from` is {d.get('from')!r}; expected "
                                        f"{{relation, column}}"))
            elif d["from"]["relation"] not in relations:
                findings.append(Finding(
                    "ENDPOINT_UNRESOLVED", where,
                    f"is carried by relation {d['from']['relation']!r}, which has no descriptor "
                    f"under {ddir}/"))

    for eid, homes in sorted(seen_ids.items()):
        if len(homes) > 1:
            findings.append(Finding(
                "ID_COLLISION", eid,
                f"appears in {len(homes)} file(s): {homes}. A renderer identifies a line by its "
                f"id; a collision makes one of them unaddressable and it silently stops responding "
                f"to selection"))

    if len(admissions) > 1:
        first = next(iter(admissions.values()))
        for path, adm in admissions.items():
            if adm != first:
                findings.append(Finding(
                    "ADMISSION_MISSING", path,
                    f"declares admission {adm} while another file in the same family declares "
                    f"{first}. Two floors in one family is two rules, and no reader can tell which "
                    f"judged a given entry"))
                break

    have = {Path(f).stem for f in files}
    for stem in sorted(relations):
        if stem in profiled and stem not in have:
            findings.append(Finding(
                "UNMEASURED_RELATION", f"{refs_dir}/{stem}.yaml",
                f"{stem} has a descriptor under {ddir}/ and a profile but NO references file. The "
                f"population is the descriptors, not this directory — an absent file is invisible "
                f"to a gate that counts only what it reads"))
    counts["relations_measured"] = len(have & set(relations))
    return findings, counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?")
    ap.add_argument("--plane", choices=sorted(PLANES), default=None,
                    help=("check ONE physical plane instead of every plane this bundle declares. "
                          "Default: every plane with descriptors — so a bundle that measured its "
                          "sources and not its served relations is told so, with the denominator, "
                          "rather than being green on half a warehouse"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        ap.error("a bundle root is required")
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2

    # ── WHICH PLANES THIS BUNDLE HAS, AND WHICH IT HAS MEASURED. Both are reported, because they
    #    are different facts and the second one being silent is how "this warehouse has fewer
    #    references than it has" comes to read as a measurement.
    if a.plane:
        wanted = [a.plane]
    else:
        wanted = [pl for pl in PLANES if glob.glob(str(root / PLANES[pl]["descriptors"] / "*.yaml"))]
    if not wanted:
        dirs = ", ".join(PLANES[pl]["descriptors"] for pl in PLANES)
        if a.json:
            print(json.dumps({"state": "no-descriptors", "measured_nothing": True,
                              "descriptor_planes": dirs}, indent=1))
            return D.EMPTY_EXIT
        # THE UNIT STRING STAYS VERBATIM. `mac_diag.empty_mark` is a CROSS-TOOL signal — a CI
        # script, the compiler and this file's own self-test all grep it — so the plane detail goes
        # on its own line beside the marker rather than inside it.
        print(f"  [planes] looked for a descriptor in every physical plane: {dirs}")
        return D.refuse_empty(NAME, root / PLANES["sources"]["descriptors"],
                              unit="source descriptor")
    measured = [pl for pl in wanted if glob.glob(str(root / PLANES[pl]["out"] / "*.yaml"))]
    if not measured:
        # NEITHER plane is measured. That is the original refusal, and it names every artifact
        # directory it looked in so the reader is not left guessing which one was expected.
        outs = ", ".join(PLANES[pl]["out"] for pl in wanted)
        if a.json:
            print(json.dumps({"state": "no-references-plane", "measured_nothing": True,
                              "planes_declared": wanted, "artifact_directories": outs},
                             indent=1))
            return D.EMPTY_EXIT
        print(f"  [planes] {len(wanted)} plane(s) declare descriptors and NONE is measured; "
              f"looked in: {outs}")
        return D.refuse_empty(NAME, root / PLANES[wanted[0]]["out"], unit="references file")

    per_plane, findings_all, code = {}, [], 0
    for pl in wanted:
        declared = len(declared_relations(root, pl))
        if pl not in measured:
            # NOT A FINDING AND NOT A PASS: this plane was never measured. Printed WITH ITS
            # DENOMINATOR (0 of N) and with the command that produces it, because a plane that is
            # simply absent from the output is a plane a reader assumes is clean.
            per_plane[pl] = {"state": "not-measured", "relations_declared": declared,
                             "relations_measured": 0, "artifact_directory": PLANES[pl]["out"]}
            continue
        f, counts = check(root, pl)
        findings_all += [{**x.as_dict(), "plane": pl} for x in f]
        code = 1 if (code or f) else 0
        per_plane[pl] = {"state": "checked", "findings": [x.as_dict() for x in f],
                         "by_class": dict(sorted(Counter(x.cls for x in f).items())),
                         "counts": dict(sorted(counts.items())),
                         "artifact_directory": PLANES[pl]["out"]}
        if not a.json:
            for x in f:
                print(f"  [plane {pl}]\n{x}")

    if a.json:
        print(json.dumps({"planes": per_plane, "findings": findings_all, "exit": code},
                         indent=1, ensure_ascii=False))
        return code
    for pl in wanted:
        r = per_plane[pl]
        if r["state"] == "not-measured":
            print(f"  [not measured] plane {pl}: 0 of {r['relations_declared']} declared "
                  f"relation(s) carry a references file — {r['artifact_directory']}/ holds none. "
                  f"Produce it with: python3 tools/mac_references.py <root> --plane {pl}")
            continue
        c, bc = r["counts"], r["by_class"]
        head = "PASS" if not bc else "FAIL"
        print(f"  {head}: plane {pl} ({r['artifact_directory']}) — {c['relations_measured']} of "
              f"{c['relations_declared']} declared relation(s) carry a references file; "
              f"{c['drawn']} of {c['references']} measured reference(s) drawn, {c['dangling']} "
              f"dangling, {c['rejected']} candidate(s) recorded as rejected; "
              f"{sum(bc.values())} finding(s)" + (f" — {bc}" if bc else ""))
    head = "PASS" if code == 0 else "FAIL"
    checked = [pl for pl in wanted if per_plane[pl]["state"] == "checked"]
    tot = {k: sum(per_plane[pl]["counts"].get(k, 0) for pl in checked)
           for k in ("relations_declared", "relations_measured", "references", "drawn", "dangling",
                     "rejected")}
    print(f"{head}: {NAME} — {len(checked)} of {len(wanted)} physical plane(s) measured "
          f"({', '.join(checked) or 'none'}); {tot['relations_measured']} of "
          f"{tot['relations_declared']} declared relation(s) across those plane(s) carry a "
          f"references file; {tot['drawn']} of {tot['references']} measured reference(s) drawn, "
          f"{tot['dangling']} dangling, {tot['rejected']} candidate(s) recorded as rejected; "
          f"{len(findings_all)} finding(s)")
    return code


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — one mutant per reject class, plus the negative controls. Synthetic names only.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

_CLEAN_REF = {
    "id": "alpha.Pointer__gamma.GammaRef",
    "from": {"relation": "alpha", "column": "Pointer"},
    "to": {"relation": "gamma", "column": "GammaRef"},
    "parent_key_role": "identity", "verdict": "real", "drawn": True,
    "cardinality": {"child": "many", "parent": "one"},
    "participation": {"child": "mandatory", "parent": "optional", "parent_unreferenced": 1},
    "evidence": {"child_rows": 5, "child_nonnull": 5, "orphan_rows": 0, "orphan_distinct": 0,
                 "parent_rows": 4, "parent_distinct": 4, "parent_used": 3, "inclusion": 1.0},
    "name_match": False, "admitted_because": "inclusion 1.000000 …",
}
_CLEAN_DANGLING = {
    "id": "alpha.DeltaRef__?", "from": {"relation": "alpha", "column": "DeltaRef"}, "to": None,
    "verdict": "dangling", "basis": "key_naming_convention", "basis_detail": "…",
    "evidence": {"child_distinct": 3},
}
_ADMISSION = {"inclusion_required": 1.0, "near_miss_floor": 0.995, "domain_exercise_floor": 0.5}


def _seed(root: Path, *, refs=None, dangling=None, admission=_ADMISSION, extra_source=True,
          alpha_cols=("Pointer", "DeltaRef"), profile_omega=False, collide=False):
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "profiles").mkdir(parents=True, exist_ok=True)
    (root / REFS_DIR).mkdir(parents=True, exist_ok=True)
    cols = {"alpha": list(alpha_cols), "gamma": ["GammaRef"]}
    if not extra_source:
        cols.pop("gamma")
    for stem, cs in cols.items():
        (root / "data" / "sources" / f"{stem}.yaml").write_text(yaml.safe_dump(
            {"of": stem, "table": {"name": stem, "schema": "alpha_schema"},
             "columns": [{"name": c, "role": "value"} for c in cs]}), encoding="utf-8")
        (root / "data" / "profiles" / f"{stem}.yaml").write_text(yaml.safe_dump(
            {"of": stem, "profile": {"rows": 5}}), encoding="utf-8")
    if profile_omega:
        (root / "data" / "sources" / "omega.yaml").write_text(yaml.safe_dump(
            {"of": "omega", "table": {"name": "omega", "schema": "alpha_schema"},
             "columns": [{"name": "OmegaRef"}]}), encoding="utf-8")
        (root / "data" / "profiles" / "omega.yaml").write_text(yaml.safe_dump(
            {"of": "omega", "profile": {"rows": 1}}), encoding="utf-8")
    # THE MEASURER WRITES A FILE FOR EVERY RELATION IT COULD READ, including one with no reference
    # of its own — that is what makes "measured and has none" distinguishable from "not measured".
    # The fixture mirrors it, so UNMEASURED_RELATION has to be seeded deliberately.
    entries = list(refs if refs is not None else [_CLEAN_REF])
    dang = list(dangling if dangling is not None else [_CLEAN_DANGLING])
    for stem, e, d in (("alpha", entries, dang),
                       ("gamma", entries if collide else [], [])):
        if stem == "gamma" and not extra_source:
            continue
        doc = {"of": stem, "relation": f"alpha_schema.{stem}",
               "references": e, "references_dangling": d, "candidates_rejected": []}
        if admission is not None:
            doc["admission"] = dict(admission)
        (root / REFS_DIR / f"{stem}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False),
                                                      encoding="utf-8")
    return root


def _run(root, *args):
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = main([str(root), *args])
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 2
    return rc, buf.getvalue()


def _self_test() -> int:                                                        # noqa: C901
    import copy
    import tempfile

    bad, cases = [], []

    def case(label, ok, why=""):
        cases.append(label)
        if not ok:
            bad.append(f"{label}: {why}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        def expect(label, root, want_code, marker=None, args=()):
            rc, out = _run(root, *args)
            ok = rc == want_code and (marker is None or marker in out)
            case(label, ok, f"exit {rc} (wanted {want_code})"
                            + ("" if marker is None or marker in out
                               else f"; marker {marker!r} absent")
                            + f" :: {out.strip().splitlines()[-1] if out.strip() else ''}")
            return out

        out = expect("NEGATIVE CONTROL a measured, drawable family passes",
                     _seed(base / "clean"), 0, "PASS: check_physical_references")
        case("NEGATIVE CONTROL the verdict line carries BOTH denominators",
             "2 of 2 declared relation(s)" in out and "1 of 1 measured reference(s) drawn" in out,
             out)

        bad_ep = copy.deepcopy(_CLEAN_REF)
        bad_ep["to"] = {"relation": "omega", "column": "OmegaRef"}
        expect("MUTANT an endpoint with no descriptor is ENDPOINT_UNRESOLVED",
               _seed(base / "unresolved", refs=[bad_ep]), 1, "ENDPOINT_UNRESOLVED")

        bad_col = copy.deepcopy(_CLEAN_REF)
        bad_col["from"] = {"relation": "alpha", "column": "NotThere"}
        expect("MUTANT a column the descriptor does not declare is COLUMN_UNDECLARED",
               _seed(base / "badcol", refs=[bad_col]), 1, "COLUMN_UNDECLARED")

        expect("MUTANT two files sharing one reference id is ID_COLLISION",
               _seed(base / "collide", collide=True), 1, "ID_COLLISION")

        ont = copy.deepcopy(_CLEAN_REF)
        ont["join_rule"] = "alpha.Pointer = gamma.GammaRef"
        expect("MUTANT a join as a STRING is ONTOLOGY_VOCABULARY",
               _seed(base / "joinrule", refs=[ont]), 1, "ONTOLOGY_VOCABULARY")
        ont2 = copy.deepcopy(_CLEAN_REF)
        ont2["from"] = {"concept": "Alpha"}
        expect("MUTANT an endpoint keyed BY CONCEPT is ONTOLOGY_VOCABULARY",
               _seed(base / "byconcept", refs=[ont2]), 1, "ONTOLOGY_VOCABULARY")

        thin = copy.deepcopy(_CLEAN_REF)
        thin["evidence"] = {"inclusion": 1.0}
        expect("MUTANT a verdict with no denominator is EVIDENCE_MISSING",
               _seed(base / "thin", refs=[thin]), 1, "EVIDENCE_MISSING")

        expect("MUTANT a file with no admission block is ADMISSION_MISSING",
               _seed(base / "noadm", admission=None), 1, "ADMISSION_MISSING")

        nopart = copy.deepcopy(_CLEAN_REF)
        nopart.pop("participation")
        expect("MUTANT a drawn reference with no participation is PARTICIPATION_MISSING",
               _seed(base / "nopart", refs=[nopart]), 1, "PARTICIPATION_MISSING")

        wild = copy.deepcopy(_CLEAN_REF)
        wild["cardinality"] = {"child": "1:N", "parent": "one"}
        expect("MUTANT a cardinality outside the closed set is VOCABULARY_CLOSED",
               _seed(base / "wild", refs=[wild]), 1, "VOCABULARY_CLOSED")
        wildp = copy.deepcopy(_CLEAN_REF)
        wildp["participation"] = {"child": "maybe", "parent": "optional"}
        expect("MUTANT a participation outside the closed set is VOCABULARY_CLOSED",
               _seed(base / "wildp", refs=[wildp]), 1, "VOCABULARY_CLOSED")

        inv = copy.deepcopy(_CLEAN_DANGLING)
        inv["to"] = {"relation": "gamma", "column": "GammaRef"}
        expect("MUTANT a dangling entry that acquired a parent is DANGLING_INVENTED",
               _seed(base / "invented", dangling=[inv]), 1, "DANGLING_INVENTED")
        nob = copy.deepcopy(_CLEAN_DANGLING)
        nob.pop("basis")
        expect("MUTANT a dangling entry with no basis is DANGLING_INVENTED",
               _seed(base / "nobasis", dangling=[nob]), 1, "DANGLING_INVENTED")

        amb = copy.deepcopy(_CLEAN_REF)
        amb["ambiguous_with"] = ["gamma.Other"]
        expect("MUTANT an ambiguity with no needs_ruling is AMBIGUITY_HIDDEN",
               _seed(base / "amb", refs=[amb]), 1, "AMBIGUITY_HIDDEN")
        amb2 = copy.deepcopy(amb)
        amb2["needs_ruling"] = "value inclusion cannot separate them"
        expect("NEGATIVE CONTROL a DECLARED ambiguity passes",
               _seed(base / "amb2", refs=[amb2]), 0, "PASS")

        expect("MUTANT a profiled relation with no references file is UNMEASURED_RELATION",
               _seed(base / "absent", profile_omega=True), 1, "UNMEASURED_RELATION")

        two = _seed(base / "twoadm")
        (two / REFS_DIR / "gamma.yaml").write_text(yaml.safe_dump(
            {"of": "gamma", "admission": {"inclusion_required": 0.9}, "references": [],
             "references_dangling": [], "candidates_rejected": []}, sort_keys=False),
            encoding="utf-8")
        expect("MUTANT two files declaring DIFFERENT floors is ADMISSION_MISSING",
               two, 1, "another file in the same family")

        bare = base / "bare"
        (bare / "data").mkdir(parents=True)
        expect("MUTANT no source descriptors refuses (exit 2), verbatim marker", bare,
               D.EMPTY_EXIT, D.empty_mark("source descriptor"))
        noplane = base / "noplane"
        _seed(noplane)
        for f in glob.glob(str(noplane / REFS_DIR / "*.yaml")):
            os.remove(f)
        expect("MUTANT a bundle with no references plane refuses (exit 2), not PASS", noplane,
               D.EMPTY_EXIT, D.empty_mark("references file"))
        rc, _o = _run(base / "not-a-directory-at-all")
        case("MUTANT a root that is not a directory could-not-run", rc == 2, f"exit {rc}")

        # ── HALF A WAREHOUSE MUST NOT READ AS A CLEAN ONE. A bundle that declares served
        #    datasets and has never measured them gets an explicit `[not measured]` line CARRYING
        #    ITS DENOMINATOR, not silence; and asking for that plane alone refuses (exit 2) rather
        #    than passing on an empty population. Both are the absence-as-completeness defect.
        semiplane = base / "semiplane"
        _seed(semiplane)
        (semiplane / "data" / "datasets").mkdir(parents=True, exist_ok=True)
        for stem in ("v_one", "v_two"):
            (semiplane / "data" / "datasets" / f"{stem}.yaml").write_text(yaml.safe_dump(
                {"of": stem, "table": {"name": stem, "schema": "own_schema"},
                 "columns": [{"name": "K", "role": "primary_key"}]}), encoding="utf-8")
        rc, out = _run(semiplane)
        case("MUTANT a declared-but-unmeasured plane is reported with its denominator, not silence",
             rc == 0 and "[not measured] plane served: 0 of 2" in out
             and "1 of 2 physical plane(s) measured" in out,
             f"exit {rc}: {out.strip()[-300:]}")
        rc, out = _run(semiplane, "--plane", "served")
        case("MUTANT --plane on an unmeasured plane refuses (exit 2), not PASS",
             rc == D.EMPTY_EXIT and D.empty_mark("references file") in out,
             f"exit {rc}: {out.strip()[-200:]}")

        ok_json = True
        for root_ in (base / "clean", base / "unresolved", bare, noplane, semiplane):
            _rc, out = _run(root_, "--json")
            try:
                json.loads(out)
            except Exception:                                                   # noqa: BLE001
                ok_json = False
        case("NEGATIVE CONTROL --json parses on every state, outage included", ok_json)

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mut = len([c for c in cases if c.startswith("MUTANT")])
    neg = len([c for c in cases if "NEGATIVE CONTROL" in c])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mut} mutant(s), one per reject class "
          f"(unresolved endpoint, undeclared column, colliding ids, a join as a string, an endpoint "
          f"keyed by concept, a verdict with no denominator, no admission block, two disagreeing "
          f"admission blocks, no participation, a cardinality and a participation outside their "
          f"closed sets, a dangling entry that acquired a parent, a dangling entry with no basis, "
          f"a hidden ambiguity, a profiled relation with no file, no source descriptors, no "
          f"references plane, a root that is not a directory, a declared-but-unmeasured plane "
          f"passing in silence, --plane on an unmeasured plane) and {neg} negative control(s) (a "
          f"clean family, both denominators on the verdict line, a DECLARED ambiguity, --json on "
          f"every state)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
