#!/usr/bin/env python3
"""mac_lookups.py — cut the VALUE REGISTERS from the domains already measured on the descriptors.

D12 of DELIVERABLES-2026-09-26_first-run-state.md. The operator: "no lookups in console".

WHY THE EXISTING CUTTER COULD NOT DO IT. `harvest --mode lookups` profiles through AWS: on a bundle
whose warehouse is a local DuckDB file it fails with `botocore.exceptions.NoCredentialsError: Unable
to locate credentials`. The framework HAS a connector seam — `_plugin.required(root, "Athena")`, which
`duckdb_seam` now answers for any DuckDB bundle — and the lookup cutter predates it. So a DuckDB
bundle could not cut a register at all, and D12 was empty on every run.

AND NOTHING NEEDS RE-PROFILING. `mac_profile` already captures a column's value domain onto its
descriptor for every column that is BOUNDED and ENUMERABLE — measured on one bundle: 28 of 72 served
columns. The register is a PROJECTION of that domain, not a new measurement, so this reads what is on
disk and writes the CSV the resolver expects.

WHAT A REGISTER IS FOR. A question names a WORD; the warehouse stores a CODE. A register maps one to
the other OFFLINE, so a question about "Germany" resolves without probing the warehouse and reading
"no rows" as "no such thing". Its first column is the CODE — the loader infers the source column from
exactly that — and `search_key` is what a person types.

THE SHAPE, unchanged from what the resolver already reads:

    <CodeColumn>,label,search_key,source_view,source_schema,confidence,note
    DE,Germany,germany,dim_contoso_customer,I,"measured: 8 members"

WHERE THE LABEL COMES FROM, and this is the one inference here. A code column often has a sibling
carrying the human name — `Country`/`CountryFull`, `CategoryKey`/`CategoryName` — and when the two
have the SAME number of members and the same row-by-row pairing, the sibling IS the label. When there
is no such sibling the code is its own label, which is correct for `Gender` (`female`) and for
`Status` (`Closed`). A pairing that does not hold one-to-one is NOT used: a label that is right for
most rows is worse than no label.

ONE REGISTER PER DIMENSION (DNA premise P4): a column already covered by a register is skipped rather
than cut twice under a second name.

AND THE MEMBERS MOVE — THE DESCRIPTOR KEEPS THE COUNT AND A POINTER. The operator: "are you sure that
it makes sense to include all possible incarnations of states into data source or dataset?!?! these
values could be in lookup if necessary?!?!"

Measured on one bundle: 1 186 of 1 595 descriptor lines — 74 % — were member lists, and
`dim_contoso_customer.yaml` was 656 lines at 89 % values. Worse, 563 of them were `State` members that
this cutter itself REFUSES as "data, not a register", so they were carried by the descriptor and used
by nothing.

So after a register is cut, its column's `values:` list is replaced by

    distinct: 8                                  the MEASUREMENT, which is a fact worth keeping
    register: data/lookups/contoso_country.lookup.csv    where the members live, once

A bounded column with NO register keeps `distinct:` and gets no pointer — which is the honest record:
measured, enumerable, and not resolvable offline. A descriptor states the SHAPE of a relation; the
members are a different fact with a different home, and two homes for one fact is what this estate
keeps paying for.

    python3 mac_lookups.py <bundle-root> [--max-members N] [--check]
"""

from __future__ import annotations

import argparse
import csv
import io
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402

GENERATOR = "mac_lookups.py/1"
#: Above this a column is not a register: it is data. 608 GeoAreaKeys is a dimension to join, not a
#: word list to resolve against, and a prompt cannot carry it.
MAX_MEMBERS = 200
#: A column whose members ARE the words needs no label sibling.
_SELF_LABELLING = ("gender", "status", "channel", "continent", "brand", "color", "colour",
                   "manufacturer", "weightunit", "currencycode", "fromcurrency", "tocurrency")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--max-members", type=int, default=MAX_MEMBERS)
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    ap.add_argument("--self-test", action="store_true",
                    help="cut real bundles in a temp dir; needs no warehouse")
    # THE PLANE, because the data plane is TWO deliveries (operator, 2026-09-28) and this tool sits on
    # the seam between them. `values:` on a descriptor is a TRANSIENT hand-off: `mac_profile` writes the
    # bounded domain, this tool cuts the register and POPS the list. Split the parts without splitting
    # this, and the sources delivery runs the writer and never the consumer — measured on contoso3's
    # first sources-only run: 7 of 7 source descriptors left carrying their member lists, one of them
    # 120 values long, which is the exact shape the operator ruled out of the YAML on 2026-09-26.
    #
    # AND CUTTING WAS DATASETS-ONLY WHILE STRIPPING WAS BOTH, which is a silent LOSS: a source column
    # whose domain no served view exposes had its members deleted and preserved nowhere. Now a plane
    # cuts what it strips.
    ap.add_argument("--plane", choices=("sources", "datasets", "both"), default="both",
                    help="which plane to cut registers from and slim (default: both)")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2

    # The connection is opened ONLY to verify a label pairing; the domains are read from disk.
    con = None
    try:
        con = _plugin.required(str(root), "Athena")(root=str(root))
    except Exception as exc:  # noqa: BLE001
        print(f"  (no engine: {str(exc)[:70]} — labels will fall back to the code)")

    marker = _marker(root, yaml)
    wrote, skipped, drift = 0, [], []
    repointed: dict[pathlib.Path, dict[str, str]] = {}
    seen_columns: set[tuple[str, str]] = set()
    planes = {"sources": ("sources",), "datasets": ("datasets",),
              "both": ("datasets", "sources")}[a.plane]
    cut_from = [d for pl in planes for d in sorted((root / "data" / pl).glob("*.yaml"))]
    # ONE REGISTER PER VALUE SET (operator, 2026-09-29): "there only one lookup for one thing that
    # can be attached to multiple targets". `by_set` accumulates every column carrying a given set,
    # so the second column to present it ATTACHES rather than cutting a second file. The old
    # `seen_columns` guard below still stands and still does its own job — it keeps the two halves
    # of a bijective pair from each cutting a register of the same dimension under two spellings.
    by_set: dict[frozenset, dict] = {}
    for desc in cut_from:
        doc = yaml.safe_load(desc.read_text(encoding="utf-8")) or {}
        relation = (doc.get("table") or {}).get("name") or desc.stem
        schema = (doc.get("table") or {}).get("schema")
        columns = doc.get("columns") or []
        names = {c.get("name") for c in columns}
        for col in columns:
            name, members = col.get("name"), col.get("values")
            if not name or not members:
                continue
            if len(members) > a.max_members:
                skipped.append(f"{relation}.{name} ({len(members)} members — data, not a register)")
                continue
            if (relation, name) in seen_columns:
                continue
            label_col = _label_column(name, names, con, schema, relation, members)
            # WHICH HALF OF A BIJECTIVE PAIR IS THE CODE. `DE` is the code, `Germany` the label —
            # and iterating in descriptor order got it backwards, keying the register on
            # `CountryFull` because that column comes first. The code is the TERSER half: a code set
            # is short by construction, and the register's first column is what the loader reads as
            # the column the warehouse stores.
            if label_col and _terser(col.get("values"), _values_of(columns, label_col)) is False:
                name, label_col = label_col, name
                members = _values_of(columns, name) or members
            # ONE REGISTER PER DIMENSION (DNA P4). A bijective pair is ONE dimension under two
            # spellings — `Country`/`CountryFull` — so the label half is claimed here and never cut
            # as a register of its own. Without this the bundle got two registers for one notion,
            # each naming the other as its label.
            if label_col:
                # BOTH HALVES CLAIMED, and after any swap — a first version added the pre-swap name
                # only, so the label half came round again and wrote the same register a second time.
                seen_columns.add((relation, label_col))
                seen_columns.add((relation, name))
            # THE SET IS THE IDENTITY. A column presenting members this bundle has already cut
            # ATTACHES to that register; it does not get a file of its own. Measured on contoso5
            # before this line existed: 48 files holding 25 value sets, the five currency codes
            # stored EIGHT times — once per column carrying them — and
            # `check_one_register_per_dimension` read `DUPLICATED: 0` over all of it, because it
            # counted the same (relation, column) pair the cutter keyed on.
            key = frozenset("" if m is None else str(m) for m in members)
            held = by_set.get(key)
            if held is not None:
                held["attached"].append((relation, name, desc, schema))
                continue
            by_set[key] = {"members": members, "label_col": label_col, "relation": relation,
                           "schema": schema, "column": name,
                           "attached": [(relation, name, desc, schema)]}

    # NOTHING IS WRITTEN UNTIL EVERY ATTACH POINT IS KNOWN, because the NAME depends on them. Cut
    # inside the loop, a register was named for whichever relation the scan reached first — and the
    # scan reads `datasets` before `sources`, so the same three currency columns produced
    # `dim_currency_currency_code` or `sales_currencycode` depending on plane order alone. A name
    # that moves when an unrelated relation is added is the instability `_stem` warns about; a name
    # settled after the whole bundle is read is at least a function of the whole bundle.
    _assign_names(marker, by_set)
    for key, held in by_set.items():
        held["out"] = root / "data" / "lookups" / f"{held['stem']}.lookup.csv"
        body = _render(held["relation"], held["column"], held["members"], held["label_col"],
                       con, held["schema"], marker)
        out = held["out"]
        if a.check:
            if (out.read_text(encoding="utf-8") if out.is_file() else "") != body:
                drift.append(str(out.relative_to(root)))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
        wrote += 1
        lab = f" label<-{held['label_col']}" if held["label_col"] else " (code is its own label)"
        extra = [f"{r}.{c}" for r, c, _, _sc in held["attached"][1:]]
        print(f"  {out.name:44} {len(held['members']):>4} member(s){lab}")
        for e in extra:
            print(f"  {'':44}      + {e}")
    if con is not None:
        con.close()

    # EVERY ATTACH POINT POINTS AT THE ONE FILE. `repointed` is what `_slim_descriptors` writes
    # back onto each column as its `register:`, and it is built from the groups rather than at cut
    # time so that the seventh column carrying the currency codes gets the same pointer as the
    # first. This is the whole of "attached to multiple targets" — the descriptor field was always
    # many-to-one capable; only the cutter's per-column identity prevented it.
    for held in by_set.values():
        rel = str(held["out"].relative_to(root))
        for _relation, column, desc, _schema in held["attached"]:
            repointed.setdefault(desc, {})[column] = rel

    if not a.check:
        _write_register_descriptors(root, by_set, yaml)
        slimmed = _slim_descriptors(root, repointed, yaml, planes)
        if slimmed:
            print(f"\n  the members MOVED: {slimmed} descriptor line(s) of member list replaced by "
                  f"`distinct:` + `register:` — one home for the members, the count kept where it "
                  f"was measured")

    if a.check:
        if drift:
            print(f"DRIFT — {len(drift)} register(s) no longer match the measured domains.")
            return 1
        print("OK — every register matches the measured domains.")
        return 0
    for s in skipped:
        print(f"  NOT A REGISTER  {s}")
    if not wrote:
        # ALREADY CUT IS NOT "NOTHING TO CUT", and saying the second when the first is true was a
        # FALSE STATEMENT ABOUT THE DATA. This tool consumes its input by design: it replaces each
        # captured `values:` list with `distinct:` + `register:` so the descriptor plane stays lean
        # (1,186 of 1,595 lines were member lists). A second run therefore finds no `values:` — and
        # said "no column is both bounded and enumerable" while 17 registers sat on disk with 22
        # columns pointing at them. An operator reading that would conclude the bundle has no closed
        # domains, which is the opposite of what was measured.
        already = len(list((root / "lookups").glob("*.lookup.csv"))) if (root / "lookups").is_dir() \
            else len(list((root / "data" / "lookups").glob("*.lookup.csv")))
        if already:
            print(f"  ALREADY CUT — {already} register(s) are present and the descriptors point at "
                  f"them; there is no `values:` list left to project because this tool moved them. "
                  f"Nothing to do.\n  To RE-MEASURE the domains (a warehouse may have gained a "
                  f"value), re-run `mac_profile`, which is what captures them; to check the "
                  f"registers against the warehouse as they stand, run "
                  f"`check_register_membership.py`.")
        else:
            print("  no column is both bounded and enumerable — nothing to resolve offline. A "
                  "register is cut from a domain `mac_profile` captured; if none was, there is none "
                  "to project.")
    # THE COUNT MUST MATCH WHAT IS ON DISK. "wrote 22 register(s)" beside 17 files is a report an
    # operator has to reconcile by hand: 22 is the number of COLUMN DOMAINS cut, and several columns
    # legitimately share one register (a code carried by both a raw landing and the view over it, or
    # port_code appearing as depart_ and arrive_). Both numbers are facts; only one was said.
    files = len({reg for cols in repointed.values() for reg in cols.values()})
    print(f"\ncut {wrote} column domain(s) into {files} register file(s), from domains already "
          f"measured on the descriptors")
    return 0


def _self_test() -> int:
    """Cut real bundles in a temp directory and count what came out. No warehouse, no network.

    THIS FILE HAD NO SELF-TEST, which is how both of its naming regimes shipped broken. The cases
    below are the two failures that actually happened, seeded so they cannot come back silently.
    """
    import tempfile

    import yaml as _yaml

    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    def cut(relations: dict) -> dict:
        """relations: {relation: {column: [members]}} -> {stem: member count}."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "data" / "sources").mkdir(parents=True)
            (root / "mac.project.yaml").write_text("metadata: {dataset: tb}\n", encoding="utf-8")
            for rel, cols in relations.items():
                doc = {"table": {"name": rel, "schema": "main"},
                       "columns": [{"name": c, "type": "string", "values": v}
                                   for c, v in cols.items()]}
                (root / "data" / "sources" / f"{rel}.yaml").write_text(
                    _yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            import contextlib
            import io as _io
            with contextlib.redirect_stdout(_io.StringIO()):
                main([str(root), "--plane", "sources"])
            out = {}
            for f in sorted((root / "data" / "lookups").glob("*.lookup.csv")):
                out[f.stem.replace(".lookup", "")] = len(f.read_text().splitlines()) - 1
            return out

    CUR = ["AUD", "CAD", "EUR", "GBP", "USD"]

    # ONE VALUE SET, MANY COLUMNS -> ONE FILE. The operator's ruling, and the thing contoso5 got
    # wrong 23 times over.
    got = cut({"sales": {"CurrencyCode": CUR}, "orders": {"CurrencyCode": CUR},
               "dim_currency": {"currency_code": CUR}})
    case(f"three columns, one value set -> ONE register named for the notion  (got {got})",
         got == {"tb_currency_code": 5})

    # TWO SETS THAT AGREE ON A NOTION MUST NOT SHARE A FILE. This is contoso4's `state`: naming by
    # notion alone cut 2 domains into 1 file and lost four codes with exit 0.
    got = cut({"dim_location": {"state": ["Alaska", "Arkansas", "Utah"]},
               "customer": {"State": ["AK", "AL", "UT", "CB"]}})
    case(f"MUTANT two different sets claiming one notion keep BOTH domains  (got {got})",
         got == {"tb_customer_state": 4, "tb_dim_location_state": 3})

    # AND THE QUALIFIED FALLBACK IS APPLIED TO ALL CLAIMANTS, not just the later one — otherwise
    # the winner's name depends on which plane the scan reached first.
    case("neither claimant keeps the bare notion when two sets claim it",
         "tb_state" not in got)

    got = cut({"sales": {"Gender": ["female", "male"], "CurrencyCode": CUR}})
    case(f"two unrelated sets on one relation -> two registers  (got {got})",
         got == {"tb_currency_code": 5, "tb_gender": 2})

    got = cut({"big": {"Zip": [str(i) for i in range(300)]}})
    case(f"a column above --max-members is NOT a register  (got {got})", got == {})

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": mac_lookups self-test — {ok[1]}/{ok[0]} case(s), including the collision that cost "
            f"contoso4 a domain and the duplication that cost contoso5 twenty-three files.")
    return 0 if ok[1] == ok[0] else 1


def _snake(name: str) -> str:
    """`SubCategoryName` -> `sub_category_name`, so two spellings of one notion compare equal."""
    import re
    return re.sub(r"_+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))).strip("_").lower()


def _register_name(marker: str, held: dict) -> str:
    """The register's file stem: the NOTION its attach points agree on, qualified when they do not.

    THE ESTATE HAS ALREADY TRIED BOTH POLES AND BEEN BURNED BY EACH. `_stem` below records it: the
    name was `{marker}_{column}`, two relations carrying a same-named column collided on one
    filename and the second cut silently OVERWROTE the first — contoso4's `customer.State`, 565
    members, pointing at a 67-member register cut from `store`. Qualifying every name with its
    relation fixed that and produced the duplication the operator ruled against on 2026-09-29: 48
    files holding 25 value sets.

    Neither name was ever the identity — the VALUE SET is, and that is settled above. This only
    chooses what to CALL the one file, and the collision that broke notion-naming can no longer
    happen: two different sets are two registers by construction, so if they also agree on a notion
    the qualified fallback keeps them apart instead of one overwriting the other.

    `state` in contoso5 is exactly that case and it is not a defect to design away — 67 NAMES on
    `dim_location` against 565 CODES on `customer` really are two dimensions. They keep their
    qualified names and `check_one_register_per_dimension` no longer calls them duplicates.
    """
    spellings = {_snake(c) for _, c, _, _sc in held["attached"]}
    base = next(iter(spellings)) if len(spellings) == 1 else None
    if base is None:
        # UNSETTLED: the attach points call this set different things (`store_name` against
        # `Description`). Falling back to the cut site's (relation, column) is the SAFE half of the
        # old rule — it cannot collide — and the plan reports it for a person to author.
        base = _snake(f"{held['relation']}_{held['column']}")
    return f"{marker}_{base}" if marker and marker not in base else base


def _assign_names(marker: str, by_set: dict) -> None:
    """Give every value set a stem, and make sure no two sets claim the same one.

    THIS IS THE GUARD WHOSE ABSENCE COST FOUR BUNDLES. Naming by notion is right and is also
    precisely how `contoso4_state` came to hold the wrong members: `customer.State` (565 codes) and
    `store.State` (67 names) both derive `state`, one file was written, and the loser's domain was
    preserved NOWHERE. Reproduced deliberately while writing this, on a two-relation bundle:

        cut 2 column domain(s) into 1 register file(s)

    — two domains in, one file out, four codes gone, exit 0. The set-level identity above does not
    prevent it: two different sets are correctly two registers and then collide on the FILENAME.

    So a notion claimed by more than one set is not usable as a name, and every set claiming it
    falls back to its own `{relation}_{column}` — which cannot collide, because the cut site is
    unique. The fallback is applied to ALL claimants, never to the later one only: qualifying just
    the loser would leave the winner's name depending on scan order.
    """
    import collections
    prefer = {k: _register_name(marker, h) for k, h in by_set.items()}
    claimed = collections.Counter(prefer.values())
    for key, held in by_set.items():
        name = prefer[key]
        if claimed[name] > 1:
            base = _snake(f"{held['relation']}_{held['column']}")
            name = f"{marker}_{base}" if marker and marker not in base else base
            held["name_qualified_because"] = f"{claimed[prefer[key]]} value sets claim {prefer[key]!r}"
        held["stem"] = name


def _write_register_descriptors(root: pathlib.Path, by_set: dict, yaml) -> int:
    """One `<stem>.lookup.yaml` per register: what it holds and every column attached to it.

    A REGISTER IS A VIRTUAL TABLE (operator, 2026-09-29): "it reads like one register is like
    virtual table. then many rules from the table domain will fit for the register lookup." A table
    states its shape in a descriptor, so a register does too — and the fact that became PLURAL when
    one register began serving many columns is exactly the one that had nowhere to live.

    IT REPLACES A FACT SMEARED ACROSS THE ROWS. `source_view` and `source_schema` are written into
    EVERY row of the CSV today — a table carrying its own lineage in each record. That was tolerable
    while a register had exactly one source and is wrong the moment it has eight. The columns stay
    in the CSV for now because four readers resolve through them (`mac_descriptors`,
    `check_register_membership`, `check_registers_reachable`, and this file), and
    `check_registers_reachable` says plainly that renaming that header "breaks a live behaviour with
    no error". They name the OWNER; this names all of them.
    """
    wrote = 0
    for held in by_set.values():
        rel_csv = str(held["out"].relative_to(root))
        # THE SCHEMA TRAVELS WITH EACH ATTACH POINT. A shared register spans PLANES — the same
        # twelve month names sit on `main.date` and `contoso_served.dim_date` — so applying the
        # owner's schema to every attach point resolved half of them against the wrong catalog.
        # Measured on contoso5 the hour this list became plural: `contoso_served.date does not
        # exist`, on a register that was correct.
        attached = sorted({(r, c, sc or "") for r, c, _, sc in held["attached"]})
        owner_rel, owner_col, _owner_schema = attached[0]
        doc = {
            "metadata": {"kind": "value_register", "schema_version": "0.1.16",
                         "generated_by": GENERATOR},
            "register": {"name": held["stem"], "csv": rel_csv,
                         "members": len(held["members"]), "grain": "one row per code"},
            "attached": [{"relation": r, "column": c, "schema": sc} for r, c, sc in attached],
        }
        head = ("# GENERATED by mac_lookups.py/1 — do not edit; re-run the cutter.\n"
                "#\n"
                "# A register is a VIRTUAL TABLE: `code` is its key, one row per member, and\n"
                "# `attached` is every column of this bundle whose values ARE this set.\n"
                f"# Cut from {owner_rel}.{owner_col}; the others attach to it.\n")
        out = held["out"].parent / f"{held['stem']}.lookup.yaml"
        out.write_text(head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                       encoding="utf-8")
        wrote += 1
    return wrote


def _slim_descriptors(root: pathlib.Path, repointed: dict, yaml, planes) -> int:
    """Replace every captured `values:` list with `distinct:` + `register:` where one was cut.

    EVERY bounded column is slimmed, not only the ones that got a register: a column refused as "data,
    not a register" was the worst case — 563 members carried by the descriptor and read by nothing.
    It keeps `distinct:` and no pointer, which says exactly that.

    Rewritten through yaml rather than by editing text, so the file stays the shape the framework's
    own schema defines and a partially-matched regex cannot leave a half-stripped list behind.
    """
    saved = 0
    # BOTH PLANES. Slimming only `datasets` left the eight SOURCE descriptors carrying their member
    # lists, which is the same duplication one directory over — and measurably so: the generated
    # sanity suite still built 30 `enumeration` cases from them after the served copies were gone.
    # SLIM EXACTLY THE PLANES THIS RUN CUT FROM. Stripping a plane this run did not cut is how a
    # domain is lost: the members go and no register holds them.
    descs = [d for pl in planes for d in sorted((root / "data" / pl).glob("*.yaml"))]
    for desc in descs:
        doc = yaml.safe_load(desc.read_text(encoding="utf-8")) or {}
        cols = doc.get("columns") or []
        touched = False
        for c in cols:
            members = c.pop("values", None)
            if members is None:
                continue
            saved += len(members)
            touched = True
            c["distinct"] = len(members)
            reg = (repointed.get(desc) or {}).get(c.get("name"))
            if reg:
                c["register"] = reg
        if not touched:
            continue
        head = "\n".join(ln for ln in desc.read_text(encoding="utf-8").splitlines()
                          if ln.startswith("#"))
        desc.write_text(head + "\n" + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                                                      width=100), encoding="utf-8")
    return saved


def _values_of(columns: list, name: str) -> list:
    return next((c.get("values") or [] for c in columns if c.get("name") == name), [])


def _terser(mine: list | None, theirs: list | None) -> bool:
    """Is my half of the pair the shorter-valued one? `DE` over `Germany`."""
    def avg(vals):
        vals = [str(v) for v in (vals or []) if v is not None]
        return sum(len(v) for v in vals) / len(vals) if vals else 0.0
    a, b = avg(mine), avg(theirs)
    return a <= b if (a and b) else True


def _marker(root: pathlib.Path, yaml) -> str:
    """The bundle's own naming marker, so a register is addressable as THIS source's."""
    f = root / "mac.project.yaml"
    if not f.is_file():
        return ""
    doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return str(((doc.get("serving") or {}).get("naming") or {}).get("marker")
               or (doc.get("metadata") or {}).get("dataset") or "")


def _stem(marker: str, relation: str, column: str) -> str:
    """`v_contoso4_product_brand` — the register's name is its (RELATION, COLUMN), because that is
    what a register IS.

    IT TOOK `relation` AND THREW IT AWAY. The name was `{marker}_{column}`, so two relations carrying a
    same-named column produced the SAME filename and the second cut silently OVERWROTE the first —
    last writer wins, and the loser's domain is preserved nowhere. The collision is invisible in the
    artifact, because an overwrite leaves one coherent file behind; it shows only in this tool's own
    count. MEASURED 2026-09-28: contoso3 "cut 22 column domain(s) into 18 register file(s)" and
    contoso5 24 into 23 — four and one domains lost, silently.

    IT IS ALSO THE ROOT OF A BUG ALREADY "FIXED" ONCE. contoso4's `customer.State` (565 distinct
    values) pointed at a 67-member register cut from `store`, and that was repaired at the POINTER by
    keying `cut_registers` on the cut site. The pointer was never the cause: both columns cut into one
    file named `contoso4_state`, and the store cut landed last.

    ALWAYS QUALIFIED, NEVER CONDITIONALLY. Qualifying only on collision would make a register's name
    depend on what ELSE the bundle holds, so adding an unrelated relation could rename an existing
    file. A name that is a function of its own subject alone is the only one that stays put.

    The marker is prefixed only when the relation does not already carry it, so a served relation that
    is already named for its bundle (`v_contoso4_product`) does not say so twice.
    """
    base = f"{relation}_{column}".lower()
    return f"{marker}_{base}" if marker and marker not in base else base


def _label_column(code: str, names: set, con, schema, relation: str, members: list) -> str | None:
    """The sibling column carrying the human name, when the pairing is ONE-TO-ONE and measured.

    BIJECTIVE, BOTH WAYS, and the first version tested only one — which is the same defect this
    session already paid for with `finer_than`. Checking "each code maps to ONE value of the
    candidate" is FUNCTIONAL DEPENDENCE, and a PARENT satisfies it: every `YearQuarter` maps to
    exactly one `Year`, so `Year` was accepted as the LABEL of `YearQuarter`. It is not a label, it
    is a coarser axis, and a register built on it would resolve "2024" to one quarter of four.

    So both directions are measured: each code to one label AND each label to one code. `Country`
    <-> `CountryFull` holds; `YearQuarter` -> `Year` does not.

    A label that is right for most rows is worse than none: it resolves a word to a code that is
    wrong on the remainder, silently. So the pairing is VERIFIED against the warehouse, and a
    candidate that does not hold exactly is dropped.
    """
    if code.lower() in _SELF_LABELLING or con is None or not schema:
        return None
    stem = code[:-3] if code.lower().endswith("key") else code
    candidates = [n for n in names
                  if n != code and (n.startswith(stem) or stem.startswith(n.rstrip("Name")))
                  and n.lower() not in ("", code.lower())]
    for cand in sorted(candidates, key=len):
        if _bijective(con, schema, relation, code, cand):
            return cand
    return None


def _bijective(con, schema: str, relation: str, a: str, b: str) -> bool:
    """One `a` per `b` AND one `b` per `a`. Either direction alone admits a parent."""
    for left, right in ((a, b), (b, a)):
        try:
            rows, _ = con.query(
                f'SELECT count(*) AS d0 FROM (SELECT "{left}" FROM "{schema}"."{relation}" '
                f'GROUP BY "{left}" HAVING count(DISTINCT "{right}") > 1)'
            )
        except Exception:  # noqa: BLE001 - a column that cannot group is not a label
            return False
        if not rows or int(rows[0]["d0"]) != 0:
            return False
    return True


def _render(relation: str, code: str, members: list, label_col: str | None,
            con, schema, marker: str) -> str:
    labels: dict[str, str] = {}
    if label_col and con is not None and schema:
        try:
            rows, _ = con.query(
                f'SELECT "{code}" AS d0, min("{label_col}") AS d1 FROM "{schema}"."{relation}" '
                f'GROUP BY "{code}"'
            )
            labels = {str(r["d0"]): ("" if r["d1"] is None else str(r["d1"])) for r in rows}
        except Exception:  # noqa: BLE001
            labels = {}

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    # `source_schema` RECORDS THE PLANE IT WAS CUT FROM, and it is not a nicety. The monitor
    # (check_register_membership) re-measures a register against its source relation, and it resolved
    # that relation in the SERVED schema for every register — fine while registers were only ever cut
    # from served views, and wrong the moment a landing-plane delivery cut its own: measured 2026-09-28
    # on contoso5's first sources ingest, all 23 registers failed as `contoso_served.store does not
    # exist` when they had been cut from `main.store`. The monitor's own docstring says the code column
    # and the source relation are "read from the file, never guessed" — so the SCHEMA is read from the
    # file too, rather than guessed from a connector default.
    w.writerow([code, "label", "search_key", "source_view", "source_schema", "confidence", "note"])
    for m in members:
        val = "" if m is None else str(m)
        label = labels.get(val) or val
        w.writerow([val, label, label.strip().lower(), relation, schema or "", "I",
                    f"measured: {len(members)} members in {relation}.{code}"])
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
