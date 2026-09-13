#!/usr/bin/env python3
"""references.py — deterministically project the answering GUARDRAILS surface the wiki /ask mandates.

The wiki assistant (wiki/local_ask.py) is guardrails-first: it MUST read `references/usage_guardrails.md`
before any other page, then `references/known_issues/`. For this source those live nowhere authored —
the routing / how-to-answer / filter-traps knowledge is INSIDE the ontology (each concept's
`contract.no_probe_guarantee` + `contract.rules[]`) and the DQ register. This projector aggregates that,
verbatim, into the pages /ask expects. Pure function of the SSOT — no timestamps, stable order — so it
never churns the publish tree hash.

Emits under <content_root>/references/:
  usage_guardrails.md          routing table + per-concept how-to-answer (no_probe_guarantee) + rules
  known_issues/index.md        the DQ register at a glance (severity + resolution coverage)
  known_issues/<finding>.md    one page per recorded impurity (finding + handling + residual risk)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml


def _load(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


def _rel(con: dict) -> str:
    srcs = (con.get("grounding") or {}).get("sources") or []
    return str(srcs[0].get("relation")) if srcs and isinstance(srcs[0], dict) else ""


def _fm(title: str) -> list:
    return ["---", "type: Reference", f"title: {title}", "tags: [reference, guardrail]", "---", ""]


def build(content_root) -> dict:
    cr = Path(content_root)
    cdir = cr / "ontology" / "concepts"
    ref = cr / "references"
    # references/ is 100% derived — clear + recreate so a removed concept/finding leaves no orphan.
    shutil.rmtree(ref, ignore_errors=True)
    (ref / "known_issues").mkdir(parents=True)

    concepts = []
    for p in sorted(cdir.glob("*.yaml")):
        obj = _load(p)
        con = obj.get("concept") or {}
        contract = obj.get("contract") or {}
        concepts.append(
            {
                "stem": p.stem,
                "name": con.get("name") or p.stem,
                "label": con.get("label") or con.get("name") or p.stem,
                "cls": con.get("class") or "",
                "relation": _rel(obj),
                "npg": contract.get("no_probe_guarantee"),
                "rules": contract.get("rules") or [],
            }
        )

    # ---- usage_guardrails.md -------------------------------------------------------------------
    # the source LABEL comes from mac.project.yaml — never a hardcoded source name
    from sdk.project import source_ident

    _label = source_ident.resolve(Path(content_root)).label
    g = _fm(f"Usage guardrails — how to answer {_label} safely")
    g += [
        "# Usage guardrails (read first)",
        "",
        "This page is projected from the ontology — every routing decision, default, and prohibition below",
        "is authored on a concept, not invented here. **Only interpretation is probabilistic; generate SQL",
        "from the question + this ontology ALONE, never from a live probe.** A fact the ontology does not",
        "state is a GAP to flag, not a value to guess.",
        "",
        "## Routing — which serving relation answers what",
        "",
        "| concept | class | relation | answer with |",
        "|---|---|---|---|",
    ]
    for c in concepts:
        one = (c["npg"] or "").strip().splitlines()[0] if c["npg"] else (c["label"])
        one = one.replace("|", "\\|")[:90]
        g.append(
            f"| [{c['label']}](../ontology/concepts/{c['stem']}.md) | {c['cls']} | "
            f"`{c['relation']}` | {one} |"
        )
    g += ["", "## How to answer — per-concept playbooks (verbatim `no_probe_guarantee`)", ""]
    for c in concepts:
        if not c["npg"] and not c["rules"]:
            continue
        g += [f"### {c['label']} — `{c['relation']}`", ""]
        if c["npg"]:
            g += ["```text", str(c["npg"]).rstrip("\n"), "```", ""]
        for r in c["rules"]:
            clauses = " · ".join(
                f"**{k}** {str(r[k]).strip()}" for k in ("when", "then", "never") if r.get(k)
            )
            if clauses:
                g.append(f"- `{r.get('id', '')}` — {clauses}")
        g.append("")

    # ---- known_issues from the DQ register -----------------------------------------------------
    q = cr / "data" / "quality"
    reg = _load(q / "data_quality_register.yaml")
    issues = sorted(
        (reg.get("issues") or reg.get("findings") or []),
        key=lambda i: str(i.get("id") or i.get("finding_id") or ""),
    )
    resmap = {
        r.get("finding_id"): r
        for r in (_load(q / "impurity_resolution_map.yaml").get("resolutions") or [])
    }

    g += [
        "## Filter traps & known issues",
        "",
        "Recorded data-quality findings that change how you must query. Full detail in "
        "`references/known_issues/`.",
        "",
    ]
    for i in issues:
        fid = i.get("id") or i.get("finding_id")
        cov = (resmap.get(fid) or {}).get("coverage") or "not yet reconciled"
        g.append(
            f"- [{fid}](known_issues/{fid}.md) — _{i.get('severity', '?')}_ · "
            f"{str(i.get('title', '')).replace('|', '\\|')} · **{cov}**"
        )
    (ref / "usage_guardrails.md").write_text("\n".join(g) + "\n")

    # ---- known_issues/ pages -------------------------------------------------------------------
    idx = [
        *_fm("Known issues — recorded data-quality findings"),
        "# Known issues",
        "",
        f"{len(issues)} recorded impurities (see also the Data Quality dashboard). Coverage is the "
        "resolving-transform status; *not yet reconciled* = a newer finding not yet mapped.",
        "",
        "| finding | severity | coverage |",
        "|---|---|---|",
    ]
    for i in issues:
        fid = i.get("id") or i.get("finding_id")
        res = resmap.get(fid) or {}
        cov = res.get("coverage") or "not yet reconciled"
        idx.append(f"| [{fid}]({fid}.md) | {i.get('severity', '?')} | {cov} |")
        page = [
            *_fm(f"{fid} — {i.get('title', '')}"),
            f"# {fid}",
            "",
            f"*{i.get('severity', '?')} · confidence {i.get('confidence', '?')}*",
            "",
            f"**Finding.** {i.get('finding', '')}",
            "",
            f"**Current handling.** {i.get('current_handling', '—')}",
            "",
            f"**Residual risk.** {i.get('residual_risk', '—')}",
            "",
        ]
        if res:
            page += [
                f"**Resolution.** {res.get('coverage', '?')} — {res.get('guarantee', '')} "
                f"(transforms: {', '.join(res.get('resolving_transforms') or []) or '—'})",
                "",
            ]
        else:
            page += [
                "**Resolution.** Not yet reconciled (newly harvested) — an honest open item.",
                "",
            ]
        (ref / "known_issues" / f"{fid}.md").write_text("\n".join(page) + "\n")
    (ref / "known_issues" / "index.md").write_text("\n".join(idx) + "\n")

    return {"concepts": len(concepts), "known_issues": len(issues)}


if __name__ == "__main__":
    import sys

    print(build(sys.argv[1] if len(sys.argv) > 1 else "."))
