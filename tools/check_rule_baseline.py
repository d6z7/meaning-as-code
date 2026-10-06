#!/usr/bin/env python3
"""check_rule_baseline.py — FREEZE what a bundle does today, so a rule migration cannot change it by
accident. Then prove the freeze is real by deleting every directive and requiring this gate to notice.

WHY check_plan_replay IS NOT THIS GATE, and the distinction is the whole reason this file exists.
That one replays every captured intent and reports the transition PLANNED -> REFUSED: a capability the
bundle had and lost. It is the right instrument for a deletion and it has held all day. It cannot see a
plan that still succeeds and now answers DIFFERENTLY.

MEASURED 2026-10-06, and this is the defect that motivated the gate. `country.default.a_sales_question_
means_the_store_country` is `confidence: C` -- a person ruled it on 2026-09-30 -- and says a sales
question means the country the STORE trades in. All seven measures take the CUSTOMER path instead:

    NetRevenue -> net_revenue__by__customer + customer__based_in__country

Both paths are two hops, so the edge graph has a tie, and `ontology/graph.py` breaks it with unweighted
BFS over an adjacency built in edges.yaml DECLARATION ORDER (`net_revenue__by__customer` at line 276,
`net_revenue__by__store` at 289). Every one of those seven PLANS. check_plan_replay reports 0 gained
over 58 and is correct to: nothing was lost. The number is simply wrong -- Germany 2025 growth is
+18.07 % through the customer and +49.65 % through the store, because the store path excludes the
online channel and online is 40 % of net revenue.

So the floor protects against losing an answer and says nothing about changing one. A migration that
moves a directive from prose into a canon body changes WHICH MECHANISM DECIDES, which is exactly the
class the floor cannot see. `Plan.edges_used` and `Plan.rules_used` can.

WHAT IS FROZEN -- five artefacts, because the keys a rule migration deletes have three live runtime
readers and one generated projection, and forgetting any of them is how a migration eats work:

  1. per-question behaviour -- outcome, SQL, bound params, edges_used, rules_used, laws_applied,
     caveats_known. The behavioural fingerprint, not just "did it plan".
  2. the interpreter's system prompt, byte-exact. `interpret/prompt.py` sends every `contract.rules[]
     .never` to the model verbatim; measured on contoso5 that is 675 chars over 12 clauses in a 19 332-
     char prompt. Changing it changes answers, so it is frozen and diffed, never eyeballed.
  3. the generated rule pages, by digest. `sdk/project/mac_okf.py` renders `### When / ### Then /
     ### Never` from those same YAML keys and rmtree's the directory first, so deleting the keys blanks
     every page in the same commit.
  4. the meaning plane's contract-rule rows, which publish `when/then/never` as columns.
  5. every reachable refusal's text, because `planner/plan.py` cites `rule.never` in the refusal a
     reader sees.

THE SELF-TEST IS A MUTATION, AND IT IS THE POINT. `--self-test` copies the bundle, strips every
`when`/`then`/`never`, and REQUIRES this gate to go red. That mutation was run against the three gates
already guarding this ground -- check_concept_narrative, check_canon_binding, check_prose_moved -- and
all three stayed GREEN on a bundle with no directives left in it, because the pages they check are a
projection of the YAML they are checking and coverage was true by construction. A harness that cannot
fail on total deletion is decoration. This one is required to fail, and the requirement is asserted
here rather than trusted.

Usage:
    python3 tools/check_rule_baseline.py <bundle-root> --capture   # freeze today
    python3 tools/check_rule_baseline.py <bundle-root>             # compare against the freeze
    python3 tools/check_rule_baseline.py --self-test               # prove the gate is not vacuous

Exit 0 = identical to the freeze · 1 = something moved · 2 = could not run (never a verdict).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location

#: Beside the corpus it is about, next to `plan_baseline.json`, whose precedent this follows: a
#: decision to carry a state lives with the thing it describes, not in the framework.
BASELINE_REL = pathlib.Path("acceptance") / "rule_baseline.json"

#: The prompt embeds the date it was built for. Pinned in the baseline so a comparison tomorrow is
#: about the ontology and not about the calendar -- the failure mode `board_diff` was fixed for.
AS_OF = "2026-01-01"

#: The keys a rule migration removes. One list, used by the capture (to count them) and by the
#: self-test mutation (to delete them), so the two can never drift apart.
DIRECTIVE_KEYS = ("when", "then", "never")


def _norm(text: object) -> str:
    """Whitespace-collapsed, so a reflowed SQL string is not reported as a behaviour change."""
    return " ".join(str(text or "").split())


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# The five artefacts
# ---------------------------------------------------------------------------


def _behaviour(root: pathlib.Path) -> dict:
    """Artefact 1: the behavioural fingerprint of every captured intent.

    Replays through the REAL planner with the REAL registers, reusing check_plan_replay's own helpers
    rather than a second copy of them -- a replay that resolved differently from that gate would
    report findings about itself. The fingerprint includes `edges_used` and `rules_used` because those
    are what a migration moves; a fingerprint of success alone would have missed the Country defect.
    """
    import check_plan_replay as CPR

    _neighbours.ensure_runtime_on_path()
    from mac_runtime.models import Intent
    from mac_runtime.ontology.index import OntologyIndex
    from mac_runtime.planner.plan import plan

    index = OntologyIndex.from_directory(root)
    resolver, _n = CPR._resolver_for(root, index)

    out: dict[str, dict] = {}
    for qid, raw, _route in CPR._recorded(root / "acceptance" / "answers"):
        try:
            intent = Intent(**{k: v for k, v in raw.items() if v is not None})
        except Exception as exc:                                    # noqa: BLE001
            out[qid] = {"outcome": "UNREADABLE", "detail": f"{type(exc).__name__}"}
            continue
        try:
            res = plan(intent, index, resolver)
        except Exception as exc:                                    # noqa: BLE001
            out[qid] = {"outcome": "RAISED", "detail": f"{type(exc).__name__}"}
            continue
        kind = type(res).__name__
        if kind == "Plan":
            out[qid] = {
                "outcome": "Plan",
                "sql": _norm(getattr(res, "sql_preview", "")),
                "params": sorted(str(p) for p in (getattr(res, "params", None) or [])),
                # THE TWO THAT CATCH A MIGRATION. `edges_used` is the join path -- the Country
                # inversion is visible here and nowhere else. `rules_used` is which rule fired, so
                # moving a directive from prose to a body shows up as a change even when the SQL
                # happens to match.
                "edges_used": sorted(str(e) for e in (getattr(res, "edges_used", None) or [])),
                "rules_used": sorted(str(r) for r in (getattr(res, "rules_used", None) or [])),
                "laws_applied": sorted(str(l) for l in (getattr(res, "laws_applied", None) or [])),
                "caveats": sorted(_norm(c) for c in (getattr(res, "caveats_known", None) or [])),
                "concepts": sorted(str(c) for c in (getattr(res, "concepts_used", None) or [])),
            }
        else:
            # Artefact 5 lives here rather than in its own pass: a refusal's TEXT is what a reader
            # sees, and `planner/plan.py` builds it from `rule.never`. Freezing the reason code alone
            # would let the citation vanish while the gate stayed green.
            out[qid] = {
                "outcome": kind,
                "reason_code": str(getattr(res, "reason_code", "") or "").rsplit(".", 1)[-1].lower(),
                "human_reason": _norm(getattr(res, "human_reason", "")),
                "missing": sorted(str(m) for m in (getattr(res, "missing", None) or [])),
            }
    return out


def _prompt(root: pathlib.Path) -> dict:
    """Artefact 2: the interpreter's system prompt, by length and digest.

    Digest rather than the text itself: the baseline is committed and a 19 kB prose blob in it would
    be re-reviewed on every diff. A changed digest is the signal; `--show-prompt` prints the text when
    somebody needs to see WHAT changed.
    """
    _neighbours.ensure_runtime_on_path()
    from mac_runtime.interpret.prompt import build_system_prompt
    from mac_runtime.interpret.vocabulary import Vocabulary
    from mac_runtime.ontology.index import OntologyIndex

    index = OntologyIndex.from_directory(root)
    voc = Vocabulary.from_index(index)
    #: A `date`, not the string: `_format_period_guidance` calls `.isoformat()` on it. Parsed from the
    #: pinned constant so the prompt is reproducible — building it with today's date would make every
    #: comparison tomorrow report a difference about the calendar.
    text = build_system_prompt(voc, as_of=datetime.date.fromisoformat(AS_OF), index=index)
    return {"chars": len(text), "digest": _digest(text), "lines": len(text.splitlines())}


def _rule_pages(root: pathlib.Path) -> dict:
    """Artefact 3: the generated rule pages, by digest.

    These are rendered FROM the keys a migration deletes, by a projector that rmtree's the directory
    first. So they are the artefact most likely to be silently emptied, and the one nobody looks at.
    """
    d = root / "ontology" / "concepts" / "rules"
    if not d.is_dir():
        return {}
    return {p.name: _digest(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.md"))}


def _meaning_plane(root: pathlib.Path) -> dict:
    """Artefact 4: the meaning plane's contract-rule rows, which publish when/then/never as columns.

    Reported as UNREACHABLE rather than skipped when the module cannot be driven: a silent skip is how
    an artefact drops out of a freeze without anyone deciding to drop it.
    """
    _neighbours.ensure_runtime_on_path()
    try:
        from mac_runtime.meaning_plane import contract_rule_rows  # type: ignore[attr-defined]
    except Exception as exc:                                       # noqa: BLE001
        return {"status": "UNREACHABLE", "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
    from mac_runtime.ontology.index import OntologyIndex
    try:
        rows = contract_rule_rows(OntologyIndex.from_directory(root))
    except Exception as exc:                                       # noqa: BLE001
        return {"status": "UNREACHABLE", "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
    return {"status": "ok", "rows": len(rows or []), "digest": _digest(_norm(json.dumps(rows, default=str, sort_keys=True)))}


def _directives(root: pathlib.Path) -> dict:
    """How many when/then/never clauses exist, per rule. Not an artefact to protect — the MEASURE OF
    THE MIGRATION itself, so progress and regression are one number in the same file."""
    counts: dict[str, list[str]] = {}
    cdir = root / "ontology" / "concepts"
    for f in sorted(cdir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                          # noqa: BLE001
            continue
        for r in ((doc.get("contract") or {}).get("rules") or []):
            present = [k for k in DIRECTIVE_KEYS if str(r.get(k) or "").strip()]
            if present:
                counts[str(r.get("id"))] = present
    return counts


def capture(root: pathlib.Path) -> dict:
    return {
        "spec": "mac.rule_baseline/1",
        "as_of_pinned": AS_OF,
        "behaviour": _behaviour(root),
        "prompt": _prompt(root),
        "rule_pages": _rule_pages(root),
        "meaning_plane": _meaning_plane(root),
        "directives": _directives(root),
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare(old: dict, new: dict) -> list[str]:
    """Every way the bundle now differs from the freeze. Order is by blast radius, not by artefact."""
    out: list[str] = []

    ob, nb = old.get("behaviour") or {}, new.get("behaviour") or {}
    for qid in sorted(set(ob) | set(nb)):
        a, b = ob.get(qid), nb.get(qid)
        if a is None:
            out.append(f"[behaviour-new] {qid} — not in the freeze")
            continue
        if b is None:
            out.append(f"[behaviour-gone] {qid} — in the freeze and no longer captured")
            continue
        if a.get("outcome") != b.get("outcome"):
            out.append(f"[outcome] {qid} — {a.get('outcome')} -> {b.get('outcome')}")
            continue
        for field in ("edges_used", "rules_used", "sql", "params", "laws_applied", "caveats",
                      "concepts", "reason_code", "human_reason", "missing"):
            if field in a and a.get(field) != b.get(field):
                was, now = a.get(field), b.get(field)
                out.append(f"[{field}] {qid} — {str(was)[:90]} -> {str(now)[:90]}")

    op, np_ = old.get("prompt") or {}, new.get("prompt") or {}
    if op.get("digest") != np_.get("digest"):
        out.append(f"[prompt] {op.get('chars')} chars -> {np_.get('chars')} "
                   f"({np_.get('chars', 0) - op.get('chars', 0):+d}); the model sees something else")

    orp, nrp = old.get("rule_pages") or {}, new.get("rule_pages") or {}
    for name in sorted(set(orp) | set(nrp)):
        if name not in nrp:
            out.append(f"[rule-page-gone] {name}")
        elif name not in orp:
            out.append(f"[rule-page-new] {name}")
        elif orp[name] != nrp[name]:
            out.append(f"[rule-page] {name} — content changed")

    omp, nmp = old.get("meaning_plane") or {}, new.get("meaning_plane") or {}
    if omp.get("digest") != nmp.get("digest") or omp.get("status") != nmp.get("status"):
        out.append(f"[meaning-plane] {omp.get('status')}/{omp.get('rows')} -> "
                   f"{nmp.get('status')}/{nmp.get('rows')}")
    return out


def _directive_delta(old: dict, new: dict) -> str:
    o, n = old.get("directives") or {}, new.get("directives") or {}
    oc = sum(len(v) for v in o.values())
    nc = sum(len(v) for v in n.values())
    return (f"{nc} directive clause(s) over {len(n)} rule(s) "
            f"— was {oc} over {len(o)} ({nc - oc:+d} clauses)")


# ---------------------------------------------------------------------------
# The self-test: a mutation this gate is REQUIRED to notice
# ---------------------------------------------------------------------------


def _strip_directives(root: pathlib.Path) -> int:
    """Delete every when/then/never from every concept YAML. Returns the clause count removed."""
    removed = 0
    for f in sorted((root / "ontology" / "concepts").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rules = ((doc.get("contract") or {}).get("rules") or [])
        touched = False
        for r in rules:
            for k in DIRECTIVE_KEYS:
                if k in r:
                    del r[k]
                    removed += 1
                    touched = True
        if touched:
            f.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return removed


def _reproject(root: pathlib.Path) -> bool:
    """Re-render the derived concept and rule pages from the YAML, as a migration commit would.

    `mac_okf.build(src, out)` takes the concepts directory as BOTH arguments — the read-view `*.md`
    and the whole `rules/` subtree are derived and it rmtree's the latter first, while never touching
    a `*.yaml`. Returns False rather than raising: a self-test that dies because the projector moved
    should report that it could not prove the page dimension, not crash.
    """
    try:
        sys.path.insert(0, str(HERE.parent))
        from sdk.project.mac_okf import build                        # noqa: PLC0415
        cdir = root / "ontology" / "concepts"
        build(cdir, cdir)
        return True
    except Exception:                                                # noqa: BLE001
        return False


def self_test(bundle: pathlib.Path) -> int:
    """Copy the bundle, delete every directive, and REQUIRE this gate to go red.

    This is the exact mutation that left check_concept_narrative, check_canon_binding and
    check_prose_moved all green. If it leaves this gate green too, this gate is decoration and says so
    about itself rather than waiting to be trusted.
    """
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td) / bundle.name
        shutil.copytree(bundle, work, symlinks=True,
                        ignore=shutil.ignore_patterns("*.duckdb", ".git"))
        try:
            frozen = capture(work)
        except Exception as exc:                                   # noqa: BLE001
            print(f"REFUSED: could not capture the copy — {type(exc).__name__}: {exc}")
            return 2

        n = _strip_directives(work)
        if n == 0:
            fails.append("the mutation removed 0 clauses — nothing was tested")
        #: AND REGENERATE, because that is what a real migration commit does. Without this the pages
        #: on disk are merely STALE, not blanked, and the page assertion below would be testing
        #: something the mutation never did — which the self-test caught on its first run.
        regenerated = _reproject(work)
        if not regenerated:
            fails.append("could not re-run the projector on the copy, so the page dimension of this "
                         "self-test proves nothing; fix that rather than dropping the assertion")
        after = capture(work)
        diffs = compare(frozen, after)

        if not diffs:
            fails.append(f"VACUOUS: {n} directive clause(s) deleted and this gate reported NO "
                         f"difference. That is the failure this gate exists to avoid.")
        # And it must notice in the places that actually matter, not merely somewhere.
        if not any(d.startswith("[prompt]") for d in diffs):
            fails.append("the prompt digest did not move, though `never` feeds it verbatim")
        if not any(d.startswith("[rule-page") for d in diffs):
            fails.append("no rule page changed, though the pages render those keys")

        before_n = sum(len(v) for v in (frozen.get("directives") or {}).values())
        if before_n != n:
            fails.append(f"counted {before_n} clauses but removed {n} — the measure and the mutation "
                         f"disagree, so one of them is wrong")

    for f in fails:
        print(f"  FAIL  {f}")
    print(("FAIL" if fails else "PASS") + f": check_rule_baseline --self-test — "
          f"{len(fails)} failure(s); the deletion mutation must be visible in the prompt and the pages")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Freeze and compare a bundle's rule behaviour.")
    ap.add_argument("root", nargs="?", help="the bundle root (the directory holding mac.project.yaml)")
    ap.add_argument("--capture", action="store_true", help="write the freeze instead of comparing")
    ap.add_argument("--self-test", action="store_true", help="prove this gate fails on total deletion")
    ap.add_argument("--show-prompt", action="store_true", help="print the built prompt and exit")
    a = ap.parse_args()

    if a.self_test:
        if not a.root:
            print("REFUSED: --self-test needs a bundle to copy. It mutates the COPY, never the bundle.")
            return 2
        return self_test(pathlib.Path(a.root).resolve())

    if not a.root:
        print("REFUSED: a bundle root is required.")
        return 2
    root = pathlib.Path(a.root).resolve()
    if not (root / "mac.project.yaml").is_file():
        print(f"REFUSED: {root} holds no mac.project.yaml — nothing declares how it is built.")
        return 2

    try:
        _neighbours.ensure_runtime_on_path()
    except _neighbours.RuntimeMissing as exc:
        print(f"REFUSED: {exc}")
        return 2

    if a.show_prompt:
        from mac_runtime.interpret.prompt import build_system_prompt
        from mac_runtime.interpret.vocabulary import Vocabulary
        from mac_runtime.ontology.index import OntologyIndex
        idx = OntologyIndex.from_directory(root)
        print(build_system_prompt(Vocabulary.from_index(idx), as_of=AS_OF, index=idx))
        return 0

    path = root / BASELINE_REL
    now = capture(root)
    nq = len(now.get("behaviour") or {})
    if nq == 0:
        print("REFUSED: 0 captured intents under acceptance/answers — a freeze over an empty "
              "population is the defect, not a baseline.")
        return 2

    if a.capture:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        planned = sum(1 for v in now["behaviour"].values() if v.get("outcome") == "Plan")
        d = now.get("directives") or {}
        print(f"WROTE {BASELINE_REL} — {nq} intent(s) ({planned} planned), prompt "
              f"{now['prompt']['chars']} chars, {len(now['rule_pages'])} rule page(s), "
              f"{sum(len(v) for v in d.values())} directive clause(s) over {len(d)} rule(s)")
        return 0

    if not path.is_file():
        print(f"REFUSED: no freeze at {BASELINE_REL}. Run --capture first; comparing against nothing "
              f"is a PASS that means nothing.")
        return 2
    old = json.loads(path.read_text(encoding="utf-8"))
    diffs = compare(old, now)
    for d in diffs:
        print(f"  {d}")
    planned = sum(1 for v in now["behaviour"].values() if v.get("outcome") == "Plan")
    verdict = "FAIL" if diffs else "PASS"
    print(f"{verdict}: check_rule_baseline — {len(diffs)} difference(s) over {nq} intent(s) "
          f"({planned} planned), {len(now['rule_pages'])} rule page(s), prompt "
          f"{now['prompt']['chars']} chars; {_directive_delta(old, now)}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
