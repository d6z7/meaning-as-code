#!/usr/bin/env python3
"""mac_model.py — the shared, provenance-carrying model of a MAC bundle.

WHY THIS EXISTS
---------------
Every gate in tools/ used to answer one question: *"what does this file say"*. Each re-globbed the
tree, re-parsed it, and held one file at a time. Measured on 2026-08-17 over the four-bundle corpus:
7 independent implementations of "find the concepts", 6 of "find the descriptors", 3 of "find the
lookups", and 3.591 file reads for one 8-gate sweep over a corpus whose model artifacts number 449.

That shape is not merely wasteful — it is *structurally blind* to a whole class of defect. The
defects that got through on 2026-08-16/17 are all of the form **"two files say the same thing and
disagree"**:

  * `ontology/concepts/ideal_stock.yaml` says a Target measure is `additive` on its geography and
    model axes; `mac_vocabulary.yaml#MeasureType.Target` says `non_aggregable` on the categorical
    axis, and the bundle's own measure register agrees with the law. Measured across 9 measures:
    8 agree, 1 contradicts. No gate could see it — the two statements live in different files.
  * two deltas added a pointer and left the superseded field behind.
  * a rule-violation check over-fired 3x on 1 real violation because nothing modelled rule
    dependencies. (Measured here: the naive additivity derivation over-fires **7x** for the same
    reason — see `Axis.role`.)

Answering "two files disagree" needs to know **where each statement was made**. So this module's
atom is not a value, it is a STATEMENT: a value plus its site (`Stated`). A field holds a list of
statements. One statement = a fact with a home. Two = a redundancy. Two that disagree = a defect.

WHAT THIS IS
------------
One read-only front end: `load(root)` parses a bundle exactly once and returns an immutable `Bundle`
carrying the resolved object graph — documents, objects, relations, columns, concepts, groundings,
value sets, measures, axes, edges, registers — every interpreted value carrying its `Site`.

WHAT THIS IS NOT
----------------
Not a new MAC syntax, not a config format, not a plugin system, not a rule engine. It does not
validate: it makes the population and the links available so a gate can. It reads; it never writes.
It depends on stdlib + PyYAML + this repo's own `mac_project.resolve` and nothing else.

CONTRACT
--------
  * NEVER raises on bundle content. A malformed file lands as `Doc.parse_error` and the load
    continues, because a gate must still report its normal findings on a partly-broken bundle.
    A dangling reference lands as an `Unresolved` value stored at the referring field. `ValueError`
    is raised only on PROGRAMMER error: an unknown scope name, an unknown fact family.
  * Deterministic: every collection is sorted at construction; dicts are insertion-ordered from
    sorted input; no set is ever iterated into output.
  * Cacheable: `load()` is memoized per (absolute root, scope), so eight gates each calling it in
    one process parse the bundle once.

Usage:
    from mac_model import load
    B = load("/path/to/bundle")
    for c in B.concepts():
        ...
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_project import resolve  # noqa: E402

# --------------------------------------------------------------------------------------------------
# framework constants — these name FRAMEWORK constructs (schema keys, canonical dirs, closed domains),
# never bundle instances. No corpus literal (a column, a brand, a measure, a question id) appears in
# this module: a bundle supplies its own vocabulary.
# --------------------------------------------------------------------------------------------------

FRAMEWORK = "«framework»"                       # the pseudo-plane a framework file's Site is stamped with
VOCABULARY = "mac_vocabulary.yaml"              # the framework law, at the repo root above tools/
SCOPES = ("planes", "tree")

LOOKUPS_DIR = ("data", "lookups")               # the ONE conventional register path (not a manifest key
                                                # today — reported, see the module's companion design §10)
CONCEPTS_DIR = "concepts"                       # relative to the resolved ontology plane
OBJECT_KINDS = ("source", "transform", "dataset", "concept", "lookup")
LOOKUP_SUFFIX = ".lookup"                       # register stems carry it; ONE identity, stripped once here

# a measure register is a lookup CSV that MATERIALIZES the additivity law: these three columns, by name.
MEASURE_REGISTER_COLUMNS = ("measure_type", "additivity_time", "additivity_categorical")

# check_references' single-source key: the path prefix ABOVE the layer dir/file.
LAYER_DIRS = ("concepts", "tables", "datasets", "rules.yaml", "rules.yml", "edges.yaml", "edges.yml")

# projections/ = generated exports; *.local.* = gitignored env-specific manifests — never model source.
_PLANE_EXCLUDE_PART = "projections"
_PLANE_EXCLUDE_NAME = ".local."
# scope="tree" preserves validate_schema's wider predicate verbatim (it reaches published artifacts/
# copies, and that is load-bearing for its verdict — see the design's risk register §8.6).
_TREE_SKIP = {".git", "node_modules", ".venv", "__pycache__", "projections"}


# ==================================================================================================
# 1. the primitives — a value, and where it was stated
# ==================================================================================================

@dataclass(frozen=True)
class Site:
    """WHERE a value was stated. The whole model rests on this being present on every fact."""
    file: str                    # bundle-relative POSIX path, or "«framework»/mac_vocabulary.yaml"
    path: str                    # dotted/indexed YAML path: "concept.semantics.additivity.geography"
    line: int | None = None      # 1-based; None until asked (see Doc.line_of — lazy, measured cost)

    def __str__(self) -> str:
        return f"{self.file}#{self.path}" + (f":{self.line}" if self.line else "")


@dataclass(frozen=True)
class Stated:
    """A value plus its site. The atom of the model.

    `value` is stored AS WRITTEN and is never normalized here. Normalization happens only inside a
    fact family's fold, and the unfolded value stays available for the error message. That is
    deliberate: the two provenance readers in the estate disagreed (one case-folded, one did not)
    precisely because normalization had been baked into the read.
    """
    value: object
    site: Site
    kind: str                    # "authored" | "projected" | "derived" (assigned by the loader)

    def __str__(self) -> str:
        return f"{self.value!r} <- {self.site}"


@dataclass(frozen=True)
class Unresolved:
    """A reference that resolved to nothing. AN UNRESOLVABLE REFERENCE IS A VALUE, NEVER AN EXCEPTION.

    Falsy, so `if not rel:` is the idiom. It carries the dirs actually searched so a gate can
    reproduce its own wording (e.g. a trailing "(looked under data/sources/)") byte-identically.
    """
    ref: str
    kind: str                    # what was expected: "relation" | "object" | "register" | "concept"
    searched: tuple[str, ...]    # bundle-relative dirs/files actually looked in, in order
    site: Site | None = None

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return f"unresolved {self.kind} {self.ref!r} (searched: {', '.join(self.searched) or '-'})"


# ==================================================================================================
# 2. documents
# ==================================================================================================

@dataclass(frozen=True, eq=False)
class Doc:
    """One parsed YAML file. `kind` comes from LOCATION, never from content."""
    relpath: str                 # bundle-relative POSIX (or "«framework»/…" for the law)
    abspath: Path
    plane: str                   # "data" | "ontology" | "" (flat bundles and root-level files)
    source: str                  # check_references' single-source key
    kind: str
    data: dict                   # parsed mapping; {} on a parse error or a non-mapping document
    parse_error: str | None      # the exception text, VERBATIM — gates print it
    anchors: frozenset           # the "#…" anchors this doc exposes
    # WAS THE DOCUMENT A MAPPING AT ALL? `data` cannot answer that: a file holding `[]`, a scalar, or
    # nothing lands as {} exactly like a file holding `{}`. The difference is load-bearing for the
    # referential gate, which registers a descriptor stem / a rule id only from a MAPPING document —
    # so a list-shaped descriptor must NOT be indexed as a relation. The loader is the only place that
    # still knows, so it records the answer here instead of throwing it away.
    is_mapping: bool = True
    _lines: dict = field(default_factory=dict, repr=False, compare=False)

    def line_of(self, path: str) -> int | None:
        """The 1-based line a dotted/indexed YAML path was written on, or None.

        LAZY, and that is a measured choice: over the corpus's 407 plane YAML files, `yaml.compose()`
        + indexing costs about as much again as `safe_load` (1,156 s vs 1,195 s in the design probe),
        so eager line indexing would roughly double the model's parse cost to serve a query only the
        reporting path makes.
        """
        if not self._lines:
            self._lines.update(_index_lines(self.abspath))
            self._lines.setdefault(_LINE_SENTINEL, None)   # so an empty index is not rebuilt per call
        return self._lines.get(path)


_LINE_SENTINEL = "\x00indexed"


def _index_lines(path: Path) -> dict:
    """{dotted_path: 1-based line} for one YAML file, from the composed node tree.

    Mapping entries take the KEY node's line (that is the line a human greps for); sequence items
    take the item node's own line. Verified exact against `grep -n` during design.
    """
    try:
        text = path.read_text(encoding="utf-8")
        root = (yaml.compose(text, Loader=_FAST_LOADER) if _FAST_LOADER is not None
                else yaml.compose(text))
    except Exception:                       # noqa: BLE001 — an unparseable file simply has no lines
        return {}
    out: dict = {}
    seen: set[int] = set()                  # YAML aliases can make the node graph cyclic

    def walk(node, prefix: str) -> None:
        if node is None or id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                key = str(getattr(k, "value", ""))
                p = f"{prefix}.{key}" if prefix else key
                out.setdefault(p, k.start_mark.line + 1)
                walk(v, p)
        elif isinstance(node, yaml.SequenceNode):
            for i, item in enumerate(node.value):
                p = f"{prefix}[{i}]"
                out.setdefault(p, item.start_mark.line + 1)
                walk(item, p)

    walk(root, "")
    return out


def collect_anchors(doc) -> frozenset:
    """Every "#anchor" a file exposes, mirroring how references address them."""
    anchors: set[str] = set()
    if not isinstance(doc, dict):
        return frozenset()

    def rec(node, prefix: str) -> None:
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
                        anchors.add(f"{prefix}.{str(key).lstrip('#').replace('`', '').strip()}")
                    rec(item, prefix)

    rec(doc, "")
    if "concept" in doc:
        anchors.add("#concept")
    return frozenset(anchors)


def source_of(relpath: str, planes: tuple[str, ...] = ()) -> str:
    """The data-source key for a file: the path prefix ABOVE the layer dir/file, with a declared
    plane dir stripped (a two-plane project is single-source, so its ontology and data planes match)."""
    parts = relpath.split("/")
    src = ""
    for i, seg in enumerate(parts):
        if seg in LAYER_DIRS:
            src = "/".join(parts[:i])
            break
    else:
        src = parts[0] if parts else ""
    segs = src.split("/") if src else []
    if segs and segs[0] in planes:
        return "/".join(segs[1:])
    return src


# ==================================================================================================
# 3. objects — the protocol-bearing artifacts both change-protocol gates index
# ==================================================================================================

@dataclass(frozen=True, eq=False)
class Object:
    """A '<kind>:<stem>' artifact: the identity the ledger and the vanilla-delta registers name."""
    ref: str                     # "<kind>:<stem>", e.g. "concept:<stem>" / "lookup:<stem>"
    kind: str
    stem: str                    # LOOKUP_SUFFIX stripped — one identity everywhere
    raw_stem: str                # the on-disk stem, unstripped
    path: Path
    doc: Doc | None              # None for lookups (a CSV register carries no YAML metadata)
    register: "Register | None"
    provenance: Stated | None    # metadata.provenance, value AS WRITTEN; None when absent


def provenance_of(obj) -> str | None:
    """THE provenance reader. One field, one reader — there is no second one.

    Measured 2026-08-17: the estate held two readers of `metadata.provenance`, one case-folding and
    one raw, and on a probe bundle stamping `Authored` they returned OPPOSITE verdicts on the same
    byte. This is the case-folding one; adopting it is byte-neutral on the whole corpus (fpl2 carries
    harvested x43 / authored x7 / tuned x10, all already lower-case; the other three bundles carry
    only free-text sentences and None, outside the vocabulary under either reader).
    """
    stated = obj.provenance if isinstance(obj, Object) else obj
    if isinstance(stated, Stated):
        value = stated.value
    elif isinstance(stated, Doc):
        value = _as_dict(stated.data.get("metadata")).get("provenance")
    else:
        value = stated
    return str(value).strip().lower() if isinstance(value, str) and value.strip() else None


# ==================================================================================================
# 4. the data plane
# ==================================================================================================

@dataclass(frozen=True)
class Column:
    relation: str
    name: str
    type: str | None
    role: str | None             # `role` or `x-field_role`, whichever the descriptor states
    nullable: bool | None
    description: str | None
    site: Site


@dataclass(frozen=True)
class ForeignKey:
    relation: str
    name: str | None
    from_column: str
    to_table: str
    to_column: str
    site: Site


@dataclass(frozen=True, eq=False)
class Relation:
    name: str                    # the DESCRIPTOR STEM — the identity the ontology grounds against
    schema: str | None
    physical: str | None         # table.name, when it differs from the stem
    role: str                    # "dataset" | "raw_source"
    doc: Doc
    columns: dict                # {column name: Column}, in declaration order
    foreign_keys: tuple


# ==================================================================================================
# 5. the ontology plane
# ==================================================================================================

@dataclass(frozen=True)
class Grounding:
    concept: str
    relation_ref: str            # AS WRITTEN, schema qualifier and all
    relation: object             # Relation | Unresolved
    key: tuple
    columns: tuple               # the restated subset — a SELECTION, not a duplicate fact
    site: Site


@dataclass(frozen=True)
class Member:
    concept: str
    code: str
    label: str | None
    confidence: Stated | None
    site: Site


@dataclass(frozen=True)
class ValueSet:
    concept: str
    closure: Stated | None
    register_ref: Stated | None  # values.realized_by.params.register, AS WRITTEN
    register: object             # Register | Unresolved | None
    members: tuple


@dataclass(frozen=True)
class Axis:
    measure: str
    name: str
    kind: Stated | None          # concept.semantics.axis_kinds.<name>, as written
    additivity: Stated | None    # RESOLVED: the concept's own value when it wrote one, otherwise the
                                 # law's, cited to «framework»/mac_vocabulary.yaml. v0.1.16 stopped
                                 # requiring concepts to write it — a consumer must not have to care
                                 # which of the two it got, only that the value carries its Site.
    role: str                    # "aggregation_axis" | "measure_selector" — DERIVED, see _axis_role


@dataclass(frozen=True)
class Measure:
    concept: str
    measure_type: Stated | None
    unit: Stated | None
    axes: dict                   # {axis name: Axis}, declaration order


@dataclass(frozen=True, eq=False)
class Concept:
    name: str                    # concept.name — the identity ("" when the file declares none)
    stem: str                    # file stem, an alias
    cls: str | None
    doc: Doc
    groundings: tuple
    field_roles: dict            # grounding.field_roles — the column whitelist, str keys only
    values: ValueSet | None
    measure: Measure | None      # set iff cls == "measure"


@dataclass(frozen=True, eq=False)
class Edge:
    edge_id: str
    level: str | None
    join_rule: Stated | None
    realized_by: Stated | None
    endpoints: tuple             # concept names AS WRITTEN
    concepts: tuple              # resolved, positionally aligned with `endpoints`
    doc: Doc
    site: Site


# ==================================================================================================
# 6. registers
# ==================================================================================================

@dataclass(frozen=True)
class RegisterRow:
    register: str
    lineno: int                  # 1-based file line; header is 1, first row is 2
    cells: dict
    _relpath: str = ""

    def site(self, column: str) -> Site:
        return Site(self._relpath, f"rows[{self.lineno}].{column}", self.lineno)


@dataclass(frozen=True, eq=False)
class Register:
    stem: str                    # LOOKUP_SUFFIX stripped
    raw_stem: str
    path: Path
    relpath: str
    columns: tuple
    rows: tuple
    is_measure_register: bool
    discriminators: frozenset    # the columns that say WHICH measure a row is — see _axis_role
    read_error: str | None       # verbatim; a gate that warns about an unreadable register prints it


# ==================================================================================================
# 7. the framework law
# ==================================================================================================

@dataclass(frozen=True, eq=False)
class Law:
    """mac_vocabulary.yaml — the framework canon, parsed once per process, provenance-carrying."""
    doc: Doc
    measure_types: dict          # MeasureType.members
    aggregation_effects: frozenset
    axis_kinds: frozenset
    namespaces: frozenset

    def additivity(self, measure_type, axis_kind) -> Stated | None:
        """The law's aggregation_effect for one (MeasureType member, axis_kind), as a Stated."""
        mt = str(measure_type or "").split(".")[-1].strip()
        ak = str(axis_kind or "").split(".")[-1].strip()
        member = self.measure_types.get(mt)
        if not isinstance(member, dict):
            return None
        cell = _as_dict(member.get("additivity")).get(ak)
        if cell is None:
            return None
        path = f"MeasureType.members.{mt}.additivity.{ak}"
        return Stated(cell, Site(self.doc.relpath, path, self.doc.line_of(path)), "authored")


# ==================================================================================================
# 8. facts — the query only a shared model can answer
# ==================================================================================================

@dataclass(frozen=True)
class Fact:
    """One fact, with every statement of it found in the bundle + the framework.

    `normalized` is positionally aligned with `statements`: each entry is the statement folded into
    the family's closed comparison domain. A statement that cannot fold TOTALLY is never admitted, so
    `normalized` never carries None.
    """
    family: str
    key: tuple
    statements: tuple
    normalized: tuple

    def agrees(self) -> bool:
        return len(set(self.normalized)) <= 1

    def home(self) -> Stated | None:
        """The statement that should hold the fact ONCE: the one the others are derivable FROM.

        It is `statements[0]`, and each family orders its statements home-first. (The design document
        says both "authored sites first" and "home() = the law"; for the one family shipped here BOTH
        statements are authored — the ontology plane and the framework canon are each authored — so
        kind cannot order them. Derivability can, and it is the property home() is named for.)
        """
        return self.statements[0] if self.statements else None


# ==================================================================================================
# 9. the bundle
# ==================================================================================================

@dataclass(frozen=True, eq=False)
class Bundle:
    root: Path
    layout: SimpleNamespace      # mac_project.resolve(root), VERBATIM — no new layout invention
    scope: str
    planes: tuple                # the declared plane DIR NAMES, in manifest order; () when flat.
                                 # Held because the single-source key strips them (source_of) and a
                                 # gate that asks the resolver again re-reads the manifest to learn
                                 # what the load already knows.
    law: Law
    _docs: tuple
    _doc_by_relpath: dict
    _objects: dict
    _object_dirs: dict           # kind -> bundle-relative dir, for Unresolved.searched
    _relations: dict             # bare name (stem AND table.name) -> Relation
    _relation_dirs: tuple
    _concepts: tuple             # ONE PER CONCEPT FILE, in sorted-rglob order
    _concept_index: dict         # name and stem -> Concept
    _registers: dict             # stripped stem -> Register
    _edges: tuple

    # -- documents ---------------------------------------------------------------------------------

    def docs(self, kind: str | None = None) -> tuple:
        return self._docs if kind is None else tuple(d for d in self._docs if d.kind == kind)

    def doc(self, relpath: str):
        key = str(relpath).replace("\\", "/")
        if key in self._doc_by_relpath:
            return self._doc_by_relpath[key]
        if key == self.law.doc.relpath:
            return self.law.doc
        return Unresolved(str(relpath), "doc", (str(self.root),))

    # -- objects -----------------------------------------------------------------------------------

    def objects(self, kinds=None) -> dict:
        """The '<kind>:<stem>' object index.

        `kinds` is the CALLER's, for a measured reason: the two change-protocol gates print different
        object counts (76 vs 60 on one corpus bundle) and the difference is exactly the lookup
        registers. Scope belongs to the caller, or one of the two headers changes.
        """
        if kinds is None:
            return dict(self._objects)
        want = tuple(kinds)
        for k in want:
            if k not in OBJECT_KINDS:
                raise ValueError(f"unknown object kind {k!r}; expected a subset of {list(OBJECT_KINDS)}")
        return {r: o for r, o in self._objects.items() if o.kind in want}

    def object(self, ref: str, site: Site | None = None):
        text = str(ref)
        if ":" not in text:
            return Unresolved(text, "object", (), site)
        kind, stem = (p.strip() for p in text.split(":", 1))
        if kind not in OBJECT_KINDS:
            return Unresolved(text, "object", (), site)
        hit = self._objects.get(f"{kind}:{stem}")
        return hit if hit is not None else Unresolved(
            text, "object", (self._object_dirs.get(kind, ""),), site)

    # -- planes ------------------------------------------------------------------------------------

    def relation(self, name, site: Site | None = None):
        bare = str(name).split(".")[-1]
        hit = self._relations.get(bare)
        return hit if hit is not None else Unresolved(str(name), "relation", self._relation_dirs, site)

    @property
    def concepts_dir(self) -> Path:
        """WHERE this bundle's concept files live, layout-resolved.

        Exists because a gate that wants to say "no concepts here" must name the directory it looked
        in, and MEASURED 2026-08-17 the estate answered that question two ways: check_shapes asked the
        layout (`resolve(root).ontology / "concepts"`), check_enumeration_closure hardcoded
        `root/ontology/concepts`. On a valid two-plane bundle whose planes are named `model`/`warehouse`
        the second one printed "no ontology/concepts directory — nothing to check" and exited 0 over a
        bundle holding exactly the defect it exists to catch. One question, one answer, here.
        """
        return Path(self.layout.ontology) / CONCEPTS_DIR

    def ontology_doc(self, name: str):
        """The parsed Doc for a NAMED file of the ontology plane (edges.yaml, rules.yaml, shapes.yaml).

        These files are addressed by name, not discovered: the ontology plane holds at most one of
        each. Returns `Unresolved` when the plane does not carry it, so `if not doc:` is the idiom and
        an absent edges file is a value rather than a branch on `Path.exists()` in every caller.
        """
        p = Path(self.layout.ontology) / str(name)
        hit = self._doc_by_relpath.get(_rel(p, self.root))
        if hit is not None:
            return hit
        return Unresolved(str(name), "doc", (_rel_dir(self.layout.ontology, self.root) or ".",))

    def concepts(self) -> tuple:
        return self._concepts

    def concept(self, name, site: Site | None = None):
        hit = self._concept_index.get(str(name))
        if hit is not None:
            return hit
        onto = _rel_dir(self.layout.ontology, self.root)
        return Unresolved(str(name), "concept",
                          (f"{onto}/{CONCEPTS_DIR}" if onto else CONCEPTS_DIR,), site)

    def registers(self) -> tuple:
        return tuple(self._registers.values())

    def register(self, ref, site: Site | None = None):
        """Resolve a register pointer: exact on-disk stem, then stripped stem, then PREFIX.

        Prefix matching is not a guess the model invents — it is the estate's existing delegation
        semantics (the closure gate globs `<stem>*.csv`), held here once instead of three times.
        """
        text = str(ref or "").strip()
        cand = text[:-4] if text.lower().endswith(".csv") else text
        for reg in self._registers.values():
            if cand in (reg.raw_stem, reg.stem):
                return reg
        for reg in self._registers.values():
            if reg.raw_stem.startswith(cand) and cand:
                return reg
        return Unresolved(text, "register", ("/".join(LOOKUPS_DIR),), site)

    def edges(self) -> tuple:
        return self._edges

    # -- facts -------------------------------------------------------------------------------------

    def facts(self, family: str) -> tuple:
        fn = _FACT_FAMILIES.get(family)
        if fn is None:                        # PROGRAMMER error, not bundle content
            raise ValueError(f"unknown fact family {family!r}; known: {sorted(_FACT_FAMILIES)}")
        return fn(self)


# ==================================================================================================
# 10. small helpers
# ==================================================================================================

def _as_dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return str(path)


def _rel_dir(path, root: Path) -> str:
    if not path:
        return ""
    r = _rel(Path(path), root)
    return "" if r == "." else r


def de(value, decimals: int = 0) -> str:
    """Render a number the way this estate shows numbers to humans: de-DE (1.234.567 / 33,08).

    Held ONCE here rather than restated in every reporter — that restatement is precisely the drift
    this module exists to kill.
    """
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{n:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# ==================================================================================================
# 11. the loader
# ==================================================================================================

_LOAD_CACHE: dict = {}
_LAW_CACHE: dict = {}


def load(root, scope: str = "planes") -> Bundle:
    """Parse a bundle once and return its immutable model. Memoized per (absolute root, scope)."""
    if scope not in SCOPES:                   # PROGRAMMER error, not bundle content
        raise ValueError(f"unknown scope {scope!r}; expected one of {list(SCOPES)}")
    root = Path(root).resolve()
    key = (str(root), scope)
    hit = _LOAD_CACHE.get(key)
    if hit is None:
        hit = _build(root, scope)
        _LOAD_CACHE[key] = hit
    return hit


def clear_cache() -> None:
    """Drop the memo. For tests that mutate a bundle on disk within one process."""
    _LOAD_CACHE.clear()
    _LAW_CACHE.clear()


def _law() -> Law:
    """The framework law, parsed once per process. It lives beside tools/, never inside a bundle."""
    path = Path(__file__).resolve().parent.parent / VOCABULARY
    hit = _LAW_CACHE.get(str(path))
    if hit is not None:
        return hit
    data, err = _parse_yaml(path)
    doc = Doc(relpath=f"{FRAMEWORK}/{VOCABULARY}", abspath=path, plane=FRAMEWORK, source="",
              kind="vocabulary", data=data, parse_error=err, anchors=collect_anchors(data))
    law = Law(
        doc=doc,
        measure_types=_as_dict(_as_dict(data.get("MeasureType")).get("members")),
        aggregation_effects=frozenset(_as_dict(_as_dict(data.get("aggregation_effect")).get("terms"))),
        axis_kinds=frozenset(_as_dict(_as_dict(data.get("axis_kind")).get("terms"))),
        namespaces=frozenset(k for k, v in data.items() if isinstance(v, dict) and v.get("kind")),
    )
    _LAW_CACHE[str(path)] = law
    return law


# The libyaml-backed loaders when PyYAML was built with them, else the pure-Python ones. MEASURED
# 2026-08-17 over 2.983 YAML files (the four corpus bundles + this repo): the two loaders returned
# IDENTICAL values on every file, 0 disagreements, and CSafeLoader took 739 ms against safe_load's
# 7.166 ms — 9,7x. Speed matters here because eight gates each load this model; the pure loader is
# 468 of the 496 ms one bundle costs.
_FAST_LOADER = getattr(yaml, "CSafeLoader", None)


def read_yaml(path):
    """(document AS WRITTEN, error-text) for ONE named file. THE estate's YAML reader. NEVER raises.

    Returns whatever the file holds — a mapping, a list, a scalar, or None for an empty file — plus
    the exception text, verbatim, when the file cannot be read or parsed.

    WHY IT IS PUBLIC: a change-protocol gate's own registers (`interventions/ledger.yaml`,
    `interventions/vanilla_delta.yaml`) sit OUTSIDE the model's document population — they are named
    files a gate is pointed at, not part of the tree the model indexes — so a gate must still be able
    to read one. Before this it did so through its own loader, and MEASURED 2026-08-17 the estate held
    two of them that did not even agree on whether a missing file and an unparseable file are the same
    thing. One reader, one wording, one place to change.

    The error text comes from the PURE-Python `yaml.safe_load` even when the fast loader is in use,
    because a gate prints it verbatim ("YAML parse error: …", "cannot parse …: …") and the two loaders
    word their exceptions differently. Value on the fast path, wording on the slow one.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:                    # noqa: BLE001 — an unreadable file is a value
        return None, str(e)
    if _FAST_LOADER is not None:
        try:
            return yaml.load(text, Loader=_FAST_LOADER), None
        except Exception:                     # noqa: BLE001 — fall through for the canonical wording
            pass
    try:
        return yaml.safe_load(text), None
    except Exception as e:                    # noqa: BLE001 — bundle content must never raise
        return None, str(e)


def _parse_yaml(path: Path):
    """`read_yaml` coerced to the mapping view the document model stores: ({}, err) for anything that
    is not a mapping. The coercion is NOT a second reader — `Doc.is_mapping` keeps the distinction the
    coercion drops, so nothing has to re-read a file to learn what shape it was."""
    doc, err = read_yaml(path)
    return (doc if isinstance(doc, dict) else {}), err


def _plane_dir(declared, root: Path, fallback: str) -> Path:
    """The declared plane dir when it exists, else the conventional one. Mirrors the estate's rule."""
    d = Path(declared) if declared else None
    if d and d.is_dir():
        return d
    fb = root / fallback
    return fb if fb.is_dir() else (d or fb)


def _file_set(root: Path, layout, scope: str) -> list:
    """The document population for a scope. TWO scopes, and only two — both already exist in the
    estate as differing, measured predicates; naming them makes the difference visible instead of
    accidental.
    """
    if scope == "tree":
        # validate_schema's predicate, preserved VERBATIM: it deliberately reaches published copies
        # under artifacts/, and 24 of its 24 errors on one corpus bundle come from that width.
        return sorted(p for p in root.rglob("*.yaml")
                      if not any(part in _TREE_SKIP for part in p.parts))
    planes = [root / str(v).strip("/").split("/")[0] for v in (layout.planes or {}).values()]
    roots = [p for p in planes if p.is_dir()] or [root]
    out: list = []
    for rt in roots:
        for pattern in ("*.yaml", "*.yml"):
            out += [p for p in rt.rglob(pattern)
                    if _PLANE_EXCLUDE_PART not in p.parts and _PLANE_EXCLUDE_NAME not in p.name]
    return sorted(set(out))


def _doc_kind(path: Path, layout, concepts_dir: Path) -> str:
    """A document's kind, from its LOCATION — never from its content, so a mis-shaped file still
    lands in the population its gate expects to find it in."""
    name = path.name
    if _within(path, concepts_dir):
        return "concept"
    for attr, kind in (("descriptors", "dataset"), ("sources", "source"), ("transforms", "transform")):
        d = getattr(layout, attr, None)
        if d and _within(path, Path(d)):
            return kind
    if name in ("edges.yaml", "edges.yml"):
        return "edges"
    if name in ("rules.yaml", "rules.yml"):
        return "rules"
    if name == "shapes.yaml":
        return "shapes"
    if name == "vocabulary.yaml":
        return "vocabulary"
    if name == "mac.project.yaml":
        return "project"
    if name == "ledger.yaml":
        return "ledger"
    if name == "vanilla_delta.yaml":
        return "delta"
    if name == "data_quality_register.yaml":
        return "dq_register"
    return "other"


def _within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _stated_kind(doc_kind: str) -> str:
    """Where a statement came from. A LOCATION table — it never names a bundle instance.

    ontology/**            authored   the ontology plane is written by a human/agent, by definition
    data/transforms/**     authored   the transform is the authored cause of its output
    data/{datasets,sources} projected harvested from the warehouse (their own metadata says so)
    data/lookups/*.csv     projected  a register materializes a domain that lives elsewhere
    «framework»/**         authored   the law is authored once
    """
    if doc_kind in ("dataset", "source"):
        return "projected"
    return "authored"


# -- registers -------------------------------------------------------------------------------------

def _load_registers(root: Path) -> dict:
    d = root.joinpath(*LOOKUPS_DIR)
    out: dict = {}
    if not d.is_dir():
        return out
    for path in sorted(d.glob("*.csv")):
        raw_stem = path.stem
        stem = raw_stem[:-len(LOOKUP_SUFFIX)] if raw_stem.endswith(LOOKUP_SUFFIX) else raw_stem
        relpath = _rel(path, root)
        try:
            # A register may carry a "#" preamble stating what it is, what generated it and what is
            # known-defective about it — provenance a bare CSV cannot hold. Feeding those lines to
            # DictReader takes the first comment as the header and every later one as a row: a 1.108-row
            # register was read as 1.163 and its projected page published that number. Skip them here,
            # once, so every consumer sees the same row set.
            _lines = [l for l in path.read_text(encoding="utf-8").splitlines()
                      if not l.lstrip().startswith("#")]
            reader = csv.DictReader(_lines)
            fieldnames = tuple(reader.fieldnames or ())
            rows = tuple(RegisterRow(stem, i, dict(r), relpath)
                         for i, r in enumerate(reader, start=2))   # +2: the header is line 1
            err = None
        except Exception as e:                # noqa: BLE001 — an unreadable register is a value
            fieldnames, rows, err = (), (), str(e)
        is_measure = bool(rows) and all(c in fieldnames for c in MEASURE_REGISTER_COLUMNS)
        out.setdefault(stem, Register(
            stem=stem, raw_stem=raw_stem, path=path, relpath=relpath, columns=fieldnames, rows=rows,
            is_measure_register=is_measure,
            discriminators=_discriminators(fieldnames, rows) if is_measure else frozenset(),
            read_error=err))
    return out


def _discriminators(columns, rows) -> frozenset:
    """A measure register's DISCRIMINATOR columns: the header columns that are not the law's three
    and whose values vary down the file — i.e. the columns that say WHICH MEASURE a row is."""
    out = set()
    for col in columns:
        if col in MEASURE_REGISTER_COLUMNS:
            continue
        if len({(r.cells.get(col) or "") for r in rows}) > 1:
            out.add(col)
    return frozenset(out)


def _axis_role(axis_name: str, selectors: frozenset) -> str:
    """An axis is a MEASURE SELECTOR when its name is a discriminator of a measure register.

    WHY: a register's discriminator columns describe WHICH measure you are reading; they never
    describe how ONE measure folds along a data axis. Selecting a different value of such a column
    selects a different measure, so the additivity law has nothing to say about it.

    MEASURED 2026-08-17: without this derivation the additivity family reports 9 contradicting
    axis-facts on the fpl2 bundle; with it, 2 (the real ones). A 7x over-fire — the same class of
    defect this module was built to stop, produced by the module itself if the role is ignored.
    """
    return "measure_selector" if axis_name in selectors else "aggregation_axis"


# -- concepts --------------------------------------------------------------------------------------

def _build_concept(doc: Doc, selectors: frozenset) -> Concept:
    data = doc.data
    c = _as_dict(data.get("concept"))
    name = c.get("name") if isinstance(c.get("name"), str) else ""
    cls = c.get("class") if isinstance(c.get("class"), str) else None
    stem = Path(doc.relpath).stem
    kind = _stated_kind(doc.kind)

    groundings = []
    g = _as_dict(data.get("grounding"))
    # `grounding.field_roles` is declared ONCE per concept, above the sources list — so it is held once,
    # on the Concept. It used to be copied onto every Grounding, which put the same fact in N places and
    # LOST it entirely when a concept declared field_roles but no source to hang them on. (The gate that
    # reads it, check_shapes' field-roles-grounded, must still report those columns as ungrounded rather
    # than fall silent; measured 2026-08-17 the corpus has 0 such concepts, which is exactly why a
    # copy-per-grounding survived unnoticed.)
    field_roles = {k: v for k, v in _as_dict(g.get("field_roles")).items() if isinstance(k, str)}
    if isinstance(g.get("table"), str):       # the sql_table adapter form
        groundings.append(Grounding(name, g["table"], None, (), (),
                                    Site(doc.relpath, "grounding.table")))
    for i, s in enumerate(_as_list(g.get("sources"))):
        s = _as_dict(s)
        ref = s.get("relation")
        if not isinstance(ref, str):
            continue
        groundings.append(Grounding(
            concept=name, relation_ref=ref, relation=None,
            key=tuple(str(k) for k in _as_list(s.get("key"))),
            columns=tuple(str(x) for x in _as_list(s.get("columns"))),
            site=Site(doc.relpath, f"grounding.sources[{i}].relation")))

    values = _build_values(doc, name, kind)
    measure = _build_measure(doc, name, c, kind, selectors) if cls == "measure" else None
    return Concept(name=name, stem=stem, cls=cls, doc=doc, groundings=tuple(groundings),
                   field_roles=field_roles, values=values, measure=measure)


def _build_values(doc: Doc, concept: str, kind: str) -> ValueSet | None:
    v = doc.data.get("values")
    if not isinstance(v, dict):
        return None
    closure = None
    if v.get("closure") is not None:
        closure = Stated(v["closure"], Site(doc.relpath, "values.closure"), kind)
    reg_ref = None
    rb = _as_dict(v.get("realized_by"))
    register = _as_dict(rb.get("params")).get("register")
    if isinstance(register, str) and register.strip():
        reg_ref = Stated(register, Site(doc.relpath, "values.realized_by.params.register"), kind)
    members = []
    for i, it in enumerate(_as_list(v.get("items"))):
        if not isinstance(it, dict):
            continue
        conf = it.get("confidence")
        members.append(Member(
            concept=concept, code=str(it.get("code", i)),
            label=it.get("label") if isinstance(it.get("label"), str) else None,
            confidence=(Stated(conf, Site(doc.relpath, f"values.items[{i}].confidence"), kind)
                        if conf is not None else None),
            site=Site(doc.relpath, f"values.items[{i}]")))
    return ValueSet(concept, closure, reg_ref, None, tuple(members))



def _derived_additivity(axis: str, axis_kinds: dict, measure_type, selectors: frozenset):
    """The law's value for an axis the concept did not write, carrying the law's own provenance.

    v0.1.16. Before this, `additivity` was schema-REQUIRED, so every measure wrote out what its own
    `measure_type` already implies — the concept authored the premise AND the conclusion, and the two
    could drift. `ideal_stock` declared `Target` and wrote `geography: additive`, which the law
    forbids; ANCHOR_05 summed Ideal Stock across models on the strength of it and stood for weeks.
    You cannot contradict a value you do not write.

    NOTHING IS REIMPLEMENTED HERE. `Law.additivity()` already resolves (MeasureType x axis_kind) and
    stamps the result with its Site in «framework»/mac_vocabulary.yaml, so a consumer can always see
    WHERE a value came from — concept or law — without caring which.

    A MEASURE SELECTOR is answered `none` and never asked of the law: selecting a different value of a
    discriminator selects a different MEASURE, so no fold along it is meaningful (see _axis_role), and
    the law deliberately makes no statement about one.

    Returns None when the law cannot decide — an unknown measure_type, or an axis with no declared
    kind. None is the honest answer; inventing `additive` would be the exact footgun this prevents.
    """
    if axis in selectors:
        return Stated("none", Site(f"{FRAMEWORK}/{VOCABULARY}", "measure_selector"), "framework")
    if not measure_type or not axis_kinds.get(axis):
        return None
    stated = _law().additivity(measure_type, axis_kinds[axis])
    if stated is None:
        return None
    return Stated(str(stated.value).split(".")[-1], stated.site, "framework")

def _build_measure(doc: Doc, concept: str, c: dict, kind: str, selectors: frozenset) -> Measure:
    s = _as_dict(c.get("semantics"))
    additivity = _as_dict(s.get("additivity"))
    axis_kinds = _as_dict(s.get("axis_kinds"))
    axes: dict = {}
    for axis in list(additivity) + [a for a in axis_kinds if a not in additivity]:
        if not isinstance(axis, str):
            continue
        axes[axis] = Axis(
            measure=concept, name=axis,
            kind=(Stated(axis_kinds[axis], Site(doc.relpath, f"concept.semantics.axis_kinds.{axis}"), kind)
                  if axis in axis_kinds else None),
            additivity=(Stated(additivity[axis],
                               Site(doc.relpath, f"concept.semantics.additivity.{axis}"), kind)
                        if axis in additivity else
                        _derived_additivity(axis, axis_kinds, s.get("measure_type"), selectors)),
            role=_axis_role(axis, selectors))
    mt = s.get("measure_type")
    unit = s.get("unit")
    return Measure(
        concept=concept,
        measure_type=(Stated(mt, Site(doc.relpath, "concept.semantics.measure_type"), kind)
                      if mt is not None else None),
        unit=(Stated(unit, Site(doc.relpath, "concept.semantics.unit"), kind) if unit is not None else None),
        axes=axes)


# -- relations -------------------------------------------------------------------------------------

def _build_relation(doc: Doc, role: str) -> Relation:
    stem = Path(doc.relpath).stem
    table = _as_dict(doc.data.get("table"))
    physical = table.get("name") if isinstance(table.get("name"), str) else None
    columns: dict = {}
    for i, col in enumerate(_as_list(doc.data.get("columns"))):
        col = _as_dict(col)
        cname = col.get("name")
        if not isinstance(cname, str):
            continue
        columns.setdefault(cname, Column(
            relation=stem, name=cname,
            type=col.get("type") if isinstance(col.get("type"), str) else None,
            role=(col.get("role") if isinstance(col.get("role"), str)
                  else col.get("x-field_role") if isinstance(col.get("x-field_role"), str) else None),
            nullable=col.get("nullable") if isinstance(col.get("nullable"), bool) else None,
            description=col.get("description") if isinstance(col.get("description"), str) else None,
            site=Site(doc.relpath, f"columns[{i}]")))
    fks = []
    for i, fk in enumerate(_as_list(doc.data.get("foreign_keys"))):
        fk = _as_dict(fk)
        if not all(isinstance(fk.get(k), str) for k in ("from_column", "to_table", "to_column")):
            continue
        fks.append(ForeignKey(
            relation=stem, name=fk.get("name") if isinstance(fk.get("name"), str) else None,
            from_column=fk["from_column"], to_table=fk["to_table"], to_column=fk["to_column"],
            site=Site(doc.relpath, f"foreign_keys[{i}]")))
    return Relation(name=stem, schema=table.get("schema") if isinstance(table.get("schema"), str) else None,
                    physical=physical if physical and physical != stem else None,
                    role=role, doc=doc, columns=columns, foreign_keys=tuple(fks))


# -- edges -----------------------------------------------------------------------------------------

def _endpoint_names(e: dict) -> tuple:
    """Concept names an edge's endpoints declare, tolerating both authored shapes (a from/to mapping,
    and a plain list)."""
    ep = e.get("endpoints")
    names = []
    if isinstance(ep, dict):
        for side in ("from", "to"):
            v = _as_dict(ep.get(side)).get("concept")
            if isinstance(v, str):
                names.append(v)
        for k, v in ep.items():               # any further named endpoints, in declaration order
            if k in ("from", "to"):
                continue
            v = _as_dict(v).get("concept")
            if isinstance(v, str):
                names.append(v)
    elif isinstance(ep, list):
        for item in ep:
            v = _as_dict(item).get("concept")
            if isinstance(v, str):
                names.append(v)
            elif isinstance(item, str):
                names.append(item)
    return tuple(names)


def _build_edges(docs, kind_of) -> list:
    edges = []
    for doc in docs:
        for i, e in enumerate(_as_list(doc.data.get("edges"))):
            e = _as_dict(e)
            eid = e.get("edge_id")
            if not isinstance(eid, str):
                continue
            base = f"edges[{i}]"
            k = kind_of(doc)
            edges.append(Edge(
                edge_id=eid,
                level=e.get("level") if isinstance(e.get("level"), str) else None,
                join_rule=(Stated(e["join_rule"], Site(doc.relpath, f"{base}.join_rule"), k)
                           if isinstance(e.get("join_rule"), str) else None),
                realized_by=(Stated(e["realized_by"], Site(doc.relpath, f"{base}.realized_by"), k)
                             if isinstance(e.get("realized_by"), str) else None),
                endpoints=_endpoint_names(e), concepts=(), doc=doc,
                site=Site(doc.relpath, base)))
    return edges


# -- the build -------------------------------------------------------------------------------------

def _build(root: Path, scope: str) -> Bundle:
    layout = resolve(root)
    law = _law()
    planes = tuple(str(v).strip("/").split("/")[0] for v in (layout.planes or {}).values())
    concepts_dir = Path(layout.ontology) / CONCEPTS_DIR

    parsed: dict = {}                          # abspath -> Doc, so nothing is parsed twice

    def get_doc(path: Path) -> Doc:
        path = path.resolve()
        hit = parsed.get(path)
        if hit is not None:
            return hit
        relpath = _rel(path, root)
        raw, err = read_yaml(path)
        data = raw if isinstance(raw, dict) else {}
        plane = relpath.split("/")[0] if relpath.split("/")[0] in planes else ""
        doc = Doc(relpath=relpath, abspath=path, plane=plane,
                  source=source_of(relpath, planes),
                  kind=_doc_kind(path, layout, concepts_dir),
                  data=data, parse_error=err, anchors=collect_anchors(data),
                  is_mapping=isinstance(raw, dict))
        parsed[path] = doc
        return doc

    docs = tuple(get_doc(p) for p in _file_set(root, layout, scope))
    doc_by_relpath = {d.relpath: d for d in docs}

    # ---- registers, and the axis roles they license ----------------------------------------------
    registers = _load_registers(root)
    selectors = frozenset().union(*[r.discriminators for r in registers.values()]) \
        if registers else frozenset()

    # ---- relations (both planes; the ontology binds by BARE name, so both keys are indexed) --------
    relations: dict = {}
    relation_dirs = []
    for attr, role in (("descriptors", "dataset"), ("sources", "raw_source")):
        d = getattr(layout, attr, None)
        if not d or not Path(d).is_dir():
            continue
        relation_dirs.append(_rel_dir(d, root))
        for p in sorted(Path(d).glob("*.yaml")):
            rel_obj = _build_relation(get_doc(p), role)
            relations.setdefault(rel_obj.name, rel_obj)
    for rel_obj in list(relations.values()):   # table.name as a secondary key — the stem wins
        if rel_obj.physical:
            relations.setdefault(rel_obj.physical, rel_obj)

    # ---- concepts: ONE PER FILE, sorted rglob (covers flat and foldered in one expression) ---------
    concept_files = sorted(concepts_dir.rglob("*.yaml")) if concepts_dir.is_dir() else []
    concepts = tuple(_build_concept(get_doc(p), selectors) for p in concept_files)
    concept_index: dict = {}
    for c in concepts:
        if c.name:
            concept_index.setdefault(c.name, c)
    for c in concepts:
        concept_index.setdefault(c.stem, c)

    # ---- objects: the five protocol-bearing kinds, in the estate's own dir order -------------------
    object_dirs = {
        "source": _plane_dir(getattr(layout, "sources", None), root, "data/sources"),
        "transform": _plane_dir(getattr(layout, "transforms", None), root, "data/transforms"),
        "dataset": _plane_dir(getattr(layout, "descriptors", None), root, "data/datasets"),
        "concept": _plane_dir(concepts_dir, root, "ontology/concepts"),
        "lookup": root.joinpath(*LOOKUPS_DIR),
    }
    objects: dict = {}
    for kind, d in object_dirs.items():
        if not Path(d).is_dir():
            continue
        if kind == "lookup":
            found = sorted(Path(d).glob("*.csv"))
        elif kind == "concept":
            found = sorted(Path(d).rglob("*.yaml"))   # foldered by domain, or flat
        else:
            found = sorted(Path(d).glob("*.yaml"))    # the data planes are flat by contract
        for p in found:
            raw_stem = p.stem
            stem = (raw_stem[:-len(LOOKUP_SUFFIX)]
                    if kind == "lookup" and raw_stem.endswith(LOOKUP_SUFFIX) else raw_stem)
            ref = f"{kind}:{stem}"
            if ref in objects:
                continue
            doc = None if kind == "lookup" else get_doc(p)
            prov = None
            if doc is not None:
                raw = _as_dict(doc.data.get("metadata")).get("provenance")
                if raw is not None:
                    prov = Stated(raw, Site(doc.relpath, "metadata.provenance"),
                                  _stated_kind(doc.kind))
            objects[ref] = Object(ref=ref, kind=kind, stem=stem, raw_stem=raw_stem, path=p, doc=doc,
                                  register=registers.get(stem) if kind == "lookup" else None,
                                  provenance=prov)

    # ---- edges ------------------------------------------------------------------------------------
    edge_docs = [d for d in docs if d.kind == "edges"]
    if not edge_docs:                          # a flat bundle may keep edges.yaml outside the scope
        ef = Path(layout.ontology) / "edges.yaml"
        if ef.is_file():
            edge_docs = [get_doc(ef)]
    edges = tuple(_build_edges(sorted(edge_docs, key=lambda d: d.relpath),
                               lambda d: _stated_kind(d.kind)))

    bundle = Bundle(
        root=root, layout=layout, scope=scope, planes=planes, law=law,
        _docs=docs, _doc_by_relpath=doc_by_relpath,
        _objects=objects, _object_dirs={k: _rel_dir(v, root) for k, v in object_dirs.items()},
        _relations=relations, _relation_dirs=tuple(relation_dirs),
        _concepts=concepts, _concept_index=concept_index,
        _registers=registers, _edges=edges)

    # ---- resolve the links, once, in place (the model is frozen to callers, not to the loader) -----
    _resolve(bundle)
    return bundle


def _resolve(b: Bundle) -> None:
    """Link every reference. A failure lands as an Unresolved AT THE REFERRING FIELD — never dropped,
    never raised."""
    for c in b._concepts:
        linked = tuple(
            Grounding(g.concept, g.relation_ref, b.relation(g.relation_ref, g.site), g.key, g.columns,
                      g.site)
            for g in c.groundings)
        object.__setattr__(c, "groundings", linked)
        if c.values is not None and c.values.register_ref is not None:
            object.__setattr__(c.values, "register",
                               b.register(c.values.register_ref.value, c.values.register_ref.site))
    for e in b._edges:
        object.__setattr__(e, "concepts", tuple(b.concept(n, e.site) for n in e.endpoints))


# ==================================================================================================
# 12. fact families
# ==================================================================================================

def _fold_declared_additivity(value):
    """The concept's own word, folded into the closed comparison domain {additive, non-additive}.

    Anything else does NOT fold, and a statement that cannot fold totally is never admitted: a
    statement the model cannot compare is not evidence of anything.
    """
    t = str(value or "").strip().lower().replace("_", "-")
    return t if t in ("additive", "non-additive") else None


def _fold_aggregation_effect(term, law: Law):
    """A framework aggregation_effect term, folded the same way.

    ONE term licenses a SUM: `additive`. Every other member of the closed domain folds to
    non-additive. The fold reads the framework's own closed set and names exactly that one term — it
    enumerates no bundle vocabulary.
    """
    t = str(term or "").split(".")[-1].strip()
    if t not in law.aggregation_effects:
        return None
    return "additive" if t == "additive" else "non-additive"


def _family_measure_additivity(b: Bundle) -> tuple:
    """FAMILY `measure.additivity` — *how measure M folds along axis A*.

    Fact key is (measure, AXIS), not (measure, axis KIND). Measured during design: the coarser key
    produces a FALSE POSITIVE on a bundle whose measure legitimately says `additive` on one
    categorical axis and `non-additive` on another — one concept making two different, both correct,
    statements at a granularity the law cannot express. Per-axis keying drops that to 0.

    Statement 1, authored: the concept's own `semantics.additivity.<axis>`.
    Statement 2, projected: the law, aimed at THAT axis through the concept's OWN bridge — it is
    admitted only when the concept itself declares both `semantics.measure_type` (a member of the
    closed MeasureType domain) and `semantics.axis_kinds.<axis>` (a member of the closed axis_kind
    domain). That declared bridge is what makes the two statements the same subject; a name
    resemblance never would.

    A measure_selector axis produces no law statement (see _axis_role).
    """
    out = []
    for c in b.concepts():
        m = c.measure
        if m is None:
            continue
        for axis_name, axis in m.axes.items():
            if axis.additivity is None:        # the family is about a DECLARED fold; nothing stated,
                continue                       # nothing to compare, and deriving it is not a defect
            # v0.1.16: a DERIVED value is not a second home — it IS the law's statement, carrying the
            # law's own Site. Counting it here would compare the law against itself and report every
            # measure as restating a fact nobody wrote. `provenance == "framework"` is the marker
            # _derived_additivity stamps on `kind`; an authored value never carries it.
            if axis.additivity.kind == "framework":
                continue
            statements, normalized = [], []
            # HOME FIRST: the law is what the concept's value is derivable FROM, never the reverse,
            # so it leads the tuple and Fact.home() names the site that should hold the fact once.
            law_stated = _law_statement(b, m, axis)
            if law_stated is not None:
                folded_law = _fold_aggregation_effect(law_stated.value, b.law)
                if folded_law is not None:
                    statements.append(law_stated)
                    normalized.append(folded_law)
            folded = _fold_declared_additivity(axis.additivity.value)
            if folded is not None:
                statements.append(axis.additivity)
                normalized.append(folded)
            if not statements:
                continue
            out.append(Fact("measure.additivity", (m.concept, axis_name),
                            tuple(statements), tuple(normalized)))
    return tuple(sorted(out, key=lambda f: f.key))


def _law_statement(b: Bundle, m: Measure, axis: Axis) -> Stated | None:
    if axis.role != "aggregation_axis" or m.measure_type is None or axis.kind is None:
        return None
    mt = str(m.measure_type.value).split(".")[-1].strip()
    ak = str(axis.kind.value).split(".")[-1].strip()
    if mt not in b.law.measure_types or ak not in b.law.axis_kinds:
        return None                            # not a member of a closed domain -> no law statement
    return b.law.additivity(mt, ak)


_FACT_FAMILIES = {"measure.additivity": _family_measure_additivity}


def families() -> tuple:
    """The fact families this model can compute. A family is a function plus one dict line — there is
    no registry, no entry point, no config."""
    return tuple(sorted(_FACT_FAMILIES))
