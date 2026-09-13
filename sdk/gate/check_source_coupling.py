#!/usr/bin/env python3
"""check_source_coupling.py — the GENERIC-INSTRUMENT gate for the framework.

THE INVARIANT
-------------
The framework (this repo's projectors + serving code) manages ontologies for ANY source. It must
therefore contain NO source literal: no `acme2.`, no `"acme"`, no `<domain>/<dataset>` spliced into executable
code. A hardcoded schema does not fail loudly — it silently mis-reports on every OTHER source, which
is the worst failure mode a shared instrument can have.

This is not hypothetical. On 2026-08-16 the plane-health chain check shipped with
`f"acme2.{table_name}"`; on any bundle whose schema was not `acme2` it reported EVERY dataset as having
no transformation. Two more `f"<source>.{stem}"` fallbacks had been sitting in objects.py before that.
Nothing caught either: the only source-coupling gate in the estate lives in a different repo
(mac-runtime), scoped to that runtime's closure.

WHAT COUNTS
-----------
A source literal is a known source name appearing in a STRING in executable code. Comments and
docstrings are exempt — explaining the rule is not breaking it (source_ident.py's whole docstring is
about de-coupling, and must stay readable).

Add a new source name to SOURCE_TOKENS as the estate grows; add a genuine, reasoned exception to
ALLOW (file -> why). An ALLOW entry that no longer matches anything is reported as STALE so the
list cannot rot.

OFFLINE + pure-structural. Usage:  python3 sdk/gate/check_source_coupling.py [repo-root]
    exit 0 = the instrument is generic ; exit 1 = a source literal leaked in.
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

from sdk import registers
from sdk.gate import contract

# directories that make up the generic instrument
SCAN_DIRS = ("sdk/project", "sdk/authoring", "sdk/cli", "sdk/container")
# The instance names this instrument must not contain. They live in a gitignored register, NOT
# here: a detector that names what it forbids is a register of those names, and this repo is
# published. With none declared the token class examines nothing — which the verdict line says.
SOURCE_TOKENS = registers.Live("source_tokens")
# TEST files legitimately name a fixture source — exercising the instrument is not coupling it.
SKIP_FILE = re.compile(r"(^|/)(test_|conftest)")
# RATCHET: file -> (allowed_count, why). Pre-existing coupling is frozen at today's count so it cannot
# GROW, while the instrument stays green and the backlog stays visible. Lower a count as you fix one;
# a count that drops to 0 should be deleted. Adding a NEW file here needs a real reason, not convenience.
ALLOW: dict[str, tuple[int, str]] = {
    "sdk/project/ontology_quality.py": (
        4,
        "the ENGLISH WORD — `answerable['gaps']` is the list of answer-path steps a concept cannot "
        "supply. It collides with one estate's domain name, which is exactly why this gate matches "
        "substrings: a `\\b`-bounded pattern could not see `v_<source>_kpi` or `<source>2`. A "
        "detector that cannot be fooled by an identifier will sometimes be fooled by a dictionary.",
    ),
}

# a source REFERENCE, not merely the letters: a schema prefix (`acme2.`), a bundle path (`<domain>/<dataset>`),
# or the bare name standing alone as an identifier ("acme2").
def _token_re():
    """Built per call: the register is read live, and the DOMAIN segment of a bundle path is derived
    from the declared tokens rather than hardcoded (it used to be one estate's literal domain)."""
    toks = [re.escape(t) for t in SOURCE_TOKENS]
    if not toks:
        return None
    tok = "|".join(toks)
    return re.compile(rf"(\b({tok})\s*\.|[A-Za-z0-9_-]+/({tok})\b|^['\"]({tok})['\"]$)", re.I)


def _string_literals(path: Path):
    """Yield (lineno, text) for STRING tokens only — comments and docstrings are skipped.

    A docstring is a STRING token that is the sole expression of its statement; tokenize does not
    label it, so we approximate: a string whose line begins the statement (col 0..8) and which is
    triple-quoted is treated as a docstring and exempt."""
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:
        return
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except Exception:
        return
    # On Python 3.12 an f-string is NOT a STRING token: it tokenizes as FSTRING_START /
    # FSTRING_MIDDLE / FSTRING_END. This gate matched STRING alone, so it was BLIND to exactly
    # the shape its own docstring cites -- an interpolated source name. Green because it could
    # not see, not because the tree was clean.
    fstring_types = {
        getattr(tokenize, n)
        for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)
    }
    wanted = {tokenize.STRING} | fstring_types
    for tok in toks:
        if tok.type not in wanted:
            continue
        text = tok.string
        if not text:
            continue
        if text.lstrip("rbufRBUF").startswith(('"""', "'''")):
            continue  # docstring / block comment
        yield tok.start[0], text


def main(argv) -> int:
    if "--self-test" in argv:
        return _self_test()
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    # Run from the wrong root this printed a tick over 0 files. Exit 2 is the honest answer.
    if not root.is_dir():
        return contract.could_not_run("check_source_coupling", f"{root} is not a directory")
    if not any((root / d).is_dir() for d in SCAN_DIRS):
        return contract.could_not_run(
            "check_source_coupling",
            f"{root} holds none of {', '.join(SCAN_DIRS)} — 0 examined is not clean",
        )
    print(f"── source-coupling gate ── the framework must name NO source ── {root} ──\n")
    violations: list[str] = []
    hits: dict[str, list[str]] = {}
    # Built ONCE per run from the live register. None means no tokens are declared, so the token
    # class examines nothing — reported in the verdict rather than passed over in silence.
    token_re = _token_re()
    if token_re is None:
        # No tokens declared means the token class has no subject. It used to print a tick with a
        # note underneath; a note is not a refusal, and a runner grepping for PASS/FAIL read it as
        # green. This gate lost its subject once before and reported a tick — never again.
        return contract.could_not_run(
            "check_source_coupling",
            "no source-token register — 0 tokens declared, so 0 literals could be found; "
            "that is not the same as none existing. See registers/ and sdk/registers.py.",
        )
    scanned = 0
    for d in SCAN_DIRS:
        for p in sorted((root / d).rglob("*.py")):
            scanned += 1
            rel = str(p.relative_to(root))
            if SKIP_FILE.search(rel):
                scanned -= 1
                continue
            for lineno, text in _string_literals(p):
                if token_re is None or not token_re.search(text):
                    continue
                hits.setdefault(rel, []).append(f"{rel}:{lineno}  {text.strip()[:88]}")

    for rel, found in sorted(hits.items()):
        allowed, why = ALLOW.get(rel, (0, ""))
        if len(found) > allowed:
            for v in found[allowed:]:
                violations.append(v)
                print(f"  [ERROR] source literal in generic code — {v}")
        elif len(found) < allowed:
            print(
                f"  [WARN]  '{rel}' now has {len(found)} of {allowed} allowed — tighten the count"
            )
    for f, (_n, why) in ALLOW.items():
        if f not in hits:
            print(f"  [WARN]  ALLOW entry '{f}' matches nothing any more — delete it ({why})")
    frozen = sum(min(len(v), ALLOW.get(k, (0, ""))[0]) for k, v in hits.items())
    print()
    if violations:
        print(
            f"✗ {len(violations)} source literal(s) in {scanned} framework file(s), "
            f"{len(list(SOURCE_TOKENS))} token(s) declared — derive the name "
            f"(source_ident / the descriptor's own schema) instead of hardcoding it"
        )
        return 1
    print(
        f"✓ OK — {scanned} framework file(s) add no NEW source literal, "
        f"{len(list(SOURCE_TOKENS))} token(s) declared "
        f"({frozen} pre-existing, frozen by the ratchet — see ALLOW)"
        + ("\n  [no source-token register: the token class examined NOTHING]"
           if not len(list(SOURCE_TOKENS)) else "")
    )
    return 0


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------


def _sc_clean(root: Path) -> None:
    contract.write(root / SCAN_DIRS[0] / "mod.py", "def build(name):\n    return name.lower()\n")


def _sc_run(root: Path):
    import contextlib
    import io as _io

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["check_source_coupling", str(root)])
    scanned = sum(1 for d in SCAN_DIRS if (root / d).is_dir() for _ in (root / d).rglob("*.py"))
    return contract.Outcome(1 if code == 1 else 0, scanned)


#: The self-test's own declared token. SYNTHETIC: the register is gitignored, so a fresh checkout
#: declares none and a self-test reading it would exercise the token class against an empty list --
#: and pass, having checked nothing. It is also not a real source name, so counting it costs the
#: gate's own tally nothing.
_SYNTHETIC_TOKEN = "zzsynthsourcezz"


def _self_test() -> int:
    import os as _os

    # Declared to the gate under test via the register's own env override — the same mechanism an
    # estate or a CI runner uses, exercised rather than bypassed.
    _reg = Path(__file__).resolve().parent / ".source_tokens.selftest"
    _reg.write_text(f"{_SYNTHETIC_TOKEN}\n", encoding="utf-8")
    _os.environ[registers.REGISTERS["source_tokens"][1]] = str(_reg)
    token = _SYNTHETIC_TOKEN
    c = contract.GateContract(
        name="check_source_coupling",
        clean=_sc_clean,
        mutants={
            "plain-string-literal": lambda r: contract.write(
                r / SCAN_DIRS[0] / "leak.py", 'TABLE = "' + token + '.orders"\n'
            ),
            # The class the gate could not see: on 3.12 an f-string is FSTRING_*, not STRING.
            "f-string-literal": lambda r: contract.write(
                r / SCAN_DIRS[0] / "fleak.py",
                'def q(col):\n    return f"' + token + '.{col}"\n',
            ),
        },
        run=_sc_run,
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
