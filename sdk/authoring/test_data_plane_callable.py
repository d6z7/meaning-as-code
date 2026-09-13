#!/usr/bin/env python3
"""Offline proof that `data_plane.process()` can actually be CALLED — an AST scope check.

WHY THIS FILE EXISTS, measured. On 2026-09-13, commit `93ca8a6` (01:26) made
`profile_table(..., *, workgroup: str)` a REQUIRED keyword — deliberately, to stop one ontology's
Athena workgroup being compiled into the tooling that serves every ontology — and did not thread the
value through the only caller. `process()` was left referencing the bare name `workgroup`, which is
not one of its fourteen parameters, not assigned anywhere in its body, not a module-level binding and
not a builtin. Every call raised `NameError` on its first statement.

Eighty-eight tests passed over it. They could not have caught it: the one production caller
(`sdk.cli.harvest.harvest_data`) is unreachable in this repository, because `profile_table` imports
`chat.sql`, which lives in another repo — `importlib.util.find_spec("chat")` is `None` here. A crash
on a dead path is invisible to every test that runs live paths. So the instrument must be one that
never executes the function: read its AST and resolve its names by Python's own scope rules.

WHAT THIS CHECKS, and deliberately what it does NOT. It is not "the string 'workgroup' is absent" —
that check would have gone green the moment the one bug it was written for was fixed, and stayed
green through the next one. It is the general property: **every name LOADED in the function resolves
to a parameter, a binding in its own scope, a module-level binding, an import, or a builtin.** The
next unbound name in `process()` — or in any other function in the module — fails it too.

Four properties, because the bug had two halves and the instrument needs its own teeth:

  1. `process()` loads no name that cannot be resolved   — the crash itself.
  2. no function in data_plane.py does                    — the ratchet, so the next one is caught.
  3. `harvest_data -> process -> profile_table` passes every REQUIRED keyword-only parameter of the
     callee — the caller-side half, which is the shape commit `93ca8a6` actually had: a keyword made
     required in one file with no caller updated. Its failure mode is a TypeError on the same dead
     path, equally invisible to every test that runs.
  4. a bundle that declares no workgroup is REFUSED, loudly, before anything is billed — the value
     `process()` now demands really does come from the bundle, and its absence is not a default.

The checker itself carries a denominator and its own mutants. A checker that reports clean having
examined nothing is this estate's dominant defect, and an AST walk that silently matches no node is
exactly that shape: `test_scan_examines_a_real_population` pins the count, and
`test_scan_rejects_each_unbound_shape` seeds one mutant per way a name can be unbound, so a scan
that stops resolving anything fails instead of passing.
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root -> `sdk` importable
from sdk.cli import harvest

_DATA_PLANE = Path(__file__).resolve().parent / "data_plane.py"

# A def/lambda/class/comprehension opens its OWN namespace. Names bound inside one are NOT bound in
# the scope that contains it (comprehensions included — that has been true since Python 3), so the
# binding collector must stop at these and the load walker must descend with a widened scope.
_OWN_SCOPE = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)

_BUILTINS = frozenset(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__"}


def _stored(node) -> set[str]:
    """The names one binding construct binds — tuple, star and nested targets included.

    Only Store/Del contexts count, which is what makes `d[k] = v` and `obj.attr = v` correctly bind
    NOTHING while still reading `d`, `k` and `obj` as loads elsewhere.
    """
    return {
        n.id
        for n in ast.walk(node)
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))
    }


def _scope_bindings(scope) -> set[str]:
    """Every name bound in THIS scope's own namespace, from every binding form Python has.

    Python binds for the whole scope, not from the assignment line onward, so this collects the
    entire body before any load is judged. Reading a name that is assigned only LATER is an
    `UnboundLocalError`, a different defect from the one measured here, and is deliberately out of
    scope for this check.

    `global`/`nonlocal` statements are deliberately NOT treated as bindings: `global wg` followed by
    a read of `wg` that nothing ever assigns is precisely the NameError this file exists to catch.
    """
    out: set[str] = set()

    def walk(node) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(child.name)  # the def binds its NAME here; its body is another namespace
                continue
            if isinstance(child, _OWN_SCOPE):  # lambda / comprehension: binds nothing out here
                continue
            if isinstance(child, ast.Assign):
                for t in child.targets:
                    out.update(_stored(t))  # .update, not `|=`: `|=` would rebind `out` as a local
            elif isinstance(child, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
                out.update(_stored(child.target))
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                out.update(_stored(child.target))
            elif isinstance(child, (ast.With, ast.AsyncWith)):
                for item in child.items:
                    if item.optional_vars is not None:
                        out.update(_stored(item.optional_vars))
            elif isinstance(child, ast.ExceptHandler) and child.name:
                out.add(child.name)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    out.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(child, (ast.MatchAs, ast.MatchStar)) and child.name:
                out.add(child.name)
            elif isinstance(child, ast.MatchMapping) and child.rest:
                out.add(child.rest)
            walk(child)

    walk(scope)
    return out


def _params(fn) -> set[str]:
    a = fn.args
    names = {p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)}
    return names | {x.arg for x in (a.vararg, a.kwarg) if x is not None}


def _scan(node, outer: frozenset[str]) -> tuple[list[tuple[str, int]], int]:
    """-> (unbound loads as (name, lineno), number of loaded names examined).

    The second value is the denominator. This walk is reported as a PASS when it finds nothing, so
    it must also say how much it looked at — a scan that matched no node would otherwise be
    indistinguishable from a clean function.
    """
    findings: list[tuple[str, int]] = []
    examined = 0

    def visit(n, bound: frozenset[str]) -> None:
        nonlocal examined
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # Defaults and decorators are evaluated in the ENCLOSING scope, the body in the new one.
            for d in (
                *n.args.defaults,
                *[k for k in n.args.kw_defaults if k is not None],
                *getattr(n, "decorator_list", []),
            ):
                visit(d, bound)
            inner = bound | _params(n) | _scope_bindings(n)
            for st in n.body if isinstance(n.body, list) else [n.body]:
                visit(st, inner)
            return
        if isinstance(n, ast.ClassDef):
            for st in n.body:
                visit(st, bound | _scope_bindings(n))
            return
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            inner = set(bound)
            for i, gen in enumerate(n.generators):
                # the FIRST iterable is evaluated in the enclosing scope; the rest see the targets
                visit(gen.iter, frozenset(bound if i == 0 else inner))
                inner |= _stored(gen.target)
                for cond in gen.ifs:
                    visit(cond, frozenset(inner))
            parts = [n.elt] if hasattr(n, "elt") else [n.key, n.value]
            for part in parts:
                visit(part, frozenset(inner))
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            examined += 1
            if n.id not in bound:
                findings.append((n.id, n.lineno))
            return
        for child in ast.iter_child_nodes(n):
            visit(child, bound)

    visit(node, frozenset(outer))
    return findings, examined


def _module_scope(tree) -> frozenset[str]:
    return frozenset(_scope_bindings(tree) | _BUILTINS)


def _function(tree, name: str):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name}() is no longer a module-level function of data_plane.py")


def _tree():
    return ast.parse(_DATA_PLANE.read_text(encoding="utf-8"), filename=str(_DATA_PLANE))


# ------------------------------------------------------------------ the defect itself
def test_process_has_no_unbound_globals():
    """`process()` must be callable: every name it loads has to resolve somewhere.

    This is the test that was missing on 2026-09-13. It fails on the tree as it stood then, naming
    `workgroup` at data_plane.py:381, and it will fail the same way for the next unbound name.
    """
    tree = _tree()
    fn = _function(tree, "process")
    unbound, examined = _scan(fn, _module_scope(tree))
    assert examined > 0, "scanned 0 loaded name(s) in process() — the walk resolved nothing"
    assert not unbound, (
        f"{len(unbound)} unbound name(s) over {examined} loaded name(s) examined in "
        f"data_plane.process() — each is a NameError at call time: "
        + ", ".join(f"{name!r} at {_DATA_PLANE.name}:{line}" for name, line in unbound)
    )


def test_no_unbound_globals_anywhere_in_data_plane():
    """The same property over EVERY module-level function in the module — the ratchet.

    `process()` is where the crash was; it is not the only function that can grow one. The module is
    small enough that the whole file is the honest population, and the denominator is printed so a
    walk that stops finding functions fails instead of passing.
    """
    tree = _tree()
    scope = _module_scope(tree)
    fns = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert len(fns) >= 8, f"only {len(fns)} module-level function(s) found — the walk lost the file"
    bad, examined = [], 0
    for fn in fns:
        found, count = _scan(fn, scope)
        examined += count
        bad += [(fn.name, name, line) for name, line in found]
    assert examined > 0
    assert not bad, (
        f"{len(bad)} unbound name(s) over {examined} loaded name(s) in {len(fns)} function(s): "
        + ", ".join(f"{fn}() loads {name!r} at {_DATA_PLANE.name}:{line}" for fn, name, line in bad)
    )


# ------------------------------------------------------------------ the caller side of the same bug
_HARVEST = Path(__file__).resolve().parents[1] / "cli" / "harvest.py"


def _required_kwonly(fn) -> set[str]:
    """The keyword-only parameters with NO default — the ones a caller MUST name."""
    a = fn.args
    return {p.arg for p, d in zip(a.kwonlyargs, a.kw_defaults) if d is None}


def _call_keywords(scope, dotted: str) -> set[str]:
    """The keywords passed at the single call to `dotted` under `scope`.

    A `**splat` at the call site makes the requirement unverifiable by reading, so it raises rather
    than returning a short set that would read as a pass — an unresolvable call must not come back
    clean.
    """
    want = dotted.split(".")
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        got = []
        while isinstance(f, ast.Attribute):
            got.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            got.append(f.id)
        if list(reversed(got)) != want:
            continue
        if any(k.arg is None for k in node.keywords):
            raise AssertionError(f"{dotted}(...) now uses a ** splat — this check cannot read it")
        return {k.arg for k in node.keywords}
    raise AssertionError(f"no call to {dotted}(...) found — the call chain moved")


def test_every_required_keyword_of_process_is_passed_by_harvest_data():
    """The defect class one level up, and the one that actually happened.

    On 2026-09-13 `profile_table` gained a REQUIRED keyword-only `workgroup` and its caller was not
    updated in the same commit. Making `process()`'s names resolve fixes that instance; it does not
    stop the next required keyword from being added with no caller passing it -- that lands as a
    TypeError at call time, on the same dead path, equally invisible. So both hops of the chain
    `harvest_data -> process -> profile_table` are read here: every required keyword-only parameter
    of the callee must be named at the call site.
    """
    dp = _tree()
    hv = ast.parse(_HARVEST.read_text(encoding="utf-8"), filename=str(_HARVEST))

    hops = [
        ("harvest_data", "data_plane.process", _function(dp, "process")),
        ("process", "profile_table", _function(dp, "profile_table")),
    ]
    checked, missing = 0, []
    for caller_name, callee_call, callee in hops:
        tree = hv if caller_name == "harvest_data" else dp
        required = _required_kwonly(callee)
        assert required, (
            f"{callee.name}() declares no required keyword-only parameter -- hop unchecked"
        )
        passed = _call_keywords(_function(tree, caller_name), callee_call)
        checked += len(required)
        missing += [
            f"{caller_name}() -> {callee_call}() omits {k!r}"
            for k in sorted(required - passed)
        ]
    assert checked >= 2, f"only {checked} required keyword(s) checked across the chain"
    assert not missing, (
        f"{len(missing)} of {checked} required keyword(s) not passed: " + "; ".join(missing)
    )


def test_harvest_data_refuses_before_any_aws_call_when_no_workgroup_is_declared(tmp_path, monkeypatch):
    """The runtime half: the value `process()` now demands comes from the BUNDLE, and its absence is
    a loud refusal taken BEFORE anything is billed.

    Both halves of that sentence are asserted, because the AST above cannot see either. `_session` is
    booby-trapped: if the workgroup resolution is ever moved below it, this test fails with the boom
    instead of the refusal, which is the point -- an operator should not pay for a Glue listing and
    N-1 tables of Bedrock before being told the bundle never said which workgroup to use.

    Nothing here reaches AWS: the refusal is raised two statements into the function, and the session
    factory would raise first if it did not.
    """
    monkeypatch.delenv("MAC_ATHENA_WORKGROUP", raising=False)
    monkeypatch.delenv("DEPLOYMENT_CONFIG", raising=False)  # no out-of-band overlay from the shell

    def _boom(*a, **k):
        raise AssertionError("harvest_data reached AWS before resolving the bundle's workgroup")

    monkeypatch.setattr(harvest, "_session", _boom)
    (tmp_path / "mac.project.yaml").write_text(
        "metadata:\n  project: fixture/none\n  data_domain: fixture\n  dataset: none\n",
        encoding="utf-8",
    )  # a bundle with NO connection.yaml -- i.e. one that never declared a workgroup

    with pytest.raises(RuntimeError, match="workgroup"):
        harvest.harvest_data(tmp_path, ["some_db"])


# ------------------------------------------------------------------ the checker's own self-test
_CLEAN_FIXTURE = """
import os
MODULE_CONST = 1

def f(a, b=2, *rest, kw, **kwargs):
    import json
    local = a + b + MODULE_CONST
    for i in rest:
        local += i
    with open(os.devnull) as fh:
        data = fh.read()
    try:
        n = int(data)
    except ValueError as exc:
        n = len(str(exc))
    squares = [y * y for y in range(n)]
    if (walrus := len(squares)):
        local += walrus
    def nested(z):
        return z + local
    return json.dumps([local, kw, kwargs, nested(n), squares])
"""

# One mutant per way a name can fail to resolve. Each must be REJECTED, and rejected by NAME — a
# checker that flags the wrong name is not coverage, it is a coincidence.
_MUTANTS = {
    "plain-unbound": ("def f(a):\n    return a + missing_name\n", "missing_name"),
    "unbound-in-comprehension": (
        "def f(items):\n    return [x * factor for x in items]\n",
        "factor",
    ),
    "leaked-from-nested-scope": (
        "def f(items):\n    def inner():\n        inner_only = 1\n        return inner_only\n"
        "    return inner() + inner_only\n",
        "inner_only",
    ),
    "leaked-comprehension-target": (
        "def f(items):\n    out = [y for y in items]\n    return out, y\n",
        "y",
    ),
    "global-declared-never-assigned": (
        "def f():\n    global wg\n    return wg\n",
        "wg",
    ),
    "kwonly-default-from-inner-scope": (
        "def f(items):\n    def inner(*, k=cap):\n        return k\n    return inner(), items\n",
        "cap",
    ),
}


def test_scan_passes_a_clean_function_that_uses_every_binding_form():
    """The must-pass fixture: params, defaults, *args/**kwargs, import-in-function, for-target,
    with-as, except-as, comprehension target, walrus, nested def, module const, builtin. If any of
    these read as unbound the checker is a false-alarm machine and the real test above is noise."""
    tree = ast.parse(_CLEAN_FIXTURE)
    unbound, examined = _scan(_function(tree, "f"), _module_scope(tree))
    assert not unbound, f"false positives on the clean fixture: {unbound}"
    assert examined >= 20, f"clean fixture examined only {examined} loaded name(s)"


@pytest.mark.parametrize("cls", sorted(_MUTANTS))
def test_scan_rejects_each_unbound_shape(cls):
    """Seed one mutant per reject class and require it be caught AS THAT NAME."""
    src, expected = _MUTANTS[cls]
    tree = ast.parse(src)
    unbound, examined = _scan(_function(tree, "f"), _module_scope(tree))
    assert examined > 0, f"{cls}: examined nothing"
    assert expected in {name for name, _ in unbound}, (
        f"{cls}: mutant not caught as its own name — expected {expected!r}, got {unbound}"
    )


def test_scan_examines_a_real_population():
    """The denominator, pinned. `process()` loads dozens of names; if a refactor of the walk ever
    drops that to a handful, the green above means nothing and this fails first."""
    tree = _tree()
    _, examined = _scan(_function(tree, "process"), _module_scope(tree))
    assert examined >= 40, f"process() scan examined only {examined} loaded name(s)"
