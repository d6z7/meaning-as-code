#!/usr/bin/env python3
"""harvest.py — the VSC build-time harvest entrypoint (authoring is NOT a wiki operation).

Enumerates a source's Glue tables and authors MAC through the SDK, persisting ONLY via
sdk.authoring.operations (the single, status-gated writer), then projects the read view.

  --mode data      author the data plane (source/dq/transform/dataset + the realizing view SQL,
                   extracted to a sibling data/transforms/<name>.sql) with live Athena profiling
  --mode materialize  own-schema MATERIALIZE: read connection.yaml (view_schema = the source's OWN
                   schema), SHOW TABLES collision-check, then CREATE OR REPLACE VIEW <view_schema>.<name>
                   from each transform's .sql and verify it SELECTs. REFUSES a shared/empty schema.
                   DRY-RUN by default (no AWS); --accept executes the DDL live.
  --mode lookups   own-schema LOOKUP-BUILD: profile every resolvable dim view -> data/lookups/
                   <name>.lookup.csv (name->code) so runtime resolves inline, never by probing the EAV.
                   DRY-RUN by default (no AWS); --accept profiles + writes the CSVs live.
  --mode concepts  author one MAC concept per table (validated against the grammar)
  --mode project   OFFLINE re-projection only (no AWS/Bedrock) — regenerate the served read view
                   (objects.json + quality/vocab + *.md), ALWAYS threading column-level lineage.
                   This is the single supported way to regen before publish; never hand-run
                   build_data() (it drops the Lineage view tab).
                   GATED — the bundle is COMPILED first (meaning-as-code tools/mac_compile.py) and
                   projection REFUSES on any error-severity diagnostic, printing the compiler's own
                   findings as the reason. The complete finding set is persisted to
                   <content-root>/compile.json on every attempt, refusals included. Override with
                   --project-anyway "<reason>" (loud + recorded). See CONFORMANCE.md §5.
  --mode onboard   ONE-COMMAND, resume-aware onboarding of a NEW dataset: scaffold (if missing)
                   -> data -> reconcile -> project. Concepts are NOT chained: authoring them is a
                   judgement, not a stage (see harvest_concepts). DRY-RUN by default (makes NO AWS
                   call — prints the plan + runs only the offline project); --accept persists the
                   billed data/concepts stages. Resume = a stage whose outputs already exist is
                   skipped. Model-swappable (--model/--effort/--thinking-budget or harvest.yaml)
                   and idempotent (a content-addressed .harvest_cache/ makes unchanged LLM inputs
                   re-run byte-identically; --refresh bypasses it).
  --scaffold       stamp a NEW source skeleton (dirs + mac.project.yaml + connection.example.yaml
                   + harvest.yaml) at --content-root, then exit (idempotent; never overwrites).

MODEL SWAP (Phase 6): the harvest model is chosen per-source (harvest.yaml) or per-run
(--model / MAC_HARVEST_MODEL) and dispatched on its id PREFIX — eu./us./global.anthropic.* =>
Bedrock Converse (with a --thinking-budget knob), openai.*/gpt-* => Mantle GPT. The id shape is
VALIDATED at startup, before any Athena/Bedrock call, so a typo fails loud for $0.

Writes into <content-root>/{data,ontology}. Requires AWS creds (Bedrock + Glue + Athena) — this
is the build-time seat, run in VSC, never from the browser. Example:

  python -m sdk.cli.harvest --content-root sources/gaps/fpl --databases <glue_db> --mode data

NOTE: this is the orchestration relocated out of the GUI (console_api). It carries the same
authoring calls that ran there; a live AWS smoke is the remaining verification (billable).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import sys as _sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from sdk.authoring import authoring, data_plane, edges, materialize, operations
from sdk.authoring.harvest_model import validate_model_id
from sdk.project import knowledge, mac_okf, project_data, references, source_ident
from sdk.project.harvest_cache import HarvestCache

# DEFAULTS. model/effort/thinking_budget are resolved per-run with precedence
# CLI flag > per-source harvest.yaml > env > these defaults (see _resolve_harvest_config).
_MODEL = "global.anthropic.claude-opus-4-6-v1"
_EFFORT = "medium"
# NO INSTANCE VALUE IS A DEFAULT IN THE TOOLING. Connection and identity belong to the
# ONTOLOGY -- connection.yaml for how to reach the warehouse, mac.project.yaml for what the
# source is called -- and the SDK reads them per bundle. A module-level default cannot be
# bundle-aware by construction, so every one of them was one ontology's configuration baked
# into the tooling that serves all of them.
# These stay ENV-ONLY: an operator may point a run at a profile/region, but the tooling ships no
# opinion about which. Absent, they are None and boto's ambient chain decides -- which is exactly
# what connection.yaml's `credentials.mode: aws-chain` already means.
_REGION = os.environ.get("AWS_REGION")
_PROFILE = os.environ.get("AWS_PROFILE")
_GLUE_REGION = os.environ.get("MAC_GLUE_REGION") or _REGION
_EXEMPLAR = _REPO / "sdk" / "authoring" / "exemplars" / "geography" / "country.yaml"
_MANIFEST_SIDECAR = ".harvest_manifest.yaml"  # reproducibility ledger; NOT served/hashed/published


# The framework. ONE home for the path — three call sites reach into it (lineage, the semantic phase,
# and the compile gate below), and three spellings of the same path is a fact in three homes.


def _framework_tools() -> Path:
    """The framework's tools/ dir, resolved the way MIGRATION.md phase 1 says consumers must.

    This was a SIBLING-DIRECTORY GUESS, and therefore one of the ~130 call sites check_docs.py
    names as the estate's measured root cause: locating the framework by filesystem path while
    it is not installed anywhere. The guess broke twice. It broke when this package moved under
    packages/ (the compile gate then refused every bundle for "compiler could not be run"), and
    it broke again on an estate that had cloned the framework under a different directory name
    -- found by a real install into a renamed scratch estate.

    THE SIBLING GUESS IS GONE. `sdk/` now lives INSIDE the framework repository, so there is no
    sibling to find and no directory name to be wrong about: `tools/` is two levels up from this
    file, by construction, in a tree `check_grammar_home` proves holds exactly one grammar. That
    is a fact about one repository rather than a guess across two, which is the entire difference.

    Order: explicit override, installed package, this tree. There is no fourth step -- if none
    resolve this RAISES, because a compile gate that cannot find the compiler must say so rather
    than report "compiler could not be run" over every bundle, which is what the guess did.
    """
    override = os.environ.get("MAC_FRAMEWORK_TOOLS")
    if override:
        return Path(override)
    try:
        from meaning_as_code import framework_root  # type: ignore[import-not-found]
    except ImportError:
        pass  # not installed — this tree is the remaining answer
    else:
        # Deliberately NOT wrapped: framework_root() raises when $MEANING_AS_CODE points at
        # something carrying no mac.schema.json, precisely so a wrong answer is loud. Catching
        # it here would turn the framework's loud failure into a silent wrong one.
        return framework_root() / "tools"
    in_tree = Path(__file__).resolve().parents[2] / "tools"
    if (in_tree / "mac_compile.py").exists():
        return in_tree
    raise RuntimeError(
        f"the framework's tools/ could not be resolved: $MAC_FRAMEWORK_TOOLS is unset, "
        f"meaning_as_code is not installed, and {in_tree} carries no mac_compile.py"
    )


# ONE home for the path -- three call sites reach into it.
_MAC_TOOLS = _framework_tools()
# The persisted compile verdict, written on EVERY projection attempt — including a refused one. This
# is the dashboard's input: after any compile the complete finding set is readable at any later point,
# by anyone, without re-running it. Sibling of objects.json (the other bundle-root read-view artifact).
_COMPILE_RECORD = "compile.json"
_OVERRIDE_FLAG = "--project-anyway"


def _session():
    import boto3

    return boto3.Session(profile_name=_PROFILE) if _PROFILE else boto3.Session()


def _tables(glue, databases):
    out = []
    for db in databases:
        tok = None
        while True:
            kw = {"DatabaseName": db, "MaxResults": 100}
            if tok:
                kw["NextToken"] = tok
            resp = glue.get_tables(**kw)
            out += [(db, t) for t in resp.get("TableList", [])]
            tok = resp.get("NextToken")
            if not tok:
                break
    return out


def _schema_md(db, tbl):
    cols = (tbl.get("StorageDescriptor", {}) or {}).get("Columns", [])
    rows = "\n".join(f"| {c.get('Name')} | {c.get('Type', '')} |" for c in cols)
    return f"# {tbl.get('Name')} ({db})\n\n| column | type |\n|---|---|\n{rows}"


def _concept_name(tname):
    return "".join(w.capitalize() for w in re.split(r"[_\s]+", tname) if w)


def _read_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(Path(p).read_text()) or {}
    except Exception:
        return {}


def _dataset_input(ds_path: Path, data_dir: Path) -> dict:
    """Assemble ONE concept's authoring input from the DATA TRANSFORMATION LAYER (not raw Glue):
    the clean serving relation's schema + roles + declared FKs, the transform SQL that builds it,
    and the upstream raw source schema(s) it derives from. This is the richer signal the user asked
    us to 'respect' — the FPL views + their transforms, grounded back to the raw DBs."""
    cr = data_dir.parent
    d = _read_yaml(ds_path)
    tbl = d.get("table", {}) or {}
    name = tbl.get("name") or ds_path.stem
    schema = tbl.get("schema") or ""
    relation = f"{schema}.{name}" if schema else name
    cols = d.get("columns", []) or []
    fks = d.get("foreign_keys", []) or []
    # the transform that produces this dataset (derived_from.pipeline, else stem match)
    pipe = (d.get("derived_from") or {}).get("pipeline")
    tr = _read_yaml(cr / pipe) if pipe else {}
    if not tr and (data_dir / "transforms" / f"{ds_path.stem}.yaml").exists():
        tr = _read_yaml(data_dir / "transforms" / f"{ds_path.stem}.yaml")
    produces = tr.get("produces", {}) or {}
    produces_relation = produces.get("relation") or relation
    grain = produces.get("grain") or ""
    sql, sqlf = "", produces.get("sql_file")
    if sqlf and (cr / sqlf).exists():
        sql = (cr / sqlf).read_text()[:6000]
    elif (data_dir / "transforms" / f"{ds_path.stem}.sql").exists():
        sql = (data_dir / "transforms" / f"{ds_path.stem}.sql").read_text()[:6000]
    # upstream raw source schema(s)
    raw_md = []
    for inp in tr.get("inputs") or []:
        desc = inp.get("descriptor") if isinstance(inp, dict) else None
        if desc and "/sources/" in str(desc):
            s = _read_yaml(cr / desc)
            stbl = s.get("table", {}) or {}
            rows = "\n".join(
                f"| {c.get('name')} | {c.get('type', '')} |" for c in (s.get("columns", []) or [])
            )
            raw_md.append(
                f"### raw source: {stbl.get('schema', '')}.{stbl.get('name', Path(desc).stem)}\n"
                f"| column | type |\n|---|---|\n{rows}"
            )
    colrows = "\n".join(
        f"| {c.get('name')} | {c.get('type', '')} | {c.get('role', '')} | "
        f"{c.get('description', '')} |"
        for c in cols
    )
    md = [f"# {produces_relation}  —  CLEAN serving relation (FPL data transformation layer)"]
    if grain:
        md.append(f"\ngrain: {grain}")
    md += [
        "",
        "## Clean schema (the AI-friendly serving shape the ontology binds to)",
        "| column | type | role | description |",
        "|---|---|---|---|",
        colrows,
    ]
    if fks:
        md += [
            "",
            "## Foreign keys (declared joins to other serving relations)",
            *[
                f"- {fk.get('from_column')} -> {fk.get('to_table')}.{fk.get('to_column')}"
                for fk in fks
            ],
        ]
    if sql:
        md += ["", "## Built by this transform (the data-transformation SQL)", "```sql", sql, "```"]
    if raw_md:
        md += ["", "## Upstream raw source(s) it derives from (the original DBs)", *raw_md]
    terms = (
        [name]
        + [w for w in re.split(r"[_\s]+", name) if len(w) > 2]
        + [c.get("name") for c in cols if c.get("name")]
    )
    return {
        "md": "\n".join(md),
        "terms": terms,
        "relation_bare": name,
        "produces_relation": produces_relation,
        "foreign_keys": fks,
        "roles": {c.get("name"): c.get("role") for c in cols if c.get("name")},
    }


def _lineage_flows(cr: Path) -> list:
    """FPL-style column-level lineage flows for this source via meaning-as-code's
    lineage_project.py. MUST be threaded into the projection: build_data() without it
    silently flips every data object's `lineage` flag to False and drops the Lineage
    view tab (regression seen 2026-08-13). Returns [] only if the tool is truly absent."""
    tool = _MAC_TOOLS / "lineage_project.py"
    if not tool.exists() or not (cr / "mac.project.yaml").exists():
        print(
            "  lineage: tool or mac.project.yaml missing — projecting WITHOUT lineage (tabs will be hidden)"
        )
        return []
    outp = Path(tempfile.gettempdir()) / f".lineage.{cr.name}.json"
    try:
        subprocess.run(
            [sys.executable, str(tool), str(cr), "--out", str(outp)],
            check=True,
            capture_output=True,
            timeout=180,
        )
        flows = json.loads(outp.read_text()).get("flows", [])
        outp.unlink(missing_ok=True)
        return flows
    except Exception as e:
        print(f"  lineage: generation FAILED ({e}) — refusing to project a lineage-less read view")
        raise


def _semantic_diagnostics(cr) -> dict:
    """Run MAC's semantic phase and write ontology/diagnostics.json. Never fatal: a framework that is
    absent or older than this projector must degrade to 'no diagnostics', not break the projection."""
    import json as _json

    tools = _MAC_TOOLS
    if not (tools / "mac_diagnostics.py").exists():
        return {"skipped": "framework has no semantic phase"}
    _sys.path.insert(0, str(tools))
    try:
        import mac_diagnostics as _diag

        doc = _diag.build(cr)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    out = Path(cr) / "ontology" / "diagnostics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return doc["stats"]


# ---------------------------------------------------------------------------------------------
# THE COMPILE GATE — projection REFUSES a bundle that does not conform
# ---------------------------------------------------------------------------------------------
# OPERATOR RULING: "you cannot run anything unless ontology follows ALL standard ... a check that
# does not block is not enforcement." Before this, `--mode project` ran happily on a bundle the MAC
# compiler reports 4 errors on, and published a read view derived from it. The findings existed; they
# just did not stop anything, which is the same as not existing.
#
# THE REFUSAL IS THE DEFAULT AND THE OVERRIDE IS LOUD. An unconditional refusal would have made every
# non-conformant bundle unprojectable in one step — including the one this was built against — so the
# escape exists. It is deliberately shaped so that using it is a decision somebody made and can be held
# to, not a config value that quietly drifts on:
#   * it is a CLI flag, never an env var — an env var is invisible in the command somebody typed;
#   * its VALUE is the reason, so the flag cannot be passed without stating why;
#   * it prints a banner that cannot be mistaken for normal output;
#   * it is RECORDED, with username and timestamp, in the same compile record the dashboard reads —
#     so an artifact built over a refusal carries the admission next to the findings, permanently.
#
# WHY IT ALSO REFUSES WHEN THE COMPILER CANNOT RUN: "not computed" and "clean" are opposite facts, and
# the compiler's own footer is built to keep them apart. A gate that degrades to silence when the
# framework is missing would report an unchecked bundle as an acceptable one — the exact failure the
# whole taxonomy exists to end. Unreachable ⇒ unknown ⇒ refuse, with the same documented override.


class CompileRefused(RuntimeError):
    """Projection refused: the bundle does not compile (or conformance could not be established).

    Carries the compiler's OWN rendered findings as the reason — never a paraphrase. A gate that
    restates a finding in its own words is a second home for it, and the two wordings drift."""

    def __init__(self, message: str, *, record: Path | None = None):
        super().__init__(message)
        self.record = record


def _compile_record_path(cr: Path) -> Path:
    return Path(cr) / _COMPILE_RECORD


def compile_gate(cr: Path, *, project_anyway: str | None = None) -> dict:
    """Compile the bundle; PERSIST the complete finding set; refuse on any error-severity finding.

    Returns the persisted record. Raises `CompileRefused` when the bundle does not compile and no
    override reason was given. `project_anyway` is the operator's reason string (the value of
    ``--project-anyway``); a blank reason is not an override."""
    cr = Path(cr)
    started = datetime.now(UTC)
    reason = (project_anyway or "").strip() or None
    _sys.path.insert(0, str(_MAC_TOOLS))
    try:
        import mac_compile as _compiler
        import mac_diag as _diag

        diags, rows, timings = _compiler.compile_bundle(str(cr))
    except Exception as exc:
        # The framework is absent, too old, or died. Conformance is UNKNOWN — which is not clean.
        why = (
            f"the MAC compiler could not be run over {cr}, so this bundle's conformance is "
            f"UNKNOWN, not clean: {type(exc).__name__}: {exc}\n"
            f"  compiler expected at: {_MAC_TOOLS / 'mac_compile.py'}"
        )
        if not reason:
            raise CompileRefused(
                f"REFUSED — projection did not run.\n{why}\n\n"
                f"  To project anyway, state why:\n"
                f"    python -m sdk.cli.harvest --content-root {cr} --mode project \\\n"
                f'        {_OVERRIDE_FLAG} "<why you are projecting an unverified bundle>"'
            ) from exc
        print(
            f"\n{'=' * 96}\n!! {_OVERRIDE_FLAG} — CONFORMANCE WAS NOT ESTABLISHED AND PROJECTION "
            f"IS PROCEEDING\n!! {why}\n!! reason (recorded): {reason}\n{'=' * 96}\n"
        )
        return {
            "schema": "mac.diagnostics/compile/1",
            "bundle": str(cr),
            "generated_at": started.isoformat(),
            "verdict": "NOT_COMPILED",
            "gate": {
                "ran_by": "sdk/cli/harvest.py::compile_gate",
                "compiler_reachable": False,
                "override": {
                    "flag": _OVERRIDE_FLAG,
                    "reason": reason,
                    "by": os.environ.get("USER") or os.environ.get("USERNAME") or "?",
                    "at": started.isoformat(),
                    "detail": why,
                },
            },
        }

    stats = _diag.summarise(diags)
    errors = [d for d in diags if d.severity == _diag.ERROR]
    codes = sorted({d.code for d in errors})
    rendered = _compiler.render(diags, str(cr), show=_diag.ERROR)
    headline = (
        f"{stats['errors']} error(s), {stats['warnings']} warning(s) over "
        f"{stats['total']} diagnostic(s) carrying {stats['witnesses']} witness(es)"
        + (f"  [{' '.join(codes)}]" if codes else "")
    )

    override = None
    if errors and reason:
        override = {
            "flag": _OVERRIDE_FLAG,
            "reason": reason,
            "by": os.environ.get("USER") or os.environ.get("USERNAME") or "?",
            "at": started.isoformat(),
            "errors_overridden": stats["errors"],
            "codes_overridden": codes,
        }
    record = _compiler.payload(
        str(cr),
        diags,
        rows,
        timings,
        started=started,
        duration=(datetime.now(UTC) - started).total_seconds(),
        extra={
            "gate": {
                "ran_by": "sdk/cli/harvest.py::compile_gate",
                "compiler_reachable": True,
                "blocks_on": "any error-severity diagnostic",
                "override": override,
            }
        },
    )
    out = _compile_record_path(cr)
    out.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )

    if not errors:
        print(f"  compile: COMPILES — {headline}; record -> {out.name}")
        return record
    if not reason:
        raise CompileRefused(
            f"REFUSED — projection did not run. The bundle DOES NOT COMPILE.\n\n"
            f"{rendered}\n\n"
            f"{headline}\n"
            f"  full finding set (every severity, every witness): {out}\n"
            f"  re-read it any time with: python {_MAC_TOOLS / 'mac_compile.py'} {cr}\n\n"
            f"  Clear the error-severity findings, or declare the ones MAC has no definition for in\n"
            f"  mac.project.yaml#conformance.out_of_scope with a reason (CONFORMANCE.md §5).\n"
            f"  To project a non-conformant bundle anyway, state why:\n"
            f"    python -m sdk.cli.harvest --content-root {cr} --mode project \\\n"
            f'        {_OVERRIDE_FLAG} "<why this non-conformant bundle must be projected>"',
            record=out,
        )

    bar = "=" * 96
    print(
        f"\n{bar}\n"
        f"!! PROJECTING A BUNDLE THAT DOES NOT COMPILE — {_OVERRIDE_FLAG} WAS USED\n"
        f"!! {stats['errors']} error-severity finding(s) are being IGNORED: {' '.join(codes)}\n"
        f"!! reason (recorded): {reason}\n"
        f"!! by {override['by']} at {override['at']}\n"
        f"!! recorded in: {out}#gate.override — permanently, next to the findings\n"
        f"!! EVERY artifact this run produces is derived from a NON-CONFORMANT bundle.\n"
        f"{bar}\n"
    )
    print(rendered + "\n")
    return record


def project_source(cr: Path, *, project_anyway: str | None = None) -> dict:
    """The SINGLE, deterministic, OFFLINE re-projection of a source's served read view
    (objects.json + ontology_quality.json + vocabulary.json + the ontology *.md). No AWS,
    no Bedrock. This is the ONLY supported way to regenerate projections after an SSOT edit
    and before publish — it always threads column-level lineage, so ad-hoc build_data() calls
    (which drop the Lineage tab) are never needed. Idempotent for a given SSOT.

    GATED: the bundle is COMPILED FIRST and this refuses to project a bundle that does not conform
    (`CompileRefused`). The gate sits here, not in `main`, because every projection path in this file
    and in `sdk/container/save.py` funnels through this function — enforcement wired at one caller is
    enforcement the next caller routes around."""
    compile_gate(cr, project_anyway=project_anyway)  # REFUSES before any artifact is written
    flows = _lineage_flows(cr)
    stats = project_data.build_data(cr / "data", lineage=flows)  # objects/quality/vocab + data *.md
    concepts_dir = cr / "ontology" / "concepts"
    if concepts_dir.exists():
        mac_okf.build(concepts_dir, concepts_dir)  # ontology read-view *.md
    know = knowledge.build(cr)  # knowledge/ pages from the source registers
    refs = references.build(cr)  # references/ guardrails page (wiki /ask reads it first)
    # SEMANTIC PHASE — the compiler's findings, generated HERE so the dashboard cannot go stale.
    # boundaries.yaml lets the projector reach meaning-as-code; _lineage_flows above already does,
    # by subprocess. This imports, because the analysis has to hand back objects, not text.
    diags = _semantic_diagnostics(cr)
    # NO SECOND COMPILE HERE. `compile_gate` above already ran the compiler and wrote the complete
    # finding set to <bundle>/compile.json — the dashboard's input. Compiling again to "refresh" the
    # record would run every check twice AND overwrite the gate's `gate.override` admission, erasing
    # the one permanent trace that a human projected a non-conformant bundle.
    print(
        f"projected read view (offline): {stats}; lineage flows: {len(flows)}; "
        f"references: {refs}; knowledge: {know}; diagnostics: {diags}; "
        f"compile record: {_COMPILE_RECORD}"
    )
    return stats


# ---------------------------------------------------------------------------------------------
# Phase 6: model-swap config resolution · response cache · reproducibility sidecar · scaffold
# ---------------------------------------------------------------------------------------------


def _resolve_harvest_config(
    cr: Path, *, cli_model=None, cli_effort=None, cli_thinking_budget=None
) -> dict:
    """Resolve the model-swap knobs for THIS run. Precedence (most specific first):
        CLI flag  >  per-source harvest.yaml  >  env (MAC_HARVEST_MODEL/MAC_EFFORT/
        MAC_THINKING_BUDGET)  >  built-in default.
    A per-source `harvest.yaml` ({model, effort, thinking_budget, region}) is the committed
    reproducibility contract; env is the fallback for sources that don't ship one. The model id
    is VALIDATED here (shape gate) so a typo fails loud BEFORE any Athena/Bedrock call."""
    hy = _read_yaml(cr / "harvest.yaml")

    def _pick(cli, key, env_key, default):
        if cli is not None:
            return cli
        if hy.get(key) is not None:
            return hy[key]
        env = os.environ.get(env_key)
        return env if env not in (None, "") else default

    model = str(_pick(cli_model, "model", "MAC_HARVEST_MODEL", _MODEL))
    effort = str(_pick(cli_effort, "effort", "MAC_EFFORT", _EFFORT))
    tb_raw = _pick(cli_thinking_budget, "thinking_budget", "MAC_THINKING_BUDGET", None)
    thinking_budget = None if tb_raw in (None, "", "null", "none") else int(tb_raw)
    region = hy.get("region") or _REGION
    validate_model_id(model)  # STARTUP shape gate — fail loud for $0, not mid-harvest
    return {"model": model, "effort": effort, "thinking_budget": thinking_budget, "region": region}


def _make_cache(cr: Path, refresh: bool) -> HarvestCache:
    """The content-addressed LLM cache for this source, under <cr>/.harvest_cache/ (gitignored,
    skipped by the secret gate, never published). --refresh bypasses reads."""
    return HarvestCache(cache_dir=cr / ".harvest_cache", refresh=bool(refresh))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_harvest_manifest(cr: Path, meta: dict) -> Path:
    """Write the reproducibility LEDGER to the SIDECAR <cr>/.harvest_manifest.yaml.

    This is deliberately a SIDECAR, NOT part of the served surface: it is gitignored, absent
    from mac.project.yaml `publish.include`, and skipped by check_bundle_secrets. It carries
    VOLATILE run data (timestamp, cache hit/miss counts) that would churn publish.py's
    write-once tree hash if it were frozen into the artifact — so it must never be a publish
    input. It records the chosen model/effort/thinking_budget, region, databases, per-input
    sha256, and cache stats, so a run is reproducible."""
    doc = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), **meta}
    path = Path(cr) / _MANIFEST_SIDECAR
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return path


_SCAFFOLD_PROJECT = """# Per-source MAC project manifest — stamped by `harvest --scaffold` for a NEW dataset.
# A data source is a self-contained MAC project: data plane + ontology plane. Fill in the
# specifics, then run `harvest --mode onboard` (dry-run) / `--accept` (live) to author it.
metadata:
  project: {domain}/{dataset}
  kind: mac_project
  data_domain: {domain}
  dataset: {dataset}
planes:
  data: data          # DATA plane root (sources -> transforms -> datasets, quality, lookups)
  ontology: ontology  # ONTOLOGY plane root (concepts under ontology/concepts, rules inline)
  governance: governance  # GOVERNANCE plane root — PHASE + lock, the SME ledger, the
                          # intervention ledger + vanilla delta, warehouse properties,
                          # decisions/. ONE home for the controls: fpl2 grew these across
                          # four separate places and each was found late, by hand.
sources: data/sources
transforms: data/transforms
descriptors: data/datasets
lookups: data/lookups   # name->code registers (built by `harvest --mode lookups`); no-probe resolution plane

# RUNTIME — what an answering engine needs to answer with THIS source (resolved from the bundle).
runtime:
  source: {label}                    # the source LABEL (badges objects; de-FPL identity)
  connection: connection.yaml        # the shared data-source connection contract

# PUBLISH — the served surface compiled into the immutable artifact (manifest-driven).
publish:
  include:
    - data
    - ontology
    - objects.json
    - mac.project.yaml
    - index.md
    - connection.yaml
    - connection.example.yaml
    - runtime
    - references

# A scaffolded bundle must COMPILE on day one: these carry no meaning, so they are declared rather
# than left undefined. MAC001's escape hatch is a DECLARATION with a reason — silence is not.
conformance:
  out_of_scope:
  - path: connection.yaml
    reason: Warehouse endpoint and workgroup. Deployment configuration, carries no meaning.
  - path: connection.example.yaml
    reason: Sanitized template for a new deployment. Configuration, carries no meaning.
  - path: harvest.yaml
    reason: Build-time model/effort knobs. Tool configuration, carries no meaning.
"""

_SCAFFOLD_CONNECTION = """# connection.example.yaml — sanitized template for a NEW deployment.
# Copy to connection.yaml (the shipped contract) and/or connection.local.yaml (gitignored
# out-of-band override). NEVER commit an account id or a credential value.
engine: athena
region: '<GLUE_ATHENA_REGION>'           # e.g. eu-west-1
workgroup: '<ATHENA_WORKGROUP>'          # enforces its own result location
output: null
catalog: AwsDataCatalog

# OWN SCHEMA (isolation): view_database/view_schema DEFAULT to this source's dataset name — its OWN
# dedicated serving schema — NEVER a shared/gold schema (e.g. `fpl`, `gaps`, `default`). Shared-schema
# incident (2026-08-13): a new source left view_database at the shared gold `fpl` and its
# CREATE OR REPLACE VIEW OVERWROTE gold's dim_country/dim_model. The materialize step (`--mode
# materialize`) REFUSES to CREATE into a known shared schema, so keep this the source's own schema.
view_database: '{dataset}'               # this source's OWN curated serving-view schema (the ontology binds here)
view_schema: '{dataset}'

glue_databases:
  fact: '<RAW_FACT_SCHEMA>'
  dims: '<RAW_DIMS_SCHEMA>'

credentials:
  mode: aws-chain                        # aws-chain | profile | secretsmanager | ssm
  ref: '<AWS_SSO_PROFILE or SECRET_REF>'

account: null                            # leave null — derived at runtime via STS
"""

_SCAFFOLD_HARVEST = """# harvest.yaml — per-source model-swap knobs for the build-time harvest (Phase 6).
# Precedence at runtime: CLI flag (--model/--effort/--thinking-budget) > this file > env
# (MAC_HARVEST_MODEL / MAC_EFFORT / MAC_THINKING_BUDGET) > built-in default.
#
# model : dispatched on prefix — eu./us./global.anthropic.* => Bedrock Converse;
#         openai.*/gpt-* => Mantle GPT. Validated at startup (fail loud on a bad id).
# effort: adaptive-thinking effort (low|medium|high|xhigh|max) OR GPT reasoning_effort.
# thinking_budget: OPTIONAL Converse token budget (pre-adaptive models); null = adaptive+effort.
model: {model}
effort: {effort}
thinking_budget: null
# region: eu-central-1                   # optional Bedrock region override
"""


# ── the GOVERNANCE plane ──────────────────────────────────────────────────────────────────────────
# One plane for every control mechanism, declared in the manifest alongside data/ and ontology/.
# fpl2 grew these across four homes (bundle root, ontology/, acceptance/, interventions/) and each
# was found late and by hand. A source born with them starts governed instead of retrofitted.

_SCAFFOLD_SME_LEDGER = """# SME LEDGER — the DOUBT CHANNEL. The single highest-value file in this plane.
#
# WHY IT EXISTS: a harvest that has nowhere to put an uncertainty writes it out as a confident fact.
# Measured on gaps/fpl2, which had no ledger: 17 of 22 concepts arrived stamped confidence C
# (CONFIRMED) with an owner who had never seen them, and one of those unreviewed claims produced a
# wrong value anchor that stood for weeks. An open question is a SUCCESSFUL outcome of authoring.
#
# status: OPEN | PARTIAL | RESOLVED | NEEDS_SME_CONFIRMATION
registry: sme_ledger
source: {label}
questions: []
"""

_SCAFFOLD_PHASE = """# Rule-governance phase switch — read by the rule-lock gate.
#
#   BUILD = ontology CRUD permitted; a missing lock is GREEN. The authoring phase.
#   TUNE  = default-DENY. Any un-blessed ontology delta REDS the gate; the agent PROPOSES, never edits.
#
# Only the OPERATOR flips this. A source sitting in BUILD is NOT governed — that is fine while
# authoring and not fine afterwards, so this file exists from day one to make the state readable.
phase: BUILD
lock: null
notes: >
  Flip to TUNE once the ontology is reviewed, and bless the lock in the same operator action.
"""

_SCAFFOLD_LEDGER = """# INTERVENTION LEDGER — the append-only record of MANUAL work.
#
# Autodiscovered output is self-documenting: the descriptor IS the record. Manual work is not, and an
# implicit object is not a protocol. Every object stamped `provenance: authored|tuned` needs an entry
# here saying WHAT changed, WHY, and HOW it was verified. Read by the change-record gate (MAC010).
#
# `sme_owner` on an entry is a QUESTION and is projected onto the SME page — write the ask, not just
# a role: "<role> — <what they must ratify>". An owner with no ask renders as UNSPECIFIED.
metadata:
  ledger: interventions
  source: {label}
interventions: []
"""

_SCAFFOLD_VANILLA = """# VANILLA DELTA REGISTER — every difference between the GENERATED bundle and what is on disk.
#
# SIBLING OF, NOT A COPY OF, the intervention ledger:
#   ledger.yaml        WHICH objects a human touched, and why.   Append-only HISTORY.
#   vanilla_delta.yaml WHAT currently differs from the generator. Current STATE.
# An intervention stays in the ledger forever; a delta disappears the moment the delta does.
#
# `baseline` is the load-bearing field: an entry that cannot say what the generator produces has not
# found its own baseline and is not finished. Object-level protocol is not locus-level protocol.
metadata:
  register: vanilla_delta
  source: {label}
deltas: []
"""

_SCAFFOLD_PROPERTIES = """# WAREHOUSE INVARIANTS — the L2 (execution-validated) evidence.
#
# Each property carries SQL that RUNS against the warehouse and asserts a fact the ontology's rules
# DEPEND on. This is NOT corpus testing (no questions, no answers) and no local check replaces it: a
# canon test exercises logic in memory, while these ask whether the DATA still satisfies the
# assumption. If a fact table grew a hidden roll-up row, every canon would still pass and every
# yearly figure would be silently inflated — only a property notices.
#
# severity: blocker | major | minor   (distinct from the DQ register's high|medium|low — the DQ scale
# grades a data FINDING; this grades an INVARIANT)
suite: {dataset}-properties
version: '1.0'
properties: []
"""


def scaffold_source(cr, *, data_domain=None, dataset=None, label=None) -> dict:
    """Stamp a NEW source skeleton at ``cr`` (a sources/<domain>/<dataset> dir): the plane dirs
    + a mac.project.yaml + connection.example.yaml + harvest.yaml. IDEMPOTENT — never overwrites
    an existing file (so re-running is safe / resume-friendly). domain/dataset/label default from
    the content-root path when not given."""
    cr = Path(cr)
    data_domain = data_domain or cr.parent.name
    dataset = dataset or cr.name
    label = label or dataset.upper()
    created, skipped = [], []
    for d in (
        "data/sources",
        "data/transforms",
        "data/datasets",
        "data/quality",
        "data/lookups",
        "ontology/concepts",
        "runtime",
        "references",
        ".context",
        # the GOVERNANCE plane — one home for the controls, declared in the manifest
        "governance",
        "governance/decisions",
        "knowledge",
    ):
        p = cr / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(d + "/")
    files = {
        "mac.project.yaml": _SCAFFOLD_PROJECT.format(
            domain=data_domain, dataset=dataset, label=label
        ),
        # OWN-schema default: view_database/view_schema = the dataset name (never a shared/gold schema).
        "connection.example.yaml": _SCAFFOLD_CONNECTION.format(dataset=dataset),
        "harvest.yaml": _SCAFFOLD_HARVEST.format(model=_MODEL, effort=_EFFORT),
        # THE GOVERNANCE PLANE. Every one of these was learned the hard way on gaps/fpl2 and added
        # late, by hand, after the defect it prevents had already been paid for. A source is born
        # with them so the first harvest lands into a governed bundle rather than a bare one.
        "governance/sme_ledger.yaml": _SCAFFOLD_SME_LEDGER.format(label=label),
        "governance/PHASE.yaml": _SCAFFOLD_PHASE,
        "governance/ledger.yaml": _SCAFFOLD_LEDGER.format(label=label),
        "governance/vanilla_delta.yaml": _SCAFFOLD_VANILLA.format(label=label),
        "governance/properties.yaml": _SCAFFOLD_PROPERTIES.format(dataset=dataset),
    }
    for name, text in files.items():
        p = cr / name
        if p.exists():
            skipped.append(name)
            continue
        p.write_text(text)
        created.append(name)
    return {
        "content_root": str(cr),
        "data_domain": data_domain,
        "dataset": dataset,
        "label": label,
        "created": created,
        "skipped": skipped,
    }


def _register_digest(cr: Path, cap: int = 400) -> str:
    """A COMPACT view of data/lookups/*.csv for the plan pass.

    WHY THE PLAN NEEDS THIS — measured live, 2026-08-18. Run without it, the plan proposed ONE measure
    concept for `v_fpl_kpi`; fpl2 models FOURTEEN concepts from that relation. The dataset descriptor
    shows a `kpi` column and a `value` column and says nothing about what `kpi` CONTAINS, so a model
    reading only descriptors cannot know the relation carries eight distinct business measures. It was
    not under-thinking; it was blind.

    The registers are where a discriminator column's real members live (`no probe by construction`:
    lookups are resolved up front, never guessed). Columns + distinct members of the FIRST column are
    enough to see that one relation serves many notions.
    """
    lk = cr / "data" / "lookups"
    if not lk.is_dir():
        return ""
    out = []
    for f in sorted(lk.glob("*.csv")):
        try:
            rows = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        if not rows:
            continue
        header = rows[0]
        keys = [r.split(",")[0] for r in rows[1:] if r.strip()]
        uniq = sorted(dict.fromkeys(keys))
        shown = ", ".join(uniq[:cap])
        more = f" … +{len(uniq) - cap} more" if len(uniq) > cap else ""
        out.append(
            f"- **{f.name}** ({len(uniq)} member(s))\n  columns: {header}\n  members: {shown}{more}"
        )
    return "\n".join(out)


def _concept_stem(name: str) -> str:
    """PascalCase notion name -> snake_case file stem. The file is named after the NOTION; naming it
    after a dataset was the third place 1:1 was enforced (prompt, loop, filename)."""
    raw = str(name).strip().replace(" ", "")
    # split at lower->UPPER and at the end of an ACRONYM RUN (OBReach -> OB|Reach), never inside one
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", raw).lower()
    words = [w for w in re.sub(r"[^a-z0-9_]+", "_", s).split("_") if w]
    # a one-letter word is the tail of an acronym the split broke (DtC -> dt|c) — glue it back
    out = []
    for w in words:
        if len(w) == 1 and out:
            out[-1] += w
        else:
            out.append(w)
    return "_".join(out) or "concept"


def harvest_concepts(
    cr: Path,
    databases,
    limit=0,
    *,
    model=_MODEL,
    effort=_EFFORT,
    thinking_budget=None,
    region=_REGION,
    cache=None,
    refresh=False,
    project_anyway=None,
):
    """Regenerate the ONTOLOGY plane from scratch: author one concept (+ inline typed rules) per
    produced dataset from the transformation layer, then LIFT the data layer's foreign_keys into
    physical ontology EDGES between those concepts. All authoring routes through the status-gated
    operations writer; edges are grammar-validated. Concepts need no Glue — only Bedrock is billed."""
    if _PROFILE:
        os.environ.setdefault("AWS_PROFILE", _PROFILE)
    if _REGION:
        os.environ.setdefault("AWS_REGION", _REGION)
    ident = source_ident.resolve(cr)  # de-FPL: source label from mac.project.yaml
    cache = cache if cache is not None else _make_cache(cr, refresh)
    data = cr / "data"
    ex = _EXEMPLAR.read_text() if _EXEMPLAR.exists() else ""
    ctx = cr / ".context"
    out_dir = cr / "ontology" / "concepts"
    out_dir.mkdir(parents=True, exist_ok=True)
    ds_paths = sorted((data / "datasets").glob("*.yaml"))[: limit or None]
    written = refused = 0
    concept_of: dict = {}  # bare relation/table -> authored concept name (for edge endpoints)
    ds_info = []
    inputs: dict = {}  # per-input sha256 for the reproducibility ledger
    # ── PASS 1: PLAN. One call over the WHOLE inventory decides what the NOTIONS are. ───────────
    # Concept:relation is M:N (operator ruling 2026-08-18). The old loop authored one concept per
    # dataset, which made it 1:1 by construction — gaps/fpl is exactly 20 concepts from 20 datasets.
    by_stem = {}
    for p in ds_paths:
        info = _dataset_input(p, data)
        inputs[f"data/datasets/{p.name}"] = _sha256_text(info["md"])
        by_stem[p.stem] = info
        ds_info.append(info)
    inventory = "\n\n---\n\n".join(
        f"### relation stem: {stem}\n\n{info['md']}" for stem, info in by_stem.items()
    )
    plan_ctx = authoring.grep_context(
        ctx if ctx.exists() else None,
        sorted({t for i in by_stem.values() for t in i["terms"]})[:40],
    )
    regs = _register_digest(cr)
    if regs:
        inventory += (
            "\n\n---\n\n## VALUE REGISTERS (data/lookups) — what the discriminator columns "
            "actually CONTAIN\n\nA relation whose discriminator has many members usually "
            "serves MANY notions, one per member family.\n\n" + regs
        )
    plan = authoring.plan_concepts(
        inventory,
        plan_ctx,
        model=model,
        effort=effort,
        region=region,
        thinking_budget=thinking_budget,
        cache=cache,
    )
    _w, plan_fail = authoring.check_plan(plan, list(by_stem))
    if plan_fail:
        # A plan that drops a relation silently is the failure this pass exists to stop. Refuse the
        # whole stage rather than author a partial ontology that LOOKS complete.
        for f in plan_fail:
            print(f"  plan: REFUSED — {f}")
        raise SystemExit(f"concept planning failed: {len(plan_fail)} problem(s); nothing authored")
    planned = plan.get("concepts") or []
    declined = plan.get("not_a_concept") or []
    print(
        f"  plan: {len(planned)} notion(s) over {len(by_stem)} relation(s); "
        f"{len(declined)} relation(s) back no concept"
    )
    for d in declined:
        print(f"    - {d.get('relation')}: {d.get('reason', '')[:90]}")

    # ── PASS 2: AUTHOR. Each notion gets EVERY relation it named. ────────────────────────────────
    for c in planned:
        name = c.get("name") or "Concept"
        rels = [r for r in (c.get("grounds_on") or []) if r in by_stem]
        md = "\n\n---\n\n".join(f"### relation stem: {r}\n\n{by_stem[r]['md']}" for r in rels)
        terms = sorted({t for r in rels for t in by_stem[r]["terms"]})
        res = authoring.process(
            name,
            md,
            ctx if ctx.exists() else None,
            terms,
            ex,
            model=model,
            effort=effort,
            region=region,
            thinking_budget=thinking_budget,
            cache=cache,
        )
        stem = _concept_stem(name)
        pw = operations.persist_concept(out_dir, stem, res)
        written += pw["written"]
        refused += not pw["written"]
        if pw["written"]:
            cn = ((res.get("obj") or {}).get("concept") or {}).get("name") or name
            for r in rels:  # M:N — every relation maps to this notion
                concept_of[by_stem[r]["relation_bare"]] = cn
                concept_of[r] = cn
        print(
            f"  {res.get('status', '?'):<12} {stem} <- [{', '.join(rels)}] -> "
            f"{'written' if pw['written'] else 'REFUSED: ' + str(pw.get('reason'))}"
            + (f" ({res.get('rules', 0)} rules)" if pw["written"] else "")
        )
    # EDGES: lift the data layer's foreign_keys into physical edges between the authored concepts.
    phys = edges.physical_edges(ds_info, concept_of)
    ef = edges.make_edges_file(phys, source=ident.label)  # de-FPL: label from the manifest
    pe = operations.persist_edges(cr / "ontology", ef)
    print(
        f"  edges: {ef['edges']} physical foreign_key -> "
        f"{'written' if pe['written'] else 'REFUSED: ' + str(pe.get('reason') or ef.get('errors'))}"
    )
    project_source(
        cr, project_anyway=project_anyway
    )  # gated; threads lineage (was bare mac_okf.build)
    write_harvest_manifest(
        cr,
        {
            "stage": "concepts",
            "source_label": ident.label,
            "model": model,
            "effort": effort,
            "thinking_budget": thinking_budget,
            "region": region,
            "databases": list(databases or []),
            "inputs": inputs,
            "cache": cache.stats,
        },
    )
    print(
        f"concepts: {written} written, {refused} refused; edges: {ef['edges']}; "
        f"cache {cache.stats}; projected read view."
    )


def harvest_data(
    cr: Path,
    databases,
    limit=0,
    *,
    model=_MODEL,
    effort=_EFFORT,
    thinking_budget=None,
    region=_REGION,
    cache=None,
    refresh=False,
    project_anyway=None,
):
    if _PROFILE:
        os.environ.setdefault("AWS_PROFILE", _PROFILE)
    if _REGION:
        os.environ.setdefault("AWS_REGION", _REGION)
    ident = source_ident.resolve(cr)  # de-FPL: source label + view schema from manifest
    cache = cache if cache is not None else _make_cache(cr, refresh)
    sess = _session()
    glue, athena = (
        sess.client("glue", region_name=_GLUE_REGION),
        sess.client("athena", region_name=_GLUE_REGION),
    )
    base = cr / "data"
    for sub in ("sources", "transforms", "datasets", "quality"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    ctx = cr / ".context"
    dq_all = []
    inputs: dict = {}  # per-table schema sha256 for the reproducibility ledger
    for db, tbl in _tables(glue, databases)[: limit or None]:
        tname = tbl.get("Name")
        cols = [
            {"name": c.get("Name"), "type": c.get("Type", "")}
            for c in (tbl.get("StorageDescriptor", {}) or {}).get("Columns", [])
        ]
        terms = [t for t in re.split(r"[_\s]+", tname) if len(t) > 2] + [c["name"] for c in cols]
        schema_md = _schema_md(db, tbl)
        inputs[f"{db}.{tname}"] = _sha256_text(schema_md)
        res = data_plane.process(
            db,
            tname,
            schema_md,
            cols,
            athena,
            ctx if ctx.exists() else None,
            terms,
            model=model,
            effort=effort,
            region=region,
            thinking_budget=thinking_budget,
            source_label=ident.label,
            view_schema=ident.view_schema,
            cache=cache,
        )
        operations.persist_descriptors(base, res["table"], res["files"], res["statuses"])
        dqf = res["files"].get("dq")
        if dqf:
            dq_all.extend(dqf["obj"])
        print(f"  {res['table']}: {res['statuses']}")
    if dq_all:
        operations.persist_register(
            base,
            {"metadata": {"register": "data_quality_register", "status": "open"}, "issues": dq_all},
        )
    project_source(
        cr, project_anyway=project_anyway
    )  # gated; threads lineage (was bare build_data(base))
    write_harvest_manifest(
        cr,
        {
            "stage": "data",
            "source_label": ident.label,
            "model": model,
            "effort": effort,
            "thinking_budget": thinking_budget,
            "region": region,
            "databases": list(databases or []),
            "inputs": inputs,
            "cache": cache.stats,
        },
    )
    print(f"data plane: {len(dq_all)} DQ issue(s); cache {cache.stats}; projected read view.")


def _stage_present(cr: Path, subdir: str) -> bool:
    """A billed stage is 'done' (resume-skippable) when its output dir already has YAML."""
    d = Path(cr) / subdir
    return d.exists() and any(d.glob("*.yaml"))


def onboard(
    cr: Path, databases, *, cfg: dict, accept=False, refresh=False, limit=0, project_anyway=None
) -> int:
    """Resume-aware, single-command onboarding of a source:
        scaffold (if missing) -> data -> reconcile -> project.  Concepts are NOT chained.

    DRY-RUN by DEFAULT (no --accept): prints the plan + resume decisions and runs ONLY the
    offline project stage — it makes NO AWS/Bedrock call. --accept PERSISTS: it executes the
    billed data/concepts stages (the existing functions, unchanged) for stages not already
    satisfied. RESUME = a stage whose outputs already exist is skipped. The model-swap knobs in
    ``cfg`` (already validated) + the shared cache (idempotency) flow into the billed stages."""
    cr = Path(cr)
    dry = not accept
    tag = "DRY-RUN (no AWS)" if dry else "ACCEPT (live)"
    print(
        f"onboard {cr.name} — {tag}; model={cfg['model']} effort={cfg['effort']} "
        f"thinking_budget={cfg['thinking_budget']} refresh={refresh}"
    )
    plan = []
    cache = _make_cache(cr, refresh)

    # 1) SCAFFOLD — stamp a skeleton for a brand-new domain/dataset if the manifest is missing.
    if not (cr / "mac.project.yaml").exists():
        plan.append("scaffold")
        if accept:
            sc = scaffold_source(cr)
            print(f"  scaffold: created {len(sc['created'])} path(s); label={sc['label']}")
        else:
            print(f"  scaffold: WOULD stamp a new skeleton at {cr} (mac.project.yaml missing)")
    else:
        print("  scaffold: present — skipping")

    # 2) DATA (billed) — resume if the clean datasets already exist.
    if _stage_present(cr, "data/datasets"):
        print("  data:     RESUME — data/datasets/*.yaml present, skipping (billed stage)")
    else:
        plan.append("data")
        if accept:
            if not databases:
                print("  data:     STOP — --databases required to author the data plane")
                return 2
            harvest_data(cr, databases, limit, cache=cache, project_anyway=project_anyway, **cfg)
        else:
            need = "" if databases else " (needs --databases)"
            print(f"  data:     WOULD author the data plane via Bedrock+Athena{need}")

    # 3) RECONCILE (offline, informational) — impurity findings -> resolution map.
    reg = cr / "data" / "quality" / "data_quality_register.yaml"
    resmap = cr / "data" / "quality" / "impurity_resolution_map.yaml"
    if reg.exists() and not resmap.exists():
        print(
            "  reconcile: register present but impurity_resolution_map.yaml missing — "
            "author the SME reconciliation next (offline, not billed)"
        )
    elif resmap.exists():
        print("  reconcile: resolution map present — skipping")
    else:
        print("  reconcile: no DQ register yet — nothing to reconcile")

    # 4) CONCEPTS — DELIBERATELY NOT RUN HERE. Onboarding stops at the data plane.
    #
    # It used to run automatically on a NEW source: the stage was skipped only when
    # ontology/concepts/ was ALREADY populated, so on the one occasion it mattered — a fresh bundle —
    # it fired. `--accept` is exactly what an operator passes to onboard a source, which made the most
    # convenient command the one that produced the failure mode: concepts authored from the table list
    # before a single business document had been read.
    #
    # The concept stage is not merely billed, it is a JUDGEMENT: which business notions this source
    # exposes, at what confidence, and which relations back no notion at all. Chaining it behind a
    # mechanical data harvest hides that decision inside a convenience flag. Run it explicitly:
    #
    #     python -m sdk.cli.harvest --content-root <root> --mode concepts
    #
    # (Removed 2026-08-18. gaps/fpl is exactly 20 concepts from 20 datasets — what the chained stage
    #  produces when nobody is looking.)
    if _stage_present(cr, "ontology/concepts"):
        print("  concepts: present — untouched (onboarding never authors concepts)")
    else:
        print(
            "  concepts: NOT RUN — onboarding stops at the data plane. Author the ontology, then:"
        )
        print("            python -m sdk.cli.harvest --content-root <root> --mode concepts")

    # 5) PROJECT (offline, deterministic) — ALWAYS, in both dry-run and accept. GATED: a bundle that
    #    does not compile stops here, in dry-run too, so onboarding cannot mint a read view over one.
    project_source(cr, project_anyway=project_anyway)

    # Reproducibility SIDECAR (not served/hashed/published).
    write_harvest_manifest(
        cr,
        {
            "stage": "onboard",
            "dry_run": dry,
            "planned_stages": plan,
            "model": cfg["model"],
            "effort": cfg["effort"],
            "thinking_budget": cfg["thinking_budget"],
            "region": cfg["region"],
            "databases": list(databases or []),
            "cache": cache.stats,
        },
    )
    verb = "planned" if dry else "executed"
    print(
        f"onboard {verb}: stages={plan or ['(all present — resumed)']}; "
        f"cache {cache.stats}; projected read view. "
        + ("run again with --accept to author the billed stages." if dry else "done.")
    )
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Build-time MAC harvest — author the data/ontology planes and project the "
        "served read view. onboard = one-command, resume-aware, model-swappable, "
        "cache-idempotent onboarding of a NEW dataset."
    )
    ap.add_argument("--content-root", required=True, help="a sources/<domain>/<dataset> dir")
    ap.add_argument("--databases", nargs="*", default=[], help="Glue database name(s)")
    ap.add_argument(
        "--mode",
        choices=["data", "materialize", "lookups", "concepts", "project", "onboard"],
        default="data",
        help="data/concepts author via AWS+Bedrock; materialize/lookups create the "
        "own-schema views + name->code registers (DRY-RUN by default, --accept to run "
        "the DDL/profiling live); project = OFFLINE re-projection only (no AWS); "
        "onboard = resume-aware scaffold->data->reconcile->concepts->project "
        "(DRY-RUN by default, --accept to persist the billed stages)",
    )
    ap.add_argument("--limit", type=int, default=0, help="cap tables (0 = all) — use 1 for a smoke")
    # Phase 6 — model swap + idempotency + onboarding
    ap.add_argument(
        "--scaffold",
        action="store_true",
        help="stamp a NEW source skeleton (dirs + mac.project.yaml + connection.example.yaml "
        "+ harvest.yaml) at --content-root, then exit (idempotent; never overwrites)",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="override the harvest model id (dispatched on prefix: "
        "eu./us./global.anthropic.* => Bedrock Converse; openai.*/gpt-* => Mantle GPT)",
    )
    ap.add_argument(
        "--effort", default=None, help="override the reasoning effort (low|medium|high|xhigh|max)"
    )
    ap.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        dest="thinking_budget",
        help="override the Converse thinking token budget (pre-adaptive models); "
        "omitted = adaptive thinking at --effort",
    )
    ap.add_argument(
        "--accept",
        action="store_true",
        help="onboard: PERSIST — actually run the billed data/concepts stages "
        "(default is a dry run that makes no AWS call)",
    )
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="bypass the .harvest_cache/ response cache (force a fresh LLM decode)",
    )
    ap.add_argument(
        _OVERRIDE_FLAG,
        metavar="REASON",
        default=None,
        dest="project_anyway",
        help="OVERRIDE the conformance refusal and project a bundle that DOES NOT COMPILE. "
        "The value IS the reason and is mandatory — the flag cannot be used without "
        "saying why. It prints a banner and is recorded, with your username and a "
        "timestamp, in <content-root>/compile.json#gate.override, next to the findings "
        "it overrode. Use it when you know the bundle is non-conformant and need the "
        "read view anyway; every artifact the run produces is then derived from a "
        "non-conformant bundle.",
    )
    a = ap.parse_args()
    cr = Path(a.content_root).resolve()
    if a.project_anyway is not None and not a.project_anyway.strip():
        print(
            f"harvest: {_OVERRIDE_FLAG} requires a REASON — it is recorded and read later. "
            f'Pass {_OVERRIDE_FLAG} "<why>".'
        )
        return 2

    try:
        return _dispatch(a, cr)
    except CompileRefused as e:
        # The compiler's own words, verbatim. Exit 2 = the run was REFUSED and nothing was written,
        # deliberately distinct from a projection that ran and failed.
        print(f"harvest: {e}")
        return 2


def _dispatch(a, cr: Path) -> int:
    # --scaffold is a standalone action (no model / no AWS).
    if a.scaffold:
        sc = scaffold_source(cr)
        print(f"scaffolded {sc['data_domain']}/{sc['dataset']} (label={sc['label']}) at {cr}")
        print(f"  created: {', '.join(sc['created']) or '(none — all present)'}")
        if sc["skipped"]:
            print(f"  kept (already present): {', '.join(sc['skipped'])}")
        return 0

    # project is OFFLINE and model-agnostic — no config resolution / no startup validation needed.
    if a.mode == "project":
        project_source(cr, project_anyway=a.project_anyway)  # gated, offline, lineage-threaded
        return 0

    # materialize / lookups are model-agnostic (connection.yaml, not Bedrock). DRY-RUN by default;
    # --accept runs the DDL/profiling live. The own-schema guardrail refuses a shared/empty schema.
    if a.mode in ("materialize", "lookups"):
        try:
            if a.mode == "materialize":
                return materialize.run_materialize(cr, execute=a.accept)
            return materialize.run_lookups(cr, execute=a.accept)
        except materialize.MaterializeRefused as e:
            print(f"harvest: {e}")  # own-schema guardrail — nothing was executed
            return 2

    # data/concepts/onboard resolve + VALIDATE the model-swap config at STARTUP (before any AWS).
    try:
        cfg = _resolve_harvest_config(
            cr, cli_model=a.model, cli_effort=a.effort, cli_thinking_budget=a.thinking_budget
        )
    except ValueError as e:
        print(f"harvest: {e}")  # fail loud, cleanly, for $0 — before any Athena/Bedrock call
        return 2
    if a.mode == "onboard":
        return onboard(
            cr,
            a.databases,
            cfg=cfg,
            accept=a.accept,
            refresh=a.refresh,
            limit=a.limit,
            project_anyway=a.project_anyway,
        )
    if a.mode == "data" and not a.databases:
        print("--databases is required for --mode data (one or more Glue database names)")
        return 2
    fn = harvest_data if a.mode == "data" else harvest_concepts
    fn(cr, a.databases, a.limit, refresh=a.refresh, project_anyway=a.project_anyway, **cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
