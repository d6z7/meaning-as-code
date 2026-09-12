#!/usr/bin/env python3
"""Project the MAC DATA PLANE (data/{sources,transforms,datasets,quality}) into the
OKF/Markdown READ VIEW the wiki serves — so business users can BROWSE the harvest AND
see, for every recorded impurity, the transform that dissolves it.

Emits, cross-linked, into <out>/:
  sources/<t>.md      Source     raw columns + roles + confidence, → consuming transform(s) + its quality issues
  quality/<id>.md     DQ Issue   finding + handling + risk + **resolution** (resolving transform · guarantee · coverage chip)
  transforms/<t>.md   Transform  each rule (defect→rule→guarantee) + open (needs-SME) + **impurities it dissolves**, → sources/dataset
  datasets/<t>.md     Dataset    clean columns + roles + FKs, → transform → sources
  index.md            the data-plane map + resolution scoreboard (resolved / partial / gap)

Lineage follows the gold's real shape — a transform's `inputs[].descriptor` names its
source(s); a dataset's `derived_from.pipeline` names its transform — so names may differ
(dim_acme_lm_country → dim_country). The impurity→resolution cross-link is read from
`data/quality/impurity_resolution_map.yaml` (harvest finding → gold transform). Lifecycle /
confidence / severity / resolution ride as frontmatter `tags` so the read server renders
them as chips. Deterministic — no LLM, no AWS; safe to re-run any time.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
_COV_CHIP = {"resolved": "✓ resolved", "partial": "◐ partial", "gap": "⚠ open gap"}
_COV_ORDER = {"gap": 0, "partial": 1, "resolved": 2}


def _fm(d: dict) -> str:
    return "---\n" + yaml.safe_dump(d, sort_keys=False, allow_unicode=True) + "---\n"


def _load(p: Path):
    try:
        return yaml.safe_load(p.read_text())
    except Exception:
        return None


def _rel_bare_name(rel) -> str:
    """`acme2.dim_model` -> `dim_model` (the served view's bare name)."""
    return str(rel or "").split(".")[-1]


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", str(s or "issue"))


def _lineage_cols_md(f: dict) -> list:
    """Column-level lineage for one output relation (a lineage_project.py 'flow'):
    every (source column -> output column) edge + derived columns, badged by the closed kind vocab."""
    edges = f.get("edges") or []
    seeds = f.get("seeds") or []
    if not edges and seeds:
        # view-of-view: no raw-source column edges — a passthrough projection of another view.
        # (lineage_project mislabels the un-raw-sourced cols 'const'; the real provenance is upstream.)
        ups = ", ".join(f"`{s.get('name')}`" for s in seeds)
        cols = ", ".join(
            f"`{c.get('name')}`" for c in ((f.get("dataset") or {}).get("columns") or [])
        )
        return [
            "",
            "## Lineage",
            "",
            f"Passthrough projection of {ups} — columns {cols} are carried through unchanged. "
            f"See the upstream view's lineage for full column provenance.",
        ]
    body = [
        "",
        "## Lineage (column-level)",
        "",
        f"`{f.get('transform')}` · kinds: {f.get('kindl', '—')}",
        "",
        "| output column | ← from | rule | kind |",
        "|---|---|---|---|",
    ]
    for e in f.get("edges") or []:
        body.append(
            f"| `{e.get('to_col')}` | `{e.get('src_table')}.{e.get('src_col')}` "
            f"| {e.get('rule_id', '')} | {e.get('kind', '')} |"
        )
    for d in f.get("derived") or []:
        body.append(
            f"| `{d.get('to_col')}` | _{d.get('via', 'derived')}_ |  | {d.get('kind', '')} |"
        )
    return body


def build_data(data_dir, out_dir=None, lineage=None) -> dict:
    # ONE tree: projected md co-locate WITH the SSOT under data_dir/<type>/ (dim_country.md next to
    # dim_country.yaml). index + objects.json live at the project root (data_dir.parent). out_dir ignored.
    data_dir = Path(data_dir)
    out = data_dir
    root = data_dir.parent
    # DE-ACME (Phase 6): the source LABEL that badges every projected object (its frontmatter
    # `tags` + the index title) is read from mac.project.yaml, not hardcoded. (The lineage-format
    # descriptor in _lineage_cols_md used to read "ACME-style" — kept deliberately as a methodology
    # reference to the gold rather than a source identity. That held while projections stayed in one
    # private estate; it stopped holding the moment this projector wrote into a PUBLIC example
    # bundle, where an instance's name means nothing to the reader and is an operator handle in a
    # repo that must carry none. The heading is now plain "column-level".)
    from sdk.project import source_ident

    label = source_ident.resolve(root).label
    for sub in ("sources", "transforms", "datasets", "quality"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    sources = {p.stem: _load(p) or {} for p in sorted((data_dir / "sources").glob("*.yaml"))}
    transforms = {p.stem: _load(p) or {} for p in sorted((data_dir / "transforms").glob("*.yaml"))}
    datasets = {p.stem: _load(p) or {} for p in sorted((data_dir / "datasets").glob("*.yaml"))}
    reg = _load(data_dir / "quality" / "data_quality_register.yaml") or {}
    issues = (
        (reg.get("issues") or reg.get("findings") or []) if isinstance(reg, dict) else (reg or [])
    )
    resmap_raw = _load(data_dir / "quality" / "impurity_resolution_map.yaml") or {}
    resmap = {
        r.get("finding_id"): r for r in (resmap_raw.get("resolutions") or []) if r.get("finding_id")
    }
    # sibling ONTOLOGY plane (per-source MAC project) — for data↔ontology cross-links
    onto_dir = data_dir.parent / "ontology" / "concepts"
    concept_stems = {p.stem for p in onto_dir.glob("*.yaml")} if onto_dir.exists() else set()
    # column-level lineage (lineage_project.py flows), keyed for per-table rendering
    l_by_rel = {f.get("transform"): f for f in (lineage or [])}
    l_by_src: dict = {}
    for f in lineage or []:
        for s in f.get("sources") or []:
            l_by_src.setdefault(s.get("short"), []).append(f)
    {(tr.get("produces") or {}).get("relation"): tstem for tstem, tr in transforms.items()}

    # ---- lineage indices (gold shape: names differ across the source→transform→dataset chain) ----
    src_transforms: dict = {}  # source stem -> [transform stem consuming it]
    tr_sources: dict = {}  # transform stem -> [source stem]
    for tstem, tr in transforms.items():
        for inp in tr.get("inputs") or []:
            desc = inp.get("descriptor") if isinstance(inp, dict) else None
            if desc and "/sources/" in str(desc):
                sstem = Path(str(desc)).stem
                tr_sources.setdefault(tstem, []).append(sstem)
                src_transforms.setdefault(sstem, []).append(tstem)
    ds_transform: dict = {}  # dataset stem -> transform stem
    tr_datasets: dict = {}  # transform stem -> [dataset stem]
    for dstem, ds in datasets.items():
        pipe = (ds.get("derived_from") or {}).get("pipeline")
        tstem = Path(str(pipe)).stem if pipe else (dstem if dstem in transforms else None)
        if tstem:
            ds_transform[dstem] = tstem
            tr_datasets.setdefault(tstem, []).append(dstem)

    # ---- impurity→resolution cross-link ----
    tr_findings: dict = {}  # transform stem -> [(finding_id, resolution)]
    for fid, r in resmap.items():
        for t in r.get("resolving_transforms") or []:
            tr_findings.setdefault(t, []).append((fid, r))

    # associate each issue to a source table (explicit `table:` else column-name overlap)
    def _assoc(iss) -> str | None:
        if iss.get("table") in sources:
            return iss["table"]
        r = resmap.get(iss.get("id")) or {}
        loc = (
            str(r.get("locus", "")).split(".")[0].strip()
        )  # resolution map "table.column" -> table
        if loc in sources:
            return loc
        text = (str(iss.get("title", "")) + " " + str(iss.get("finding", ""))).lower()
        best, score = None, 0
        for stem, src in sources.items():
            cols = [str(c.get("name", "")).lower() for c in src.get("columns", []) or []]
            s = sum(1 for c in cols if c and c in text)
            if s > score:
                best, score = stem, s
        return best

    by_table: dict = {}
    _seen: dict = {}  # de-dupe colliding DQ ids (the register numbers per-table)
    for i, iss in enumerate(issues):
        base = _slug(iss.get("id") or f"issue-{i}")
        _seen[base] = _seen.get(base, 0) + 1
        iss["_id"] = base if _seen[base] == 1 else f"{base}-{_seen[base]}"
        iss["_table"] = _assoc(iss)
        by_table.setdefault(iss["_table"], []).append(iss)

    # ---- DQ Issue pages ----
    for iss in issues:
        sev, conf = iss.get("severity", "?"), iss.get("confidence", "?")
        res = resmap.get(iss.get("id"))
        cov = (res or {}).get("coverage")
        tags = [label, f"severity:{sev}", f"confidence:{conf}", "lifecycle:draft"]
        if cov:
            tags.append(f"resolution:{cov}")
        fm = {
            "type": "DQ Issue",
            "title": iss.get("title", iss["_id"]),
            "description": str(iss.get("finding", ""))[:200],
            "tags": tags,
        }
        body = [
            f"`{iss.get('id', '')}` · severity **{sev}** · confidence **{conf}**"
            + (f" · resolution **{_COV_CHIP.get(cov, cov)}**" if cov else ""),
            "",
            "## Finding",
            str(iss.get("finding", "—")),
            "",
            "## Current handling",
            str(iss.get("current_handling", "—")),
            "",
            "## Residual risk",
            str(iss.get("residual_risk", "—")),
            "",
            "## Sign-off required",
            str(iss.get("sme_owner", "—")),
        ]
        # resolution — the gold transform (if any) that dissolves this impurity
        if res:
            body += [
                "",
                "## Resolution",
                "",
                f"**{_COV_CHIP.get(cov, cov)}** — {res.get('guarantee', '')}",
            ]
            rts = res.get("resolving_transforms") or []
            if rts:
                body += [
                    "",
                    *(
                        f"- Dissolved by [{t}](../transforms/{t}.md)"
                        for t in rts
                        if t in transforms
                    ),
                    *(f"- Dissolved by `{t}`" for t in rts if t not in transforms),
                ]
            elif cov == "gap":
                body += [
                    "",
                    "_No transform in the copied gold dissolves this yet — an honest open gap._",
                ]
            if res.get("evidence"):
                body += ["", f"> evidence — {res['evidence']}"]
        if iss["_table"] in sources:
            body += ["", "## Table", f"- [{iss['_table']}](../sources/{iss['_table']}.md)"]
        (out / "quality" / f"{iss['_id']}.md").write_text(_fm(fm) + "\n" + "\n".join(body))

    # ---- Source pages ----
    for stem, src in sources.items():
        tbl, _meta = src.get("table", {}) or {}, src.get("metadata", {}) or {}
        rel = f"{tbl.get('schema', '')}.{tbl.get('name', stem)}"
        # Consistent naming: the TITLE is always the raw table name (matches the tree/breadcrumb).
        # The SME prose becomes the subtitle; the address is stated once (not 3x).
        fm = {
            "type": "Source",
            "title": tbl.get("name") or stem,
            "description": tbl.get("description") or f"Raw source-of-record — {rel}",
            "resource": f"table://{rel}",
            "tags": [
                label,
                "source",
                "lifecycle:draft",
                f"confidence:{tbl.get('confidence', 'C')}",
            ],
        }
        body = ["## Columns", "", "| column | type | role | confidence |", "|---|---|---|---|"]
        for c in src.get("columns", []) or []:
            body.append(
                f"| `{c.get('name')}` | {c.get('type', '')} | {c.get('role', '')} "
                f"| {c.get('confidence', '')} |"
            )
        # The doc is the raw schema-of-record (Columns). Lineage and quality findings live in the
        # object's TABS (Lineage / Quality) — not repeated here; a raw source has no ontology concept.
        (out / "sources" / f"{stem}.md").write_text(_fm(fm) + "\n" + "\n".join(body))

    # ---- Transform pages ----
    for stem, tr in transforms.items():
        prod = tr.get("produces", {}) or {}
        fm = {
            "type": "Transform",
            "title": f"Cleansing: {stem}",
            "description": f"Cleansing → {prod.get('relation', '')}",
            "relation": prod.get("relation"),  # produced relation — for lineage flow matching
            "tags": [label, "transform", "lifecycle:draft"],
        }
        body = [f"Produces `{prod.get('relation', '')}` · grain: {prod.get('grain', '—')}", ""]
        # AUTHORED rationale (the WHY/HOW — the cause) supersedes the generated rules (the consequence).
        # <stem>.why.md is hand-authored and NEVER owned/overwritten by this projector; we only surface it,
        # leading the Cleaning tab. Reasoning cannot be reverse-engineered from the YAML, so it lives here.
        whyf = data_dir / "transforms" / f"{stem}.why.md"
        if whyf.exists():
            wtxt = whyf.read_text()
            if wtxt.startswith("---"):  # strip its own frontmatter if present
                _parts = wtxt.split("---", 2)
                wtxt = _parts[2] if len(_parts) == 3 else wtxt
            body += [wtxt.strip(), ""]
        body += ["## Rules"]
        for t in tr.get("transforms", []) or []:
            body += [
                f"### {t.get('impurity_class', '')} — `{t.get('id', '')}`"
                + (f" · {t.get('status')}" if t.get("status") else ""),
                f"- **defect** {t.get('raw_defect', '')}",
                f"- **rule** {t.get('rule', '')}",
                f"- **guarantee** {t.get('establishes_guarantee', '')}",
                "",
            ]
        opn = tr.get("open_transforms", []) or []
        if opn:
            body += ["## Open — needs SME"]
            body += [
                f"- **{t.get('impurity_class', '')}** "
                f"{t.get('proposed_rule', t.get('raw_defect', ''))}"
                + (f" _({t.get('status')})_" if t.get("status") else "")
                for t in opn
            ]
            body += [""]
        # impurities this transform dissolves (from the reconciliation map)
        diss = sorted(
            tr_findings.get(stem, []), key=lambda x: _COV_ORDER.get(x[1].get("coverage"), 3)
        )
        if diss:
            body += ["## Impurities dissolved"]
            for fid, r in diss:
                iid = _slug(fid)
                body.append(
                    f"- {_COV_CHIP.get(r.get('coverage'), r.get('coverage'))} "
                    f"[{fid}](../quality/{iid}.md) — {r.get('guarantee', '')}"
                )
            body += [""]
        lin = []
        for sstem in sorted(set(tr_sources.get(stem, []))):
            lin.append(f"- Source: [{sstem}](../sources/{sstem}.md)")
        for dstem in tr_datasets.get(stem, []):
            lin.append(f"- Clean dataset: [{dstem}](../datasets/{dstem}.md)")
        if lin:
            body += ["## Lineage", *lin]
        sqlf = data_dir / "transforms" / f"{stem}.sql"
        if sqlf.exists():
            fm["sql_file"] = (
                f"data/transforms/{stem}.sql"  # LINKED via the SQL button, not embedded
            )
            body += [
                "",
                "## SQL realization",
                f"Realized by `{sqlf.name}` (a deployed `CREATE VIEW`) — open it with the "
                f"**SQL** button in the header, or in the Source browser.",
            ]
        flow = l_by_rel.get(prod.get("relation"))
        if flow:
            body += _lineage_cols_md(flow)
        (out / "transforms" / f"{stem}.md").write_text(_fm(fm) + "\n" + "\n".join(body))

    # ---- Dataset pages ----
    for stem, ds in datasets.items():
        tbl = ds.get("table", {}) or {}
        _dtf = ds_transform.get(stem)
        _drel = (
            ((transforms.get(_dtf) or {}).get("produces") or {}).get("relation") if _dtf else None
        )
        fm = {
            "type": "Dataset",
            "title": f"Clean: {tbl.get('name', stem)}",
            "description": "AI-friendly clean shape the ontology binds to",
            "relation": _drel,  # produced relation — for lineage flow matching
            "tags": [label, "dataset", "lifecycle:draft"],
        }
        body = ["## Columns", "", "| column | type | role |", "|---|---|---|"]
        for c in ds.get("columns", []) or []:
            body.append(f"| `{c.get('name')}` | {c.get('type', '')} | {c.get('role', '')} |")
        fks = ds.get("foreign_keys", []) or []
        if fks:
            body += ["", "## Foreign keys"]
            body += [
                f"- `{fk.get('from_column')}` → `{fk.get('to_table')}.{fk.get('to_column')}`"
                for fk in fks
            ]
        # Lineage lives in the object's Lineage TAB — not repeated in the doc.
        (out / "datasets" / f"{stem}.md").write_text(_fm(fm) + "\n" + "\n".join(body))

    # ---- Lookup pages (reference CSVs -> browsable MD tables; the SSOT stays CSV) ----
    import csv as _csv

    lookups = (
        sorted((data_dir / "lookups").glob("*.csv")) if (data_dir / "lookups").exists() else []
    )
    if lookups:
        (out / "lookups").mkdir(exist_ok=True)
    for lk in lookups:
        # Skip a "#" preamble. A register may carry one stating what it is, what generated it and
        # what is known-defective about it; counting those lines as data published "1.163 rows" for a
        # 1.108-row register. The same skip lives in meaning-as-code's mac_model._load_registers —
        # two readers, one rule, and they must not disagree about how many rows a register has.
        rows = list(
            _csv.reader([l for l in lk.read_text().splitlines() if not l.lstrip().startswith("#")])
        )
        hdr = rows[0] if rows else []
        n = max(0, len(rows) - 1)
        b = [f"Reference lookup · {n} rows · SSOT: `data/lookups/{lk.name}` (CSV).", ""]
        if hdr:
            b += ["| " + " | ".join(hdr) + " |", "| " + " | ".join(["---"] * len(hdr)) + " |"]
            b += ["| " + " | ".join(r) + " |" for r in rows[1:201]]
            if n > 200:
                b += ["", f"_…{n - 200} more rows — open the CSV in the Source browser._"]
        lfm = {
            "type": "Lookup",
            "title": lk.stem,
            "source_yaml": f"data/lookups/{lk.name}",
            "tags": [label, "lookup"],
        }
        (out / "lookups" / f"{lk.stem}.md").write_text(_fm(lfm) + "\n" + "\n".join(b))

    # ---- index ----
    covc = {"resolved": 0, "partial": 0, "gap": 0}
    for iss in issues:
        c = (resmap.get(iss.get("id")) or {}).get("coverage")
        if c in covc:
            covc[c] += 1
    idx = [
        "---",
        "type: Index",
        f"title: {label} data plane",
        "---",
        "",
        f"{len(sources)} sources · {len(issues)} quality issues · {len(transforms)} transforms "
        f"· {len(datasets)} clean datasets",
        "",
        "**Resolution scoreboard** — how the recorded impurities are dissolved by the gold "
        f"transforms: **{covc['resolved']} ✓ resolved · {covc['partial']} ◐ partial · "
        f"{covc['gap']} ⚠ open gap**.",
        "",
        "📋 **[Issues & inconsistencies — the full overview](quality/0-issues-overview.md)**",
        "",
        "❓ **[SME questions — data & data quality](quality/SME-QUESTIONS.md)**",
        "",
        "## Sources",
    ]
    idx += [f"- [{s}](sources/{s}.md)" for s in sorted(sources)]
    idx += ["", "## Data quality (by severity → resolution)"]
    for iss in sorted(
        issues,
        key=lambda x: (
            _SEV_ORDER.get(x.get("severity"), 3),
            _COV_ORDER.get((resmap.get(x.get("id")) or {}).get("coverage"), 3),
        ),
    ):
        cov = (resmap.get(iss.get("id")) or {}).get("coverage")
        chip = f" — {_COV_CHIP.get(cov, cov)}" if cov else ""
        idx.append(
            f"- **{iss.get('severity', '?')}** [{iss.get('title', '')}](quality/{iss['_id']}.md){chip}"
        )
    idx += ["", "## Clean datasets"]
    idx += [f"- [{d}](datasets/{d}.md)" for d in sorted(datasets)]
    if lookups:
        idx += ["", "## Reference lookups"]
        idx += [f"- [{lk.stem}](lookups/{lk.stem}.md)" for lk in lookups]
    (root / "index.md").write_text("\n".join(idx) + "\n")

    # Authored narrative docs (data/quality/RECONCILIATION.md — self-contained, its own frontmatter)
    # are served AS-IS by the Bundle. NOT re-projected here: globbing quality/*.md would re-wrap the
    # generated finding pages. So co-located generated md and the one authored doc coexist cleanly.
    ndocs = 0
    # ---- Issues & inconsistencies — ONE overview page aggregating everything found ----
    sev = {"high": 0, "medium": 0, "low": 0}
    for iss in issues:
        if iss.get("severity") in sev:
            sev[iss["severity"]] += 1
    unrec = len(issues) - covc["resolved"] - covc["partial"] - covc["gap"]
    ov = [
        f"Everything the harvest + reconciliation found for this source: "
        f"**{len(issues)} findings** across {len(sources)} tables.",
        "",
        f"- **Severity** — {sev['high']} high · {sev['medium']} medium · {sev['low']} low",
        f"- **Resolution** — {covc['resolved']} ✓ resolved · {covc['partial']} ◐ partial · "
        f"{covc['gap']} ⚠ open gap · {unrec} not yet reconciled (newly harvested)",
        "",
        "## All findings",
        "",
        "| severity | finding | table | impurity | resolution |",
        "|---|---|---|---|---|",
    ]
    for iss in sorted(
        issues,
        key=lambda x: (
            _SEV_ORDER.get(x.get("severity"), 3),
            _COV_ORDER.get((resmap.get(x.get("id")) or {}).get("coverage"), 9),
        ),
    ):
        r = resmap.get(iss.get("id")) or {}
        cov = r.get("coverage")
        chip = _COV_CHIP.get(cov) if cov else "not yet reconciled"
        rts = ", ".join(f"`{t}`" for t in (r.get("resolving_transforms") or []))
        title = str(iss.get("title", "")).replace("|", "\\|")[:64]
        ov.append(
            f"| {iss.get('severity', '?')} | [{title}]({iss['_id']}.md) "
            f"| {iss.get('_table') or '—'} | {r.get('impurity_class') or iss.get('impurity_class', '')} "
            f"| {chip} {rts} |"
        )
    opens = sorted(
        [(fid, r) for fid, r in resmap.items() if r.get("coverage") in ("gap", "partial")],
        key=lambda x: _COV_ORDER.get(x[1].get("coverage"), 3),
    )
    if opens:
        ov += ["", "## Open items — still need work", ""]
        ov += [
            f"- {_COV_CHIP.get(r.get('coverage'))} [{fid}]({_slug(fid)}.md) — {r.get('guarantee', '')}"
            for fid, r in opens
        ]
    ov += ["", "_Full narrative: [RECONCILIATION](RECONCILIATION.md)._"]
    (out / "quality" / "0-issues-overview.md").write_text(
        _fm(
            {
                "type": "Doc",
                "title": "Issues & inconsistencies",
                "description": f"{len(issues)} findings — the full overview",
                "tags": [label, "overview"],
            }
        )
        + "\n"
        + "\n".join(ov)
    )

    # ---- SME questions — the DATA + DATA-QUALITY sign-offs, exposed as ONE prioritised, in-sync list.
    # Derived from the register's per-issue `sme_owner` (the DQ perspective) + each transform's
    # `open_transforms` (the data-model perspective). A VIEW of authored sources — re-projected every run. ----
    def _owner_ask(s):
        s = str(s or "").strip()
        for sep in ("—", " - ", ": "):
            if sep in s:
                o, a = s.split(sep, 1)
                return o.strip(), a.strip()
        return "domain-owner", s

    _pipe = "\\|"

    def _esc(x, n):
        return str(x or "").replace("|", _pipe)[:n]

    sq = [
        f"The open **SME sign-offs** the data + data-quality work surfaces — {len(issues)} from the quality "
        f"register plus proposed transform changes awaiting ratification. Prioritised by severity; each "
        f"links to the finding it unblocks. This list is projected from the register + transforms, so it "
        f"stays in sync.",
        "",
    ]
    for sevname in ("high", "medium", "low"):
        rows = [i for i in issues if i.get("severity") == sevname]
        rows.sort(key=lambda x: _COV_ORDER.get((resmap.get(x.get("id")) or {}).get("coverage"), 9))
        if not rows:
            continue
        sq += [
            f"## {sevname.title()} priority — {len(rows)} question(s)",
            "",
            "| ask | owner | on (finding) | status | table |",
            "|---|---|---|---|---|",
        ]
        for i in rows:
            owner, ask = _owner_ask(i.get("sme_owner"))
            cov = (resmap.get(i.get("id")) or {}).get("coverage")
            chip = _COV_CHIP.get(cov, "unreconciled") if cov else "unreconciled"
            sq.append(
                f"| {_esc(ask, 130)} | {_esc(owner, 22)} | [{_esc(i.get('title'), 56)}]({i['_id']}.md) "
                f"| {chip} | {i.get('_table') or '—'} |"
            )
        sq += [""]
    prop = [
        (t, o.get("impurity_class", ""), str(o.get("proposed_rule") or o.get("raw_defect") or ""))
        for t, tr in transforms.items()
        for o in (tr.get("open_transforms") or [])
    ]
    if prop:
        sq += [
            "## Proposed data-model changes awaiting SME ratification",
            "",
            "| transform | class | proposed change |",
            "|---|---|---|",
        ]
        for tstem, cls, txt in prop:
            sq.append(
                f"| [{tstem}](../transforms/{tstem}.md) | {_esc(cls, 24)} | {_esc(txt, 150)} |"
            )
        sq += [""]
    (out / "quality" / "SME-QUESTIONS.md").write_text(
        _fm(
            {
                "type": "Doc",
                "title": "SME questions — data & data quality",
                "description": f"{len(issues)} sign-offs + {len(prop)} proposed changes awaiting SME",
                "tags": [label, "sme-questions"],
            }
        )
        + "\n"
        + "\n".join(sq)
    )

    # ---- PLANE HEALTH — the CHAIN + LINEAGE + PROTOCOL metrics, surfaced instead of living only in a
    # terminal gate run. Computed from the SAME artifacts the gates read (the lineage flows, the
    # descriptors, the ledger), so this is a read-view of the plane, not a second implementation of the
    # rules: the gates under meaning-as-code/tools stay authoritative and are what fail a build. ----
    _COV_WARN = 0.50  # mirrors check_lineage_coverage.MIN_COVERAGE_WARN
    ph = [
        "The structural health of this source's data plane — the same numbers the gates check, "
        "surfaced here so they are visible without running a terminal command. "
        "**The gates remain authoritative**; this page is a read-view.",
        "",
    ]
    # 1) the chain
    # match on the BARE relation name — the framework is a generic instrument and must never assume a
    # source's schema (hardcoding one silently mis-reports the chain on every other bundle).
    _produced = {
        _rel_bare_name(((transforms.get(t) or {}).get("produces") or {}).get("relation"))
        for t in transforms
    }
    _no_producer = [
        d
        for d in datasets
        if d not in transforms and (datasets[d].get("table") or {}).get("name", d) not in _produced
    ]
    ph += [
        "## Chain — `raw source → transformation → dataset → ontology concept`",
        "",
        "| link | count |",
        "|---|---|",
        f"| raw sources | {len(sources)} |",
        f"| transformations | {len(transforms)} |",
        f"| served datasets | {len(datasets)} |",
        f"| ontology concepts | {len(concept_stems)} |",
        "",
        (
            "✅ every dataset is produced by a transformation."
            if not _no_producer
            else f"⚠️ **{len(_no_producer)}** dataset(s) with no transformation: "
            + ", ".join(f"`{d}`" for d in _no_producer)
        ),
        "",
    ]
    # 2) lineage coverage — per served dataset, how many output columns descend from an upstream column
    if lineage:
        ph += [
            "## Lineage coverage",
            "",
            "How many of each served view's columns descend from an upstream column. Computed columns "
            "(pivots, aggregates, literals) legitimately have no single parent, so <100% is normal — "
            "**0% is the alarm**: it means the transform's inputs are mis-declared and the lineage "
            "silently collapsed.",
            "",
            "| dataset | covered | of | coverage | |",
            "|---|---|---|---|---|",
        ]
        tot_c = tot_n = 0
        for f in sorted(lineage, key=lambda x: str(x.get("transform"))):
            cols = [c.get("name") for c in ((f.get("dataset") or {}).get("columns") or [])]
            tos = {e.get("to_col") for e in (f.get("edges") or [])}
            cov = len([c for c in cols if c in tos])
            n = len(cols)
            tot_c += cov
            tot_n += n
            pct = (cov / n) if n else 0
            chip = (
                "🔴 explains nothing"
                if (n and cov == 0)
                else ("🟡 thin" if pct < _COV_WARN else "🟢")
            )
            ph.append(
                f"| `{_rel_bare_name(f.get('transform'))}` | {cov} | {n} | {round(100 * pct)}% | {chip} |"
            )
        ph += [
            "",
            f"**Overall — {tot_c}/{tot_n} columns ({round(100 * tot_c / max(1, tot_n))}%) trace to an "
            f"upstream column.**",
            "",
        ]
    # 3) the change protocol
    _led0 = _load(root / "interventions" / "ledger.yaml") or {}
    _ivs0 = (_led0.get("interventions") or []) if isinstance(_led0, dict) else []
    _prov = {"harvested": 0, "authored": 0, "tuned": 0, "unstamped": 0}
    for _grp in (sources, transforms, datasets):
        for _d in _grp.values():
            _p = ((_d or {}).get("metadata") or {}).get("provenance")
            _prov[_p if _p in _prov else "unstamped"] += 1
    ph += [
        "## Change protocol — autodiscovery vs manual",
        "",
        "| | count |",
        "|---|---|",
        f"| objects harvested (self-documenting) | {_prov['harvested']} |",
        f"| objects authored / tuned (need a protocol entry) | {_prov['authored'] + _prov['tuned']} |",
        f"| objects with no provenance stamp | {_prov['unstamped']} |",
        f"| protocolled interventions | {len(_ivs0)} |",
        "",
        (
            "✅ every authored/tuned object is protocolled — see [Interventions](../interventions/LEDGER.md)."
            if _ivs0
            else "⚠️ no `interventions/ledger.yaml` yet — manual changes are unrecorded."
        ),
        "",
    ]
    (out / "quality" / "PLANE-HEALTH.md").write_text(
        _fm(
            {
                "type": "Doc",
                "title": "Plane health — chain, lineage & protocol",
                "description": "Chain integrity, lineage coverage and change-protocol metrics",
                "tags": [label, "plane-health"],
            }
        )
        + "\n"
        + "\n".join(ph)
    )

    # ---- INTERVENTIONS — the explicit protocol for MANUAL work (interventions/ledger.yaml).
    # Autodiscovered work documents itself (the descriptor IS the record); anything AUTHORED, TUNED or
    # RETIRED by hand does not — so it is protocolled here and cross-linked to the objects it touched and
    # the DQ findings it answers. A VIEW of the authored ledger — re-projected every run. ----
    led = _load(root / "interventions" / "ledger.yaml") or {}
    ivs = (led.get("interventions") or []) if isinstance(led, dict) else []
    if ivs:
        _KIND_CHIP = {"authored": "✎ authored", "tuned": "⚙ tuned", "retired": "⌫ retired"}
        _obj_link = {
            "dataset": "../data/datasets/{}.md",
            "transform": "../data/transforms/{}.md",
            "source": "../data/sources/{}.md",
            "concept": "../ontology/concepts/{}.md",
            "lookup": "../data/lookups/{}.lookup.md",
        }
        by_kind = {}
        for i in ivs:
            by_kind.setdefault(i.get("kind", "?"), []).append(i)
        iv = [
            f"Every **manual** change to this bundle — what was authored, tuned or retired, **why**, and how "
            f"it was verified. Autodiscovered work needs no entry (the descriptor is its own record); manual "
            f"work does, because an implicit object is not a protocol. "
            f"**{len(ivs)} intervention(s)**: "
            + " · ".join(f"{len(v)} {_KIND_CHIP.get(k, k)}" for k, v in sorted(by_kind.items()))
            + ".",
            "",
            "Enforced by `check_intervention_ledger.py` — an object stamped `provenance: authored|tuned` "
            "with no entry here is a red gate.",
            "",
        ]
        for i in ivs:
            objs = []
            for o in i.get("objects") or []:
                t, _, stem = str(o).partition(":")
                pat = _obj_link.get(t)
                objs.append(
                    f"[{_esc(stem, 40)}]({pat.format(stem)})"
                    if (pat and i.get("kind") != "retired")
                    else f"`{_esc(stem, 40)}`"
                )
            dqs = " ".join(
                f"[{_esc(d, 44)}](../data/quality/{_slug(d)}.md)" for d in (i.get("dq_ids") or [])
            )
            iv += [
                f"### {_esc(i.get('id'), 60)} · {_KIND_CHIP.get(i.get('kind'), i.get('kind'))}",
                "",
                f"**{_esc(i.get('what'), 400)}**",
                "",
                f"- **Why** — {_esc(i.get('why'), 600)}",
            ]
            if i.get("evidence"):
                iv += [f"- **Verified** — {_esc(i['evidence'], 400)}"]
            iv += [f"- **Objects** — {', '.join(objs) if objs else '—'}"]
            if dqs:
                iv += [f"- **Answers** — {dqs}"]
            iv += [
                f"- **Status** — `{_esc(i.get('status'), 20)}`"
                + (f" · sign-off: {_esc(i.get('sme_owner'), 120)}" if i.get("sme_owner") else "")
                + f" · {_esc(i.get('date'), 12)} · {_esc(i.get('actor'), 20)}",
                "",
            ]
        (root / "interventions").mkdir(parents=True, exist_ok=True)
        (root / "interventions" / "LEDGER.md").write_text(
            _fm(
                {
                    "type": "Doc",
                    "title": "Interventions — the manual-change protocol",
                    "description": f"{len(ivs)} protocolled manual change(s)",
                    "tags": [label, "interventions"],
                }
            )
            + "\n"
            + "\n".join(iv)
        )

    # ---- structured DQ dashboard JSON — the Data Quality object's Overview renders this
    # (status cards + findings with detail INLINE, so there are no dead links). ----
    import json as _json

    _dash = {
        "stats": {
            "total": len(issues),
            "resolved": covc["resolved"],
            "partial": covc["partial"],
            "gap": covc["gap"],
            "unreconciled": unrec,
            "by_severity": sev,
        },
        "findings": [],
    }
    for iss in sorted(
        issues,
        key=lambda x: (
            _SEV_ORDER.get(x.get("severity"), 3),
            _COV_ORDER.get((resmap.get(x.get("id")) or {}).get("coverage"), 9),
        ),
    ):
        r = resmap.get(iss.get("id")) or {}
        _dash["findings"].append(
            {
                "id": iss.get("id"),
                "title": iss.get("title", ""),
                "severity": iss.get("severity"),
                "confidence": iss.get("confidence"),
                "table": iss.get("_table"),
                "impurity_class": r.get("impurity_class") or iss.get("impurity_class"),
                "coverage": r.get("coverage") or "unreconciled",
                "resolving_transforms": r.get("resolving_transforms") or [],
                "guarantee": r.get("guarantee"),
                "evidence": r.get("evidence"),
                "finding": iss.get("finding"),
                "current_handling": iss.get("current_handling"),
                "residual_risk": iss.get("residual_risk"),
                "sme_owner": iss.get("sme_owner"),
            }
        )
    (out / "quality" / "dq_dashboard.json").write_text(_json.dumps(_dash, indent=2, default=str))

    # DETERMINISTIC object index — the object-centric model the wiki navigates by.
    # Regenerated on every projection; a re-harvest re-emits the same object graph (idempotent).
    from sdk.project import objects as _objects

    _objects.build_objects(data_dir, onto_dir, lineage=lineage, issues=issues, out_dir=root)
    return {
        "sources": len(sources),
        "issues": len(issues),
        "transforms": len(transforms),
        "datasets": len(datasets),
        "docs": ndocs,
        "resolution": covc,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print(build_data(a.data, a.out))
