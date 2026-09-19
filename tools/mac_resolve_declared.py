#!/usr/bin/env python3
"""THE DECLARATION RESOLVER — render `@cols:` / `@n:` / `@frag:` from the plane that declares them,
at run time, and REFUSE when a path does not resolve.

    PASS: mac_resolve_declared --self-test — 24 of 24 case(s) over 2 concept layout(s)
    (flat + foldered); 5 mutant(s) covering 5 reject class(es)

── WHY THIS MODULE EXISTS, AND WHY IT IS IN THE FRAMEWORK AND NOT IN A BUNDLE ──────────────────

`mac_vocabulary.yaml` splits the property kinds on OPPOSITE obligations:

    mac.test_kind.ground_truth   measures the world. Must NOT render its assertion from the
                                 declaration — its purpose is to DISAGREE when the declaration has
                                 gone stale. It types literals, and needs no resolver.
    mac.test_kind.conformance    renders EVERY asserted value from the declaration at run time.
                                 A typed literal IS the defect. It is all markers, and cannot run
                                 without a resolver.

`mac_generate_ontology_tests.py` therefore emits markers BY CONTRACT, and says so in its own
statements: *"The column list is READ from the concept at run time, never typed here — a typed key
would go on passing after the concept changed."*

MEASURED on a live two-plane bundle. `acceptance/ontology_generated.yaml` carries 46
markers over 20 distinct paths; `acceptance/data_sanity_generated.yaml` carries 0. The free
framework runner `run_suite.py` had NO marker resolution at all — `grep -n '@cols|@n:|@frag|resolve'`
returned two hits, both `Path(...).resolve()` — so it handed the marker text straight to DuckDB:

    Parser Error: syntax error at or near ":"
    LINE 2: FROM (SELECT @cols:concept:brand.grounding.sources.0.key FROM dim_contoso_pro...

20 of the suite's 33 properties died that way, 0 were examined, and nothing in the estate called it
a failure. THE CONFORMANCE TEST KIND HAD NO RUNNER IN THE FRAMEWORK. Every new bundle running the
framework's own generated conformance suite would ERROR on every marker-carrying property, by
construction; contoso was simply the first bundle to prove it.

The resolver existed — ONCE, and inside a BUNDLE rather than in the framework: one bundle's own local
`tools/run_properties.py` carried the marker regex, a fragment resolver and a declaration resolver, and
applied the last of them immediately before each query. That bundle's comparable suite ran 41 declared
/ 41 examined / 36 PASS / 5 FAIL on the SAME generator and the SAME marker grammar. Same suite kind,
two runners, one resolves and one does not.

AND THE PER-BUNDLE HOME IS WHAT HID IT. A SECOND bundle's `tools/run_properties.py` defines

    def resolve_declared(text) -> str:   # "here it means: nothing to resolve"
        return text

— a NAMESPACE resolver satisfying `_plugin.required`, sharing one name with the other bundle's MARKER
resolver.
Anyone looking for the marker resolver finds a function of the right name doing nothing. One name,
two jobs, and the silent one won. `_plugin.py` already names this as the worse of two failure modes:
*"the silent identity fallback leaves every @cols: slot unresolved, every parse fails."*

So the algorithm lives HERE, once, and a bundle declares which planes it has.

── IT REFUSES, IT NEVER GUESSES ────────────────────────────────────────────────────────────────

Every failure raises `Unresolved`. NOTHING is substituted for a path that does not resolve, because
the alternative was measured in this estate: a test partitioned on six columns while reporting
seven, and both halves agreed with each other and with nothing else. A renamed descriptor or a
mistyped path fails LOUDLY, as an ERROR on that property, naming the marker and the file it looked
in — which is a finding about the declaration, not a green.

── THE REJECT CLASSES ──────────────────────────────────────────────────────────────────────────

    NO_PLANE_FILE   the marker names a document no plane holds (`@cols:concept:nope.x`). Includes
                    the FOLDERED case: a live bundle files all 17 of its concepts under subject
                    folders, so a
                    depth-0 `concepts/*.yaml` lookup finds none of them. Resolution goes through
                    `mac_project.concept_files`, which walks both layouts — the same defect that
                    already bit eight gates.
    NO_SUCH_PATH    the document exists and declares no such path (`grounding.sources.9.key`).
    EMPTY_VALUE     the path resolves to an empty list, or to a values list whose members carry no
                    `code`. Rendering nothing here is what puts an empty column list into a
                    `GROUP BY`.
    NOT_RENDERABLE  the path resolves to a mapping or a number — not a string and not a list — so
                    there is no column list or count to render.
    NO_FRAGMENT     an `@frag:` marker with no `protosql_render` reachable, or a fragment id that
                    renderer refuses. `protosql_render` has its OWN slot grammar (`@cols:<bare>`)
                    and is a SIBLING of this module, not its home; this module delegates and
                    refuses, it does not re-implement.

Usage
    python3 tools/mac_resolve_declared.py <bundle> --sql "SELECT @cols:concept:brand.…"
    python3 tools/mac_resolve_declared.py <bundle> --suite acceptance/ontology_generated.yaml
    python3 tools/mac_resolve_declared.py --self-test
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mac_project as P  # noqa: E402

VERSION = "mac_resolve_declared.py/1"

#: The declaration grammar, verbatim from the one working implementation in the estate
#: (a bundle-local `tools/run_properties.py`) so a suite written for either runner resolves identically.
#: `cols` renders the members; `n` renders how many there are.
_DECL = re.compile(r"@(cols|n):((?:concept:|profile:|transform:)?[A-Za-z0-9_]+)\.([A-Za-z0-9_.\-]+)")

#: `@frag:<rule.id>(fact=<relation>)` — a rendered ontology fragment. Different grammar, different
#: renderer, delegated below.
_FRAG = re.compile(r"@frag:([A-Za-z0-9_.]+)\(fact=([A-Za-z0-9_]+)\)")


class Unresolved(RuntimeError):
    """A marker that could not be rendered. Carries its reject class so a caller can attribute it."""

    def __init__(self, cls: str, marker: str, detail: str):
        self.cls, self.marker = cls, detail and marker
        super().__init__(f"{cls}: {marker} — {detail}")


def _concept_index(root: Path) -> dict:
    """Concept documents by FILE STEM and by `concept.name`, over BOTH layouts.

    THE GENERATORS KEY BY FILE STEM. `mac_generate_ontology_tests.py:173` writes
    `@cols:concept:{path.stem}.…`, so the stem is the primary key; `concept.name` is accepted as
    well because a hand-authored conformance property naturally names the concept.

    FOLDERED AND FLAT, through `mac_project.concept_files`. A depth-0 glob here would resolve NONE
    of contoso's 17 concepts and every conformance property would refuse — turning a runner defect
    into a resolver defect and changing nothing about the 0 examined."""
    idx: dict = {}
    for f in P.concept_files(root):
        idx.setdefault(f.stem, f)
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        name = ((doc.get("concept") or {}).get("name"))
        if name:
            idx.setdefault(str(name), f)
    return idx


def _plane_file(root: Path, dataset: str, marker: str) -> Path:
    """The document a marker's plane prefix names.

    FOUR PLANES, because a conformance assertion must be rendered from whichever plane DECLARES it:
    `concept:` the ontology, `profile:` the measurement, `transform:` what a transform claims it
    produces, a bare stem the descriptor (served first, then raw — a served dataset and its landing
    share a stem in some bundles and the served one is what a suite asserts over)."""
    if dataset.startswith("concept:"):
        want = dataset.split(":", 1)[1]
        f = _concept_index(root).get(want)
        if f is None:
            where = P.rel(root, P.concepts_dir(root))
            raise Unresolved("NO_PLANE_FILE", marker,
                             f"no concept document named `{want}` under {where}/ "
                             f"(searched flat and foldered)")
        return f
    if dataset.startswith("profile:"):
        cands = [root / "data" / "profiles" / f"{dataset.split(':', 1)[1]}.yaml"]
    elif dataset.startswith("transform:"):
        cands = [root / "data" / "transforms" / f"{dataset.split(':', 1)[1]}.yaml"]
    else:
        cands = [root / "data" / "datasets" / f"{dataset}.yaml",
                 root / "data" / "sources" / f"{dataset}.yaml"]
    for c in cands:
        if c.is_file():
            return c
    raise Unresolved("NO_PLANE_FILE", marker,
                     "nothing at " + " or ".join(P.rel(root, c) for c in cands))


def _walk(doc, path: str, marker: str, fname: str):
    """Follow a dotted path, INCLUDING LIST INDICES.

    List indices are what lets a path reach `grounding.sources.0.key`. Without them a conformance
    test could not dereference a concept's key at all — which is exactly why the generator typed the
    columns instead, for four versions, while its own statement claimed they were read at run time."""
    cur = doc
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
                continue
            except (ValueError, IndexError):
                raise Unresolved("NO_SUCH_PATH", marker,
                                 f"{fname} has no `{path}` (list has {len(cur)} item(s))")
        if not isinstance(cur, dict) or part not in cur:
            raise Unresolved("NO_SUCH_PATH", marker, f"{fname} declares no `{path}`")
        cur = cur[part]
    return cur


def _render(kind: str, value, path: str, marker: str, fname: str) -> str:
    """A resolved value as SQL text: `cols` renders the members, `n` renders the count.

    A key may be declared as a single STRING or as a LIST — `grounding.sources[].key` does both, and
    refusing the scalar made every conformance test on a single-column key unresolvable."""
    if isinstance(value, str):
        value = [value]
    if isinstance(value, dict) or isinstance(value, (int, float, bool)) or value is None:
        raise Unresolved("NOT_RENDERABLE", marker,
                         f"{fname}#{path} is {type(value).__name__}, not a string or a list")
    if not isinstance(value, list):
        raise Unresolved("NOT_RENDERABLE", marker,
                         f"{fname}#{path} is {type(value).__name__}, not a string or a list")
    # a values.items[] list holds mappings; the renderable part is the code
    quoted = any(isinstance(c, dict) for c in value) or path.endswith(("items", "values"))
    flat = [c.get("code") if isinstance(c, dict) else c for c in value]
    flat = [c for c in flat if c is not None]
    if not flat:
        raise Unresolved("EMPTY_VALUE", marker,
                         f"{fname}#{path} renders to nothing — an empty column list in a GROUP BY "
                         f"is the defect this refusal exists to prevent")
    if kind == "n":
        return str(len(flat))
    if quoted:
        return ", ".join("'" + str(c).replace("'", "''") + "'" for c in flat)
    return ", ".join(str(c) for c in flat)


def resolve_fragments(root: Path, sql: str) -> str:
    """`@frag:<rule.id>(fact=<rel>)` -> the fragment's CTE list plus a final `pinned` CTE.

    DELEGATED TO `protosql_render`, never re-implemented: that module owns the fragment grammar and
    its own `@cols:<bare>` slots. A fragment that cannot be rendered REFUSES — a caller writing
    `WITH @frag:…` and selecting `FROM pinned` gets a parse error otherwise, which reads as a bad
    property rather than an absent renderer."""
    if not _FRAG.search(sql):
        return sql
    try:
        from protosql_render import render as _render_frag
    except ImportError as exc:  # pragma: no cover - protosql_render ships with the framework
        raise Unresolved("NO_FRAGMENT", "@frag:", f"protosql_render is unreachable ({exc})")

    def sub(m):
        frag_id, rel = m.group(1), m.group(2)
        marker = f"@frag:{frag_id}(fact={rel})"
        try:
            body, _prov = _render_frag(str(root), frag_id, {"fact": rel})
        except Exception as exc:
            raise Unresolved("NO_FRAGMENT", marker, str(exc)[:200])
        txt = (body or "").strip().rstrip(";")
        if not txt:
            raise Unresolved("NO_FRAGMENT", marker, "the renderer returned an empty body")
        low = txt.lower()
        if not low.startswith("with"):
            return f"pinned AS ({txt})"
        # Balanced-paren scan, not sqlglot: `tree.set("with", None)` silently did NOT remove the
        # WITH, so the fragment came back NESTED inside the caller's CTE and its internal names went
        # invisible — valid SQL, wrong scope, no error.
        i, n = 4, len(txt)
        while i < n:
            while i < n and txt[i] in " \t\r\n,":
                i += 1
            j = txt.find("(", i)
            if j < 0:
                break
            depth, k = 1, j + 1
            while k < n and depth:
                depth += (txt[k] == "(") - (txt[k] == ")")
                k += 1
            i = k
            while i < n and txt[i] in " \t\r\n":
                i += 1
            if i < n and txt[i] == ",":
                continue
            break
        ctes, tail = txt[4:i].strip(), txt[i:].strip()
        return f"{ctes}, pinned AS ({tail})"
    return _FRAG.sub(sub, sql)


def resolve_declared(root, sql: str) -> str:
    """Render every declaration marker in `sql` against `root`'s planes, or raise `Unresolved`.

    THE ONE ENTRY POINT. `run_suite.py` calls this before `eng.query()`; a bundle-local runner that
    wants the same behaviour imports it rather than redefining a function of the same name."""
    if not sql:
        return sql
    root = Path(root)
    sql = resolve_fragments(root, sql)
    if not _DECL.search(sql):
        return sql
    cache: dict = {}

    def sub(m):
        kind, dataset, path = m.groups()
        marker = m.group(0)
        f = _plane_file(root, dataset, marker)
        if f not in cache:
            try:
                cache[f] = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                raise Unresolved("NO_PLANE_FILE", marker, f"{P.rel(root, f)} did not parse ({exc})")
        doc = cache[f]
        # `values.served_items` — the codes a concept STILL admits, i.e. items not marked
        # `served: false`. COMPUTED, never stored: the flags already say which labels are withheld,
        # and a second list would drift from them the first time one was added.
        if path.endswith("values.served_items"):
            items = ((doc.get("values") or {}).get("items")) or []
            keep = [i.get("code") for i in items
                    if isinstance(i, dict) and i.get("served") is not False and i.get("code")]
            if not keep:
                raise Unresolved("EMPTY_VALUE", marker,
                                 f"{f.name}#values.items admits no served item")
            return (str(len(keep)) if kind == "n"
                    else ", ".join("'" + str(c).replace("'", "''") + "'" for c in keep))
        return _render(kind, _walk(doc, path, marker, f.name), path, marker, f.name)
    return _DECL.sub(sub, sql)


def markers_in(sql: str) -> list[str]:
    """Every declaration marker in `sql`, in order of appearance. Used by the suite mode below and
    by anything that wants to report what a property depends on without resolving it."""
    return [m.group(0) for m in _DECL.finditer(sql or "")] + \
           [m.group(0) for m in _FRAG.finditer(sql or "")]


# ── SELF-TEST ───────────────────────────────────────────────────────────────────────────────────
# One mutant per reject class, plus the clean cases the mutants are mutations OF, plus the FOLDERED
# layout — because the depth-0 concept glob is the live defect this estate has already paid for eight
# times, and a resolver that only passes on a flat bundle resolves nothing in contoso.

_CLEAN_CONCEPT = {
    "concept": {"name": "Brand", "identity": {"canonical_key": "BrandName"}},
    "grounding": {"sources": [{"relation": "srv.dim_product", "key": "BrandName"}]},
    "values": {"items": [{"code": "Contoso"}, {"code": "Fabrikam"}, {"code": "Litware"}]},
}


def _seed(tmp: Path, foldered: bool) -> Path:
    """Two REAL layouts, not two spellings of one.

    `flat` is the framework default: no manifest, `concepts/` at the root — which is what
    `mac_project.resolve` falls back to. `foldered` is the two-plane manifest layout with concepts under
    a subject folder — which is what a live two-plane bundle has, and the layout a depth-0 glob
    resolves NONE of."""
    root = tmp / ("foldered" if foldered else "flat")
    cdir = (root / "ontology" / "concepts" / "catalog") if foldered else (root / "concepts")
    cdir.mkdir(parents=True, exist_ok=True)
    if foldered:
        (root / "mac.project.yaml").write_text(
            yaml.safe_dump({"planes": {"data": "data", "ontology": "ontology"},
                            "descriptors": "data/datasets", "sources": "data/sources",
                            "transforms": "data/transforms"}), encoding="utf-8")
    (cdir / "brand.yaml").write_text(yaml.safe_dump(_CLEAN_CONCEPT), encoding="utf-8")
    (root / "data" / "profiles").mkdir(parents=True, exist_ok=True)
    (root / "data" / "profiles" / "dim_product.yaml").write_text(
        yaml.safe_dump({"relation": "srv.dim_product",
                        "identity_evidence": {"key": ["ProductKey", "Version"]}}), encoding="utf-8")
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets" / "dim_product.yaml").write_text(
        yaml.safe_dump({"table": {"name": "dim_product", "schema": "srv"},
                        "columns": [{"name": "ProductKey"}]}), encoding="utf-8")
    return root


#: (name, sql, expected reject class or None, why this case is here)
_CASES = (
    ("cols_scalar_key", "SELECT @cols:concept:brand.grounding.sources.0.key", None,
     "a key declared as a STRING renders — refusing the scalar made every single-column "
     "conformance test unresolvable"),
    ("cols_by_concept_name", "SELECT @cols:concept:Brand.concept.identity.canonical_key", None,
     "a hand-authored property may name the CONCEPT rather than the file stem; the generators "
     "write the stem, so both must resolve"),
    ("cols_list_key", "SELECT @cols:profile:dim_product.identity_evidence.key", None,
     "a composite key renders as a comma list, which is what a GROUP BY needs"),
    ("n_of_items", "SELECT @n:concept:brand.values.items", None,
     "`n` renders the COUNT, and a values list renders its member codes"),
    ("cols_of_items", "SELECT @cols:concept:brand.values.items", None,
     "value-set members are QUOTED; a column list is not"),
    ("descriptor_plane", "SELECT @cols:dim_product.table.name", None,
     "a bare stem resolves through the descriptor"),
    ("no_markers", "SELECT 1", None, "a marker-free property is returned untouched"),
    # ── the mutants, one per reject class ──
    ("NO_PLANE_FILE", "SELECT @cols:concept:nope.identity.canonical_key", "NO_PLANE_FILE",
     "a marker naming a document no plane holds must refuse, never render nothing"),
    ("NO_SUCH_PATH", "SELECT @cols:concept:brand.grounding.sources.9.key", "NO_SUCH_PATH",
     "an index past the end of a list is a mistyped path, not an empty column list"),
    ("EMPTY_VALUE", "SELECT @cols:concept:empty.values.items", "EMPTY_VALUE",
     "an empty list must refuse — this is the partition-on-six-report-seven defect"),
    ("NOT_RENDERABLE", "SELECT @cols:concept:brand.grounding", "NOT_RENDERABLE",
     "a mapping has no column list to render"),
    ("NO_FRAGMENT", "WITH @frag:no.such.rule(fact=dim_product) SELECT * FROM pinned", "NO_FRAGMENT",
     "a fragment the renderer refuses must refuse here too, not reach the engine as text"),
)


def _self_test() -> int:
    import tempfile
    bad, n = 0, 0
    mutants = sum(1 for c in _CASES if c[2])
    classes = sorted({c[2] for c in _CASES if c[2]})
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for foldered in (False, True):
            root = _seed(tmp, foldered)
            # EMPTY_VALUE needs a concept whose value set is present and empty — a declared
            # closure with no members, which is how the defect actually arrives.
            ed = (root / "ontology" / "concepts" / "catalog") if foldered else (root / "concepts")
            (ed / "empty.yaml").write_text(
                yaml.safe_dump({"concept": {"name": "Empty"}, "values": {"items": []}}),
                encoding="utf-8")
            layout = "foldered" if foldered else "flat"
            for name, sql, want, why in _CASES:
                n += 1
                try:
                    out = resolve_declared(root, sql)
                    got, detail = None, out
                except Unresolved as exc:
                    got, detail = exc.cls, str(exc)
                except Exception as exc:  # a traceback is not a verdict
                    got, detail = f"CRASH({type(exc).__name__})", str(exc)
                ok = got == want
                # A marker left in the output is the silent-substitution failure wearing a green.
                if ok and want is None and _DECL.search(detail):
                    ok, detail = False, f"marker survived resolution: {detail}"
                if not ok:
                    bad += 1
                    print(f"  FAIL [{layout}] {name}: expected "
                          f"{want or 'a resolution'}, got {got or 'a resolution'} — {detail[:160]}")
                else:
                    print(f"  ok   [{layout}] {name:<22} {(got or detail)[:88]}")
    verdict = "PASS" if not bad else "FAIL"
    print(f"\n{verdict}: {VERSION} --self-test — {n - bad} of {n} case(s) over 2 concept layout(s) "
          f"(flat + foldered); {mutants} mutant(s) covering {len(classes)} reject class(es): "
          f"{', '.join(classes)}")
    if not bad:
        print("  Every mutant is asserted to RAISE with its own class — a resolver that substituted "
              "nothing would pass the clean cases and fail these.")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--sql", help="resolve one statement and print it")
    ap.add_argument("--suite", help="resolve every property's sql in this suite and report")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    root = Path(a.bundle).resolve()
    if a.sql:
        try:
            print(resolve_declared(root, a.sql))
            return 0
        except Unresolved as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
    if a.suite:
        doc = yaml.safe_load((root / a.suite).read_text(encoding="utf-8")) or {}
        props = [p for p in (doc.get("properties") or []) if isinstance(p, dict)]
        carrying = [p for p in props if markers_in(p.get("sql") or "")]
        ok, refused = 0, []
        for p in carrying:
            try:
                resolve_declared(root, p["sql"])
                ok += 1
            except Unresolved as exc:
                refused.append((p.get("id"), exc))
        for pid, exc in refused:
            print(f"  REFUSED {pid}: {exc}")
        n = len(carrying)
        verdict = "PASS" if not refused else "FAIL"
        print(f"{verdict}: {VERSION} — {ok} of {n} marker-carrying propert"
              f"{'y' if n == 1 else 'ies'} resolve, of {len(props)} declared in {a.suite}")
        return 1 if refused else 0
    ap.error("one of --sql, --suite or --self-test is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
