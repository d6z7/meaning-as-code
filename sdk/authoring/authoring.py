#!/usr/bin/env python3
"""MAC authoring — the harvest's per-table brain when the target is MAC (not OKF).

`author_concept()` turns one table's raw schema (+ SME context + an exemplar concept)
into a MAC concept YAML via one Bedrock call; `process()` authors → parses → validates
against mac.schema.json → applies deterministic closed-vocabulary autofixes → re-validates,
returning a status the harvest streams to the console. Same loop proven in author_spike.py,
packaged for reuse by console_api's MAC harvest mode.
"""

from __future__ import annotations

# ── THE SCHEMA GENERATION HAS ONE HOME, AND IT IS THE SCHEMA ────────────────────────────────────
# `schema_version: '0.1.13'` was a LITERAL in this file's prompt, in edges.py and twice in
# data_plane.py — so every concept, edge and descriptor this SDK authored claimed a generation TWO
# behind the core. Nothing tied the literal to CONFORMANCE.md §6 or to validate_schema, so a bump
# left it silently stale, and the operator found it in the authored output: "how on earth are you
# coming with the schema version schema_version: 0.1.13 ?!?!".
def schema_generation() -> str:
    """The generation `mac.schema.json` declares, read at call time so a bump cannot leave a copy."""
    import json as _json, pathlib as _p
    here = _p.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "mac.schema.json"
        if cand.is_file():
            return str(_json.loads(cand.read_text(encoding="utf-8")).get("version") or "0.1.15")
    return "0.1.15"


import re
from pathlib import Path

import yaml
from jsonschema import validators as jsv

_ROOT = Path(__file__).resolve().parent.parent
from sdk.grammar.resolve import load_schema as _load_schema  # ONE schema home

SCHEMA = _load_schema()

# ── THE EXEMPLAR IS THE FIXTURE, and the fixture is a bundle on the current standard ────────────
# `exemplars/geography/country.yaml` was shown to the model as "the SHAPE to match" while carrying
# schema_version 0.1.13, a flat `columns:` list, a `field_roles` block and `identity.canonical_key`
# beside the key — every one of them forbidden by the prompt three lines above it. It validated,
# because the flat list is kept legal, and no test ever loaded what the composer wrote. The
# exemplar now lives in a bundle that tests/test_column_roundtrip.py validates, runs through this
# module's own gates, and (when the platform is beside this repo) loads with the runtime parser.
EXEMPLAR_BUNDLE = _ROOT / "authoring" / "exemplars" / "bundle"
EXEMPLAR = EXEMPLAR_BUNDLE / "ontology" / "concepts" / "product.yaml"


# ── CLOSED VOCABULARIES ARE READ, NEVER RE-LISTED (CONFORMANCE §2.1) ────────────────────────────
# The prompt used to carry identity kinds, rule kinds, roles and measure types typed by hand, and
# one of them (`resolved_axis`) had been retired for a day while the prompt still taught it. The
# lists below are rendered from mac_vocabulary.yaml at import, the way `schema_generation()` renders
# the version, so a term the vocabulary drops disappears from the prompt in the same change.
def _vocabulary() -> dict:
    for parent in Path(__file__).resolve().parents:
        cand = parent / "mac_vocabulary.yaml"
        if cand.is_file():
            return yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
    raise FileNotFoundError("mac_vocabulary.yaml above sdk/authoring/authoring.py")


def vocabulary_terms(namespace: str) -> list[str]:
    """The terms of one closed vocabulary block, in declared order — e.g. `concept.identity`."""
    block = _vocabulary().get(namespace) or {}
    terms = block.get("terms") or block.get("members") or {}
    return list(terms.keys() if isinstance(terms, dict) else terms)


def _term_glosses(namespace: str) -> str:
    block = _vocabulary().get(namespace) or {}
    lines = []
    for term, body in (block.get("terms") or {}).items():
        gloss = body if isinstance(body, str) else (body.get("definition") or body.get("description") or "")
        first = str(gloss).strip().split(". ")[0].rstrip(".")
        lines.append(f"    {term:<12} {first}")
    return "\n".join(lines)


def concept_classes() -> list[str]:
    """The schema's concept classes, minus `meta` — that class is the runtime's own meaning plane,
    never authored for a source."""
    enum = SCHEMA["$defs"]["ConceptFile"]["properties"]["concept"]["properties"]["class"]["enum"]
    return [c for c in enum if c != "meta"]
_CF = dict(SCHEMA["$defs"]["ConceptFile"])
_CF["$defs"] = SCHEMA["$defs"]
_CONCEPT_VALIDATOR = jsv.validator_for(SCHEMA)(_CF)

# Autofix philosophy: the validator NAMES the legal enum, so don't hand-transcribe
# vocabularies (that's how the misses happened). For any enum error we first reconcile
# spelling generically (underscore/hyphen/case) against the schema's real values, then
# fall back to this small SEMANTIC map for genuine near-misses (not mere spelling).
# 2026-09-29: five key-shaped guesses (surrogate/primary_key/pk/id/natural_key -> code) were
# removed — a key's KIND cannot be told from the word "id", which is exactly why the runtime parser
# refuses to guess it; and `semi_additive -> non-additive` mapped onto a scale the schema retired
# (aggregation_effect is additive | average | none), so the entry could never apply.
_SEMANTIC = {
    "compound": "composite",
    "namespace": "namespace_code",
    "foreign_key": "fk_name",
    "fk": "fk_name",
    "I": "P",
    "Q": "P",  # rule confidence scale C/P/R
}

SYS_PROMPT = """You are a MAC ontology author. MAC models a data source as CONCEPT files (YAML). Author ONE concept for the business notion named below.

A CONCEPT IS A BUSINESS NOTION, NOT A TABLE. The mapping between concepts and relations is M:N and you are given every relation this notion needs:
- ONE concept may ground on SEVERAL relations — list each under `grounding.sources`, which is a LIST.
- ONE relation may serve SEVERAL concepts; grounding on a relation does not consume it.
- A relation may back NO concept at all: a pure mapping/bridge table is not a notion, it dissolves into a rule or an edge on the notions it relates.
- A notion may exist with NO backing table of its own (a perspective, a plan stage, a rollup) — ground it on the relation that carries its discriminating column.

Shape of a concept file:
- metadata: {concept, source, version, schema_version: '{SCHEMA_GENERATION}', status: draft, owner, confidence}   # metadata.confidence ∈ C|I|Q (C=confirmed, I=inferred, Q=needs-SME)
- concept: {name, label, class, definition}   # class is EXACTLY one of: {CLASSES}. There is NO `identity:` block on a concept — identity is declared on the COLUMNS, below.
- grounding: {sources: [{relation, key, columns: {<col>: {role, identity?, measure?}}}], grain: "one row per ..."}
  EVERYTHING ABOUT A COLUMN GOES ON THE COLUMN. `columns` is a MAP keyed by column name, not a list of
  names, and it is the ONLY place a column's facts are declared:
      columns:
        OrderKey:    {role: key, identity: part}
        LineNumber:  {role: key, identity: part}
        CustomerKey: {role: key, identity: reference}
        OrderDate:   {role: dimension}
        Quantity:    {role: measure, measure: {type: mac.concept.column.measure_type.flow, unit: units}}
        Surname:     {role: dimension}
        ValidFrom:   {role: housekeeping}   # pipeline bookkeeping — never offered to a question
        Status:                      # a bare name serves the column and says nothing more
  TODAY'S FLAGS ARE role, identity, counts, measure, rulings — and ONLY those five, because a flag ships
  with the code that reads it. A misspelled flag is a LOAD ERROR, which is the whole difference between a
  flag and a sentence. `identity: canonical` IS the concept's key; `part` marks one column of a
  composite key (several parts and no canonical IS a composite — there is nothing else to declare);
  `reference` marks a foreign key. `counts: true` marks the column one INSTANCE is counted by when the
  relation is served FINER than the thing — a store dimension keyed on a version surrogate counts
  VERSIONS unless this says otherwise. Several columns may carry `measure:` when they compose
  ONE quantity (Quantity x NetPrice); then `semantics.unit` on the concept states the composed unit.
  DO NOT WRITE A `field_roles:` BLOCK. It is PROJECTED from these roles — writing both gives one fact
  two homes that can drift, and check_delivery_consistency's ONE-HOME invariant reports both. Do not write
  the namespaced form (`<ns>.field_role.dimension`) either: the namespace is added by the projection.
  DO NOT WRITE AN `identity:` BLOCK UNDER `concept:` AT ALL. It was removed from the schema on
  2026-10-05 and a file carrying one fails validation. Identity is a column fact: which column is the
  key, which columns compose a composite, and which one a count DISTINCTs are all statements about
  columns, so they are declared where the column is.
- contract: {no_probe_guarantee?, rules: [{id, subject, kind: mac.concept.rule.<{RULE_KINDS}>, confidence, scope: ACME, binds: [<cols>], when, then, never, why}]}   # a RULE's confidence ∈ C|P|R (C=confirmed, P=proposed, R=rejected) — this is NOT the metadata C/I/Q scale; default P when unconfirmed
- governance: {owner, last_reviewed}

CHOOSE THE CLASS FIRST, and INCLUDE ITS REQUIRED BLOCK — this is mandatory and schema-enforced:
- a CODE / LOOKUP table (a small set of coded values — e.g. package type, material, price tier, sales channel) → class: enumeration, and you MUST add a TOP-LEVEL `values:` block:
      values:
        closure: closed | open | unknown
        items:
          - {code: <code>, label: <human label>, meaning: <what it means>}
  Fill items from the CONTEXT / lookup tables when present; if the value set is not in the inputs, use closure: unknown and include only codes you can justify (never invent values).
- a FACT / KPI / measure table (numeric values you aggregate) → class: measure, and you MUST add a `concept.semantics:` block:
      semantics:
        purpose: <one line>
        measure_type: mac.concept.column.measure_type.<{MEASURE_TYPES}>
        axis_kinds: {<axis>: mac.concept.axis_kind.<time|categorical>, ...}   # one entry per aggregation axis
  DO NOT WRITE AN `additivity:` BLOCK. How the measure folds along each axis is DERIVED from
  (measure_type x axis_kind) by the law in mac_vocabulary.yaml. Writing it out would state the same
  fact twice — and because you would be authoring both the premise and the conclusion, the two can
  drift: a concept once declared `Target` and wrote `geography: additive`, which the law forbids, and
  a value anchor summed that measure across models for weeks on the strength of it.
  CHOOSE THE TYPE CAREFULLY — it is the whole claim (mac_vocabulary.yaml#concept.column.measure_type):
{MEASURE_TYPE_GLOSSES}
- an EVENT table (rows that track a lifecycle / state transitions) → class: event, and you MUST add a TOP-LEVEL `lifecycle:` block using ONLY these keys (any other key is schema-rejected):
      lifecycle:
        phases: [<phase name>, ...]        # optional siblings: phase_sequence, states, boundary, note — and NOTHING else
- a ROLLUP / GROUPING table (rows that GROUP or ROLL UP other rows — e.g. a region→countries map, a market footprint, a membership list) → class: grouping, and you MUST add a TOP-LEVEL `members:` OBJECT (NOT a list) shaped exactly as:
      members:
        over: <the LEAF concept this rolls up — e.g. Country, Product>   # REQUIRED — the grouped concept
        member_source:
          kind: rule        # 'rule' = membership computed via a FK / transitive walk; 'enumerated' = explicit named sets
          rule: <one line: how membership is computed, e.g. "region groups countries via acme_scoped_market_code">
  `members:` is a TOP-LEVEL OBJECT with a REQUIRED `over:` key (sibling of `concept:` / `grounding:` / `contract:`), NEVER a bare list and NEVER nested under `concept:`. (Placement reference: `semantics` is nested UNDER `concept:`; but `values`, `members`, and `lifecycle` are TOP-LEVEL siblings of `concept:`.)
- a plain dimension / identifier table (keys + attributes, not a closed code list) → class: reference or entity (no extra required block).

Authoring rules:
- Ground on the REAL table and columns provided. NEVER invent a column that isn't in the schema.
- Give every meaningful column a role from mac.concept.column.role — {ROLES}: key (identity/join), dimension (filterable, groupable), measure (numeric payload, folded as its measure_type allows), period (THE reporting date when a relation carries several), housekeeping (pipeline bookkeeping — validity windows, load stamps — never offered to a question). `attribute` is not a role.
- EXACTLY ONE column carries `identity: canonical` when a single column identifies the thing. If the grain is a COMPOSITE of several columns (typical for fact / KPI tables), mark EVERY column of the tuple `identity: part` and give NONE of them `canonical` — several parts and no canonical IS the composite, and there is no concept-level term to add.
- Write a precise 2-4 sentence definition anchored in the schema + context.
- WHERE MAC HAS A CANON FOR A RULE SHAPE, BIND — DO NOT WRITE THE CLAUSES. Supply
  `realized_by: {udf: mac.canon.<name>, params: {...}}` and OMIT when/then/never; they are RENDERED
  from the canon. This is not a style preference: 13 concepts once each wrote their own copy of ONE
  refusal law, producing 13 different wordings, and one of them came out with an empty `then` that
  promised an answer it could not give. A rule that supplies parameters cannot have a bare clause.
      exclusion.no_evidence — a MEASURE with no row for a resolved scope:
        realized_by: {udf: mac.canon.refuse_measure_no_row,
                      params: {source: <SOURCE>, label: <measure as a human says it>,
                               slot: <what was resolved and found empty: scope|country|cell>,
                               confusable: [<measures a tired reader would substitute>],
                               substitute_kind: measure|source,
                               null_is_real: <set ONLY if a resolved row's null MEANS something>}}
      exclusion.no_evidence — a NAME that does not resolve to a code:
        realized_by: {udf: mac.canon.refuse_unresolvable_name,
                      params: {source: <SOURCE>, thing: <model|market|brand|country>,
                               code: <the identity it should resolve to>,
                               via: <the register the lookup goes through, if any>}}
  `confusable` matters most: an empty On-hand Inventory answered with Target Inventory is worse than no answer,
  and only you know which measure is the tempting one here.
- Propose contract rules ONLY where the schema or context justify them; a rule's confidence ∈ C|P|R (default P). Never fabricate a rule or a guarantee the data doesn't support.
- Match the SHAPE and style of the EXAMPLE concept, but NOT its content.
- Output ONLY the YAML for the one concept — no prose, no markdown fences, no commentary."""


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE PLAN PASS — decide WHAT the notions are before authoring any of them
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# WHY THIS EXISTS. Authoring used to run one call per dataset, which made the concept/relation mapping
# 1:1 by construction — the prompt said "exactly ONE concept for the given target table", the driver
# looped per dataset, and the file was named after the dataset stem. Three independent enforcements of
# the same wrong shape. Measured: one measured bundle is exactly 20 concepts from 20 datasets. A per-table unit of
# work cannot express a notion spanning two relations, cannot let one relation serve two notions, and
# cannot decline to make a concept for a bridge table.
#
# OPERATOR RULING 2026-08-18: the concept/relation relationship is M:N. Not negotiable.
#
# So the model sees the WHOLE relation inventory ONCE and proposes the notions. Only then is each
# notion authored, with every relation it named. Declining a relation is a first-class outcome and
# must carry a reason, so "no concept here" is a recorded judgement rather than an omission.
# SUBSTITUTED AT IMPORT, because SYS_PROMPT is a plain literal passed straight to the model: a
# `{SCHEMA_GENERATION}` placeholder left in it would reach the author verbatim, which is worse than the
# stale `0.1.13` it replaced.
SYS_PROMPT = (
    SYS_PROMPT.replace("{SCHEMA_GENERATION}", schema_generation())
    .replace("{CLASSES}", " | ".join(concept_classes()))
    .replace("{RULE_KINDS}", "|".join(vocabulary_terms("concept.rule")))
    .replace("{ROLES}", " | ".join(vocabulary_terms("concept.column.role")))
    .replace("{MEASURE_TYPES}", "|".join(vocabulary_terms("concept.column.measure_type")))
    .replace("{MEASURE_TYPE_GLOSSES}", _term_glosses("concept.column.measure_type"))
)
assert "{" + "CLASSES}" not in SYS_PROMPT and "resolved_axis" not in SYS_PROMPT

PLAN_PROMPT = """You are a MAC ontology architect. You are given EVERY produced relation of one data source, plus SME context. Propose the BUSINESS NOTIONS this source should expose as MAC concepts.

A concept is a business notion, NOT a table. The mapping is M:N:
- one notion may need SEVERAL relations;
- one relation may serve SEVERAL notions;
- a pure mapping/bridge table backs NO notion — it dissolves into a rule or an edge;
- A NOTION OFTEN HAS NO TABLE OF ITS OWN. This is the most commonly MISSED case, so work it deliberately: for every FACT relation, walk its columns and ask of each dimension/discriminator column whether it names a thing the business talks about. If it does, that is a NOTION, and it grounds on the fact relation that carries the column.
  Worked example of the shape: a fact relation with columns `role`, `scenario`, `brand_code`, `country_code` carries FOUR notions — a Perspective (which view of the world the row is stated from), a Scenario (how firm the number is), a Brand and a Country — none of which has a table. A register in the VALUE REGISTERS section naming that column's members is strong evidence the notion exists.
  Do this pass EXPLICITLY before you finish: list the fact relations' dimension columns and confirm each is either already a notion or deliberately not one.

Emit ONE YAML document, exactly these two top-level keys:

concepts:
  - name: <PascalCase business name — what a business person calls it, NOT the table name>
    class: entity | event | measure | enumeration | reference | grouping
    grounds_on: [<relation stem>, ...]        # one or more; every entry MUST be a relation given below
    why: <one line: what business question this notion answers>
    confidence: C|I|Q                          # Q = you are guessing and an SME must confirm this notion exists
not_a_concept:
  - relation: <relation stem>
    reason: <why this relation backs no notion — e.g. "bridge table; dissolves into a rule on X">

RULES
- EVERY relation given to you appears exactly once across `concepts[].grounds_on` and `not_a_concept[]`. Never silently drop one.
- Never invent a relation that was not given.
- THE COUNT IS DRIVEN BY THE BUSINESS, NOT BY THE TABLE COUNT — it may be FEWER than the number of relations, or MORE. Both directions are errors:
  * TOO FEW: a relation whose discriminator column holds several distinct member FAMILIES serves ONE NOTION PER FAMILY. If a fact table's `kpi`/`type`/`metric` column contains families like `sales_*`, `stock_*`, `plan_*`, each family is a SEPARATE measure notion with its own meaning and its own aggregation behaviour — never one generic "Measurement" concept over all of them. Read the VALUE REGISTERS below and count the families.
  * TOO MANY: two relations that are the same notion at different grain are ONE concept grounding on both; a bridge table is no notion at all.
- CONFIDENCE IS ABOUT EVIDENCE, NOT ABOUT YOUR CERTAINTY. Use C only where a named SME document or a register MEMBER LIST establishes the notion. Use I where you inferred it from the schema. Use Q where an SME must confirm the notion exists at all. A plan in which everything is C is wrong by construction — you are proposing, not ratifying, and the whole point of this pass is to hand a human the list of things worth arguing about.
- Output ONLY the YAML — no prose, no fences."""


def plan_concepts(
    inventory_md: str,
    context: str,
    *,
    model: str,
    effort: str,
    region: str,
    max_tokens: int = 8000,
    thinking_budget: int | None = None,
    cache=None,
) -> dict:
    """One call over the WHOLE relation inventory -> {concepts: [...], not_a_concept: [...]}."""
    from sdk.authoring.harvest_model import make_invoker

    human = (
        "## PRODUCED RELATIONS — every relation this source exposes\n\n"
        f"{inventory_md}\n\n"
        "## CONTEXT — SME docs (grounding; use what is relevant)\n\n"
        f"{context or '(no context docs uploaded)'}\n\n"
        "Propose the business notions now. Output only YAML."
    )
    from botocore.config import Config

    cfg = Config(
        read_timeout=900, connect_timeout=20, retries={"max_attempts": 4, "mode": "adaptive"}
    )
    invoke = make_invoker(
        model,
        effort,
        max_tokens,
        region=region,
        thinking_budget=thinking_budget,
        botocore_config=cfg,
    )
    raw = (
        cache.complete(
            PLAN_PROMPT,
            human,
            model=model,
            effort=effort,
            thinking_budget=thinking_budget,
            invoke_fn=invoke,
        )
        if cache is not None
        else invoke(PLAN_PROMPT, human)
    )
    return yaml.safe_load(_strip_fences(raw)) or {}


def check_plan(plan: dict, relations: list) -> tuple[list, list]:
    """(warnings, failures). The plan must ACCOUNT FOR every relation — exactly once — and may not
    invent one. Silent omission is the failure mode this catches: a relation neither grounded nor
    declined is a relation nobody decided about."""
    warn, fail = [], []
    given = set(relations)
    seen = {}
    for c in plan.get("concepts") or []:
        for r in c.get("grounds_on") or []:
            seen.setdefault(r, []).append(c.get("name"))
    for d in plan.get("not_a_concept") or []:
        seen.setdefault(d.get("relation"), []).append("(declined)")
    invented = sorted(set(seen) - given)
    missing = sorted(given - set(seen))
    if invented:
        fail.append(f"plan names {len(invented)} relation(s) that were not given: {invented[:5]}")
    if missing:
        fail.append(
            f"plan accounts for neither a concept nor a decline on {len(missing)} relation(s): "
            f"{missing[:5]} — every relation must be decided about"
        )
    for r, owners in seen.items():
        if len(owners) > 1 and "(declined)" in owners:
            fail.append(
                f"relation {r!r} is both grounded ({[o for o in owners if o != '(declined)']}) "
                f"and declined — decide one"
            )
    if not (plan.get("concepts") or []):
        fail.append("plan proposes no concepts at all")
    return warn, fail


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return str(content or "")


def _strip_fences(t: str) -> str:
    t = t.strip()
    m = re.search(r"```ya?ml\n(.*?)\n```", t, re.DOTALL)
    if m:
        return m.group(1).strip()
    return re.sub(r"^```.*?\n|\n```$", "", t).strip()


def grep_context(ctx_dir: Path | None, terms: list[str], cap: int = 20000) -> str:
    if not ctx_dir or not ctx_dir.exists() or not terms:
        return ""
    pat = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)
    chunks, total = [], 0
    for f in sorted(ctx_dir.glob("*.md")):
        keep, seen = [], set()
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, ln in enumerate(lines):
            if pat.search(ln):
                for h in lines[max(0, i - 1) : i + 2]:
                    if h not in seen:
                        seen.add(h)
                        keep.append(h)
        if keep:
            block = (f"### from {f.name}\n" + "\n".join(keep[:150]))[: cap - total]
            chunks.append(block)
            total += len(block)
            if total >= cap:
                break
    return "\n\n".join(chunks)


def author_concept(
    name: str,
    schema_md: str,
    context: str,
    exemplar: str,
    *,
    model: str,
    effort: str,
    region: str,
    max_tokens: int = 12000,
    thinking_budget: int | None = None,
    cache=None,
    corrective: str = "",
) -> str:
    """Author ONE MAC concept YAML via a single LLM call.

    Routes through the shared harvest_model layer: a single model-swappable builder (dispatch
    on id prefix, thinking_budget knob) wrapped by an optional content-addressed ``cache`` so
    an unchanged authoring input re-runs byte-identically. ``cache=None`` runs live (uncached)
    — the legacy behavior, preserved for any direct caller.
    """
    from sdk.authoring.harvest_model import make_invoker

    human = (
        "## EXAMPLE MAC CONCEPT (shape reference only — do NOT copy its content)\n\n"
        f"{exemplar}\n\n"
        "## GROUNDING RELATIONS — schema, provenance and ROWS for EVERY relation this notion needs\n\n"
        "(one concept may ground on several; list each under grounding.sources. Each relation ends "
        "with a sample of its rows: the definition, the identity and the grain are read FROM THE ROWS, "
        "and a claim the rows contradict is wrong.)\n\n"
        f"{schema_md}\n\n"
        "## CONTEXT — SME docs (grounding; use what's relevant, ignore the rest)\n\n"
        f"{context or '(no context docs uploaded)'}\n\n"
        f"Author the MAC concept YAML for the business notion now (concept name: {name}). "
        "Output only YAML."
        + (
            f"\n\n## CORRECTION REQUIRED — a previous attempt was REJECTED\n\n{corrective}\n\n"
            "Fix exactly this and re-emit the whole concept."
            if corrective
            else ""
        )
    )
    from botocore.config import Config

    cfg = Config(
        read_timeout=900, connect_timeout=20, retries={"max_attempts": 4, "mode": "adaptive"}
    )
    invoke = make_invoker(
        model,
        effort,
        max_tokens,
        region=region,
        thinking_budget=thinking_budget,
        botocore_config=cfg,
    )
    if cache is not None:
        raw = cache.complete(
            SYS_PROMPT,
            human,
            model=model,
            effort=effort,
            thinking_budget=thinking_budget,
            invoke_fn=invoke,
        )
    else:
        raw = invoke(SYS_PROMPT, human)
    return _strip_fences(raw)


def _errors(obj) -> list:
    return sorted(_CONCEPT_VALIDATOR.iter_errors(obj), key=lambda e: list(e.path))


def _autofix(obj: dict) -> list[str]:
    """Deterministic conformance fixes driven by the validator's own errors:
    (0) composite grain (canonical_key list -> kind=composite), then for every enum
    error, reconcile spelling generically against the schema's real enum, falling back
    to the SEMANTIC near-miss map. Returns the applied fixes."""
    fixes = []
    for err in _errors(obj):
        parts = list(err.path)
        path = "/".join(str(x) for x in parts)
        # (0) composite grain: canonical_key given as a list -> kind=composite, drop it
        if path == "concept/identity/canonical_key":
            ident = obj.get("concept", {}).get("identity", {})
            if isinstance(ident.get("canonical_key"), list):
                ident["kind"] = "composite"
                ident.pop("canonical_key", None)
                fixes.append(
                    "concept/identity: canonical_key was a list -> kind=composite (key dropped)"
                )
            continue
        # (0b) a null grounding key (per-run variance) -> drop the optional key
        m = re.fullmatch(r"grounding/sources/(\d+)/key", path)
        if m and err.instance is None:
            src = obj.get("grounding", {}).get("sources", [])[int(m.group(1))]
            src.pop("key", None)
            fixes.append(f"{path}: null key dropped")
            continue
        # (1) enum errors: spelling-normalize against the schema's real enum, else SEMANTIC
        if getattr(err, "validator", None) != "enum" or not parts:
            continue
        allowed = list(err.validator_value or [])
        bad = err.instance
        if not isinstance(bad, str):
            continue
        newval = next(
            (
                c
                for c in (
                    bad.replace("_", "-"),
                    bad.replace("-", "_"),
                    bad.lower(),
                    bad.replace("_", "-").lower(),
                    _SEMANTIC.get(bad),
                )
                if c and c in allowed
            ),
            None,
        )
        if newval is None:
            continue
        cur = obj
        for p in parts[:-1]:
            cur = cur[p]
        if cur.get(parts[-1]) == bad:
            cur[parts[-1]] = newval
            fixes.append(f"{path}: '{bad}' -> '{newval}'")
    return fixes


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# INSTRUCTION COMPLIANCE — schema-valid is not instruction-followed
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# MEASURED on acme/acme2, 2026-08-18. SYS_PROMPT asks for two things it does not get:
#
#   "Give every meaningful column a field_role"      -> field_roles present on 0 of 22 concepts
#   "metadata.confidence in C|I|Q ... Q=needs-SME"   -> 17 of 22 stamped C, none reviewed
#
# The instructions are THERE. The JSON Schema cannot see them: `field_roles` is optional and `C` is a
# legal enum member, so every one of those concepts validates. A prompt whose compliance is never
# checked degrades silently, and downstream nothing can tell a measured claim from a guess — which is
# how a target-inventory measure shipped `additive` as CONFIRMED and produced a wrong anchor.
#
# WHY THE CONFIDENCE RULE IS NOT A JUDGEMENT CALL. `C` means an SME ratified the meaning
# (CONFORMANCE.md L3). A model cannot ratify its own output, so `C` on a freshly authored concept is
# not "possibly optimistic", it is structurally unavailable. Forcing it to `I` changes no meaning; it
# states the truth about who is claiming. The concept keeps its claim and loses only the certificate.


def _canon_shapes() -> dict:
    """{rule shape -> [canon names]} read from mac_vocabulary.yaml#canon.members[].serves.

    THE REGISTRY ALREADY KNOWS THIS. Each canon declares the SHAPE it serves, so nothing here needs a
    hand-written table of which rule is canon-backed — a table that would be a second home for the
    fact and would drift from the library it describes.
    """
    try:
        import yaml

        from sdk.grammar.resolve import FRAMEWORK

        f = FRAMEWORK.parent / "mac_vocabulary.yaml"
        if not f.exists():
            return {}
        out = {}
        for name, m in (
            (yaml.safe_load(f.read_text(encoding="utf-8")) or {})
            .get("canon", {})
            .get("members", {})
            or {}
        ).items():
            s = (m or {}).get("serves")
            if s:
                out.setdefault(str(s), []).append(name)
        return out
    except Exception:
        return {}


def _shape_of(rule_id: str) -> str:
    """`<concept>.exclusion.no_evidence` -> `exclusion_no_evidence`, the form `serves` uses."""
    parts = str(rule_id or "").split(".")
    return "_".join(parts[1:]) if len(parts) > 1 else ""


def check_instruction_compliance(obj: dict) -> tuple[list, list]:
    """(corrections_applied, blocking_failures) for one authored concept.

    Corrections are deterministic and stated. Failures are things only a re-author can fix.
    """
    corrections, failures = [], []
    if not isinstance(obj, dict):
        return corrections, failures

    md = obj.get("metadata")
    if isinstance(md, dict) and str(md.get("confidence", "")).strip().upper() == "C":
        md["confidence"] = "I"
        # THE REASON IS REPORTED, NOT WRITTEN AS AN `x-` KEY. This wrote
        # `metadata.x-confidence-downgraded`, and CONFORMANCE.md §2 prohibits that outright: "`x-` keys
        # are PROHIBITED. An `x-` key is a conformance error wherever it appears, diagnosed MAC012" —
        # `ConceptFile.metadata` is `additionalProperties: false` with no legal place for a note, so
        # nine concepts came out unable to compile, every one of them stamped by this function.
        #
        # §2 also records why it is not a nuance to document: the framework "was teaching, at its most
        # effective surface, the one declaration two other mechanisms refuse", and its own remedy is
        # "the model says it in prose or does not say it". The correction below IS that prose — it is
        # returned to the caller and printed at write time — and the artifact already carries the fact
        # in `confidence: I` beside `provenance: harvested`. A key nothing may check adds nothing.
        corrections.append(
            "metadata.confidence C -> I: a model may not certify its own output. C is CONFORMANCE §1's "
            "L3, 'an SME has ratified the meaning', which a generator cannot assert about its own "
            "guess — it would read as a ratified fact to anyone who did not check.")

    # A RULE MAC HAS A CANON FOR MUST BIND, NOT BE RETOLD IN PROSE.
    #
    # Measured on acme2: 13 concepts each wrote their own copy of ONE refusal law — 13 distinct `when`
    # wordings, 13 `then`, 12 `never`. Every copy individually well-formed, so no gate saw anything.
    # One of them (`market`) ended up with a BARE `then`: no refusal message and no "never guess",
    # so it could not produce the answer the other twelve promise. That defect was documented in the
    # canon library's own docstring months before anything blocked on it.
    #
    # A rule that supplies PARAMETERS cannot have a bare clause: the clause is rendered, not typed.
    # This is the same move that removed authored `additivity` — declare the input, derive the output.
    shapes = _canon_shapes()
    for r in (obj.get("contract") or {}).get("rules") or []:
        if not isinstance(r, dict):
            continue
        canons = shapes.get(_shape_of(r.get("id", "")))
        if canons and not r.get("realized_by"):
            failures.append(
                f"rule {r.get('id')!r} has a canon ({' or '.join('mac.canon.' + c for c in canons)}) "
                f"and writes its clauses as prose instead of binding to it. Supply "
                f"`realized_by: {{udf: mac.canon.<name>, params: {{...}}}}` — the clauses are RENDERED "
                f"from the canon, so they cannot come out bare or drift from the other concepts "
                f"stating the same law."
            )

    # A ROLE MUST EXIST FOR EVERY MEANINGFUL COLUMN — AND THE MAP FORM IS WHERE IT NOW LIVES.
    #
    # This demanded a `field_roles` block unconditionally, and iterating the MAP form yields its KEYS,
    # so a correctly-authored concept looked like 13 bare column names with no roles and was refused as
    # noncompliant. That made this the THIRD place the superseded standard was enforced — after the
    # schema (`columns` was `type: array`, so the map was a conformance error) and the prompt (which
    # taught the flat list). Three enforcements of the old form is the full explanation of ColumnSpec's
    # "21 concepts, 0 using the standard": the standard could not be written, taught, or accepted.
    gr = obj.get("grounding")
    if isinstance(gr, dict):
        flat, mapped, unroled = [], 0, []
        for src in gr.get("sources") or []:
            if not isinstance(src, dict):
                continue
            cols = src.get("columns")
            if isinstance(cols, dict):
                mapped += len(cols)
                unroled += [n for n, body in cols.items()
                            if isinstance(body, dict) and not body.get("role")]
            else:
                flat += [c for c in (cols or []) if isinstance(c, str)]
        roles = gr.get("field_roles")
        if mapped and isinstance(roles, dict) and roles:
            failures.append(
                f"grounding declares columns as a MAP ({mapped} column(s)) AND a `field_roles` block. "
                f"That is one fact with two homes: the roles are PROJECTED from the map, so the two can "
                f"drift and the projection keeps whichever the file declared explicitly. Delete "
                f"`field_roles`."
            )
        if flat and not (isinstance(roles, dict) and roles):
            failures.append(
                f"grounding.sources[].columns is a flat list of {len(flat)} name(s) and there is no "
                f"`field_roles` block, so nothing says what any column IS. Prefer the MAP form — "
                f"`columns: {{<name>: {{role: ...}}}}` — which puts each column's facts on the column."
            )
    return corrections, failures


def process(
    name: str,
    schema_md: str,
    ctx_dir: Path | None,
    terms: list[str],
    exemplar: str,
    *,
    model: str,
    effort: str,
    region: str,
    thinking_budget: int | None = None,
    cache=None,
) -> dict:
    """Author + validate + autofix one concept. Returns a status dict (JSON-safe)."""
    context = grep_context(ctx_dir, terms)
    try:
        yaml_text = author_concept(
            name,
            schema_md,
            context,
            exemplar,
            model=model,
            effort=effort,
            region=region,
            thinking_budget=thinking_budget,
            cache=cache,
        )
    except Exception as e:
        return {
            "name": name,
            "status": "error",
            "detail": f"author failed: {type(e).__name__}: {e}",
        }
    try:
        obj = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return {"name": name, "status": "invalid_yaml", "detail": str(e)[:200], "yaml": yaml_text}
    errs = _errors(obj)
    fixes = []
    if errs:
        fixes = _autofix(obj)
        errs = _errors(obj)
    # Compliance runs AFTER autofix: autofix makes the object schema-legal, this asks whether the
    # model actually did what it was told. A concept failing it is `noncompliant` and therefore not
    # in PERSISTABLE — it never reaches disk, which is the whole point of catching it here rather
    # than as a diagnostic days later.
    corrections, failures = check_instruction_compliance(obj)
    # ONE corrective retry. A compliance failure is something only a re-author can fix, and the model
    # is not told what it got wrong unless we tell it — so a silent give-up here would report a
    # deficiency the pipeline could have repaired for one extra call. Measured need: field_roles is
    # absent on 22 of 22 acme2 concepts despite SYS_PROMPT requiring it three times.
    retried = False
    if failures:
        retried = True
        try:
            yaml_text2 = author_concept(
                name,
                schema_md,
                context,
                exemplar,
                model=model,
                effort=effort,
                region=region,
                thinking_budget=thinking_budget,
                cache=cache,
                corrective="\n".join(f"- {f}" for f in failures),
            )
            obj2 = yaml.safe_load(yaml_text2)
            errs2 = _errors(obj2)
            fixes2 = _autofix(obj2) if errs2 else []
            errs2 = _errors(obj2) if errs2 else errs2
            corr2, fail2 = check_instruction_compliance(obj2)
            if not errs2 and not fail2:  # the retry fixed it — take it
                obj, errs, fixes = obj2, errs2, list(fixes2) + corr2
                corrections, failures = [], []
        except Exception as e:
            failures = [*list(failures), f"corrective retry failed: {type(e).__name__}: {e}"]
    fixes = list(fixes) + corrections
    status = "invalid" if errs else "noncompliant" if failures else "fixed" if fixes else "valid"
    return {
        "name": name,
        "status": status,
        "rules": len(((obj or {}).get("contract") or {}).get("rules") or []),
        "fixes": fixes,
        "compliance_failures": failures,
        "retried": retried,
        "errors": [
            f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message[:160]}" for e in errs[:8]
        ],
        "obj": obj,
        "yaml": yaml.safe_dump(obj, sort_keys=False, allow_unicode=True),
    }
