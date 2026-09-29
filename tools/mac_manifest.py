#!/usr/bin/env python3
"""mac_manifest.py — THE DELIVERY CENSUS, and the skeleton it generates.

WHY IT GENERATES RATHER THAN ASKS ME TO TYPE. Operator, 2026-09-29, after the fifth re-ingest of one
bundle in a day, each of which lost a different deliverable:

    "every new time you have managed to forget someting ... this is maximal unreliability and it is
     unacceptable ... you need enumerated list of items that need to be delivererd"

A list I write from memory reproduces the memory. Measured on contoso5 that day: the bundle holds
45 artifact classes over 278 files; `mac_import.CHECKLISTS` enumerated 14 of them and reported
`6 of 6` and `9 of 9` complete. The list must therefore be DERIVED from what the estate already
declares and from what a delivered bundle actually contains — so that a class I have never thought
about is still in it.

THE FOUR SOURCES, unioned. None is authoritative alone, and where they disagree the disagreement is
carried into the skeleton rather than resolved silently:

  1. `mac_resources.DERIVED | AUTHORED | NOT_DECLARED | PLANES` — 48 globs with their producers
  2. `mac_import._stages()` — every stage's `produces` and its `part` (the PHASE)
  3. the DISK of one or more delivered bundles — the only source that knows about a class the
     framework writes but never declared (measured: `data/lookups/*.lookup.md`, 48 files, in no
     registry and checked by nothing)
  4. `mac_artifacts.yaml` itself — the 12 kinds already declared, which are PRESERVED verbatim

WHAT IT REFUSES TO INVENT. `consumers`, `checkers` and `lifecycle` are judgement, not measurement:
who READS an artifact cannot be derived from the fact that something writes it. The skeleton emits
them as explicit `TODO`, and `check_artifact_conformance` treats a `TODO` as a VIOLATION — so an
undeclared consumer is a failing delivery, never a quiet default.

    python3 mac_manifest.py --census <bundle>...     what exists, and which sources name it
    python3 mac_manifest.py --skeleton <bundle>...   the kinds not yet declared, as YAML
    python3 mac_manifest.py --self-test
"""

from __future__ import annotations

import argparse
import fnmatch
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
_REPO = str(pathlib.Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

#: THE PHASE VOCABULARY — operator ruling 2026-09-29, all four declared from the start. `tuning` is
#: manual and will likely hold no automated kind; declaring it costs nothing and keeps the fourth
#: delivery from being invisible the way the third was. `both` is not a phase, it is "every phase",
#: and it is kept because `_stages()` already speaks it.
PHASES = ("sources", "datasets", "ontology", "tuning")

#: A file whose path matches one of these is not a delivered artifact and is not censused. Each
#: carries its reason: an input the delivery consumes, or a working file of the engine itself.
NOT_DELIVERED = (
    ("*.duckdb", "the warehouse itself — built by the bundle's own build.sh from its landings"),
    ("data/*.parquet", "the landing bytes — pre-delivery input, not something the import writes"),
    ("build.sh", "the bundle's own warehouse builder — authored input"),
    ("connection.yaml", "authored input; the connector seam reads it"),
    ("mac.project.yaml", "authored input; the manifest the delivery is performed against"),
    ("**/.DS_Store", "operating-system noise"),
    ("**/__pycache__/**", "interpreter cache"),
    ("**/.*", "dotfiles"),
)


#: THE DIRECTORIES A DELIVERY WRITES INTO. A class outside them is BUNDLE-LOCAL — a bundle's own
#: build script, mockup, scratch query or site archive — and is reported with that reason rather
#: than dropped, because "not mine" and "I did not look" must stay distinguishable. Measured on
#: mac-ontology-contoso: `mockup/`, `queries/`, `tools/`, `ask.py`, `site.zip` are all its own.
DELIVERY_PLANES = ("data", "acceptance", "ontology", "references", "governance", "knowledge",
                   "interventions", "evidence", "decisions", "runtime", "documentation")

#: Root-level files a delivery writes. Anything else at the root is bundle-local.
ROOT_DELIVERED = ("objects.json", "index.md", "compile.json", "{stem}.mac")

#: Directory segments that are a POPULATION, not a name. `ontology/concepts/catalog/x.yaml` and
#: `ontology/concepts/finance/x.yaml` are one class over a group axis, not two classes — collapsing
#: them is the difference between a census of 380 rows and one a person can actually rule on.
GROUPED_UNDER = {"ontology/concepts": "{group}"}


def _delivered(cls: str) -> tuple[bool, str]:
    top = cls.split("/")[0]
    if "/" not in cls:
        return (cls in ROOT_DELIVERED, "" if cls in ROOT_DELIVERED
                else "a root file no delivery writes — bundle-local")
    if top in DELIVERY_PLANES:
        return True, ""
    return False, f"outside every delivery plane ({top}/) — bundle-local"


def _segments(rel: str) -> str:
    """One artifact CLASS from one file path — the pattern, not the instance.

    The class is what a naming rule can be written about. `data/sources/customer.yaml` and
    `data/sources/store.yaml` are one class; `data/quality/DQ-ORPHAN-ORDERS.md` and
    `data/quality/PLANE-HEALTH.md` are two, because one varies over a population and the other is a
    fixed name. Getting that split wrong in either direction is how a census either explodes into
    one class per file or collapses a real distinction.
    """
    p = pathlib.PurePosixPath(rel)
    d, base = str(p.parent), p.name
    for parent, token in GROUPED_UNDER.items():
        if d.startswith(parent + "/") and d.count("/") == parent.count("/") + 1:
            d = f"{parent}/{token}"
    for pat, lbl in (
        (r".+\.src\.sample\.csv$", "{relation}.src.sample.csv"),
        (r".+\.sample\.csv$", "{relation}.sample.csv"),
        (r".+\.lookup\.csv$", "{register}.lookup.csv"),
        (r".+\.lookup\.md$", "{register}.lookup.md"),
        (r".+\.run\.json$", "{stem}.run.json"),
        (r"^DQ-.+\.md$", "DQ-{id}.md"),
        (r"^NS-.+\.md$", "NS-{id}.md"),
        (r"^\d{8}T\d{6}Z-.+\.json$", "{utc}-{suite}.json"),
        (r".+\.why\.md$", "{relation}.why.md"),
    ):
        if re.match(pat, base):
            return f"{d}/{lbl}" if d != "." else lbl
    # a FIXED name is its own class; anything else varies over its directory's population
    fixed = {"index.md", "objects.json", "compile.json", "lineage.json",
             "data_quality_register.yaml", "dq_dashboard.json", "diagnostics.json",
             "PLANE-HEALTH.md", "SME-QUESTIONS.md", "0-issues-overview.md",
             "0-registers-overview.md", "suite_history.jsonl", "suite_history.json",
             "usage_guardrails.md", "vocabulary.json", "edges.yaml", "edges.json",
             "rules.yaml", "ontology_quality.json", "questions_dashboard.json",
             "expected_first_run.yaml", "sme_needs.json", "sme_threads.json",
             "impurity_resolution_map.yaml"}
    if base in fixed:
        return f"{d}/{base}" if d != "." else base
    ext = "".join(pathlib.PurePosixPath(base).suffixes[-1:]) or ""
    stem_token = "{stem}"
    return f"{d}/{stem_token}{ext}" if d != "." else f"{stem_token}{ext}"


def disk_classes(roots) -> dict:
    """{class -> {"files": n, "seen_in": [bundle,...]}} over one or more delivered bundles."""
    out: dict = {}
    for r in roots:
        root = pathlib.Path(r)
        label = root.name
        for f in sorted(root.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(root))
            # A DOT SEGMENT ANYWHERE is tooling, not delivery: `.git/` alone contributed 273 of 314
            # excluded classes and drowned the twelve that are a real finding. fnmatch on the whole
            # relative path does not catch a dot segment in the middle, so it is tested per segment.
            if any(seg.startswith(".") for seg in pathlib.PurePosixPath(rel).parts):
                continue
            if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(f.name, pat)
                   for pat, _why in NOT_DELIVERED):
                continue
            c = _segments(rel)
            e = out.setdefault(c, {"files": 0, "seen_in": []})
            e["files"] += 1
            if label not in e["seen_in"]:
                e["seen_in"].append(label)
    return out


def registry_globs() -> dict:
    """{glob -> {"origin","by","kind","reason"}} from mac_resources' four tables."""
    import mac_resources as R

    out: dict = {}
    for row in R.DERIVED:
        out[row["glob"]] = {"origin": "derived", "by": row.get("by"),
                            "kind": row.get("kind"), "producer": row.get("producer")}
    for row in R.AUTHORED:
        out.setdefault(row["glob"], {}).update(
            {"origin": "authored", "by": row.get("by"), "kind": row.get("kind"),
             "note": row.get("note")})
    for row in R.NOT_DECLARED:
        out.setdefault(row["glob"], {}).update(
            {"origin": "not-declared-by-design", "by": row.get("by"),
             "reason": row.get("reason")})
    for plane, glob, kind in R.PLANES:
        out.setdefault(glob, {}).update({"plane": plane, "kind": kind})
    return out


def stage_produces(root) -> dict:
    """{glob -> {"phase": set, "stages": [name,...], "always": bool}} from the importer's own table.

    THE PHASE COMES FROM HERE AND NOWHERE ELSE. A stage with no `part` is held by every part — the
    defect that lost lineage and then the whole DQ assessment — so an absent `part` is recorded as
    the empty set and surfaces in the skeleton as a hole, not as a default.
    """
    import mac_import as MI

    out: dict = {}
    for st in MI._stages(pathlib.Path(root)):
        prod = st.get("produces")
        if not prod:
            continue
        # A STAGE MAY WRITE SEVERAL CLASSES. `_present` already reads `produces` as a list with ALL
        # semantics ("MUTANT a stage writing two planes is NOT present when one is missing"), and
        # the projector writes fourteen — so the census reads it the same way rather than assuming
        # one glob per stage.
        for g in (prod if isinstance(prod, (list, tuple)) else [prod]):
            e = out.setdefault(g, {"phase": set(), "stages": [], "always": False, "by_stage": {}})
            part = st.get("part")
            if part == "both":
                e["phase"].update(("sources", "datasets"))
            elif part:
                e["phase"].add(part)
            if st["name"] not in e["stages"]:
                e["stages"].append(st["name"])
            # PER STAGE, NOT UNIONED. Two stages legitimately declare the same glob —
            # `descriptors-sources` measures the descriptor and `promote-sources` rewrites it — and
            # collapsing them to one `always` let the second one's flag excuse the first, which
            # went on resuming on a present file while the gate reported the kind clean. `always`
            # stays as the union for callers that want "is any writer re-deriving"; `by_stage` is
            # what a correctness question has to ask.
            e["by_stage"][st["name"]] = bool(st.get("always"))
            e["always"] = e["always"] or bool(st.get("always"))
    return out


def declared_kinds(framework) -> dict:
    import yaml

    f = pathlib.Path(framework) / "mac_artifacts.yaml"
    if not f.is_file():
        return {}
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("kinds") or {}


def _tokenless(pattern: str) -> str:
    """One `*` per segment, spanning every token in it — the SAME rule the name gate's selector
    uses. Substituting each `{token}` separately produced `*_*_*.lookup.csv` here and
    `*.lookup.csv` there, so a declared register kind did not claim the register class it owns and
    48 files reported as undeclared. One rule, one home."""
    segs = []
    for seg in str(pattern or "").split("/"):
        if "{" in seg and "}" in seg:
            seg = seg[: seg.index("{")] + "*" + seg[seg.rindex("}") + 1 :]
        segs.append(seg)
    return "/".join(segs)


def specificity(pattern: str) -> int:
    """How narrow a claim is — literal characters outside any wildcard. The estate's existing
    tie-break (`check_artifact_has_producer._registry_entries` resolves overlapping families the
    same way): `data/{plane}/index.md` beats `data/{plane}/{relation}.md` over `index.md`, because
    one names the file and the other names a population it happens to fall into."""
    return sum(len(part) for part in _tokenless(pattern).split("*"))


def _claims(pattern: str, cls: str) -> bool:
    """Does a declared `path` (or a registry glob) claim this disk class?"""
    for branch in str(pattern or "").split("|"):
        g = _tokenless(branch.strip())
        if fnmatch.fnmatch(cls, g) or fnmatch.fnmatch(_tokenless(cls), g):
            return True
    return False


def census(bundles, framework) -> list:
    """One row per artifact class, with every source that names it. The ENUMERATION CONTRACT: one
    item per subject, the reason on every exclusion, counts derived from the list."""
    disk = disk_classes(bundles)
    reg = registry_globs()
    stages = stage_produces(bundles[0]) if bundles else {}
    kinds = declared_kinds(framework)

    rows = []
    for cls, info in sorted(disk.items()):
        rkey = next((g for g in reg if _claims(g, cls)), None)
        skey = next((g for g in stages if _claims(g, cls)), None)
        dkey = next((n for n, k in kinds.items() if _claims(k.get("path"), cls)), None)
        st = stages.get(skey, {}) if skey else {}
        is_del, why = _delivered(cls)
        rows.append({
            "delivered": is_del,
            "why_not": why,
            "class": cls,
            "files": info["files"],
            "seen_in": info["seen_in"],
            "declared_kind": dkey,
            "registry": reg.get(rkey) if rkey else None,
            "registry_glob": rkey,
            "phase": sorted(st.get("phase") or []),
            "stages": st.get("stages") or [],
            "always": st.get("always", False),
        })
    return rows


def _fmt(rows) -> str:
    rows = [r for r in rows if r["delivered"]]
    w = max((len(r["class"]) for r in rows), default=10)
    out = [f"{'artifact class'.ljust(w)}  {'n':>4}  {'declared':10} {'origin':22} {'phase':18} stages"]
    out.append("-" * (w + 80))
    for r in rows:
        origin = (r["registry"] or {}).get("origin") or "—"
        out.append(f"{r['class'].ljust(w)}  {r['files']:>4}  "
                   f"{(r['declared_kind'] or '—'):10} {origin:22} "
                   f"{(','.join(r['phase']) or '— NONE —'):18} {','.join(r['stages']) or '—'}")
    return "\n".join(out)


def skeleton(rows) -> str:
    """YAML for every class no kind declares. Mechanical fields filled, judgement fields TODO."""
    undeclared = [r for r in rows if not r["declared_kind"]]
    if not undeclared:
        return "# every artifact class on disk is claimed by a declared kind.\n"
    out = ["# GENERATED by mac_manifest.py --skeleton — one entry per artifact class that no kind",
           "# claims today. The mechanical fields are MEASURED; the judgement fields are TODO and",
           "# `check_artifact_conformance` counts a TODO as a VIOLATION, so this cannot be merged",
           "# and forgotten. Fill them by reading, not by guessing.",
           ""]
    for r in undeclared:
        reg = r["registry"] or {}
        name = re.sub(r"[^a-z0-9]+", "_", r["class"].lower()).strip("_")
        out += [
            f"  {name}:",
            f"    what:      TODO   # one line: what this artifact IS, not where it lives",
            f"    phase:     {r['phase'] or 'TODO   # no stage declares a part — see PHASED'}",
            f"    path:      {r['class']}",
            f"    origin:    {reg.get('origin') or 'TODO'}",
            f"    lifecycle: TODO   # re-derived | resumable | authored-once",
            f"    producers:",
        ]
        by = reg.get("by")
        out.append(f"      - {{tool: {by}, role: TODO}}" if by
                   else "      - {tool: TODO, role: TODO}")
        out += [
            "    consumers: TODO   # [{tool, role, reads: [field,...]}] — who READS it, and which fields",
            "    checkers:  TODO   # [{tool, rejects: [class,...]}]",
            f"    # measured: {r['files']} file(s) in {', '.join(r['seen_in'])}"
            + (f"; stages {','.join(r['stages'])}" if r["stages"] else "; NO STAGE PRODUCES IT"),
            "",
        ]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundles", nargs="*", default=[])
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--skeleton", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--framework", default=_REPO)
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()
    if not a.bundles:
        print("REFUSED: name at least one delivered bundle — the census cannot be taken from the "
              "framework alone, because a class the framework writes but never declared is exactly "
              "what it exists to find.")
        return 2
    rows = census(a.bundles, a.framework)
    if a.skeleton:
        print(skeleton([r for r in rows if r["delivered"]]))
        return 0
    print(_fmt(rows))
    deliv = [r for r in rows if r["delivered"]]
    local = [r for r in rows if not r["delivered"]]
    n = len(deliv)
    dec = sum(1 for r in deliv if r["declared_kind"])
    nophase = sum(1 for r in deliv if not r["phase"])
    print(f"\n{n} DELIVERED artifact class(es) over {sum(r['files'] for r in deliv)} file(s)")
    print(f"  declared by a kind : {dec} of {n}")
    print(f"  carrying a phase   : {n - nophase} of {n}")
    print(f"\n{len(local)} bundle-local class(es) excluded, each with its reason:")
    import collections
    by_why = collections.defaultdict(list)
    for r in local:
        by_why[r["why_not"]].append(r["class"])
    for why, cls in sorted(by_why.items()):
        print(f"  {len(cls):>3}  {why}  e.g. {', '.join(sorted(cls)[:3])}")
    return 0


def _self_test() -> int:
    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    case("a per-relation descriptor collapses to one class",
         _segments("data/sources/customer.yaml") == "data/sources/{stem}.yaml")
    case("two relations are ONE class, not two",
         _segments("data/sources/store.yaml") == _segments("data/sources/customer.yaml"))
    case("a landed preview keeps its plane marker",
         _segments("data/samples/store.src.sample.csv") == "data/samples/{relation}.src.sample.csv")
    case("a served preview is a DIFFERENT class from a landed one",
         _segments("data/samples/dim_store.sample.csv")
         != _segments("data/samples/store.src.sample.csv"))
    case("a fixed name is its own class",
         _segments("data/quality/PLANE-HEALTH.md") == "data/quality/PLANE-HEALTH.md")
    case("a DQ page varies over its register",
         _segments("data/quality/DQ-ORPHAN-ORDERS.md") == "data/quality/DQ-{id}.md")
    case("a fixed name and a varying one in the SAME directory stay apart",
         _segments("data/quality/DQ-X.md") != _segments("data/quality/PLANE-HEALTH.md"))
    case("a register page is not a register",
         _segments("data/lookups/a_b_c.lookup.md") != _segments("data/lookups/a_b_c.lookup.csv"))
    case("a declared path claims its class",
         _claims("data/sources/{relation}.yaml", "data/sources/{stem}.yaml"))
    case("an alternation claims BOTH branches",
         _claims("data/references/{r}.yaml | data/references_served/{r}.yaml",
                 "data/references_served/{stem}.yaml"))
    case("MUTANT a path does NOT claim a class in another directory",
         not _claims("data/sources/{relation}.yaml", "data/datasets/{stem}.yaml"))
    case("concept GROUPS collapse to one class over a group axis",
         _segments("ontology/concepts/catalog/product.yaml")
         == _segments("ontology/concepts/finance/currency.yaml")
         == "ontology/concepts/{group}/{stem}.yaml")
    case("a delivery plane is delivered", _delivered("data/sources/{stem}.yaml")[0])
    case("MUTANT a bundle's own mockup is NOT delivered, and says why",
         not _delivered("mockup/{stem}.html")[0] and "bundle-local" in _delivered("mockup/{stem}.html")[1])
    case("MUTANT a root script is NOT delivered", not _delivered("{stem}.sh")[0])
    case("a root projection IS delivered", _delivered("objects.json")[0])
    case("MUTANT a csv path does NOT claim the md beside it",
         not _claims("data/lookups/{m}_{r}_{c}.lookup.csv", "data/lookups/{register}.lookup.md"))
    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": mac_manifest self-test — {ok[1]}/{ok[0]} case(s)")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE CHECKLIST, PROJECTED FROM THE MANIFEST
#
# It was fifteen hand-written lambdas, and that is how an entire deliverable went missing while the
# report read `6 of 6` and `9 of 9`: the data-quality assessment was in no item, so no item could be
# short. A hand-written list can only ever check what somebody remembered to write down, and the
# thing this whole change exists to fix is that I do not remember reliably.
#
# Derived from three declared fields and nothing else:
#   phase       which delivery owes the artifact          -> which checklist it appears on
#   path        where its files live                      -> what HAS been delivered
#   population  the set it must cover, and where counted  -> the DENOMINATOR
#
# `0 of 0` stays EMPTY and never complete, because that rule is the estate's and predates this file.
# ══════════════════════════════════════════════════════════════════════════════════════════════

#: Where a population phrase is counted, per plane. The manifest says `data/{plane}/*.yaml`; this is
#: the only place that knows `sources` and `datasets` are the two planes it can mean.
_PLANE_OF = {"sources": "sources", "datasets": "datasets"}

#: The population of a kind that is ONE artifact: itself. Spelled once so the projector can ask
#: "is this a single-file kind" without re-deriving the answer from the path.
_SELF = "«this artifact»"


def _plane_stems(root, plane) -> list:
    return sorted(p.stem for p in (pathlib.Path(root) / "data" / plane).glob("*.yaml"))


def _have_for(root, path_pattern: str, plane: str, stems: list) -> list:
    """Which of `stems` actually have this kind's file, for this plane."""
    out = []
    for branch in str(path_pattern or "").split("|"):
        b = branch.strip().replace("{plane}", plane)
        if "{" not in b:
            continue
        head, _, tail = b.partition("{")
        _tok, _, ext = tail.partition("}")
        for s in stems:
            f = pathlib.Path(root) / f"{head}{s}{ext}"
            if f.is_file() and s not in out:
                out.append(s)
    return sorted(out)


def _resolve_population(root, pop: dict, plane: str) -> tuple:
    """(want, reason-it-cannot-be-counted). The DENOMINATOR comes from `population.from` and from
    nowhere else — reading it off the path is how one kind silently borrows another's population."""
    root = pathlib.Path(root)
    frm = str(pop.get("from") or "").strip()
    if not frm:
        return [], "the kind declares no `population.from`, so its denominator is unstated"
    if frm.startswith("«"):
        # «none» — a kind that exists only where somebody chose to write one. Its honest
        # denominator is zero, and `empty_is: OK` is what distinguishes that from a shortfall.
        return ([] if "none" in frm else [_SELF]), ""
    if "#" in frm:
        where, _, sel = frm.partition("#")
        where = where.strip().replace("{plane}", plane)
        if where.startswith("mac_"):
            return ["«the framework's own declaration»"], ""
        f = root / where
        if not f.is_file():
            return [], f"{where} is not present, so {sel} cannot be counted"
        try:
            import yaml as _y
            doc = _y.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                                 # noqa: BLE001
            return [], f"{where} could not be read, so {sel} cannot be counted"
        key = sel.split("[")[0].split(".")[0]
        got = doc.get(key)
        if isinstance(got, list):
            return [str(i.get("id") if isinstance(i, dict) else i) for i in got], ""
        return [], f"{where} carries no `{key}` list, so {sel} cannot be counted"
    if "+" in frm:
        out = []
        for part_ in frm.split("+"):
            out += _plane_stems(root, part_.strip().split("/")[1]) if "/" in part_ else []
        return sorted(set(out)), ""
    if "{plane}" in frm or f"data/{plane}" in frm:
        return _plane_stems(root, plane), ""
    if frm.startswith("data/"):
        d = frm.split("/")[1]
        return _plane_stems(root, d), ""
    return [], f"`population.from: {frm}` names no countable set this projector understands"


def checklist(root, part: str, kinds: dict) -> list:
    """One item per declared kind that THIS delivery owes, with its measured (have, want).

    Three item shapes, derived from the declared `path` — not from a taxonomy invented here:
      * a `{relation}` token  -> one file per member of the population
      * a `{plane}` token only -> one file per plane that has any relation
      * no token at all        -> one file, present or not
    """
    root = pathlib.Path(root)
    items = []
    for name, k in sorted(kinds.items()):
        phases = k.get("phase") or []
        phases = phases if isinstance(phases, list) else [phases]
        if part not in phases and "both" not in phases:
            continue
        pop = k.get("population") or {}
        path = str(k.get("path") or "")
        plane = _PLANE_OF.get(part, part)
        want, why = _resolve_population(root, pop, plane)
        if why:
            # A POPULATION THIS CANNOT COUNT IS `n/a` WITH ITS REASON, never a silent number.
            # Defaulting to the plane's relations is what made `register` read `0 of 8` against a
            # bundle holding 48 registers cut from 24 columns: a denominator borrowed from another
            # kind is worse than none, because it looks like an answer.
            items.append({"id": name, "what": str(k.get("what") or name), "of": pop.get("of") or "—",
                          "where": path.replace("{plane}", plane), "have": [], "want": [],
                          "na": why, "empty_is": pop.get("empty_is") or "EMPTY"})
            continue
        # THE SHAPE OF THE WANT DECIDES, NOT THE SHAPE OF THE PATH. `register`'s path contains the
        # token `{relation}` inside `{marker}_{relation}_{column}`, so a path-first test sent it down
        # the one-file-per-relation branch and reported `0 of 1` over 48 delivered registers. What
        # makes a kind per-relation is that its POPULATION is relations — which is the thing the
        # manifest states outright.
        if want == [_SELF]:
            have = []
            for branch in path.split("|"):
                b = branch.strip().replace("{plane}", plane)
                hits = list(root.glob(_tokenless(b))) if "{" in b else \
                    ([root / b] if (root / b).is_file() else [])
                if any(h.is_file() for h in hits):
                    have = [_SELF]
                    break
        elif "{relation}" in path:
            have = _have_for(root, path, plane, want)
        elif "{plane}" in path:
            have = [plane] if (root / path.replace("{plane}", plane)).is_file() else []
        else:
            # A SINGLE-FILE KIND IS PRESENT IF ANY BRANCH OF ITS PATH MATCHES. `(root/path).is_file()`
            # answered False for every kind whose path carries an alternation or a token — the
            # register (48 files on disk) read `0 of 1`, and so did the reference run records and the
            # bundle's own resource description. A checklist that reports a delivered artifact absent
            # is worse than one that omits it: it sends somebody to look for what is already there.
            have = []
            for branch in path.split("|"):
                b = branch.strip().replace("{plane}", plane)
                hits = list(root.glob(_tokenless(b))) if "{" in b else \
                    ([root / b] if (root / b).is_file() else [])
                if any(h.is_file() for h in hits):
                    have = [path]
                    break
        items.append({
            "id": name,
            "what": str(k.get("what") or name),
            "of": pop.get("of") or "—",
            "where": path.replace("{plane}", plane),
            "have": have,
            "want": want,
            "empty_is": pop.get("empty_is") or "EMPTY",
        })
    return items
