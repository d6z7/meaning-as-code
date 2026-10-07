#!/usr/bin/env python3
"""gen_schema_shapes.py — the STRUCTURAL SHAPE section of the Shape Reference, from mac.schema.json.

Not a flat key list — an annotated YAML skeleton per object type showing WHERE each key nests, in
WHAT context it is valid (incl. per-class conditionals), its type/enum, and the x- extension rule.
The current, can't-drift companion to the closed-vocabulary schema. Domain-neutral (reads the schema
only). It writes ONLY the block between the GENERATED markers, so the hand-written reference prose
around it (the naming contract, reference syntax) survives regeneration.

TWO FALSE STATEMENTS THIS FILE PRINTED, MEASURED 2026-10-04, and what caused each.

  1. `## Structural shapes — generated (schema 0.1.14)` against a schema whose `version` field is
     `0.1.16`. `version()` REGEX-SCRAPED the first `\\d+\\.\\d+\\.\\d+` out of the schema's
     `description` — a prose changelog that still narrates "current generation v0.1.14-develop" —
     instead of reading the one field that holds the version. A second home for a fact, and the
     generator read the copy. It now reads `schema["version"]` and nothing else.

  2. The page billed as "every object type's shape" did not mention `rulings`, a key the schema has
     carried since 2026-09-28. The column map is a FREE-KEY level — `columns:` is
     `additionalProperties: {…}`, the author chooses the key names — and `render()` iterated
     `node["properties"]` only, so it emitted `columns:` as a leaf and dropped the entire per-column
     level: `role`, `identity`, `measure`, `rulings`, `register`, `axis` and everything under
     them. A second, independent cause sat behind it: a hard `depth < 4` cutoff that truncated
     SILENTLY. Both are fixed — free-key levels render as `<name>:`, and the depth cap is gone (the
     `$ref` cycle guard already terminates the walk; inline nesting cannot cycle).

  3. `--check` printed `OK: … generated block is current.` through both of those, because the
     comparator and the renderer were THE SAME CODE: it re-rendered and byte-compared, so a renderer
     that drops a key produces a page missing that key and a fresh render missing it identically.
     Agreement by construction is not evidence.

SO THE CHECK ASKS A SECOND QUESTION OF A DIFFERENT SOURCE. `admitted_keys()` is a SEPARATE walk of
`mac.schema.json` — all `oneOf`/`anyOf` branches, not the renderer's "richest" one; array items;
free-key and pattern levels — and it asserts, against the text ON DISK, that every key name the
schema admits under a file type appears in that file type's section, and that the version in the
heading is the version in the schema. Four reject classes, four mutants, and `--self-test` also
asserts that each mutant CHANGED the page: in `gen_structure_reference.py` a mutant that deleted a table
row silently stopped deleting anything when the emitter stopped emitting tables, and the self-test
reported 6/6 over a reject it was no longer exercising.

    python3 tools/gen_schema_shapes.py                # inject into reference_manual/shape_reference.md
    python3 tools/gen_schema_shapes.py --check        # exit 1 if stale, mis-versioned or incomplete
    python3 tools/gen_schema_shapes.py --self-test    # one mutant per reject class + a clean fixture
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tempfile

SELF = pathlib.Path(__file__).resolve()
ROOT = SELF.parents[1]

BEGIN = "<!-- BEGIN GENERATED:schema-shapes (tools/gen_schema_shapes.py — do not edit inside this block) -->"
END   = "<!-- END GENERATED:schema-shapes -->"

#: THE FREE-KEY LINE. A level whose key names the author chooses — a column name, a serving role —
#: is rendered as `<name>:`, so a reader can see that the level EXISTS and what its value admits.
#: Rendering nothing is what hid `rulings`.
ANY = "<name>"

HEAD_RE = re.compile(r"^## Structural shapes — generated \(schema (?P<v>[^)]*)\)\s*$", re.M)


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the renderer
# ──────────────────────────────────────────────────────────────────────────────────────────────────

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
            req = b2.get("required")
            if req and not b2.get("type"): return "+".join(req)
            return b2.get("type") or "value"
        def rank(b):
            b2, _ = self.deref(b)
            return 3 if b2.get("properties") else 2 if b2.get("type") == "object" \
                else 1 if b2.get("type") == "array" else 0
        def bare_required(b):
            """A branch that constrains WHICH keys are required and nothing else."""
            b2, _ = self.deref(b)
            return bool(b2.get("required")) and not (
                b2.get("properties") or b2.get("type") or b2.get("items") or b2.get("enum")
                or b2.get("additionalProperties") is not None)
        alts = " | ".join(dict.fromkeys(kind(b) for b in branches))
        #: A oneOf THAT ONLY CONSTRAINS `required` LEAVES THE PROPERTIES ON THE NODE, and replacing
        #: the node with such a branch discarded every one of them. Measured: `$defs.PipelineExit`
        #: declares `register`, `approval`, `gate` and `must_exit` beside a oneOf of three bare
        #: `required` lists, and the page showed NONE of the four — the same silent-drop family as
        #: the free-key level that hid `rulings`, reached by a different route.
        if all(bare_required(b) for b in branches) and (
                node.get("properties") or node.get("additionalProperties")):
            return ({k: v for k, v in node.items() if k not in ("oneOf", "anyOf")},
                    f"exactly one of: {alts}")
        chosen, _ = self.deref(max(branches, key=rank))
        if node.get("description") and not chosen.get("description"):
            chosen = dict(chosen, description=node["description"])
        return chosen, f"one of: {alts}"

    def closure(self, node):
        ap = node.get("additionalProperties", True)
        if ap is False: return "  # closed: only keys above"
        if isinstance(ap, dict) and ap: return "  # free key names; the VALUE shape is below"
        return "  # open: extra keys allowed"

    def free_level(self, node):
        """THE SCHEMA FOR AN ARBITRARY KEY'S VALUE at a free-key level, or None.

        `columns:`, `serving.naming.roles:` and `field_roles:` are maps whose KEY NAMES the author
        chooses and whose VALUES are constrained. `properties` is empty on such a node, which is why
        iterating it alone rendered `columns:` as a leaf and lost `role`, `measure` and `rulings`.
        """
        ap = node.get("additionalProperties")
        if not isinstance(ap, dict) or not ap:
            return None
        real, _ = self.deref(ap)
        real, _ = self.pick_oneof(real)
        return real if isinstance(real, dict) and real else None

    def render(self, node, indent, required_keys, path, depth, condmap=None, top=False):
        out = []
        node, refname = self.deref(node)
        if refname and refname in path:           # cycle guard — the only termination needed
            return [f"{'  '*indent}# … recurse: see $defs.{refname}"]
        path = path + ([refname] if refname else [])
        props = node.get("properties", {})
        free = self.free_level(node)
        if not props and not free:
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
            nested = self.render(v2, indent + 1, v2.get("required", []), path, depth + 1)
            if vtype == "object" or "properties" in v2 or self.free_level(v2):
                out.append(line + self.annot(v2, req, cond) + (self.closure(v2) if depth >= 1 else ""))
                out += nested
            elif vtype == "array":
                items, iname = self.deref(v2.get("items", {}))
                items, _ = self.pick_oneof(items)
                if items.get("properties") or self.free_level(items):
                    out.append(line + self.annot(v2, req, cond))
                    out.append(f"{'  '*(indent+1)}- <item>" + (f"  # $defs.{iname}" if iname else ""))
                    out += self.render(items, indent + 2, items.get("required", []), path, depth + 1)
                else:
                    out.append(line + " [ ... ]" + self.annot(v2, req, cond))
            else:
                out.append(line + " <…>" + self.annot(v2, req, cond))
        if free:
            if top and out:
                out.append("")
            ftype = free.get("type")
            fline = f"{'  '*indent}{ANY}:"
            if free.get("properties") or self.free_level(free):
                out.append(fline + self.annot(free, False, "author-chosen key name")
                           + self.closure(free))
                out += self.render(free, indent + 1, free.get("required", []), path, depth + 1)
            elif ftype == "array":
                out.append(fline + " [ ... ]" + self.annot(free, False, "author-chosen key name"))
            else:
                out.append(fline + " <…>" + self.annot(free, False, "author-chosen key name"))
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
        lines.append("```")
        cc = self.class_conditionals(fd)
        if cc:
            lines += ["", "**Per `concept.class` (conditional shape):**", ""]
            for cl in ["entity", "event", "measure", "enumeration", "reference", "grouping"]:
                if cl in cc:
                    lines.append(f"- **{cl}** — " + "; ".join(dict.fromkeys(cc[cl])))
        lines.append("")
        return "\n".join(lines)

    def roots(self):
        return [b["$ref"].split("/")[-1] for b in self.s.get("oneOf", []) if "$ref" in b]

    def version(self):
        """THE VERSION FIELD, AND NOTHING ELSE.

        This used to `re.search(r"v?(\\d+\\.\\d+\\.\\d+)", self.s["description"])` — the first
        version-shaped string in a prose changelog. That changelog still opens "current generation
        v0.1.14-develop", so the page said 0.1.14 while `version` said 0.1.16, and no instrument
        could disagree because the only one that looked re-rendered the same mistake.
        """
        v = self.s.get("version")
        return str(v) if v not in (None, "") else "?"

    def block(self):
        """The generated section that lives between the markers (no top-level H1 — the doc owns that)."""
        head = [f"## Structural shapes — generated (schema {self.version()})", "",
                "_Generated from [`mac.schema.json`](../mac.schema.json) by `tools/gen_schema_shapes.py`._",
                "_Do not hand-edit between the markers; re-run the generator. The closed vocabulary is",
                "authoritative in the schema — this is its readable, per-object-type face._", ""]
        return "\n".join(head) + "\n" + "\n".join(self.file_block(r) for r in self.roots())


def splice(existing, block):
    payload = f"{BEGIN}\n\n{block}\n{END}"
    if existing and BEGIN in existing and END in existing:
        pre = existing[:existing.index(BEGIN)]
        post = existing[existing.index(END) + len(END):]
        return pre + payload + post
    # no markers yet: append a markers section to whatever exists
    sep = "\n\n" if existing.strip() else ""
    return (existing.rstrip() + sep + payload + "\n") if existing else payload + "\n"


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# THE INDEPENDENT ASSERTION — a second walk, asking a different question of the same source
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def admitted_keys(schema: dict) -> dict[str, set[str]]:
    """{root $def name -> every key name a file of that type may write}.

    DELIBERATELY NOT THE RENDERER'S WALK. It follows EVERY `oneOf`/`anyOf` branch (the renderer
    picks the richest one), every array's items, and every free-key or pattern level; it is
    cycle-guarded by `$def` name and has no depth cap. The question it answers — "which key names
    does this schema admit?" — is a fact about the schema, so it cannot agree with the renderer by
    construction. That is the whole point: byte-comparing a page against a fresh render catches a
    page that drifted and CANNOT catch a renderer that drops a key, which is how `rulings` stayed
    missing while `--check` printed OK.
    """
    defs = schema.get("$defs", {})

    def deref(n):
        name = None
        guard = 0
        while isinstance(n, dict) and "$ref" in n and guard < 64:
            name = n["$ref"].split("/")[-1]
            n = defs.get(name, {})
            guard += 1
        return (n if isinstance(n, dict) else {}), name

    out: dict[str, set[str]] = {}

    def walk(node, acc: set[str], seen: tuple[str, ...]):
        node, rn = deref(node)
        if not isinstance(node, dict):
            return
        if rn:
            if rn in seen:
                return
            seen = seen + (rn,)
        for branch in (node.get("oneOf") or []) + (node.get("anyOf") or []) + (node.get("allOf") or []):
            walk(branch, acc, seen)
        for k, v in (node.get("properties") or {}).items():
            acc.add(k)
            walk(v, acc, seen)
        ap = node.get("additionalProperties")
        if isinstance(ap, dict) and ap:
            walk(ap, acc, seen)
        for _pat, v in (node.get("patternProperties") or {}).items():
            if isinstance(v, dict):
                walk(v, acc, seen)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, acc, seen)

    for b in schema.get("oneOf", []):
        if "$ref" not in b:
            continue
        root = b["$ref"].split("/")[-1]
        acc: set[str] = set()
        walk(b, acc, ())
        out[root] = acc
    return out


def sections_of(block_text: str) -> dict[str, str]:
    """{`### Name` -> that section's text}, read out of the page ON DISK."""
    out: dict[str, str] = {}
    cur, buf = None, []
    for ln in block_text.splitlines():
        m = re.match(r"^### (\S+)\s*$", ln)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def generated_block(text: str) -> str | None:
    if BEGIN not in text or END not in text:
        return None
    return text[text.index(BEGIN) + len(BEGIN):text.index(END)]


def check(schema: dict, target: pathlib.Path) -> list[str]:
    """Two different questions, four different rejects."""
    rejects: list[str] = []
    gen = Gen(schema)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""

    # QUESTION ONE — did the page drift from the declarations? (re-render and compare)
    if existing != splice(existing, gen.block()):
        rejects.append(f"[stale-block] {target.name} — the schema moved and the page did not; "
                       f"regenerate with `python3 tools/gen_schema_shapes.py`")

    # QUESTION TWO — does the page ON DISK say what the schema admits? Nothing below re-renders.
    body = generated_block(existing)
    if body is None:
        rejects.append(f"[no-markers] {target.name} — the page carries no "
                       f"BEGIN/END GENERATED:schema-shapes markers; nothing is generated in it")
        return rejects

    want = gen.version()
    m = HEAD_RE.search(body)
    got = m.group("v") if m else None
    if got != want:
        rejects.append(f"[wrong-version] {target.name} — the page says schema {got!r}; "
                       f"mac.schema.json `version` is {want!r}")

    sections = sections_of(body)
    admitted = admitted_keys(schema)
    for root in gen.roots():
        if root not in sections:
            rejects.append(f"[uncovered-root] {root} — the schema's root `oneOf` admits this file "
                           f"type and the page has no `### {root}` section")
    for root, keys in sorted(admitted.items()):
        sec = sections.get(root)
        if sec is None:
            continue                      # already reported as [uncovered-root]
        for k in sorted(keys):
            if not re.search(rf"^\s*(?:- )?{re.escape(k)}:", sec, re.M):
                rejects.append(f"[uncovered-key] {root}.{k} — the schema admits this key and the "
                               f"`### {root}` section never writes it")
    return rejects


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# self-test — one mutant per reject class, plus a clean fixture that must pass
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def self_test(schema_path: pathlib.Path) -> int:
    checks = 0
    failures: list[str] = []

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    schema = load(schema_path)
    gen = Gen(schema)
    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "shape_reference.md"
        page.write_text(splice("# Shape reference\n\nhand-written prose.\n", gen.block()),
                        encoding="utf-8")
        clean = page.read_text(encoding="utf-8")

        expect(check(schema, page) == [], "a freshly written page must be clean")

        def mutate(new_text: str, cls: str, why: str):
            """Seed one mutant, assert it REJECTS — and assert it CHANGED THE PAGE.

            THE SECOND ASSERTION IS NOT CEREMONY. gen_structure_reference.py's `uncovered-key` mutant
            deleted a TABLE ROW; when the emitter stopped emitting tables the mutant deleted
            nothing, every `check` stayed clean, and the self-test still reported 6/6 — green over
            a reject class it was no longer testing.
            """
            expect(new_text != clean, f"the {cls} mutant must actually change the page ({why})")
            page.write_text(new_text, encoding="utf-8")
            rs = check(schema, page)
            expect(any(r.startswith(f"[{cls}]") for r in rs),
                   f"{why} must reject as {cls} (got: {[r.split(']')[0] + ']' for r in rs] or 'clean'})")
            page.write_text(clean, encoding="utf-8")

        # stale-block — a hand edit inside the markers
        mutate(clean.replace("### ConceptFile", "### ConceptFile EDITED", 1),
               "stale-block", "a hand-edited generated block")

        # wrong-version — the exact defect: a page stating a version the schema does not
        mutate(HEAD_RE.sub("## Structural shapes — generated (schema 0.1.14)", clean, count=1),
               "wrong-version", "a page stating a schema version the schema does not")

        # uncovered-root — a whole file type's section gone
        mutate("\n".join(ln for ln in clean.splitlines() if ln.strip() != "### ConnectionFile") + "\n",
               "uncovered-root", "a file type the root oneOf admits with no section")

        # uncovered-key — THE RENDERER DROPPING A KEY. `rulings` is the measured case: the column
        # map is a free-key level, `render()` walked `properties` only, and the page billed as every
        # object type's shape did not mention a key the schema has carried since 2026-09-28.
        # THE MUTANT MATCHES THE KEY POSITION, not a whole line: the emitted line carries a trailing
        # `# …` annotation, so an equality test against `"rulings:"` deleted nothing and the first
        # run of this self-test went green over a reject it was not exercising — the same way
        # gen_structure_reference's table-row mutant did. The `mutate` helper now refuses that silently.
        drop = re.compile(r"^\s*rulings:")
        mutate("\n".join(ln for ln in clean.splitlines() if not drop.match(ln)) + "\n",
               "uncovered-key", "a key the schema admits and the page omits")

        # no-markers — nothing generated in the page at all
        mutate(clean.replace(BEGIN, "").replace(END, ""),
               "no-markers", "a page with the generated markers removed")

        expect(check(schema, page) == [], "restoring every mutant must return to clean")

    if failures:
        for f in failures:
            print(f"  [SELF-TEST] {f}")
        print(f"FAIL: gen_schema_shapes self-test — {len(failures)} of {checks} check(s) failed "
              f"over 5 reject class(es)")
        return 1
    print(f"PASS: gen_schema_shapes self-test — {checks}/{checks} check(s) over 5 reject class(es)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schema", default=str(ROOT / "mac.schema.json"))
    ap.add_argument("-o", default=str(ROOT / "reference_manual" / "shape_reference.md"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the block is stale, mis-versioned or incomplete")
    ap.add_argument("--self-test", action="store_true",
                    help="one mutant per reject class, plus a clean fixture that must pass")
    a = ap.parse_args(argv)

    schema_path = pathlib.Path(a.schema)
    if not schema_path.is_file():
        print(f"COULD NOT RUN: no schema at {schema_path}", file=sys.stderr)
        return 2
    try:
        schema = load(schema_path)
    except json.JSONDecodeError as exc:
        print(f"COULD NOT RUN: {schema_path.name} is not parseable JSON ({exc})", file=sys.stderr)
        return 2
    if not schema.get("oneOf"):
        print(f"COULD NOT RUN: {schema_path.name} declares no root `oneOf` of file types",
              file=sys.stderr)
        return 2

    if a.self_test:
        return self_test(schema_path)

    target = pathlib.Path(a.o)
    gen = Gen(schema)
    keys = admitted_keys(schema)
    total = sum(len(v) for v in keys.values())

    if a.check:
        rejects = check(schema, target)
        if rejects:
            for r in rejects[:40]:
                print(f"  {r}")
            if len(rejects) > 40:
                print(f"  … and {len(rejects) - 40} more")
            print(f"FAIL: gen_schema_shapes — {len(rejects)} reject(s) over {len(keys)} file type(s) "
                  f"and {total} admitted key(s) in {target.name}")
            return 1
        print(f"PASS: gen_schema_shapes — {target.name} current against mac.schema.json "
              f"{gen.version()}: {len(keys)} file type(s), every one of {total} admitted key(s) written")
        return 0

    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(splice(existing, gen.block()), encoding="utf-8")
    print(f"PASS: gen_schema_shapes — {'injected into' if BEGIN in existing else 'wrote'} "
          f"{target.name} from mac.schema.json {gen.version()}: {len(keys)} file type(s), "
          f"{total} admitted key(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
