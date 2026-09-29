#!/usr/bin/env python3
"""check_artifact_conformance.py — EVERY ARTIFACT IS THE KIND IT CLAIMS TO BE.

THE DEFECT THIS EXISTS FOR. Operator, 2026-09-28: "we need to discuss how do we make sure that your
action always create artifacts with ONE EXPECTED name and one expected content ... the same content
MUST follow naming convention and formal language/vocabulary/grammar" — and then, on my habit of
inventing one when I cannot find one: "i cannot stop you doing that. but i can ask you to make checker
if for specifig object standard notations and declarations have strictly been followd. if not you have
to do it in the second round."

WHY A SHAPE GATE WAS NOT ENOUGH, measured that day: the estate declared a SHAPE for 27 artifact kinds,
a NAME rule for ONE, and a producer for NONE. Not one shape was violated all day. Four naming and
producer faults were, and two vocabulary faults:

  * an invented `d_`/`f_`/`b_` prefix scheme for served relations, against a role table that is CLOSED
    and already had a gate — caught only at `project`, after the model was built, verified, committed
    and reported
  * TWO lineage producers disagreeing about the same column, the UI reading the wrong one
  * an ER diagram and a relation page built from different files, drawing 17 relationships against 6
  * a register filename that took `relation` and discarded it, silently overwriting eight value
    domains across four bundles

Every one of those is a NAME or a PRODUCER question, and nothing asked either.

WHAT IT CHECKS, per kind declared in mac_artifacts.yaml:
  NAME       every file under the kind's path satisfies the kind's naming rule
  PRODUCER   the kind declares at least one producer, each with a DISTINCT role — co-writers are
             legitimate ("if they do different thing over same artifact - then why not"), an
             undeclared writer or two writers claiming one role is not
  TRANSIENT  a key legal in flight is absent at delivery
  SHAPE      NOT re-checked here: mac.schema.json is its single home and validate_schema owns it.
             The registry REFERENCES the definition so a kind with no shape is visible as a gap.

THE ENUMERATION CONTRACT. One item per subject, `ok` / `violation` / `n/a`, the reason on every
exclusion, and the counts derived from the list so they cannot disagree with it.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, NA = "ok", "violation", "n/a"


def _i(subject, verdict, note=""):
    return {"subject": subject, "verdict": verdict, "note": note}


def counts(items):
    bad = sum(1 for i in items if i["verdict"] == VIOLATION)
    na = sum(1 for i in items if i["verdict"] == NA)
    return len(items), len(items) - bad - na, bad, na


def load_registry(framework: pathlib.Path, yaml):
    f = framework / "mac_artifacts.yaml"
    if not f.is_file():
        return None
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("kinds") or {}


def inv_producer(kinds) -> list:
    """Every kind declares producers, each with a DISTINCT role."""
    out = []
    for name, k in sorted(kinds.items()):
        prods = k.get("producers") or []
        if not prods:
            out.append(_i(name, VIOLATION, "declares NO producer — an artifact nothing is known to "
                                           "write is one nobody can regenerate or trust"))
            continue
        roles = [str(p.get("role") or "").strip() for p in prods]
        if any(not r for r in roles):
            out.append(_i(name, VIOLATION, f"{len(prods)} producer(s) and one names no role; "
                                           "co-writers are legitimate only when each says what it does"))
        elif len(set(roles)) != len(roles):
            dupe = sorted({r for r in roles if roles.count(r) > 1})
            out.append(_i(name, VIOLATION, f"two producers claim the same role {dupe} — that is a "
                                           "conflict, not a collaboration"))
        else:
            out.append(_i(name, OK, f"{len(prods)} producer(s), each with a distinct role: "
                                    + "; ".join(f"{p['tool'].split('/')[-1]} {p['role']}" for p in prods)))
    return out


def inv_shape_declared(kinds) -> list:
    """A kind whose files are structured declares WHICH definition they satisfy."""
    out = []
    for name, k in sorted(kinds.items()):
        path = str(k.get("path") or "")
        structured = any(path.endswith(s) or f"{s}" in path for s in (".yaml", ".json"))
        if not structured:
            out.append(_i(name, NA, f"path {path} is not a structured document, so no schema "
                                    f"definition applies"))
        elif k.get("shape"):
            out.append(_i(name, OK, f"shape -> {k['shape']}"))
        else:
            out.append(_i(name, VIOLATION, "a structured artifact with no declared shape: "
                                           "validate_schema cannot route it and it is checked by nothing"))
    return out


def inv_transient(root: pathlib.Path, kinds, yaml) -> list:
    """A key legal in flight is ABSENT at delivery."""
    out = []
    for name, k in sorted(kinds.items()):
        keys = k.get("transient") or []
        if not keys:
            out.append(_i(name, NA, "declares no transient key"))
            continue
        globpat = _glob_of(k.get("path"))
        files = sorted(root.glob(globpat)) if globpat else []
        if not files:
            out.append(_i(name, NA, f"no file under {globpat} in this bundle"))
            continue
        bad = []
        for f in files:
            try:
                doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception:                                        # noqa: BLE001
                continue
            for c in (doc.get("columns") or []):
                if isinstance(c, dict) and any(t in c for t in keys):
                    bad.append(f"{f.name}.{c.get('name')}")
        if bad:
            out.append(_i(name, VIOLATION,
                          f"{len(bad)} column(s) still carry a transient {keys} at delivery — "
                          f"{', '.join(bad[:4])}. It is consumed in flight and must not survive"))
        else:
            out.append(_i(name, OK, f"{len(files)} file(s) carry no transient {keys}"))
    return out


def _glob_of(path: str | None) -> str:
    """The kind's path pattern as a SELECTING glob — the population this kind is responsible for.

    ONE `*` PER SEGMENT, SPANNING EVERY TOKEN IN IT, and that is the whole correction. Turning each
    `{token}` into its own `*` made the selector as restrictive as the judge: for
    `{marker}_{relation}_{column}.lookup.csv` it produced `*_*_*.lookup.csv`, which does not match
    `country.lookup.csv` — so the one filename the register rules exist to forbid was never
    ENUMERATED, and therefore never a violation. Measured 2026-09-29 with that file present:
    `PASS — 4 of 4 invariant(s) hold`.

    A kind's selector must be the widest thing that is still unambiguously ITS directory and ITS
    extension. `data/lookups/*.lookup.csv` is that; `data/lookups/*_*_*.lookup.csv` is the judge
    wearing the selector's clothes.
    """
    if not path:
        return ""
    first = str(path).split("|")[0].strip()
    segs = []
    for seg in first.split("/"):
        if "{" in seg and "}" in seg:
            seg = seg[: seg.index("{")] + "*" + seg[seg.rindex("}") + 1 :]
        segs.append(seg)
    return "/".join(segs)


def _discriminates(pattern: str) -> bool:
    """Can this pattern REJECT anything its own selector admits?

    It can only do so where a segment holds MORE THAN ONE token, because the literal between them
    is the only thing the selector's single `*` does not already allow. A one-token segment —
    `{relation}.yaml` — says "any name at all in this directory", and the judge and the selector
    then describe the same language.

    This is not a flaw in the gate, it is an UNBOUND TOKEN. `{relation}` means "a relation of this
    plane", and that population is a fact the registry does not yet carry. Until it does, the
    honest verdict is `n/a` with the reason — never `ok`, which is what this returned for nine of
    twelve kinds while a descriptor named `THIS_IS_NOT_A_RELATION NAME!!.yaml` sat in the bundle.
    """
    return any(seg.count("{") > 1 for seg in str(pattern or "").split("/"))


def inv_name(root: pathlib.Path, kinds) -> list:
    """Every file under a kind's path is NAMED the way the kind says."""
    out = []
    for name, k in sorted(kinds.items()):
        pats = [p.strip() for p in str(k.get("path") or "").split("|") if p.strip()]
        rules = []
        for p in pats:
            rules.append(re.compile("^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(p)) + "$"))
        files = []
        for p in pats:
            files += sorted(root.glob(_glob_of(p)))
        if not files:
            out.append(_i(name, NA, f"no file under {_glob_of(pats[0]) if pats else '?'} in this bundle"))
            continue
        if not any(_discriminates(p) for p in pats):
            # ADMIT, DO NOT PASS. The pattern accepts every name its own selector finds, so a green
            # tick here would assert something this gate cannot know. `population` (the delivery
            # manifest, RULED 2026-09-29) is what binds `{relation}` to the relations of a plane and
            # turns this back into a real check.
            out.append(_i(name, NA,
                          f"{len(files)} file(s) present, but `{k.get('path')}` constrains nothing "
                          f"beyond the directory — its token is UNBOUND, so no name can fail it. "
                          f"Bind it to a population to make this checkable."))
            continue
        bad = [str(f.relative_to(root)) for f in files
               if not any(r.match(str(f.relative_to(root))) for r in rules)]
        if bad:
            out.append(_i(name, VIOLATION,
                          f"{len(bad)} of {len(files)} file(s) do not match the declared path "
                          f"{k.get('path')} — {', '.join(bad[:4])}"))
        else:
            out.append(_i(name, OK, f"{len(files)} file(s) match {k.get('path')}"))
    return out



#: THE PHASE VOCABULARY — operator ruling 2026-09-29. Four deliveries, in order, each complete and
#: approved before the next. `both` is not a phase; it means "every data-plane phase" and is kept
#: because `mac_import._stages()` already speaks it.
PHASES = ("sources", "datasets", "ontology", "tuning", "both")

#: How an artifact behaves across runs. The reason this field exists at all: on 2026-09-28 the DQ
#: stages and the lineage stage both RESUMED on the previous phase's output, and a stale artifact
#: is indistinguishable from a fresh one by its presence. A `re-derived` kind whose stage does not
#: carry `always` is a defect that can be found statically, before a single run.
LIFECYCLES = ("re-derived", "resumable", "authored-once")

#: A field left as a placeholder is a VIOLATION, never a default. The whole failure this manifest
#: answers is a delivery reporting itself complete over things nobody had declared.
TODO = "TODO"


def _todo(v) -> bool:
    return isinstance(v, str) and v.strip().upper().startswith(TODO)


def inv_consumed(kinds) -> list:
    """Every kind names who READS it, and names the fields they read.

    THE ONE FACT THE ESTATE COULD NOT WRITE DOWN. Measured 2026-09-29 across the whole estate:
    `grep -c "Consumed by" ontology/planes/*.md` = 0 — nine declaration mechanisms and not one of
    them could express that an artifact has a reader. Every loss of 2026-09-28 was a consumer
    question and none of them could be asked:

      * three lineage producers, the UI reading the one nobody else wrote
      * the DQ assessment absent from both checklists, so no reader missed it
      * `SMEThread.jsx` reading `question.sme_owner` while `mac_dq_findings` writes `ruling.question`,
        which rendered "Every condition has been ruled" over seven open questions

    `reads` is what makes the last one checkable: a consumer that names its fields can be held
    against the producer's shape. A consumer that names only a path cannot, and says so.
    """
    out = []
    for name, k in sorted(kinds.items()):
        cons = k.get("consumers")
        if _todo(cons) or cons is None:
            out.append(_i(name, VIOLATION,
                          "declares no consumers — an artifact nobody reads is either dead weight "
                          "or a reader nobody declared; both are findings, and TODO is neither"))
            continue
        if not cons:
            out.append(_i(name, VIOLATION,
                          "declares `consumers: []` — NOTHING reads this artifact. Retire it, or "
                          "name the reader. An empty list is an honest declaration and still a "
                          "finding the operator must rule on"))
            continue
        bad = [c for c in cons if not str(c.get("tool") or "").strip()
               or not str(c.get("role") or "").strip()]
        if bad:
            out.append(_i(name, VIOLATION,
                          f"{len(bad)} consumer(s) name no tool or no role — "
                          "'something reads it' is not a declaration"))
            continue
        nofields = [c["tool"] for c in cons if not (c.get("reads") or [])]
        if nofields:
            out.append(_i(name, VIOLATION,
                          f"{len(nofields)} consumer(s) declare no `reads`: {', '.join(nofields[:3])}. "
                          "A reader that does not name its fields cannot be held against the "
                          "producer's shape, which is exactly how a reader of `sme_owner` survived "
                          "beside a writer of `ruling.question`"))
        else:
            out.append(_i(name, OK, f"{len(cons)} consumer(s), each naming the fields it reads"))
    return out


def inv_phased(kinds, root=None) -> list:
    """Every kind names the delivery that owes it, and a re-derived kind is re-derived every run.

    TWO DELIVERABLES WERE LOST TO AN ABSENT PHASE AND A THIRD TO AN ABSENT `always`, in one day.
    A stage with no `part` is not neutral — `mac_import` holds it under EVERY part, so it runs only
    under `--part all`, which the operator's sequential delivery rule forbids. That is how lineage
    went missing, then the whole DQ assessment, each time with the checklist reporting complete.
    """
    out = []
    for name, k in sorted(kinds.items()):
        ph, lc = k.get("phase"), k.get("lifecycle")
        problems = []
        if _todo(ph) or not ph:
            problems.append("names no phase — an unphased item is held by EVERY delivery and "
                            "therefore runs in none of them")
        else:
            unknown = [x for x in (ph if isinstance(ph, list) else [ph]) if x not in PHASES]
            if unknown:
                problems.append(f"phase {unknown} is not one of {list(PHASES)}")
        if _todo(lc) or not lc:
            problems.append("names no lifecycle — nothing then says whether a present file may be "
                            "trusted or must be re-derived")
        elif lc not in LIFECYCLES:
            problems.append(f"lifecycle {lc!r} is not one of {list(LIFECYCLES)}")
        # THE LIFECYCLE IS A CONTRACT WITH THE STAGE THAT WRITES IT, and this is the clause that
        # makes it one. A kind declared `re-derived` whose stage resumes on a present file is the
        # exact shape of 2026-09-28's third loss: the DQ stages resumed on phase 1's output, so the
        # served plane got zero properties and the register still claimed eight landings fed no
        # transformation — eight transformations later. `transform_descriptor` has done it too, and
        # the importer's own comment dates it: "after the served views were renamed, this stage
        # RESUMED on the old file and the checklist read T8 0 of 8".
        if not problems and lc == "re-derived" and root is not None:
            stale = _resuming_stages(root, k)
            if stale:
                problems.append(
                    f"declared `re-derived`, but {', '.join(stale)} RESUME on a present file — a "
                    f"stale artifact is indistinguishable from a fresh one by its presence. Add "
                    f"`always: True` to the stage, or declare this `resumable` and say why it is "
                    f"safe to skip")
        if problems:
            out.append(_i(name, VIOLATION, "; ".join(problems)))
        else:
            out.append(_i(name, OK, f"phase {ph}, lifecycle {lc}"))
    return out


def _resuming_stages(root, kind) -> list:
    """Stages that write this kind and may SKIP when the output is already on disk."""
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import mac_manifest as M
    except Exception:                                                    # noqa: BLE001
        return []
    try:
        stages = M.stage_produces(root)
    except Exception:                                                    # noqa: BLE001
        return []
    # EVERY stage that writes the kind, not any. Unioning `always` across them let ONE always-stage
    # excuse its siblings: `landed_descriptor` is written by `descriptors-sources` AND
    # `promote-sources`, only the second carried the flag, and the first went on resuming on a
    # present file while this invariant reported the kind clean. A stale artifact needs only one
    # writer willing to skip.
    path = kind.get("path") or ""
    resuming = []
    for g, info in stages.items():
        if M._claims(path, M._tokenless(g)) or M._claims(g, M._tokenless(path)):
            resuming += [n for n, always in (info.get("by_stage") or {}).items() if not always]
    return sorted(set(resuming))


def inv_covered(root: pathlib.Path, kinds) -> list:
    """Every DELIVERED artifact class on disk is claimed by exactly one kind.

    Operator ruling 2026-09-29: an artifact no kind declares REFUSES the delivery. The escape is
    the one the estate already has — declare the kind, or list it under
    `mac.project.yaml#conformance.out_of_scope` with a reason. There is deliberately no warning
    tier: a warning is exactly how the DQ assessment went missing while every surface read green.

    Measured that day, before this ran: contoso5 held 45 artifact classes and 13 kinds were
    declared; across four bundles, 97 classes and 24 declared.
    """
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import mac_manifest as M
    except Exception as exc:                                             # noqa: BLE001
        return [_i("«census»", NA, f"the census could not be taken: {exc}")]

    disk = M.disk_classes([root])
    out = []
    for cls in sorted(disk):
        delivered, why = M._delivered(cls)
        if not delivered:
            out.append(_i(cls, NA, why))
            continue
        owners = [n for n, k in sorted(kinds.items()) if M._claims(k.get("path"), cls)]
        if len(owners) > 1:
            # MOST SPECIFIC WINS, which is the estate's existing tie-break rather than a new rule.
            # `data/{plane}/index.md` and `data/{plane}/{relation}.md` both match `index.md`; one
            # names the file and the other names a population it falls into. Only an EQUALLY
            # specific pair is a genuine two-homes conflict.
            best = max(M.specificity(kinds[n].get("path")) for n in owners)
            owners = [n for n in owners if M.specificity(kinds[n].get("path")) == best]
        if not owners:
            out.append(_i(cls, VIOLATION,
                          f"{disk[cls]['files']} file(s) claimed by NO declared kind — declare it, "
                          f"or list it under mac.project.yaml#conformance.out_of_scope with a reason"))
        elif len(owners) > 1:
            out.append(_i(cls, VIOLATION,
                          f"claimed by {len(owners)} kinds {owners} — two homes for one artifact "
                          f"is the defect this registry exists to remove"))
        else:
            out.append(_i(cls, OK, f"{disk[cls]['files']} file(s) -> {owners[0]}"))
    return out


INVARIANTS = (
    ("PRODUCER-DECLARED", "every kind names its producers, each with a distinct role", "kinds"),
    ("SHAPE-DECLARED", "every structured kind references a schema definition", "kinds"),
    ("NAME-MATCHES", "every file is named the way its kind declares", "root"),
    ("TRANSIENT-GONE", "a key legal in flight is absent at delivery", "root"),
    # ── the delivery manifest, RULED 2026-09-29 ───────────────────────────────────────────────
    ("CONSUMED", "every kind names who reads it, and which fields they read", "kinds"),
    ("PHASED", "every kind names its delivery phase and its lifecycle", "kinds"),
    ("COVERED", "every delivered artifact class on disk is claimed by exactly one kind", "root"),
)


def run(root: pathlib.Path, framework: pathlib.Path, yaml) -> tuple[list, int]:
    kinds = load_registry(framework, yaml)
    if kinds is None:
        print(f"REFUSED: no mac_artifacts.yaml under {framework} — the registry IS the declaration, "
              f"and without it this gate has nothing to hold an artifact to.")
        return [], 2
    rows = [
        ("PRODUCER-DECLARED", INVARIANTS[0][1], inv_producer(kinds)),
        ("SHAPE-DECLARED", INVARIANTS[1][1], inv_shape_declared(kinds)),
        ("NAME-MATCHES", INVARIANTS[2][1], inv_name(root, kinds)),
        ("TRANSIENT-GONE", INVARIANTS[3][1], inv_transient(root, kinds, yaml)),
        ("CONSUMED", INVARIANTS[4][1], inv_consumed(kinds)),
        ("PHASED", INVARIANTS[5][1], inv_phased(kinds, root)),
        ("COVERED", INVARIANTS[6][1], inv_covered(root, kinds)),
    ]
    return rows, 0


#: WHERE THE MEASUREMENT GOES SO SOMEBODY CAN SEE IT. Operator, 2026-09-29: "if this is the
#: instrument ... where is display to watch the measurement?" — and the estate already answers that
#: for its sibling: `check_delivery_consistency` DECIDES and writes
#: `acceptance/delivery_consistency_runs.json`, and the console only RENDERS it. One home for the
#: verdict, one renderer, and no second opinion computed in a browser. This follows that exactly.
RECORD = pathlib.Path("acceptance") / "manifest_runs.json"


def record(root: pathlib.Path, rows, kinds, checklist_by_part) -> dict:
    """The run record: the verdict, every invariant with its denominators, and the projected
    checklist per delivery. The ENUMERATION CONTRACT holds here too — one item per subject, the
    reason on every exclusion, counts derived from the list so they cannot disagree with it."""
    import json
    from datetime import UTC, datetime

    out_rows = []
    for code, what, items in rows:
        n, held, bad, na = counts(items)
        out_rows.append({
            "code": code, "checks": what,
            "enumerated": n, "held": held, "failed": bad, "not_applicable": na,
            "verdict": VIOLATION if bad else OK,
            # VACUOUS IS ITS OWN FACT, not a flavour of `ok`. An invariant that examined nothing
            # has proved nothing, and `NAME-MATCHES` reported PASS over 11 of 12 kinds it could
            # not judge for as long as it existed.
            "vacuous": (held + bad) == 0,
            "items": items,
        })
    doc = {
        "generated_by": "check_artifact_conformance.py",
        "executed": datetime.now(UTC).isoformat(timespec="seconds"),
        "bundle": root.name,
        "verdict": VIOLATION if any(r["verdict"] == VIOLATION for r in out_rows) else OK,
        "invariants": len(out_rows),
        "invariants_failing": sum(1 for r in out_rows if r["verdict"] == VIOLATION),
        "invariants_vacuous": sum(1 for r in out_rows if r["vacuous"]),
        "kinds_declared": len(kinds or {}),
        "rows": out_rows,
        "checklist": checklist_by_part,
    }
    f = root / RECORD
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc


def _checklists(root: pathlib.Path, kinds) -> dict:
    """The projected checklist for every delivery, folded into the same record — so the operator
    reads ONE artifact to answer both 'does the manifest hold' and 'what does this delivery owe'."""
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import mac_manifest as M
    except Exception:                                                    # noqa: BLE001
        return {}
    out = {}
    for part in ("sources", "datasets", "ontology", "tuning"):
        try:
            items = M.checklist(root, part, kinds)
        except Exception:                                                # noqa: BLE001
            continue
        if not items:
            continue
        out[part] = [{
            "id": it["id"], "what": it["what"], "of": it["of"], "where": it["where"],
            "have": len(it["have"]), "want": len(it["want"]),
            "na": it.get("na"),
            "verdict": ("n/a" if it.get("na") else
                        ("ok" if (len(it["want"]) and len(it["have"]) == len(it["want"]))
                         or (not len(it["want"]) and it.get("empty_is") == "OK")
                         else ("empty" if not len(it["want"]) else "short"))),
            "missing": [str(x) for x in it["want"] if x not in it["have"]][:12],
        } for it in items]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2
    fw = pathlib.Path(__file__).resolve().parent.parent
    if a.self_test:
        return _self_test(yaml, fw)
    root = pathlib.Path(a.root).resolve()
    rows, rc = run(root, fw, yaml)
    if rc:
        return rc
    # WRITE THE RECORD BEFORE PRINTING, and write it whatever the verdict. A gate that records only
    # its passes leaves the operator with a display that goes blank exactly when something is wrong.
    kinds = load_registry(fw, yaml) or {}
    try:
        doc = record(root, rows, kinds, _checklists(root, kinds))
        _wrote = f"{RECORD} — {doc['invariants']} invariant(s), {doc['kinds_declared']} kind(s)"
    except Exception as exc:                                             # noqa: BLE001
        _wrote = f"the record could NOT be written: {type(exc).__name__}: {exc}"
    print(f"── artifact conformance ── {root.name} ──")
    failed = 0
    for code, what, items in rows:
        tot, held, bad, na = counts(items)
        mark = "FAIL" if bad else "ok  "
        failed += 1 if bad else 0
        print(f"  [{mark}] {code:19} {what:56} {tot} enumerated · {held} held · {bad} failed · {na} n/a")
        for i in items:
            if i["verdict"] == VIOLATION:
                print(f"         - {i['subject']}: {i['note']}")
    print(f"  -> {_wrote}")
    if failed:
        print(f"\nFAIL: check_artifact_conformance — {failed} of {len(rows)} invariant(s) broken. An "
              f"artifact that does not follow its kind's declaration is one nobody can find, "
              f"regenerate or trust.")
        return 1
    print(f"\nPASS: check_artifact_conformance — {len(rows)} of {len(rows)} invariant(s) hold over "
          f"{len(load_registry(fw, yaml))} declared kind(s).")
    return 0


def _self_test(yaml, fw) -> int:
    cases, bad = [], 0

    def case(name, cond, why=""):
        nonlocal bad
        cases.append((name, cond))
        if not cond:
            bad += 1
            print(f"  ✗ {name}" + (f" — {why}" if why else ""))

    base = {"k": {"path": "data/x/{rel}.yaml", "shape": "s#/d",
                  "producers": [{"tool": "a.py", "role": "measures"}]}}
    case("a kind with one producer and a role holds", counts(inv_producer(base))[2] == 0)
    case("MUTANT a kind with NO producer fails",
         counts(inv_producer({"k": {"path": "p"}}))[2] == 1,
         "an artifact nothing is known to write is one nobody can regenerate")
    case("MUTANT two producers claiming ONE role fails",
         counts(inv_producer({"k": {"producers": [{"tool": "a", "role": "r"},
                                                  {"tool": "b", "role": "r"}]}}))[2] == 1,
         "that is a conflict, not a collaboration")
    case("CO-WRITERS with distinct roles are legitimate — the operator's ruling",
         counts(inv_producer({"k": {"producers": [{"tool": "a", "role": "measures"},
                                                  {"tool": "b", "role": "slims"}]}}))[2] == 0)
    case("MUTANT a producer with no role fails",
         counts(inv_producer({"k": {"producers": [{"tool": "a"}]}}))[2] == 1)
    case("MUTANT a structured kind with NO shape fails",
         counts(inv_shape_declared({"k": {"path": "data/x/{r}.yaml"}}))[2] == 1)
    case("a CSV kind is n/a for shape, not a violation",
         counts(inv_shape_declared({"k": {"path": "data/x/{r}.csv"}}))[3] == 1)
    # THIS CASE USED TO RATIFY THE BUG. It asserted `*_*_*.lookup.csv` — a selector as narrow as
    # the judge — and so it went green for as long as the gate could not fail. A self-test that
    # pins the defect is worse than none: it is the defect with a certificate. What the selector
    # must do is name the kind's WHOLE population; the pattern is what discriminates inside it.
    case("the selector spans every token in a segment with ONE star",
         _glob_of("data/lookups/{m}_{r}_{c}.lookup.csv") == "data/lookups/*.lookup.csv")
    case("MUTANT the old per-token selector would have excluded the violation",
         not pathlib.PurePath("data/lookups/country.lookup.csv").match("data/lookups/*_*_*.lookup.csv")
         and pathlib.PurePath("data/lookups/country.lookup.csv").match("data/lookups/*.lookup.csv"))
    case("a token in a DIRECTORY segment is spanned too",
         _glob_of("data/{plane}/{relation}.md") == "data/*/*.md")
    case("an alternative path takes its FIRST branch for the glob",
         _glob_of("a/{x}.csv | b/{x}.csv") == "a/*.csv")
    # THE VACUITY ADMISSION — a one-token segment cannot reject anything its selector admits.
    case("a multi-token segment DISCRIMINATES",
         _discriminates("data/lookups/{m}_{r}_{c}.lookup.csv"))
    case("a one-token segment does NOT, and must be admitted rather than passed",
         not _discriminates("data/sources/{relation}.yaml"))
    case("a fixed name does not discriminate either — nothing varies",
         not _discriminates("data/lineage/lineage.json"))

    # ── the three manifest invariants, each shown to REJECT ───────────────────────────────────
    # THE META-RULE, and the reason it is written down here rather than assumed: `NAME-MATCHES`
    # shipped as a tautology and reported PASS over two deliberately-broken files for as long as it
    # existed. An invariant nobody has watched fail is a sentence, not a check.
    case("MUTANT a kind with consumers TODO fails",
         counts(inv_consumed({"k": {"consumers": "TODO   # who reads it"}}))[2] == 1)
    case("MUTANT a kind with NO consumers at all fails — an empty list is still a finding",
         counts(inv_consumed({"k": {"consumers": []}}))[2] == 1)
    case("MUTANT a consumer that names no `reads` fails",
         counts(inv_consumed({"k": {"consumers": [{"tool": "t", "role": "r"}]}}))[2] == 1)
    case("a consumer naming its fields holds",
         counts(inv_consumed({"k": {"consumers": [
             {"tool": "t", "role": "r", "reads": ["verdict"]}]}}))[1] == 1)
    case("MUTANT a kind with no phase fails",
         counts(inv_phased({"k": {"lifecycle": "re-derived"}}))[2] == 1)
    case("MUTANT a kind with an UNKNOWN phase fails",
         counts(inv_phased({"k": {"phase": ["harvest"], "lifecycle": "re-derived"}}))[2] == 1)
    case("MUTANT a kind with no lifecycle fails",
         counts(inv_phased({"k": {"phase": ["sources"]}}))[2] == 1)
    case("MUTANT a kind with an UNKNOWN lifecycle fails",
         counts(inv_phased({"k": {"phase": ["sources"], "lifecycle": "cached"}}))[2] == 1)
    case("a phased, lifecycled kind holds",
         counts(inv_phased({"k": {"phase": ["sources"], "lifecycle": "re-derived"}}))[1] == 1)

    import tempfile
    with tempfile.TemporaryDirectory() as t:
        r = pathlib.Path(t)
        (r / "data" / "x").mkdir(parents=True)
        (r / "data" / "x" / "good.yaml").write_text("columns: [{name: a}]\n")
        k = {"k": {"path": "data/x/{rel}.yaml", "transient": ["values"],
                   "producers": [{"tool": "a", "role": "m"}]}}
        case("a clean bundle passes NAME and TRANSIENT",
             counts(inv_name(r, k))[2] == 0 and counts(inv_transient(r, k, yaml))[2] == 0)
        (r / "data" / "x" / "bad.yaml").write_text("columns: [{name: a, values: [1,2]}]\n")
        case("MUTANT a transient surviving to delivery fails",
             counts(inv_transient(r, k, yaml))[2] == 1,
             "this is DOMAIN-HOMED generalised — a key consumed in flight must not survive")
        (r / "data" / "x" / "nested").mkdir()
        (r / "data" / "x" / "nested" / "deep.yaml").write_text("{}\n")
        case("a file NOT matching the declared path is a NAME violation",
             counts(inv_name(r, {"k": {"path": "data/x/{rel}.yaml"}}))[2] == 0,
             "a nested file is outside the kind's glob, so it is not this kind's subject")

    case("the REAL registry holds its own rules",
         counts(inv_producer(load_registry(fw, yaml)))[2] == 0
         and counts(inv_shape_declared(load_registry(fw, yaml)))[2] == 0,
         "the registry must satisfy the gate it declares")

    print(("PASS" if not bad else "FAIL") + f": check_artifact_conformance self-test — "
          f"{len(cases) - bad}/{len(cases)} case(s): producers with distinct roles are a "
          f"COLLABORATION and with the same role a CONFLICT; a structured kind with no shape, a "
          f"transient surviving delivery, and a misnamed file each fail; and the registry itself "
          f"satisfies its own rules.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
