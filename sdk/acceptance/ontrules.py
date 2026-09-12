"""sdk.acceptance.ontrules — read a bundle's concept rules and the relations they are grounded on.

WHAT THIS IS FOR
    The first three acceptance flags check the ORACLE's assertions: how the question should have
    been disposed of, which axes it names, what number an anchor derives. Nothing checked whether
    the engine broke a rule the ONTOLOGY itself already states — and the ontology states 83 of them
    in the reference bundle, each with an explicit ``never`` clause. ``ACME_C1.1`` filtered on the
    raw display name while ``vehicle_model.resolve.by_code_not_name`` says never to, and the board
    called that question ``proven``.

    This module is the READER for those rules. It renders no judgement: ``flags.py`` decides which
    clauses are machine-checkable and what the SQL did about them. Same seam as ``anchors.py`` —
    reading lives here, policy lives there, and the evaluator stays pure.

WHAT A RULE CARRIES, AND WHY ``binds`` IS THE LOAD-BEARING KEY
    A MAC rule is ``{id, subject, kind, binds, when, then, never}``. ``binds`` is not decoration:
    CONFORMANCE.md defines a typed rule as "anchored to the field(s) they govern", and the
    framework shape ``rule-binds-grounded`` enforces cross-file that every bound name is a column
    of the concept's grounded table. So ``binds`` is a MACHINE-READABLE set of column names, while
    ``when`` / ``then`` / ``never`` are prose. Every structural check downstream is therefore a
    statement about a bound COLUMN, and a clause that names no bound column is not checkable — a
    limit this module makes visible rather than papers over.

WHY THE RELATIONS COME ALONG
    A rule is bound to a question's ROUTE by the relations its concept is grounded on: if the run
    never read the relation, the rule cannot have been broken by it. ``grounding.sources[].relation``
    is reduced to the bare, lowercased table name so it can be matched against the relation names
    ``sqlfacts`` reads out of the executed SQL, which carry no schema qualifier and no quoting.

NO BUNDLE LITERALS, EVER
    Not one concept, column, relation or question id appears in the code below. The vocabulary
    arrives at runtime from the bundle's own ``ontology/concepts/*.yaml``. The ids quoted in this
    docstring are the measured evidence for the design — historical record, not data; no code path
    reads them, and pointing this module at another bundle touches nothing here.

I/O-BEARING BY DESIGN. Reads YAML; ``flags.py`` is handed the already-resolved list.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Where the concepts plane lives inside a bundle. One definition, used for both the scan and the
# bundle-relative `_file` path the UI turns into a link.
CONCEPTS_SUBDIR = ("ontology", "concepts")


def _bare_relation(value) -> str | None:
    """``acme2.dim_model`` / ``"cat"."schema"."t"`` -> ``dim_model`` / ``t``.

    The last dotted segment, unquoted and lowercased — exactly the form ``sqlfacts`` reports for a
    table reference, because an ontology names a relation while a query names a schema-qualified,
    possibly quoted path to the same thing. Matching those two by their bare name is what keeps the
    route binding source-agnostic; matching by the full string would bind nothing on any bundle
    whose engine qualifies its FROM clauses, which is all of them.
    """
    if not isinstance(value, str):
        return None
    name = value.strip().strip('"').strip("'")
    if not name:
        return None
    name = name.split(".")[-1].strip().strip('"').strip("'").lower()
    return name or None


def _relations(concept_doc: dict) -> list:
    """The bare relation names a concept is grounded on, sorted and deduped.

    ``grounding.sources`` entries are mappings carrying ``relation`` in every bundle seen so far,
    but a bare string is accepted too: a reader that throws on an authored shorthand takes the
    whole board down over a formatting choice.
    """
    grounding = concept_doc.get("grounding")
    grounding = grounding if isinstance(grounding, dict) else {}
    sources = grounding.get("sources")
    sources = sources if isinstance(sources, (list, tuple)) else []

    out: set = set()
    for src in sources:
        if isinstance(src, str):
            rel = _bare_relation(src)
        elif isinstance(src, dict):
            rel = _bare_relation(src.get("relation"))
        else:
            rel = None
        if rel:
            out.add(rel)
    return sorted(out)


def _binds(rule: dict) -> list:
    """``binds`` reduced to non-blank lowercase column names, order preserved, deduped.

    Lowercased because ``sqlfacts`` reduces every column reference to its bare lowercase
    identifier; comparing an authored ``Region`` against a parsed ``region`` would silently check
    nothing. Deduped because a repeated bind is an authoring slip, not two columns.
    """
    value = rule.get("binds")
    if not isinstance(value, (list, tuple)):
        return []
    out: list = []
    for item in value:
        if not isinstance(item, str):
            continue
        name = item.strip().lower()
        if name and name not in out:
            out.append(name)
    return out


def build_index(bundle: Path) -> dict:
    """Every concept rule in the bundle, with its concept's relations attached.

    Returns::

        {
          "rules": [ {                       # in (file, authored) order
              "id":       str,               # the authored rule id
              "concept":  str,               # the concept file stem
              "subject":  str | None,
              "kind":     str | None,
              "binds":    [str],             # lowercased column names
              "never":    str | None,        # the prohibition, VERBATIM
              "relations":[str],             # bare lowercase names the concept is grounded on
              "file":     str,               # bundle-relative, for the UI's file link
          } ],
          "count":    int,                   # rules that entered the index
          "concepts": int,                   # concept documents that loaded
          "errors":   [{"file": str, "error": str}],
        }

    A rule with no ``never`` clause is SKIPPED: this index exists to serve a check about
    prohibitions, and carrying rules that prohibit nothing would inflate every denominator the
    flag reports without adding a single checkable claim.

    A YAML or shape failure never stops the scan — the file lands in ``errors`` and the other
    concepts keep working. One malformed concept must not blank the rules column of the whole
    board.
    """
    root = Path(bundle)
    directory = root.joinpath(*CONCEPTS_SUBDIR)
    # Sorted so the index is reproducible: glob order is filesystem order, not a contract.
    files = sorted(directory.glob("*.yaml")) if directory.is_dir() else []

    rules: list[dict] = []
    errors: list[dict] = []
    concepts = 0

    for path in files:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:  # pragma: no cover - only reachable on a symlinked bundle
            rel = path.as_posix()
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as err:
            errors.append(
                {"file": rel, "error": f"{type(err).__name__}: {' '.join(str(err).split())[:300]}"}
            )
            continue
        if not isinstance(doc, dict):
            errors.append(
                {"file": rel, "error": f"expected a YAML mapping, got {type(doc).__name__}"}
            )
            continue

        concepts += 1
        contract = doc.get("contract")
        contract = contract if isinstance(contract, dict) else {}
        authored = contract.get("rules")
        authored = authored if isinstance(authored, (list, tuple)) else []
        relations = _relations(doc)

        for rule in authored:
            if not isinstance(rule, dict):
                continue
            never = rule.get("never")
            if not isinstance(never, str) or not never.strip():
                continue
            rid = rule.get("id")
            rules.append(
                {
                    "id": rid.strip() if isinstance(rid, str) and rid.strip() else path.stem,
                    "concept": path.stem,
                    "subject": rule.get("subject")
                    if isinstance(rule.get("subject"), str)
                    else None,
                    "kind": rule.get("kind") if isinstance(rule.get("kind"), str) else None,
                    "binds": _binds(rule),
                    "never": never,
                    "relations": relations,
                    "file": rel,
                }
            )

    return {"rules": rules, "count": len(rules), "concepts": concepts, "errors": errors}
