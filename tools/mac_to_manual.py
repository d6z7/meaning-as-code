#!/usr/bin/env python3
"""
mac_to_manual.py — generate a source-authored operator manual (`docs/manual.md`) from a
markdown TEMPLATE + the ontology, so the man page can never silently drift from the model.

A companion to mac_to_explorer.py. It REUSES that projector's parser (build_model) so the manual
and the explorer draw from the SAME parsed ontology — the tables and lists in the manual are the
model, not a hand-transcription of it. The split is deliberate:

  • the SME owns the PROSE — framing, teaching, worked examples — written directly in the template;
  • the machine owns the FACTS — concept/measure tables, decision lanes, option gates, limitations,
    the SEE ALSO index — emitted into `{{tokens}}` the template places.

Output is ONE markdown file (docs/manual.md) that serves two consumers unchanged: any static-docs
host that renders markdown, and the explorer's Manual tab (mac_to_explorer.load_manual reads exactly
this path). Generation stays inside the explorer's markdown subset (pipe tables, `-` bullets,
#/##/### headings, > blockquotes, `code`, **bold** — no links, ordered/nested lists or raw HTML), so
what renders in the browser matches what a full markdown renderer shows on the docs site.

Source-agnostic: every token is filled from the parsed model alone; nothing here names a source. A
project with no `docs/manual.template.md` is a no-op (exit 0) — absent template degrades, never errors.

Usage:
  python3 tools/mac_to_manual.py <ontology_root> [-o out.md] [--template path]
  # default template: <root>/docs/manual.template.md   default output: <root>/docs/manual.md
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))          # so `import mac_to_explorer` resolves when run as a script
import mac_to_explorer as mx           # reuse build_model() + the DECISION lane vocabulary  # noqa: E402


# ── markdown-safe text helpers (keep every emitted string inside the explorer's mdRender subset) ──

def _flat(s):
    """Collapse any whitespace/newlines to single spaces — folded YAML scalars become one line."""
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def _cell(s):
    """Table/bullet-safe: single line, and no literal '|' (a pipe would split a table row / break a
    paragraph line, since mdRender treats a stray '|' as a table signal)."""
    return _flat(s).replace("|", "/")


def _first_sentence(s, cap=170):
    t = _flat(s)
    parts = re.split(r"(?<=[.!?])\s", t, maxsplit=1)
    t = parts[0] if parts else t
    if len(t) > cap:
        t = t[:cap - 1].rstrip() + "…"
    return t.replace("|", "/")


def _first_line(s):
    for ln in str(s or "").splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def _formula(template):
    """The renderable SQL/expression: first non-empty template line, trailing `-- comment` dropped."""
    ln = _first_line(template)
    ln = ln.split("--", 1)[0].strip()
    return ln.replace("|", "/")


def _all_rules(model):
    """Every judgement rule in the model, tagged with its owning concept id ('' for general rules)."""
    out = []
    for c in model.get("concepts", []):
        for r in c.get("rules", []):
            out.append((r, c.get("id", "")))
    for r in model.get("general_rules", []):
        out.append((r, ""))
    return out


def _gist(rule):
    """A one-line headline for a rule: its authored `subject`, else its `when` clause."""
    return _cell(rule.get("subject") or rule.get("when") or rule.get("id"))


def _primary_rel(concept):
    """The concept's primary grounding relation (the table it binds to)."""
    src = concept.get("sources") or []
    return src[0].get("relation", "") if src else ""


def _primary_cols(concept):
    src = concept.get("sources") or []
    cols = src[0].get("columns", []) if src else []
    return cols if isinstance(cols, list) else [cols]


def _register_total(concept):
    """The closed value-count if the concept is pinned by a register (enum lookup), else None."""
    regs = concept.get("registers") or []
    return regs[0].get("total") if regs else None


# ── token producers — each returns a markdown block filled from the model alone ──

LANE_ORDER = ["COMMIT", "ASK", "REFUSE", "INVARIANT", "OTHER"]
LANE_GLOSS = {
    "COMMIT":    "resolve and answer (disclosing any assumed default)",
    "ASK":       "a required choice is open with no safe default — ask",
    "REFUSE":    "the question asks for something the model must not answer that way",
    "INVARIANT": "a guarantee that always holds",
    "OTHER":     "unclassified",
}


def tok_meta(model):
    m = model.get("meta", {})
    lanes = model.get("lanes", {})
    lane_bits = " · ".join("%s %d" % (k, lanes.get(k, 0)) for k in ("COMMIT", "ASK", "REFUSE", "INVARIANT")
                           if lanes.get(k, 0))
    rows = [
        "- **Source** — `%s`" % _cell(m.get("source", "")),
        "- **Concepts** — %d" % m.get("concept_count", 0),
        "- **Rules** — %d  (%s)" % (m.get("rule_count", 0), lane_bits or "—"),
    ]
    if m.get("derived_count"):
        rows.append("- **Derived readings** — %d" % m["derived_count"])
    if m.get("edge_count"):
        rows.append("- **Joins** — %d" % m["edge_count"])
    return "\n".join(rows)


def tok_concepts(model):
    concepts = model.get("concepts", [])
    if not concepts:
        return "(no concepts)"
    out = ["| Concept | Kind | What it is |", "| --- | --- | --- |"]
    for c in concepts:
        name = _cell(c.get("label") or c.get("id"))
        out.append("| **%s** | %s | %s |" % (name, _cell(c.get("klass")), _first_sentence(c.get("definition"))))
    return "\n".join(out)


def tok_measures(model):
    derived = model.get("derived_measures", [])
    if derived:
        out = ["| Reading | Produces | Formula | Guardrails |", "| --- | --- | --- | --- |"]
        for d in derived:
            guards = "; ".join(_cell(c).rstrip(".") for c in d.get("conditions", [])) or "—"
            out.append("| `%s` | %s | `%s` | %s |" % (
                _cell(d.get("id")), _cell(d.get("derives")) or "—", _formula(d.get("template")) or "—", guards))
        return "\n".join(out)
    # no derived-measure registry — fall back to the concepts typed as measures
    measures = [c for c in model.get("concepts", []) if c.get("klass") == "measure"]
    if not measures:
        return "(no measures declared)"
    out = ["| Measure | What it is |", "| --- | --- |"]
    for c in measures:
        out.append("| **%s** | %s |" % (_cell(c.get("label") or c.get("id")), _first_sentence(c.get("definition"))))
    return "\n".join(out)


def tok_synopsis(model):
    """The compact man-page SYNOPSIS of the question grammar: `ask <MEASURE> [--flag <v>] …`.
    Flags are the measure's dimension concepts (joined via an edge, a discriminator on the fact's own
    relation, or an enumeration on a joined dimension). A flag is REQUIRED (bare) when a
    mandatory_no_default decision-policy slot governs it, else OPTIONAL ([...]). Value hints are inline
    enums for small register-backed sets, else <PLACEHOLDER>. Mutually-exclusive `(a|b)` groups and
    nested sub-options are NOT emitted — they need an alternative/sub-option relation the model does not
    declare; where a source declares neither (as here), the synopsis is simply all-optional."""
    concepts = model.get("concepts", [])
    by_id = {c["id"]: c for c in concepts}
    edges = model.get("edges", [])
    measures = [c for c in concepts if c.get("klass") == "measure"]
    if not measures:
        return "(no measure to build a synopsis for)"
    derived = model.get("derived_measures", [])
    mandatory = [s for s in model.get("decision_policy", []) if s.get("policy") == "mandatory_no_default"]

    def required(c):
        blob = " ".join((s.get("slot", "") + " " + s.get("governing_rule", "")).lower() for s in mandatory)
        key = (c.get("label") or c.get("id") or "").lower()
        return bool(key) and (key in blob or (c.get("id") or "").lower() in blob)

    INLINE_MAX = 6

    def flag(c):
        name = "--" + (c.get("label") or c.get("id") or "").strip().lower().replace(" ", "-")
        regs = c.get("registers") or []
        if c.get("klass") == "enumeration" and regs and (regs[0].get("total") or 0) <= INLINE_MAX:
            hint = "|".join(_cell(r[0]).lower() for r in (regs[0].get("rows") or []) if r)
        else:
            hint = "<%s>" % (c.get("label") or c.get("id") or "V").upper()
        return "%s %s" % (name, hint)

    blocks = []
    for M in measures:
        m_rel = _primary_rel(M)
        flag_ids, seen = [], set()
        for e in edges:                                  # joined dimensions
            if e.get("from") == M["id"] and e.get("to") in by_id and e["to"] not in seen:
                flag_ids.append(e["to"]); seen.add(e["to"])
        joined_rels = {_primary_rel(by_id[i]) for i in flag_ids}
        for c in concepts:                               # discriminators on the fact + enums on a joined dim
            if c["id"] in seen or c["id"] == M["id"] or c.get("klass") == "measure":
                continue
            rel = _primary_rel(c)
            if rel == m_rel or (c.get("klass") == "enumeration" and rel in joined_rels):
                flag_ids.append(c["id"]); seen.add(c["id"])

        req = [flag(by_id[i]) for i in flag_ids if required(by_id[i])]
        opt = [flag(by_id[i]) for i in flag_ids if not required(by_id[i])]
        parts = req + ["[%s]" % o for o in opt]          # required bare, optional bracketed

        head, lines, cur = "ask <MEASURE>", [], "ask <MEASURE>"
        indent = " " * (len(head) + 1)
        for p in parts:
            if cur == head:
                cur = head + " " + p
            elif len(cur) + 1 + len(p) > 78:
                lines.append(cur); cur = indent + p
            else:
                cur = cur + " " + p
        lines.append(cur)

        if derived:
            enum = "MEASURE := %s      # %s" % (
                " | ".join(_cell(d.get("id")) for d in derived), _cell(M.get("label") or M.get("id")))
        else:
            enum = "MEASURE := %s" % _cell(M.get("label") or M.get("id"))

        legend = (["()  required"] if req else []) + ["[]  optional (has a disclosed default)", "|  alternatives"]
        syn = "\n".join(lines) + "\n\n" + enum + "\n\n" + "     ".join(legend)
        blocks.append(syn if len(measures) == 1 else "# %s\n%s" % (_cell(M.get("label") or M.get("id")), syn))
    return "\n\n".join(blocks)


def tok_ask_grammar(model):
    """The question grammar as an explicit WHITELIST: for each measure, every dimension AND every
    property a question may slice or group it by, named. A property is CLOSED (its allowed values
    listed by name, from the register that pins it) or OPEN (any value, with the column's data type
    as a hint). Axes come from the join graph (edges leaving the measure) + concepts grounded on the
    fact's own relation (discriminators). Only MODELLED axes appear — an axis named in policy but
    never grounded is absent by construction, the honest signal the model does not yet carry it."""
    concepts = model.get("concepts", [])
    by_id = {c["id"]: c for c in concepts}
    edges = model.get("edges", [])
    measures = [c for c in concepts if c.get("klass") == "measure"]
    if not measures:
        return "(no measure to build a question grammar for)"

    # data-type hint per physical column, from the data plane: {(relation_leaf, column): type}
    type_of = {}
    for rel in model.get("relations", []) or []:
        leaf = rel.get("leaf") or rel.get("name")
        for col in rel.get("columns", []) or []:
            if col.get("name"):
                type_of[(leaf, col["name"])] = col.get("type", "")

    def closed_values(rel):
        """{column: (named values, total)} for register-backed enumerations grounded on this relation."""
        out = {}
        for c in concepts:
            if c.get("klass") != "enumeration" or _primary_rel(c) != rel:
                continue
            regs = c.get("registers") or []
            if not regs:
                continue
            vals = [r[0] for r in (regs[0].get("rows") or []) if r]   # register convention: 1st col = the code
            for col in _primary_cols(c):
                out[col] = (vals, regs[0].get("total"))
        return out

    VCAP = 14

    def value_cell(rel, col):
        cv = closed_values(rel).get(col)
        if cv:
            vals, total = cv
            more = "" if (total is None or total <= VCAP) else " …(+%d)" % (total - VCAP)
            return "**closed** · %s%s" % (", ".join(_cell(v) for v in vals[:VCAP]), more)
        t = type_of.get((mx._rel_leaf(rel), col), "")
        return "open (%s)" % _cell(t) if t else "open"

    blocks = []
    for M in measures:
        m_rel = _primary_rel(M)
        joined_ids = {e.get("to") for e in edges if e.get("from") == M["id"]}
        axes = []   # (dimension label, its relation, [properties])
        for e in edges:
            if e.get("from") == M["id"] and e.get("to") in by_id:
                d = by_id[e["to"]]
                axes.append((d.get("label") or d.get("id"), _primary_rel(d), _primary_cols(d)))
        for c in concepts:
            if c["id"] == M["id"] or c.get("klass") == "measure" or c["id"] in joined_ids:
                continue
            if _primary_rel(c) == m_rel:
                axes.append((c.get("label") or c.get("id"), m_rel, _primary_cols(c)))

        rows = ["| Dimension | Property | Values you can name |", "| --- | --- | --- |"]
        for label, rel, cols in axes:
            for i, col in enumerate(cols):
                rows.append("| %s | `%s` | %s |" % (
                    ("**%s**" % _cell(label)) if i == 0 else "", _cell(col), value_cell(rel, col)))
        table = "\n".join(rows)
        blocks.append(("**%s**\n\n%s" % (_cell(M.get("label") or M.get("id")), table)) if len(measures) > 1 else table)
    return "\n\n".join(blocks)


def tok_decision_lanes(model):
    buckets = {}
    for r, cid in _all_rules(model):
        buckets.setdefault(r.get("decision", "OTHER"), []).append((r, cid))
    blocks = []
    for lane in LANE_ORDER:
        items = buckets.get(lane)
        if not items:
            continue
        # bare lane word in a paragraph → the explorer chips it (COMMIT/ASK/REFUSE); INVARIANT/OTHER stay plain
        block = ["%s · %s" % (lane, LANE_GLOSS[lane]), ""]
        for r, cid in items:
            block.append("- `%s` — %s" % (_cell(r.get("id")), _gist(r)))
        blocks.append("\n".join(block))
    return "\n\n".join(blocks) if blocks else "(no rules)"


def tok_options(model):
    policy = model.get("decision_policy", [])
    if not policy:
        return "(no decision policy)"
    buckets = {}
    for s in policy:
        buckets.setdefault(s.get("lane", "OTHER"), []).append(s)
    gloss = {
        "REFUSE": "hard gates — worst-wins, these override any default on the same question",
        "ASK":    "required, no defensible default — the model asks",
        "COMMIT": "safe defaults — assumed and disclosed",
    }
    blocks = []
    for lane in ("REFUSE", "ASK", "COMMIT"):
        slots = buckets.get(lane)
        if not slots:
            continue
        block = ["%s · %s" % (lane, gloss[lane]), ""]
        for s in slots:
            block.append("- `%s` — %s" % (_cell(s.get("slot")), _cell(s.get("on_missing")) or "—"))
        blocks.append("\n".join(block))
    return "\n\n".join(blocks) if blocks else "(no decision policy)"


def tok_limitations(model):
    seen, out = set(), []
    for r, cid in _all_rules(model):
        if r.get("decision") != "REFUSE":
            continue
        rid = r.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        out.append("- `%s` — %s" % (_cell(rid), _cell(r.get("then") or r.get("when"))))
    for s in model.get("decision_policy", []):
        if s.get("lane") != "REFUSE":
            continue
        sid = s.get("slot")
        if sid in seen:
            continue
        seen.add(sid)
        out.append("- `%s` — %s" % (_cell(sid), _cell(s.get("on_missing"))))
    return "\n".join(out) if out else "(no declared limitations)"


def tok_see_also(model):
    out = []
    by_domain = {}
    for c in model.get("concepts", []):
        by_domain.setdefault(c.get("domain", "general"), []).append(c)
    if by_domain:
        out.append("Concepts —")
        for dom in by_domain:
            for c in by_domain[dom]:
                out.append("- `%s`" % _cell(c.get("file")))
    files = []
    if model.get("derived_measures"):
        files.append("`ontology/rules.yaml`")
    if model.get("general_rules") or model.get("decision_policy"):
        files.append("`ontology/query_rules.yaml`")
    if model.get("edges"):
        files.append("`ontology/edges.yaml`")
    if files:
        out += ["", "Rules & policy —", "- " + ", ".join(files)]
    edges = model.get("edges", [])
    if edges:
        out += ["", "Joins —"]
        for e in edges:
            jr = _cell(e.get("join_rule"))
            tail = " (`%s`)" % jr if jr else ""
            out.append("- %s → %s%s" % (_cell(e.get("from")), _cell(e.get("to")), tail))
    return "\n".join(out) if out else "(nothing to cross-reference)"


TOKENS = {
    "meta": tok_meta,
    "concepts": tok_concepts,
    "measures": tok_measures,
    "synopsis": tok_synopsis,
    "ask_grammar": tok_ask_grammar,
    "decision_lanes": tok_decision_lanes,
    "options": tok_options,
    "limitations": tok_limitations,
    "see_also": tok_see_also,
}

TOKEN_RX = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

BANNER = ("> Generated from the ontology by `mac_to_manual.py` — do not edit by hand. Author the prose in "
          "`docs/manual.template.md`; the tables and lists below are filled from the concept, rule and "
          "policy files, so this page can never drift from the model.")


def render_template(text, model):
    unknown = []

    def sub(m):
        key = m.group(1)
        fn = TOKENS.get(key)
        if fn is None:
            unknown.append(key)
            return m.group(0)                 # leave the literal so the author sees the typo
        return fn(model)

    body = TOKEN_RX.sub(sub, text)
    return _inject_banner(body), unknown


def _inject_banner(body):
    """Place the generated-notice blockquote right after the leading `# H1` (or at the very top)."""
    lines = body.split("\n")
    for idx, ln in enumerate(lines):
        if ln.strip() == "":
            continue
        if ln.lstrip().startswith("# "):
            lines[idx + 1:idx + 1] = ["", BANNER]
            return "\n".join(lines)
        break
    return BANNER + "\n\n" + body


def find_template(root, explicit):
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    for cand in ("docs/manual.template.md", "docs/manual.tmpl.md", "MANUAL.template.md"):
        p = root / cand
        if p.exists():
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description="Generate docs/manual.md from a template + the ontology.")
    ap.add_argument("root", help="ontology project root (contains ontology/concepts/ or concepts/)")
    ap.add_argument("-o", "--out", help="output markdown path (default: <root>/docs/manual.md)")
    ap.add_argument("--template", help="template path (default: <root>/docs/manual.template.md)")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    tpl = find_template(root, a.template)
    if not tpl:
        sys.stderr.write("mac_to_manual: no manual template under %s — skipping (nothing to generate)\n" % root)
        return
    model = mx.build_model(root)
    body, unknown = render_template(tpl.read_text(encoding="utf-8"), model)

    out = Path(a.out) if a.out else (root / "docs" / "manual.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")

    if unknown:
        sys.stderr.write("mac_to_manual: WARNING — unknown token(s) left un-filled: %s (known: %s)\n" % (
            ", ".join(sorted(set(unknown))), ", ".join(sorted(TOKENS))))
    sys.stderr.write("mac_to_manual: %s — %d concepts, %d rules → %s\n" % (
        model["meta"]["source"], model["meta"]["concept_count"], model["meta"]["rule_count"], out))


if __name__ == "__main__":
    main()
