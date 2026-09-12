#!/usr/bin/env python3
"""Assemble the OBJECT INDEX for a per-source MAC project — the object-centric model the
wiki navigates by. DETERMINISTIC + IDEMPOTENT: no LLM, no AWS; derived purely from the
authored descriptors + the lineage flows + the DQ register. Re-running the harvest re-emits
the SAME object graph (only the authored prose inside each descriptor can drift).

An OBJECT is a relation. The chain the system enforces is

    raw source -> transformation -> dataset -> ontology concept

and the TRANSFORMATION is strictly 1:1 with the dataset it produces, so it FOLDS INTO that
dataset as view tabs ('cleaning' = the transformation narrative, 'sql' = its realization)
rather than becoming an object of its own — one dataset object carries the whole pipeline.
The wiki presents the chain as a strip on each data-plane object (see ObjectsView ChainStrip);
the 'cleaning' KEY is the wire contract and is labelled "Transformation" in the UI.

  kind      views (only those that exist)                            links
  dataset   doc · schema · sample · cleaning · sql · lineage · qual  sources[] (upstream)
  source    doc · schema(yaml) · quality · lineage                   feeds[]   (downstream)
  lookup    doc · data(csv) · schema(yaml)                —
  concept   doc · schema(yaml) · rules · chain          grounds[] (the chain, embedded)

The 'chain' view is the ONTOLOGY end of that same chain, read backwards: a concept carries
`grounds[]` = the datasets it is grounded on, each already resolved to its transformation and its
raw sources. It is resolved HERE rather than in the UI because the wiki's Ontology nav filters the
DATA plane out of the object list — a concept page has no dataset object to look up at render time.

Emits <out>/objects.json = {objects:[...]}; ORDER is stable (sorted) so a byte-diff of two
runs over the same descriptors is empty.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import yaml

try:
    from sdk.project import er_model, lineage_graph, ontology_quality, vocabulary
    from sdk.project import questions as _questions
except ImportError:  # when objects.py is run as a standalone script
    import er_model
    import lineage_graph
    import ontology_quality
    import questions as _questions
    import vocabulary


def _load(p: Path):
    try:
        return yaml.safe_load(p.read_text())
    except Exception:
        return None


def _rel_bare(rel: str) -> str:
    return str(rel or "").split(".")[-1]


def _emit_ontology_sme_md(sme, odir, label):
    """Project the ontology SME questions into the SAME prioritised-table markdown the DATA
    SME-QUESTIONS.md uses (rendered by the same DocPane), so both SME lists read identically.
    Grouped high/medium/low; each question links to its concept. In sync (re-projected each run)."""
    _pipe = "\\|"

    def esc(x, n):
        return str(x or "").replace("|", _pipe)[:n]

    def prio(q):
        return q.get("severity") or {
            "identity": "high",
            "ratification": "high",
            "aggregation": "medium",
            "enumeration": "medium",
            "confirm-rule": "low",
        }.get(q.get("kind"), "medium")

    body = [
        f"The open **SME sign-offs** the ontology surfaces — {len(sme)} questions, one per concept "
        f"needing ratification (confirm a concept or rule, an aggregation rule, an enum domain, an "
        f"identity key). Prioritised by severity; each links to its concept. Projected from "
        f"ontology_quality.json, so it stays in sync.",
        "",
    ]
    for sev in ("high", "medium", "low"):
        rows = [q for q in sme if prio(q) == sev]
        if not rows:
            continue
        body += [
            f"## {sev.title()} priority — {len(rows)} question(s)",
            "",
            "| ask | concept | kind | status |",
            "|---|---|---|---|",
        ]
        for q in rows:
            cid = q.get("concept") or ""
            link = f"[{esc(q.get('concept_title') or cid, 40)}](concepts/{cid}.md)" if cid else "—"
            body.append(
                f"| {esc(q.get('question'), 150)} | {link} | {esc(q.get('kind'), 20)} "
                f"| {esc(q.get('current'), 12)} |"
            )
        body += [""]
    fm = (
        "---\ntype: Doc\ntitle: SME questions — ontology\n"
        f"description: {len(sme)} concept sign-offs awaiting SME\ntags:\n- {label}\n- sme-questions\n---\n"
    )
    (odir / "SME-QUESTIONS.md").write_text(fm + "\n" + "\n".join(body))


def grounded_relations(concept: dict) -> list[dict]:
    """The relations a concept grounds on, from EITHER grounding shape.

    `sources[]` is the binding; `table` is legacy and still accepted — the grammar says so in its
    own description as of 0.1.14. Readers that honoured only `sources[]` linked a legacy-keyed
    bundle to NOTHING: measured, 13 of one bundle's datasets carried a concept link and 0 of
    another's did, purely on which key the author had used. This is the fifth and sixth site in this
    estate with that assumption, which is why it is a named function rather than three more inline
    fallbacks.
    """
    g = concept.get("grounding") or {}
    srcs = list(g.get("sources") or [])
    if not srcs and g.get("table"):
        srcs = [{"relation": g["table"]}]
    return srcs


def build_objects(data_dir, ontology_concepts_dir, lineage=None, issues=None, out_dir=None) -> dict:
    data_dir = Path(data_dir)
    sources = {p.stem: _load(p) or {} for p in sorted((data_dir / "sources").glob("*.yaml"))}
    transforms = {p.stem: _load(p) or {} for p in sorted((data_dir / "transforms").glob("*.yaml"))}
    datasets = {p.stem: _load(p) or {} for p in sorted((data_dir / "datasets").glob("*.yaml"))}
    # RECURSIVE. This globbed "*.yaml" — flat only — so a bundle that files its concepts by domain
    # (`ontology/concepts/finance/revenue.yaml`) projected ZERO concepts and the console rendered an
    # empty ontology. Measured: the reference bundle keeps 22 concepts flat and projected fine,
    # while both bundles shipped with the standard nest theirs (13 and 8) and projected nothing.
    # Nothing reported an error — an empty index is indistinguishable from an empty ontology, which
    # is the shape of every defect in this estate.
    concepts = (
        {p.stem: _load(p) or {} for p in sorted(Path(ontology_concepts_dir).rglob("*.yaml"))}
        if ontology_concepts_dir and Path(ontology_concepts_dir).exists()
        else {}
    )
    # stem -> the concept's REAL path, which is not always flat. `paths.schema` was built as
    # f"ontology/concepts/{stem}.yaml", so a nested concept was indexed at a path that does not
    # exist and the console answered "no such source file: ontology/concepts/revenue.yaml" for a
    # file sitting at ontology/concepts/finance/revenue.yaml. The doc IS flat — that is where the
    # page builder writes it — so only the schema path needed the truth.
    _cdir = Path(ontology_concepts_dir) if ontology_concepts_dir else None
    concept_schema_path = (
        {
            p.stem: f"ontology/concepts/{p.relative_to(_cdir).as_posix()}"
            for p in sorted(_cdir.rglob("*.yaml"))
        }
        if _cdir and _cdir.exists()
        else {}
    )
    lookups_csv = (
        sorted((data_dir / "lookups").glob("*.csv")) if (data_dir / "lookups").exists() else []
    )
    issues = issues or []

    # which .sql realizations exist (a transform view is only offered when its sql is present)
    sql_stems = {p.stem for p in (data_dir / "transforms").glob("*.sql")}
    # baked samples — datasets: <name>.sample.csv (from the served view); sources: <name>.src.sample.csv
    # (from the raw table). Offered as the object's Sample view.
    _sdir = data_dir / "samples"
    dataset_sample_stems = (
        {
            p.name[: -len(".sample.csv")]
            for p in _sdir.glob("*.sample.csv")
            if not p.name.endswith(".src.sample.csv")
        }
        if _sdir.exists()
        else set()
    )
    source_sample_stems = (
        {p.name[: -len(".src.sample.csv")] for p in _sdir.glob("*.src.sample.csv")}
        if _sdir.exists()
        else set()
    )

    # lineage: relation -> flow; source-short -> flows consuming it
    l_by_rel = {f.get("transform"): f for f in (lineage or [])}
    l_by_src: dict = {}
    for f in lineage or []:
        for s in f.get("sources") or []:
            l_by_src.setdefault(s.get("short"), []).append(f.get("transform") or "")

    # dataset stem -> its transform stem (via derived_from.pipeline) + reverse (source -> feeding datasets)
    ds_transform: dict = {}
    for dstem, ds in datasets.items():
        pipe = (ds.get("derived_from") or {}).get("pipeline")
        tstem = Path(str(pipe)).stem if pipe else (dstem if dstem in transforms else None)
        if tstem:
            ds_transform[dstem] = tstem
    src_feeds: dict = {}
    for dstem, tstem in ds_transform.items():
        drel = (
            _rel_bare(((transforms.get(tstem) or {}).get("produces") or {}).get("relation"))
            or dstem
        )
        for inp in (transforms.get(tstem) or {}).get("inputs") or []:
            desc = inp.get("descriptor") if isinstance(inp, dict) else None
            if desc and "/sources/" in str(desc):
                src_feeds.setdefault(Path(str(desc)).stem, []).append(drel)

    # DQ findings grouped to a table (by explicit `table` else column-overlap is left to the register)
    # Quality findings map to their RAW SOURCE table via the dashboard projection (finding.table,
    # derived from the resolution map's locus). Group finding ids per table -> the per-source Quality tab.
    # ---- TREATS: findings this dataset's transform RESOLVES ------------------------------------
    # The register binds a finding to the RAW table it was found in, so a finding surfaces on the
    # SOURCE page. But "what did we do about it" lives in impurity_resolution_map.yaml, which names the
    # TRANSFORM that treats it — and that was projected nowhere. A dataset page could therefore carry a
    # DISTINCT put there specifically to treat a defect, and say nothing about the defect. This closes
    # the loop from the other end: the issue is on the source, the treatment is on the dataset, and each
    # points at the other.
    treats_by_transform: dict = {}
    _resmap = Path(data_dir) / "quality" / "impurity_resolution_map.yaml"
    if _resmap.exists():
        try:
            for r in (yaml.safe_load(_resmap.read_text()) or {}).get("resolutions") or []:
                for tr in r.get("resolving_transforms") or []:
                    treats_by_transform.setdefault(tr, []).append(
                        {
                            "id": r.get("finding_id"),
                            "coverage": r.get("coverage"),
                            "guarantee": r.get("guarantee"),
                        }
                    )
        except Exception:
            pass

    q_by_table: dict = {}
    _dash = Path(data_dir) / "quality" / "dq_dashboard.json"
    if _dash.exists():
        try:
            for f in json.loads(_dash.read_text()).get("findings") or []:
                if f.get("table"):
                    q_by_table.setdefault(f["table"], []).append(f.get("id"))
        except Exception:
            pass

    # ---- ONTOLOGY EDGES -> concept correlations (the relationship projection) --------------------
    # edges.yaml (concept->concept physical FK joins) is the authoritative link source. Project it
    # onto each concept object as joins{out,in} — a REVERSE index, so BOTH ends see the relationship
    # (out = this concept references others; in = others reference this concept).
    name_to: dict = {}  # concept.name / stem -> {stem, title}
    for _cs, _c in concepts.items():
        _con = _c.get("concept") or {}
        _title = _con.get("label") or _con.get("name") or _cs
        name_to.setdefault(_cs, {"stem": _cs, "title": _title})
        if _con.get("name"):
            name_to[_con["name"]] = {"stem": _cs, "title": _title}

    def _join_cols(jr):  # "relA.from_col = relB.to_col" -> (from_col, to_col)
        try:
            lhs, rhs = [s.strip() for s in str(jr).split("=", 1)]
            return lhs.split(".")[-1], rhs.split(".")[-1]
        except Exception:
            return None, None

    _edges_yaml = (
        Path(ontology_concepts_dir).parent / "edges.yaml" if ontology_concepts_dir else None
    )
    ont_edges = (
        ((_load(_edges_yaml) or {}).get("edges") or [])
        if (_edges_yaml and _edges_yaml.exists())
        else []
    )
    joins: dict = {}  # stem -> {"out": [...], "in": [...]}
    for e in ont_edges:
        ep = e.get("endpoints") or {}
        fo = name_to.get((ep.get("from") or {}).get("concept"))
        to = name_to.get((ep.get("to") or {}).get("concept"))
        if not fo or not to:
            continue
        fcol, tcol = _join_cols(e.get("join_rule"))
        jr = e.get("join_rule")
        joins.setdefault(fo["stem"], {"out": [], "in": []})["out"].append(
            {"concept": to["stem"], "title": to["title"], "on": fcol, "join_rule": jr}
        )
        joins.setdefault(to["stem"], {"out": [], "in": []})["in"].append(
            {"concept": fo["stem"], "title": fo["title"], "on": tcol, "join_rule": jr}
        )
    for st in joins:  # stable order for the drift-guard
        joins[st]["out"].sort(key=lambda x: (x["title"], x.get("on") or ""))
        joins[st]["in"].sort(key=lambda x: (x["title"], x.get("on") or ""))

    def _views(kind, paths, lineage_flag, quality):
        order = {
            "dataset": ["doc", "schema", "sample", "cleaning", "sql", "lineage", "quality"],
            "source": ["doc", "schema", "sample", "lineage", "quality"],
            "lookup": ["doc", "data", "schema"],
            "concept": ["doc", "schema"],
            "quality": ["dashboard", "register", "health"],
            "compile": ["dashboard"],
            "diagnostics": ["dashboard"],
            "knowledge": ["doc"],
        }[kind]
        have = {
            "doc": bool(paths.get("doc")),
            "schema": bool(paths.get("schema")),
            "sql": bool(paths.get("sql")),
            "data": bool(paths.get("data")),
            "sample": bool(paths.get("sample")),  # a baked 10-row sample of the produced view
            "cleaning": bool(
                paths.get("cleaning")
            ),  # the TRANSFORMATION step (labelled so in the UI)
            "dashboard": bool(paths.get("dashboard")),
            "register": bool(paths.get("register")),
            "health": bool(paths.get("health")),
            "lineage": bool(lineage_flag),
            "quality": bool(quality),
        }
        return [v for v in order if have.get(v)]

    objects = []

    # ---- DATASET objects (transform folded in as the sql view) ----
    # ---- dataset -> the CONCEPTS that bind it (the 4th chain link, reverse-indexed) --------------
    # A concept declares its grounding.sources[].relation, so concept -> dataset is readable; the
    # reverse is not, which left the data plane unable to answer "who uses this view?" — the exact
    # question you must answer before changing or retiring one. Index it here, once, while the
    # concepts are already loaded. Matched on the bare relation name so it holds whether the concept
    # writes `acme2.dim_model` or the stem.
    ds_concepts: dict = {}
    for cstem, c in concepts.items():
        ctitle = (
            (c.get("concept") or {}).get("label") or (c.get("concept") or {}).get("name") or cstem
        )
        seen_here = set()
        # BOTH grounding shapes. Reading only `sources[]` meant a concept using the legacy `table`
        # key was linked to NO dataset — measured: 13 of acme2's datasets carry a concept link
        # because it uses `sources[]`, and 0 of tpch's do because it uses `table`. The dataset
        # descriptors declared `grounded_by_concepts` the whole time; nothing read it, and nothing
        # read the legacy key either, so the data plane and the ontology plane sat unconnected.
        # Fifth reader in this estate with this assumption; the grammar now documents `table` as
        # legacy-but-accepted, and a reader must honour both.
        for s in grounded_relations(c):
            rel = str((s or {}).get("relation") or "")
            if not rel or "/" in rel:  # skip authored-lookup paths (data/lookups/*.csv)
                continue
            bare = _rel_bare(rel)
            if bare in seen_here:  # a concept may ground the same relation twice
                continue
            seen_here.add(bare)
            ds_concepts.setdefault(bare, []).append({"id": cstem, "title": ctitle})
    for k in ds_concepts:  # stable order — two runs byte-match
        ds_concepts[k].sort(key=lambda x: x["id"])

    # ---- the FORWARD twin: bare relation -> that dataset's own provenance (title, transformation,
    # raw sources), filled in as the dataset objects are built below. A concept then copies the
    # entries for the relations it grounds on, so its page carries the WHOLE chain
    # (raw source -> transformation -> dataset -> concept) without resolving anything at render time.
    ds_chain: dict = {}

    for dstem, ds in datasets.items():
        tstem = ds_transform.get(dstem)
        tr = transforms.get(tstem) or {}
        # no source literal: fall back to the dataset's OWN declared schema, else the bare stem
        _dsch = (ds.get("table") or {}).get("schema")
        relation = (tr.get("produces") or {}).get("relation") or (
            f"{_dsch}.{dstem}" if _dsch else dstem
        )
        tbl = ds.get("table") or {}
        src_ids = sorted(
            {
                Path(str(inp.get("descriptor"))).stem
                for inp in (tr.get("inputs") or [])
                if isinstance(inp, dict) and "/sources/" in str(inp.get("descriptor") or "")
            }
        )
        # EVERY input, not just the raw sources: a transform may also read another DATASET
        # (dim_country_register <- dim_brand_country_code) or an ATTRIBUTED LOOKUP (authored_seed,
        # e.g. iso_3166.lookup) — the seeds that carry "how the values came to being". Keeping only
        # the /sources/ ones made those dependencies invisible in the whole-bundle graph.
        inputs = []
        for inp in tr.get("inputs") or []:
            if not isinstance(inp, dict):
                continue
            desc, kind = str(inp.get("descriptor") or ""), str(inp.get("kind") or "")
            if "/sources/" in desc:
                inputs.append({"kind": "source", "ref": Path(desc).stem})
            elif kind == "dataset":
                inputs.append({"kind": "dataset", "ref": _rel_bare(str(inp.get("relation") or ""))})
            elif "/lookups/" in desc:
                inputs.append({"kind": "lookup", "ref": Path(desc).stem})
        _seen_i = set()
        inputs = [
            i
            for i in inputs
            if not ((i["kind"], i["ref"]) in _seen_i or _seen_i.add((i["kind"], i["ref"])))
        ]
        inputs.sort(key=lambda i: (i["kind"], i["ref"]))
        quality = q_by_table.get(dstem, []) + q_by_table.get(_rel_bare(relation), [])
        paths = {
            "doc": f"data/datasets/{dstem}.md",
            "schema": f"data/datasets/{dstem}.yaml",
            "sample": f"data/samples/{dstem}.sample.csv" if dstem in dataset_sample_stems else None,
            "sql": f"data/transforms/{tstem}.sql" if (tstem in sql_stems) else None,
            "cleaning": f"data/transforms/{tstem}.md"
            if tstem
            else None,  # the transformation (why/how)
            "transform": f"data/transforms/{tstem}.yaml" if tstem else None,
        }
        # same key as ds_concepts (the BARE relation name) so the two indexes agree
        ds_chain[_rel_bare(relation)] = {
            "id": _rel_bare(relation),
            "title": tbl.get("name") or dstem,
            "transform": tstem,
            "sources": src_ids,
            "inputs": inputs,
        }
        objects.append(
            {
                "id": _rel_bare(relation),
                "kind": "dataset",
                "plane": "data",
                "title": tbl.get("name") or dstem,
                "relation": relation,
                "views": _views("dataset", paths, relation in l_by_rel, quality),
                "paths": paths,
                "lineage": relation in l_by_rel,
                "quality": quality,
                "sources": src_ids,
                "inputs": inputs,
                "transform": tstem,
                # the defects this dataset's transform exists to treat (impurity_resolution_map.yaml)
                "treats": sorted(
                    treats_by_transform.get(tstem or dstem, [])
                    or treats_by_transform.get(dstem, []),
                    key=lambda x: str(x["id"]),
                ),
                # the 4th chain link: which ontology concepts bind this dataset
                "concepts": ds_concepts.get(_rel_bare(relation), []),
            }
        )

    # ---- SOURCE objects ----
    for sstem, src in sources.items():
        tbl = src.get("table") or {}
        quality = q_by_table.get(sstem, [])
        paths = {
            "doc": f"data/sources/{sstem}.md",
            "schema": f"data/sources/{sstem}.yaml",
            "sample": f"data/samples/{sstem}.src.sample.csv"
            if sstem in source_sample_stems
            else None,
        }
        objects.append(
            {
                "id": sstem,
                "kind": "source",
                "plane": "data",
                "title": tbl.get("name") or sstem,
                "relation": f"{tbl.get('schema', '')}.{tbl.get('name', sstem)}",
                "views": _views("source", paths, bool(l_by_src.get(sstem)), quality),
                "paths": paths,
                "lineage": bool(l_by_src.get(sstem)),
                "quality": quality,
                "feeds": sorted(set(src_feeds.get(sstem, []))),
            }
        )

    # ---- LOOKUP objects ----
    for csv in lookups_csv:
        stem = csv.stem
        yaml_sib = data_dir / "lookups" / f"{stem}.yaml"
        paths = {
            "doc": f"data/lookups/{stem}.md",
            "data": f"data/lookups/{csv.name}",
            "schema": f"data/lookups/{stem}.yaml" if yaml_sib.exists() else None,
        }
        objects.append(
            {
                "id": stem,
                "kind": "lookup",
                "plane": "data",
                "title": stem,
                "relation": None,
                "views": _views("lookup", paths, False, []),
                "paths": paths,
                "lineage": False,
                "quality": [],
            }
        )

    # ---- SOURCE KNOWLEDGE — what the vendor's documents SAY, structured and quoted. The documents
    # themselves stay hidden by design; this is the knowledge taken from them.
    _kidx = Path(data_dir).parent / "knowledge" / "index.md"
    if _kidx.exists():
        for _kp in sorted((Path(data_dir).parent / "knowledge").glob("*.md")):
            if _kp.name == "index.md":
                continue
            kpaths = {"doc": f"knowledge/{_kp.name}"}
            objects.append(
                {
                    "id": f"knowledge_{_kp.stem}",
                    "kind": "knowledge",
                    "plane": "ontology",
                    "title": _kp.stem.replace("-", " ").title(),
                    "relation": None,
                    "views": _views("knowledge", kpaths, False, []),
                    "paths": kpaths,
                    "lineage": False,
                    "quality": [],
                }
            )

    # ---- THE COMPILE — the WHOLE-BUNDLE verdict, read from the compile record the projection gate
    # writes (`sdk/cli/harvest.py::compile_gate` -> <bundle>/compile.json, the shape single-homed in
    # meaning-as-code `mac_compile.payload`). Distinct from Semantic Diagnostics below, which is ONE
    # phase's findings (facts stated twice): this is every code in the closed taxonomy at once —
    # what is defined, what is defined redundantly, what is not defined — plus the verdict and which
    # checks were able to establish it. It answers "what is the state of the ontology" without a
    # terminal, which is the whole reason the record is persisted rather than printed.
    #
    # PROJECTED WHENEVER THE RECORD EXISTS — including when the verdict is DOES_NOT_COMPILE. A page
    # that appears only for a clean bundle would hide exactly the state a reader needs to see.
    _comp = Path(data_dir).parent / "compile.json"
    if _comp.exists():
        cpaths = {"dashboard": "compile.json"}
        objects.append(
            {
                # PLANE `bundle`, not `ontology` — the comment above already called this the WHOLE-BUNDLE
                # verdict while the code filed it under one plane. It reports on the data plane, the
                # governance files and the testing corpus too; nesting it under Ontology mis-states its
                # scope and hides it behind a plane a reader may not open.
                "id": "mac_compile",
                "kind": "compile",
                "plane": "bundle",
                "title": "Compiler Report",
                "relation": None,
                "views": _views("compile", cpaths, False, []),
                "paths": cpaths,
                "lineage": False,
                "quality": [],
            }
        )

    # ---- SEMANTIC DIAGNOSTICS — the compiler's findings. Distinct from Data Quality: DQ is about the
    # SOURCE (what the data is like), this is about the MODEL (what the ontology says about itself).
    # Written by the projector's semantic phase, so it is as fresh as the pages beside it.
    _diag = Path(data_dir).parent / "ontology" / "diagnostics.json"
    if _diag.exists():
        dpaths = {"dashboard": "ontology/diagnostics.json"}
        objects.append(
            {
                "id": "semantic_diagnostics",
                "kind": "diagnostics",
                "plane": "ontology",
                "title": "Semantic Diagnostics",
                "relation": None,
                "views": _views("diagnostics", dpaths, False, []),
                "paths": dpaths,
                "lineage": False,
                "quality": [],
            }
        )

    # ---- DATA-QUALITY overview object (one per source): Overview (0-issues-overview.md,
    # with the resolved/partial/gap tally + the resolving transform per finding) + full Register.
    if (data_dir / "quality" / "data_quality_register.yaml").exists():
        qpaths = {
            "dashboard": "data/quality/dq_dashboard.json",
            "register": "data/quality/data_quality_register.yaml",
            "health": "data/quality/PLANE-HEALTH.md",
        }
        objects.append(
            {
                "id": "data_quality",
                "kind": "quality",
                "plane": "data",
                "title": "Data Quality",
                "relation": None,
                "views": _views("quality", qpaths, False, []),
                "paths": qpaths,
                "lineage": False,
                "quality": [],
            }
        )
        # the DATA + DATA-QUALITY SME sign-offs (projected SME-QUESTIONS.md) — a doc object so it
        # sits under the Quality nav's Data branch, symmetric with the ontology's SME Questions.
        if (data_dir / "quality" / "SME-QUESTIONS.md").exists():
            objects.append(
                {
                    "id": "sme_questions_data",
                    "kind": "dqquestions",
                    "plane": "data",
                    "title": "SME Questions",
                    "relation": None,
                    "views": ["doc"],
                    "paths": {"doc": "data/quality/SME-QUESTIONS.md"},
                    "lineage": False,
                    "quality": [],
                }
            )

    # ---- DECISION objects (ADRs) — the AUTHORED rationale behind the bundle's shape. These are the
    # "cause" the descriptors are only the "consequence" of, and they were reachable only through the raw
    # file browser, which the SME audience never opens. Surfaced as their own objects so the reasoning is
    # navigable. The projector NEVER writes them (they are hand-authored); it only indexes what is there.
    _dec_dir = data_dir.parent / "decisions"
    if _dec_dir.exists():
        for p in sorted(_dec_dir.glob("*.md")):
            title = p.stem
            try:  # the H1 is the human title; fall back to the filename
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
            except Exception:
                pass
            objects.append(
                {
                    "id": p.stem,
                    "kind": "decisions",
                    "plane": "data",
                    "title": title,
                    "relation": None,
                    "views": ["doc"],
                    "paths": {"doc": f"decisions/{p.name}"},
                    "lineage": False,
                    "quality": [],
                }
            )

    # ---- INTERVENTIONS object — the manual-change protocol (projected from interventions/ledger.yaml).
    # Sits in the Manage nav beside Quality: autodiscovered work is self-documenting, manual work is not. ----
    _led = data_dir.parent / "interventions" / "LEDGER.md"
    if _led.exists():
        objects.append(
            {
                "id": "interventions",
                "kind": "interventions",
                "plane": "data",
                "title": "Interventions",
                "relation": None,
                "views": ["doc"],
                "paths": {"doc": "interventions/LEDGER.md"},
                "lineage": False,
                "quality": [],
            }
        )

    # ---- CONCEPT objects (ontology plane) ----
    for cstem, c in concepts.items():
        con = c.get("concept") or {}
        contract = c.get("contract") or {}
        paths = {
            "doc": f"ontology/concepts/{cstem}.md",
            "schema": concept_schema_path.get(cstem, f"ontology/concepts/{cstem}.yaml"),
        }
        # FULL rule logic (id/subject/kind/confidence/scope/binds + when/then/never) so the concept
        # page can render each rule INLINE — not click-through-only. The trimmed shape used to drop the
        # actual logic, hiding the answering playbook one click away on the per-rule page.
        rules = [
            {
                "id": r.get("id"),
                "subject": r.get("subject") or r.get("then") or "",
                "kind": str(r.get("kind") or "").split(".")[-1],
                "confidence": r.get("confidence"),
                "scope": r.get("scope"),
                "binds": r.get("binds") or [],
                "when": r.get("when"),
                "then": r.get("then"),
                "never": r.get("never"),
            }
            for r in (contract.get("rules") or [])
        ]
        # ---- this concept's PROVENANCE CHAIN, read from the ontology end: for every relation the
        # concept grounds on, the dataset it is, the transformation that built it, and the raw
        # sources that fed it. Matched on the bare relation name (same convention as ds_concepts);
        # authored-lookup paths (data/lookups/*.csv) are not relations and are skipped. A grounding
        # with no dataset of its own still yields a row (honest > hidden) — just without a
        # transformation or raw sources to name.
        grounds, seen_g = [], set()
        for s in grounded_relations(c):
            rel = str((s or {}).get("relation") or "")
            if not rel or "/" in rel:
                continue
            bare = _rel_bare(rel)
            if bare in seen_g:  # a concept may ground the same relation twice
                continue
            seen_g.add(bare)
            ch = ds_chain.get(bare)
            grounds.append(
                {
                    "id": bare,
                    "title": (ch or {}).get("title") or bare,
                    "transform": (ch or {}).get("transform"),
                    "sources": list((ch or {}).get("sources") or []),
                }
            )
        grounds.sort(key=lambda g: g["id"])  # stable order — two runs byte-match
        obj = {
            "id": cstem,
            "kind": "concept",
            "plane": "ontology",
            "title": con.get("label") or con.get("name") or cstem,
            "relation": None,
            "class": con.get("class"),  # measure/reference/… — drives the class icon + type badge
            # extra view tabs — this concept's rules overview, then its provenance chain
            "views": (
                _views("concept", paths, False, [])
                + (["rules"] if rules else [])
                + (["chain"] if grounds else [])
            ),
            "paths": paths,
            "lineage": False,
            "quality": [],
            "joins": joins.get(cstem, {"out": [], "in": []}),
            # raw source -> transformation -> dataset -> THIS concept, one entry per grounding
            "grounds": grounds,
            "rules": rules,
        }
        # contract.no_probe_guarantee — the concept's agent-facing "how to answer" playbook. Carried so
        # the UI can surface it as a panel (it was dropped entirely from the render before).
        npg = contract.get("no_probe_guarantee")
        if npg:
            obj["no_probe_guarantee"] = npg
        objects.append(obj)
        # ---- RULE objects (single-homed rule pages) — NOT in the tree (kind not in KIND_ORDER),
        # but addressable, so the concept page's rule links resolve + open the full rule page.
        for r in (c.get("contract") or {}).get("rules") or []:
            rid = str(r.get("id", "rule")).replace("/", "_")
            objects.append(
                {
                    "id": f"rules/{rid}",
                    "kind": "rule",
                    "plane": "ontology",
                    "title": r.get("subject") or r.get("id") or rid,
                    "relation": None,
                    "parent": cstem,
                    "rule_kind": str(r.get("kind") or "").split(".")[-1],
                    "views": ["doc"],
                    "paths": {"doc": f"ontology/concepts/rules/{rid}.md"},
                    "lineage": False,
                    "quality": [],
                }
            )

    # ---- ONTOLOGY-QUALITY objects — TWO panel-2 entries, both over ontology_quality.json:
    #      the quality dashboard (score + findings) and the SME-question backlog. ----
    if concepts:
        objects.append(
            {
                "id": "ontology_quality",
                "kind": "ontquality",
                "plane": "ontology",
                "title": "Ontology Quality",
                "relation": None,
                "views": ["dashboard"],
                "paths": {"dashboard": "ontology/ontology_quality.json"},
                "lineage": False,
                "quality": [],
            }
        )
        objects.append(
            {
                "id": "sme_questions",
                "kind": "smeq",
                "plane": "ontology",
                "title": "SME Questions",
                "relation": None,
                # SAME style as the data SME questions: a projected prioritised-table markdown doc,
                # rendered by the same DocPane (not a bespoke pane). Emitted at write time below.
                "views": ["doc"],
                "paths": {"doc": "ontology/SME-QUESTIONS.md"},
                "lineage": False,
                "quality": [],
            }
        )
        # ---- VOCABULARY object (the glossary: what every <source>.*/mac.* term means) ----
        objects.append(
            {
                "id": "vocabulary",
                "kind": "vocab",
                "plane": "ontology",
                "title": "Vocabulary",
                "relation": None,
                "views": ["ref"],
                "paths": {"ref": "ontology/vocabulary.json"},
                "lineage": False,
                "quality": [],
            }
        )

    # ---- QUESTION LIGHTHOUSE object (acceptance plane) — the per-ontology testing corpus:
    # the standard question catalog + captured verdicts (sdk/project/questions.py). Tagged
    # plane="acceptance" for its own physical bundle-plane dir, mirroring how ontquality/smeq/
    # vocab tag "ontology" for theirs. Offered only once the projector has actually run.
    if (data_dir.parent / "acceptance" / "questions_dashboard.json").exists():
        objects.append(
            {
                "id": "questions",
                "kind": "questions",
                "plane": "acceptance",
                "title": "Question Lighthouse",
                "relation": None,
                "views": ["dashboard"],
                "paths": {
                    "dashboard": "acceptance/questions_dashboard.json",
                    "corpus": "acceptance/questions.yaml",
                },
                "lineage": False,
                "quality": [],
            }
        )

    # stable order: plane, then kind, then id — so two runs byte-match
    _kind_ord = {
        "dataset": 0,
        "source": 1,
        "lookup": 2,
        "quality": 3,
        "questions": 4,
        "concept": 5,
        "ontquality": 6,
        "smeq": 7,
        "vocab": 8,
    }
    objects.sort(key=lambda o: (o["plane"], _kind_ord.get(o["kind"], 9), o["id"]))
    # globally-unique key (a raw table is legitimately both a data 'source' and an
    # ontology 'concept'; the frontend keys on this, displays `title`/`id`).
    for o in objects:
        o["key"] = f"{o['plane']}:{o['kind']}:{o['id']}"
    result = {
        "objects": objects,
        "counts": {
            k: sum(1 for o in objects if o["kind"] == k)
            for k in ("dataset", "source", "lookup", "quality", "concept")
        },
    }
    # ---- the WHOLE-BUNDLE lineage graph: every source, dataset and concept in ONE picture, with
    # the transformation folded into its dataset (1:1). Built from `objects` so it can never disagree
    # with the pages it links to. See sdk/project/lineage_graph.py for why the strand-at-a-time views
    # were not enough.
    lgraph = lineage_graph.build(objects)
    result["lineage_graph"] = lgraph
    # ---- the ENTITY-RELATIONSHIP model: entities with keys + relationships with authored CARDINALITY,
    # resolved to the exact join columns. See sdk/project/er_model.py — the crow's feet are the
    # cardinality authored in edges.yaml, not an inference.
    _dsrel = {
        stem: _rel_bare(
            ((transforms.get(ds_transform.get(stem)) or {}).get("produces") or {}).get("relation")
            or stem
        )
        for stem in datasets
    }
    result["er_model"] = er_model.build(datasets, concepts, ont_edges, _dsrel)
    if out_dir:
        (Path(out_dir) / "objects.json").write_text(json.dumps(result, indent=2, sort_keys=True))
        (Path(out_dir) / "lineage_graph.json").write_text(
            json.dumps(lgraph, indent=2, sort_keys=True)
        )
        if concepts:
            odir = Path(out_dir) / "ontology"
            odir.mkdir(parents=True, exist_ok=True)
            _oq = ontology_quality.build(concepts, datasets, ont_edges, root=Path(data_dir).parent)
            (odir / "ontology_quality.json").write_text(json.dumps(_oq, indent=2, sort_keys=True))
            # ALSO project the ontology SME questions as prioritised-table markdown — same style as the
            # data SME-QUESTIONS.md, rendered by the same DocPane (the smeq object points here).
            try:
                from sdk.project import source_ident as _si

                _lbl = _si.resolve(Path(data_dir).parent).label
            except Exception:
                # never assume a source: fall back to the bundle's own directory name
                _lbl = Path(data_dir).parent.name.upper()
            _emit_ontology_sme_md(_oq.get("sme_questions") or [], odir, _lbl)
        # ---- the TESTING corpus read-view. questions.py was NOT in the pipeline, so the dashboard
        # only refreshed when a run happened to call it — a freshly opened bundle reported
        # `with_oracle: 0` while 96 oracles sat on disk, i.e. the wiki said the corpus was ungradeable
        # when it was fully graded. Project it with everything else.
        with contextlib.suppress(Exception):
            _questions.build(Path(data_dir).parent)
        if concepts:
            (odir / "vocabulary.json").write_text(
                json.dumps(vocabulary.build(concepts, ont_edges), indent=2, sort_keys=True)
            )
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--ontology", default=None)
    ap.add_argument("--lineage", default=None, help="lineage.json (flows)")
    ap.add_argument("--register", default=None, help="data_quality_register.yaml")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lin = []
    if a.lineage:
        with open(a.lineage) as fh:
            lin = json.load(fh).get("flows", [])
    iss = []
    if a.register:
        with open(a.register) as fh:
            iss = (yaml.safe_load(fh) or {}).get("issues", [])
    r = build_objects(a.data, a.ontology, lineage=lin, issues=iss, out_dir=a.out)
    print(json.dumps(r["counts"]))
