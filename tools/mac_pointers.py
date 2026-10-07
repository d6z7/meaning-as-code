#!/usr/bin/env python3
"""mac_pointers.py — resolve declaration-to-declaration pointers from the CATALOGUE, not from code.

MOVED HERE 2026-10-04 from mac-platform/tools/estate/pointer_index.py, the step after promoting
mac_pointers.yaml. The catalogue said WHICH pointers a bundle may carry and this says HOW each one
resolves; splitting them across two repositories left the framework's own gates unable to use
either — the dependency runs platform -> framework, so a MAC gate could not import a resolver
living in the platform.

WHAT IT IS FOR, and the distinction that took a day to get right: every gate in this estate
re-derives pointer resolution PRIVATELY — 33 lines of its own path and name handling across seven
files, each slightly different. The defect is "privately", not "re-derives". A gate must keep
deriving from the authored YAML, because a gate that reads the emitted graph agrees with it by
construction and could never catch a bug in it ("READ FROM THE SSOT, NOT FROM THE PROJECTION",
check_datasets_are_grounded.py). So this module is shared and the TABLE is not: one implementation
of how a pointer resolves, called by many gates, each still reading the bundle itself.


THE DEFECT THIS REPLACES. Every pointer kind in the estate is gated somewhere — and nothing
enumerates them. check_references.py owns six kinds in hardcoded handlers; check_lookups,
check_registers_reachable, check_dangling_references, check_rule_reference_basis and three more
each own one. The census measured M = 121 pointer kinds across contoso5, so coverage is ~5%, and
each gate re-derives its own resolution privately and throws it away. This module reads
mac_pointers.yaml (framework canon since 2026-10-04) and produces the table they all discard.

WHY IT PARSES YAML INSTEAD OF GREPPING. A pointer in a real bundle lives in any of six carriers,
and a text regex sees only the first: a scalar value · a prose scalar · a comment · an embedded SQL
string · a map KEY rather than a value · and a YAML alias (contoso5 has 16 anchors and 110
aliases — "a text-based resolver sees *id010, not the target"). safe_load resolves aliases for
free, which is why this is a parser and not a grep. Carriers covered here: value, prose.
Comments are NOT yet covered and the gate says so rather than scoring them as clean.

LOCATORS ARE STRUCTURAL AND ROOT-RELATIVE, in compile.json's existing shape
(`grounding.sources[0].register`), because that is the estate's precedent and because an absolute
path in a published payload is a leak class.

READ-ONLY. Opens a bundle, writes nothing into it, takes no out_dir.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

def framework_root() -> Path | None:
    """Where the installed framework is — by IMPORT, then by declaration, never by a hardcoded
    sibling path (this repo already retired "the runtime hardcodes where the estate is")."""
    import os
    try:
        import meaning_as_code                              # noqa: PLC0415
        return Path(meaning_as_code.__file__).resolve().parent
    except Exception:                                       # noqa: BLE001
        pass
    env = os.environ.get("MEANING_AS_CODE")
    return Path(env).resolve() if env and Path(env).is_dir() else None

def _catalogue_path() -> Path:
    """`mac_pointers.yaml` in the installed framework — the ONE home of the pointer kinds.

    PROMOTED 2026-10-04. It lived at tools/estate/mac_pointers.prototype.yaml, which meant the
    catalogue was a fact about this checkout: another bundle, or the same bundle on another
    machine, had none of it. It now ships in the wheel beside mac_vocabulary.yaml, and this
    resolves it the way every other framework file here is resolved — by import, then by the
    declared MEANING_AS_CODE override, never by a hardcoded sibling path.

    NO LOCAL FALLBACK. A copy under tools/ would be a second home for the thing whose entire
    purpose is that pointer kinds have one, and it would be the copy that went stale. If the
    framework is not resolvable the readers REFUSE, which is a state this estate already
    distinguishes from "the bundle is wrong".
    """
    root = framework_root()
    return (root / "mac_pointers.yaml") if root else Path("mac_pointers.yaml<unresolved>")


def catalogue_or_refuse(path: Path) -> Path:
    """The catalogue, or a refusal a reader can act on.

    AN UNRESOLVABLE FRAMEWORK IS COULD-NOT-RUN, NOT A FINDING — the distinction this estate draws
    everywhere else and had to draw here too: with no catalogue every bundle resolves zero pointer
    kinds, which is indistinguishable from a bundle that declares none.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"mac_pointers.yaml was not found at {path}. Either the framework is not resolvable "
            f"(meaning_as_code not importable and MEANING_AS_CODE unset) or it predates "
            f"mac.pointers/1. This is COULD-NOT-RUN, never a verdict about a bundle.")
    return path


REGISTRY = _catalogue_path()

#: `# GENERATED by mac_resources.py/1 — do not edit; regenerate.` on the first lines of a file.
GENERATED_COMMENT = re.compile(r"GENERATED by\s+([A-Za-z0-9_.]+/[0-9]+)")

#: A backticked root-relative path inside a prose scalar.
PROSE_PATH = re.compile(r"`([A-Za-z0-9_./-]+\.(?:csv|sql|yaml|yml|json|md))`")

CLOSED_RESOLUTIONS = {
    "resolved", "dangling", "ambiguous", "external", "placeholder", "uncovered_kind",
    # A DECLARED RETIREMENT IS A MIGRATION, NOT A BREAK. A pointer at a retired object resolves to
    # the tombstone, which carries the successor — so it must not be counted among the dangling,
    # and it must carry a dst so the repoint worklist can join it. Without this state the worklist
    # could never return a row: a retired target is gone from disk, so the reference dangled with
    # dst NULL and nothing could match it to the tombstone naming it.
    "retired",
}
#: `measured` is the seventh carrier and the only one not written in a declaration at all: the
#: edge was MEASURED by another tool and is read from its artifact. Added deliberately rather than
#: stretching `value` to cover it, because the distinction is the point — a measured edge and a
#: declared one have different authorities, and the estate already keeps `claims` separate from
#: `feeds` for exactly that reason.
CLOSED_CARRIERS = {"value", "prose", "comment", "embedded_sql", "map_key", "yaml_alias",
                   "measured"}


@dataclass
class Ref:
    reference_kind: str
    carrier: str
    src_path: str
    src_locator: str
    raw_value: str
    resolution: str
    resolution_basis: str
    #: The tool that WROTE the carrier file, read from the file's own declaration. A dangling
    #: pointer in a GENERATED artifact is not an authored mistake and must not be reported as one:
    #: the fix is to re-run the producer, and the artifact says who that is.
    producer: str | None = None
    dst: str | None = None
    #: THE SOURCE, WHEN THE CARRIER FILE IS NOT IT. Every AUTHORED pointer is written inside the
    #: thing that depends on the target, so the source is the carrier and needs no field. A
    #: MEASURED edge is different: data/lineage/lineage.json records that a dataset grounds a
    #: concept, and the carrier is the lineage artifact, which is neither end.
    src: str | None = None
    #: The ENDPOINT KINDS, when they are not the catalogue row's. A measured node declares its own
    #: kind through `lineage.node_kinds`, and that is the authority — the row's src_kind/dst_kind
    #: describe the SHAPE of the edge, which is the same thing only when every instance agrees.
    src_kind: str | None = None
    dst_kind: str | None = None

    @property
    def reference_id(self) -> str:
        """A ROW key, and it must include the value — unlike a DISPOSITION signature, which is
        deliberately location-only so that repointing a pointer does not orphan its owner.

        One scalar can carry several pointers: `location.yaml`'s definition prose names TWO
        register csvs at a single locator, so (path, kind, locator) is not unique and a primary
        key built from it collides. Two distinct targets written in one place are two references,
        which is simply true.
        """
        return hashlib.sha256(
            f"{self.src_path}|{self.reference_kind}|{self.src_locator}|{self.raw_value}".encode()
        ).hexdigest()[:16]


@dataclass
class Index:
    refs: list[Ref] = field(default_factory=list)
    coverage: list[dict] = field(default_factory=list)
    ambiguous: list[dict] = field(default_factory=list)
    producers: dict[str, str | None] = field(default_factory=dict)
    out_of_scope: list = field(default_factory=list)
    carved_out: list = field(default_factory=list)
    #: Pointer-shaped nodes in files the BUNDLE rules outside framework scope. Recorded, never
    #: resolved and never turned into objects — see the claim guard in `resolve`.
    oos_pointers: list = field(default_factory=list)
    #: `<relation>.<column>` -> the descriptor declaring it; the target side of the column edges.
    columns: dict = field(default_factory=dict)
    #: Provenance of the lineage read — what it saw and what it SKIPPED.
    lineage: dict = field(default_factory=dict)
    concepts: dict[str, str] = field(default_factory=dict)
    relations: dict[str, str] = field(default_factory=dict)
    files_seen: int = 0
    files_parsed: int = 0
    #: THE BUNDLE'S OWN FILE COUNT — the denominator `files_seen` was standing in for. They
    #: differed by 260 on contoso5 and every headline quoted the smaller one.
    files_in_bundle: int = 0
    #: WHICH files, not how many. The counters alone cannot answer "what do you not track",
    #: because the answer is a list of paths and a reason each.
    seen_paths: list = field(default_factory=list)
    parsed_paths: list = field(default_factory=list)
    unparsed_paths: list = field(default_factory=list)
    kinds: dict[str, dict] = field(default_factory=dict)


#: ----------------------------------------------------------------------------------------------
#: READING YAML: ONE LOADER, ONE PARSE PER FILE
#: ----------------------------------------------------------------------------------------------
#: PyYAML's pure-python parser was 96% of a resolve -- 24.7 of 25.8 s, in 748 parses for 421
#: files. Two separate costs hid in that number and each has its own fix.
#:
#: COST ONE, the parser. Measured on contoso5's 420 YAML files (1.8 MB of source): 426.9 ms for
#: the python loader against 50.4 ms for the libyaml one, 8.5x, for identical semantics --
#: CSafeLoader resolves aliases exactly as safe_load does, which is the one property this module
#: depends on ("a text-based resolver sees *id010, not the target"). The getattr fallback is not
#: decoration: a PyYAML wheel built without libyaml has no CSafeLoader, and the resolver must
#: still run there, only slower.
LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

#: Reported, not assumed, so a slow run can be explained instead of guessed at.
LIBYAML = LOADER is not yaml.SafeLoader

#: COST TWO, re-parsing. 748 parses for 421 files is 1.8x per file, and this catalogue alone is
#: parsed six times a run by six accessors that each read one of its sections. A cache fixes it,
#: but an UNBOUNDED cache is the same scalability defect one layer down: parsed docs measured
#: 5.6x their source bytes, so a bundle 100x this one would hold multiple GB. The budget caps the
#: cache at ~90 MB resident and, once spent, serves misses straight through -- it does NOT evict,
#: because every pass here is a full sweep of the corpus and an LRU under a sequential scan
#: thrashes to a 0% hit rate while still paying the eviction. Above the budget this degrades to
#: "no cache, still libyaml", which is the 8.5x, not to an OOM. contoso5 fits nine times over.
#:
#: WHAT THE TWO TOGETHER BOUGHT, on contoso5, whole `estate_graph build`, best of three:
#:   both fixes + sqlite   1,650 ms          <- today
#:   cache only            3,970 ms          libyaml is worth 2.4x
#:   libyaml only          2,770 ms          parse-once is worth 1.7x
#:   neither              16,380 ms          the python loader alone cost 10x
#:   neither, + duckdb    25,700 ms          <- the default before 2026-10-04, so 15.7x in all
DOC_CACHE_BUDGET_BYTES = 16 * 1024 * 1024
_DOC_CACHE: dict[tuple[str, int, int], Any] = {}
_DOC_CACHE_BYTES = 0
_MISS = object()


def load_yaml_shared(path: Path) -> Any:
    """The cached document itself. THE CALLER MUST NOT MUTATE IT, OR ITS NEXT READER INHERITS THE
    EDIT. Use `load_yaml` unless the call is in a hot loop that only navigates.

    Two readers earn this. `pointer_load._doc` is called once per POINTER, not once per file, so
    a copy per call would cost more than the parse it saves. And the content hash reads each
    carrier to digest it, never to change it.

    Keyed on (path, mtime_ns, size), so a file edited under a long-lived process -- the console --
    re-parses on its next read. A path-only cache serves the stale doc instead, and this estate
    has already lost an afternoon to a process holding code older than the fix on disk.
    """
    global _DOC_CACHE_BYTES
    st = path.stat()                      # raises what read_text would raise, before any work
    key = (str(path), st.st_mtime_ns, st.st_size)
    doc = _DOC_CACHE.get(key, _MISS)
    if doc is _MISS:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=LOADER)
        if _DOC_CACHE_BYTES + st.st_size > DOC_CACHE_BUDGET_BYTES:
            return doc                    # past the budget: uncached, so already unshared
        _DOC_CACHE[key] = doc
        _DOC_CACHE_BYTES += st.st_size
    return doc


def load_yaml(path: Path) -> Any:
    """Parse `path` once and hand back a doc the caller OWNS. The default; prefer it.

    The copy is not caution, it is required: `load_registry` writes `_object_kinds` into every
    kind dict it returns, so a shared master would be mutated by its own first reader. A deepcopy
    measured 6.3 ms against a 50.4 ms libyaml parse of the same 40 files -- 8x cheaper than the
    parse it replaces, which is why the cache can be safe and still be a win.
    """
    return copy.deepcopy(load_yaml_shared(path))


def clear_doc_cache() -> None:
    """Drop the parse cache. For a test that writes a fixture and reads it back inside one
    mtime tick, and for a long-lived process that wants the memory back."""
    global _DOC_CACHE_BYTES
    _DOC_CACHE.clear()
    _DOC_CACHE_BYTES = 0


def _why_unparsed(exc: BaseException) -> str:
    """Why a claimed file would not parse, IN TERMS THAT DO NOT DEPEND ON WHICH LOADER RAN.

    These rows are emitted clockless so `verify` can prove them byte-exact, and PyYAML's two
    scanners word the same defect differently: libyaml says "not allowed in this context" and
    carries no source snippet, where the python one says "not allowed here" and quotes the line
    with a caret. Letting either phrasing into a row makes `verify` report a difference between
    two machines that agree about the file -- a wheel built without libyaml would fail the gate on
    8 of contoso5's .sql files. The POSITION is the actionable half and both report it the same.
    """
    mark = getattr(exc, "problem_mark", None)
    if mark is not None:
        return f"{type(exc).__name__} at line {mark.line + 1}, column {mark.column + 1}"
    return f"{type(exc).__name__}: {exc}"[:160]



def load_tombstone_spec(path: Path = REGISTRY) -> dict:
    """Where retirements are declared, and what an entry must carry."""
    return (load_yaml(path) or {}).get("tombstones") or {}


def census_kinds(path: Path = REGISTRY) -> int:
    """M, the denominator of every coverage claim — from the registry, not from a constant.

    It was `121` typed into two files. Two homes for one measurement is the drift this estate
    keeps re-measuring, and here the two were guaranteed to disagree the moment either was
    re-measured, with no gate able to notice.
    """
    doc = load_yaml(path) or {}
    n = ((doc.get("census") or {}).get("pointer_kinds"))
    if not isinstance(n, int) or n <= 0:
        raise ValueError(f"{path.name}#census.pointer_kinds must be a positive int, got {n!r}")
    return n


def file_population(bundle: Path, path: Path = REGISTRY) -> list[str]:
    """Every file this bundle carries THAT THIS REGISTRY CLAIMS — the denominator of the
    untracked side, which had none.

    Not `git ls-files`: a bundle is handed over as a directory and may arrive without a .git at
    all, and the integrity record must still be able to say what it did not look at.

    A CARVED-OUT PLANE IS NOT IN THIS DENOMINATOR, and that is the half this was missing. A
    carve-out already means "the registry could cover this and something else covers it better",
    and it already removed the plane from the WALK -- but not from the file census, so a plane
    the operator had ruled out still arrived as one row per file. On contoso5 that was 401 rows
    of 690, 58% of the census, for a plane nothing was going to judge. Listing 401 files as "not
    looked at" is noise; the carve-out entry, which names what covers the plane instead, is the
    fact. The COUNT is not lost either -- build.json reports `carved_out` so the number of files
    this removed stays visible beside the census rather than vanishing from it.

    The exclusions come from two different declarations ON PURPOSE. `exclude_dir_named` is
    machinery and is deliberately mirrored to `mac_resources.py#tree_hash`, which means adding
    anything to it changes every bundle's fingerprint -- so a SCOPING decision must never be
    expressed there. `carved_out` is where scoping decisions live, with a reason and a covering
    mechanism each.
    """
    doc = load_yaml(path) or {}
    spec = ((doc.get("census") or {}).get("file_population") or {})
    skip = set(spec.get("exclude_dir_named") or ())
    if not skip:
        raise ValueError(f"{path.name}#census.file_population.exclude_dir_named is empty — the "
                         f"census would include the emitted graph and describe itself")
    carved = [c["path"] for c in carved_out(path)]
    out = []
    for f in bundle.rglob(spec.get("include") or "**/*"):
        if not f.is_file():
            continue
        rel = f.relative_to(bundle)
        if any(part in skip for part in rel.parts):
            continue
        if spec.get("exclude_dot_entries") and any(part.startswith(".") for part in rel.parts):
            continue
        if _oos_match(rel.as_posix(), carved):
            continue
        out.append(rel.as_posix())
    return sorted(out)


#: Where a pointer kind can be, and whether this registry can see it. A CLOSED vocabulary.
KIND_STATUS = (
    "registered",            # a registry row claims this key
    "observed_unregistered", # the walk sees it and no row claims it — the registry's debt
    "unopened_filetype",     # it lives in a file type no glob opens, so it cannot even be judged
    "in_out_of_scope_file",  # the BUNDLE ruled its file outside framework scope; listed, not judged
)


def kind_census(bundle: Path, kinds: dict[str, dict], idx: "Index | None" = None) -> list[dict]:
    """EVERY POINTER KIND THIS BUNDLE CONTAINS, as a list — the denominator "of 121" never had.

    THE DEFECT. `census.pointer_kinds: 121` is a one-off measurement from 2026-10-02 with a prose
    basis ("88 in YAML + 33 in JSON") and NO enumeration, and every coverage claim on every panel
    was "N of 121" against it. Asked to list the 91 unregistered kinds, nothing could: the graph
    observes 15 distinct uncovered keys, not 91. A denominator with no population behind it is the
    exact defect this registry exists to end, one level up from the files — and it was the headline.

    THE THIRD BUCKET IS THE ONE THAT MATTERED. The walk opens `.yaml`, `.yml` and `.mac` and
    nothing else, so the bundle's 60 `.json` files were never read at all: 35 distinct
    pointer-shaped keys over 43,394 nodes, `binds` alone 17,681. Those kinds were not "uncovered"
    in any report — they were absent from the population, which is how 0 and "we did not look"
    arrive as the same answer.

    JSON IS COUNTED HERE AND DELIBERATELY NOT RESOLVED. Resolving it would invent verdicts for
    kinds that have no registry row, which is the opposite of this module's contract. The census
    says "this key exists here, in this many places, and nothing can judge it yet".
    """
    import json as _json
    import re as _re
    rows: dict[tuple, dict] = {}

    def add(key: str, where: str, status: str, claimed_by: str | None, path: str) -> None:
        k = (key, where)
        r = rows.setdefault(k, {"key_name": key, "where_seen": where, "status": status,
                                "claimed_by": claimed_by, "nodes": 0, "files": set(),
                                "example_path": path})
        r["nodes"] += 1
        r["files"].add(path)
        # REGISTERED WINS over observed-unregistered for the same key in the same place: one key
        # can carry several kinds (`register:` has four value shapes), and a single unclaimed
        # instance must not make the whole key read as unregistered.
        if status == "registered" and r["status"] != "registered":
            r["status"], r["claimed_by"] = status, claimed_by

    # ── the two buckets the walk can see, taken from the coverage table it already produced
    by_key: dict[str, str] = {}
    for name, kind in kinds.items():
        kp = str(kind.get("key_pattern") or "")
        if kp and kp != "*":
            by_key.setdefault(_leaf(kp), name)
    idx = idx if idx is not None else resolve(bundle, kinds)
    for c in idx.coverage:
        add(c["key_name"], Path(c["path"]).suffix or "<none>",
            "registered" if c.get("matched_kind") and not str(c["matched_kind"]).startswith(
                ("out-of-scope", "carved-out")) else "observed_unregistered",
            c.get("matched_kind") if c.get("matched_kind") else None, c["path"])
    for r in idx.refs:
        # FOR A map_key CARRIER THE KEY IS DATA, NOT A KIND. `grounding.sources[0].columns.brand`
        # has leaf `brand`, a column name — so taking the leaf counted 47 COLUMN NAMES as 47
        # distinct pointer types and the catalogue grew from 78 to 125 the moment the carrier was
        # read. The unit of this census is the pointer KIND, so a map_key row is counted under the
        # pattern it was declared with, once.
        k = kinds.get(r.reference_kind) or {}
        key = (str(k.get("key_pattern")) if k.get("carrier") == "map_key"
               else _leaf(r.src_locator))
        add(key, Path(r.src_path).suffix or "<none>", "registered", r.reference_kind, r.src_path)

    # ── the bucket nothing could see: file types no object kind's glob opens
    # WHICH EXTENSIONS ARE OPENED IS DERIVED FROM THE DECLARED GLOBS, not listed here — a kind
    # registered tomorrow for `*.toml` must move this boundary without an edit in this function.
    opened = {".yaml", ".yml", ".mac"}
    globs: set[str] = set()
    for kind in kinds.values():
        for ok2 in (kind.get("_object_kinds") or {}).values():
            fg = (ok2 or {}).get("file_glob")
            for g in ([fg] if isinstance(fg, str) else list(fg or [])):
                m = _re.search(r"\.[A-Za-z0-9]+$", g or "")
                if m:
                    globs.add(m.group(0))
    opened |= globs
    for f in file_population(bundle):
        suf = Path(f).suffix
        if suf in opened or suf not in {".json"}:
            continue
        try:
            doc = _json.loads((bundle / f).read_text(encoding="utf-8"))
        except Exception:                                          # noqa: BLE001
            continue
        for locator, value in walk(doc):
            if isinstance(value, str) and _is_pointer_shaped(locator, value):
                add(_leaf(locator), suf, "unopened_filetype", None, f)

    # THE FOURTH BUCKET: framework tokens the bundle has placed beyond the framework's reach. Not
    # a debt (nobody owes a row for them) and not covered (nothing checks them) — a third thing,
    # and it has to be sayable or dropping the plane is a silent loss.
    for e in (idx.oos_pointers if idx is not None else []):
        add(_leaf(e["locator"]), Path(e["path"]).suffix or "<none>",
            "in_out_of_scope_file", None, e["path"])

    out = []
    for r in rows.values():
        r = dict(r)
        r["files"] = len(r["files"])
        out.append(r)
    return sorted(out, key=lambda r: (r["status"] != "observed_unregistered",
                                      r["status"] != "unopened_filetype", -r["nodes"]))


def carved_out(path: Path = REGISTRY) -> list[dict]:
    """Planes the registry tracked and deliberately stopped tracking, each naming its replacement.

    A CARVE-OUT IS A THIRD STATE. `out-of-scope` is the bundle's ruling, `uncovered` is a debt,
    and this is neither: the registry could cover it and something else covers it better. Without
    a declaration the three collapse into one, and a deliberate decision becomes indistinguishable
    from an oversight six months later -- which is the failure mode this whole registry exists to
    end, applied to itself.

    REFUSES AN ENTRY THAT CANNOT BE ACTED ON. `path` and `covered_by` are the minimum: a carve-out
    that does not name what covers the plane instead is just a deletion with prose attached.
    """
    doc = load_yaml(path) or {}
    out: list[dict] = []
    for e in (doc.get("carved_out") or []):
        if not isinstance(e, dict):
            raise ValueError(f"{path.name}#carved_out entries must be maps, got {type(e).__name__}")
        missing = [f for f in ("path", "covered_by", "reason") if not str(e.get(f) or "").strip()]
        if missing:
            raise ValueError(f"{path.name}#carved_out[{e.get('path')!r}] is missing {missing}")
        out.append(e)
    return out


def out_of_scope_globs(bundle: Path) -> list[str]:
    """The paths THE BUNDLE ITSELF declares outside framework scope.

    READ, NEVER RESTATED. `mac.project.yaml#conformance.out_of_scope` already names them with a
    reason each — on contoso5 that is the test corpus, by an operator ruling the manifest quotes:
    "corpus testing is outside the framework, because MAC defines the ontology and not the
    questions asked of it". Writing a second list here would be a second home for that ruling, and
    the first thing to go stale when the bundle's own list changes.

    A node under one of these paths is not UNCOVERED, it is OUT OF SCOPE — which is a different
    fact and must not inflate the number that measures how far the registry has to go.
    """
    proj = bundle / "mac.project.yaml"
    if not proj.is_file():
        return []
    try:
        doc = load_yaml(proj) or {}
    except Exception:                                              # noqa: BLE001
        return []
    out = []
    for e in ((doc.get("conformance") or {}).get("out_of_scope") or []):
        if isinstance(e, dict) and isinstance(e.get("path"), str):
            out.append(e["path"])
        elif isinstance(e, str):
            out.append(e)
    return out


def load_lineage_spec(path: Path = REGISTRY) -> dict:
    """The declared lineage mapping: the artifact, its shape, and the two closed vocabularies that
    join its node ids to object ids and give its edges a direction."""
    return (load_yaml(path) or {}).get("lineage") or {}


def load_registry(path: Path = REGISTRY) -> dict[str, dict]:
    doc = load_yaml(catalogue_or_refuse(path))
    kinds = {k["reference_kind"]: k for k in doc["pointer_kinds"]}
    object_kinds = doc.get("object_kinds") or {}
    for k in kinds.values():
        k["_object_kinds"] = object_kinds
    for name, k in kinds.items():
        if k["carrier"] not in CLOSED_CARRIERS:            # closed set, no silent default
            raise SystemExit(f"pointer_index: kind {name} has carrier "
                             f"{k['carrier']!r}, not in {sorted(CLOSED_CARRIERS)}")
    return kinds


def walk(node: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar, with its structural locator. Aliases are already resolved by safe_load."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, node


def _doc_of(path: Path) -> Any:
    try:
        return load_yaml(path)
    except Exception:                                              # noqa: BLE001
        return None


def _producer_of(path: Path, doc: Any) -> str | None:
    """Who wrote this file, by its OWN declaration — a top-level or metadata `generated_by`, else
    a `GENERATED by <tool>` header comment. Never guessed from the filename."""
    if isinstance(doc, dict):
        for key in ("generated_by",):
            v = doc.get(key)
            if isinstance(v, str):
                return v
        meta = doc.get("metadata")
        if isinstance(meta, dict) and isinstance(meta.get("generated_by"), str):
            return meta["generated_by"]
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
    except Exception:                                       # noqa: BLE001
        return None
    m = GENERATED_COMMENT.search(head)
    return m.group(1) if m else None


def _leaf(locator: str) -> str:
    return locator.rsplit(".", 1)[-1].split("[")[0]


def _matches(kind: dict, locator: str, value: Any, rel: str = "",
             object_kinds: dict | None = None) -> bool:
    """Does this registry row claim this node?

    THREE things must agree, and the third was a measured bug in this file's first version: the
    key pattern, the value shape, AND the src_kind's home layer. Without the layer, a register
    descriptor's own `register.csv` matched BOTH register_pointer_path (leaf `csv`) and
    register_self_declaration, double-counting 17 pointers — an inflated denominator in the one
    design whose whole argument is that denominators must be honest.

    Key-pattern plus value-shape together are what let ONE key (`register:`) carry four
    incompatible meanings without the resolver mistaking a vocabulary token for a dangling path.
    """
    # VALUE SUFFIX — the discriminator that lets two forms of ONE binding coexist while the estate
    # migrates between them. `register:` may name the register's .csv (the artifact) or its
    # .lookup.yaml (the declaration); both are `value_shape: path` with `resolver: by_path`, so
    # nothing else in either row can tell them apart and BOTH claimed every node. The gate caught
    # it immediately — "5 ambiguous node(s): the registry claims one node from two rows" — which is
    # the finding this registry rates above every count it produces.
    #
    # BOTH rows declare a suffix, rather than one row carrying the exception: mutually exclusive by
    # construction beats mutually exclusive by the absence of a field somewhere else.
    _suf = kind.get("value_suffix")
    if _suf and not (isinstance(value, str) and value.endswith(str(_suf))):
        return False
    if kind["src_kind"] == "*":
        # CARRIER-AGNOSTIC BY DECLARATION. Every other row is scoped to its src_kind's population,
        # because a key alone does not say what wrote it. A framework term is different: the VALUE
        # identifies itself (`mac.<ns>.<term>` is one shape and nothing else looks like it), so
        # scoping it to a carrier would mean one row per plane for a single fact — the row-per-
        # carrier duplication the spike measured at 86% of the remaining gap.
        pass
    elif object_kinds is not None and rel:
        layer = (object_kinds.get(kind["src_kind"]) or {}).get("home_layer")
        spec = object_kinds.get(kind["src_kind"]) or {}
        glob = spec.get("enumerate")
        if glob and layer not in ("", "."):
            # A KIND'S POPULATION IS ITS `enumerate` GLOB, NOT ITS DIRECTORY. `edge` is homed at
            # `ontology` and enumerated from `edges.yaml`, but `ontology/` also contains
            # `concepts/` — so directory-scoping let edge rows claim all 17 concept files and
            # built 55 `edge` objects where edges.yaml holds 38. Fourth instance of one class in
            # this module: a scope that defaults open. Where a kind declares the glob that IS its
            # population, a reference can only be carried by a file inside it.
            from fnmatch import fnmatch
            if not fnmatch(rel, f"{layer.rstrip('/')}/{glob}"):
                return False
        if layer in ("", "."):
            # THE BUNDLE ROOT MEANS THE ROOT, NOT EVERYWHERE. An empty home_layer is falsy, so
            # the first version skipped the scope check entirely for root-homed kinds: the
            # resource manifest's `path` row claimed 119 pointers where the manifest holds 66,
            # silently annexing every other `path:` key in the bundle. An inflated denominator
            # again, from the same root cause as the first one -- a scope that defaults to open.
            if "/" in rel:
                return False
        elif layer and not rel.startswith(layer.rstrip("/") + "/"):
            return False
    pat, shape = kind["key_pattern"], kind["value_shape"]
    if pat != "*":
        if "[]" in pat:
            # AN INDEXED PATTERN PINS THE PARENT, not just the leaf. `resources[].path` must match
            # `resources[12].path` and NOT `bom.phases.ontology.absent[0].path` -- both end in
            # `.path` inside the same file, and only one is a pointer. The root-scoping lesson
            # again, one level finer: a pattern that pins only the leaf defaults to open.
            rx = "^" + re.escape(pat).replace(r"\[\]", r"\[\d+\]") + "$"
            if not re.match(rx, locator):
                return False
        elif "." in pat:
            if not locator.endswith(pat):
                return False
        elif _leaf(locator) not in pat.split("|"):
            return False
    if not isinstance(value, str):
        return False
    if shape == "path":
        # A GLOB IS NOT A PATH, AND NEITHER IS A TEMPLATE. `conformance.out_of_scope[].path`
        # carries `acceptance/oracle/**`, and `bom.phases.*.absent[].path` carries
        # `ontology/concepts/rules/{rule}.yaml` -- a PLACEHOLDER. Both sit on the same key as real
        # paths. Reporting either as a missing file is the same class of error as reading a
        # vocabulary token as a path, which this resolver has now made three times: a value shape
        # that does not discriminate claims what it should not.
        return "/" in value and "*" not in value and "{" not in value
    if shape == "anchored_path":
        head = value.split("#", 1)[0].split(" (", 1)[0].strip()
        return "#" in value and "/" in head
    if shape == "glob":
        return "*" in value
    if shape == "path_or_glob":
        # `planes_empty` carries BOTH forms -- ontology/concepts/**/*.yaml and ontology/rules.yaml.
        # Scoping this row to `glob` silently dropped 2 of its 3 entries, so the one declaration
        # that is measurably FALSE was two-thirds unchecked.
        return "/" in value
    if shape == "framework_term":
        # `mac.<namespace>.<term>` — the namespace may be dotted (mac.concept.column.role.key).
        # NOT a contract id (`mac.references/1`, which carries a version after a slash) and NOT a
        # framework file (`mac.schema.json`). Three shapes share the `mac.` prefix and only one is
        # a vocabulary term; resolving the other two against a vocabulary would report a correct
        # declaration as unknown, which is this reader's third vocabulary mistake avoided rather
        # than made.
        # CASE DOES NOT DECIDE MEMBERSHIP, and requiring lowercase here was a hole rather than a
        # tightening. Measured by a differential against check_references: break
        # `mac.concept.axis.time` to `...NOPE_time` and the count went 196 -> 195 — the
        # value did not become DANGLING, it left the population, because one capital made it stop
        # looking like a framework term. A required pointer that can be escaped by malforming it
        # is not required.
        #
        # THIS IS THE THIRD INSTANCE TODAY of one class: a value_shape so tight that it excludes
        # exactly the broken values it exists to catch (`column_name` wanted lowercase and lost 18
        # raw-plane attachments; `value_suffix: .lookup.csv` stopped claiming a near-miss typo).
        # The rule that falls out: a SHAPE decides which kind judges a value, and must be the
        # loosest expression of "this is that sort of token"; the RESOLVER decides whether it is
        # right. Shapes that encode a convention do the resolver's job badly.
        #
        # The three `mac.` shapes still part cleanly: a contract carries `/<version>`, a framework
        # FILE ends in a real extension, and everything else dotted is a vocabulary term.
        if re.fullmatch(r"mac\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", value):
            # THE EXCLUSION IS FOR FRAMEWORK *FILES*, so it lists the extensions framework
            # files actually use. `duckdb` and `sql` were in it for one build and that dropped
            # `mac.connector.duckdb` — a CONNECTOR NAME, and the very token this resolver was
            # taught this morning to answer `external` for. The clean bundle went 196 -> 195 and
            # the count was the only thing that said so.
            return value.rsplit(".", 1)[-1] not in ("json", "yaml", "yml", "md", "py")
        return False
    if shape == "framework_contract":
        return bool(re.fullmatch(r"mac\.[a-z_][a-z0-9_]*/[0-9]+", value))
    if shape == "template":
        return "{" in value and "}" in value
    if shape == "tool_id":
        # `mac_lookups.py/1`, `sdk.project.lineage_graph` — a producer's declared identity.
        return bool(re.fullmatch(r"[A-Za-z_][\w.]*\.py/\d+", value)
                    or re.fullmatch(r"[a-z_]+(?:\.[a-z_]+){1,}", value))
    if shape == "marker":
        return bool(re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", value))
    if shape == "column_name":
        # CASE IS NOT PART OF BEING A COLUMN NAME. This was `[a-z_][a-z0-9_]*`, which is true of
        # the SERVED plane (snake_case by convention) and false of the raw one: contoso5's
        # registers attach to `customer.Country`, `product.Brand`, `currencyexchange.FromCurrency`.
        # 18 of the 40 declared attachments were silently unclaimed — not dangling, not external,
        # simply never matched, because a convention of one plane had been written into the shape
        # that describes both.
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))
    if shape == "relation_name":
        # A concept names its relation BARE — `relation: dim_product`, not
        # `contoso_served.dim_product`. Without its own shape it fell through to `kind_token`
        # (no dot, no slash) and the declared concept->dataset edge matched nothing at all: 0
        # claimed against 17 measured, which read as "the ontology claims no grounding".
        return bool(re.fullmatch(r"[a-z_][a-z0-9_]*", value))
    if shape == "dotted_id":
        return bool(re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}", value))
    if shape == "concept_name":
        return bool(re.fullmatch(r"[A-Z][A-Za-z0-9]*", value))
    if shape == "schema_relation":
        return "/" not in value and re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", value) is not None
    if shape == "kind_token":
        return "/" not in value and "." not in value
    if shape == "stem":
        return "/" not in value and "." in value
    return False


def scan_population(bundle: Path, kinds: dict[str, dict],
                    carve_globs: list[str] | None = None) -> list[Path]:
    """Every file the registry's object kinds say they live in.

    THE POPULATION IS DECLARED, NOT HARDCODED, and that is a fix as much as a tidy-up: the
    framework's own referential gate restricts itself to the two declared PLANES and therefore
    indexes 92 of contoso5's 420 YAML files -- 22% -- while printing a line that reads as a total.
    Here, registering a kind widens the population automatically, and the gate prints what it saw
    over what exists.
    """
    # A CARVED-OUT PLANE IS NOT WALKED. This is the opposite of what it did until 2026-10-04,
    # and the reversal was an operator ruling, not a tidy-up: carved files were ADDED to the walk
    # here so their rows could be LABELLED rather than missing, on the argument that "the files
    # simply stop appearing, which is exactly how an oversight looks". True, and it cost 61% of a
    # build to label a plane nothing was going to judge. The operator's ruling on acceptance
    # ("does not have to be absolutely strict ... you should not even try to track acceptance
    # here") settles the trade the other way.
    #
    # THE TRACE DID NOT GO WITH IT, because that objection was right. The ruling is in the
    # registry's `carved_out`, which must name a `covered_by` to exist at all, and build.json
    # reports `carved_out_files` and `carved_out_covered_by` -- so the number of files this
    # removed and the mechanisms that judge them instead travel with every build. What is gone is
    # one row per carved file, which is what was asked for.
    object_kinds: dict = {}
    for k in kinds.values():
        object_kinds.update(k.get("_object_kinds") or {})
    seen: dict[Path, None] = {}
    for ok in object_kinds.values():
        layer = (ok or {}).get("home_layer")
        globs = (ok or {}).get("file_glob") or "*.yaml"
        if layer is None:
            continue
        base = bundle / layer if layer not in ("", ".") else bundle
        if not base.is_dir():
            continue
        # A LIST, BECAUSE A POPULATION CAN SPAN EXTENSIONS. The carrier-agnostic kinds live in
        # every declaration the bundle has, and those are not all `.yaml` — `.mac` is one too.
        for g in ([globs] if isinstance(globs, str) else list(globs)):
            it = base.glob(g) if layer in ("", ".") else base.rglob(g)
            for f in it:
                if f.is_file():
                    seen.setdefault(f, None)
    if carve_globs:
        for f in list(seen):
            if _oos_match(f.relative_to(bundle).as_posix(), list(carve_globs)):
                del seen[f]
    return sorted(seen)


def build_name_index(bundle: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Concept names and served relation names, for the two by-name resolvers.

    Concepts are addressed BY NAME in PascalCase (`validates: [CalendarDay]`) while their files are
    snake_case stems, so the index carries both, case-folded -- three casings for one target was a
    measured finding (`Brand` / `brand` / `id: brand` + `name: Brand`).
    """
    concepts: dict[str, str] = {}
    cdir = bundle / "ontology" / "concepts"
    if cdir.is_dir():
        for f in sorted(cdir.rglob("*.yaml")):
            try:
                doc = load_yaml(f) or {}
            except Exception:                               # noqa: BLE001
                continue
            rel = f.relative_to(bundle).as_posix()
            concepts[f.stem.lower().replace("_", "")] = rel
            nm = ((doc.get("concept") or {}) if isinstance(doc.get("concept"), dict) else {}).get("name")
            if isinstance(nm, str):
                concepts[nm.lower().replace("_", "")] = rel
    relations: dict[str, str] = {}
    for layer in ("datasets", "sources"):
        d = bundle / "data" / layer
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")):
            try:
                doc = load_yaml(f) or {}
            except Exception:                               # noqa: BLE001
                continue
            rel = f.relative_to(bundle).as_posix()
            relations[f.stem.lower()] = rel
            tbl = doc.get("table") if isinstance(doc.get("table"), dict) else {}
            for cand in (tbl.get("name"), (doc.get("produces") or {}).get("relation")
                         if isinstance(doc.get("produces"), dict) else None):
                if isinstance(cand, str):
                    relations[cand.lower()] = rel
                    relations[cand.split(".")[-1].lower()] = rel
    return concepts, relations


def walk_maps(node: Any, prefix: str = "") -> Iterator[tuple[str, dict]]:
    """Every MAPPING, with its structural locator — the traversal `walk` cannot do.

    `walk` yields scalars, so a pointer carried as a map KEY is invisible to it: the estate's own
    census counted 7 carriers and this module read 2. `grounding.sources[].columns` is a map whose
    KEYS are column names, which is 112 concept-to-column edges in contoso5 that no reader has
    ever seen.
    """
    if isinstance(node, dict):
        yield prefix, node
        for k, v in node.items():
            yield from walk_maps(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_maps(v, f"{prefix}[{i}]")


def _dig_locator(doc: Any, locator: str) -> Any:
    """Follow a structural locator (`grounding.sources[0]`) back into the document.

    `walk_maps` yields a locator and the node, but a map KEY's qualifier lives on a SIBLING of the
    map, so the parent has to be reachable from the locator. Returns None rather than raising on
    any mismatch — a locator that does not fit the document is not an error here, it is a node
    this kind does not claim.
    """
    cur = doc
    for part in locator.split(".") if locator else []:
        while part.endswith("]") and "[" in part:
            head, _, idx_s = part.partition("[")
            if head:
                if not isinstance(cur, dict) or head not in cur:
                    return None
                cur = cur[head]
            try:
                i = int(idx_s.rstrip("]"))
            except ValueError:
                return None
            if not isinstance(cur, list) or i >= len(cur):
                return None
            cur = cur[i]
            part = ""
        if part:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
    return cur


def _locator_matches_pattern(locator: str, pattern: str) -> bool:
    """`grounding.sources[0].columns` matches `grounding.sources[].columns`. Indices are positions,
    not identity, so a pattern names the shape and the locator names the instance."""
    return re.sub(r"\[\d+\]", "[]", locator) == pattern


def build_column_index(bundle: Path) -> dict[str, str]:
    """`<relation>.<column>` -> the descriptor that declares it.

    THE TARGET SIDE OF THE COLUMN EDGE, and the reason it is a real check rather than a
    restatement: a concept grounding on a column no descriptor declares is DANGLING, which is
    exactly what a column rename in the data plane produces. Measured when this was built: 112 of
    112 grounded columns resolve, so it refuses nothing that ships today.
    """
    out: dict[str, str] = {}
    base = bundle / "data" / "datasets"
    if not base.is_dir():
        return out
    for f in sorted(base.glob("*.yaml")):
        try:
            doc = load_yaml(f) or {}
        except Exception:                                          # noqa: BLE001
            continue
        if not isinstance(doc, dict):
            continue
        relation = ((doc.get("table") or {}) if isinstance(doc.get("table"), dict) else {}).get("name")
        if not isinstance(relation, str) or not relation:
            continue
        for c in (doc.get("columns") or []):
            if isinstance(c, dict) and isinstance(c.get("name"), str):
                out[f"{relation}.{c['name']}"] = f.relative_to(bundle).as_posix()
    return out


def lineage_refs(bundle: Path, kinds: dict[str, dict]) -> tuple[list[Ref], dict]:
    """The MEASURED data chain as references — read, never re-derived.

    `data/lineage/lineage.json` is the one home for that graph by operator ruling, and
    lineage_graph.py#OWNERSHIP declares a third producer illegal. This READS it and maps node ids
    onto names using the mapping DECLARED in mac_pointers.yaml#lineage.

    WHY IT IS HERE AND NOT IN THE LOADER. It was in the loader, which meant `resolve()` — the one
    thing a gate can call — returned ZERO for all six lineage kinds while the graph built from the
    same bundle held 42. Two readers of one bundle disagreeing by 42 edges, with nothing saying so:
    `check_pointers` printed `lineage_cuts=0` beside a graph printing 17, and a gate asking the
    resolver about the data chain got silence indistinguishable from a bundle with no lineage.

    EACH ENDPOINT CARRIES ITS OWN KIND, from `lineage.node_kinds`. A first attempt used the
    catalogue row's src_kind/dst_kind for both ends and produced four datasets that were really raw
    sources — the row describes the SHAPE of an edge, the node declares what it IS.
    """
    import json as _json                                             # noqa: PLC0415
    spec = load_lineage_spec()
    rel = spec.get("artifact") or "data/lineage/lineage.json"
    art = bundle / rel
    out: dict = {"artifact": rel, "read": False, "nodes": 0, "edges": 0,
                 "skipped_node_kinds": {}, "skipped_edge_kinds": {}, "unjoined": []}
    if not art.is_file():
        out["why"] = f"{rel} is absent — the data chain is simply not in this graph"
        return [], out
    try:
        doc = _json.loads(art.read_text(encoding="utf-8"))
    except Exception as exc:                                         # noqa: BLE001
        out["why"] = f"{rel} is unreadable: {type(exc).__name__}"
        return [], out
    want = spec.get("shape")
    if want is not None and doc.get("shape") != want:
        out["why"] = (f"shape {doc.get('shape')!r} is not the declared {want!r} — refused rather "
                      f"than interpreted, as lineage_graph.py's own loader does")
        return [], out

    nkinds = spec.get("node_kinds") or {}
    ekinds = spec.get("edge_kinds") or {}
    out["read"] = True
    out["measured"] = bool(doc.get("measured"))
    out["generated_by"] = doc.get("generated_by")

    node: dict[str, tuple[str, str]] = {}      # id -> (kind, ref)
    for n in doc.get("nodes") or []:
        nid = str(n.get("id") or "")
        prefix = nid.split(":", 1)[0] if ":" in nid else ""
        kind = nkinds.get(prefix)
        if not kind:
            out["skipped_node_kinds"][prefix or "?"] = \
                out["skipped_node_kinds"].get(prefix or "?", 0) + 1
            continue
        node[nid] = (kind, str(n.get("ref") or nid.split(":", 1)[-1]))
        out["nodes"] += 1

    gen = ", ".join(doc.get("generated_by") or []) or "unknown"
    refs: list[Ref] = []
    for i, e in enumerate(doc.get("edges") or []):
        ekind = str(e.get("kind") or "")
        rule = ekinds.get(ekind)
        name = f"lineage_{ekind}"
        if rule is None or name not in kinds:
            out["skipped_edge_kinds"][ekind or "?"] = \
                out["skipped_edge_kinds"].get(ekind or "?", 0) + 1
            continue
        a, b = node.get(str(e.get("from"))), node.get(str(e.get("to")))
        if not a or not b:
            out["unjoined"].append(f"{e.get('from')} -{ekind}-> {e.get('to')}")
            continue
        # DIRECTION APPLIED HERE from the declared `invert`, so the emitted reference already reads
        # "src depends on dst" like every other row and the loader needs no special case.
        (sk, sref), (dk, dref) = (b, a) if rule.get("invert") else (a, b)
        refs.append(Ref(name, "measured", rel, f"edges[{i}]",
                        f"{e.get('from')} -> {e.get('to')}", "resolved",
                        f"MEASURED by {gen} and read from {rel}#edges[{i}] — not re-derived here; "
                        f"{str(rule.get('what', '')).strip()}",
                        producer=gen, dst=dref, src=sref, src_kind=sk, dst_kind=dk))
        out["edges"] += 1
    return refs, out


def resolve(bundle: Path, kinds: dict[str, dict]) -> Index:
    idx = Index(kinds=kinds)
    idx.concepts, idx.relations = build_name_index(bundle)
    idx.out_of_scope = out_of_scope_globs(bundle)
    idx.carved_out = carved_out()
    idx.files_in_bundle = len(file_population(bundle))
    idx.columns = build_column_index(bundle)
    # THE MEASURED CHAIN IS PART OF THE ANSWER. Without it `resolve()` reported 0 lineage
    # references while the graph built from the same bundle held 42.
    _lin, idx.lineage = lineage_refs(bundle, kinds)
    idx.refs.extend(_lin)
    for p in scan_population(bundle, kinds, [c["path"] for c in idx.carved_out]):
        if True:
            idx.files_seen += 1
            _rel0 = p.relative_to(bundle).as_posix()
            idx.seen_paths.append(_rel0)
            try:
                doc = load_yaml(p)
            except Exception as _exc:                      # noqa: BLE001
                # UNPARSED IS NOT UNTRACKED AND NOT CLEAN. It is a file the registry CLAIMED and
                # could not read, which is the one state a census must never fold into either
                # neighbour -- it looked like "nothing to see here" in every count until now.
                idx.unparsed_paths.append({"path": _rel0, "why": _why_unparsed(_exc)})
                continue
            if not isinstance(doc, (dict, list)):
                idx.unparsed_paths.append({"path": _rel0,
                                           "why": f"parsed as {type(doc).__name__}, not a mapping "
                                                  f"or a list -- not a declaration"})
                continue
            idx.files_parsed += 1
            rel = _rel0
            idx.parsed_paths.append(rel)
            # A FILE THE BUNDLE RULES OUTSIDE FRAMEWORK SCOPE IS NOT A SOURCE OF ANYTHING.
            #
            # Operator, 2026-10-03, looking at `*/ADV-01` in the object list: "explain the
            # existance of test files ... to my knowledge we decided not to track acceptance test
            # objects or questions". They were 91 of 394 objects — 23% of the graph — and 83 of
            # those were acceptance/answers/*.yaml, the captured question corpus.
            #
            # They arrived as a side effect of a correct fix: the carrier-agnostic `*` kind was
            # given a bundle-wide population so the acceptance CARVE-OUT would not silently take
            # 312 framework-term edges with it. But the bundle's own mac.project.yaml already
            # rules `acceptance/answers/**` outside framework scope, with an operator's reason
            # attached — "Observation, not a MAC model artifact". A registry that walks those files
            # and makes dependency NODES of them is overriding a ruling the bundle carries, which
            # is not the platform's call to make.
            #
            # IT REMAINS A VALID TARGET. The manifest legitimately declares acceptance/questions.yaml
            # as a resource and `resource_declared_path` must still confirm the file exists; this
            # guard is about being a SOURCE. Five inbound edges are unaffected.
            if _oos_match(rel, idx.out_of_scope):
                for locator, value in walk(doc):
                    if isinstance(value, str) and _is_framework_shaped(value):
                        idx.oos_pointers.append({"path": rel, "locator": locator, "value": value})
                continue
            idx.producers[rel] = _producer_of(p, doc)

            # ── CARRIER: map_key. A third of the declared carriers had no reader at all, and
            # this is the one that carries the data plane's finest grain. Kept to kinds that
            # DECLARE `carrier: map_key` so no existing row changes behaviour.
            for name, kind in kinds.items():
                if kind.get("carrier") != "map_key":
                    continue
                layer = (kind.get("_object_kinds", {}).get(kind["src_kind"]) or {}
                         ).get("home_layer")
                if layer and not rel.startswith(layer.rstrip("/") + "/"):
                    continue
                for maploc, node in walk_maps(doc):
                    if not _locator_matches_pattern(maploc, str(kind.get("key_pattern") or "")):
                        continue
                    # A MAP KEY IS LOCALLY UNIQUE AT BEST, so the kind declares which SIBLING key
                    # makes it global — `relation` here, giving `dim_store.store_key`. Without it
                    # every `store_key` in the estate would be one node.
                    sib = kind.get("qualify_sibling")
                    qual = None
                    if sib:
                        parent_loc = maploc.rsplit(".", 1)[0]
                        parent = _dig_locator(doc, parent_loc)
                        qual = (parent or {}).get(sib) if isinstance(parent, dict) else None
                        if not isinstance(qual, str) or not qual:
                            continue
                    for key in node:
                        if not isinstance(key, str) or not key:
                            continue
                        full = f"{qual}.{key}" if qual else key
                        idx.refs.append(_judge(bundle, name, kind, rel,
                                               f"{maploc}.{key}", full, idx))

            for locator, value in walk(doc):
                if not isinstance(value, str):
                    continue

                claimants = [
                    (name, kind) for name, kind in kinds.items()
                    if kind["carrier"] == "value"
                    and _matches(kind, locator, value, rel, kind.get("_object_kinds"))
                ]
                claimed = bool(claimants)
                if len(claimants) > 1:
                    # THE REGISTRY MUST BE UNAMBIGUOUS. Two rows claiming one node means the
                    # count is wrong in a way no verdict would reveal, so it is a finding of its
                    # own rather than a silent first-match-wins.
                    idx.ambiguous.append({
                        "path": rel, "locator": locator, "value": value[:80],
                        "kinds": sorted(n for n, _ in claimants),
                    })
                for name, kind in claimants[:1]:
                    # A VALUE CAN BE LOCALLY UNIQUE TOO. `attached[0].column: brand` names a
                    # column, and `brand` alone is ambiguous across relations exactly as a map key
                    # is — the qualifier sits on a SIBLING (`attached[0].relation`). Same declared
                    # field as the map_key pass so there is one rule, not two: a kind says which
                    # sibling makes its value global and both carriers obey it.
                    v = value
                    sib = kind.get("qualify_sibling")
                    if sib:
                        parent = _dig_locator(doc, locator.rsplit(".", 1)[0])
                        q = (parent or {}).get(sib) if isinstance(parent, dict) else None
                        if not isinstance(q, str) or not q:
                            continue
                        v = f"{q}.{value}"
                    ref = _judge(bundle, name, kind, rel, locator, v, idx)
                    ref.producer = idx.producers.get(rel)
                    idx.refs.append(ref)

                # carrier: prose — a backticked path inside any string scalar
                for m in PROSE_PATH.finditer(value):
                    target = m.group(1)
                    if not target.startswith("data/lookups/"):
                        continue
                    for name, kind in kinds.items():
                        if kind["carrier"] != "prose":
                            continue
                        layer = (kind.get("_object_kinds", {}).get(kind["src_kind"]) or {}
                                 ).get("home_layer")
                        if layer and not rel.startswith(layer.rstrip("/") + "/"):
                            continue
                        claimed = True
                        idx.refs.append(_judge(bundle, name, kind, rel, locator, target, idx))

                if _is_pointer_shaped(locator, value) and not claimed:
                    # OUT OF SCOPE IS NOT UNCOVERED. Recorded with the bundle's own ruling as the
                    # matched_kind, so the row is still enumerated — the population never shrinks
                    # silently — while the uncovered COUNT measures only what the registry still
                    # owes.
                    # THE BUNDLE'S RULING OUTRANKS THE REGISTRY'S. Where the bundle has already
                    # placed a path outside framework scope, that is the more accurate statement
                    # and relabelling it `carved-out` would overwrite an operator ruling with a
                    # platform decision. The carve-out speaks only where the bundle is silent.
                    oos = _oos_match(rel, idx.out_of_scope)
                    carve = None if oos else _oos_match(rel, [c["path"] for c in idx.carved_out])
                    if oos:
                        label = f"out-of-scope: {oos}"
                    elif carve:
                        by = next(c["covered_by"] for c in idx.carved_out if c["path"] == carve)
                        label = f"carved-out: {carve} -> {by}"
                    else:
                        label = None
                    idx.coverage.append({
                        "path": rel, "locator": locator, "carrier": "value",
                        "key_name": _leaf(locator), "value_excerpt": value[:90],
                        "matched_kind": label,
                    })
    return idx


#: The wide walk: deliberately broader than the registry, so the blindness is a row not a silence.
POINTER_LEXICON = {
    "ref", "register", "register_file", "csv", "realized_by", "binds", "source", "relation",
    "table", "produces", "consumes", "depends_on", "over", "verified_by", "enforced_by",
    "validated_against", "superseded_by", "sql_file", "value_domain", "resolved_by", "descriptor",
    "source_view", "run_record", "generated_by", "raised_by", "target", "database", "glob",
}


def _oos_match(rel: str, globs: list) -> str | None:
    from fnmatch import fnmatch
    for g in globs:
        pat = g[:-1] + "*" if g.endswith("**") else g
        if fnmatch(rel, pat) or fnmatch(rel, pat.rstrip("*") + "*"):
            return g
    return None


def _is_framework_shaped(value: str) -> bool:
    """A `mac.<namespace>.<term>` or `mac.<name>/<version>` token.

    WHY THESE ARE STILL COLLECTED from files that are otherwise skipped: 7 of the 8 framework terms
    used in contoso5's acceptance corpus are used NOWHERE ELSE in the bundle. Dropping the plane
    without a word would mean a term retired in MAC breaks those files and nothing anywhere says
    so. They are not resolved and not made into edges — they are LISTED, as "used only where the
    bundle has ruled the framework out", which is a true sentence and a reader can act on it.
    """
    return bool(re.match(r"^mac\.[A-Za-z0-9_]+[./][A-Za-z0-9_.\-]+$", value))


def _is_pointer_shaped(locator: str, value: str) -> bool:
    if _leaf(locator) in POINTER_LEXICON:
        return True
    return bool(re.search(r"\.(?:csv|sql|yaml|yml|json|py|duckdb|md)$", value))




def framework_rule_ids() -> tuple[set[str], str]:
    """Fully-qualified rule ids from `mac_rules.yaml`.

    THE FRAMEWORK'S TERM SPACE HAS TWO HOMES, and a reader that knows only one reports the other
    as unknown. `mac_vocabulary.yaml` holds NAMESPACED GROUPS whose terms are bare
    (`canon` -> `ratio_select`, written `mac.canon.ratio_select`); `mac_rules.yaml` holds RULE IDS
    already fully qualified (`mac.guarantee.never_guess`). Measured on contoso5: 116 of 311
    framework-term references — every `mac.aggregate.*`, `mac.resolve.*` and `mac.guarantee.*` —
    resolve against the second home and nothing at all against the first.
    """
    root = framework_root()
    if root is None:
        return set(), "framework unreachable"
    f = root / "mac_rules.yaml"
    if not f.is_file():
        return set(), "mac_rules.yaml absent"
    try:
        doc = load_yaml(f) or {}
    except Exception as exc:                                       # noqa: BLE001
        return set(), f"mac_rules.yaml unreadable: {exc}"
    ids = set()
    def walk(n):
        if isinstance(n, dict):
            v = n.get("id")
            if isinstance(v, str) and v.startswith("mac."):
                ids.add(v)
            for x in n.values():
                walk(x)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(doc)
    return ids, f"mac_rules.yaml ({len(ids)} rule id(s))"


#: The third answer from framework_terms -- a group that registers a namespace and no members.
#: A distinct object rather than None or an empty set, both of which already mean something else
#: ("unreadable" and "a closed set that happens to be empty").
NAMESPACE_ONLY = object()


def _vocab_block(doc: Any, group: str) -> Any:
    """The vocabulary block at `group`, under EITHER addressing the framework has used.

    `mac_vocabulary.yaml` was FOLDED on 2026-10-04 from flat dotted keys (`concept.axis:`)
    into a nested tree (`concept:` -> `axis:`), 25 top-level keys down to 17. The block
    SHAPE did not change at all -- only its address did. This reader looked the group up as a
    flat key, found nothing, and reported 77 correct references as dangling, which is "renames
    break readers silently" from the other side: the fold had no way to know this reader existed,
    and nothing connected the two.

    BOTH addressings are accepted, and not out of indecision -- this is the only cross-repo
    pointer in the registry, so a bundle may legitimately be held against an older framework
    checkout, and a reader that understands only today's shape turns that into 77 false reds.
    The flat key is tried FIRST because it is unambiguous: a dotted key, where one exists, IS the
    group, whereas a walk could in principle land on a nested block that merely shares the name.
    """
    if isinstance(doc, dict) and isinstance(doc.get(group), dict):
        return doc[group]
    node: Any = doc
    for seg in group.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(seg)
    return node


def framework_terms(arg: str) -> tuple[set[str] | None, str]:
    """The closed term set a framework vocabulary group declares.

    `arg` is '<file>#<group>'. THREE ANSWERS, not two, because the vocabulary has three states:

      (set,  basis)  the group declares a closed term set -- compare against it
      (None, basis)  the vocabulary could not be READ, or declares no such group at all
      (NAMESPACE_ONLY, basis)
                     the group EXISTS and deliberately declares no members

    The third was found by this reader calling a correct declaration dangling. `mac_vocabulary.yaml`
    registers `connector:` with `kind: registry`, `closed: false` and no `terms` map, and says so in
    its own words -- "This block registers the NAMESPACE ONLY. It lists NO members: which
    first-party connectors exist is a fact about the MAC DISTRIBUTION, not about meaning, and lives
    in the shipped index (sdk/connector/index.json)". So `mac.connector.duckdb` in
    mac.project.yaml#runtime.connector is a VALID framework reference, and reporting it as a term
    that "moved or was retired" is this reader reading the vocabulary wrongly for the third time --
    the same shape as the two mistakes already recorded above and below.

    It is machine-detectable and not guessed: `connector` is the ONLY group in the file with no
    member container, so the rule is read from the vocabulary rather than special-cased on a name.

    THE GAP THIS LEAVES, STATED RATHER THAN PAPERED OVER. The member list exists -- in
    sdk/connector/index.json -- and the vocabulary names that path in PROSE only. So the typo the
    vocabulary itself says it exists to catch (`mac.connector.athna`) cannot be caught from here
    without hardcoding a path that is the framework's to declare. Closing it is one line in
    mac_vocabulary.yaml (a machine-readable `members_from:`), which is a framework change and
    therefore gated on explicit permission. Until then these resolve `external`: the framework owns
    the namespace, the membership is outside the vocabulary, and the registry says which.
    """
    vocab_file, _, group = arg.partition("#")
    root = framework_root()
    if root is None:
        return None, ("framework vocabulary unreachable: meaning_as_code is not importable and "
                      "MEANING_AS_CODE is unset, so this kind cannot be judged")
    vf = root / vocab_file
    if not vf.is_file():
        return None, f"framework vocabulary unreachable: {vf} does not exist"
    try:
        doc = load_yaml(vf) or {}
    except Exception as exc:                                # noqa: BLE001
        return None, f"framework vocabulary unreadable: {vocab_file} -- {exc}"
    block = _vocab_block(doc, group)
    if isinstance(block, dict) and not isinstance(block.get("terms"), dict) \
            and not block.get("closed"):
        return NAMESPACE_ONLY, (
            f"{vocab_file}#{group} registers the NAMESPACE and declares no members "
            f"(kind: {block.get('kind')!r}, closed: false) -- membership is a fact the framework "
            f"keeps outside its vocabulary, so a `mac.{group}.*` id is a framework reference this "
            f"registry can confirm the namespace of but not the member of")
    if not isinstance(block, dict) or not isinstance(block.get("terms"), dict):
        return None, (f"framework vocabulary {vocab_file} has no group {group!r} with terms "
                      f"(it declares {len(doc)} group(s))")
    closed = " (closed)" if block.get("closed") else ""
    # BOTH SPELLINGS. A vocabulary declares BARE terms (`population_select`); a declaration may
    # write the QUALIFIED form the framework's own term grammar uses (`mac.canon.population_select`,
    # i.e. mac.<namespace>.<term>). Comparing the written value against bare terms alone reported
    # all six machine-executable rule bodies in contoso5 as dangling — correct declarations, read
    # wrongly, which is this reader's second vocabulary mistake and the same shape as the first:
    # the vocabulary existed and I compared against the wrong spelling of it.
    bare = set(block["terms"])
    qualified = {f"mac.{group}.{term}" for term in bare}
    return bare | qualified, (f"by_dotted_term against {vocab_file}#{group}{closed}, accepting "
                              f"the bare term or the qualified mac.{group}.<term> form")


def _common_prefix(a: str, b: str) -> str:
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[:i]


def _judge(bundle: Path, name: str, kind: dict, rel: str, locator: str, value: str,
           idx: "Index | None" = None) -> Ref:
    """Resolve one pointer, and carry the basis that judged it — a resolution with no basis is
    not readable (the estate's own admission-block pattern)."""
    resolver = kind["resolver"]
    if resolver == "by_path":
        if (bundle / value).is_file():
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_path found {value}", dst=value)
        # NEAR-MISS CANDIDATES, RANKED — because naming the successor IS the deliverable. An
        # unranked list sorted alphabetically surfaced the .md and .yaml siblings and truncated
        # away the renamed .csv, which is the only candidate a repoint can use. Same extension
        # first, then by shared prefix length.
        target = Path(value)
        ext = target.suffix
        pref = target.name.split(".")[0]
        # THE TEST IS PREFIX CONTAINMENT, NOT A SHARED-CHARACTER COUNT. A rename adds or removes
        # a suffix, so a candidate qualifies when one prefix extends the other. A character
        # threshold cannot express that: every contoso5_* register shares a 9-char family prefix,
        # so "contoso5_color" would be offered as the successor to "contoso5_brand".
        cands = []
        for q in (bundle / target.parent).glob("*"):
            if not q.is_file() or q.name == target.name:
                continue
            qpref = q.name.split(".")[0]
            if len(qpref) < 3 or not (qpref.startswith(pref) or pref.startswith(qpref)):
                continue
            cands.append((0 if q.suffix == ext else 1,
                          -len(_common_prefix(qpref, pref)),
                          q.relative_to(bundle).as_posix()))
        cands.sort()
        basis = f"by_path found no {value}"
        if cands:
            best = [c[2] for c in cands]
            same_ext = sum(1 for c in cands if c[0] == 0)
            basis += (f"; {len(cands)} near-miss candidate(s), {same_ext} with the same "
                      f"extension: {', '.join(best[:2])}")
        return Ref(name, kind["carrier"], rel, locator, value, "dangling", basis)

    if resolver == "by_dotted_term":
        terms, basis = framework_terms(kind.get("resolver_arg") or "")
        if terms is None:
            # "I COULD NOT FIND THE VOCABULARY" IS NOT "THE VOCABULARY DOES NOT EXIST", and
            # conflating the two is how this resolver's first version produced five false
            # positives and called a correctly-authored bundle undeclared. Unresolvable-by-the-
            # tool is its own state, and it must never read as a finding against the subject.
            return Ref(name, kind["carrier"], rel, locator, value, "uncovered_kind", basis)
        if value in terms:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"{basis}; {value!r} is one of {len(terms)} closed term(s)", dst=value)
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"{basis}; {value!r} is NOT among the {len(terms)} closed term(s): "
                   f"{', '.join(sorted(terms))}")

    if resolver == "by_anchor":
        # `source: data/profiles/dim_date.yaml#profile (measured 2026-09-29T13:18:26+02:00)`
        # -- a path, an anchor and a parenthetical stamp in ONE scalar. Resolve the file; the
        # anchor is reported but not yet walked, and the basis says so rather than implying it was.
        head = value.split("#", 1)[0].split(" (", 1)[0].strip()
        anchor = value.split("#", 1)[1].split(" (", 1)[0].strip() if "#" in value else ""
        if (bundle / head).is_file():
            # THE ANCHOR IS WALKED NOW, and until 2026-10-04 it was not: this resolver confirmed
            # the FILE and said so in its basis ("anchor NOT verified by this prototype"). An
            # honest limit, but a limit — and the differential against check_references found
            # exactly what it cost: break the anchor and leave the file alone, and
            # check_references caught it while this missed it. A gate cannot replace one that
            # catches something it does not.
            #
            # AN ANCHOR NAMES A RECORD IN THE TARGET, and the shape varies by artifact: a top-level
            # key in a profile, a nested key, or — in evidence/edge_measurements.json, 37 of the 60
            # anchored paths in contoso5 — the value of the `edge` field of one of 37 result
            # records. So the test is PRESENCE at any depth, as a key or as a string value.
            #
            # WHAT IT STILL DOES NOT CHECK, said rather than implied: that the anchor names the
            # right KIND of record. Presence is what makes a rename or a deletion a finding, which
            # is the staleness class this exists for.
            doc = _doc_of(bundle / head)
            if doc is None and (bundle / head).suffix == ".json":
                try:
                    import json as _json                            # noqa: PLC0415
                    doc = _json.loads((bundle / head).read_text(encoding="utf-8"))
                except Exception:                                   # noqa: BLE001
                    doc = None
            if not anchor:
                return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                           f"by_anchor: {head} exists and the value names no anchor", dst=head)
            if doc is None:
                return Ref(name, kind["carrier"], rel, locator, value, "uncovered_kind",
                           f"by_anchor: {head} exists but could not be read, so anchor "
                           f"{anchor!r} cannot be judged — not a finding about the bundle")

            def _present(node, target: str) -> bool:
                """`target` named anywhere under `node` — as a key, or as a string value."""
                if isinstance(node, dict):
                    if target in node:
                        return True
                    return any(_present(v, target) for v in node.values())
                if isinstance(node, list):
                    return any(_present(v, target) for v in node)
                return isinstance(node, str) and node == target

            def _walk_dotted(node, parts: list[str]):
                for part in parts:
                    if not isinstance(node, dict) or part not in node:
                        return None
                    node = node[part]
                return node

            def _holds(doc_) -> bool:
                # TWO ANCHOR FORMS, and the first cut only knew one. A FLAT name identifies a
                # record outright (`...json#product__sold_under__brand`, the value of `edge` on one
                # of 37 result rows). A DOTTED one is a locator plus an identity:
                # `...order.yaml#contract.rules.order.resolution.rate_on_order_date` is the rule
                # whose id is `order.resolution.rate_on_order_date`, inside `contract.rules` — and
                # the id itself contains dots, so the split point cannot be guessed from the string.
                # Reporting those 4 as dangling was this check being wrong, not the bundle.
                if _present(doc_, anchor):
                    return True
                parts = anchor.split(".")
                for i in range(len(parts) - 1, 0, -1):
                    node = _walk_dotted(doc_, parts[:i])
                    if node is not None and _present(node, ".".join(parts[i:])):
                        return True
                return False

            if _holds(doc):
                return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                           f"by_anchor: {head} declares {anchor!r}", dst=head)
            return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                       f"by_anchor: {head} exists but declares no {anchor!r} — the file is there "
                       f"and the record it was pointed at is not")
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"by_anchor: {head} does not exist, so anchor {anchor!r} cannot resolve")

    if resolver == "by_concept_name":
        key = value.lower().replace("_", "")
        hit = (idx.concepts if idx else {}).get(key)
        if hit:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_concept_name: {value} -> {hit}", dst=hit)
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"by_concept_name: no concept named {value!r} among "
                   f"{len(set((idx.concepts if idx else {}).values()))} concept file(s)")

    if resolver == "by_relation_name":
        hit = (idx.relations if idx else {}).get(value.lower()) or \
              (idx.relations if idx else {}).get(value.split(".")[-1].lower())
        if hit:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_relation_name: {value} -> {hit}", dst=hit)
        return Ref(name, kind["carrier"], rel, locator, value, "external",
                   f"by_relation_name: {value!r} is described by no dataset/source descriptor "
                   f"in this bundle -- a RAW relation the bundle does not own, not a break")

    if resolver == "by_glob_empty":
        # AN ASSERTION, NOT A POINTER: the declaration claims the glob matches NOTHING.
        # contoso5.mac#planes_empty says three ontology paths are empty; two are not.
        hits = [q.relative_to(bundle).as_posix()
                for q in bundle.glob(value) if q.is_file()]
        if not hits:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_glob_empty: {value} matches 0 file(s), as asserted", dst=None)
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"by_glob_empty: the declaration asserts {value} is EMPTY, but it matches "
                   f"{len(hits)} file(s) -- e.g. {', '.join(sorted(hits)[:2])}")

    if resolver == "by_framework_term":
        # THE ONLY CROSS-REPO POINTER IN THIS REGISTRY. A bundle declaration depends on a CLOSED
        # VOCABULARY that lives in meaning-as-code and changes on ITS release cycle, so a term
        # retired or renamed there breaks every bundle that used it — and nothing in the estate
        # connects the two today. The value names its own namespace, which is why this kind needs
        # no resolver_arg and one row covers every carrier.
        body = value[len("mac."):]
        ns, _, term = body.rpartition(".")
        terms, basis = framework_terms(f"mac_vocabulary.yaml#{ns}")
        if terms is NAMESPACE_ONLY:
            # EXTERNAL, which is already in the closed resolution vocabulary and means exactly
            # this: a target the registry does not own and cannot resolve further. NOT `resolved`
            # -- that would claim the member was checked, and it was not.
            return Ref(name, kind["carrier"], rel, locator, value, "external", basis)
        if terms is None:
            # SECOND HOME before giving up: a fully-qualified RULE ID from mac_rules.yaml. Treating
            # "not in the vocabulary" as the whole answer reported 116 correct references as
            # unjudgeable — the same shape as this reader's two earlier vocabulary mistakes, which
            # is why the fallback is tried before any verdict is returned.
            rule_ids, rbasis = framework_rule_ids()
            if value in rule_ids:
                return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                           f"by_framework_term: {value} is a framework RULE id, from {rbasis}",
                           dst=value)
            if rule_ids:
                return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                           f"{basis}; and not a rule id in {rbasis} either — the framework "
                           f"declares this term in neither of its two homes")
            # Unreachable is NOT "the bundle is wrong" — the conflation that produced five false
            # positives the first time a vocabulary was read here.
            return Ref(name, kind["carrier"], rel, locator, value, "uncovered_kind", basis)
        if value in terms or term in terms:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"{basis}; {term!r} is one of {len(terms)} closed term(s)", dst=value)
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"{basis}; {term!r} is NOT among the closed term(s) of mac_vocabulary.yaml#{ns}"
                   f" — a framework term that moved or was retired: "
                   f"{', '.join(sorted(x for x in terms if '.' not in x))}")

    if resolver == "by_id":
        # THE TARGET IS NAMED, NOT LOCATED. A producer id (`mac_lookups.py/1`) or a bundle marker
        # identifies something that is not a file in this bundle — the framework's tool, or the
        # bundle itself. Declared for the lineage kinds since they were added and never reached
        # until now, because lineage edges are injected directly rather than judged.
        return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                   f"by_id: {value!r} taken as the identity it declares", dst=value)

    if resolver == "by_glob_nonempty":
        # THE INVERSE OF by_glob_empty: a manifest glob claims a population EXISTS. One matching
        # nothing is a promise to a consumer that cannot be kept, exactly as a dangling path is.
        hits = [q for q in bundle.glob(value) if q.is_file()]
        if hits:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_glob_nonempty: {value} matches {len(hits)} file(s)", dst=None)
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"by_glob_nonempty: {value} matches NOTHING — the manifest claims a population "
                   f"this bundle does not carry")

    if resolver == "by_column_in_grounding":
        # A WITHIN-FILE SCOPE, and the first resolver whose target is not a file or a name but a
        # position INSIDE the carrier. `binds:` names columns of the concept's OWN grounding, so a
        # bind naming a column the concept does not ground is unresolvable without ever leaving
        # the file.
        # IT NOW RETURNS A TARGET. It used to resolve `dst=None` — correct while columns had no
        # identity, and the reason `impact` could not answer "what depends on dim_store.store_key":
        # the edge existed and pointed at nothing, so 32 real dependencies were unreachable from
        # either end. The column's identity is `<relation>.<column>`, which is also what the
        # dataset descriptor's sub_file objects are named, so the two join.
        doc = _doc_of(bundle / rel)
        cols: dict[str, str | None] = {}
        g = (doc or {}).get("grounding") if isinstance(doc, dict) else None
        if isinstance(g, dict):
            # `grounding.source` IS SINGULAR since 2026-10-07 (column_declaration.md rev 5):
            # `sources:` as a list is now a schema load error, so there is one relation to read,
            # not several to loop over. MEASURED the day this was found: 23 of 560
            # `concept_binds_column` pointers resolved to nothing on contoso5 because this read the
            # dead plural key and saw zero columns for every concept — the exact "reader on a dead
            # address while reporting success" failure this estate keeps naming.
            src = g.get("source")
            if isinstance(src, dict):
                relation = src.get("relation")
                relation = relation if isinstance(relation, str) and relation else None
                c = src.get("columns")
                if isinstance(c, dict):
                    for col in c:
                        cols.setdefault(col, relation)
                elif isinstance(c, list):
                    for x in c:
                        if isinstance(x, dict) and x.get("name"):
                            cols.setdefault(x["name"], relation)
        if value in cols:
            relation = cols[value]
            if not relation:
                # GROUNDED BUT UNATTRIBUTABLE: the source declares columns and no relation, so the
                # column cannot be named globally. Resolved-without-a-target is the honest answer —
                # inventing a relation would fabricate a join.
                return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                           f"by_column_in_grounding: {value!r} is one of {len(cols)} grounded "
                           f"column(s), but its source declares no `relation`, so the column has "
                           f"no global identity to point at", dst=None)
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_column_in_grounding: {value!r} is one of {len(cols)} grounded "
                       f"column(s), on relation {relation!r}", dst=f"{relation}.{value}")
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"by_column_in_grounding: {value!r} is NOT among this concept's "
                   f"{len(cols)} grounded column(s): {', '.join(sorted(cols)) or 'none'}")

    if resolver == "by_column_in_descriptor":
        # A CROSS-FILE CHECK, unlike by_column_in_grounding which never leaves the concept. The
        # concept says it grounds on `dim_store.store_key`; the DESCRIPTOR is the authority on
        # whether that column exists. A column renamed in the data plane dangles here, which is
        # the staleness class the whole data-plane half of this registry is for.
        where = idx.columns.get(value)
        if where:
            return Ref(name, kind["carrier"], rel, locator, value, "resolved",
                       f"by_column_in_descriptor: {value!r} is declared in {where}", dst=value)
        relation = value.rsplit(".", 1)[0] if "." in value else ""
        siblings = sorted(k for k in idx.columns if k.startswith(relation + "."))
        if not siblings:
            # NO DESCRIPTOR FOR THE RELATION AT ALL is a different fact from a missing column, and
            # `external` is already the word for a target this bundle does not own — a concept may
            # legitimately ground on a relation the bundle does not describe.
            return Ref(name, kind["carrier"], rel, locator, value, "external",
                       f"by_column_in_descriptor: no descriptor in data/datasets declares relation "
                       f"{relation!r}, so this bundle cannot confirm or deny the column")
        return Ref(name, kind["carrier"], rel, locator, value, "dangling",
                   f"by_column_in_descriptor: {relation!r} is described but declares no column "
                   f"{value.rsplit('.', 1)[-1]!r} — it declares "
                   f"{', '.join(x.rsplit('.', 1)[-1] for x in siblings)}")

    if resolver == "declared_not_a_pointer":
        # A REGISTRY ROW MAY DECLARE THAT A KEY IS NOT A POINTER. That is an answer, not an
        # absence: it moves a node out of "nobody has looked at this" into "someone decided", which
        # is the only difference that matters for a coverage number.
        return Ref(name, kind["carrier"], rel, locator, value, "external",
                   f"declared not a pointer: {kind.get('note_short') or kind['what'][:90]}")

    return Ref(name, kind["carrier"], rel, locator, value, "uncovered_kind",
               f"resolver {resolver!r} is not implemented in this prototype")
