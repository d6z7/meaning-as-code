#!/usr/bin/env python3
"""
gen_vocabulary_terms.py — generate the TERM DEFINITION blocks of the reference manual from
mac_vocabulary.yaml.

The value-side companion to gen_schema_shapes.py. That one renders STRUCTURE from mac.schema.json
(which keys exist, where they nest); this one renders MEANING from mac_vocabulary.yaml (what the
values of those keys mean). Same marker convention, same --check gate, same rule: it writes ONLY
between the markers, so the hand-written guidance around each block survives regeneration.

WHY IT EXISTS. A manual that retypes its definitions is a second home for them, and a second home
drifts. Measured 2026-09-25: twenty files in this estate defined what `dimension` means — seven
verbatim copies and eleven generated ones giving five different terms the same placeholder
sentence. check_references.py scans only *.yaml/*.yml, so no markdown in this repo has ever been
checked against the vocabulary it cites.

Usage:
  python3 tools/gen_vocabulary_terms.py           # inject into reference_manual/*.md
  python3 tools/gen_vocabulary_terms.py --check   # gate: fail if a block is stale or a notion has no chapter
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VOCAB = ROOT / "mac_vocabulary.yaml"
DOCS = ROOT / "reference_manual"

BLOCK = re.compile(
    r"(?P<open><!-- BEGIN GENERATED:vocabulary-terms:(?P<notion>[A-Za-z_.]+) "
    r"\(tools/gen_vocabulary_terms\.py — do not edit inside this block\) -->\n)"
    r"(?P<body>.*?)"
    r"(?P<close><!-- END GENERATED:vocabulary-terms:(?P=notion) -->)",
    re.DOTALL,
)


def _wrap(text: str, width: int = 96) -> str:
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        words, line, lines = para.split(), "", []
        for w in words:
            if line and len(line) + 1 + len(w) > width:
                lines.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            lines.append(line)
        out.append("\n".join(lines))
    return "\n\n".join(out)


def render(notion: str, spec: dict) -> str:
    """Render one notion, whichever of the three shapes it is written in.

    THREE SHAPES, and this used to read only the first:
      * `kind: vocabulary`  + `terms:`   -- name -> a sentence            (17 notions)
      * `kind: value_domain` + `terms:` -- name -> a RECORD of fields    (measure_type, canon)
      * `kind: registry`    + neither     -- nothing term-shaped           (connector)

    The second shape is not merely spelled differently: a member carries structured fields, and
    they are the useful part. `canon.composite_key_guard` records `serves: context_dependent_meaning`
    -- the pattern it implements -- so the cross-reference the manual needs is already data and does
    not have to be written by hand. Reading it as a string printed a Python dict repr.
    """
    entries = spec.get("terms") or spec.get("members") or {}
    word = "terms" if spec.get("terms") else "members"
    closed = "closed — these are all of them" if spec.get("closed") else "open — a bundle may add its own"
    lines = ["", f"> {_wrap(str(spec.get('description') or '')).strip()}", ""]
    if not entries:
        lines += [f"*`mac.{notion}` · {spec.get('kind', 'vocabulary')} · no enumerated members*", ""]
        return "\n".join(lines)
    lines += [f"*`mac.{notion}` · {len(entries)} {word} · {closed}*", ""]
    for name, body in entries.items():
        lines += [f"#### `mac.{notion}.{name}`", ""]
        if isinstance(body, dict):
            # A RECORD. Its main prose field leads; the rest becomes a small table, because the
            # fields are what distinguish one member from another.
            main = next((body[k] for k in ("definition", "doc", "description") if body.get(k)), None)
            if main:
                lines += [_wrap(str(main)), ""]
            rest = {k: v for k, v in body.items()
                    if k not in ("definition", "doc", "description") and v is not None}
            if rest:
                lines += ["| field | value |", "|---|---|"]
                for k, v in rest.items():
                    if isinstance(v, dict):
                        v = " · ".join(f"{kk}: {vv}" for kk, vv in v.items())
                    elif isinstance(v, list):
                        v = ", ".join(str(x) for x in v)
                    cell = str(v).replace("|", "\\|")
                    lines += [f"| `{k}` | {cell} |"]
                lines += [""]
        else:
            lines += [_wrap(str(body)), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("--check", action="store_true", help="fail (exit 1) if a block is stale")
    a = ap.parse_args(argv)

    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: PyYAML is not importable ({exc})")
        return 2
    if not VOCAB.is_file() or not DOCS.is_dir():
        print(f"REFUSED: need {VOCAB.name} and {DOCS}")
        return 2

    vocab = yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {}
    notions = {k: v for k, v in vocab.items()
               if isinstance(v, dict) and v.get("kind") in ("vocabulary", "value_domain", "registry")}

    seen: list[str] = []
    unknown: list[str] = []
    updates: dict[pathlib.Path, str] = {}

    def sub(m: re.Match[str]) -> str:
        notion = m.group("notion")
        seen.append(notion)
        if notion not in notions:
            unknown.append(notion)
            return m.group(0)
        return m.group("open") + render(notion, notions[notion]) + m.group("close")

    for page in sorted(DOCS.glob("*.md")):
        text = page.read_text(encoding="utf-8")
        rendered = BLOCK.sub(sub, text)
        if rendered != text:
            updates[page] = rendered

    if unknown:
        print(f"FAIL — the manual cites {len(unknown)} notion(s) the vocabulary does not define: "
              f"{', '.join(sorted(set(unknown)))}")
        return 1

    missing = sorted(n for n in notions if n not in seen)
    if a.check:
        print(f"notions defined: {len(notions)}   documented: {len(set(seen))}   "
              f"UNDOCUMENTED: {len(missing)}")
        if missing:
            print("  no chapter yet: " + ", ".join(missing))
        if updates:
            print("FAIL — stale generated blocks in: "
                  + ", ".join(sorted(p.name for p in updates)))
            print("  run: python3 tools/gen_vocabulary_terms.py")
            return 1
        print("OK — every generated block matches mac_vocabulary.yaml.")
        return 0

    for page, rendered in updates.items():
        page.write_text(rendered, encoding="utf-8")
    print(f"rewrote {len(updates)} page(s)" if updates else "already current")
    if missing:
        print("  no chapter yet: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
