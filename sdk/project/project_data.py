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
(dim_acme_raw_country → dim_country). The impurity→resolution cross-link is read from
`data/quality/impurity_resolution_map.yaml` (harvest finding → gold transform). Lifecycle /
confidence / severity / resolution ride as frontmatter `tags` so the read server renders
them as chips. Deterministic — no LLM, no AWS; safe to re-run any time.
"""

from __future__ import annotations

import re
from pathlib import Path

from sdk.project import layout as _layout

import yaml

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
_COV_CHIP = {"resolved": "✓ resolved", "partial": "◐ partial", "gap": "⚠ open gap"}
_COV_ORDER = {"gap": 0, "partial": 1, "resolved": 2}

# ─── FIELD PARITY: what these projections deliberately do NOT carry, and why ─────────────────────
# Every per-finding dict below is a HAND-WRITTEN ALLOW-LIST of `iss.get(...)` calls, and that shape
# is why `status`, `ruled_by` and `reason` were absent from the dashboard while sitting in memory:
# on a register carrying `status` on 6 of 6, the projection carried it on 0 of 6, so the console
# could not tell an issue a named human examined and tolerated from an issue nobody has read.
#
# Dropping a field is legitimate — a roll-up is a summary. Dropping it SILENTLY is not. So each
# projection declares its omissions here, WITH A REASON, and tools/check_projection_field_parity.py
# reads these tables, runs this projector over a synthetic register carrying every field the schema
# and the vocabulary declare, and refuses any field that neither reaches the page nor appears below.
# The tables are checked BOTH WAYS: a field declared omitted that the page does carry is a stale
# claim and fails too, because an unchecked omission table rots into the same confident wrong answer
# as the prose it replaced.
#
# `mac.schema.json#$defs.DataQualityRegisterFile` declares the fields; `mac_vocabulary.yaml#dq_status`
# declares `status` and the `ruled_by` + `reason` its rulings REQUIRE — the second authority is the
# one that carries the three fields the defect dropped, so a schema-only check stays green through it.

#: THE STRUCTURED SURFACE — the console's only structured input. It carries EVERYTHING, on purpose.
DQ_DASHBOARD_OMITS: dict[str, str] = {}

#: THE PER-ISSUE PAGE — the detail view. Also complete; a reader who opens one issue gets all of it.
DQ_ISSUE_PAGE_OMITS: dict[str, str] = {}

#: THE ROLL-UP — one table row per issue, so it is a SUMMARY by design.
DQ_OVERVIEW_OMITS: dict[str, str] = {
    "finding": "the roll-up is one row per issue; the finding prose is the per-issue page's job and "
               "is linked from the row's title",
    "current_handling": "same row-budget reason — carried in full on the per-issue page",
    "residual_risk": "same row-budget reason — carried in full on the per-issue page",
    "sme_owner": "the roll-up is not the sign-off surface; SME-QUESTIONS.md is, and it is projected "
                 "from this same register in the same run",
    "confidence": "grading is shown on the per-issue page beside the finding it grades; the row "
                  "shows severity, which is what the table is sorted by",
    "reason": "the ruling's PHRASE is carried (`_disposition`: status + who ruled), the prose of "
              "why is the per-issue page's Disposition section",
}
# NOT LISTED, and measured rather than assumed: `ruled_by` IS carried here — `_disposition` renders
# "accepted · ruled by <who>" into the row. It was listed above on a first pass and the parity gate
# refused the claim, which is the whole point of checking the table in both directions.


def _disposition(iss: dict) -> str:
    """The HUMAN's ruling as one phrase, for the projected markdown.

    A SECOND AXIS FROM `resolution`, which is a transform's claim out of the resolution map. The
    same entry can read `✓ resolved` there and `accepted · operator` here, and a reader shown only
    the first is shown a machine's opinion where a person's ruling exists.

    ABSENCE IS NAMED, NOT BLANK. `mac.dq_status` is closed precisely so that a missing status is a
    finding rather than a fourth meaning, and a blank cell reads as "nothing to say" instead.
    """
    status = str(iss.get("status") or "").strip()
    if not status:
        return "no status recorded"
    # `open` IS THE VOCABULARY'S OWN WORD for "recorded and undispositioned", and it requires no
    # ruler — so it must not read as a ruling that forgot to name one.
    if status == "open":
        return "open — nobody has ruled"
    who = str(iss.get("ruled_by") or "").strip()
    return f"{status} · ruled by {who}" if who else f"{status} · no ruler named"


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


from sdk.project import column_table as _CT  # ONE renderer for the columns table


def _plane_index(out, plane: str, title: str, docs: dict, label: str) -> int:
    """`data/<plane>/index.md` — ONE PAGE OVER ALL OF A PLANE'S RELATIONS.

    WHY IT EXISTS. Operator, 2026-09-28: "there is one thing which is for sure missing - page overview
    on all sources". It was missing from every bundle in the estate, and nothing produced it: the root
    `index.md` lists relation NAMES as links, and a per-relation page describes ONE relation. Neither
    answers the question an operator actually opens a landing plane to ask — what did we land, how big is
    it, what is keyed, and what still has no key. That question is about the PLANE, so it gets a page at
    the plane, next to the descriptors it summarises.

    EVERY NUMBER HERE IS READ FROM THE DESCRIPTORS, never recounted from the warehouse: this is a read
    view, and a page that re-measures is a second measurement that can disagree with the first.

    A RELATION WITH NO KEY IS CALLED OUT RATHER THAN LEFT BLANK. `mac_references` will not derive a key
    and says so; a relation with none is not a parent endpoint and cannot be drawn in an ER model, which
    is a fact worth one line on the overview instead of a shrug in a cell.
    """
    if not docs:
        return 0
    rows_total = cols_total = refs_total = regs_total = 0
    keyless: list[str] = []
    lines = [f"| relation | rows | columns | key | references | registers |",
             "|---|---:|---:|---|---:|---:|"]
    for stem, d in sorted(docs.items()):
        tbl = d.get("table") or {}
        cols = [c for c in (d.get("columns") or []) if isinstance(c, dict)]
        n_rows = tbl.get("rows_measured")
        pk = [c for c in cols if str(c.get("role")) == "primary_key"]
        pk.sort(key=lambda c: (c.get("key_position") or 0))
        refs = [c for c in cols if c.get("references")]
        regs = [c for c in cols if c.get("register")]
        rows_total += int(n_rows or 0)
        cols_total += len(cols)
        refs_total += len(refs)
        regs_total += len(regs)
        if pk:
            key = " + ".join(f"`{c.get('name')}`" for c in pk)
        else:
            key = "**none measured**"
            keyless.append(str(tbl.get("name") or stem))
        lines.append(f"| [{tbl.get('name') or stem}]({stem}.md) | {n_rows if n_rows is not None else '?'} "
                     f"| {len(cols)} | {key} | {len(refs)} | {len(regs)} |")
    head = (f"{len(docs)} relation(s) · {rows_total:,} row(s) measured · {cols_total} column(s) · "
            f"{refs_total} declared reference(s) · {regs_total} register pointer(s)")
    body = [_fm({"type": "Index", "title": f"{label} {title}", "tags": [label, plane, "overview"]}),
            "", head, ""] + lines
    if keyless:
        body += ["", f"**{len(keyless)} relation(s) carry NO measured key** — "
                     + ", ".join(f"`{k}`" for k in keyless)
                     + ". `mac_references` reads the key and will not derive one, so these are not "
                       "parent endpoints and an ER model cannot draw them.", ""]
    (out / plane / "index.md").write_text("\n".join(body) + "\n")
    return len(docs)


#: The lookup page's declared layout — `delivers.lookup_page.shape`.
_LOOKUP_LAYOUT = _layout.layout("lookup_page")


def lookup_documents(root) -> dict:
    """`{register stem: its page body}` — the renderer `delivers.lookup_page` declares.

    PURE. `build_data` writes the real pages; this renders the same three sections from the same
    inputs so the layout checker and its frozen copies never need a write.
    """
    import csv as _csv

    root = Path(root)
    usage = register_users(root)
    out: dict = {}
    for lk in sorted((root / "data" / "lookups").glob("*.lookup.csv")):
        try:
            with lk.open(encoding="utf-8-sig", newline="") as handle:
                rows = [r for r in _csv.reader(handle) if r and not r[0].lstrip().startswith("#")]
        except Exception:
            continue
        hdr, data_rows = (rows[0] if rows else []), rows[1:]
        constant = {}
        for i, name in enumerate(hdr):
            if i == 0:
                continue
            vals = {(r[i] if len(r) > i else "") for r in data_rows}
            if len(vals) == 1:
                constant[name] = next(iter(vals))
        shown = [i for i, name in enumerate(hdr) if i == 0 or name not in constant]
        empty = _LOOKUP_LAYOUT.empty_section_says
        b = [f"Reference lookup · {len(data_rows)} rows · SSOT: `data/lookups/{lk.name}` (CSV).", ""]
        b += _layout.section(
            "Cut from",
            [f"- **{k}** — `{v}`" for k, v in constant.items() if k != "confidence" and v],
            empty,
        )
        used = usage.get(lk.name) or []
        b += _layout.section(
            "Used by",
            [f"- `{c}.{col}` — {how}" for c, col, how in sorted(used)]
            # A POSITIVE STATEMENT, NOT THE EMPTY MARKER. "Nothing reaches this register" is a
            # finding; `empty_section_says` is for a section the bundle declares nothing for. The
            # layout gate caught the first version wearing the marker's words.
            or ["- **Nothing reaches this register.** No column declares it and no descriptor "
                "attaches it, so its members cannot be resolved."],
            empty,
        )
        members = []
        if hdr:
            head = [hdr[i] for i in shown]
            members += ["| " + " | ".join(head) + " |",
                        "| " + " | ".join(["---"] * len(head)) + " |"]
            members += ["| " + " | ".join((r[i] if len(r) > i else "") for i in shown) + " |"
                        for r in data_rows[:200]]
        b += _layout.section("Members", members, empty)
        out[lk.stem] = "\n".join(b)
    return out


def register_users(root) -> dict:
    """`{register filename: [(concept, column, how)]}` — WHO USES EACH LOOKUP.

    Two ways a register is reached, and the page must distinguish them: a column that DECLARES it
    with `register:`, and a column whose NAME the register was cut from, which the undeclared path
    still reads. A register neither declares nor matches is reached by nothing, and that is the
    evidence for deleting it.
    """
    import csv as _csv

    root = Path(root)
    declared: dict = {}
    by_column: dict = {}
    relations: dict = {}
    for f in sorted((root / "ontology" / "concepts").glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        name = ((doc.get("concept") or {}) if isinstance(doc.get("concept"), dict) else {}).get("name")
        if not name:
            continue
        for src in ((doc.get("grounding") or {}).get("sources") or []):
            if not isinstance(src, dict):
                continue
            if src.get("relation"):
                relations.setdefault(name, str(src["relation"]))
            if not isinstance(src.get("columns"), dict):
                continue
            for column, body in src["columns"].items():
                body = body if isinstance(body, dict) else {}
                if body.get("register"):
                    declared.setdefault(Path(str(body["register"])).name, []).append(
                        (name, column, "declared")
                    )
                by_column.setdefault(str(column).casefold(), []).append((name, column))
    # THE DESCRIPTOR'S `attached:` IS THE ONE HOME of "which columns carry this set"
    # (mac.schema.json#ValueRegisterFile.attached), and it is what the runtime's loader reads. A
    # first cut here matched the CSV's first header against column names instead and disagreed with
    # the loader on three of 17 registers — a page that contradicts the engine is worse than none.
    out: dict = {}
    for lk in sorted((root / "data" / "lookups").glob("*.lookup.csv")):
        users = list(declared.get(lk.name, []))
        if not users:
            descriptor = lk.with_name(lk.name.removesuffix(".lookup.csv") + ".lookup.yaml")
            attached = []
            if descriptor.is_file():
                try:
                    raw = yaml.safe_load(descriptor.read_text(encoding="utf-8")) or {}
                except Exception:
                    raw = {}
                attached = [
                    (str(e["relation"]), str(e["column"]))
                    for e in (raw.get("attached") or [])
                    if isinstance(e, dict) and e.get("relation") and e.get("column")
                ]
            for relation, column in attached:
                for concept, own_relation in relations.items():
                    bare = (own_relation or "").rsplit(".", 1)[-1]
                    if bare and bare == relation.rsplit(".", 1)[-1]:
                        users.append((concept, column, "by descriptor"))
            if not attached:
                try:
                    with lk.open(encoding="utf-8-sig", newline="") as handle:
                        rows = [r for r in _csv.reader(handle)
                                if r and not r[0].lstrip().startswith("#")]
                except Exception:
                    rows = []
                head = rows[0][0].casefold() if rows else ""
                users = [(c, col, "by column name") for c, col in by_column.get(head, [])]
        out[lk.name] = sorted(set(users))
    return out


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

    # ASSOCIATE EACH ISSUE TO A SOURCE TABLE, AND SAY HOW IT WAS ASSOCIATED.
    #
    # Two of the three branches below are a DEREFERENCE of something a human declared — the issue's
    # own `table:`, or the resolution map's `locus`. The third is a GUESS: it counts how many of a
    # source's column names appear as substrings inside the issue's English prose and takes the
    # argmax, with ties broken by whatever order `sources` happens to iterate in.
    #
    # The guess is not removed here, because removing it would lose the only attribution most
    # issues have. What is fixed is that it USED TO BE INDISTINGUISHABLE from a declaration:
    # `_table` was emitted the same either way, so every consumer downstream — the per-source
    # Quality tab, the lineage node badge, the concept DESCRIBE pane — rendered an inference with
    # exactly the confidence of a fact. Measured on one bundle: 12 of 45 issues declare a table and
    # 33 are guessed, and one concept's "conditions addressed where this is built" card was 3
    # declared beside 1 guess with nothing to tell them apart.
    #
    # Unproven is a TYPE, not a silence — the same rule the acceptance suites already follow. So
    # the provenance travels with the value and consumers can choose; what they may no longer do is
    # be misled by accident.
    def _assoc(iss) -> tuple[str | None, bool]:
        """(table, inferred). `inferred` is True when nothing declared this and prose was matched."""
        if iss.get("table") in sources:
            return iss["table"], False
        r = resmap.get(iss.get("id")) or {}
        loc = (
            str(r.get("locus", "")).split(".")[0].strip()
        )  # resolution map "table.column" -> table
        if loc in sources:
            return loc, False
        text = (str(iss.get("title", "")) + " " + str(iss.get("finding", ""))).lower()
        best, score = None, 0
        for stem, src in sources.items():
            cols = [str(c.get("name", "")).lower() for c in src.get("columns", []) or []]
            s = sum(1 for c in cols if c and c in text)
            if s > score:
                best, score = stem, s
        # A zero-score argmax is not a weak match, it is NO match — `best` stays None and the issue
        # is attributed to nothing rather than to whichever table sorted first.
        return best, best is not None

    by_table: dict = {}
    _seen: dict = {}  # de-dupe colliding DQ ids (the register numbers per-table)
    for i, iss in enumerate(issues):
        base = _slug(iss.get("id") or f"issue-{i}")
        _seen[base] = _seen.get(base, 0) + 1
        iss["_id"] = base if _seen[base] == 1 else f"{base}-{_seen[base]}"
        iss["_table"], iss["_table_inferred"] = _assoc(iss)
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
        # THE RULING, ON THE HEADER LINE, beside severity/confidence/resolution. It used to be
        # absent from every projected surface, so the page for an entry a named person had
        # accepted read exactly like the page for one nobody had opened.
        _status = str(iss.get("status") or "").strip()
        _ruler = str(iss.get("ruled_by") or "").strip()
        _reason = str(iss.get("reason") or "").strip()
        _disp_term = f" · disposition **{_disposition(iss)}**"
        body = [
            f"`{iss.get('id', '')}` · severity **{sev}** · confidence **{conf}**"
            + (f" · resolution **{_COV_CHIP.get(cov, cov)}**" if cov else "")
            + _disp_term,
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
        # THE RULING ITSELF, where a reader can see it beside the question that asked for it. Only
        # when one exists: an invented "Disposition: none" heading would make an absence look like
        # a section somebody filled in.
        if _status:
            body += [
                "",
                "## Disposition",
                "",
                f"**{_status}** — ruled by **{_ruler or 'nobody named'}**.",
                "",
                _reason or "_No reason recorded. `accepted` and `wont_fix` both require one._",
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
                # READ IT WHERE IT IS DECLARED, AND DEFAULT TO THE LOWEST TIER, NOT THE HIGHEST.
                # This read `tbl.get('confidence', 'C')` — the `table:` block, where a source's
                # confidence has never lived; it is declared under `metadata:`. Measured: the
                # lookup missed on 8 of 8 source descriptors, every one declaring `I`, and every
                # page rendered `confidence:C`.
                #
                # `C` is CONFORMANCE §1's L3 — "an SME has ratified the meaning" — and
                # check_confidence_earned exists to catch an object claiming it with no
                # ratification on record. So a defaulting bug here does not produce a blank a
                # reader can question; it produces the most reassuring answer in the vocabulary,
                # on every page, for a raw landing table nobody has confirmed.
                #
                # THE DEFAULT IS NOW `Q` (needs-SME). An undeclared tier is not a confirmed one:
                # if nothing says who ratified this, the honest reading is that nobody has.
                f"confidence:{(src.get('metadata') or {}).get('confidence') or tbl.get('confidence') or 'Q'}",
            ],
        }
        # NO PER-COLUMN CONFIDENCE ON A SOURCE, and it is not a display choice — the column was
        # empty by construction and redundant by design. Measured on a live bundle: **0 of 96**
        # source columns carry `confidence`, so the column rendered 96 blanks; and the trust tier
        # this page needs is already stamped ONCE, at source level, in the frontmatter tag two
        # lines above (`confidence:{tbl.confidence}`, carried by 8 of 8 source descriptors).
        #
        # A RAW SOURCE IS TRUSTED AS A WHOLE OR NOT AT ALL. Operator ruling: "you already have
        # confidence on the data source as whole and this is enough. no need to evaluate each
        # column." A delivered table's columns are not independently ratified — one delivery, one
        # provenance, one tier. Reintroducing the column would ask an author to answer 96 times a
        # question the plane answers once.
        #
        # THIS IS NOT THE BLANK-CELL RULE'S OPPOSITE. That rule says a blank which means "nothing
        # is declared HERE" must stay visible and be counted. This column was never a slot anything
        # could declare into on this plane: the schema allows it, no source uses it, and the fact it
        # would carry lives elsewhere and is shown. An empty column whose emptiness is structural is
        # not information; it is a question asked of the wrong plane.
        body = ["## Columns", ""] + _CT.header()
        for c in src.get("columns", []) or []:
            body.append(_CT.row(c))
        body += _CT.fk_section(src.get("columns"))
        body += _CT.register_section(src.get("columns"))
        # The doc is the raw schema-of-record (Columns). Lineage and quality findings live in the
        # object's TABS (Lineage / Quality) — not repeated here; a raw source has no ontology concept.
        (out / "sources" / f"{stem}.md").write_text(_fm(fm) + "\n" + "\n".join(body))

    # ---- the LANDING PLANE's own overview page ----
    _plane_index(out, "sources", "landing plane", sources, label)

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
        body = ["## Columns", ""] + _CT.header()
        for c in ds.get("columns", []) or []:
            body.append(_CT.row(c))
        # BOTH RESOLUTION SURFACES, from the one renderer. The old hand-built block read the RETIRED
        # `foreign_keys:` key — which 0 of 16 descriptors carry — so it rendered nothing on every
        # delivered bundle; and registers had no section at all.
        body += _CT.fk_section(ds.get("columns"))
        body += _CT.register_section(ds.get("columns"))
        # Lineage lives in the object's Lineage TAB — not repeated in the doc.
        (out / "datasets" / f"{stem}.md").write_text(_fm(fm) + "\n" + "\n".join(body))

    # ---- the SERVED PLANE's own overview page. The same renderer, because the question an operator
    #      asks of a plane does not change with the plane: what is here, how big, what is keyed.
    _plane_index(out, "datasets", "served plane", datasets, label)

    # ---- Lookup pages (reference CSVs -> browsable MD tables; the SSOT stays CSV) ----
    import csv as _csv

    lookups = (
        sorted((data_dir / "lookups").glob("*.csv")) if (data_dir / "lookups").exists() else []
    )
    if lookups:
        (out / "lookups").mkdir(exist_ok=True)
    usage = register_users(root)
    for lk in lookups:
        # Skip a "#" preamble. A register may carry one stating what it is, what generated it and
        # what is known-defective about it; counting those lines as data published a row count 55 too
        # high for a register of about a thousand rows. The same skip lives in meaning-as-code's mac_model._load_registers —
        # two readers, one rule, and they must not disagree about how many rows a register has.
        rows = list(
            _csv.reader([l for l in lk.read_text().splitlines() if not l.lstrip().startswith("#")])
        )
        hdr = rows[0] if rows else []
        n = max(0, len(rows) - 1)
        # A COLUMN THAT NEVER VARIES IS A FACT ABOUT THE REGISTER, NOT ABOUT A MEMBER. Operator,
        # 2026-09-28: "in the lookup page these columns are redundant: source_view source_schema
        # confidence note / you can put them above the table as they apply for the whole table".
        # Correct, and measurably: `mac_lookups._render` writes the SAME source_view, source_schema,
        # confidence and note on every data row, so a 120-member register repeated four constants 120
        # times and the reader had to scan sideways past them to reach the member.
        #
        # DERIVED, NOT LISTED BY NAME. The rule is "one distinct value over every row", so a register
        # whose note or schema genuinely varies per member keeps that column in the table, and a
        # future constant column needs no change here. Hardcoding the four names would state the
        # instance instead of the requirement.
        #
        # THE CODE COLUMN ALWAYS STAYS IN THE TABLE. On a one-member register every column is constant,
        # including the code — and a register page whose table is empty because its single member was
        # "constant" would be an absurd reading of the same rule.
        #
        # `confidence` IS DROPPED ALTOGETHER when constant, on the operator's ruling: "confidence can
        # be dropped here ... of course its confiden ... its the database itself". A register is CUT
        # from the warehouse by measurement, so a measured tier repeated on every row tells a reader
        # nothing they did not already know from the artifact existing. It survives as a column only if
        # it actually varies, which would be a real disagreement worth showing.
        DROP_IF_CONSTANT = {"confidence"}
        data_rows = rows[1:]
        constant: dict[str, str] = {}
        if hdr and data_rows:
            for i, name in enumerate(hdr):
                if i == 0:
                    continue
                vals = {(r[i] if len(r) > i else "") for r in data_rows}
                if len(vals) == 1:
                    constant[name] = next(iter(vals))
        shown = [i for i, name in enumerate(hdr) if i == 0 or name not in constant]
        b = [f"Reference lookup · {n} rows · SSOT: `data/lookups/{lk.name}` (CSV).", ""]
        # THREE DECLARED SECTIONS, ALL ALWAYS PRESENT — `delivers.lookup_page.shape`. `Used by` is
        # the one a reader could not get anywhere else: a register nothing reaches is dead weight,
        # and until the page said so the only way to know was to run the loader.
        facts = [(k, v) for k, v in constant.items() if k not in DROP_IF_CONSTANT and v]
        b += _layout.section(
            "Cut from",
            [f"- **{k}** — `{v}`" if len(v) < 60 else f"- **{k}** — {v}" for k, v in facts],
            _LOOKUP_LAYOUT.empty_section_says,
        )
        used = (usage or {}).get(lk.name) or []
        b += _layout.section(
            "Used by",
            [
                f"- `{concept}.{column}` — {how}"
                for concept, column, how in sorted(used)
            ]
            # A POSITIVE STATEMENT, NOT THE EMPTY MARKER. "Nothing reaches this register" is a
            # finding; `empty_section_says` is for a section the bundle declares nothing for. The
            # layout gate caught the first version wearing the marker's words.
            or ["- **Nothing reaches this register.** No column declares it and no descriptor "
                "attaches it, so its members cannot be resolved."],
            _LOOKUP_LAYOUT.empty_section_says,
        )
        members: list = []
        if hdr:
            head = [hdr[i] for i in shown]
            members += ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * len(head)) + " |"]
            members += ["| " + " | ".join((r[i] if len(r) > i else "") for i in shown) + " |"
                        for r in data_rows[:200]]
            if n > 200:
                members += ["", f"_…{n - 200} more rows — open the CSV in the Source browser._"]
        b += _layout.section("Members", members, _LOOKUP_LAYOUT.empty_section_says)
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
    #: THE INDEX SITS AT THE BUNDLE ROOT AND ITS TARGETS SIT UNDER THE DATA DIRECTORY, so every link
    #: below needs that segment. Without it this projector wrote, for EVERY bundle it ever projected,
    #: an index whose every link resolved to nothing: 28 of the 35 entries in
    #: `tools/dangling_floor.txt` were this one line's output, across both exemplar bundles. `root` is
    #: `data_dir.parent`, so the prefix is computed from the pair rather than spelled "data/" — a
    #: renamed data directory then stays linked instead of breaking the same way again.
    dp = out.relative_to(root).as_posix()
    dp = f"{dp}/" if dp and dp != "." else ""
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
        f"📋 **[Issues & inconsistencies — the full overview]({dp}quality/0-issues-overview.md)**",
        "",
        f"❓ **[SME questions — data & data quality]({dp}quality/SME-QUESTIONS.md)**",
        "",
        "## Sources",
    ]
    idx += [f"- [{s}]({dp}sources/{s}.md)" for s in sorted(sources)]
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
            f"- **{iss.get('severity', '?')}** [{iss.get('title', '')}]({dp}quality/{iss['_id']}.md){chip}"
        )
    idx += ["", "## Clean datasets"]
    idx += [f"- [{d}]({dp}datasets/{d}.md)" for d in sorted(datasets)]
    if lookups:
        idx += ["", "## Reference lookups"]
        idx += [f"- [{lk.stem}]({dp}lookups/{lk.stem}.md)" for lk in lookups]
    (root / "index.md").write_text("\n".join(idx) + "\n")

    # Authored narrative docs (data/quality/RECONCILIATION.md — self-contained, its own frontmatter)
    # are served AS-IS by the Bundle. NOT re-projected here: globbing quality/*.md would re-wrap the
    # generated finding pages. So co-located generated md and the one authored doc coexist cleanly.
    ndocs = 0
    # ---- Issues & inconsistencies — ONE overview page aggregating everything found ----
    sev = {"high": 0, "medium": 0, "low": 0}
    # THE DISPOSITION TALLY, beside the severity one and counted the same way: DECLARED values
    # only, with the absence counted separately rather than folded into a fourth meaning.
    # `mac_vocabulary.yaml#dq_status` is closed and says why — `open` means somebody WROTE `open`,
    # so a missing status is a FINDING, not a synonym for it. On a legacy register measured at
    # 45 of 45 with no status key, defaulting would have fabricated 45 human rulings.
    by_status: dict = {}
    status_absent = 0
    for iss in issues:
        if iss.get("severity") in sev:
            sev[iss["severity"]] += 1
        stv = str(iss.get("status") or "").strip()
        if stv:
            by_status[stv] = by_status.get(stv, 0) + 1
        else:
            status_absent += 1
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
        # `resolution` is what a TRANSFORM claims; `disposition` is what a PERSON ruled. Both
        # columns, never merged: the two entries an operator had ruled on used to print
        # "✓ resolved" and "not yet reconciled", and neither said who had accepted them.
        "| severity | finding | table | impurity | resolution | disposition |",
        "|---|---|---|---|---|---|",
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
            f"| {chip} {rts} | {_disposition(iss)} |"
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
    #: THE NARRATIVE IS AUTHORED AND OPTIONAL, so the link is written only when the file is there. The
    #: comment 60 lines below already says these docs are "served AS-IS ... NOT re-projected here" —
    #: which means a bundle may simply not have one, and this line linked it unconditionally. Both
    #: exemplar bundles have no RECONCILIATION.md, so both carried a dead link in a GENERATED page.
    if (out / "quality" / "RECONCILIATION.md").is_file():
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
    def _ask_from_owner(v):
        """The ask out of a hand-authored `sme_owner`, which packs owner and question into one
        string separated by a dash or a colon. Returns "" when it carries only a role."""
        v = str(v or "").strip()
        for sep in ("—", " - ", ": "):
            if sep in v:
                return v.split(sep, 1)[1].strip()
        return ""

    def _owner_ask(i):
        """(owner, question, answer-set) — READ FROM THE FIELDS THE REGISTER ACTUALLY CARRIES.

        THIS READ A KEY NOBODY WRITES. It took `issue["sme_owner"]` and split it on a dash to
        recover an owner and an ask. No finding `mac_dq_findings` has ever written carries that
        key — the register's fields are id/title/severity/status/ruled_by/reason/finding/needs/
        ruling/raised_by — so `ask` was the empty string on every row. Measured on contoso5,
        2026-09-28: SME-QUESTIONS.md rendered 7 sign-offs, 1 high and 6 medium, each with an owner,
        a finding link, a status chip and a table name, and a BLANK QUESTION. The one column an SME
        opens the page for was the one that was empty, and the page looked complete without it.

        The questions were there the whole time, and they are good ones: `needs` carries the ask in
        prose with its recommendation, and `ruling` carries it as a closed choice — `question` plus
        an `answers` list. A closed answer set is the thing an SME can actually act on, so it is
        rendered as its own column rather than buried in the prose.
        """
        r = i.get("ruling") or {}
        # THREE FIELD GENERATIONS, READ IN ORDER OF PRECISION — and the third is not legacy cruft,
        # it is the only ask a HAND-AUTHORED register carries. Fixing this reader to prefer
        # `ruling`/`needs` (which only `mac_dq_findings` writes) silently blanked every bundle whose
        # register was written by a person: measured 2026-09-28, one hand-authored bundle carries
        # `sme_owner` 45 times and `ruling:` zero times, as do two others. Dropping the oldest
        # spelling turned the bug inside out instead of fixing it.
        q = ((r.get("question") or "").strip()
             or str(i.get("needs") or "").strip()
             or _ask_from_owner(i.get("sme_owner")))
        answers = r.get("answers") or []
        owner = str(i.get("sme_owner") or "").strip() or "domain-owner"
        for sep in ("—", " - ", ": "):
            if sep in owner:
                owner = owner.split(sep, 1)[0].strip()
                break
        return owner, q, " \u007c ".join(str(a) for a in answers)

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
            "| ask | answer one of | owner | on (finding) | status | table |",
            "|---|---|---|---|---|---|",
        ]
        for i in rows:
            owner, ask, answers = _owner_ask(i)
            cov = (resmap.get(i.get("id")) or {}).get("coverage")
            chip = _COV_CHIP.get(cov, "unreconciled") if cov else "unreconciled"
            sq.append(
                f"| {_esc(ask, 200)} | {_esc(answers, 90) or '—'} | {_esc(owner, 22)} "
                f"| [{_esc(i.get('title'), 56)}]({i['_id']}.md) | {chip} | {i.get('_table') or '—'} |"
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
            # DECLARED dispositions only, e.g. {"accepted": 2, "open": 4}, so a consumer can draw
            # the "ruled" step against a real denominator instead of a hard-coded zero. A plain
            # dict, for a diff-stable artifact.
            "by_status": by_status,
            "status_absent": status_absent,
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
                # THE DISPOSITION — what a HUMAN decided, a different axis from `coverage` below
                # (what a TRANSFORM claims). The two diverge on live data: an entry can carry
                # coverage `resolved` — a transform's claim, from the agent-writable resolution
                # map — while its status is `accepted`, a person's ruling. Drawing them as one
                # chip states a machine's claim as a human's.
                #
                # CARRIED RAW, NEVER DEFAULTED. `mac.dq_status` is a closed set in which `open`
                # means somebody WROTE `open`, so a missing status must arrive as null: coercing
                # it would fabricate a ruling. `ruled_by` and `reason` are the two fields
                # `accepted` and `wont_fix` REQUIRE, and they are the difference between an issue
                # a named human examined and tolerated and one nobody has read. `ruled_by` passes
                # through VERBATIM — it is a role in the register and this payload is committed to
                # a repo with a remote, so the projector must not resolve it to a display name.
                #
                # NOT computed here: any notion of "ruled", "covered" or "terminal". That needs
                # mac_vocabulary.yaml#dq_status, whose two readers (check_dq_resolution_sync.py,
                # check_data_plane_approved.py) hold an NS-/DQ- asymmetry a third implementation
                # would disagree with. The verdict reaches a page from the gate, not from here.
                "status": iss.get("status"),
                "ruled_by": iss.get("ruled_by"),
                "reason": iss.get("reason"),
                "table": iss.get("_table"),
                # HOW `table` WAS ARRIVED AT. True means no human declared it and the projector
                # matched the issue's prose against column names to pick one. A consumer that
                # renders both identically states an inference as a fact — see _assoc above.
                "table_inferred": bool(iss.get("_table_inferred")),
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
    # THIS CLI IS THE TRAP THE REST OF THIS ESTATE ALREADY WARNS ABOUT, and it warns in prose while
    # the entry point stayed open. `sdk/cli/harvest.py` says it three times — "build_data() (it
    # drops the Lineage view tab)", "MUST be threaded into the projection", "so ad-hoc build_data()
    # calls are never needed" — and none of that reaches someone typing the module name.
    #
    # WHAT IT COSTS. `build_data(data_dir, out_dir=None, lineage=None)` takes the flows as an
    # argument and this parser had no way to supply them, so every invocation projected with
    # lineage=None and `_views` silently dropped the `lineage` tab from EVERY source and dataset —
    # measured: 12 sources and 14 datasets, reported by the operator as "lineage tab is not there".
    # It also bypassed the compile gate that `project_source` runs first, so a bundle that the
    # estate refuses to project was projected anyway.
    #
    # A degraded artifact written silently is worse than a refusal, so this refuses and names the
    # supported path instead of doing three-quarters of the job.
    import sys

    print(
        "REFUSED: project_data is not a supported entry point.\n"
        "\n"
        "  It takes column-level lineage as an ARGUMENT and this CLI cannot supply it, so a direct\n"
        "  invocation drops the Lineage view tab from every source and dataset, and skips the\n"
        "  compile gate that refuses a non-conformant bundle.\n"
        "\n"
        "  Use the one supported path, which computes the flows and threads them:\n"
        "\n"
        "    python -m sdk.cli.harvest --content-root <bundle> --mode project\n"
        "\n"
        "  Import build_data(data_dir, lineage=flows) directly only if you are supplying flows.",
        file=sys.stderr,
    )
    raise SystemExit(2)
