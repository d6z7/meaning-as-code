#!/usr/bin/env python3
"""The reachable probe, as a SUBPROCESS. `python -m sdk.connector.probe <bundle-root> --json`

WHY A SUBPROCESS AND NOT A FUNCTION CALL. `boundaries.yaml` forbids the console importing `sdk` —
"may_not_import: [sdk]" — and that rule is not softened by the SDK fork being retired. The console
already reaches every other build-time operation this way (`-m sdk.container.loader`,
`-m sdk.cli.harvest`), so the probe travels the same road: a process boundary the host cannot
accidentally cross, and a connector's import-time failure cannot take the console down with it.

THE ONE PLACE THAT REACHES A SOURCE. Everything else in the connector contract is offline and free:
`validate_config` reads JSON, the registry reads a shipped index, `resolvable` imports nothing. This
module is the only code that opens a connection, and it runs ONLY when a human asks.

BILLING IS EXPLICIT AND PER-CONNECTOR. `probe_cost` is a property of the CONNECTOR, not of the tier:
a local database costs nothing and a cloud warehouse costs money. A `billed` connector therefore
refuses without `--i-accept-billing`, and refuses LOUDLY — exit 2, could-not-run — rather than
quietly doing it. Nothing in this estate reaches a billed service unprompted, and a page that probed
on load would break that rule every time somebody clicked a tab.

Emits one JSON object on stdout. Exit 0 = the probe ran (ok true or false); exit 2 = it could not
run and nothing was attempted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _fail(reason: str, *, cost: str | None = None) -> int:
    print(json.dumps({"ok": None, "could_not_run": True, "reason": reason, "probe_cost": cost}))
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", help="the bundle root")
    ap.add_argument("--json", action="store_true", help="accepted for symmetry; output is always JSON")
    ap.add_argument("--i-accept-billing", action="store_true",
                    help="required for a connector whose probe_cost is `billed`")
    a = ap.parse_args(argv)

    root = Path(a.root)
    manifest = root / "mac.project.yaml"
    if not manifest.is_file():
        return _fail(f"no mac.project.yaml at {root}")

    m = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    rt = m.get("runtime") or {}
    cid = rt.get("connector")
    if not cid:
        return _fail("the bundle declares no runtime.connector — below the tiers, not a failure")

    conn_rel = rt.get("connection")
    if not conn_rel:
        return _fail(f"{cid} is declared but no runtime.connection names its config")
    conn_path = root / str(conn_rel)
    if not conn_path.is_file():
        return _fail(f"runtime.connection names {conn_rel}, which is not there")

    conn = yaml.safe_load(conn_path.read_text(encoding="utf-8")) or {}

    from sdk.connector import registry

    cls = registry.resolve(cid)
    if cls is None:
        return _fail(f"{cid} is not installed on this host")

    cost = getattr(cls, "probe_cost", None)
    cost = cost() if callable(cost) else cost
    cost = str(cost) if cost is not None else None
    if cost == "billed" and not a.i_accept_billing:
        return _fail(f"{cid} bills for a probe; re-run with --i-accept-billing", cost=cost)

    errs = cls.validate_config(conn) if hasattr(cls, "validate_config") else []
    if errs:
        return _fail("the config does not validate: "
                     + "; ".join(getattr(e, "message", str(e)) for e in list(errs)[:3]), cost=cost)

    try:
        c = cls(conn, base_dir=root)
        r = c.probe()
    except Exception as exc:                                            # noqa: BLE001
        # A connector's failure is REPORTED, never raised into the host. That is the same rule
        # tools/_plugin.py states for bundle plugins: a plugin's exit code must not become the
        # checker's verdict.
        return _fail(f"{cid} raised during probe: {type(exc).__name__}: {exc}", cost=cost)

    print(json.dumps({
        "ok": bool(getattr(r, "ok", False)),
        "could_not_run": False,
        "detail": getattr(r, "detail", None),
        "target": getattr(r, "target", None),
        "latency_ms": getattr(r, "latency_ms", None),
        "connector": cid,
        "probe_cost": cost,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
