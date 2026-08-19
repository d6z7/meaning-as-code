#!/usr/bin/env python3
"""MAC003 — a term the reader has retired may not come back.

THREE TIMES IN ONE DAY the operator had to stop and ask what a word meant, each time a term imported
from a technical vocabulary and never justified in the language the ontology exists to speak:

  "and here is this reporting vintage ... i must ask you to propose another wording for vintage
   ... it is confucing me to much ... this is my problem i know but still please"
  "i actually do not know this word: anti-vacuity"

It is NOT his problem. An ontology exists so a business reader can talk about the business, and a
word he has to ask about is a word that failed at that job. Each time the fix was a find-and-replace,
and a find-and-replace does not survive the next agent who learned the old word from the last file
they read. This is the mechanism instead: retired terms are DECLARED once, with their replacement
and the reason, and prose that reintroduces one fails.

The replacement is never a synonym for its own sake. `vintage` became `reporting cycle` because the
underlying column IS a month and the plainer word is also the more accurate one; `anti-vacuity`
became `proof of search` because the reader needed to know what it guarded, not what it is called in
the literature.

SCOPE IS PROSE, NOT KEYS. `served: false` stays in plan_stage.yaml and the P-VINT-* family keeps its
name — renaming a schema key is a versioned change and the ontology is locked. What must not survive
is the term in a sentence a person reads.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import yaml

# Declared here rather than in a bundle file: these are rulings about the FRAMEWORK's language, and
# the next source inherits them instead of rediscovering each one by confusing its own reader.
RETIRED = {
    "vintage": {
        "use": "reporting cycle",
        "why": "bitemporal-modelling jargon; the column is config_reporting_month and it IS a month, "
               "so the plainer word is also the more accurate one",
        "ruled": "2026-08-19",
    },
    "anti-vacuity": {
        "use": "proof of search",
        "why": "names the academic property rather than what it protects — that a search reporting "
               "nothing was pointed at real data, not at an empty warehouse",
        "ruled": "2026-08-19",
    },
    "anti vacuity": {"use": "proof of search", "why": "spacing variant", "ruled": "2026-08-19"},
    "vacuity": {
        "use": "proof of search",
        "why": "same term, shortened; equally opaque",
        "ruled": "2026-08-19",
    },
    "served rows": {
        "use": "production data (test deliveries excluded)",
        "why": "'served' is a pipeline word; the reader's distinction is production versus test",
        "ruled": "2026-08-19",
    },
    "not served": {
        "use": "test deliveries",
        "why": "as above — say what the rows ARE, not what the pipeline does with them",
        "ruled": "2026-08-19",
    },
}

# Where a person actually reads prose. Keys and code are out of scope by design.
PROSE_FIELDS = ("statement", "why", "reason", "detail", "note", "notes", "definition",
                "purpose", "subject", "disclose", "locus", "baseline", "delta", "evidence")


def _walk(node, path: str = ""):
    """Yield (path, text) for every prose-bearing string in a parsed document."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(v, str) and k in PROSE_FIELDS:
                yield here, v
            else:
                yield from _walk(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def scan(root: str) -> list[dict]:
    out = []
    pats = {t: re.compile(rf"(?<![\w-]){re.escape(t)}(?![\w-])", re.I) for t in RETIRED}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "node_modules", ".venv", ".harvest_cache", "evidence"}]
        for fn in filenames:
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                doc = yaml.safe_load(open(p, encoding="utf-8"))
            except Exception:
                continue
            for where, text in _walk(doc):
                for term, pat in pats.items():
                    m = pat.search(text)
                    if not m:
                        continue
                    lo = max(0, m.start() - 45)
                    out.append({
                        "file": os.path.relpath(p, root), "path": where, "term": term,
                        "use": RETIRED[term]["use"], "why": RETIRED[term]["why"],
                        "quote": "…" + text[lo:m.end() + 45].replace("\n", " ") + "…",
                    })
                    break  # one finding per field is enough to send someone to fix it
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true", help="print the retired vocabulary and exit")
    a = ap.parse_args()

    if a.list:
        for t, d in sorted(RETIRED.items()):
            print(f"  {t:<14} -> {d['use']}\n      {d['why']}  (ruled {d['ruled']})")
        return 0

    findings = scan(a.root)
    if a.json:
        print(json.dumps({"findings": findings}, indent=1, ensure_ascii=False))
        return 1 if findings else 0

    by_term: dict[str, int] = {}
    for f in findings:
        by_term[f["term"]] = by_term.get(f["term"], 0) + 1
        print(f"  [ERROR] {f['file']}  {f['path']}")
        print(f"          uses {f['term']!r} — say {f['use']!r}")
        print(f"          {f['quote']}")
    if findings:
        print(f"\n✗ {len(findings)} retired term(s) in prose: "
              + " · ".join(f"{t} x{n}" for t, n in sorted(by_term.items())))
        print("  the reader asked what these meant; a word he has to ask about failed its job")
        return 1
    print(f"✓ OK — no retired term appears in prose ({len(RETIRED)} declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
