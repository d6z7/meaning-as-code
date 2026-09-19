#!/usr/bin/env python3
"""mac_resources.py — write the ontology's RESOURCE DESCRIPTION: `<name>.mac` at the bundle root.

WHY THIS EXISTS. An ontology is hundreds of files across several planes. To open one the way a
document is opened, a host must be able to read ONE file and learn what the thing contains, which
grammar judged it, and whether that description is still true. Nothing did that job:

  mac.project.yaml   says WHERE the planes are (`data:`, `ontology:`, `descriptors:`) and what the
                     container CLAIMS it can do. It does not say what components exist.
  MANIFEST.json      says WHICH BYTES — path:sha256 and a tree hash. Integrity, not semantics.
  objects.json       the closest thing, and it fails as this in four measured ways: 244 KB, so
                     nothing reads it to DECIDE; zero provenance stamps, so staleness is
                     undetectable; absent from all three other bundles in the estate; and it is a
                     read-view shaped for one UI rather than a declaration.

THE FILE'S SHAPE, per the operator: the BASENAME IS ARBITRARY and the EXTENSION IS FIXED, at the
bundle ROOT — the project-file convention. `tpch.mac`, `shop.mac`, `anything.mac`. A host discovers
an ontology by globbing `*.mac` in a directory: exactly one match means this IS an ontology and that
file is its description; zero means it is not one; two is ambiguous and must be refused rather than
guessed at.

WHY GENERATED AND STAMPED. A description maintained by hand drifts from the tree it describes, and a
description that has drifted is worse than none — it is a confident wrong answer, which is the defect
this estate spent a programme removing. So it carries `grammar_id` (WHICH grammar judged these
components) and `tree_hash` (the bytes it describes), and `--check` re-derives and refuses on any
difference. Regenerate it; never edit it.

    python3 tools/mac_resources.py <bundle>              # write/refresh <name>.mac
    python3 tools/mac_resources.py <bundle> --check      # PASS/FAIL: is the description still true?
    python3 tools/mac_resources.py --self-test
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

#: FIXED. The basename beside it is the author's to choose.
EXT = ".mac"

SPEC = "mac.resources/1"
GENERATOR = "mac_resources.py/1"

#: The DERIVED artifacts: produced by a tool, reproducible from the authored files, and NOT the
#: source of truth. Tonight's failures were all in this column — a host asked for a read-view that
#: no projector had emitted, and an index recorded a path that did not exist — because nothing
#: declared which files are generated, by what, or where they land.
#:
#: `flat: True` is the one that cost the most: the page builder writes `<stem>.md` at the concepts
#: ROOT even when the concept it describes is nested, so doc and schema paths differ in shape.
#: `producer` is the KEY INTO `PRODUCERS` below — the command that actually runs this writer. It is
#: separate from `by` because `by` names the MODULE (three spellings, historically) while the
#: question a reproduction record has to answer is "which declared command reaches it".
DERIVED: tuple[dict, ...] = (
    {"glob": "objects.json", "by": "sdk.project.objects", "kind": "object-index",
     "producer": "projector"},
    {"glob": "ontology/concepts/*.md", "by": "sdk.project.mac_okf", "kind": "read-view", "flat": True,
     "producer": "projector"},
    {"glob": "ontology/concepts/rules/*.md", "by": "sdk.project.mac_okf", "kind": "read-view",
     "producer": "projector"},
    {"glob": "ontology/concepts/index.md", "by": "sdk.project.mac_okf", "kind": "read-view",
     "producer": "projector"},
    {"glob": "data/**/*.md", "by": "sdk.project.project_data", "kind": "read-view",
     "producer": "projector"},
    {"glob": "compile.json", "by": "mac_compile", "kind": "verdict", "producer": "compiler"},
    {"glob": "lineage_graph.json", "by": "lineage_project.py", "kind": "graph",
     "producer": "projector"},
    # ── ADDED 2026-09-18, and the reason this table exists at all ────────────────────────────────
    # Everything below was ALREADY being written by a tool and was in NO machine-readable table, so
    # nothing could ask "is this family's producer declared anywhere". `data/samples` rotted for
    # months on exactly that hole (3 of 25 headers stale, one short by ten of twenty-two columns,
    # and a decision record citing the stale file as proof). The entries carry the write site so a
    # reader can check the attribution rather than trust it.
    {"glob": "index.md", "by": "sdk.project.project_data:515", "kind": "read-view",
     "producer": "projector"},
    {"glob": "data/profiles/*.yaml", "by": "mac_profile.py:255", "kind": "measurement",
     "producer": "profiler"},
    {"glob": "data/samples/*.csv", "by": "mac_sample.py", "kind": "preview", "producer": "sampler"},
    # THE CONCEPT MEMBER DRAW, AND IT IS AN ONTOLOGY ARTIFACT, NOT A DATA ONE. Same tool, second
    # draw (`mac_sample.py --plane concepts`), and a different plane on purpose: the entry above
    # previews a RELATION at the columns a DESCRIPTOR declares, while this one draws a CONCEPT's
    # own members — the population is `grounding.discriminator` / `value_filter` and the columns
    # are the concept's Fields table, so nothing in the data plane can say what the file is. It
    # lived at `data/samples/concepts/*.csv` until the operator ruled the plane wrong. ONE FILE
    # PER GROUNDING SOURCE: a concept over two relations cuts `<stem>.<relation>.sample.csv` twice
    # and a single-source concept keeps the bare `<stem>.sample.csv`.
    {"glob": "ontology/samples/*.csv", "by": "mac_sample.py --plane concepts",
     "kind": "member-draw", "producer": "sampler"},
    {"glob": "data/references/*.yaml", "by": "mac_references.py --plane sources",
     "kind": "reference-structure", "producer": "references"},
    {"glob": "data/references_served/*.yaml", "by": "mac_references.py --plane served",
     "kind": "reference-structure", "producer": "references"},
    {"glob": "data/lookups/*.csv", "by": "harvest --mode lookups", "kind": "register",
     "producer": "lookup-build"},
    {"glob": "data/quality/*.json", "by": "sdk.project.project_data:930", "kind": "dashboard",
     "producer": "projector"},
    {"glob": "ontology/vocabulary.json", "by": "sdk.project.vocabulary (objects.py:1161)",
     "kind": "read-view", "producer": "projector"},
    {"glob": "ontology/ontology_quality.json", "by": "sdk.project.ontology_quality (objects.py:1129)",
     "kind": "dashboard", "producer": "projector"},
    {"glob": "ontology/edges.json", "by": "sdk.project.objects:1176", "kind": "read-view",
     "producer": "projector"},
    {"glob": "ontology/diagnostics.json", "by": "sdk.cli.harvest:333", "kind": "dashboard",
     "producer": "projector"},
    {"glob": "ontology/SME-QUESTIONS.md", "by": "sdk.project.objects:184", "kind": "read-view",
     "producer": "projector"},
    {"glob": "knowledge/*.md", "by": "sdk.project.knowledge:115", "kind": "read-view",
     "producer": "projector"},
    {"glob": "references/*.md", "by": "sdk.project.references:133", "kind": "read-view",
     "producer": "projector"},
    {"glob": "references/known_issues/*.md", "by": "sdk.project.references:175", "kind": "read-view",
     "producer": "projector"},
    {"glob": "interventions/LEDGER.md", "by": "sdk.project.project_data:846", "kind": "read-view",
     "producer": "projector"},
    {"glob": "acceptance/questions_dashboard.json", "by": "sdk.project.questions:557",
     "kind": "dashboard", "producer": "question-projector"},
)

#: WHICH DECLARED COMMAND REACHES A PRODUCER. `entrypoints` are substrings of a command string, and
#: each one is a door that PROVABLY reaches the writer — the citation is in `why` so the claim can be
#: checked. Substring matching is deliberately generous: the question is "does the record name a way
#: to remake this", not "is the command spelled the canonical way".
#:
#: THE ONE THAT MATTERS: `--mode onboard` reaches the WHOLE projector, because
#: sdk/cli/harvest.py:1230 ends the onboard flow with `project_source(cr, ...)` under the comment
#: "5) PROJECT (offline, deterministic) — ALWAYS, in both dry-run and accept". A gate that looked
#: only for `--mode project` would call a bundle that declares `--mode onboard --accept` undeclared,
#: and the remedy it demanded — a standalone `projection` stage that was never run — would make the
#: reproduction record LESS true than the silence it replaced.
PRODUCERS: dict[str, dict] = {
    "projector": {
        "entrypoints": ("--mode project", "--mode onboard", "sdk.container.save",
                        "project_objects.py", "regen_projections"),
        "why": "sdk/cli/harvest.py:1230 (onboard ends in project_source) and harvest.py --mode "
               "project, the offline door; project_source runs project_data.build_data + objects + "
               "mac_okf + knowledge + references + _semantic_diagnostics + compile_gate in ONE run",
    },
    "compiler": {
        "entrypoints": ("mac_compile.py", "--mode project", "--mode onboard"),
        "why": "compile.json is written by compile_gate inside project_source (harvest.py:512) and "
               "by tools/mac_compile.py run directly",
    },
    "profiler": {
        "entrypoints": ("mac_profile.py", "mac_profile_split.py", "mac_admit_identity.py"),
        "why": "tools/mac_profile.py:255 writes data/profiles/<stem>.yaml; the splitter and the "
               "identity admitter rewrite the same family",
    },
    "sampler": {
        "entrypoints": ("mac_sample.py",),
        "why": "tools/mac_sample.py writes data/samples/<stem>.sample.csv + its samples.run.json "
               "(the relation preview), and --plane concepts writes ontology/samples/"
               "<stem>[.<relation>].sample.csv + its own samples.run.json (the concept member "
               "draw). TWO DRAWS, TWO PLANES, ONE COMMAND — one entrypoint reaches both",
    },
    "references": {
        "entrypoints": ("mac_references.py",),
        "why": "tools/mac_references.py writes data/references{,_served}/<stem>.yaml",
    },
    "lookup-build": {
        "entrypoints": ("--mode lookups", ".lookup.build.py"),
        "why": "harvest --mode lookups builds the registers; a bundle may instead declare its "
               "per-register `<x>.lookup.build.py`, which is the same producer by another door",
    },
    "question-projector": {
        "entrypoints": ("sdk.project.questions",),
        "why": "sdk/project/questions.py:557 — its own module, invoked as `python3 -m "
               "sdk.project.questions <bundle>` (what console_api shells)",
    },
}

#: AUTHORED families: a human or a model wrote them and NO tool reproduces them, so a reproduction
#: record must NOT claim to produce them. Registered here so that "nothing produces this" can be
#: told apart from "nobody has said where this comes from" — the two were indistinguishable, and the
#: second is the defect.
AUTHORED: tuple[dict, ...] = (
    {"glob": "data/sources/*.yaml", "kind": "source", "by": "model (harvest --mode data) or hand"},
    {"glob": "data/datasets/*.yaml", "kind": "dataset", "by": "model (harvest --mode data) or hand"},
    {"glob": "data/transforms/*.yaml", "kind": "transform", "by": "model or hand"},
    {"glob": "data/transforms/*.sql", "kind": "transform-sql", "by": "model or hand"},
    {"glob": "data/transforms/*.why.md", "kind": "rationale", "by": "hand",
     "note": "beats the generic data/**/*.md read-view glob on specificity: this one is NOT projected"},
    {"glob": "data/quality/*.yaml", "kind": "dq-register",
     "by": "SME/operator, or a model in a declared authoring stage",
     "note": "the register and the resolution map are the SOURCE OF TRUTH the dashboard projects "
             "FROM. Whether a stage may claim to `produce` them is BUNDLE-SPECIFIC and measured "
             "both ways in this estate: one bundle declares them under an `authoring: model` "
             "stage (an LLM authored that register), another's are an SME's own rulings. A "
             "framework registry cannot decide that, so it states only the part that is always "
             "true: no TOOL reproduces them."},
    {"glob": "data/lookups/*.py", "kind": "build-script", "by": "hand"},
    {"glob": "ontology/*.yaml", "kind": "ontology-ssot", "by": "hand"},
    {"glob": "ontology/*.md", "kind": "prose", "by": "hand",
     "note": "prose beside the plane; a bundle may document itself. The projector's OWN pages in "
             "this directory are registered above and win on specificity."},
    {"glob": "**/*.parquet", "kind": "engine-store", "by": "the engine / a landing load",
     "note": "not a semantic artifact: the bytes a connector reads. Registered so a bundle that "
             "keeps its landing data inside the data plane is not a finding."},
)

#: DELIBERATELY NOT DECLARED in any reproduction record, with the reason. A `produces` pattern that
#: CANNOT FAIL adds no signal and inflates the denominator — the run record is written in the same
#: branch as the per-relation files it accounts for, so it can never miss while they hit. Contoso's
#: manifest already ruled on this in prose ("FOUR PATTERNS AND NOT SIX"); this is the machine-readable
#: form of that ruling, so a disk-sourced population does not false-red on it in every bundle.
NOT_DECLARED: tuple[dict, ...] = (
    {"glob": "data/samples/samples.run.json", "by": "mac_sample.py:677",
     "reason": "run record, written in the same branch as the previews it accounts for"},
    {"glob": "ontology/samples/samples.run.json", "by": "mac_sample.py --plane concepts",
     "reason": "run record, written in the same branch as the concept blocks it accounts for. A "
               "SECOND record and not a second copy: it holds the concept draw and its stamps, "
               "the file above holds the relation previews and theirs, and each carries a POINTER "
               "at the other rather than any of its facts — one record for two draws could only "
               "ever stamp one of them truthfully, and measurably did not"},
    {"glob": "data/references/references.run.json", "by": "mac_references.py:1100",
     "reason": "run record, written in the same branch as the reference files it accounts for"},
    {"glob": "data/references_served/references.run.json", "by": "mac_references.py:1100",
     "reason": "run record, written in the same branch as the reference files it accounts for"},
)

#: plane -> (glob relative to the bundle root, kind)
PLANES: tuple[tuple[str, str, str], ...] = (
    ("ontology", "ontology/concepts/**/*.yaml", "concept"),
    ("ontology", "ontology/rules.yaml", "rules"),
    ("ontology", "ontology/edges.yaml", "edges"),
    ("data", "data/datasets/*.yaml", "dataset"),
    ("data", "data/sources/*.yaml", "source"),
    ("data", "data/transforms/*.yaml", "transform"),
    ("data", "data/lookups/*.csv", "lookup"),
    ("data", "data/profiles/*.yaml", "profile"),
    ("acceptance", "acceptance/*.yaml", "suite"),
)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tree_hash(root: Path) -> str:
    """sha256 over sorted `relpath:sha256` of every tracked-shaped file, excluding derived output.

    Deliberately NOT the publisher's MANIFEST hash: that covers a sealed artifact. This one covers
    the SOURCE tree the description was derived from, so `--check` can tell "the tree moved" from
    "the description is stale".
    """
    parts = []
    skip = {".git", "__pycache__", "artifacts", ".context", "node_modules"}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(s in p.parts for s in skip):
            continue
        rel = p.relative_to(root)
        if rel.suffix == EXT or rel.name in {"objects.json", "compile.json"}:
            continue  # derived: describing it would make the hash describe itself
        parts.append(f"{rel}:{_sha(p.read_bytes())}")
    return _sha("\n".join(parts).encode())


def grammar_id() -> str:
    """WHICH grammar these components were judged against."""
    try:
        from meaning_as_code import framework_root  # noqa: PLC0415

        fw = framework_root()
    except Exception:
        fw = Path(__file__).resolve().parent.parent
    schema = fw / "mac.schema.json"
    if not schema.is_file():
        return "unknown"
    payload = _sha(schema.read_bytes())[:16]
    ver = (fw / "VERSION").read_text(encoding="utf-8").strip() if (fw / "VERSION").is_file() else "0"
    return f"mac/{ver}+{payload}"


def _title(path: Path, kind: str) -> tuple[str, dict]:
    """The component's own declared identity, read from its own file — never inferred from its name."""
    extra: dict = {}
    if path.suffix != ".yaml":
        return path.stem, extra
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return path.stem, {"unreadable": True}
    if not isinstance(doc, dict):
        return path.stem, extra
    if kind == "concept":
        c = doc.get("concept") or {}
        extra = {k: v for k, v in (("class", c.get("class")), ("definition", (c.get("definition") or "").strip()[:120])) if v}
        return c.get("name") or path.stem, extra
    if kind == "dataset":
        t = doc.get("table") or {}
        if t.get("schema"):
            extra["relation"] = f"{t['schema']}.{t.get('name') or path.stem}"
        return t.get("name") or path.stem, extra
    if kind == "transform":
        pr = doc.get("produces") or {}
        if pr.get("relation"):
            extra["produces"] = pr["relation"]
        if pr.get("grain"):
            extra["grain"] = pr["grain"]
        return (doc.get("metadata") or {}).get("pipeline") or path.stem, extra
    if kind in {"suite", "rules"}:
        n = len(doc.get("properties") or doc.get("rules") or [])
        if n:
            extra["entries"] = n
        return doc.get("suite") or path.stem, extra
    return path.stem, extra


def describe(root: Path) -> dict:
    root = root.resolve()
    proj = {}
    mp = root / "mac.project.yaml"
    if mp.is_file():
        proj = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    meta = proj.get("metadata") or {}

    resources, counts, absent = [], {}, []
    for plane, pattern, kind in PLANES:
        hits = sorted(glob.glob(str(root / pattern), recursive=True))
        if not hits:
            absent.append(pattern)
            continue
        for h in hits:
            p = Path(h)
            title, extra = _title(p, kind)
            resources.append(
                {"id": title, "kind": kind, "plane": plane,
                 "path": str(p.relative_to(root)), **extra}
            )
        counts[kind] = counts.get(kind, 0) + len(hits)

    # LAYOUT — where each kind lives and whether it actually nests, MEASURED rather than assumed.
    # Three projectors in this estate globbed `ontology/concepts/*.yaml` (flat) and silently
    # produced nothing for a bundle that files concepts by domain. A host that reads this does not
    # have to guess, and a projector can be checked against it.
    layout = {}
    for plane, pattern, kind in PLANES:
        hits = sorted(glob.glob(str(root / pattern), recursive=True))
        if not hits:
            continue
        base = pattern.split("*")[0].rstrip("/")
        nests = any(
            len(Path(h).relative_to(root / base).parts) > 1 for h in hits
        ) if base else False
        layout[kind] = {"glob": pattern, "plane": plane, "nests": nests, "files": len(hits)}

    derived = []
    for d in DERIVED:
        hits = sorted(glob.glob(str(root / d["glob"]), recursive=True))
        if not hits:
            continue
        derived.append(
            {**{k: v for k, v in d.items()}, "files": len(hits)}
        )

    return {
        "spec_version": SPEC,
        "identity": {
            "container": f"{meta.get('data_domain')}/{meta.get('dataset')}"
            if meta.get("dataset")
            else None,
            "label": meta.get("label"),
            "grammar_id": grammar_id(),
            "tree_hash": tree_hash(root),
            "generated_by": GENERATOR,
        },
        "counts": dict(sorted(counts.items())),
        # HOW IT IS STRUCTURED, and HOW IT IS BUILT — the two questions a host or a projector had
        # to guess at, and got wrong.
        "layout": layout,
        "derived": derived,
        "resources": resources,
        # DECLARED, so a reader can tell "this plane is empty" from "I did not look".
        "absent": absent,
    }


def existing(root: Path) -> list[Path]:
    return sorted(Path(root).glob(f"*{EXT}"))


def target(root: Path, name: str | None = None) -> Path:
    """Where to write. An existing `*.mac` is refreshed in place; its NAME is the author's."""
    found = existing(root)
    if name:
        return Path(root) / f"{name}{EXT}"
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise SystemExit(
            f"could not run: {root} carries {len(found)} '*{EXT}' files "
            f"({', '.join(p.name for p in found)}) — a container has exactly one description"
        )
    meta = {}
    mp = Path(root) / "mac.project.yaml"
    if mp.is_file():
        meta = (yaml.safe_load(mp.read_text(encoding="utf-8")) or {}).get("metadata") or {}
    return Path(root) / f"{meta.get('dataset') or Path(root).name}{EXT}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--name", default=None, help=f"basename for a NEW description (extension is {EXT})")
    ap.add_argument("--check", action="store_true", help="re-derive and refuse if it has drifted")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2

    desc = describe(root)
    n = sum(desc["counts"].values())
    if n == 0:
        print(
            f"could not run: {root} carries no MAC component under any declared plane — "
            f"0 described is not the same as an empty ontology",
            file=sys.stderr,
        )
        return 2

    if a.check:
        found = existing(root)
        if not found:
            print(f"FAIL: mac_resources — {root.name} has no '*{EXT}' description", file=sys.stderr)
            return 1
        if len(found) > 1:
            print(
                f"FAIL: mac_resources — {len(found)} '*{EXT}' files; a container has exactly one",
                file=sys.stderr,
            )
            return 1
        on_disk = yaml.safe_load(found[0].read_text(encoding="utf-8")) or {}
        drift = []
        if on_disk.get("identity", {}).get("tree_hash") != desc["identity"]["tree_hash"]:
            drift.append("tree_hash — the bundle changed since this was written")
        if on_disk.get("identity", {}).get("grammar_id") != desc["identity"]["grammar_id"]:
            drift.append(
                f"grammar_id — described under {on_disk.get('identity', {}).get('grammar_id')}, "
                f"now {desc['identity']['grammar_id']}"
            )
        if on_disk.get("counts") != desc["counts"]:
            drift.append(f"counts — {on_disk.get('counts')} != {desc['counts']}")
        if drift:
            for d in drift:
                print(f"  [DRIFT] {d}")
            print(
                f"\nFAIL: mac_resources — {found[0].name} no longer describes this bundle "
                f"({len(drift)} difference(s) over {n} component(s) re-derived); regenerate it"
            )
            return 1
        print(
            f"PASS: mac_resources — {found[0].name} still describes this bundle "
            f"({n} component(s) re-derived, tree_hash and grammar_id match)"
        )
        return 0

    out = target(root, a.name)
    out.write_text(
        "# GENERATED by " + GENERATOR + " — do not edit; regenerate.\n"
        "# The ontology's resource description. The BASENAME is yours; the extension is fixed.\n"
        "# A host opens a directory by globbing '*" + EXT + "': exactly one match is this ontology.\n"
        + yaml.safe_dump(desc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(
        f"wrote {out.relative_to(root)} — {n} component(s): "
        + ", ".join(f"{k} {v}" for k, v in desc["counts"].items())
    )
    return 0


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "b"
        (root / "ontology" / "concepts").mkdir(parents=True)
        (root / "data" / "datasets").mkdir(parents=True)
        (root / "mac.project.yaml").write_text(
            "metadata:\n  data_domain: dom\n  dataset: ds\n  label: DS\n", encoding="utf-8"
        )
        (root / "ontology" / "concepts" / "thing.yaml").write_text(
            "concept:\n  name: Thing\n  class: entity\n  definition: A thing.\n", encoding="utf-8"
        )
        (root / "data" / "datasets" / "facts.yaml").write_text(
            "table:\n  name: facts\n  schema: wh\n", encoding="utf-8"
        )

        # 1 · it writes, and the basename is the author's
        if main_argv([str(root), "--name", "anything"]) != 0:
            failures.append("writing with an explicit name failed")
        if not (root / f"anything{EXT}").is_file():
            failures.append(f"anything{EXT} was not written")

        # 2 · a fresh description passes --check
        if main_argv([str(root), "--check"]) != 0:
            failures.append("a freshly written description did not pass --check")

        # 3 · the id comes from the component's OWN declaration, not its filename
        d = yaml.safe_load((root / f"anything{EXT}").read_text(encoding="utf-8"))
        ids = {r["id"] for r in d["resources"]}
        if "Thing" not in ids:
            failures.append(f"concept id not read from its declaration: {ids}")

        # 4 · DRIFT: add a component, and --check must refuse
        (root / "ontology" / "concepts" / "other.yaml").write_text(
            "concept:\n  name: Other\n  class: entity\n", encoding="utf-8"
        )
        if main_argv([str(root), "--check"]) == 0:
            failures.append("mutant not caught: a new component did not register as drift")

        # 5 · regenerating clears it
        main_argv([str(root)])
        if main_argv([str(root), "--check"]) != 0:
            failures.append("regenerating did not clear the drift")

        # 6 · TWO descriptions is ambiguous and must be refused, never guessed
        (root / f"second{EXT}").write_text("spec_version: x\n", encoding="utf-8")
        if main_argv([str(root), "--check"]) == 0:
            failures.append("mutant not caught: two descriptions were accepted")
        (root / f"second{EXT}").unlink()

        # 7 · a directory with no components must refuse, not write an empty description
        empty = Path(tmp) / "empty"
        empty.mkdir()
        if main_argv([str(empty)]) != 2:
            failures.append("an empty directory did not exit 2")

    total = 8
    if failures:
        print(f"FAIL: mac_resources self-test — {len(failures)} of {total} failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(
        f"PASS: mac_resources self-test — {total}/{total} (arbitrary basename, fixed extension, "
        f"ids read from declarations, drift refused, two descriptions refused, empty refused)"
    )
    return 0


def main_argv(argv: list[str]) -> int:
    """Run main() with a given argv. Used by the self-test; keeps main() the single entry point."""
    import contextlib
    import io as _io

    saved = sys.argv
    sys.argv = ["mac_resources.py", *argv]
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return main()
    finally:
        sys.argv = saved


if __name__ == "__main__":
    raise SystemExit(main())
