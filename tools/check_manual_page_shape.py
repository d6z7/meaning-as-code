#!/usr/bin/env python3
"""check_manual_page_shape.py — A MANUAL PAGE IS THE SHAPE ITS GUARDRAIL DECLARES.

`tools/check_page_shape.py` opens with "WHAT A SCHEMA IS FOR YAML, THIS IS FOR MARKDOWN" and then
governs BUNDLE pages only. MEASURED 2026-10-04 on this tree: `reference_manual/` holds 123 markdown
pages and NOT ONE was named by any declaration — the four artifacts declaring `shape.sections` were
all bundle deliverables. The mechanism existed and pointed somewhere else. This points it here.

WHY A SECOND FILE AND NOT A FLAG ON check_page_shape.py. Four measurements, not a preference:

  1. THE SUBJECT IS A DIFFERENT THING. `check_page_shape.py` takes a BUNDLE root in argv[1] and
     `run_framework_gates.sh` hands it one. This gate's subject is THIS REPOSITORY's manual; a bundle
     has no `reference_manual/`. The estate already split exactly this case rather than overload one
     file: `check_key_reference.py` exists only because its subject is this repo while the runner's
     convention is a bundle root.
  2. `required` IS COMPUTED FROM A DIFFERENT FACT. `check_page_shape._needs` reads the page's sibling
     `.yaml` DESCRIPTOR, so "required" there means "the data for it exists". A manual page has no
     descriptor. Sharing that function means two condition vocabularies inside one `if` chain.
  3. THE REJECT CLASSES DO NOT MEET. That gate rejects SECTION_MISSING / LINE_MALFORMED over rendered
     table and bullet lines. A manual page's defects are frontmatter schema, a status vocabulary, a
     missing purpose statement and a genre variant — none of which it has a notion of.
  4. THE DECLARATION CANNOT LIVE UNDER `delivers:`, measured. Declaring one manual page there put
     `reference_manual/patterns/*.md` into `mac_manifest.bom()` as ABSENT from contoso5 (absent 1 ->
     2, so the BOM's completeness answer broke), added it to `sdk/project/layout.layouts()` (10 ->
     11), and made check_document_layout print "held by tools/check_page_shape.py" about a page that
     gate can never see. So the declaration is `authored:` in guardrails/reference_manual.yaml, and a
     new block needs its own reader.

WHAT IS SHARED, BECAUSE IT MUST BE: the heading parser. Section names come from
`check_page_shape.sections()` — the same normalisation the bundle gate uses, so `## Contract (the
pluggable interface)` is the declared `Contract` in both places. The one time a heading rule in this
estate was written down twice, the copy was double-escaped and refused three correct pages inside
four minutes.

FENCE-AWARE, AND THE SHARED PARSER IS NOT. `sections()` reads `^##` anywhere, including inside a
fenced code block — fine on a rendered bundle page, wrong on a manual page full of YAML examples.
This strips fenced blocks first and then calls the shared parser, so the regex still has one home.
Measured on these 123 pages: stripping fences removes 2 phantom headings and changes no verdict.

ASSERT LITTLE AND TRUE. A genre governs only what it declares. `sections: []` asserts nothing about
sections and is REPORTED as asserting nothing; `status_closed: null` asserts nothing about the
vocabulary and says so. Three rules measured as cry-wolf were deliberately not written — see the
guardrail's header for the counts.

ONLY NEWS EXITS 1. A measured non-conformance that cannot be fixed by this change is declared in the
guardrail's `standing:` list with an owner and a reason; it is counted and NAMED on every run and
exits 0. A standing entry whose page has started conforming is STANDING_STALE and exits 1, so the
list cannot rot into an excuse.

    python3 tools/check_manual_page_shape.py                 # the manual in this repository
    python3 tools/check_manual_page_shape.py <ignored>        # the runner's convention; see below
    python3 tools/check_manual_page_shape.py --self-test

A POSITIONAL ARGUMENT IS ACCEPTED AND IGNORED, loudly. `run_framework_gates.sh` globs `check_*.py`
and passes `<bundle-root>` to every gate not listed in its `REPO_SUBJECT_GATES` array. This gate
belongs in that array and adding it is not part of this change, so refusing the argument would turn
a calling-convention miss into a could-not-run — a NEW red in the suite that is not news about the
manual, and "a suite must never get greener (or redder) as a side effect of someone else's task".
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from check_page_shape import sections as _shared_sections  # noqa: E402  — ONE home for the parser

#: THE ENUMERATION VERDICTS. `standing` is a declared, owned non-conformance: counted, named, exit 0.
HELD, FAILED, STANDING, NA, EXEMPT = "held", "failed", "standing", "n/a", "exempt"

#: Every way a manual page can be refused. One self-test mutant per entry — see `_self_test`.
REJECTS = (
    "FRONTMATTER_MISSING",      # no `---` block at all
    "FRONTMATTER_UNPARSEABLE",  # a `---` block that is not YAML
    "KEY_MISSING",              # a declared required key is absent
    "KEY_UNDECLARED",           # a key in neither `required` nor `optional` — frontmatter schema N+1
    "STATUS_UNDECLARED",        # `status` outside the genre's closed set
    "STATUS_FIRST_WORD_UNDECLARED",   # the term before the em-dash justification is not closed
    "SECTION_MISSING",          # a declared `required: always` section is absent
    "NO_VARIANT",               # a multi-variant genre's page satisfies none of them
    "NO_PURPOSE",               # `opens_with: purpose` and nothing between the H1 and the first `##`
    "UNGOVERNED_PAGE",          # a page under reference_manual/ that no genre claims
    "GENRE_OVERLAP",            # a page claimed by two genres — no precedence rule exists here
    "EXEMPT_UNHELD",            # an exemption whose `held_by` tool is not on disk
    "STANDING_STALE",           # a declared standing failure that now conforms
)

MANUAL = "reference_manual"
BLOCK = "authored"


def _f(subject, verdict, reject="", note=""):
    return {"subject": subject, "verdict": verdict, "reject": reject, "note": note}


# ── the page, parsed ────────────────────────────────────────────────────────────────────────────
def frontmatter(text: str):
    """`(mapping, body)` — `(None, text)` when there is no `---` block, `(str, body)` when it is not
    YAML. The error is a VALUE, not an exception: an unparseable declaration must not read as a
    missing one."""
    import yaml

    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    raw, body = text[4:end], text[end + 4:]
    try:
        doc = yaml.safe_load(raw)
    except Exception as exc:                                              # noqa: BLE001
        return f"{type(exc).__name__}: {str(exc).splitlines()[0]}", body
    return (doc if isinstance(doc, dict) else {}), body


def defence(text: str) -> str:
    """The page with fenced code blocks removed. A `##` inside a fence is an EXAMPLE, not a section."""
    out, fence = [], None
    for line in text.splitlines():
        m = re.match(r"^\s*(```+|~~~+)", line)
        if m:
            tok = m.group(1)[:3]
            if fence is None:
                fence = tok
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence is None:
            out.append(line)
    return "\n".join(out)


def headings(text: str) -> dict:
    """The page's sections, fence-stripped, named by the SHARED parser."""
    return _shared_sections(defence(text))


def has_purpose(body: str) -> bool:
    """Prose between the first `# ` title and the first `##` — the page saying what it is for."""
    lines = defence(body).splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
    if start is None:
        return False
    for line in lines[start + 1:]:
        s = line.strip()
        if not s or s.startswith("<!--"):
            continue
        return not s.startswith("#")
    return False


# ── the declaration, read ───────────────────────────────────────────────────────────────────────
def _branch_re(branch: str) -> re.Pattern:
    """One `path` branch as a matcher. `{token}` is a segment wildcard; `**` spans segments."""
    pat, i = "", 0
    branch = branch.strip()
    while i < len(branch):
        if branch[i] == "{":
            j = branch.find("}", i)
            pat += "[^/]*"
            i = (j + 1) if j != -1 else len(branch)
        elif branch.startswith("**", i):
            pat += ".*"
            i += 2
        elif branch[i] == "*":
            pat += "[^/]*"
            i += 1
        else:
            pat += re.escape(branch[i])
            i += 1
    return re.compile(f"^{pat}$")


def claims(path_pattern: str) -> list:
    """Every matcher a `path` declares. ALL branches, not the first — `check_page_shape` takes
    `path.split('|')[0]` because a bundle kind has one real branch; three of the five genres here
    are explicit `|` lists of named pages, and reading only the first would govern one page of 8."""
    return [_branch_re(b) for b in str(path_pattern or "").split("|") if b.strip()]


def genres(framework: pathlib.Path) -> dict:
    """`{name -> declaration}` over every `authored:` item of every guardrails topic.

    RECURSIVE. A flat `guardrails/*.yaml` sees `common` and `unfiled` and misses every topic under
    `data/` — this estate's most-repeated defect, nine occurrences.
    """
    import yaml

    out = {}
    d = framework / "guardrails"
    if not d.is_dir():
        return out
    for f in sorted(d.rglob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                                 # noqa: BLE001
            continue        # an unreadable topic is check_guardrails.py's refusal, not a shape fact
        if not isinstance(doc, dict):
            continue
        for name, item in (doc.get(BLOCK) or {}).items():
            if isinstance(item, dict):
                it = dict(item)
                it["_topic"] = str(doc.get("topic") or f.stem)
                out[str(name)] = it
    return out


# ── one page against one genre ──────────────────────────────────────────────────────────────────
def check_frontmatter(rel: str, fm, shape: dict) -> list:
    """The frontmatter against `shape.frontmatter`. NO CASCADE: a page with no block gets one
    finding, not five — the cause is the block, and five findings would make one defect look like a
    rotten page."""
    spec = shape.get("frontmatter") or {}
    if not spec:
        return [_f(rel, NA, note="the genre declares no frontmatter rule")]
    if fm is None:
        return [_f(rel, FAILED, "FRONTMATTER_MISSING",
                   "no `---` frontmatter block; the genre requires "
                   f"{sorted(spec.get('required') or [])}")]
    if isinstance(fm, str):
        return [_f(rel, FAILED, "FRONTMATTER_UNPARSEABLE", f"the `---` block is not YAML — {fm}")]

    out = []
    required = list(spec.get("required") or [])
    optional = list(spec.get("optional") or [])
    missing = [k for k in required if k not in fm]
    if missing:
        out.append(_f(rel, FAILED, "KEY_MISSING",
                      f"frontmatter has {sorted(fm)} and the genre requires {missing}"))
    extra = [k for k in sorted(fm) if k not in required and k not in optional]
    if extra:
        out.append(_f(rel, FAILED, "KEY_UNDECLARED",
                      f"{extra} is in neither `required` {required} nor `optional` {optional} — "
                      f"an undeclared key is frontmatter schema N+1, which is what this governs"))

    status = str(fm.get("status", "")).strip()
    closed = spec.get("status_closed")
    first = spec.get("status_closed_first_word")
    if closed and "status" in fm and status not in [str(v) for v in closed]:
        out.append(_f(rel, FAILED, "STATUS_UNDECLARED",
                      f"status {status[:60]!r} is not one of {list(closed)}"))
    elif first and "status" in fm:
        word = status.split()[0] if status else ""
        if word not in [str(v) for v in first]:
            out.append(_f(rel, FAILED, "STATUS_FIRST_WORD_UNDECLARED",
                          f"status opens {word!r} and the closed terms are {list(first)} "
                          f"(the em-dash justification after the term is free prose)"))
    return out or [_f(rel, HELD, note=f"frontmatter: {len(required)} required key(s), "
                                      f"status {'closed' if (closed or first) else 'open'}")]


def check_sections(rel: str, present: dict, shape: dict) -> list:
    """`shape.sections` or `shape.variants`, whichever the genre declares. Neither is `n/a`."""
    variants = shape.get("variants") or {}
    declared = shape.get("sections")
    if variants:
        scored = {}
        for vname, v in variants.items():
            need = [s["heading"] for s in (v.get("sections") or [])
                    if str(s.get("required")) == "always"]
            scored[vname] = [h for h in need if h not in present]
        winner = next((v for v, miss in scored.items() if not miss), None)
        if winner:
            return [_f(rel, HELD, note=f"variant {winner!r} — every required section present "
                                       f"({len(present)} heading(s) on the page)")]
        near = min(scored, key=lambda v: len(scored[v]))
        return [_f(rel, FAILED, "NO_VARIANT",
                   f"satisfies none of {sorted(scored)}; nearest is {near!r}, missing "
                   f"{scored[near]} — the page has {sorted(present)}")]
    if not declared:
        return [_f(rel, NA, note="the genre declares no sections — nothing is asserted about them")]
    missing = [s["heading"] for s in declared
               if str(s.get("required")) == "always" and s["heading"] not in present]
    if missing:
        return [_f(rel, FAILED, "SECTION_MISSING",
                   f"declared `required: always` and absent: {missing}")]
    return [_f(rel, HELD, note=f"{len(declared)} declared section(s) present"
                               + ("" if shape.get("extra_sections") != "allowed"
                                  else f"; {len(present) - len(declared)} extra allowed"))]


def check_page(rel: str, text: str, shape: dict) -> list:
    """One manual page against one genre's `shape`. The ENUMERATION CONTRACT: one item per subject."""
    fm, body = frontmatter(text)
    out = [_f(f"{rel} «frontmatter»", i["verdict"], i["reject"], i["note"])
           for i in check_frontmatter(rel, fm, shape)]
    out += [_f(f"{rel} «sections»", i["verdict"], i["reject"], i["note"])
            for i in check_sections(rel, headings(text), shape)]
    if shape.get("opens_with") == "purpose":
        out.append(_f(f"{rel} «purpose»", HELD, note="states what it is for before its first `##`")
                   if has_purpose(body) else
                   _f(f"{rel} «purpose»", FAILED, "NO_PURPOSE",
                      "nothing between the `# ` title and the first `##` — the page never says "
                      "what it is for"))
    return out


# ── the run ─────────────────────────────────────────────────────────────────────────────────────
def run(framework: pathlib.Path) -> tuple:
    """`(findings, census)` over EVERY page under reference_manual/. The census IS the denominator."""
    decl = genres(framework)
    man = framework / MANUAL
    pages = sorted(str(p.relative_to(framework).as_posix()) for p in man.rglob("*.md"))
    matchers = {name: claims(item.get("path")) for name, item in decl.items()}

    findings, census = [], {"pages": len(pages), "genres": {}, "ungoverned": []}
    owners = {}
    for rel in pages:
        mine = [n for n, ms in matchers.items() if any(m.match(rel) for m in ms)]
        if not mine:
            census["ungoverned"].append(rel)
            findings.append(_f(rel, FAILED, "UNGOVERNED_PAGE",
                               "under reference_manual/ and claimed by no genre — "
                               "UNSPECIFIED IS NOT RULED, but it must not be INVISIBLE"))
            continue
        if len(mine) > 1:
            findings.append(_f(rel, FAILED, "GENRE_OVERLAP",
                               f"claimed by {sorted(mine)} — a page belongs to exactly one genre and "
                               f"no precedence rule exists in this block"))
            continue
        owners[rel] = mine[0]

    for name, item in sorted(decl.items()):
        shape = item.get("shape") or {}
        mine = [r for r, g in owners.items() if g == name]
        row = {"claimed": len(mine), "judged": 0, "held": 0, "failed": 0, "standing": 0,
               "exempt": 0, "genre": item.get("genre", "?")}
        if shape.get("exempt"):
            row["exempt"] = len(mine)
            holders = [str(h) for h in (shape.get("held_by") or [])]
            if not holders:
                findings.append(_f(name, FAILED, "EXEMPT_UNHELD",
                                   "declares `exempt: true` and names no `held_by` — an exemption "
                                   "with no holder is a hole with a sentence over it"))
            for h in holders:
                if not (framework / h).is_file():
                    findings.append(_f(f"{name} -> {h}", FAILED, "EXEMPT_UNHELD",
                                       f"the exemption is held by {h} and that file is not on disk"))
            census["genres"][name] = row
            continue
        standing = {(str(s.get("page")), str(s.get("reject"))): s
                    for s in (item.get("standing") or []) if isinstance(s, dict)}
        matched = set()
        for rel in sorted(mine):
            items = check_page(rel, (framework / rel).read_text(encoding="utf-8"), shape)
            row["judged"] += 1
            for i in items:
                if i["verdict"] != FAILED:
                    row["held"] += 1 if i["verdict"] == HELD else 0
                    findings.append(i)
                    continue
                key = (rel, i["reject"])
                if key in standing:
                    matched.add(key)
                    row["standing"] += 1
                    findings.append(_f(i["subject"], STANDING, i["reject"],
                                       f"DECLARED standing, owner {standing[key].get('owner')}, "
                                       f"since {standing[key].get('since')} — {i['note']}"))
                else:
                    row["failed"] += 1
                    findings.append(i)
        for key, s in standing.items():
            if key not in matched:
                findings.append(_f(f"{key[0]} «standing»", FAILED, "STANDING_STALE",
                                   f"declared standing for {key[1]} in guardrails/"
                                   f"{item['_topic']}.yaml and the page no longer breaks it — "
                                   f"remove the entry"))
        census["genres"][name] = row
    return findings, census


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ignored", nargs="?", default=None,
                    help="accepted and ignored: the runner's one calling convention")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    try:
        import yaml                                                       # noqa: F401
    except ImportError as exc:
        print(f"could not run: {exc} — a gate that cannot read its declaration must not pass")
        return 2

    fw = pathlib.Path(__file__).resolve().parent.parent
    if not (fw / MANUAL).is_dir():
        print(f"could not run: no {MANUAL}/ under {fw} — this gate's subject is absent")
        return 2
    decl = genres(fw)
    if not decl:
        print(f"could not run: no guardrail declares an `{BLOCK}:` block, so no manual page has a "
              f"shape to be held to. A gate with an empty population must never print PASS.")
        return 2

    findings, census = run(fw)
    bad = [f for f in findings if f["verdict"] == FAILED]
    standing = [f for f in findings if f["verdict"] == STANDING]

    print(f"── manual page shape ── {MANUAL}/ in {fw.name} ──")
    if a.ignored:
        print(f"  note     positional {a.ignored!r} IGNORED — this gate's subject is this "
              f"repository's manual, never a bundle")
    tot = census["genres"]
    for name, r in sorted(tot.items()):
        if r["exempt"]:
            print(f"  exempt   {name:24s} {r['exempt']:3d} page(s) — held by their generator's "
                  f"--check, verified on disk")
            continue
        print(f"  judged   {name:24s} {r['judged']:3d} of {r['claimed']:3d} claimed · "
              f"{r['held']:3d} subject(s) held · {r['standing']:3d} standing · {r['failed']:3d} failed")
    judged = sum(r["judged"] for r in tot.values())
    exempt = sum(r["exempt"] for r in tot.values())
    claimed = sum(r["claimed"] for r in tot.values())
    print(f"  ── DENOMINATOR: {census['pages']} page(s) exist under {MANUAL}/ · {claimed} claimed by "
          f"{len(tot)} genre(s) · {judged} judged · {exempt} exempt · "
          f"{len(census['ungoverned'])} ungoverned")
    for f in standing:
        print(f"    ~ {f['subject']}  [{f['reject']}]")
        print(f"        {f['note']}")
    for f in bad:
        print(f"    ✗ {f['subject']}  [{f['reject']}]")
        print(f"        {f['note']}")

    if bad:
        print(f"\nFAIL: check_manual_page_shape — {len(bad)} finding(s) over {judged} page(s) "
              f"judged of {census['pages']} that exist. The shape is `{BLOCK}.<genre>.shape` in "
              f"guardrails/ — change it THERE, never in this file.")
        return 1
    print(f"\nPASS: check_manual_page_shape — {judged} of {census['pages']} page(s) judged against "
          f"{len(tot)} declared genre(s) ({exempt} exempt, {len(census['ungoverned'])} ungoverned, "
          f"{len(standing)} declared standing); every judged page is the shape its guardrail declares.")
    return 0


def _self_test() -> int:
    """ONE SEEDED MUTANT PER REJECT CLASS, plus a clean fixture that must pass. A gate with no
    self-test asserts nothing about its own ability to reject."""
    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    SHAPE = {
        "sections": [{"heading": "Initial state", "required": "always"},
                     {"heading": "The footgun, concretely", "required": "always"}],
        "extra_sections": "allowed",
        "frontmatter": {"required": ["title", "status"], "optional": ["scope"],
                        "status_closed": ["prototype", "gap"]},
        "opens_with": "purpose",
    }
    GOOD = ("---\ntitle: T\nstatus: prototype\nscope: s\n---\n\n# T\n\nWhat this page is for.\n\n"
            "## Initial state — what you're handed\n\nx\n\n## The footgun, concretely\n\ny\n")

    def rejects(text, shape=SHAPE):
        return {i["reject"] for i in check_page("p.md", text, shape) if i["verdict"] == FAILED}

    case("a page in the declared shape HOLDS", not rejects(GOOD))

    # ── frontmatter ───────────────────────────────────────────────────────────────────────────
    case("MUTANT no frontmatter block at all is REFUSED",
         "FRONTMATTER_MISSING" in rejects(GOOD.split("---\n", 2)[2].lstrip()))
    case("MUTANT a frontmatter block that is not YAML is REFUSED",
         "FRONTMATTER_UNPARSEABLE" in rejects(GOOD.replace("title: T", "title: [unclosed")))
    case("MUTANT a required key dropped is REFUSED",
         "KEY_MISSING" in rejects(GOOD.replace("status: prototype\n", "")))
    case("MUTANT an UNDECLARED key — frontmatter schema N+1 — is REFUSED",
         "KEY_UNDECLARED" in rejects(GOOD.replace("scope: s", "audience: everyone")))
    case("MUTANT a status outside the closed set is REFUSED",
         "STATUS_UNDECLARED" in rejects(GOOD.replace("status: prototype", "status: draft")))
    FW = {**SHAPE, "frontmatter": {"required": ["title", "status"], "optional": ["scope"],
                                   "status_closed_first_word": ["reference", "SHIPPED"]}}
    case("MUTANT the TERM before the em-dash justification is not closed — REFUSED",
         "STATUS_FIRST_WORD_UNDECLARED" in
         rejects(GOOD.replace("status: prototype", "status: maybe — one day"), FW))
    case("a closed FIRST WORD with free prose after the dash HOLDS",
         not rejects(GOOD.replace("status: prototype",
                                  "status: SHIPPED — implemented in mac-runtime"), FW))

    # ── sections ──────────────────────────────────────────────────────────────────────────────
    case("MUTANT a declared `required: always` section dropped is REFUSED",
         "SECTION_MISSING" in rejects(GOOD.replace("## The footgun, concretely\n\ny\n", "")))
    case("an EXTRA section the declaration does not name is allowed, not a violation",
         not rejects(GOOD + "\n## Reading the entry\n\nz\n"))
    VAR = {"variants": {
        "pluggable": {"sections": [{"heading": "Serves", "required": "always"},
                                   {"heading": "Determinism & honest limits", "required": "always"}]},
        "entry": {"sections": [{"heading": "Serves", "required": "always"},
                               {"heading": "Limits", "required": "always"}]}},
        "frontmatter": {"required": ["title"], "optional": ["status", "scope"]}}
    PLUG = "---\ntitle: T\n---\n\n# T\n\n## Serves\n\nx\n\n## Determinism & honest limits (A5)\n\ny\n"
    ENTRY = "---\ntitle: T\n---\n\n# T\n\n## Serves\n\nx\n\n## Limits\n\ny\n"
    case("variant 'pluggable' HOLDS, and the parenthetical qualifier still resolves",
         not rejects(PLUG, VAR))
    case("variant 'entry' — the OTHER generation — HOLDS on the same declaration",
         not rejects(ENTRY, VAR))
    case("MUTANT a page satisfying NEITHER variant is REFUSED, naming the nearest",
         "NO_VARIANT" in rejects("---\ntitle: T\n---\n\n# T\n\n## Serves\n\nx\n", VAR)
         and any("nearest" in i["note"]
                 for i in check_page("p.md", "---\ntitle: T\n---\n\n# T\n\n## Serves\n", VAR)
                 if i["verdict"] == FAILED))

    # ── the purpose statement ─────────────────────────────────────────────────────────────────
    case("MUTANT the H1 followed straight by a `##` — the page never says what it is for",
         "NO_PURPOSE" in rejects(GOOD.replace("\nWhat this page is for.\n", "")))
    case("a genre that declares `opens_with: null` asserts NOTHING about the purpose line",
         not rejects(GOOD.replace("\nWhat this page is for.\n", ""),
                     {**SHAPE, "opens_with": None}))

    # ── fences, and the shared parser ─────────────────────────────────────────────────────────
    case("a `##` INSIDE a fenced block is an example, not a section — and cannot satisfy a rule",
         "SECTION_MISSING" in rejects(
             GOOD.replace("## The footgun, concretely\n\ny\n",
                          "```md\n## The footgun, concretely\n```\n")))
    case("the heading name comes from the SHARED parser, not a copy of its regex",
         headings("## Contract (the pluggable interface)\n\nx\n")
         == _shared_sections("## Contract (the pluggable interface)\n\nx\n"))

    # ── `n/a` is not a pass ───────────────────────────────────────────────────────────────────
    case("a genre declaring NO sections reports n/a, never a silent held",
         any(i["verdict"] == NA and "nothing is asserted" in i["note"]
             for i in check_page("p.md", GOOD, {"sections": [],
                                                "frontmatter": {"required": ["title"],
                                                                "optional": ["status", "scope"]}})))
    case("a genre declaring NO frontmatter rule reports n/a, never a silent held",
         any(i["verdict"] == NA and "no frontmatter rule" in i["note"]
             for i in check_page("p.md", GOOD, {"sections": []})))

    # ── the run-level rejects, on a seeded tree ───────────────────────────────────────────────
    import tempfile

    import yaml

    def tree(guardrail: dict, files: dict):
        tmp = pathlib.Path(tempfile.mkdtemp())
        (tmp / "guardrails").mkdir()
        (tmp / "guardrails" / "t.yaml").write_text(yaml.safe_dump(guardrail), encoding="utf-8")
        for rel, body in files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        return tmp

    G = {"spec_version": "mac.guardrail/1", "topic": "t",
         BLOCK: {"g1": {"path": f"{MANUAL}/patterns/" + "{p}.md", "shape": SHAPE}}}
    t = tree(G, {f"{MANUAL}/patterns/a.md": GOOD})
    f, c = run(t)
    case("the clean seeded tree is green, and its DENOMINATOR is printed",
         not [i for i in f if i["verdict"] == FAILED] and c["pages"] == 1
         and c["genres"]["g1"]["judged"] == 1)

    t = tree(G, {f"{MANUAL}/patterns/a.md": GOOD, f"{MANUAL}/orphan.md": GOOD})
    f, c = run(t)
    case("MUTANT a page no genre claims is REFUSED, not silently skipped",
         any(i["reject"] == "UNGOVERNED_PAGE" for i in f) and c["ungoverned"] == [f"{MANUAL}/orphan.md"])

    G2 = {**G, BLOCK: {**G[BLOCK], "g2": {"path": f"{MANUAL}/patterns/a.md", "shape": SHAPE}}}
    f, _ = run(tree(G2, {f"{MANUAL}/patterns/a.md": GOOD}))
    case("MUTANT one page claimed by TWO genres is REFUSED — there is no precedence rule",
         any(i["reject"] == "GENRE_OVERLAP" for i in f))

    GX = {**G, BLOCK: {"gx": {"path": f"{MANUAL}/keys/**",
                              "shape": {"exempt": True, "held_by": ["tools/not_on_disk.py"]}}}}
    f, _ = run(tree(GX, {f"{MANUAL}/keys/a.md": "# a\n"}))
    case("MUTANT an exemption held by a tool that does not exist is REFUSED",
         any(i["reject"] == "EXEMPT_UNHELD" for i in f))
    GX0 = {**G, BLOCK: {"gx": {"path": f"{MANUAL}/keys/**", "shape": {"exempt": True}}}}
    f, _ = run(tree(GX0, {f"{MANUAL}/keys/a.md": "# a\n"}))
    case("MUTANT an exemption naming NO holder at all is REFUSED",
         any(i["reject"] == "EXEMPT_UNHELD" for i in f))

    BAD = GOOD.replace("## The footgun, concretely\n\ny\n", "")
    GS = {**G, BLOCK: {"g1": {**G[BLOCK]["g1"],
                              "standing": [{"page": f"{MANUAL}/patterns/a.md",
                                            "reject": "SECTION_MISSING", "owner": "operator",
                                            "since": "2026-10-04"}]}}}
    f, c = run(tree(GS, {f"{MANUAL}/patterns/a.md": BAD}))
    case("a DECLARED standing failure is counted and named, and does not fail the gate",
         not [i for i in f if i["verdict"] == FAILED]
         and any(i["verdict"] == STANDING for i in f) and c["genres"]["g1"]["standing"] == 1)
    f, _ = run(tree(GS, {f"{MANUAL}/patterns/a.md": GOOD}))
    case("MUTANT a standing entry whose page now CONFORMS is REFUSED as stale",
         any(i["reject"] == "STANDING_STALE" for i in f))
    f, _ = run(tree(G, {f"{MANUAL}/patterns/a.md": BAD}))
    case("the SAME defect UNDECLARED fails the gate — only news exits 1, and this is news",
         any(i["reject"] == "SECTION_MISSING" and i["verdict"] == FAILED for i in f))

    case("every reject class this gate declares is seeded above",
         set(REJECTS) == {"FRONTMATTER_MISSING", "FRONTMATTER_UNPARSEABLE", "KEY_MISSING",
                          "KEY_UNDECLARED", "STATUS_UNDECLARED", "STATUS_FIRST_WORD_UNDECLARED",
                          "SECTION_MISSING", "NO_VARIANT", "NO_PURPOSE", "UNGOVERNED_PAGE",
                          "GENRE_OVERLAP", "EXEMPT_UNHELD", "STANDING_STALE"})

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": check_manual_page_shape self-test — {ok[1]}/{ok[0]} case(s), one mutant for each of "
            f"the {len(REJECTS)} reject classes plus the clean fixture, the two-variant canon shape, "
            f"and the standing list in both directions.")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())
