#!/usr/bin/env python3
"""
test_out_of_scope.py — `conformance.out_of_scope` takes a file out of scope even when a ROUTE claims it.

The gate tells a bundle, in as many words, to "declare them in mac.project.yaml#conformance.out_of_scope
with a reason". That remedy used to work only for files NO route matched. The pattern routes claim by
LOCATION, not by content -- every `acceptance/*.yaml` is routed to PropertiesFile -- so a corpus file
that is not a property suite was validated against a definition it never claimed, failed on its own
shape, and the bundle had no way to say so. The declaration now means what the gate says it means.

A waived file must still be COUNTED as waived, never silently dropped: taking something out of scope is
a visible act, and a gate that hides it cannot be audited.

Usage:  python3 tests/test_out_of_scope.py   ·   Exit: 0 = ok · 1 = an assertion failed
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from validate_schema import enumerate_bundle  # noqa: E402

fails = 0


def check(cond, msg):
    global fails
    print(("✓ " if cond else "✗ ") + msg)
    fails += 0 if cond else 1


MANIFEST = """metadata: {{schema_version: 0.1.14}}
project: {{name: t, domain: d, dataset: s}}
planes: {{ontology: ontology, data: data}}
conformance:
  out_of_scope:
{entries}"""


def bundle(*declared: str) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "ontology" / "concepts").mkdir(parents=True)
    (root / "acceptance").mkdir()
    (root / "acceptance" / "properties.yaml").write_text("properties: []\n")
    (root / "acceptance" / "intents.yaml").write_text("questions: []\n")
    entries = "".join(f"    - path: {d}\n      reason: test\n" for d in declared) or "    []\n"
    (root / "mac.project.yaml").write_text(MANIFEST.format(entries=entries))
    return root


def rel(paths, root):
    return {os.path.relpath(p, root) for p in paths}


# -- 1. undeclared: the route claims it, so it is validated (unchanged behaviour) -------------
root = bundle()
e = enumerate_bundle(str(root))
check("acceptance/intents.yaml" in rel(e.routed, root), "undeclared acceptance file is still routed")

# -- 2. declared: the route no longer keeps it in scope ----------------------------------------
root = bundle("acceptance/intents.yaml")
e = enumerate_bundle(str(root))
check("acceptance/intents.yaml" not in rel(e.routed, root),
      "a declared file is taken out of scope even though a route claims it")
check("acceptance/intents.yaml" in set(e.waived), "a declared, routed file is COUNTED as waived")

# -- 3. the declaration is not a blanket: its sibling stays in scope ----------------------------
check("acceptance/properties.yaml" in rel(e.routed, root),
      "a sibling the declaration does not name stays in scope")

# -- 4. a glob declaration works the same way ---------------------------------------------------
root = bundle("acceptance/**")
e = enumerate_bundle(str(root))
check(not [p for p in rel(e.routed, root) if p.startswith("acceptance/")],
      "a glob declaration takes the whole directory out of scope")

print(f"\n{'all out-of-scope assertions passed' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
