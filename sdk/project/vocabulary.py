#!/usr/bin/env python3
"""sdk.project.vocabulary — the ONE place that says what the ontology's controlled-vocabulary terms
MEAN. The authored MAC carries namespaced tokens (<source>.field_role.dimension, mac.rule_kind.guarantee,
confidence C/I/Q, class enumeration, …) all over the concepts; their meaning lived only in the grammar
+ the author prompt. This projects a single glossary (vocabulary.json), grouped by namespace, with a
plain-language meaning per term AND how many times each is actually used in this source's ontology.

DETERMINISTIC + IDEMPOTENT (no LLM). Meanings are curated here (the grammar's closed sets are the
source of truth for WHICH terms exist; this adds the WHAT-they-mean)."""

from __future__ import annotations

from collections import Counter

# The field-role namespace is a SOURCE fact, not a method fact: every source defines its own
# (`<source>.field_role.dimension`), which is what the note below has always said. It was nonetheless
# hardcoded to one instance's prefix, so every glossary this projector wrote — the public example
# bundles included — carried that instance's name. `build()` substitutes the namespace it MEASURES in
# the ontology it is projecting; this placeholder stands only when the ontology declares no field role.
FIELD_ROLE_NS = "<source>.field_role.*"

# group, namespace, note, [(term, meaning)]  — the curated glossary.
VOCAB = [
    (
        "Field roles",
        FIELD_ROLE_NS,
        "What each column DOES in a concept's grounding (source-namespaced — every source defines its own).",
        [
            ("key", "An identity / join column — how a row is identified and how relations join."),
            ("dimension", "A filterable, group-by attribute — you slice and pivot the data by it."),
            (
                "attribute",
                "Display-only detail — carried for context, not a key and not aggregated.",
            ),
            ("measure", "An additive numeric fact — the number you sum / average."),
        ],
    ),
    (
        "Rule kinds",
        "mac.rule_kind.*",
        "The kind of behavioural contract a rule expresses (MAC-core, source-agnostic).",
        [
            (
                "resolution",
                "How to resolve / interpret a value — routing, canonicalisation, which column to trust.",
            ),
            (
                "aggregation",
                "How a measure rolls up across an axis (sum / average / not-additive).",
            ),
            ("default", "The assumption to apply when something isn't specified in the question."),
            (
                "ambiguity",
                "How to handle a genuinely ambiguous case (which reading wins, or refuse).",
            ),
            ("exclusion", "Rows or values to exclude / filter out of an answer."),
            (
                "guarantee",
                "An invariant the data is guaranteed to hold — relied on without re-checking.",
            ),
        ],
    ),
    (
        "Concept class",
        "class",
        "What kind of thing a concept is (MAC-core). Chosen first; drives which blocks are required.",
        [
            ("entity", "A real-world thing with its own identity."),
            ("event", "Something that happens — a lifecycle with states / phases."),
            ("measure", "A numeric fact you aggregate (needs an additivity block)."),
            (
                "enumeration",
                "A closed set of coded values — a lookup / code list (needs a values block).",
            ),
            ("reference", "A dimension / lookup that identifies and describes."),
            (
                "grouping",
                "A rollup that groups a leaf concept — e.g. region over country (needs a members block).",
            ),
            ("meta", "A meta-plane concept — about the model itself, not the business data."),
        ],
    ),
    (
        "Concept confidence",
        "metadata.confidence",
        "How trustworthy a concept's definition is — the maturity signal on the Ontology Quality dashboard.",
        [
            ("C", "Confirmed by an SME — authoritative."),
            ("I", "Inferred by the harvest (machine) — plausible but not SME-confirmed."),
            ("Q", "Needs SME input — a known open question / gap."),
        ],
    ),
    (
        "Rule confidence",
        "contract.rules[].confidence",
        "How trustworthy a single rule is (a different scale from concept confidence).",
        [
            ("C", "Confirmed — an SME has signed it off."),
            ("P", "Proposed — authored from the schema/context, not yet confirmed (the default)."),
            ("R", "Rejected — kept for the record but NOT active."),
        ],
    ),
    (
        "Identity kind",
        "concept.identity.kind",
        "How a concept's rows are uniquely identified (MAC-core).",
        [
            ("iso", "An ISO standard code (e.g. iso2 / iso3 for country)."),
            ("code", "A plain coded key."),
            (
                "namespace_code",
                "A code namespaced by another dimension (e.g. brand-scoped country code).",
            ),
            ("fk_name", "Identity via a foreign-key name."),
            (
                "composite",
                "Identity is the composite of several columns (typical for fact / KPI grain).",
            ),
            ("resolved_axis", "Identity resolved along an axis at query time."),
            ("sme_pending", "Identity not yet decided — needs an SME."),
        ],
    ),
    (
        "Additivity",
        "concept.semantics.additivity",
        "Per axis, whether a measure can be summed (MAC-core; only these two values exist).",
        [
            ("additive", "Can be summed across this axis (e.g. volume over time)."),
            (
                "non-additive",
                "Cannot be summed across this axis (a stock, or unlike KPI types together).",
            ),
        ],
    ),
    (
        "Edge level",
        "edges[].level",
        "The stage a relationship lives at (MAC-core).",
        [
            ("physical", "A stored foreign-key join between the relations."),
            ("business", "A semantic relationship between concepts (identity / shared_attribute)."),
            ("federation", "A cross-source relationship (same real-world thing across sources)."),
        ],
    ),
]


def _strip(v):
    return str(v or "").split(".")[-1]


def _diagnostic_taxonomy() -> list:
    """The compiler's closed diagnostic taxonomy, READ from mac_vocabulary.yaml#diagnostic_code.

    IT BELONGS HERE, not on the Compiler Report. The report answers "what is wrong with THIS bundle";
    the full code list — including every code that did NOT fire — answers "what can the compiler even
    say", which is a fact about the FRAMEWORK and identical for every source. It was rendered as a
    grid on every compile page, so the reader met the whole taxonomy before the findings.

    Curated meanings are not duplicated: the vocabulary carries each code's `kind` and `description`,
    so this reads them. A fourth hand-maintained copy is the exact defect check_vocabulary_drift exists
    to catch — and the taxonomy moved INTO the vocabulary this evening for the same reason.
    """
    try:
        from pathlib import Path  # NOT imported at module level in this file

        import yaml

        for base in (
            Path(__file__).resolve().parents[2].parent / "meaning-as-code",
            Path(__file__).resolve().parents[2] / "sdk" / "grammar",
        ):
            f = base / "mac_vocabulary.yaml"
            if f.exists():
                terms = (
                    (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("diagnostic_code")
                    or {}
                ).get("terms") or {}
                return [
                    (code, f"{m.get('kind', '')} — {m.get('description', '')}")
                    for code, m in terms.items()
                ]
    except Exception as exc:
        # NARROW THE SILENCE. A bare `pass` here hid a NameError (Path was never imported in this
        # module) and the taxonomy simply rendered as absent — a missing section looks identical to
        # "this framework has no codes". A projection must not break on an unreadable framework, but
        # it must SAY so rather than quietly show less.
        print(f"  vocabulary: diagnostic taxonomy unavailable ({type(exc).__name__}: {exc})")
    return []


def build(concepts: dict, ont_edges: list | None = None) -> dict:
    # count how often each term is actually used across this ontology
    field_role_ns: set[str] = set()
    field_roles, rule_kinds, classes, mconf, rconf, idkind, additiv = (
        Counter(),
        Counter(),
        Counter(),
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    for c in concepts.values():
        con = c.get("concept") or {}
        classes[con.get("class")] += 1
        mconf[(c.get("metadata") or {}).get("confidence")] += 1
        idkind[(con.get("identity") or {}).get("kind")] += 1
        for role in ((c.get("grounding") or {}).get("field_roles") or {}).values():
            field_roles[_strip(role)] += 1
            prefix = str(role or "").rpartition(".")[0]
            if prefix:
                field_role_ns.add(f"{prefix}.*")
        for ax in ((con.get("semantics") or {}).get("additivity") or {}).values():
            additiv[ax] += 1
        for r in (c.get("contract") or {}).get("rules") or []:
            rule_kinds[_strip(r.get("kind"))] += 1
            rconf[r.get("confidence")] += 1
    edge_levels = Counter(e.get("level") for e in (ont_edges or []))
    usage = {
        "Field roles": field_roles,
        "Rule kinds": rule_kinds,
        "Concept class": classes,
        "Concept confidence": mconf,
        "Rule confidence": rconf,
        "Identity kind": idkind,
        "Additivity": additiv,
        "Edge level": edge_levels,
    }
    groups = []
    vocab = list(VOCAB)
    _dx = _diagnostic_taxonomy()
    if _dx:
        vocab.append(
            (
                "Diagnostic codes",
                "mac.diagnostic_code.*",
                "Every finding the MAC compiler can report — the CLOSED taxonomy, whether or not "
                "it fired on this source. A code is the contract: suppressions and counts are "
                "keyed on it, so its meaning cannot change without a version bump.",
                _dx,
            )
        )
    for group, ns, note, terms in vocab:
        if ns is FIELD_ROLE_NS:
            ns = ", ".join(sorted(field_role_ns)) or FIELD_ROLE_NS
        u = usage.get(group, Counter())
        groups.append(
            {
                "group": group,
                "namespace": ns,
                "note": note,
                "terms": [{"term": t, "meaning": m, "count": int(u.get(t, 0))} for t, m in terms],
            }
        )
    return {"groups": groups}
