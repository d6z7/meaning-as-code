#!/usr/bin/env python3
"""check_projection_field_parity — a projection may not silently drop a field its source declares.

WHY THIS EXISTS
---------------
`data/quality/dq_dashboard.json` is the only structured artifact the console's Data Quality page
reads, and its per-finding dict is a HAND-WRITTEN ALLOW-LIST of `iss.get("...")` calls. `status`,
`ruled_by` and `reason` were not in it. The register is loaded whole, so every value was in memory
and none was emitted.

MEASURED: on a register carrying `status` on 6 of 6 entries (4 `open`, 2 `accepted` with `ruled_by`
and `reason`), the projected dashboard carried `status` on 0 of 6 — every issue arrived at the
console as `status: None`, including two the operator had ruled BY NAME. `mac_vocabulary.yaml`'s own
header calls an issue a named human examined and tolerated, and an issue no human has ever read,
"THE TWO MOST DIFFERENT THINGS IN THE REGISTER" — and the page could not tell them apart.

That was fixed where it appeared. Nothing stops the next instance: the allow-list is still a list,
the source still declares more keys than any one page shows, and no gate in tools/ compares a
projection's fields to its source's. check_dq_resolution_sync gates the register's OWN fields, not
the projection of them. The only guard was four unit tests over one projector.

HOW IT IS TESTED: BY RUNNING THE REAL PROJECTOR, NOT BY READING IT
------------------------------------------------------------------
A static walk over the allow-list would be defeated by the first author who writes a comprehension
instead of a dict literal. So the gate BUILDS a synthetic source document carrying every declared
key with a distinctive sentinel value, runs the REAL projector over it, and asks of each key: did
that value reach the projection? A key read and then renamed away, or read and then dropped by a
later edit, fails exactly like a key never read.

WHERE THE DECLARED KEY SET COMES FROM — two authorities, both machine-readable, both in this repo:
  * `mac.schema.json#$defs.<Source>.properties.<items>.properties` — the schema's own field list.
  * `mac_vocabulary.yaml#<block>` — the closed value set that governs a field, plus every field its
    terms `require`. This is the authority that carries `status`, `ruled_by` and `reason`: the three
    fields A3 dropped are declared by the vocabulary, NOT by the schema, which is why a schema-only
    gate would have been green through the whole defect.
Neither authority is prose, and neither lives in another repo.

DELIBERATE OMISSION IS LEGITIMATE — AND MUST BE NAMED WITH A REASON
-------------------------------------------------------------------
A roll-up page is a summary by design; demanding every field reach every surface would forbid the
one honest pattern. So a projector DECLARES what it does not carry, in a module-level table beside
the builder, and the gate reads that table. An omission with no reason is a finding; a key that is
neither carried nor declared is a finding. The omission table is also checked the other way round:
a key declared omitted that the projection DOES carry is a stale claim, and a key declared omitted
that the source does not declare at all is an omission of nothing — both are reported, because an
omission table nobody checks rots into the same confident wrong answer as the prose it replaced.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case
------------------------------------------------------
* A KEY WHOSE VALUE IS LEGITIMATELY TRANSFORMED. A sentinel is a substring test, not equality, so a
  projector that truncates, slugifies or wraps a value still passes. A projector that HASHES or
  re-codes one would false-fire, and the remedy is a declared omission with that as its reason.
* A SURFACE THAT IS NOT A PROJECTION OF THAT SOURCE. Only declared (source, projection) pairs are
  judged. That is a small population and the PASS line prints it, so a green line can never be read
  as "every projection in the estate carries every field".

    exit 0 = every declared field reaches every declared projection, or is declared omitted
         1 = one is silently dropped (or an omission claim is stale)
         2 = could not run: the authorities, the projector or the key set could not be resolved
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys

NAME = "check_projection_field_parity"

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_TOOLS)
for _p in (_TOOLS, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SENTINEL = "ALPHASENTINEL{}BETA"          # alpha/beta/gamma only; nothing real, nothing domain-ish


# ── the declared pairs ──────────────────────────────────────────────────────────────────────────
#: ONE ENTRY PER (source of truth, projection of it). `keys` names the two authorities; `omits`
#: names the module-level table the projector itself declares. Adding a pair is how this gate's
#: coverage grows, and its denominator is printed so the coverage is never over-read.
PAIRS: tuple[dict, ...] = (
    {
        "id": "dq-register -> dq_dashboard.json",
        "source": "data/quality/data_quality_register.yaml",
        "schema_def": "DataQualityRegisterFile",
        "schema_items": "issues",
        "vocabulary_block": "dq_status",
        "vocabulary_field": "status",
        "projection": "data/quality/dq_dashboard.json",
        "kind": "json-per-item",
        "omits": ("sdk.project.project_data", "DQ_DASHBOARD_OMITS"),
    },
    {
        "id": "dq-register -> per-issue page",
        "source": "data/quality/data_quality_register.yaml",
        "schema_def": "DataQualityRegisterFile",
        "schema_items": "issues",
        "vocabulary_block": "dq_status",
        "vocabulary_field": "status",
        "projection": "data/quality/*.md",
        "kind": "markdown-per-item",
        "omits": ("sdk.project.project_data", "DQ_ISSUE_PAGE_OMITS"),
    },
    {
        "id": "dq-register -> 0-issues-overview.md",
        "source": "data/quality/data_quality_register.yaml",
        "schema_def": "DataQualityRegisterFile",
        "schema_items": "issues",
        "vocabulary_block": "dq_status",
        "vocabulary_field": "status",
        "projection": "data/quality/0-issues-overview.md",
        "kind": "markdown-rollup",
        "omits": ("sdk.project.project_data", "DQ_OVERVIEW_OMITS"),
    },
)


class CouldNotRun(Exception):
    pass


def declared_keys(pair: dict) -> tuple[dict, list]:
    """The source's declared field set, from the schema AND the governing vocabulary."""
    keys, where = {}, []

    sp = os.path.join(_REPO, "mac.schema.json")
    if not os.path.isfile(sp):
        raise CouldNotRun(f"mac.schema.json not found at {sp}")
    schema = json.load(open(sp, encoding="utf-8"))
    node = ((schema.get("$defs") or {}).get(pair["schema_def"]) or {})
    props = (((node.get("properties") or {}).get(pair["schema_items"]) or {})
             .get("items") or {}).get("properties") or {}
    if not props:
        raise CouldNotRun(
            f"mac.schema.json#$defs.{pair['schema_def']}.properties.{pair['schema_items']}"
            f".items.properties declares 0 field(s) — the schema authority resolved to nothing")
    for k in props:
        keys[k] = "mac.schema.json"
    where.append(f"mac.schema.json#$defs.{pair['schema_def']} ({len(props)} field(s))")

    import yaml
    vp = os.path.join(_REPO, "mac_vocabulary.yaml")
    if not os.path.isfile(vp):
        raise CouldNotRun(f"mac_vocabulary.yaml not found at {vp}")
    voc = yaml.safe_load(open(vp, encoding="utf-8")) or {}
    block = voc.get(pair["vocabulary_block"])
    if not isinstance(block, dict):
        raise CouldNotRun(f"mac_vocabulary.yaml declares no `{pair['vocabulary_block']}` block")
    terms = block.get("terms") or {}
    req = set()
    for t in terms.values():
        for r in ((t or {}).get("requires") or []):
            req.add(str(r))
    if not terms:
        raise CouldNotRun(
            f"mac_vocabulary.yaml#{pair['vocabulary_block']}.terms is empty — the vocabulary "
            f"authority resolved to nothing, and 0 governed field(s) is not the same as parity")
    if not req:
        # THE REACHABLE EMPTINESS. `requires: [ruled_by, reason]` is what makes this gate able to
        # see A3 at all. If it is ever emptied, this gate must refuse rather than pass over the two
        # fields it no longer knows about.
        raise CouldNotRun(
            f"mac_vocabulary.yaml#{pair['vocabulary_block']} declares {len(terms)} term(s) and NOT "
            f"ONE `requires` field — the fields that carry the evidence a human ruled are exactly "
            f"the ones this gate exists to follow, so an empty `requires` is a refusal, not a pass")
    keys[pair["vocabulary_field"]] = f"mac_vocabulary.yaml#{pair['vocabulary_block']}"
    for r in sorted(req):
        keys[r] = f"mac_vocabulary.yaml#{pair['vocabulary_block']}.terms[*].requires"
    where.append(f"mac_vocabulary.yaml#{pair['vocabulary_block']} "
                 f"(1 governed field + {len(req)} required by its terms)")
    return keys, where


def _omissions(pair: dict) -> dict:
    mod_name, attr = pair["omits"]
    try:
        mod = importlib.import_module(mod_name)
    except Exception as exc:                                       # noqa: BLE001
        raise CouldNotRun(f"could not import the projector {mod_name}: {exc}") from exc
    if not hasattr(mod, attr):
        raise CouldNotRun(
            f"{mod_name} declares no `{attr}` — a projection's deliberate omissions must be stated "
            f"beside the builder, with a reason each, or 'carried' and 'dropped' are the same fact")
    table = getattr(mod, attr)
    if not isinstance(table, dict):
        raise CouldNotRun(f"{mod_name}.{attr} is not a mapping of field -> reason")
    return dict(table)


def _synthetic_bundle(tmp: str, keys: list) -> str:
    """The smallest bundle the projector will run over: a register, and nothing else. Every declared
    key carries a sentinel, so 'did this field reach the page' is a substring question."""
    import yaml
    q = os.path.join(tmp, "data", "quality")
    os.makedirs(q, exist_ok=True)
    issue = {k: SENTINEL.format(k.upper().replace("_", "")) for k in keys}
    issue["id"] = "DQ-ALPHA-01"            # the id is the page's own filename; it must stay an id
    doc = {"metadata": {"status": "draft"}, "issues": [issue]}
    with open(os.path.join(q, "data_quality_register.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
    return os.path.join(tmp, "data")


def _project(data_dir: str) -> None:
    from sdk.project import project_data as P
    P.build_data(data_dir)


def _projected_text(data_dir: str, pair: dict) -> str:
    """The projection, as text. JSON is compared as text too: a sentinel is a value, and a value
    that reached the file reached it under SOME key — which is the question."""
    import glob as _g
    pat = os.path.join(os.path.dirname(data_dir), pair["projection"])
    hits = [h for h in _g.glob(pat) if os.path.isfile(h)]
    if pair["kind"] == "markdown-per-item":
        hits = [h for h in hits if os.path.basename(h).startswith("DQ-")]
    if not hits:
        raise CouldNotRun(
            f"the projector wrote no `{pair['projection']}` for a register that declares one "
            f"issue — the projection under test does not exist, which proves nothing about parity")
    return "\n".join(open(h, encoding="utf-8").read() for h in sorted(hits))


def evaluate(pair: dict) -> dict:
    import tempfile

    keys, authorities = declared_keys(pair)
    omits = _omissions(pair)
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = _synthetic_bundle(tmp, list(keys))
        _project(data_dir)
        text = _projected_text(data_dir, pair)

    carried, dropped, declared_ok, stale, phantom = [], [], [], [], []
    for k in sorted(keys):
        hit = SENTINEL.format(k.upper().replace("_", "")) in text or (
            k == "id" and "DQ-ALPHA-01" in text)
        if hit:
            carried.append(k)
            if k in omits:
                stale.append(k)
        elif k in omits:
            if str(omits[k]).strip():
                declared_ok.append(k)
            else:
                dropped.append(k)                  # declared omitted with no reason is not declared
        else:
            dropped.append(k)
    for k in omits:
        if k not in keys:
            phantom.append(k)
    return {"pair": pair, "keys": keys, "authorities": authorities, "omits": omits,
            "carried": carried, "dropped": dropped, "declared": declared_ok,
            "stale": stale, "phantom": phantom}


def report() -> int:
    if not PAIRS:
        print(f"could not run: {NAME} declares 0 (source, projection) pair(s) — 0 declared is not "
              f"the same as parity", file=sys.stderr)
        return 2
    results, errs, warns = [], [], []
    for pair in PAIRS:
        try:
            results.append(evaluate(pair))
        except CouldNotRun as exc:
            print(f"could not run: {pair['id']} — {exc}", file=sys.stderr)
            return 2
        except Exception as exc:                                   # noqa: BLE001
            print(f"could not run: {pair['id']} — the projector raised {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            return 2

    total_keys = 0
    for r in results:
        p, n = r["pair"], len(r["keys"])
        total_keys += n
        print(f"  {p['id']} — {len(r['carried'])} of {n} declared field(s) carried, "
              f"{len(r['declared'])} declared omitted, {len(r['dropped'])} DROPPED "
              f"[{'; '.join(r['authorities'])}]")
        for k in r["dropped"]:
            errs.append((p["id"], "SILENT_FIELD_DROP", k,
                         f"declared by {r['keys'][k]} and its value does not reach "
                         f"{p['projection']}, and {p['omits'][0]}.{p['omits'][1]} does not declare "
                         f"it omitted with a reason"))
        for k in r["stale"]:
            errs.append((p["id"], "STALE_OMISSION_CLAIM", k,
                         f"{p['omits'][0]}.{p['omits'][1]} claims this field is not carried, and "
                         f"the projection carries it — the claim is a confident wrong answer"))
        for k in r["phantom"]:
            warns.append((p["id"], "OMISSION_OF_NOTHING", k,
                          f"declared omitted, and no authority declares it on the source — either "
                          f"the source stopped declaring it or the table names a field that never "
                          f"existed"))

    for src, cls, k, why in errs:
        print(f"  [{cls}] {src} · `{k}`: {why}", file=sys.stderr)
    for src, cls, k, why in warns:
        print(f"  [{cls}] {src} · `{k}`: {why}")

    denom = (f"{len(PAIRS)} declared (source, projection) pair(s), {total_keys} declared field(s) "
             f"examined; every field checked by RUNNING the projector over a synthetic source")
    if errs:
        print(f"\nFAIL: {NAME} — {len(errs)} defect(s), {len(warns)} warning(s) over {denom}",
              file=sys.stderr)
        return 1
    print(f"\nPASS: {NAME} — 0 defect(s), {len(warns)} warning(s) over {denom}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    return report()


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# self-test: one mutant per reject class. THE FIRST ONE IS A3 ITSELF — the three fields are deleted
# from the real projector's allow-list, in memory, and the gate must go red. A gate that cannot
# reproduce the occurrence that motivated it is not the gate.
# ─────────────────────────────────────────────────────────────────────────────────────────────────

def _run_quiet() -> tuple[int, str]:
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = report()
    return code, buf.getvalue()


def _self_test() -> int:
    global PAIRS
    failures: list[str] = []

    # 0 · the estate as it stands must be green, or every mutant below proves nothing.
    code, out = _run_quiet()
    if code != 0:
        failures.append(f"baseline: expected exit 0, got {code}\n{out}")

    from sdk.project import project_data as P

    # 1 · MUTANT — A3, BYTE FOR BYTE. The projector's per-finding allow-list loses `status`,
    #     `ruled_by` and `reason`. This is the wrap that reproduces the drop without editing the
    #     file: the builder's own `iss.get` calls are served a register item with those keys gone.
    real_build = P.build_data

    def _a3(data_dir, *a, **k):
        import yaml as _y
        reg = os.path.join(str(data_dir), "quality", "data_quality_register.yaml")
        doc = _y.safe_load(open(reg, encoding="utf-8"))
        for iss in doc.get("issues") or []:
            for f in ("status", "ruled_by", "reason"):
                iss.pop(f, None)
        with open(reg, "w", encoding="utf-8") as fh:
            _y.safe_dump(doc, fh, sort_keys=False)
        return real_build(data_dir, *a, **k)

    P.build_data = _a3
    try:
        code, out = _run_quiet()
        if code != 1:
            failures.append(f"A3 mutant: expected exit 1, got {code}\n{out}")
        for f in ("status", "ruled_by", "reason"):
            if f"`{f}`" not in out:
                failures.append(f"A3 mutant: `{f}` was not named as dropped")
        if "SILENT_FIELD_DROP" not in out:
            failures.append("A3 mutant: the reject class did not fire")
    finally:
        P.build_data = real_build

    # 2 · MUTANT — STALE_OMISSION_CLAIM: a field the projection demonstrably carries, declared
    #     omitted. An omission table nobody checks rots the same way the prose did.
    real_tbl = dict(P.DQ_DASHBOARD_OMITS)
    P.DQ_DASHBOARD_OMITS["title"] = "not carried (false)"
    try:
        code, out = _run_quiet()
        if code != 1 or "STALE_OMISSION_CLAIM" not in out:
            failures.append(f"stale-omission mutant: expected exit 1 with the class, got {code}")
    finally:
        P.DQ_DASHBOARD_OMITS.clear()
        P.DQ_DASHBOARD_OMITS.update(real_tbl)

    # 3 · MUTANT — an omission declared with an EMPTY reason is not a declaration.
    real_ov = dict(P.DQ_OVERVIEW_OMITS)
    if real_ov:
        victim = sorted(real_ov)[0]
        P.DQ_OVERVIEW_OMITS[victim] = "   "
        try:
            code, out = _run_quiet()
            if code != 1 or "SILENT_FIELD_DROP" not in out:
                failures.append("empty-reason mutant: an omission with no reason was accepted")
        finally:
            P.DQ_OVERVIEW_OMITS.clear()
            P.DQ_OVERVIEW_OMITS.update(real_ov)
    else:
        failures.append("empty-reason mutant: DQ_OVERVIEW_OMITS is empty, so the roll-up's "
                        "omissions are not declared anywhere and this mutant cannot be seeded")

    # 4 · MUTANT — OMISSION_OF_NOTHING (warning, exit 0).
    P.DQ_OVERVIEW_OMITS["a_field_no_authority_declares"] = "a field that does not exist"
    try:
        code, out = _run_quiet()
        if code != 0 or "OMISSION_OF_NOTHING" not in out:
            failures.append(f"phantom-omission mutant: expected exit 0 with the warning, got {code}")
    finally:
        P.DQ_OVERVIEW_OMITS.clear()
        P.DQ_OVERVIEW_OMITS.update(real_ov)

    # 5 · REFUSE — the vocabulary authority empties. `requires: [ruled_by, reason]` is what lets
    #     this gate see A3; emptied, it must refuse rather than pass over a shrunken key set.
    real_dk = globals()["declared_keys"]

    def _no_requires(pair):
        keys, where = real_dk(pair)
        raise CouldNotRun(
            f"mac_vocabulary.yaml#{pair['vocabulary_block']} declares 4 term(s) and NOT ONE "
            f"`requires` field (simulated)")

    globals()["declared_keys"] = _no_requires
    try:
        code, out = _run_quiet()
        if code != 2:
            failures.append(f"empty-requires: expected exit 2, got {code}")
    finally:
        globals()["declared_keys"] = real_dk

    # 6 · REFUSE — the projector declares no omission table at all.
    real_pairs = PAIRS
    PAIRS = ({**dict(real_pairs[0]), "omits": ("sdk.project.project_data", "NO_SUCH_TABLE")},)
    try:
        code, out = _run_quiet()
        if code != 2:
            failures.append(f"no-omission-table: expected exit 2, got {code}")
    finally:
        PAIRS = real_pairs

    # 7 · REFUSE — zero declared pairs must never print a PASS.
    PAIRS = ()
    try:
        code, out = _run_quiet()
        if code != 2:
            failures.append(f"zero-pairs: expected exit 2, got {code}")
    finally:
        PAIRS = real_pairs

    total = 7
    if failures:
        print(f"FAIL: {NAME} self-test — {len(failures)} of {total} assertion group(s) failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: {NAME} self-test — {total}/{total} (the estate is green; A3's three dropped "
          f"disposition fields go RED by name; a stale omission claim and an omission with no "
          f"reason both fail; an omission of nothing warns; an emptied vocabulary authority, a "
          f"missing omission table and zero declared pairs all refuse with exit 2)")
    return 0


if __name__ == "__main__":                                         # pragma: no cover
    raise SystemExit(main())
