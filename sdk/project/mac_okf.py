#!/usr/bin/env python3
"""MAC-in-OKF spike — depict a MAC ontology object as an OKF-compliant markdown page.

Readability-first layout (v2):
  * FRONTMATTER carries ONLY the small OKF surface (`type`, `title`, `description`,
    `tags`, `resource`, + a light `rule_pages` pointer) — a handful of lines that a
    generic OKF catalog reads and that renders as a clean header, not a wall.
  * The BODY is the readable doc (definition, grain, fields, a kind-grouped RULES
    INDEX, relationships) and ends with a delimited **`## Model` code fence** holding
    the FULL typed MAC object — the thing `mac.schema.json` validates and `rules.lock`
    hashes. A fence renders as a scrollable code block, never as an unreadable table.
  * RULES are single-homed on their own `type: Rule` pages; the concept's model fence
    excludes `contract.rules` and lists the rule pages instead. The bundle round-trips
    losslessly (concept model fence + referenced rule pages == the source object).

Usage:
  ./mac_okf.py build --src <concepts_dir> --out <bundle_dir>
  ./mac_okf.py audit --src <concepts_dir> --out <bundle_dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml
from jsonschema import validators as jsv

# ONE schema home. This module used to build its own path to the vendored fork, bypassing
# sdk.grammar.resolve entirely — so the process could hold TWO grammars at once and nothing said
# which had judged what. That is the same second-home defect the fork itself was, one level down.
from sdk.grammar.resolve import schema_path as _schema_path  # noqa: E402

_SCHEMA_PATH = _schema_path()
SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_Validator = jsv.validator_for(SCHEMA)
_Validator.check_schema(SCHEMA)
_CONCEPT_VALIDATOR = _Validator(SCHEMA)

_RULE_ITEM = dict(SCHEMA["$defs"]["contract"]["properties"]["rules"]["items"])
_RULE_ITEM["$defs"] = SCHEMA["$defs"]
_RULE_VALIDATOR = _Validator(_RULE_ITEM)

TYPE_OF = {
    "entity": "Entity",
    "event": "Event",
    "measure": "Metric",
    "enumeration": "Enum",
    "reference": "Reference",
    "grouping": "Grouping",
    "meta": "Meta",
}


# --------------------------------------------------------------------------- #
# frontmatter + model-fence helpers
# --------------------------------------------------------------------------- #
def _dump(obj) -> str:
    return yaml.safe_dump(
        obj, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100000
    )


def frontmatter(surface: dict) -> str:
    return f"---\n{_dump(surface)}---\n"


def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---\n") and "\n---\n" in text:
        head, body = text.split("\n---\n", 1)
        return yaml.safe_load(head[4:]) or {}, body
    return {}, text


def lock_hash(obj) -> str:
    canon = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# body rendering
# --------------------------------------------------------------------------- #
def _one_line(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _first_sentence(s: str, cap: int = 220) -> str:
    """A clean OKF `description`: the first sentence, never a mid-word cut."""
    t = _one_line(s)
    m = re.search(r"(.+?[.!?])(\s|$)", t)
    out = m.group(1) if m else t
    if len(out) > cap:
        out = out[:cap].rsplit(" ", 1)[0] + "…"
    return out


def _bullets(text: str) -> str:
    parts = [p.strip() for p in re.split(r";\s+(?=[A-Za-z])", _one_line(text)) if p.strip()]
    return "\n".join(f"- {p}" for p in parts) if parts else ""


def _edge_joins(concepts_dir: Path, concepts: list) -> dict:
    """{concept.name: {"out":[{title,on,join_rule}], "in":[...]}} projected from ontology/edges.yaml —
    the authoritative concept->concept join source (replaces the old prose-grep). out = this concept
    references others; in = others reference this concept."""
    name_title, name_stem = {}, {}
    for nm, _p, obj, _r in concepts:
        con = obj.get("concept") or {}
        cn = con.get("name") or nm
        name_title[cn] = con.get("label") or cn
        name_stem[cn] = nm  # the .md file stem (for building relative links)
    ep = Path(concepts_dir).parent / "edges.yaml"
    edges = ((yaml.safe_load(ep.read_text()) or {}).get("edges") or []) if ep.exists() else []

    def _cols(jr):  # "relA.from_col = relB.to_col" -> (from_col, to_col)
        try:
            lhs, rhs = [s.strip() for s in str(jr).split("=", 1)]
            return lhs.split(".")[-1], rhs.split(".")[-1]
        except Exception:
            return None, None

    res: dict = {}
    for e in edges:
        epr = e.get("endpoints") or {}
        fn = (epr.get("from") or {}).get("concept")
        tn = (epr.get("to") or {}).get("concept")
        if fn not in name_title or tn not in name_title:
            continue
        fc, tc = _cols(e.get("join_rule"))
        jr = e.get("join_rule")
        # A BUSINESS EDGE HAS NO `join_rule`, AND THAT IS NOT AN ABSENCE OF INFORMATION.
        # Measured: of 17 declared edges, 5 carry a `join_rule` and 12 do not — because both
        # concepts ground on the SAME relation, so there are not two relations to join and a
        # predicate there would be an invented self-join. Reading the column only out of
        # `join_rule` therefore dropped 11 of 17 edges from the Fields table, and the operator saw
        # a `CurrencyCode` row with an empty `joins →` while `order_line__denominated_in__currency`
        # sat declared in edges.yaml.
        #
        # The column such an edge carries is in `realized_by`, in one of two shapes:
        #   'rel.Column'                     — the attribute both concepts read
        #   'rel.KeyCol -> rel.ValueCol'     — a key to the value it carries; the FROM side is the key
        level = str(e.get("level") or "").strip() or None
        if not fc and not tc:
            rb = str(e.get("realized_by") or "")
            if rb:
                lhs, _, rhs = rb.partition("->")
                fc = lhs.strip().split(".")[-1].strip() or None
                tc = (rhs.strip() or lhs.strip()).split(".")[-1].strip() or None
        res.setdefault(fn, {"out": [], "in": []})["out"].append(
            {"title": name_title[tn], "stem": name_stem[tn], "on": fc, "join_rule": jr, "level": level}
        )
        res.setdefault(tn, {"out": [], "in": []})["in"].append(
            {"title": name_title[fn], "stem": name_stem[fn], "on": tc, "join_rule": jr, "level": level}
        )
    for k in res:
        res[k]["out"].sort(key=lambda x: (x["title"], x.get("on") or ""))
        res[k]["in"].sort(key=lambda x: (x["title"], x.get("on") or ""))
    return res


def _column_descriptions(data_dir: Path, errors: list | None = None) -> dict:
    """{relation-bare / dataset-stem -> {column: {"description", "type"}}} from the data layer.

    READ `description` OR `notes`, AND CARRY THE TYPE, because reading one key that nothing writes
    renders a blank that LOOKS like an absent declaration and is really a missed lookup. Measured on
    a live bundle when this was found: of 167 descriptor columns, `description` was present on **0**
    and the prose that existed sat in `notes` on 35 — so every description cell in every concept
    page was blank, 117 of 117 rows, while the text was on disk the whole time. `description` stays
    FIRST because the schema declares it and a bundle that fills it means it; `notes` is the
    fallback, not a synonym.

    `type` is carried for the same reason it belongs on the page at all: it is declared on 167 of
    167 columns and the Fields table never showed it, so a reader learned a column's ROLE and where
    it was GROUNDED but never what it IS.

    A FILE THAT WILL NOT PARSE IS REPORTED, NOT DROPPED. `errors` is an out-list: when a caller
    passes one, every descriptor this function could not read is appended to it as
    `{path, error}` with the path relative to the bundle root. The `except` below used to
    `continue` in silence, and that silence was measured — `tools/check_seam_contract.py` corrupted
    each traced input of the concept-page seam in turn and 8 of 17 changed the payload NOT AT ALL,
    because a quarter of the Fields table can vanish here without anything saying so. The read site
    is the one place that KNOWS, so it is the one place that reports; what to do about it is the
    caller's (the page seam refuses, being document mode — SEAM_CONTRACT.md §5). The default of
    `None` keeps every existing caller's behaviour byte-identical, so this is additive: `build`
    still projects what it can, and now has the fact available to act on when projection resumes.
    """
    out: dict = {}
    for sub in ("datasets", "sources"):
        for p in sorted((data_dir / sub).glob("*.yaml")) if (data_dir / sub).exists() else []:
            try:
                d = yaml.safe_load(p.read_text()) or {}
            except Exception as e:  # noqa: BLE001 — a fact to report, not to raise
                if errors is not None:
                    try:
                        rel = p.relative_to(data_dir.parent).as_posix()
                    except ValueError:
                        rel = p.name
                    errors.append({"path": rel, "error": f"{type(e).__name__}: {e}"})
                continue
            rel = (d.get("table") or {}).get("name") or p.stem
            cols = {
                c["name"]: {
                    "description": str(c.get("description") or c.get("notes") or "").strip(),
                    "type": str(c.get("type") or "").strip(),
                }
                for c in (d.get("columns") or [])
                if c.get("name")
            }
            out.setdefault(rel, {}).update(cols)
            out.setdefault(p.stem, {}).update(cols)
    return out


def _merged_col_meta(col_desc: dict, obj: dict, stem: str, rel_bare: str | None) -> dict:
    """One {column -> {description, type}} map covering EVERY relation the concept grounds on.

    The Fields table lists the union of all sources' columns, so its metadata must be looked up the
    same way. Sources are merged in REVERSE declared order and the primary relation last, so on a
    column name carried by two relations the FIRST-declared source wins — matching the precedence
    `_grounding_fields` already uses when it orders the rows.
    """
    merged: dict = {}
    srcs = (obj.get("grounding") or {}).get("sources") or []
    keys = [str((s or {}).get("relation") or "").split(".")[-1] for s in srcs if isinstance(s, dict)]
    for k in reversed([k for k in keys if k]):
        merged.update(col_desc.get(k) or {})
    merged.update(col_desc.get(rel_bare) or col_desc.get(stem) or {})
    return merged


def _property_docs(obj: dict) -> dict:
    """{casefolded column name -> the concept's own `properties[].doc`}.

    THE RICHEST PROSE IN THE BUNDLE IS HERE AND THE TABLE NEVER READ IT. A concept's `properties[]`
    carries a written `doc` per attribute — the transform that cleansed it, the measured null share,
    why a unique-looking column is deliberately not the key. The descriptor's `notes` is a sentence;
    this is the explanation.

    IT IS KEYED DIFFERENTLY, WHICH IS WHY IT WAS NEVER JOINED: `properties[].name` is camelCase
    (`productKey`) while the Fields table is keyed by the PHYSICAL column (`ProductKey`). Matching
    is by casefold, and that is a deliberate, narrow claim — same letters, different capitalisation.

    A COLLISION IS DROPPED, NOT GUESSED. If two properties casefold to one key the mapping is
    ambiguous, and attaching either doc to a column would state something the concept did not. Both
    are withheld so the cell reads as undeclared, which is true, instead of as wrong, which is worse.
    """
    docs: dict = {}
    collided: set = set()
    for prop in obj.get("properties") or []:
        if not isinstance(prop, dict):
            continue
        nm = str(prop.get("name") or "").strip()
        doc = str(prop.get("doc") or "").strip()
        if not nm or not doc:
            continue
        k = nm.casefold()
        if k in docs and docs[k] != doc:
            collided.add(k)
        docs[k] = doc
    for k in collided:
        docs.pop(k, None)
    return docs


def _concept_relation(obj: dict) -> str | None:
    srcs = (obj.get("grounding") or {}).get("sources") or []
    rel = srcs[0].get("relation") if srcs and isinstance(srcs[0], dict) else None
    return str(rel).split(".")[-1] if rel else None


def _relationships_panel(joins: dict, over) -> str:
    """Relationships at a glance — joins OUT (this concept references) + IN (referenced by), each with
    the join key, plus a grouping's leaf. Rendered from the projected edges, not scraped from prose."""
    out, inn = joins.get("out") or [], joins.get("in") or []
    if not out and not inn and not over:
        return ""
    lines = [
        "## Relationships",
        "",
        f"*{len(out)} join(s) out · {len(inn)} in — click a concept to open it.*",
        "",
    ]
    if over:
        lines += [f"**Groups** → **{over}** — the leaf concept this rolls up.", ""]
    if out:
        lines += ["**Joins to** — this concept references:", ""]
        for j in out:
            lines.append(f"- [{j['title']}]({j['stem']}.md) — joined on `{j.get('on') or '?'}`")
        lines.append("")
    if inn:
        lines += ["**Referenced by** — these point at this concept:", ""]
        for j in inn:
            lines.append(f"- [{j['title']}]({j['stem']}.md) — on `{j.get('on') or '?'}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _rule_ids(obj: dict) -> list[str]:
    return [
        r.get("id", "rule").replace("/", "_")
        for r in (obj.get("contract") or {}).get("rules") or []
    ]


#: The fold law, read from the framework registry rather than restated here. A measure's
#: `MeasureType` crossed with an axis's `axis_kind` yields an `aggregation_effect`, and the
#: registry declares that crossing itself — `MeasureType.members.<Type>.additivity.<axis_kind>`.
#: THIS FILE MUST NOT CARRY A SECOND COPY OF IT: the whole reason the page is worth rendering is
#: that it shows the law the runtime obeys, and a page quoting its own private table would be a
#: second home for the one fact, free to drift from the one the planner reads.
_VOCAB_PATH = Path(__file__).resolve().parents[2] / "mac_vocabulary.yaml"


def _fold_law() -> dict:
    """{MeasureType term -> {axis_kind term -> aggregation_effect term}}, from the registry.

    Returns {} when the registry cannot be read. An ABSENT law renders an em dash in the fold
    column — never a guessed SUM, because a wrong fold is the one error on this page that turns
    into a wrong number downstream."""
    try:
        doc = yaml.safe_load(_VOCAB_PATH.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — a state to report as a dash, not to raise
        return {}
    out: dict = {}
    for term, body in ((doc.get("MeasureType") or {}).get("members") or {}).items():
        add = (body or {}).get("additivity") or {}
        if isinstance(add, dict):
            out[str(term)] = {str(k): str(v) for k, v in add.items()}
    return out


def _axes_block(obj: dict) -> list[str]:
    """`## Axes` — the axes a measure may be folded along, and WHAT FOLD each one admits.

    WHY IT EXISTS. The concept declares `semantics.measure_type` and `semantics.axis_kinds`, and
    the page said so only in prose: "the fold along each axis is resolved from measure_type x
    axis_kinds". That names a law governing every figure the measure produces and then shows the
    reader none of its inputs — measured on one bundle, 3 concepts declared a measure_type and 18
    axis_kind entries were declared, and not one of them reached the page.

    IT IS NOT A COLUMN OF THE FIELDS TABLE, and that is the substantive point. An axis is not a
    column of this concept — it is ANOTHER CONCEPT. A sales measure's columns are its price and
    its quantity; its axes are Brand, Country, Store and time. Forcing eight axes into a table of
    four columns would be the same category error as sampling a host relation instead of a
    concept's members.

    THE FOLD IS DERIVED, NEVER AUTHORED HERE. `measure_type x axis_kind -> aggregation_effect` is
    declared in the framework registry; this reads it. An unknown type, an unknown axis kind or an
    unreadable registry all render an em dash, which says "not declared" — the same thing an em
    dash says everywhere else on this page."""
    c = obj.get("concept") or {}
    sem = c.get("semantics") or obj.get("semantics") or {}
    mt = str(sem.get("measure_type") or "").strip()
    axes = sem.get("axis_kinds") or {}
    if not mt and not axes:
        return []
    law = _fold_law()
    short = mt.rsplit(".", 1)[-1] if mt else ""
    rows = []
    for axis, kind in sorted((axes or {}).items()):
        kind_s = str(kind or "")
        kshort = kind_s.rsplit(".", 1)[-1]
        eff = (law.get(short) or {}).get(kshort, "")
        rows.append((str(axis), kshort or "—", eff.rsplit(".", 1)[-1] if eff else "—"))
    out = ["## Axes", ""]
    if mt:
        out += [f"Measure type: `{short}` — `{mt}`.", ""]
    if rows:
        out += ["| axis | axis kind | fold |", "|---|---|---|"]
        out += [f"| `{a}` | {k} | {f} |" for a, k, f in rows]
        out += [
            "",
            "_The fold is read from the framework registry "
            "(`MeasureType.<type>.additivity.<axis kind>`), not declared on this concept. "
            "An em dash means the crossing is not declared there._",
            "",
        ]
    else:
        out += ["_No axis is declared for this measure._", ""]
    return out


def _details_block(obj: dict) -> list[str]:
    """A compact, structured header block — the small typed facts a reader (and an answering agent)
    need at a glance: identity kind, version / schema_version / status / owner, what dissolves the
    concept, and governance. Rendered as a plain bullet list; only present fields appear, in a fixed
    order (deterministic — every value is authored, no timestamps/volatile fields)."""
    c = obj.get("concept") or {}
    meta = obj.get("metadata") or {}
    ident = c.get("identity") or {}
    contract = obj.get("contract") or {}
    gov = obj.get("governance") or {}
    rows: list[tuple[str, str]] = []
    if ident.get("kind"):
        rows.append(("Identity", str(ident["kind"])))
    if meta.get("version"):
        rows.append(("Version", str(meta["version"])))
    if meta.get("schema_version"):
        rows.append(("Schema version", str(meta["schema_version"])))
    if meta.get("status"):
        rows.append(("Status", str(meta["status"])))
    if meta.get("owner"):
        rows.append(("Owner", str(meta["owner"])))
    if contract.get("dissolved_by"):
        rows.append(("Dissolved by", f"`{contract['dissolved_by']}`"))
    if gov.get("owner"):
        rows.append(("Governance owner", str(gov["owner"])))
    if gov.get("last_reviewed"):
        rows.append(("Last reviewed", str(gov["last_reviewed"])))
    if not rows:
        return []
    return ["## Details", ""] + [f"- **{k}** — {v}" for k, v in rows] + [""]


def _grounding_fields(grounding: dict) -> list[dict]:
    """The UNION of grounding.sources[].columns and grounding.field_roles — so NO grounded column is
    dropped just because it lacks a field_role, and EVERY source (not just sources[0]) is represented.
    Stable order: each source's columns in declared order, then any field_roles-only column. Each entry
    carries the column's role (from field_roles) and the source relation(s) it belongs to, flagging the
    relation for which the column is the declared key (grounding.sources[].key)."""
    fr = grounding.get("field_roles") or {}
    srcs = grounding.get("sources") or []
    order: list[str] = []
    seen: set = set()
    src_of: dict = {}  # column -> [(relation_bare, is_key), ...]
    for s in srcs:
        if not isinstance(s, dict):
            continue
        rel_bare = str(s.get("relation") or "").split(".")[-1]
        key = s.get("key")
        for col in s.get("columns") or []:
            if col not in seen:
                seen.add(col)
                order.append(col)
            src_of.setdefault(col, []).append((rel_bare, col == key))
    for col in fr:  # grounded-role column not listed under any source
        if col not in seen:
            seen.add(col)
            order.append(col)
    return [
        {
            "column": col,
            "role": str(fr[col]).split(".")[-1] if col in fr else "",
            "sources": src_of.get(col, []),
        }
        for col in order
    ]


def concept_to_md(
    obj: dict,
    src_path: Path,
    name: str,
    bundle: dict[str, str],
    joins: dict | None = None,
    col_desc: dict | None = None,
) -> str:
    joins = joins or {"out": [], "in": []}
    col_desc = col_desc or {}
    c = obj.get("concept", {})
    meta = obj.get("metadata", {})
    klass = c.get("class", "reference")
    title = c.get("label") or c.get("name") or name
    grounding = obj.get("grounding", {})
    srcs = grounding.get("sources") or []
    resource = f"table://{srcs[0]['relation']}" if srcs and srcs[0].get("relation") else None

    # ---- small OKF surface (the whole frontmatter) ----
    surface = {
        "type": TYPE_OF.get(klass, klass.title()),
        "title": title,
        "description": _first_sentence(c.get("definition", "")),
        "tags": [
            t
            for t in (
                meta.get("source"),
                klass,
                f"confidence:{meta.get('confidence')}" if meta.get("confidence") else None,
            )
            if t
        ],
    }
    if resource:
        surface["resource"] = resource
    rule_ids = _rule_ids(obj)
    if rule_ids:
        surface["rule_pages"] = [f"rules/{r}.md" for r in rule_ids]

    # ---- readable body ----
    parts = [
        c.get("definition", "").strip(),
        "",
    ]  # no body H1 — the read-view renders the frontmatter title
    parts += _details_block(obj)
    # HOW TO ANSWER — the concept's agent-facing playbook (contract.no_probe_guarantee), rendered
    # VERBATIM inside a fence so its numbered steps / SQL / semicolons survive untouched. The single
    # highest-value field for "present AND later answer questions" (the wiki /ask reads this same .md).
    npg = (obj.get("contract") or {}).get("no_probe_guarantee")
    if npg:
        parts += [
            "## How to answer",
            "",
            "*What an agent needs ONLY, to answer with this concept — no data probing.*",
            "",
            "```text",
            str(npg).rstrip("\n"),
            "```",
            "",
        ]
    # GROUNDED IN — every source relation (not just sources[0]) + its declared key.
    ground_srcs = [s for s in srcs if isinstance(s, dict) and s.get("relation")]
    if ground_srcs:
        parts += ["## Grounded in", ""]
        for s in ground_srcs:
            parts.append(f"- `{s['relation']}`" + (f" — key `{s['key']}`" if s.get("key") else ""))
        parts.append("")
    if grounding.get("grain"):
        parts += ["## Grain", grounding["grain"].strip(), ""]
    fields = _grounding_fields(grounding)
    if fields:
        # each FK column links to the concept it joins (relative .md -> the viewer navigates it)
        # THE PLANE IS NAMED, BECAUSE A BUSINESS EDGE IS NOT A FOREIGN KEY. The operator ruled that
        # the physical layer and the business layer are two sets of edges and must read as two —
        # the graph canvas draws physical solid and business dashed for the same reason. A bare
        # link here would tell a reader the concepts are joined in the warehouse, which for 11 of
        # the 17 declared edges is false: they share an attribute on one relation.
        joins_by_col = {
            j["on"]: f"[{j['title']}]({j['stem']}.md)"
            + ("" if (j.get("level") or "physical") == "physical" else f" _({j['level']})_")
            for j in (joins.get("out") or [])
            if j.get("on")
        }
        # THE DESCRIPTION HAS THREE SOURCES AND THE TABLE READ NONE OF THEM PROPERLY.
        # Precedence, most specific first: the descriptor's `description` (the schema's own field),
        # then its `notes`, then the CONCEPT's own `properties[].doc` — which is the richest prose
        # in the bundle and was never joined at all because it is keyed in camelCase. An em dash
        # means NOTHING IS DECLARED, and it is the same marker `role` and `grounded in` already use,
        # so one glyph means one thing across the row.
        #
        # A BLANK IS NOT HIDDEN AND A COLUMN IS NEVER DROPPED FOR BEING EMPTY. Operator, on being
        # told an all-empty table might be collapsed into prose: "grid of blanks hints on the error
        # or incompletenes. it is much better then hiding it." They are right — a grid shows WHICH
        # column lacks WHICH fact; a sentence replaces that with a feeling. So the shape is
        # constant, and the footer COUNTS the emptiness instead, over its denominator, because an
        # unmeasured absence is the one thing this estate refuses to ship.
        prop_docs = _property_docs(obj)
        filled = {"description": 0, "type": 0, "joins →": 0}
        parts += [
            "## Fields",
            "",
            "| column | type | role | grounded in | description | joins → |",
            "|---|---|---|---|---|---|",
        ]
        for f in fields:
            col = f["column"]
            meta_col = col_desc.get(col) or {}
            if not isinstance(meta_col, dict):  # a caller passing the old {col: str} shape
                meta_col = {"description": str(meta_col or ""), "type": ""}
            desc = (
                meta_col.get("description") or prop_docs.get(col.casefold()) or ""
            ).replace("|", "\\|").replace("\n", " ").strip()
            ctype = str(meta_col.get("type") or "").strip()
            joined = joins_by_col.get(col, "")
            grounded = (
                ", ".join(f"`{rel}`{' (key)' if is_key else ''}" for rel, is_key in f["sources"])
                or "—"
            )
            if desc:
                filled["description"] += 1
            if ctype:
                filled["type"] += 1
            if joined:
                filled["joins →"] += 1
            parts.append(
                f"| `{col}` | {ctype or '—'} | {f['role'] or '—'} | {grounded} "
                f"| {desc or '—'} | {joined or '—'} |"
            )
        parts.append("")
        n = len(fields)
        parts += [
            "_Declared per column, over "
            + str(n)
            + " column"
            + ("" if n == 1 else "s")
            + ": "
            + " · ".join(f"{k} {v} of {n}" for k, v in filled.items())
            + ". An em dash is a column for which nothing is declared._",
            "",
        ]
    parts += _axes_block(obj)
    # Rules are NOT repeated on the Page — they have their own "Rules" view tab now.
    over = (obj.get("members") or {}).get("over") if isinstance(obj.get("members"), dict) else None
    rel = _relationships_panel(joins, over)
    if rel:
        parts += [rel]
    parts += [
        "## Source of record",
        f"- Full MAC concept: `{src_path.name}` — open the **YAML** tab for the complete typed definition.",
    ]
    return frontmatter(surface) + "\n" + "\n".join(parts)


def rule_to_md(rule: dict, parent_name: str, parent_title: str) -> str:
    title = rule.get("subject") or rule.get("id")
    _kind = str(rule.get("kind") or "rule").split(".")[-1]
    _binds = ", ".join(rule.get("binds") or [])
    surface = {
        "type": "Rule",
        "title": title,
        # a DISTINCT subtitle (not a repeat of the title) — the kind + the columns it binds
        "description": f"{_kind} rule" + (f" · binds {_binds}" if _binds else ""),
        "tags": [
            t
            for t in (
                rule.get("scope"),
                rule.get("kind"),
                f"confidence:{rule.get('confidence')}" if rule.get("confidence") else None,
            )
            if t
        ],
        "applies_to": f"../{parent_name}.md",
    }
    _conf = {"C": "confirmed", "P": "proposed", "R": "rejected"}.get(
        rule.get("confidence"), rule.get("confidence")
    )
    # FULL detail, labelled, with the raw namespaces stripped (mac.rule_kind.* -> the bare kind).
    # No body H1 / subject blockquote — the read-view already renders the frontmatter title.
    details = [f"- **Kind** — `{_kind}`"]
    if rule.get("confidence"):
        details.append(f"- **Confidence** — {rule.get('confidence')} ({_conf})")
    if rule.get("scope"):
        details.append(f"- **Scope** — {rule.get('scope')}")
    if rule.get("binds"):
        details.append("- **Binds** — " + ", ".join(f"`{b}`" for b in rule.get("binds")))
    if rule.get("id"):
        details.append(f"- **Rule id** — `{rule.get('id')}`")
    body = ["## Rule", "", *details, ""]
    for label, key in (
        ("When", "when"),
        ("Then — do (then)", "then"),
        ("Never — don't (never)", "never"),
    ):
        if rule.get(key):
            # VERBATIM — a single authored clause stays ONE clause. The old _bullets() split on '; ',
            # fragmenting SME phrasing and any clause/SQL that legitimately contains a semicolon.
            body += [f"### {label}", "", str(rule[key]).strip(), ""]
    body += [f"Applies to [{parent_title}](../{parent_name}.md)."]
    return frontmatter(surface) + "\n" + "\n".join(body)


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def load_concepts(src: Path):
    """Every concept under `src`, at any depth.

    RECURSIVE. This globbed "*.yaml" — flat only — so a bundle filing concepts by domain
    (`concepts/finance/revenue.yaml`) built ZERO concept pages and reported "built 0 concept pages"
    as a success. The console then 404'd every doc it asked for: "no such bundle file:
    ontology/concepts/customer.md". Third projector in this package with the same assumption; the
    object index and the data projector had it too.
    """
    out = []
    for p in sorted(src.rglob("*.yaml")):
        raw = p.read_text()
        obj = yaml.safe_load(raw)
        if isinstance(obj, dict) and "concept" in obj:
            out.append((p.stem, p, obj, raw))
    return out


def bundle_title(src: Path) -> str:
    """The concept index's title, READ from the bundle's own manifest.

    It used to be the string "ACME geography" — one instance's name, hardcoded, so EVERY bundle this
    projector touched got a concept index titled after a bundle it has nothing to do with. It reached
    the public example ontologies that way. The manifest already carries the identity the console
    addresses the container by; this reads it there rather than inventing a second home for it.
    """
    for root in (src.parent.parent, src.parent, src):
        mf = root / "mac.project.yaml"
        if not mf.is_file():
            continue
        try:
            md = (yaml.safe_load(mf.read_text(encoding="utf-8")) or {}).get("metadata") or {}
        except Exception:
            continue
        label = md.get("label") or md.get("project") or md.get("dataset")
        if label:
            return str(label)
    return src.parent.parent.name or "Ontology"


def page_inputs(src: Path, concepts: list) -> dict:
    """The WHOLE-BUNDLE context every concept page needs, computed once.

    EXTRACTED FROM `build`, VERBATIM, AND FOR ONE REASON. The console renders the concept Page tab
    LIVE now (tools/project_concept_page.py -> the console's /concept-page route), because the
    `.md` under `ontology/concepts/` is a BUILD ARTIFACT: a page is exactly as old as the last
    projection run and says nothing about it — the same defect already repaired for the object
    index and the edge index, one surface over. A live page therefore needs the page builder
    callable for ONE concept without writing anything.

    Re-deriving this context in the caller would make a SECOND AUTHOR for what a page says, which
    is the defect class this estate spends its time removing: the four arguments below are not
    plumbing, they are content — `rel_joins` IS the Relationships panel, `col_desc` IS the Fields
    table, and a caller that assembled them slightly differently would render a DIFFERENT page
    from the one `build` writes while both claimed to be the page. So `build` and the live seam
    call these two functions and nothing else.

    Nothing about what a page SAYS changed here: `build`'s loop body moved into `concept_page`
    under it, and the 17 pages of the bundle this was measured on are byte-identical before and
    after the extraction.

    `col_desc_unparsed` is the one addition, and it says nothing new about a page — it names the
    descriptor files the Fields table's metadata could NOT be read from, which `_column_descriptions`
    used to drop in silence. A caller that serves a document refuses on it (SEAM_CONTRACT.md §5);
    `build` is unaffected, because the list is empty whenever every descriptor parses.
    """
    col_desc_unparsed: list = []
    col_desc = _column_descriptions(src.parent.parent / "data", errors=col_desc_unparsed)
    return {
        "bundle": {
            name: (obj.get("concept", {}).get("label") or obj.get("concept", {}).get("name") or name)
            for name, _p, obj, _r in concepts
        },
        # sibling data plane (per-source MAC project)
        "data_sources": src.parent.parent / "data" / "sources",
        # concept.name -> {out,in} from edges.yaml
        "rel_joins": _edge_joins(src, concepts),
        # relation/stem -> {col: description}
        "col_desc": col_desc,
        # the descriptors that would not parse: [{path, error}], root-relative. Empty on a clean
        # bundle — a swallowed read is a silent lie about what the Fields table is missing.
        "col_desc_unparsed": col_desc_unparsed,
    }


def concept_page(name: str, path: Path, obj: dict, inputs: dict) -> str:
    """ONE concept's page, as markdown. Writes nothing; `build` writes what this returns.

    This is `build`'s per-concept loop body, moved without a character of its rendering changed —
    see `page_inputs` for why it is a function at all.
    """
    cname = (obj.get("concept") or {}).get("name") or name
    rel_bare = _concept_relation(obj) or name
    md = concept_to_md(
        obj,
        path,
        name,
        inputs["bundle"],
        inputs["rel_joins"].get(cname, {"out": [], "in": []}),
        # EVERY SOURCE, NOT JUST THE FIRST. `_grounding_fields` deliberately unions the columns
        # of ALL `grounding.sources`, so a lookup keyed on one relation leaves every column of
        # the second source unresolved — measured when the type column landed: 6 of 117 rows
        # blank, and all 6 were a second source (a concept grounded in both a customer and a
        # store relation). The first relation still wins a name collision, which is the same
        # precedence the rest of this builder uses.
        _merged_col_meta(inputs["col_desc"], obj, name, rel_bare),
    )
    if (inputs["data_sources"] / f"{name}.yaml").exists():
        md += f"\n\n## Data\n- Source table: [{name}](../../data/sources/{name}.md)\n"
    return md


def build(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    concepts = load_concepts(src)
    # IDEMPOTENCY: the read-view *.md and rules/ are DERIVED. Clear stale derived pages so a
    # renamed/removed concept or rule cannot leave an orphan that bloats the signed artifact and
    # makes index.md list phantom rules. NEVER touch the SSOT: out == the concepts dir also holds
    # the authored *.yaml, so we only remove derived *.md (whose stem has no sibling .yaml) + the
    # rules/ subtree (which is 100% derived).
    shutil.rmtree(out / "rules", ignore_errors=True)
    (out / "rules").mkdir()
    _valid_md = {f"{name}.md" for name, _p, _o, _r in concepts} | {"index.md"}
    for md in out.glob("*.md"):
        if md.name not in _valid_md and not (out / f"{md.stem}.yaml").exists():
            md.unlink()
    inputs = page_inputs(src, concepts)
    bundle = inputs["bundle"]
    n_rules = 0
    for name, path, obj, _raw in concepts:
        (out / f"{name}.md").write_text(concept_page(name, path, obj, inputs))
        for rule in (obj.get("contract") or {}).get("rules") or []:
            rid = rule.get("id", "rule").replace("/", "_")
            (out / "rules" / f"{rid}.md").write_text(rule_to_md(rule, name, bundle[name]))
            n_rules += 1
    title = bundle_title(src)
    idx = [
        "---",
        "type: Index",
        f"title: {title} — concepts (MAC-in-OKF)",
        "---",
        "",
        f"# {title} — MAC objects as OKF pages",
        "",
    ]
    idx += [f"- [{bundle[n]}]({n}.md)" for n in sorted(bundle)]
    idx += ["", "## Rules"] + [
        f"- [{rp.stem}](rules/{rp.name})" for rp in sorted((out / "rules").glob("*.md"))
    ]
    (out / "index.md").write_text("\n".join(idx) + "\n")
    print(f"built {len(concepts)} concept pages + {n_rules} rule pages -> {out}")


def audit(src: Path, out: Path):
    """Validate the ontology. The .md read-view is now a LOSSY human projection (no embedded model
    fence), so the SSOT is the .yaml — validate that directly, confirm every concept has a page, and
    check cross-links resolve."""
    concepts = load_concepts(src)
    ok = True
    print(f"\n{'object':<26}{'page':<10}{'MAC valid':<11}{'lock/12'}")
    print("-" * 62)
    for name, _path, obj, _raw in concepts:
        page = (out / f"{name}.md").exists()
        mac_valid = not list(_CONCEPT_VALIDATOR.iter_errors(obj))  # validate the YAML SSOT
        ok = ok and mac_valid and page
        print(
            f"{name:<26}{('yes' if page else 'MISSING'):<10}{_yn(mac_valid):<11}{lock_hash(obj)[:12]}"
        )
    all_rules = [
        r for _n, _p, obj, _r in concepts for r in ((obj.get("contract") or {}).get("rules") or [])
    ]
    rule_ok = sum(1 for r in all_rules if not list(_RULE_VALIDATOR.iter_errors(r)))
    broken = _check_links(out)
    print("-" * 62)
    print(
        f"concepts: {len(concepts)} | rules valid: {rule_ok}/{len(all_rules)} "
        f"| broken cross-links: {len(broken)}"
    )
    if broken:
        print("  broken:", broken)
    return 0 if (ok and rule_ok == len(all_rules) and not broken) else 1


def _check_links(out: Path):
    files = {p.relative_to(out).as_posix() for p in out.rglob("*.md")}
    broken = []
    for p in out.rglob("*.md"):
        head = p.read_text().split("\n```yaml\n", 1)[0]  # ignore links inside the fence
        for _txt, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", head):
            if "://" in href or href.startswith("#"):
                continue
            tgt = (p.parent / href).resolve().relative_to(out.resolve()).as_posix()
            if tgt not in files:
                broken.append(f"{p.relative_to(out)} -> {href}")
    return broken


def _yn(b):
    return "PASS" if b else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "audit"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    if a.cmd == "build":
        build(src, out)
        return 0
    return audit(src, out)


if __name__ == "__main__":
    sys.exit(main())
