#!/usr/bin/env python3
"""gate_register.py — A RED GATE STOPS SOMETHING: the standing-failure register the framework gate
runner reads, so that exit 1 means NEWS and not weather.

THE MEASUREMENT, 2026-09-29. `run_framework_gates.sh` over contoso5: 48/78 green, 11 failing, 19
could-not-run — and that was ordinary. The kit records "in a pristine clone both suites are red:
30/37"; the wiki records baseline 30/34. Exit 1 had been 1 continuously, so it switched nothing:
a parity gate had reported the schema contradicting the vocabulary for two days inside that run
while a bundle was authored with the retired term, and nobody stopped. A signal that is always on
is not a signal.

Standing failures already existed — in three PROSE homes with zero machine readers: the runner's
own header (`check_topology`… "run bare: PASS", stale — it fails bare today), a PROTOCOL entry
("left red deliberately"), the platform's BACKLOG (`check_mac_public` fails — stale, it passes).
Two of three had outlived their facts before this file existed. That is the STALE defect, and it
is why a declaration here that outlives its red FAILS the suite, the way a stale waiver fails
`test_the_intent_waivers_are_not_stale` in the platform.

THE RULE. Every non-green gate is one of exactly four things, and the runner exits 0 only when
the last three are empty:
  standing            declared: kind, owner, since, reason, expected — LISTED with its owner
  absent-by-design    a could-not-run whose subject the bundle legitimately lacks — LISTED
  undeclared-red      a FAIL or could-not-run nobody declared                          -> exit 1
  stale-declaration   a declared red that is now green, or names a gate that no longer exists
                                                                                       -> exit 1
  declaration-mismatch the declared kind is not what happened (fail vs could-not-run)  -> exit 1
A could-not-run is RED unless declared `subject-absent-by-design`: the runner's header once
claimed moving repo-subject gates would make the suite greener; measured bare, five of eight were
FAILING behind the calling-convention error. Could-not-run had hidden five reds.

TWO FILES, BY SCOPE, and the scope is enforced. A fact about this repository (the protocol gate's
orphans, the artifact registry's self-test) is one fact for every bundle: it lives in
`tools/framework_gate_failures.yaml` (`scope: repo`), always read. A fact about one bundle (a
computed concept with no canonical key) lives with the bundle in
`<bundle>/acceptance/standing_failures.yaml` (`scope: bundle:<name>`), read when present. An
entry in the wrong file is refused, exit 2 — without that rule the framework file becomes the
dumping ground within a week. There is no `--override`: editing the register is one line and IS
the override, recorded where the next reader finds it.

FORMAT (reused from the floor files: DECLARED / OWNER / REVIEW BY / STANDING):
    spec_version: mac.gate_failures/1
    scope: repo | bundle:<name>
    declared: YYYY-MM-DD
    review_by: YYYY-MM-DD           # printed as REVIEW OVERDUE after this date; not (yet) a failure
    standing: <n>                   # MUST equal len(entries) — two statements of one size cannot drift
    entries:
      check_x.py:
        kind: fail | could-not-run
        class: subject-absent-by-design | cannot-open     # required with could-not-run
        owner: operator | platform | data-plane | unknown  # `unknown` is a declared value; "" is not
        since: YYYY-MM-DD
        reason: <the gate's own last line>
        expected: <what makes it green>
        record: <optional: protocol/decision path>

Exit: 0 clean (standing may be > 0 — every one printed with an owner) · 1 news · 2 the register
itself could not be read (malformed, ownerless, wrong scope) — a broken register does not turn 27
declared reds into 27 undeclared ones and exit 1, which is the exit this file exists to make rare.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

SPEC = "mac.gate_failures/1"
KINDS = ("fail", "could-not-run")
CNR_CLASSES = ("subject-absent-by-design", "cannot-open")
OWNERS = ("operator", "platform", "data-plane", "unknown")
REQUIRED = ("kind", "owner", "since", "reason", "expected")
NEWS = ("undeclared-red", "stale-declaration", "declaration-mismatch")


class RegisterError(Exception):
    """The register could not be read as a register. Exit 2, never a shrug."""


# ── loading ───────────────────────────────────────────────────────────────────────────────────
def _date(v, what: str, where: str) -> dt.date:
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v))
    except Exception as exc:  # noqa: BLE001
        raise RegisterError(f"{where}: {what} must be a date (YYYY-MM-DD), got {v!r}") from exc


def validate_doc(doc: dict, where: str, expect_scope: str | None = None) -> dict[str, dict]:
    """The document's own rules; returns gate -> entry with `_scope` and `_file` attached."""
    if not isinstance(doc, dict):
        raise RegisterError(f"{where}: not a mapping")
    if doc.get("spec_version") != SPEC:
        raise RegisterError(f"{where}: spec_version must be {SPEC!r}, got {doc.get('spec_version')!r}")
    scope = str(doc.get("scope") or "")
    if not (scope == "repo" or (scope.startswith("bundle:") and len(scope) > 7)):
        raise RegisterError(f"{where}: scope must be 'repo' or 'bundle:<name>', got {scope!r}")
    if expect_scope == "repo" and scope != "repo":
        raise RegisterError(f"{where}: the framework register carries scope 'repo' only; {scope!r} "
                            f"belongs in the bundle's acceptance/standing_failures.yaml")
    if expect_scope == "bundle" and not scope.startswith("bundle:"):
        raise RegisterError(f"{where}: a bundle register carries scope 'bundle:<name>'; {scope!r} "
                            f"belongs in tools/framework_gate_failures.yaml")
    _date(doc.get("declared"), "declared", where)
    if doc.get("review_by") is not None:
        _date(doc.get("review_by"), "review_by", where)
    entries = doc.get("entries") or {}
    if not isinstance(entries, dict):
        raise RegisterError(f"{where}: entries must be a mapping keyed by gate file name")
    if doc.get("standing") != len(entries):
        raise RegisterError(f"{where}: standing says {doc.get('standing')!r} but {len(entries)} "
                            f"entr(y/ies) are declared — two statements of one size disagree, so one is stale")
    out = {}
    for gate, e in entries.items():
        g = str(gate)
        if not (g.startswith("check_") and g.endswith(".py")):
            raise RegisterError(f"{where}: {g!r} is not a gate file name (check_*.py)")
        if not isinstance(e, dict):
            raise RegisterError(f"{where}: {g}: entry must be a mapping")
        for k in REQUIRED:
            if not str(e.get(k) or "").strip():
                raise RegisterError(f"{where}: {g}: {k} is required — a red without an {k} is a permanent exemption")
        if e["kind"] not in KINDS:
            raise RegisterError(f"{where}: {g}: kind must be one of {KINDS}, got {e['kind']!r}")
        if e["kind"] == "could-not-run" and e.get("class") not in CNR_CLASSES:
            raise RegisterError(f"{where}: {g}: a could-not-run must say which: {CNR_CLASSES}")
        if e["owner"] not in OWNERS:
            raise RegisterError(f"{where}: {g}: owner must be one of {OWNERS} (the literal 'unknown' "
                                f"is a declared value; a made-up name is not)")
        _date(e["since"], "since", f"{where}: {g}")
        out[g] = {**e, "_scope": scope, "_file": where}
    return out


def load(paths: list[str]) -> tuple[dict[str, dict], list[str]]:
    """Merge the framework register (must exist) and any bundle register (read when present)."""
    import yaml  # noqa: PLC0415

    merged: dict[str, dict] = {}
    notes: list[str] = []
    for i, p in enumerate(paths):
        path = pathlib.Path(p)
        expect = "repo" if i == 0 else "bundle"
        if not path.is_file():
            if i == 0:
                raise RegisterError(f"{path}: the framework register is missing — it may be empty, not absent")
            notes.append(f"no bundle register at {path} — every bundle red is undeclared")
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RegisterError(f"{path}: not YAML — {exc}") from exc
        for gate, e in validate_doc(doc, str(path), expect).items():
            if gate in merged:
                raise RegisterError(f"{gate} is declared twice: {merged[gate]['_file']} and {path}")
            merged[gate] = e
        rb = doc.get("review_by")
        if rb is not None and _date(rb, "review_by", str(path)) < dt.date.today():
            notes.append(f"REVIEW OVERDUE: {path} declared review_by {rb}")
    return merged, notes


# ── judging (pure) ────────────────────────────────────────────────────────────────────────────
def _norm(verdict: str) -> str:
    v = verdict.strip().upper()
    if v.startswith("PASS"):
        return "PASS"
    if v.startswith("COULD-NOT-RUN"):
        return "CNR"
    return "FAIL"


def judge(raw: dict[str, tuple[str, str]], reg: dict[str, dict]) -> list[tuple[str, str, str]]:
    """raw: gate -> (verdict as the runner printed it, its last line). Returns (class, gate, sentence)."""
    out: list[tuple[str, str, str]] = []
    for gate in sorted(raw):
        verdict, line = raw[gate]
        v = _norm(verdict)
        e = reg.get(gate)
        if v == "PASS":
            if e is None:
                out.append(("green", gate, ""))
            else:
                out.append(("stale-declaration", gate,
                            f"remove {gate} from {e['_file']} — it passed; a declaration that outlives "
                            f"its red is how a once-fixed gap gets re-opened unnoticed"))
        elif v == "FAIL":
            if e is None:
                out.append(("undeclared-red", gate, line))
            elif e["kind"] != "fail":
                out.append(("declaration-mismatch", gate,
                            f"declared could-not-run ({e.get('class')}), observed {verdict}: {line}"))
            else:
                out.append(("standing", gate, f"{e['owner']} · since {e['since']} · {e['reason']} → {e['expected']}"))
        else:
            if e is None:
                out.append(("undeclared-red", gate, line))
            elif e["kind"] != "could-not-run":
                out.append(("declaration-mismatch", gate, f"declared fail, observed could-not-run: {line}"))
            elif e["class"] == "subject-absent-by-design":
                out.append(("absent-by-design", gate, f"{e['owner']} · {e['reason']}"))
            else:
                out.append(("standing", gate, f"{e['owner']} · since {e['since']} · {e['reason']} → {e['expected']}"))
    for gate, e in sorted(reg.items()):
        if gate not in raw:
            out.append(("stale-declaration", gate,
                        f"{gate} is declared in {e['_file']} but no such gate ran — renamed or removed; "
                        f"the declaration excuses nothing"))
    return out


def verdict(findings: list[tuple[str, str, str]]) -> tuple[int, dict[str, int]]:
    counts: dict[str, int] = {}
    for cls, _g, _s in findings:
        counts[cls] = counts.get(cls, 0) + 1
    return (1 if any(counts.get(k) for k in NEWS) else 0), counts


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────
def _read_tsv(path: str) -> dict[str, tuple[str, str]]:
    raw: dict[str, tuple[str, str]] = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        gate, verd = parts[0], parts[1] if len(parts) > 1 else ""
        raw[gate] = (verd, parts[2] if len(parts) > 2 else "")
    return raw


def _reconcile(a) -> int:
    try:
        reg, notes = load(a.registers)
    except RegisterError as exc:
        print(f"could not run: gate register — {exc}", file=sys.stderr)
        return 2
    raw = _read_tsv(a.reconcile)
    findings = judge(raw, reg)
    code, counts = verdict(findings)
    c = dict(kv.split("=", 1) for kv in a.counts)
    standing = [f for f in findings if f[0] == "standing"]
    absent = [f for f in findings if f[0] == "absent-by-design"]
    news = [f for f in findings if f[0] in NEWS]
    print()
    if standing:
        print(f"STANDING — {len(standing)} declared red(s), each with an owner (the register, not this run, is where they change):")
        for _cls, g, s in standing:
            print(f"  {g:<42} {s}")
    if absent:
        print(f"ABSENT BY DESIGN — {len(absent)} gate(s) whose subject this bundle does not carry:")
        for _cls, g, s in absent:
            print(f"  {g:<42} {s}")
    for n in notes:
        print(f"  note: {n}")
    if news:
        print(f"NEWS — {len(news)} thing(s) the register does not describe:")
        for cls, g, s in news:
            print(f"  [{cls}] {g:<32} {s}")
    print()
    tail = (f"{c.get('PASS')}/{c.get('TOTAL')} green over {a.bundle}, "
            f"{c.get('BUNDLE_JUDGED')} judged the bundle and {c.get('REPO_SUBJ')} judged this repository; "
            f"{len(standing)} standing (declared, owned — listed above), {len(absent)} absent by design; "
            f"self-test arm {c.get('ST_PASS')}/{c.get('ST_DECL')} green over {c.get('ST_DECL')} declaring one of "
            f"{c.get('TOTAL')} ({c.get('ST_NONE')} declare none — judged on the bundle run alone) ({c.get('SECS')}s)")
    if code == 0:
        print(f"PASS: run_framework_gates — {tail}")
    else:
        print(f"FAIL: run_framework_gates — {counts.get('undeclared-red', 0)} undeclared red, "
              f"{counts.get('stale-declaration', 0)} stale declaration(s), "
              f"{counts.get('declaration-mismatch', 0)} mismatch(es) — {tail}")
    return code


def _check(a) -> int:
    try:
        reg, notes = load(a.check)
    except RegisterError as exc:
        print(f"could not run: gate register — {exc}", file=sys.stderr)
        return 2
    for n in notes:
        print(f"  note: {n}")
    by_scope: dict[str, int] = {}
    for e in reg.values():
        by_scope[e["_scope"]] = by_scope.get(e["_scope"], 0) + 1
    print(f"gate register: {len(reg)} standing failure(s) declared "
          + (f"({', '.join(f'{k} {v}' for k, v in sorted(by_scope.items()))})" if by_scope else "(none)"))
    return 0


# ── self-test: one case per class in the table, over dicts ────────────────────────────────────
def _self_test() -> int:
    import textwrap  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    fails: list[str] = []

    def case(label: str, cond: bool) -> None:
        if not cond:
            fails.append(label)

    def entry(kind="fail", owner="platform", cls=None, **kw):
        e = {"kind": kind, "owner": owner, "since": "2026-09-29", "reason": "r", "expected": "e",
             "_scope": "repo", "_file": "tools/framework_gate_failures.yaml", **kw}
        if cls:
            e["class"] = cls
        return e

    def cls_of(findings, gate):
        return next(c for c, g, _s in findings if g == gate)

    # clean: all PASS, empty register
    f = judge({"check_a.py": ("PASS", "")}, {})
    case("clean tree is green and exits 0", cls_of(f, "check_a.py") == "green" and verdict(f)[0] == 0)
    # undeclared-red, both forms
    f = judge({"check_a.py": ("FAIL (exit 1)", "FAIL: x")}, {})
    case("an undeclared FAIL is news (exit 1)", cls_of(f, "check_a.py") == "undeclared-red" and verdict(f)[0] == 1)
    f = judge({"check_a.py": ("COULD-NOT-RUN", "could not run: y")}, {})
    case("an undeclared could-not-run is news, not weather", cls_of(f, "check_a.py") == "undeclared-red" and verdict(f)[0] == 1)
    # standing, listed with owner, exit 0
    f = judge({"check_a.py": ("FAIL (exit 1)", "FAIL: x")}, {"check_a.py": entry(owner="data-plane")})
    case("a declared FAIL stands, exits 0", cls_of(f, "check_a.py") == "standing" and verdict(f)[0] == 0)
    case("the owner travels with the verdict", "data-plane" in next(s for c, g, s in f if g == "check_a.py"))
    f = judge({"check_a.py": ("COULD-NOT-RUN", "")}, {"check_a.py": entry(kind="could-not-run", cls="cannot-open")})
    case("a declared cannot-open stands (it is red)", cls_of(f, "check_a.py") == "standing" and verdict(f)[0] == 0)
    f = judge({"check_a.py": ("COULD-NOT-RUN", "")}, {"check_a.py": entry(kind="could-not-run", cls="subject-absent-by-design")})
    case("subject-absent-by-design is listed, exits 0", cls_of(f, "check_a.py") == "absent-by-design" and verdict(f)[0] == 0)
    # stale, both forms
    f = judge({"check_a.py": ("PASS", "")}, {"check_a.py": entry()})
    case("a declared red that passed is STALE (exit 1)", cls_of(f, "check_a.py") == "stale-declaration" and verdict(f)[0] == 1)
    f = judge({"check_a.py": ("PASS", "")}, {"check_ghost.py": entry()})
    case("a declaration for a gate that did not run is STALE", cls_of(f, "check_ghost.py") == "stale-declaration" and verdict(f)[0] == 1)
    # mismatch
    f = judge({"check_a.py": ("COULD-NOT-RUN", "")}, {"check_a.py": entry(kind="fail")})
    case("declared fail, observed could-not-run is a mismatch", cls_of(f, "check_a.py") == "declaration-mismatch" and verdict(f)[0] == 1)
    f = judge({"check_a.py": ("FAIL (self-test)", "")}, {"check_a.py": entry(kind="could-not-run", cls="cannot-open")})
    case("declared could-not-run, observed FAIL is a mismatch", cls_of(f, "check_a.py") == "declaration-mismatch")
    # negative control
    f = judge({"check_a.py": ("FAIL (exit 1)", "")}, {"check_a.py": entry(owner="unknown")})
    case("owner 'unknown' is a declared value and stands", cls_of(f, "check_a.py") == "standing")

    # refusals through validate_doc (exit-2 branch), each must raise
    base = textwrap.dedent("""
        spec_version: mac.gate_failures/1
        scope: repo
        declared: 2026-09-29
        standing: 1
        entries:
          check_a.py: {kind: fail, owner: platform, since: 2026-09-29, reason: r, expected: e}
    """)

    def refuses(label, text, expect="repo"):
        try:
            validate_doc(yaml.safe_load(text), "x.yaml", expect)
        except RegisterError:
            return
        fails.append(f"{label}: accepted")

    validate_doc(yaml.safe_load(base), "x.yaml", "repo")  # must load
    refuses("missing owner refused", base.replace("owner: platform, ", ""))
    refuses("blank owner refused", base.replace("owner: platform", "owner: ''"))
    refuses("made-up owner refused", base.replace("owner: platform", "owner: bob"))
    refuses("standing != entries refused", base.replace("standing: 1", "standing: 2"))
    refuses("bundle scope in the framework file refused", base.replace("scope: repo", "scope: bundle:x"))
    refuses("repo scope in a bundle file refused", base, expect="bundle")
    refuses("could-not-run without class refused", base.replace("kind: fail", "kind: could-not-run"))
    refuses("not a gate name refused", base.replace("check_a.py", "a.py"))
    refuses("wrong spec refused", base.replace("mac.gate_failures/1", "mac.gate_failures/9"))
    refuses("bad date refused", base.replace("declared: 2026-09-29", "declared: yesterday"))

    n = 22
    if fails:
        print("FAIL: gate_register self-test — " + "; ".join(fails))
        return 1
    print(f"PASS: gate_register self-test — {n}/{n} case(s): one per class in the table (green, undeclared-red x2, "
          f"standing x2, absent-by-design, stale x2, mismatch x2, unknown owner) and ten register refusals")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", nargs="+", metavar="REGISTER", help="validate the registers; exit 2 if any cannot be read")
    ap.add_argument("--reconcile", metavar="TSV", help="gate<TAB>verdict<TAB>last-line per gate, as the runner recorded them")
    ap.add_argument("--registers", nargs="+", default=[], metavar="REGISTER")
    ap.add_argument("--counts", nargs="*", default=[], metavar="K=V")
    ap.add_argument("--bundle", default="<bundle>")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if a.check:
        return _check(a)
    if a.reconcile:
        return _reconcile(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
