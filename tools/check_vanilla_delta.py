#!/usr/bin/env python3
"""check_vanilla_delta — every difference from the GENERATED bundle is registered, at its LOCUS.

WHY THIS EXISTS AND WHY IT IS NOT check_intervention_ledger
-----------------------------------------------------------
The ledger already proves that every authored/tuned OBJECT has a protocol entry, and that gate is
green. It was green while a real defect sat unrecorded inside a covered object: `transform:dim_model`
carried INT-0001 ("full harmonization of the raw EAV model dimension"), which is a true statement and
tells you nothing about the two hand-written regex token lists inside that file — one of which had
been extended past gold's and was folding a distinct nameplate (Golf Plus) into another model.

Object-level protocol is not locus-level protocol. An entry that names the object answers "was this
touched"; this register answers "what, precisely, is different from what the generator emits, and has
anyone agreed to it". Those are different questions and they need different registers:

    ledger.yaml         append-only HISTORY  — which objects were touched, and why
    vanilla_delta.yaml  current STATE        — what differs from vanilla right now

A delta entry is DELETED when the delta is removed. A ledger entry never is.

WHAT IS CHECKED
  A. ERROR — an object stamped `metadata.provenance: authored|tuned` with no delta entry.
  B. ERROR — a duplicate delta id; a missing required key; a status/ratified shape outside its set.
  C. ERROR — `file:` naming a path that does not exist, or `ledger_ref:` naming an unknown intervention.
  D. ERROR — an empty or placeholder `baseline:`. The baseline is the load-bearing field: an entry that
             cannot say what the generator produces has not found its own baseline. This is the one
             check that stops the register decaying into a list of titles.
  E. WARN  — a delta with `status: applied` and no ratification. Legitimate for a bundle under
             construction; it stops being legitimate the moment an answer is treated as authoritative.
  F. WARN  — an entry whose object is no longer stamped authored/tuned (the delta may have been
             reverted and the entry left behind).

Warn-only until the register exists, so adopting it is never a breaking change.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: pip install pyyaml")

REGISTER = "interventions/vanilla_delta.yaml"
LEDGER = "interventions/ledger.yaml"
MANUAL = ("authored", "tuned")
STATUSES = ("open", "applied", "reverted")
REQUIRED = ("id", "objects", "file", "locus", "baseline", "delta", "why",
            "evidence", "ledger_ref", "introduced", "ratified", "status")

# A baseline that says nothing is worse than no entry: it looks like protocol and carries none.
PLACEHOLDER = ("", "tbd", "todo", "unknown", "n/a", "na", "-", "none", "?")


def _load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        return {"__error__": str(e)}


def _provenance(p: Path) -> str | None:
    d = _load(p)
    if not isinstance(d, dict):
        return None
    return ((d.get("metadata") or {}) if isinstance(d.get("metadata"), dict) else {}).get("provenance")


def _entries(doc, key: str) -> list:
    if isinstance(doc, dict):
        v = doc.get(key)
        return v if isinstance(v, list) else []
    return doc if isinstance(doc, list) else []


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_vanilla_delta.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    # ---- index the objects that CAN carry a delta (harvested ones cannot: re-harvest overwrites) ----
    dirs = {
        "source": root / "data" / "sources",
        "transform": root / "data" / "transforms",
        "dataset": root / "data" / "datasets",
        "concept": root / "ontology" / "concepts",
    }
    stamps: dict[str, str | None] = {}
    for otype, d in dirs.items():
        if not d.is_dir():
            continue
        found = sorted(d.rglob("*.yaml")) if otype == "concept" else sorted(d.glob("*.yaml"))
        for p in found:
            stamps.setdefault(f"{otype}:{p.stem}", _provenance(p))

    manual = {k for k, v in stamps.items() if v in MANUAL}
    n_harvested = sum(1 for v in stamps.values() if v == "harvested")

    reg_path = root / REGISTER
    if not reg_path.exists():
        print(f"── vanilla-delta gate ── no {REGISTER} under {root} ──\n")
        print(f"  [WARN]  the vanilla delta is unregistered: {len(manual)} object(s) are stamped "
              f"authored/tuned, so they differ from what the generator emits, and nothing records HOW")
        print(f"\n✓ OK — register not yet adopted (warn-only until {REGISTER} exists)")
        return 0

    doc = _load(reg_path)
    if "__error__" in doc:
        print(f"✗ {REGISTER} does not parse: {doc['__error__']}")
        return 1
    deltas = _entries(doc, "deltas")

    ledger_ids = {str(e.get("id")) for e in _entries(_load(root / LEDGER), "interventions")
                  if isinstance(e, dict)}

    errors: list[str] = []
    warns: list[str] = []
    seen: set[str] = set()
    covered: set[str] = set()

    for i, e in enumerate(deltas):
        label = (e.get("id") if isinstance(e, dict) else None) or f"#{i}"
        if not isinstance(e, dict):
            errors.append(f"delta '{label}' is not a mapping")
            continue

        for k in REQUIRED:
            if k not in e or e[k] in (None, ""):
                errors.append(f"delta '{label}' is missing required key `{k}`")

        did = str(e.get("id") or "")
        if did in seen:
            errors.append(f"duplicate delta id '{did}'")
        seen.add(did)

        # A delta routinely spans a PAIR — renaming a served view changes the transform and its
        # dataset descriptor together — so `objects` is a list, the same shape the ledger uses.
        objs = e.get("objects")
        objs = objs if isinstance(objs, list) else ([objs] if objs else [])
        if not objs:
            errors.append(f"delta '{label}' names no objects")
        for obj in (str(o) for o in objs):
            covered.add(obj)
            if obj not in stamps:
                errors.append(f"delta '{label}' names object '{obj}', which is not on disk")
            elif stamps.get(obj) not in MANUAL:
                warns.append(f"delta '{label}' names '{obj}', stamped '{stamps.get(obj)}' — "
                             f"if the delta was reverted, delete the entry")

        f = str(e.get("file") or "")
        if f and not (root / f).exists():
            errors.append(f"delta '{label}' names file '{f}', which does not exist")

        lr = str(e.get("ledger_ref") or "")
        if lr and ledger_ids and lr not in ledger_ids:
            errors.append(f"delta '{label}' references unknown intervention '{lr}'")

        st = str(e.get("status") or "")
        if st and st not in STATUSES:
            errors.append(f"delta '{label}' has status '{st}' outside {list(STATUSES)}")

        base = str(e.get("baseline") or "").strip().lower().rstrip(".")
        if base in PLACEHOLDER:
            errors.append(f"delta '{label}' has an empty or placeholder `baseline` — an entry that "
                          f"cannot state what the generator produces has not found its own baseline")

        rat = e.get("ratified")
        if isinstance(rat, dict):
            if st == "applied" and not rat.get("by"):
                warns.append(f"delta '{label}' is applied but unratified")
        elif "ratified" in e:
            errors.append(f"delta '{label}' has a `ratified` that is not a mapping of by/date")

    for m in sorted(manual - covered):
        errors.append(f"object '{m}' is stamped '{stamps[m]}' — it differs from the generated bundle "
                      f"and has NO entry in {REGISTER}")

    print(f"── vanilla-delta gate ── {len(deltas)} delta(s) over {len(stamps)} object(s) "
          f"[{n_harvested} harvested / {len(manual)} authored+tuned] under {root} ──\n")
    for w in warns:
        print(f"  [WARN]  {w}")
    for x in errors:
        print(f"  [ERROR] {x}")

    unratified = sum(1 for e in deltas if isinstance(e, dict)
                     and isinstance(e.get("ratified"), dict) and not e["ratified"].get("by"))
    open_n = sum(1 for e in deltas if isinstance(e, dict) and e.get("status") == "open")
    if deltas:
        print(f"\n  {unratified} of {len(deltas)} delta(s) carry no SME ratification; "
              f"{open_n} still open")

    if errors:
        print(f"\n✗ {len(errors)} vanilla-delta defect(s) — an unregistered difference from the "
              f"generated bundle, or a malformed entry ({len(warns)} warning(s))")
        return 1
    print(f"\n✓ OK — every authored/tuned object registers its delta from vanilla "
          f"({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
