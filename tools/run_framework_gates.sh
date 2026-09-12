#!/usr/bin/env bash
# run_framework_gates.sh — ONE runner for every tools/check_*.py gate this framework ships.
#
# WHY THIS EXISTS
# ----------------
# The 2026-09-12 framework-gate review measured 34 `check_*.py` scripts run one at a time, by hand,
# with no aggregate verdict — so a single failing or silently-not-running gate among 34 was easy to
# miss, and nothing printed a denominator for "how many of the framework's own gates actually ran".
# This script is that denominator: it runs every checker against ONE bundle root, runs each
# checker's own `--self-test` where it declares one, and prints exactly one final line.
#
# A checker's `--self-test` support is detected the same way every wired self-test in this repo
# signals it: the literal string `--self-test` appears in its source. A checker with no such string
# is never invoked with the flag — several accept ANY argument positionally, so passing an
# unsupported flag would be silently (mis)read as a bundle root instead of being refused, which is
# exactly the defect class this runner exists to catch, not reproduce.
#
# THE CONTRACT (CORE.md §2), applied to the AGGREGATE itself:
#   * exactly one PASS:/FAIL: line, last
#   * exit 0 (all green) or 1 (anything else) — never a bare success on a partial run
#   * exit 2 reserved for could-not-run (a bad bundle root argument to THIS script)
#   * a checker's own exit 2 ("could not run") is counted SEPARATELY from pass and fail, and can
#     never make the aggregate print a plain PASS line — a could-not-run is not a verdict, and
#     folding it into "green" would be exactly the false confidence this program was built to remove
#
# Usage:
#   tools/run_framework_gates.sh <bundle-root>
#
# A gate is judged failed if EITHER its own run against the bundle exits 1, OR its `--self-test`
# (when it has one) exits 1 — a checker whose self-test cannot pass is not trustworthy evidence about
# the bundle, whatever its own run against the bundle happened to say.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
usage: tools/run_framework_gates.sh <bundle-root>

Runs every tools/check_*.py in this framework against <bundle-root>, plus each checker's own
--self-test where it declares one. Prints one line per checker and one final PASS:/FAIL: line.
Exit 0 = every checker green. Exit 1 = at least one failed or could not run. Exit 2 = this
script itself could not run (bad or missing bundle-root argument).
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ "${1:-}" = "" ]; then
  usage >&2
  echo "could not run: no bundle-root given" >&2
  exit 2
fi

BUNDLE_ROOT="$1"
if [ ! -d "$BUNDLE_ROOT" ]; then
  echo "could not run: '$BUNDLE_ROOT' is not a directory" >&2
  exit 2
fi
BUNDLE_ROOT="$(cd "$BUNDLE_ROOT" && pwd)"

# Portable per-invocation timeout. macOS carries neither `timeout` (GNU coreutils) nor a guarantee
# of `gtimeout` (brew coreutils); a runner that hangs forever because ONE checker hangs is worse
# than one that occasionally lets a checker run long, so this degrades gracefully rather than
# failing when neither is present.
TIMEOUT_CMD=()
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_CMD=(timeout 120)
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_CMD=(gtimeout 120)
fi

run_capped() {
  # run_capped <script> <arg>...   -- prints nothing, returns the process's exit code (124 on our
  # own timeout, distinct from the checker's own 0/1/2 so a hang is never misread as could-not-run).
  if [ "${#TIMEOUT_CMD[@]}" -gt 0 ]; then
    "${TIMEOUT_CMD[@]}" python3 "$@"
  else
    python3 "$@"
  fi
}

PASS=0
FAIL=0
CNR=0
declare -a NOTES

T0=$(date +%s)

for checker in "$HERE"/check_*.py; do
  name="$(basename "$checker")"
  out_run="$(mktemp)"
  out_st="$(mktemp)"

  st_rc=""
  if grep -q -- '--self-test' "$checker"; then
    run_capped "$checker" --self-test >"$out_st" 2>&1
    st_rc=$?
  fi

  run_capped "$checker" "$BUNDLE_ROOT" >"$out_run" 2>&1
  run_rc=$?

  last_run="$(grep -E '^(PASS|FAIL):|could not run:' "$out_run" | tail -1)"
  [ -n "$last_run" ] || last_run="$(tail -1 "$out_run")"

  if [ "$run_rc" = "2" ] || [ "$st_rc" = "2" ]; then
    CNR=$((CNR + 1))
    verdict="COULD-NOT-RUN"
    NOTES+=("  $name — $last_run")
  elif [ -n "$st_rc" ] && [ "$st_rc" != "0" ]; then
    FAIL=$((FAIL + 1))
    verdict="FAIL (self-test)"
    last_st="$(grep -E '^(PASS|FAIL):' "$out_st" | tail -1)"
    [ -n "$last_st" ] || last_st="$(tail -1 "$out_st")"
    NOTES+=("  $name — self-test: $last_st")
  elif [ "$run_rc" = "0" ]; then
    PASS=$((PASS + 1))
    verdict="PASS"
  else
    FAIL=$((FAIL + 1))
    verdict="FAIL (exit $run_rc)"
    NOTES+=("  $name — $last_run")
  fi

  printf '  %-42s %s\n' "$name" "$verdict"
  rm -f "$out_run" "$out_st"
done

T1=$(date +%s)
TOTAL=$((PASS + FAIL + CNR))

if [ -n "${NOTES:-}" ] && [ "${#NOTES[@]}" -gt 0 ]; then
  echo
  echo "why (first line of each non-pass verdict):"
  for n in "${NOTES[@]}"; do
    echo "$n"
  done
fi

echo
if [ "$FAIL" -eq 0 ] && [ "$CNR" -eq 0 ]; then
  echo "PASS: run_framework_gates — ${PASS}/${TOTAL} green over ${BUNDLE_ROOT} ($((T1 - T0))s)"
  exit 0
fi
echo "FAIL: run_framework_gates — ${PASS}/${TOTAL} green, ${FAIL} failing, ${CNR} could-not-run" \
     "over ${BUNDLE_ROOT} ($((T1 - T0))s)"
exit 1
