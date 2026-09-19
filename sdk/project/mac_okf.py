#!/usr/bin/env python3
"""MAC-in-OKF spike — depict a MAC ontology object as an OKF-compliant markdown page.

Readability-first layout (v2):
  * FRONTMATTER carries ONLY the small OKF surface (`type`, `title`, `description`,
    `tags`, `resource`, + a light `rule_pages` pointer) — a handful of lines that a
    generic OKF catalog reads and that renders as a clean header, not a wall.
  * The BODY is the readable doc (definition, grain, fields, a kind-grouped RULES
    INDEX, relationships) and ends with a delimited **`## Model` code fence** holding
    the FULL typed MAC object — the thing `mac.schema.json` validates and `rules.lock`
    hashes. A fence renders as a scrollable code block, never as an unreadable table.
  * RULES are single-homed on their own `type: Rule` pages; the concept's model fence
    excludes `contract.rules` and lists the rule pages instead. The bundle round-trips
    losslessly (concept model fence + referenced rule pages == the source object).

THE PAGE'S CONTENT IS NOT HERE, AND THE NAME IS THE REASON. This module is the projector of a
MAC object into OKF — `frontmatter`, `split_frontmatter`, `lock_hash` and the surface dict are
what that means, and it "cannot be used for other purposes". What a concept page SAYS — the nine
section builders, the whole-bundle context and the body — is `sdk/project/concept_page_content.py`,
which knows nothing about OKF and is read by this module and by the live page seam alike. The
dependency runs one way, and every page renders byte-for-byte as it did before the split.

Usage:
  ./mac_okf.py build --src <concepts_dir> --out <bundle_dir>
  ./mac_okf.py audit --src <concepts_dir> --out <bundle_dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml
from jsonschema import validators as jsv

# ONE schema home. This module used to build its own path to the vendored fork, bypassing
# sdk.grammar.resolve entirely — so the process could hold TWO grammars at once and nothing said
# which had judged what. That is the same second-home defect the fork itself was, one level down.
from sdk.grammar.resolve import schema_path as _schema_path  # noqa: E402

# ONE PAGE AUTHOR, AND IT IS NOT NAMED AFTER A FORMAT. What a concept page SAYS moved to
# `concept_page_content` — the nine section builders, the whole-bundle context and the body —
# because this module is the projector of a MAC object into OKF and nothing else, and the
# console now serves that same page LIVE. The dependency runs one way: this reads the content,
# the content knows nothing about OKF.
from sdk.project.concept_page_content import (
    concept_body,
    concept_sections,
    page_inputs,
)

_SCHEMA_PATH = _schema_path()
SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_Validator = jsv.validator_for(SCHEMA)
_Validator.check_schema(SCHEMA)
_CONCEPT_VALIDATOR = _Validator(SCHEMA)

_RULE_ITEM = dict(SCHEMA["$defs"]["contract"]["properties"]["rules"]["items"])
_RULE_ITEM["$defs"] = SCHEMA["$defs"]
_RULE_VALIDATOR = _Validator(_RULE_ITEM)

TYPE_OF = {
    "entity": "Entity",
    "event": "Event",
    "measure": "Metric",
    "enumeration": "Enum",
    "reference": "Reference",
    "grouping": "Grouping",
    "meta": "Meta",
}


# --------------------------------------------------------------------------- #
# frontmatter + model-fence helpers
# --------------------------------------------------------------------------- #
def _dump(obj) -> str:
    return yaml.safe_dump(
        obj, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100000
    )


def frontmatter(surface: dict) -> str:
    return f"---\n{_dump(surface)}---\n"


def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---\n") and "\n---\n" in text:
        head, body = text.split("\n---\n", 1)
        return yaml.safe_load(head[4:]) or {}, body
    return {}, text


def lock_hash(obj) -> str:
    canon = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# the OKF surface — the only rendering left in this file. What a concept page SAYS
# is `sdk/project/concept_page_content.py`; these build the head that makes it OKF.
# --------------------------------------------------------------------------- #
def _one_line(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _first_sentence(s: str, cap: int = 220) -> str:
    """A clean OKF `description`: the first sentence, never a mid-word cut."""
    t = _one_line(s)
    m = re.search(r"(.+?[.!?])(\s|$)", t)
    out = m.group(1) if m else t
    if len(out) > cap:
        out = out[:cap].rsplit(" ", 1)[0] + "…"
    return out


def _bullets(text: str) -> str:
    parts = [p.strip() for p in re.split(r";\s+(?=[A-Za-z])", _one_line(text)) if p.strip()]
    return "\n".join(f"- {p}" for p in parts) if parts else ""


def _rule_ids(obj: dict) -> list[str]:
    return [
        r.get("id", "rule").replace("/", "_")
        for r in (obj.get("contract") or {}).get("rules") or []
    ]


def _okf_surface(obj: dict, name: str) -> dict:
    """The OKF frontmatter surface — the whole of what makes this page OKF rather than markdown.

    `type`/`title`/`description`/`tags`/`resource`/`rule_pages` are the generic OKF catalog's
    vocabulary, and a catalog reads nothing else about the concept. Split out of `concept_to_md`
    when the page's body moved to `concept_page_content`: this is the half that is about the
    FORMAT, so it is the half that stayed in the module named for one.
    """
    c = obj.get("concept", {})
    meta = obj.get("metadata", {})
    klass = c.get("class", "reference")
    title = c.get("label") or c.get("name") or name
    grounding = obj.get("grounding", {})
    srcs = grounding.get("sources") or []
    resource = f"table://{srcs[0]['relation']}" if srcs and srcs[0].get("relation") else None

    # ---- small OKF surface (the whole frontmatter) ----
    surface = {
        "type": TYPE_OF.get(klass, klass.title()),
        "title": title,
        "description": _first_sentence(c.get("definition", "")),
        "tags": [
            t
            for t in (
                meta.get("source"),
                klass,
                f"confidence:{meta.get('confidence')}" if meta.get("confidence") else None,
            )
            if t
        ],
    }
    if resource:
        surface["resource"] = resource
    rule_ids = _rule_ids(obj)
    if rule_ids:
        surface["rule_pages"] = [f"rules/{r}.md" for r in rule_ids]
    return surface


def concept_to_md(
    obj: dict,
    src_path: Path,
    name: str,
    bundle: dict[str, str],
    joins: dict | None = None,
    col_desc: dict | None = None,
) -> str:
    """A concept as an OKF page: the small OKF surface, then the page's own content.

    The body is `concept_page_content.concept_body` — see that module for why the content does not
    live here. This composition is byte-for-byte what this function returned before the split.
    """
    return (
        frontmatter(_okf_surface(obj, name))
        + "\n"
        + concept_body(obj, src_path, name, bundle, joins, col_desc)
    )


def rule_to_md(rule: dict, parent_name: str, parent_title: str) -> str:
    title = rule.get("subject") or rule.get("id")
    _kind = str(rule.get("kind") or "rule").split(".")[-1]
    _binds = ", ".join(rule.get("binds") or [])
    surface = {
        "type": "Rule",
        "title": title,
        # a DISTINCT subtitle (not a repeat of the title) — the kind + the columns it binds
        "description": f"{_kind} rule" + (f" · binds {_binds}" if _binds else ""),
        "tags": [
            t
            for t in (
                rule.get("scope"),
                rule.get("kind"),
                f"confidence:{rule.get('confidence')}" if rule.get("confidence") else None,
            )
            if t
        ],
        "applies_to": f"../{parent_name}.md",
    }
    _conf = {"C": "confirmed", "P": "proposed", "R": "rejected"}.get(
        rule.get("confidence"), rule.get("confidence")
    )
    # FULL detail, labelled, with the raw namespaces stripped (mac.rule_kind.* -> the bare kind).
    # No body H1 / subject blockquote — the read-view already renders the frontmatter title.
    details = [f"- **Kind** — `{_kind}`"]
    if rule.get("confidence"):
        details.append(f"- **Confidence** — {rule.get('confidence')} ({_conf})")
    if rule.get("scope"):
        details.append(f"- **Scope** — {rule.get('scope')}")
    if rule.get("binds"):
        details.append("- **Binds** — " + ", ".join(f"`{b}`" for b in rule.get("binds")))
    if rule.get("id"):
        details.append(f"- **Rule id** — `{rule.get('id')}`")
    body = ["## Rule", "", *details, ""]
    for label, key in (
        ("When", "when"),
        ("Then — do (then)", "then"),
        ("Never — don't (never)", "never"),
    ):
        if rule.get(key):
            # VERBATIM — a single authored clause stays ONE clause. The old _bullets() split on '; ',
            # fragmenting SME phrasing and any clause/SQL that legitimately contains a semicolon.
            body += [f"### {label}", "", str(rule[key]).strip(), ""]
    body += [f"Applies to [{parent_title}](../{parent_name}.md)."]
    return frontmatter(surface) + "\n" + "\n".join(body)


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def load_concepts(src: Path):
    """Every concept under `src`, at any depth.

    RECURSIVE. This globbed "*.yaml" — flat only — so a bundle filing concepts by domain
    (`concepts/finance/revenue.yaml`) built ZERO concept pages and reported "built 0 concept pages"
    as a success. The console then 404'd every doc it asked for: "no such bundle file:
    ontology/concepts/customer.md". Third projector in this package with the same assumption; the
    object index and the data projector had it too.
    """
    out = []
    for p in sorted(src.rglob("*.yaml")):
        raw = p.read_text()
        obj = yaml.safe_load(raw)
        if isinstance(obj, dict) and "concept" in obj:
            out.append((p.stem, p, obj, raw))
    return out


def bundle_title(src: Path) -> str:
    """The concept index's title, READ from the bundle's own manifest.

    It used to be the string "ACME geography" — one instance's name, hardcoded, so EVERY bundle this
    projector touched got a concept index titled after a bundle it has nothing to do with. It reached
    the public example ontologies that way. The manifest already carries the identity the console
    addresses the container by; this reads it there rather than inventing a second home for it.
    """
    for root in (src.parent.parent, src.parent, src):
        mf = root / "mac.project.yaml"
        if not mf.is_file():
            continue
        try:
            md = (yaml.safe_load(mf.read_text(encoding="utf-8")) or {}).get("metadata") or {}
        except Exception:
            continue
        label = md.get("label") or md.get("project") or md.get("dataset")
        if label:
            return str(label)
    return src.parent.parent.name or "Ontology"


def concept_page(name: str, path: Path, obj: dict, inputs: dict) -> str:
    """ONE concept's OKF page, as markdown. Writes nothing; `build` writes what this returns.

    The OKF head, then `concept_page_content.concept_sections` — the same two halves as
    `concept_to_md`, over the whole-bundle context `page_inputs` computed. `build` and the live
    page seam (`tools/project_concept_page.py`) both call exactly this, which is what keeps one
    page from having two authors.
    """
    return (
        frontmatter(_okf_surface(obj, name))
        + "\n"
        + concept_sections(name, path, obj, inputs)
    )


def build(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    concepts = load_concepts(src)
    # IDEMPOTENCY: the read-view *.md and rules/ are DERIVED. Clear stale derived pages so a
    # renamed/removed concept or rule cannot leave an orphan that bloats the signed artifact and
    # makes index.md list phantom rules. NEVER touch the SSOT: out == the concepts dir also holds
    # the authored *.yaml, so we only remove derived *.md (whose stem has no sibling .yaml) + the
    # rules/ subtree (which is 100% derived).
    shutil.rmtree(out / "rules", ignore_errors=True)
    (out / "rules").mkdir()
    _valid_md = {f"{name}.md" for name, _p, _o, _r in concepts} | {"index.md"}
    for md in out.glob("*.md"):
        if md.name not in _valid_md and not (out / f"{md.stem}.yaml").exists():
            md.unlink()
    inputs = page_inputs(src, concepts)
    bundle = inputs["bundle"]
    n_rules = 0
    for name, path, obj, _raw in concepts:
        (out / f"{name}.md").write_text(concept_page(name, path, obj, inputs))
        for rule in (obj.get("contract") or {}).get("rules") or []:
            rid = rule.get("id", "rule").replace("/", "_")
            (out / "rules" / f"{rid}.md").write_text(rule_to_md(rule, name, bundle[name]))
            n_rules += 1
    title = bundle_title(src)
    idx = [
        "---",
        "type: Index",
        f"title: {title} — concepts (MAC-in-OKF)",
        "---",
        "",
        f"# {title} — MAC objects as OKF pages",
        "",
    ]
    idx += [f"- [{bundle[n]}]({n}.md)" for n in sorted(bundle)]
    idx += ["", "## Rules"] + [
        f"- [{rp.stem}](rules/{rp.name})" for rp in sorted((out / "rules").glob("*.md"))
    ]
    (out / "index.md").write_text("\n".join(idx) + "\n")
    print(f"built {len(concepts)} concept pages + {n_rules} rule pages -> {out}")


def audit(src: Path, out: Path):
    """Validate the ontology. The .md read-view is now a LOSSY human projection (no embedded model
    fence), so the SSOT is the .yaml — validate that directly, confirm every concept has a page, and
    check cross-links resolve."""
    concepts = load_concepts(src)
    ok = True
    print(f"\n{'object':<26}{'page':<10}{'MAC valid':<11}{'lock/12'}")
    print("-" * 62)
    for name, _path, obj, _raw in concepts:
        page = (out / f"{name}.md").exists()
        mac_valid = not list(_CONCEPT_VALIDATOR.iter_errors(obj))  # validate the YAML SSOT
        ok = ok and mac_valid and page
        print(
            f"{name:<26}{('yes' if page else 'MISSING'):<10}{_yn(mac_valid):<11}{lock_hash(obj)[:12]}"
        )
    all_rules = [
        r for _n, _p, obj, _r in concepts for r in ((obj.get("contract") or {}).get("rules") or [])
    ]
    rule_ok = sum(1 for r in all_rules if not list(_RULE_VALIDATOR.iter_errors(r)))
    broken = _check_links(out)
    print("-" * 62)
    print(
        f"concepts: {len(concepts)} | rules valid: {rule_ok}/{len(all_rules)} "
        f"| broken cross-links: {len(broken)}"
    )
    if broken:
        print("  broken:", broken)
    return 0 if (ok and rule_ok == len(all_rules) and not broken) else 1


def _check_links(out: Path):
    files = {p.relative_to(out).as_posix() for p in out.rglob("*.md")}
    broken = []
    for p in out.rglob("*.md"):
        head = p.read_text().split("\n```yaml\n", 1)[0]  # ignore links inside the fence
        for _txt, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", head):
            if "://" in href or href.startswith("#"):
                continue
            tgt = (p.parent / href).resolve().relative_to(out.resolve()).as_posix()
            if tgt not in files:
                broken.append(f"{p.relative_to(out)} -> {href}")
    return broken


def _yn(b):
    return "PASS" if b else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "audit"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    if a.cmd == "build":
        build(src, out)
        return 0
    return audit(src, out)


if __name__ == "__main__":
    sys.exit(main())
