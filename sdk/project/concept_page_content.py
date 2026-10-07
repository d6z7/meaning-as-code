"""The concept page's CONTENT — what a concept page SAYS, with no format in the name.

WHY THIS IS NOT IN `mac_okf`. That module is named for a FORMAT: it projects a MAC object into an
OKF-compliant page, and the operator's ruling on the name is that it "cannot be used for other
purposes". Measured when this was split, `mac_okf.py` held thirteen rendering functions and only
FOUR of them were about OKF — `frontmatter`, `split_frontmatter`, `lock_hash` and the frontmatter
surface dict. The other NINE are the page's own sections and the lookups behind them: the Fields
table's descriptions, types and join column, the Relationships panel, the Details block, the Axes
block and the fold law it reads. Not one of them knows, or needs to know, what format carries the
result.

That stopped being a tidiness point the day the console began rendering the concept Page tab LIVE
through `tools/project_concept_page.py`: the page a reader actually sees was being authored by
"the MAC->OKF projector", so every consumer that is not OKF had to import the OKF module to ask
what a concept page says. This module is that answer. Its consumers today are the OKF projection
(`sdk/project/mac_okf.py`) and the live page seam; the next projection of the same content — HTML,
JSON, a console component — reads it here rather than growing a second author.

ONE AUTHOR STILL, AND THAT IS THE POINT. Nothing here was rewritten: every function below is the
byte-for-byte text that stood in `mac_okf.py`, and the 17 concept pages of the bundle this was
measured on render IDENTICALLY before and after the move. Two calls are what a caller needs —
`page_inputs`, the whole-bundle context (it IS the Relationships panel and the Fields table), and
`concept_sections`, one concept's page below the frontmatter. A caller that assembled either a
second time would be the SECOND AUTHOR this split exists to prevent, not to create.

WHAT STAYED BEHIND, and why each of the four is genuinely OKF: `frontmatter` and
`split_frontmatter` write and read OKF's YAML head; `lock_hash` digests the typed object that
OKF's `rules.lock` signs; and the surface dict (`type: Entity`, `resource: table://...`,
`rule_pages: [...]`) is the OKF catalog vocabulary itself. This module renders none of them, and
MUST NOT import the module that does — the dependency runs one way, projector -> content, so that
a format can be added without touching what the page says.
"""

from __future__ import annotations

from pathlib import Path

import yaml

#: THE FOLD-AGNOSTIC VOCABULARY READER. `mac_vocabulary.yaml` may nest its dotted blocks
#: (`concept: column: measure_type:`) or spell them flat; every lookup here indexes them by their
#: DOTTED identity, and `tools/mac_vocab.flatten` is the one converter between the two.
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2] / 'tools'))
import mac_vocab as _mv  # noqa: E402

#: THE ONE READER OF A COLUMN'S DECLARATION, for the same reason. The column standard moved on
#: 2026-10-07 and every per-column lookup below read the PRE-MOVE flat keys. MEASURED on
#: `sdk/authoring/exemplars/bundle` before the repoint, over the 35 columns of its four concepts:
#: role 0 of 35, identity 0 of 35, measure 0 of 35, and the `## Axes` section empty on 4 of 4
#: concepts — while the bundle declares 4 identity tuples, 4 aggregate columns and 22 axes. Nothing
#: failed; the page simply said "nothing is declared" 105 times. `mac_project.column_identity` owns
#: the identity read and the retired `part` -> `composite` spelling.
import mac_project as _P  # noqa: E402


#: THE FIVE ROLE NAMES ARE DERIVED NOW, NOT AUTHORED — and this page is one of the readers that has
#: to derive them. `role:` was retired from the column on 2026-10-07 in favour of the `roles:` MAP
#: (one fact, several uses: a join key you also group by is both, which 21 of contoso5's 112 columns
#: are and the scalar could not say). The Fields table's `role` column is declared in
#: `guardrails/unfiled.yaml#delivers.concept_page.shape#fields_table_columns` and the frozen document
#: `tests/golden/concept_page/calendar_day.md` shows what it holds (`key`, `dimension`,
#: `housekeeping`), so the column stays and the reader derives it.
#:
#: THE PRECEDENCE IS NOT INVENTED HERE. It is mac-runtime's `ontology/models.py#ColumnSpec.role`,
#: whose own docstring records the measurement that fixed it: 112 of 112 contoso5 columns reproduced,
#: and the `identity == canonical and axis` branch is what took it from 109 to 112. That module is
#: NOT importable from this repo (`import mac_runtime` -> ModuleNotFoundError, which is why
#: check_canon_implemented REFUSES rather than guesses), and `tools/mac_project` exports no role
#: derivation, so this is a second copy of a one-line law with nowhere better to live. Verified
#: against the frozen goldens: it reproduces all 10 `role` cells of net_revenue, all 10 of product
#: and all 7 of calendar_day.
#: `_derived_role` WAS HERE and is a second home for a one-line law, which is what this whole
#: change removes. It lives in `tools/mac_project.column_role` now, beside `column_identity`, and
#: `tests/test_column_roundtrip.py` pins it against mac-platform's `ColumnSpec.role` whenever the
#: platform is beside this repo.
def _derived_role(roles: dict) -> str:
    return _P.column_role({"roles": roles})


from sdk.project import layout as _layout_reader


def _edge_joins(concepts_dir: Path, concepts: list) -> dict:
    """{concept.name: {"out":[{title,on,join_rule}], "in":[...]}} projected from ontology/edges.yaml —
    the authoritative concept->concept join source (replaces the old prose-grep). out = this concept
    references others; in = others reference this concept."""
    name_title, name_stem = {}, {}
    for nm, _p, obj, _r in concepts:
        con = obj.get("concept") or {}
        cn = con.get("name") or nm
        name_title[cn] = con.get("label") or cn
        name_stem[cn] = nm  # the .md file stem (for building relative links)
    ep = Path(concepts_dir).parent / "edges.yaml"
    edges = ((yaml.safe_load(ep.read_text()) or {}).get("edges") or []) if ep.exists() else []

    def _cols(jr):  # "relA.from_col = relB.to_col" -> (from_col, to_col)
        try:
            lhs, rhs = [s.strip() for s in str(jr).split("=", 1)]
            return lhs.split(".")[-1], rhs.split(".")[-1]
        except Exception:
            return None, None

    res: dict = {}
    for e in edges:
        epr = e.get("endpoints") or {}
        fn = (epr.get("from") or {}).get("concept")
        tn = (epr.get("to") or {}).get("concept")
        if fn not in name_title or tn not in name_title:
            continue
        fc, tc = _cols(e.get("join_rule"))
        jr = e.get("join_rule")
        # A BUSINESS EDGE HAS NO `join_rule`, AND THAT IS NOT AN ABSENCE OF INFORMATION.
        # Measured: of 17 declared edges, 5 carry a `join_rule` and 12 do not — because both
        # concepts ground on the SAME relation, so there are not two relations to join and a
        # predicate there would be an invented self-join. Reading the column only out of
        # `join_rule` therefore dropped 11 of 17 edges from the Fields table, and the operator saw
        # a `CurrencyCode` row with an empty `joins →` while `order_line__denominated_in__currency`
        # sat declared in edges.yaml.
        #
        # The column such an edge carries is in `realized_by`, in one of two shapes:
        #   'rel.Column'                     — the attribute both concepts read
        #   'rel.KeyCol -> rel.ValueCol'     — a key to the value it carries; the FROM side is the key
        level = str(e.get("level") or "").strip() or None
        if not fc and not tc:
            rb = str(e.get("realized_by") or "")
            if rb:
                lhs, _, rhs = rb.partition("->")
                fc = lhs.strip().split(".")[-1].strip() or None
                tc = (rhs.strip() or lhs.strip()).split(".")[-1].strip() or None
        res.setdefault(fn, {"out": [], "in": []})["out"].append(
            {"title": name_title[tn], "stem": name_stem[tn], "on": fc, "join_rule": jr, "level": level}
        )
        res.setdefault(tn, {"out": [], "in": []})["in"].append(
            {"title": name_title[fn], "stem": name_stem[fn], "on": tc, "join_rule": jr, "level": level}
        )
    for k in res:
        res[k]["out"].sort(key=lambda x: (x["title"], x.get("on") or ""))
        res[k]["in"].sort(key=lambda x: (x["title"], x.get("on") or ""))
    return res


def _column_descriptions(data_dir: Path, errors: list | None = None) -> dict:
    """{relation-bare / dataset-stem -> {column: {"description", "type"}}} from the data layer.

    READ `description` OR `notes`, AND CARRY THE TYPE, because reading one key that nothing writes
    renders a blank that LOOKS like an absent declaration and is really a missed lookup. Measured on
    a live bundle when this was found: of 167 descriptor columns, `description` was present on **0**
    and the prose that existed sat in `notes` on 35 — so every description cell in every concept
    page was blank, 117 of 117 rows, while the text was on disk the whole time. `description` stays
    FIRST because the schema declares it and a bundle that fills it means it; `notes` is the
    fallback, not a synonym.

    `type` is carried for the same reason it belongs on the page at all: it is declared on 167 of
    167 columns and the Fields table never showed it, so a reader learned a column's ROLE and where
    it was GROUNDED but never what it IS.

    A FILE THAT WILL NOT PARSE IS REPORTED, NOT DROPPED. `errors` is an out-list: when a caller
    passes one, every descriptor this function could not read is appended to it as
    `{path, error}` with the path relative to the bundle root. The `except` below used to
    `continue` in silence, and that silence was measured — `tools/check_seam_contract.py` corrupted
    each traced input of the concept-page seam in turn and 8 of 17 changed the payload NOT AT ALL,
    because a quarter of the Fields table can vanish here without anything saying so. The read site
    is the one place that KNOWS, so it is the one place that reports; what to do about it is the
    caller's (the page seam refuses, being document mode — SEAM_CONTRACT.md §5). The default of
    `None` keeps every existing caller's behaviour byte-identical, so this is additive: `build`
    still projects what it can, and now has the fact available to act on when projection resumes.
    """
    out: dict = {}
    for sub in ("datasets", "sources"):
        for p in sorted((data_dir / sub).glob("*.yaml")) if (data_dir / sub).exists() else []:
            try:
                d = yaml.safe_load(p.read_text()) or {}
            except Exception as e:  # noqa: BLE001 — a fact to report, not to raise
                if errors is not None:
                    try:
                        rel = p.relative_to(data_dir.parent).as_posix()
                    except ValueError:
                        rel = p.name
                    errors.append({"path": rel, "error": f"{type(e).__name__}: {e}"})
                continue
            rel = (d.get("table") or {}).get("name") or p.stem
            cols = {
                c["name"]: {
                    "description": str(c.get("description") or c.get("notes") or "").strip(),
                    "type": str(c.get("type") or "").strip(),
                }
                for c in (d.get("columns") or [])
                if c.get("name")
            }
            out.setdefault(rel, {}).update(cols)
            out.setdefault(p.stem, {}).update(cols)
    return out


def _merged_col_meta(col_desc: dict, obj: dict, stem: str, rel_bare: str | None) -> dict:
    """One {column -> {description, type}} map covering EVERY relation the concept grounds on.

    The Fields table lists the union of all sources' columns, so its metadata must be looked up the
    same way. Sources are merged in REVERSE declared order and the primary relation last, so on a
    column name carried by two relations the FIRST-declared source wins — matching the precedence
    `_grounding_fields` already uses when it orders the rows.
    """
    merged: dict = {}
    srcs = (obj.get("grounding") or {}).get("sources") or []
    keys = [str((s or {}).get("relation") or "").split(".")[-1] for s in srcs if isinstance(s, dict)]
    for k in reversed([k for k in keys if k]):
        merged.update(col_desc.get(k) or {})
    merged.update(col_desc.get(rel_bare) or col_desc.get(stem) or {})
    return merged


def _property_docs(obj: dict) -> dict:
    """{casefolded column name -> the concept's own `properties[].doc`}.

    THE RICHEST PROSE IN THE BUNDLE IS HERE AND THE TABLE NEVER READ IT. A concept's `properties[]`
    carries a written `doc` per attribute — the transform that cleansed it, the measured null share,
    why a unique-looking column is deliberately not the key. The descriptor's `notes` is a sentence;
    this is the explanation.

    IT IS KEYED DIFFERENTLY, WHICH IS WHY IT WAS NEVER JOINED: `properties[].name` is camelCase
    (`productKey`) while the Fields table is keyed by the PHYSICAL column (`ProductKey`). Matching
    is by casefold, and that is a deliberate, narrow claim — same letters, different capitalisation.

    A COLLISION IS DROPPED, NOT GUESSED. If two properties casefold to one key the mapping is
    ambiguous, and attaching either doc to a column would state something the concept did not. Both
    are withheld so the cell reads as undeclared, which is true, instead of as wrong, which is worse.
    """
    docs: dict = {}
    collided: set = set()
    for prop in obj.get("properties") or []:
        if not isinstance(prop, dict):
            continue
        nm = str(prop.get("name") or "").strip()
        doc = str(prop.get("doc") or "").strip()
        if not nm or not doc:
            continue
        k = nm.casefold()
        if k in docs and docs[k] != doc:
            collided.add(k)
        docs[k] = doc
    for k in collided:
        docs.pop(k, None)
    return docs


def _concept_relation(obj: dict) -> str | None:
    srcs = (obj.get("grounding") or {}).get("sources") or []
    rel = srcs[0].get("relation") if srcs and isinstance(srcs[0], dict) else None
    return str(rel).split(".")[-1] if rel else None


def _relationships_panel(joins: dict, over) -> str:
    """Relationships at a glance — joins OUT (this concept references) + IN (referenced by), each with
    the join key, plus a grouping's leaf. Rendered from the projected edges, not scraped from prose."""
    out, inn = joins.get("out") or [], joins.get("in") or []
    if not out and not inn and not over:
        return ""
    lines = [
        "",
        f"*{len(out)} join(s) out · {len(inn)} in — click a concept to open it.*",
        "",
    ]
    if over:
        lines += [f"**Groups** → **{over}** — the leaf concept this rolls up.", ""]
    if out:
        lines += ["**Joins to** — this concept references:", ""]
        for j in out:
            lines.append(f"- [{j['title']}]({j['stem']}.md) — joined on `{j.get('on') or '?'}`")
        lines.append("")
    if inn:
        lines += ["**Referenced by** — these point at this concept:", ""]
        for j in inn:
            lines.append(f"- [{j['title']}]({j['stem']}.md) — on `{j.get('on') or '?'}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


#: The fold law, read from the framework registry rather than restated here. A measure's
#: `measure_type` crossed with an axis's `axis` yields an `aggregation_effect`, and the
#: registry declares that crossing itself — `measure_type.members.<Type>.additivity.<axis>`.
#: THIS FILE MUST NOT CARRY A SECOND COPY OF IT: the whole reason the page is worth rendering is
#: that it shows the law the runtime obeys, and a page quoting its own private table would be a
#: second home for the one fact, free to drift from the one the planner reads.
_VOCAB_PATH = Path(__file__).resolve().parents[2] / "mac_vocabulary.yaml"


def _fold_law() -> dict:
    """{measure_type term -> {axis term -> aggregation_effect term}}, from the registry.

    Returns {} when the registry cannot be read. An ABSENT law renders an em dash in the fold
    column — never a guessed SUM, because a wrong fold is the one error on this page that turns
    into a wrong number downstream."""
    try:
        #: FLATTENED: `mac_vocabulary.yaml` nests its dotted blocks (`concept: column: measure_type:`) and
        #: this reader indexes them by their dotted identity. `tools/mac_vocab.flatten` converts between the
        #: two — the one place that rule lives on this side of the estate.
        doc = _mv.flatten(yaml.safe_load(_VOCAB_PATH.read_text(encoding="utf-8")) or {})
    except Exception:  # noqa: BLE001 — a state to report as a dash, not to raise
        return {}
    out: dict = {}
    for term, body in ((doc.get("concept.column.measure_type") or {}).get("terms") or {}).items():
        add = (body or {}).get("additivity") or {}
        if isinstance(add, dict):
            out[str(term)] = {str(k): str(v) for k, v in add.items()}
    return out


def _axes_block(obj: dict) -> list[str]:
    """`## Axes` — the axes a measure may be folded along, and WHAT FOLD each one admits.

    WHY IT EXISTS. The concept declares its measure type and its axes, and the page said so only in
    prose: "the fold along each axis is resolved from measure_type x axis_kinds". That names a law
    governing every figure the measure produces and then shows the reader none of its inputs —
    measured on one bundle, 3 concepts declared a measure_type and 18 axis entries were declared, and
    not one of them reached the page.

    AND THEN THE INPUTS MOVED AND THE SECTION WENT BLANK. `concept.semantics.measure_type` and
    `.axis_kinds` are no longer the HOME of either fact: the type is `roles.aggregate.type` on the
    column that carries the number, and the axis is `roles.axis` on each column a question may slice
    by, because one concept can hold several quantities that fold by different laws (net_amount is a
    `flow`, net_price an `intensive`) and one concept-level slot could only misreport that. The two
    semantics keys survive in the schema as the runtime's PROJECTION of the columns, so a reader of a
    loaded object still sees them — but this reads the AUTHORED YAML, where no projection has
    happened. MEASURED on `sdk/authoring/exemplars/bundle`: the section rendered the layout's
    "nothing declared" sentence on 4 of 4 concepts, over 4 declared aggregate columns and 22 declared
    axes. `semantics.axis_kinds`'s own schema description says `DO NOT USE IT`.

    IT IS NOT A COLUMN OF THE FIELDS TABLE, and that is the substantive point. An axis is not a
    column of this concept — it is ANOTHER CONCEPT. A sales measure's columns are its price and
    its quantity; its axes are Brand, Country, Store and time. Forcing eight axes into a table of
    four columns would be the same category error as sampling a host relation instead of a
    concept's members.

    THE FOLD IS DERIVED, NEVER AUTHORED HERE. `measure_type x axis -> aggregation_effect` is
    declared in the framework registry; this reads it. An unknown type, an unknown axis kind or an
    unreadable registry all render an em dash, which says "not declared" — the same thing an em
    dash says everywhere else on this page."""
    grounding = obj.get("grounding") or {}
    #: THE COLUMNS, UNIONED OVER EVERY SOURCE, as the Fields table above already does — a concept
    #: grounded on two relations must not lose the second one's axes.
    cols: dict = {}
    for src in (grounding.get("sources") or []):
        if isinstance(src, dict) and isinstance(src.get("columns"), dict):
            for n, b in src["columns"].items():
                cols.setdefault(str(n), b if isinstance(b, dict) else {})
    def _roles(b):
        r = b.get("roles") if isinstance(b, dict) else None
        return r if isinstance(r, dict) else {}
    #: WHICH TYPE THE FOLD IS RESOLVED FOR. `aggregate.canonical: true` names the column that IS the
    #: concept's number, and that is the one the retired `semantics.measure_type` projected — so the
    #: canonical column's type reproduces the frozen `tests/golden/concept_page/net_revenue.md`
    #: exactly (`flow`, not the `intensive` of its unit price). With no canonical column and ONE type
    #: across the aggregates, that type is unambiguous. With no canonical column and SEVERAL types,
    #: the fold is genuinely several laws and this says so rather than picking by iteration order:
    #: a silently chosen type is a wrong fold, which is the one error on this page that becomes a
    #: wrong number downstream.
    aggregates = {n: _roles(b)["aggregate"] for n, b in cols.items()
                  if isinstance(_roles(b).get("aggregate"), dict)}
    canonical = [a for a in aggregates.values() if a.get("canonical")]
    types: list[str] = []
    for a in aggregates.values():
        t = str(a.get("type") or "").strip()
        if t and t not in types:
            types.append(t)
    mt = str((canonical[0] if canonical else {}).get("type") or "").strip()
    if not mt and len(types) == 1:
        mt = types[0]
    axes = {n: _roles(b)["axis"] for n, b in cols.items() if _roles(b).get("axis")}
    if not mt and not axes and not types:
        return []   # the CALLER emits the heading; an empty body becomes NOTHING_DECLARED
    law = _fold_law()
    short = mt.rsplit(".", 1)[-1] if mt else ""
    rows = []
    for axis, kind in sorted((axes or {}).items()):
        kind_s = str(kind or "")
        kshort = kind_s.rsplit(".", 1)[-1]
        eff = (law.get(short) or {}).get(kshort, "")
        rows.append((str(axis), kshort or "—", eff.rsplit(".", 1)[-1] if eff else "—"))
    out: list[str] = []
    if mt:
        out += [f"Measure type: `{short}` — `{mt}`.", ""]
    elif len(types) > 1:
        #: NO FOLD IS RENDERED HERE, DELIBERATELY. Several types and no `canonical: true` means the
        #: concept has not said which number it IS, so every cell of the fold column would be a
        #: guess. The types are NAMED with their columns, which is what a person needs to fix it.
        out += [
            "Several measure types are declared and none of their columns is marked "
            "`aggregate.canonical: true`, so there is no one type to resolve the fold against: "
            + ", ".join(
                f"`{n}` is `{str((a.get('type') or '')).rsplit('.', 1)[-1]}`"
                for n, a in aggregates.items()
            )
            + ". Mark the column the concept's number is `canonical` and the fold resolves.",
            "",
        ]
    if rows:
        out += ["| axis | axis kind | fold |", "|---|---|---|"]
        out += [f"| `{a}` | {k} | {f} |" for a, k, f in rows]
        out += [
            "",
            "_The fold is read from the framework registry "
            "(`measure_type.<type>.additivity.<axis kind>`), not declared on this concept. "
            "An em dash means the crossing is not declared there._",
            "",
        ]
    else:
        out += ["_No axis is declared for this measure._", ""]
    return out


def _details_block(obj: dict) -> list[str]:
    """A compact, structured header block — the small typed facts a reader (and an answering agent)
    need at a glance: version / schema_version / status / owner, what dissolves the concept, and
    governance. Rendered as a plain bullet list; only present fields appear, in a fixed order
    (deterministic — every value is authored, no timestamps/volatile fields).

    THE `Identity` ROW IS GONE BECAUSE ITS SOURCE IS. `concept.identity.kind` was read here and the
    whole `concept.identity` block was removed from mac.schema.json on 2026-10-05 (`concept` is
    `additionalProperties: false`, so a file carrying one now FAILS validation) — operator ruling:
    *"declare on concept level only what belongs to the concept level"*. Identity is a COLUMN fact and
    the Fields table's `identity` column states it per column, where it varies. This read measured 0
    of 4 concepts on `sdk/authoring/exemplars/bundle` — the Details block is 4 lines before and after
    — so nothing on the page changes; what is removed is a branch that could only ever fire on a file
    the grammar refuses, which is the kind of read that makes an empty page look like an empty bundle.
    The frozen `tests/golden/concept_page/calendar_day.md` still shows `- **Identity** — iso`, from a
    0.1.16 render; that golden is stale and is regenerated with `check_document_layout.py --accept`.
    """
    meta = obj.get("metadata") or {}
    contract = obj.get("contract") or {}
    gov = obj.get("governance") or {}
    rows: list[tuple[str, str]] = []
    if meta.get("version"):
        rows.append(("Version", str(meta["version"])))
    if meta.get("schema_version"):
        rows.append(("Schema version", str(meta["schema_version"])))
    if contract.get("dissolved_by"):
        rows.append(("Dissolved by", f"`{contract['dissolved_by']}`"))
    if gov.get("owner"):
        rows.append(("Governance owner", str(gov["owner"])))
    if gov.get("last_reviewed"):
        rows.append(("Last reviewed", str(gov["last_reviewed"])))
    return [f"- **{k}** — {v}" for k, v in rows]


#: EVERY SECTION, IN ORDER, ALWAYS PRESENT — READ, NOT TYPED, THROUGH ONE LOOKUP. The hand-rolled
#: loader that stood here read ONE topic file by name and was the second mechanism for one fact
#: (`knowledge.py` carried a Python tuple); `sdk/project/layout.py` is the reader for both.
LAYOUT = _layout_reader.layout("concept_page")

#: The headings, in order. Every one `required: always` — asserted by test_concept_page_layout.
PAGE_SECTIONS: tuple[str, ...] = LAYOUT.sections

#: What an empty section says, declared beside the sections so one sentence serves all of them.
NOTHING_DECLARED: str = LAYOUT.empty_section_says

#: The Fields table's columns — PER-COLUMN FACTS ONLY. `grounded in` was removed from here on the
#: operator's standing rule: "i dont want to have column for somehting that applies for the whole
#: object like grounded-in".
FIELDS_COLUMNS: tuple[str, ...] = LAYOUT.columns("fields_table_columns")


def _section(heading: str, body: list[str]) -> list[str]:
    """One section, ALWAYS emitted: its heading, then its body or the empty sentence."""
    return _layout_reader.section(heading, body, NOTHING_DECLARED)


def _measure_cell(measure: dict) -> str:
    """`flow · USD · canonical` — the measure family as one cell.

    ONE COLUMN PER FAMILY, not per leaf: `measure` declares `type`, `unit` and `canonical`, and three
    columns of which two are empty on 88 % of rows reads worse than one that is empty on 88 % of
    rows. `canonical` is shown as a word rather than `true`, because what it MEANS is "this is the
    number the concept IS" and a boolean says nothing about which.
    """
    if not isinstance(measure, dict) or not measure:
        return ""
    bits = [str(measure.get("type") or "").rsplit(".", 1)[-1], str(measure.get("unit") or "")]
    if measure.get("canonical"):
        bits.append("**canonical**")
    additivity = measure.get("additivity")
    if isinstance(additivity, dict) and additivity:
        bits.append(
            "additivity " + ", ".join(f"{k}={str(v).rsplit('.', 1)[-1]}" for k, v in additivity.items())
        )
    return " · ".join(b for b in bits if b)


def _rulings_cell(rulings: dict) -> str:
    """`label_of brand (legal) · sort desc` — the authored judgements as one cell.

    `register` IS NOT A SEPARATE RULING: it says WHICH of a thing's names a `label_of` column is, so
    it renders in that ruling's parenthesis. `evidence` likewise belongs to the prohibition it
    evidences -- a `never_axis` without its measurement is a preference, and the page shows them
    together or the reader cannot tell which it is.
    """
    if not isinstance(rulings, dict) or not rulings:
        return ""
    out: list[str] = []
    if rulings.get("label_of"):
        register = rulings.get("register")
        out.append(f"label_of `{rulings['label_of']}`" + (f" ({register})" if register else ""))
    if rulings.get("finer_than"):
        out.append(f"finer_than `{rulings['finer_than']}`")
    if rulings.get("scoped_by"):
        out.append(f"scoped_by `{rulings['scoped_by']}`")
    if rulings.get("sort"):
        out.append(f"sort {rulings['sort']}")
    if rulings.get("never_axis"):
        evidence = rulings.get("evidence")
        out.append(
            f"never_axis: {rulings['never_axis']}" + (f" ({evidence})" if evidence else "")
        )
    # ANY RULING THIS FUNCTION DOES NOT KNOW IS STILL SHOWN. A new term in
    # mac_vocabulary.yaml#concept.column.ruling would otherwise be declared, authored, read by the
    # planner and INVISIBLE on the page that exists to show it.
    known = {"label_of", "register", "finer_than", "scoped_by", "sort", "never_axis", "evidence"}
    out += [f"{k}: {v}" for k, v in rulings.items() if k not in known]
    return " · ".join(out)


def _ordered_by_relation(fields: list[dict], relations: list[str]) -> list[dict]:
    """``fields`` regrouped so every column of one relation is contiguous, relations in declared
    order. A column serving several relations is listed under the FIRST that declares it, so no row
    appears twice -- a duplicated row would double the footer's denominator and read as two columns.
    """
    out: list[dict] = []
    placed: set = set()
    for relation in relations:
        for f in fields:
            if f["column"] in placed:
                continue
            if any(rel == relation for rel, _ in f["sources"]):
                placed.add(f["column"])
                out.append(f)
    out += [f for f in fields if f["column"] not in placed]
    return out


def _source_key(source: dict) -> list[str]:
    """The columns that make ONE ROW of this source unique — the authored `key:`, else DERIVED.

    THE KEY IS A COLUMN FACT, and since 2026-10-02 the runtime derives it: `identity: canonical`, or
    every `identity: part` column in declaration order. Operator, on seeing both declared at once:
    "is this not redundancy? you define key by grounding and by the column". The `key:` list is the
    deprecated spelling and contoso5 no longer carries it -- so a page that read only `key:` lost
    the grain it used to show ("Grounded in `v_…_sales_line` — key `['order_key','line_number']`"
    became a bare relation name, and no Fields row was flagged `(key)`).

    THE SAME PRECEDENCE AS THE RUNTIME'S `parser._cell_key`, deliberately: authored first, derived
    second. A page that disagreed with the planner about the grain would be worse than a blank one.

    THE DERIVED HALF READ A RETIRED ADDRESS until 2026-10-07: the flat `identity:` beside `role:`,
    and `part` for what is now `composite`. Every source of the exemplar bundle carries an authored
    `key:` so this branch measured 0 there either way — the repoint is still the point, because the
    `key:` list is the DEPRECATED spelling and a bundle that has dropped it (contoso5 has) would have
    rendered a bare relation name under `## Grounded in` and no `(key)` anywhere. `column_identity`
    is the one reader of that fact and maps the old spelling.
    """
    key = source.get("key")
    if key:
        return [key] if isinstance(key, str) else list(key)
    columns = source.get("columns")
    if not isinstance(columns, dict):
        return []
    canonical = [n for n, b in columns.items() if _P.column_identity(b) == "canonical"]
    return canonical or [n for n, b in columns.items() if _P.column_identity(b) == "composite"]


def _grounding_fields(grounding: dict) -> list[dict]:
    """The UNION of grounding.sources[].columns and grounding.field_roles — so NO grounded column is
    dropped just because it lacks a field_role, and EVERY source (not just sources[0]) is represented.
    Stable order: each source's columns in declared order, then any field_roles-only column. Each entry
    carries the column's role (from field_roles) and the source relation(s) it belongs to, flagging the
    relation for which the column is the declared key (grounding.sources[].key)."""
    # THE ROLE IS ON THE COLUMN when the MAP form is used, and that is now the standard form.
    #
    # MEASURED 2026-10-02, reported by the operator: "the table on cocept page does not show the
    # role" -- every row of the Fields table rendered `—`. This read `field_roles` ONLY, which is
    # the LEGACY block form (`field_roles: {order_key: ...}` beside a flat list of column names).
    # A bundle on the column standard declares `columns: {order_key: {role: key, ...}}` and carries
    # no `field_roles:` block at all, so there was nothing to read and the column was blank for
    # every concept of every migrated bundle -- 17 of 17 on contoso5.
    #
    # The runtime's parser PROJECTS the map form onto `field_roles`, which is why the planner never
    # saw this; this tool reads the authored YAML, where the projection has not happened.
    #
    # AND THEN THE MAP MOVED AGAIN, 2026-10-07, AND THE TABLE WENT BLANK A SECOND TIME. The four
    # flags a column carries are now `roles` / `counts` / `register` / `rulings` and nothing else
    # (mac.schema.json makes the column spec `additionalProperties: false`), so `role:` is refused by
    # name and `identity:` / `axis:` / `measure:` are inside `roles:`. This read all four at the old
    # flat address. MEASURED on `sdk/authoring/exemplars/bundle`, 35 columns over four concepts:
    # role 0 of 35, identity 0 of 35, measure 0 of 35 — and `rulings` 5 of 35, which is the whole
    # tell, because `rulings` is the ONE family that did not move.
    fr = dict(grounding.get("field_roles") or {})
    srcs = grounding.get("sources") or []
    order: list[str] = []
    seen: set = set()
    src_of: dict = {}  # column -> [(relation_bare, is_key), ...]
    ident: dict = {}  # column -> its identity part, from the map form
    extra: dict = {}  # column -> {axis, measure, rulings} as declared
    for s in srcs:
        if not isinstance(s, dict):
            continue
        rel_bare = str(s.get("relation") or "").split(".")[-1]
        key = _source_key(s)
        columns = s.get("columns") or []
        if isinstance(columns, dict):
            for col, body in columns.items():
                if not isinstance(body, dict):
                    continue
                roles = body.get("roles") if isinstance(body.get("roles"), dict) else {}
                if _P.column_identity(body):
                    ident.setdefault(col, _P.column_identity(body))
                # EVERY OTHER PER-COLUMN FAMILY THE YAML DECLARES, kept whole so the renderer can
                # format them and this function stays a reader. `axis` and `aggregate` are roles —
                # uses a question may make of the column — while `rulings` and `register` are flags
                # of the column itself, which is why only the first two are looked up under `roles`.
                # `measure` IS `roles.aggregate`: the family was renamed with the move and
                # `_measure_cell` still reads `{type, unit, canonical, additivity}` out of it,
                # unchanged, because the body did not change — only its address.
                for family, value in (
                    ("axis", roles.get("axis")),
                    ("measure", roles.get("aggregate")),
                    ("rulings", body.get("rulings")),
                    ("register", body.get("register")),
                ):
                    if value is not None:
                        extra.setdefault(col, {}).setdefault(family, value)
                # THE ROLE IS DERIVED FROM `roles`, NOT READ. The scalar is gone; `_derived_role`
                # reproduces the five names from the map (see its comment for the 112-of-112
                # measurement that fixed the precedence). An authored `field_roles:` block still
                # WINS, because a bundle carrying both is half-migrated and that block is the half
                # being retired — the same precedence this function already used.
                if col not in fr and "roles" in body:
                    fr[col] = _derived_role(roles)
        for col in columns:
            if col not in seen:
                seen.add(col)
                order.append(col)
            src_of.setdefault(col, []).append((rel_bare, col in key))
    for col in fr:  # grounded-role column not listed under any source
        if col not in seen:
            seen.add(col)
            order.append(col)
    return [
        {
            "column": col,
            "role": str(fr[col]).split(".")[-1] if col in fr else "",
            # THE PART THIS COLUMN PLAYS IN THE CONCEPT'S IDENTITY -- canonical | composite |
            # reference (`part` was renamed `composite`; `column_identity` maps the old spelling).
            # A PER-COLUMN fact, and the one the grain is now derived from, so it replaces the
            # `grounded in` column that used to sit here.
            "identity": str(ident.get(col, "")).split(".")[-1],
            "axis": str((extra.get(col) or {}).get("axis") or "").rsplit(".", 1)[-1],
            "measure": (extra.get(col) or {}).get("measure") or {},
            "rulings": (extra.get(col) or {}).get("rulings") or {},
            # THE VALUE SET THIS COLUMN CARRIES. Shown as the file's BARE NAME: the path is
            # bundle-relative and identical in every row's prefix, which is the whole-object
            # repetition the `grounded in` column was removed for.
            "register": str((extra.get(col) or {}).get("register") or ""),
            "sources": src_of.get(col, []),
        }
        for col in order
    ]


def concept_body(
    obj: dict,
    src_path: Path,
    name: str,
    bundle: dict[str, str],
    joins: dict | None = None,
    col_desc: dict | None = None,
    source_table: tuple[str, ...] = (),
) -> str:
    """ONE concept page's BODY — every section below the frontmatter, as markdown.

    This is `mac_okf.concept_to_md`'s second half, moved without a character of its rendering
    changed; `concept_to_md` is now the OKF surface plus a call to this. The sections it renders
    (Details, How to answer, Grounded in, Grain, Fields, Axes, Relationships, Source of record)
    say the same thing whatever format carries them, which is why they live here and the
    frontmatter does not.
    """
    joins = joins or {"out": [], "in": []}
    col_desc = col_desc or {}
    c = obj.get("concept", {})
    grounding = obj.get("grounding", {})
    srcs = grounding.get("sources") or []
    # ---- readable body ----
    parts = [
        c.get("definition", "").strip(),
        "",
    ]  # no body H1 — the read-view renders the frontmatter title
    parts += _section("Details", _details_block(obj))
    # HOW TO ANSWER — the concept's agent-facing playbook (contract.no_probe_guarantee), rendered
    # VERBATIM inside a fence so its numbered steps / SQL / semicolons survive untouched. The single
    # highest-value field for "present AND later answer questions" (the wiki /ask reads this same .md).
    npg = (obj.get("contract") or {}).get("no_probe_guarantee")
    parts += _section(
        "How to answer",
        [
            "*What an agent needs ONLY, to answer with this concept — no data probing.*",
            "",
            "```text",
            str(npg).rstrip("\n"),
            "```",
        ]
        if npg
        else [],
    )
    # GROUNDED IN — every source relation (not just sources[0]) + its declared key.
    ground_srcs = [s for s in srcs if isinstance(s, dict) and s.get("relation")]
    parts += _section(
        "Grounded in",
        [
            f"- `{g['relation']}`"
            + (f" — key `{_source_key(g)}`" if _source_key(g) else "")
            for g in ground_srcs
        ],
    )
    # GRAIN — WHAT ONE ROW IS, derived from the columns that identify it.
    #
    # `grounding.grain` WAS A PROSE RESTATEMENT AND IT IS GONE. The key removed from mac.schema.json
    # on 2026-10-07 (`grounding` is `additionalProperties: false`, so a file carrying it no longer
    # validates) because the grain IS the identity: the column marked `canonical`, or the set marked
    # `composite`. The guardrails say so where the Fields table's `identity` column is declared —
    # "which is what the grain is derived from". This section read the retired key and so was the
    # layout's "nothing declared" sentence on 4 of 4 concepts of `sdk/authoring/exemplars/bundle`,
    # every one of which declares its identity. `_source_key` is the derivation, and it is the SAME
    # one `## Grounded in` above and the runtime's `parser._cell_key` use, so the page cannot
    # disagree with the planner about the grain.
    #
    # IT IS NOT A REPEAT OF `## Grounded in`. That section says WHERE the rows come from and what
    # keys them; this says what ONE of them IS, which is the concept's own label against those
    # columns — the sentence the retired prose carried ("one row per calendar day (date_day)").
    grain_label = c.get("label") or c.get("name") or name
    grain: list[str] = []
    for g in ground_srcs:
        gk = _source_key(g)
        if not gk:
            continue
        where = f" in `{g['relation']}`" if len(ground_srcs) > 1 else ""
        grain.append(
            f"- One row{where} is one {grain_label}, identified by "
            + ", ".join(f"`{k}`" for k in gk)
            + "."
        )
    parts += _section("Grain", grain)
    fields = _grounding_fields(grounding)
    if fields:
        # each FK column links to the concept it joins (relative .md -> the viewer navigates it)
        # THE PLANE IS NAMED, BECAUSE A BUSINESS EDGE IS NOT A FOREIGN KEY. The operator ruled that
        # the physical layer and the business layer are two sets of edges and must read as two —
        # the graph canvas draws physical solid and business dashed for the same reason. A bare
        # link here would tell a reader the concepts are joined in the warehouse, which for 11 of
        # the 17 declared edges is false: they share an attribute on one relation.
        joins_by_col = {
            j["on"]: f"[{j['title']}]({j['stem']}.md)"
            + ("" if (j.get("level") or "physical") == "physical" else f" _({j['level']})_")
            for j in (joins.get("out") or [])
            if j.get("on")
        }
        # THE DESCRIPTION HAS THREE SOURCES AND THE TABLE READ NONE OF THEM PROPERLY.
        # Precedence, most specific first: the descriptor's `description` (the schema's own field),
        # then its `notes`, then the CONCEPT's own `properties[].doc` — which is the richest prose
        # in the bundle and was never joined at all because it is keyed in camelCase. An em dash
        # means NOTHING IS DECLARED, and it is the same marker `role` and `grounded in` already use,
        # so one glyph means one thing across the row.
        #
        # NO COLUMN FOR A WHOLE-OBJECT FACT. Operator, 2026-10-02, having said it several times
        # before: "i dont want to have column for somehting that applies for the whole object like
        # grounded-in". `grounded in` repeated the SAME relation on every row of a single-source
        # concept -- 10 of 10 rows reading `v_contoso5_sales_line` -- which is the relation the
        # `## Grounded in` section states once, above. Its slot now carries `identity`
        # (canonical | part | reference), which genuinely varies per column and is what the grain is
        # derived from. WHERE A CONCEPT IS M:N OVER RELATIONS the relation does vary, and the answer
        # is a sub-heading per relation below, never a repeated column.
        #
        # THIS IS NOT THE RULING BELOW. That one forbids dropping a column because it is EMPTY; this
        # column was dropped for being REDUNDANT, which is the opposite problem: it carried the same
        # fact N times instead of none.
        #
        # A BLANK IS NOT HIDDEN AND A COLUMN IS NEVER DROPPED FOR BEING EMPTY. Operator, on being
        # told an all-empty table might be collapsed into prose: "grid of blanks hints on the error
        # or incompletenes. it is much better then hiding it." They are right — a grid shows WHICH
        # column lacks WHICH fact; a sentence replaces that with a feeling. So the shape is
        # constant, and the footer COUNTS the emptiness instead, over its denominator, because an
        # unmeasured absence is the one thing this estate refuses to ship.
        prop_docs = _property_docs(obj)
        filled = {
            "type": 0,
            "role": 0,
            "identity": 0,
            "measure": 0,
            "rulings": 0,
            "register": 0,
            "description": 0,
            "joins →": 0,
        }
        # ONE RELATION PER SUB-HEADING WHERE A CONCEPT HAS SEVERAL, so the relation is stated once
        # per group instead of once per row. Measured: contoso4's `Currency` grounds
        # `v_contoso4_sales` (where `CurrencyCode` IS its identity) and
        # `v_contoso4_currencyexchange` (where the same members appear as FromCurrency/ToCurrency) --
        # there the relation genuinely varies per column, and a heading says so without a column
        # that is pure repetition on every single-source concept.
        relations = [r for r, _ in dict.fromkeys(
            (rel, None) for f in fields for rel, _ in f["sources"]
        )]
        grouped = len(relations) > 1
        parts += ["## Fields", ""]
        if not grouped:
            parts += [
                "| " + " | ".join(FIELDS_COLUMNS) + " |",
                "|" + "---|" * len(FIELDS_COLUMNS),
            ]
        current = None
        for f in _ordered_by_relation(fields, relations) if grouped else fields:
            if grouped:
                rel = (f["sources"] or [(None, False)])[0][0]
                if rel != current:
                    current = rel
                    parts += [
                        f"### `{rel}`" if rel else "### (no declared relation)",
                        "",
                        "| " + " | ".join(FIELDS_COLUMNS) + " |",
                        "|" + "---|" * len(FIELDS_COLUMNS),
                    ]
            col = f["column"]
            meta_col = col_desc.get(col) or {}
            if not isinstance(meta_col, dict):  # a caller passing the old {col: str} shape
                meta_col = {"description": str(meta_col or ""), "type": ""}
            desc = (
                meta_col.get("description") or prop_docs.get(col.casefold()) or ""
            ).replace("|", "\\|").replace("\n", " ").strip()
            ctype = str(meta_col.get("type") or "").strip()
            joined = joins_by_col.get(col, "")
            if desc:
                filled["description"] += 1
            if ctype:
                filled["type"] += 1
            if f["role"]:
                filled["role"] += 1
            if joined:
                filled["joins →"] += 1
            if f["identity"]:
                filled["identity"] += 1
            measure_cell = _measure_cell(f["measure"])
            rulings_cell = _rulings_cell(f["rulings"])
            if measure_cell:
                filled["measure"] += 1
            if rulings_cell:
                filled["rulings"] += 1
            register_cell = (
                f"`{f['register'].rsplit('/', 1)[-1]}`" if f["register"] else ""
            )
            if register_cell:
                filled["register"] += 1
            parts.append(
                f"| `{col}` | {ctype or '—'} | {f['role'] or '—'} | {f['identity'] or '—'} "
                f"| {measure_cell or '—'} | {rulings_cell or '—'} "
                f"| {register_cell or '—'} | {desc or '—'} | {joined or '—'} |"
            )
        parts.append("")
        n = len(fields)
        parts += [
            "_Declared per column, over "
            + str(n)
            + " column"
            + ("" if n == 1 else "s")
            + ": "
            + " · ".join(f"{k} {v} of {n}" for k, v in filled.items())
            + ". An em dash is a column for which nothing is declared._",
            "",
        ]
    if not fields:
        # A CONCEPT THAT GROUNDS NO COLUMNS still gets the section. The branch above builds the
        # table in place, so this is its else: without it, Fields was the one section that could
        # still vanish, and a value-domain concept (an enumeration with no relation) rendered a
        # page with seven headings where every other concept had eight.
        parts += _section("Fields", [])
    parts += _section("Axes", _axes_block(obj))
    # Rules are NOT repeated on the Page — they have their own "Rules" view tab now.
    over = (obj.get("members") or {}).get("over") if isinstance(obj.get("members"), dict) else None
    rel = _relationships_panel(joins, over)
    parts += _section("Relationships", rel.splitlines() if rel else [])
    parts += _section(
        "Source of record",
        [
            f"- Full MAC concept: `{src_path.name}` — open the **YAML** tab for the complete "
            f"typed definition.",
            *source_table,
        ],
    )
    return "\n".join(parts)


def page_body(name: str, path: Path, obj: dict, inputs: dict, *, source_table: tuple[str, ...] = ()) -> str:
    """ONE concept's page body — the SURFACE `delivers.concept_page.shape` governs, nothing else.

    Split out of `concept_sections` so the freeze checker renders what the declaration rules
    (`tools/check_document_layout.py`) and `concept_sections` adds the `## Data` pointer on top.
    Not a character of the rendering changed in the split.
    """
    cname = (obj.get("concept") or {}).get("name") or name
    rel_bare = _concept_relation(obj) or name
    return concept_body(
        obj,
        path,
        name,
        inputs["bundle"],
        inputs["rel_joins"].get(cname, {"out": [], "in": []}),
        # EVERY SOURCE, NOT JUST THE FIRST. `_grounding_fields` deliberately unions the columns
        # of ALL `grounding.sources`, so a lookup keyed on one relation leaves every column of
        # the second source unresolved — measured when the type column landed: 6 of 117 rows
        # blank, and all 6 were a second source (a concept grounded in both a customer and a
        # store relation). The first relation still wins a name collision, which is the same
        # precedence the rest of this builder uses.
        _merged_col_meta(inputs["col_desc"], obj, name, rel_bare),
        source_table=source_table,
    )


def concept_sections(name: str, path: Path, obj: dict, inputs: dict) -> str:
    """ONE concept's page below the frontmatter. `mac_okf.concept_page` is this with the OKF head in
    front, and the live page seam reaches the same text through it. Writes nothing.

    THE SOURCE-TABLE POINTER GOES IN `Source of record`, not a section of its own. It used to be
    appended as `## Data`, which made the page NINE headings on a bundle with a data plane (3 of 17
    concepts on contoso5) against the eight `delivers.concept_page.shape` declares — a conditional
    section of exactly the kind the always-present ruling removed, carrying one pointer line next to
    a section that already holds one.
    """
    source_table: tuple[str, ...] = ()
    if (inputs["data_sources"] / f"{name}.yaml").exists():
        source_table = (f"- Source table: [{name}](../../data/sources/{name}.md)",)
    return page_body(name, path, obj, inputs, source_table=source_table)


def documents(root: Path) -> dict[str, str]:
    """`{concept stem: its page body}` for a whole bundle — the renderer the guardrails declare.

    The enumeration is `mac_okf.load_concepts`'s, repeated here rather than imported: the
    dependency runs projector -> content (see this module's docstring), never back.
    """
    src = Path(root) / "ontology" / "concepts"
    concepts = []
    for path in sorted(src.rglob("*.yaml")) if src.is_dir() else []:
        raw = path.read_text(encoding="utf-8")
        obj = yaml.safe_load(raw)
        if isinstance(obj, dict) and "concept" in obj:
            concepts.append((path.stem, path, obj, raw))
    inputs = page_inputs(src, concepts)
    return {name: page_body(name, path, obj, inputs) for name, path, obj, _raw in concepts}


def page_inputs(src: Path, concepts: list) -> dict:
    """The WHOLE-BUNDLE context every concept page needs, computed once.

    EXTRACTED FROM `build`, VERBATIM, AND FOR ONE REASON. The console renders the concept Page tab
    LIVE now (tools/project_concept_page.py -> the console's /concept-page route), because the
    `.md` under `ontology/concepts/` is a BUILD ARTIFACT: a page is exactly as old as the last
    projection run and says nothing about it — the same defect already repaired for the object
    index and the edge index, one surface over. A live page therefore needs the page builder
    callable for ONE concept without writing anything.

    Re-deriving this context in the caller would make a SECOND AUTHOR for what a page says, which
    is the defect class this estate spends its time removing: the four arguments below are not
    plumbing, they are content — `rel_joins` IS the Relationships panel, `col_desc` IS the Fields
    table, and a caller that assembled them slightly differently would render a DIFFERENT page
    from the one `build` writes while both claimed to be the page. So `build` and the live seam
    call these two functions and nothing else.

    Nothing about what a page SAYS changed here: `build`'s loop body moved into `concept_sections`
    above (and `mac_okf.concept_page`, which puts the OKF head on it), and the 17 pages of the
    bundle this was measured on are byte-identical before and after the extraction.

    `col_desc_unparsed` is the one addition, and it says nothing new about a page — it names the
    descriptor files the Fields table's metadata could NOT be read from, which `_column_descriptions`
    used to drop in silence. A caller that serves a document refuses on it (SEAM_CONTRACT.md §5);
    `build` is unaffected, because the list is empty whenever every descriptor parses.
    """
    col_desc_unparsed: list = []
    col_desc = _column_descriptions(src.parent.parent / "data", errors=col_desc_unparsed)
    return {
        "bundle": {
            name: (obj.get("concept", {}).get("label") or obj.get("concept", {}).get("name") or name)
            for name, _p, obj, _r in concepts
        },
        # sibling data plane (per-source MAC project)
        "data_sources": src.parent.parent / "data" / "sources",
        # concept.name -> {out,in} from edges.yaml
        "rel_joins": _edge_joins(src, concepts),
        # relation/stem -> {col: description}
        "col_desc": col_desc,
        # the descriptors that would not parse: [{path, error}], root-relative. Empty on a clean
        # bundle — a swallowed read is a silent lie about what the Fields table is missing.
        "col_desc_unparsed": col_desc_unparsed,
    }
