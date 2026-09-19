#!/usr/bin/env python3
"""Generate the ONTOLOGY suite from the ontology, as the sanity suite is generated from the profile.

Operator: *"inspect if you can autogenerate test series also for ontology as you generated for data.
then manually generated must be only few of them."*

Yes — and the two suites are generated in OPPOSITE directions, which is the whole point of MAC having
two test kinds (mac_vocabulary.yaml#test_kind):

    data sanity   GROUND_TRUTH.  Measures the world. Must NOT be rendered from the declaration,
                  because its purpose is to DISAGREE when the declaration has gone stale.
    ontology      CONFORMANCE.   Every asserted value is RENDERED from the declaration at run time.
                  A typed literal IS the defect: it freezes a claim the ontology has since changed.

So this generator never writes a number. It writes `@n:concept:perspective.values.items`, and
run_properties resolves it against the concept at run time. Edit the concept, and every test that
reads it moves with it — which is exactly what a conformance test is for.

── WHAT IT CAN GENERATE, and the ceiling ───────────────────────────────────────────────────────
Measured on <dataset> (22 concepts, 30 rules):

    ALREADY ENFORCED OFFLINE, so deliberately NOT generated — 58 assertions. Column existence for
    rules[].binds, grounding.columns and properties[] is a SHAPE (rule-binds-grounded,
    field-roles-grounded), checked without touching the warehouse. Re-asserting it in SQL would move
    a fast structural gate into a slow expensive plane and call it coverage.

    GENERATED — the declarations that can only be settled against data:
        identity      concept.identity.canonical_key names every row of THE CONCEPT'S OWN
                      population — see `member_population`, which is where "its own" is decided
        key_grain     grounding.sources[].key identifies exactly one row
        closure       a CLOSED value set holds no value the data does not
        presence      every declared value actually occurs (a declaration ahead of its data)

    NOT GENERATABLE — 22 of 30 rules state their directive only in `then:` PROSE. You cannot render
    SQL from a sentence. Only the 8 carrying `realized_by`/`enforced_by` are machine-readable.

THAT LAST NUMBER IS THE REAL FINDING. The route to "only a few hand-written" is not a cleverer
generator; it is giving more rules a machine-readable form. Every rule that gains a `realized_by`
becomes testable for free, and until it does, its test must be written and maintained by a person.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import pathlib
import sqlite3
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P       # noqa: E402

GEN = "mac_generate_ontology_tests.py/7"

# concepts whose declared value set matches no grounded column — reported, never guessed
UNMATCHED: list[tuple[str, str, str]] = []
# concepts whose declared key is NOT the relation's grain — a finding, not a test
NOT_GRAIN: list[tuple[str, str, str]] = []
# concepts whose canonical_key is not a column of the relation they ground on
NO_IDENT_COLUMN: list[tuple[str, str, str, str]] = []
# concepts whose grounding key names a column the relation does not have
NO_KEY_COLUMN: list[tuple[str, str, str, str]] = []
# concepts whose identity assertion would have a FIXED VERDICT once read over their own members
IDENT_FIXED: list[tuple[str, str, str, str]] = []


def column_types(root: pathlib.Path, rel: str) -> dict[str, str]:
    """`{column -> declared type}` for a relation, from the ONE descriptor that claims it.

    This was answered THREE TIMES inside `for_concept` — an inner `relation_columns` for the
    key_grain guard, an inline loop for the identity guard, and `value_column`'s own read — each
    walking ("datasets", "sources") in the same order and each throwing the type away. Collapsed
    here because the narrowing below needs the TYPE, not just the name, and a fourth private reader
    of the same file is how the first three came to disagree about nothing in particular.

    Empty when no descriptor claims the relation. An empty map is NOT "no such column": every
    caller must treat it as "not established", which is why the identity guard already writes
    `if have and ident not in have` rather than `if ident not in have`."""
    stem = rel.split(".")[-1]
    for dd in ("datasets", "sources"):
        f0 = root / "data" / dd / f"{stem}.yaml"
        if not f0.is_file():
            continue
        try:
            doc = yaml.safe_load(f0.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {}
        return {str(x.get("name")): str(x.get("type") or "") for x in (doc.get("columns") or [])}
    return {}


def member_population(gnd: dict, ident: str,
                      coltypes: dict[str, str]) -> tuple[str | None, str, str | None]:
    """WHICH ROWS ARE THIS CONCEPT'S OWN — the population every identity assertion is read over.

    THE DEFECT THIS EXISTS FOR, measured on a live two-plane bundle: a `class: enumeration` concept
    whose own note says it is "a value set held in the <host> dimension, with no relation of its
    own" got an identity test over the WHOLE host relation — 59 of 74 rows carried no value and it
    failed. The host relation's rows are versions of the HOST, two concepts co-inhabit it, and the
    concept had ALREADY declared which rows are its members: `grounding.discriminator`. The
    generator ignored it. Operator ruling, asked whether the test or the concept was wrong: *"The
    test — fix the generator."*

    AND THE RED WAS THE CHEAP HALF. 8 of that bundle's 17 concepts declare BOTH a canonical_key and
    a discriminator; the ignored discriminator produced ONE honest red and SEVEN greens that were
    green only because those discriminator columns happen to carry zero empties. Seven tests proved
    a property no concept had asserted — "every row of the shared host relation is nameable by this
    concept" — which is the estate's false-green defect class, not a coverage win.

    The same recognition already lives in the key_grain family: NOT_GRAIN skips a uniqueness test
    where "the concept is a DISCRIMINATOR there, not the row identity". That guard SKIPS; this one
    NARROWS, because an identity assertion over the concept's own members is still worth making.

    Returns `(where, basis, refusal)`:
        where     the WHERE clause the population needs, or None for the whole relation
        basis     the declaration the population was read from, for the statement prose
        refusal   None, or why a narrowed assertion here would have a FIXED VERDICT

    ── THE TWO CASES THE NARROWING MUST KEEP APART ─────────────────────────────────────────────
    NOT A MEMBER, so not a defect. The discriminator is absent (SQL NULL) — the concept states
    that such a row is not one of its members, and nothing this test asserts applies to it. These
    are the 59 rows, and dropping them is the fix.

    A MEMBER THAT CANNOT BE NAMED, so still a defect. The discriminator marks the row as a member
    and the canonical key is not a usable name. `count(*) - count(x)` sees only SQL NULL, so a
    PRESENT-BUT-BLANK key is counted as a member and asserted about by nothing — and blank is not
    hypothetical: the same host dimension's transform conformed 58 empty strings and 1 NULL into
    one served NULL, so a regression there puts blanks back among the members. The emitted SQL
    therefore counts `NULL OR blank-after-trim`, which is the half of the assertion that survives
    the narrowing.

    ── AND WHERE NOTHING SURVIVES IT, REFUSE ───────────────────────────────────────────────────
    In 8 of those 8 concepts the discriminator IS the canonical key. Membership is then "the key is
    present", so the NULL half is true by construction and only the BLANK half can fail — live on a
    text column, IMPOSSIBLE on a numeric one. Emitting it there would replace seven wrong-reason
    greens with greens that cannot go red, which is the same defect wearing the fix's clothes. So a
    numeric (or type-unknown) key that is its own discriminator gets NO test and a reported finding,
    the way this generator already refuses a test it cannot make honestly."""
    vf = gnd.get("value_filter")
    if isinstance(vf, dict):
        vf = vf.get("sql") or vf.get("expression")
    vf = " ".join(str(vf or "").split())
    if vf:
        # A filter is the concept's OWN membership predicate and is independent of the key, so both
        # halves of the assertion bite and there is nothing to refuse. Parenthesised because a
        # filter written as `a OR b` under an added AND would otherwise change meaning silently.
        return f"({vf})", f"grounding.value_filter: {vf}", None
    disc = str(gnd.get("discriminator") or "").strip()
    if not disc:
        return None, "", None
    where, basis = f'"{disc}" IS NOT NULL', f"grounding.discriminator: {disc}"
    if disc != ident:
        return where, basis, None
    t = str(coltypes.get(ident) or "").lower()
    if any(k in t for k in ("char", "text", "string")):
        return where, basis, None
    return where, basis, (
        f"`{disc}` IS the canonical key, so membership already asserts the key is present"
        + (f", and the descriptor declares it {t} — no blank spelling of absence can occur, "
           f"leaving nothing that could fail" if t
           else ", and no descriptor declares its type — that a blank can occur is not established"))


def identity_property(name: str, rel: str, ident: str,
                      where: str | None, basis: str) -> dict:
    """The identity family's `statement`, `sql` and `assertion`, in the two population shapes.

    Pure on purpose: `--self-test` drives it with fixtures and EXECUTES the SQL it returns, because
    "a member row with a blank key must still be counted" is a claim about SQL semantics and a
    claim about SQL semantics is not proven by reading the string."""
    if where is None:
        # UNCHANGED, DELIBERATELY AND BYTE FOR BYTE. A concept that declares neither a
        # discriminator nor a value_filter grounds the whole relation, so "every row of <rel>" is
        # exactly what it claims and the prose is already true. A fix that quietly restates a
        # passing test's meaning is worse than the defect it was sent to fix.
        return {
            "statement":
                f"Prove {name}'s canonical key is present on every row of {rel}\n"
                f"QUESTION. Can every row of this relation be named by the key the concept "
                f"identifies itself with?\n"
                f"ANSWER. The concept identifies itself by `{ident}`.\n"
                f"RISK. A row whose identity is empty cannot be addressed, compared or joined — it "
                f"silently drops out of every answer that needs it.\n---\n"
                f"HOW. Counts empties in the canonical key. GENERATED by {GEN}.\n"
                f"WHERE. {rel}.{ident}.",
            "sql": f'SELECT count(*) - count("{ident}") AS rows_with_no_identity,\n'
                   f"       count(*) AS rows_examined\nFROM {rel}",
            "assertion": {"type": "must_be_zero", "columns": ["rows_with_no_identity"]},
        }
    # NARROWED — and the prose changes with the SQL. The three sentences this replaces were
    # "present on every row of <rel>", "can every row of this relation be named" and a RISK that
    # the row "silently drops out of every answer that needs it". All three become FALSE the moment
    # the population is the concept's members: the last one doubly so for a concept that documents
    # its NULL as SERVED and filters nothing by it. A statement that outlives its SQL is how a test
    # comes to be read as evidence for something it never measured.
    return {
        "statement":
            f"Prove every row {name} claims as its own in {rel} carries a usable canonical key\n"
            f"QUESTION. Of the rows this concept declares to be ITS OWN members, can each one be "
            f"named by the key the concept identifies itself with?\n"
            f"ANSWER. The concept identifies itself by `{ident}` and marks its members by "
            f"{basis}.\n"
            f"RISK. A member whose key is absent or blank is a member this concept cannot name: it "
            f"still counts toward the host relation's total while answering to no value of the "
            f"set, so the per-member figures and the total disagree and neither looks wrong. The "
            f"rows the membership declaration EXCLUDES are not asserted about here and are not a "
            f"defect — the concept says such a row is not one of its members.\n---\n"
            f"HOW. Counts, among THIS CONCEPT'S OWN members, the rows whose canonical key is NULL "
            f"or blank after trimming. The population is narrowed by the concept's own membership "
            f"declaration ({basis}) rather than taken as the whole relation, because the relation "
            f"is a HOST that several concepts co-inhabit. Blank counts as absent on purpose: "
            f"narrowing a population must not become a second way to spell an absence that escapes "
            f"the count. Both denominators are returned — the members examined and the host "
            f"relation's rows — so the narrowing is visible in the run record instead of being "
            f"taken on trust. GENERATED by {GEN}.\n"
            f"WHERE. {rel}.{ident}, over the rows where {where}.",
        "sql": f'SELECT count(*) - count(NULLIF(TRIM(CAST("{ident}" AS VARCHAR)), \'\'))\n'
               f"           AS member_rows_with_no_identity,\n"
               f"       count(*) AS member_rows_examined,\n"
               f"       (SELECT count(*) FROM {rel}) AS host_relation_rows\n"
               f"FROM {rel}\nWHERE {where}",
        "assertion": {"type": "must_be_zero", "columns": ["member_rows_with_no_identity"]},
    }


def measured_key(root: pathlib.Path, rel: str) -> list[str]:
    """The relation's MEASURED grain, from the measurement plane. Empty when nothing measured it."""
    f = root / "data" / "profiles" / f"{rel.split('.')[-1]}.yaml"
    if not f.exists():
        return []
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return list((d.get("identity_evidence") or {}).get("key") or [])


def value_column(root: pathlib.Path, rel: str, declared: list[str], ident: str) -> tuple[str | None, str]:
    """WHICH column actually holds this concept's value set — matched, not assumed.

    The first run assumed `identity.canonical_key`. On package_type that produced a test comparing
    `<source>_raw_package_type_id` (int) against 'Gift Box' — because the concept identifies itself by
    the ID and enumerates the LABEL column. Both facts are true; nothing had ever compared them.

    So the column is found by matching the declared set against each grounded column's measured
    domain. A concept whose values match NO column is not given a wrong test — it is reported, which
    is the more useful outcome."""
    stem = rel.split(".")[-1]
    for d in ("datasets", "sources"):
        f = root / "data" / d / f"{stem}.yaml"
        if not f.exists():
            continue
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        best, score = None, 0.0
        want = {str(x) for x in declared}
        for c in doc.get("columns") or []:
            dom = c.get("values")
            if not dom:
                continue
            have = {str(x) for x in dom}
            overlap = len(want & have) / max(len(want), 1)
            if overlap > score:
                best, score = str(c["name"]), overlap
        if best and score >= 0.8:
            note = ("" if best == ident else
                    f" NOTE: the concept identifies itself by `{ident}` but its value set lives on "
                    f"`{best}` — matched at {score*100:.0f} %, not assumed.")
            return best, note
        return None, (f"no grounded column of {rel} carries this concept's declared value set "
                      f"(best match {score*100:.0f} %)")
    return None, f"no descriptor for {stem}"


def _rel(src: dict, root: pathlib.Path | None = None) -> str:
    """The relation a grounding source names, QUALIFIED BY ITS SCHEMA.

    A concept declares the relation as it thinks of it, which is often the bare stem — measured:
    `ontology/concepts/catalog/brand.yaml` declares `relation: dim_<x>_product`. Returned
    verbatim, that reached DuckDB unqualified and 13 of a live two-plane bundle's 33 generated
    properties died as

        Catalog Error: Table with name dim_<x>_product does not exist!
        Did you mean "<served>.dim_<x>_product"?

    THE QUALIFICATION WAS ALREADY IN THE BUNDLE, IN TWO PLACES, AND NEITHER WAS READ:
    `data/profiles/<stem>.yaml#relation` carries `<served>.dim_<x>_product`, and
    `data/datasets/<stem>.yaml#table.schema` carries `<served>`. `mac_generate_sanity.py`
    goes through the descriptor and emits `FROM <served>.…`, which is why its 67 properties
    examined 67 and errored 0 against the same engine in the same session.

    So this resolves the stem the same way its sibling does. `run_suite.py --schema` cannot
    substitute: that flag runs `CREATE SCHEMA IF NOT EXISTS` / `ATTACH DATABASE ':memory:'` to seed
    FIXTURES — it is not a search path. Fixing it here is one generator edit; the alternative is 17
    concept-file edits in a plane two other builds are rewriting.

    An already-qualified relation is returned untouched, and a stem no descriptor claims is returned
    bare — an unqualified name that fails loudly in the catalog is a better outcome than a schema
    invented from a neighbouring relation."""
    rel = str(src.get("relation") or "")
    if not rel or "." in rel or root is None:
        return rel
    prof = root / "data" / "profiles" / f"{rel}.yaml"
    if prof.is_file():
        try:
            qualified = str((yaml.safe_load(prof.read_text(encoding="utf-8")) or {})
                            .get("relation") or "")
        except (OSError, yaml.YAMLError):
            qualified = ""
        if qualified.split(".")[-1] == rel and "." in qualified:
            return qualified
    for dd in ("datasets", "sources"):
        f0 = root / "data" / dd / f"{rel}.yaml"
        if not f0.is_file():
            continue
        try:
            doc = yaml.safe_load(f0.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        schema = str(((doc.get("table") or {}).get("schema")) or "")
        if schema:
            return f"{schema}.{rel}"
    return rel


def for_concept(path: pathlib.Path, root: pathlib.Path) -> list[dict]:
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    c = d.get("concept") or {}
    name = str(c.get("name") or path.stem)
    stem = path.stem
    gnd = d.get("grounding") or {}
    srcs = (gnd.get("sources") or [])

    def relation_columns(rel: str) -> set[str]:
        return set(column_types(root, rel))
    out: list[dict] = []
    src_note = f"ontology/concepts/{path.name}"

    def prop(fam, sid, statement, sql, assertion):
        out.append({
            "id": sid, "family": fam, "test_kind": "mac.test_kind.conformance",
            "severity": "major", "source": src_note, "validates": [name],
            "statement": statement, "assertion": assertion, "tolerance": 0, "sql": sql,
        })

    for i, s in enumerate(srcs):
        rel = _rel(s, root)
        if not rel:
            continue
        key = s.get("key")
        keys = [key] if isinstance(key, str) else list(key or ())
        # A key is a ROW key only where the concept IS the grain of the relation. On a FACT relation
        # an enumeration or reference concept keys on a DISCRIMINATOR — `perspective` keys on `role`,
        # 6 values over 800 Mio rows — and asserting uniqueness there fails by construction. The
        # first cut generated 16 such tests. The measured grain settles it: compare the concept's
        # declared key against identity_evidence.key rather than guessing from the relation name.
        # THE SAME GUARD THE IDENTITY FAMILY GOT, and it needed to be in both places. /5 checked
        # only canonical_key, so a territory-key test still shipped and died as COLUMN_NOT_FOUND on
        # `<source>_group_market_code` — dim_market_register spells it `group_code`. A guard
        # applied to one of two families is a guard that looks present and is not.
        have = relation_columns(rel)
        absent = [k for k in keys if have and k not in have]
        if absent:
            NO_KEY_COLUMN.append((name, rel, ", ".join(absent),
                                  ", ".join(sorted(x for x in have
                                                   if absent[0].split("_")[-1] in x)) or "nothing similar"))
            keys = []
        measured = measured_key(root, rel)
        if keys and measured and set(keys) != set(measured):
            NOT_GRAIN.append((name, rel, f"declares [{', '.join(keys)}] · measured grain "
                                         f"[{', '.join(measured)}]"))
            keys = []
        if keys:
            # RENDER the key from the concept, do not type it. Until v/4 this wrote the columns as
            # literals while the STATEMENT BELOW claimed they were read at run time and warned that
            # "a typed key would go on passing after the concept changed". The prose described the
            # right design and the SQL did the opposite — the same shape of defect as x-grain's
            # VERIFIED. The substitution needed list indices to reach grounding.sources.0.key; they
            # did not exist, which is how the shortcut got taken.
            cols = f"@cols:concept:{stem}.grounding.sources.{i}.key"
            prop("key_grain", f"O-{stem.upper()}-KEY{i or ''}",
                 f"Prove {name}'s declared key still identifies one row of {rel}\n"
                 f"QUESTION. Does the key this concept says it is identified by actually pick out a "
                 f"single row?\n"
                 f"ANSWER. The concept declares {len(keys)} column(s).\n"
                 f"RISK. If the key repeats, every join through this concept fans out and every "
                 f"figure downstream is multiplied without anything looking wrong.\n---\n"
                 f"HOW. Groups {rel} by the DECLARED key and counts the groups holding more than one "
                 f"row. The column list is READ from the concept at run time "
                 f"(@cols:concept:{stem}.grounding.sources.{i}.key), never typed here — a typed key would go "
                 f"on passing after the concept changed. GENERATED by {GEN}.\n"
                 f"WHERE. {rel}.",
                 f"SELECT count(*) AS keys_holding_more_than_one_row\n"
                 f"FROM (SELECT {cols} FROM {rel} GROUP BY {cols} HAVING count(*) > 1)",
                 {"type": "must_be_zero", "columns": ["keys_holding_more_than_one_row"]})

    ident = (c.get("identity") or {}).get("canonical_key")
    # DO NOT TEST A COLUMN THE RELATION DOES NOT HAVE. Three generated tests died as Athena
    # COLUMN_NOT_FOUND: Brand identifies itself by `brand_code` where the relation carries
    # `<source>_brand_code`; Market by `<source>_scoped_market_code`, which dim_market_register has
    # no column resembling; Territory declares no canonical_key at all and got a test regardless.
    # Those are three real modelling gaps — reported, not thrown at the warehouse to discover.
    if ident and srcs:
        have = relation_columns(_rel(srcs[0]))
        if have and ident not in have:
            NO_IDENT_COLUMN.append((name, _rel(srcs[0], root), str(ident),
                                    ", ".join(sorted(x for x in have if ident.split("_")[-1] in x)) or "nothing similar"))
            ident = None
    elif srcs and not ident:
        NO_IDENT_COLUMN.append((name, _rel(srcs[0], root), "(none declared)", "-"))
    if ident and srcs:
        rel = _rel(srcs[0], root)
        if rel:
            # THE POPULATION IS A DECLARATION, NOT THE RELATION NAME. See `member_population`.
            where, basis, refusal = member_population(gnd, str(ident), column_types(root, rel))
            if refusal:
                IDENT_FIXED.append((name, rel, str(ident), refusal))
            else:
                spec = identity_property(name, rel, str(ident), where, basis)
                prop("identity", f"O-{stem.upper()}-IDENT",
                     spec["statement"], spec["sql"], spec["assertion"])

    v = d.get("values") or {}
    items = [i for i in (v.get("items") or []) if isinstance(i, dict) and i.get("code") is not None]
    if items and srcs and ident:
        rel = _rel(srcs[0], root)
        vcol, why = value_column(root, rel, [i["code"] for i in items], str(ident)) if rel else (None, "")
        if rel and not vcol:
            UNMATCHED.append((name, rel, why))
        if rel and vcol:
            ident = vcol
            if v.get("closure") == "closed":
                prop("closure", f"O-{stem.upper()}-CLOSURE",
                     f"Prove {rel} holds no {name} the concept has not declared\n"
                     f"QUESTION. The concept says this value set is CLOSED — is it?\n"
                     f"ANSWER. It declares @n:concept:{stem}.values.items values.\n"
                     f"RISK. A value outside a closed set is either a new business case nobody has "
                     f"modelled or a data defect, and both are invisible until asked for.\n---\n"
                     f"HOW. Counts distinct values in the data that the CONCEPT does not list. The "
                     f"list is rendered from the concept at run time, so editing the concept moves "
                     f"this test with it. GENERATED by {GEN}.\n"
                     f"WHERE. {rel}.{ident}.",
                     f'SELECT count(*) AS values_the_concept_does_not_declare,\n'
                     f"       @n:concept:{stem}.values.items AS values_declared\n"
                     f'FROM (SELECT DISTINCT CAST("{ident}" AS varchar) AS v FROM {rel})\n'
                     f"WHERE v NOT IN (@cols:concept:{stem}.values.items)",
                     {"type": "must_be_zero", "columns": ["values_the_concept_does_not_declare"]})
            prop("presence", f"O-{stem.upper()}-PRESENCE",
                 f"Prove every {name} the concept declares actually occurs\n"
                 f"QUESTION. Does the model describe values the data no longer has?\n"
                 f"ANSWER. The concept declares @n:concept:{stem}.values.items values.\n"
                 f"RISK. A declared value with no data behind it is a promise the source cannot "
                 f"keep — a question about it returns nothing, which reads as 'none happened' "
                 f"rather than 'this was never real'.\n---\n"
                 f"HOW. Counts declared values absent from the relation, rendered from the concept. "
                 f"GENERATED by {GEN}.\n"
                 f"WHERE. {rel}.{ident}.",
                 f'SELECT @n:concept:{stem}.values.items - count(*) AS declared_values_with_no_data,\n'
                 f"       @n:concept:{stem}.values.items AS values_declared,\n"
                 f"       count(*) AS values_declared_and_present\n"
                 f'FROM (SELECT DISTINCT CAST("{ident}" AS varchar) AS v FROM {rel}\n'
                 f'      WHERE CAST("{ident}" AS varchar) IN (@cols:concept:{stem}.values.items))',
                 {"type": "must_be_zero", "columns": ["declared_values_with_no_data"]})
    return out


def _run(sql: str, fixture: list[tuple]) -> dict:
    """Execute a generated identity query against a 4-row fixture in the STANDARD LIBRARY.

    sqlite3 is here on every machine and `run_suite.py --engine sqlite` is already one of the
    estate's three free tiers, so the mutant below costs nothing and needs no warehouse. The SQL is
    the generator's own output, unedited — the point is to run the string that ships."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE host (host_key INTEGER, tag VARCHAR, code VARCHAR)")
    con.executemany("INSERT INTO host VALUES (?, ?, ?)", fixture)
    cur = con.execute(sql)
    row = dict(zip([dd[0] for dd in cur.description], cur.fetchone()))
    con.close()
    return row


def self_test() -> int:
    """One mutant per reject class this version adds, plus the controls that stop it over-firing.

    THE CLASSES ARE NEW, so the cases are about the POPULATION, not about SQL syntax:
        narrowed          a declared membership predicate must reach the WHERE clause
        filter wins       `value_filter` outranks `discriminator` when a concept declares both
        fixed verdict     a numeric key that is its own discriminator gets NO test
        blank member      the narrowing must NOT stop a member with an unusable key from failing
    plus the negative control that matters most here: a concept declaring NEITHER must come out
    BYTE-IDENTICAL to /6, because 5 of the 13 identity tests in the measured bundle are that shape
    and a fix that silently restates a passing test is worse than the defect."""
    bad, cases = 0, 0

    def check(label: str, got, want) -> None:
        nonlocal bad, cases
        cases += 1
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {label}: {got!r}, expected {want!r}")

    T = {"tag": "varchar", "code": "varchar", "host_key": "integer"}

    # ── 1. NO MEMBERSHIP DECLARED — the whole relation, and the /6 prose verbatim ─────────────
    where, basis, refusal = member_population({}, "host_key", T)
    check("no declaration narrows nothing", (where, basis, refusal), (None, "", None))
    whole = identity_property("Alpha", "w.host", "host_key", where, basis)
    check("whole-relation assertion column unchanged",
          whole["assertion"], {"type": "must_be_zero", "columns": ["rows_with_no_identity"]})
    check("whole-relation prose still claims every row",
          "canonical key is present on every row of w.host" in whole["statement"], True)
    check("whole-relation RISK unchanged",
          "silently drops out of every answer that needs it" in whole["statement"], True)
    check("whole-relation SQL has no WHERE", "WHERE" in whole["sql"], False)

    # ── 2. A DISCRIMINATOR THAT IS NOT THE KEY — narrowed, and both halves still bite ─────────
    where, basis, refusal = member_population({"discriminator": "tag"}, "code", T)
    check("discriminator narrows", (where, refusal), ('"tag" IS NOT NULL', None))
    narrowed = identity_property("Beta", "host", "code", where, basis)
    check("narrowed assertion column renamed", narrowed["assertion"],
          {"type": "must_be_zero", "columns": ["member_rows_with_no_identity"]})
    check("narrowed prose drops the every-row claim",
          "every row of" in narrowed["statement"], False)
    check("narrowed prose drops the false RISK",
          "silently drops out" in narrowed["statement"], False)
    check("narrowed prose names the basis it narrowed by",
          "grounding.discriminator: tag" in narrowed["statement"], True)
    # MUTANT — a MEMBER (tag present) whose key is NULL must still be counted.
    check("member with a NULL key still fails",
          _run(narrowed["sql"], [(1, "alpha", "c1"), (2, None, None), (3, "gamma", None)]),
          {"member_rows_with_no_identity": 1, "member_rows_examined": 2, "host_relation_rows": 3})

    # ── 3. THE KEY IS ITS OWN DISCRIMINATOR ───────────────────────────────────────────────────
    # TEXT: only the blank spelling of absence can fail, and it CAN, so the test is emitted.
    where, basis, refusal = member_population({"discriminator": "tag"}, "tag", T)
    check("text key as its own discriminator is still testable", refusal, None)
    same = identity_property("Gamma", "host", "tag", where, basis)
    fixture = [(1, "alpha", None), (2, None, None), (3, None, None), (4, "", None)]
    # MUTANT — row 4 is a MEMBER (tag is present) that names nothing. It must fail.
    check("member with a BLANK key still fails", _run(same["sql"], fixture),
          {"member_rows_with_no_identity": 1, "member_rows_examined": 2, "host_relation_rows": 4})
    # CONTROL — the same shape with no blank passes, over a population smaller than the host.
    check("clean members pass, and the narrowing is visible in both denominators",
          _run(same["sql"], [(1, "alpha", None), (2, None, None), (3, None, None),
                             (4, "beta", None)]),
          {"member_rows_with_no_identity": 0, "member_rows_examined": 2, "host_relation_rows": 4})
    # NEGATIVE CONTROL — this is the DEFECT, in miniature: the whole-relation shape reds on the two
    # rows the concept says are not its members, and never looks at the blank one that is.
    check("the un-narrowed shape counts non-members and misses the blank member",
          _run(identity_property("Gamma", "host", "tag", None, "")["sql"], fixture),
          {"rows_with_no_identity": 2, "rows_examined": 4})
    # NUMERIC: absence can only be NULL, which membership already excludes -> refuse.
    _, _, refusal = member_population({"discriminator": "host_key"}, "host_key", T)
    check("numeric key as its own discriminator is refused", bool(refusal), True)
    check("and the refusal says why", "integer" in str(refusal), True)
    # TYPE UNKNOWN: not established that anything can fail -> refuse, for a different reason.
    _, _, refusal = member_population({"discriminator": "tag"}, "tag", {})
    check("unknown type is refused too", bool(refusal), True)
    check("and is not confused with the numeric case",
          "not established" in str(refusal), True)

    # ── 4. value_filter OUTRANKS THE DISCRIMINATOR, AND IS PARENTHESISED ──────────────────────
    where, basis, refusal = member_population(
        {"discriminator": "tag", "value_filter": "tag = 'alpha' OR tag = 'beta'"}, "tag", T)
    check("filter wins over discriminator",
          (where, refusal), ("(tag = 'alpha' OR tag = 'beta')", None))
    check("filter is the basis in the prose", basis.startswith("grounding.value_filter:"), True)
    filt = identity_property("Delta", "host", "code", where, basis)
    # MUTANT — a row the FILTER admits whose key is empty must fail even though the filter column
    # is populated. This is the case a discriminator-only narrowing could not express.
    check("a filtered-in member with an empty key still fails",
          _run(filt["sql"], [(1, "alpha", "c1"), (2, "gamma", None), (3, "beta", "  "),
                             (4, None, None)]),
          {"member_rows_with_no_identity": 1, "member_rows_examined": 2, "host_relation_rows": 4})
    where, _, _ = member_population({"value_filter": {"sql": "tag IS NOT NULL"}}, "tag", T)
    check("a filter given as a mapping is read", where, "(tag IS NOT NULL)")

    print(f"{'PASS' if not bad else 'FAIL'}: {GEN} self-test — {cases - bad}/{cases} check(s): "
          f"4 executed mutant(s) (a member with a NULL key, a member with a BLANK key, a "
          f"filtered-in member with a whitespace key, and the un-narrowed shape counting "
          f"non-members), 2 refusal class(es) (numeric and unknown-typed self-discriminating "
          f"keys), and the byte-identical control for a concept that declares no membership")
    return 1 if bad else 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default="acceptance/ontology_generated.yaml")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    props, seen = [], 0
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER. This was `glob("ontology/concepts/*.yaml")` —
    # depth 0, two-plane path hardcoded — the exact defect tools/mac_project.py documents at length
    # ("eight gates globbed concepts/*.yaml ... found ZERO files and printed a clean verdict").
    # Measured 2026-09-18 on a live two-plane bundle (17 concepts, ALL foldered under
    # concepts/<group>/): this generator reported "0 conformance properties from 0 concept(s)" and
    # exited 0. check_rule_coverage.py already reads through the resolver; this one did not.
    for f in P.concept_files(root):
        got = for_concept(pathlib.Path(f), root)
        if got:
            seen += 1
        props.extend(got)

    from collections import Counter
    print(f"  {len(props)} conformance properties from {seen} concept(s)")
    if NO_KEY_COLUMN:
        print(f"\n  {len(NO_KEY_COLUMN)} concept(s) declare a grounding KEY naming a column the")
        print(f"  relation does not have. No test generated:")
        for nm, rel, key, near in NO_KEY_COLUMN:
            print(f"     {nm:<14}{rel:<28}{key:<26}nearest: {near}")
        print()
    if NO_IDENT_COLUMN:
        print(f"\n  {len(NO_IDENT_COLUMN)} concept(s) identify themselves by a column their relation")
        print(f"  does NOT have. No test generated — a query that cannot compile is not a finding:")
        for nm, rel, key, near in NO_IDENT_COLUMN:
            print(f"     {nm:<14}{rel:<28}{key:<26}nearest: {near}")
        print()
    if IDENT_FIXED:
        print(f"\n  {len(IDENT_FIXED)} concept(s) whose identity assertion would have a FIXED")
        print(f"  VERDICT once read over their own members. No test generated — a green that")
        print(f"  cannot go red is not evidence, and the coverage it claims is the hole:")
        for nm, rel, key, why in IDENT_FIXED:
            print(f"     {nm:<20}{rel:<28}{key:<18}{why[:96]}")
        print()
    if NOT_GRAIN:
        print(f"\n  {len(NOT_GRAIN)} concept(s) key on something that is NOT the relation's grain.")
        print(f"  No key_grain test generated — the concept is a DISCRIMINATOR there, not the row")
        print(f"  identity, and asserting uniqueness would fail by construction. Worth reading:")
        for nm, rel, why in NOT_GRAIN:
            print(f"     {nm:<18}{rel:<20}{why[:76]}")
        print()
    if UNMATCHED:
        print(f"\n  {len(UNMATCHED)} concept(s) declare a value set no grounded column carries — NOT")
        print(f"  given a test, because a wrong test is worse than an absent one:")
        for nm, rel, why in UNMATCHED:
            print(f"     {nm:<22}{rel:<28}{why[:70]}")
        print()
    for fam, n in Counter(p["family"] for p in props).most_common():
        print(f"     {fam:<12}{n:>4}")
    if a.dry_run:
        print("\n  (dry run — nothing written)")
        return 0
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    out = root / a.out
    out.write_text(yaml.safe_dump({
        # DERIVED FROM THE BUNDLE, for the reason mac_generate_sanity.py:405 states: a name a tool
        # writes about a bundle is the bundle's to supply. This was the literal string
        # "<dataset>-ontology-generated" — a scrub placeholder — so every bundle's run record named
        # a suite that does not exist, in every bundle, identically.
        "suite": f"{root.name}-ontology-generated", "version": "1.0",
        "purpose": ("DOES THE WAREHOUSE STILL MATCH WHAT THE ONTOLOGY CLAIMS? Every assertion here is "
                    "RENDERED from a concept at run time, never typed — so a concept edit moves its "
                    "tests with it. The opposite obligation to the data-sanity suite, which must not "
                    "read the declaration at all."),
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": GEN, "engine": eng, "properties": props,
    }, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print(f"  -> {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
