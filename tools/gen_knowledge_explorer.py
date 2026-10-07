#!/usr/bin/env python3
"""gen_knowledge_explorer — a browsable tree over a bundle's knowledge, concepts and rules.

WHY, operator 2026-10-05: "you should make tree view left and let us choose topic by group / concept
/ cathegory". A flat markdown page is a document, not a tool: to compare a narrative against a
declaration you need to reach both in two clicks, and to see what is DONE you need the whole corpus
at once rather than one file at a time.

THREE LEVELS, AND EACH IS READ FROM THE BUNDLE:
  group    `concept.class` — enumeration · reference · entity · measure · event
  concept  the concept document's own stem
  topic    a `##` section of its knowledge page, each of its rules, and its declaration

NOTHING IS TYPED HERE. The tree, the counts and the prose all come from the bundle, so a concept
whose knowledge page has not been written yet shows as exactly that — which makes the tree the
migration's coverage view as well as its reader.

    python3 tools/gen_knowledge_explorer.py <bundle> [-o out.html]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P  # noqa: E402

TEMPLATE = pathlib.Path(__file__).resolve().parent / "knowledge_explorer_template.html"


def sections(md: str) -> list[dict]:
    """A markdown page split at `## ` — [{title, body}], with anything before the first as intro."""
    out: list[dict] = []
    body = re.sub(r"^---\n.*?\n---\n", "", md, flags=re.S)       # drop frontmatter
    parts = re.split(r"^## +(.+)$", body, flags=re.M)
    intro = parts[0].strip()
    if intro:
        out.append({"title": "Overview", "body": intro})
    for i in range(1, len(parts) - 1, 2):
        out.append({"title": parts[i].strip(), "body": parts[i + 1].strip()})
    return out


def _identity_columns(cols) -> list:
    """The columns that identify a row — the grain, since `grounding.grain` was retired 2026-10-07.

    The prose key said "one row per sale (order_key, line_number)" beside columns already declaring
    `identity: composite` on exactly those two. The page now states the grain from the declaration,
    so it cannot drift from it.
    """
    if not isinstance(cols, dict):
        return []
    out = []
    for name, spec in cols.items():
        roles = (spec or {}).get("roles") if isinstance(spec, dict) else None
        term = str((roles or {}).get("identity") or "").rsplit(".", 1)[-1]
        if term in ("canonical", "composite"):
            out.append(str(name))
    return out


def declaration_view(doc: dict) -> str:
    """The formal side, rendered as markdown so the two panes read alike."""
    g = (doc.get("grounding") or {})
    src = (g.get("sources") or [{}])[0]
    cols = src.get("columns") or {}
    L = [f"**Relation** · `{src.get('relation', '—')}`", ""]
    if src.get("key"):
        L += [f"**Grain** · one row per {', '.join(str(k) for k in src['key'])}", ""]
    elif _identity_columns(cols):
        L += [f"**Grain** · one row per {', '.join(_identity_columns(cols))}", ""]
    if g.get("snapshot_rule"):
        L += [f"**Snapshot rule** · {' '.join(str(g['snapshot_rule']).split())}", ""]
    if cols:
        # OFFERS, NOT A ROLE NAME. The column says which uses a question may make of it, and a
        # column holding several (a join key you also group by — 21 of contoso5's 112) had no
        # honest single-role spelling. The page shows what it offers, in the order the standard
        # lists them, and the retired scalar is not reconstructed for display.
        L += ["| column | offers | terms |", "|---|---|---|"]
        for n, b in cols.items():
            b = b if isinstance(b, dict) else {}
            roles = b.get("roles") if isinstance(b.get("roles"), dict) else {}
            offers, terms = [], []
            if roles.get("identity"):
                offers.append("identity")
                terms.append(str(roles["identity"]).rsplit(".", 1)[-1])
            if roles.get("axis"):
                offers.append("axis")
                terms.append(str(roles["axis"]).rsplit(".", 1)[-1])
            if isinstance(roles.get("aggregate"), dict):
                m = roles["aggregate"]
                offers.append("aggregate")
                terms.append(
                    f"{str(m.get('type', '')).rsplit('.', 1)[-1]} {m.get('unit', '')}".strip()
                )
                if m.get("canonical"):
                    terms.append("canonical")
            if roles.get("period_binding"):
                offers.append("period_binding")
            if roles.get("extremum"):
                offers.append("extremum")
                terms.append(", ".join(str(x) for x in roles["extremum"]))
            if b.get("counts"):
                terms.append("counted by this column")
            if b.get("register"):
                terms.append("register")
            L.append(f"| `{n}` | {', '.join(offers) or '— (offered to no question)'} | {', '.join(terms) or '—'} |")
        L.append("")
    return "\n".join(L)


def build(root: pathlib.Path) -> dict:
    import yaml

    kdir = root / "knowledge"
    cdir = P.concepts_dir(root)
    rdir = cdir / "rules"
    out = []
    for f in P.concept_files(root):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        c = doc.get("concept") or {}
        rules = [r for r in ((doc.get("contract") or {}).get("rules") or []) if r.get("id")]
        kp = kdir / f"{f.stem}.md"
        topics = []
        if kp.is_file():
            topics = sections(kp.read_text(encoding="utf-8"))
        #: THE CANONICAL TABS, and they are honest rather than aspirational. Measured over
        #: contoso5's 17: `definition` 17/17, `grain` 17/17, columns 17/17, rules 14/17,
        #: identity.kind 10/17, snapshot_rule 1/17 — so Overview, Grain and Declaration are
        #: always there, Identity and Rules are usually, and the snapshot rule lives INSIDE
        #: Grain rather than earning a tab that is empty on sixteen concepts. A tab with no
        #: content is not rendered; its absence is the measurement.
        canon = {"Overview": None, "Identity": None, "Grain": None}
        rest = []
        for i, t in enumerate(topics):
            if t["title"] in canon and canon[t["title"]] is None:
                canon[t["title"]] = i
            else:
                rest.append(i)
        rule_topics = []
        for r in rules:
            page = rdir / f"{r['id']}.md"
            why = ""
            if page.is_file():
                m = re.search(r"^## +Why\s*$(.*?)(?=^## |\Z)", page.read_text(encoding="utf-8"),
                              re.M | re.S)
                why = m.group(1).strip() if m else ""
            binds = r.get("binds") or []
            canons = [b.get("udf", "").rsplit(".", 1)[-1]
                      for b in (r.get("realized_by") or []) if isinstance(b, dict)]
            rule_topics.append({
                "id": r["id"],
                "kind": str(r.get("kind", "")).rsplit(".", 1)[-1],
                "binds": binds,
                "canons": canons,
                "why": why or " ".join(str(r.get("why", "")).split()),
                "clauses": {k: " ".join(str(r[k]).split()) for k in ("when", "then", "never")
                            if r.get(k)},
            })
        out.append({
            "tabs": {k: v for k, v in canon.items() if v is not None},
            "extra": rest,
            "stem": f.stem,
            "name": c.get("name") or f.stem,
            "cls": c.get("class") or "—",
            "definition": " ".join(str(c.get("definition") or "").split()),
            "has_knowledge": kp.is_file(),
            "topics": topics,
            "rules": rule_topics,
            "declaration": declaration_view(doc),
            "columns": len((doc.get("grounding", {}).get("sources") or [{}])[0].get("columns") or {}),
            "bound": sum(1 for r in rule_topics if r["canons"]),
            "relation": (doc.get("grounding", {}).get("sources") or [{}])[0].get("relation") or "—",
        })
    idx = kdir / "index.md"
    return {
        "bundle": root.name,
        "concepts": out,
        "knowledge_intro": sections(idx.read_text(encoding="utf-8")) if idx.is_file() else [],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    root = pathlib.Path(a.bundle).resolve()
    if not P.concept_files(root):
        print(f"REFUSED: no concept document under {P.concepts_dir(root)}")
        return 2
    if not TEMPLATE.is_file():
        print(f"REFUSED: {TEMPLATE.name} is missing")
        return 2
    data = build(root)
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    left = sorted(set(re.findall(r"__[A-Z_]+__", html)))
    out = pathlib.Path(a.out) if a.out else (root / "knowledge" / "explorer.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    n_k = sum(1 for c in data["concepts"] if c["has_knowledge"])
    n_r = sum(len(c["rules"]) for c in data["concepts"])
    print(f"PASS: gen_knowledge_explorer — wrote {out}: {len(data['concepts'])} concept(s) in "
          f"{len({c['cls'] for c in data['concepts']})} group(s), {n_r} rule(s), "
          f"{n_k} with a knowledge page. Unsubstituted: {left or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
