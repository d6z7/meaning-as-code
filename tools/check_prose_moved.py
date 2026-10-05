#!/usr/bin/env python3
"""check_prose_moved — every sentence of prose a concept dropped must be findable somewhere else.

WHY THIS EXISTS, and it is a correction of my own method. On 2026-10-05 store.yaml's prose was moved
out by hand and the move was verified with TOKEN PROBES — did `67`, `74`, `RC05`, `1 504` still appear
somewhere? They did, all sixteen of them, so the migration was reported as lossless. It was not.
Measured when the operator asked where the prose had gone: of 92 prose sentences in the original,
21 were already word-for-word in the narrative and **45 — 6 253 bytes — were in no new home at all**.

THE PROBE PASSED WHILE THE ARGUMENT DIED, which is the whole lesson. A distinctive number survives in
one summarising sentence; the reasoning that made the number mean something does not. What was lost
was exactly what a reader reads prose FOR: that `closed` and `active` partition all 74 rows BY
CONSTRUCTION, 16 + 58, "so there is nothing to verify and no way to author an overlap or a gap"; that
`shut` is named apart from `closed` because "one word cannot denote two sets", RC08 approved at 9
against STORE-02's 57; that `shut` and `restructured` were DERIVED from the rows (0 of 8, 6 of 6)
rather than chosen.

SO THE UNIT IS THE SENTENCE, NOT THE TOKEN. This takes a git revision as the BEFORE, extracts every
prose sentence a concept document carried then — block scalars, long inline values, and `#` comments,
which are prose with no reader and the first thing a migration drops — and asks whether each is still
findable across the AFTER corpus: the concept document, its narrative, its rule pages, the bundle's
knowledge plane, and the framework pages a generic fact may legitimately have been promoted to.

MATCHED ON A NORMALISED PREFIX, not on equality, because a migration is allowed to re-wrap, re-punctuate
and merge. It is NOT allowed to lose the claim. The prefix is long enough that two different claims do
not collide and short enough that re-wrapping does not break the match; `--prefix` moves it and the
verdict prints what was used.

    python3 tools/check_prose_moved.py <bundle> --since HEAD~1
    python3 tools/check_prose_moved.py <bundle> --since HEAD~1 --concept store
    python3 tools/check_prose_moved.py --self-test

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, denominators printed,
and `--self-test` with one mutant per reject class.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P  # noqa: E402  — ONE home for where a bundle keeps its concepts

#: Shorter than this is a fragment, not a claim: a YAML key echo ("role: dimension"), a list item, a
#: clause continuation. 45 was measured on store.yaml — below it the extraction is mostly structure.
MIN_SENTENCE = 45
#: How much of a normalised sentence must survive. 55 characters distinguished all 92 of store.yaml's
#: sentences from one another while tolerating every re-wrap the migration made.
PREFIX = 55

_FW = pathlib.Path(__file__).resolve().parent.parent / "reference_manual"


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", t.lower())).strip()


def sentences(text: str) -> list[str]:
    """Every prose sentence in a concept document — block scalars, long values, and comments."""
    parts: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("#"):
            parts.append(s.lstrip("#:").strip())
            continue
        m = re.match(r"^(?:-\s*)?[A-Za-z0-9_\-]+:\s*(.*)$", s)
        if m:
            v = m.group(1).strip()
            if v and v not in {">", "|", ">-", "|-", ">+", "|+"} and len(v) > MIN_SENTENCE:
                parts.append(v)
            continue
        parts.append(s)
    joined = " ".join(p for p in parts if p)
    return [re.sub(r"\s+", " ", x).strip()
            for x in re.split(r"(?<=[.!?])\s+", joined)
            if len(x.strip()) > MIN_SENTENCE]


def _git_show(repo: pathlib.Path, rev: str, rel: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=repo,
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _repo_of(path: pathlib.Path) -> pathlib.Path | None:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                       capture_output=True, text=True)
    return pathlib.Path(r.stdout.strip()) if r.returncode == 0 else None


def after_corpus(root: pathlib.Path, stem: str) -> str:
    """Everywhere a sentence may legitimately have moved TO."""
    cdir = P.concepts_dir(root)
    out: list[str] = []
    for p in [cdir / f"{stem}.yaml", cdir / f"{stem}.md"]:
        if p.is_file():
            out.append(p.read_text(encoding="utf-8"))
    rules = cdir / "rules"
    if rules.is_dir():
        out += [p.read_text(encoding="utf-8") for p in rules.glob(f"{stem}.*.md")]
    # THE KNOWLEDGE PLANE, which is where the operator ruled this prose belongs: "the yaml belongs
    # back to concepts but prosa is in knowledge documents ... because it is human readable
    # collection of implementations in the code" (2026-10-05).
    for k in (root / "knowledge",):
        if k.is_dir():
            out += [p.read_text(encoding="utf-8") for p in k.glob("*.md")]
    # AND THE FRAMEWORK, because a GENERIC fact is legitimately promoted rather than moved sideways:
    # two of store.yaml's comments were true of every bundle binding population_select and belong on
    # that canon's page, not in any bundle.
    if _FW.is_dir():
        out += [p.read_text(encoding="utf-8") for p in _FW.rglob("*.md")]
    return norm(" ".join(out))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--since", default="HEAD~1", help="the revision to take as BEFORE")
    ap.add_argument("--concept", help="one concept stem, else every concept")
    ap.add_argument("--prefix", type=int, default=PREFIX)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    repo = _repo_of(root)
    if repo is None:
        print(f"REFUSED: {root} is not inside a git checkout — there is no BEFORE to compare")
        return 2
    files = [f for f in P.concept_files(root) if not a.concept or f.stem == a.concept]
    if not files:
        print(f"REFUSED: no concept document under {P.concepts_dir(root)}"
              + (f" matching {a.concept!r}" if a.concept else ""))
        return 2

    lost: list[tuple[str, str]] = []
    n_before = n_checked = 0
    for f in files:
        rel = str(f.relative_to(repo))
        before = _git_show(repo, a.since, rel)
        if before is None:
            continue                      # new file at this revision: nothing was dropped from it
        olds = sentences(before)
        n_before += len(olds)
        if not olds:
            continue
        corpus = after_corpus(root, f.stem)
        for s in olds:
            key = norm(s)[: a.prefix]
            if not key:
                continue
            n_checked += 1
            if key not in corpus:
                lost.append((f.stem, s))

    denom = (f"{len(files)} concept(s), {n_before} prose sentence(s) at {a.since}, "
             f"{n_checked} judged at a {a.prefix}-char prefix")
    if lost:
        for stem, s in lost[:30]:
            print(f"  [prose-lost] {stem} — {s[:140]}")
        if len(lost) > 30:
            print(f"  … {len(lost) - 30} more")
        print(f"\nFAIL: check_prose_moved — {len(lost)} sentence(s) "
              f"({sum(len(s) for _, s in lost)} bytes) in no new home, over {denom}")
        return 1
    print(f"PASS: check_prose_moved — every sentence is still findable, over {denom}")
    return 0


def _self_test() -> int:
    checks = 0
    bad: list[str] = []

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            bad.append(msg)

    SENT = ("A store is its code and a row is a trading period, which is why the count is "
            "sixty-seven and not seventy-four across this relation.")
    YAML_BEFORE = f"concept:\n  name: Thing\n  definition: >-\n    {SENT}\n"
    YAML_AFTER = "concept:\n  name: Thing\n  definition: >-\n    A store. The account is thing.md.\n"

    def repo(tmp, after_md: str | None):
        r = pathlib.Path(tmp)
        subprocess.run(["git", "init", "-q", str(r)], check=True)
        subprocess.run(["git", "-C", str(r), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(r), "config", "user.name", "t"], check=True)
        (r / "mac.project.yaml").write_text("planes:\n  ontology: ontology\n", encoding="utf-8")
        c = r / "ontology" / "concepts"
        c.mkdir(parents=True)
        (c / "thing.yaml").write_text(YAML_BEFORE, encoding="utf-8")
        subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(r), "commit", "-qm", "before"], check=True)
        (c / "thing.yaml").write_text(YAML_AFTER, encoding="utf-8")
        if after_md is not None:
            (c / "thing.md").write_text(after_md, encoding="utf-8")
        return r

    with tempfile.TemporaryDirectory() as t:
        # dropped and NOT rehomed -> reject
        expect(main([str(repo(t, None)), "--since", "HEAD"]) == 1,
               "a dropped sentence with no new home must reject")
    with tempfile.TemporaryDirectory() as t:
        # dropped and rehomed VERBATIM -> pass
        expect(main([str(repo(t, SENT + "\n")), "--since", "HEAD"]) == 0,
               "a sentence rehomed verbatim must pass")
    with tempfile.TemporaryDirectory() as t:
        # dropped and rehomed RE-WRAPPED -> pass; the unit is the claim, not the layout
        rewrapped = SENT.replace(", which is", ",\nwhich is").replace(" and a row", "\nand a row")
        expect(main([str(repo(t, rewrapped + "\n")), "--since", "HEAD"]) == 0,
               "a re-wrapped sentence must still match")
    with tempfile.TemporaryDirectory() as t:
        # rehomed but TRUNCATED past the prefix -> reject; losing the claim is not re-wrapping
        expect(main([str(repo(t, SENT[:30] + "\n")), "--since", "HEAD"]) == 1,
               "a sentence truncated past the prefix must reject")
    with tempfile.TemporaryDirectory() as t:
        r = pathlib.Path(t)
        (r / "mac.project.yaml").write_text("planes:\n  ontology: ontology\n", encoding="utf-8")
        (r / "ontology" / "concepts").mkdir(parents=True)
        expect(main([str(r)]) == 2, "no git checkout must refuse, not pass")

    if bad:
        for b in bad:
            print(f"  [SELF-TEST] {b}")
        print(f"FAIL: check_prose_moved self-test — {len(bad)} of {checks} failed")
        return 1
    print(f"PASS: check_prose_moved self-test — {checks}/{checks} check(s): lost, verbatim, "
          f"re-wrapped, truncated, and the refusal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
