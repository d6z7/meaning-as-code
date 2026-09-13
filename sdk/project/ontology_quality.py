#!/usr/bin/env python3
"""sdk.project.ontology_quality — the ONTOLOGY-QUALITY projection: the model's own quality /
completeness dashboard, the twin of the data-quality dashboard. DETERMINISTIC + IDEMPOTENT (no LLM,
no AWS) — derived purely from the authored concepts + edges + the data grounding.

It measures three things the data-quality dashboard cannot:
  - MATURITY      — how much is SME-CONFIRMED (confidence C) vs machine-inferred (I) / needs-SME (Q),
                    and confirmed (C) vs proposed (P) for rules. The direct analog of DQ's resolved/gap.
  - CONNECTIVITY  — how many concepts are related to another concept, whether by an ontology EDGE or
                    by a contract RULE that binds another concept's canonical key. Refuse-stubs
                    (identity.kind = sme_pending, no key) are excluded: they are authored to be
                    unlinked, so counting them as a shortfall argues for asserting a false relationship.
  - DOCUMENTATION / COVERAGE — column descriptions, rule-kind coverage, edge depth.
  - EXECUTION VALIDATION — FRAMEWORK.md §8's THIRD rung. MATURITY above measures the fourth
                    (SME-confirmed vs inferred); nothing measured the third. A concept can be authored,
                    structurally valid, and never once checked against the warehouse — and the dashboard
                    reported it at 95 % confirmed. Read from acceptance/*.yaml `validates`, the field
                    that attributes L2 evidence to the concepts it holds to account.
  - ANSWERABILITY — whether each concept's answer path DERIVES from its declarations, or is only
                    sworn to in a hand-written no_probe_guarantee. Read from the compiler's own
                    check_answerability (compile.json), never recomputed here: the logic has ONE home
                    in meaning-as-code/tools, and a dashboard that re-derived it would be a second.
And it emits an SME-QUESTION backlog: exactly what a human still needs to confirm or answer.
"""

from __future__ import annotations

RULE_KINDS = ["resolution", "aggregation", "default", "ambiguity", "exclusion", "guarantee"]
_SEV = {"high": 0, "medium": 1, "low": 2}

import re as _re
from pathlib import Path


def build(concepts: dict, datasets: dict, ont_edges: list, root=None) -> dict:
    title_of, name_of = {}, {}
    for stem, c in concepts.items():
        con = c.get("concept") or {}
        title_of[stem] = con.get("label") or con.get("name") or stem
        name_of[stem] = con.get("name") or stem

    touched, edge_levels = set(), {}
    for e in ont_edges or []:
        ep = e.get("endpoints") or {}
        touched.add((ep.get("from") or {}).get("concept"))
        touched.add((ep.get("to") or {}).get("concept"))
        edge_levels[e.get("level", "?")] = edge_levels.get(e.get("level", "?"), 0) + 1

    # ── CONNECTED BY RULE ────────────────────────────────────────────────────────────────────────
    # An edge asserts THAT two concepts relate. A contract rule that binds another concept's canonical
    # key asserts WHAT GOES WRONG if you ignore the relationship — a stronger statement, and the one an
    # answering engine actually executes. Counting only edges made this metric report a concept as
    # "isolated" while eight measures were pinning it by rule, and the only way to satisfy it was to
    # restate in edges what the rules already said (2026-08-16, acme2 `perspective`). So relationships
    # expressed as rules count too, in both directions: the rule connects its subject AND its object.
    key_owner: dict[str, set[str]] = {}
    for stem, c in concepts.items():
        ck = ((c.get("concept") or {}).get("identity") or {}).get("canonical_key")
        if ck:
            key_owner.setdefault(ck, set()).add((c.get("concept") or {}).get("name") or stem)

    bound, rule_links = set(), []
    for stem, c in concepts.items():
        me = (c.get("concept") or {}).get("name") or stem
        for r in (c.get("contract") or {}).get("rules") or []:
            for col in r.get("binds") or []:
                others = key_owner.get(col, set()) - {me}
                if not others:
                    continue  # binds its own key — not a relationship
                bound.add(me)
                bound |= others
                rule_links.append(
                    {"from": me, "to": sorted(others), "via": r.get("id"), "binds": col}
                )

    findings, sme, refuse_stubs = [], [], []
    conf_c = {"C": 0, "I": 0, "Q": 0}
    rule_c = {"C": 0, "P": 0, "R": 0}
    kinds_present = set()
    by_edge = by_rule = 0

    for stem, c in concepts.items():
        con = c.get("concept") or {}
        meta = c.get("metadata") or {}
        title, nm, klass = title_of[stem], name_of[stem], con.get("class")
        # A REFUSE-STUB is a concept authored precisely so the engine can say "this source has no
        # information about X" instead of inventing one: identity.kind = sme_pending, no canonical key.
        # It is SUPPOSED to be unlinked and unconfirmed, so neither is a defect — reporting them as
        # findings argues for wiring a relationship that does not exist. The open question is still
        # real, so it stays in the SME backlog below; only the FINDINGS are suppressed.
        is_refuse_stub = (con.get("identity") or {}).get("kind") == "sme_pending" and not (
            con.get("identity") or {}
        ).get("canonical_key")
        if is_refuse_stub:
            refuse_stubs.append(stem)
        mc = meta.get("confidence", "?")
        if mc in conf_c:
            conf_c[mc] += 1
        if mc in ("I", "Q") and not is_refuse_stub:
            findings.append(
                {
                    "id": f"maturity.{stem}",
                    "category": "maturity",
                    "severity": "medium" if mc == "Q" else "low",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"{title} is {'needs-SME' if mc == 'Q' else 'inferred'}, not confirmed",
                    "detail": f"metadata.confidence = {mc} — machine-authored, awaiting SME confirmation.",
                }
            )
            sme.append(
                {
                    "id": f"confirm.{stem}",
                    "concept": stem,
                    "concept_title": title,
                    "kind": "confirm-concept",
                    "current": mc,
                    "question": f"Is the concept “{title}” ({klass}) defined correctly? "
                    f"(currently {mc} = {'needs SME' if mc == 'Q' else 'inferred'})",
                }
            )

        if nm in touched:
            by_edge += 1
        elif nm in bound:
            by_rule += 1
        elif not is_refuse_stub:
            findings.append(
                {
                    "id": f"isolated.{stem}",
                    "category": "connectivity",
                    "severity": "medium",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"{title} has no relationships",
                    "detail": "Neither an ontology edge nor a contract rule relates it to another "
                    "concept — it stands alone in the model.",
                }
            )

        rules = (c.get("contract") or {}).get("rules") or []
        for r in rules:
            rc = r.get("confidence", "?")
            if rc in rule_c:
                rule_c[rc] += 1
            kinds_present.add(str(r.get("kind", "")).split(".")[-1])
            if rc == "P":
                subj = r.get("subject") or r.get("id")
                findings.append(
                    {
                        "id": f"proposed.{r.get('id')}",
                        "category": "maturity",
                        "severity": "low",
                        "concept": stem,
                        "concept_title": title,
                        "title": f"Proposed rule on {title}: {subj}",
                        "detail": f"Rule {r.get('id')} is confidence P (proposed) — not SME-confirmed.",
                    }
                )
                sme.append(
                    {
                        "id": f"rule.{r.get('id')}",
                        "concept": stem,
                        "concept_title": title,
                        "kind": "confirm-rule",
                        "current": "P",
                        "question": f"Is this rule on “{title}” correct? — {subj}",
                    }
                )

        if klass == "measure" and not any(
            str(r.get("kind", "")).split(".")[-1] == "aggregation" for r in rules
        ):
            findings.append(
                {
                    "id": f"noagg.{stem}",
                    "category": "rule-coverage",
                    "severity": "medium",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"Measure {title} has no aggregation rule",
                    "detail": "How it rolls up across its axes is unspecified.",
                }
            )
            sme.append(
                {
                    "id": f"agg.{stem}",
                    "concept": stem,
                    "concept_title": title,
                    "kind": "aggregation",
                    "current": "—",
                    "question": f"How does the measure “{title}” aggregate across its axes "
                    "(sum / average / non-additive)?",
                }
            )

        if klass == "enumeration":
            v = c.get("values") or {}
            if v.get("closure") == "unknown" or not v.get("items"):
                findings.append(
                    {
                        "id": f"enum.{stem}",
                        "category": "completeness",
                        "severity": "medium",
                        "concept": stem,
                        "concept_title": title,
                        "title": f"{title} value set is not fully enumerated",
                        "detail": f"closure = {v.get('closure')} — the full valid-value set is not captured.",
                    }
                )
                sme.append(
                    {
                        "id": f"enum.{stem}",
                        "concept": stem,
                        "concept_title": title,
                        "kind": "enumeration",
                        "current": v.get("closure"),
                        "question": f"Is “{title}” a CLOSED set? If so, what are all its valid values?",
                    }
                )

        if (con.get("identity") or {}).get("kind") == "sme_pending":
            sme.append(
                {
                    "id": f"identity.{stem}",
                    "concept": stem,
                    "concept_title": title,
                    "kind": "identity",
                    "current": "sme_pending",
                    "question": f"What is the canonical identity / key of “{title}”?",
                }
            )

    # ---- RATIFICATIONS AWAITING A HUMAN, lifted from the intervention ledger. -------------------
    # MEASURED on acme2 2026-08-18: 25 of 25 ledger entries carry an `sme_owner` naming a person and
    # what they must ratify, and NOT ONE surfaced anywhere. SME questions were generated from exactly
    # two conditions (unknown enum closure, identity.kind = sme_pending), so every judgement call made
    # while tuning the bundle sat in a file nobody reads as a question.
    #
    # THE PROTOCOL THIS SERVES (operator, 2026-08-18): a contested reading is never left broken and
    # never silently guessed. A consistent view is ADOPTED, the reason is RECORDED, and the question
    # is RAISED — so if an answer later proves wrong, the evidence for what was configured and why is
    # already there, next to the open question.
    try:
        import yaml as _yaml

        _led = (Path(root) / "interventions" / "ledger.yaml") if root else None
        if _led and _led.exists():
            for e in (_yaml.safe_load(_led.read_text(encoding="utf-8")) or {}).get(
                "interventions"
            ) or []:
                owner = str(e.get("sme_owner") or "").strip()
                if not owner or str(e.get("status", "")).lower() in ("ratified", "closed"):
                    continue
                who, _, ask = owner.partition("—")
                sme.append(
                    {
                        "id": f"ledger.{e.get('id')}",
                        "concept": None,
                        "concept_title": e.get("id"),
                        "kind": "ratification",
                        "current": str(e.get("status") or "applied"),
                        "owner": who.strip() or "domain-owner",
                        # MEASURED: 4 of 25 acme2 entries name an owner with no "— <what to ratify>".
                        # An owner without an ask is a half-recorded question; rendering the owner
                        # AS the question would make it look answered when nobody knows what was asked.
                        "question": (
                            ask.strip()
                            or f"UNSPECIFIED — the ledger names {who.strip() or 'an owner'} but "
                            f"does not say what they must ratify; the entry's `why` is the "
                            f"only record of what was decided"
                        ),
                        "why": str(e.get("why") or "").strip()[:400],
                    }
                )
    except Exception:
        pass  # a ledger we cannot read must not break the projection

    cols_total = sum(len(d.get("columns") or []) for d in datasets.values())
    cols_desc = sum(
        1 for d in datasets.values() for col in (d.get("columns") or []) if col.get("description")
    )

    kinds_absent = [k for k in RULE_KINDS if k not in kinds_present]
    if kinds_absent:
        findings.append(
            {
                "id": "rulekinds.absent",
                "category": "rule-coverage",
                "severity": "low",
                "concept": None,
                "concept_title": None,
                "title": f"Rule kinds never used: {', '.join(kinds_absent)}",
                "detail": "These contract-rule kinds appear on no concept — an ontology-wide coverage gap.",
            }
        )
    if edge_levels and not any(lvl in edge_levels for lvl in ("business", "federation")):
        findings.append(
            {
                "id": "edges.physicalonly",
                "category": "relationship-depth",
                "severity": "low",
                "concept": None,
                "concept_title": None,
                "title": "All edges are physical (no business / federation)",
                "detail": "Only foreign-key relationships are modelled; semantic (identity / "
                "shared_attribute) and cross-source (federation) edges are absent.",
            }
        )

    # ── ANSWERABILITY, read from the compiler rather than recomputed ──────────────────────────────
    # mac.schema.json on no_probe_guarantee: "if more is needed, the concept is INCOMPLETE (fix it,
    # don't probe)". That is a completeness test, and until 2026-08-19 every bundle answered it by
    # hand — one prose block per concept, each reciting steps its own declarations already hold, each
    # drifting silently whenever a declaration moved. The compiler now DERIVES the path and reports
    # the steps it cannot; this surfaces that verdict beside the other dimensions.
    answerable = {"derives": 0, "total": 0, "gaps": [], "exempt": [], "measured": False}
    try:
        import json as _json

        cj = Path(root or ".") / "compile.json"
        if cj.exists():
            diags = (_json.loads(cj.read_text(encoding="utf-8")) or {}).get("diagnostics") or []
            ans = [d for d in diags if d.get("source") == "check_answerability"]
            answerable["measured"] = True
            for d in ans:
                for w in d.get("witnesses") or []:
                    answerable["gaps"].append(
                        {
                            "concept": (w.get("detail") or "").split(":")[0],
                            "step": (w.get("path") or "").split(".")[-1],
                            "detail": w.get("detail"),
                        }
                    )
                m = _re.search(r"refuse-stubs: ([^.]+)", d.get("note") or "")
                if m:
                    answerable["exempt"] = [s.strip() for s in m.group(1).split(",")]
            short = {g["concept"] for g in answerable["gaps"]}
            answerable["total"] = len(concepts) - len(answerable["exempt"])
            answerable["derives"] = answerable["total"] - len(short)
            for g in answerable["gaps"]:
                findings.append(
                    {
                        "id": f"answerpath.{g['concept']}.{g['step']}",
                        "category": "answerability",
                        "severity": "high",
                        "concept": g["concept"],
                        "concept_title": g["concept"],
                        "title": f"{g['concept']}: the `{g['step']}` step of the answer path is not declared",
                        "detail": "An agent cannot reach this step without probing, and no declaration "
                        "supplies it. A no_probe_guarantee asserting otherwise is a promise "
                        "nothing keeps — supply the declaration instead.",
                    }
                )
    except Exception:
        pass

    # ── EXECUTION VALIDATION — which concepts a warehouse property actually holds to account ──────
    # mac.schema.json calls PropertiesFile "the L2 (execution-validated) evidence", and FRAMEWORK.md §8
    # makes execution validation the third rung of the trust gradient. Until 2026-08-19 a property
    # carried no link to a concept, so the evidence existed and could not be attributed: the suite
    # proved the warehouse satisfied an assumption while nothing recorded WHICH part of the model was
    # thereby validated. `validates` is that link; this counts it.
    execval = {
        "covered": 0,
        "total": len(concepts),
        "uncovered": [],
        "properties": 0,
        "measured": False,
        "run": None,
    }
    try:
        import yaml as _yaml

        acc = Path(root or ".") / "acceptance"
        claimed: set = set()
        nprop = 0
        for f in sorted(acc.glob("*.yaml")) if acc.is_dir() else []:
            doc = _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for pr in (doc.get("properties") or []) if isinstance(doc, dict) else []:
                nprop += 1
                for c in pr.get("validates") or []:
                    claimed.add(str(c))
        if nprop:
            execval["measured"] = True
            execval["properties"] = nprop
            execval["covered"] = len(claimed & set(concepts))
            execval["uncovered"] = sorted(set(concepts) - claimed)
            for c in execval["uncovered"]:
                findings.append(
                    {
                        "id": f"execval.{c}",
                        "category": "execution-validation",
                        "severity": "medium",
                        "concept": c,
                        "concept_title": c,
                        "title": f"{c} has never been checked against the warehouse",
                        "detail": "No property in acceptance/ names this concept in `validates`. It may be "
                        "authored and structurally valid and still wrong about the data — "
                        "FRAMEWORK.md §8: structure is not correctness.",
                    }
                )
        # ── THE RUN, not just the suite. A property that exists and has never been executed is a
        # claim, and until this read the only place a result lived was a JSON file nobody opens and a
        # terminal nobody keeps. Written by tools/run_properties.py --json.
        runs = Path(root or ".") / "acceptance" / "property_runs.json"
        if runs.exists():
            import json as _j

            rr = (_j.loads(runs.read_text(encoding="utf-8")) or {}).get("results") or []
            tally = {"pass": 0, "fail": 0, "accepted": 0}
            for r in rr:
                st = str(r.get("status") or "").upper()
                tally["pass" if st == "PASS" else "accepted" if st == "ACCEPTED" else "fail"] += 1
            execval["run"] = dict(tally, total=len(rr))
            for r in rr:
                if str(r.get("status") or "").upper() != "FAIL":
                    continue
                findings.append(
                    {
                        "id": f"propfail.{r.get('id')}",
                        "category": "property-failure",
                        # a blocker property that FAILS is the strongest signal this dashboard carries:
                        # the warehouse contradicts an assumption the ontology's rules are written on.
                        "severity": "high" if r.get("severity") == "blocker" else "medium",
                        "concept": None,
                        "concept_title": r.get("family"),
                        "title": f"{r.get('id')} FAILED — {r.get('family')}",
                        "detail": " ".join(str(r.get("statement") or "").split())[:400],
                    }
                )
    except Exception:
        pass

    nconc = len(concepts)
    total_r = sum(rule_c.values())
    findings.sort(
        key=lambda f: (_SEV.get(f.get("severity"), 3), f.get("category"), f.get("concept") or "")
    )
    return {
        "score": {
            "maturity": {
                "concepts": conf_c,
                "rules": rule_c,
                "concept_confirmed_pct": round(100 * conf_c["C"] / max(1, nconc)),
                "rule_confirmed_pct": round(100 * rule_c["C"] / max(1, total_r)),
            },
            # `total` excludes refuse-stubs: a concept authored to be unlinked cannot be a shortfall.
            "connectivity": {
                "linked": by_edge + by_rule,
                "by_edge": by_edge,
                "by_rule": by_rule,
                "total": nconc - len(refuse_stubs),
                "refuse_stubs": sorted(refuse_stubs),
                "pct": round(100 * (by_edge + by_rule) / max(1, nconc - len(refuse_stubs))),
                "edges": edge_levels,
                "rule_links": len(rule_links),
            },
            "documentation": {
                "cols_described": cols_desc,
                "cols_total": cols_total,
                "pct": round(100 * cols_desc / max(1, cols_total)),
            },
            "rule_kinds": {
                "present": sorted(kinds_present),
                "absent": kinds_absent,
                "total": len(RULE_KINDS),
            },
            # UNMEASURED is not CLEAN: with no compile.json the dashboard says it does not know,
            # rather than reporting 100 % and inventing an assurance nobody computed.
            "execution_validation": (
                dict(execval, pct=round(100 * execval["covered"] / max(1, execval["total"])))
                if execval["measured"]
                else {"measured": False}
            ),
            "answerability": (
                dict(
                    answerable, pct=round(100 * answerable["derives"] / max(1, answerable["total"]))
                )
                if answerable["measured"]
                else {"measured": False}
            ),
        },
        "counts": {
            "concepts": nconc,
            "rules": total_r,
            "findings": len(findings),
            "sme_questions": len(sme),
        },
        "findings": findings,
        "sme_questions": sme,
        "rule_links": rule_links,
    }
