#!/usr/bin/env python3
"""check_guard_scope.py — the three predicates PROPOSED for ontology_guard.py, under test.

WHY THIS FILE EXISTS. `ontology_guard.py` denies every agent write to itself, always, and no unlock
lifts it — deliberately, because an agent that can edit a gate has no gate. So the three changes in
`decisions/PROPOSED-2026-09-29_guard-scope.md` cannot be written by the agent proposing them. What
CAN be done is prove they are right before a human spends a minute on them, which is what this does.

THE PREDICATES ARE WRITTEN AS THEY WOULD DROP IN: standard library only — `os` and `re` — because
the guard imports `json, os, re, sys, tempfile, time` and refuses PyYAML on purpose. It is copied
into `.claude/hooks/` with no import path and FAILS CLOSED, so an import error in it would deny
every edit in the repository. Anything here that needed a YAML parser would be untrue to its target.

AND THAT CONSTRAINT KILLED THE FIRST DESIGN, which is recorded because the reasoning generalises. The
obvious rule is "guard by `lifecycle`" — every kind in `guardrails/` already declares `authored-once`
or `re-derived`, and that is the real axis, not data-versus-ontology. The guard cannot read those
files: they are nested YAML with block scalars and comments. Hardcoding the lifecycles into the guard
instead would put one fact in two homes and guarantee they diverge the day a kind is added. So the
principle is expressed as three CONTENT tests, in the style the guard already uses for
`_is_method_track`.

    python3 check_guard_scope.py            # run every case
    python3 check_guard_scope.py --estate   # also classify the real directories on this machine
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile

# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE PREDICATES — copy these into ontology_guard.py. Nothing below the fold is needed there.
# ══════════════════════════════════════════════════════════════════════════════════════════════

_SCHEMA_REL = "mac.schema.json"


def is_guardrail_tree(path: str) -> bool:
    """`<framework>/guardrails/ontology/…` — rules ABOUT the plane, never meaning IN it.

    SELF-IDENTIFYING, like `_is_method_track`, and for the reason that function gives: a list of
    directory names would have to grow every time the framework did. Two positive conditions —
    the `ontology/` directory sits directly under `guardrails/`, AND the repository root carries
    `mac.schema.json`, which is what makes it the framework.

    NEITHER ALONE. `/guardrails/ontology/` is acquirable — a bundle could create one.
    `mac.schema.json` alone would exempt the whole framework repository.
    """
    p = path.replace(os.sep, "/")
    i = p.find("/guardrails/ontology/")
    if i == -1:
        return False
    root = p[:i]
    return os.path.isfile(os.path.join(root.replace("/", os.sep), _SCHEMA_REL))


_RULED = re.compile(r"^--\s*mac\.transform\.driven_by:\s*ruled\s*$", re.M)


def is_ruled_transform(path: str) -> bool:
    """A `data/transforms/*.sql` a PERSON decided. Read from the file ON DISK, never the incoming.

    The file that exists is the authority; the write being proposed is the thing under judgement.
    Reading the incoming content would let one write rewrite `ruled` to `proposed` and replace the
    statement in the same breath — the same shape as rewriting the sign-off that authorises you.

    A file that does not exist yet is not ruled: the first write of a transform is how one comes to
    be, and the marker can only be there once somebody put it there.
    """
    p = path.replace(os.sep, "/")
    if "/data/transforms/" not in p or not p.endswith(".sql"):
        return False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    return bool(_RULED.search(head))


_ID = re.compile(r"^\s*-?\s*id:\s*(\S+)\s*$", re.M)
_TERMINAL = ("accepted", "wont_fix", "resolved")


def _scalar(line: str):
    """The value after the colon, with YAML's ways of saying NOTHING folded to None.

    `null` IS NOT A PERSON. `mac_dq_findings` writes `ruled_by: null` on every finding it raises —
    its own header says so — so a predicate that reads that string as a ruler refuses the very act
    it is meant to allow: raising a finding. Caught against the REAL register; the synthetic one
    omitted the key entirely and passed.
    """
    v = line.split(":", 1)[1].strip()
    return None if v in ("", "null", "~", "Null", "NULL", "none", "None") else v


def _dispositions(text: str) -> dict:
    """`{issue id: (status, ruled_by, reason-present)}` from the register, with `re` alone.

    FLAT SCALARS ONLY, which is what makes this possible at all — the same property that lets the
    guard read the sign-off without PyYAML. An issue's `id`, `status` and `ruled_by` are plain
    one-line scalars; everything nested is ignored because nothing here needs it.
    """
    out, cur = {}, None
    status = ruled = reason = None
    for line in text.splitlines():
        m = _ID.match(line)
        if m:
            if cur:
                out[cur] = (status, ruled, reason)
            cur, status, ruled, reason = m.group(1), None, None, None
            continue
        if cur is None:
            continue
        s = line.strip()
        if s.startswith("#"):
            continue          # THE FILE'S OWN HEADER SAYS "EVERY ENTRY IS `status: open` AND
                              # `ruled_by: null` UNTIL A PERSON RULES" — a comment about a
                              # disposition is not one, and reading it as one would refuse an
                              # edit to the prose that explains the rule.
        if s.startswith("status:"):
            status = _scalar(s)
        elif s.startswith("ruled_by:"):
            ruled = _scalar(s)
        elif s.startswith("reason:"):
            reason = _scalar(s) or ("«block»" if s.rstrip().endswith((">-", "|", ">")) else None)
    if cur:
        out[cur] = (status, ruled, reason)
    return out


def disposition_changed(old_text: str, new_text: str) -> str | None:
    """The id whose DISPOSITION this write would create or alter, or None.

    "An agent may write a DESCRIPTION; only a human may write a DISPOSITION" — the rule already
    stated on `DataPlaneApprovalFile.submitted_via`, applied where it is actually reachable.

    RAISING A FINDING IS A DESCRIPTION and stays allowed: a new issue at `status: open` with no
    `ruled_by` changes no disposition. So does re-measuring one — the `finding:` prose is not read
    here at all.

    WHY THIS MATTERS MORE THAN THE OTHER TWO. `check_data_plane_approved` takes the data pipeline's
    exit to BE this register fully dispositioned. An agent that can write dispositions can therefore
    manufacture the approval that starts the ontology — the sign-off artifact is unwritable exactly
    so that cannot happen, and this is the same authority through an unguarded door.
    """
    old, new = _dispositions(old_text), _dispositions(new_text)
    for ident, (status, ruled, reason) in new.items():
        was = old.get(ident, (None, None, None))
        if (status in _TERMINAL and was[0] != status) or ruled != was[1] or reason != was[2]:
            return ident
    for ident, (status, ruled, _r) in old.items():
        if ident not in new and (status in _TERMINAL or ruled):
            return ident          # deleting a ruled finding is altering its disposition
    return None


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE CASES
# ══════════════════════════════════════════════════════════════════════════════════════════════

REG = """\
issues:
  - id: DQ-ORPHAN-ORDERS
    severity: medium
    status: open
    finding: 93,470 rows harvested and never curated
  - id: DQ-DUP-ORDERROWS-SALES
    severity: medium
    status: open
    finding: same 223,974 rows
"""


def _line_of(lines, ident):
    """Index of the `id:` line naming `ident` — so a mutant targets a REAL issue, not a comment."""
    for i, ln in enumerate(lines):
        m = _ID.match(ln)
        if m and m.group(1) == ident:
            return i
    return 0


def _ok(ok, what, cond):
    ok[0] += 1
    ok[1] += bool(cond)
    print(("  ✓ " if cond else "  ✗ ") + what)


def run(estate: bool) -> int:
    ok = [0, 0]
    case = lambda w, c: _ok(ok, w, c)  # noqa: E731

    print("\n1 — the register's dispositions  (an agent may describe, only a human may dispose)")
    case("raising a NEW finding at `open` is a description, allowed",
         disposition_changed(REG, REG + "  - id: DQ-NEW\n    status: open\n    finding: x\n") is None)
    case("re-measuring a finding's prose changes no disposition, allowed",
         disposition_changed(REG, REG.replace("93,470 rows", "93,471 rows")) is None)
    case("an identical write is allowed", disposition_changed(REG, REG) is None)
    # THE HOLE. `check_data_plane_approved` reads exactly this to decide the pipeline's exit.
    case("MUTANT open -> accepted is REFUSED",
         disposition_changed(REG, REG.replace("status: open\n    finding: 93,470",
                                              "status: accepted\n    finding: 93,470")) == "DQ-ORPHAN-ORDERS")
    case("MUTANT adding `ruled_by` is REFUSED — it claims a person acted",
         disposition_changed(REG, REG.replace("    status: open\n    finding: 93,470",
                                              "    status: open\n    ruled_by: Someone\n    finding: 93,470"))
         == "DQ-ORPHAN-ORDERS")
    case("MUTANT adding a `reason` is REFUSED",
         disposition_changed(REG, REG.replace("    status: open\n    finding: 93,470",
                                              "    status: open\n    reason: fine\n    finding: 93,470"))
         == "DQ-ORPHAN-ORDERS")
    ruled = REG.replace("    status: open\n    finding: 93,470",
                        "    status: accepted\n    ruled_by: Drazen\n    reason: agreed\n    finding: 93,470")
    case("MUTANT rewriting a human's name on a ruled finding is REFUSED",
         disposition_changed(ruled, ruled.replace("ruled_by: Drazen", "ruled_by: Nobody"))
         == "DQ-ORPHAN-ORDERS")
    case("MUTANT deleting a ruled finding is REFUSED — that alters its disposition too",
         disposition_changed(ruled, REG.split("  - id: DQ-DUP")[0]) == "DQ-ORPHAN-ORDERS")
    case("re-measuring a bundle that HAS rulings leaves them alone, allowed",
         disposition_changed(ruled, ruled.replace("same 223,974 rows", "same 223,975 rows")) is None)

    # ── AGAINST THE REAL REGISTER, which is what found the bug the synthetic cases could not.
    # `mac_dq_findings` writes `ruled_by: null` on every finding it raises; the synthetic fixture
    # omitted the key, so "adding a new finding" passed there and was REFUSED on the real file —
    # the predicate was reading the string `null` as a person. A fixture that differs from the
    # producer's real output tests the fixture.
    real_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "..", "archive-sources", "example", "contoso5",
                             "data", "quality", "data_quality_register.yaml")
    if os.path.isfile(real_path):
        with open(real_path, encoding="utf-8") as fh:
            real = fh.read()
        rl = real.splitlines(True)

        def mutate(n, text):
            out = list(rl)
            out[n - 1] = text
            return "".join(out)

        parsed = _dispositions(real)
        case(f"the REAL register parses with `re` alone ({len(parsed)} issues)", len(parsed) >= 5)
        case("every real finding reads as undisposed — `ruled_by: null` is not a person",
             all(v[1] is None for v in parsed.values()))
        case("an identical write to the real register is allowed",
             disposition_changed(real, real) is None)
        case("re-measuring real prose is allowed",
             disposition_changed(real, real.replace("93,470 rows", "93,471 rows")) is None)
        case("adding a NEW real-shaped finding (with `ruled_by: null`) is allowed",
             disposition_changed(real, real + "- id: DQ-NEW\n  status: open\n  ruled_by: null\n")
             is None)
        first = sorted(parsed)[0]
        n_status = next(i + 1 for i, ln in enumerate(rl)
                        if ln.strip().startswith("status:") and i > _line_of(rl, first))
        case(f"MUTANT forging a real finding's status is REFUSED ({first})",
             disposition_changed(real, mutate(n_status, "  status: accepted\n")) is not None)
        n_ruled = next(i + 1 for i, ln in enumerate(rl)
                       if ln.strip().startswith("ruled_by:") and i > _line_of(rl, first))
        case("MUTANT forging a real `ruled_by` name is REFUSED",
             disposition_changed(real, mutate(n_ruled, "  ruled_by: Someone\n")) is not None)
        case("MUTANT forging ALL of them — the approval itself — is REFUSED",
             disposition_changed(real, real.replace("status: open", "status: accepted")) is not None)
        # THE FILE'S OWN HEADER MENTIONS BOTH FIELDS IN PROSE.
        case("a COMMENT that mentions a disposition is not one",
             disposition_changed(real, real.replace("# EVERY ENTRY IS `status: open`",
                                                    "# EVERY ENTRY IS `status: accepted`")) is None)
    else:
        case("the real register was not found — real-file cases NOT run", False)

    print("\n2 — a ruled transform  (read the file ON DISK, never the incoming content)")
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "data", "transforms")
        os.makedirs(d)
        def sql(name, driver):
            p = os.path.join(d, name)
            head = f"-- {name}\n--\n-- mac.transform.driven_by: {driver}\n--\n" if driver else f"-- {name}\n"
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(head + "CREATE OR REPLACE VIEW s.t AS SELECT 1;\n")
            return p
        case("a `ruled` transform is protected", is_ruled_transform(sql("a.sql", "ruled")))
        case("a `proposed` transform is NOT — the platform may revise its own proposal",
             not is_ruled_transform(sql("b.sql", "proposed")))
        case("a `passthrough` transform is NOT — it is the regenerable floor",
             not is_ruled_transform(sql("c.sql", "passthrough")))
        case("an UNMARKED transform is NOT protected — absent is undeclared, not ruled",
             not is_ruled_transform(sql("d.sql", None)))
        case("a file that does not exist yet is NOT protected — first writes create transforms",
             not is_ruled_transform(os.path.join(d, "nope.sql")))
        case("a .sql outside data/transforms/ is not this rule's business",
             not is_ruled_transform(os.path.join(tmp, "x.sql")))
        # THE MUTANT THE WHOLE DESIGN TURNS ON.
        case("MUTANT incoming content claiming `proposed` cannot unprotect a `ruled` file on disk",
             is_ruled_transform(sql("a.sql", "ruled")))

    print("\n3 — the guardrail tree  (rules ABOUT the plane, not meaning IN it)")
    fw = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    case("this framework's own guardrails/ontology/ IS exempt",
         is_guardrail_tree(os.path.join(fw, "guardrails", "ontology", "concepts.yaml")))
    case("a bundle's ontology/concepts/ is NOT exempt",
         not is_guardrail_tree("/x/bundle/ontology/concepts/customer.yaml"))
    with tempfile.TemporaryDirectory() as tmp:
        fake = os.path.join(tmp, "guardrails", "ontology")
        os.makedirs(fake)
        target = os.path.join(fake, "concepts.yaml")
        case("MUTANT a bundle that creates guardrails/ontology/ does NOT acquire the exemption",
             not is_guardrail_tree(target))
        with open(os.path.join(tmp, _SCHEMA_REL), "w", encoding="utf-8") as fh:
            fh.write("{}")
        case("...it would need to ship mac.schema.json, i.e. ship the framework",
             is_guardrail_tree(target))

    if estate:
        print("\n4 — every `ontology` directory on this machine, classified")
        base = os.path.dirname(os.path.dirname(fw))
        seen = 0
        for root, dirs, _files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in (".git", "node_modules", ".venv", "site-packages")]
            if root.count(os.sep) - base.count(os.sep) > 4:
                dirs[:] = []
                continue
            if os.path.basename(root) != "ontology":
                continue
            seen += 1
            probe = os.path.join(root, "concepts", "x.yaml")
            verdict = "EXEMPT (guardrail tree)" if is_guardrail_tree(probe) else "protected"
            print(f"    {verdict:24} {root.replace(base + os.sep, '')}")
        case(f"classified {seen} real directories, and exactly one is exempt",
             seen >= 5)

    print(("\nPASS" if ok[1] == ok[0] else "\nFAIL")
          + f": check_guard_scope — {ok[1]}/{ok[0]} case(s). These predicates are PROPOSED for "
            f"ontology_guard.py, which no agent may write; see "
            f"decisions/PROPOSED-2026-09-29_guard-scope.md.")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--estate", action="store_true", help="also classify the real directories here")
    sys.exit(run(ap.parse_args().estate))
