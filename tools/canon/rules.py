#!/usr/bin/env python3
"""mac.canon.<rule> — rules defined ONCE, attached to concepts by reference.

WHY THIS EXISTS
---------------
Measured on a live bundle: 46 of 83 concept rules are six shapes, hand-copied per concept. The largest,
`exclusion.no_evidence`, appears in THIRTEEN concepts — as thirteen distinct `then` clauses, twelve
distinct `never` clauses and eleven distinct `when` clauses. Every copy is individually well-formed, so
no syntax gate sees anything wrong, and nothing can tell whether they still mean the same thing.

They already do not. `DtC` forbids "substituting another measure's figure"; `GrossStock` does not.
`Market` carries no refusal message at all, so it cannot produce the answer the other twelve promise.
Copies drift in whichever clause each author happened to touch.

A checker over the copies is the wrong instrument — it fires on rewording as loudly as on redefinition.
The fix is to stop having copies: define the rule once here, attach it with
`realized_by: {udf: mac.canon.<name>, params: {...}}`, and RENDER the prose. One wording, N
attachments, nothing to drift, and a missing parameter is a loud failure rather than a quiet omission.

The schema has supported this since v0.1.9 — `canonRef` is defined, `rules[].realized_by` is an allowed
key, and `values.realized_by` already delegates closed value sets to a register. Nothing had ever used
it for rules; `tools/canon/` held only `__init__.py`.

TWO CANONS, NOT ONE. The corpus files both of these under the single id `exclusion.no_evidence`, which
is why no single template fitted: refusing because a MEASURE has no row for a resolved scope, and
refusing because a NAME does not resolve to a code, are different rules with different triggers. The id
hid the difference; the canon makes it explicit.

NOTHING HERE NAMES A BUNDLE. `source`, `label`, `slot` and the rest are parameters. A canon that
hardcoded an fpl2 column would be a framework rule about one customer's data.
"""
from __future__ import annotations


def _join(items) -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "; ".join(items)


def refuse_measure_no_row(*, source: str, label: str, slot: str = "scope",
                          confusable=None, null_is_real: str = "", ban_in_then: bool = True,
                          substitute_kind: str = "measure") -> dict:
    """A MEASURE has no row for the resolved scope — refuse at the evidence boundary.

    params
      source        the bundle's own name, as it appears to a reader ("FPL2")
      label         the measure as a human says it ("Deliveries to Customer")
      slot          what was resolved and found empty — "scope", "country", ...
      confusable    measures a tired reader might substitute instead. Named explicitly because the
                    substitution is the actual failure: an empty Gross Stock answered with Ideal Stock
                    is worse than no answer, and only the concept's author knows which measure is the
                    tempting one.
      null_is_real  set when a RESOLVED row can carry a null value that MEANS something. Then null is
                    an answer, not an absence, and coercing it to 0 invents a fact.
      ban_in_then   MEASURED 2026-08-18 across the 13 authored copies: five state the substitution ban
                    in BOTH `then` and `never`, and `ideal_stock` states it ONLY in `never`. Rendering
                    it in both regardless ADDS a clause its author did not write — a canon that
                    silently adds content is the mirror of one that silently drops it.
      substitute_kind  what a tired reader would substitute FROM. `total_market` bans substituting
                    "another SOURCE's figure" (it is the only cross-source measure here), every other
                    copy bans "another MEASURE's". One word, and the wrong one names the wrong risk.
    """
    never = ["returning an empty result framed as a real zero"]
    if confusable:
        never.insert(0, f"silently substituting {_join(confusable)} or another {substitute_kind}'s value")
    else:
        never.append(f"substituting another {substitute_kind}'s value")
    # The authored corpus states the substitution ban in BOTH `then` and `never` on five of the nine
    # measures. Rendering it once would quietly weaken those five, so the canon carries it in both —
    # a canon that silently drops authored content is worse than the copies it replaces.
    ban = (f", or substitute another {substitute_kind}'s figure"
           if (confusable is not None and ban_in_then) else "")
    then = (f"REFUSE with an evidence-boundary answer "
            f"('{source} has no {label} information for <{slot}>') — never guess, estimate{ban}")
    if null_is_real:
        then += (f". A resolved row whose value is null is an ANSWER, not an absence: report it as "
                 f"null ('{null_is_real}'), never coerce it to 0 or an estimate")
        never.append("coercing a null value on a resolved row to 0")
    return {
        "subject": f"Refuse {label} with no row — don't guess or zero-fill",
        "when": f"the resolved {slot} has no {label} row for the requested variant/period",
        "then": then,
        "never": _join(never),
    }


def derive_name_params(concept: dict, source: str) -> dict:
    """`refuse_unresolvable_name`'s parameters, READ from the concept rather than attached to a rule.

    thing = concept.label (what a person calls it), code = concept.identity.canonical_key (what a
    name must resolve to). Both are already declared on every conformant concept; attaching them to
    a rule creates a second home that can — and did — disagree with the first.
    """
    c = concept or {}
    ident = (c.get("identity") or {})
    return {"source": source,
            "thing": str(c.get("label") or c.get("name") or "").lower(),
            "code": str(ident.get("canonical_key") or "")}


def refuse_unresolvable_name(*, source: str, thing: str, code: str, via: str = "") -> dict:
    """A NAME does not resolve to a code — refuse rather than fuzzy-match.

    params
      source  the bundle's own name ("FPL2")
      thing   what was named and could not be resolved ("model", "market", "brand")
      code    the identity it should have resolved to ("fpl_model_code")
      via     the register the resolution goes THROUGH, when the concept names one. `country` and
              `market` both say "via the register" and the canon had no way to carry it, so binding
              them would have dropped the clause that says WHERE the lookup happens.

    A near-miss substitution is the failure this prevents: answering about the Golf when the question
    said Golf Plus is worse than refusing, because the answer looks right.
    """
    return {
        "subject": f"Refuse an unresolvable {thing} — don't guess or fuzzy-substitute",
        "when": (f"a named {thing} does not resolve to any {code}"
                 + (f" via {via}" if via else "")),
        "then": (f"REFUSE with an evidence-boundary answer "
                 f"('{source} has no information about <{thing}>') — never guess or fuzzy-substitute "
                 f"a similarly-named {thing}"),
        "never": f"silently substituting a near-miss {thing}; inventing a {code}",
    }


CANONS = {
    "mac.canon.refuse_measure_no_row": refuse_measure_no_row,
    "mac.canon.refuse_unresolvable_name": refuse_unresolvable_name,
}


def _params_from_registry(udf: str) -> dict:
    """{param: dotted concept path} declared in mac_vocabulary.yaml#canon.members[].params_from."""
    try:
        import yaml
        from pathlib import Path as _P
        f = _P(__file__).resolve().parent.parent.parent / "mac_vocabulary.yaml"
        m = ((yaml.safe_load(f.read_text(encoding="utf-8")) or {})
             .get("canon", {}).get("members", {}) or {}).get(udf.split(".")[-1]) or {}
        return m.get("params_from") or {}
    except Exception:                                                    # noqa: BLE001
        return {}


def _dig(doc, dotted: str):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def render(udf: str, params: dict, concept: dict | None = None) -> dict:
    """Render a rule's authored clauses from its canon binding.

    DERIVED PARAMETERS ARE READ, NOT ATTACHED. The registry declares which of a canon's parameters
    live on the concept (`params_from`); those are filled from `concept` here, and an ATTACHED value
    never overrides a declared one — that is what makes attaching them pointless rather than merely
    redundant. Measured 2026-08-19: `label` was attached on 5 fpl2 bindings and disagreed with
    concept.label on THREE of them ("DtC" vs "Deliveries to Customer", "IstProd" vs "Actual
    Production", "Prodant" vs "Production Request"), so the refusal message named the measure
    something its own concept does not call it.

    Unknown canon, or a parameter left unfilled, raises — a rule that cannot render is a build error,
    never a silently empty rule.
    """
    fn = CANONS.get(udf)
    if fn is None:
        raise KeyError(f"unknown canon {udf!r}; known: {sorted(CANONS)}")
    merged = dict(params or {})
    if concept is not None:
        for prm, path in _params_from_registry(udf).items():
            val = _dig(concept, path)
            if val:
                merged[prm] = val
    return fn(**merged)
