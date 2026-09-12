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
        res.setdefault(fn, {"out": [], "in": []})["out"].append(
            {"title": name_title[tn], "stem": name_stem[tn], "on": fc, "join_rule": jr}
        )
        res.setdefault(tn, {"out": [], "in": []})["in"].append(
            {"title": name_title[fn], "stem": name_stem[fn], "on": tc, "join_rule": jr}
        )
    for k in res:
        res[k]["out"].sort(key=lambda x: (x["title"], x.get("on") or ""))
        res[k]["in"].sort(key=lambda x: (x["title"], x.get("on") or ""))
    return res


def _column_descriptions(data_dir: Path) -> dict:
    """{relation-bare / dataset-stem -> {column: description}} from the data layer, so the concept's
    Fields table can carry the real column descriptions (the ontology field_roles hold only the role)."""
    out: dict = {}
    for sub in ("datasets", "sources"):
        for p in sorted((data_dir / sub).glob("*.yaml")) if (data_dir / sub).exists() else []:
            try:
                d = yaml.safe_load(p.read_text()) or {}
            except Exception:
                continue
            rel = (d.get("table") or {}).get("name") or p.stem
            cols = {
                c.get("name"): c.get("description", "")
                for c in (d.get("columns") or [])
                if c.get("name")
            }
            out.setdefault(rel, {}).update(cols)
            out.setdefault(p.stem, {}).update(cols)
    return out


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
        joins_by_col = {
            j["on"]: f"[{j['title']}]({j['stem']}.md)"
            for j in (joins.get("out") or [])
            if j.get("on")
        }
        parts += [
            "## Fields",
            "",
            "| column | role | grounded in | description | joins → |",
            "|---|---|---|---|---|",
        ]
        for f in fields:
            col = f["column"]
            desc = str(col_desc.get(col, "") or "").replace("|", "\\|").replace("\n", " ").strip()
            grounded = (
                ", ".join(f"`{rel}`{' (key)' if is_key else ''}" for rel, is_key in f["sources"])
                or "—"
            )
            parts.append(
                f"| `{col}` | {f['role'] or '—'} | {grounded} | {desc} "
                f"| {joins_by_col.get(col, '')} |"
            )
        parts.append("")
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

    It used to be the string "FPL geography" — one instance's name, hardcoded, so EVERY bundle this
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
    bundle = {
        name: (obj.get("concept", {}).get("label") or obj.get("concept", {}).get("name") or name)
        for name, _p, obj, _r in concepts
    }
    data_sources = (
        src.parent.parent / "data" / "sources"
    )  # sibling data plane (per-source MAC project)
    rel_joins = _edge_joins(src, concepts)  # concept.name -> {out,in} from edges.yaml
    col_desc = _column_descriptions(
        src.parent.parent / "data"
    )  # relation/stem -> {col: description}
    n_rules = 0
    for name, path, obj, _raw in concepts:
        cname = (obj.get("concept") or {}).get("name") or name
        rel_bare = _concept_relation(obj) or name
        md = concept_to_md(
            obj,
            path,
            name,
            bundle,
            rel_joins.get(cname, {"out": [], "in": []}),
            col_desc.get(rel_bare) or col_desc.get(name) or {},
        )
        if (data_sources / f"{name}.yaml").exists():
            md += f"\n\n## Data\n- Source table: [{name}](../../data/sources/{name}.md)\n"
        (out / f"{name}.md").write_text(md)
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
