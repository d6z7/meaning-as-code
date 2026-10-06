#!/usr/bin/env python3
"""mac.canon.<rule> — rules defined ONCE, attached to concepts by reference.

WHY THIS EXISTS
---------------
Measured on a live bundle: 46 of 83 concept rules are six shapes, hand-copied per concept. The largest,
`exclusion.no_evidence`, appears in THIRTEEN concepts — as thirteen distinct `then` clauses, twelve
distinct `never` clauses and eleven distinct `when` clauses. Every copy is individually well-formed, so
no syntax gate sees anything wrong, and nothing can tell whether they still mean the same thing.

They already do not. `Shipments` forbids "substituting another measure's figure"; `OnHandInventory` does
not. `Market` carries no refusal message at all, so it cannot produce the answer the other twelve
promise. Copies drift in whichever clause each author happened to touch.

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
hardcoded an <dataset> column would be a framework rule about one customer's data.
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
      source        the bundle's own name, as it appears to a reader ("<DATASET>")
      label         the measure as a human says it ("Units Shipped")
      slot          what was resolved and found empty — "scope", "country", ...
      confusable    measures a tired reader might substitute instead. Named explicitly because the
                    substitution is the actual failure: an empty On-hand Inventory answered with Target Inventory
                    is worse than no answer, and only the concept's author knows which measure is the
                    tempting one.
      null_is_real  set when a RESOLVED row can carry a null value that MEANS something. Then null is
                    an answer, not an absence, and coercing it to 0 invents a fact.
      ban_in_then   MEASURED 2026-08-18 across the 13 authored copies: five state the substitution ban
                    in BOTH `then` and `never`, and `target_inventory` states it ONLY in `never`. Rendering
                    it in both regardless ADDS a clause its author did not write — a canon that
                    silently adds content is the mirror of one that silently drops it.
      substitute_kind  what a tired reader would substitute FROM. `market_size` bans substituting
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

    thing = concept.label (what a person calls it), code = the column carrying `identity: canonical`
    (what a name must resolve to). Both are already declared on every conformant concept; attaching
    them to a rule creates a second home that can — and did — disagree with the first.

    `code` MOVED 2026-10-05: it was `concept.identity.canonical_key` and that block is gone, so this
    reads the column through the one helper that owns the lookup. Takes the whole DOC, not the
    `concept:` block — the columns live under `grounding`.
    """
    doc = concept or {}
    c = doc.get("concept") or doc
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    import mac_project as P
    return {"source": source,
            "thing": str(c.get("label") or c.get("name") or "").lower(),
            "code": str(P.canonical_key(doc) or "")}


def refuse_unresolvable_name(*, source: str, thing: str, code: str, via: str = "") -> dict:
    """A NAME does not resolve to a code — refuse rather than fuzzy-match.

    params
      source  the bundle's own name ("<DATASET>")
      thing   what was named and could not be resolved ("model", "market", "brand")
      code    the identity it should have resolved to ("<source>_model_code")
      via     the register the resolution goes THROUGH, when the concept names one. `country` and
              `market` both say "via the register" and the canon had no way to carry it, so binding
              them would have dropped the clause that says WHERE the lookup happens.

    A near-miss substitution is the failure this prevents: answering about the Alpha when the question
    said Alpha Plus is worse than refusing, because the answer looks right.
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


def resolve_by_register(*, thing: str, code: str, register: str, search: str,
                        display_label: str = "", scope: str = "", fact_join: str = "",
                        served_view: str = "") -> dict:
    """Resolve a NAME to a CODE through a declared register — never through the display label.

    params
      thing          what a question names ("country", "market", "model")
      code           the identity it resolves to ("market_code", "<source>_model_code")
      register       WHERE the resolution happens — an offline register, so an unresolvable name can
                     be refused BEFORE a query rather than returning zero rows that read as "no data"
      search         the column(s) a name is matched against ("name_en / name_de / iso2")
      display_label  the column that must NEVER be used as a key. Optional only because a concept may
                     not expose one; when it does, this is the clause that carries the actual trap.
      scope          a filter the resolution is only valid under ("market_class = single_country")
      fact_join      the column the FACT joins on, when it differs from `code`
      served_view    the in-warehouse alternative, for when a round trip is acceptable

    WHY THIS EXISTS. MEASURED on <domain>/<dataset>, 2026-08-19: four rules said this with different nouns —
    country and market resolve `name_en/name_de/iso2 -> market_code` through the SAME register and
    forbid the SAME column (`market_label_raw`), differing only in which concept they sit on;
    product does it through `name_key -> <source>_product_code`. One law, four spellings, and the
    kind of repetition MODELLERS_COOKBOOK C6 calls "a law nobody has stated".

    THE DISPLAY LABEL IS THE POINT. Each of those rules exists because the register carries a
    human-readable column that LOOKS like an identity and is not — `market_label_raw` holds HOME for
    the home country, and a product's display name holds 'Aurora Large' where the search key is AURORA. Matching
    on it silently answers about the wrong thing.
    """
    where = f"in {register}" + (f" (where {scope})" if scope else "")
    then = (f"resolve the named {thing} to `{{{code}}}` OFFLINE, {where}, on {search}")
    if fact_join and fact_join != code:
        then += f"; the fact joins on `{{{fact_join}}}`"
    if served_view:
        then += f". `{{{served_view}}}` carries the same rows if a warehouse round trip is acceptable"
    never = (f"using {display_label} as the key — it is a display label, not an identity"
             if display_label else
             f"matching a raw display name as the identity; `{{{code}}}` is the stable one")
    return {
        "subject": f"Resolve a {thing} by its code, via the register — never by the display label",
        "when": f"resolving or filtering the {thing} a question names",
        "then": then,
        "never": never,
    }


CANONS = {
    "mac.canon.refuse_measure_no_row": refuse_measure_no_row,
    "mac.canon.refuse_unresolvable_name": refuse_unresolvable_name,
    "mac.canon.resolve_by_register": resolve_by_register,
}


def render(udf: str, params: dict, concept: dict | None = None, root=None) -> dict:
    """Render a rule's authored clauses from its canon binding.

    DERIVED PARAMETERS ARE READ, NOT ATTACHED. The registry declares which of a canon's parameters
    live on the concept (`params_from`); those are filled from `concept` here, and an ATTACHED value
    never overrides a declared one — that is what makes attaching them pointless rather than merely
    redundant. Measured 2026-08-19: `label` was attached on 5 <dataset> bindings and disagreed with
    concept.label on THREE of them ("NetShip" vs "Units Shipped", "ActProd" vs "Units
    Produced", "ProdReq" vs "Units Requested"), so the refusal message named the measure
    something its own concept does not call it.

    Unknown canon, or a parameter left unfilled, raises — a rule that cannot render is a build error,
    never a silently empty rule.
    """
    fn = CANONS.get(udf)
    if fn is None:
        raise KeyError(f"unknown canon {udf!r}; known: {sorted(CANONS)}")
    from . import resolve_params
    return fn(**resolve_params(udf, params, concept, root))


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# THE SELECTION FAMILY, and the two guards contoso5 binds. Added 2026-10-06.
#
# WHY THESE SIX, AND WHY NOW. The operator's sequence ends "rule trigger creation of projection what
# the rule does in the knowledge about the concept" — the human text about a rule is DERIVED from the
# formal rule, not authored beside it. That projection is this module, and it covered 3 of 23 canons,
# NONE of them the six a worked bundle actually binds. So `check_canon_binding` could hold 0 of 12
# bindings against their canon, and `sdk/project/mac_okf.py` had to render a rule page from the
# authored `when`/`then`/`never` instead — which is why deleting that prose blanked 19 pages.
#
# EACH RENDERER STATES WHAT ITS CANON DECIDES AND WHAT IT REFUSES TO DO, from the params alone. None
# names a concept, a column or a bundle: the words come from the declaration it is handed.
# ─────────────────────────────────────────────────────────────────────────────────────────────────


def _surfaces_of(body) -> list:
    return list((body or {}).get("surfaces") or ())


def _named_readings(bodies: dict, what: str) -> str:
    """`a (also called x, y), b` — the readings and the words that select each."""
    parts = []
    for name in sorted(bodies):
        words = _surfaces_of(bodies[name])
        parts.append(f"`{name}`" + (f" (also called {_join(words)})" if words else ""))
    return f"{len(bodies)} named {what}: " + _join(parts)


def _default_clause(default, kind: str) -> tuple[str, str]:
    """(then-tail, never-tail) for a declaration that does or does not name a default."""
    if default:
        return (f"a question naming none of them takes `{default}`, and the answer DISCLOSES that it "
                f"did", "")
    return ("a question naming none of them is ASKED BACK, with every reading offered",
            f"choosing between {kind} the question did not name")


def population_select(*, populations: dict, default: str = "") -> dict:
    """WHICH ROWS the concept has — named readings of one axis, as bound predicates."""
    subsets = {n: b.get("of") for n, b in populations.items() if (b or {}).get("of")}
    complements = {n: b.get("not") for n, b in populations.items() if (b or {}).get("not")}
    then_tail, never_tail = _default_clause(default, "populations")
    then = [_named_readings(populations, "population(s) of one axis"), then_tail]
    if complements:
        then.append("; ".join(f"`{n}` is everything `{o}` is not" for n, o in sorted(complements.items())))
    if subsets:
        then.append("; ".join(f"`{n}` is a subset of `{o}`" for n, o in sorted(subsets.items())))
    never = ["mixing two readings of one axis in a single figure",
             "reporting a count over all rows as a count of the default reading"]
    if never_tail:
        never.insert(0, never_tail)
    return {
        "subject": "which rows this concept has, and which reading a bare question means",
        "when": "a question counts, lists or filters this concept's rows",
        "then": ". ".join(p for p in then if p),
        "never": _join(never),
    }


def ratio_select(*, ratios: dict, default: str = "") -> dict:
    """WHICH FIGURE a named ratio divides by."""
    then_tail, never_tail = _default_clause(default, "denominators")
    bodies = {n: {"surfaces": _surfaces_of(b)} for n, b in ratios.items()}
    denoms = "; ".join(f"`{n}` divides by {(ratios[n] or {}).get('denominator')}"
                       for n in sorted(ratios))
    never = ["dividing by a figure this bundle has not declared"]
    if never_tail:
        never.insert(0, never_tail)
    return {
        "subject": "which figure a rate over this measure divides by",
        "when": "a rate, share or percentage over this measure is asked for",
        "then": f"{_named_readings(bodies, 'ratio(s)')}. {denoms}. {then_tail}",
        "never": _join(never),
    }


def column_select(*, columns: dict, default: str = "") -> dict:
    """WHICH COLUMN a named reading resolves to, among columns this concept declares."""
    then_tail, never_tail = _default_clause(default, "columns")
    bodies = {n: {"surfaces": _surfaces_of(b)} for n, b in columns.items()}
    cols = "; ".join(f"`{n}` is `{(columns[n] or {}).get('column')}`" for n in sorted(columns))
    never = ["answering on one column while reporting the other's name"]
    if never_tail:
        never.insert(0, never_tail)
    return {
        "subject": "which of this concept's columns a named reading answers on",
        "when": "a question names this concept and does not say which reading it means",
        "then": f"{_named_readings(bodies, 'reading(s)')}. {cols}. {then_tail}",
        "never": _join(never),
    }


def path_select(*, paths: dict, default: str = "") -> dict:
    """WHICH RELATION the answer is reached through — the last hop into this concept."""
    then_tail, never_tail = _default_clause(default, "relations")
    bodies = {n: {"surfaces": _surfaces_of(b)} for n, b in paths.items()}
    vias = "; ".join(f"`{n}` arrives by `{(paths[n] or {}).get('via')}`" for n in sorted(paths))
    never = ["averaging two readings, which are answers to different questions",
             "picking between them silently"]
    if never_tail:
        never.insert(0, never_tail)
    return {
        "subject": "which relation an answer about this concept is reached through",
        "when": "a measure is grouped by or filtered on this concept and the question does not say "
                "through what",
        "then": f"{_named_readings(bodies, 'reading(s)')}. {vias}. {then_tail}",
        "never": _join(never),
    }


def additivity_guard(*, measure_column: str, axis_effects: dict) -> dict:
    """HOW this measure folds across each kind of axis — the fold law, per axis kind."""
    def _effect(v) -> str:
        return str(v).rsplit(".", 1)[-1]
    allowed = sorted(k for k, v in axis_effects.items() if _effect(v) == "additive")
    banned = sorted(k for k, v in axis_effects.items() if _effect(v) != "additive")
    spelled = "; ".join(f"across a {k} axis it is {_effect(axis_effects[k])}"
                        for k in sorted(axis_effects))
    #: `_join` uses "; " because most clauses are lists of independent prohibitions. An axis list is
    #: not: "a categorical; time axis" is not a sentence, and the first render of this canon produced
    #: exactly that. Alternatives are joined with "or" here and nowhere else.
    def _or(items) -> str:
        items = sorted(items)
        return items[0] if len(items) == 1 else " or ".join([", ".join(items[:-1]), items[-1]])

    sum_clause = (f"Sum it only across " + (f"{_or(allowed)} axes" if allowed else "")) if allowed \
        else "It may not be summed across ANY declared axis"
    return {
        "subject": f"how `{measure_column}` may be folded, per kind of axis",
        "when": f"`{measure_column}` is aggregated across an axis",
        #: NO "elsewhere" WHEN THERE IS NO ELSEWHERE. With nothing additive the sentence read "it may
        #: not be summed across ANY declared axis; elsewhere apply the declared effect", which
        #: contradicts itself in eleven words.
        "then": (f"{spelled}. {sum_clause}"
                 + ("; elsewhere apply the declared effect and say which was applied" if allowed
                    else ". Apply the declared effect and say which was applied")),
        "never": _join([f"summing `{measure_column}` across "
                        + (f"a {_or(banned)} axis" if banned else "an axis it is not additive over"),
                        "weighting every member of an axis equally when the declaration says otherwise"]),
    }


def composite_key_guard(*, code_column: str, scope_columns) -> dict:
    """A CODE THAT IS ONLY MEANINGFUL INSIDE A SCOPE — constrain it with its scope or not at all."""
    scopes = list(scope_columns or ())
    return {
        "subject": f"`{code_column}` is identified by the pair, not by itself",
        "when": f"`{code_column}` is constrained, grouped on, or joined",
        "then": (f"carry {_join([f'`{c}`' for c in scopes])} with it — the identity is "
                 f"({code_column}, {', '.join(scopes)}), and a value of `{code_column}` means "
                 f"different things under different {_join(scopes)}"),
        "never": _join([f"constraining or grouping on `{code_column}` without "
                        f"{_join([f'`{c}`' for c in scopes])}",
                        "treating two rows with the same code and different scope as one thing"]),
    }


CANONS.update({
    "mac.canon.population_select": population_select,
    "mac.canon.ratio_select": ratio_select,
    "mac.canon.column_select": column_select,
    "mac.canon.path_select": path_select,
    "mac.canon.additivity_guard": additivity_guard,
    "mac.canon.composite_key_guard": composite_key_guard,
})
