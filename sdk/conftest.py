"""Test-wide infra-handle register.

The gates that detect infra handles read a register that is GITIGNORED by design -- a detector that
names what it forbids is a register of those secrets, and this repository is published. So a fresh
checkout has no handles declared, and any test that proves "the gate catches a handle" would pass
vacuously against an empty list.

These tests therefore DECLARE their own, synthetic, handle. Nothing real is written into a fixture
to prove a detector works; previously three tests wrote a production SSO profile into a temp file
for exactly that purpose.
"""

from __future__ import annotations

import pytest

from sdk.gate.check_bundle_secrets import HANDLE_REGISTER_ENV

SYNTHETIC_HANDLE = "zz-synthetic-infra-handle-zz"


@pytest.fixture(autouse=True)
def _synthetic_infra_handles(tmp_path_factory, monkeypatch):
    reg = tmp_path_factory.mktemp("handles") / "infra_handles.txt"
    reg.write_text(f"# synthetic, for tests only\n{SYNTHETIC_HANDLE}\n", encoding="utf-8")
    monkeypatch.setenv(HANDLE_REGISTER_ENV, str(reg))
