#!/usr/bin/env python3
"""sdk.project.vocabulary — the ONE place that says what the ontology's controlled-vocabulary terms
MEAN. The authored MAC carries namespaced tokens (<source>.field_role.dimension, mac.concept.rule.guarantee,
confidence C/I/Q, class enumeration, …) all over the concepts; their meaning lived only in the grammar
+ the author prompt. This projects a single glossary (vocabulary.json), grouped by namespace, with a
plain-language meaning per term AND how many times each is actually used in this source's ontology.

DETERMINISTIC + IDEMPOTENT (no LLM). WHERE THE TERMS COME FROM, in two kinds:

  * A group the framework CLOSES in mac_vocabulary.yaml — field roles (concept.column.roles), rule
    kinds (concept.rule), identity kinds (concept.column.identity), aggregation effect
    (concept.aggregation_effect), diagnostic codes — is READ from there: both WHICH terms exist and
    WHAT they mean. Until 2026-09-29 the first four were curated here as a second copy, and the copy
    had drifted every way a copy can: it still listed `attribute` (retired) and lacked `period` and
    `housekeeping`; it listed `resolved_axis` (retired 2026-09-28); and its "additivity" group was the
    binary `additive | non-additive` scale the vocabulary replaced at v0.1.15 with three terms —
    so every glossary this projector wrote, the public example bundles included, taught terms the
    schema refuses.

    READING THE DECLARATION IS NOT ENOUGH ON ITS OWN: the NAME of the block has to keep up with it.
    Two of these five were retired under this file on 2026-10-05/07 — `concept.column.role` with the
    scalar it named, and `concept.identity` with the block it described — and because a missing key
    returns `{}` the groups rendered EMPTY rather than failing. Measured on
    `sdk/authoring/exemplars/bundle`: 0 terms in `Field roles` and 0 in `Identity kind`, a glossary
    claiming the framework closes neither.
  * A group with NO vocabulary home — concept class, the two confidence scales, edge level — is
    curated below (CURATED). Those are the only meanings this file still owns.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

#: THE FOLD-AGNOSTIC VOCABULARY READER. `mac_vocabulary.yaml` may nest its dotted blocks
#: (`concept: column: measure_type:`) or spell them flat; every lookup here indexes them by their
#: DOTTED identity, and `tools/mac_vocab.flatten` is the one converter between the two.
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2] / 'tools'))
import mac_vocab as _mv  # noqa: E402

#: THE ONE READER OF A COLUMN'S DECLARATION, for the counts below. This module's own docstring records
#: what a SECOND COPY of a closed term set costs — the curated list "had drifted every way a copy can"
#: — and on 2026-10-07 it drifted the other way: the vocabularies it NAMES were retired under it.
#: MEASURED on `sdk/authoring/exemplars/bundle`: the `Field roles` group rendered 0 terms and the
#: `Identity kind` group 0 terms, because `mac.concept.column.role` and `mac.concept.identity` no
#: longer exist — so the glossary showed two empty groups and the page read as a framework with no
#: roles and no identity vocabulary at all.
import mac_project as _P  # noqa: E402


# THE ROLE NAMESPACE STOPPED BEING A SOURCE FACT ON 2026-10-07. It was one: every source defined its
# own `<source>.field_role.dimension`, and `build()` substituted the prefix it MEASURED so the public
# bundles would not carry one instance's name. The `roles:` map that replaced the scalar is MAC-CORE —
# `mac.concept.column.roles.<term>`, the same five terms in every bundle — so there is no per-source
# prefix left to measure and a placeholder standing in for one would be a hole with no filler. The
# constant survives as the group's namespace, now a fact rather than a template.
FIELD_ROLE_NS = "mac.concept.column.roles.*"

# group, namespace, note, [(term, meaning)] — the groups NO framework vocabulary declares. Anything
# that has a block in mac_vocabulary.yaml does not belong here; see FRAMEWORK below.
CURATED = [
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

# group, namespace shown, note, vocabulary block — the groups mac_vocabulary.yaml CLOSES. The terms and
# their meanings are read from the block at build time; nothing here names a term.
FRAMEWORK = [
    (
        # `mac.concept.column.role` WAS RETIRED WITH THE SCALAR IT NAMED, 2026-10-07, together with
        # `mac.concept.column.query_use` — "the machine-readable half" of it. One fact in two
        # vocabularies, of which only one had a key in mac.schema.json and neither could say that a
        # join key is also an axis (21 of contoso5's 112 columns). `mac.concept.column.roles` is the
        # whole declaration now, and this group measured 0 terms until it pointed there.
        "Field roles",
        FIELD_ROLE_NS,
        "What a question may DO with each column of a concept's grounding — declared as a MAP under "
        "`roles:`, each term carrying its own qualifier; the closed term set is "
        "mac.concept.column.roles.",
        "concept.column.roles",
    ),
    (
        "Rule kinds",
        "mac.concept.rule.*",
        "The kind of behavioural contract a rule expresses (MAC-core, source-agnostic).",
        "concept.rule",
    ),
    (
        # `mac.concept.identity` IS GONE AND SO IS THE BLOCK IT DESCRIBED. `concept.identity` left
        # mac.schema.json on 2026-10-05 (operator: "declare on concept level only what belongs to the
        # concept level") because identity is a COLUMN fact — which column is the key, which compose a
        # composite, which a count DISTINCTs. The surviving vocabulary is
        # `mac.concept.column.identity`, whose own description says "THE ONLY HOME — there is no
        # concept-level identity block". This group measured 0 terms until it pointed there.
        "Identity kind",
        "grounding.sources[].columns[].roles.identity",
        "What part a column plays in identifying one row of a concept (MAC-core; "
        "mac.concept.column.identity).",
        "concept.column.identity",
    ),
    (
        "Additivity",
        "concept.semantics.additivity",
        "Per axis, how a measure may be folded (MAC-core; the closed set is "
        "mac.concept.aggregation_effect — three terms, replacing the binary additive | non-additive "
        "scale at v0.1.15).",
        "concept.aggregation_effect",
    ),
]

#: The order the glossary renders in — stable across the 2026-09-29 change of source.
_GROUP_ORDER = [
    "Field roles", "Rule kinds", "Concept class", "Concept confidence", "Rule confidence",
    "Identity kind", "Additivity", "Edge level",
]


def _strip(v):
    return str(v or "").split(".")[-1]


def _vocabulary_file() -> Path | None:
    """The first readable mac_vocabulary.yaml: this checkout's own, then a sibling `meaning-as-code`
    checkout, then the platform's vendored copy under sdk/grammar."""
    root = Path(__file__).resolve().parents[2]
    for f in (root / "mac_vocabulary.yaml",
              root.parent / "meaning-as-code" / "mac_vocabulary.yaml",
              root / "sdk" / "grammar" / "mac_vocabulary.yaml"):
        if f.exists():
            return f
    return None


def _vocabulary() -> dict:
    """mac_vocabulary.yaml as a dict, or {} — and a printed line saying so, because a glossary with
    four empty groups must not look like a framework with no terms."""
    try:
        import yaml

        f = _vocabulary_file()
        if f is None:
            raise FileNotFoundError("no mac_vocabulary.yaml beside this checkout")
        #: FLATTENED: `mac_vocabulary.yaml` nests its dotted blocks and `_terms(vocab, block)` below
        #: indexes them by their dotted identity. `tools/mac_vocab.flatten` is the one converter.
        return _mv.flatten(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
    except Exception as exc:  # noqa: BLE001 — a projection must not break on an unreadable framework
        print(f"  vocabulary: mac_vocabulary.yaml unavailable ({type(exc).__name__}: {exc}); the "
              f"framework-governed groups render empty")
        return {}


def _terms(vocab: dict, block: str) -> list[tuple[str, str]]:
    """[(term, one-line meaning)] for a vocabulary block, in declaration order. A term's body is a bare
    string (concept.column.role) or a map carrying `description` / `definition` / `doc`
    (concept.column.measure_type, diagnostic_code) — the registry uses both, deliberately."""
    body = vocab.get(block) or {}
    t = body.get("terms") if body.get("terms") is not None else body.get("members")
    if not isinstance(t, dict):
        return []
    out = []
    for term, meaning in t.items():
        if isinstance(meaning, dict):
            meaning = meaning.get("description") or meaning.get("definition") or meaning.get("doc") or ""
        out.append((str(term), " ".join(str(meaning or "").split())))
    return out


def _diagnostic_taxonomy(vocab: dict) -> list:
    """The compiler's closed diagnostic taxonomy, READ from mac_vocabulary.yaml#diagnostic_code.

    IT BELONGS HERE, not on the Compiler Report. The report answers "what is wrong with THIS bundle";
    the full code list — including every code that did NOT fire — answers "what can the compiler even
    say", which is a fact about the FRAMEWORK and identical for every source. It was rendered as a
    grid on every compile page, so the reader met the whole taxonomy before the findings.

    Curated meanings are not duplicated: the vocabulary carries each code's `kind` and `description`,
    so this reads them. A fourth hand-maintained copy is the exact defect check_vocabulary_drift exists
    to catch — and the taxonomy moved INTO the vocabulary for the same reason.
    """
    terms = (vocab.get("diagnostic_code") or {}).get("terms") or {}
    return [
        (code, f"{(m or {}).get('kind', '')} — {(m or {}).get('description', '')}")
        for code, m in terms.items()
    ]


def glossary(vocab: dict) -> list:
    """[(group, namespace, note, [(term, meaning)])] in render order — framework groups from the
    vocabulary, the rest curated."""
    by_name = {g: (g, ns, note, terms) for g, ns, note, terms in CURATED}
    for g, ns, note, block in FRAMEWORK:
        by_name[g] = (g, ns, note, _terms(vocab, block))
    return [by_name[g] for g in _GROUP_ORDER]


def _column_specs(doc: dict):
    """Every column spec of a concept, over EVERY source — `(name, spec)` pairs.

    THE COUNTS ARE PER COLUMN NOW, because the facts are. `mac_project.column_roles` answers for the
    PRIMARY source only, which would undercount a concept grounded on two relations; the glossary's
    job is "how many times is this term actually used in this ontology", so it must see all of them.
    The part that needs judgement — the identity term, and the retired `part` -> `composite` spelling —
    still goes through `mac_project.column_identity` below.
    """
    for src in ((doc.get("grounding") or {}).get("sources") or []):
        if not isinstance(src, dict) or not isinstance(src.get("columns"), dict):
            continue
        for name, spec in src["columns"].items():
            yield str(name), (spec if isinstance(spec, dict) else {})


def build(concepts: dict, ont_edges: list | None = None) -> dict:
    # count how often each term is actually used across this ontology
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
        # THE TWO COLUMN GROUPS ARE COUNTED FROM THE COLUMNS, 2026-10-07. `Field roles` counted
        # `grounding.field_roles`, the LEGACY block a bundle on the column standard does not carry at
        # all, and `Identity kind` counted `concept.identity.kind`, a key mac.schema.json no longer
        # admits. MEASURED on `sdk/authoring/exemplars/bundle`: both counters came out EMPTY over 35
        # columns declaring 65 role terms and 12 identity terms, so the two groups rendered as a
        # framework with no roles and no identity vocabulary.
        #
        # ONE COLUMN CONTRIBUTES SEVERAL ROLE TERMS and that is the whole point of the map replacing
        # the scalar: a join key a question also groups by claims `identity` AND `axis`, which the
        # single `field_roles` value could not express and which is 21 of contoso5's 112 columns.
        # Counting the map's KEYS is therefore counting uses, not columns, and the denominator a
        # reader should compare against is the role count, never the column count.
        for _name, spec in _column_specs(c):
            roles = spec.get("roles") if isinstance(spec.get("roles"), dict) else {}
            for term in roles:
                field_roles[_strip(term)] += 1
            ident = _P.column_identity(spec)
            if ident:
                idkind[ident] += 1
        # fold effects may be written bare or `mac.`-qualified; the glossary's terms are bare, so the
        # count is keyed bare too
        for ax in ((con.get("semantics") or {}).get("additivity") or {}).values():
            additiv[_strip(ax)] += 1
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
    vocabulary = _vocabulary()
    vocab = glossary(vocabulary)
    _dx = _diagnostic_taxonomy(vocabulary)
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
        # NO NAMESPACE SUBSTITUTION ANY MORE. It existed because the role token was source-prefixed
        # (`<source>.field_role.dimension`) and the projector had to show the prefix it MEASURED
        # rather than one instance's. `mac.concept.column.roles.*` is MAC-core and the same in every
        # bundle, so there is nothing left to measure and `FIELD_ROLE_NS` is simply the namespace.
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
