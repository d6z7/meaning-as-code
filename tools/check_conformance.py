#!/usr/bin/env python3
"""check_conformance — HOW FAR IS THIS BUNDLE FROM THE STANDARD, in BOTH directions.

THE HOLE THIS FILLS
-------------------
Every existing gate answers "is what you wrote legal?". None answers "is what the standard OFFERS
being used, and is there structure here the standard never defined?". A standard that cannot detect
non-adoption or invention is a suggestion, not a standard. Measured on a live bundle, with every
gate green:

    validate_schema     0 errors, 61/61 clean       ...over 61 of 218 yaml files
    check_references    0 errors                    ...61 files indexed
    check_shapes        7 shapes x 22 concepts OK
    check_confidence    "OK (warn-first)"           ...16 objects self-certify CONFIRMED

Green, and the bundle uses `grounding.field_roles` on zero of 22 concepts, binds zero of seven
canon slots, declares no profile for the `x-` keys it carries, and ships documents stamped with a
`mac.*` schema id the framework has never defined. Nothing noticed, because nothing looks.

WHAT IT MEASURES — four sections, mapped to CONFORMANCE.md
  A  LEVEL COVERAGE       (CONFORMANCE §1)  how much of the bundle L1 even reaches; which planes are
                          outside it entirely; L2 defined-but-unimplemented (and what the bundle
                          built in its place, outside MAC's sight); L3 claimed vs ratified.
  B  PROFILE + EXTENSION  (CONFORMANCE §2)  is a profile declared; which `x-` keys are used vs
                          declared; and the harder violation §2 never anticipated — whole FILES the
                          schema has no definition for, each classified by evidence.
  C  CAPABILITY ADOPTION  the red line. Every OPTIONAL mechanism the framework offers, derived from
                          the schema + mac_shapes.yaml + mac_vocabulary.yaml + tools/canon/ — offered,
                          adopted, and where not adopted, WHAT THE BUNDLE DOES INSTEAD.
  D  VERDICT              one line a human can act on.

NOTHING IS HARDCODED. The capability register is derived from the framework's own artifacts at run
time, so a capability added to MAC tomorrow is measured tomorrow:
  * canon seam        every `$ref: canonBinding` site in mac.schema.json  x  the mac.canon registry
                      x  the executable canons in tools/canon/
  * shape machinery   every built-in shape in mac_shapes.yaml, and the slot it constrains
  * vocabularies      every `mac.<namespace>` in mac_vocabulary.yaml
  * file recognition  every bundle-relative artifact name any tools/*.py NAMES (AST-scanned, never
                      executed) — the framework's tools are the single home of "what MAC knows about"
  * schema routing    validate_schema's own file-selection, imported, not restated

SEVERITY, honestly
  An unadopted capability is INFO or WARN and never an error: a bundle may have a reason, and the
  gate does not know the reason. What IS an error: a claim the bundle makes and cannot back (a
  ratification-free L3), and a structure that asserts the framework's own identity without the
  framework defining it (a `mac.*` schema id with no definition; an `x-` key with no profile). Those
  are not "not yet adopted" — they are statements that are untrue today.

N WITNESSES COLLAPSE TO ONE ROOT. A capability unused on 22 concepts is ONE finding with a count,
not 22 lines. Per-object lists belong to the gate that owns them and are delegated by name.

SORTING is by what it costs to leave the finding unaddressed, not by severity alone: a WARN over 22
objects outranks an ERROR over one.

EXIT CODE, and the operator's ruling that a check which does not block is not enforcement:
  default   0  — warn-first. EVERY warn-first finding prints its EXPIRES-WHEN condition; a warn with
                 no stated expiry is a suggestion and this tool does not emit one.
  --strict  1  — any BLOCKING-class finding fails the run. The BLOCKING SLATE printed at the end is
                 the list of codes that should be moved to blocking, each with its trigger.

Usage:
  tools/check_conformance.py <bundle> [--reference <bundle>] [--strict] [--json]

`--reference` is read ONLY to establish that a mechanism is usable in practice (adoption counts).
Its own defects are never reported: it is evidence, not a target.
"""
from __future__ import annotations

import argparse
import ast
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: pip install pyyaml")

import validate_schema as VS  # noqa: E402  — the single home of "which files L1 routes"
from mac_project import resolve  # noqa: E402

MAC_ROOT = Path(__file__).resolve().parent.parent
TOOLS = MAC_ROOT / "tools"


# ═════════════════════════════════════════════════════════════════ loading

def load_yaml(p: Path):
    class L(yaml.SafeLoader):
        pass
    L.add_constructor("tag:yaml.org,2002:timestamp", lambda l, n: l.construct_scalar(n))
    try:
        return yaml.load(p.read_text(encoding="utf-8"), Loader=L)
    except Exception:
        return None


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def walk(node, path=""):
    """(jsonpath, key, value) for every mapping entry, depth-first."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield path, k, v
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


# ═══════════════════════════════════════════════ the framework, introspected

@dataclass
class Framework:
    """What MAC offers — derived from MAC's own artifacts, never restated here."""
    schema: dict
    shapes: list
    vocab: dict
    artifacts: dict            # bundle-relative artifact name -> {tools that name it}
    canon_registered: set      # names in the mac.canon registry
    canon_executable: set      # names with a callable in tools/canon/
    canon_slots: list          # schema paths carrying a canonBinding
    mac_spec_ids: set          # mac.<thing>/<n> ids the framework itself defines
    tool_stems: set            # token vocabulary of MAC's own tool module names
    schema_enums: dict = field(default_factory=dict)   # property name -> the closed set the schema allows


_PATHY = re.compile(r"^[A-Za-z0-9_.]+(/[A-Za-z0-9_.*-]+)*\.(yaml|json|csv|md|sql)$")
_SPEC_ID = re.compile(r"mac\.[a-z_]+/[0-9]+")


def introspect_framework() -> Framework:
    schema = json.loads((MAC_ROOT / "mac.schema.json").read_text())
    shapes = (load_yaml(MAC_ROOT / "mac_shapes.yaml") or {}).get("shapes") or []
    vocab = load_yaml(MAC_ROOT / "mac_vocabulary.yaml") or {}

    # --- every artifact name a MAC tool NAMES (AST, not exec). Framework-internal files (which exist
    #     inside this repo) are excluded: those are MAC's own, not a bundle's.
    artifacts: dict[str, set] = defaultdict(set)
    spec_ids: set[str] = set()
    tool_stems: set[str] = set()
    for f in sorted(TOOLS.glob("*.py")):
        if f.name == Path(__file__).name:
            continue
        tool_stems.update(_tokens(f.stem))
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                s = n.value
                if _PATHY.match(s) and not (MAC_ROOT / s).exists():
                    artifacts[s].add(f.name)
                spec_ids.update(_SPEC_ID.findall(s))

    # --- the canon seam: schema slots x registry x executable library
    canon_slots: list[str] = []

    def find_canon(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str) and v.endswith("canonBinding"):
                    canon_slots.append(path)
                find_canon(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                find_canon(v, f"{path}/{i}")

    find_canon(schema, "")
    _canon_blk = vocab.get("canon") or {}
    # a mac_vocabulary block spells its members `terms` (a vocabulary) or `members` (a value_domain)
    registered = set(_canon_blk.get("terms") or _canon_blk.get("members") or {})
    executable: set[str] = set()
    try:
        sys.path.insert(0, str(TOOLS))
        import canon as _canon  # noqa
        executable = set(getattr(_canon, "CANON_NAMES", None) or getattr(_canon, "CANONS", {}))
    except Exception:
        pass

    # --- every closed set the SCHEMA itself spells out. A bare value drawn from one of these is the
    #     LEGAL form, not a restatement of a mac.* vocabulary — without this, the restatement probe
    #     fires on `identity.kind: code` and `additivity.<axis>: additive`, both of which the schema
    #     defines as enums and neither of which has a mac.* reference form to use instead.
    enums: dict[str, set] = defaultdict(set)

    def find_enums(node):
        if isinstance(node, dict):
            for k, v in (node.get("properties") or {}).items():
                if isinstance(v, dict):
                    if isinstance(v.get("enum"), list):
                        enums[k].update(v["enum"])
                    ap = v.get("additionalProperties")
                    if isinstance(ap, dict) and isinstance(ap.get("$ref"), str):
                        tgt = (schema.get("$defs") or {}).get(ap["$ref"].rsplit("/", 1)[-1], {})
                        if isinstance(tgt.get("enum"), list):
                            enums[k].update(tgt["enum"])
            for v in node.values():
                find_enums(v)
        elif isinstance(node, list):
            for v in node:
                find_enums(v)

    find_enums(schema)
    return Framework(schema, shapes, vocab, dict(artifacts), registered, executable,
                     canon_slots, spec_ids, tool_stems, {k: set(v) for k, v in enums.items()})


_GENERIC_TOKENS = {"mac", "check", "to", "gen", "project", "model", "tool", "the", "data",
                   "ontology", "file", "files", "build", "run", "out", "index", "map"}


def _tokens(name: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) > 2 and t not in _GENERIC_TOKENS}


# ═══════════════════════════════════════════════════ the bundle, measured

@dataclass
class Bundle:
    root: Path
    layout: object
    routed: set = field(default_factory=set)      # abs paths validate_schema routes to a $def
    all_files: list = field(default_factory=list)  # every non-vcs file, bundle-relative
    concepts: dict = field(default_factory=dict)   # relpath -> doc
    docs: dict = field(default_factory=dict)       # relpath -> parsed doc (yaml/json)
    _corpus_cache: dict = None                     # relpath -> text, filled lazily


_SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", "projections", ".harvest_cache"}


def load_bundle(root: Path) -> Bundle:
    layout = resolve(str(root))
    b = Bundle(root=root, layout=layout)

    # --- routed: reuse validate_schema's OWN selection so there is one definition of "L1 sees it"
    files = []
    for pat in ("**/concepts/**/*.yaml", "**/rules.yaml", "**/edges.yaml", "**/tables/*.yaml"):
        files += glob.glob(str(root / pat), recursive=True)
    files += glob.glob(str(layout.descriptors / "*.yaml"))
    for extra in (getattr(layout, "transforms", None), getattr(layout, "sources", None)):
        if extra:
            files += glob.glob(str(extra / "*.yaml"))
    b.routed = {os.path.abspath(f) for f in files
                if not any(p in Path(f).parts for p in _SKIP_PARTS)}

    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in _SKIP_PARTS for part in p.parts):
            continue
        rel = str(p.relative_to(root))
        b.all_files.append(rel)
        if p.suffix == ".yaml":
            d = load_yaml(p)
            if isinstance(d, dict):
                b.docs[rel] = d
                if "concept" in d and "metadata" in d and os.path.abspath(p) in b.routed:
                    b.concepts[rel] = d
        elif p.suffix == ".json":
            d = load_json(p)
            if isinstance(d, dict):
                b.docs[rel] = d
    return b


# ═════════════════════════════════════════════════════════════ findings

BLOCKING, WARN, INFO = "BLOCKING", "WARN", "INFO"
_SEV_RANK = {BLOCKING: 0, WARN: 1, INFO: 2}


@dataclass
class Finding:
    code: str
    section: str
    severity: str
    headline: str
    cost: str                    # what it costs to leave this unaddressed
    blast: int = 1               # objects affected — the collapse count
    detail: list = field(default_factory=list)
    expires: str = ""            # the condition that makes a warn-first finding blocking
    delegate: str = ""           # the gate that owns the per-object list

    def rank(self):
        return (_SEV_RANK[self.severity], -self.blast, self.code)


# ═════════════════════════════════════ A — LEVEL COVERAGE (CONFORMANCE §1)

_SQL_KEYS = {"sql", "query", "cross_check_sql", "derivation"}
_EXPECT_KEYS = {"expect", "expected", "assert", "assertion", "raw_value", "tolerance", "value_is"}


def _looks_like_execution_validation(doc) -> bool:
    """L2 by CONFORMANCE §1: 'the query the model implies runs and the number is sane'. A document
    implements it when it pairs a QUERY with an EXPECTED VALUE. A transform descriptor carries sql
    and no expectation, so it does not match — that separation is what makes this test cheap."""
    has_sql = has_exp = False
    for _, k, _v in walk(doc):
        if k in _SQL_KEYS:
            has_sql = True
        if k in _EXPECT_KEYS:
            has_exp = True
        if has_sql and has_exp:
            return True
    return False


def section_a(b: Bundle, fw: Framework) -> list:
    out = []
    yamls = [f for f in b.all_files if f.endswith(".yaml")]
    routed_rel = {os.path.relpath(p, b.root) for p in b.routed}
    outside = [f for f in yamls if f not in routed_rel]

    by_dir = Counter(os.path.dirname(f) or "." for f in outside)
    routed_dirs = {os.path.dirname(f) or "." for f in routed_rel}
    dark = {d: n for d, n in by_dir.items() if d not in routed_dirs}

    out.append(Finding(
        code="A1-l1-reach", section="A", severity=INFO, blast=len(outside),
        headline=(f"L1 routes {de(len(routed_rel))} of {de(len(yamls))} yaml files "
                  f"({pct(len(routed_rel), len(yamls))}) — "
                  f"{de(len(outside))} carry model content no schema definition covers"),
        cost="every gate downstream of the schema is blind to those files; a change there is unreviewable by machine",
        detail=[f"{n:4d}  {d}/" for d, n in sorted(by_dir.items(), key=lambda kv: -kv[1])],
        expires="never blocking on its own — it is the denominator the other findings are measured against"))

    if dark:
        planes = sorted(dark, key=lambda d: -dark[d])
        out.append(Finding(
            code="A2-dark-planes", section="A", severity=WARN, blast=sum(dark.values()),
            headline=(f"{len(dark)} director{'y' if len(dark) == 1 else 'ies'} are entirely outside L1 — "
                      f"{sum(dark.values())} yaml files, not one routed to a schema definition"),
            cost=("these are whole planes of the model the standard does not govern: their keys are open, "
                  "their references unresolved, their drift undetectable"),
            detail=[f"{dark[d]:4d}  {d}/" for d in planes],
            expires=("blocking once the schema defines a file type for the largest of these, or the project "
                     "declares them out of scope in mac.project.yaml#conformance.out_of_scope")))

    # --- L2: defined by the standard, implemented by nobody in the framework
    impl = sorted(rel for rel, d in b.docs.items() if _looks_like_execution_validation(d))
    impl_dirs = Counter(os.path.dirname(f) or "." for f in impl)
    out.append(Finding(
        code="A3-l2-unimplemented", section="A", severity=WARN, blast=len(impl),
        headline=(f"L2 (execution-validated) is DEFINED by CONFORMANCE §1 and implemented by no MAC tool — "
                  f"while this bundle implements it itself in {len(impl)} file(s), outside MAC's sight"),
        cost=("the standard's own trust gradient has a middle rung nobody can climb inside the framework; "
              "each bundle reinvents it, so no two bundles' L2 claims are comparable"),
        detail=([f"{n:4d}  {d}/  (query + expected value, the §1 definition of L2)"
                 for d, n in sorted(impl_dirs.items(), key=lambda kv: -kv[1])]
                or ["    (this bundle implements no execution validation either)"]),
        expires=("blocking when MAC ships an L2 runner and a file type for it; until then it is a framework "
                 "debt, not a bundle defect")))

    # --- L3: claimed vs ratified. The per-object list belongs to mac_checks_semantic's MAC006.
    #     Two counts, because they answer different questions and the weaker one is the one that
    #     survives argument: EVERY C without ratification evidence is unbacked by the standard's own
    #     definition ("an SME has ratified the meaning"); the subset stamped `provenance: harvested`
    #     is one a machine certified about its own output, which nobody defends.
    claimed, ratified, sites, machine = 0, 0, [], 0
    for rel, d in b.docs.items():
        md = d.get("metadata") if isinstance(d.get("metadata"), dict) else None
        if not md or str(md.get("confidence", "")) not in ("C", "CONFIRMED"):
            continue
        claimed += 1
        gov = d.get("governance") if isinstance(d.get("governance"), dict) else {}
        if gov.get("ratified_by") or gov.get("ratified_on") or gov.get("approval_status") == "approved":
            ratified += 1
            continue
        sites.append(rel)
        if str(md.get("provenance", "")) == "harvested":
            machine += 1
    if claimed and ratified < claimed:
        out.append(Finding(
            code="A4-l3-unratified", section="A", severity=BLOCKING, blast=claimed - ratified,
            headline=(f"{claimed - ratified} of {claimed} objects claim L3 (confidence: C = expert-confirmed) "
                      f"and carry no ratification evidence — {machine} of them are machine-written "
                      f"(provenance: harvested)"),
            cost=("L3 is the standard's HIGHEST level and the one a reader trusts without checking. An "
                  "unratified C is not an unadopted capability — it is a false statement, and a reader "
                  "who believes it stops looking. CONFORMANCE §1 defines L3 as 'an SME has ratified the "
                  "meaning'; nothing on these objects records that anyone did"),
            detail=[f"     {claimed - ratified} objects; first: {', '.join(sorted(sites)[:3])}",
                    f"     ratification evidence looked for: governance.ratified_by / ratified_on / "
                    f"approval_status=approved  (found on {ratified})"],
            delegate=("mac_checks_semantic.py MAC006 claim-unearned — owns the per-object list and the "
                      "provenance cross-check; it currently rules the machine-written subset unearned"),
            expires="already blocking under --strict here and there; make it unconditional once triaged"))
    return out


# ═════════════════════════════ B — PROFILE + EXTENSION DISCIPLINE (§2)

def _profile_of(b: Bundle) -> dict:
    """RETIRED. CONFORMANCE §2 used to say a project declares a PROFILE of the `x-` keys it uses.
    That whole mechanism is withdrawn: `x-` keys are PROHIBITED (MAC012), the schema no longer
    defines a profile slot, and MAC009 — whose remedy was "declare it" — is retired.

    Kept as a stub returning {} so the declared-set plumbing below still works, and so a bundle
    that still carries a legacy profile block is not silently credited for it."""
    man = b.docs.get("mac.project.yaml") or {}
    for key in ("profile", "x_profile", "extensions"):
        p = man.get(key)
        if isinstance(p, dict):
            return p
    return {}


def section_b(b: Bundle, fw: Framework) -> list:
    out = []
    profile = _profile_of(b)
    declared = set(profile.get("x_keys") or profile.get("keys") or profile) if profile else set()

    # --- x- keys in use
    used: dict[str, list] = defaultdict(list)
    for rel, d in b.docs.items():
        for jpath, k, _v in walk(d):
            if isinstance(k, str) and k.startswith("x-"):
                used[k].append(f"{rel}{jpath}")
    undeclared = {k: v for k, v in used.items() if k not in declared}

    # PROHIBITION, not declaration. There is exactly ONE thing to say about an `x-` key now, and
    # this axis used to say the opposite: it reported "no profile is declared" as the defect and
    # named declaring as the remedy. With MAC009 retired and the schema's profile slot removed,
    # that advice pointed at a construct with no home and ratified a banned one. A framework must
    # not encode opposite policies; this was one of the voices that did.
    if used:
        out.append(Finding(
            code="B1-prohibited-x", section="B", severity=BLOCKING, blast=len(used),
            headline=(f"{len(used)} `x-` key(s) in use at "
                      f"{sum(len(v) for v in used.values())} site(s) — prohibited"),
            cost=("`x-` extension keys are prohibited (MAC012). They are not easily verifiable and "
                  "they are a weak point in the chain. There is no declaration that makes one legal: "
                  "the key is removed, or the thing it carries earns a CORE key by proposal"),
            detail=([f"     {k}  x{len(v)}   {v[0]}" for k, v in sorted(used.items())]
                    + ["", "     REMEDY: check whether the core already expresses it — measured on a real",
                       "     bundle, every `x-` key there was either derivable from a declared type or",
                       "     restating at the wrong layer something the core already owned. If the core",
                       "     genuinely cannot express it, propose a core key (CONFORMANCE §2)."]),
            expires="blocking now — prohibition, not debt"))

    # --- mac.* spec ids the bundle asserts that the framework does not define
    forged: dict[str, list] = defaultdict(list)
    for rel, d in b.docs.items():
        for jpath, k, v in walk(d):
            if k in ("spec_version", "schema", "schema_id") and isinstance(v, str):
                for sid in _SPEC_ID.findall(v):
                    if sid not in fw.mac_spec_ids:
                        forged[sid].append(f"{rel}{jpath}.{k}")
    if forged:
        out.append(Finding(
            code="B3-forged-spec-id", section="B", severity=BLOCKING, blast=len(forged),
            headline=(f"{len(forged)} document(s) declare a `mac.*` schema id the framework does not define"),
            cost=("this is stronger than an undeclared x- key: an x- key is namespaced AS an extension, "
                  "while a mac.* id claims the framework's own identity. A consumer that trusts the "
                  "namespace has no way to learn the id is fiction"),
            detail=[f"     {sid}   {', '.join(v[:2])}" for sid, v in sorted(forged.items())]
                   + [f"     framework defines: {', '.join(sorted(fw.mac_spec_ids)) or '(none)'}"],
            expires="blocking now — either the framework defines the id, or the document renames out of mac.*"))

    # --- the harder violation §2 never anticipated: whole FILES with no definition
    out += _unknown_files(b, fw, declared)
    return out


_CODE_EXT = {".py", ".sh", ".bash", ".js", ".rb"}
_STRUCTURED = {".yaml", ".yml", ".json"}


def _known_reason(rel: str, b: Bundle, fw: Framework) -> str | None:
    """Why MAC knows this file — '' means it does not."""
    if os.path.abspath(b.root / rel) in b.routed:
        return "schema"
    base = os.path.basename(rel)
    if rel in fw.artifacts or base in fw.artifacts:
        return "tool"
    d = b.docs.get(rel) or {}
    for _, k, v in walk(d):
        if k in ("spec_version", "schema", "schema_id") and isinstance(v, str):
            if any(sid in fw.mac_spec_ids for sid in _SPEC_ID.findall(v)):
                return "emitted"
    return None


_TEXTY = _STRUCTURED | {".md", ".sql", ".py", ".csv", ".txt"}


def _corpus(b: Bundle) -> dict:
    """Every text file's content, read ONCE. Inbound-reference counting is the only quadratic thing
    here and it is what separates load-bearing content from an orphan; caching keeps it cheap."""
    if getattr(b, "_corpus_cache", None) is None:
        cache = {}
        for rel in b.all_files:
            p = b.root / rel
            if p.suffix in _TEXTY:
                try:
                    cache[rel] = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass
        b._corpus_cache = cache
    return b._corpus_cache


def _inbound(rel: str, b: Bundle) -> list:
    """Which other bundle files name this one. Load-bearing content is referenced; orphans are not."""
    base = os.path.basename(rel)
    return [o for o, t in _corpus(b).items() if o != rel and base in t]


def _classify(rel: str, b: Bundle, fw: Framework, routed_rel: set) -> tuple:
    """(bucket, per-file reason, collapse category) for one undeclared file, by EVIDENCE, in
    precedence order. The category is the stable phrase a directory collapses onto — the per-file
    reason carries counts, which must not survive collapsing or the group line reads as nonsense.

    Precedence matters: a name collision with a framework artifact outranks everything (the bundle is
    re-implementing something MAC has), then code, then orphanhood, then load-bearing-ness."""
    # (ii) MAC ALREADY OFFERS IT — deliberately the STRICT test: the stem's token set must be EQUAL
    # to a framework artifact's, i.e. the same construct under a different extension or path. The
    # looser "tokens intersect" test was measured first and fired on 3 of 5 sites (85 oracle answer
    # files matched `meta_tables.ddl.sql` on the token `meta`; `ontology_quality.json` matched
    # `data_quality_register.yaml` on `quality`). Recall is the price: `lineage_graph.json` and
    # `.harvest_manifest.yaml` fall through to the orphan/absorb buckets instead. A finding that is
    # wrong three times in five teaches a reader to skip the section.
    toks = _tokens(Path(rel).stem)
    collision = sorted({a for a in fw.artifacts if toks and _tokens(Path(a).stem) == toks})
    if collision:
        msg = (f"MAC already offers this as {collision[0]} — same construct, "
               f"a file type the framework cannot read")
        return "already", msg, msg
    if Path(rel).suffix in _CODE_EXT:
        msg = ("executable code inside a content bundle — unversioned framework, "
               "outside every gate, reproducible by nobody")
        return "should_not", msg, msg
    refs = _inbound(rel, b)
    if not refs:
        msg = "nothing in the bundle references it — an orphan register"
        return "should_not", msg, msg
    n_model = sum(r in routed_rel for r in refs)
    if n_model:
        return ("absorb", f"load-bearing: {n_model} schema-governed file(s) depend on it",
                "load-bearing: schema-governed files depend on it")
    return ("absorb", f"referenced by {len(refs)} file(s), all prose — documented but ungoverned",
            "referenced only from prose — documented but ungoverned")


_GROUP_MIN = 3   # a directory with this many undeclared files is reported AS A DIRECTORY, not as files


def _collapse(items: list) -> list:
    """N witnesses -> one root. A directory holding >= _GROUP_MIN undeclared files of the same kind is
    ONE finding line carrying the count; only small or mixed sites are listed file by file. A check
    that emits 96 identical lines gets muted, and a muted check enforces nothing."""
    by_dir = defaultdict(list)
    for rel, reason, cat in items:
        by_dir[os.path.dirname(rel) or "."].append((rel, reason, cat))
    out = []
    for d, group in sorted(by_dir.items()):
        if len(group) < _GROUP_MIN:
            out += [(rel, reason) for rel, reason, _ in sorted(group)]
            continue
        cats = Counter(c for _, _, c in group)
        head, n = cats.most_common(1)[0]
        extra = (f"  [+{len(group) - n} here classified differently]" if n < len(group) else "")
        out.append((f"{d}/  ({len(group)} files)", f"{head}{extra}"))
    return out


def _unknown_files(b: Bundle, fw: Framework, declared: set) -> list:
    out = []
    unknown, gate_only = [], []
    for rel in b.all_files:
        ext = Path(rel).suffix
        if ext not in (_STRUCTURED | _CODE_EXT):
            continue
        why = _known_reason(rel, b, fw)
        if why == "schema":
            continue
        if why in ("tool", "emitted"):
            gate_only.append((rel, why))
            continue
        if rel in declared:
            continue
        unknown.append(rel)

    routed_rel = {os.path.relpath(p, b.root) for p in b.routed}
    buckets = defaultdict(list)
    for rel in unknown:
        bucket, reason, cat = _classify(rel, b, fw, routed_rel)
        buckets[bucket].append((rel, reason, cat))
    absorb = _collapse(buckets["absorb"])
    already = _collapse(buckets["already"])
    should_not = _collapse(buckets["should_not"])
    n_raw = {k: len(v) for k, v in buckets.items()}

    if gate_only:
        out.append(Finding(
            code="B4-gate-known-schema-less", section="B", severity=WARN, blast=len(gate_only),
            headline=(f"{len(gate_only)} file(s) a MAC tool reads but mac.schema.json does not define — "
                      f"governed by code, not by the contract"),
            cost=("the schema is advertised as the single source of structural truth; for these files it is "
                  "not, and their shape lives in whichever tool happens to parse them"),
            detail=[f"     {rel:52s} known via {why}" for rel, why in sorted(gate_only)],
            expires="blocking when the schema gains a $def for each; until then it is framework debt"))

    for code, key, bucket, sev, label, cost in (
        ("B5-undeclared-should-not-exist", "should_not", should_not, BLOCKING, "SHOULD NOT EXIST",
         "code and orphans in a content bundle are outside every gate: nothing validates them, nothing "
         "regenerates them, and nothing notices when they rot"),
        ("B6-undeclared-mac-offers-it", "already", already, WARN, "MAC ALREADY OFFERS IT UNDER ANOTHER NAME",
         "the bundle maintains a second, incompatible copy of a construct the framework already has — "
         "so the framework's tooling cannot read the bundle's version, and vice versa"),
        ("B7-undeclared-should-absorb", "absorb", absorb, WARN, "A LEGITIMATE EXTENSION MAC SHOULD ABSORB",
         "real model content with no definition: it cannot be validated, projected, or promoted, and the "
         "next bundle will invent it differently"),
    ):
        if not bucket:
            continue
        out.append(Finding(
            code=code, section="B", severity=sev, blast=n_raw[key],
            headline=(f"{n_raw[key]} undeclared file(s) at {len(bucket)} site(s) — {label}"),
            cost=cost,
            detail=[f"     {rel:52s} {why}" for rel, why in bucket],
            expires=("blocking once a profile can declare files; a bundle that declares them keeps them"
                     if sev is WARN else
                     "blocking now for code; orphans expire when deleted or declared")))
    return out


# ═══════════════════════════════ C — CAPABILITY ADOPTION (the red line)

@dataclass
class Capability:
    key: str
    offered_by: str          # the framework evidence that it is offered
    slot: str                # where a bundle would write it
    used: int = 0
    sites: list = field(default_factory=list)
    instead: list = field(default_factory=list)   # what the bundle does in its place
    ref_used: int = 0
    ref_scope: str = ""


_IDX = re.compile(r"\[\d+\]")


def _l1_docs(b: Bundle) -> dict:
    """The L1 corpus — the documents the schema actually routes. Capability adoption is a statement
    about the MODEL, so it is counted here and not over prose registers that merely mention a key.
    Counting `realized_by` bundle-wide gave 14 on a bundle whose model carries exactly 1; the other
    13 were the word appearing in an intervention register and in oracle files."""
    if getattr(b, "_l1_cache", None) is None:
        b._l1_cache = {rel: d for rel, d in b.docs.items()
                       if os.path.abspath(b.root / rel) in b.routed}
    return b._l1_cache


def _count_slot(b: Bundle, dotted: str, l1_only: bool = True) -> tuple:
    """Sites carrying a DOTTED SLOT PATH, e.g. `contract.rules[].binds` or `concept.semantics.additivity`.

    Anchored, not name-matched. An unanchored key count is not a capability measurement: `kind`
    appears 800 times in this bundle and `concept.identity.kind` 22 — the first number says nothing
    about whether the identity capability is adopted."""
    target = _IDX.sub("[]", dotted).lstrip(".")
    docs = _l1_docs(b) if l1_only else b.docs
    n, sites = 0, []
    for rel, d in docs.items():
        for jpath, k, _v in walk(d):
            full = _IDX.sub("[]", f"{jpath}.{k}").lstrip(".")
            if full == target or full.endswith("." + target):
                n += 1
                sites.append(f"{rel}:{full}")
    return n, sites


# Where each relational shape KIND lands in a bundle document. The shape's own `constraint.path` is
# authoritative when it has one; these three are the relational kinds, whose subject is implied by the
# kind's name rather than written as a path. Framework-level and domain-neutral.
_SHAPE_KIND_SLOT = {
    "rule_binds_grounded": "contract.rules[].binds",
    "field_roles_grounded": "grounding.field_roles",
    "join_rule_grounded": "edges[].join_rule",
}


def build_capabilities(b: Bundle, fw: Framework) -> list:
    caps: list[Capability] = []

    # ---- 1. the canon seam: every canonBinding slot in the schema, measured as one mechanism
    n_rb, sites_rb = _count_slot(b, "realized_by")
    per_slot = Counter(s.split(":", 1)[1] for s in sites_rb)
    caps.append(Capability(
        key="canon seam — realized_by / canonRef",
        offered_by=(f"{len(fw.canon_slots)} schema slots accept a canonBinding; "
                    f"{len(fw.canon_registered)} canons registered in mac_vocabulary.yaml, "
                    f"{len(fw.canon_executable)} executable in tools/canon/"),
        slot=" · ".join(sorted({s.rsplit("/", 2)[0].replace("/$defs/", "").split("/")[0]
                                for s in fw.canon_slots})),
        used=n_rb, sites=[f"{p} x{n}" for p, n in per_slot.most_common()]))

    # ---- 2. slots the built-in shapes enforce (mac_shapes.yaml IS the machinery)
    for sh in fw.shapes:
        c = sh.get("constraint") or {}
        path = c.get("path") or _SHAPE_KIND_SLOT.get(c.get("kind"))
        if not path:
            continue
        n, sites = _count_slot(b, path)
        caps.append(Capability(
            key=f"{path}  (shape {sh['id']})",
            offered_by=f"built-in shape `{sh['id']}` ({sh.get('severity')}) in mac_shapes.yaml, run cross-file",
            slot=path, used=n, sites=sites))

    # ---- 3. every mac.<namespace> vocabulary: defined once, referenced or not
    ns = [k for k, v in fw.vocab.items() if k != "metadata" and isinstance(v, dict)]
    text = {rel: json.dumps(d, default=str) for rel, d in _l1_docs(b).items()}
    for name in sorted(ns):
        pat = re.compile(rf"mac\.{re.escape(name)}\b")
        sites = [rel for rel, t in text.items() if pat.search(t)]
        terms = (fw.vocab[name].get("terms") or fw.vocab[name].get("members") or {})
        caps.append(Capability(
            key=f"mac.{name}  ({len(terms)} terms)",
            offered_by="mac_vocabulary.yaml — resolved by check_references; an unknown term is an ERROR",
            slot=f"any string, as `mac.{name}.<term>`",
            used=len(sites), sites=sites))

    # ---- 4. the application-vocabulary mechanism (v0.1.7): a project-owned vocabulary.yaml
    appvocab = [rel for rel in b.all_files if os.path.basename(rel) == "vocabulary.yaml"]
    caps.append(Capability(
        key="application vocabulary  (project vocabulary.yaml)",
        offered_by=("check_references rglob's `vocabulary.yaml`, indexes `<ns>.<vocab>[.<term>]`, and "
                    "ERRORS on an unresolved reference — the define-once half of field_roles"),
        slot="<anywhere>/vocabulary.yaml with `namespace: <ns>`",
        used=len(appvocab), sites=appvocab))

    # ---- 5. application shapes (--shapes): the constraint gate, extended by the project
    appshapes = [rel for rel in b.all_files if os.path.basename(rel) == "shapes.yaml"]
    caps.append(Capability(
        key="application shapes  (--shapes)",
        offered_by="check_shapes.py loads project shapes alongside the built-ins",
        slot="<plane>/shapes.yaml", used=len(appshapes), sites=appshapes))

    # ---- 6. the x- extension namespace + profile (CONFORMANCE §2)
    xn, xs = 0, []
    for rel, d in b.docs.items():
        for jpath, k, _v in walk(d):
            if isinstance(k, str) and k.startswith("x-"):
                xn += 1
                xs.append(f"{rel}{jpath}.{k}")
    caps.append(Capability(
        key="x- extension namespace (RETIRED — prohibited, MAC012)",
        offered_by="schema patternProperties `^x-` at every object level (CONFORMANCE §2)",
        slot="any object; each key declared in the project profile",
        used=xn, sites=xs))

    # ---- 7. optional slots that carry BEHAVIOUR and have a named consumer in the framework
    for path, why in (
        ("contract.rules[].enforced_by",
         "the deterministic backstop a rule names — the link from a written rule to the thing that fails "
         "if it is broken"),
        ("contract.rules[].why", "the rule's one-line rationale (the authored cause, beside the directive)"),
        ("contract.rules[].subject", "v0.1.13 rule headline (rendered by mac_to_explorer / mac_to_manual)"),
        ("grounding.serves_from", "v0.5 PROMOTE — the serving view(s) a concept is answered from"),
        ("grounding.grain", "v0.5 PROMOTE — the committed leaf grain, one row = one …"),
        ("concept.semantics.null_semantics", "what an absent value MEANS, rather than what it looks like"),
        ("values.aliases", "the auditable surface→code trigger vocabulary (aliasBlock)"),
        ("edges[].aliases", "v0.1.12 relationAliasBlock — the surface→RELATION trigger vocabulary"),
        ("edges[].resolved_by", "v0.1.12 — the rule computing a shared_attribute relation's set"),
    ):
        n, sites = _count_slot(b, path)
        caps.append(Capability(
            key=path, offered_by=f"schema — {why}", slot=path, used=n, sites=sites))

    return caps


# --- "what is the bundle doing INSTEAD" — evidence-based, per capability family

def probe_alternatives(cap: Capability, b: Bundle, fw: Framework) -> list:
    """WHAT IS THE BUNDLE DOING INSTEAD. A gate that only says 'unused' is a scold; the useful half is
    the substitute the project built, because that is the thing that has to be migrated or defended."""
    out = []
    k = cap.key

    if "field_roles" in k:
        # the vocabulary the mechanism resolves against may exist in an unreadable format
        for rel, d in b.docs.items():
            t = json.dumps(d, default=str)
            m = re.findall(r"\b([a-z][a-z0-9_]*)\.field_role\b", t)
            if m and os.path.basename(rel) != "vocabulary.yaml":
                out.append(f"declares a `{sorted(set(m))[0]}.field_role.*` vocabulary in {rel} — "
                           f"a format check_references does not read (it rglobs vocabulary.yaml)")
                break
        ncols = sum(len(s.get("columns") or [])
                    for d in b.concepts.values()
                    for s in ((d.get("grounding") or {}).get("sources") or []))
        if ncols:
            out.append(f"lists {ncols} columns under grounding.sources[].columns with no role on any of them — "
                       f"the whitelist exists, the MEANING of each column does not")

    if "canon seam" in k:
        # enumerations that restate a value set a pinned register already holds
        cands = _register_delegable(b)
        if cands:
            out.append(f"{len(cands)} enumeration(s) restate a value set an existing register already holds "
                       f"exactly — mac.canon.enum_from_register is the slot for it")
            out += [f"    {c}" for c in cands]
        nrules = sum(len((d.get("contract") or {}).get("rules") or []) for d in b.concepts.values())
        if nrules:
            out.append(f"{nrules} typed rules carry when/then prose only — every one is model-interpreted, "
                       f"none is run")

    if k.startswith("x- extension namespace") and cap.used:
        out.append(f"uses the namespace at {cap.used} site(s) with no profile declaring any of them — "
                   f"half the mechanism (see B1); the extension is visible but not explained")

    if k.startswith("contract.rules[].enforced_by"):
        # an anchor/oracle plane that rules could name but do not
        anch = Counter(os.path.dirname(f) for f in b.all_files
                       if f.endswith(".yaml") and re.search(r"anchor|oracle", f))
        if anch:
            top = ", ".join(f"{d}/ ({n})" for d, n in anch.most_common(2))
            nrules = sum(len((d.get("contract") or {}).get("rules") or []) for d in b.concepts.values())
            out.append(f"holds {sum(anch.values())} deterministic backstop artifacts in {top} and names "
                       f"none of them from any of {nrules} rules — the link is made in prose, or not at all")

    if k.startswith("application vocabulary"):
        alt = [rel for rel in b.all_files if Path(rel).stem == "vocabulary"]
        if alt:
            out.append(f"has the content in {alt[0]} — right idea, wrong file type; the resolver never sees it")

    if k.startswith("contract.rules[].why"):
        sib = Counter(k2 for d in b.concepts.values()
                      for r in ((d.get("contract") or {}).get("rules") or []) for k2 in r)
        near = [f"{k2} x{n}" for k2, n in sib.most_common() if k2 in ("subject", "never", "then")]
        if near:
            out.append(f"carries {', '.join(near)} on its rules instead — the directive is written, "
                       f"the REASON for it is not, so a reader cannot tell a law from a preference")

    if k.startswith("grounding.serves_from"):
        rels = {s.get("relation") for d in b.concepts.values()
                for s in ((d.get("grounding") or {}).get("sources") or []) if isinstance(s, dict)}
        rels.discard(None)
        if rels:
            out.append(f"grounds on {len(rels)} relation name(s) via grounding.sources[].relation with no "
                       f"pointer to the SQL that serves them — the view is named, its definition is not")

    if k.startswith("mac."):
        # A vocabulary is RESTATED when a model document writes one of its terms as a bare VALUE where
        # the `mac.<ns>.<term>` reference belongs. Deliberately narrow: term-as-a-value inside the L1
        # corpus only. The first cut matched the term anywhere in any file's text and reported that
        # this bundle "restates mac.aggregation_effect in 158 files" — the word `additive` occurring in
        # prose. A probe that counts English is not evidence.
        name = k.split()[0][4:]
        terms = set((fw.vocab.get(name) or {}).get("terms") or
                    (fw.vocab.get(name) or {}).get("members") or {})
        hits, seen = set(), Counter()
        for rel, d in _l1_docs(b).items():
            for jpath, k2, v in walk(d):
                if not isinstance(v, str) or v not in terms:
                    continue
                if v in fw.schema_enums.get(k2, ()) or v in fw.schema_enums.get(
                        jpath.rsplit(".", 1)[-1].split("[")[0], ()):
                    continue   # the schema spells this set out here; the bare value IS the legal form
                hits.add(rel)
                seen[f"{k2}: {v}"] += 1
        if hits:
            top = ", ".join(f"`{s}`" for s, _ in seen.most_common(2))
            out.append(f"writes this vocabulary's terms as bare values in {len(hits)} model file(s) "
                       f"({top}) with no `mac.{name}.*` reference — restated, not resolved, so a "
                       f"misspelling is invisible to check_references")
    return out


def _register_delegable(b: Bundle) -> list:
    """Enumerations whose inline items EXACTLY equal a register column — the safe delegation set.

    Exact set equality, deliberately. The looser `codes subset of column` test was measured first and
    fired on an enumeration whose closed set is a 2-of-8 subset of the register: delegating there would
    silently WIDEN the value domain. Exactness costs recall and buys zero false positives."""
    regs = {}
    for p in b.root.rglob("*.csv"):
        if any(part in _SKIP_PARTS for part in p.parts):
            continue
        try:
            with p.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        if not rows or not rows[0]:
            continue
        regs[str(p.relative_to(b.root))] = {
            c: {str(r[c]).strip() for r in rows if r.get(c)} for c in rows[0]}
    out = []
    for rel, d in b.concepts.items():
        v = d.get("values") or {}
        items = v.get("items")
        if not isinstance(items, list) or v.get("realized_by"):
            continue
        codes = {str(i.get("code") or i.get("value") or i.get("id"))
                 for i in items if isinstance(i, dict)}
        codes = {c for c in codes if c and c != "None"}
        if not codes:
            continue
        for rf, cols in sorted(regs.items()):
            for cn, vals in cols.items():
                if vals == codes:
                    out.append(f"{rel}: {len(codes)} items == {rf}#{cn} "
                               f"(closure: {v.get('closure')})")
                    break
            else:
                continue
            break
    return out


def section_c(b: Bundle, fw: Framework, ref: Bundle | None) -> tuple:
    caps = build_capabilities(b, fw)
    refcaps = {c.key: c for c in build_capabilities(ref, fw)} if ref else {}
    for c in caps:
        c.instead = probe_alternatives(c, b, fw)
        r = refcaps.get(c.key)
        if r:
            c.ref_used, c.ref_scope = r.used, "reference bundle"

    unadopted = [c for c in caps if c.used == 0]
    proven = [c for c in unadopted if c.ref_used > 0]
    substituted = [c for c in caps if c.instead]
    out = []
    if unadopted:
        out.append(Finding(
            code="C1-unadopted", section="C", severity=WARN if proven else INFO,
            blast=len(unadopted),
            headline=(f"{len(unadopted)} of {len(caps)} MAC capabilities are offered and unused"
                      + (f" — {len(proven)} of them PROVEN usable by the reference bundle" if proven else "")),
            cost=("each unused mechanism is a determinism the model does not have: its slot's meaning stays "
                  "prose an agent interprets, instead of a canon, a shape, or a resolved term. The bundle is "
                  "not missing FEATURES — it is missing the places where a machine could have checked it"),
            detail=([f"     PROVEN elsewhere, unused here: "
                     f"{', '.join(c.key.split('  ')[0] for c in sorted(proven, key=lambda c: -c.ref_used))}"]
                    if proven else []),
            expires=("blocking per-capability only when the project adopts it and then regresses; a bundle "
                     "may legitimately decline a mechanism, but not silently — declining is an out_of_scope entry with a reason")))
    if substituted:
        out.append(Finding(
            code="C2-substituted", section="C", severity=WARN, blast=len(substituted),
            headline=(f"{len(substituted)} capabilit{'y has' if len(substituted) == 1 else 'ies have'} a "
                      f"SUBSTITUTE standing in the bundle — the work was done, outside the slot MAC offers"),
            cost=("a substitute is more expensive than an absence: it has to be maintained, it cannot be "
                  "projected, and the next reader has to discover it. Every one of these is a migration "
                  "with a known destination, not a feature request"),
            detail=[f"     {c.key.split('  ')[0]:44s} -> {c.instead[0][:120]}" for c in substituted],
            expires=("blocking when the substitute and the slot both carry the fact — two homes for one "
                     "fact is drift, and that is what the single-source gate already errors on")))
    return caps, out


# ═════════════════════════════════════════════════════════════ rendering

def de(n: int) -> str:
    """German locale grouping."""
    return f"{n:,}".replace(",", ".")


def pct(a: int, b: int) -> str:
    if not b:
        return "0,00 %"
    return f"{a * 100 / b:.2f}".replace(".", ",") + " %"


BAR = "═" * 100


def render(b: Bundle, fw: Framework, findings: list, caps: list, ref: Bundle | None, strict: bool) -> int:
    print(BAR)
    print(f"MAC CONFORMANCE — {b.root}")
    print(f"framework: {MAC_ROOT}   ·   schema {json.loads((MAC_ROOT / 'mac.schema.json').read_text()).get('title','')}")
    if ref:
        print(f"reference (read for adoption evidence only, never a target): {ref.root}")
    print(BAR)

    by_section = defaultdict(list)
    for f in findings:
        by_section[f.section].append(f)

    titles = {"A": "A · LEVEL COVERAGE                     (CONFORMANCE §1)",
              "B": "B · PROFILE AND EXTENSION DISCIPLINE   (CONFORMANCE §2)",
              "C": "C · CAPABILITY ADOPTION                (the red line)"}

    for sec in ("A", "B"):
        print(f"\n{titles[sec]}\n{'─' * 100}")
        for f in sorted(by_section[sec], key=lambda x: x.rank()):
            _print_finding(f)

    # --- section C renders the register itself, not just findings
    print(f"\n{titles['C']}\n{'─' * 100}")
    adopted = [c for c in caps if c.used > 0]
    print(f"  {len(caps)} optional mechanisms found in the framework "
          f"· {len(adopted)} adopted · {len(caps) - len(adopted)} unadopted\n")
    hdr = f"  {'':2s} {'MECHANISM':52s} {'HERE':>7s} {'REF':>6s}"
    print(hdr)
    print(f"  {'─' * 96}")
    #  ·  not adopted at all      ◐  adopted somewhere, with a substitute still standing      ✓  adopted
    for c in sorted(caps, key=lambda c: (c.used > 0 and not c.instead, c.used > 0, -len(c.instead), c.key)):
        mark = "·" if not c.used else ("◐" if c.instead else "✓")
        refc = de(c.ref_used) if ref else "—"
        print(f"  {mark:2s} {c.key[:52]:52s} {de(c.used):>7s} {refc:>6s}")
        if c.used and not c.instead:
            continue
        print(f"       offered by: {c.offered_by}")
        print(f"       slot:       {c.slot}")
        for line in c.instead:
            print(f"       INSTEAD:    {line}")
        if ref and c.ref_used and not c.used:
            print(f"       PROVEN:     the reference bundle uses this at {de(c.ref_used)} site(s) — "
                  f"the mechanism works in practice")
    print()
    for f in sorted(by_section["C"], key=lambda x: x.rank()):
        _print_finding(f)

    # ── D ──────────────────────────────────────────────────────────────────
    yamls = [f for f in b.all_files if f.endswith(".yaml")]
    outside = len(yamls) - len(b.routed)
    l3 = next((f.blast for f in findings if f.code == "A4-l3-unratified"), 0)
    blocking = [f for f in findings if f.severity == BLOCKING]
    undeclared = sum(f.blast for f in findings if f.code.startswith(("B5-", "B6-", "B7-")))
    substituted = len([c for c in caps if c.instead])

    print(f"\nD · VERDICT\n{'─' * 100}")
    print(f"  {len(caps)} MAC capabilities offered · {len(adopted)} adopted · "
          f"{len(caps) - len(adopted)} unadopted · {substituted} with a substitute standing")
    print(f"  {de(outside)} of {de(len(yamls))} yaml files outside L1 ({pct(outside, len(yamls))}) · "
          f"{de(undeclared)} files the schema has no definition for · "
          f"{de(l3)} unratified L3 claims · {len(blocking)} blocking-class finding(s)")

    print(f"\n  BLOCKING SLATE — what SHOULD fail a build, and when\n{'  ' + '─' * 98}")
    for f in sorted(findings, key=lambda x: x.rank()):
        tag = "BLOCKS NOW " if f.severity == BLOCKING else "warn-first "
        print(f"  {tag}{f.code:32s} {f.expires}")

    fail = bool(blocking) and strict
    print(f"\n  EXIT {1 if fail else 0}"
          + ("  — blocking-class findings present and --strict given" if fail else
             f"  — warn-first; {len(blocking)} blocking-class finding(s) would fail under --strict"))
    print(BAR)
    # CORE §2 wants exactly one PASS:/FAIL: line, LAST, carrying a denominator. Every number above
    # already exists; this restates none of them, it only closes the report with the one line a
    # caller (this framework's own gate runner, CI) can grep for.
    verdict = "FAIL" if fail else "PASS"
    mode = "strict" if strict else "warn-first"
    print(f"{verdict}: check_conformance — {len(adopted)} of {len(caps)} MAC capabilities adopted, "
          f"{de(outside)} of {de(len(yamls))} yaml file(s) outside L1, {len(blocking)} "
          f"blocking-class finding(s) ({mode})")
    return 1 if fail else 0


def _print_finding(f: Finding):
    print(f"\n  [{f.severity}] {f.code}")
    print(f"  {f.headline}")
    print(f"    COST IF LEFT: {f.cost}")
    for d in f.detail:
        print(f"  {d}")
    if f.delegate:
        print(f"    PER-OBJECT LIST: {f.delegate}")
    if f.expires:
        print(f"    EXPIRES WHEN: {f.expires}")


# ═════════════════════════════════════════════════════════════════ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?",
                    help="the bundle to measure (required unless --self-test)")
    ap.add_argument("--reference", help="a second bundle, read ONLY for adoption evidence")
    ap.add_argument("--strict", action="store_true", help="blocking-class findings fail the run")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return _self_test()

    # A GATE MUST NEVER BE ABLE TO PASS HAVING MEASURED NOTHING. `load_bundle` walks the root with
    # `Path.rglob`, which silently yields zero files for a path that does not exist — so a typo'd or
    # deleted bundle used to produce a full conformance report of zeroes ("0 of 0 yaml files outside
    # L1", 31 capabilities "offered and unused") ending in "EXIT 0", indistinguishable from a real,
    # clean, tiny bundle. Both are COULD-NOT-RUN.
    if not args.bundle:
        ap.error("the following arguments are required: bundle (unless --self-test is given)")
    bundle_root = Path(args.bundle).resolve()
    if not bundle_root.is_dir():
        print(f"could not run: {bundle_root} is not a directory", file=sys.stderr)
        return 2
    ref_root = None
    if args.reference:
        ref_root = Path(args.reference).resolve()
        if not ref_root.is_dir():
            print(f"could not run: --reference {ref_root} is not a directory", file=sys.stderr)
            return 2

    fw = introspect_framework()
    b = load_bundle(bundle_root)
    ref = load_bundle(ref_root) if ref_root else None

    findings = section_a(b, fw) + section_b(b, fw)
    caps, cfind = section_c(b, fw, ref)
    findings += cfind

    if args.json:
        print(json.dumps({
            "bundle": str(b.root),
            "findings": [f.__dict__ for f in sorted(findings, key=lambda x: x.rank())],
            "capabilities": [c.__dict__ for c in caps],
        }, indent=2, default=str))
        return 1 if (args.strict and any(f.severity == BLOCKING for f in findings)) else 0

    return render(b, fw, findings, caps, ref, args.strict)


# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class this CLI wrapper is responsible for, plus a clean fixture
# that must reach a real verdict. section_a/b/c and render() are exercised as-is, unmodified by
# this fix — only the missing-root / missing-reference refusals and the final PASS:/FAIL: line are
# new. Fixtures are domain-neutral on purpose: this repo is public.
# ---------------------------------------------------------------------------------------------

def _minimal_bundle(root) -> str:
    """The smallest tree `load_bundle` can walk without crashing: a manifest and one concept."""
    import pathlib as _pl

    import yaml as _yaml

    r = _pl.Path(root)
    (r / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
    (r / "mac.project.yaml").write_text(_yaml.safe_dump({"name": "self-test-bundle"}),
                                        encoding="utf-8")
    (r / "ontology" / "concepts" / "widget.yaml").write_text(_yaml.safe_dump({
        "concept": {"name": "Widget", "class": "entity"},
        # confidence "I" (inferred), deliberately NOT "C" (expert-confirmed) — a "C" with no
        # ratification evidence is itself a BLOCKING finding (A4-l3-unratified) this fixture is not
        # trying to provoke; that reject class belongs to section_c's own tests, not this CLI
        # wrapper's could-not-run refusals.
        "metadata": {"provenance": "hand-authored", "confidence": "I"},
    }), encoding="utf-8")
    return str(r)


def _run(argv: list) -> int:
    saved = sys.argv
    sys.argv = ["check_conformance.py", *argv]
    try:
        return main()
    except SystemExit as exc:
        # argparse's own `ap.error()` (a malformed invocation) raises SystemExit(2) rather than
        # returning — caught here so the missing-bundle-argument case is a comparable exit code
        # like every other reject class, not a self-test that aborts itself.
        return exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.argv = saved


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1 · no bundle argument at all, and not --self-test — a usage error, exit 2 (argparse's
        #     own could-not-run code), never a silent pass.
        got = _run([])
        if got != 2:
            failures.append(f"no-bundle-argument: expected exit 2, got {got}")

        # 2 · a bundle path that does not exist — the defect this fix exists for: it used to walk
        #     to zero files and print a full report ending EXIT 0.
        missing = base / "does-not-exist"
        got = _run([str(missing)])
        if got != 2:
            failures.append(f"nonexistent-bundle: expected exit 2, got {got}")

        # 3 · a real bundle, but a --reference that does not exist.
        clean = _minimal_bundle(base / "clean")
        got = _run([clean, "--reference", str(base / "no-such-reference")])
        if got != 2:
            failures.append(f"nonexistent-reference: expected exit 2, got {got}")

        # 4 · clean fixture: a real, minimal bundle reaches an actual verdict (warn-first, so a
        #     bundle adopting nothing still exits 0 — see CONFORMANCE.md).
        got = _run([clean])
        if got != 0:
            failures.append(f"clean-bundle: expected exit 0 (warn-first), got {got}")

        # 5 · liveness under --strict: without a single MAC capability adopted, section C's
        #     C1-unadopted finding is WARN-class, not BLOCKING, so --strict must still exit 0 here —
        #     this asserts the plumbing carries --strict through rather than asserting a specific
        #     blocking class exists in this minimal fixture (that population belongs to section_c's
        #     own tests, not this CLI wrapper's).
        got = _run([clean, "--strict"])
        if got != 0:
            failures.append(f"clean-bundle --strict: expected exit 0, got {got}")

    total = 5
    if failures:
        print(f"FAIL: check_conformance self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_conformance self-test — {total}/{total} (missing bundle argument, a "
          f"nonexistent bundle, and a nonexistent --reference all refuse; a minimal real bundle "
          f"reaches a verdict under both default and --strict)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
