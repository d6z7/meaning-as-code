#!/usr/bin/env bash
# run_gates.sh — every gate in this package, and every gate's own self-test.
#
# Two runs per gate, deliberately. The self-test proves the gate can still REJECT; the real run
# reports what it finds. A suite that ran only the second kind is how eight gates reached this point
# with no mutant between them.
#
# THE COMMENT ABOVE USED TO BE FALSE, AND THE CODE IS WHAT WAS FIXED.
# ------------------------------------------------------------------
# MEASURED 2026-09-13: the loop below ran ONLY `--self-test`. There was no real run at all, so the
# header's "two runs per gate" described an intention, not this file. The final line read
# `PASS: run_gates — 9/9 gate self-tests green` — accurate about the self-tests and silent about the
# fact that no gate had been pointed at a subject. Running the nine for real for the first time:
# four examined something, FIVE exited 2 for want of an argument no runner passed them. One of them
# (`check_boundaries`, legacy mode) had been exiting 2 over directories that live in a different
# repository, and nothing said so.
#
# The fix is the code, not the comment: each gate now gets BOTH arms, and the real arm is given its
# subject from the declared table below rather than from a single guessed convention. That mismatch
# between "one calling convention" and "gates have several" is the documented cause of a false green
# in the sibling runner (see tools/run_framework_gates.sh, REPO_SUBJECT_GATES), so the subject is
# DECLARED PER GATE here, and a gate whose subject this repository cannot supply is marked UNWIRED
# BY NAME rather than quietly dropped.
#
# Exit 2 from any gate is "could not run" and is NOT a pass: it is counted separately and fails the
# suite, because "did not run" is the one verdict a gate must never be able to give silently. The
# same applies, for the same reason, to an UNWIRED real run: a gate this suite declares but does not
# point at anything is a could-not-run whose cause is the suite, and it keeps the suite red until an
# operator rules on the subject. A shrinking denominator must never be able to print green.
#
# THREE COUNTED CLASSES PER ARM, plus two disclosures:
#   pass (exit 0) · fail (exit 1) · could-not-run (exit 2) · crash/hang (any other code, named)
#   disclosure 1: UNWIRED real runs, by gate name and reason
#   disclosure 2: SILENT GREEN — exit 0 with no `PASS:` line. CORE.md §2 requires exactly one
#                 PASS:/FAIL: line; a gate that exits 0 without printing one has returned a code,
#                 not a verdict. Counted and named beside the totals, never folded into them,
#                 because inventing a pass/fail rule for it is an operator's call and not this
#                 runner's — but hiding it would be this runner's defect.
#
# Usage:
#   sdk/gate/run_gates.sh [bundle-root]      # bundle-root default: example_tpch_ontology
set -uo pipefail
# gate/ -> sdk/ -> src/  : `src` is the import root that makes `sdk.gate.*` resolvable.
cd "$(dirname "$0")/../.." || exit 2
REPO="$(pwd)"
export PYTHONPATH="${PYTHONPATH:-}:$REPO"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  sed -n '2,42p' "$0"
  exit 0
fi

# The bundle this suite points bundle-subject gates at. Printed on the final line: a verdict whose
# subject is not named is not reproducible.
BUNDLE="${1:-example_tpch_ontology}"
if [ ! -d "$REPO/$BUNDLE" ]; then
  echo "could not run: run_gates — '$BUNDLE' is not a directory under $REPO" >&2
  exit 2
fi

GATES=(annotation_isolation check_source_coupling check_write_paths check_rule_lock
       check_bundle_secrets check_host_coupling check_boundaries check_artifact
       check_grammar_home check_engine_coupling check_entry_points check_seam_agreement)

# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE DECLARED REAL-RUN SUBJECT TABLE
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# One line per gate, stating WHAT it is pointed at and, where it is pointed at nothing, WHY NOT.
# `UNWIRED:<reason>` is a first-class entry, not an omission: it is counted, printed, and fails the
# suite until an operator rules. Echoing nothing would be the same silence this file exists to end.
#
# check_host_coupling is UNWIRED on purpose and must stay that way until an operator rules.
#   Its subject is "a HOST (wiki / runtime)" — by its own docstring — and the hosts are in
#   mac-platform, a different repository. A gate reaching across a repository boundary to find its
#   subject is the exact defect documented in check_boundaries' legacy mode (configured over
#   `local_harvest/` and `mac_bridge/`, which do not exist here). Two candidates in THIS repo were
#   measured and both are wrong:
#     * `wiki/`  — `check_host_coupling wiki` exits 2: "wiki holds no python file — 0 examined is
#                  not the same as separated". It is compiled markdown, not a host.
#     * `sdk/`   — not a host; it is the thing a host is supposed to be separated FROM, so the gate
#                  would measure the wrong side of its own boundary.
#   And its token derivation reads `<repo>/sources/*/*/mac.project.yaml`, of which this repo has
#   NONE — so even a plausible host directory would be judged against an EMPTY token set, i.e. a
#   zero-denominator green. Guessing a subject here would manufacture exactly the false confidence
#   this suite exists to remove.
real_args() {  # real_args <gate> -> prints the argv for the real run, or UNWIRED:<reason>
  case "$1" in
    annotation_isolation)   echo "--root $REPO" ;;
    check_source_coupling)  echo "$REPO" ;;
    check_write_paths)      echo "--root $REPO" ;;
    # a content-root carrying an `ontology/` plane; this repo's example bundles are the only ones
    check_rule_lock)        echo "--content-root $REPO/$BUNDLE" ;;
    check_bundle_secrets)   echo "$REPO/$BUNDLE" ;;
    check_host_coupling)    echo "UNWIRED:subject is a HOST (wiki/runtime); hosts live in mac-platform, and no directory in this repo is one — OPERATOR RULING NEEDED" ;;
    # target mode ONLY. `--mode legacy` (the argparse default) is configured over `local_harvest/`
    # and `mac_bridge/` — the pre-split layout, which is not in this repository; it exits 2 with
    # "none of the configured directories exist". Target mode's dirs (`wiki/`, `sdk/`) are both here,
    # so target is the unambiguous half and legacy stays unrun. DISCLOSED on the final line.
    check_boundaries)       echo "--mode target --root $REPO" ;;
    check_artifact)         echo "--content-root $REPO/$BUNDLE" ;;
    check_grammar_home)     echo "--root $REPO" ;;
    check_engine_coupling)  echo "$REPO" ;;
    check_entry_points)     echo "$REPO" ;;
    check_seam_agreement)   echo "--root $REPO" ;;
    *)                      echo "UNWIRED:no subject declared in run_gates.sh's table" ;;
  esac
}

# Portable per-invocation timeout, same reasoning as tools/run_framework_gates.sh: macOS carries
# neither GNU `timeout` nor a guaranteed `gtimeout`, and a runner that hangs forever because ONE
# gate hangs is worse than one that occasionally runs long. 600s because check_entry_points spawns
# ~70 subprocesses of its own.
TIMEOUT_CMD=()
if command -v timeout >/dev/null 2>&1; then TIMEOUT_CMD=(timeout 600)
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD=(gtimeout 600); fi

run_capped() {  # run_capped <module> <arg>...  -- returns the process's code (124 on our timeout)
  if [ "${#TIMEOUT_CMD[@]}" -gt 0 ]; then "${TIMEOUT_CMD[@]}" python3 -m "$@"; else python3 -m "$@"; fi
}

st_pass=0; st_fail=0; st_cnr=0; st_crash=0; st_absent=0
rr_pass=0; rr_fail=0; rr_cnr=0; rr_crash=0; rr_unwired=0
silent=0
declare -a NOTES
declare -a UNWIRED_NOTES
declare -a SILENT_NOTES

T0=$(date +%s)

for g in "${GATES[@]}"; do
  out_st="$(mktemp)"; out_rr="$(mktemp)"

  # ---- arm 1: the self-test (can it still REJECT?) ----
  st_rc=""
  if grep -q -- '--self-test' "$REPO/sdk/gate/$g.py"; then
    run_capped "sdk.gate.$g" --self-test >"$out_st" 2>&1
    st_rc=$?
  fi
  if [ -z "$st_rc" ]; then
    st_absent=$((st_absent + 1)); st_v="no self-test"
    NOTES+=("  $g — declares no --self-test: nothing proves it can still reject")
  elif [ "$st_rc" = "0" ]; then
    st_pass=$((st_pass + 1)); st_v="PASS"
  elif [ "$st_rc" = "1" ]; then
    st_fail=$((st_fail + 1)); st_v="FAIL"
    NOTES+=("  $g self-test — $(grep -E '^(PASS|FAIL):' "$out_st" | tail -1 || tail -1 "$out_st")")
  elif [ "$st_rc" = "2" ]; then
    st_cnr=$((st_cnr + 1)); st_v="COULD-NOT-RUN"
    NOTES+=("  $g self-test — $(grep -E 'could not run:' "$out_st" | tail -1 || tail -1 "$out_st")")
  else
    st_crash=$((st_crash + 1)); st_v="CRASH (exit $st_rc)"
    NOTES+=("  $g self-test — exit $st_rc (a traceback or a hang is not a verdict): $(tail -1 "$out_st")")
  fi

  # ---- arm 2: the real run (what does it FIND, over a declared subject?) ----
  args="$(real_args "$g")"
  case "$args" in
    UNWIRED:*)
      rr_unwired=$((rr_unwired + 1)); rr_v="UNWIRED"
      UNWIRED_NOTES+=("  $g — ${args#UNWIRED:}")
      ;;
    *)
      # shellcheck disable=SC2086  -- the table's argv is deliberately word-split
      run_capped "sdk.gate.$g" $args >"$out_rr" 2>&1
      rr_rc=$?
      last="$(grep -E '^(PASS|FAIL):|could not run:' "$out_rr" | tail -1)"
      [ -n "$last" ] || last="$(tail -1 "$out_rr")"
      if [ "$rr_rc" = "0" ]; then
        rr_pass=$((rr_pass + 1)); rr_v="PASS"
        if ! grep -qE '^PASS:' "$out_rr"; then
          silent=$((silent + 1)); rr_v="PASS (no verdict line)"
          SILENT_NOTES+=("  $g — exit 0 but printed no 'PASS:' line; it said: $last")
        fi
      elif [ "$rr_rc" = "1" ]; then
        rr_fail=$((rr_fail + 1)); rr_v="FAIL"
        NOTES+=("  $g real run — $last")
      elif [ "$rr_rc" = "2" ]; then
        rr_cnr=$((rr_cnr + 1)); rr_v="COULD-NOT-RUN"
        NOTES+=("  $g real run — $last")
      else
        rr_crash=$((rr_crash + 1)); rr_v="CRASH (exit $rr_rc)"
        NOTES+=("  $g real run — exit $rr_rc (a traceback or a hang is not a verdict): $last")
      fi
      ;;
  esac

  printf '  %-24s self-test %-14s real %s\n' "$g" "$st_v" "$rr_v"
  rm -f "$out_st" "$out_rr"
done

T1=$(date +%s)
DECLARED=${#GATES[@]}
ST_TOTAL=$((st_pass + st_fail + st_cnr + st_crash))
RR_WIRED=$((rr_pass + rr_fail + rr_cnr + rr_crash))

if [ -n "${NOTES+x}" ] && [ "${#NOTES[@]}" -gt 0 ]; then
  echo
  echo "why (one line per non-pass):"
  printf '%s\n' "${NOTES[@]}"
fi
if [ -n "${UNWIRED_NOTES+x}" ] && [ "${#UNWIRED_NOTES[@]}" -gt 0 ]; then
  echo
  echo "UNWIRED real runs — counted as could-not-run, NOT as pass, and they keep this suite red:"
  printf '%s\n' "${UNWIRED_NOTES[@]}"
fi
if [ -n "${SILENT_NOTES+x}" ] && [ "${#SILENT_NOTES[@]}" -gt 0 ]; then
  echo
  echo "DISCLOSURE — exit 0 with no PASS: line (a code is not a verdict; CORE.md §2 wants both):"
  printf '%s\n' "${SILENT_NOTES[@]}"
fi
echo
echo "NOTE: check_boundaries' real run judges --mode target ONLY (wiki/, sdk/). Its --mode legacy" \
     "half (local_harvest/, mac_bridge/) is configured over a repository this is not, and is UNRUN."

echo
SUBJ="subjects: repo=$REPO, bundle=$BUNDLE"
if [ "$st_fail" = "0" ] && [ "$st_cnr" = "0" ] && [ "$st_crash" = "0" ] && [ "$st_absent" = "0" ] \
   && [ "$rr_fail" = "0" ] && [ "$rr_cnr" = "0" ] && [ "$rr_crash" = "0" ] && [ "$rr_unwired" = "0" ]; then
  echo "PASS: run_gates — self-test ${st_pass}/${ST_TOTAL} green over ${DECLARED} declared gate(s);" \
       "real run ${rr_pass}/${RR_WIRED} green over ${RR_WIRED} wired of ${DECLARED} declared;" \
       "${silent} exit-0-without-a-PASS-line; ${SUBJ} ($((T1 - T0))s)"
  exit 0
fi
echo "FAIL: run_gates — self-test ${st_pass}/${ST_TOTAL} green, ${st_fail} failing, ${st_cnr}" \
     "could-not-run, ${st_crash} crash/hang, ${st_absent} declaring no self-test, over ${DECLARED}" \
     "declared gate(s); real run ${rr_pass}/${RR_WIRED} green, ${rr_fail} failing, ${rr_cnr}" \
     "could-not-run, ${rr_crash} crash/hang, over ${RR_WIRED} wired of ${DECLARED} declared" \
     "(${rr_unwired} UNWIRED, named above, counted as could-not-run); ${silent}" \
     "exit-0-without-a-PASS-line; ${SUBJ} ($((T1 - T0))s)"
exit 1
