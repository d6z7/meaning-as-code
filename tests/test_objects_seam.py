#!/usr/bin/env python3
"""
test_objects_seam.py — the OBJECT INDEX seam, pinned against `mac.seam/1`.

`tools/project_objects.py` derives a bundle's object index live, so the console can render the
index from the bundle instead of reading `objects.json` — a BUILD ARTIFACT, exactly as old as the
last projection run. Measured once: the file held 9 objects while the bundle had gained 6 dataset
descriptors and 12 transform files, and the console showed none of them for 46 minutes with no
marker of any kind.

Deriving it live fixed the staleness and left the harder half open: an answer that is DERIVED but
INCOMPLETE reads exactly like a complete one. SEAM_CONTRACT.md is the repair and
`tools/check_seam_contract.py` is the copy that refuses. This file pins the clauses that are about
THIS seam's behaviour rather than about the envelope's grammar, on a fixture it writes itself.

  P1 ONE SHAPE ON EVERY EXIT    — the reserved key set of §3 is identical on a success, on a
                                  refusal and on a caller error. 3 of the 6 top-level keys of the
                                  version before this one vanished on a failure exit, so a client
                                  reading one of them was reading a key that exists only when
                                  nothing went wrong
  P2 EVERY INPUT IS DECLARED    — every file the run OPENS is named by an `inputs[]` entry, with a
                                  role from the closed four. MEASURED with the gate's own audit
                                  hook, never read off the docstring: a manifest cannot catch what
                                  its author did not know he read
  P3 A SWALLOWED READ SPEAKS    — corrupting `data/quality/dq_dashboard.json` used to change the
                                  payload NOT AT ALL, because build_objects read it under
                                  `except Exception: pass`. Of 20 traced inputs it was the one
                                  whose corruption was invisible. THE regression this file exists
                                  for
  P4 THE DENOMINATOR IS REAL    — `counts.declared` counts the descriptor files the enumerating
                                  planes declare, so it CAN differ from what came back. Two
                                  concepts filed under different domains with the same stem
                                  collide and one is dropped silently; `returned of declared` and
                                  `partial[]` are what make that visible
  P5 DEGRADE, NOT REFUSE        — an index whose membership is intact and whose per-member
                                  attribute is not is SERVED (exit 0) as `degraded` with
                                  `partial[]` naming the loss — §5, the partial-result rule
  P6 THE INTERPRETER FLOOR      — the seam runs on `/usr/bin/python3`, the interpreter its own
                                  usage line documents. It used to exit 1 with 0 bytes there, on
                                  `datetime.UTC`, before reaching any line that could report it
  P7 A CALLER ERROR SPEAKS      — exit 2 with the envelope on stdout, not 0 bytes and prose on
                                  stderr, and `--out` may not name a path inside the bundle
  P8 NO PATH LEAVES             — no absolute filesystem path anywhere outside `local`, which the
                                  host drops before the wire
  P9 NOTHING IS WRITTEN         — every file under the fixture is stat-snapshotted, the derivation
                                  runs, and the snapshot must be identical with no new file

The fixture bundle is written by this file into a temp dir and is generic (alpha/beta over
rel_alpha/rel_beta). No project, customer, brand or source specifics.

Usage:  python3 tests/test_objects_seam.py   ·   Exit: 0 = all assertions passed · 1 = a failure
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOOLS = REPO / "tools"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))

# THE GATE'S OWN TRACER, not a second one. `_probe` runs the seam under `sys.addaudithook` and
# classifies what it opened; P2 is only worth anything if it measures the same way the enforcing
# copy measures. A second tracer written here could agree with the docstring and disagree with the
# gate, which is the defect class this whole contract is about.
from check_seam_contract import (  # noqa: E402
    _ABS,
    RESERVED,
    SEAM_MINTED,
    _probe,
    _walk_strings,
)

SEAM = TOOLS / "project_objects.py"

fails = 0


def ok(cond, msg):
    global fails
    print(("  ✓ " if cond else "  ✗ ") + msg)
    fails += 0 if cond else 1


# ── the fixture bundle ───────────────────────────────────────────────────────────────────────────
_MANIFEST = """\
spec_version: mac.container/1
metadata:
  project: alpha/beta
  label: Alpha Beta
  data_domain: alpha
  dataset: beta
planes:
  data: data
  ontology: ontology
"""

_SOURCE = """\
table:
  name: src_alpha
columns:
  - name: alpha_key
    type: varchar
"""

_DATASET = """\
table:
  name: rel_alpha
columns:
  - name: alpha_key
    type: varchar
    description: the identifying column
"""

_TRANSFORM = """\
produces:
  relation: rel_alpha
inputs:
  - descriptor: data/sources/src_alpha.yaml
"""

# A DASHBOARD WITH A FINDING THAT NAMES A TABLE. An EMPTY `findings` list is what made the original
# defect invisible: with nothing to lose, a corrupted dashboard and a clean one produce the same
# index, so the corruption probe could only ever be answered by a DECLARATION.
_DASHBOARD = json.dumps(
    {"stats": {"total": 1}, "findings": [{"id": "DQ-001", "table": "src_alpha", "severity": "low"}]},
    indent=1,
)

_EDGES = """\
edges:
  - edge_id: alpha__joins__beta
    level: physical
    type: foreign_key
    join_rule: "rel_alpha.beta_key = rel_beta.beta_key"
    endpoints:
      from: { concept: Alpha, cardinality: "0..N", role: joinsBeta }
      to: { concept: Beta, cardinality: "1" }
"""


def _concept(name: str, relation: str) -> str:
    return (
        "spec_version: mac.concept/1\n"
        "concept:\n"
        f"  name: {name}\n"
        f"  label: {name.upper()}\n"
        "  class: entity\n"
        f"  definition: the {name} a bundle declares\n"
        "metadata:\n"
        "  confidence: I\n"
        "grounding:\n"
        "  sources:\n"
        f"    - relation: {relation}\n"
        "      key: alpha_key\n"
    )


def _bundle(root: Path, second_alpha=False) -> Path:
    """The fixture. `second_alpha` files a SECOND concept under a different domain with the same
    filename stem — the silent collision P4 measures."""
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "data" / "transforms").mkdir(parents=True, exist_ok=True)
    (root / "data" / "quality").mkdir(parents=True, exist_ok=True)
    (root / "ontology" / "concepts" / "domain_one").mkdir(parents=True, exist_ok=True)
    (root / "ontology" / "concepts" / "domain_two").mkdir(parents=True, exist_ok=True)
    (root / "mac.project.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "data" / "sources" / "src_alpha.yaml").write_text(_SOURCE, encoding="utf-8")
    (root / "data" / "datasets" / "rel_alpha.yaml").write_text(_DATASET, encoding="utf-8")
    (root / "data" / "transforms" / "rel_alpha.yaml").write_text(_TRANSFORM, encoding="utf-8")
    (root / "data" / "quality" / "dq_dashboard.json").write_text(_DASHBOARD, encoding="utf-8")
    (root / "ontology" / "edges.yaml").write_text(_EDGES, encoding="utf-8")
    (root / "ontology" / "concepts" / "domain_one" / "alpha.yaml").write_text(
        _concept("Alpha", "rel_alpha"), encoding="utf-8"
    )
    stem = "alpha" if second_alpha else "beta"
    (root / "ontology" / "concepts" / "domain_two" / f"{stem}.yaml").write_text(
        _concept("Beta", "rel_beta"), encoding="utf-8"
    )
    return root


def _seam(root: Path, *args, interp=None) -> tuple[dict, int, str, str]:
    r = subprocess.run(
        [interp or sys.executable, str(SEAM), str(root), *args], capture_output=True, text=True
    )
    try:
        payload = json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        payload = {}
    return payload, r.returncode, r.stdout, r.stderr


def _snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = _bundle(Path(td) / "bundle")

        # ── P1 ──────────────────────────────────────────────────────────────────────────────────
        print("P1 ONE SHAPE ON EVERY EXIT — a reserved key never vanishes on the failure path")
        good, _code, _out, _err = _seam(root)
        bad_root, code_bad, out_bad, _ = _seam(Path(td) / "no-such-root")
        bad_flag = subprocess.run(
            [sys.executable, str(SEAM), str(root), "--nope"], capture_output=True, text=True
        )
        flag_payload = json.loads(bad_flag.stdout) if bad_flag.stdout.strip() else {}
        shapes = {
            "derive": tuple(sorted(good)),
            "bad-root": tuple(sorted(bad_root)),
            "bad-flag": tuple(sorted(flag_payload)),
        }
        ok(len(set(shapes.values())) == 1, f"one key set across 3 exits, not {len(set(shapes.values()))}")
        ok(
            all(k in good for k in RESERVED),
            f"every reserved key of §3 is present ({sorted(set(RESERVED) - set(good))} missing)",
        )
        ok(good.get("envelope") == "mac.seam/1", f"the envelope names its contract ({good.get('envelope')!r})")
        ok(good.get("mode") == "index", f"mode is declared, not inferred ({good.get('mode')!r})")
        ok(
            isinstance(good.get("result"), list) and good["result"],
            "the principal result is a list under the fixed key `result`",
        )
        ok(
            good.get("status") in SEAM_MINTED and good.get("status") == "derived",
            f"a clean fixture derives ({good.get('status')!r})",
        )
        ok("reason" in good and good["reason"] is None,
           "`reason` is PRESENT and null exactly when derived — absent is not null (§3)")
        ok("subject" in good and good["subject"] is None,
           "a whole-bundle seam declares its subject as null, and declares it")

        # ── P2 ──────────────────────────────────────────────────────────────────────────────────
        print("P2 EVERY INPUT IS DECLARED — measured with the gate's audit hook, not the docstring")
        probe = _probe("derived", sys.executable, SEAM, [str(root)], root.resolve(), REPO)
        p_inputs = ((probe.payload or {}).get("inputs")) or []
        declared = [i.get("path", "") for i in p_inputs]
        undeclared = [
            o
            for o in probe.bundle_opens
            if not any(o == d or o.startswith(d.rstrip("/") + "/") for d in declared)
        ]
        ok(
            bool(probe.bundle_opens) and not undeclared,
            f"{len(probe.bundle_opens) - len(undeclared)} of {len(probe.bundle_opens)} traced "
            f"bundle open(s) are declared ({sorted(undeclared)[:4]})",
        )
        fdecl = [d.split(":", 1)[1] for d in declared if d.startswith("framework:")]
        funcov = [o for o in probe.framework_opens if o not in fdecl and Path(o).name not in fdecl]
        ok(
            not funcov and probe.framework_opens,
            f"{len(probe.framework_opens) - len(funcov)} of {len(probe.framework_opens)} "
            f"framework-side read(s) declared — the cache hole (§6.1)",
        )
        roles = {i.get("role") for i in p_inputs}
        ok(
            bool(roles) and roles <= {"spine", "row", "attribute", "framework"},
            f"every role is from the closed four, and there are some ({sorted(roles)})",
        )
        ok("spine" in roles, "at least one input says which plane ENUMERATES the members (§5.1)")
        ok(
            any(i.get("path") == "data/quality/dq_dashboard.json" for i in p_inputs),
            "the dashboard build_objects swallowed is now a DECLARED input the cache can watch",
        )

        # ── P3 ──────────────────────────────────────────────────────────────────────────────────
        print("P3 A SWALLOWED READ SPEAKS — the one corruption of 20 that used to be invisible")
        dash = root / "data" / "quality" / "dq_dashboard.json"
        keep = dash.read_bytes()
        try:
            dash.write_bytes(b"{{{ not JSON ]]]\n")
            corrupt, ccode, _o, _e = _seam(root)
        finally:
            dash.write_bytes(keep)
        clean_cmp = {k: v for k, v in good.items() if k not in ("derived_at", "local")}
        corr_cmp = {k: v for k, v in corrupt.items() if k not in ("derived_at", "local")}
        ok(clean_cmp != corr_cmp, "corrupting the dashboard CHANGES the answer (modulo the clock)")
        ok(corrupt.get("status") == "degraded", f"and names it a degrade ({corrupt.get('status')!r})")
        entry = next(
            (p for p in corrupt.get("partial") or [] if p["input"] == "data/quality/dq_dashboard.json"),
            None,
        )
        ok(entry is not None, "`partial[]` names the input by path")
        ok(
            bool(entry) and "Quality tab" in entry["effect"],
            f"and says what it COST the answer ({(entry or {}).get('effect')!r})",
        )
        ok(
            bool(entry) and "JSONDecodeError" in (entry["reason"] or ""),
            f"and why ({(entry or {}).get('reason')!r})",
        )
        di = next((i for i in corrupt.get("inputs") or []
                   if i.get("path") == "data/quality/dq_dashboard.json"), {})
        ok(di.get("present") is True and di.get("parsed") is False,
           f"the input entry says present-but-unparsed ({di})")

        # THE EXACT SHAPE THAT MADE IT INVISIBLE. With `findings: []` there is nothing for a
        # corruption to REMOVE, so the derived content is identical by construction and no amount
        # of deriving harder can tell the two apart — on the public example bundle this dashboard
        # is empty, which is why that one traced input of 20 measured as silent. Only a declared
        # input that is CHECKED can signal it.
        hollow = _bundle(Path(td) / "hollow")
        hdash = hollow / "data" / "quality" / "dq_dashboard.json"
        hdash.write_text(json.dumps({"stats": {"total": 0}, "findings": []}), encoding="utf-8")
        h_clean, _c, _o, _e = _seam(hollow)
        hdash.write_bytes(b"{{{ not JSON ]]]\n")
        h_corrupt, _c, _o, _e = _seam(hollow)
        ok(
            (h_clean.get("result") or []) == (h_corrupt.get("result") or []),
            "with an empty `findings` the derived members are identical — the content CANNOT tell",
        )
        ok(
            h_clean.get("status") == "derived" and h_corrupt.get("status") == "degraded",
            f"and the seam still tells them apart, on the declaration alone "
            f"({h_clean.get('status')!r} vs {h_corrupt.get('status')!r})",
        )

        # ── P4 ──────────────────────────────────────────────────────────────────────────────────
        print("P4 THE DENOMINATOR IS REAL — a silent stem collision shows up as N of M")
        c = good.get("counts") or {}
        ok(
            c.get("declared") == 4,
            f"M counts the descriptor files the planes declare: 1 source + 1 dataset + 2 concepts "
            f"(got {c.get('declared')})",
        )
        ok(c.get("returned") is not None and c.get("returned") == c.get("declared"),
           f"all of them produced a member ({c.get('returned')} of {c.get('declared')})")
        ok(
            c.get("returned") is not None
            and c["returned"] + c.get("composed", 0) == c.get("result_size"),
            f"every member is either descriptor-backed or composed ({c})",
        )
        collided = _bundle(Path(td) / "collision", second_alpha=True)
        col, _code, _o, _e = _seam(collided)
        cc = col.get("counts") or {}
        ok(
            cc.get("declared") == 4 and cc.get("returned") == 3,
            f"two concepts sharing a stem: one is dropped and the count says so "
            f"({cc.get('returned')} of {cc.get('declared')})",
        )
        ok(
            any(p["role"] == "spine" for p in col.get("partial") or []),
            "and the loss is named in `partial[]` against the enumerating plane",
        )
        ok(
            col.get("status") == "degraded",
            f"a member that went missing is a degrade, not a clean bill ({col.get('status')!r})",
        )

        # ── P5 ──────────────────────────────────────────────────────────────────────────────────
        print("P5 DEGRADE, NOT REFUSE — §5, index mode may serve an incomplete answer")
        ok(ccode == 0, f"a degraded index is SERVED, exit 0 (got {ccode})")
        ok(bool(corrupt.get("result")), "with its members still in `result`")
        ok(
            "partial" in corrupt
            and bool(corrupt["partial"]) == (corrupt.get("status") == "degraded"),
            "`partial != []` and `status == degraded` are ONE declared fact",
        )
        # AN ABSENT ATTRIBUTE IS A DEGRADE ONLY WHERE IT IS A DERIVED RECORD AND THERE ARE MEMBERS
        # TO DECORATE. §5.2's precedent (the edge seam degrades on a MISSING measurement record)
        # applied flatly would mark every bundle in the estate degraded forever.
        nolin = _bundle(Path(td) / "no-manifest")
        (nolin / "mac.project.yaml").unlink()
        nl, nlcode, _o, _e = _seam(nolin)
        lin_p = next((q for q in nl.get("partial") or [] if q["input"] == "mac.project.yaml"), None)
        ok(
            nl.get("status") == "degraded" and nlcode == 0 and lin_p is not None,
            f"no manifest: lineage is UNKNOWN, so the index is served degraded "
            f"({nl.get('status')!r}, exit {nlcode})",
        )
        ok(
            bool(lin_p) and "Lineage view" in lin_p["effect"],
            f"and the partial says every source and dataset lost its Lineage view "
            f"({(lin_p or {}).get('effect')!r})",
        )
        noreg = _bundle(Path(td) / "no-register")
        nr, _c, _o, _e = _seam(noreg)
        ok(
            nr.get("status") == "derived"
            and not any(
                q["input"] == "data/quality/data_quality_register.yaml"
                for q in nr.get("partial") or []
            ),
            f"an absent SSOT (no quality register) is empty, not unknown — no false degrade "
            f"({nr.get('status')!r})",
        )
        ok(
            any(
                i["path"] == "data/quality/data_quality_register.yaml" and i["present"] is False
                for i in nr.get("inputs") or []
            ),
            "and it is still DECLARED as an absent input, so the cache watches for it appearing",
        )

        empty = Path(td) / "empty-bundle"
        empty.mkdir()
        emp, ecode, _o, _e = _seam(empty)
        ok(
            emp.get("status") == "absent_input" and ecode == 0,
            f"a bundle with no enumerating plane at all is `absent_input`, not an empty success "
            f"({emp.get('status')!r}, exit {ecode})",
        )
        ok(
            (emp.get("counts") or {}).get("declared") == 0
            and (emp.get("counts") or {}).get("declared_known") is True,
            "and its zero has a denominator: 0 members DECLARED, not 0 measured",
        )

        # ── P6 ──────────────────────────────────────────────────────────────────────────────────
        print("P6 THE INTERPRETER FLOOR — the interpreter this seam's own usage line documents")
        floor = "/usr/bin/python3"
        if Path(floor).exists():
            ver = subprocess.run(
                [floor, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            fpay, fcode, fout, ferr = _seam(root, interp=floor)
            ok(fcode == 0, f"exit 0 on {floor} ({ver}), not 1 with 0 bytes (got {fcode}: {ferr.strip()[-90:]!r})")
            ok(bool(fout.strip()) and fpay.get("status") == "derived", "and a full envelope on stdout")
        else:
            ok(False, f"no {floor} on this machine, so the floor clause was not exercised")

        # ── P7 ──────────────────────────────────────────────────────────────────────────────────
        print("P7 A CALLER ERROR SPEAKS — exit 2 WITH the structured reason, never 0 bytes")
        ok(code_bad == 2, f"a root that is not a directory exits 2 (got {code_bad})")
        ok(bool(out_bad.strip()), f"and stdout carries the envelope ({len(out_bad)} bytes)")
        ok(bad_root.get("status") == "bad_request", f"under the closed token ({bad_root.get('status')!r})")
        ok(bad_flag.returncode == 2 and bool(bad_flag.stdout.strip()), "an unknown flag does the same")
        inside = root / "sneak.json"
        r = subprocess.run(
            [sys.executable, str(SEAM), str(root), "--out", str(inside)], capture_output=True, text=True
        )
        ok(r.returncode == 2 and not inside.exists(), "`--out` inside the bundle is refused (§2.2)")
        outside = Path(td) / "caller.json"
        r = subprocess.run(
            [sys.executable, str(SEAM), str(root), "--out", str(outside)], capture_output=True, text=True
        )
        ok(
            r.returncode == 0 and outside.exists() and bool(r.stdout.strip()),
            "`--out` writes the caller's file AND stdout still carries the envelope",
        )

        # ── P8 ──────────────────────────────────────────────────────────────────────────────────
        print("P8 NO PATH LEAVES — `local` is the only block that may carry one")
        leaks = []
        for payload, label in ((good, "derive"), (corrupt, "degraded"), (bad_root, "bad-request")):
            for where, val in _walk_strings({k: v for k, v in payload.items() if k != "local"}):
                if _ABS.match(val):
                    leaks.append(f"{label} {where}={val}")
        ok(not leaks, f"no absolute path outside `local` ({leaks[:3]})")
        ok(
            (good.get("local") or {}).get("root") == str(root.resolve()),
            "and `local.root` still carries the RESOLVED root, for the operator's log",
        )
        ok(
            str(root) not in json.dumps({k: v for k, v in corrupt.items() if k != "local"}),
            "a scrubbed reason does not smuggle the bundle root back in",
        )

        # ── P9 ──────────────────────────────────────────────────────────────────────────────────
        print("P9 NOTHING IS WRITTEN — the bundle is immutable to the seam that reads it")
        before = _snapshot(root)
        _seam(root)
        after = _snapshot(root)
        ok(after == before, "no file under the bundle changed, and none was created")

    print()
    print(("FAIL: %d assertion(s)" % fails) if fails else "PASS: all assertions")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
