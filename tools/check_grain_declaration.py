#!/usr/bin/env python3
"""MAC008 — the cell key DECLARATION must be well-formed, complete, and honest about its evidence.

The MEASURED key (data/profiles/<stem>.yaml#identity_evidence.key) states the columns at which
exactly one row of a fact relation exists. Five tools,
eight canon bindings and every generated concept view now read it. Its declaration in
mac.project.yaml#profile.extensions is RETIRED (x- prohibited, MAC012; MAC009 withdrawn)
check — and constrains nothing:

  · no shape        cell_key could be a string, a number, or []
  · not required    a fact relation carrying none violates nothing
  · no column tie   nothing required it to name columns the relation actually has
  · "VERIFIED"      the descriptions SAY they were checked against Athena; that is prose

All four holes produced real defects before this existed. A reach view declared
`excludes_vintage: true` and put the reporting cycle INSIDE its own key, so a collapse partitioned on
it would separate every cycle into its own group and collapse nothing at all — caught only when
protosql_render refused to render it. v_<source>_kpi.yaml still carries "VERIFIED 2026-08-16: <N>
cells, 0 multi-row" while the data now says close to a million figures are multi-row: the word VERIFIED is a
sentence, not a test, and it went stale the moment a second business status arrived.

WHAT THIS ENFORCES, all offline:
  1. SHAPE            cell_key is a non-empty list of unique, non-blank column names
  2. COLUMNS EXIST    every name appears in the dataset's own columns[]
  3. VINTAGE          excludes_vintage: true is CONSISTENT — the key holds no republication column
  4. REQUIRED         a relation any measure concept grounds on must declare one
  5. EVIDENCE         a description claiming VERIFIED must carry a date, and a claim older than the
                      last edit to the key is a stale claim, not evidence

(5) is the interesting one: it cannot prove the key is right — only a warehouse sweep does that, which
is what S-GRAIN is for. What it CAN prove is that the claim has not outlived the thing it describes.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
import mac_diag as D          # noqa: E402
import mac_project as P       # noqa: E402

from sdk import registers as _registers                                  # noqa: E402

# Columns that identify WHEN a figure was published rather than WHICH figure it is. A key containing
# one of these makes every republication its own group, so the collapse collapses nothing.
#
# THESE SEVEN ARE GENERIC AND STAY IN CODE. `reporting_month`, `reporting_cycle`, `vintage`,
# `snapshot`, `created_at`, `loaded_at`, `ingested_at` are warehouse column SHAPES: every estate that
# republishes a figure has some of them, under some of these names, and none of them names anybody's
# system, brand, market or KPI. Writing a shape down leaks nothing — and these MUST live in code,
# because the register below is gitignored, so a fresh clone and CI have these and nothing else.
#
# An eighth entry was NOT generic. `tools/check_mac_public.py` reported this line as one of the last
# four real leaks in this public repository (2026-09-17, rule `source-column`): a private source's
# own column name, sitting in a framework checker. It now comes from the estate register.
_GENERIC_CYCLE_HINTS = ("reporting_month", "reporting_cycle", "vintage", "snapshot",
                        "created_at", "loaded_at", "ingested_at")

_ESTATE_REGISTER = "estate_terms"
_ESTATE_GROUP = "vintage_column"


def _estate_cycle_hints() -> tuple:
    """This estate's own publication-cycle column names, or () when none are declared.

    Read at CALL time, never snapshot at import, so `$MAC_ESTATE_TERMS` works for CI and the
    self-test.
    """
    return tuple(sorted({h.strip().lower() for h in
                         _registers.group(_ESTATE_REGISTER, _ESTATE_GROUP) if h.strip()}))


def cycle_hints() -> tuple:
    return _GENERIC_CYCLE_HINTS + _estate_cycle_hints()


# ABSENT REGISTER: REDUCED SCOPE, DISCLOSED — NOT could-not-run. This is the one of the three
# consumers whose absent register can HIDE a finding rather than add one, so the decision is the
# closest of the three and the reasoning is recorded rather than left implicit:
#
#   FOR could-not-run (exit 2). Rule (3) is the only rule here that reads the register, and with no
#   estate columns declared a key built on a private republication column passes silently. A PASS
#   that cannot see the defect it was written for is the empty-population defect exactly.
#
#   AGAINST, and this is what was chosen. Four of this gate's five rules — shape, columns exist,
#   required, evidence-not-stale — never touch the register, and rule (3) keeps the seven generic
#   hints, which are a real floor and not a token gesture. Refusing to run would take four working
#   rules offline for a reason unrelated to any of them, and a gate that refuses on a fresh clone is
#   a gate that gets dropped from `run_gates.sh` rather than fixed. `check_mac_public` refuses in the
#   same situation because the token scan is the WHOLE of what it does; here it is one rule of five.
#
#   SO: it runs, and the verdict states the shortfall on BOTH paths — and the OK line drops the word
#   "complete", because "✓ OK — every declared cell key is well-formed and complete" quoted over a
#   vintage class that could not see this estate's own column is precisely the sentence this estate
#   keeps having to retract.


def _git(root: str, *a: str) -> str:
    try:
        return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return ""


def check(root: str) -> list[dict]:
    out: list[dict] = []
    # ONE read for the whole run, so every descriptor is judged against the same hint vocabulary.
    hints = cycle_hints()

    def bad(sev, where, msg, fix):
        out.append({"severity": sev, "where": where, "msg": msg, "fix": fix})

    # which relations a measure concept grounds on — those MUST declare a key
    needed: dict[str, str] = {}
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane
    # the project declares. Globbing flat found no measure concept on a foldered bundle, which
    # silently disabled rule (4): "a relation any measure concept grounds on must declare a key"
    # cannot fire when the set of measure concepts is empty by construction.
    for f in P.concept_files(root):
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        if ((d.get("concept") or {}).get("class")) != "measure":
            continue
        for s in ((d.get("grounding") or {}).get("sources") or []):
            rel = str(s.get("relation") or "")
            if rel:
                needed.setdefault(rel.split(".")[-1], os.path.basename(str(f))[:-5])

    seen = set()
    for f in sorted(glob.glob(os.path.join(root, "data", "datasets", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        rel = os.path.relpath(f, root)
        stem = os.path.basename(f)[:-5]
        seen.add(stem)
        grain = _measured(root, stem)
        cols = {c.get("name") for c in (doc.get("columns") or []) if isinstance(c, dict)}

        if grain is None:
            if stem in needed:
                bad("ERROR", rel,
                    f"no measured key, but concept:{needed[stem]} grounds a MEASURE on it",
                    "declare the columns at which exactly one row exists, and verify them")
            continue

        if not isinstance(grain, dict):
            bad("ERROR", rel, "identity_evidence is not a mapping", "it must carry key")
            continue

        key = grain.get("cell_key")
        # 1. SHAPE
        if not isinstance(key, list) or not key:
            bad("ERROR", f"{rel}#identity_evidence.key",
                f"is {type(key).__name__}, not a non-empty list", "give it the column tuple")
            continue
        if any(not isinstance(c, str) or not c.strip() for c in key):
            bad("ERROR", f"{rel}#identity_evidence.key", "holds a non-string or blank entry",
                "every entry is a column name")
        dupes = sorted({c for c in key if key.count(c) > 1})
        if dupes:
            bad("ERROR", f"{rel}#identity_evidence.key", f"repeats {dupes}",
                "a column cannot identify a figure twice")

        # 2. COLUMNS EXIST
        if cols:
            missing = [c for c in key if c not in cols]
            if missing:
                bad("ERROR", f"{rel}#identity_evidence.key",
                    f"names {missing}, which the relation does not have",
                    "a key over columns that do not exist partitions nothing")

        # 3. VINTAGE CONSISTENCY
        cyc = [c for c in key if any(h in str(c).lower() for h in hints)]
        if cyc:
            sev = "ERROR" if grain.get("excludes_vintage") else "WARNING"
            bad(sev, f"{rel}#identity_evidence.key",
                f"contains {cyc} — a column identifying WHEN the figure was published"
                + (" while excludes_vintage says it does not" if grain.get("excludes_vintage") else ""),
                "partition on it and every republication becomes its own group, so nothing collapses")

        # 5. EVIDENCE NOT STALE
        note = str(grain.get("note") or "") + " " + str(grain.get("description") or "")
        if re.search(r"\bVERIFIED\b", note, re.I):
            m = re.search(r"(20\d\d-\d\d-\d\d)", note)
            if not m:
                bad("WARNING", f"{rel}#x-grain",
                    "claims VERIFIED with no date", "an undated claim cannot be shown to be current")
            else:
                claimed = m.group(1)
                last = _git(root, "log", "-1", "--format=%cs", "--", rel)
                if last and last > claimed:
                    bad("WARNING", f"{rel}#x-grain",
                        f"claims VERIFIED {claimed} but the descriptor was edited {last}",
                        "re-verify against the warehouse, or drop the claim — a claim that has "
                        "outlived the thing it describes is not evidence")

    for stem, concept in sorted(needed.items()):
        if stem not in seen:
            bad("ERROR", f"data/datasets/{stem}.yaml",
                f"concept:{concept} grounds a measure on it and no descriptor exists",
                "every relation the ontology reads must be described")
    return out



def _measured(root, stem):
    """The relation's measured key, shaped like the block these gates used to read. ONE reader, so
    the two gates cannot disagree about where the key lives."""
    import pathlib as _pl
    p = _pl.Path(root) / "data" / "profiles" / f"{stem}.yaml"
    if not p.exists():
        return None
    d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("identity_evidence") or {}
    return {"cell_key": d.get("key"), "key": d.get("key")} if d.get("key") else None


def _measured_key(root, stem):
    m = _measured(root, stem)
    return (m or {}).get("key") or []

def vocabulary_line() -> str:
    """The vintage class's own denominator, on EVERY run. See the decision note above."""
    est = _estate_cycle_hints()
    if est:
        return (f"  vintage hints: {len(_GENERIC_CYCLE_HINTS)} generic + {len(est)} estate "
                f"column(s) declared — rule (3) is at full scope")
    return (f"  vintage hints: {len(_GENERIC_CYCLE_HINTS)} generic + 0 estate column(s) "
            f"({_registers.disclosed_path(_ESTATE_REGISTER)} absent or empty) — REDUCED SCOPE: "
            "rule (3) cannot see THIS estate's own republication columns, so a cell key built on "
            "one passes here. Copy registers/estate_terms.example.txt, or set $MAC_ESTATE_TERMS.")


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    # ZERO IS NOT A SCORE. This gate reads TWO populations — the concepts that make a key REQUIRED,
    # and the dataset descriptors that declare one. An empty one used to print a tick.
    nc = len(P.concept_files(a.root))
    nd = len(glob.glob(os.path.join(a.root, "data", "datasets", "*.yaml")))
    f = check(a.root) if (nc and nd) else []
    if a.json:
        # THE VINTAGE CLASS'S DENOMINATOR TRAVELS WITH THE FINDINGS. A machine reader of this JSON
        # gets the same disclosure the human gets on the verdict line — counts only, never the
        # estate's column names, because this output is pasted into reports and issue trackers.
        print(json.dumps({"findings": f, "concepts": nc, "datasets": nd,
                          "measured_nothing": not (nc and nd),
                          "vintage_hints_generic": len(_GENERIC_CYCLE_HINTS),
                          "vintage_hints_estate": len(_estate_cycle_hints()),
                          "vintage_scope": "full" if _estate_cycle_hints() else "reduced",
                          "vintage_register": _registers.disclosed_path(_ESTATE_REGISTER)},
                         indent=1, ensure_ascii=False))
        return D.EMPTY_EXIT if not (nc and nd) else (
            1 if any(x["severity"] == "ERROR" for x in f) else 0)
    if not nc:
        return D.refuse_empty("check_grain_declaration", P.concepts_dir(a.root))
    if not nd:
        return D.refuse_empty("check_grain_declaration", os.path.join(a.root, "data", "datasets"),
                              unit="dataset descriptor")

    for x in f:
        print(f"  [{x['severity']:<7}] {x['where']}")
        print(f"            {x['msg']}")
        print(f"            {x['fix']}")
    errs = sum(1 for x in f if x["severity"] == "ERROR")
    warns = len(f) - errs
    if errs:
        print(f"\n✗ {errs} malformed cell-key declaration(s) ({warns} warning(s)) — five tools, eight "
              f"canon bindings and every generated view read this")
        print(vocabulary_line())
        return 1
    # THE WORD "complete" IS CONDITIONAL. It was unconditional, and an unqualified "complete" quoted
    # over a vintage class that could not see this estate's own republication columns is the
    # zero-denominator PASS in its purest form: the sentence is true of the four rules that ran at
    # full scope and false of the fifth, and nothing on the line let a reader tell which.
    if _estate_cycle_hints():
        print(f"✓ OK — every declared cell key is well-formed and complete ({warns} warning(s))")
    else:
        print(f"✓ OK on what could be checked — every declared cell key is well-formed, and the "
              f"vintage class ran at REDUCED SCOPE ({warns} warning(s))")
    print(vocabulary_line())
    return 0


# -------------------------------------------------------------------------------------------------
# self-test: a seeded mutant per reject class, routed through the shared harness (which asserts
# exit 1 AND that the rejection is ATTRIBUTED to the class it was seeded for), plus the
# register-absent path, which the harness cannot express because its honest outcome is exit 0.
#
# Every token is SYNTHETIC (`zz...`). The estate register is gitignored, so a fresh checkout declares
# none: a self-test reading the real one would exercise the estate-column class against an empty list
# and pass having checked nothing — the defect this whole change is about.
# -------------------------------------------------------------------------------------------------

_SYN_ESTATE_COL = "zzcycle_col"
_SYN_GENERIC_COL = "zzsnapshot_col"          # contains the GENERIC hint `snapshot`

_MEASURE_CONCEPT = """concept:
  name: Gadget
  label: Gadget
  class: measure
  semantics:
    unit: widgets
grounding:
  sources:
    - relation: zzsch.gadget_fact
      key: gadget_code
      columns: [gadget_code, period_code, amount]
"""

_DESCRIPTOR_COLS = ["gadget_code", "period_code", "amount",
                    _SYN_GENERIC_COL, _SYN_ESTATE_COL]


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _descriptor(cols=None) -> str:
    cols = _DESCRIPTOR_COLS if cols is None else cols
    return "columns:\n" + "".join(f"  - name: {c}\n" for c in cols)


def _profile(key, *, excludes_vintage=None) -> str:
    body = "identity_evidence:\n"
    if isinstance(key, str):
        body += f"  key: {key}\n"
    else:
        body += "  key: [" + ", ".join('""' if k == "" else str(k) for k in key) + "]\n"
    if excludes_vintage is not None:
        body += f"  excludes_vintage: {str(bool(excludes_vintage)).lower()}\n"
    return body


def _subject(root) -> None:
    """The gate's own rule needs a POPULATION: a measure concept, a descriptor, a measured key.

    Without this the shared fixture seeds one REFERENCE concept and no descriptor, so `needed` is
    empty, the descriptor loop never runs, and the gate prints a tick over zero cell keys — the
    false green `selftest_discovery`'s own docstring was written about.
    """
    _write(os.path.join(str(P.concepts_dir(root)), "gadget.yaml"), _MEASURE_CONCEPT)
    _write(os.path.join(str(root), "data", "datasets", "gadget_fact.yaml"), _descriptor())
    _write(os.path.join(str(root), "data", "datasets", "other_fact.yaml"), _descriptor())
    _write(os.path.join(str(root), "data", "profiles", "gadget_fact.yaml"),
           _profile(["gadget_code", "period_code"]))


def _reprofile(root, key, **kw):
    _write(os.path.join(str(root), "data", "profiles", "gadget_fact.yaml"), _profile(key, **kw))


_MUTANTS = (
    ("shape-not-a-list", lambda r: _reprofile(r, "gadget_code"),
     "not a non-empty list",
     "cell_key is a bare string — it could be a string, a number or [] and nothing looked"),
    ("column-absent", lambda r: _reprofile(r, ["gadget_code", "zzmissing_col"]),
     "which the relation does not have",
     "a key over a column the relation has not got partitions nothing"),
    ("repeated-column", lambda r: _reprofile(r, ["gadget_code", "gadget_code"]),
     "repeats",
     "a column cannot identify a figure twice"),
    ("blank-entry", lambda r: _reprofile(r, ["gadget_code", ""]),
     "holds a non-string or blank entry",
     "a blank entry is not a column name"),
    ("key-required", lambda r: os.remove(
        os.path.join(str(r), "data", "profiles", "gadget_fact.yaml")),
     "grounds a MEASURE on it",
     "a relation a measure concept grounds on must declare a key"),
    # A SECOND DESCRIPTOR IS WHY `_subject` SEEDS ONE. Deleting the only descriptor drops `nd` to 0
    # and the gate REFUSES (exit 2) on an empty descriptor population — correct behaviour, and not
    # this class. With another descriptor present the population is real and the missing one is a
    # FINDING, which is what this mutant is for.
    ("descriptor-missing", lambda r: os.remove(
        os.path.join(str(r), "data", "datasets", "gadget_fact.yaml")),
     "no descriptor exists",
     "every relation the ontology reads must be described"),
)

# THE VINTAGE CLASS IS NOT IN `_MUTANTS`, and the reason is a defect this change deliberately does
# NOT fix. `_measured()` rebuilds the profile block as `{"cell_key": ..., "key": ...}` and drops
# `excludes_vintage` (and `note`/`description`) on the floor, so rule (3)'s ERROR branch — and the
# whole of rule (5) — can never fire: a cycle column in a key is always only a WARNING, and the gate
# exits 0. `selftest_discovery`'s mutant slot asserts exit 1, so routing the vintage class through it
# would fail for a reason that has nothing to do with the register.
#
# It is asserted below instead, on the WARNING it actually emits — which still proves the exact
# property this change is about: the column is SEEN with the register and INVISIBLE without it. The
# dead ERROR branch is reported to the operator as a separate finding rather than repaired here,
# because repairing it would change the findings on the private bundle, and this change is required
# to leave them identical.
_VINTAGE_NOTE = ("rule (3) emits a WARNING, never the ERROR its own code writes: _measured() drops "
                 "excludes_vintage (and note/description, which kills rule (5) outright)")


def _self_test() -> int:
    import subprocess
    import tempfile

    env_name = _registers.REGISTERS[_ESTATE_REGISTER][1]
    saved = os.environ.get(env_name)
    failures, checks = [], 0

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        try:
            reg = os.path.join(tmp, "estate_terms.txt")
            _write(reg, f"{_ESTATE_GROUP} | {_SYN_ESTATE_COL}\n")

            # ── THE REGISTER-ABSENT PATH ───────────────────────────────────────────────────────
            # One bundle, one key built on THIS ESTATE's republication column, run twice. With the
            # register it is an ERROR; without it, it passes — and the verdict must say so, in those
            # words, rather than printing the same tick as a clean bundle.
            bundle = os.path.join(tmp, "bundle")
            os.makedirs(os.path.join(bundle, "concepts"))
            _write(os.path.join(bundle, "concepts", "gadget.yaml"), _MEASURE_CONCEPT)
            _write(os.path.join(bundle, "data", "datasets", "gadget_fact.yaml"), _descriptor())
            _write(os.path.join(bundle, "data", "profiles", "gadget_fact.yaml"),
                   _profile(["gadget_code", _SYN_ESTATE_COL], excludes_vintage=True))

            def run(register):
                env = dict(os.environ)
                env[env_name] = register or os.path.join(tmp, "nowhere", "estate_terms.txt")
                p = subprocess.run([sys.executable, os.path.abspath(__file__), bundle],
                                   capture_output=True, text=True, timeout=300, env=env)
                return p.returncode, (p.stdout or "") + (p.stderr or "")

            _rc_with, out_with = run(reg)
            _rc_without, out_without = run(None)

            expect(_SYN_ESTATE_COL in out_with and "identifying WHEN the figure was published"
                   in out_with,
                   f"mutant not caught WITH the register: this estate's republication column sat "
                   f"in a cell key and went unreported: {out_with!r}")
            expect(_SYN_ESTATE_COL not in out_without,
                   "the no-register run still flagged the estate column — the register is not what "
                   "drives this class, so nothing here proves it moved out of the code")
            expect("REDUCED SCOPE" in out_without,
                   "mutant not caught: with no register the gate passed a key built on this "
                   "estate's republication column and did NOT say its scope was reduced")
            expect("and complete" not in out_without,
                   "the absent-register PASS still calls the declaration 'complete' — the exact "
                   "sentence a reduced scope makes false")

            # ── THE GENERIC FLOOR TRAVELS WITH THE CLONE ──────────────────────────────────────
            # The seven generic hints are in code precisely so a checkout with no register still
            # catches the common shape. If they had gone into the register too, this fails.
            _write(os.path.join(bundle, "data", "profiles", "gadget_fact.yaml"),
                   _profile(["gadget_code", _SYN_GENERIC_COL]))
            expect(_SYN_GENERIC_COL in run(None)[1],
                   "a GENERIC publication-cycle column shape went unreported with no register — "
                   "the floor that must survive a fresh clone is gone")

            # THE DISCLOSURE MUST DISCRIMINATE. A clean bundle WITH the register must NOT carry the
            # reduced-scope wording, or the wording fires on everything and attributes nothing.
            _write(os.path.join(bundle, "data", "profiles", "gadget_fact.yaml"),
                   _profile(["gadget_code", "period_code"]))
            rc_clean, out_clean = run(reg)
            expect(rc_clean == 0 and "REDUCED SCOPE" not in out_clean
                   and "and complete" in out_clean,
                   f"a clean bundle with the register present does not read as complete: "
                   f"exit {rc_clean}, {out_clean!r}")
            expect("1 estate column(s) declared" in out_clean,
                   f"the healthy verdict line omits its denominator: {out_clean!r}")

            # An EMPTY register, and the term filed under ANOTHER group, are both "absent".
            empty = os.path.join(tmp, "empty.txt")
            _write(empty, "# nothing declared\n")
            expect("REDUCED SCOPE" in run(empty)[1],
                   "an EMPTY register was treated as a declared vocabulary")
            wrong = os.path.join(tmp, "wrong.txt")
            _write(wrong, f"kpi_surface_stem | {_SYN_ESTATE_COL}\n")
            expect("REDUCED SCOPE" in run(wrong)[1],
                   "a column declared under another group leaked into the vintage class")

            # ── the eight reject classes, through the shared harness ───────────────────────────
            # The register is declared for these: the `vintage-estate` mutant is the one that needs
            # it, and the other seven must reject with it present too.
            os.environ[env_name] = reg
            harness = P.selftest_discovery(__file__, subject=_subject, mutants=_MUTANTS)
        finally:
            if saved is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = saved

    if failures:
        print(f"FAIL: check_grain_declaration self-test — {len(failures)} failure(s) over {checks} "
              f"register check(s)")
        for f in failures:
            if f:
                print(f"  {f}")
        return 1
    print(f"PASS: check_grain_declaration self-test — {checks}/{checks} check(s) on the vintage "
          f"class (estate register present / absent / empty / wrong-group, and the generic floor "
          f"with no register), each with its own disclosure")
    print(f"  KNOWN, NOT FIXED HERE: {_VINTAGE_NOTE}")
    return harness


if __name__ == "__main__":
    raise SystemExit(main())
