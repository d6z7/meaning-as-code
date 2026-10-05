"""column_table — ONE renderer for the data plane's columns table.

WHY IT EXISTS. Four places rendered this table: sdk/cli/harvest.py, sdk/project/project_data.py twice,
and tools/mac_to_okf.py. Changing it on 2026-09-28 meant changing it four times — and the operator asked
for a second change to the same table the same afternoon, which is the point at which four homes stops
being a note and becomes the defect. One renderer now; the callers pass what differs.

WHAT THE CELLS SAY, and the reasoning is the operator's:

  role   `PK1`, `PK2` for a composite key, `PK` for a single-column one, `FK`, else the term itself.
         COMPOSING THE POSITION INTO THE ROLE IS RIGHT HERE AND WRONG IN THE YAML, which is not a
         contradiction: the declaration keeps `role` and `key_position` apart because a number inside a
         categorical token has to be string-parsed by every consumer that wants to sort by it (the same
         shape as StoreCode = StoreKey // 10, rejected for that reason). A markdown table is read by a
         person; nothing parses it. So the declaration stays structured and the page stays legible.
         `PK`/`FK` are DISPLAY abbreviations and are not members of mac.dataset.column.role, which is
         why `legend()` states the mapping on the page instead of leaving an agent to infer it.

  reference  where the column's values resolve: `-> relation.column` for a foreign key, or
         `register: <name>` for a declared value set. ONE COLUMN, TWO MARKED KINDS. One column because
         the reader's question is "what does this resolve against"; marked because the mechanisms are
         not the same — a foreign key points at another relation's ROW, a register is a closed set of
         VALUES with labels, and a page that renders them identically claims they are one thing.
         Measured before this was built: 24 columns across 7 of contoso4's descriptors carry a register
         pointer and the word `register` appeared 0 times in any rendered table.

NO LEGEND. An earlier version printed a paragraph above every table explaining that `PK1` is the
`primary_key` role with its `key_position`. That was my invention, not a requirement, and the operator
removed it: "we dont need the legend". `PK` and `FK` are the conventional abbreviations every reader of a
table definition already knows, and the same paragraph repeated on 42 pages is clutter, not clarity. The
principle it came from — state a vocabulary rather than leave it inferred — is real and belongs to
TOKENS a framework closes; it does not extend to two abbreviations a DBA reads at a glance.
"""

from __future__ import annotations

#: The display abbreviations. Conventional, and deliberately not explained on the page.
_ABBREV = {"primary_key": "PK", "foreign_key": "FK"}


def role_cell(col: dict) -> str:
    """`PK1` / `PK` / `FK` / `PK1 · FK` / the term. Position appended only where one is declared.

    A REFERENCE IS A SIBLING OF THE ROLE, NOT A PROPERTY OF IT — the same operator ruling that
    `fk_section` below carries, applied at the second site, which was missed when the first was
    fixed. `role` is a closed single-value vocabulary and a column that is both part of the key and
    a reference can only choose one term for it; identity wins, and the reference fact then had
    nowhere to appear in this column.

    THE ABSENCE OF A TOKEN IS READ AS A FACT. `FK` prints here for the 17 columns whose role IS
    `foreign_key`, so for the 6 that are keys AND reference a parent its absence says "not a foreign
    key", which is false. Measured 2026-09-29 across contoso5's 32 descriptors: 23 columns carry a
    reference, 17 print `FK`, 6 printed `PK1`/`PK2`/`PK3` alone —

        v_contoso5_fx_rate.date_day / .from_currency / .to_currency   (all three key parts)
        currencyexchange.Date, orderrows.OrderKey, sales.OrderKey

    The reference column beside this one always showed the arrow, so the fact was on the page
    IMPLICITLY. That is not the same as being stated: a reader scanning one column got a wrong
    answer from it. `·` is the separator this table already uses to join two facts in one cell
    (`reference_cell`), not a new convention introduced here.

    NOT A YAML CHANGE. The descriptor states both facts already, each in its own typed field:
    `role: primary_key` + `key_position: 1` + `references:`. `PK1 · FK` is a DISPLAY composition of
    two declared fields, the way `PK1` is already a composition of `role` and `key_position`, and it
    is assembled here rather than stored so that no consumer has to do string surgery on a
    vocabulary token to learn either fact (CONFORMANCE 2.4).
    """
    c = col or {}
    role = str(c.get("role") or "")
    short = _ABBREV.get(role, role)
    pos = c.get("key_position")
    if role == "primary_key" and pos:
        short = f"{short}{pos}"
    # The test is whether the column CARRIES a reference, never whether its role names one — that is
    # the filter that dropped three references from three pages in `fk_section`.
    if role != "foreign_key" and _ref_parts(c)[0]:
        short = f"{short} · FK" if short else "FK"
    return short


def reference_cell(col: dict, *, code: bool = True) -> str:
    """`-> relation.column`, or `register: <name>`. Empty when the column resolves against nothing.

    A column may carry both — a foreign key whose values also have a declared register — so both are
    shown rather than one silently winning.
    """
    c = col or {}
    parts = []
    # BOTH SHAPES. `references` was a bare target string and may now be a mapping carrying `to` plus the
    # measured cardinality and participation, so the ER diagram can be drawn from the descriptor instead
    # of from a second artifact. The CELL wants only the target — the crow's feet are the diagram's job,
    # and a table that printed `many:one` in a reference column would be restating the picture badly.
    _r = c.get("references")
    ref = str((_r.get("to") if isinstance(_r, dict) else _r) or "").strip()
    if ref:
        parts.append(f"→ `{ref}`" if code else f"→ {ref}")
    reg = str(c.get("register") or "").strip()
    if reg:
        name = reg.rsplit("/", 1)[-1]
        for suf in (".lookup.csv", ".csv"):
            if name.endswith(suf):
                name = name[: -len(suf)]
                break
        parts.append(f"register: `{name}`" if code else f"register: {name}")
    # HOW A VALUE IN THIS COLUMN IS RESOLVED is the question this cell answers, and for an open-text
    # column the answer was BLANK — indistinguishable from a column nobody had profiled. The
    # operator, 2026-09-29: "one huge table where the search criteria is text cannot be converted
    # into lookup. it should just be declared later to be searchebal with like." contoso5 carries 16
    # such columns; `dim_customer.customer_name` holds 99 200 distinct values over 104 990 rows, and
    # a register of it would be the table.
    if str(c.get("searchable") or "").strip() == "like":
        parts.append("search: `like`" if code else "search: like")
    return " · ".join(parts)


def header(*, description: bool = False) -> list[str]:
    """The two header lines, with the optional trailing `description` column."""
    cols = ["column", "type", "role", "reference"] + (["description"] if description else [])
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]


def row(col: dict, *, description: str | None = None, code: bool = True) -> str:
    """One table row. `description` None means the table has no description column."""
    name = str((col or {}).get("name") or "")
    cells = [f"`{name}`" if code else name, str((col or {}).get("type") or ""),
             role_cell(col), reference_cell(col, code=code)]
    if description is not None:
        cells.append(" ".join(str(description).split()))
    return "| " + " | ".join(cells) + " |"


def _ref_parts(col: dict) -> tuple:
    """(relation, column) from a reference, in EITHER shape it is written in.

    TWO FUNCTIONS IN THIS FILE DISAGREED ABOUT ONE SHAPE, thirty lines apart. `reference_cell`
    above has been dict-aware since the measured reference gained its cardinality block; this one
    was left on `str(...).split(".")`, and a mapping stringifies to its repr rather than failing.
    Measured 2026-09-29 in a DELIVERED bundle — contoso5/data/sources/sales.md renders the cell
    correctly on line 19 and then, fourteen lines lower, prints:

        - `OrderDate` → `{'to': 'date.Date', 'cardinality': {'child': 'many', ...}}`

    A Python dict in a page a person reads, shipped, with every gate green. This is the exact defect
    `CONSUMED` exists to name — a consumer reading a field in a shape its producer does not write —
    and it was invisible because nothing could record that this function wanted `references.to`.
    """
    _r = (col or {}).get("references")
    ref = _r.get("to") if isinstance(_r, dict) else _r
    p = [x for x in str(ref or "").split(".") if x]
    return (".".join(p[:-1]), p[-1]) if len(p) >= 2 else ((p[0] if p else ""), "")


def register_name(col: dict) -> str:
    """The register's bare name from a `data/lookups/<name>.lookup.csv` pointer."""
    reg = str((col or {}).get("register") or "").strip()
    if not reg:
        return ""
    name = reg.rsplit("/", 1)[-1]
    for suf in (".lookup.csv", ".csv"):
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def fk_section(cols) -> list:
    """`## Foreign keys` — one line per column pointing at another relation, or [] if none.

    THE SHAPE IS DECLARED, not decided here: `guardrails/data/sources.yaml#relation_page.shape`
    states the line form and `tools/check_page_shape.py` holds the DELIVERED page to it. Change
    this and the gate refuses until the declaration changes too — which is the point. Operator,
    2026-09-29: "the question is if you can do it EVERY TIME".

    THE CARDINALITY IS ON THE LINE, and it is not decoration. It was measured, it is stored on the
    descriptor, and it disappeared from the page without anybody deciding: the rationale for
    omitting it was written about the columns TABLE CELL — "the crow's feet are the diagram's job,
    and a table that printed `many:one` in a reference column would be restating the picture badly"
    — which is sound for a cell beside a diagram and not sound for a section read on its own. A
    person reading this page has no diagram in front of them, and `many:one` against `one:one` is
    the difference between a join that can multiply rows and one that cannot.

    A REFERENCE IS A SIBLING OF THE ROLE, NOT A PROPERTY OF IT (operator ruling). A column can be
    part of the primary key AND point at a parent — `sales.OrderKey` is PK1 and references
    `orders.OrderKey` — so filtering on `role == "foreign_key"` dropped three real references from
    three pages. The test is whether the column CARRIES a reference.
    """
    out = []
    for c in cols or []:
        if not isinstance(c, dict):
            continue
        rel, tgt = _ref_parts(c)
        if not rel:
            continue
        r = c.get("references")
        card = (r or {}).get("cardinality") if isinstance(r, dict) else None
        part = (r or {}).get("participation") if isinstance(r, dict) else None
        target = f"{rel}.{tgt}" if tgt else rel
        line = f"- `{c.get('name')}` → `{target}`"
        if isinstance(card, dict) and isinstance(part, dict):
            line += (f" ({card.get('child')}:{card.get('parent')}, "
                     f"{part.get('child')}:{part.get('parent')})")
        out.append(line)
    return ["", "## Foreign keys", ""] + out if out else []


def register_section(cols) -> list:
    """`## Registers` — one line per column whose values resolve through a declared value set.

    THE SIBLING OF `## Foreign keys`, and named for what the framework already calls these: the column
    field is `register`, the invariants are REGISTER-MONITOR and REGISTER-ORPHAN, and the vocabulary says
    `register` 42 times. The operator asked for a section "References ... alike to Foreign keys"; the
    intent is this section, and the NAME is `Registers` because a third word for a thing already called
    two is how `attribute` came to mean four things. The artifacts live in `data/lookups/`, so the line
    names the file a reader can open.

    WHY IT EXISTS AT ALL. Before the columns table gained a `reference` cell, a register pointer appeared
    NOWHERE on any page — 24 columns across 7 of the reference bundle's descriptors carried one and the
    word `register` occurred 0 times in any rendered page. The cell made it visible per column; this
    section makes the relation's whole resolution surface readable in one place, which is the question an
    operator actually asks ("what does this table resolve against").
    """
    out = []
    for c in cols or []:
        if not isinstance(c, dict):
            continue
        n = register_name(c)
        if n:
            out.append(f"- `{c.get('name')}` → `data/lookups/{n}.lookup.csv`")
    return ["", "## Registers", ""] + out if out else []
