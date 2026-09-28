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
         `PK`/`FK` are DISPLAY abbreviations and are not members of mac.relation.column.role, which is
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
    """`PK1` / `PK` / `FK` / the term. Position appended only where one is declared."""
    role = str((col or {}).get("role") or "")
    short = _ABBREV.get(role, role)
    pos = (col or {}).get("key_position")
    if role == "primary_key" and pos:
        return f"{short}{pos}"
    return short


def reference_cell(col: dict, *, code: bool = True) -> str:
    """`-> relation.column`, or `register: <name>`. Empty when the column resolves against nothing.

    A column may carry both — a foreign key whose values also have a declared register — so both are
    shown rather than one silently winning.
    """
    c = col or {}
    parts = []
    ref = str(c.get("references") or "").strip()
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
    """(relation, column) from a `relation.column` reference, or ('','')."""
    p = [x for x in str((col or {}).get("references") or "").split(".") if x]
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
    """`## Foreign keys` — one line per column pointing at another relation, or [] if none."""
    out = []
    for c in cols or []:
        if not isinstance(c, dict) or str(c.get("role")) != "foreign_key":
            continue
        rel, tgt = _ref_parts(c)
        if rel:
            out.append(f"- `{c.get('name')}` → `{rel}.{tgt}`" if tgt else f"- `{c.get('name')}` → `{rel}`")
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
