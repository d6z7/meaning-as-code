#!/usr/bin/env python3
"""check_bundle_secrets.py — a REAL secret / infra-handle detector for what gets FROZEN.

Replaces the old 5-literal blocklist (mac-runtime/tools/check_no_hardcoded_secrets.py) —
which was an enumerated list, not a detector, and self-contradicted by blocking the very
handle a self-contained bundle must ship. This runs over the STAGED publish tree BEFORE the
write-once freeze, so a credential can never be baked into an immutable artifact, and it
catches NOVEL secrets by pattern, not just known literals.

Two tiers:
  GENERIC SECRETS — real credentials (AWS access/secret/session keys, private keys, bearer
    tokens, inline passwords, user:pass@ connection strings, and — with --entropy — high-
    entropy blobs). BLOCKED EVERYWHERE, including the connection config.
  INFRA HANDLES — the AWS account id (and account ids embedded in ARNs) plus a source
    denylist of infra handles (SSO profile / workgroup / warehouse-db / bucket names).
    Account ids are BLOCKED EVERYWHERE (operator posture: ship handles, NEVER the account
    id — derive it at runtime via STS). Denylisted handles are blocked everywhere EXCEPT the
    connection config allowlist, where non-secret reference handles are permitted to travel.

Exit 0 = clean, 1 = leak. Stdlib only. Usable both as the publish post-stage gate and as a
source-tree pre-commit hook.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from sdk.gate import contract

# ---- generic real-credential patterns (blocked EVERYWHERE) -----------------------------------
_GENERIC = [
    (
        "aws_access_key_id",
        re.compile(r"\b(?:AKIA|ASIA|AIDA|AGPA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])[0-9A-Z]{16}\b"),
    ),
    ("private_key_block", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    (
        "aws_secret_access_key",
        re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+]{40}\b"),
    ),
    ("aws_session_token", re.compile(r"(?i)aws_session_token\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{100,}")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    (
        "password_inline",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret)\s*[:=]\s*"
            r"(?!['\"]?(?:\$|<|\{\{|%|xxx|placeholder|changeme|redacted|none|null|true|false)\b)"
            r"['\"]?[^\s'\"#]{6,}"
        ),
    ),
    ("connection_string_creds", re.compile(r"[a-z][a-z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@")),
]

# ---- AWS account id (blocked EVERYWHERE — posture is to omit it and derive via STS) -----------
_ARN_ACCOUNT = re.compile(r"arn:aws[a-z\-]*:[^:\n]*:[^:\n]*:(\d{12}):")
_BARE_ACCOUNT = re.compile(r"\b\d{12}\b")
_ACCOUNT_CONTEXT = re.compile(r"(?i)account|acct|:aws:")

# ---- the infra-handle denylist: READ FROM OUTSIDE THIS TREE -----------------------------------
# This list used to be four literal infra handles — a production SSO profile, a workgroup family, a
# prod results bucket, and another source's warehouse database (one of them carrying a person's
# name). A detector that names what it forbids IS a register of those secrets, and this repository
# is published. The gate's own source was the densest concentration of the strings it exists to keep
# out of everything else.
#
# So the handles now live in a file this repo never tracks, exactly as the integration kit already
# does for its instance-token register: "a public method must not carry them". `infra_handles.txt`
# is gitignored; `infra_handles.example.txt` ships with placeholders and no real values.
#
# A MISSING REGISTER IS NOT A CLEAN BUNDLE. With no handles declared, the handle class examines
# nothing — so the count travels into the verdict line and the reader sees `0 handle(s) declared`
# rather than an unqualified PASS. The shape-based classes (key formats, entropy) are unaffected and
# keep running, which is why this is a narrowed denominator and not a could-not-run.
_HANDLE_REGISTER = Path(__file__).resolve().parent / "infra_handles.txt"


def load_deny(register: Path = _HANDLE_REGISTER) -> list[str]:
    """The declared infra handles, or [] when none are declared. Never a literal in this file."""
    if not register.is_file():
        return []
    return [
        ln.strip()
        for ln in register.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


_DEFAULT_DENY = load_deny()

# Basenames where non-secret reference HANDLES may live (account ids + generic secrets still blocked).
_CONFIG_ALLOWLIST = {
    "connection.yaml",
    "connection.example.yaml",
    "connection.local.yaml",
    "mac.project.yaml",
}

# Skipped by path RELATIVE to the scan root (so pointing the scan AT an artifacts/<ver> dir still
# scans it, while a source-tree scan skips the nested artifacts/ outputs and .context/ inputs — the
# latter are SME material never carried by _COMPILE).
_SKIP_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    ".harvest_cache",
    "artifacts",
    ".context",
    ".context_src",
}
# per-file sha256 map + version tag — hashes, not secrets; and the harvest reproducibility
# SIDECAR (.harvest_manifest.yaml), a gitignored, never-published volatile ledger that records
# the run's databases/region (infra handles that legitimately live only in the connection config).
_SKIP_FILES = {"MANIFEST.json", "VERSION", ".harvest_manifest.yaml"}
_TEXT_EXT = {
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".sql",
    ".txt",
    ".py",
    ".csv",
    ".cfg",
    ".ini",
    ".toml",
    ".sh",
    ".env",
    ".example",
    ".jsonl",
}

_B64_TOKEN = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    freq = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _entropy_hits(line: str):
    """High-entropy base64-ish blobs that look like keys (mixed classes, not a plain hex hash)."""
    out = []
    for m in _B64_TOKEN.finditer(line):
        tok = m.group(0)
        if not (
            any(c.islower() for c in tok)
            and any(c.isupper() for c in tok)
            and any(c.isdigit() for c in tok)
        ):
            continue  # needs all three classes to look like a key
        if re.fullmatch(r"[0-9a-fA-F]+", tok):
            continue  # a hex hash, not a secret
        if _shannon(tok) >= 4.0:
            out.append(("high_entropy_blob", tok[:12] + "…"))
    return out


def _scan_text(rel: str, text: str, deny_res, in_config: bool, use_entropy: bool):
    """Return [(rel, lineno, kind, match)] for one file's text."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, rx in _GENERIC:
            m = rx.search(line)
            if m:
                hits.append((rel, i, kind, m.group(0)[:40]))
        # account ids — everywhere
        for m in _ARN_ACCOUNT.finditer(line):
            hits.append((rel, i, "aws_account_id_in_arn", m.group(1)))
        if _ACCOUNT_CONTEXT.search(line):
            for m in _BARE_ACCOUNT.finditer(line):
                hits.append((rel, i, "aws_account_id", m.group(0)))
        # infra handles — everywhere EXCEPT the connection config allowlist
        if not in_config:
            for name, rx in deny_res:
                m = rx.search(line)
                if m:
                    hits.append((rel, i, f"infra_handle:{name}", m.group(0)))
        if use_entropy:
            for kind, match in _entropy_hits(line):
                hits.append((rel, i, kind, match))
    return hits


def check(root: Path, deny=None, use_entropy: bool = False):
    """Scan a directory (or single file) tree. Returns a list of (relpath, lineno, kind, match)."""
    root = Path(root)
    deny = deny if deny is not None else list(_DEFAULT_DENY)
    deny_res = [(d, re.compile(re.escape(d))) for d in deny if d]
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    violations = []
    for p in files:
        rel_parts = p.relative_to(root).parts if root.is_dir() else ()
        if any(part in _SKIP_DIRS for part in rel_parts) or p.name in _SKIP_FILES:
            continue
        if p.suffix.lower() not in _TEXT_EXT:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(p.relative_to(root)) if root.is_dir() else p.name
        in_config = p.name in _CONFIG_ALLOWLIST
        violations += _scan_text(rel, text, deny_res, in_config, use_entropy)
    return violations


def examined(root: Path) -> int:
    """Text files the scan actually read -- the same filter `check()` applies.

    `clean — no secret/handle leaks in <root>` was printed over a nonexistent directory and over a
    tree of nothing but binaries, both with exit 0. A secret gate that passes having read no text
    has established nothing.
    """
    root = Path(root)
    if root.is_file():
        return 1 if root.suffix.lower() in _TEXT_EXT else 0
    if not root.is_dir():
        return 0
    n = 0
    for pth in root.rglob("*"):
        if not pth.is_file():
            continue
        if any(part in _SKIP_DIRS for part in pth.relative_to(root).parts):
            continue
        if pth.name in _SKIP_FILES or pth.suffix.lower() not in _TEXT_EXT:
            continue
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Detect secrets / infra-handle leaks in a bundle or source tree."
    )
    ap.add_argument(
        "root", nargs="?", help="directory (staged artifact / source tree) or a file to scan"
    )
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--deny-file",
        help="newline-separated infra handles to block outside the connection config "
        "(default: the built-in gaps/fpl handle list)",
    )
    ap.add_argument(
        "--entropy",
        action="store_true",
        help="also flag high-entropy base64 blobs (novel-key heuristic)",
    )
    ap.add_argument(
        "--warn", action="store_true", help="report but exit 0 (default: exit 1 on any finding)"
    )
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    # Exit 2 in main() only: publish.py:113 calls `check(stage)` in process and treats the returned
    # list as findings, so a sentinel from check() would be read as a leak.
    target = Path(a.root)
    if not target.exists():
        return contract.could_not_run("check_bundle_secrets", f"{a.root} does not exist")
    n = examined(target)
    if n == 0:
        return contract.could_not_run(
            "check_bundle_secrets",
            f"{a.root} holds no scannable text file — 0 read is not the same as clean",
        )
    deny = None
    if a.deny_file:
        deny = [
            ln.strip()
            for ln in Path(a.deny_file).read_text().splitlines()
            if ln.strip() and not ln.startswith("#")
        ]
    v = check(Path(a.root), deny=deny, use_entropy=a.entropy)
    if v:
        for rel, ln, kind, match in v:
            print(f"  {rel}:{ln}  [{kind}]  {match}")
        print(
            f"FAIL: check_bundle_secrets — {len(v)} secret/handle leak(s) over {n} "
            f"text file(s) examined, {len(deny if deny is not None else _DEFAULT_DENY)} "
            f"handle(s) declared"
        )
        return 0 if a.warn else 1
    nd = len(deny if deny is not None else _DEFAULT_DENY)
    print(
        f"PASS: check_bundle_secrets — 0 leak(s) over {n} text file(s) examined, "
        f"{nd} handle(s) declared"
        + ("  [no handle register: the handle class examined nothing]" if not nd else "")
    )
    return 0


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------


def _bs_clean(root: Path) -> None:
    contract.write(root / "ontology" / "concept.yaml", "concept:\n  name: Thing\n")
    contract.write(root / "README.md", "# A bundle\n\nNothing secret here.\n")


#: The self-test's own declared register. Nothing real, and nothing read from disk.
_SYNTHETIC_HANDLE = "zz-synthetic-infra-handle-zz"


def _bs_run(root: Path):
    # The synthetic handle is DECLARED to the gate under test. The gate's live register is empty in
    # a fresh clone by design, so a self-test that relied on it would exercise the handle class
    # against zero declared handles — and pass, having checked nothing. That is the zero-denominator
    # pass this estate keeps finding, and it would sit inside the gate meant to catch leaks.
    return contract.Outcome(len(check(root, deny=[_SYNTHETIC_HANDLE])), examined(root))


def _self_test() -> int:
    handle = _SYNTHETIC_HANDLE
    c = contract.GateContract(
        name="check_bundle_secrets",
        clean=_bs_clean,
        mutants={
            "denied-infra-handle-outside-the-connection-config": lambda r: contract.write(
                r / "ontology" / "leak.yaml", f"note: uses {handle}\n"
            ),
            "aws-access-key-shape": lambda r: contract.write(
                r / "ontology" / "key.yaml", "token: " + "AKIA" + "ABCDEFGHIJKLMNOP" + "\n"
            ),
        },
        run=_bs_run,
        extra={
            "a tree with no text file must refuse, not pass": lambda base: (
                ""
                if examined(base / "nothing-here") == 0
                else "examined() counted files in a nonexistent tree"
            ),
            "an absent handle register yields no handles, never an error": lambda base: (
                "" if load_deny(base / "no-such-register.txt") == [] else "absent register not empty"
            ),
            "a register is read, comments and blanks ignored": lambda base: (
                ""
                if (
                    contract.write(base / "reg.txt", "# a comment\n\n  h-one  \nh-two\n")
                    or load_deny(base / "reg.txt") == ["h-one", "h-two"]
                )
                else "register parsing wrong"
            ),
            "the gate finds NOTHING when no handle is declared": lambda base: (
                ""
                if (
                    contract.write(base / "t" / "x.yaml", f"note: {_SYNTHETIC_HANDLE}\n")
                    or len(check(base / "t", deny=[])) == 0
                )
                else "a handle was reported with an empty register"
            ),
        },
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
