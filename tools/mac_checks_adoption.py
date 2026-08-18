#!/usr/bin/env python3
"""mac_checks_adoption — MAC005 capability-unadopted. The one question no gate could ask.

THE HOLE
--------
Every other gate asks "is what you wrote legal?". This one asks the opposite question: **MAC offers a
mechanism, it is the right way to do the thing, and the bundle does not use it.** Nothing noticed
before, because nothing looked. Three regressions on one live bundle, every gate green throughout:

  * `grounding.field_roles` — offered since 0.1.7, shipped with a resolver AND a cross-file shape.
    Used on 28 concepts / 167 bindings by a sibling bundle. Used on 0 of 22 here.
  * `values.realized_by` register delegation — the concept restates a value set a pinned register
    already holds, verbatim, and nothing ties the two together.
  * `tools/canon/` — two implemented canons bound to nothing, in a bundle with 59 hand-copied rules.

WHY IT IS MAC005 AND NEVER AN ERROR
A bundle may decline a mechanism for a good reason, and this gate does not know the reason. An
unadoption that blocked the build would be the toolchain dictating design. `MAC005` is therefore
WARNING at most — enforced structurally here: `_severity()` cannot return `ERROR`.

NOTHING IS HARDCODED — the register is DERIVED, five ways, at run time
  S1 mac.schema.json      an OPTIONAL property whose own description carries a version stamp
                          (`v0.1.x` / `v0.5`) or the word OPTIONAL. MAC stamps the version into the
                          description at the moment it ADDS an offer (CONFORMANCE §6 schema_version
                          discipline), so the schema is self-describing about what it OFFERS versus
                          what it REQUIRES. A capability added to MAC tomorrow is measured tomorrow.
  S2 mac_shapes.yaml      every built-in shape's constrained slot. A shape is machinery; the slot it
                          constrains is a slot MAC expects filled.
  S3 mac_vocabulary.yaml  every `mac.<namespace>` NAMED IN A SCHEMA DESCRIPTION — see the axis_kind
                          guard below — plus the `mac.canon` registry × the executable library.
  S4 tools/*.py           bundle-relative artifacts a framework tool searches for BY NAME, and the
                          manifest keys a framework tool reads. The tools are the single home of
                          "what MAC knows how to find"; read as source, never executed.
  S5 CONFORMANCE.md §6    the version bullets. Stamps `since` on every derived offer, and surfaces
                          mechanisms the PROSE offers that the schema never gave a slot (the profile).

FIVE GUARDS, EACH MEASURED BEFORE IT WAS TRUSTED. The naive version of this check fires on all five:

  G1 SCHEMA-ENUMERATED VOCABULARIES.   `mac.identity_kind` is referenced 1× in the whole model, so a
     reference-counting probe reports it unadopted. It is not: the schema spells the seven terms as a
     bare `enum` at `concept.identity.kind`, so `kind: code` IS the legal form and 22 of 22 concepts
     adopt it. A vocabulary whose terms the schema enumerates at its own slot is measured BY THE SLOT.
     Same for `additivity: additive`. Without G1: 2 false findings.
  G2 NON-BUNDLE-FACING VOCABULARIES.   `mac.binding_mode` says in its own definition that it is a
     per-question runtime classification and NOT a property a concept declares; `mac.aggregation_effect`
     is referenced only from inside `mac.MeasureType`'s own cells. Neither is named by any schema
     description. A bundle cannot adopt them and must not be charged for them. Without G2: 2 false
     findings, one of which a sibling tool currently reports as "PROVEN usable by the reference".
  G3 APPLICABILITY.   An offer is only chargeable where its PARENT OBJECT exists. `edges[].aliases` on
     a bundle with no business edges, `values.realized_by` on a bundle with no enumerations, is not a
     defect. Zero applicable sites ⇒ INFO, never WARNING.
  G4 FRAMEWORK-SIDE INCOMPLETENESS.   The `x-` PROFILE is offered by CONFORMANCE §2 and `mac.schema.json`
     defines no slot for it — the bundle has nowhere legal to write one. Charging the bundle for that
     is the gate blaming the reader for the book. Such offers are reported INFO and against the
     FRAMEWORK. Four registered canons (`alias_resolve`, `enum_from_register`, `grouping_from_register`,
     `relation_alias_resolve`) have no executable; two executable ones (`tools/canon/rules.py`) are not
     in the registry, so `check_references` would ERROR on a bundle that bound them. Reported as
     framework state, not bundle debt.
  G5 PROSE SLOTS ARE NOT MECHANISMS.   `contract.rules[].why` is unfilled on 83 of 83 rules here and it
     is NOT a MAC005: it is a documentation field with no machinery behind it, so its absence is a
     COVERAGE fact (MAC011), not an unadopted capability. S1 excludes it automatically — it carries no
     version stamp — which is the point of deriving rather than listing.

FANOUT. One Diagnostic per MECHANISM, carrying every applicable site as a Witness. Fifteen mechanisms
are fifteen findings because each has a different remedy — that is not fanout. Fanout would be one
finding per concept, and `field_roles` unused on 22 concepts is exactly ONE diagnostic with 22
witnesses. The distinction is the remedy: same remedy ⇒ one finding.

WHAT THE BUNDLE DOES INSTEAD. A gate that says only "unused" is a scold. The useful half is the
SUBSTITUTE the project built, because that is the thing that has to be migrated or defended — and
every probe below is MEASURED evidence from the bundle, never an assertion about what it "should"
have. A substitute is more expensive than an absence: it must be maintained, it cannot be projected,
and the next reader has to discover it.

THE REFERENCE BUNDLE is read ONLY to establish that a mechanism is usable in practice, as an adoption
count. It is evidence, never a target: `check()` takes its diagnostics from `root` alone and there is
no code path that can emit a finding about the reference.

Usage:
  tools/mac_checks_adoption.py <bundle> [--reference <bundle>] [--json] [--show info]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mac_diag as D  # noqa: E402  — the frozen diagnostic contract

# The framework introspection and the bundle loader live in check_conformance today. They are shared
# infrastructure, not adoption facts, and are IMPORTED rather than restated — a second home for
# "what MAC offers" inside the tool whose job is to find second homes would be self-refuting. When the
# compiler driver lands they belong in a neutral module; the import direction is one-way until then.
from check_conformance import (  # noqa: E402
    Framework, introspect_framework, load_bundle, walk, _SKIP_PARTS,
)

MAC_ROOT = Path(__file__).resolve().parent.parent
SOURCE = "mac_checks_adoption"

# ── kinds of offer, and what "used" means for each ────────────────────────────────────────────────
SLOT, VOCAB, LIBRARY, ARTIFACT, MANIFEST, PROSE = "slot", "vocabulary", "library", "artifact", "manifest", "prose"

_IDX = re.compile(r"\[\d+\]")
_VERSION = re.compile(r"\bv?(0\.\d+(?:\.\d+)?)\b")


def de(n, decimals: int = 0) -> str:
    """de-DE: grouping '.', decimal ','. The operator reads every number in this locale."""
    s = f"{n:,.{decimals}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# ══════════════════════════════════════════════════════════ the offer register (DERIVED)

@dataclass
class Offer:
    key: str                     # the mechanism, as a reader names it
    kind: str                    # SLOT | VOCAB | LIBRARY | ARTIFACT | MANIFEST
    slot: str                    # where a bundle writes it (dotted path, filename, or reference form)
    since: str = ""              # the schema generation that OFFERED it (CONFORMANCE §6)
    offered_by: str = ""         # the framework evidence, named so a reader can check it
    parent: str = ""             # G3 — the object whose presence makes this offer applicable
    framework_gap: str = ""      # G4 — set when MAC cannot honour the offer today
    detail: str = ""             # anything a reader needs that the columns do not carry
    tier: str = "dated"          # dated = MAC recorded the addition; undated = it did not


@dataclass
class Adoption:
    offer: Offer
    used: int = 0
    sites: list = field(default_factory=list)          # where it IS used
    applicable: int = 0
    applicable_sites: list = field(default_factory=list)   # where it COULD be used and is not
    instead: list = field(default_factory=list)        # measured substitutes
    ref_used: int = 0
    ref_scope: str = ""

    @property
    def adopted(self) -> bool:
        return self.used > 0


# ── S5: CONFORMANCE.md §6 — the changelog IS the "offered since" register ─────────────────────────

def _since_index(mac_root: Path = MAC_ROOT) -> dict:
    """token -> earliest schema generation whose §6 bullet names it.

    §6 is written as `- **`0.1.7`** adds, on the same contract: … **`grounding.field_roles`** …`. Every
    identifier MAC considers part of that release is backticked in its own bullet, so the changelog is
    a machine-readable offer register and nobody has to remember which release shipped what."""
    text = (mac_root / "CONFORMANCE.md").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for para in re.split(r"\n(?=- )", text):
        m = re.match(r"-\s+\*\*`(\d+\.\d+\.\d+)`\*\*", para)
        if not m:
            continue
        ver = m.group(1)
        for tok in re.findall(r"`([A-Za-z0-9_.\[\]\-]+)`", para):
            tok = tok.strip("`")
            if tok == ver:
                continue
            prev = out.get(tok)
            if prev is None or _vkey(ver) < _vkey(prev):
                out[tok] = ver
    return out


def _vkey(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def _since_for(slot: str, description: str, index: dict) -> str:
    """The generation that offered a slot.

    THE SLOT'S OWN DESCRIPTION FIRST, the changelog second. The changelog is indexed by backticked
    TOKEN, and a token can be ambiguous across releases: `aliases` appears in the 0.1.12 bullet (the
    business-edge relationAliasBlock) and `values.aliases` is stamped v0.1.9 in its own description.
    Token-first dated the enum alias block three releases late. The per-slot stamp is unambiguous when
    it exists; the changelog covers the slots whose description carries no stamp."""
    m = _VERSION.search(description or "")
    if m:
        return m.group(1)
    leaf = slot.rsplit(".", 1)[-1]
    cands = [slot, slot.replace("[]", "")]
    if "_" in leaf:          # a generic leaf (`kind`, `type`, `note`) matches the wrong bullet: the
        cands += [leaf, f"contract.{leaf}", f"grounding.{leaf}"]   # 0.1.8 bullet dates `kind` on the
    for cand in cands:                                             # TransformFile, not on identity
        if cand in index:
            return index[cand]
    return "undated"


# ── S1: mac.schema.json — the optional, version-stamped properties ────────────────────────────────

def _def_slot_names(schema: dict) -> dict:
    """`$def` name -> the property name an AUTHOR writes it under.

    `enumerationValues` is a $def name; nobody ever types it. Authors write `values:`, because
    `ConceptFile.properties.values` is what `$ref`s it. Without this map the register reports a slot
    called `enumerationValues.aliases`, which is unfindable in any bundle and unactionable in a report."""
    out: dict[str, str] = {}

    def visit(node):
        if isinstance(node, dict):
            for k, v in (node.get("properties") or {}).items():
                ref = v.get("$ref") if isinstance(v, dict) else None
                if isinstance(ref, str) and ref.startswith("#/$defs/"):
                    out.setdefault(ref.rsplit("/", 1)[-1], k)
            for v in node.values():
                visit(v)
        elif isinstance(node, list):
            for v in node:
                visit(v)

    visit(schema)
    return out


def _schema_offers(fw: Framework, since: dict) -> tuple:
    """Every OPTIONAL property of the schema, split into two tiers.

    DATED   — its description carries a version stamp or says OPTIONAL. CONFORMANCE §6 requires an
              addition to be recorded against a generation, so MAC stamps the version into the
              description at the moment it ADDS an offer. The date is MAC's OWN marker that something
              was offered, which is why this register tracks the framework instead of a memory of it.
    UNDATED — optional, and MAC never dated it. `contract.rules[].enforced_by` lives here: it is a real
              seam (a rule naming the deterministic backstop that fails if the rule is broken) and no
              derived register can tell it from `note` or `label`, because the framework recorded
              nothing about it. That blind spot is the framework's, and it is REPORTED rather than
              patched over with a keyword list — a hand-kept list of "the ones I remember" is the exact
              failure this whole file exists to end."""
    schema = fw.schema
    defslot = _def_slot_names(schema)
    dated: list[Offer] = []
    undated: list[Offer] = []
    seen: set[str] = set()

    def dotted(jsonptr: str, key: str) -> str:
        """A schema pointer -> the dotted slot an author actually writes.
        `/$defs/contract/properties/rules/items/properties/realized_by` -> `contract.rules[].realized_by`"""
        parts = [p for p in jsonptr.split("/") if p and p not in ("$defs", "properties")]
        out: list[str] = []
        for i, p in enumerate(parts):
            if p == "items":
                if out:
                    out[-1] += "[]"
                continue
            if p.endswith("File") or p in ("oneOf", "allOf", "anyOf") or p.isdigit():
                continue
            out.append(defslot.get(p, p) if i == 0 else p)
        out.append(key)
        dedup = [p for i, p in enumerate(out) if i == 0 or p != out[i - 1]]
        return ".".join(dedup)

    def visit(node, ptr: str):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                req = set(node.get("required") or [])
                for k, v in props.items():
                    if k in req or not isinstance(v, dict):
                        continue
                    desc = v.get("description") or ""
                    if not desc and isinstance(v.get("$ref"), str):    # a $ref'd slot inherits its
                        tgt = (schema.get("$defs") or {}).get(v["$ref"].rsplit("/", 1)[-1], {})
                        desc = tgt.get("description") or ""            # description from the $def
                    slot = dotted(ptr, k)
                    if slot in seen or "." not in slot:
                        continue                       # a bare top-level key is a document, not a slot
                    # A DERIVED slot is not an unadopted capability. v0.1.16 made
                    # `concept.semantics.additivity` derivable from (measure_type x axis_kind), so its
                    # ABSENCE is the desired state — and this check promptly reported 9 sites as
                    # failing to adopt the very block that was just removed on purpose, i.e. it told
                    # the reader to re-add what the framework had stopped asking for. A slot says so
                    # itself via `x-derived-from`; nothing here carries a list of special cases.
                    if v.get("x-derived-from"):
                        continue
                    seen.add(slot)
                    o = Offer(key=slot, kind=SLOT, slot=slot,
                              since=_since_for(slot, desc, since),
                              offered_by=f"mac.schema.json — {(desc.split('—')[0].strip() or 'optional key')[:96]}",
                              parent=slot.rsplit(".", 1)[0], detail=desc)
                    (dated if (_VERSION.search(desc) or "OPTIONAL" in desc) else undated).append(o)
            for k, v in node.items():
                visit(v, f"{ptr}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                visit(v, f"{ptr}/{i}")

    visit(schema, "")
    return dated, undated


# ── S2: mac_shapes.yaml — the slots the built-in shapes police ────────────────────────────────────

# Three built-in shapes are RELATIONAL: their subject is implied by the constraint kind's name rather
# than written as a path, because the check is "left set ⊆ right set" across two files. Framework-level
# and domain-neutral; the shape ids themselves are read from the file.
_SHAPE_KIND_SLOT = {
    "rule_binds_grounded": "contract.rules[].binds",
    "field_roles_grounded": "grounding.field_roles",
    "join_rule_grounded": "edges[].join_rule",
}


def _shape_offers(fw: Framework, since: dict, known: set) -> list:
    out = []
    for sh in fw.shapes:
        c = sh.get("constraint") or {}
        path = c.get("path") or _SHAPE_KIND_SLOT.get(c.get("kind"))
        if not path:
            continue
        if path in known:              # S1 already registered this slot; a shape does not re-offer it
            continue
        sev = sh.get("severity", "?")
        note = f"built-in shape `{sh['id']}` ({sev}) in mac_shapes.yaml — machinery, run cross-file"
        out.append(Offer(key=path, kind=SLOT, slot=path,
                         since=_since_for(path, sh.get("description", ""), since),
                         offered_by=note, parent=path.rsplit(".", 1)[0]))
    return out


# ── S3: mac_vocabulary.yaml — the bundle-facing vocabularies, and the canon library ───────────────

def _vocab_offers(fw: Framework, since: dict) -> list:
    """G2 — a vocabulary is BUNDLE-FACING only if a schema description names it. `mac.binding_mode`
    documents itself as a per-question runtime classification, not a declared property, and
    `mac.aggregation_effect` is referenced only from inside `mac.MeasureType`'s own additivity cells.
    Neither is named by any schema property, so neither is a slot a bundle could fill; charging a
    bundle for not referencing them is the check inventing a requirement."""
    schema_text = json.dumps(fw.schema)
    out = []
    for name, blk in fw.vocab.items():
        if name == "metadata" or not isinstance(blk, dict):
            continue
        terms = blk.get("terms") or blk.get("members") or {}
        if not terms:
            continue
        if not re.search(rf"mac\.{re.escape(name)}\b", schema_text):
            continue                                        # G2
        slots = _vocab_slots(fw.schema, name)
        # G1 — where the schema spells the same terms as a bare enum, the bare value IS the reference
        bare = sorted({s for s in slots if set(terms) & set(fw.schema_enums.get(s.rsplit(".", 1)[-1], ()))})
        out.append(Offer(
            key=f"mac.{name}", kind=VOCAB,
            slot=(" · ".join(slots) if slots else f"any string, as `mac.{name}.<term>`"),
            since=_since_for(f"mac.{name}", "", since),
            offered_by=(f"mac_vocabulary.yaml, {len(terms)} terms — resolved by check_references; "
                        f"an unknown term is an ERROR"),
            parent=(slots[0].rsplit(".", 1)[0] if slots else ""),
            detail=("|".join(slots)),
            framework_gap=("" if not bare else
                           f"the schema also spells these terms as a bare enum at {', '.join(bare)}, so "
                           f"the bare value is the legal form there and adoption is measured by the slot")))
    return out


def _vocab_slots(schema: dict, ns: str) -> list:
    """Every dotted slot whose description names `mac.<ns>` — the places an author writes the term."""
    hits: list[str] = []

    def visit(node, trail):
        if isinstance(node, dict):
            for k, v in (node.get("properties") or {}).items():
                if isinstance(v, dict) and f"mac.{ns}" in (v.get("description") or ""):
                    hits.append(".".join([t for t in trail if t] + [k]))
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    for pk, pv in v.items():
                        visit(pv, trail + [pk])
                elif k == "items":
                    visit(v, (trail[:-1] + [trail[-1] + "[]"]) if trail else trail)
                elif k in ("$defs",) and isinstance(v, dict):
                    for dk, dv in v.items():
                        visit(dv, [] if dk.endswith("File") else [dk])
                elif isinstance(v, (dict, list)) and k not in ("enum", "required"):
                    visit(v, trail)
        elif isinstance(node, list):
            for v in node:
                visit(v, trail)

    visit(schema, [])
    # keep the shortest spelling of each leaf; `concept.identity.kind` beats `identity.kind`
    best: dict[str, str] = {}
    for h in hits:
        leaf = h.rsplit(".", 1)[-1]
        if leaf not in best or len(h) > len(best[leaf]):
            best[leaf] = h
    return sorted(set(best.values()))


def _library_offer(fw: Framework, since: dict) -> Offer:
    """The canon library: the registry × the executables × the schema slots that accept a binding."""
    registered, executable = set(fw.canon_registered), set(fw.canon_executable)
    # tools/canon/ may hold sub-modules with their own CANONS map (rules.py does). Anything callable
    # there is IMPLEMENTED; anything absent from mac_vocabulary.yaml is UNBINDABLE, because
    # check_references errors on a canon name the registry does not define.
    extra: set[str] = set()
    cdir = MAC_ROOT / "tools" / "canon"
    for p in sorted(cdir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        for m in re.finditer(r'^\s*"(mac\.canon\.(\w+))"\s*:', p.read_text(encoding="utf-8"), re.M):
            extra.add(m.group(2))
    implemented = executable | extra
    unbindable = sorted(implemented - registered)
    unimplemented = sorted(registered - implemented)
    gap = []
    if unbindable:
        gap.append(f"{len(unbindable)} implemented canon(s) are absent from the mac.canon registry "
                   f"({', '.join(unbindable)}) — check_references ERRORS on an unknown canon name, so a "
                   f"bundle CANNOT bind them today")
    if unimplemented:
        gap.append(f"{len(unimplemented)} registered canon(s) have no executable in tools/canon/ "
                   f"({', '.join(unimplemented)}) — declarative registry entries, realized by the consumer")
    return Offer(
        key="the canon library (mac.canon.* bindings)", kind=LIBRARY,
        slot=" · ".join(sorted({s.split("/")[-2] if s.endswith("/realized_by") else s.rsplit("/", 1)[-1]
                                for s in fw.canon_slots})) or "realized_by",
        since=_since_for("mac.canon", "v0.1.9", since),
        offered_by=(f"{de(len(fw.canon_slots))} schema slots accept a canonBinding; "
                    f"{de(len(registered))} canons registered; {de(len(implemented))} implemented in tools/canon/"),
        parent="realized_by",
        framework_gap=" · ".join(gap))


# ── S4: tools/*.py — artifacts and manifest keys the framework searches for ───────────────────────

_RGLOB = re.compile(r"rglob\(\s*[\"']([\w.\-]+\.ya?ml)[\"']\s*\)")
_BASENAME_EQ = re.compile(r"basename\([^)]*\)\s*==\s*[\"']([\w.\-]+\.ya?ml)[\"']")
_MANIFEST_KEY = re.compile(r"get\(\s*[\"'](\w+)[\"']\s*\)\s*or\s*\{\}\s*\)\s*\.\s*get\(\s*[\"'](\w+)[\"']")


MANIFEST_FILE = "mac.project.yaml"
_MANIFEST_WINDOW = 25        # lines


def _tool_offers(since: dict) -> list:
    """Artifacts a framework tool LOOKS FOR BY NAME, and manifest keys it READS.

    Read as text, never executed. The tools are the single home of "what MAC knows how to find", so a
    discovery rule added to a checker tomorrow becomes an offer tomorrow. A wildcard glob is not a
    discovery rule — only a LITERAL name is, because only a literal name is a contract with the author
    about what to call the file.

    THE MANIFEST WINDOW. The first cut matched every `.get('a') or {}).get('b')` chain in a tool that
    mentioned the manifest anywhere in the file, and reported EIGHT manifest keys — `concept.class`,
    `contract.rules`, `grounding.sources` and friends, which are reads of a CONCEPT document, not of the
    project manifest. Exactly one of the eight was real. The chain now has to occur within 25 lines of a
    line that names the manifest file, which is the distance a `proj = .../mac.project.yaml` assignment
    sits from the `.get()` that unpacks it, and the register drops from eight to one."""
    self_name = Path(__file__).name
    arts: dict[str, set] = defaultdict(set)
    keys: dict[tuple, set] = defaultdict(set)
    for f in sorted((MAC_ROOT / "tools").glob("*.py")):
        if f.name == self_name:
            continue
        src = f.read_text(encoding="utf-8")
        for m in _RGLOB.finditer(src):
            arts[m.group(1)].add(f.name)
        for m in _BASENAME_EQ.finditer(src):
            arts[m.group(1)].add(f.name)
        lines = src.splitlines()
        near = {i for i, ln in enumerate(lines) if MANIFEST_FILE in ln}
        if near:
            for i, ln in enumerate(lines):
                if any(abs(i - j) <= _MANIFEST_WINDOW for j in near):
                    for m in _MANIFEST_KEY.finditer(ln):
                        keys[(m.group(1), m.group(2))].add(f.name)
    out = []
    for name, tools in sorted(arts.items()):
        if (MAC_ROOT / name).exists() or name == MANIFEST_FILE:
            continue        # a framework-own file, or the manifest itself: required, not offered
        out.append(Offer(
            key=f"project {name}", kind=ARTIFACT, slot=f"<anywhere>/{name}",
            since=_since_for(name, "", since),
            offered_by=f"{', '.join(sorted(tools))} searches for `{name}` by name",
            parent=""))
    for (a, b), tools in sorted(keys.items()):
        out.append(Offer(
            key=f"{MANIFEST_FILE}#{a}.{b}", kind=MANIFEST, slot=f"{MANIFEST_FILE}#{a}.{b}",
            since=_since_for(b, "", since),
            offered_by=f"{', '.join(sorted(tools))} reads it from the project manifest",
            parent=""))
    return out


# ── S5 (second half): mechanisms the PROSE offers with no schema slot ─────────────────────────────

def _prose_offers(fw: Framework, since: dict) -> list:
    """CONFORMANCE §2 rules that an `x-` key with no PROFILE entry is undeclared debt. There is no
    profile slot in mac.schema.json and no tool that reads one. G4: the bundle has nowhere legal to
    write it, so this is reported INFO and against the FRAMEWORK — a gate that charges a reader for a
    chapter the book never printed is not evidence, it is noise."""
    text = (MAC_ROOT / "CONFORMANCE.md").read_text(encoding="utf-8")
    if "profile" not in text:
        return []
    # a PROPERTY named `profile`, not the WORD "profile" — the schema says "lineage-complete profile"
    # in prose four times and defines no such key, and a substring test reads that as an implemented slot
    has_slot = _has_property(fw.schema, "profile")
    return [Offer(
        key="x- extension profile (CONFORMANCE §2)", kind=PROSE,
        slot="mac.project.yaml#profile — the x- keys the project uses and what each means",
        since=_since_for("profile", "", since) or "§2",
        offered_by="CONFORMANCE.md §2 — 'an x- key with no profile entry is undeclared debt, not license'",
        parent="",
        framework_gap=("" if has_slot else
                       "mac.schema.json defines no profile slot and no tool reads one — the bundle has "
                       "nowhere legal to declare, so this is FRAMEWORK debt before it is bundle debt"))]


def _has_property(schema: dict, name: str) -> bool:
    found = [False]

    def visit(node):
        if found[0]:
            return
        if isinstance(node, dict):
            if name in (node.get("properties") or {}):
                found[0] = True
                return
            for v in node.values():
                visit(v)
        elif isinstance(node, list):
            for v in node:
                visit(v)

    visit(schema)
    return found[0]


def offers(fw: Framework | None = None, with_undated: bool = True) -> list:
    """The capability register. Derived at run time from MAC's own artifacts, five ways."""
    fw = fw or introspect_framework()
    since = _since_index()
    dated, undated = _schema_offers(fw, since)
    reg = list(dated)
    have = {o.slot for o in reg}
    reg += [o for o in _shape_offers(fw, since, have) if o.slot not in have]
    reg += _vocab_offers(fw, since)
    reg.append(_library_offer(fw, since))
    reg += _tool_offers(since)
    reg += _prose_offers(fw, since)
    if with_undated:
        for o in undated:
            if o.slot not in {x.slot for x in reg}:
                o.since, o.tier = "undated", "undated"
                o.framework_gap = ("MAC never recorded this addition against a generation, so no derived "
                                   "register can tell a seam here from a prose field")
                reg.append(o)
    # The canon library subsumes the per-slot `realized_by` offers S1 finds and the `mac.canon`
    # vocabulary S3 finds. Keep the library; drop the copies — reporting one fact six times with six
    # remedies that are one remedy is the defect this toolchain calls MAC003, and a tool that commits it
    # while hunting for it has no standing.
    reg = [o for o in reg
           if not (o.kind == SLOT and o.slot.endswith("realized_by"))
           and not (o.kind == VOCAB and o.key == "mac.canon")]
    # a slot that is a proper suffix of another registered slot is the same slot, spelled shorter
    slots = {o.slot for o in reg}
    reg = [o for o in reg
           if not (o.kind == SLOT and any(s != o.slot and s.endswith("." + o.slot) for s in slots))]
    return sorted(reg, key=lambda o: (o.kind, o.key))


# ══════════════════════════════════════════════════════════ measurement

def _l1_docs(b) -> dict:
    """The L1 corpus — the documents the schema gate actually routes.

    Adoption is a statement about the MODEL. Counting a slot name bundle-wide gave 14 hits on a bundle
    whose model carries 1; the other 13 were the word appearing in an intervention register and in
    oracle prose. A word in a document MAC does not validate is not adoption of anything."""
    cache = getattr(b, "_adoption_l1", None)
    if cache is None:
        cache = {rel: d for rel, d in b.docs.items() if os.path.abspath(b.root / rel) in b.routed}
        b._adoption_l1 = cache
    return cache


def _sites(b, dotted: str, containers_only: bool = False) -> tuple:
    """Sites carrying an ANCHORED dotted slot path.

    Anchored, never name-matched: `kind` appears ~800 times in this bundle and `concept.identity.kind`
    22 — the first number says nothing about whether the identity capability is adopted.

    `containers_only` counts a hit only where the value is an object or a list — used for the
    APPLICABILITY denominator. Without it, `concept` was found at 108 sites: 22 concept documents plus
    both endpoints of all 32 edges, which name a `concept:` too. The endpoint's value is a STRING and
    the document's is a MAPPING, so the container test separates them exactly — a denominator inflated
    five-fold makes every ratio built on it meaningless, and a threshold would have guessed.

    A path ending `[]` counts LIST MEMBERS, not the list: `edges[]` is 32 edges, not one `edges:` key."""
    target = _IDX.sub("[]", dotted).lstrip(".")
    if not target:
        return 0, []
    listy = target.endswith("[]")
    stem = target[:-2] if listy else target
    n, sites = 0, []
    for rel, d in _l1_docs(b).items():
        for jpath, k, v in walk(d):
            full = _IDX.sub("[]", f"{jpath}.{k}").lstrip(".")
            hit = (full == stem) or full.endswith("." + stem)
            if not hit:
                continue
            if containers_only and not isinstance(v, (dict, list)):
                continue
            if listy:
                for i in range(len(v) if isinstance(v, list) else 0):
                    n += 1
                    sites.append((rel, f"{full}[{i}]"))
            else:
                n += 1
                sites.append((rel, full))
    return n, sites


def _measure_one(b, o: Offer, fw: Framework) -> Adoption:
    a = Adoption(offer=o)
    if o.kind in (SLOT, VOCAB):
        slots = [s for s in (o.detail.split("|") if o.kind == VOCAB and o.detail else [o.slot]) if s]
        # A vocabulary named at both `concept.identity` and `concept.identity.kind` is ONE slot spelled
        # at two depths. Keeping both counted 44 adoptions on 22 concepts — a 200 % adoption rate, which
        # is the kind of number that discredits a whole report.
        slots = sorted({s for s in slots if not any(t != s and t.startswith(s + ".") for t in slots)})
        for s in slots:
            n, sites = _sites(b, s)
            a.used += n
            a.sites += [f"{r}#{p}" for r, p in sites]
        # G3 — applicability is the presence of the PARENT object. Derived from the path, so it needs
        # no per-mechanism knowledge: `grounding.field_roles` is applicable wherever `grounding` is.
        if o.parent:
            pn, psites = _sites(b, o.parent, containers_only=True)
            have = {f"{r}#{p}" for r, p in psites}
            filled = {s.rsplit(".", 1)[0] for s in a.sites}
            a.applicable = pn
            a.applicable_sites = sorted(have - filled)
    elif o.kind == LIBRARY:
        for rel, d in _l1_docs(b).items():
            for jpath, k, v in walk(d):
                if k == "realized_by" and _names_canon(v):
                    a.used += 1
                    a.sites.append(f"{rel}{jpath}.{k}")
        for slot in ("semantics", "grounding", "values", "members", "contract.rules[]"):
            n, sites = _sites(b, slot)
            a.applicable += n
            a.applicable_sites += [f"{r}#{p}" for r, p in sites]
    elif o.kind == ARTIFACT:
        name = o.slot.rsplit("/", 1)[-1]
        a.sites = [rel for rel in b.all_files if os.path.basename(rel) == name]
        a.used = len(a.sites)
        a.applicable = 1
    elif o.kind == MANIFEST:
        blk, key = o.slot.split("#", 1)[1].split(".", 1)
        man = b.docs.get("mac.project.yaml") or {}
        val = (man.get(blk) or {}).get(key) if isinstance(man.get(blk), dict) else None
        a.used = len(val) if isinstance(val, (list, dict)) else (1 if val else 0)
        a.sites = [f"mac.project.yaml#{blk}.{key}"] if a.used else []
        a.applicable = 1
    elif o.kind == PROSE:
        # the x- profile: "used" is a declaration; applicability is an x- key actually in use
        for rel, d in b.docs.items():
            for jpath, k, _v in walk(d):
                if isinstance(k, str) and k.startswith("x-"):
                    a.applicable += 1
                    a.applicable_sites.append(f"{rel}{jpath}.{k}")
    return a


def _names_canon(v) -> bool:
    for item in (v if isinstance(v, list) else [v]):
        if isinstance(item, dict) and str(item.get("udf", "")).startswith(("mac.canon.", "canon.")):
            return True
    return False


def measure(b, reg: list, fw: Framework) -> list:
    return [_measure_one(b, o, fw) for o in reg]


# ══════════════════════════════════════════════════════════ what the bundle does INSTEAD

def _probe(a: Adoption, b, fw: Framework) -> list:
    """Every line here is MEASURED from the bundle. A probe that asserts what a bundle "should" have
    done is an opinion; a probe that names the artifact standing in the slot's place is evidence."""
    o, out = a.offer, []
    if a.adopted and o.kind != PROSE:
        return out

    if o.slot == "grounding.field_roles":
        ncols = sum(len(s.get("columns") or [])
                    for d in b.concepts.values()
                    for s in ((d.get("grounding") or {}).get("sources") or []) if isinstance(s, dict))
        if ncols:
            out.append(f"lists {de(ncols)} columns under grounding.sources[].columns and puts a role on "
                       f"none of them — the whitelist exists, the MEANING of each column does not")
        for rel, d in b.docs.items():
            hits = sorted(set(re.findall(r"\b([a-z][a-z0-9_]*)\.field_role\b", json.dumps(d, default=str))))
            if hits and os.path.basename(rel) != "vocabulary.yaml":
                out.append(f"declares a `{hits[0]}.field_role.*` vocabulary in {rel} — the second half of "
                           f"the mechanism, in a file check_references never opens (it rglobs vocabulary.yaml)")
                break

    if o.kind == LIBRARY:
        deleg = _register_delegable(b)
        if deleg:
            out.append(f"{de(len(deleg))} enumeration(s) restate a value set an existing register already "
                       f"holds EXACTLY — mac.canon.enum_from_register is the slot for it")
            out += [f"    {d}" for d in deleg]
        fams = _copied_rule_shapes(b)
        nrules = sum(len((d.get("contract") or {}).get("rules") or []) for d in b.concepts.values())
        if fams:
            n = sum(len(v) for v in fams.values())
            out.append(f"{de(n)} of {de(nrules)} typed rules are hand-copies of {de(len(fams))} shapes "
                       f"(largest: {max(fams, key=lambda k: len(fams[k]))} × {de(len(max(fams.values(), key=len)))}) "
                       f"— every copy drifts alone; a canon has one wording and N attachments")
        elif nrules:
            out.append(f"{de(nrules)} typed rules carry when/then prose only — model-interpreted, never run")

    if o.slot == "contract.rules[].enforced_by":
        anch = Counter(os.path.dirname(f) for f in b.all_files
                       if f.endswith(".yaml") and re.search(r"anchor|oracle", f))
        if anch:
            nrules = sum(len((d.get("contract") or {}).get("rules") or []) for d in b.concepts.values())
            top = ", ".join(f"{d}/ ({de(n)})" for d, n in anch.most_common(2))
            out.append(f"ships {de(sum(anch.values()))} deterministic backstop artifacts in {top} and names "
                       f"none of them from any of {de(nrules)} rules — the link is prose, or nothing")

    if o.kind == ARTIFACT:
        name = o.slot.rsplit("/", 1)[-1]
        stem = name.rsplit(".", 1)[0]
        near = [rel for rel in b.all_files
                if Path(rel).stem == stem and os.path.basename(rel) != name]
        if near:
            out.append(f"holds the content in {near[0]} — right idea, wrong file type; "
                       f"the tool that resolves it never sees the file")

    if o.slot == "grounding.serves_from":
        rels = {s.get("relation") for d in b.concepts.values()
                for s in ((d.get("grounding") or {}).get("sources") or []) if isinstance(s, dict)}
        rels.discard(None)
        if rels:
            out.append(f"grounds on {de(len(rels))} relation name(s) via grounding.sources[].relation with no "
                       f"pointer to the SQL that serves them — the view is named, its definition is not")

    if o.kind == PROSE and a.applicable:
        keys = sorted({s.rsplit(".", 1)[-1] for s in a.applicable_sites})
        out.append(f"uses {de(len(keys))} x- key(s) ({', '.join(keys)}) at {de(a.applicable)} site(s), none "
                   f"declared anywhere — the extension is visible and unexplained")

    if o.kind == MANIFEST and not a.used:
        out.append("declares nothing — every file MAC has no definition for is silent debt rather than "
                   "arguable debt (the file-level witnesses belong to MAC001, not here)")
    return out


def _register_delegable(b) -> list:
    """Enumerations whose inline items EXACTLY equal some register column — the safe delegation set.

    EXACT SET EQUALITY, deliberately. The looser `codes ⊆ column` test was measured first and fired on
    an enumeration whose closed 2-value set is a subset of an 8-row register: delegating there would
    silently WIDEN the value domain from 2 to 8. Exactness costs recall and buys zero false positives.
    Two further enumerations here have no register at all and the loose test would have named them by
    matching an unrelated column — measured, and the reason the equality is on the SET, not the count."""
    regs: dict[str, dict] = {}
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
        regs[str(p.relative_to(b.root))] = {c: {str(r[c]).strip() for r in rows if r.get(c)}
                                            for c in rows[0]}
    out = []
    for rel, d in b.concepts.items():
        v = d.get("values") or {}
        items = v.get("items")
        if not isinstance(items, list) or v.get("realized_by"):
            continue
        codes = {str(i.get("code")) for i in items if isinstance(i, dict) and i.get("code") is not None}
        if not codes:
            continue
        for rf, cols in sorted(regs.items()):
            hit = next((cn for cn, vals in cols.items() if vals == codes), None)
            if hit:
                out.append(f"{rel}: {de(len(codes))} items == {rf}#{hit}  (closure: {v.get('closure')})")
                break
    return out


def _copied_rule_shapes(b) -> dict:
    """Rule shapes hand-copied across concepts, keyed by the rule id's TAIL.

    Generic by construction: a typed rule id is `<subject>.<shape>`, so the tail is the shape and the
    head is whose copy it is. A family counts only when it spans TWO OR MORE concepts — a concept with
    two rules of one shape is elaboration, not duplication, and charging it would be the check
    mistaking richness for drift."""
    fams: dict[str, list] = defaultdict(list)
    for rel, d in b.concepts.items():
        for r in ((d.get("contract") or {}).get("rules") or []):
            rid = str(r.get("id") or "")
            if "." not in rid:
                continue
            fams[rid.split(".", 1)[1]].append(rel)
    return {k: v for k, v in fams.items() if len(set(v)) > 1}


# ══════════════════════════════════════════════════════════ diagnostics

def _severity(a: Adoption) -> str:
    """MAC005 is WARNING at most — never ERROR. A bundle may decline a mechanism for a reason this gate
    does not know, and an unadoption that blocked the build would be the toolchain dictating design.

    WARNING when the bundle has somewhere to put it and does not.
    INFO    when there is nowhere to put it (no applicable site), or when MAC itself cannot honour the
            offer today — that is framework debt and the bundle is not the subject."""
    if a.offer.framework_gap and a.offer.kind in (PROSE,):
        return D.INFO
    return D.WARNING if a.applicable else D.INFO


def check(root, reference=None, fw: Framework | None = None, bundle=None) -> list:
    """Every MAC005 for one bundle. `reference` is read for adoption COUNTS only — it is evidence that
    a mechanism works in practice, never a target, and no diagnostic below is ever about it.

    `bundle` and `fw` are INJECTION POINTS, added 2026-08-18 for `mac_compile`. A driver running three
    phases over one bundle parses it once and hands the same object to each; called without them this
    loads its own, exactly as before, so the standalone `main()` below is unchanged. Nothing about the
    analysis depends on which way it arrived — measured identical on fpl2, 10 findings either way."""
    fw = fw or introspect_framework()
    reg = offers(fw)
    b = bundle if bundle is not None else load_bundle(Path(root))
    adoptions = measure(b, reg, fw)
    for a in adoptions:
        a.instead = _probe(a, b, fw)
    if reference:
        rb = load_bundle(Path(reference))
        ref = {x.offer.key: x for x in measure(rb, reg, fw)}
        for a in adoptions:
            r = ref.get(a.offer.key)
            if r:
                a.ref_used, a.ref_scope = r.used, "reference bundle"

    diags, quiet = [], []
    for a in sorted(adoptions, key=lambda x: (-x.applicable, x.offer.key)):
        if a.adopted and a.offer.kind != PROSE:
            continue
        if a.offer.kind == PROSE and not a.applicable:
            continue
        o = a.offer
        # THE UNDATED TIER, collapsed. An undated optional slot earns its own finding only when the
        # bundle demonstrably BUILT SOMETHING IN ITS PLACE — that is evidence the slot was needed.
        # `contract.rules[].enforced_by` earns one: the bundle ships a backstop plane and no rule names
        # it. `note`, `label`, `examples` do not, and a report that lists thirty empty prose keys beside
        # a real seam is the report nobody reads twice.
        if o.tier == "undated" and not a.instead:
            quiet.append(a)
            continue
        w = [D.Witness(file=s.split("#", 1)[0], path=(s.split("#", 1)[1] if "#" in s else ""),
                       detail="offered here, not filled")
             for s in a.applicable_sites[:200]]
        note_bits = [f"offered since {o.since}; {o.offered_by}"]
        if a.ref_used:
            note_bits.append(f"the reference bundle uses it at {de(a.ref_used)} site(s) — usable in practice")
        if o.framework_gap:
            note_bits.append(f"FRAMEWORK: {o.framework_gap}")
        if a.instead:
            note_bits.append("INSTEAD → " + "; ".join(x.strip() for x in a.instead if not x.startswith("    ")))
        summary = (f"{o.key} is offered and unused"
                   + (f" — {de(a.applicable)} site(s) in this bundle where it would apply"
                      if a.applicable else " — no site in this bundle where it would apply"))
        diags.append(D.Diagnostic(code="MAC005", severity=_severity(a), summary=summary,
                                  witnesses=w, note="  ·  ".join(note_bits), source=SOURCE))
    if quiet:
        diags.append(D.Diagnostic(
            code="MAC005", severity=D.INFO,
            summary=(f"{de(len(quiet))} optional schema slot(s) are unfilled here and MAC never dated any "
                     f"of them — the register cannot tell a seam from a prose field without a changelog entry"),
            witnesses=[D.Witness(file="mac.schema.json", path=a.offer.slot,
                                 detail=f"{de(a.applicable)} applicable site(s), 0 filled")
                       for a in sorted(quiet, key=lambda x: -x.applicable)],
            note=("FRAMEWORK: CONFORMANCE §6 records an addition against a generation; these were added "
                  "without one. Date them, or accept that no derived register can classify them. Listed "
                  "as ONE finding, not one per slot — a slot with no measured substitute in this bundle "
                  "is not evidence of anything on its own"),
            source=SOURCE))
    return diags


# ══════════════════════════════════════════════════════════ the table

def table(root, reference=None) -> str:
    fw = introspect_framework()
    reg = offers(fw)
    b = load_bundle(Path(root))
    ads = measure(b, reg, fw)
    for a in ads:
        a.instead = _probe(a, b, fw)
    ref = {}
    if reference:
        rb = load_bundle(Path(reference))
        ref = {x.offer.key: x.used for x in measure(rb, reg, fw)}
    # THE TABLE IS THE DATED REGISTER. An undated optional slot appears only when the bundle built a
    # substitute for it — otherwise 142 rows of `note:` and `label:` bury the ten findings that matter.
    shown = [a for a in ads if a.offer.tier == "dated" or a.instead]
    hidden = len(ads) - len(shown)
    dated = [a for a in ads if a.offer.tier == "dated"]
    lines = [f"── MAC005 capability adoption ── {de(len(dated))} dated mechanism(s) offered · "
             f"{de(sum(1 for a in dated if a.adopted))} adopted · "
             f"{de(sum(1 for a in dated if not a.adopted))} unadopted "
             f"(+ {de(len(ads) - len(dated))} undated optional slots) ── {root}\n",
             f"  {'MECHANISM':<44} {'SINCE':>7} {'USED':>6} {'APPLIC':>7} {'REF':>5}  WHAT THE BUNDLE DOES INSTEAD",
             "  " + "─" * 116]
    for a in sorted(shown, key=lambda x: (x.adopted, -x.applicable, x.offer.key)):
        o = a.offer
        mark = "✓" if a.adopted else ("!" if a.applicable else "·")
        first = (a.instead[0] if a.instead else ("—" if a.adopted else "(nothing — the slot is simply empty)"))
        lines.append(f"{mark} {o.key[:43]:<44} {o.since:>7} {de(a.used):>6} {de(a.applicable):>7} "
                     f"{de(ref.get(o.key, 0)) if ref else '-':>5}  {first[:70]}")
        for extra in a.instead[1:]:
            lines.append(f"  {'':<44} {'':>7} {'':>6} {'':>7} {'':>5}  {extra.strip()[:70]}")
        if o.framework_gap and o.tier == "dated":
            lines.append(f"  {'':<44} {'':>7} {'':>6} {'':>7} {'':>5}  FRAMEWORK: {o.framework_gap[:60]}")
    if hidden:
        lines.append(f"  … and {de(hidden)} undated optional slot(s), unfilled with no substitute standing "
                     f"— one collapsed finding below, never one row each")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="MAC005 — capability-unadopted")
    ap.add_argument("bundle")
    ap.add_argument("--reference", help="read ONLY for adoption counts; never a target")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show", default=D.INFO, choices=[D.ERROR, D.WARNING, D.INFO])
    a = ap.parse_args()
    root = Path(a.bundle).resolve()
    if not root.is_dir():
        print(f"bundle not found: {root}", file=sys.stderr)
        return 2
    diags = check(root, a.reference)
    if a.json:
        print(json.dumps({"schema": "mac.diagnostics/1", "source": SOURCE, "bundle": str(root),
                          "summary": D.summarise(diags),
                          "diagnostics": [{"code": d.code, "severity": d.severity, "summary": d.summary,
                                           "note": d.note, "source": d.source,
                                           "witnesses": [w.__dict__ for w in d.witnesses]}
                                          for d in diags]}, indent=2, ensure_ascii=False))
        return 0
    print(table(root, a.reference))
    print()
    print(D.render(diags, str(root), show=a.show))
    s = D.summarise(diags)
    print(f"\n{de(s['total'])} MAC005 finding(s) — {de(s['warnings'])} warning, "
          f"{de(s['by_severity'].get(D.INFO, 0))} info, {de(s['witnesses'])} witness(es). "
          f"MAC005 never blocks a build.")
    return 0                       # MAC005 is warning at most — it cannot fail a run, by contract


if __name__ == "__main__":
    raise SystemExit(main())
