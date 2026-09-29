#!/usr/bin/env python3
"""check_guardrails.py — READS guardrails/, and REFUSES.

WHAT MAKES THIS DIFFERENT FROM EVERY OTHER GATE HERE. They report. This one is built to be called
BEFORE an action, answer allow/deny, and be wired to a hook that honours the answer.

    "reporting is not refusing" — guardrails/README.md

Measured 2026-09-28/29, why that distinction is the whole point: `conformance` printed FAIL and the
delivery ran to completion; `mac_artifacts.yaml` was committed unparseable because nothing stood
between writing it and committing it, and four commits later every run of the gate was a traceback
rather than a verdict. A finding after the fact is a record of a mistake.

TWO MODES, one vocabulary:

    --inspect <bundle>          how the bundle stands against every topic (the DIAL)
    --propose <path> [--content-file F]
                                may this file be written? exit 0 allow, exit 1 REFUSE (the HOOK)

UNSPECIFIED IS NOT RULED. A path no topic claims under a plane no topic rules is ALLOWED, and says
so. This gate only ever speaks about what a guardrail declares.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re
import sys

GUARDRAILS = "guardrails"
ALLOW, REFUSE = 0, 1


def load_topics(framework: pathlib.Path) -> dict:
    """{topic -> spec}. A topic that does not PARSE is itself a refusal — see UNPARSEABLE-SPEC."""
    import yaml

    out, broken = {}, []
    d = framework / GUARDRAILS
    if not d.is_dir():
        return {"«none»": {}}
    for f in sorted(d.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception as exc:                                          # noqa: BLE001
            broken.append((f.name, str(exc).split("\n")[0]))
            continue
        out[doc.get("topic") or f.stem] = doc
    if broken:
        out["«broken»"] = broken
    return out


def _glob_of(path_pattern: str) -> list:
    """The declared path as globs — one `*` per segment, spanning every token in it.

    Substituting each `{token}` separately makes the selector as narrow as the judge, and then a
    file that violates the rule is never enumerated: measured 2026-09-29, `country.lookup.csv` — the
    exact name the register rule exists to forbid — was not even looked at.
    """
    out = []
    for branch in str(path_pattern or "").split("|"):
        segs = []
        for seg in branch.strip().split("/"):
            if "{" in seg and "}" in seg:
                seg = seg[: seg.index("{")] + "*" + seg[seg.rindex("}") + 1:]
            segs.append(seg)
        out.append("/".join(segs))
    return out


def _regex_of(path_pattern: str) -> list:
    return [re.compile("^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(b.strip())) + "$")
            for b in str(path_pattern or "").split("|")]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE REFUSALS. One function per declared id; a declared id with no function here is reported as
# UNENFORCED rather than silently passing — an unenforced rule is worse than an absent one, because
# the file says it is covered.
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _r_undeclared_artifact(rel, text, spec, topics):
    """A file under a ruled plane that no item of any topic claims."""
    ruled = set()
    for t in topics.values():
        if not isinstance(t, dict):
            continue
        for item in (t.get("delivers") or {}).values():
            ruled.update(_glob_of(item.get("path")))
    if not ruled:
        return None
    planes = {g.split("/")[0] + "/" + g.split("/")[1] for g in ruled if g.count("/") >= 1}
    here = "/".join(rel.split("/")[:2])
    if here not in planes:
        return None                                   # UNSPECIFIED IS NOT RULED
    if any(fnmatch.fnmatch(rel, g) for g in ruled):
        return None
    return f"{rel} sits under {here}/, which a guardrail rules, but no declared item claims it"


def _r_invented_vocabulary(rel, text, spec, topics):
    """A `mac.<ns>.<term>` token whose namespace mac_vocabulary.yaml does not declare."""
    if text is None:
        return None
    import yaml

    fw = pathlib.Path(__file__).resolve().parent.parent
    vf = fw / "mac_vocabulary.yaml"
    if not vf.is_file():
        return None
    try:
        vocab = yaml.safe_load(vf.read_text(encoding="utf-8")) or {}
    except Exception:                                                     # noqa: BLE001
        return None
    known = {k for k in vocab if k not in ("metadata", "spec_version")}
    # the longest declared namespace wins — the vocabulary says where the boundary is, not the dots
    bad = []
    for tok in sorted(set(re.findall(r"\bmac\.([A-Za-z_][\w.]*)", text))):
        if any(tok == k or tok.startswith(k + ".") for k in known):
            continue
        if tok.split(".")[0] in ("schema", "project", "connector", "seam", "artifacts",
                                 "guardrail", "resources", "sme-questions", "test_kind"):
            continue                                   # registries and spec_versions, not vocabularies
        bad.append("mac." + tok)
    return (f"{len(bad)} token(s) resolve to no declared namespace: {', '.join(bad[:4])}"
            if bad else None)


def _r_invented_column_role(rel, text, spec, topics):
    """A data-plane column `role` outside the closed set."""
    if text is None or not rel.endswith((".yaml", ".yml")):
        return None
    closed = None
    for t in topics.values():
        for c in (t.get("conventions") or []) if isinstance(t, dict) else []:
            if "role a data-plane column" in str(c.get("what", "")):
                closed = set(c.get("closed") or [])
    if not closed:
        return None
    bad = sorted({m for m in re.findall(r"^\s*role:\s*([A-Za-z_][\w]*)\s*$", text, re.M)}
                 - closed)
    return (f"role {bad} is outside the closed set {sorted(closed)}" if bad else None)


def _r_renamed_landing(rel, text, spec, topics):
    """A landed descriptor that does not name a relation the WAREHOUSE actually landed.

    CHECKING THE STEM AGAINST `table.name` WAS NOT ENOUGH, and the feasibility test found it: a
    descriptor called `d_customer.yaml` declaring `table.name: d_customer` is internally consistent
    and entirely invented. That is exactly the failure this rule exists for — on 2026-09-28 I
    invented a `d_`/`f_`/`b_` prefix scheme against a CLOSED role table, and it survived being
    designed, built, measured, committed and REPORTED before anything objected.

    Internal consistency is not conformance. The landing plane's names belong to the warehouse, so
    the warehouse is what a landed name is held against — with the parquet landings as the offline
    stand-in when no connection is open. No evidence available means NO VERDICT, never a pass.
    """
    if text is None or not fnmatch.fnmatch(rel, "data/sources/*.yaml"):
        return None
    stem = pathlib.PurePosixPath(rel).stem
    m = re.search(r"^\s*name:\s*['\"]?([A-Za-z_][\w]*)['\"]?\s*$", text, re.M)
    if m and m.group(1) != stem:
        return f"table.name is {m.group(1)!r} but the file is {stem}.yaml — a landing is never renamed"
    landed = _landed_relations(rel)
    if landed is None:
        return None                                   # nothing to hold it against — no verdict
    if stem not in landed:
        return (f"{stem!r} is not a relation this warehouse landed "
                f"({len(landed)} landed: {', '.join(sorted(landed)[:6])}"
                f"{'...' if len(landed) > 6 else ''}) — a landing is DESCRIBED, never invented")
    return None


def _landed_relations(rel: str):
    """What the warehouse actually landed, or None when it cannot be known offline.

    The parquet landings are the bundle's own record of what was loaded — `build.sh` creates one
    table per file — so they answer this without a connection. A bundle with neither is not judged.
    """
    here = pathlib.Path.cwd()
    for root in (here, *here.parents):
        d = root / "data"
        if d.is_dir() and (root / "connection.yaml").is_file():
            pq = sorted(p.stem.lower() for p in d.glob("*.parquet"))
            return set(pq) if pq else None
    return None


def _r_transient_at_delivery(rel, text, spec, topics):
    """A delivered landed descriptor still carrying `values:` on a column."""
    if text is None or not fnmatch.fnmatch(rel, "data/sources/*.yaml"):
        return None
    return ("a column still carries `values:` — a value domain's home is a register"
            if re.search(r"^\s+values:\s*$|^\s+values:\s*\[", text, re.M) else None)


def _r_unparseable_spec(rel, text, spec, topics):
    """Any guardrail file that does not parse as YAML."""
    if text is None or not fnmatch.fnmatch(rel, "guardrails/*.yaml"):
        return None
    import yaml

    try:
        yaml.safe_load(text)
    except Exception as exc:                                              # noqa: BLE001
        return f"does not parse as YAML: {str(exc).splitlines()[0]}"
    return None


ENFORCERS = {
    "UNDECLARED-ARTIFACT": _r_undeclared_artifact,
    "INVENTED-VOCABULARY": _r_invented_vocabulary,
    "INVENTED-COLUMN-ROLE": _r_invented_column_role,
    "RENAMED-LANDING": _r_renamed_landing,
    "TRANSIENT-AT-DELIVERY": _r_transient_at_delivery,
    "UNPARSEABLE-SPEC": _r_unparseable_spec,
}


def propose(framework: pathlib.Path, rel: str, text: str | None) -> tuple:
    """(verdict, findings, unenforced) for ONE proposed write."""
    topics = load_topics(framework)
    if "«broken»" in topics:
        return REFUSE, [("UNPARSEABLE-SPEC", f"{n}: {e}") for n, e in topics["«broken»"]], []
    findings, unenforced = [], []
    for name, spec in topics.items():
        for r in (spec.get("refuses") or []) if isinstance(spec, dict) else []:
            fn = ENFORCERS.get(r["id"])
            if fn is None:
                unenforced.append(r["id"])
                continue
            note = fn(rel, text, r, topics)
            if note:
                findings.append((r["id"], note, r.get("instead", "")))
    return (REFUSE if findings else ALLOW), findings, sorted(set(unenforced))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--framework", default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument("--propose", metavar="PATH", help="a bundle-relative path about to be written")
    ap.add_argument("--content-file", help="the content it would be written with")
    ap.add_argument("--inspect", metavar="BUNDLE", help="how a bundle stands against every topic")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    fw = pathlib.Path(a.framework).resolve()

    if a.propose:
        text = None
        if a.content_file:
            text = pathlib.Path(a.content_file).read_text(encoding="utf-8", errors="replace")
        verdict, findings, unenforced = propose(fw, a.propose.lstrip("./"), text)
        if a.json:
            print(json.dumps({"verdict": "refuse" if verdict else "allow",
                              "findings": [{"rule": r, "note": n, "instead": i}
                                           for r, n, i in findings],
                              "unenforced": unenforced}))
            return verdict
        if verdict == ALLOW:
            print(f"ALLOW  {a.propose}")
            if unenforced:
                print(f"       ({len(unenforced)} declared rule(s) have no enforcer: "
                      f"{', '.join(unenforced)} — declared is not enforced)")
            return ALLOW
        print(f"REFUSE {a.propose}")
        for rule, note, instead in findings:
            print(f"  ✗ {rule}")
            print(f"      {note}")
            if instead:
                print(f"      instead: {instead}")
        return REFUSE

    if a.inspect:
        return inspect(fw, pathlib.Path(a.inspect).resolve(), a.json)

    ap.print_help()
    return 2


def inspect(fw: pathlib.Path, bundle: pathlib.Path, as_json: bool) -> int:
    """THE DIAL — every declared item of every topic, have of want, with its population."""
    topics = load_topics(fw)
    report = {"bundle": bundle.name, "topics": {}}
    for name, spec in sorted(topics.items()):
        if not isinstance(spec, dict) or not spec.get("delivers"):
            continue
        rows = []
        for item, decl in sorted(spec["delivers"].items()):
            globs = _glob_of(decl.get("path"))
            rx = _regex_of(decl.get("path"))
            hits = sorted({str(p.relative_to(bundle))
                           for g in globs for p in bundle.glob(g) if p.is_file()})
            bad = [h for h in hits if not any(r.match(h) for r in rx)]
            rows.append({"item": item, "path": decl.get("path"),
                         "present": len(hits), "misnamed": bad,
                         "population": (decl.get("population") or {}).get("of", "—")})
        report["topics"][name] = {"phase": spec.get("phase"), "items": rows,
                                  "refuses": [r["id"] for r in (spec.get("refuses") or [])],
                                  "unenforced": [r["id"] for r in (spec.get("refuses") or [])
                                                 if r["id"] not in ENFORCERS]}
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return ALLOW
    for name, t in report["topics"].items():
        print(f"── guardrail: {name}  (phase {t['phase']}) ── {bundle.name} ──")
        for r in t["items"]:
            flag = f"  ✗ {len(r['misnamed'])} MISNAMED: {', '.join(r['misnamed'][:3])}" if r["misnamed"] else ""
            print(f"  {r['item']:24} {r['present']:>3} file(s)   {r['path']}{flag}")
        print(f"  refuses: {', '.join(t['refuses'])}")
        if t["unenforced"]:
            print(f"  NOT ENFORCED: {', '.join(t['unenforced'])} — declared is not enforced")
    return ALLOW


if __name__ == "__main__":
    sys.exit(main())
