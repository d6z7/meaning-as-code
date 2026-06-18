#!/usr/bin/env python3
"""
mac_to_okf.py — project a MAC ontology onto a Google Cloud Open Knowledge Format (OKF) v0.1 bundle.

OKF (https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) is a portable
"LLM-wiki" format: a directory tree of markdown files, each with YAML frontmatter whose ONE required
field is `type`. It is the agent-context / knowledge-bundle target — a different family from the query
projectors (OSI, openCypher, RDF). It maps MAC's *Meaning* level onto human- and agent-readable docs.

The point: OKF's own reference implementation enriches each concept with "schemas, citations, and join
paths" via a SECOND LLM pass that crawls documentation. MAC already holds all of that as data, so this
projector emits the enriched bundle DETERMINISTICALLY — no crawl, no guess.

Mapping (all from data already in the MAC files):
  each concept            -> one OKF concept doc <Name>.md
    class                 -> frontmatter `type`  (measure->Metric, reference->Reference, entity->Entity, …)
    label / definition    -> `title` / `description` (first sentence) + body prose
    grounding (table)     -> frontmatter `resource` URI + the conventional `# Schema` column table
    edges (endpoints)     -> `## Relationships` prose with bundle-relative links (`/Customer.md`)
    enumeration value_set -> `# Values` table
    metadata + governance -> `tags`, `timestamp`, and a `# Citations` pointer back to the source .yaml
  bundle index            -> reserved `index.md`  (directory listing)
  change_log entries      -> reserved `log.md`    (update history)

Validation: OKF has no JSON Schema. `--check` instead asserts every emitted doc has parseable frontmatter
with the required `type`, and that every internal link resolves inside the bundle (OKF tolerates broken
links; we hold ours to a higher bar).

Usage:
  python3 tools/mac_to_okf.py <ontology_root> [-o out_bundle_dir]   # default: <root>/projections/<name>.okf
  python3 tools/mac_to_okf.py <ontology_root> --check               # validate the bundle just written
"""
import argparse
import sys
from pathlib import Path

import yaml
from mac_project import resolve, meaning_by_table

NODE_CLASSES = {"entity", "event", "reference", "grouping"}
TYPE_OF = {"entity": "Entity", "event": "Event", "measure": "Metric",
           "reference": "Reference", "enumeration": "Enumeration", "grouping": "Grouping"}


def load(p):
    return yaml.safe_load(Path(p).read_text()) or {}


def first_sentence(text):
    t = " ".join(str(text or "").split())
    if not t:
        return ""
    cut = t.find(". ")
    return (t[:cut + 1] if cut != -1 else t).strip()


def ground_table(d):
    g = d.get("grounding") or {}
    if isinstance(g.get("table"), str):
        return g["table"], g.get("schema")
    for s in (g.get("sources") or []):
        if isinstance(s, dict) and isinstance(s.get("relation"), str):
            parts = s["relation"].split(".")
            return parts[-1], (".".join(parts[:-1]) or None)
    return None, None


def table_cols(root, name):
    if not name:
        return []
    f = resolve(root).descriptors / f"{name}.yaml"
    return [c for c in (load(f).get("columns") or []) if isinstance(c, dict) and c.get("name")] if f.exists() else []


def frontmatter(d):
    """Emit YAML frontmatter (insertion order preserved), `type` first."""
    body = yaml.safe_dump({k: v for k, v in d.items() if v not in (None, [], "")},
                          sort_keys=False, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{body}\n---\n"


def doc_path(name):
    return f"{name}.md"


def build_bundle(root):
    """Return {relpath: markdown_text} for the whole OKF bundle."""
    concepts = [(f, load(f)) for f in sorted((resolve(root).ontology / "concepts").glob("**/*.yaml"))]
    concepts = [(f, d) for f, d in concepts if (d.get("concept") or {}).get("name")]
    source = next((str((d.get("metadata") or {}).get("source")) for _, d in concepts
                   if (d.get("metadata") or {}).get("source")), root.name)
    name = source.lower()

    names = {(d["concept"]["name"]) for _, d in concepts}                      # all concept names in bundle
    edges = (load(resolve(root).ontology / "edges.yaml").get("edges") or []) if (resolve(root).ontology / "edges.yaml").exists() else []
    mbt = meaning_by_table([d for _, d in concepts], lambda d: ground_table(d)[0])  # Option B: meaning from field rules

    files = {}
    listing = []     # (title, type, desc, link) for index.md
    history = []     # (date, concept, change)

    for f, d in concepts:
        c = d["concept"]
        nm, cls = c["name"], c.get("class")
        meta, gov = (d.get("metadata") or {}), (d.get("governance") or {})
        tbl, schema = ground_table(d)
        last = gov.get("last_reviewed") or meta.get("version")
        desc = first_sentence(c.get("definition"))

        fm = {
            "type": TYPE_OF.get(cls, (cls or "Concept").title()),
            "title": c.get("label") or nm,
            "description": desc,
            "resource": (f"table://{schema}/{tbl}" if tbl else None),
            "tags": [t for t in [source, cls, (f"confidence:{meta['confidence']}" if meta.get("confidence") else None)] if t],
            "timestamp": (str(last) if last else None),
        }

        b = [f"# {fm['title']}", "", " ".join(str(c.get("definition") or "").split()) or desc, ""]
        purpose = ((c.get("semantics") or {}).get("purpose"))
        if purpose:
            b += ["## Purpose", "", " ".join(str(purpose).split()), ""]

        # # Schema — the grounded physical columns (OKF conventional heading)
        cols = table_cols(root, tbl)
        if cols:
            b += [f"# Schema", "", f"Grounded in `{schema + '.' if schema else ''}{tbl}`.", "",
                  "| column | type | role | description |", "|---|---|---|---|"]
            for col in cols:
                meaning = mbt.get((tbl, col["name"])) or col.get("description", "")   # field rule first
                b.append(f"| `{col['name']}` | {col.get('type', '')} | {col.get('role', '')} "
                         f"| {' '.join(str(meaning).split())} |")
            b.append("")

        # # Values — closed enumeration code list
        vals = d.get("values") or {}
        if vals.get("items"):
            closed = vals.get("closure") == "closed"
            b += [f"# Values", "", f"{'Closed' if closed else 'Open'} code list"
                  + (f" — these {len(vals['items'])} are the complete set." if closed else "."), "",
                  "| code | label | meaning |", "|---|---|---|"]
            for it in vals["items"]:
                if isinstance(it, dict) and it.get("code"):
                    b.append(f"| `{it['code']}` | {it.get('label', '')} | {' '.join(str(it.get('meaning', '')).split())} |")
            b.append("")

        # ## Relationships — edges as bundle-relative links (the kind is in the prose, per OKF)
        rels = []
        for e in edges:
            ep = e.get("endpoints") or {}
            fr, to = (ep.get("from") or {}), (ep.get("to") or {})
            jr = e.get("join_rule", "")
            if fr.get("concept") == nm and to.get("concept") in names:
                rels.append(f"- **{fr.get('role') or e.get('edge_id')}** → [{to['concept']}](/{doc_path(to['concept'])}) "
                            f"(cardinality {to.get('cardinality', '?')}; grounded join `{jr}`)")
            elif to.get("concept") == nm and fr.get("concept") in names:
                rels.append(f"- inverse of **{fr.get('role') or e.get('edge_id')}** ← [{fr['concept']}](/{doc_path(fr['concept'])}) "
                            f"(grounded join `{jr}`)")
        if rels:
            b += ["## Relationships", ""] + rels + [""]

        # ## Derivation — for measures that point at a rule
        if d.get("derived_by_rule"):
            b += ["## Derivation", "", f"Computed by rule `{d['derived_by_rule']}` (see the MAC rules layer); "
                  "do not re-derive the formula.", ""]

        # # Citations — provenance back to the authoritative MAC source
        rel_src = f.relative_to(resolve(root).ontology).as_posix()   # ontology-relative citation
        b += ["# Citations", "", f"1. MAC concept source of record: `{rel_src}` "
              f"(schema_version {meta.get('schema_version', '?')}, confidence {meta.get('confidence', '?')}).", ""]

        files[doc_path(nm)] = frontmatter(fm) + "\n" + "\n".join(b)
        listing.append((fm["title"], fm["type"], desc, doc_path(nm)))
        for ch in (gov.get("change_log") or []):
            if isinstance(ch, dict) and ch.get("date"):
                history.append((str(ch["date"]), nm, ch.get("change", "")))

    # index.md (reserved) — directory listing
    idx = [frontmatter({"type": "Index", "title": f"{source} knowledge bundle",
                        "description": f"OKF bundle projected from the {source} MAC ontology."}), "",
           f"# {source} knowledge bundle", "",
           f"Projected from the **{source}** MAC ontology by `mac_to_okf.py`. {len(listing)} concepts.", "",
           "| concept | type | description |", "|---|---|---|"]
    for title, typ, desc, link in sorted(listing):
        idx.append(f"| [{title}](/{link}) | {typ} | {desc} |")
    files["index.md"] = "\n".join(idx) + "\n"

    # log.md (reserved) — update history
    lg = [frontmatter({"type": "Log", "title": f"{source} update history"}), "",
          "# Update history", "", "| date | concept | change |", "|---|---|---|"]
    for date, nm, ch in sorted(history, reverse=True):
        lg.append(f"| {date} | {nm} | {' '.join(str(ch).split())} |")
    files["log.md"] = "\n".join(lg) + "\n"

    return name, files


def check_bundle(out_dir):
    """OKF has no JSON Schema; assert frontmatter+`type` parse and internal links resolve in-bundle."""
    import re
    md = sorted(Path(out_dir).rglob("*.md"))
    present = {p.relative_to(out_dir).as_posix() for p in md}
    errs = []
    link_re = re.compile(r"\]\((/[^)]+\.md)\)")
    for p in md:
        text = p.read_text()
        if not text.startswith("---\n") or "\n---\n" not in text:
            errs.append(f"{p.name}: missing YAML frontmatter")
            continue
        fm = yaml.safe_load(text.split("\n---\n", 1)[0][4:]) or {}
        if not fm.get("type"):
            errs.append(f"{p.name}: required frontmatter field `type` absent")
        for m in link_re.findall(text):
            if m.lstrip("/") not in present:
                errs.append(f"{p.name}: dangling bundle link {m}")
    n_links = sum(len(link_re.findall(p.read_text())) for p in md)
    if errs:
        print("✗ OKF bundle check FAILED:", file=sys.stderr)
        for e in errs:
            print("   - " + e, file=sys.stderr)
        return False
    print(f"✓ OKF bundle valid — {len(md)} docs, all carry `type`, all {n_links} internal links resolve", file=sys.stderr)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("-o", "--out")
    ap.add_argument("--check", action="store_true", help="validate the bundle after writing")
    a = ap.parse_args()
    root = Path(a.root)

    name, files = build_bundle(root)
    out_dir = Path(a.out) if a.out else (root / "projections" / f"{name}.okf")
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        (out_dir / rel).write_text(text)
    n_concept = len(files) - 2   # minus index.md + log.md
    print(f"wrote {out_dir}/: {n_concept} concept docs + index.md + log.md ({len(files)} files)")

    if a.check and not check_bundle(out_dir):
        sys.exit(1)


if __name__ == "__main__":
    main()
