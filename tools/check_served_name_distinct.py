#!/usr/bin/env python3
"""check_served_name_distinct.py — the SERVED-NAME-DISTINCT gate.

WHAT IT ENFORCES
----------------
A served/curated dataset (``data/datasets/*``) must carry a name DISTINCT from every raw source
(``data/sources/*``), and must be spelled the way its bundle says it spells served relations. When a
served view is named the same as its raw source, the lineage's source node and dataset node collapse
into one — the ``source -> dataset`` (A->B) transformation renders as a SELF-LOOP and reads as
flawed. This gate makes shipping that impossible.

THE CONVENTION IS PART OF THE GATE, NOT PART OF THE FOLKLORE
------------------------------------------------------------
This gate publishes the naming convention in its FAILURE MESSAGE. An operator must never have to
read this source file to learn what an acceptable name looks like. That is not a style preference,
it is the measured mechanism: in an eight-operator ingestion experiment run from one raw source in
isolated workspaces, SEVEN operators read this gate and all seven adopted the convention it prints;
two of them had no method document at all and still produced BYTE-IDENTICAL served-name sets from
the gate alone. The one operator who never reached the gate diverged completely — zero name overlap
with its peers. A gate that refuses a name without saying what would be accepted transmits nothing;
it just blocks. So every refusal below carries the rule, the closed role table, and a worked example.

THE ROLE TABLE IS CLOSED (and this is where the residual disagreement sat)
--------------------------------------------------------------------------
The rule used to read "``v`` for a view, ``dim`` for a dimension, …" — and that ellipsis is exactly
where the seven readers still split: several spelled a served fact ``fact_`` and several ``v_``, for
the SAME relation. An ellipsis in a rule is not brevity, it is an unmade decision handed to whoever
reads it next, and it costs one divergence per reader. It is now a closed table, decided by what the
estate actually serves rather than by taste. The table below is the DEFAULT, and it is reproduced
here only to be readable — the one that is published and enforced is read at runtime from
``mac.schema.json#/$defs/ProjectFile/…/naming/properties/roles/default``, so the gate keeps no second
copy of it that could quietly disagree:

    ROLE   KIND(S)         WHAT IT IS FOR
    v      view, fact      a relation a question reads at its own grain — curated entity views,
                           event streams, KPI grids. A served FACT is spelled `v`, NOT `fact`: it is
                           materialised as a view in the serving schema, and the estate's served
                           descriptors carry `v` several hundred times and `fact` zero times.
    dim    dimension       a conformed descriptive relation, joined by key so a code can be given
                           its label and its attributes.
    meta   meta            a register ABOUT the bundle — its measures, rules, edges, provenance —
                           read by the instrument rather than by a business question.

Nothing else is a role. A leading `fact`/`f`/`vw`/`view`/`d`/`stg`/`raw`/`src`/`tmp`/`curated`/…
names a pipeline STAGE or an abbreviation of a member, not a fourth role, and each is refused with
the member it should have been.

WHERE A BUNDLE DECLARES ITS OWN — A CORE KEY, NOT AN EXTENSION
---------------------------------------------------------------
Every one of the seven readers then tried to declare the convention in ``mac.project.yaml`` under an
``x-`` key, because that is what this gate used to tell them to do. All seven were wrong, and the
gate was the reason: ``mac.schema.json`` rejects it (``ProjectFile`` is ``additionalProperties:false``
with no ``^x-`` pattern) and ``tools/check_extension_keys.py`` PROHIBITS it as MAC012, on a standing
operator ruling — "they are not easily verifiable, they are a weak point in the chain". So the
framework was teaching, at its most effective surface, the one declaration two other mechanisms
refuse. Opposite policies inside one framework are a DEFECT, not a tension to document, so the
extension spelling is gone and the convention has a home the core defines:

    serving:
      naming:
        marker: acme                              # REQUIRED — what makes these relations THIS bundle's
        roles:                                    # optional — omit to take the default table above
          view:      {prefix: v,    marker: required}
          fact:      {prefix: v,    marker: required}
          dimension: {prefix: dim,  marker: optional}
          meta:      {prefix: meta, marker: optional}
        example: "raw `shipments` -> served `v_acme_shipments`"

The declaration is STRUCTURAL — a marker plus a role table — and the gate DERIVES the acceptance
test from it. It is deliberately not a free-text regex or name template: an unverifiable string is
the same weakness that got ``x-`` ruled out, and a convention nothing can check is worse than none,
because the manifest then claims a guarantee nothing enforces.

DECLARED vs DEFAULT — and why the default is not a free pass
-------------------------------------------------------------
  DEFAULT (a bundle declares nothing). In force, and it judges:
      * the INVARIANT — the served name differs from every raw name; and
      * ROLE CLOSURE — a name that LEADS with a role-shaped token must lead with a member of the
        table. `fact_shipments` is refused and told to be `v_…`; that is the measured split, closed.
    The marker is suggested but not required here: a bundle that never declared one is not
    retro-legislated into it, and the estate's conformed dimensions (`dim_country`) go without.

  DECLARED (``serving.naming`` present). The full build-shape becomes required and checked:
      <role>_<marker>_<business noun>      role from the bundle's own table; marker per kind.
    Declaring is therefore worth something — it is the only way to have the marker enforced.

THE ALREADY-CLEAN-NOUN CASE (the defect an earlier rewrite fixed; still guarded)
--------------------------------------------------------------------------------
"Rename to a clean name" is UNSATISFIABLE when the raw relation is ALREADY a clean business noun:
raw `shipments` has no source-system infix to strip, so the only "clean name" is `shipments`, which
is exactly the name being refused. The answer is the marker: `v_acme_shipments`. A standing self-test
guard holds both halves of this — a refusal may never hand back the name it refused, and every name
this gate SUGGESTS must be one this gate would ACCEPT.

Suggestions are DERIVED, never hardcoded: the source-system infix is inferred from tokens the raw
namespace repeats, and the marker from the declaration or from the bundle's own ``metadata.source``.

The suggested rename covers the FILE STEM and ``table.name`` TOGETHER — ``check_relation_identity.py``
requires stem == table.name, so renaming only one of them trades this gate's red for that one's.

OFFLINE + pure-structural (files on disk, no AWS).

Usage:  python3 tools/check_served_name_distinct.py <bundle-root>
        python3 tools/check_served_name_distinct.py --self-test
Exit:   0 = PASS ; 1 = FAIL (a collision, or a violation of the convention in force)
        2 = SETUP failure (bad usage / unreadable or incoherent declaration) — by this toolchain's
            convention exit 2 means "the gate did not judge the bundle", which mac_compile.py maps to
            a WARNING rather than an error. Never returned for a bundle defect.
Output: exactly one ``PASS:``/``FAIL:`` line (the last line), for exit 0 and 1. Exit 2 prints
        neither — a gate that did not judge must not emit a verdict.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import yaml


class SetupError(Exception):
    """The gate cannot judge — a declaration it was asked to enforce is unusable. Exit 2, not 1."""


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the CLOSED role table — the ellipsis that used to sit here is what operators disagreed about
# ──────────────────────────────────────────────────────────────────────────────────────────────────

_SCHEMA = Path(__file__).resolve().parent.parent / "mac.schema.json"
_ROLES_PTR = ("$defs", "ProjectFile", "properties", "serving", "properties", "naming",
              "properties", "roles")


def _default_roles() -> dict:
    """kind -> (prefix, marker policy), READ from the schema that declares it.

    Deliberately not a literal here. The schema defines the key, so the schema is where the default
    table lives — as `default` DATA, not prose — and this gate reads it. Two copies of one table is
    exactly the drift this framework reports elsewhere as MAC003, and it would be the worst possible
    place for it: the published default and the enforced default silently disagreeing, in the one
    surface measured to transmit the convention. If the schema cannot be read the gate does not
    guess, it declines to judge (SETUP).
    """
    try:
        node = json.loads(_SCHEMA.read_text(encoding="utf-8"))
        for step in _ROLES_PTR:
            node = node[step]
        table = {kind: (str(spec["prefix"]), str(spec.get("marker") or "required"))
                 for kind, spec in node["default"].items()}
        if not table:
            raise ValueError("empty default role table")
        return table
    except Exception as exc:  # noqa: BLE001
        raise SetupError(
            f"the default role table could not be read from {_SCHEMA.name}"
            f"#/{'/'.join(_ROLES_PTR)}/default ({exc!r}). That table is the convention this gate "
            f"publishes and enforces; it is held THERE so the published and enforced defaults cannot "
            f"drift apart, and this gate does not keep a second copy to fall back on. Restore the "
            f"schema rather than teaching the gate to guess.") from exc

# What each kind is FOR — printed with every refusal, because a table of prefixes without purposes
# is the same ellipsis one level down: it says what to type, not how to choose.
_KIND_PURPOSE = {
    "view": "a relation a question reads at its own grain — curated entity views, event streams, "
            "KPI grids",
    "fact": "a served fact — SAME prefix as a view on purpose: it is materialised as a view in the "
            "serving schema (estate: several hundred `v_`, zero `fact_`)",
    "dimension": "a conformed descriptive relation, joined by key to give a code its label and "
                 "attributes",
    "meta": "a register ABOUT the bundle — its measures, rules, edges, provenance — read by the "
            "instrument, not by a business question",
}

# Leading tokens that ANNOUNCE a role and are not members. Each maps to the kind it meant, so the
# refusal can name the replacement instead of only the offence. This is the list that closes the
# ellipsis: every one of these was a plausible reading of "v for a view, dim for a dimension, …".
_ROLE_ALIASES = {
    "fact": "fact", "facts": "fact", "f": "fact",
    "vw": "view", "view": "view", "vi": "view",
    "d": "dimension", "dimension": "dimension", "dims": "dimension",
    "metadata": "meta",
    # pipeline STAGES: a stage is not a role. If the relation is served at all, it is a view.
    "stg": "view", "stage": "view", "raw": "view", "src": "view", "source": "view",
    "tmp": "view", "temp": "view", "base": "view", "curated": "view", "clean": "view",
    "tbl": "view", "t": "view", "final": "view", "mart": "view", "agg": "view",
}

# Role/structural tokens: they say what KIND of relation this is, so they are never the
# source-system infix and never the bundle marker. Kept small and generic on purpose.
_ALIAS_TOKENS = set(_ROLE_ALIASES)


def _structural(conv: dict) -> set:
    """Tokens that say what KIND a relation is — never a source-system infix, never the marker.

    The role prefixes come from the convention IN FORCE, not from a literal, so a bundle that spells
    its roles its own way gets its own prefixes stripped when the gate derives a business noun.
    """
    return _ALIAS_TOKENS | set(_prefixes(conv))


def _slug(text: str) -> str:
    """A name token safe to paste into a relation name."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text or "").lower())).strip("_")


def _descriptors(d: Path) -> dict:
    """{stem: {"name": table.name, "source": metadata.source, "path": <repo-relative>}} for a plane dir.

    The stem is the fallback name: a descriptor with no ``table.name`` still materialises to something,
    and that something is its stem.
    """
    out = {}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        tbl = doc.get("table") or {}
        meta = doc.get("metadata") or {}
        out[p.stem] = {
            "name": str((tbl.get("name") if isinstance(tbl, dict) else None) or p.stem),
            "source": str((meta.get("source") if isinstance(meta, dict) else "") or ""),
            "path": f"data/{d.name}/{p.name}",
        }
    return out


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the convention: declared by the bundle in the CORE key, or the published default
# ──────────────────────────────────────────────────────────────────────────────────────────────────

_CORE_KEY_EXAMPLE = (
    "    serving:\n"
    "      naming:\n"
    "        marker: {mk}\n"
    "        roles:\n"
    "          view:      {{prefix: v,    marker: required}}\n"
    "          fact:      {{prefix: v,    marker: required}}\n"
    "          dimension: {{prefix: dim,  marker: optional}}\n"
    "          meta:      {{prefix: meta, marker: optional}}\n"
    "        example: \"raw `shipments` -> served `v_{mk}_shipments`\"")


def _core_key_example(marker: str) -> str:
    return _CORE_KEY_EXAMPLE.format(mk=marker or "<source-key>")


def _read_manifest(root: Path) -> dict:
    manifest = root / "mac.project.yaml"
    if not manifest.exists():
        return {}
    try:
        doc = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise SetupError(f"mac.project.yaml is not readable YAML ({exc!r}) — the gate cannot tell "
                         f"whether this bundle declares a serving-name convention") from exc
    return doc if isinstance(doc, dict) else {}


def _declared_convention(root: Path) -> dict | None:
    """The bundle's own convention from ``mac.project.yaml#serving.naming``, or None.

    ``serving`` is a CORE key (mac.schema.json#/$defs/ProjectFile). The ``x-serving-naming`` spelling
    this gate used to publish is intercepted here rather than honoured: the schema rejects it and
    MAC012 prohibits it, so silently reading it would leave the framework holding two opposite
    policies — one teaching an extension key, two others refusing it.
    """
    defaults = _default_roles()
    doc = _read_manifest(root)
    if not doc:
        return None

    for key in doc:
        if isinstance(key, str) and key.startswith("x-") and "serv" in key and "nam" in key:
            raise SetupError(
                f"mac.project.yaml declares the serving-name convention under `{key}`. An `x-` "
                f"extension key is PROHIBITED (tools/check_extension_keys.py, MAC012, on a standing "
                f"ruling) AND rejected by mac.schema.json — ProjectFile is additionalProperties:false "
                f"with no `^x-` pattern — so this declaration is enforced by nothing and blocks the "
                f"bundle elsewhere. It has a core home now. Move it verbatim:\n"
                + _core_key_example(_slug(str((doc.get("metadata") or {}).get("dataset") or
                                              (doc.get("metadata") or {}).get("project") or "")))
                + "\n  (MAC012 is the gate that FAILS on the `x-` key; this one only tells you where "
                  "the fact now lives, so it reports SETUP rather than passing judgement on names it "
                  "cannot know the convention for.)")

    serving = doc.get("serving")
    if serving is None:
        return None
    if not isinstance(serving, dict):
        raise SetupError("mac.project.yaml `serving` is not a mapping — expected `serving.naming` "
                         "with keys `marker` (required), `roles`, `example`")
    block = serving.get("naming")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise SetupError("mac.project.yaml `serving.naming` is not a mapping — expected keys "
                         "`marker` (required), `roles`, `example`")

    for legacy in ("pattern", "template"):
        if legacy in block:
            raise SetupError(
                f"mac.project.yaml `serving.naming` carries `{legacy}`, which this gate no longer "
                f"accepts and mac.schema.json rejects. A convention stated as a free-text "
                f"regex/template is unverifiable — the gate cannot tell a typo from a policy, which "
                f"is the same weakness that got extension keys ruled out. State it STRUCTURALLY and "
                f"the acceptance test is derived:\n" + _core_key_example(_slug(block.get("marker"))))

    marker = _slug(block.get("marker"))
    if not marker:
        raise SetupError(
            "mac.project.yaml declares `serving.naming` with no `marker`. A declared convention the "
            "gate cannot check is worse than none: the manifest claims a guarantee nothing enforces. "
            "The marker is what makes this bundle's served relations addressable as its own — "
            "commonly its source key, lowercased:\n" + _core_key_example(""))

    roles = block.get("roles")
    if roles is None:
        table = dict(defaults)
    elif not isinstance(roles, dict):
        raise SetupError("mac.project.yaml `serving.naming.roles` is not a mapping — expected "
                         "`<kind>: {prefix: <token>, marker: required|optional}` per kind, with "
                         f"kind one of {', '.join(sorted(defaults))}")
    else:
        table = {}
        for kind, spec in roles.items():
            if kind not in defaults:
                raise SetupError(
                    f"mac.project.yaml `serving.naming.roles` declares kind `{kind}`, which is not a "
                    f"relation kind. The kinds are CLOSED — {', '.join(sorted(defaults))} — "
                    f"because what a served relation can BE is a framework fact; only the PREFIX is "
                    f"the bundle's to choose. A new kind is a change to mac.schema.json, not a line "
                    f"in a manifest.")
            if not isinstance(spec, dict) or not spec.get("prefix"):
                raise SetupError(
                    f"mac.project.yaml `serving.naming.roles.{kind}` has no `prefix` — expected "
                    f"`{kind}: {{prefix: <token>, marker: required|optional}}`")
            prefix = str(spec.get("prefix"))
            if not re.fullmatch(r"[a-z][a-z0-9]*", prefix):
                raise SetupError(
                    f"mac.project.yaml `serving.naming.roles.{kind}.prefix` is {prefix!r} — a role "
                    f"prefix is one lowercase token with no underscore (the underscore is the "
                    f"separator, so a prefix containing one cannot be found in a name)")
            policy = str(spec.get("marker") or "required")
            if policy not in ("required", "optional"):
                raise SetupError(
                    f"mac.project.yaml `serving.naming.roles.{kind}.marker` is {policy!r} — expected "
                    f"`required` or `optional`")
            table[kind] = (prefix, policy)
        for kind, spec in defaults.items():                # kinds left unsaid keep the default
            table.setdefault(kind, spec)

    return {"declared": True, "marker": marker, "roles": table,
            "example": str(block.get("example") or "")}


def _default_convention(marker: str) -> dict:
    """The published DEFAULT — in force whenever a bundle declares nothing. Not a free pass."""
    return {"declared": False, "marker": marker, "roles": _default_roles(), "example": ""}


def _prefixes(conv: dict) -> dict:
    """prefix -> [kind, …] for the convention in force (two kinds legitimately share `v`)."""
    out = {}
    for kind, (prefix, _policy) in conv["roles"].items():
        out.setdefault(prefix, []).append(kind)
    order = list(_KIND_PURPOSE)
    return {p: sorted(k, key=order.index) for p, k in out.items()}


def _marker_required(conv: dict, prefix: str) -> bool:
    """Does a name carrying this prefix have to carry the marker? Only ever true when DECLARED."""
    if not conv["declared"]:
        return False
    policies = {p for kind, (pre, p) in conv["roles"].items() if pre == prefix}
    return policies == {"required"}          # shared prefix: the laxer policy wins, never the stricter


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# derivation: the business noun, the bundle's marker
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _system_tokens(raw_names: list, structural: set) -> list:
    """Tokens the RAW namespace REPEATS — the source-system infix, derived rather than hardcoded.

    A token carried by at least half the raw relations (and by at least two of them) is naming the
    SYSTEM, not the subject; the business noun is what survives its removal. Used for SUGGESTIONS
    only — a mis-derived token can never fail a bundle, only make one hint less apt.
    """
    if len(raw_names) < 2:
        return []
    counts = Counter()
    for n in raw_names:
        for tok in set(str(n).split("_")):
            if tok and tok not in structural and not tok.isdigit():
                counts[tok] += 1
    threshold = max(2, (len(raw_names) + 1) // 2)
    return [t for t, c in counts.items() if c >= threshold]


def _business_noun(name: str, system_tokens: list, marker: str, structural: set) -> str:
    """The clean noun inside a relation name: its tokens, less the system/role/marker ones."""
    toks = [t for t in name.split("_") if t and t not in system_tokens and t != marker]
    keep = [t for t in toks if t not in structural] or toks
    return "_".join(keep) or name


def _marker(served: dict, root: Path) -> str:
    """The bundle's serving marker — what makes ITS relations addressable as its own.

    Taken from the descriptors' own ``metadata.source`` (a declared MAC field, present on every
    served descriptor in every bundle in the estate), falling back to the manifest's dataset/project
    metadata and finally to the bundle directory name. Derived from the bundle, never assumed.
    """
    votes = Counter(_slug(d.get("source")) for d in served.values() if _slug(d.get("source")))
    if votes:
        return votes.most_common(1)[0][0]
    try:
        meta = _read_manifest(root).get("metadata") or {}
    except SetupError:
        meta = {}
    if isinstance(meta, dict):
        for key in ("dataset", "project", "label"):
            cand = _slug(str(meta.get(key) or "").split("/")[-1])
            if cand:
                return cand
    return _slug(root.name)



# ──────────────────────────────────────────────────────────────────────────────────────────────────
# conformance + the suggestion (which must itself conform — see the self-test guard)
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _violations(name: str, raw_tokens: set, conv: dict) -> list:
    """Every way this served name breaks the convention in force. Empty list = acceptable."""
    out = []
    if name in raw_tokens:
        out.append(("collision",
                    "the source node and the dataset node collapse into one, so the "
                    "source -> dataset edge renders as a self-loop"))
    head = name.split("_", 1)[0]
    prefixes = _prefixes(conv)
    if head in prefixes:
        if _marker_required(conv, head) and conv["marker"] not in name.split("_"):
            out.append(("marker",
                        f"this bundle DECLARES `{conv['marker']}` as its serving marker and "
                        f"`{head}` as a prefix that must carry it; without it the name is not "
                        f"addressable as this bundle's"))
    elif conv["declared"]:
        out.append(("role",
                    f"this bundle DECLARES its role table, so every served name leads with one of "
                    f"{', '.join(sorted(prefixes))} — `{head}` is not a role it declares"))
    elif head in _ROLE_ALIASES:
        out.append(("role",
                    f"`{head}` ANNOUNCES a role and is not one — the role table is closed at "
                    f"{', '.join(sorted(prefixes))}, and `{head}` is where readers of the old "
                    f"open-ended rule independently diverged"))
    return out


def _conforming(name: str, taken: set, conv: dict, system_tokens: list) -> tuple:
    """(a name this gate would ACCEPT, why it has that shape). Never returns `name` itself.

    Three shapes, and which applies is the whole already-clean-noun question:
      * the raw name CARRIES a source-system infix -> the infix stripped off is already distinct;
      * the leading token announces the WRONG role -> the member it meant, in its place;
      * the raw name is ALREADY the business noun  -> the bundle's marker is what makes it its own.
    """
    marker = conv["marker"]
    noun = _business_noun(name, system_tokens, marker, _structural(conv))
    head = name.split("_", 1)[0]
    prefixes = _prefixes(conv)

    # a mis-spelled role: keep the relation's KIND, fix only the spelling
    aliased = _ROLE_ALIASES.get(head)
    if aliased and head not in prefixes:
        prefix = conv["roles"][aliased][0]
        why = (f"`{head}` meant the `{aliased}` kind; the table spells that kind `{prefix}`")
    elif head in prefixes:
        prefix, why = head, "the role this relation already announces, kept"
    else:
        prefix = conv["roles"]["view"][0]
        why = ("nothing in the name says what kind of relation this is, so it takes the default "
               f"role `{prefix}` (a relation a question reads at its own grain)")

    base = noun or name
    already_clean = base == name          # nothing was stripped -> the raw name IS the business noun

    # Candidates in preference order. The FIRST that this gate would itself accept wins, so the
    # suggestion conforms by construction rather than by arithmetic — which is what the self-test
    # guard checks, and what an earlier version got wrong by hand-assembling a single answer.
    candidates = []
    if not conv["declared"] and not already_clean:
        candidates.append((base, "the same relation with the source-system infix removed — the raw "
                                 "name carries one, so the business noun alone is already distinct"))
    marker_why = ("the raw name is ALREADY the clean business noun — there is no infix to strip, so "
                  "the served relation takes the bundle's serving marker to become its own node"
                  ) if already_clean else why
    if marker:
        candidates.append((f"{prefix}_{marker}_{base}", marker_why))
    candidates.append((f"{prefix}_{base}", why))

    for cand, reason in candidates:
        if cand != name and cand not in taken and not _violations(cand, taken, conv):
            return cand, reason
    cand, reason = candidates[0]                 # pathological: every shape is already spoken for
    n = 2
    while cand in taken or cand == name:         # never hand the refusal back to the operator
        cand, n = f"{candidates[0][0]}_{n}", n + 1
    return cand, reason


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the teaching surface: the convention, the role table and a worked example, AT the failure
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _accepted_line(conv: dict) -> str:
    """The convention on ONE line, with a worked example — carried by EVERY [ERROR].

    Deliberately redundant with the convention block below: operators grep single ``[ERROR]`` lines
    and read their neighbours, and a rule that only appears in a trailing block is a rule half the
    readers never see.
    """
    mk = conv["marker"] or "acme"
    roles = ", ".join(sorted(_prefixes(conv)))
    if conv["declared"]:
        shown = conv.get("example") or f"raw `shipments` -> served `{conv['roles']['view'][0]}_{mk}_shipments`"
        return (f"`<role>_<marker>_<business noun>` as THIS BUNDLE declares it — role one of "
                f"{roles}, marker `{mk}` — e.g. {shown}")
    return (f"`<role>_<marker>_<business noun>` with role one of {roles} (closed) and marker `{mk}` "
            f"— e.g. raw `shipments` -> served `{conv['roles']['view'][0]}_{mk}_shipments`; or the "
            f"business noun ALONE when the raw name carries a source-system infix — e.g. raw "
            f"`{mk}_lm_shipments` -> served `shipments`")


def _role_table_lines(conv: dict) -> list:
    """The CLOSED role table, printed with every refusal. This replaced an ellipsis."""
    lines = ["  ── the role table (CLOSED — a served name leads with one of these) ─────────────"]
    for prefix, kinds in sorted(_prefixes(conv).items()):
        head = f"      {prefix + '_':<8} {'/'.join(kinds):<16}"
        purpose = " · ".join(_KIND_PURPOSE[k] for k in kinds)
        wrapped = _wrap(purpose, 62)
        lines.append(head + wrapped[0])
        lines += [" " * len(head) + w for w in wrapped[1:]]
    aliases = _wrap(", ".join(sorted(a for a in _ROLE_ALIASES if a not in _prefixes(conv))), 62)
    lines.append(f"      NOT roles: {aliases[0]}")
    lines += [" " * 17 + w for w in aliases[1:]]
    lines.append("      ^ each names a pipeline STAGE or an abbreviation of a member above, not a")
    lines.append("        fourth role; each is refused with the member it should have been.")
    return lines


def _wrap(text: str, width: int) -> list:
    out, line = [], ""
    for word in str(text).split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return out + ([line] if line else [""])


def _convention_block(conv: dict) -> list:
    """The convention, as the operator should read it — printed with every refusal."""
    mk = conv["marker"] or "<source-key>"
    view = conv["roles"]["view"][0]
    lines = ["  ── the convention ──────────────────────────────────────────────────────────────"]
    if conv["declared"]:
        lines += ["  DECLARED by this bundle in mac.project.yaml#serving.naming — the gate checks",
                  "  conformance to THAT, not to any MAC default:",
                  f"      marker  : {mk}   (required in every name whose role demands it)"]
        for kind, (prefix, policy) in sorted(conv["roles"].items()):
            lines.append(f"      {kind:<10}: {prefix + '_':<8} marker {policy}")
        lines.append(f"      example : {conv['example'] or f'raw `shipments` -> served `{view}_{mk}_shipments`'}")
    else:
        lines += ["  This bundle declares no convention, so the published DEFAULT is in force. It is",
                  "  not a free pass: it requires the invariant AND a role from the closed table.",
                  f"      <role>_<marker>_<business noun>        marker for this bundle: {mk}",
                  f"      worked example: raw `shipments` -> served `{view}_{mk}_shipments`",
                  "      (the marker is SUGGESTED here, not required — declare the block below to",
                  "       have it enforced, which is the only way to make it a guarantee)",
                  "  To have the gate enforce YOUR spelling instead, declare it in mac.project.yaml.",
                  "  It is a CORE key — never an `x-` extension, which mac.schema.json rejects and",
                  "  MAC012 prohibits:",
                  _core_key_example(conv["marker"])]
    lines += _role_table_lines(conv)
    lines += ["  Rename the FILE STEM and table.name TOGETHER — check_relation_identity.py requires",
              "  stem == table.name, so renaming one of them only moves the red.",
              "  ────────────────────────────────────────────────────────────────────────────────"]
    return lines


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the gate
# ──────────────────────────────────────────────────────────────────────────────────────────────────

_HEADLINE = {
    "collision": "EQUALS a raw source name",
    "role": "does not lead with a role from the closed role table",
    "marker": "does not carry this bundle's declared serving marker",
}


def run(root: Path, out=None) -> int:
    """The gate proper. Returns 0 (PASS), 1 (FAIL) or 2 (SETUP — no verdict printed)."""
    emit = (lambda s="": print(s, file=out)) if out is not None else (lambda s="": print(s))

    data = root / "data"
    sources = _descriptors(data / "sources")
    served = _descriptors(data / "datasets")
    try:
        # Both halves can decline to judge: the bundle's declaration may be unusable, and the
        # framework's own default table may be unreadable. Neither is a bundle defect, so both
        # land on SETUP rather than on a verdict.
        conv = _declared_convention(root) or _default_convention(_marker(served, root))
    except SetupError as exc:
        emit(f"── served-name-distinct gate ── SETUP ── {root} ──\n")
        first = True
        for para in str(exc).splitlines():
            # prose is wrapped; an indented line is a YAML example and is emitted verbatim
            for line in (_wrap(para, 86) if not para.startswith("    ") else [para]):
                emit((f"  [ERROR] {line}" if first else f"          {line}").rstrip())
                first = False
        return 2

    emit(f"── served-name-distinct gate ── {len(served)} served dataset(s) vs {len(sources)} raw "
         f"source(s) under {root} ── convention: "
         f"{'DECLARED (mac.project.yaml#serving.naming)' if conv['declared'] else 'DEFAULT (published below)'} ──\n")
    if not served:
        emit("PASS: served-name-distinct — no served datasets under data/datasets, nothing to judge")
        return 0

    # The lineage self-loops when the served view's PHYSICAL name (table.name — the relation it
    # materialises to) equals a raw source's physical name OR its descriptor stem, since a raw
    # descriptor with no table.name still materialises to its stem.
    raw_tokens = {d["name"] for d in sources.values()} | set(sources.keys())
    system_tokens = _system_tokens(sorted(raw_tokens), _structural(conv))
    taken = raw_tokens | {d["name"] for d in served.values()}
    accepted = _accepted_line(conv)

    errors = []
    for _stem, d in served.items():
        name, path = d["name"], d["path"]
        bad = _violations(name, raw_tokens, conv)
        if not bad:
            continue
        fix, why = _conforming(name, taken - {name}, conv, system_tokens)
        headline = "; ".join(_HEADLINE[k] for k, _ in bad)
        block = [f"{path} — served name '{name}' {headline} -> rename to '{fix}'"]
        for _kind, reason in bad:
            for i, w in enumerate(_wrap(reason, 86)):
                block.append(f"      {'why      : ' if i == 0 else '           '}{w}")
        for i, w in enumerate(_wrap(accepted, 86)):
            block.append(f"      {'accepted : ' if i == 0 else '           '}{w}")
        block.append(f"      rename to: '{fix}'")
        for i, w in enumerate(_wrap(why, 74)):
            block.append(f"                 {'(' if i == 0 else ' '}{w}" + (")" if i == len(_wrap(why, 74)) - 1 else ""))
        errors.append(block)

    for e in errors:
        emit(f"  [ERROR] {e[0]}")
        for line in e[1:]:
            emit(line)
        emit("")
    if errors:
        for line in _convention_block(conv):
            emit(line)
        emit("")
        emit(f"FAIL: served-name-distinct — {len(errors)} served relation(s) refused; each refusal "
             f"above names the accepted shape and a conforming rename")
        return 1
    emit(f"PASS: served-name-distinct — {len(served)} served relation(s) distinct from "
         f"{len(sources)} raw source(s) and conforming to the "
         + ("convention this bundle declares" if conv["declared"] else "default role table"))
    return 0


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# --self-test : one mutant per reject class + clean fixtures that must pass
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _fixture(base: Path, name: str, raws: list, dsets: list, manifest: str = "") -> Path:
    root = base / name
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    if manifest:
        (root / "mac.project.yaml").write_text(manifest, encoding="utf-8")
    for n in raws:
        (root / "data" / "sources" / f"{n}.yaml").write_text(
            f"metadata:\n  table: {n}\n  kind: raw_source\n  source: ACME\ntable:\n  name: {n}\n",
            encoding="utf-8")
    for n in dsets:
        (root / "data" / "datasets" / f"{n}.yaml").write_text(
            f"metadata:\n  table: {n}\n  source: ACME\ntable:\n  name: {n}\n", encoding="utf-8")
    return root


_DECLARED = ("planes: {data: data, ontology: ontology}\n"
             "serving:\n"
             "  naming:\n"
             "    marker: acme\n"
             "    roles:\n"
             "      view:      {prefix: v,    marker: required}\n"
             "      fact:      {prefix: v,    marker: required}\n"
             "      dimension: {prefix: dim,  marker: optional}\n"
             "      meta:      {prefix: meta, marker: optional}\n"
             "    example: \"raw `shipments` -> served `v_acme_shipments`\"\n")


def self_test() -> int:
    import io

    cases, failures = [], []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # ── CLEAN FIXTURES — must PASS, or the gate rejects work that is correct ─────────────────
        cases.append(("clean/infix-stripped", _fixture(
            base, "clean_infix", ["acme_lm_shipments", "acme_lm_orders"], ["shipments", "orders"]), 0, []))
        # the already-clean case, SATISFIED direction: raw names are clean nouns, served names carry
        # the bundle's serving marker. This is the resolution the failure message prescribes — if it
        # did not pass, the gate would be publishing advice it then refuses.
        cases.append(("clean/already-clean-noun-satisfied", _fixture(
            base, "clean_marker", ["shipments", "orders"], ["v_acme_shipments", "v_acme_orders"]), 0, []))
        cases.append(("clean/no-datasets", _fixture(base, "clean_empty", ["shipments"], []), 0, []))
        # the ESTATE shape, undeclared: bundle-specific views carry the marker, conformed dimensions
        # and meta registers do not. The default must accept this or it retro-legislates the estate.
        cases.append(("clean/estate-shape-undeclared", _fixture(
            base, "clean_estate", ["shipments", "regions"],
            ["v_acme_shipments", "dim_country", "meta_measures"]), 0, []))
        cases.append(("clean/declared-conforming", _fixture(
            base, "clean_declared", ["shipments"], ["v_acme_shipments", "dim_country"], _DECLARED), 0, []))
        # a bundle may spell its roles differently — as long as it SAYS so, the gate enforces ITS table
        cases.append(("clean/declared-own-spelling", _fixture(
            base, "clean_own", ["shipments"], ["fact_acme_shipments"],
            "serving: {naming: {marker: acme, roles: {view: {prefix: fact}, fact: {prefix: fact}}}}\n"),
            0, []))

        # ── MUTANTS — one per reject class ───────────────────────────────────────────────────────
        # 1. collision where the raw name carries a source-system infix
        cases.append(("mutant/collision-with-infix", _fixture(
            base, "m_infix", ["acme_lm_shipments", "acme_lm_orders"], ["acme_lm_shipments"]), 1,
            ["EQUALS a raw source name", "rename to: 'shipments'"]))
        # 2. collision where the raw name is ALREADY the clean business noun — the fixed defect.
        cases.append(("mutant/collision-already-clean-noun", _fixture(
            base, "m_clean", ["shipments", "orders"], ["shipments"]), 1,
            ["EQUALS a raw source name", "rename to: 'v_acme_shipments'",
             "ALREADY the clean business noun", "<role>_<marker>_<business noun>",
             "serving:", "naming:", "MAC012 prohibits"]))
        # 3. collision with a raw descriptor STEM that declares no table.name
        stem_root = _fixture(base, "m_stem", [], ["shipments"])
        (stem_root / "data" / "sources" / "shipments.yaml").write_text(
            "metadata:\n  kind: raw_source\n", encoding="utf-8")
        cases.append(("mutant/collision-with-raw-stem", stem_root, 1, ["EQUALS a raw source name"]))
        # 4. THE MEASURED SPLIT: `fact_` vs `v_` for the same relation, with nothing declared. The
        #    old ellipsis let this through; the closed table refuses it and names the member.
        cases.append(("mutant/role-outside-closed-table-default", _fixture(
            base, "m_role", ["shipments"], ["fact_shipments"]), 1,
            ["closed role table", "rename to: 'v_acme_shipments'",
             "meant the `fact` kind", "the role table is closed at", "NOT roles:"]))
        # 5. a pipeline STAGE token leading a served name
        cases.append(("mutant/role-is-a-pipeline-stage", _fixture(
            base, "m_stage", ["shipments"], ["stg_acme_shipments"]), 1,
            ["closed role table", "rename to: 'v_acme_shipments'"]))
        # 6. DECLARED: no role at all — declared bundles are held to the full build-shape
        cases.append(("mutant/declared-role-missing", _fixture(
            base, "m_norole", ["orders"], ["shipments"], _DECLARED), 1,
            ["DECLARES its role table", "rename to: 'v_acme_shipments'"]))
        # 7. DECLARED: role fine, marker missing on a kind that requires it
        cases.append(("mutant/declared-marker-missing", _fixture(
            base, "m_nomarker", ["orders"], ["v_shipments"], _DECLARED), 1,
            ["declared serving marker", "rename to: 'v_acme_shipments'"]))
        # 8. declared with no marker -> SETUP (exit 2), never a silent pass
        cases.append(("mutant/declared-without-marker", _fixture(
            base, "m_nomk", ["shipments"], ["v_acme_shipments"],
            "serving:\n  naming:\n    roles: {view: {prefix: v}}\n"), 2,
            ["declares `serving.naming` with no `marker`"]))
        # 9. declared kind outside the closed set -> SETUP
        cases.append(("mutant/declared-unknown-kind", _fixture(
            base, "m_kind", ["shipments"], ["v_acme_shipments"],
            "serving: {naming: {marker: acme, roles: {cube: {prefix: c}}}}\n"), 2,
            ["is not a relation kind", "The kinds are CLOSED"]))
        # 10. the legacy free-text regex declaration -> SETUP, pointed at the structural form
        cases.append(("mutant/declared-legacy-regex", _fixture(
            base, "m_legacy", ["shipments"], ["v_acme_shipments"],
            "serving: {naming: {marker: acme, pattern: '^v_acme_[a-z_]+$'}}\n"), 2,
            ["unverifiable", "serving:"]))
        # 11. THE INTERCEPTED CONTRADICTION: the x- spelling this gate used to publish. The schema
        #     rejects it and MAC012 prohibits it, so honouring it would leave the framework holding
        #     two opposite policies. It is intercepted and redirected to the core key.
        cases.append(("mutant/x-extension-declaration", _fixture(
            base, "m_xkey", ["shipments"], ["v_acme_shipments"],
            "x-serving-naming:\n  pattern: '^v_acme_[a-z_]+$'\n"), 2,
            ["PROHIBITED", "MAC012", "additionalProperties:false", "serving:", "naming:"]))
        # 12. unreadable manifest -> SETUP, never a verdict on names whose convention is unknown
        cases.append(("mutant/manifest-not-yaml", _fixture(
            base, "m_badyaml", ["shipments"], ["v_acme_shipments"], "serving: [\n"), 2,
            ["not readable YAML"]))

        # 13. the FRAMEWORK's own default table unreadable -> SETUP. The gate keeps no second copy
        #     of that table (one fact, one home: mac.schema.json), so "cannot read it" must decline
        #     to judge rather than fall back on a literal that could silently disagree with it.
        cases.append(("mutant/framework-default-table-unreadable",
                      _fixture(base, "m_noschema", ["shipments"], ["v_acme_shipments"]), 2,
                      ["default role table could not be read", "does not keep a second copy"]))
        _no_schema = {"m_noschema"}

        for label, root, want_rc, want_text in cases:
            buf = io.StringIO()
            global _SCHEMA
            _kept, _SCHEMA = _SCHEMA, (base / "no-such-schema.json" if root.name in _no_schema
                                       else _SCHEMA)
            try:
                rc = run(root, out=buf)
            finally:
                _SCHEMA = _kept
            text = buf.getvalue()
            verdicts = [ln for ln in text.splitlines()
                        if ln.startswith("PASS:") or ln.startswith("FAIL:")]
            ok, notes = True, []
            if rc != want_rc:
                ok, _ = False, notes.append(f"exit {rc}, expected {want_rc}")
            # contract: exactly one verdict line for a judgement; none for a setup failure
            want_verdicts = 0 if want_rc == 2 else 1
            if len(verdicts) != want_verdicts:
                ok, _ = False, notes.append(f"{len(verdicts)} PASS:/FAIL: line(s), expected {want_verdicts}")
            if want_rc == 1 and verdicts and not verdicts[0].startswith("FAIL:"):
                ok, _ = False, notes.append("verdict line is not a FAIL:")
            if want_rc == 0 and verdicts and not verdicts[0].startswith("PASS:"):
                ok, _ = False, notes.append("verdict line is not a PASS:")
            # Fragments are matched against the WHITESPACE-NORMALISED message: the gate wraps its
            # prose, so a literal match would make the test fail on a line break rather than on a
            # missing rule — the test would then be measuring the wrap width, not the teaching.
            flat = " ".join(text.split())
            for frag in want_text:
                if frag not in text and " ".join(frag.split()) not in flat:
                    ok, _ = False, notes.append(f"message never says {frag!r}")
            # STANDING GUARD, generalised: a refusal must never hand back the name it refused, AND
            # every name this gate suggests must be a name this gate would accept. A gate that
            # prescribes what it then refuses is the defect this file has now been rewritten twice for.
            try:
                guard_conv = _declared_convention(root) or _default_convention(
                    _marker(_descriptors(root / "data" / "datasets"), root))
            except SetupError:
                guard_conv = None
            if guard_conv is not None:
                raws = _descriptors(root / "data" / "sources")
                raw_tokens = {d["name"] for d in raws.values()} | set(raws.keys())
                for line in text.splitlines():
                    m = re.search(r"served name '([^']+)' .* -> rename to '([^']+)'", line)
                    if not m:
                        continue
                    refused, fix = m.group(1), m.group(2)
                    if fix == refused:
                        ok, _ = False, notes.append(f"suggests the refused name back ({refused!r})")
                    bad = _violations(fix, raw_tokens, guard_conv)
                    if bad:
                        ok, _ = False, notes.append(
                            f"suggests {fix!r}, which this gate would refuse ({bad[0][0]})")
            print(f"  {'ok  ' if ok else 'FAIL'}  {label}"
                  + ("" if ok else "  <- " + "; ".join(notes)))
            if not ok:
                failures.append(label)

    print()
    if failures:
        print(f"FAIL: served-name-distinct self-test — {len(failures)} of {len(cases)} case(s) wrong: "
              f"{', '.join(failures)}")
        return 1
    print(f"PASS: served-name-distinct self-test — {len(cases)} case(s): every mutant refused with a "
          f"conforming rename, every clean fixture accepted, every suggestion itself acceptable")
    return 0


def main(argv) -> int:
    if len(argv) == 2 and argv[1] == "--self-test":
        return self_test()
    if len(argv) != 2 or argv[1].startswith("-"):
        print("usage: check_served_name_distinct.py <bundle-root>\n"
              "       check_served_name_distinct.py --self-test", file=sys.stderr)
        return 2                     # SETUP, not a verdict: the gate judged nothing
    return run(Path(argv[1]).resolve())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
