"""sdk.acceptance — the Question Lighthouse execution/grading plane (build-time, sdk-only).

Two pure graders + a disposition classifier (``grade``) and an sdk-side orchestrator CLI
(``run``) that grades captured ``/ask`` answers against the bundle's oracle, persists
``acceptance/answers/<id>.yaml``, and re-projects ``acceptance/questions_dashboard.json``.

The wiki (a source-less viewer that MUST NOT import sdk — boundaries.yaml) does the live
answering (``local_ask``) and then hands the captures to ``python -m sdk.acceptance.run``
over a subprocess seam — the same boundary-legal pattern console_api already uses for
export / open / save / lineage. So the SSOT write + deterministic projection stay on the
sdk side of the fence; the graders stay pure and unit-testable.
"""
