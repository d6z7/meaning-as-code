#!/usr/bin/env python3
"""Move the measured blocks out of a descriptor and into data/profiles/. One-way, idempotent.

The descriptor keeps what a READER needs: the columns, their roles, and the value DOMAIN of any
column small enough to enumerate. The measurement — census counts, the table profile, the identity
evidence — moves to its own file, because the two have different lifecycles and the runtime pays for
mixing them.

MEASURED, on the 25 fpl2 descriptors: 64,9 % of their bytes were profile. Of that, 95,3 % was the
value domain and only 4,7 % the census. So this moves the SMALL half — which is the point. The token
saving is noise; the reason is that `mac_profile.py` rewrites a descriptor on every run (measured_at
always moves) and the runtime keys its prompt cache on descriptor mtime, so each re-measurement
invalidated ~97.000 tokens of cached system prompt for a change no engine could observe.
"""
from __future__ import annotations

import argparse
import glob
import pathlib
import sys

import yaml

SCHEMA_VERSION = "0.1.14-develop"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mac_profile import _enumerable          # ONE definition of "worth enumerating", not a second copy

CENSUS = ("distinct", "nulls", "min", "max", "determined_by")


def split(path: pathlib.Path, outdir: pathlib.Path, apply: bool) -> tuple[int, int]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tbl = doc.get("table") or {}
    rel = ".".join(x for x in (tbl.get("schema"), tbl.get("name")) if x)
    census, moved = [], 0
    for c in doc.get("columns") or []:
        p = c.get("profile")
        if not p:
            continue
        if p.get("values") is not None:            # the DOMAIN stays with the meaning
            c["values"] = p["values"]
        row = {"name": str(c["name"])}
        row.update({k: p[k] for k in CENSUS if k in p})
        if len(row) > 1:
            census.append(row)
        del c["profile"]
        moved += 1
    tprof, ie = doc.pop("profile", None), doc.pop("identity_evidence", None)
    if not (census or tprof or ie):
        return 0, 0

    prof = {"metadata": {"schema_version": (doc.get("metadata") or {}).get("schema_version")
                                              or SCHEMA_VERSION,
                         "generated_by": "mac_profile_split.py/1"},
            "of": path.stem, "relation": rel}
    if tprof: prof["profile"] = tprof
    if census: prof["columns"] = census
    if ie: prof["identity_evidence"] = ie
    before = len(path.read_text(encoding="utf-8"))
    if apply:
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / f"{path.stem}.yaml").write_text(
            yaml.safe_dump(prof, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                        encoding="utf-8")
    after = len(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100))
    return moved, before - after


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--apply", action="store_true", help="without this it only reports")
    ap.add_argument("--prune-domains", action="store_true",
                    help="also drop a `values:` domain from any column that is bounded but not "
                         "ENUMERABLE — a date, a load stamp, a surrogate. Applies mac_profile's own "
                         "rule to descriptors already written, so the fix does not cost 25 rescans.")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    out = root / "data" / "profiles"
    tot = files = 0
    # BOTH descriptor planes. The first cut walked only datasets/ and silently halved the generated
    # suite — 267 properties over 25 relations became 150 over 13, because twelve profiled relations
    # are RAW SOURCES. Caught by the count, which is the whole reason the generator prints one.
    if a.prune_domains:
        pruned = dropped = 0
        for d in ("datasets", "sources"):
            for f in sorted(glob.glob(str(root / "data" / d / "*.yaml"))):
                path = pathlib.Path(f)
                doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                cols = doc.get("columns") or []
                pf = root / "data" / "profiles" / f"{path.stem}.yaml"
                ex = set((((yaml.safe_load(pf.read_text(encoding="utf-8")) if pf.exists() else {})
                           or {}).get("identity_evidence") or {}).get("excluded") or [])
                hit = False
                for c in cols:
                    if c.get("values") is not None and not _enumerable(c, cols, ex):
                        dropped += len(str(c["values"])); del c["values"]; hit = True
                if hit:
                    pruned += 1
                    if a.apply:
                        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                                                       width=100), encoding="utf-8")
        print(f"  pruned non-enumerable domains from {pruned} descriptor(s): {dropped:,} bytes "
              f"(~{dropped//4:,} tokens)".replace(",", "."))
        if not a.apply:
            print("  (report only — pass --apply)")
        return 0

    todo = [f for d in ("datasets", "sources")
            for f in sorted(glob.glob(str(root / "data" / d / "*.yaml")))]
    for f in todo:
        p = pathlib.Path(f)
        n, saved = split(p, out, a.apply)
        if n:
            files += 1; tot += saved
            print(f"  {p.name:<36} {n:>3} columns · descriptor -{saved:,} bytes".replace(",", "."))
    print(f"\n  {files} descriptor(s), {tot:,} bytes moved to data/profiles/ (~{tot//4:,} tokens "
          f"off every request)".replace(",", "."))
    if not a.apply:
        print("  (report only — pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
