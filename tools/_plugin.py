#!/usr/bin/env python3
"""_plugin.py — the BUNDLE owns how its declarations resolve; MAC owns the analysis.

WHY THIS EXISTS. Five tools need a resolver or a warehouse connection that only the subject bundle
can supply, so they import `tools/run_properties.py` from the bundle under test. Three of them
guarded that import with:

    resolve = lambda x: x
    if tools.is_dir():
        sys.path.insert(0, tools)
        try:
            from run_properties import resolve_declared as resolve
        except Exception:
            pass

Both branches of that are wrong, in opposite directions, and together they let the SUBJECT choose
the CHECKER's verdict:

  * `SystemExit` is not a subclass of `Exception` — verified, `issubclass(SystemExit, Exception)` is
    False. A plugin that calls `sys.exit()` at import time for a missing dependency therefore
    escapes the guard entirely and ITS exit code becomes the checker's. A could-not-run is then
    published as a FAIL, or worse as a PASS.
  * When the guard does fire, the silent identity fallback leaves every `@cols:` slot unresolved,
    every parse fails, and each failure is reported as a fabricated identifier — a confident FALSE
    report of an invariant breach. `check_no_fabricated_identifiers` predicted this in its own
    docstring ("3 findings became 56 the moment properties started RENDERING their value sets… a
    checker that punishes the correct pattern is worse than no checker") and then did it.

Broadening the guard to `BaseException` does not fix it; it converts the first failure mode into the
second, which is the more damaging one.

THE RULE, stated once, here:

  * A bundle that DECLARES a plugin and cannot supply it makes the check UNRUNNABLE — the caller
    exits 2. "Could not run" is the one honest answer available, and it is never a finding.
  * A bundle that declares NO plugin gets the documented fallback, because there is nothing broken
    to hide: identity resolution over un-namespaced declarations is the correct behaviour.
  * Nothing the plugin does at import time can set our exit code.

`required()` is for a plugin with no meaningful fallback (a warehouse connection). `optional()` is
for one that has a defined default (a resolver). Neither can return a degraded object silently.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys

#: The module name a bundle uses to declare its resolver / connection.
PLUGIN_MODULE = "run_properties"


class PluginUnavailable(RuntimeError):
    """The bundle DECLARES a plugin that could not be used. The check cannot run — exit 2."""


def declared(root: object) -> str | None:
    """The bundle's plugin file, or None when the bundle declares no plugin at all."""
    p = os.path.join(os.path.abspath(str(root)), "tools", PLUGIN_MODULE + ".py")
    return p if os.path.isfile(p) else None


def _load(root: object):
    """Import the bundle's plugin. Returns None when none is declared; never degrades silently.

    Loaded by EXPLICIT FILE PATH, not by name off `sys.path`. Every one of the five tools that grew
    this seam did `sys.path.insert(0, tools)` then `from run_properties import ...`, which means the
    winner is decided by sys.path ORDER, not by the root asked for: check bundle A then bundle B in
    one process and B silently gets A's plugin. This module's own self-test caught exactly that in
    its first draft. A per-root module name plus a path-pinned loader removes the ambiguity.

    The bundle's `tools/` is APPENDED to `sys.path`, not prepended, so the plugin's own siblings
    still resolve while a bundle-local `version.py` or `json.py` can no longer shadow the stdlib.
    """
    path = declared(root)
    if path is None:
        return None

    path = os.path.abspath(path)
    tools = os.path.dirname(path)
    # Stable per root, so a repeat call reuses the module and two roots never collide.
    key = hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
    modname = f"_mac_plugin_{PLUGIN_MODULE}_{key}"
    if modname in sys.modules:
        return sys.modules[modname]

    if tools not in sys.path:
        sys.path.append(tools)

    try:
        spec = importlib.util.spec_from_file_location(modname, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no import machinery claims {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[modname] = mod
        spec.loader.exec_module(mod)
        return mod
    except KeyboardInterrupt:
        # An operator's interrupt is not a property of the bundle.
        sys.modules.pop(modname, None)
        raise
    except BaseException as exc:
        # BaseException deliberately: SystemExit is the failure mode this module exists for. It is
        # converted into our own typed error, never propagated, so the subject cannot set our code.
        sys.modules.pop(modname, None)
        raise PluginUnavailable(
            f"{os.path.join('tools', PLUGIN_MODULE + '.py')} could not be imported: "
            f"{type(exc).__name__}: {exc}"
        ) from None


def _symbol(mod, root: object, symbol: str):
    try:
        return getattr(mod, symbol)
    except AttributeError:
        raise PluginUnavailable(
            f"{os.path.join('tools', PLUGIN_MODULE + '.py')} is declared but does not supply "
            f"{symbol!r}"
        ) from None


def optional(root: object, symbol: str, fallback):
    """The declared plugin's `symbol`, or `fallback` when the bundle declares NO plugin.

    A bundle that declares a plugin and cannot supply the symbol raises — it does NOT get the
    fallback, because a degraded resolver produces findings that look like real breaches.
    """
    mod = _load(root)
    if mod is None:
        return fallback
    return _symbol(mod, root, symbol)


def required(root: object, symbol: str):
    """The declared plugin's `symbol`. Raises when the bundle declares none — there is no default."""
    mod = _load(root)
    if mod is None:
        raise PluginUnavailable(
            f"this check needs {os.path.join('tools', PLUGIN_MODULE + '.py')} to supply "
            f"{symbol!r}, and the bundle declares none"
        )
    return _symbol(mod, root, symbol)


# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus a clean fixture that must work.
# ---------------------------------------------------------------------------------------------

_FIXTURES: dict[str, str | None] = {
    # name                  tools/run_properties.py content (None = declare no plugin at all)
    "no-plugin-declared":   None,
    "plugin-sys-exits":     "import sys\nsys.exit('missing dependency: no module named widget')\n",
    "plugin-import-error":  "import a_module_that_is_not_installed_anywhere\n",
    "plugin-raises":        "raise RuntimeError('boom at import time')\n",
    "plugin-missing-symbol": "def something_else(x):\n    return x\n",
    "plugin-works":         "def resolve_declared(x):\n    return x.replace('@slot', 'resolved')\n",
}


def _seed(tmp: str, name: str, body: str | None) -> str:
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, "tools"), exist_ok=True)
    if body is not None:
        with open(os.path.join(root, "tools", PLUGIN_MODULE + ".py"), "w", encoding="utf-8") as fh:
            fh.write(body)
    return root


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    sentinel = object()

    with tempfile.TemporaryDirectory() as tmp:
        roots = {n: _seed(tmp, n, b) for n, b in _FIXTURES.items()}

        # Every mutant must have actually been written. A self-test whose mutant did not mutate
        # passes for the wrong reason -- it happened once in this estate and cost a day.
        for name, body in _FIXTURES.items():
            got = declared(roots[name])
            if (body is None) != (got is None):
                failures.append(f"fixture '{name}' was not seeded as intended")

        # 1 · clean fixture: the plugin is used, and it is really the plugin's behaviour.
        try:
            fn = optional(roots["plugin-works"], "resolve_declared", lambda x: x)
            if fn("a @slot b") != "a resolved b":
                failures.append("clean fixture: the declared resolver was not the one used")
        except PluginUnavailable as exc:
            failures.append(f"clean fixture wrongly refused: {exc}")

        # 2 · a bundle that declares NO plugin gets the documented fallback.
        if optional(roots["no-plugin-declared"], "resolve_declared", sentinel) is not sentinel:
            failures.append("mutant not caught: no-plugin-declared did not receive the fallback")
        try:
            required(roots["no-plugin-declared"], "Athena")
            failures.append("mutant not caught: required() returned with no plugin declared")
        except PluginUnavailable:
            pass

        # 3 · every broken-plugin class must REFUSE, never degrade to the fallback.
        for name in ("plugin-sys-exits", "plugin-import-error", "plugin-raises",
                     "plugin-missing-symbol"):
            for api, args in (("optional", ("resolve_declared", sentinel)), ("required", ("Athena",))):
                try:
                    got = (optional(roots[name], *args) if api == "optional"
                           else required(roots[name], *args))
                except PluginUnavailable:
                    continue
                except BaseException as exc:            # noqa: BLE001 - that is the point
                    failures.append(
                        f"mutant not contained: {name} via {api}() escaped as "
                        f"{type(exc).__name__} -- the subject set our outcome")
                    continue
                failures.append(
                    f"mutant not caught: {name} via {api}() returned "
                    f"{'the fallback' if got is sentinel else got!r} instead of refusing")

        # 4 · the decisive one, stated as its own assertion: SystemExit is not an Exception, so the
        #     old `except Exception` could not have contained it.
        if issubclass(SystemExit, Exception):
            failures.append("SystemExit is an Exception on this interpreter; the premise changed")

        # 5 · two roots in one process must not share a plugin.
        first = optional(roots["plugin-works"], "resolve_declared", lambda x: x)
        if first("@slot") != "resolved":
            failures.append("caching: first root's plugin did not resolve")
        try:
            optional(roots["plugin-raises"], "resolve_declared", sentinel)
            failures.append("caching: a second, BROKEN root silently reused the first root's plugin")
        except PluginUnavailable:
            pass

    total = len(_FIXTURES) + 4 + 4 * 2 + 1 + 2
    if failures:
        print(f"FAIL: _plugin self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: _plugin self-test — {total}/{total} "
          f"({len(_FIXTURES) - 1} mutants refuse via both APIs, no-plugin gets the fallback, "
          f"clean fixture resolves, SystemExit contained, per-root cache proven)")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv else
             print("usage: _plugin.py --self-test") or 0)
