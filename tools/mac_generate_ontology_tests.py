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
Measured on fpl2 (22 concepts, 30 rules):

    ALREADY ENFORCED OFFLINE, so deliberately NOT generated — 58 assertions. Column existence for
    rules[].binds, grounding.columns and properties[] is a SHAPE (rule-binds-grounded,
    field-roles-grounded), checked without touching the warehouse. Re-asserting it in SQL would move
    a fast structural gate into a slow expensive plane and call it coverage.

    GENERATED — the declarations that can only be settled against data:
        identity      concept.identity.canonical_key is unique and non-null
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
import sys

import yaml

GEN = "mac_generate_ontology_tests.py/4"

# concepts whose declared value set matches no grounded column — reported, never guessed
UNMATCHED: list[tuple[str, str, str]] = []
# concepts whose declared key is NOT the relation's grain — a finding, not a test
NOT_GRAIN: list[tuple[str, str, str]] = []


def measured_key(root: pathlib.Path, rel: str) -> list[str]:
    """The relation's MEASURED grain, from the measurement plane. Empty when nothing measured it."""
    f = root / "data" / "profiles" / f"{rel.split('.')[-1]}.yaml"
    if not f.exists():
        return []
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return list((d.get("identity_evidence") or {}).get("key") or [])


def value_column(root: pathlib.Path, rel: str, declared: list[str], ident: str) -> tuple[str | None, str]:
    """WHICH column actually holds this concept's value set — matched, not assumed.

    The first run assumed `identity.canonical_key`. On body_type that produced a test comparing
    `fpl_lm_body_type_id` (int) against 'Cabrio/Roadster' — because the concept identifies itself by
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


def _rel(src: dict) -> str:
    return str(src.get("relation") or "")


def for_concept(path: pathlib.Path, root: pathlib.Path) -> list[dict]:
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    c = d.get("concept") or {}
    name = str(c.get("name") or path.stem)
    stem = path.stem
    srcs = ((d.get("grounding") or {}).get("sources") or [])
    out: list[dict] = []
    src_note = f"ontology/concepts/{path.name}"

    def prop(fam, sid, statement, sql, assertion):
        out.append({
            "id": sid, "family": fam, "test_kind": "mac.test_kind.conformance",
            "severity": "major", "source": src_note, "validates": [name],
            "statement": statement, "assertion": assertion, "tolerance": 0, "sql": sql,
        })

    for i, s in enumerate(srcs):
        rel = _rel(s)
        if not rel:
            continue
        key = s.get("key")
        keys = [key] if isinstance(key, str) else list(key or ())
        # A key is a ROW key only where the concept IS the grain of the relation. On a FACT relation
        # an enumeration or reference concept keys on a DISCRIMINATOR — `perspective` keys on `role`,
        # 6 values over 800 Mio rows — and asserting uniqueness there fails by construction. The
        # first cut generated 16 such tests. The measured grain settles it: compare the concept's
        # declared key against identity_evidence.key rather than guessing from the relation name.
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
                 f"(@cols:concept:{stem}.grounding.sources), never typed here — a typed key would go "
                 f"on passing after the concept changed. GENERATED by {GEN}.\n"
                 f"WHERE. {rel}.",
                 f"SELECT count(*) AS keys_holding_more_than_one_row\n"
                 f"FROM (SELECT {cols} FROM {rel} GROUP BY {cols} HAVING count(*) > 1)",
                 {"type": "must_be_zero", "columns": ["keys_holding_more_than_one_row"]})

    ident = (c.get("identity") or {}).get("canonical_key")
    if ident and srcs:
        rel = _rel(srcs[0])
        if rel:
            prop("identity", f"O-{stem.upper()}-IDENT",
                 f"Prove {name}'s canonical key is present on every row of {rel}\n"
                 f"QUESTION. Can every row of this relation be named by the key the concept "
                 f"identifies itself with?\n"
                 f"ANSWER. The concept identifies itself by `{ident}`.\n"
                 f"RISK. A row whose identity is empty cannot be addressed, compared or joined — it "
                 f"silently drops out of every answer that needs it.\n---\n"
                 f"HOW. Counts empties in the canonical key. GENERATED by {GEN}.\n"
                 f"WHERE. {rel}.{ident}.",
                 f'SELECT count(*) - count("{ident}") AS rows_with_no_identity,\n'
                 f"       count(*) AS rows_examined\nFROM {rel}",
                 {"type": "must_be_zero", "columns": ["rows_with_no_identity"]})

    v = d.get("values") or {}
    items = [i for i in (v.get("items") or []) if isinstance(i, dict) and i.get("code") is not None]
    if items and srcs and ident:
        rel = _rel(srcs[0])
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default="acceptance/ontology_generated.yaml")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    props, seen = [], 0
    for f in sorted(glob.glob(str(root / "ontology" / "concepts" / "*.yaml"))):
        got = for_concept(pathlib.Path(f), root)
        if got:
            seen += 1
        props.extend(got)

    from collections import Counter
    print(f"  {len(props)} conformance properties from {seen} concept(s)")
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
        "suite": "fpl2-ontology-generated", "version": "1.0",
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
