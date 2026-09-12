#!/usr/bin/env python3
"""MAC authoring — the harvest's per-table brain when the target is MAC (not OKF).

`author_concept()` turns one table's raw schema (+ SME context + an exemplar concept)
into a MAC concept YAML via one Bedrock call; `process()` authors → parses → validates
against mac.schema.json → applies deterministic closed-vocabulary autofixes → re-validates,
returning a status the harvest streams to the console. Same loop proven in author_spike.py,
packaged for reuse by console_api's MAC harvest mode.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from jsonschema import validators as jsv

_ROOT = Path(__file__).resolve().parent.parent
from sdk.grammar.resolve import load_schema as _load_schema  # ONE schema home

SCHEMA = _load_schema()
_CF = dict(SCHEMA["$defs"]["ConceptFile"])
_CF["$defs"] = SCHEMA["$defs"]
_CONCEPT_VALIDATOR = jsv.validator_for(SCHEMA)(_CF)

# Autofix philosophy: the validator NAMES the legal enum, so don't hand-transcribe
# vocabularies (that's how the misses happened). For any enum error we first reconcile
# spelling generically (underscore/hyphen/case) against the schema's real values, then
# fall back to this small SEMANTIC map for genuine near-misses (not mere spelling).
_SEMANTIC = {
    "surrogate": "code",
    "primary_key": "code",
    "pk": "code",
    "id": "code",
    "natural_key": "code",
    "compound": "composite",
    "namespace": "namespace_code",
    "foreign_key": "fk_name",
    "fk": "fk_name",
    "I": "P",
    "Q": "P",  # rule confidence scale C/P/R
    "semi_additive": "non-additive",
    "semi-additive": "non-additive",  # only additive/non-additive exist
}

SYS_PROMPT = """You are a MAC ontology author. MAC models a data source as CONCEPT files (YAML). Author ONE concept for the business notion named below.

A CONCEPT IS A BUSINESS NOTION, NOT A TABLE. The mapping between concepts and relations is M:N and you are given every relation this notion needs:
- ONE concept may ground on SEVERAL relations — list each under `grounding.sources`, which is a LIST.
- ONE relation may serve SEVERAL concepts; grounding on a relation does not consume it.
- A relation may back NO concept at all: a pure mapping/bridge table is not a notion, it dissolves into a rule or an edge on the notions it relates.
- A notion may exist with NO backing table of its own (a perspective, a plan stage, a rollup) — ground it on the relation that carries its discriminating column.

Shape of a concept file:
- metadata: {concept, source, version, schema_version: '0.1.13', status: draft, owner, confidence}   # metadata.confidence ∈ C|I|Q (C=confirmed, I=inferred, Q=needs-SME)
- concept: {name, label, class, identity?, definition}   # class is EXACTLY one of: entity | event | measure | enumeration | reference | grouping ; identity.kind ∈ iso|code|namespace_code|fk_name|composite|resolved_axis|sme_pending
- grounding: {sources: [{relation, key, columns: [...]}], field_roles: {<col>: fpl.field_role.key|dimension|attribute|measure}, grain: "one row per ..."}
- contract: {no_probe_guarantee?, rules: [{id, subject, kind: mac.rule_kind.resolution|guarantee|exclusion|ambiguity, confidence, scope: FPL, binds: [<cols>], when, then, never}]}   # a RULE's confidence ∈ C|P|R (C=confirmed, P=proposed, R=rejected) — this is NOT the metadata C/I/Q scale; default P when unconfirmed
- governance: {owner, last_reviewed}

CHOOSE THE CLASS FIRST, and INCLUDE ITS REQUIRED BLOCK — this is mandatory and schema-enforced:
- a CODE / LOOKUP table (a small set of coded values — e.g. body type, fuel type, brand indicator, registration type) → class: enumeration, and you MUST add a TOP-LEVEL `values:` block:
      values:
        closure: closed | open | unknown
        items:
          - {code: <code>, label: <human label>, meaning: <what it means>}
  Fill items from the CONTEXT / lookup tables when present; if the value set is not in the inputs, use closure: unknown and include only codes you can justify (never invent values).
- a FACT / KPI / measure table (numeric values you aggregate) → class: measure, and you MUST add a `concept.semantics:` block:
      semantics:
        purpose: <one line>
        measure_type: mac.MeasureType.<Flow|Stock|Intensive|Precomputed|Target>
        axis_kinds: {<axis>: mac.axis_kind.<time|categorical>, ...}   # one entry per aggregation axis
  DO NOT WRITE AN `additivity:` BLOCK. How the measure folds along each axis is DERIVED from
  (measure_type x axis_kind) by the law in mac_vocabulary.yaml. Writing it out would state the same
  fact twice — and because you would be authoring both the premise and the conclusion, the two can
  drift: a concept once declared `Target` and wrote `geography: additive`, which the law forbids, and
  a value anchor summed that measure across models for weeks on the strength of it.
  CHOOSE THE TYPE CAREFULLY — it is the whole claim:
    Flow        accrues per period and accumulates (units sold in a period)         -> sums over time
    Stock       a level read at a point in time (inventory on hand)                 -> read at period end
    Intensive   meaningful only as an average (a duration, an age, a rate)          -> never summed
    Precomputed exists ONLY at the grains it was computed for; locate the row and read it
    Target      a planning target, not an observed quantity                         -> not foldable
- an EVENT table (rows that track a lifecycle / state transitions) → class: event, and you MUST add a TOP-LEVEL `lifecycle:` block using ONLY these keys (any other key is schema-rejected):
      lifecycle:
        phases: [<phase name>, ...]        # optional siblings: phase_sequence, states, boundary, note — and NOTHING else
- a ROLLUP / GROUPING table (rows that GROUP or ROLL UP other rows — e.g. a region→countries map, a market footprint, a membership list) → class: grouping, and you MUST add a TOP-LEVEL `members:` OBJECT (NOT a list) shaped exactly as:
      members:
        over: <the LEAF concept this rolls up — e.g. Country, Car Model>   # REQUIRED — the grouped concept
        member_source:
          kind: rule        # 'rule' = membership computed via a FK / transitive walk; 'enumerated' = explicit named sets
          rule: <one line: how membership is computed, e.g. "region groups countries via fpl_brand_country_code">
  `members:` is a TOP-LEVEL OBJECT with a REQUIRED `over:` key (sibling of `concept:` / `grounding:` / `contract:`), NEVER a bare list and NEVER nested under `concept:`. (Placement reference: `semantics` is nested UNDER `concept:`; but `values`, `members`, and `lifecycle` are TOP-LEVEL siblings of `concept:`.)
- a plain dimension / identifier table (keys + attributes, not a closed code list) → class: reference or entity (no extra required block).

Authoring rules:
- Ground on the REAL table and columns provided. NEVER invent a column that isn't in the schema.
- Give every meaningful column a field_role: keys are identity/join columns; dimensions are filterable; attributes are display-only; measures are additive numeric facts.
- identity.canonical_key is a SINGLE column name (a string). If the grain is a COMPOSITE of several columns (typical for fact / KPI tables), set identity.kind: composite and OMIT canonical_key entirely — NEVER set canonical_key to a list.
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
  `confusable` matters most: an empty Gross Stock answered with Ideal Stock is worse than no answer,
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
# the same wrong shape. Measured: gaps/fpl is exactly 20 concepts from 20 datasets. A per-table unit of
# work cannot express a notion spanning two relations, cannot let one relation serve two notions, and
# cannot decline to make a concept for a bridge table.
#
# OPERATOR RULING 2026-08-18: the concept/relation relationship is M:N. Not negotiable.
#
# So the model sees the WHOLE relation inventory ONCE and proposes the notions. Only then is each
# notion authored, with every relation it named. Declining a relation is a first-class outcome and
# must carry a reason, so "no concept here" is a recorded judgement rather than an omission.
PLAN_PROMPT = """You are a MAC ontology architect. You are given EVERY produced relation of one data source, plus SME context. Propose the BUSINESS NOTIONS this source should expose as MAC concepts.

A concept is a business notion, NOT a table. The mapping is M:N:
- one notion may need SEVERAL relations;
- one relation may serve SEVERAL notions;
- a pure mapping/bridge table backs NO notion — it dissolves into a rule or an edge;
- A NOTION OFTEN HAS NO TABLE OF ITS OWN. This is the most commonly MISSED case, so work it deliberately: for every FACT relation, walk its columns and ask of each dimension/discriminator column whether it names a thing the business talks about. If it does, that is a NOTION, and it grounds on the fact relation that carries the column.
  Worked example of the shape: a fact relation with columns `role`, `plan_level`, `brand_letter`, `country_code` carries FOUR notions — a Perspective (which view of the world the row is stated from), a PlanStage (how firm the number is), a Brand and a Country — none of which has a table. A register in the VALUE REGISTERS section naming that column's members is strong evidence the notion exists.
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
        "## GROUNDING RELATIONS — schema + provenance for EVERY relation this notion needs\n\n"
        "(one concept may ground on several; list each under grounding.sources)\n\n"
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
# MEASURED on gaps/fpl2, 2026-08-18. SYS_PROMPT asks for two things it does not get:
#
#   "Give every meaningful column a field_role"      -> field_roles present on 0 of 22 concepts
#   "metadata.confidence in C|I|Q ... Q=needs-SME"   -> 17 of 22 stamped C, none reviewed
#
# The instructions are THERE. The JSON Schema cannot see them: `field_roles` is optional and `C` is a
# legal enum member, so every one of those concepts validates. A prompt whose compliance is never
# checked degrades silently, and downstream nothing can tell a measured claim from a guess — which is
# how `ideal_stock` shipped `additive` as CONFIRMED and produced a wrong anchor.
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
    """`dtc.exclusion.no_evidence` -> `exclusion_no_evidence`, the form `serves` uses."""
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
        md["x-confidence-downgraded"] = (
            "authored by a model and not yet ratified: C asserts an SME confirmed this meaning "
            "(CONFORMANCE.md L3), which a model cannot do for its own output"
        )
        corrections.append("metadata.confidence C -> I (a model may not certify its own output)")

    # A RULE MAC HAS A CANON FOR MUST BIND, NOT BE RETOLD IN PROSE.
    #
    # Measured on fpl2: 13 concepts each wrote their own copy of ONE refusal law — 13 distinct `when`
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

    gr = obj.get("grounding")
    if isinstance(gr, dict):
        cols = []
        for s in gr.get("sources") or []:
            if isinstance(s, dict):
                cols += [c for c in (s.get("columns") or []) if isinstance(c, str)]
        roles = gr.get("field_roles")
        if cols and not (isinstance(roles, dict) and roles):
            failures.append(
                f"grounding.field_roles is empty while the concept grounds on {len(cols)} column(s). "
                f"SYS_PROMPT requires a role for every meaningful column; without it nothing binds a "
                f"rule's columns to an analytical role."
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
    # absent on 22 of 22 fpl2 concepts despite SYS_PROMPT requiring it three times.
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
