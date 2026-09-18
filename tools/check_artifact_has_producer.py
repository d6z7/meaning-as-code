#!/usr/bin/env python3
"""check_artifact_has_producer — every artifact family on disk must have a producer that declares it.

WHY THIS EXISTS
---------------
Twice in one day an artifact family turned out to be written by nothing the estate declares.

  * `data/samples`. The data-plane doc said it outright: "no tool in meaning-as-code/tools writes
    data/samples, and mac.project.yaml's reproduction.stages[].produces never lists it ... an agent
    runs SELECT * FROM <relation> LIMIT 20 and dumps the CSV by hand", and "nothing checks this — and
    it has already rotted". MEASURED: 3 of 25 headers stale, one short by ten of twenty-two columns,
    and a decision record citing that stale file as proof.
  * `data/references` + `data/references_served`. Built as a tool and a gate and NOTHING ELSE — no
    declared stage, no skill, no rung. Its 28 measured references existed only because somebody ran
    the tool by hand.

Both are the same shape: an artifact family the plane declares must have a producer that declares it
back. And the gate that looks closest — check_reproduction.py — is STRUCTURALLY BLIND to it, which is
not a guess: it prints `PASS: check_reproduction — 0 defect(s) over 2 stage(s)` on a bundle carrying
19 families no stage claims to produce. Its population is STAGES and it runs record -> disk; this
one's population is FILES and it runs disk -> record. That direction caught nothing all day because
nothing looked in it.

WHAT IT REFUSES TO DO, and why
------------------------------
R1 AS FIRST STATED ("every family the plane DOC declares is named in some stage's produces") WAS
REJECTED, with measurements, in three ways:

  * WRONG DIRECTION. Run doc -> manifest it goes red on 25 of 30 families in one bundle and 29 of 40
    in another — 54 findings across two bundles that are both committed, clean and green. A rule
    whose debut is a 54-row debt dump gets suppressed, not obeyed. 42 of those 54 are ONE producer
    (the projector) counted 42 times.
  * WRONG AUTHORITY. The plane doc's own `Produced by.` vocabulary has two members; the pair
    `Origin: derived` + `Produced by: tool` matches exactly TWO of its fourteen family sections, and
    they are the two families already fixed. Worse, `data/references` had no doc section at all at
    the moment it went wrong — so a doc-sourced population inherits the exact omission it exists to
    catch. The producer map therefore comes from CODE (`mac_resources.DERIVED` + `AUTHORED` +
    `NOT_DECLARED` + `PLANES`), which breaks loudly, and the doc is not read at all.
  * WRONG GRANULARITY for the projector. `harvest --mode project` writes 17+ families in one run.
    Demanding 17 `produces` patterns is ceremony nobody intends. So the projector is judged as ONE
    producer with one entrypoint question, not once per family.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate cases that must not fire
-------------------------------------------------------------------------
* A BUNDLE MID-INGESTION. check_reproduction's docstring already ruled on this: "a partially-run
  stage is a real finding, an unrun one is not". This gate never asks "is there a stage"; it asks
  "does any DECLARED COMMAND ANYWHERE in `reproduction` reach the registered producer" — and that
  is `stages[].command` UNION `pipelines.*.entry` UNION `reproduction.gate.command`. MEASURED: one
  committed clean bundle declares NO stage with id `projection` and yet names the producing command
  one key over, at `reproduction.pipelines.data.entry` (`--mode onboard --accept`), because
  sdk/cli/harvest.py:1230 ends the onboard flow with `project_source(...)`. A gate reading only
  `stages[].command` would print ERROR on that bundle and demand a `projection` stage that was never
  run — making the record LESS true than the silence it replaced. It goes green here, truthfully.
* A PROJECTION OLDER THAN ITS SOURCE. Not this gate's question at all. Freshness was rejected as a
  rule on measurement (a projection legitimately predates a source mid-authoring; `--project-anyway`
  exists to take one deliberately); the surface-disclosure half lives in check_projection_disclosure.
* A BUNDLE'S OWN LOCAL FAMILIES. A bundle may carry a family the framework has never heard of. It
  declares the origin itself, in its own manifest under `artifact_families:` (same entry shape), and
  the framework registry is not the only authority. That is the remedy for UNREGISTERED_FAMILY, and
  it is two lines.
* PROSE AND LANDING DATA inside a plane. `ontology/*.md` (a bundle documenting itself) and
  `*.parquet` (the bytes a connector reads) are registered as AUTHORED, so they are counted and not
  accused.

REJECT CLASSES
--------------
  UNREGISTERED_FAMILY        error    a family present under a DECLARED PLANE that no registry entry
                                      describes at all — framework or bundle-local. This is B1 as it
                                      actually happened: samples rotted because NOTHING, doc or code,
                                      named its producer. Remedy: one registry line, either here or
                                      in the bundle's own manifest.
  UNREACHED_PRODUCER         error    a registered DERIVED family is on disk and no declared command
                                      in `reproduction` reaches its producer. Nothing tells the next
                                      operator the command exists, so the file rots unnoticed.
  PARTIAL_PRODUCES_COVERAGE  warning  a stage DOES name this family in `produces`, and its patterns
                                      cover fewer files than the family holds — a literal path
                                      declares that one file, not its sixteen neighbours. Warning,
                                      not error: the producing command is named, so the family is
                                      reproducible; what is under-stated is the record's reach.
  STAMP_UNKNOWN_WRITER       warning  the files' own `metadata.generated_by` names a writer no
                                      registered producer knows. Either the registry is behind the
                                      tool or the artifact was written by something else.

DENOMINATORS, AND WHY THERE ARE FOUR
------------------------------------
The PASS line prints the FULL on-disk family census and what was NOT judged, following
validate_schema:575 — "the denominator is fixed by the enumeration and cannot be moved". A green line
that does not say how many families it did not judge will be read as "this bundle's artifacts have
declared producers", which is false in both real bundles.

    exit 0 = every judged family has a producer that declares it · 1 = one does not · 2 = could not run
"""
from __future__ import annotations

import argparse
import glob as _glob
import os
import sys

NAME = "check_artifact_has_producer"

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# SKIPPED: not artifacts of any plane. `.harvest_cache`/`.harvest_manifest.yaml` are the declared
# gitignored sidecars (harvest.py's write_harvest_manifest says so in full).
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache",
              ".harvest_cache", ".claude", "build", "dist", ".ruff_cache", ".mypy_cache"}

ERROR, WARNING = "error", "warning"


# ── the registry ────────────────────────────────────────────────────────────────────────────────
def load_registry():
    """The producer map, FROM CODE. Raises ImportError — an unreachable registry is exit 2, never a
    PASS: `not computed` and `clean` are opposite facts (compile_gate's own wording)."""
    import mac_resources as R
    return R


def _bundle_families(manifest) -> tuple:
    """A bundle's OWN registry entries, from `mac.project.yaml#artifact_families`.

    Precedent: `conformance.out_of_scope` is already a bundle-local declaration a framework gate
    (validate_schema) reads. A family only this bundle has is only this bundle's to explain."""
    ents = manifest.get("artifact_families")
    if not isinstance(ents, list):
        return ()
    out = []
    for e in ents:
        if isinstance(e, dict) and e.get("glob"):
            out.append(dict(e))
    return tuple(out)


def _specificity(pattern: str) -> int:
    """How specific a glob is: non-wildcard characters. `data/transforms/*.why.md` must beat the
    generic `data/**/*.md` read-view glob, or a hand-authored rationale page is called a projection."""
    return sum(1 for c in pattern if c not in "*?[]")


def _registry_entries(R, manifest) -> list:
    """Every entry, tagged with its ORIGIN class. Order is irrelevant: specificity decides."""
    ents = []
    for d in R.DERIVED:
        ents.append({**d, "_origin": "derived"})
    for d in R.AUTHORED:
        ents.append({**d, "_origin": "authored"})
    for d in R.NOT_DECLARED:
        ents.append({**d, "_origin": "not-declared-by-design"})
    for plane, pattern, kind in R.PLANES:
        ents.append({"glob": pattern, "kind": kind, "plane": plane, "_origin": "authored",
                     "by": "hand or a declared authoring stage", "_from": "PLANES"})
    for d in _bundle_families(manifest):
        o = str(d.get("origin") or "authored")
        ents.append({**d, "_origin": o if o in ("derived", "authored", "not-declared-by-design")
                     else "authored", "_bundle_local": True})
    return ents


# ── enumeration ─────────────────────────────────────────────────────────────────────────────────
def _files(root: str) -> list:
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in _SKIP_DIRS and not d.startswith("."))
        rel_dir = os.path.relpath(dp, root).replace(os.sep, "/")
        for f in sorted(fn):
            if f.startswith("."):
                continue
            out.append(f if rel_dir == "." else f"{rel_dir}/{f}")
    return out


def _family_of(rel: str) -> tuple:
    d = os.path.dirname(rel) or "."
    ext = os.path.splitext(rel)[1] or "<no-extension>"
    return (d, ext)


def _plane_prefixes(manifest) -> list:
    """The directories this bundle DECLARES as planes. A family outside all of them is counted and
    printed, never accused: a bundle's scratch, docs and evidence are its own business."""
    pres = []
    planes = manifest.get("planes")
    if isinstance(planes, dict):
        pres += [str(v) for v in planes.values() if isinstance(v, str)]
    for key in ("descriptors", "transforms", "sources", "lookups", "profiles", "samples"):
        v = manifest.get(key)
        if isinstance(v, str):
            pres.append(v)
    seen, out = set(), []
    for p in pres:
        p = p.strip("/").replace(os.sep, "/")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _in_plane(fam_dir: str, prefixes: list) -> bool:
    return any(fam_dir == p or fam_dir.startswith(p + "/") for p in prefixes)


# ── the reproduction record ─────────────────────────────────────────────────────────────────────
def declared_commands(manifest) -> list:
    """EVERY declared command in the reproduction record, not just `stages[].command`.

    `pipelines.*.entry` is where one real bundle names the command that writes its projector output;
    a gate that read only `stages[]` would call that bundle undeclared. `reproduction.gate.command`
    is included for the same reason: it is a declared way to run something."""
    repro = manifest.get("reproduction") or {}
    cmds = []
    for st in (repro.get("stages") or []):
        if isinstance(st, dict) and st.get("command"):
            cmds.append((f"stages[{st.get('id')}].command", str(st["command"])))
    pipes = repro.get("pipelines")
    if isinstance(pipes, dict):
        for pid, p in pipes.items():
            if isinstance(p, dict) and p.get("entry"):
                cmds.append((f"pipelines.{pid}.entry", str(p["entry"])))
    g = repro.get("gate")
    if isinstance(g, dict) and g.get("command"):
        cmds.append(("gate.command", str(g["command"])))
    return cmds


def _reaches(producer: str, R, cmds: list):
    """Which declared command reaches this producer, resolved through the registry's entrypoints
    rather than by string-matching one spelling of one mode flag."""
    spec = (R.PRODUCERS or {}).get(producer) or {}
    for ep in spec.get("entrypoints") or ():
        for where, cmd in cmds:
            if ep in cmd:
                return where, cmd, ep
    return None


def _stamp_writers(root: str, rels: list) -> set:
    """`metadata.generated_by` as the ARTIFACTS state it. Read from at most three files per family:
    the question is which writer the family claims, not a per-file audit."""
    out = set()
    try:
        import yaml
    except ImportError:                                            # pragma: no cover
        return out
    for rel in rels[:3]:
        if not rel.endswith((".yaml", ".yml")):
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
        except Exception:                                          # noqa: BLE001
            continue
        if isinstance(doc, dict):
            gb = (doc.get("metadata") or {}).get("generated_by") if isinstance(
                doc.get("metadata"), dict) else None
            if isinstance(gb, str) and gb.strip():
                out.add(gb.strip())
    return out


# ── the check ───────────────────────────────────────────────────────────────────────────────────
class Census:
    def __init__(self):
        self.families = {}          # (dir, ext) -> dict
        self.defects = []           # (severity, cls, subject, why)
        self.notes = []


def census(root: str, R, manifest) -> Census:
    c = Census()
    ents = _registry_entries(R, manifest)
    prefixes = _plane_prefixes(manifest)
    cmds = declared_commands(manifest)

    # WHICH ENTRY OWNS WHICH FILE — resolved with glob.glob(recursive=True), the SAME call
    # check_reproduction uses for `produces`, so the two gates cannot disagree about what a pattern
    # means. That was the whole reason the console's hand-written plane list was wrong every time it
    # was written.
    owner = {}
    for e in ents:
        pat = str(e["glob"])
        for hit in _glob.glob(os.path.join(root, pat), recursive=True):
            if not os.path.isfile(hit):
                continue
            rel = os.path.relpath(hit, root).replace(os.sep, "/")
            prev = owner.get(rel)
            if prev is None or _specificity(pat) > _specificity(str(prev["glob"])):
                owner[rel] = e

    # WHICH `produces` PATTERN COVERS WHICH FILE — same call, same semantics.
    covered, pattern_of = set(), {}
    for st in ((manifest.get("reproduction") or {}).get("stages") or []):
        if not isinstance(st, dict):
            continue
        for pat in (st.get("produces") or []):
            for hit in _glob.glob(os.path.join(root, str(pat)), recursive=True):
                if os.path.isfile(hit):
                    rel = os.path.relpath(hit, root).replace(os.sep, "/")
                    covered.add(rel)
                    pattern_of.setdefault(rel, f"stages[{st.get('id')}] {pat}")

    for rel in _files(root):
        key = _family_of(rel)
        fam = c.families.setdefault(key, {
            "dir": key[0], "ext": key[1], "files": [], "unowned": [],
            "origins": set(), "entries": [], "in_plane": _in_plane(key[0], prefixes),
        })
        fam["files"].append(rel)
        e = owner.get(rel)
        if e is None:
            fam["unowned"].append(rel)
        else:
            fam["origins"].add(e["_origin"])
            fam.setdefault("owner_of", {})[rel] = e
            if e not in fam["entries"]:
                fam["entries"].append(e)

    for key, fam in sorted(c.families.items()):
        name = f"{fam['dir']}/*{fam['ext']}"
        n = len(fam["files"])

        # 1 · UNREGISTERED_FAMILY — nothing, doc or code, says where these files come from.
        #     PER FILE, not per family: a family that mixes a projected page with a hand-written one
        #     (the root `*.md` of a real bundle: `index.md` projected, `README.md` by hand) must not
        #     let either half hide the other. The derived half is still judged below.
        if fam["unowned"]:
            if fam["in_plane"]:
                c.defects.append((
                    ERROR, "UNREGISTERED_FAMILY", name,
                    f"{len(fam['unowned'])} of {n} file(s) under the declared plane match no "
                    f"registry entry — no producer, no author, no deliberate omission is recorded "
                    f"anywhere (e.g. {fam['unowned'][0]}). Declare it in "
                    f"mac_resources.DERIVED/AUTHORED/NOT_DECLARED, or, if only this bundle has it, "
                    f"in mac.project.yaml#artifact_families"))
            else:
                fam["out_of_plane_unknown"] = True

        # 2 · UNREACHED_PRODUCER — a tool writes it and no declared command reaches that tool.
        #     The population is the files a DERIVED entry owns, so an unregistered neighbour neither
        #     silences this class nor inflates its denominator.
        if "derived" in fam["origins"]:
            derived_files = [r for r, e in (fam.get("owner_of") or {}).items()
                             if e["_origin"] == "derived"]
            n = len(derived_files)
            for e in fam["entries"]:
                if e["_origin"] != "derived":
                    continue
                prod = e.get("producer")
                if not prod:
                    c.notes.append(f"NO-PRODUCER-KEY  {name} — registry entry `{e['glob']}` is "
                                   f"derived but names no `producer`, so reachability is unknown")
                    continue
                hit = _reaches(prod, R, cmds)
                if hit is None:
                    doors = ", ".join(f"`{x}`" for x in
                                      ((R.PRODUCERS.get(prod) or {}).get("entrypoints") or ()))
                    c.defects.append((
                        ERROR, "UNREACHED_PRODUCER", name,
                        f"{n} file(s) present, written by `{e.get('by')}` (producer `{prod}`), and "
                        f"NONE of the {len(cmds)} declared command(s) in `reproduction` reaches it "
                        f"— not stages[].command, not pipelines.*.entry, not gate.command. The next "
                        f"operator is not told the command exists. Doors that would reach it: "
                        f"{doors or '(none registered)'}"))
                else:
                    fam.setdefault("reached", []).append((e["glob"], prod, hit[0], hit[2]))

            # 3 · PARTIAL_PRODUCES_COVERAGE — a stage names this family and under-states its reach.
            named = sorted(r for r in derived_files if r in covered)
            if named and len(named) < n:
                c.defects.append((
                    WARNING, "PARTIAL_PRODUCES_COVERAGE", name,
                    f"a stage declares this family — {pattern_of[named[0]]} — and its pattern(s) "
                    f"cover {len(named)} of {n} file(s); the other {n - len(named)} have a "
                    f"producing command but no record that it makes them "
                    f"(e.g. {sorted(set(derived_files) - set(named))[0]})"))

            # 4 · STAMP_UNKNOWN_WRITER — the artifacts name a writer the registry does not know.
            stamps = _stamp_writers(root, sorted(derived_files))
            if stamps:
                known = set()
                for e in fam["entries"]:
                    for ep in ((R.PRODUCERS.get(e.get("producer")) or {}).get("entrypoints") or ()):
                        known.add(ep)
                for s in sorted(stamps):
                    if not any(ep.strip("-").split()[0] in s for ep in known if ep):
                        c.defects.append((
                            WARNING, "STAMP_UNKNOWN_WRITER", name,
                            f"the files stamp `metadata.generated_by: {s}`, which no registered "
                            f"producer's entrypoints name — the registry is behind the tool, or "
                            f"something else wrote them"))
    return c


def report(root: str) -> int:
    if not os.path.isdir(root):
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(root, "mac.project.yaml")):
        print(f"could not run: {root} has no mac.project.yaml, so there is no manifest to read "
              f"planes or a reproduction record from", file=sys.stderr)
        return 2
    try:
        R = load_registry()
    except Exception as exc:                                       # noqa: BLE001
        print(f"could not run: the artifact-family registry could not be imported "
              f"(mac_resources: {exc}) — an unreachable registry means UNKNOWN, and `not computed` "
              f"and `clean` are opposite facts", file=sys.stderr)
        return 2
    try:
        import check_reproduction as CR
        manifest = CR._manifest(root)                              # THE SAME manifest reader
    except Exception as exc:                                       # noqa: BLE001
        print(f"could not run: could not read the manifest through check_reproduction's own reader "
              f"({exc})", file=sys.stderr)
        return 2
    if not manifest:
        print(f"could not run: {root}/mac.project.yaml parsed to nothing", file=sys.stderr)
        return 2

    c = census(root, R, manifest)
    fams = c.families
    # THE MANIFEST IS NOT AN ARTIFACT FAMILY. Counting it would let a bundle holding nothing but
    # `mac.project.yaml` report a healthy-looking "1 family present".
    bearing = sum(len([f for f in v["files"] if f != "mac.project.yaml"]) for v in fams.values())
    if bearing == 0:
        print(f"could not run: {root} carries 0 file(s) besides its manifest — a scaffolded or "
              f"empty tree proves nothing, and 0 families present is not the same as clean",
              file=sys.stderr)
        return 2

    in_plane = {k: v for k, v in fams.items() if v["in_plane"]}
    derived = {k: v for k, v in fams.items() if "derived" in v["origins"]}
    authored = {k: v for k, v in fams.items()
                if "derived" not in v["origins"] and "authored" in v["origins"]}
    by_design = {k: v for k, v in fams.items()
                 if v["origins"] == {"not-declared-by-design"}}
    unreg_in = {k: v for k, v in in_plane.items() if v["unowned"]}
    unreg_out = {k: v for k, v in fams.items() if v["unowned"] and not v["in_plane"]}
    reached = sum(1 for v in derived.values() if v.get("reached"))
    judged = len(derived) + len(unreg_in)

    # THE REACHABLE EMPTINESS. Families are present and NONE of them is judged by either class: a
    # registry that stopped matching, or a filter that quietly emptied. validate_schema closed this
    # mode at the file layer today; this is the same mode one layer up.
    if judged == 0:
        print(f"could not run: {len(fams)} family(ies) present under {root} and NONE is judged — "
              f"0 registered-derived families and 0 unregistered in-plane families. The registry "
              f"matched nothing judgeable, so this run proves nothing about "
              f"{sum(len(v['files']) for v in fams.values())} file(s)", file=sys.stderr)
        return 2

    for n in c.notes:
        print(f"  {n}")
    errs = [d for d in c.defects if d[0] == ERROR]
    warns = [d for d in c.defects if d[0] == WARNING]
    for sev, cls, subj, why in errs + warns:
        stream = sys.stderr if sev == ERROR else sys.stdout
        print(f"  [{cls}] {subj}: {why}", file=stream)

    denom = (f"{len(fams)} family(ies) on disk, {len(in_plane)} under a declared plane; judged "
             f"{judged} — {len(derived)} registered-derived ({reached} with a declared command that "
             f"reaches the producer) + {len(unreg_in)} unregistered in-plane; UNCHECKED: "
             f"{len(authored)} authored, {len(by_design)} not-declared-by-design, "
             f"{len(unreg_out)} outside every declared plane")
    if errs:
        print(f"\nFAIL: {NAME} — {len(errs)} defect(s), {len(warns)} warning(s) over {denom}",
              file=sys.stderr)
        return 1
    print(f"\nPASS: {NAME} — 0 defect(s), {len(warns)} warning(s) over {denom}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    return report(os.path.abspath(a.root))


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# self-test: one mutant per reject class, plus the two negative controls that are RECONSTRUCTIONS OF
# REAL BUNDLES — without them this gate ships born-red at error severity on a committed clean bundle
# and gets suppressed. Fixtures name nothing real: alpha, beta, gamma in a temp directory.
# ─────────────────────────────────────────────────────────────────────────────────────────────────

_MANIFEST_PLANES = """\
metadata:
  project: alpha/beta
  data_domain: alpha
  dataset: beta
planes:
  data: data
  ontology: ontology
descriptors: data/datasets
sources: data/sources
lookups: data/lookups
"""

_STAGE_MEASURE = """\
reproduction:
  stages:
    - id: measure
      authoring: tool
      command: >-
        python3 meaning-as-code/tools/mac_profile.py <root> <stem>;
        python3 meaning-as-code/tools/mac_sample.py <root>;
        python3 meaning-as-code/tools/mac_references.py <root> --plane sources;
        python3 meaning-as-code/tools/mac_references.py <root> --plane served
      produces:
        - data/profiles/*.yaml
        - data/samples/*.csv
        - data/references/*.yaml
        - data/references_served/*.yaml
"""

_PIPELINE_ONBOARD = """\
reproduction:
  pipelines:
    data:
      entry: python3 -m sdk.cli.harvest --content-root <root> --mode onboard --accept
"""

_STAGE_PROJECTION = """\
reproduction:
  stages:
    - id: projection
      authoring: tool
      command: python -m sdk.cli.harvest --content-root <root> --mode project
      produces:
        - objects.json
        - ontology/vocabulary.json
        - ontology/ontology_quality.json
"""


def _seed(root, *, manifest, files) -> str:
    import pathlib as _pl
    r = _pl.Path(root)
    r.mkdir(parents=True, exist_ok=True)
    (r / "mac.project.yaml").write_text(manifest, encoding="utf-8")
    for rel, text in files.items():
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return str(r)


_SRC = "source:\n  name: gamma\n"
_PROFILE = "metadata:\n  generated_by: mac_profile.py/5\nof: gamma\n"
_PROFILE_ODD = "metadata:\n  generated_by: handmade_profiler.py/1\nof: gamma\n"
_SAMPLE = "a,b\n1,2\n"
_REF = "references: []\n"


def _run(root: str) -> int:
    argv = sys.argv
    sys.argv = [f"{NAME}.py", root]
    try:
        return main()
    finally:
        sys.argv = argv


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "cases")

        def case(label, *, manifest, files, want):
            root = _seed(os.path.join(base, label), manifest=manifest, files=files)
            got = _run(root)
            if got != want:
                failures.append(f"{label}: expected exit {want}, got {got}")
            return root

        # 1 · not a directory at all.
        if _run(os.path.join(tmp, "nope")) != 2:
            failures.append("not-a-directory: expected exit 2")

        # 2 · a real directory with no manifest.
        nm = os.path.join(base, "no-manifest")
        os.makedirs(nm, exist_ok=True)
        open(os.path.join(nm, "data.txt"), "w").close()
        if _run(nm) != 2:
            failures.append("no-manifest: expected exit 2")

        # 3 · REFUSE on an empty tree — 0 families present is not clean.
        case("empty", manifest=_MANIFEST_PLANES, files={}, want=2)

        # 4 · REFUSE on the REACHABLE emptiness: families present, none judged. Everything on disk
        #     is authored or outside a plane, so both reject classes have a population of zero while
        #     the enumeration is healthy — the mode validate_schema closed today, one layer up.
        case("nothing-judged", manifest=_MANIFEST_PLANES,
             files={"data/sources/gamma.yaml": _SRC, "decisions/why.md": "# why\n"}, want=2)

        # 5 · MUTANT for UNREGISTERED_FAMILY — B2 AS IT ACTUALLY HAPPENED: a family on disk with no
        #     stage, no doc section and no registry entry. Both other populations presuppose the
        #     family is already described, so this is the only class that can catch the next one.
        case("b2-unregistered", manifest=_MANIFEST_PLANES + _STAGE_PROJECTION,
             files={"data/sources/gamma.yaml": _SRC,
                    "data/attestations/gamma.yaml": "attested: true\n",
                    "objects.json": "{}\n"}, want=1)

        # 6 · and its REMEDY: the bundle declares the family itself. Two lines, its own manifest.
        case("b2-bundle-local-remedy",
             manifest=_MANIFEST_PLANES + _STAGE_PROJECTION + """\
artifact_families:
  - glob: data/attestations/*.yaml
    origin: authored
    by: the data steward, by hand
""",
             files={"data/sources/gamma.yaml": _SRC,
                    "data/attestations/gamma.yaml": "attested: true\n",
                    "objects.json": "{}\n"}, want=0)

        # 7 · MUTANT for UNREACHED_PRODUCER — B1 AS IT IS STILL LIVE in one real bundle: previews and
        #     profiles on disk, a reproduction record that names neither producing command.
        case("b1-unreached", manifest=_MANIFEST_PLANES + _STAGE_PROJECTION,
             files={"data/sources/gamma.yaml": _SRC,
                    "data/profiles/gamma.yaml": _PROFILE,
                    "data/samples/gamma.sample.csv": _SAMPLE,
                    "objects.json": "{}\n"}, want=1)

        # 8 · NEGATIVE CONTROL: the same families under the fused `measure` stage — the real bundle's
        #     post-fix shape. MUST pass, or the fix that landed today is called a defect.
        case("b1-fixed", manifest=_MANIFEST_PLANES + _STAGE_MEASURE,
             files={"data/sources/gamma.yaml": _SRC,
                    "data/profiles/gamma.yaml": _PROFILE,
                    "data/samples/gamma.sample.csv": _SAMPLE,
                    "data/samples/samples.run.json": "{}\n",
                    "data/references/gamma.yaml": _REF,
                    "data/references/references.run.json": "{}\n",
                    "data/references_served/gamma.yaml": _REF}, want=0)

        # 9 · NEGATIVE CONTROL, THE ONE THAT DECIDES WHETHER THIS GATE IS USABLE: a bundle whose ONLY
        #     declaration of the projector is `pipelines.data.entry` (--mode onboard). That is a
        #     committed clean bundle's real shape. A gate reading only stages[].command prints ERROR
        #     here and demands a stage that was never run.
        case("projector-via-pipeline-entry", manifest=_MANIFEST_PLANES + _PIPELINE_ONBOARD,
             files={"data/sources/gamma.yaml": _SRC,
                    "data/sources/gamma.md": "# gamma\n",
                    "objects.json": "{}\n",
                    "lineage_graph.json": "{}\n",
                    "compile.json": "{}\n",
                    "index.md": "# index\n"}, want=0)

        # 10 · MUTANT for PARTIAL_PRODUCES_COVERAGE (warning, exit 0): one literal path declared,
        #      three files present. Must NOT be an error — the producing command IS named.
        part = case("partial-coverage", manifest=_MANIFEST_PLANES + """\
reproduction:
  stages:
    - id: measure-register
      command: python3 data/lookups/gamma.lookup.build.py <root>
      produces:
        - data/lookups/gamma.lookup.csv
""",
                    files={"data/sources/gamma.yaml": _SRC,
                           "data/lookups/gamma.lookup.csv": "code,label\n1,a\n",
                           "data/lookups/delta.lookup.csv": "code,label\n2,b\n",
                           "data/lookups/epsilon.lookup.csv": "code,label\n3,c\n"}, want=0)
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _run(part)
        if "PARTIAL_PRODUCES_COVERAGE" not in buf.getvalue():
            failures.append("partial-coverage: the warning class did not fire")
        if "1 of 3 file(s)" not in buf.getvalue():
            failures.append("partial-coverage: coverage was not printed as 1 of 3")

        # 11 · MUTANT for STAMP_UNKNOWN_WRITER (warning, exit 0).
        stamp = case("odd-stamp", manifest=_MANIFEST_PLANES + _STAGE_MEASURE,
                     files={"data/sources/gamma.yaml": _SRC,
                            "data/profiles/gamma.yaml": _PROFILE_ODD,
                            "data/samples/gamma.sample.csv": _SAMPLE,
                            "data/references/gamma.yaml": _REF,
                            "data/references_served/gamma.yaml": _REF}, want=0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _run(stamp)
        if "STAMP_UNKNOWN_WRITER" not in buf.getvalue():
            failures.append("odd-stamp: the warning class did not fire")

        # 12 · THE MUTANT FOR THE REGISTRY ITSELF: families on disk and an UNRESOLVABLE registry.
        #      Without this the reject-class-per-mutant rule is not satisfied — an unimportable
        #      producer map must REFUSE, never pass over a population it could not build.
        broke = _seed(os.path.join(base, "no-registry"), manifest=_MANIFEST_PLANES,
                      files={"data/profiles/gamma.yaml": _PROFILE})
        real, sys.modules["mac_resources"] = sys.modules.get("mac_resources"), None
        try:
            import builtins
            real_import = builtins.__import__

            def _boom(name, *a, **k):
                if name == "mac_resources":
                    raise ImportError("simulated: the registry is unreachable")
                return real_import(name, *a, **k)
            builtins.__import__ = _boom
            try:
                if _run(broke) != 2:
                    failures.append("no-registry: expected exit 2")
            finally:
                builtins.__import__ = real_import
        finally:
            if real is not None:
                sys.modules["mac_resources"] = real
            else:
                sys.modules.pop("mac_resources", None)

        # 13 · the PASS line must carry what it did NOT judge. A green line without an UNCHECKED
        #      term reads as "this bundle's artifacts have declared producers", which is false in
        #      both real bundles.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _run(os.path.join(base, "b1-fixed"))
        out = buf.getvalue()
        for term in ("family(ies) on disk", "under a declared plane", "judged", "UNCHECKED"):
            if term not in out:
                failures.append(f"pass-line: missing the term {term!r}")

    total = 13
    if failures:
        print(f"FAIL: {NAME} self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: {NAME} self-test — {total}/{total} (not-a-directory, no-manifest, empty tree, "
          f"NOTHING-JUDGED and an unresolvable registry all refuse with exit 2; B2's undeclared "
          f"family and B1's unreached producer both fail; the bundle-local remedy, the fused "
          f"`measure` stage and a projector declared ONLY at pipelines.data.entry all pass; "
          f"partial produces coverage and an unknown writer stamp warn without failing; the PASS "
          f"line carries its UNCHECKED term)")
    return 0


if __name__ == "__main__":                                         # pragma: no cover
    raise SystemExit(main())
