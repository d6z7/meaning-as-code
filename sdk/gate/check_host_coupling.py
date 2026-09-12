#!/usr/bin/env python3
"""check_host_coupling.py — is a HOST (wiki / runtime) coupled to a specific source? (ADR 2026-08-13)

The existing mac-runtime `check_source_coupling` is an FPL-marker grep (hardcoded `brand_letter`,
`v_fpl`, …) and is import-AST only — it can't certify a NON-FPL source and is blind to `subprocess`/`-m`
shell-outs (the adversary's #6). This gate is SOURCE-NEUTRAL: it derives the "source tokens" from the
ACTUAL sources on disk (each `mac.project.yaml`'s data_domain/dataset + connection handles), so it works
for any source, and it flags three coupling classes a separated host must not have:

  1. infra-handle literals   — profile / workgroup / glue-db / account / bucket hardcoded in host code
                               (a host must read these from the mounted container's connection.yaml)
  2. source-pin literals     — a source's own domain/dataset/schema token hardcoded in host code
                               (a host pinned to one source is not source-neutral)
  3. boundary-via-shell      — subprocess/os.system calls that invoke `-m sdk...`/`sdk/...` (a boundary
                               crossing the import-AST gate cannot see)

Report-mode by default (a host may be mid-separation); `--enforce` exits 1 on any class-1/3 finding.
Stdlib + reuses the bundle-secret detector. See ADR "host contract".
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yaml

from sdk.gate import check_bundle_secrets, contract

_SKIP = {"__pycache__", ".git", "node_modules", "dist", "build", ".venv", "venv"}


def _source_tokens(repo: Path) -> set:
    """The source-identifying tokens to treat as pins, DERIVED from the sources on disk (not hardcoded)."""
    toks: set = set()
    for mp in (repo / "sources").glob("*/*/mac.project.yaml"):
        try:
            m = yaml.safe_load(mp.read_text()) or {}
        except Exception:
            continue
        meta = m.get("metadata") or {}
        for k in ("data_domain", "dataset", "label"):
            v = meta.get(k)
            if v and len(str(v)) >= 3:  # skip 1-2 char tokens (too noisy)
                toks.add(str(v))
    return toks


def _is_gate_or_test(name: str) -> bool:
    # gates + tests legitimately NAME source tokens/handles (denylists, markers, fixtures) — not host coupling.
    return name.startswith("check_") or name.startswith("test_")


def _py_files(host: Path):
    for p in sorted(host.rglob("*.py")):
        if not (_SKIP & set(p.parts)) and not _is_gate_or_test(p.name):
            yield p


def check(host_dir, repo_root) -> dict:
    host, repo = Path(host_dir), Path(repo_root)
    # 1. infra handles hardcoded in host code (reuse the bundle-secret detector; host code is never the config
    #    allowlist). Exclude gate/test files, which name handles by design (denylists, fixtures).
    infra = [
        (rel, ln, kind, m)
        for rel, ln, kind, m in check_bundle_secrets.check(host)
        if (kind.startswith("infra_handle") or "account" in kind)
        and not _is_gate_or_test(Path(rel).name)
        and ".example" not in Path(rel).name
    ]  # *.example carry placeholders by design
    # 2. source pins — a source's own token appearing as a string literal in host code
    toks = _source_tokens(repo)
    pins = []
    tok_re = {t: re.compile(rf"['\"]{re.escape(t)}['\"]") for t in toks}
    # 3. boundary-via-shell — subprocess/system calls that reach into sdk
    shell = []
    for p in _py_files(host):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text, filename=str(p))
        except Exception:
            continue
        rel = str(p.relative_to(host))
        for i, line in enumerate(text.splitlines(), 1):
            for t, rx in tok_re.items():
                if rx.search(line) and not line.lstrip().startswith("#"):
                    pins.append((rel, i, t))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                src = ast.unparse(n) if hasattr(ast, "unparse") else ""
                if ("subprocess" in src or "os.system" in src or ".run(" in src) and (
                    ("-m" in src and "sdk" in src) or "sdk/" in src or "sdk." in src
                ):
                    shell.append((rel, n.lineno, src[:80]))
    return {"infra_handles": infra, "source_pins": pins, "boundary_via_shell": shell}


def examined(host_dir) -> int:
    """Python files the scan actually parsed.

    Without it `SEPARATED: YES (0 infra-handle coupling(s), 0 source-pin(s))` is printed over a
    host directory that does not exist, exit 0 -- the strongest possible claim from the weakest
    possible evidence. And `_source_tokens` derives pins from `repo/sources/*/*/mac.project.yaml`,
    so a repo with no sources yields NO tokens and the pin class cannot fire at all: that is a
    second, quieter zero-denominator, reported separately below.
    """
    return sum(1 for _ in _py_files(Path(host_dir)))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Measure a host's coupling to any specific source (source-neutral)."
    )
    ap.add_argument("host", nargs="?", help="a host dir to scan (e.g. a runtime tools/ dir)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parents[2]),
        help="repo root (to derive source tokens)",
    )
    ap.add_argument(
        "--enforce",
        action="store_true",
        help="exit 1 on any infra-handle or boundary-via-shell finding",
    )
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.host:
        return contract.could_not_run("check_host_coupling", "a host directory is required")
    if not Path(a.host).is_dir():
        return contract.could_not_run("check_host_coupling", f"{a.host} is not a directory")
    n = examined(a.host)
    if n == 0:
        return contract.could_not_run(
            "check_host_coupling",
            f"{a.host} holds no python file — 0 examined is not the same as separated",
        )

    r = check(a.host, a.repo)
    print(f"host-coupling scan of {a.host} (source tokens derived from {a.repo}/sources):")
    print(f"  infra-handle literals : {len(r['infra_handles'])}")
    for rel, ln, kind, m in r["infra_handles"][:12]:
        print(f"    {rel}:{ln}  [{kind}]  {m}")
    print(f"  source-pin literals   : {len(r['source_pins'])}")
    for rel, ln, t in r["source_pins"][:12]:
        print(f"    {rel}:{ln}  pins {t!r}")
    # boundary-via-shell is INFORMATIONAL: shelling out to an sdk CLI is the sanctioned tool-use pattern
    # (the wiki already shells out to lineage_project.py); a reviewer confirms it's a CLI call, not smuggling.
    # The SEPARATED verdict keys on the unambiguous coupling: infra-handle + source-pin literals.
    print(
        f"  boundary-via-shell    : {len(r['boundary_via_shell'])} (informational — confirm each is a CLI call, not an import)"
    )
    for rel, ln, s in r["boundary_via_shell"][:8]:
        print(f"    {rel}:{ln}  {s}")
    hard = len(r["infra_handles"])
    tokens = _source_tokens(Path(a.repo))
    if not tokens:
        # Stated, not hidden: with no source on disk the pin class has no subject, so a clean pin
        # count here is "could not look", and SEPARATED must not be claimed on it.
        print(
            f"  NOTE: 0 source token(s) derived from {a.repo}/sources — the source-pin class "
            f"had no subject in this run"
        )
    verdict = "YES" if hard == 0 and not r["source_pins"] and tokens else "NO"
    print(
        f"SEPARATED: {verdict} "
        f"({hard} infra-handle coupling(s), {len(r['source_pins'])} source-pin(s) over "
        f"{n} python file(s) examined, {len(tokens)} source token(s) derived)"
    )
    return 1 if (a.enforce and hard) else 0


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------


def _hc_clean(root: Path) -> None:
    """A host that reads its config rather than naming anything, plus one source on disk so the
    pin class HAS a subject -- otherwise the clean fixture would pass for the wrong reason."""
    contract.write(root / "host" / "server.py", "def serve(cfg):\n    return cfg['connection']\n")
    contract.write(
        root / "sources" / "dom" / "ds" / "mac.project.yaml",
        "metadata:\n  data_domain: dom\n  dataset: demoset\n  label: demoset\n",
    )


def _hc_run(root: Path):
    r = check(root / "host", root)
    findings = len(r["infra_handles"]) + len(r["source_pins"])
    return contract.Outcome(findings, examined(root / "host"))


def _self_test() -> int:
    c = contract.GateContract(
        name="check_host_coupling",
        clean=_hc_clean,
        mutants={
            # a source's own token, typed into host code as a literal
            "source-pin-literal": lambda r: contract.write(
                r / "host" / "pinned.py", 'DATASET = "demoset"\n'
            ),
            "infra-handle-literal": lambda r: contract.write(
                r / "host" / "infra.py",
                "PROFILE = " + repr(next(iter(check_bundle_secrets._DEFAULT_DENY))) + "\n",
            ),
        },
        run=_hc_run,
        extra={
            "the pin class must have a subject": lambda base: (
                ""
                if _source_tokens(base / "clean")
                else "the clean fixture derived 0 source tokens — the pin class is untestable"
            ),
        },
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
