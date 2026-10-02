"""The bundle's naming REGISTERS, read — so a code and its label are not two answers.

WHY THIS EXISTS. Operator, 2026-10-02: "why are you patching ANSWERS instead of IMPLEMENTING
missing readers to use the catalog?!" `mac_vocabulary.yaml` declares 21 closed vocabularies and
only two had a reader; `name_register` (`code | common | legal | long`) was one of the nineteen
that did not, and this bundle declares against it.

THE DEFECT IT REMOVES, measured on AGG-10 "Show net revenue by customer country":

    approved   [["US", 111862187.56],         ["DE", 24638830.18],   ...]
    produced   [["United States", 111862187.56017], ["Germany", 24638830.1795], ...]

The NUMBERS agree to the cent. `country_name` is ruled `label_of: country_code` with
`register: long` (operator ruling, 2026-09-30) and the planner honours it exactly -- `sql.py` groups
on the code and DISPLAYS the label, which is what the vocabulary says to do. So the engine was
right, the reference was right, and the grader called them different because nothing read the
register that says `US` and `United States` are one country under two namings. Two questions failed
for a reason that was declared in the bundle and unread.

NOT FUZZY MATCHING. A register is a CLOSED, authored mapping: the pair is in the file or it is not.
Nothing here normalises beyond case and surrounding whitespace, nothing stems, nothing guesses --
`Deutschland` does not match `DE` unless a register says so.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

#: The register files a bundle carries, as `data/lookups/<name>.lookup.csv`. Two columns is the
#: shape this reads: a code and a name. Wider files are read on their first two columns, which is
#: what a `<thing>_code -> <thing>_name` lookup is.
LOOKUPS = "data/lookups"


def _fold(v: object) -> str:
    return " ".join(str(v).split()).casefold()


@lru_cache(maxsize=16)
def equivalents(bundle: str) -> dict[str, frozenset[str]]:
    """`folded value -> every folded value naming the same thing`, over every register in the bundle.

    Symmetric and transitive within a row: a code maps to its names and each name back to the code,
    so a comparison may be made in either direction without knowing which register a reference was
    authored in.
    """
    root = Path(bundle) / LOOKUPS
    groups: dict[str, set[str]] = {}
    if not root.is_dir():
        return {}
    for path in sorted(root.glob("*.lookup.csv")):
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                for row in csv.reader(fh):
                    cells = [c for c in row if str(c).strip()]
                    if len(cells) < 2:
                        continue
                    keys = {_fold(c) for c in cells[:2]}
                    # SKIP THE HEADER by shape, not by position: `country_code,country_name` names
                    # columns, not values, and a register whose first row is a header would
                    # otherwise make the two COLUMN NAMES equivalent to each other.
                    if any(k.endswith(("_code", "_name", "_key", "_id")) for k in keys):
                        continue
                    merged: set[str] = set()
                    for k in keys:
                        merged |= groups.get(k, set())
                    merged |= keys
                    for k in merged:
                        groups[k] = merged
        except Exception:  # noqa: BLE001 - an unreadable register must not fail a grading run
            continue
    return {k: frozenset(v) for k, v in groups.items()}


def same_thing(bundle: str | Path, a: object, b: object) -> bool:
    """Do `a` and `b` name the same thing under some register this bundle declares?

    Exact (folded) equality first, so a bundle with no registers behaves exactly as before.
    """
    fa, fb = _fold(a), _fold(b)
    if fa == fb:
        return True
    if not fa or not fb:
        return False
    eq = equivalents(str(bundle))
    return fb in eq.get(fa, frozenset())


__all__ = ["equivalents", "same_thing"]
