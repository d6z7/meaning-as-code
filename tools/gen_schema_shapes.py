#!/usr/bin/env python3
"""
gen_schema_shapes.py — generate the STRUCTURAL SHAPE section of the Shape Reference from mac.schema.json.

Not a flat key list — an annotated YAML skeleton per object type showing WHERE each key nests, in WHAT
context it is valid (incl. per-class conditionals), its type/enum, and the x- extension rule. The current,
can't-drift companion to the closed-vocabulary schema. Domain-neutral (reads the schema only).

It writes ONLY the block between the GENERATED markers in the target doc, so the hand-written reference
prose around it (the naming contract, reference syntax) is preserved across regenerations.

Usage:
  python tools/gen_schema_shapes.py                 # inject into reference_manual/shape_reference.md
  python tools/gen_schema_shapes.py --check         # gate: fail if the doc's generated block is stale
"""
import json, argparse, re
from pathlib import Path

BEGIN = "<!-- BEGIN GENERATED:schema-shapes (tools/gen_schema_shapes.py — do not edit inside this block) -->"
END   = "<!-- END GENERATED:schema-shapes -->"

def load(p): return json.loads(Path(p).read_text())

class Gen:
    def __init__(self, schema):
        self.s = schema
        self.defs = schema.get("$defs", {})

    def deref(self, node):
        seen = []
        while isinstance(node, dict) and "$ref" in node:
            name = node["$ref"].split("/")[-1]
            seen.append(name)
            node = self.defs.get(name, {})
        return node, (seen[-1] if seen else None)

    def annot(self, node, required, condnote=""):
        bits = []
        if required: bits.append("REQUIRED")
        if condnote: bits.append(condnote)
        real, _ = self.deref(node)
        if "enum" in real: bits.append("enum: " + " | ".join(map(str, real["enum"])))
        elif "const" in real: bits.append("= " + str(real["const"]))
        else:
            t = real.get("type")
            if isinstance(t, list): t = "|".join(t)
            if t and t not in ("object", "array"): bits.append(t)
        d = (real.get("description") or node.get("description") or "").strip()
        if d:
            first = d.split(". ")[0]
            if len(first) > 72:
                first = first[:72].rsplit(" ", 1)[0] + "…"   # cut on a word boundary, not mid-word
            bits.append(first)
        return "  # " + " · ".join(bits) if bits else ""

    def pick_oneof(self, node):
        """oneOf/anyOf -> (richest branch, 'one of: a | b' note). Else (node, '')."""
        branches = node.get("oneOf") or node.get("anyOf")
        if not branches:
            return node, ""
        def kind(b):
            b2, _ = self.deref(b)
            if b2.get("properties"): return "object"
            return b2.get("type") or "value"
        def rank(b):
            b2, _ = self.deref(b)
            return 3 if b2.get("properties") else 2 if b2.get("type") == "object" \
                else 1 if b2.get("type") == "array" else 0
        chosen, _ = self.deref(max(branches, key=rank))
        if node.get("description") and not chosen.get("description"):
            chosen = dict(chosen, description=node["description"])
        alts = " | ".join(dict.fromkeys(kind(b) for b in branches))
        return chosen, f"one of: {alts}"

    def closure(self, node):
        ap = node.get("additionalProperties", True)
        xp = "^x-" in (node.get("patternProperties") or {})
        if ap is False and xp: return "  # closed: only keys above + x-*"
        if ap is False: return "  # closed: only keys above"
        return "  # open: extra keys allowed"

    def render(self, node, indent, required_keys, path, depth, condmap=None, top=False):
        out = []
        node, refname = self.deref(node)
        if refname and refname in path:           # cycle guard
            return [f"{'  '*indent}# … recurse: see $defs.{refname}"]
        path = path + ([refname] if refname else [])
        props = node.get("properties", {})
        if not props:
            return out
        for k, v in props.items():
            if top and out:                       # blank line between top-level key-blocks (legibility)
                out.append("")
            req = k in (required_keys or [])
            cond = (condmap or {}).get(k, "")
            v2, rname = self.deref(v)
            v2, altnote = self.pick_oneof(v2)          # follow oneOf/anyOf to its richest branch
            if altnote:
                cond = " · ".join(x for x in [cond, altnote] if x)
            vtype = v2.get("type")
            line = f"{'  '*indent}{k}:"
            if vtype == "object" or "properties" in v2:
                out.append(line + self.annot(v2, req, cond) + (self.closure(v2) if depth>=1 else ""))
                if depth < 4:
                    out += self.render(v2, indent+1, v2.get("required",[]), path, depth+1)
            elif vtype == "array":
                items, iname = self.deref(v2.get("items", {}))
                items, _ = self.pick_oneof(items)
                if items.get("properties"):
                    out.append(line + self.annot(v2, req, cond))
                    out.append(f"{'  '*(indent+1)}- <item>" + (f"  # $defs.{iname}" if iname else ""))
                    if depth < 4:
                        out += self.render(items, indent+2, items.get("required",[]), path, depth+1)
                else:
                    out.append(line + " [ ... ]" + self.annot(v2, req, cond))
            else:
                out.append(line + " <…>" + self.annot(v2, req, cond))
        return out

    def class_conditionals(self, filedef):
        """Parse allOf if/then -> {class: [notes]} for the per-class table."""
        rows = {}
        for a in filedef.get("allOf", []):
            cond = a.get("if", {})
            cl = (((cond.get("properties") or {}).get("concept") or {}).get("properties") or {}).get("class", {}).get("const")
            then = a.get("then", {})
            notes = []
            for rk in then.get("required", []): notes.append(f"requires `{rk}`")
            forb = (then.get("not") or {}).get("required", [])
            for fk in forb: notes.append(f"forbids `{fk}`")
            tp = (then.get("properties") or {})
            for pk, pv in tp.items():
                sub = (pv.get("properties") or {})
                for sk, sv in sub.items():
                    for rr in sv.get("required", []): notes.append(f"requires `{pk}.{sk}.{rr}`")
                    for rr in pv.get("required", []): notes.append(f"requires `{pk}.{rr}`")
            if cl and notes: rows.setdefault(cl, []).extend(notes)
        return rows

    def file_block(self, refname):
        fd = self.defs.get(refname, {})
        disc = {"ConceptFile": "concept", "RulesFile": "rules", "EdgesFile": "edges",
                "TableFile": "table", "TransformFile": "transforms"}.get(refname, "?")
        lines = [f"### {refname}", "",
                 f"*discriminator key:* `{disc}:` · *required:* {', '.join('`'+r+'`' for r in fd.get('required',[]))}",
                 "", "```yaml"]
        lines += self.render(fd, 0, fd.get("required", []), [refname], 0, top=True)
        if "^x-" in (fd.get("patternProperties") or {}):
            lines.append("# x-<name>:  project-specific extension keys allowed anywhere (only sanctioned extension)")
        lines.append("```")
        cc = self.class_conditionals(fd)
        if cc:
            lines += ["", "**Per `concept.class` (conditional shape):**", ""]
            for cl in ["entity", "event", "measure", "enumeration", "reference", "grouping"]:
                if cl in cc:
                    lines.append(f"- **{cl}** — " + "; ".join(dict.fromkeys(cc[cl])))
        lines.append("")
        return "\n".join(lines)

    def version(self):
        mm = re.search(r"v?(\d+\.\d+\.\d+)", self.s.get("description", ""))
        return mm.group(1) if mm else "?"

    def block(self):
        """The generated section that lives between the markers (no top-level H1 — the doc owns that)."""
        head = [f"## Structural shapes — generated (schema {self.version()})", "",
                "_Generated from [`mac.schema.json`](../mac.schema.json) by `tools/gen_schema_shapes.py`._",
                "_Do not hand-edit between the markers; re-run the generator. The closed vocabulary is",
                "authoritative in the schema — this is its readable, per-object-type face._", ""]
        roots = [b["$ref"].split("/")[-1] for b in self.s.get("oneOf", [])]
        return "\n".join(head) + "\n" + "\n".join(self.file_block(r) for r in roots)

def splice(existing, block):
    payload = f"{BEGIN}\n\n{block}\n{END}"
    if existing and BEGIN in existing and END in existing:
        pre = existing[:existing.index(BEGIN)]
        post = existing[existing.index(END) + len(END):]
        return pre + payload + post
    # no markers yet: append a markers section to whatever exists
    sep = "\n\n" if existing.strip() else ""
    return (existing.rstrip() + sep + payload + "\n") if existing else payload + "\n"

if __name__ == "__main__":
    here = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=str(here / "mac.schema.json"))
    ap.add_argument("-o", default=str(here / "reference_manual" / "shape_reference.md"))
    ap.add_argument("--check", action="store_true", help="fail (exit 1) if the doc's generated block is stale")
    a = ap.parse_args()
    block = Gen(load(a.schema)).block()
    target = Path(a.o)
    existing = target.read_text() if target.exists() else ""
    updated = splice(existing, block)
    if a.check:
        if existing != updated:
            print(f"STALE: {a.o} — regenerate with: python tools/gen_schema_shapes.py")
            raise SystemExit(1)
        print(f"OK: {a.o} generated block is current.")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(updated)
        print(f"{'injected into' if BEGIN in existing else 'wrote'} {a.o}")
