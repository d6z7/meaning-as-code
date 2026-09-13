#!/usr/bin/env bash
# run_gates.sh — every gate in this package, and every gate's own self-test.
#
# Two runs per gate, deliberately. The self-test proves the gate can still REJECT; the real run
# reports what it finds. A suite that ran only the second kind is how eight gates reached this point
# with no mutant between them.
#
# Exit 2 from any gate is "could not run" and is NOT a pass: it is counted separately and fails the
# suite, because "did not run" is the one verdict a gate must never be able to give silently.
set -uo pipefail
# gate/ -> sdk/ -> src/  : `src` is the import root that makes `sdk.gate.*` resolvable.
cd "$(dirname "$0")/../.." || exit 2
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

GATES=(annotation_isolation check_source_coupling check_write_paths check_rule_lock
       check_bundle_secrets check_host_coupling check_boundaries check_artifact
       check_grammar_home)

pass=0; fail=0; unrun=0; total=0
for g in "${GATES[@]}"; do
  total=$((total+1))
  if out=$(python3 -m "sdk.gate.$g" --self-test 2>&1); then
    pass=$((pass+1)); echo "$out" | grep -E '^PASS:' || echo "  PASS: $g self-test"
  else
    rc=$?
    if [ "$rc" = "2" ]; then unrun=$((unrun+1)); echo "  COULD NOT RUN: $g self-test"
    else fail=$((fail+1)); echo "  FAIL: $g self-test"; echo "$out" | tail -3; fi
  fi
done

echo
if [ "$fail" = "0" ] && [ "$unrun" = "0" ]; then
  echo "PASS: run_gates — $pass/$total gate self-tests green"
  exit 0
fi
echo "FAIL: run_gates — $pass/$total green, $fail failing, $unrun could-not-run"
exit 1
