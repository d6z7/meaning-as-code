#!/usr/bin/env python3
"""check_intervention_ledger.py — the CHANGE-PROTOCOL gate.

Every object in a bundle got there one of two ways: it was AUTODISCOVERED (emitted by the harvest from
what the warehouse actually contains) or it was MANUALLY TUNED (a human — or an agent acting as one —
authored it, corrected it, retired it). Both are legitimate. What is NOT legitimate is a manual
intervention nobody can see: an authored lookup, a hand-edited transform rule, a concept whose meaning
was decided rather than observed, sitting in the tree with no record of WHO changed WHAT, WHY, on what
EVIDENCE, and who must RATIFY it. That is how a judgement call silently becomes "the data".

So the protocol is: an object may be stamped `metadata.provenance: harvested | authored | tuned`, and
every `authored`/`tuned` stamp must be answered by an entry in the bundle's ledger —
`interventions/ledger.yaml` — naming the objects touched, the DQ findings addressed, the what/why, the
evidence, and the status (proposed -> applied -> ratified).

This gate makes an unprotocolled manual change impossible to ship:
  A. WARN  — no interventions/ledger.yaml at all: the protocol is not yet established (warn-first, so
             existing bundles adopt it incrementally). Exit 0.
  B. ERROR — a duplicate intervention id; a missing required key; a kind/status/actor outside its set.
  C. ERROR — an `objects[]` entry that resolves to no file on disk (or carries an unknown type prefix).
  D. ERROR — a `dq_ids[]` entry absent from data/quality/data_quality_register.yaml.
  E. ERROR — an object stamped `authored`/`tuned` that NO intervention references (the core teeth: a
             manual change with no protocol entry).
  F. WARN  — an object carrying no `metadata.provenance` stamp at all (adoption warning).

OFFLINE + pure-structural (files on disk, no AWS).
Usage:  python3 tools/check_intervention_ledger.py <bundle-root>
        exit 0 = every manual intervention is protocolled ; exit 1 = an unprotocolled or malformed one.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_project import resolve  # noqa: E402

REQUIRED = ("id", "date", "actor", "kind", "objects", "what", "why", "status")
KINDS = {"authored", "tuned", "retired"}
STATUSES = {"proposed", "applied", "ratified"}
ACTORS = {"claude", "operator", "sme"}
PROVENANCE = {"harvested", "authored", "tuned"}
MANUAL = {"authored", "tuned"}          # the stamps that demand a ledger entry
LEDGER = "interventions/ledger.yaml"


def _load(p: Path):
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] cannot parse {p}: {e}")
        return None


def _plane(layout_dir, root: Path, fallback: str) -> Path:
    """The declared plane dir (mac.project.yaml) when it exists, else the conventional layout."""
    declared = Path(layout_dir) if layout_dir else None
    if declared and declared.is_dir():
        return declared
    fb = root / fallback
    return fb if fb.is_dir() else (declared or fb)


def _rel(p: Path, root: Path) -> str:
    """A path shown relative to the bundle root when it lives inside it."""
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _provenance(p: Path) -> str | None:
    doc = _load(p)
    if not isinstance(doc, dict):
        return None
    md = doc.get("metadata")
    if not isinstance(md, dict):
        return None
    v = md.get("provenance")
    return str(v).strip().lower() if isinstance(v, str) and v.strip() else None


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_intervention_ledger.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    L = resolve(root)
    dirs = {
        "source": _plane(L.sources, root, "data/sources"),
        "transform": _plane(L.transforms, root, "data/transforms"),
        "dataset": _plane(L.descriptors, root, "data/datasets"),
        "concept": _plane(Path(L.ontology) / "concepts", root, "ontology/concepts"),
        "lookup": root / "data" / "lookups",
    }

    # ---- index every object in the data + ontology planes, with its provenance stamp --------------
    # The concepts plane may be flat (fpl2) or foldered by domain (the gold: concepts/brand/brand.yaml),
    # so it is walked recursively; the data planes are flat by contract.
    files: dict[str, Path] = {}                 # "<type>:<stem>" -> file
    stamps: dict[str, str | None] = {}          # "<type>:<stem>" -> provenance | None
    for otype, d in dirs.items():
        if not d.is_dir():
            continue
        found = sorted(d.glob("*.csv")) if otype == "lookup" else (
            sorted(d.rglob("*.yaml")) if otype == "concept" else sorted(d.glob("*.yaml")))
        for p in found:
            stem = p.stem[:-len(".lookup")] if otype == "lookup" and p.stem.endswith(".lookup") else p.stem
            key = f"{otype}:{stem}"
            files.setdefault(key, p)
            stamps.setdefault(key, None if otype == "lookup" else _provenance(p))

    def _object_file(otype: str, stem: str) -> Path | None:
        return files.get(f"{otype}:{stem}")
    n_harvested = sum(1 for v in stamps.values() if v == "harvested")
    n_manual = sum(1 for v in stamps.values() if v in MANUAL)
    # lookups are CSV registers — they carry no metadata block, so they are never counted as unstamped
    n_unstamped = sum(1 for k, v in stamps.items() if v is None and not k.startswith("lookup:"))

    ledger_path = root / LEDGER
    if not ledger_path.exists():
        print(f"── intervention-ledger gate ── no {LEDGER} under {root} ──\n")
        print(f"  [WARN]  the change protocol is not established: {LEDGER} is absent, so manual "
              f"interventions (authored/tuned objects) are unrecorded — {len(stamps)} object(s) on disk, "
              f"{n_manual} stamped authored/tuned, {n_unstamped} carrying no provenance stamp")
        print(f"\n✓ OK — 0 intervention(s); protocol not yet adopted (warn-only until "
              f"{LEDGER} exists)")
        return 0

    doc = _load(ledger_path)
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        print(f"── intervention-ledger gate ── {LEDGER} under {root} ──\n")
        print(f"  [ERROR] {LEDGER} is not a mapping (expected metadata: + interventions:)")
        print("\n✗ 1 malformed ledger")
        return 1
    entries = doc.get("interventions")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        errors.append("`interventions:` must be a list")
        entries = []

    reg = _load((root / "data" / "quality" / "data_quality_register.yaml")) or {}
    issue_ids = {i.get("id") for i in (reg.get("issues") or reg.get("findings") or [])
                 if isinstance(i, dict) and i.get("id")}

    referenced: set[str] = set()
    seen_ids: set[str] = set()

    for n, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            errors.append(f"intervention #{n} is not a mapping")
            continue
        iid = e.get("id") if isinstance(e.get("id"), str) else None
        dup = bool(iid) and iid in seen_ids
        label = (f"{iid} (#{n})" if dup else iid) or f"#{n}"
        # B — shape
        if dup:
            errors.append(f"intervention id '{iid}' is duplicated (entry #{n}) — an id must name exactly "
                          f"one intervention")
        if iid:
            seen_ids.add(iid)
        for k in REQUIRED:
            if e.get(k) in (None, "", []):
                errors.append(f"intervention '{label}' is missing required key `{k}`")
        for key, allowed in (("kind", KINDS), ("status", STATUSES), ("actor", ACTORS)):
            v = e.get(key)
            if v is not None and v not in allowed:
                errors.append(f"intervention '{label}' {key} '{v}' not in {sorted(allowed)}")
        # C — objects resolve
        objs = e.get("objects")
        if objs is not None and not isinstance(objs, list):
            errors.append(f"intervention '{label}' `objects` must be a list of '<type>:<stem>'")
            objs = []
        for o in (objs or []):
            if not isinstance(o, str) or ":" not in o:
                errors.append(f"intervention '{label}' object '{o}' is malformed — expected "
                              f"'<type>:<stem>' with type in {sorted(dirs)}")
                continue
            otype, stem = o.split(":", 1)
            otype, stem = otype.strip(), stem.strip()
            if otype not in dirs:
                errors.append(f"intervention '{label}' object '{o}' has unknown type '{otype}' — "
                              f"expected one of {sorted(dirs)}")
                continue
            referenced.add(f"{otype}:{stem}")
            # A RETIRED object is GONE by definition — its file must NOT exist. Requiring resolution
            # there would make it impossible to protocol a removal, which is exactly the kind of manual
            # change that most needs a record. So existence is only enforced for authored/tuned.
            if e.get("kind") != "retired" and _object_file(otype, stem) is None:
                errors.append(f"intervention '{label}' object '{o}' resolves to no file "
                              f"(looked under {_rel(dirs[otype], root)}/)")
        # D — dq ids exist
        dq = e.get("dq_ids")
        if dq is not None and not isinstance(dq, list):
            errors.append(f"intervention '{label}' `dq_ids` must be a list")
            dq = []
        for d in (dq or []):
            if d not in issue_ids:
                errors.append(f"intervention '{label}' cites dq_id '{d}' — not in "
                              f"data/quality/data_quality_register.yaml")

    # ---- E + F : every manual stamp is answered by the ledger -------------------------------------
    unprotocolled: list[str] = []
    for key, prov in sorted(stamps.items()):
        if prov is None:
            if key.split(":", 1)[0] != "lookup":
                warnings.append(f"{key} carries no `metadata.provenance` stamp — mark it harvested / "
                                f"authored / tuned so manual work is distinguishable from harvest output")
            continue
        if prov not in PROVENANCE:
            warnings.append(f"{key} provenance '{prov}' not in {sorted(PROVENANCE)} — treated as unstamped")
            continue
        if prov in MANUAL and key not in referenced:
            unprotocolled.append(key)
            errors.append(f"{key} is stamped provenance '{prov}' but NO intervention in {LEDGER} "
                          f"references it — a manual change with no protocol entry")

    print(f"── intervention-ledger gate ── {len(entries)} intervention(s), {len(stamps)} object(s) "
          f"[{n_harvested} harvested / {n_manual} authored+tuned / {n_unstamped} unstamped], "
          f"{len(unprotocolled)} unprotocolled under {root} ──\n")
    for w in warnings:
        print(f"  [WARN]  {w}")
    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"✗ {len(errors)} change-protocol defect(s) — an unprotocolled manual change or a "
              f"malformed ledger entry ({len(warnings)} warning(s))")
        return 1
    print(f"✓ OK — every authored/tuned object is protocolled in {LEDGER}"
          + (f" ({len(warnings)} warning(s))" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
