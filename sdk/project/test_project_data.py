"""The DQ dashboard's DISPOSITION — what a human ruled, carried through the projector.

THE DEFECT THIS FILE IS BUILT AGAINST, measured once and then turned into tests.

`data/quality/dq_dashboard.json` is the only structured artifact the console's Data Quality page
reads, and its per-finding dict is a hand-written allow-list. `status`, `ruled_by` and `reason` were
not in it. The register is loaded whole, so every value was in memory and none was emitted: measured
on a live bundle whose register carried `status` on 6 of 6 (4 `open`, 2 `accepted` with `ruled_by`
and `reason`), the projected dashboard carried `status` on 0 of 6. The page therefore could not tell
an issue a named human examined and tolerated from an issue nobody has read, which the register's
own header calls the two most different things in it — and the two entries the operator HAD ruled on
rendered as the least-attended rows in the bundle.

THE NEGATIVE CONTROL IS THE POINT OF CASE `beta`. `mac_vocabulary.yaml#dq_status` is a closed set and
says why: `open` means somebody WROTE `open`, and the set is closed "so that absence of a status is a
FINDING rather than a fourth, unnamed meaning". A projector that defaulted a missing status to `open`
would fabricate a human ruling on every entry of a legacy register — measured at 45 of 45 with no
status key on one live bundle. Absence must arrive as null and be counted separately.

WHAT THIS PROJECTOR DELIBERATELY DOES NOT COMPUTE: any notion of "ruled", "covered" or "terminal".
That needs the disposition law, which has exactly two readers (check_dq_resolution_sync.py and
check_data_plane_approved.py) and an NS-/DQ- asymmetry a third implementation would disagree with.
Case `gamma` pins the consequence: a half-ruled entry is carried as it stands, present field and
absent field alike, and is not silently dropped or repaired here.

The bundles name nothing real — alpha, beta, gamma in a temp directory. Offline: no duckdb, no
warehouse, no network, no fixture repo.
"""

from __future__ import annotations

import json

import yaml

from sdk.project import project_data as P


def _bundle(tmp_path, issues):
    """The smallest bundle build_data() will run over: a register, and nothing else."""
    q = tmp_path / "data" / "quality"
    q.mkdir(parents=True)
    (q / "data_quality_register.yaml").write_text(
        yaml.safe_dump({"metadata": {"status": "draft"}, "issues": issues}, sort_keys=False)
    )
    return tmp_path / "data"


def _dash(tmp_path, issues) -> dict:
    data_dir = _bundle(tmp_path, issues)
    P.build_data(data_dir)
    return json.loads((data_dir / "quality" / "dq_dashboard.json").read_text())


def _by_id(dash) -> dict:
    return {f["id"]: f for f in dash["findings"]}


def test_alpha_carries_the_disposition_for_a_ruled_and_an_unruled_issue(tmp_path):
    """The register's ruling reaches the dashboard, for an `accepted` entry and an `open` one."""
    dash = _dash(
        tmp_path,
        [
            {
                "id": "DQ-ALPHA-01",
                "title": "a defect a person examined and tolerated",
                "severity": "low",
                "confidence": "C",
                "status": "accepted",
                "ruled_by": "operator",
                "reason": "the residue is disclosed and does not change any served answer",
            },
            {
                "id": "DQ-ALPHA-02",
                "title": "a defect nobody has read",
                "severity": "high",
                "confidence": "C",
                "status": "open",
            },
        ],
    )
    f = _by_id(dash)
    assert f["DQ-ALPHA-01"]["status"] == "accepted"
    assert f["DQ-ALPHA-01"]["ruled_by"] == "operator"
    assert f["DQ-ALPHA-01"]["reason"].startswith("the residue is disclosed")
    assert f["DQ-ALPHA-02"]["status"] == "open"
    assert f["DQ-ALPHA-02"]["ruled_by"] is None
    assert f["DQ-ALPHA-02"]["reason"] is None
    # The denominator the page needs to draw a "ruled" step instead of a hard-coded zero.
    assert dash["stats"]["by_status"] == {"accepted": 1, "open": 1}
    assert dash["stats"]["status_absent"] == 0


def test_beta_absence_arrives_as_absence_and_is_counted(tmp_path):
    """A register with no `status` key anywhere: null per finding, and an absence count.

    NOT `open`. Defaulting would fabricate a ruling on every entry of a legacy register.
    """
    dash = _dash(
        tmp_path,
        [
            {"id": "DQ-BETA-01", "title": "no disposition recorded", "severity": "medium"},
            {"id": "NS-BETA-01", "title": "measured, deliberately not served", "severity": "low"},
        ],
    )
    for f in dash["findings"]:
        assert f["status"] is None, f
        assert f["ruled_by"] is None
        assert f["reason"] is None
    assert dash["stats"]["by_status"] == {}
    assert dash["stats"]["status_absent"] == 2
    assert dash["stats"]["status_absent"] == dash["stats"]["total"]


def test_gamma_a_half_ruled_entry_is_carried_as_it_stands(tmp_path):
    """`accepted` with `ruled_by` and no `reason` — carried present/None, not repaired, not dropped.

    The requires-law failure belongs to the gate (mac.dq_status.accepted requires both fields). The
    projector reports; it does not judge, and it must not quietly drop the half-ruled row that a
    gate is about to name.
    """
    dash = _dash(
        tmp_path,
        [
            {
                "id": "DQ-GAMMA-01",
                "title": "a ruling with no stated reason",
                "severity": "low",
                "status": "accepted",
                "ruled_by": "data-owner",
            }
        ],
    )
    f = _by_id(dash)["DQ-GAMMA-01"]
    assert f["status"] == "accepted"
    assert f["ruled_by"] == "data-owner"
    assert f["reason"] is None
    assert dash["stats"]["by_status"] == {"accepted": 1}
    assert dash["stats"]["status_absent"] == 0


def test_the_overview_markdown_prints_the_disposition_too(tmp_path):
    """The markdown is a projected surface as well, and it dropped the ruling identically.

    Measured: the two entries the operator had ruled on printed `✓ resolved` (a transform's claim)
    and `not yet reconciled` (nobody's claim). Neither said `accepted · ruled by operator`.
    """
    data_dir = _bundle(
        tmp_path,
        [
            {
                "id": "DQ-ALPHA-01",
                "title": "a defect a person examined and tolerated",
                "severity": "low",
                "status": "accepted",
                "ruled_by": "operator",
                "reason": "disclosed",
            }
        ],
    )
    P.build_data(data_dir)
    ov = (data_dir / "quality" / "0-issues-overview.md").read_text()
    assert "| disposition |" in ov
    assert "accepted · ruled by operator" in ov
    page = (data_dir / "quality" / "DQ-ALPHA-01.md").read_text()
    assert "disposition **accepted · ruled by operator**" in page
    assert "ruled by **operator**" in page
