#!/usr/bin/env python3
"""mac_register_plan.py — what the registers WOULD be if a register were a value set. Writes nothing.

THE OPERATOR, 2026-09-29: "they all show the same thing! lookup policy must be changed in way that
there only one lookup for one thing that can be attached to multiple targets. and another thing is
that not everyting is suitable for lookup. one huge table where the search criteria is text cannot be
converted into lookup. it should just be declared later to be searchebal with like."

Measured on contoso5 before this existed: 48 register files holding 25 DISTINCT value sets — 23
redundant copies, 47 %. The 5 currency codes were stored EIGHT times, once per column that happens to
carry them. Meanwhile `tools/check_one_register_per_dimension.py` reported

    registers: 48   distinct domains: 48   DUPLICATED: 0
    OK — every (source_view, column) has at most one register.

because it calls a (source_view, column) pair a "domain". A gate is only as true as its denominator.

WHY THE ESTATE ALREADY TRIED BOTH NAMES AND GOT BURNED BOTH TIMES. `mac_lookups._stem` records it:
the name was `{marker}_{column}`, two relations carrying a same-named column collided on one filename
and the second cut silently OVERWROTE the first — contoso4's `customer.State`, 565 members, pointing
at a 67-member register cut from `store`. That was repaired by qualifying every name with its
relation, which is exactly what produces the duplication above. Notion-naming collides; column-naming
duplicates. NEITHER IS THE IDENTITY.

A REGISTER IS A VALUE SET. That is the whole change. Two columns holding the same members share one
register however they are spelled; two columns holding different members never share one however
alike they are named. `state` in this bundle is BOTH — 67 names (`Alaska`, `Arkansas`) on
`dim_location`, and 565 codes (`AK`, `AL`) on `customer` — so it is two registers, and the collision
is a MODELLING defect worth saying out loud rather than a filename to disambiguate.

SUITABILITY, and the rule is not the obvious one. The first hypothesis was distinct/rows: a
vocabulary is a few values over many rows, an identifier is near-unique. It is killed by the most
canonical register in the bundle — `dim_currency.currency_code` is 5 values over 5 rows, ratio 1.0,
because a dimension table IS its own register. So the ratio decides only where a column is not the
dimension's key, and a column other relations REFERENCE is a register by declaration:

    REGISTER            it is the target of a declared reference   (a shared dimension key)
                     or <= SMALL members                           (a person can name them all)
                     or <= RATIO of its rows and <= BOUNDED        (a vocabulary, repeated)
    searchable: like    anything else                              (open text)

Measured over contoso5's 72 candidate columns that rule gives 56 registers over 28 value sets and 16
open-text columns — `customer_name` at 99 200 of 104 990 rows, `StreetAddress` at 95 854,
`ProductName` at 2 517 of 2 517. Those are the ones that want LIKE, and none of them is a register
today, so this is not a regression: it NAMES what is currently unhandled.

THE NAME IS PROPOSED HERE AND CONFIRMED BY A PERSON. Derivation is a proposal because every derivable
name depends on what else the bundle holds — add a relation and an alphabetical winner changes, which
is the instability `_stem` warns about. So a register's name is `authored-once`: this proposes it, a
person confirms it, and it never moves again.

    python3 mac_register_plan.py <bundle-root> [--small N] [--ratio R] [--bounded N] [--json]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402

#: A set a person could name every member of. Below this, cardinality alone settles it.
SMALL = 100
#: A vocabulary repeats. Above this share of its rows a column is identifying, not describing.
RATIO = 0.05
#: Even a well-repeated column stops being nameable somewhere. `Occupation` has 2 571 members.
BOUNDED = 1000


def _snake(name: str) -> str:
    """`SubCategoryName` -> `sub_category_name`, so two spellings of one notion compare equal."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))
    return re.sub(r"_+", "_", s).strip("_").lower()


def _candidates(root: pathlib.Path, yaml) -> list:
    """Every column that either HAS a register today or could plausibly want one.

    A column already carrying `register:` is included because the point of this plan is to re-decide
    it; a string column with no reference and no key role is included because that is where the
    open-text columns live, and they are the half of the operator's ruling that nothing covers today.
    """
    out = []
    for f in sorted(root.glob("data/*/*.yaml")):
        if f.parent.name not in ("sources", "datasets"):
            continue
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        tbl = doc.get("table") or {}
        rel = tbl.get("name") or f.stem
        for col in doc.get("columns") or []:
            if not isinstance(col, dict):
                continue
            name = col.get("name")
            if not name:
                continue
            registered = bool(col.get("register"))
            plain = (str(col.get("type")) == "string"
                     and not col.get("references")
                     and col.get("role") not in ("primary_key", "foreign_key"))
            if registered or plain:
                out.append({"schema": tbl.get("schema"), "relation": rel, "column": name,
                            "rows": tbl.get("rows_measured") or 0, "registered": registered})
    return out


def _targets(root: pathlib.Path, yaml) -> set:
    """Every `relation.column` some other column declares a reference to."""
    out = set()
    for f in root.glob("data/*/*.yaml"):
        if f.parent.name not in ("sources", "datasets"):
            continue
        for col in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("columns") or []:
            if not isinstance(col, dict):
                continue
            ref = col.get("references")
            to = ref.get("to") if isinstance(ref, dict) else ref
            if to:
                out.add(str(to))
    return out


def classify(distinct: int, rows: int, referenced: bool,
             small: int = SMALL, ratio: float = RATIO, bounded: int = BOUNDED) -> tuple:
    """(verdict, why). The whole suitability rule, in one place, so a self-test can hold it."""
    if referenced:
        return "register", "referenced by other relations"
    if distinct <= small:
        return "register", f"closed set of {distinct}"
    if rows and distinct / rows <= ratio and distinct <= bounded:
        return "register", f"vocabulary: {distinct} over {rows} rows"
    return "searchable", f"open text: {distinct} of {rows} rows"


def propose_name(attached: list, owner: str | None) -> tuple:
    """(name, settled). The notion its attach points agree on, or the owner's column.

    NOT A FUNCTION OF THE SET ALONE, and it cannot be — members carry no name. So where the attach
    points disagree and no reference names an owner, this returns the shortest normalised spelling
    and says `settled=False`, which is the signal that a person must confirm it.
    """
    spellings = {_snake(c) for _, c in attached}
    if owner:
        return _snake(owner.split(".")[-1]), True
    if len(spellings) == 1:
        return next(iter(spellings)), True
    return sorted(spellings, key=lambda s: (len(s), s))[0], False


def plan(root: pathlib.Path, yaml, con, **thresholds) -> dict:
    targets = _targets(root, yaml)
    groups: dict = collections.defaultdict(list)
    text, unreadable = [], []
    for c in _candidates(root, yaml):
        key = f"{c['relation']}.{c['column']}"
        # THROUGH THE CONNECTOR SEAM, `con.query` -> (rows as dicts, meta) — the same call
        # `mac_lookups._bijective` makes. A first version called `con.execute(...).fetchall()` as if
        # this were a DBAPI connection and every one of 72 columns came back unreadable.
        try:
            rows, _ = con.query(f'SELECT DISTINCT "{c["column"]}" AS v '
                                f'FROM "{c["schema"]}"."{c["relation"]}"')
        except Exception as exc:  # noqa: BLE001
            unreadable.append((key, str(exc)[:70]))
            continue
        members = frozenset(r["v"] for r in rows if r.get("v") is not None)
        verdict, why = classify(len(members), c["rows"], key in targets, **thresholds)
        if verdict == "register":
            groups[members].append((key, c["column"], key in targets))
        else:
            text.append({"at": key, "distinct": len(members), "rows": c["rows"], "why": why})

    registers = []
    for members, attached in groups.items():
        owner = next((k for k, _, ref in attached if ref), None)
        name, settled = propose_name([(k, col) for k, col, _ in attached], owner)
        registers.append({"name": name, "settled": settled, "members": len(members),
                          "owner": owner, "sample": sorted(members)[:4],
                          "attached": sorted(k for k, _, _ in attached)})
    registers.sort(key=lambda r: (-len(r["attached"]), r["name"]))

    # TWO DIFFERENT SETS UNDER ONE NAME IS THE COLLISION THAT STARTED ALL OF THIS. It is reported,
    # never silently qualified: qualifying would make a register's name depend on what else the
    # bundle holds, and it is how `contoso4_state` came to hold the wrong 67 members.
    byname = collections.Counter(r["name"] for r in registers)
    for r in registers:
        r["collides"] = byname[r["name"]] > 1
    return {"registers": registers, "searchable": sorted(text, key=lambda t: -t["distinct"]),
            "unreadable": unreadable}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--small", type=int, default=SMALL)
    ap.add_argument("--ratio", type=float, default=RATIO)
    ap.add_argument("--bounded", type=int, default=BOUNDED)
    ap.add_argument("--json", action="store_true", help="the plan as data")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2
    try:
        con = _plugin.required(str(root), "Athena")(root=str(root))
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: no engine — a plan needs the MEASURED domains, not the names ({exc})")
        return 2

    p = plan(root, yaml, con, small=a.small, ratio=a.ratio, bounded=a.bounded)
    con.close()
    if a.json:
        print(json.dumps(p, indent=2, sort_keys=True))
        return 0

    on_disk = len(list(root.glob("data/lookups/*.lookup.csv")))
    regs, text = p["registers"], p["searchable"]
    attach = sum(len(r["attached"]) for r in regs)
    print(f"\n  {on_disk} register file(s) on disk today")
    print(f"  {len(regs)} register(s) under this plan, holding {attach} attach point(s) — "
          f"one value set, many columns")
    print(f"  {len(text)} column(s) are open text and want `searchable: like`, not a register\n")

    print("  REGISTERS")
    for r in regs:
        flag = "" if r["settled"] else "   NAME UNSETTLED"
        if r["collides"]:
            flag = "   COLLISION — two different value sets propose this name"
        print(f"    {r['name']:<24} {r['members']:>5} member(s)  "
              f"{len(r['attached'])} attach point(s){flag}")
        print(f"      {', '.join(str(s) for s in r['sample'])}"
              + (" …" if r["members"] > len(r["sample"]) else ""))
        for at in r["attached"]:
            print(f"        {at}" + ("   <- owner, referenced" if at == r["owner"] else ""))
    print("\n  SEARCHABLE WITH LIKE — no register is cut for these")
    for t in text:
        print(f"    {t['at']:<44} {t['why']}")
    if p["unreadable"]:
        print("\n  NOT MEASURED")
        for k, why in p["unreadable"]:
            print(f"    {k:<44} {why}")

    unsettled = [r for r in regs if not r["settled"] or r["collides"]]
    if unsettled:
        print(f"\n  {len(unsettled)} name(s) need a person: a derived name depends on what else the "
              f"bundle holds, so it is proposed here and authored once.")
    return 0


def _self_test() -> int:
    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    # WHERE THE REFERENCE CLAUSE EARNS ITS PLACE, and it is not where it first looks like it does.
    # `dim_currency.currency_code` is 5 of 5 rows at ratio 1.0, which is what killed the plain
    # distinct/rows hypothesis — but 5 members clear the small-set clause anyway, so the reference
    # is not what rescues it. The clause is load-bearing only ABOVE the small-set line: a dimension
    # key that is near-unique AND too large to name, which other relations point at. A first
    # version of this test asserted the currency pair and passed while proving nothing.
    case("a LARGE referenced dimension key is a register though it is near-unique",
         classify(2517, 2517, True)[0] == "register")
    case("MUTANT the same column unreferenced is REFUSED — this is the only pair the clause decides",
         classify(2517, 2517, False)[0] == "searchable")
    case("a small set needs no reference to qualify — the clause is not what rescues currency",
         classify(5, 5, False)[0] == "register")
    case("a small closed set is a register however it sits — 67 states over 67 rows",
         classify(67, 67, False)[0] == "register")
    case("a vocabulary over a large relation is a register — 565 codes over 104 990 rows",
         classify(565, 104990, False)[0] == "register")
    case("MUTANT open text over the same relation is REFUSED — 99 200 names over 104 990 rows",
         classify(99200, 104990, False)[0] == "searchable")
    case("MUTANT a near-unique column on a small relation is REFUSED — 2 517 of 2 517",
         classify(2517, 2517, False)[0] == "searchable")
    case("a well-repeated but unnameable column is REFUSED — 2 571 occupations",
         classify(2571, 104990, False)[0] == "searchable")
    case("two spellings of one notion normalise equal",
         _snake("SubCategoryName") == _snake("sub_category_name") == "sub_category_name")
    case("an owner settles the name against disagreeing attach points",
         propose_name([("sales.CurrencyCode", "CurrencyCode"),
                       ("v.from_currency", "from_currency")],
                      "dim_currency.currency_code") == ("currency_code", True))
    case("agreeing attach points settle it with no owner",
         propose_name([("customer.Gender", "Gender"), ("dim_customer.gender", "gender")],
                      None) == ("gender", True))
    case("disagreeing attach points with no owner are UNSETTLED, never guessed",
         propose_name([("dim_store.store_name", "store_name"),
                       ("store.Description", "Description")], None)[1] is False)

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": mac_register_plan self-test — {ok[1]}/{ok[0]} case(s), including the hypothesis this "
            f"rule replaced: distinct/rows alone rejects dim_currency.currency_code.")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    raise SystemExit(main())
