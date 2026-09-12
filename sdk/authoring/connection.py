#!/usr/bin/env python3
"""connection.py — parse the portable connection.yaml CONTRACT + the {mode,ref} credentials SEAM.

The D4 shared data contract: the wiki backend and mac-runtime each PARSE connection.yaml locally (no
cross-repo import). This is the wiki-side parser; mac-runtime carries its own copy of the same tiny
contract. Discovery merges an out-of-band override on top of the shipped base:
  1. $DEPLOYMENT_CONFIG                      — explicit override path (any absolute path)
  2. $CONTENT_ROOT/connection.local.yaml     — out-of-band sibling (gitignored; may carry the account id)
  3. connection.yaml                         — the shipped bundle contract (base)

resolve_credentials() is the D3 SEAM. It returns HOW to authenticate (a boto session spec) — NEVER a
secret value (never fetched here, never logged, never persisted). aws-chain / profile work today;
secretsmanager / ssm are declared but FAIL LOUD with the ref rather than silently degrading to the
ambient chain (which would mis-target a different account). Stdlib + pyyaml only.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def _read(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


def load_connection(content_root, *, deployment_config: str | None = None) -> dict:
    """The effective connection = connection.yaml overlaid with any out-of-band override."""
    cr = Path(content_root)
    base = _read(cr / "connection.yaml")
    ovp = (
        deployment_config
        or os.environ.get("DEPLOYMENT_CONFIG")
        or str(cr / "connection.local.yaml")
    )
    ov = _read(Path(ovp)) if Path(ovp).exists() else {}
    return {**base, **ov} if ov else base


def resolve_credentials(conn: dict) -> dict:
    """The {mode,ref} seam -> a boto session spec. NEVER returns a secret value.

    aws-chain  -> {} (ambient chain: env AWS_PROFILE / SSO / ECS task role — the de-facto manager)
    profile    -> {profile_name: ref} (explicit named SSO/CLI profile)
    secretsmanager | ssm -> raise (fetch-at-call-time not wired; fail loud so it never mis-targets)
    """
    creds = conn.get("credentials") or {}
    mode = creds.get("mode") or "aws-chain"
    ref = creds.get("ref")
    if mode == "aws-chain":
        return {}  # let the ambient chain resolve (task role in prod)
    if mode == "profile":
        if not ref:
            raise ValueError("credentials.mode=profile requires a `ref` (the profile name)")
        return {"profile_name": ref}
    if mode in ("secretsmanager", "ssm"):
        raise NotImplementedError(
            f"credentials.mode={mode!r} (ref={ref!r}) resolver not wired yet — set mode "
            f"profile/aws-chain, or wire the {mode} fetch-at-call-time before answering"
        )
    raise ValueError(f"unknown credentials.mode {mode!r}")


def redacted(conn: dict) -> dict:
    """The safe, reportable view of HOW we authenticate — mode/ref/region/workgroup, NEVER a value.
    The account id is reported as derived-via-STS unless an override explicitly supplies one."""
    creds = conn.get("credentials") or {}
    return {
        "engine": conn.get("engine"),
        "region": conn.get("region"),
        "workgroup": conn.get("workgroup"),
        "credentials_mode": creds.get("mode"),
        "credentials_ref": creds.get("ref"),
        "account": conn.get("account") or "(derived at runtime via STS)",
    }


if __name__ == "__main__":
    import json
    import sys

    c = load_connection(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(json.dumps({"redacted": redacted(c), "session_spec": resolve_credentials(c)}, indent=2))
