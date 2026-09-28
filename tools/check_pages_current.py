#!/usr/bin/env python3
"""check_pages_current.py — THE PAGE AN OPERATOR READS MATCHES WHAT THE SOURCE WOULD PRODUCE.

THE DEFECT THIS REPAIRS, AND IT IS MINE, 2026-09-28. Asked to put the PK position and the FK target on
the data plane's columns table, I changed the schema, the producer, the descriptors in three bundles and
four renderers — then reported it done while every DELIVERED page still showed the old table. The
operator looked, saw nothing, and was right: "when asked to change something then make is so that the
change is visible!"

WHY NOTHING CAUGHT IT, AND WHAT IS NOT THE REASON. `.gitignore` in the bundle repo carries `**/*.md`,
so a rendered page appears in no diff. That ignore is DELIBERATE and correct — the operator wrote it on
2026-08-13 and the file states the rule: "Tracked = the SSOT + config ... Ignored below = DERIVED
read-views", with a hand-built exception list (`decisions/*.md`, `*.why.md`, `RECONCILIATION.md`,
`acceptance/PROPERTIES.md`) because "AUTHORED rationale + decisions are NOT derived ... They MUST be
versioned." I first reported the ignore as the defect; it is not, and calling a deliberate design a flaw
was the second mistake of the same afternoon.

THE REASON IS SIMPLER. A derived page is declared "regenerable via --mode project" and NOTHING
REGENERATES IT WHEN THE SOURCE MOVES, nor checks that it has. Every gate in the estate reads the YAML
source of record; none reads the page. So the source ran three changes ahead of the page and thirteen
invariants passed. DNA's own law is the one that broke: "a produced file is not a delivered deliverable;
deliver where the operator looks."

WHAT IT DOES. Re-runs the page producers into a TEMPORARY directory and compares byte for byte with the
pages delivered in the bundle. A page that differs is STALE — the source moved and the page did not.
Nothing is written to the bundle, so the gate cannot "fix" a bundle into passing: it reports, and a
person re-runs the producer.

IT IS NOT A LINT ON CONTENT. It says only that the delivered page is what today's source renders. Whether
that rendering is any good is the renderer's business and a reader's judgement.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: (subdirectory under data/, glob) — the operator-facing pages the data-plane projector renders.
PAGES = (("sources", "*.md"), ("datasets", "*.md"), ("transforms", "*.md"))

ACCEPTED_SHAPE = """\
ACCEPTED SHAPE — a bundle root holding data/ with descriptors in data/sources and data/datasets.
usage: check_pages_current.py [bundle] [--diff]
"""


#: What a render does NOT need, and what would make the copy below expensive.
_SKIP = shutil.ignore_patterns("*.parquet", "*.duckdb", "*.duckdb.wal", "*.csv.gz", ".git",
                               ".harvest", ".harvest_cache", ".context")


def render_fresh(bundle: pathlib.Path, work: pathlib.Path) -> pathlib.Path:
    """Copy the bundle into `work`, render there, and return its data dir.

    THE PROJECTOR WRITES IN PLACE, BY DESIGN — build_data's own first line says "ONE tree: projected md
    co-locate WITH the SSOT under data_dir/<type>/ ... out_dir ignored". So a fresh render cannot be
    aimed at a temporary directory; the bundle has to be copied and rendered there instead. That is not
    a workaround to be embarrassed about: rendering beside the SSOT is what makes the page a DELIVERED
    artifact rather than a build output, which is the property DNA §P11 asks for. It just means a gate
    that wants an untouched comparison must bring its own copy.

    The copy skips the warehouse itself (parquet, duckdb) and the caches; a render reads YAML and prose.

    IT MUST RENDER THE WAY THE PROJECTOR RENDERS, LINEAGE INCLUDED. A bare `build_data()` drops the
    Lineage tab — `sdk/cli/harvest.py` says so three times ("it drops the Lineage view tab", "MUST be
    threaded into the projection", "so ad-hoc build_data() calls are never needed") — and this gate made
    exactly that ad-hoc call. Measured 2026-09-28, immediately after a clean projection of all three
    bundles: 18 transform pages across contoso2/3/4 reported STALE and every diff line was the missing
    Lineage table. A gate whose reference render is built differently from the artifact reports the
    DIFFERENCE BETWEEN ITS TWO RENDERERS as a defect in the delivery, and the repair it demands ("re-run
    the projector") cannot ever clear it. So the flows are threaded here from the projector's own helper
    rather than re-derived, for the same reason the pages have one renderer.
    """
    dst = work / bundle.name
    shutil.copytree(bundle, dst, ignore=_SKIP, dirs_exist_ok=True)
    from sdk.cli.harvest import _lineage_flows
    from sdk.project.project_data import build_data
    build_data(dst / "data", lineage=_lineage_flows(dst))
    return dst / "data"


def compare(data_dir: pathlib.Path, fresh: pathlib.Path) -> list:
    """(relpath, state, detail) per page. States: current | stale | missing | extra."""
    out = []
    for sub, pat in PAGES:
        want = {p.name: p for p in sorted((fresh / sub).glob(pat))} if (fresh / sub).is_dir() else {}
        have = {p.name: p for p in sorted((data_dir / sub).glob(pat))} if (data_dir / sub).is_dir() else {}
        for n in sorted(set(want) | set(have)):
            rel = f"{sub}/{n}"
            if n not in have:
                out.append((rel, "missing", "the producer renders this page and the bundle does not "
                                            "carry it — an undelivered deliverable"))
            elif n not in want:
                out.append((rel, "extra", "delivered but no producer renders it — left behind by a "
                                          "rename or a retired relation"))
            else:
                a = have[n].read_text(encoding="utf-8")
                b = want[n].read_text(encoding="utf-8")
                out.append((rel, "current", "matches what the source renders") if a == b else
                           (rel, "stale", f"differs from what today's source renders "
                                          f"({sum(1 for _ in difflib.unified_diff(a.splitlines(), b.splitlines())) } diff line(s))"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--diff", action="store_true", help="print the first differing hunk per stale page")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    root = pathlib.Path(a.bundle).resolve()
    data = root / "data"
    if not data.is_dir():
        print(f"COULD NOT RUN: {root.name} has no data/ plane, so no page can be compared. This is not "
              f"a pass.\n\n{ACCEPTED_SHAPE}")
        return 2
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mac-pages-"))
    try:
        try:
            fresh = render_fresh(root, tmp)
        except Exception as exc:                                    # noqa: BLE001
            print(f"COULD NOT RUN: the page producer failed ({type(exc).__name__}: {exc}), so nothing "
                  f"can be compared. A gate that cannot render must refuse, not pass."
                  f"\n\n{ACCEPTED_SHAPE}")
            return 2
        rows = compare(data, fresh)
        bad = [r for r in rows if r[1] != "current"]
        print(f"  PAGES CURRENT — {root.name}\n  {len(rows)} operator-facing page(s) compared against a "
              f"fresh render\n")
        for rel, state, detail in rows:
            if state != "current":
                print(f"  [{'FAIL'}] {rel:44} {state.upper()} — {detail}")
                if a.diff:
                    x = (data / rel).read_text(encoding="utf-8").splitlines() if (data / rel).is_file() else []
                    y = (fresh / rel).read_text(encoding="utf-8").splitlines() if (fresh / rel).is_file() else []
                    for ln in list(difflib.unified_diff(x, y, "delivered", "fresh", lineterm=""))[:12]:
                        print(f"           {ln}")
        if not rows:
            print("  NOTHING TO COMPARE — the producer rendered no page and the bundle carries none. "
                  "That is not a pass: a data plane with no operator-facing page is undelivered.")
            return 1
        if bad:
            # COUNT PAGES, NOT FINDINGS. One page can be both STALE and missing its legend, and
            # "2 of 24 pages" for one bad page is the kind of number this estate keeps removing.
            npages = len({r[0] for r in bad})
            print(f"\nFAIL: check_pages_current — {npages} of {len(rows)} page(s) are not what the "
                  f"source renders ({len(bad)} finding(s)). The page is what an operator READS: git now "
                  f"shows WHAT changed in one (they are tracked as of 2026-09-28, CONFORMANCE.md §2.5) "
                  f"and this gate shows what SHOULD have. Re-run the data-plane projector")
            return 1
        print(f"\nPASS: check_pages_current — {len(rows)} of {len(rows)} page(s) match what the source "
              f"renders")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _self_test() -> int:
    """The states, over a fabricated pair of trees — no bundle, no projector, no database."""
    cases = []
    def case(label, cond):
        cases.append((label, bool(cond)))
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mac-pages-st-"))
    try:
        d, f = tmp / "data", tmp / "fresh"
        for base in (d, f):
            (base / "sources").mkdir(parents=True)
            (base / "datasets").mkdir(parents=True)
        (d / "sources" / "same.md").write_text("| a |\n", encoding="utf-8")
        (f / "sources" / "same.md").write_text("| a |\n", encoding="utf-8")
        (d / "sources" / "old.md").write_text("| role |\n", encoding="utf-8")
        (f / "sources" / "old.md").write_text("| role | key |\n", encoding="utf-8")
        (f / "sources" / "new.md").write_text("| a |\n", encoding="utf-8")
        (d / "sources" / "gone.md").write_text("| a |\n", encoding="utf-8")
        got = {r[0]: r[1] for r in compare(d, f)}
        case("an identical page is current", got.get("sources/same.md") == "current")
        # THE REAL REGRESSION: the source grew a column and the delivered page did not.
        case("MUTANT a page the source has moved past is STALE", got.get("sources/old.md") == "stale")
        case("MUTANT a page the producer renders and the bundle lacks is MISSING",
             got.get("sources/new.md") == "missing")
        case("MUTANT a delivered page no producer renders is EXTRA",
             got.get("sources/gone.md") == "extra")
        case("every page gets exactly one verdict", len(got) == 4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [l for l, ok in cases if not ok]
    for l in bad:
        print(f"  FAIL  {l}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_pages_current self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_pages_current self-test — {n}/{n} case(s): identical is current, a page the "
          f"source has moved past is STALE, one the producer renders but the bundle lacks is MISSING, "
          f"and one delivered with no producer is EXTRA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
