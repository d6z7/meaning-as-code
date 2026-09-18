#!/usr/bin/env python3
"""mac_references.py — MEASURE a bundle's PHYSICAL referential structure, through the connector.

    python3 tools/mac_references.py <root> [--plane sources|served]
                                    [--dry-run] [--verify] [--json] [--self-test]

WHAT THIS FILE IS ABOUT, AND THE WORD IT REFUSES TO USE
-------------------------------------------------------
This tool writes the DATA plane's own picture of how relations point at each other: RELATIONS,
COLUMNS, KEYS, REFERENCES, CARDINALITY, PARTICIPATION. It never says `concept` and it never says
`edge`. Those are the MEANING plane's words, and the two planes had been sharing one artifact.

The defect, measured on a live bundle before this existed: the physical half of an ER picture was
read out of the ontology's relationship file. Twenty-five entries there declared `level: physical,
type: foreign_key` and were keyed BY CONCEPT — `endpoints.from.concept`, `endpoints.to.concept` —
with the actual physical content (which relation, which column) flattened into a `join_rule` STRING
that a consumer had to re-parse with a regular expression. The consequences were not cosmetic:

  * a bundle with no ontology could not draw a physical diagram AT ALL, however completely its
    warehouse was measured — the picture needed a concept to exist before a foreign key could;
  * the crow's feet were AUTHORED claims, so an optional relationship and a mandatory one drew
    identically whenever the author had not thought about participation;
  * a reference whose two columns are spelled differently was unreachable, because a concept-keyed
    entry is written by a person who already believes the two things are the same thing.

A PHYSICAL REFERENCE IS KEYED BY RELATION AND COLUMN, on both ends, as fields — never as a string
to be parsed and never through a business object. That is the whole reason this file exists.

THE FOUR THINGS IT MUST GET RIGHT, and how each is arranged for
---------------------------------------------------------------
1. THE NAME IS NEVER THE EVIDENCE. Candidate generation does not look at column names at all; it
   pairs every column against every measured KEY COLUMN and prunes on TYPE CLASS and on the
   profiles' distinct counts. `name_match` is carried as a LABEL for a reader and is not an input
   to any verdict. Measured on the reference bundle: name matching would have proposed 14 of 171
   surviving candidates and would have missed 8 of the 17 drawn references.

2. A REFERENCE WITH NO TARGET IS REPORTED, NOT INVENTED AND NOT DROPPED. A column that follows the
   bundle's OWN key-naming convention, is not itself a key, and has no measured parent, leaves here
   as `references_dangling` with `to: null`. Its basis is SELF-CALIBRATED from the bundle's measured
   key column names and is stated in the file, because it is weaker evidence than a measurement
   against a parent — there is no parent to measure against. A bundle with no naming convention gets
   no dangling detection, and that must read as "not detectable here", never as "none exist".

3. PARTICIPATION IS NOT CARDINALITY, and the artifact carries them as two separate blocks measured
   two different ways. Cardinality comes from the maximum row count per value on each side;
   participation comes from comparing the parent's used key values against its whole key domain and
   the child's non-null rows against its whole row count. On the reference bundle all three of the
   busiest references are `one_to_many` while one parent has 10 of 74 rows never referenced, another
   52,801 of 104,990, and a third 0 of 2,517. Keys alone would draw all three identically mandatory.

4. INCLUSION ALONE INVENTS PARENTS. A dense integer column falls inside a wider dense integer key BY
   ARITHMETIC. The first version of this measurement admitted 37 references on inclusion alone,
   among them a demographic column "referencing" a product key at 1.000000 over 104,990 rows. A
   second, independent test — DOMAIN EXERCISE — is therefore required: a real reference covers a
   real fraction of the parent key's value span or of its distinct values. Every drawn reference on
   the reference bundle scores >= 0.859 coverage or >= 0.875 span; every coincidental one scores
   <= 0.286. Both floors are written into the `admission:` block of EVERY file, so no entry can be
   read without the numbers that judged it, and a reviewer who disagrees can see the consequence
   without re-running anything. Nothing that decides a verdict lives in a Python constant.

WHAT IT REFUSES TO DO
---------------------
  * It never asserts what it did not measure. A relation it could not read gets NO FILE.
  * It never chooses between two parents that measure identically. `orders.CurrencyCode` includes
    perfectly into TWO key columns of one relation, 5 of 5 values, 0 orphans, against both. Value
    inclusion cannot separate them, so BOTH are recorded with `ambiguous_with` and `needs_ruling`,
    and neither is silently dropped. Picking one would be a fabrication dressed as a measurement.
  * It records REJECTIONS WITH THEIR NUMBERS. An operator who cannot see what was considered cannot
    tell a missing reference from an unconsidered one.

DETERMINISM. Two runs over unchanged data produce BYTE-IDENTICAL per-relation files. Everything is
sorted by an explicit total order, every ratio is rounded to a fixed width, and THE CLOCK IS NOT IN
THEM: `measured_at` lives only in the run record beside them, which is the one file that moves. That
is deliberate — a family that churns on every run stops being re-derived, which is how a hand-typed
plane rots back in. `--verify` re-derives in memory and compares bytes, writing nothing.

THE SEAM. The reader is opened by `mac_sample.open_reader`, imported rather than re-implemented:
that function is already documented as THE seam (manifest `runtime.connector` -> registry ->
`validate_config` -> `base_dir` by signature), and a second opener beside it would be a second home
for the one fact about how a bundle is opened. `harvest.py` is NOT used and cannot be: it is
hardwired to one cloud catalog and cannot reach a local-file bundle at all.

EXIT CODES. 0 every in-scope relation was measured · 1 a finding about the bundle (a relation whose
profile carries no key, a descriptor whose relation the catalog does not have, a `--verify` that
differs) · 2 could not run (no connector, unresolvable, driver absent, an EMPTY POPULATION). Every
verdict line carries its DENOMINATOR.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import glob
import io
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:                                                        # noqa: E402
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mac_diag as D                                                             # noqa: E402
from mac_sample import SampleRefused, open_reader                                # noqa: E402

NAME = "mac_references"
CONTRACT = "mac.references/1"
TOOL = "mac_references.py/1"
SCHEMA_VERSION = "0.1.14-develop"
RUN_RECORD = "references.run.json"

# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE TWO PHYSICAL PLANES — and why one tool measures both rather than two tools measuring one each.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# A warehouse has TWO populations of relations and they point at each other differently. The LANDED
# relations (`data/sources/*.yaml`) carry the delivery's own referential structure, redundancy and
# all. The SERVED relations (`data/datasets/*.yaml`) carry what the transforms left, which is the
# structure a question actually traverses. Both are PHYSICAL: relations, columns, keys, references,
# cardinality, participation. NEITHER reads `ontology/edges.yaml`, and the served plane is not one
# step closer to the ontology for being downstream — an ontology edge relates BUSINESS OBJECTS, and
# nothing here has an opinion about a business object.
#
# WHY NOT A SECOND TOOL. Every verdict in this file — the type-class prune, the inclusion floor, the
# DOMAIN EXERCISE second test, the direction resolution, the ambiguity refusal, the dangling
# self-calibration — is plane-independent arithmetic, and the estate's measured failure mode is one
# fact with two homes. A `mac_references_served.py` would be that, and the first floor to drift
# between the two copies would be invisible in both.
#
# THE ONE THING THAT GENUINELY DIFFERS IS WHERE THE PARENT KEY COMES FROM, and it differs because
# the two descriptor planes mean different things by `role`:
#   sources   the profile's MEASURED key (`identity_evidence.key`). A source descriptor's own note
#             calls `role: value` "the NEUTRAL physical role and not a ruling", so a role there is
#             not evidence of identity and this tool will not read one.
#   served    the descriptor's DECLARED key roles (`primary_key` / `composite_key_part`). On a served
#             relation the role IS the authored contract — it is what the promotion step decided and
#             what `sdk/project/er_model.py#KEY_ROLES` already reads — so reading it here is reading
#             the plane's own statement of identity, not inferring one. It is a DECLARATION and the
#             artifact says so in `key_source`, so a reader never has to guess which it was.
# Everything a VERDICT turns on is still measured against the warehouse either way: the parent key
# only decides which pairs are CANDIDATES.
#
# THE PAIRING ITSELF IS NOT DECLARED HERE. `sdk/project/er_model.py#PLANES` owns which descriptor
# plane goes with which artifact directory, because the PROJECTOR and this DERIVER must never
# disagree about it and sdk may not import tools. This table adds only the two things the deriver
# owns and the projector has no use for: the refusal's unit noun, and where the parent key comes
# from. A second copy of `descriptors`/`out` here is exactly the drift both files warn about.
from sdk.project.er_model import DEFAULT_PLANE, PLANES as _PLANE_DIRS          # noqa: E402

_PLANE_EXTRA = {
    "sources": {"unit": "source descriptor", "key_from": "profile"},
    "served": {"unit": "served dataset descriptor", "key_from": "descriptor_role"},
}
PLANES = {pl: {**dirs, **_PLANE_EXTRA[pl]} for pl, dirs in _PLANE_DIRS.items()}

#: The three `role` values that declare identity on a SERVED descriptor. `foreign_key` is
#: deliberately NOT here: a declared foreign key is a CLAIM about a target, and this tool measures
#: those rather than believing them — admitting it as a parent endpoint would let an author's
#: assumption enter the candidate set as evidence.
DECLARED_KEY_ROLES = ("primary_key", "composite_key_part")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE ADMISSION RULE — every number a verdict turns on. Written into every file it judges.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# These are NOT tuning knobs hidden in code. They are copied verbatim into the `admission:` block of
# each artifact, and each entry restates its own arithmetic against them in a sentence, because the
# estate's recurring failure is a threshold nobody could see and therefore nobody could argue with.
#
# domain_exercise_floor IS CALIBRATED ON ONE WAREHOUSE. The measured separation there is clean and
# wide (drawn >= 0.859 coverage or >= 0.875 span; coincidental <= 0.286) and 0.50 sits in the gap.
# It is one dataset. A second warehouse may land a real reference inside that gap — which is exactly
# why the number travels in the file rather than living here alone.
ADMISSION = {
    "inclusion_required": 1.0,
    "near_miss_floor": 0.995,
    "domain_exercise_floor": 0.50,
    "distinct_tolerance": 0.05,
    "min_child_distinct": 2,
}

#: Verbatim engine types -> a comparison class. Two columns of different classes cannot reference
#: one another, and OTHER never proposes: an unrecognised type is a type this tool cannot reason
#: about, and guessing would be the invention it exists to prevent.
TYPECLASS = (
    (("tinyint", "smallint", "integer", "bigint", "hugeint", "int"), "INTEGRAL"),
    (("decimal", "numeric", "double", "real", "float"), "DECIMAL"),
    (("varchar", "char", "text", "string", "uuid"), "TEXT"),
    (("timestamp", "date", "time"), "TEMPORAL"),
    (("boolean", "bool"), "BOOLEAN"),
)

#: Ratios are rounded to a FIXED width before they reach a file. Without this the artifact churns on
#: the last bit of a float and a `--verify` can never be clean.
RATIO_DIGITS = 6

#: EXPLICIT, per-process connector injection for the offline self-test — the same shape and the same
#: registry guard mac_sample uses, passed through so a fixture can never shadow a shipped `mac.*` id.
EXTRA_CONNECTORS = {}


class ReferencesRefused(Exception):
    """This bundle's references cannot be measured. Carries the exit code the refusal deserves."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE PURE HALF — type classes, prunes, verdicts, direction, dangling. No engine, no file, no clock.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def typeclass(t) -> str:
    low = str(t or "").strip().lower()
    for names, cls in TYPECLASS:
        for n in names:
            if low.startswith(n):
                return cls
    return "OTHER"


def ratio(n, d):
    """n/d rounded to the pinned width, or None when there is no denominator.

    A ZERO DENOMINATOR IS NOT A ZERO RESULT. Returning 0.0 for "nothing to divide by" is how an
    unmeasured column comes to read as a measured-and-empty one.
    """
    if not d:
        return None
    return round(n / d, RATIO_DIGITS)


def span_ratio(child_stat, parent_stat, tc):
    """Fraction of the PARENT key's value SPAN that the child's span covers. PURE — from profiles.

    ORDERED TYPES ONLY. TEXT has no meaningful min/max distance, so it returns None and the
    domain-exercise test falls through to `parent_coverage`, which every type has. Returning a
    number for TEXT by comparing string bounds would be arithmetic on a lexicographic accident.
    """
    cmn, cmx = child_stat.get("min"), child_stat.get("max")
    pmn, pmx = parent_stat.get("min"), parent_stat.get("max")
    if None in (cmn, cmx, pmn, pmx):
        return None
    try:
        if tc in ("INTEGRAL", "DECIMAL"):
            a, b, c, d = float(cmn), float(cmx), float(pmn), float(pmx)
        elif tc == "TEMPORAL":
            def f(s):
                return datetime.datetime.fromisoformat(str(s)).timestamp()
            a, b, c, d = f(cmn), f(cmx), f(pmn), f(pmx)
        else:
            return None
    except (TypeError, ValueError):
        return None
    if d - c <= 0:
        return None
    return round(max(0.0, (min(b, d) - max(a, c)) / (d - c)), RATIO_DIGITS)


def parent_endpoints(profiles) -> list:
    """Every measured KEY COLUMN in the bundle, with its role. The key is READ, never re-derived.

    INDIVIDUAL COLUMNS OF A COMPOSITE KEY ARE ENDPOINTS TOO, and that is not a nicety. On the
    reference bundle one relation's measured key is three columns; the reference that the name could
    never have found points at ONE of those three. A whole-key-only generator yields 5 endpoints
    there instead of 12 and that reference is structurally unreachable.

    A reference to a key PART targets a VALUE SET, not one row, so it is labelled `key_part` and its
    parent-side cardinality is measured rather than assumed — conflating it with `identity` would
    draw a crow's foot that says something the data does not.
    """
    out = []
    for rel in sorted(profiles):
        key = profiles[rel]["key"]
        for col in key:
            out.append({"relation": rel, "column": col,
                        "role": "identity" if len(key) == 1 else "key_part"})
    return out


def generate(catalog, profiles):
    """(candidates, pruned). PURE: the profiles and the catalog types do all of this work.

    Four prunes, each naming its own arithmetic. On the reference bundle they kill 857 of 1,028
    pairs (83.4 %) before a single statement is rendered, which is what makes the whole measurement
    a three-second gate rather than a ceremony.
    """
    parents = parent_endpoints(profiles)
    candidates, pruned = [], []
    for crel in sorted(catalog):
        cprof = profiles.get(crel) or {"cols": {}}
        for ccol, ctype in catalog[crel]["columns"]:
            cs = cprof["cols"].get(ccol, {})
            for p in parents:
                if p["relation"] == crel:
                    continue                      # a relation does not reference itself here
                ps = (profiles.get(p["relation"]) or {}).get("cols", {}).get(p["column"], {})
                ptype = dict(catalog.get(p["relation"], {}).get("columns", ())).get(p["column"], "")
                tc, ptc = typeclass(ctype), typeclass(ptype)
                row = {
                    "from": {"relation": crel, "column": ccol},
                    "to": {"relation": p["relation"], "column": p["column"]},
                    "parent_key_role": p["role"],
                    "child_type": str(ctype), "parent_type": str(ptype),
                    "name_match": ccol.casefold() == p["column"].casefold(),
                    "span_ratio": span_ratio(cs, ps, tc),
                }
                why = None
                if tc != ptc or tc == "OTHER":
                    why = (f"type class {tc} does not match the parent's {ptc}"
                           if tc != ptc else
                           f"type {ctype!r} is outside the classes this tool compares")
                elif (ps.get("nulls") or 0) != 0:
                    why = (f"the parent column carries {ps.get('nulls')} null(s), so it is not a "
                           f"key column of its relation")
                elif (cs.get("distinct") or 0) < ADMISSION["min_child_distinct"]:
                    why = (f"child distinct {cs.get('distinct')} < min_child_distinct "
                           f"{ADMISSION['min_child_distinct']}: a column with one value includes "
                           f"into anything and is not evidence")
                elif cs.get("distinct") and ps.get("distinct") and \
                        cs["distinct"] > ps["distinct"] * (1 + ADMISSION["distinct_tolerance"]):
                    why = (f"child distinct {cs['distinct']} > parent distinct {ps['distinct']} "
                           f"+{ADMISSION['distinct_tolerance']:.0%} tolerance: more values than the "
                           f"key has cannot all be in it")
                if why:
                    pruned.append({**row, "pruned_because": why})
                else:
                    candidates.append(row)
    considered = len(candidates) + len(pruned)
    return candidates, pruned, considered, parents


def derive_shape(m: dict) -> dict:
    """The measured counts -> inclusion, coverage, CARDINALITY and PARTICIPATION. PURE.

    CARDINALITY AND PARTICIPATION COME FROM DIFFERENT NUMBERS AND ARE KEPT APART, because the whole
    reason the picture is called an ER diagram is that it says both and they are not the same claim:
      cardinality.child   — can one parent VALUE have many child rows?      max_child_rows_per_value
      cardinality.parent  — can one child value match many parent ROWS?     max_parent_rows_per_value
      participation.child — does EVERY child row have a parent?             child_nonnull vs child_rows
      participation.parent— is EVERY parent key value referenced?           parent_used vs parent_distinct
    """
    nn = m.get("child_nonnull") or 0
    out = dict(m)
    out["inclusion"] = ratio(nn - (m.get("orphan_rows") or 0), nn)
    out["parent_coverage"] = ratio(m.get("parent_used") or 0, m.get("parent_distinct") or 0)
    card = {
        "child": "many" if (m.get("max_child_rows_per_value") or 0) > 1 else "one",
        "parent": "many" if (m.get("max_parent_rows_per_value") or 0) > 1 else "one",
    }
    part = {
        "child": "mandatory" if m.get("child_rows") == m.get("child_nonnull") else "optional",
        "parent": "mandatory" if m.get("parent_used") == m.get("parent_distinct") else "optional",
        "parent_unreferenced": (m.get("parent_distinct") or 0) - (m.get("parent_used") or 0),
        "child_without_parent": (m.get("child_rows") or 0) - (m.get("child_nonnull") or 0),
    }
    return out, card, part


def verdict(ev: dict, span: float | None) -> tuple:
    """(verdict, sentence). TWO independent tests, never one. The sentence restates the arithmetic.

    The second test is the one that matters. Run on inclusion alone this measurement admitted a
    demographic column as a reference to a product key at 1.000000 over 104,990 rows — a dense
    integer column falling inside a wider dense integer key by arithmetic, not by design.
    """
    inc, cov = ev.get("inclusion"), ev.get("parent_coverage")
    floor = ADMISSION["domain_exercise_floor"]
    if inc is None:
        return "no_denominator", ("the child column has no non-null rows, so there is no "
                                  "denominator to judge inclusion on")
    exercises = (span is not None and span >= floor) or (cov is not None and cov >= floor)
    if inc < ADMISSION["near_miss_floor"]:
        return "rejected", (
            f"inclusion {inc:.6f} < near_miss_floor {ADMISSION['near_miss_floor']} — "
            f"{ev['orphan_rows']} of {ev['child_nonnull']} non-null child rows carry a value "
            f"({ev['orphan_distinct']} distinct) that no parent row carries")
    if inc < ADMISSION["inclusion_required"]:
        return "near_miss", (
            f"inclusion {inc:.6f} >= near_miss_floor {ADMISSION['near_miss_floor']} but < "
            f"inclusion_required {ADMISSION['inclusion_required']} — {ev['orphan_rows']} orphan "
            f"row(s) over {ev['orphan_distinct']} orphan value(s). REPORTED, NOT DRAWN: one orphan "
            f"is a finding about the data, not a reason to hide the candidate")
    if not exercises:
        return "coincidental", (
            f"inclusion {inc:.6f} and it means nothing: the parent key domain is NOT exercised — "
            f"span_ratio {span} and parent_coverage {cov} are both below domain_exercise_floor "
            f"{floor}. A dense column falls inside a wider dense key by arithmetic")
    return "real", (
        f"inclusion {inc:.6f} over {ev['child_nonnull']} non-null child row(s) "
        f"({ev['orphan_rows']} orphan row(s) over {ev['orphan_distinct']} orphan value(s)) >= "
        f"inclusion_required {ADMISSION['inclusion_required']}; the parent key domain IS exercised "
        f"(span_ratio {span}, parent_coverage {cov} against floor {floor}). PARTICIPATION IS A "
        f"SEPARATE FACT and is measured in its own block")


def resolve_direction(results):
    """Which of the real inclusions is DRAWN. Derived from the measured key roles, never guessed.

    Three rules, each the answer to a picture that was actually wrong without it:
      * MUTUAL INCLUSION. When both directions hold, the reference points AT the `identity`
        endpoint — one row — and the reverse is `superseded_by_reverse`. Without this every mutual
        pair draws twice, once in each direction.
      * TWO PARENTS, ONE IDENTITY. When one child column really includes into both an `identity`
        key and a `key_part`, the identity wins and the other is `superseded_by_identity`. Without
        this, date-like columns hang off every relation that happens to key on a date.
      * NEITHER SIDE IS AN IDENTITY. `undecided_mutual` — recorded, not drawn, and named as needing
        a ruling. Two relations at the same grain is a modelling question, not a measurement.
    Anything left over with two equally-ranked parents is `ambiguous_with` and IS drawn on both,
    because value inclusion genuinely cannot separate them and choosing would be fabrication.
    """
    real = {(r["from"]["relation"], r["from"]["column"],
             r["to"]["relation"], r["to"]["column"]): r
            for r in results if r["verdict"] == "real"}
    for (cr, cc, pr, pc), r in real.items():
        back = real.get((pr, pc, cr, cc))
        if back is None:
            r["direction"] = "drawn"
            continue
        r["mutual_with"] = f"{pr}.{pc}"
        if r["parent_key_role"] == "identity" and back["parent_key_role"] != "identity":
            r["direction"] = "drawn"
        elif r["parent_key_role"] != "identity" and back["parent_key_role"] == "identity":
            r["direction"] = "superseded_by_reverse"
            r["superseded_by"] = [f"{pr}.{pc} is a key part while the reverse points at an identity"]
        else:
            r["direction"] = "undecided_mutual"
            r["needs_ruling"] = (
                f"{cr}.{cc} and {pr}.{pc} include into each other and NEITHER is a whole-relation "
                f"identity, so no measurement can say which relation is the parent. Two relations "
                f"at the same grain is a modelling ruling, not a measurement")
    by_child = defaultdict(list)
    for r in real.values():
        if r.get("direction") == "drawn":
            by_child[(r["from"]["relation"], r["from"]["column"])].append(r)
    for rs in by_child.values():
        if len(rs) < 2:
            continue
        ident = [r for r in rs if r["parent_key_role"] == "identity"]
        # AN IDENTITY SETTLES IT. A reference into a whole-relation key names ONE ROW; one into a
        # key PART names a value set, so when both hold the identity is the parent and the other is
        # superseded — NOT ambiguous. Calling the settled case ambiguous would ask an operator to
        # rule on a question the measured key roles have already answered.
        remaining = ident if ident else rs
        for r in rs:
            if r not in remaining:
                r["direction"] = "superseded_by_identity"
                r["superseded_by"] = sorted(
                    f"{o['to']['relation']}.{o['to']['column']}" for o in remaining)
                continue
            if len(remaining) < 2:
                continue
            others = sorted(f"{o['to']['relation']}.{o['to']['column']}"
                            for o in remaining if o is not r)
            r["ambiguous_with"] = others
            r["needs_ruling"] = (
                f"{r['from']['relation']}.{r['from']['column']} includes perfectly into "
                f"{', '.join(others)} as well, on the same evidence and at the same key role. "
                f"Value inclusion cannot separate them; BOTH are recorded and neither is silently "
                f"chosen")
    for r in results:
        r.setdefault("direction", None)
    return results


def key_name_convention(profiles) -> tuple:
    """(suffixes, key_columns). SELF-CALIBRATED from THIS bundle's own measured key column names.

    Never hardcoded. A suffix is this bundle's convention only if at least two of its measured key
    columns carry it. A bundle whose keys follow no convention gets an EMPTY list here and therefore
    no dangling detection at all — which the artifact must render as "not detectable here", never as
    "none exist". That distinction is the difference between a silence and a claim.
    """
    keycols = sorted({c for p in profiles.values() for c in p["key"]})
    counts = Counter()
    for k in keycols:
        for n in (3, 4, 5):
            if len(k) > n:
                counts[k[-n:]] += 1
    # TIE-BREAK TOWARD THE SHORTER SUFFIX, deliberately. Two key columns spelled `AlphaRef` and
    # `BetaRef` share BOTH `Ref` and `aRef` at the same count, and `aRef` is an accident of those two
    # names while `Ref` is the convention. Taking the longer one would narrow the detector to the
    # sample it was calibrated on, which is the opposite of what a self-calibrated rule is for.
    conv = sorted((s for s, n in counts.items() if n >= 2),
                  key=lambda s: (-counts[s], len(s), s))[:1]
    return conv, keycols


def find_dangling(catalog, profiles, results, conv):
    """Columns that follow the bundle's key convention, are not keys, and have NO measured parent."""
    drawn = {(r["from"]["relation"], r["from"]["column"])
             for r in results if r.get("direction") in ("drawn", "superseded_by_identity",
                                                        "superseded_by_reverse")}
    is_key = {(rel, c) for rel, p in profiles.items() for c in p["key"]}
    measured_against = defaultdict(int)
    admitted = defaultdict(int)
    for r in results:
        k = (r["from"]["relation"], r["from"]["column"])
        measured_against[k] += 1
        if r["verdict"] == "real":
            admitted[k] += 1
    out = defaultdict(list)
    for rel in sorted(catalog):
        for col, _typ in catalog[rel]["columns"]:
            if not conv or not any(col.endswith(s) for s in conv):
                continue
            if (rel, col) in drawn or (rel, col) in is_key:
                continue
            st = (profiles.get(rel) or {}).get("cols", {}).get(col, {})
            rows = (profiles.get(rel) or {}).get("rows")
            if st.get("distinct") and rows and st["distinct"] == rows:
                continue          # unique within its own relation: an ALTERNATE KEY, not a reference
            out[col].append({
                "relation": rel, "column": col,
                "distinct": st.get("distinct"), "nulls": st.get("nulls"),
                "min": st.get("min"), "max": st.get("max"),
                "candidate_parents_measured": measured_against[(rel, col)],
                "candidate_parents_admitted": admitted[(rel, col)],
            })
    return dict(out)


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE MEASUREMENT — one statement per candidate. The half a fixture replaces.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# Rendering the statement and RUNNING it are split so the self-test can measure real numbers over
# in-memory columns without a database driver, while the rendered text stays assertable on its own.

MEASURE_SQL = """SELECT
 (SELECT count(*) FROM c) AS child_rows,
 (SELECT count(v) FROM c) AS child_nonnull,
 (SELECT count(DISTINCT v) FROM c) AS child_distinct,
 (SELECT count(*) FROM c WHERE v IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM p WHERE p.v = c.v)) AS orphan_rows,
 (SELECT count(DISTINCT v) FROM c WHERE v IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM p WHERE p.v = c.v)) AS orphan_distinct,
 (SELECT count(*) FROM {pr}) AS parent_rows,
 (SELECT count(*) FROM p) AS parent_distinct,
 (SELECT count(DISTINCT v) FROM c WHERE v IS NOT NULL
    AND EXISTS (SELECT 1 FROM p WHERE p.v = c.v)) AS parent_used,
 (SELECT max(n) FROM (SELECT count(*) n FROM c WHERE v IS NOT NULL GROUP BY v) q1)
   AS max_child_rows_per_value,
 (SELECT max(n) FROM (SELECT count(*) n FROM pv GROUP BY v) q2) AS max_parent_rows_per_value"""

MEASURE_HEAD = ("WITH c AS (SELECT {cc} AS v FROM {cr}),\n"
                "     pv AS (SELECT {pc} AS v FROM {pr} WHERE {pc} IS NOT NULL),\n"
                "     p AS (SELECT DISTINCT v FROM pv)\n")

_COUNTS = ("child_rows", "child_nonnull", "child_distinct", "orphan_rows", "orphan_distinct",
           "parent_rows", "parent_distinct", "parent_used", "max_child_rows_per_value",
           "max_parent_rows_per_value")


def render_measurement(conn, cand, namespaces) -> str:
    """The EXACT statement this tool would run for one candidate. PURE — no driver, no socket."""
    from sdk.connector.base import RelationRef
    cr = conn.qualify(RelationRef(namespace=namespaces[cand["from"]["relation"]],
                                  name=cand["from"]["relation"]))
    pr = conn.qualify(RelationRef(namespace=namespaces[cand["to"]["relation"]],
                                  name=cand["to"]["relation"]))
    cc = conn.quote_identifier(cand["from"]["column"])
    pc = conn.quote_identifier(cand["to"]["column"])
    return (MEASURE_HEAD.format(cc=cc, cr=cr, pc=pc, pr=pr)
            + MEASURE_SQL.format(pr=pr))


class SqlMeasurer:
    """One candidate -> the ten exact counts, through the connector's own read verb."""

    def __init__(self, conn, namespaces):
        self.conn, self.namespaces, self.statements = conn, namespaces, 0

    def __call__(self, cand) -> dict:
        from sdk.connector import bind
        from sdk.connector.base import ConnectorError, exit_code_for
        body = render_measurement(self.conn, cand, self.namespaces)
        try:
            res = self.conn.read(bind(body, params={}, user_values=(), purpose="reference"))
        except ConnectorError as exc:
            raise ReferencesRefused(
                f"{cand['from']['relation']}.{cand['from']['column']} -> "
                f"{cand['to']['relation']}.{cand['to']['column']}: {exc}",
                exit_code_for(exc)) from exc
        self.statements += 1
        if not res.rows:
            raise ReferencesRefused(
                f"the engine returned NO ROW for a measurement of "
                f"{cand['from']['relation']}.{cand['from']['column']}; an aggregate that answers "
                f"nothing is not a measurement of zero", 2)
        row = dict(res.rows[0])
        return {k: (int(row[k]) if row.get(k) is not None else None) for k in _COUNTS}


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# READING THE BUNDLE — the population, the catalog, the measured keys.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_plane(root: Path, plane: str = DEFAULT_PLANE):
    """(relations, profiles, findings). The population is `PLANES[plane]["descriptors"]`.

    A descriptor names the relation and its namespace; the profile beside it carries the per-column
    census, and — on the SOURCES plane — the measured key. A relation with one and not the other is a
    FINDING, not something to fill in: half a measurement is how a plane comes to disagree with
    itself.

    THE PROFILE DIRECTORY IS SHARED BY BOTH PLANES and that is not a collision: profiles are keyed by
    DESCRIPTOR STEM, a served stem is a name the promotion step coined (`check_served_name_distinct`
    gates exactly that), and `mac_profile.py` already accepts a stem "under data/datasets or
    data/sources" and writes both to `data/profiles/`. One census plane, two descriptor planes.

    ON THE SERVED PLANE THE KEY COMES FROM THE DESCRIPTOR, not the profile — see PLANES above for
    why the two descriptor planes mean different things by `role`. It is read from the roles the
    promotion step declared and it is carried as a declaration; nothing here re-derives a key and
    nothing here promotes a declaration to a measurement.
    """
    spec = PLANES[plane]
    ddir = spec["descriptors"]
    relations, profiles, findings = {}, {}, []
    declared_keys = {}
    for p in sorted(glob.glob(str(root / ddir / "*.yaml"))):
        doc = _load(Path(p))
        stem = doc.get("of") or Path(p).stem
        tbl = doc.get("table") or {}
        if not tbl.get("name"):
            findings.append({"relation": stem, "exit": 1,
                             "detail": f"{ddir}/{Path(p).name} declares no table.name, so "
                                       f"there is no relation to measure"})
            continue
        relations[stem] = {"name": tbl.get("name"), "schema": tbl.get("schema"),
                           "file": f"{ddir}/{Path(p).name}"}
        if spec["key_from"] == "descriptor_role":
            declared_keys[stem] = [c["name"] for c in (doc.get("columns") or [])
                                   if c.get("name") and c.get("role") in DECLARED_KEY_ROLES]
    for p in sorted(glob.glob(str(root / "data" / "profiles" / "*.yaml"))):
        doc = _load(Path(p))
        stem = doc.get("of") or Path(p).stem
        profiles[stem] = {
            "rows": (doc.get("profile") or {}).get("rows"),
            "cols": {c["name"]: c for c in (doc.get("columns") or []) if c.get("name")},
            "key": (declared_keys.get(stem, []) if spec["key_from"] == "descriptor_role"
                    else list(((doc.get("identity_evidence") or {}).get("key")) or [])),
            "file": f"data/profiles/{Path(p).name}",
        }
    return relations, profiles, findings


def key_source(plane: str, stem: str, profiles: dict) -> str:
    """Where THIS plane's parent key came from, as the artifact records it. One home for the string."""
    if PLANES[plane]["key_from"] == "descriptor_role":
        return (f"{PLANES[plane]['descriptors']}/{stem}.yaml#columns[].role in "
                f"{list(DECLARED_KEY_ROLES)} — DECLARED by the promotion step, not re-derived here")
    return f"{profiles[stem]['file']}#identity_evidence.key"


def read_catalog(conn, sources, profiles, plane: str = DEFAULT_PLANE):
    """(catalog, namespaces, findings). Types come from the ENGINE, never from a descriptor.

    The descriptor's `type` is a declaration; `describe_relation` is a measurement, and the two
    vocabularies genuinely disagree across engines. The candidate prune compares type CLASSES, so
    comparing declared spellings would prune on a naming convention.
    """
    from sdk.connector.base import AdapterError, RelationRef
    catalog, namespaces, findings = {}, {}, []
    if "describe_relation" not in getattr(conn, "supports", ()):
        raise ReferencesRefused(
            f"{conn.id} has no catalog verb, so the column types a candidate prune compares cannot "
            f"be MEASURED; nothing is written", 2)
    for stem in sorted(sources):
        src = sources[stem]
        ns = tuple(s for s in (src.get("schema"),) if s)
        ref = RelationRef(namespace=ns, name=src["name"])
        try:
            schema = conn.describe_relation(ref)
        except AdapterError as exc:
            findings.append({"relation": stem, "exit": 1,
                             "detail": f"{src['file']} names relation "
                                       f"{'.'.join((*ns, src['name']))} which the catalog does not "
                                       f"have ({exc}); NOTHING is written for it"})
            continue
        cols = [(c.name, c.type) for c in schema.columns]
        if not cols:
            findings.append({"relation": stem, "exit": 2,
                             "detail": f"the catalog returned ZERO columns for {src['name']}; that "
                                       f"is not a measurement, so this relation is not judged"})
            continue
        if stem not in profiles or not profiles[stem]["key"]:
            # THE WORD IS PLANE-SPECIFIC AND THAT IS THE POINT. A sources relation's key is
            # MEASURED; a served relation's is DECLARED by the promotion step. Printing one word for
            # both would tell a reader the served plane measured something it read.
            declared = PLANES[plane]["key_from"] == "descriptor_role"
            kind = "declared key" if declared else "measured key"
            where = (f"{PLANES[plane]['descriptors']}/{stem}.yaml#columns[].role in "
                     f"{list(DECLARED_KEY_ROLES)}" if declared
                     else f"data/profiles/{stem}.yaml#identity_evidence.key")
            findings.append({"relation": stem, "exit": 1,
                             "detail": f"{stem} has no {kind} ({where}); this tool READS the key "
                                       f"and will not re-derive one, so {stem} is not a parent "
                                       f"endpoint"})
        catalog[stem] = {"columns": cols, "relation": ".".join((*ns, src["name"]))}
        namespaces[stem] = ns
    return catalog, namespaces, findings


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE RENDER — measured facts -> the per-relation artifact. PURE, and it carries no clock.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _ref_id(r) -> str:
    """RELATION AND COLUMN ON BOTH ENDS. Never the relation pair alone.

    Two references can join the same pair on different columns (two date-like columns of one
    relation both pointing at one calendar). A renderer identifies a line by this id; keying on the
    pair collides and one of the two lines silently stops responding to selection. That regression
    has already happened once in this estate, on the ontology-derived model this replaces.
    """
    return (f"{r['from']['relation']}.{r['from']['column']}__"
            f"{r['to']['relation']}.{r['to']['column']}")


def _evidence(r) -> dict:
    ev = {k: r.get(k) for k in _COUNTS}
    ev["inclusion"] = r.get("inclusion")
    ev["parent_coverage"] = r.get("parent_coverage")
    ev["span_ratio"] = r.get("span_ratio")
    return ev


def _entry(r) -> dict:
    e = {
        "id": _ref_id(r),
        "from": dict(r["from"]),
        "to": dict(r["to"]),
        "parent_key_role": r["parent_key_role"],
        "verdict": r["verdict"],
        "drawn": r.get("direction") == "drawn",
        "cardinality": r["cardinality"],
        "participation": r["participation"],
        "evidence": _evidence(r),
        "name_match": r["name_match"],
        "admitted_because": r["because"],
    }
    for k in ("direction", "mutual_with", "superseded_by", "ambiguous_with", "needs_ruling"):
        if r.get(k):
            e[k] = r[k]
    return e


def _rejected(r) -> dict:
    return {
        "id": _ref_id(r),
        "from": dict(r["from"]), "to": dict(r["to"]),
        "parent_key_role": r["parent_key_role"],
        "verdict": r["verdict"],
        "evidence": _evidence(r),
        "name_match": r["name_match"],
        "rejected_because": r["because"],
    }


def _dangling_entry(carrier, others, conv, keycols, corroboration) -> dict:
    return {
        "id": f"{carrier['relation']}.{carrier['column']}__?",
        "from": {"relation": carrier["relation"], "column": carrier["column"]},
        "to": None,
        "verdict": "dangling",
        "basis": "key_naming_convention",
        "basis_detail": (
            f"SELF-CALIBRATED from this bundle, not hardcoded: of its {len(keycols)} measured key "
            f"column name(s), at least two end in {conv[0]!r}, so {conv[0]!r} is THIS bundle's "
            f"key-name suffix. This column carries it, is not itself a measured key, and no "
            f"relation in scope carries it as a key column. This is WEAKER evidence than a "
            f"measurement against a parent, because there is no parent to measure against"),
        "evidence": {
            "child_rows": carrier.get("rows"),
            "child_distinct": carrier.get("distinct"),
            "child_nulls": carrier.get("nulls"),
            "min": carrier.get("min"), "max": carrier.get("max"),
            "candidate_parents_measured": carrier.get("candidate_parents_measured"),
            "candidate_parents_admitted": carrier.get("candidate_parents_admitted"),
            "relations_matching_name": corroboration.get(carrier["column"]),
            "also_carried_by": others,
        },
        "note": (
            "A reference with NO TARGET RELATION. Reported, not invented and not dropped: the "
            "diagram must show this column as a reference that points nowhere, never as a plain "
            "attribute and never as a line to a relation that measurement did not admit"),
    }


def render_relation_file(stem, catalog, profiles, entries, rejected, dangling, scope,
                         plane: str = DEFAULT_PLANE) -> bytes:
    """One relation's artifact -> its exact bytes. PURE and CLOCKLESS, so a re-run is byte-identical.

    `admission:` is repeated in EVERY file on purpose. A reader opens one file, and an entry whose
    verdict depends on two floors must not be readable without them.
    """
    doc = {
        "metadata": {"schema_version": SCHEMA_VERSION, "generated_by": TOOL},
        "of": stem,
        "relation": catalog[stem]["relation"],
        "measurement": {
            "contract": CONTRACT,
            # WHICH OF THE TWO PHYSICAL PLANES THIS FILE IS. Without it a reader holding one
            # artifact cannot tell a landed relation's references from a served relation's, and the
            # two are different claims about different populations. See PLANES at the top of
            # tools/mac_references.py.
            "plane": plane,
            "descriptor_plane": PLANES[plane]["descriptors"],
            "key_source": key_source(plane, stem, profiles),
            "relations_in_scope": scope["relations_in_scope"],
            "parent_endpoints": scope["parent_endpoints"],
            "run_record": f"{PLANES[plane]['out']}/{RUN_RECORD}",
            "single_column_references_only": True,
            "note": (
                "SINGLE-COLUMN references only in this contract. A genuinely composite reference "
                "is therefore recorded here as its separate single-column parts, and that is "
                "SAID rather than left to be inferred from absence. The column NAME is never an "
                "input to a verdict; `name_match` is a label for a reader. No clock is written "
                "into this file so that two runs over unchanged data are byte-identical — the "
                "measurement time lives in the run record named above"),
        },
        "admission": dict(ADMISSION),
        "references": entries,
        "references_dangling": dangling,
        "candidates_rejected": rejected,
    }
    text = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True,
                          width=100)
    return text.encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE COMMAND
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def measure_bundle(root: Path, conn, measurer_factory=None, *, dry_run=False,
                   plane: str = DEFAULT_PLANE):
    """Everything except writing. Returns a record the writer and the reporter both read."""
    sources, profiles, findings = read_plane(root, plane)
    if not sources:
        raise ReferencesRefused("__EMPTY__", D.EMPTY_EXIT)
    catalog, namespaces, cat_findings = read_catalog(conn, sources, profiles, plane)
    findings += cat_findings
    if not catalog:
        raise ReferencesRefused(
            f"none of the {len(sources)} declared source relation(s) could be read from the "
            f"catalog, so NOTHING is written — a plane judged on an empty denominator has not been "
            f"judged", 2)
    keyed = {s: p for s, p in profiles.items() if s in catalog and p["key"]}
    prof_in_scope = {s: profiles[s] for s in catalog if s in profiles}
    candidates, pruned, considered, parents = generate(catalog, keyed)
    # Candidate generation needs the profile stats of EVERY in-scope relation, and the parent
    # endpoints only of the KEYED ones. Feeding it `keyed` for both would make a relation with no
    # measured key invisible as a CHILD too, which would hide its dangling columns.
    for rel in prof_in_scope:
        keyed.setdefault(rel, {**prof_in_scope[rel], "key": []})
    if dry_run:
        return {"dry": True, "candidates": candidates, "pruned": pruned, "considered": considered,
                "catalog": catalog, "namespaces": namespaces, "profiles": prof_in_scope,
                "parents": parents, "findings": findings, "sources": sources,
                "plane": plane}

    measurer = (measurer_factory or SqlMeasurer)(conn, namespaces)
    results = []
    for cand in sorted(candidates, key=lambda c: (c["from"]["relation"], c["from"]["column"],
                                                  c["to"]["relation"], c["to"]["column"])):
        counts = measurer(cand)
        ev, card, part = derive_shape(counts)
        r = {**cand, **ev, "cardinality": card, "participation": part}
        r["verdict"], r["because"] = verdict(ev, cand["span_ratio"])
        results.append(r)
    results = resolve_direction(results)
    conv, keycols = key_name_convention({s: p for s, p in prof_in_scope.items() if p["key"]})
    dangling = find_dangling(catalog, prof_in_scope, results, conv)
    return {"dry": False, "results": results, "pruned": pruned, "considered": considered,
            "catalog": catalog, "namespaces": namespaces, "profiles": prof_in_scope,
            "parents": parents, "findings": findings, "sources": sources,
            "plane": plane,
            "dangling": dangling, "convention": conv, "keycols": keycols,
            "statements": getattr(measurer, "statements", len(candidates))}


def compose(rec) -> dict:
    """{stem: bytes} — the artifact for every relation the tool could read. PURE."""
    catalog, profiles = rec["catalog"], rec["profiles"]
    scope = {"relations_in_scope": len(catalog), "parent_endpoints": len(rec["parents"])}
    by_child_entries = defaultdict(list)
    by_child_rejected = defaultdict(list)
    for r in rec["results"]:
        stem = r["from"]["relation"]
        if r["verdict"] == "real":
            by_child_entries[stem].append(_entry(r))
        else:
            by_child_rejected[stem].append(_rejected(r))
    conv, keycols = rec["convention"], rec["keycols"]
    by_child_dangling = defaultdict(list)
    for col, carriers in rec["dangling"].items():
        for c in carriers:
            prof = (profiles.get(c["relation"]) or {})
            others = sorted(
                ({"relation": o["relation"], "column": o["column"], "distinct": o["distinct"],
                  "nulls": o["nulls"], "min": o["min"], "max": o["max"]}
                 for o in carriers if o is not c),
                key=lambda o: o["relation"])
            by_child_dangling[c["relation"]].append(
                _dangling_entry({**c, "rows": prof.get("rows")}, others, conv, keycols,
                                rec.get("corroboration", {})))
    out = {}
    for stem in sorted(catalog):
        if stem not in profiles:
            continue                       # nothing measured about it; write nothing about it
        out[stem] = render_relation_file(
            stem, catalog, profiles,
            sorted(by_child_entries[stem], key=lambda e: e["id"]),
            sorted(by_child_rejected[stem], key=lambda e: e["id"]),
            sorted(by_child_dangling[stem], key=lambda e: e["id"]),
            scope, rec.get("plane", DEFAULT_PLANE))
    return out


def run_record(rec, files, *, engine: str) -> dict:
    """The global denominators, the admission rule ONCE, and every pruned pair with its reason.

    The pruned pairs live here rather than in the per-relation files because they are global by
    nature and bulky: 857 of them on the reference bundle. The per-relation file carries only what a
    human would argue with. This is also the only file carrying a clock.
    """
    results = rec["results"]
    by_verdict = Counter(r["verdict"] for r in results)
    by_direction = Counter(r.get("direction") for r in results if r["verdict"] == "real")
    plane = rec.get("plane", DEFAULT_PLANE)
    return {
        "contract": CONTRACT,
        "generated_by": TOOL,
        "measured_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "engine": engine,
        "plane": plane,
        "descriptor_plane": PLANES[plane]["descriptors"],
        "key_from": PLANES[plane]["key_from"],
        "admission": dict(ADMISSION),
        "denominators": {
            "relations_in_scope": len(rec["catalog"]),
            "relations_with_a_measured_key": sum(1 for p in rec["profiles"].values() if p["key"]),
            "parent_endpoints": len(rec["parents"]),
            "pairs_considered": rec["considered"],
            "pairs_pruned": len(rec["pruned"]),
            "pairs_measured": len(results),
            "statements_run": rec["statements"],
            "name_matching_would_propose": sum(1 for r in results if r["name_match"]),
            "files_written": len(files),
        },
        "verdicts": dict(sorted(by_verdict.items())),
        "directions": {str(k): v for k, v in sorted(by_direction.items(), key=lambda kv: str(kv[0]))},
        "dangling_columns": sorted(rec["dangling"]),
        "key_name_convention": {
            "suffixes": rec["convention"],
            "measured_key_columns": rec["keycols"],
            "note": ("SELF-CALIBRATED from this bundle's own measured key column names. An EMPTY "
                     "suffix list means dangling references are NOT DETECTABLE in this bundle — it "
                     "never means there are none"),
        },
        "findings": rec["findings"],
        "pruned_pairs": sorted(
            ({"from": p["from"], "to": p["to"], "pruned_because": p["pruned_because"]}
             for p in rec["pruned"]),
            key=lambda p: (p["from"]["relation"], p["from"]["column"],
                           p["to"]["relation"], p["to"]["column"])),
    }


def _report(rec, files, *, engine, verify, wrote, differs):
    lines = []
    d = run_record(rec, files, engine=engine)["denominators"]
    plane = rec.get("plane", DEFAULT_PLANE)
    lines.append(
        f"  plane {plane} · descriptors {PLANES[plane]['descriptors']} -> "
        f"{PLANES[plane]['out']} · parent key from {PLANES[plane]['key_from']}")
    lines.append(
        f"  seam {engine} · {d['relations_in_scope']} relation(s) in scope · "
        f"{d['relations_with_a_measured_key']} of {d['relations_in_scope']} carry a key")
    lines.append(
        f"  {d['parent_endpoints']} parent endpoint(s) · {d['pairs_considered']} pair(s) considered "
        f"· {d['pairs_pruned']} pruned "
        f"({d['pairs_pruned'] / d['pairs_considered']:.1%}) · {d['pairs_measured']} measured")
    lines.append(
        f"  name matching alone would propose {d['name_matching_would_propose']} of "
        f"{d['pairs_measured']} measured candidate(s)")
    drawn = [r for r in rec["results"] if r.get("direction") == "drawn"]
    amb = [r for r in drawn if r.get("ambiguous_with")]
    for r in sorted(drawn, key=_ref_id):
        lines.append(
            f"  [reference] {_ref_id(r)}  {r['cardinality']['child']}:{r['cardinality']['parent']} "
            f"child={r['participation']['child']} parent={r['participation']['parent']}"
            f"({r['participation']['parent_unreferenced']} of {r['parent_distinct']} unreferenced) "
            f"inclusion={r['inclusion']} name_match={r['name_match']}"
            + (f"  AMBIGUOUS_WITH {r['ambiguous_with']}" if r.get("ambiguous_with") else ""))
    for col, carriers in sorted(rec["dangling"].items()):
        lines.append(f"  [dangling ] {col}: no relation in scope carries it as a key; carried by "
                     + ", ".join(f"{c['relation']}({c['distinct']} distinct)" for c in carriers))
    for f in rec["findings"]:
        lines.append(f"  [finding  ] {f['relation']}: {f['detail']}")
    for f in differs:
        lines.append(f"  [DIFFERS  ] {f}")
    return lines, drawn, amb


def main(argv=None) -> int:                                                      # noqa: C901
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", help="the bundle root (REQUIRED; this command writes files)")
    ap.add_argument("--plane", choices=sorted(PLANES), default=DEFAULT_PLANE,
                    help=("which PHYSICAL plane to measure: `sources` (data/sources -> "
                          "data/references, parent key from the profile's measured "
                          "identity_evidence.key) or `served` (data/datasets -> "
                          "data/references_served, parent key from the descriptor's declared "
                          "primary_key/composite_key_part roles). Both are physical; neither reads "
                          "ontology/edges.yaml. Default: sources"))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the statement each candidate WOULD run; reads and writes nothing")
    ap.add_argument("--verify", action="store_true",
                    help="re-derive in memory and compare bytes with the files on disk")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        ap.error("a bundle root is required")       # exit 2: a writer must not default to cwd
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    spec = PLANES[a.plane]
    declared = len(glob.glob(str(root / spec["descriptors"] / "*.yaml")))
    if not declared:
        if a.json:
            print(json.dumps({"state": "no-descriptors", "measured_nothing": True,
                              "plane": a.plane, "relations": 0}, indent=1))
            return D.EMPTY_EXIT
        return D.refuse_empty(NAME, root / spec["descriptors"], unit=spec["unit"])

    try:
        conn, advisories = open_reader(root, extra=EXTRA_CONNECTORS or None)
    except SampleRefused as exc:
        print(f"✗ could not open a reader: {exc}")
        return exc.exit_code
    for adv in advisories:
        print(f"  [advisory] {adv}")

    try:
        rec = measure_bundle(root, conn, dry_run=a.dry_run, plane=a.plane)
    except ReferencesRefused as exc:
        if str(exc) == "__EMPTY__":
            return D.refuse_empty(NAME, root / spec["descriptors"], unit=spec["unit"])
        print(f"✗ {exc}")
        return exc.exit_code

    if a.dry_run:
        for cand in sorted(rec["candidates"],
                           key=lambda c: (c["from"]["relation"], c["from"]["column"],
                                          c["to"]["relation"], c["to"]["column"]))[:3]:
            print(f"  [dry] {_ref_id(cand)}\n"
                  + "\n".join("        " + ln
                              for ln in render_measurement(conn, cand,
                                                           rec["namespaces"]).splitlines()))
        print(f"PASS: {NAME} --dry-run — {len(rec['candidates'])} of {rec['considered']} pair(s) "
              f"would be measured ({len(rec['pruned'])} pruned from the profiles alone); engine "
              f"{conn.id}; nothing was read and nothing was written")
        return 0

    # The dangling corroboration: does ANY relation in the whole catalog carry the missing name?
    # A separate, cheap statement, and it is the difference between "no relation in scope" and
    # "no relation at all" — the second is the claim a reader will make anyway, so it is measured.
    rec["corroboration"] = _corroborate(conn, rec)

    files = compose(rec)
    out_dir = spec["out"]
    out = root / out_dir
    wrote, differs = [], []
    if a.verify:
        for stem, data in sorted(files.items()):
            p = out / f"{stem}.yaml"
            old = p.read_bytes() if p.exists() else b""
            (wrote if old == data else differs).append(f"{out_dir}/{stem}.yaml")
    else:
        out.mkdir(parents=True, exist_ok=True)
        for stem, data in sorted(files.items()):
            (out / f"{stem}.yaml").write_bytes(data)
            wrote.append(f"{out_dir}/{stem}.yaml")
        (out / RUN_RECORD).write_text(
            json.dumps(run_record(rec, files, engine=conn.id), indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")

    lines, drawn, amb = _report(rec, files, engine=conn.id, verify=a.verify,
                               wrote=wrote, differs=differs)
    if a.json:
        print(json.dumps({"relations": len(rec["catalog"]), "written": len(wrote),
                          "differs": differs, "drawn": [_ref_id(r) for r in drawn],
                          "ambiguous": [_ref_id(r) for r in amb],
                          "dangling": sorted(rec["dangling"]),
                          "record": run_record(rec, files, engine=conn.id)},
                         indent=1, ensure_ascii=False, default=str))
    else:
        for ln in lines:
            print(ln)
    codes = [f.get("exit", 1) for f in rec["findings"]] + [1] * len(differs)
    code = 1 if 1 in codes else (2 if 2 in codes else 0)
    head = "PASS" if code == 0 else ("FAIL" if code == 1 else "INCOMPLETE")
    verb = "verified" if a.verify else "wrote"
    n_dang = sum(len(v) for v in rec["dangling"].values())
    print(f"{head}: {NAME} [plane {rec.get('plane', DEFAULT_PLANE)}] — {verb} {len(wrote)} of "
          f"{len(files)} relation file(s) over "
          f"{len(rec['catalog'])} relation(s) in scope; {len(drawn)} reference(s) drawn of "
          f"{len(rec['results'])} candidate(s) measured ({len(amb)} ambiguous, needing a ruling); "
          f"{n_dang} dangling reference(s) reported; engine {conn.id}"
          + (f"; {len(differs)} file(s) DIFFER from disk" if differs else "")
          + (f"; {len(rec['findings'])} finding(s)" if rec["findings"] else ""))
    return code


def _corroborate(conn, rec) -> dict:
    """{column: relations whose NAME resembles the missing parent}. Best effort, never a verdict.

    Measured through the catalog verb the connector already answers, not through a bespoke query:
    the question is "does a relation by that name exist ANYWHERE", and the catalog is where that
    lives. An engine that cannot answer leaves the field None, which the artifact renders as
    "not measured" rather than as zero.
    """
    out = {}
    known = {r.lower() for r in rec["catalog"]}
    for col in rec["dangling"]:
        stub = col
        for suf in rec["convention"]:
            if stub.endswith(suf):
                stub = stub[: -len(suf)]
        stub = stub.lower()
        out[col] = sum(1 for r in known if stub and stub in r) if stub else None
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — one mutant per reject class, plus the negative controls. Synthetic names only.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# The measurement half is replaced by a RowsMeasurer that computes the same ten counts over in-memory
# columns. That is a real measurement, not a canned answer: every verdict, every cardinality and
# every participation value below is derived from actual numbers, so a mutant changes the numbers and
# the rule has to notice. It also lets the whole suite run on an interpreter with no database driver.

_FIXTURE_ID = "fixture.connector.relations"


class RowsMeasurer:
    """The SqlMeasurer's arithmetic, over Python lists. The half a fixture replaces."""

    def __init__(self, conn, namespaces):
        self.cols = conn.fixture_columns
        self.statements = 0

    def __call__(self, cand):
        self.statements += 1
        child = list(self.cols[cand["from"]["relation"]][cand["from"]["column"]])
        parent = list(self.cols[cand["to"]["relation"]][cand["to"]["column"]])
        cnn = [v for v in child if v is not None]
        pnn = [v for v in parent if v is not None]
        pset = set(pnn)
        orphans = [v for v in cnn if v not in pset]
        used = {v for v in cnn if v in pset}
        cc, pc = Counter(cnn), Counter(pnn)
        return {
            "child_rows": len(child), "child_nonnull": len(cnn),
            "child_distinct": len(set(cnn)),
            "orphan_rows": len(orphans), "orphan_distinct": len(set(orphans)),
            "parent_rows": len(parent), "parent_distinct": len(pset),
            "parent_used": len(used),
            "max_child_rows_per_value": max(cc.values()) if cc else None,
            "max_parent_rows_per_value": max(pc.values()) if pc else None,
        }


def _fixture_class(columns, catalog):
    from sdk.connector.base import ColumnSpec, ReadResult, RelationSchema
    from sdk.connector.base import AdapterError, AdapterErrorReason
    from sdk.connector.sql import SqlConnector

    class RelationsConnector(SqlConnector):
        id = _FIXTURE_ID
        supports = frozenset({"describe_relation", "profile_relation"})
        credential_modes = frozenset({"none"})
        permissions = frozenset({"read"})
        probe_cost = "free"
        param_style = ":name"
        fixture_columns = columns

        @classmethod
        def config_schema(cls):
            return {"type": "object"}

        @classmethod
        def validate_config(cls, conn):
            return []

        @classmethod
        def credential_plan(cls, conn):
            from sdk.connector.base import CredentialPlan
            return CredentialPlan(mode="none", ref=None, detail="fixture")

        def orderable(self, engine_type):
            return True

        def describe_relation(self, ref):
            spec = catalog.get(ref.name)
            if spec is None:
                raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                                   f"{self.id}: no such relation {ref.name}")
            return RelationSchema(ref=ref, columns=tuple(ColumnSpec(name=n, type=t)
                                                         for n, t in spec))

        def _execute(self, body, params, *, limit=None, timeout_s=None):
            raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                               f"{self.id}: the self-test measures through RowsMeasurer")

    _ = ReadResult
    return RelationsConnector


_MANIFEST = ("planes:\n  data: data\ndescriptors: data/datasets\nsources: data/sources\n"
             "transforms: data/transforms\nprofiles: data/profiles\n"
             "runtime:\n  connector: %s\n  connection: connection.yaml\n")


def _seed(root: Path, relations, *, connector=_FIXTURE_ID):
    """relations = {stem: {"columns": [(name,type)], "key": [...], "rows": n, "cols": {stats}}}"""
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "profiles").mkdir(parents=True, exist_ok=True)
    (root / "mac.project.yaml").write_text(_MANIFEST % connector, encoding="utf-8")
    (root / "connection.yaml").write_text("spec_version: mac.connector/1\nconfig: {}\n",
                                          encoding="utf-8")
    for stem, spec in relations.items():
        (root / "data" / "sources" / f"{stem}.yaml").write_text(yaml.safe_dump({
            "of": stem,
            "table": {"name": stem, "schema": spec.get("schema", "alpha_schema")},
            "columns": [{"name": n, "type": t, "role": "value"} for n, t in spec["columns"]],
        }), encoding="utf-8")
        prof = {
            "of": stem, "relation": f"{spec.get('schema', 'alpha_schema')}.{stem}",
            "profile": {"rows": spec["rows"]},
            "columns": [{"name": n, **spec["cols"].get(n, {})} for n, _t in spec["columns"]],
        }
        if spec.get("key"):
            prof["identity_evidence"] = {"key": list(spec["key"])}
        (root / "data" / "profiles" / f"{stem}.yaml").write_text(yaml.safe_dump(prof),
                                                                encoding="utf-8")
    return root


def _stats(values):
    nn = [v for v in values if v is not None]
    num = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nn)
    return {"distinct": len(set(nn)), "nulls": len(values) - len(nn),
            "min": (min(nn) if num else None) if nn else None,
            "max": (max(nn) if num else None) if nn else None}


def _bundle(base: Path, name: str, columns, keys, schema="alpha_schema"):
    """columns = {relation: {column: [values]}} -> a seeded bundle + its fixture connector."""
    rels = {}
    for rel, cols in columns.items():
        rels[rel] = {
            "columns": [(c, "bigint" if all(isinstance(v, int) and not isinstance(v, bool)
                                            for v in vals if v is not None) else "varchar")
                        for c, vals in cols.items()],
            "key": keys.get(rel, []),
            "rows": max(len(v) for v in cols.values()),
            "cols": {c: _stats(v) for c, v in cols.items()},
            "schema": schema,
        }
    root = _seed(base, rels)
    catalog = {rel: rels[rel]["columns"] for rel in rels}
    return root, _fixture_class(columns, catalog)


def _run(root, *args, cls=None):
    global EXTRA_CONNECTORS
    if cls is not None:
        EXTRA_CONNECTORS = {_FIXTURE_ID: cls}
    buf = io.StringIO()
    argv = [str(root)] + list(args)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = main(argv)
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 2
    return rc, buf.getvalue()


def _measure_into(root, cls):
    """measure_bundle + compose with the fixture measurer. Returns (record, {stem: bytes})."""
    conn = cls({})
    rec = measure_bundle(Path(root), conn, RowsMeasurer)
    rec["corroboration"] = _corroborate(conn, rec)
    return rec, compose(rec)


def _self_test() -> int:                                                        # noqa: C901
    import tempfile

    bad, cases = [], []

    def case(label, ok, why):
        cases.append((label, ok, why))
        if not ok:
            bad.append(f"{label}: {why}")

    # ── the PURE rules, mutated one at a time ────────────────────────────────────────────────────
    case("typeclass buckets an engine type", typeclass("BIGINT") == "INTEGRAL"
         and typeclass("varchar(5)") == "TEXT" and typeclass("geometry") == "OTHER",
         "a type outside the compared classes must be OTHER and never propose")
    case("ratio refuses a zero denominator", ratio(0, 0) is None,
         "0/0 must be None; 0.0 would read as a measured zero")
    case("span_ratio is None for TEXT",
         span_ratio({"min": "a", "max": "z"}, {"min": "a", "max": "z"}, "TEXT") is None,
         "string bounds have no meaningful distance")
    case("span_ratio measures overlap on an ordered type",
         span_ratio({"min": 1, "max": 5}, {"min": 1, "max": 10}, "INTEGRAL") == 0.444444,
         "the fraction of the parent span the child covers")

    ev = {"inclusion": 1.0, "parent_coverage": 0.9, "child_nonnull": 10, "orphan_rows": 0,
          "orphan_distinct": 0}
    case("NEGATIVE CONTROL a held, exercised inclusion is real",
         verdict(ev, 1.0)[0] == "real", str(verdict(ev, 1.0)))
    case("MUTANT inclusion 1.0 with no domain exercise is coincidental",
         verdict({**ev, "parent_coverage": 0.2}, 0.2)[0] == "coincidental",
         "a dense column inside a wider dense key is arithmetic, not a reference")
    case("MUTANT one orphan row is a near_miss, not a reference",
         verdict({**ev, "inclusion": 0.996, "orphan_rows": 1, "orphan_distinct": 1},
                 1.0)[0] == "near_miss", "0.996 sits above the floor and below 1.0")
    case("MUTANT inclusion below the near-miss floor is rejected",
         verdict({**ev, "inclusion": 0.5, "orphan_rows": 5, "orphan_distinct": 2},
                 1.0)[0] == "rejected", "half the rows orphaned is not a reference")
    case("MUTANT no non-null child rows has no denominator",
         verdict({**ev, "inclusion": None}, 1.0)[0] == "no_denominator",
         "an empty denominator is an outage, never a clean result")
    case("the admitted sentence restates its own arithmetic",
         "inclusion_required" in verdict(ev, 1.0)[1] and "PARTICIPATION" in verdict(ev, 1.0)[1],
         "an entry must not be readable without the numbers that judged it")

    conv, keys = key_name_convention({"a": {"key": ["AlphaRef"]}, "b": {"key": ["BetaRef"]}})
    case("key convention is self-calibrated from the bundle's own keys",
         conv == ["Ref"] and keys == ["AlphaRef", "BetaRef"], f"got {conv}")
    conv2, _ = key_name_convention({"a": {"key": ["x"]}, "b": {"key": ["y"]}})
    case("MUTANT a bundle with no convention gets NO dangling detection",
         conv2 == [], "an empty suffix list must mean 'not detectable here', never 'none exist'")

    r = {"from": {"relation": "alpha", "column": "GammaRef"},
         "to": {"relation": "gamma", "column": "GammaRef"}}
    case("a reference id is keyed by RELATION AND COLUMN on both ends",
         _ref_id(r) == "alpha.GammaRef__gamma.GammaRef", _ref_id(r))
    r2 = {"from": {"relation": "alpha", "column": "OtherRef"}, "to": r["to"]}
    case("MUTANT two references joining one pair get DIFFERENT ids",
         _ref_id(r) != _ref_id(r2), "keying on the relation pair alone collides")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # ── THE WORKED BUNDLE. alpha (child) -> gamma (parent) on a MISMATCHED name, plus a
        #    dangling reference, plus a coincidental inclusion, plus an unreferenced parent row.
        cols = {
            "gamma": {"GammaRef": [1, 2, 3, 4], "Label": ["p", "q", "r", "s"]},
            "delta": {"DeltaCode": list(range(100, 140)),
                      "Tag": [f"t{i}" for i in range(40)]},
            "alpha": {"AlphaRef": [10, 11, 12, 13, 14],
                      "Pointer": [1, 1, 2, 3, 3],          # -> gamma.GammaRef, NAME DOES NOT MATCH
                      "DeltaRef": [7, 7, 8, 9, 9],         # dangling: nothing keys on this domain
                      "Size": [100, 101, 102, 100, 101]},  # inside delta's wide key BY ARITHMETIC
        }
        root, cls = _bundle(base / "worked", "worked", cols,
                            {"gamma": ["GammaRef"], "alpha": ["AlphaRef"],
                             "delta": ["DeltaCode"]})
        rec, files = _measure_into(root, cls)
        drawn = {_ref_id(r) for r in rec["results"] if r.get("direction") == "drawn"}
        case("NEGATIVE CONTROL the name-MISMATCHED reference is found",
             "alpha.Pointer__gamma.GammaRef" in drawn, f"drawn = {sorted(drawn)}")
        hit = next(r for r in rec["results"] if _ref_id(r) == "alpha.Pointer__gamma.GammaRef")
        case("MUTANT the name was never an input", hit["name_match"] is False,
             "name_match is a label; a True here would mean the name did the work")
        case("participation is measured on BOTH sides and is not cardinality",
             hit["cardinality"] == {"child": "many", "parent": "one"}
             and hit["participation"]["parent"] == "optional"
             and hit["participation"]["parent_unreferenced"] == 1
             and hit["participation"]["child"] == "mandatory",
             f"got {hit['cardinality']} / {hit['participation']}")
        case("MUTANT the coincidental inclusion is demoted, not admitted",
             any(r["verdict"] == "coincidental" and r["from"]["column"] == "Size"
                 for r in rec["results"]),
             "Size includes into GammaRef at 1.0 and exercises nothing")
        case("MUTANT the dangling column is reported, with no invented parent",
             "DeltaRef" in rec["dangling"]
             and all(_ref_id(r) != "alpha.DeltaRef__gamma.GammaRef" for r in rec["results"]
                     if r.get("direction") == "drawn"),
             f"dangling = {sorted(rec['dangling'])}")
        doc = yaml.safe_load(files["alpha"].decode("utf-8"))
        case("the dangling entry carries to: null and its BASIS",
             doc["references_dangling"][0]["to"] is None
             and doc["references_dangling"][0]["basis"] == "key_naming_convention"
             and "WEAKER evidence" in doc["references_dangling"][0]["basis_detail"],
             str(doc["references_dangling"])[:200])
        case("every rejection carries its NUMBERS",
             all(x["evidence"]["inclusion"] is not None and x["rejected_because"]
                 for x in doc["candidates_rejected"]),
             "an operator who cannot see what was considered cannot tell missing from unconsidered")
        case("the admission floors travel in EVERY file",
             all(yaml.safe_load(b.decode())["admission"] == ADMISSION for b in files.values()),
             "an entry must not be readable without the numbers that judged it")
        text = files["alpha"].decode("utf-8")
        case("VOCABULARY the artifact never says concept or edge",
             "concept" not in text and "edge" not in text.replace("acknowledge", ""),
             "a physical reference is keyed by relation and column, never through a business object")
        case("VOCABULARY every reference names a relation and a column on both ends",
             all(set(e["from"]) == {"relation", "column"} and set(e["to"]) == {"relation", "column"}
                 for e in doc["references"]),
             "never a join_rule string to be re-parsed")

        # ── DETERMINISM: two independent runs, byte-identical ────────────────────────────────────
        root2, cls2 = _bundle(base / "worked2", "worked", cols,
                              {"gamma": ["GammaRef"], "alpha": ["AlphaRef"],
                               "delta": ["DeltaCode"]})
        _rec2, files2 = _measure_into(root2, cls2)
        case("NEGATIVE CONTROL two runs over unchanged data are BYTE-IDENTICAL",
             files == files2, "a family that churns stops being re-derived")
        case("NEGATIVE CONTROL no clock is written into a relation file",
             "measured_at" not in files["alpha"].decode("utf-8"),
             "the clock lives in the run record, which is the one file that moves")

        # ── AMBIGUITY: two parent key columns with the identical domain ──────────────────────────
        amb_cols = {
            "gamma": {"Left": ["a", "b"], "Right": ["a", "b"], "Seq": [1, 2]},
            "alpha": {"AlphaRef": [1, 2, 3, 4], "Token": ["a", "a", "b", "b"]},
        }
        root3, cls3 = _bundle(base / "amb", "amb", amb_cols,
                              {"gamma": ["Left", "Right", "Seq"], "alpha": ["AlphaRef"]})
        rec3, _f3 = _measure_into(root3, cls3)
        ambs = [r for r in rec3["results"] if r.get("ambiguous_with")]
        case("MUTANT two parents that measure identically are BOTH recorded",
             len(ambs) == 2 and all(r.get("needs_ruling") for r in ambs),
             f"got {[(_ref_id(r), r.get('ambiguous_with')) for r in ambs]}")
        case("MUTANT neither ambiguous parent is silently chosen",
             all(r["direction"] == "drawn" for r in ambs),
             "dropping one would be a fabrication dressed as a measurement")

        # ── DIRECTION: a mutual inclusion points at the identity ─────────────────────────────────
        mut_cols = {
            "gamma": {"GammaRef": [1, 2, 3], "Note": ["x", "y", "z"]},
            "alpha": {"AlphaRef": [1, 2, 3], "Seq": [1, 2, 3]},
        }
        root4, cls4 = _bundle(base / "mutual", "mutual", mut_cols,
                              {"gamma": ["GammaRef"], "alpha": ["AlphaRef", "Seq"]})
        rec4, _f4 = _measure_into(root4, cls4)
        dirs = {_ref_id(r): r.get("direction") for r in rec4["results"] if r["verdict"] == "real"}
        case("MUTANT a mutual inclusion is drawn ONCE, pointing at the identity",
             dirs.get("alpha.AlphaRef__gamma.GammaRef") == "drawn"
             and dirs.get("gamma.GammaRef__alpha.AlphaRef") == "superseded_by_reverse",
             f"got {dirs}")

        # ── THE PRUNES, one mutant each ──────────────────────────────────────────────────────────
        pr_cols = {
            "gamma": {"GammaRef": [1, 2, 3, 4], "Word": ["a", "b", "c", "d"]},
            "alpha": {"AlphaRef": [1, 2, 3, 4, 5, 6],       # more distinct than the parent key
                      "Flat": [1, 1, 1, 1, 1, 1],           # one value: includes into anything
                      "Text": ["a", "b", "c", "d", "e", "f"]},
        }
        root5, cls5 = _bundle(base / "prunes", "prunes", pr_cols,
                              {"gamma": ["GammaRef"], "alpha": ["AlphaRef"]})
        conn5 = cls5({})
        rec5 = measure_bundle(Path(root5), conn5, RowsMeasurer)
        why = {(p["from"]["column"], p["to"]["column"]): p["pruned_because"] for p in rec5["pruned"]}
        case("MUTANT type-class mismatch is pruned and says so",
             "type class" in why.get(("Text", "GammaRef"), ""), str(why.get(("Text", "GammaRef"))))
        case("MUTANT a one-value child column is pruned and says so",
             "min_child_distinct" in why.get(("Flat", "GammaRef"), ""),
             str(why.get(("Flat", "GammaRef"))))
        case("MUTANT more distinct values than the key has is pruned and says so",
             "tolerance" in why.get(("AlphaRef", "GammaRef"), ""),
             str(why.get(("AlphaRef", "GammaRef"))))

        # ── the bundle-level reject classes, driven through main() ───────────────────────────────
        rc, out = _run(base / "worked", cls=cls)
        # (the fixture cannot execute SQL, so main() is exercised for its refusal paths only)
        bare = base / "bare"
        (bare / "data").mkdir(parents=True)
        rc, out = _run(bare)
        case("MUTANT empty population refuses (exit 2), verbatim marker",
             rc == D.EMPTY_EXIT and D.empty_mark("source descriptor") in out,
             f"exit {rc}: {out.strip()[-200:]}")
        nokey = base / "nokey"
        _bundle(nokey, "nokey", {"gamma": {"GammaRef": [1, 2]}, "alpha": {"Pointer": [1, 2]}},
                {"gamma": ["GammaRef"]})
        conn6 = _fixture_class({"gamma": {"GammaRef": [1, 2]}, "alpha": {"Pointer": [1, 2]}},
                               {"gamma": [("GammaRef", "bigint")],
                                "alpha": [("Pointer", "bigint")]})({})
        rec6 = measure_bundle(nokey, conn6, RowsMeasurer)
        case("MUTANT a relation with no measured key is a FINDING, not a re-derived key",
             any("no measured key" in f["detail"] for f in rec6["findings"]),
             f"findings = {rec6['findings']}")
        gone = base / "gone"
        _bundle(gone, "gone", {"gamma": {"GammaRef": [1, 2]}, "omega": {"Pointer": [1, 2]}},
                {"gamma": ["GammaRef"], "omega": ["Pointer"]})
        conn7 = _fixture_class({"gamma": {"GammaRef": [1, 2]}},
                               {"gamma": [("GammaRef", "bigint")]})({})     # omega NOT in catalog
        rec7 = measure_bundle(gone, conn7, RowsMeasurer)
        _f7 = compose({**rec7, "corroboration": {}})
        case("MUTANT a relation the catalog does not have gets NO FILE and a named finding",
             "omega" not in _f7 and any("catalog does not have" in f["detail"]
                                        for f in rec7["findings"]),
             f"files = {sorted(_f7)}, findings = {rec7['findings']}")

        # ── THE SERVED PLANE reads its key from the DESCRIPTOR'S DECLARED ROLES, and the two planes
        #    do not see each other. Three separate claims, because each is a way to be wrong:
        #      · the served population comes from data/datasets, not data/sources;
        #      · the parent key comes from role primary_key/composite_key_part, NOT from the
        #        profile's identity_evidence — the mutant below gives the profile a DIFFERENT key,
        #        so a tool still reading the profile would report that one and fail here;
        #      · `foreign_key` is NOT admitted as a parent key: a declared FK is a claim about a
        #        target, and this tool measures those rather than believing them.
        planes = base / "planes"
        (planes / "data" / "datasets").mkdir(parents=True)
        (planes / "data" / "profiles").mkdir(parents=True, exist_ok=True)
        (planes / "data" / "sources").mkdir(parents=True, exist_ok=True)
        (planes / "data" / "datasets" / "v_served.yaml").write_text(yaml.safe_dump({
            "of": "v_served",
            "table": {"name": "v_served", "schema": "own_schema"},
            "columns": [{"name": "ServedKey", "role": "primary_key"},
                        {"name": "OtherRef", "role": "foreign_key"},
                        {"name": "Payload", "role": "value"}],
        }), encoding="utf-8")
        (planes / "data" / "profiles" / "v_served.yaml").write_text(yaml.safe_dump({
            "of": "v_served", "relation": "own_schema.v_served",
            "profile": {"rows": 3},
            "columns": [{"name": "ServedKey", "distinct": 3, "nulls": 0},
                        {"name": "OtherRef", "distinct": 3, "nulls": 0},
                        {"name": "Payload", "distinct": 1, "nulls": 0}],
            "identity_evidence": {"key": ["Payload"]},     # the WRONG key, on purpose
        }), encoding="utf-8")
        srv_rels, srv_profs, srv_find = read_plane(planes, "served")
        src_rels, _, _ = read_plane(planes, "sources")
        case("MUTANT the served plane takes its key from the DESCRIPTOR, not the profile",
             (sorted(srv_rels) == ["v_served"] and srv_profs["v_served"]["key"] == ["ServedKey"]
              and src_rels == {} and not srv_find),
             f"served relations={sorted(srv_rels)} key={srv_profs.get('v_served', {}).get('key')} "
             f"(profile declares ['Payload']) · sources relations={sorted(src_rels)}")
        case("NEGATIVE CONTROL the two planes write to different artifact directories",
             (PLANES["sources"]["out"] != PLANES["served"]["out"]
              and PLANES["sources"]["descriptors"] != PLANES["served"]["descriptors"]
              and "foreign_key" not in DECLARED_KEY_ROLES),
             f"{PLANES} · DECLARED_KEY_ROLES={DECLARED_KEY_ROLES}")
        case("NEGATIVE CONTROL every plane's artifact names the plane it measured",
             all(b"plane: " in render_relation_file(
                     "gamma", rec7["catalog"], rec7["profiles"], [], [], [],
                     {"relations_in_scope": 1, "parent_endpoints": 1}, pl)
                 for pl in PLANES),
             "an artifact that does not name its plane is unreadable beside the other plane's")

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mutants = len([c for c in cases if c[0].startswith("MUTANT")])
    controls = len([c for c in cases if "NEGATIVE CONTROL" in c[0]])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mutants} mutant(s), one per reject "
          f"class (no domain exercise, one orphan row, inclusion below the floor, no denominator, "
          f"no key-name convention, colliding reference ids, the name doing the work, an invented "
          f"parent for a dangling column, a silently-chosen parent among equals, a mutual inclusion "
          f"drawn twice, type-class mismatch, a one-value child column, more distinct values than "
          f"the key has, an empty population, a re-derived key, a relation the catalog does not "
          f"have, a served plane reading the profile's key instead of the descriptor's) and "
          f"{controls} negative control(s) (a name-mismatched reference found, byte-identity across "
          f"two runs, no clock in a relation file, two planes with two artifact directories, every "
          f"artifact naming its own plane)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
