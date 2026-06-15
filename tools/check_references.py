#!/usr/bin/env python3
"""
check_references.py — generic referential-integrity checker for a YAML ontology built on this framework.

The companion to validate_schema_v3.py: that one checks STRUCTURE (class present, semantics placement,
naming contract, edge legality); this one checks REFERENTIAL INTEGRITY — that every cross-file reference
resolves to a real target. A green structural validator plus a green referential checker means the model
is well-formed AND internally whole. (Neither proves correctness-against-data; that is execution
validation — see FRAMEWORK.md §8.)

This module is GENERIC and domain-neutral: it knows only framework constructs (concepts, the four layers,
edges, rules, grounding, the `ref:`/`#anchor` mechanism). It makes NO assumption about a `public/` root, a
federation layer, a findings register, or any project naming convention. Applications extend it (subclass
`ReferenceChecker` and override the hooks) to add their own reference kinds — see the GAPS extension for a
worked example.

Canonical reference syntax it validates (see CONCEPT_SPEC.md §"Reference syntax"):
  - a reference is a path to a file, optionally followed by a `#anchor`:  <relpath>.yaml#<anchor>
  - addressable anchors: `#concept`, `#<top-level-key>`, and `#<list>.<id-or-name>` for any list whose
    entries carry an `id:` or `name:` (e.g. `#instances.X`, `#individual_kpis.Y`, `#foreign_keys.Z`),
    nested by container (`#a.b.<id>`). Names with spaces are backtick-quoted; backticks are ignored on
    resolution.

What it checks:
  - every embedded `<path>.yaml#anchor` reference: the file exists and (if parsed) the anchor resolves
  - edge endpoints (`endpoints.{from,to}.ref`) -> concept file + anchor
  - grounding (concept -> table): concept grounding tables resolve to a tables/<name>.yaml
  - rule `validated_against` -> table file ; `{{ rules.X.template }}` injection -> a rule X exists
  - rule `over:` / attribute `value_domain:` -> a referable name (concept / subclass) [WARNING: semantic]

What it does NOT check (out of scope; noted, not silently dropped):
  - SQL correctness, live-schema column existence (execution validation)
  - structural schema rules (validate_schema_v3.py owns those)

Usage:
  python tools/check_references.py <ontology-root> [--strict] [--quiet]
  exit 0 = no errors (warnings allowed unless --strict); exit 1 = orphans found.
"""

from __future__ import annotations
import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")


# ----------------------------------------------------------------------------- model

@dataclass
class Finding:
    severity: str          # ERROR | WARNING | INFO
    where: str
    message: str

@dataclass
class Index:
    files: set[str] = field(default_factory=set)                       # relpaths of parsed yaml
    anchors: dict[str, set[str]] = field(default_factory=dict)         # relpath -> {#anchors}
    concept_names: dict[str, set[str]] = field(default_factory=dict)   # source -> {concept names}
    enum_ref_names: dict[str, set[str]] = field(default_factory=dict)  # source -> {enum/reference names}
    referable_names: dict[str, set[str]] = field(default_factory=dict) # source -> {names over:/value_domain may point at}
    table_files: dict[str, set[str]] = field(default_factory=dict)     # source -> {table file stems}
    rule_ids: dict[str, set[str]] = field(default_factory=dict)        # source -> {rule ids}


# the canonical reference regex: a path + optional #anchor (anchor may contain a backtick-quoted segment)
REF_PATH_RE = re.compile(r"([\w./-]+?\.(?:yaml|yml|md))(#(?:[\w.\-]|`[^`]*`)+)?")
RULE_INJECT_RE = re.compile(r"\{\{\s*rules\.([\w]+)\.template\s*\}\}")


# ----------------------------------------------------------------------------- helpers

def rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")

def load_yaml(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return e

def norm_anchor(tok: str) -> str:
    """Remove backticks anywhere (names with spaces are backtick-quoted) and the leading #."""
    return tok.lstrip("#").replace("`", "").strip()

def in_layer(relpath: str, layer: str) -> bool:
    """True if relpath is inside a <layer>/ dir, whether at the root (concepts/x.yaml) or
    under a wrapper (public/FPL/concepts/x.yaml)."""
    return relpath.startswith(f"{layer}/") or f"/{layer}/" in relpath

def walk_strings(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node

LAYER_DIRS = ("concepts", "tables", "rules.yaml", "rules.yml", "edges.yaml", "edges.yml")

def source_of(relpath: str) -> str:
    """The data-source key for a file: the path prefix that sits ABOVE the layer dir/file
    (concepts/ tables/ rules.yaml edges.yaml). So:
      SHOP/concepts/order/order.yaml -> 'SHOP'      (wrapped, multi-source style)
      concepts/order/order.yaml      -> ''          (single-source: the root IS the source)
      tables/orders.yaml             -> ''          (same source -> concepts and tables now MATCH)
    Applications with an extra wrapper (e.g. public/FPL/...) override `ReferenceChecker.source_of`."""
    parts = relpath.split("/")
    for i, seg in enumerate(parts):
        if seg in LAYER_DIRS:
            return "/".join(parts[:i])      # '' when the layer dir is first
    return parts[0] if parts else ""


def collect_anchors(doc) -> set[str]:
    """Every #anchor a file exposes, mirroring how refs address them (see module docstring)."""
    anchors: set[str] = set()
    if not isinstance(doc, dict):
        return anchors

    def rec(node, prefix: str):
        if isinstance(node, dict):
            for k, v in node.items():
                cur = f"{prefix}.{k}" if prefix else f"#{k}"
                anchors.add(cur)
                rec(v, cur)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    key = item.get("id") or item.get("name") or item.get("rule") or item.get("edge_id")
                    if key is not None:
                        anchors.add(f"{prefix}.{key}")
                        anchors.add(f"{prefix}.{norm_anchor(str(key))}")
                    rec(item, prefix)

    rec(doc, "")
    if "concept" in doc:
        anchors.add("#concept")
    return anchors


# ----------------------------------------------------------------------------- the checker

class ReferenceChecker:
    """Generic referential checker. Subclass and override the hooks to add application-specific checks."""

    def __init__(self, root: Path, scan_subdir: str | None = None):
        """root: the base that relative references are resolved against (and relpaths are reported from).
        scan_subdir: if set, only files under root/<scan_subdir> are scanned — but relpaths stay relative
        to `root`, so references written as `<scan_subdir>/...` still resolve. Used by wrapped projects
        whose refs are repo-relative (e.g. root=repo, scan_subdir='public')."""
        self.root = root.resolve()
        self.scan_root = (self.root / scan_subdir).resolve() if scan_subdir else self.root
        self.idx = Index()
        self.findings: list[Finding] = []

    # -- hooks an application overrides -------------------------------------------------

    def source_of(self, relpath: str) -> str:
        return source_of(relpath)

    def index_file(self, relpath: str, doc) -> None:
        """Called once per parsed yaml during indexing. Override to index extra referable objects."""

    def resolve_file(self, relpath: str, doc) -> None:
        """Called once per parsed yaml during resolution. Override to check extra reference kinds."""

    def table_status(self, src: str, tname: str) -> str:
        """'ok' | 'missing' | 'skip'. Override to add e.g. catalog-prefix tolerance."""
        if "<" in tname or ">" in tname:
            return "skip"
        return "ok" if tname in self.idx.table_files.get(src, set()) else "missing"

    # -- core ---------------------------------------------------------------------------

    def add(self, severity: str, where: str, message: str) -> None:
        self.findings.append(Finding(severity, where, message))

    def run(self) -> int:
        self._build_index()
        self._resolve()
        return self._report()

    def _yaml_files(self):
        return sorted(p for p in self.scan_root.rglob("*.yaml")) + sorted(p for p in self.scan_root.rglob("*.yml"))

    def _build_index(self):
        for p in self._yaml_files():
            r = rel(p, self.root)
            self.idx.files.add(r)
            doc = load_yaml(p)
            if isinstance(doc, Exception):
                self.add("ERROR", r, f"YAML parse error: {doc}")
                continue
            if not isinstance(doc, dict):
                self.idx.anchors[r] = set()
                continue
            self.idx.anchors[r] = collect_anchors(doc)
            src = self.source_of(r)

            if in_layer(r, "concepts") and isinstance(doc.get("concept"), dict):
                c = doc["concept"]
                if c.get("name"):
                    self.idx.concept_names.setdefault(src, set()).add(c["name"])
                    self.idx.referable_names.setdefault(src, set()).add(c["name"])
                    if c.get("class") in ("enumeration", "reference"):
                        self.idx.enum_ref_names.setdefault(src, set()).add(c["name"])
                for rc in (doc.get("related_concepts") or []):
                    if isinstance(rc, dict) and rc.get("name"):
                        self.idx.concept_names.setdefault(src, set()).add(rc["name"])
                        self.idx.referable_names.setdefault(src, set()).add(rc["name"])
                subs = c.get("subclasses")
                if isinstance(subs, dict):
                    for s in subs:
                        self.idx.referable_names.setdefault(src, set()).add(s)
                elif isinstance(subs, list):
                    for s in subs:
                        if isinstance(s, dict) and s.get("name"):
                            self.idx.referable_names.setdefault(src, set()).add(s["name"])

            if in_layer(r, "tables"):
                self.idx.table_files.setdefault(src, set()).add(p.stem)

            if p.name in ("rules.yaml", "rules.yml"):
                for rule in (doc.get("rules") or []):
                    if isinstance(rule, dict) and rule.get("rule"):
                        self.idx.rule_ids.setdefault(src, set()).add(rule["rule"])

            self.index_file(r, doc)   # application hook

    def anchor_resolves(self, path: str, anchor: str) -> bool:
        cands = {anchor, "#" + norm_anchor(anchor)}
        return bool(cands & self.idx.anchors.get(path, set()))

    @staticmethod
    def is_placeholder(value: str) -> bool:
        v = value.upper()
        return ("TODO" in v or "NEEDS_MAP" in v or "TBC" in v or "(ENRICH)" in v
                or ("<" in value and ">" in value))

    def _root_segments(self) -> set[str]:
        if not hasattr(self, "_root_seg_cache"):
            self._root_seg_cache = {p.name for p in self.root.iterdir()} if self.root.is_dir() else set()
        return self._root_seg_cache

    def _is_structured_ref(self, where: str, path: str) -> bool:
        """A structured reference (vs a bare filename mentioned in prose). True iff the path is
        root-anchored — it starts with a real top-level entry of the root (e.g. 'public/...',
        'concepts/...') — OR it sits under a ref-family key. Prose like 'see body_types.yaml' is NOT
        root-anchored, so it is ignored (the canonical syntax, CONCEPT_SPEC §5a, is root-relative)."""
        first = path.split("/", 1)[0]
        if first in self._root_segments():
            return True
        ref_keys = (".ref", ".realized_by", "cross_references", "validated_against")
        return any(k in where for k in ref_keys)

    def check_ref_string(self, where: str, value: str) -> None:
        if self.is_placeholder(value):
            self.add("INFO", where, f"placeholder/TODO reference: {value.strip()[:80]}")
            return
        for m in REF_PATH_RE.finditer(value):
            path, anchor = m.group(1), m.group(2)
            if not self._is_structured_ref(where, path):
                continue  # a bare filename in prose, not a structured root-anchored reference
            indexed = path in self.idx.files
            on_disk = (self.root / path).is_file()
            if not indexed and not on_disk:
                self.add("ERROR", where, f"reference to missing file: {path}")
                continue
            if anchor and indexed and not self.anchor_resolves(path, anchor):
                self.add("ERROR", where, f"unresolved anchor {anchor} in {path}")
            elif anchor and not indexed:
                self.add("INFO", where, f"anchor {anchor} in non-parsed file {path} (existence ok; anchor unverified)")

    def _resolve(self):
        for p in self._yaml_files():
            r = rel(p, self.root)
            doc = load_yaml(p)
            if not isinstance(doc, dict):
                continue
            src = self.source_of(r)

            # (a) every embedded reference path + (b) rule injection
            for jpath, s in walk_strings(doc):
                if REF_PATH_RE.search(s) and ("/" in s):
                    self.check_ref_string(f"{r}{jpath}", s)
                for m in RULE_INJECT_RE.finditer(s):
                    rule_name = m.group(1)
                    if rule_name not in self.idx.rule_ids.get(src, set()):
                        self.add("ERROR", f"{r}{jpath}",
                                 f"rule-injection references unknown rule '{rule_name}' in {src} rules")

            # (c) concept grounding -> table, (d) value_domain
            if in_layer(r, "concepts"):
                cblock = doc.get("concept") if isinstance(doc.get("concept"), dict) else {}
                grounding = cblock.get("grounding") or doc.get("grounding")
                if isinstance(grounding, dict):
                    tbls = []
                    # scalar form: grounding.table: orders   (FRAMEWORK §5 anatomy)
                    if isinstance(grounding.get("table"), str):
                        tbls.append(grounding["table"])
                    # list form: grounding.tables: / primary_tables:  (multi-table grounding)
                    for key in ("tables", "primary_tables"):
                        for t in (grounding.get(key) or []):
                            if isinstance(t, dict) and t.get("name"):
                                tbls.append(t["name"])
                            elif isinstance(t, str):
                                tbls.append(t)
                    # v0.5 agnostic form: grounding.sources: [{relation, key, columns}]
                    for s in (grounding.get("sources") or []):
                        if isinstance(s, dict) and isinstance(s.get("relation"), str):
                            tbls.append(s["relation"])
                    for tname in tbls:
                        st = self.table_status(src, tname)
                        if st == "missing":
                            self.add("ERROR", f"{r} grounding",
                                     f"grounding references table '{tname}' with no tables/{tname}.yaml in {src}")
                        elif st == "skip":
                            self.add("INFO", f"{r} grounding", f"grounding table name is a placeholder: '{tname}'")
                for attr in (cblock.get("attributes") or []):
                    if isinstance(attr, dict) and attr.get("value_domain"):
                        vd = attr["value_domain"]
                        if vd not in self.idx.referable_names.get(src, set()):
                            self.add("WARNING", f"{r} attributes",
                                     f"value_domain '{vd}' not found as a concept/subclass in {src}")

            # (e) rule validated_against -> table ; over: -> referable name
            if p.name in ("rules.yaml", "rules.yml"):
                for rule in (doc.get("rules") or []):
                    if not isinstance(rule, dict):
                        continue
                    for tname in (rule.get("validated_against") or []):
                        st = self.table_status(src, tname)
                        if st == "missing":
                            self.add("ERROR", f"{r} rule:{rule.get('rule')}",
                                     f"validated_against references table '{tname}' with no tables/{tname}.yaml in {src}")
                    for cname in (rule.get("over") or []):
                        if not any(cname in names for names in self.idx.referable_names.values()):
                            self.add("WARNING", f"{r} rule:{rule.get('rule')}",
                                     f"over: names '{cname}' not found as any concept/subclass")

            self.resolve_file(r, doc)   # application hook

    def _report(self, quiet: bool = False, strict: bool = False) -> int:
        errs = [f for f in self.findings if f.severity == "ERROR"]
        warns = [f for f in self.findings if f.severity == "WARNING"]
        infos = [f for f in self.findings if f.severity == "INFO"]

        def show(g):
            for f in g:
                print(f"  [{f.severity}] {f.where}\n      {f.message}")

        if errs:
            print(f"\nERRORS ({len(errs)}) — orphaned / unresolved references:"); show(errs)
        if warns and not quiet:
            print(f"\nWARNINGS ({len(warns)}) — semantic references not resolved (name-level):"); show(warns)
        if infos and not quiet:
            print(f"\nINFO ({len(infos)}) — placeholders / unverified:"); show(infos)

        nc = sum(len(v) for v in self.idx.concept_names.values())
        nt = sum(len(v) for v in self.idx.table_files.values())
        nr = sum(len(v) for v in self.idx.rule_ids.values())
        print(f"\nINDEX: {len(self.idx.files)} files · {nc} concepts · {nt} tables · {nr} rules")
        print(f"RESULT: {len(errs)} error(s), {len(warns)} warning(s), {len(infos)} info")
        print("NOTE: referential gate only — does NOT check SQL correctness or live-schema columns.")
        if errs:
            return 1
        return 1 if (warns and strict) else 0


# ----------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generic referential-integrity checker for a framework ontology")
    ap.add_argument("root", help="base dir references resolve against (relpaths reported from here)")
    ap.add_argument("--scan-subdir", default=None,
                    help="only scan files under root/<subdir>, but keep relpaths relative to root "
                         "(for wrapped projects whose refs are repo-relative, e.g. --scan-subdir public)")
    ap.add_argument("--strict", action="store_true", help="treat WARNINGs as failures")
    ap.add_argument("--quiet", action="store_true", help="errors + summary only")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    chk = ReferenceChecker(root, scan_subdir=args.scan_subdir)
    chk._build_index()
    chk._resolve()
    return chk._report(quiet=args.quiet, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
