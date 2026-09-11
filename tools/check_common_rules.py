#!/usr/bin/env python3
"""check_common_rules — a concept restating a law MAC already states is a copy, not a contract.

WHY
---
mac_rules.yaml states behavioural contracts that hold for ANY conformant ontology, in the ORDINARY
rule shape — id · kind · subject · when · then · never · realized_by, plus `scope` carrying a class
selector rather than a source name. It is not a new construct. A concept matching
a common rule's `scope` gets that behaviour whether or not it writes anything. So a concept that
writes the rule out again is not adding a contract — it is adding a COPY of one, and copies drift.

MEASURED on gaps/fpl2: thirteen concepts each wrote the same refusal law. 13 distinct `when` wordings,
13 `then`, 12 `never`. Three of the thirteen carried NO information beyond the concept's own name, and
one (`market`) ended up with a bare `then` promising an answer it could not produce. None of that was
visible to any gate, because every copy was individually well-formed.

WHAT IT REPORTS
---------------
  MAC003  a local rule that adds NOTHING the common rule does not already say — pure restatement.
  MAC005  a local rule that adds only PARAMETERS (a confusable list, a via) — MAC offers a place to
          put just those, and the concept is carrying the whole law to deliver them.
  MAC008  a local rule that could NOT be compared to any common rule in its class, reported at INFO.
          Not a defect and not a clearance: a SKIP, counted out loud (see IDENTITY below).

IDENTITY — WHICH LOCAL RULE IS "THE SAME RULE" AS WHICH COMMON RULE
-------------------------------------------------------------------
This is the whole check. Everything downstream is a verdict on a pair, so a wrong pairing is a wrong
verdict every time.

MEASURED DEFECT (2026-09-11, fixed here). The pairing was `local.realized_by.udf == common.realized_by.udf`.
For an UNBOUND rule that field is `None` — on BOTH sides — so `None == None` paired EVERY unbound local
rule with EVERY unbound common rule in its class. Seven of the nine common rules are unbound, so on one
bundle 18 witnesses were reported where the true count is 0, and a single local rule appeared THREE
times because three unbound common rules each "matched" it. Four operators on four different bundles
were each told to delete 30, 22, 25 and 34 rules that were not copies of anything. All four refused.
Absence of a binding on both sides is not evidence of sameness; it is absence of evidence.

WHAT COUNTS AS THE SAME RULE NOW — positive evidence only, in two tiers:

  1. DECLARED.  Both sides name a canon and share one: `realized_by.udf`. The author has SAID which
     law this rule realizes; nothing is inferred. Different canons named on both sides means different
     laws — decided, not skipped.

  2. EVIDENCED.  At least one side is unbound, so there is no declared link. Then the two are the same
     statement only when they demonstrably say the same thing: the same rule `kind`, and the SAME set
     of semantic elements (REFUSE · no-guess · no-zero-fill · substitution ban · null branch · via a
     register), that set carrying at least TWO of them.
       · EQUALITY, not overlap. A local rule carrying an element the common rule lacks is an OVERRIDE
         (ob_reach's refusal has a second branch — a resolved row whose null IS the answer — that the
         generic law does not mention), and an override is the point of allowing local rules at all. A
         local rule carrying FEWER elements is saying something narrower, and narrower is not a copy.
       · TWO, not one. MEASURED on a second bundle while fixing this: a rule about an unresolved-name
         FLAG matched the catalogued-member law on the single element `null branch`, because both are
         guarantees and both contain the word "null". One element in common is a shared word, not a
         shared law. Below the threshold the pair is SKIPPED and said out loud, never reported.
     This tier is what still catches the original thirteen: before they were bound to a canon they were
     hand-written prose whose element sets matched the common law exactly — four elements, 13 wordings.

  3. NEITHER.  Both element sets cannot establish anything — typically the common rule states a law
     this vocabulary has no probe for (unit algebra, period reading), so its element set is empty. Then
     the honest answer is "not compared", and it is SAID: one MAC008 witness per local rule, at INFO.
     A silent skip would read as a clearance, and the bundle would look cleaner than it was checked.

Elements, not wording, is deliberate and was measured: across the thirteen copies the mean string
similarity to the canon render is 0,88 and chasing it higher made things worse — the copies disagree
on clause ORDER and on label, which carries nothing.

ONE WITNESS PER LOCAL RULE. The first matching common rule decides; the rest are not re-reported. The
old fan-out (one witness per (local, common) pair) inflated a count that operators then had to audit
by hand.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* A concept that genuinely DIFFERS from the common law — see OVERRIDE in tier 2. Never reported.
* A bundle with no mac_rules.yaml reachable. Then nothing is reported and the check says it could not
  run, rather than reporting a clean bundle.

KNOWN, NOT FIXED HERE (adjacent, and it under-reports rather than over-reports): common rules scoped
`concept.class: "*"` are bucketed under the literal key `*`, which no concept's class equals, so a
wildcard common rule currently reaches no concept at all. Widening it changes what every bundle is
told; that is its own change, with its own before/after.
"""
from __future__ import annotations

import sys
from pathlib import Path

import mac_diag as D

# One SET of spellings per semantic element. Narrow on purpose: each maps to a clause the canons
# actually emit. Used to decide whether two rules SAY the same thing when neither declares which law
# it realizes — never to decide wording quality.
_ELEMENTS = [("REFUSE", ("refuse",)), ("no-guess", ("guess", "estimat")),
             ("no-zero-fill", ("zero", "to 0", "coerc")), ("substitution ban", ("substitut",)),
             ("null branch", ("null",)), ("via a register", ("via ",))]

_DERIVED_PARAMS = ("source", "label", "thing")   # read from the concept, never a bundle contribution

# How many elements two rules must share, identically, before an unbound pair counts as the same law.
# Two, because one is a word in common (see _same_law); the thirteen authored copies that motivated
# this check share four.
_DISTINCT_ELEMENTS = 2


def _flat(rule) -> str:
    return " ".join(" ".join(str(rule.get(k) or "").split())
                    for k in ("when", "then", "never")).lower()


def _elements(rule) -> frozenset:
    text = _flat(rule)
    return frozenset(label for label, spellings in _ELEMENTS
                     if any(s in text for s in spellings))


def _udfs(rule) -> set:
    """The canon(s) a rule declares. `realized_by` is a canonRef OR a list of them (mac.schema.json
    #canonBinding), so a list must not be read with `.get`."""
    rb = rule.get("realized_by")
    binds = rb if isinstance(rb, list) else [rb]
    return {str(b["udf"]) for b in binds if isinstance(b, dict) and b.get("udf")}


def _params(rule) -> dict:
    out = {}
    rb = rule.get("realized_by")
    for b in (rb if isinstance(rb, list) else [rb]):
        if isinstance(b, dict) and isinstance(b.get("params"), dict):
            out.update(b["params"])
    return out


def _kind(rule) -> str:
    return str(rule.get("kind") or "").strip().lower()


def _same_law(local, common) -> tuple:
    """(basis, undecidable_reason) for one (local, common) pair.

    basis      non-empty -> they are the same law, and the string SAYS on what evidence.
    reason     non-empty -> the pair could not be decided either way; the caller must report the skip.
    both empty -> decided: different laws.
    """
    lu, cu = _udfs(local), _udfs(common)
    if lu and cu:
        shared = sorted(lu & cu)
        if shared:
            return (f"both realize {shared[0]}", "")
        return ("", "")                       # different canons named — decided, different laws
    if _kind(local) != _kind(common):
        return ("", "")                       # a rule kind is declared; unequal kinds decide it
    le, ce = _elements(local), _elements(common)
    if not le or not ce:
        # NO DECLARED LINK AND NOTHING COMPARABLE. This is exactly the case that used to be paired by
        # `None == None`. It is now a skip, and the skip is reported.
        return ("", "neither declares a canon and their clauses carry no comparable element")
    if le != ce:
        return ("", "")                       # one says more (override) or less — not the same rule
    if len(le) < _DISTINCT_ELEMENTS:
        # ONE ELEMENT IS A SHARED WORD, NOT A SHARED LAW. MEASURED on a second bundle while fixing
        # this check: a rule about an unresolved-name FLAG ("when the flag is false the name is null")
        # matched the catalogued-member law ("never treat a catalogued member as a null") on the single
        # element `null branch`, because both are guarantees and both contain the word. That is the
        # same defect one notch weaker, so the evidence has to be distinctive, not merely present.
        return ("", f"their only common element ({', '.join(sorted(le))}) is one coarse token — a "
                    f"shared word is not a shared law")
    return (f"no canon binding on either side, but same kind and the same elements "
            f"({', '.join(sorted(le))})", "")


def _canon_signature(udf: str):
    """The parameter names a canon declares, or None when the canon cannot be read. Read from the
    function's own signature — an earlier draft listed them in the rule under an invented
    `bundle_may_supply` key, a second home for a fact the function already declares."""
    cache = _canon_signature.__dict__.setdefault("_cache", {})
    if udf in cache:
        return cache[udf]
    try:
        import inspect
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from canon import rules as _CR
        fn = _CR.CANONS.get(udf)
        cache[udf] = set(inspect.signature(fn).parameters) if fn else None
    except Exception:                                                   # noqa: BLE001
        cache[udf] = None
    return cache[udf]


def check_common_rules(root) -> list:
    try:
        import yaml
        f = Path(__file__).resolve().parent.parent / "mac_rules.yaml"
        if not f.exists():
            return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_common_rules",
                                 summary="mac_rules.yaml is not reachable, so common-rule coverage "
                                         "is UNKNOWN, not clean")]
        common = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("rules") or []
    except Exception as exc:                                            # noqa: BLE001
        return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_common_rules",
                             summary=f"common rules could not be read: {exc!r}")]

    by_class = {}
    for c in common:
        cls = (c.get("scope") or {}).get("concept.class")
        if cls:
            by_class.setdefault(cls, []).append(c)

    restated, params_only, uncompared = [], [], []
    for p in sorted((Path(root) / "ontology" / "concepts").glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        cls = ((doc.get("concept") or {}).get("class"))
        commons = by_class.get(cls) or []
        if not commons:
            continue
        rel = str(p.relative_to(root))
        for r in ((doc.get("contract") or {}).get("rules") or []):
            rid, paired, skipped = r.get("id", ""), None, []
            for cr in commons:
                basis, reason = _same_law(r, cr)
                if basis:
                    paired = (cr, basis)
                    break                       # ONE witness per local rule, never one per pair
                if reason:
                    skipped.append(reason)
            if not paired:
                if skipped:
                    uncompared.append(D.Witness(
                        file=rel, path=rid,
                        detail=f"not compared against {len(skipped)} common rule(s) for class {cls} — "
                               f"{skipped[0]}"))
                continue
            cr, basis = paired
            cid = cr.get("id", "")
            # What the CONCEPT contributes beyond the common law: the canon parameters MAC cannot know.
            known, udf = set(), ""
            for u in sorted(_udfs(r)):
                sig = _canon_signature(u)
                if sig is None:
                    known, udf = None, u
                    break
                known, udf = known | sig, u
            if known is None:
                # The pairing stands, but the canon cannot be read, so a parameter cannot be told from
                # a restatement. Guessing here is what this check exists to stop doing.
                uncompared.append(D.Witness(
                    file=rel, path=rid,
                    detail=f"same law as {cid} ({basis}) but canon {udf} is unreadable, so its "
                           f"parameters cannot be distinguished from the law"))
                continue
            extra = {k: v for k, v in _params(r).items()
                     if k in known and k not in _DERIVED_PARAMS and v not in (None, "", False)}
            if extra:
                params_only.append(D.Witness(file=rel, path=rid,
                                             detail=f"supplies only {', '.join(sorted(extra))} "
                                                    f"to {cid}"))
            else:
                restated.append(D.Witness(file=rel, path=rid,
                                          detail=f"adds nothing {cid} does not say — {basis}"))
    out = []
    if restated:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_common_rules",
            summary=f"{len(restated)} concept rule(s) restate a law mac_rules.yaml already states for "
                    f"their class, adding nothing",
            note="Delete them. The behaviour does not change — that is the test: removing a rule that "
                 "only repeats the common one must not change what the bundle refuses. Each witness "
                 "names the common rule it copies and the evidence for that pairing; if the pairing "
                 "is wrong, the rule is an override and the check is the thing to fix.",
            witnesses=restated))
    if params_only:
        out.append(D.Diagnostic(
            code="MAC005", severity=D.INFO, source="check_common_rules",
            summary=f"{len(params_only)} concept rule(s) exist only to carry PARAMETERS to a common rule",
            note="Not a defect — the parameters are real knowledge only the author has (which measure "
                 "a reader would wrongly substitute). Recorded so the ratio of law to parameter is "
                 "visible: the law is MAC's, the parameters are the bundle's.",
            witnesses=params_only))
    if uncompared:
        # INFO, and severity is overridden from the taxonomy default deliberately: this blocks nothing
        # and accuses nobody. It exists so that "no MAC003" is not read as "every rule was cleared".
        out.append(D.Diagnostic(
            code="MAC008", severity=D.INFO, source="check_common_rules",
            summary=f"{len(uncompared)} concept rule(s) could not be compared to the common rules for "
                    f"their class — SKIPPED, not cleared",
            note="Neither side declares `realized_by`, so there is no stated identity, and the clauses "
                 "carry no element the other side can be measured against. Binding the rule to a canon "
                 "(or the common rule to one) makes the comparison decidable. Reported because a "
                 "silent skip reads as a clearance.",
            witnesses=uncompared))
    return out


# ── gate ──────────────────────────────────────────────────────────────────────────────────────────
def _could_not_run(diags) -> bool:
    """The two MAC008 diagnostics with NO witnesses are the could-not-run pair (mac_rules.yaml
    unreachable / unreadable). The MAC008 skip always carries witnesses."""
    return any(d.code == "MAC008" and d.source == "check_common_rules" and not d.witnesses
               for d in diags)


def _fails(diags) -> bool:
    return (any(d.severity == D.ERROR for d in diags)
            or any(d.code == "MAC003" for d in diags)
            or _could_not_run(diags))


def _counts(diags) -> str:
    n = {c: sum(len(d.witnesses) for d in diags if d.code == c) for c in ("MAC003", "MAC005", "MAC008")}
    return (f"{n['MAC003']} restatement(s), {n['MAC005']} parameter-carrier(s), "
            f"{n['MAC008']} not compared")


# ── self-test ─────────────────────────────────────────────────────────────────────────────────────
# Every case is a whole bundle written to a temp dir and run through the real check against the real
# mac_rules.yaml. A mutant per reject class, and a clean fixture that must pass.
_CLEAN = """
concept: {name: alpha, class: measure}
contract:
  rules:
    - id: alpha.resolve.abstraction_level
      kind: mac.rule_kind.resolution
      when: "a question asks at a coarser grain than the stored cell"
      then: "read at the level the question names, not the level the table happens to store"
      never: "inventing an intermediate level the grain declaration does not support"
    - id: alpha.resolve.reference_window
      kind: mac.rule_kind.resolution
      when: "a rate is asked without a window"
      then: "take the window the concept declares"
      never: "widening the window to make the rate look steadier"
    - id: alpha.aggregate.rollup
      kind: mac.rule_kind.aggregation
      when: "cells are folded over the declared hierarchy"
      then: "fold along the declared parent edge only"
"""
_MUTANT_BOUND_COPY = """
concept: {name: beta, class: measure}
contract:
  rules:
    - id: beta.exclusion.no_evidence
      kind: mac.rule_kind.exclusion
      when: "the resolved scope has no row"
      then: "REFUSE with an evidence-boundary answer"
      never: "returning an empty result framed as a real zero"
      realized_by: {udf: mac.canon.refuse_measure_no_row}
"""
_MUTANT_PROSE_COPY = """
concept: {name: gamma, class: measure}
contract:
  rules:
    - id: gamma.exclusion.nothing_there
      kind: mac.rule_kind.exclusion
      when: "the resolved period holds no row for what was asked"
      then: "REFUSE and say what was missing — never guess or estimate one, and never substitute a
             different figure"
      never: "handing back an empty result dressed as a real zero"
"""
_PARAMS_ONLY = """
concept: {name: delta, class: measure}
contract:
  rules:
    - id: delta.exclusion.no_evidence
      kind: mac.rule_kind.exclusion
      when: "the resolved scope has no row"
      then: "REFUSE with an evidence-boundary answer"
      never: "returning an empty result framed as a real zero"
      realized_by:
        udf: mac.canon.refuse_measure_no_row
        params: {confusable: ["a neighbouring figure"]}
"""
_OVERRIDE = """
concept: {name: epsilon, class: measure}
contract:
  rules:
    - id: epsilon.exclusion.no_evidence_with_branch
      kind: mac.rule_kind.exclusion
      when: "the resolved period holds no row, or holds one whose value is null"
      then: "REFUSE and say what was missing — never guess or estimate, never substitute a different
             figure; but a resolved row whose value is null is an ANSWER, report it as such"
      never: "handing back an empty result dressed as a real zero; coercing a real null to 0"
"""
_ONE_ELEMENT_IN_COMMON = """
concept: {name: eta, class: reference}
contract:
  rules:
    - id: eta.guarantee.resolution_flag
      kind: mac.rule_kind.guarantee
      when: "a member is displayed whose resolution flag is false"
      then: "show the code — the flag says the catalogue holds no readable name, so the name column is
             null and the source column says unresolved"
      never: "assuming every code carries a readable name"
"""
_TWO_DISTINCT_UNBOUND = """
concept: {name: zeta, class: measure}
contract:
  rules:
    - id: zeta.resolve.one
      kind: mac.rule_kind.resolution
      when: "a bare period is named"
      then: "read the period as the declared type dictates"
    - id: zeta.resolve.two
      kind: mac.rule_kind.resolution
      when: "a relative period is named"
      then: "anchor it to the latest stored cell"
    - id: zeta.resolve.three
      kind: mac.rule_kind.resolution
      when: "two grains are named at once"
      then: "take the finer of the two"
"""


def _run_fixture(name: str, files: dict):
    import tempfile
    with tempfile.TemporaryDirectory(prefix=f"ccr_{name}_") as td:
        cdir = Path(td) / "ontology" / "concepts"
        cdir.mkdir(parents=True)
        for fn, body in files.items():
            (cdir / fn).write_text(body, encoding="utf-8")
        return check_common_rules(td)


def _wit(diags, code) -> list:
    return [w for d in diags for w in d.witnesses if d.code == code]


def self_test() -> int:
    cases, bad = [], []

    def case(name, ok, detail=""):
        cases.append((name, ok, detail))
        if not ok:
            bad.append(name)

    # 1. CLEAN — distinct unbound rules, nothing restated, and the skip is VISIBLE.
    d = _run_fixture("clean", {"alpha.yaml": _CLEAN})
    case("clean fixture reports no restatement", not _wit(d, "MAC003"),
         f"got {len(_wit(d, 'MAC003'))}")
    case("clean fixture passes the gate", not _fails(d), _counts(d))
    case("clean fixture SAYS what it skipped", bool(_wit(d, "MAC008")),
         "the skip must be reported, never silent")

    # 2. MUTANT — a genuine copy, DECLARED: same canon as the common rule, no parameters.
    d = _run_fixture("bound_copy", {"beta.yaml": _MUTANT_BOUND_COPY})
    w = _wit(d, "MAC003")
    case("genuine bound copy is caught", len(w) == 1, f"got {len(w)}")
    case("bound copy names the common rule it copies",
         bool(w) and "mac.exclusion.no_evidence.measure" in w[0].detail,
         w[0].detail if w else "no witness")
    case("bound copy fails the gate", _fails(d), _counts(d))

    # 3. MUTANT — a genuine copy in the author's OWN WORDS, bound to nothing. This is the original
    #    thirteen: no canon anywhere, same kind, same elements.
    d = _run_fixture("prose_copy", {"gamma.yaml": _MUTANT_PROSE_COPY})
    w = _wit(d, "MAC003")
    case("genuine unbound prose copy is caught", len(w) == 1, f"got {len(w)}")
    case("prose copy states the evidence for the pairing",
         bool(w) and "same elements" in w[0].detail, w[0].detail if w else "no witness")

    # 4. THE DEFECT — two rules that are merely BOTH UNBOUND are not the same rule.
    d = _run_fixture("distinct_unbound", {"zeta.yaml": _TWO_DISTINCT_UNBOUND})
    w, u = _wit(d, "MAC003"), _wit(d, "MAC008")
    case("distinct unbound rules are NOT paired", not w,
         "; ".join(str(x) for x in w) or "none")
    case("each uncompared rule is reported ONCE, not once per common rule",
         len(u) == 3 and len({x.path for x in u}) == 3, f"{len(u)} witness(es) for 3 rules")

    # 4b. ONE ELEMENT IN COMMON is a shared word, not a shared law — the weaker form of the same
    #     defect. It must not be reported as a copy, and it must not vanish either.
    d = _run_fixture("one_element", {"eta.yaml": _ONE_ELEMENT_IN_COMMON})
    w, u = _wit(d, "MAC003"), _wit(d, "MAC008")
    case("a single shared element does not make a copy", not w,
         "; ".join(str(x) for x in w) or "none")
    case("the single-element near miss is reported as a skip",
         any("coarse token" in x.detail for x in u), "; ".join(str(x) for x in u) or "no skip")

    # 5. PARAMETERS, not a copy.
    d = _run_fixture("params", {"delta.yaml": _PARAMS_ONLY})
    case("a parameter carrier is MAC005, not MAC003",
         not _wit(d, "MAC003") and len(_wit(d, "MAC005")) == 1, _counts(d))
    case("a parameter carrier does not fail the gate", not _fails(d), _counts(d))

    # 6. OVERRIDE — says something the common law cannot. Never reported.
    d = _run_fixture("override", {"epsilon.yaml": _OVERRIDE})
    case("an override is not reported as a copy", not _wit(d, "MAC003"),
         "; ".join(str(x) for x in _wit(d, "MAC003")) or "none")

    for name, ok, detail in cases:
        print(f"  [{'ok ' if ok else 'bad'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    ok = len(cases) - len(bad)
    if bad:
        print(f"FAIL: check_common_rules self-test — {ok}/{len(cases)} cases, broken: "
              + ", ".join(bad))
        return 1
    print(f"PASS: check_common_rules self-test — {ok}/{len(cases)} cases")
    return 0


def main() -> int:                                                      # pragma: no cover
    args = sys.argv[1:]
    if "--self-test" in args:
        return self_test()
    root = args[0] if args else "."
    d = check_common_rules(root)
    body = D.render(d, root, show=D.INFO)
    if body:
        print(body)
    failed = _fails(d)
    verdict = "FAIL" if failed else "PASS"
    print(f"{verdict}: check_common_rules on {root} — {_counts(d)}")
    return 1 if failed else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
