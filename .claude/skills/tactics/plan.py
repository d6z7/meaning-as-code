#!/usr/bin/env python3
"""What is runnable now, what is blocked, and on what. Reads decisions/PLAN.yaml."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
plan = yaml.safe_load((ROOT / "decisions" / "PLAN.yaml").read_text(encoding="utf-8"))
items = plan.get("items") or []
rulings = {r["id"]: r for r in (plan.get("rulings") or [])}
done = {i["id"] for i in items if i.get("state") == "done"}
brief = "--brief" in sys.argv[1:]

if brief:
    for i in items:
        print(f"  {i.get('state','?'):<10} {i['id']:<18} {i['what'][:70]}")
    sys.exit(0)

print(f"GOAL: {plan['goal'].strip()}\n")
flight = [i for i in items if i.get("state") == "in-flight"]
blocked = [i for i in items if i.get("state") == "blocked"]
ready = [i for i in items if i.get("state") not in {"done", "in-flight", "blocked"}]

print(f"IN FLIGHT ({len(flight)}):")
for i in flight:
    t = f"  testable now: {i['testable_now']}" if i.get("testable_now") else ""
    print(f"  {i['id']:<18} workflow={i.get('workflow','?')}{t}")

print(f"\nRUNNABLE NOW ({len(ready)}):")
for i in ready:
    print(f"  {i['id']:<18} {i['what'][:70]}")
if not ready:
    print("  (none — everything not done is in flight or blocked)")

print(f"\nBLOCKED ({len(blocked)}):")
for i in blocked:
    on = i.get("blocked_on") or []
    human = [b for b in on if b in rulings]
    print(f"  {i['id']:<18} on {', '.join(on)}" + ("   <- HUMAN RULING" if human else ""))

open_r = sorted({b for i in blocked for b in (i.get("blocked_on") or []) if b in rulings})
print(f"\nRULINGS THAT UNBLOCK WORK ({len(open_r)}) — batch these, never one at a time:")
for rid in open_r:
    r = rulings[rid]
    print(f"  {rid}  gates {', '.join(r.get('gates', []))}")
    print(f"      {r['question']}")
    for o in r.get("options", []):
        print(f"        - {o}")
