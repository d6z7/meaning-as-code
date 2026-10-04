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
#
# THE SELF-TEST ARM HAD NO DENOMINATOR, MEASURED 2026-09-13.
# ---------------------------------------------------------
# This runner has always executed `--self-test` for every gate that declares one, and has always
# folded a self-test failure into that gate's verdict. What it never printed is HOW MANY gates have
# a self-test at all. Measured on this tree: 23 of 37. So 14 gates were judged on their real run
# ALONE, with nothing asserting they can still REJECT — and the final line said `30/37 green`
# without distinguishing the two kinds of evidence behind that 30.
#
# That is the same defect this file was built to remove, one level up: a number with no denominator.
# The self-test arm now reports its own denominator (declared / green / failing / could-not-run) and
# NAMES the gates that declare none. No verdict changes — a gate passes and fails exactly as before.
# The only change is that the suite can no longer imply evidence it does not have.
#
# NOT FIXED HERE, ON PURPOSE — two gates are miscounted as could-not-run and it would make this
# suite GREENER to fix, which needs an operator, not this runner:
#   check_topology.py       run bare: PASS (5 capabilities over 620 tracked files)
#   check_wiki_citations.py run bare: PASS (1021 citations over 34 pages)
# Both refuse <bundle-root> because their subject is THIS REPOSITORY, so both belong in
# REPO_SUBJECT_GATES below. Moving them turns 2 could-not-runs into 2 passes (30/37 -> 32/37)
# without proving one new thing, and it moves a published baseline. Left visible, not silently
# harvested: a suite must never get greener as a side effect of someone else's task.
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
if [ "${1:-}" = "--self-test" ]; then
  # The runner's own verdict logic lives in gate_register.py (pure, so every branch is reachable).
  exec python3 "$HERE/gate_register.py" --self-test
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

# THE STANDING-FAILURE REGISTER IS READ FIRST, so a malformed or ownerless register costs 0 s, not
# 110 s, and exits 2 (could-not-run) rather than turning every declared red into an undeclared one.
FRAMEWORK_REGISTER="$HERE/framework_gate_failures.yaml"
BUNDLE_REGISTER="$BUNDLE_ROOT/acceptance/standing_failures.yaml"
python3 "$HERE/gate_register.py" --check "$FRAMEWORK_REGISTER" "$BUNDLE_REGISTER" || exit 2

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

# GATES WHOSE SUBJECT IS THIS REPOSITORY, NOT A BUNDLE.
#
# This runner had ONE calling convention -- every gate gets <bundle-root> as argv[1] -- and gates
# have more than one. That mismatch was INVISIBLE while gates mis-read the argument instead of
# refusing it. Measured, and it is the worst kind of false green: `check_protocol`'s subject is this
# repo's own commit history, so `git log` read the bundle path as a PATHSPEC, the gate judged 7
# commits against a floor measured over 38, and PRINTED PASS. A wrong denominator silently
# substituted by the runner's own convention.
#
# It is now a DECLARED SET with its size printed, not a silent special case. A gate added here must
# be one whose subject is the repository; anything else belongs on the bundle path. And drift stays
# visible in both directions: a gate NOT listed here that refuses a bundle root still exits 2 and
# still fails this suite, so nothing is quietly forgiven by omission.
# 2026-09-29: seven more, MEASURED bare rather than assumed. The header above once claimed moving
# them would make the suite greener; run bare, five of the eight that refused a bundle root were
# FAILING (canon_documented, projection_field_parity, query_grammar, topology, vocabulary_parity)
# and two PASS (guard_scope, wiki_citations). Could-not-run had hidden five reds. `check_guardrails`
# needs a flag the runner has no convention for and stays declared in the register as cannot-open.
# `check_dangling_references` judges THIS repository's documents against THIS repository's baseline;
# handed a bundle root it reported 58 new and 35 stale — a calling-convention miss, not a finding.
# 2026-10-04: check_key_reference. Its subject is this repository's reference_manual/keys/ pages;
# a bundle only supplies the examples, so it takes no bundle root. It is also the FIRST generator in
# this repository whose --check the suite can see: the loop above globs `check_*.py`, so the five
# existing `gen_*.py --check` instruments are invisible to it, which is how shape_reference.md held
# `schema 0.1.14` against a 0.1.16 schema with nothing red.
# 2026-10-04, same day, three more of exactly that kind — check_schema_shapes, check_slot_reference and
# check_vocabulary_terms. Every one is a thin delegate to a `gen_*.py --check` the suite could not see,
# and each covered a measured false green: the 0.1.14 version claim and the missing `rulings` level on
# shape_reference.md; five raw Python dict reprs in column_map.generated.md's TERM MEANINGS; and
# `UNDOCUMENTED: 4` printed with exit 0 because the number reached no return statement. Four of the
# repository's seven generators are now visible to this runner. THE THREE STILL INVISIBLE, named rather
# than left to be rediscovered, and each MEASURED on this tree rather than assumed:
#   gen_column_bench.py --check   requires `--bundle <root>`; the runner's one convention is a POSITIONAL
#                                 bundle root, so wiring it needs a convention that does not exist yet.
#   gen_grammar_map.py  --check   requires `--runtime <path to mac_runtime>`; same gap, a sibling path.
#   gen_strategy.py     --check   runs bare and is GREEN (STRATEGY.md matches guardrails/strategy.yaml,
#                                 11 rungs, 6 principles) — but it prints `OK —`, not one PASS:/FAIL:
#                                 line, and declares no --self-test, so wiring it would add a gate that
#                                 does not meet the contract. It is NOT check_strategy.py's question:
#                                 that one resolves the references INSIDE strategy.yaml. Left visible and
#                                 unharvested — a suite must never get greener as a side effect.
REPO_SUBJECT_GATES=(check_protocol.py check_canon_documented.py check_projection_field_parity.py
  check_query_grammar.py check_topology.py check_vocabulary_parity.py check_guard_scope.py
  check_wiki_citations.py check_dangling_references.py check_strategy.py check_declarations_read.py
  check_key_reference.py check_schema_shapes.py check_slot_reference.py check_vocabulary_terms.py)

repo_subject() {  # repo_subject <basename> -- 0 if this gate takes no bundle root
  local n="$1" g
  for g in "${REPO_SUBJECT_GATES[@]}"; do [ "$n" = "$g" ] && return 0; done
  return 1
}

PASS=0
FAIL=0
CNR=0
REPO_SUBJ=0
# The SELF-TEST arm's own denominator. Counted separately from the bundle run because they are
# different evidence about different things: "can this gate still reject?" and "what does it find
# here?". One number covering both is the conflation this block exists to end.
ST_DECL=0
ST_NONE=0
ST_PASS=0
ST_FAIL=0
ST_CNR=0
declare -a NOTES
declare -a NO_SELFTEST

T0=$(date +%s)
RAW_TSV="$(mktemp)"   # gate<TAB>verdict<TAB>last line — what gate_register.py reconciles at the end

for checker in "$HERE"/check_*.py; do
  name="$(basename "$checker")"
  out_run="$(mktemp)"
  out_st="$(mktemp)"

  st_rc=""
  if grep -q -- '--self-test' "$checker"; then
    ST_DECL=$((ST_DECL + 1))
    run_capped "$checker" --self-test >"$out_st" 2>&1
    st_rc=$?
    if [ "$st_rc" = "0" ]; then ST_PASS=$((ST_PASS + 1))
    elif [ "$st_rc" = "2" ]; then ST_CNR=$((ST_CNR + 1))
    else ST_FAIL=$((ST_FAIL + 1)); fi
  else
    ST_NONE=$((ST_NONE + 1))
    NO_SELFTEST+=("$name")
  fi

  if repo_subject "$name"; then
    REPO_SUBJ=$((REPO_SUBJ + 1))
    run_capped "$checker" >"$out_run" 2>&1
  else
    run_capped "$checker" "$BUNDLE_ROOT" >"$out_run" 2>&1
  fi
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
  printf '%s\t%s\t%s\n' "$name" "$verdict" "$last_run" >>"$RAW_TSV"
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

if [ -n "${NO_SELFTEST:-}" ] && [ "${#NO_SELFTEST[@]}" -gt 0 ]; then
  echo
  echo "DISCLOSURE — ${#NO_SELFTEST[@]} of ${TOTAL} gate(s) declare NO --self-test, so nothing here"
  echo "asserts they can still REJECT; their verdict above rests on the bundle run alone:"
  for n in "${NO_SELFTEST[@]}"; do
    echo "  $n"
  done
fi

# THE VERDICT IS THE REGISTER'S, NOT THE COUNT'S. Exit 1 fires only on NEWS — a red nobody
# declared, a declaration that outlived its red, a declared kind that is not what happened. A PASS
# line may carry standing failures, but every one is printed above it with an owner; it can never
# say a bare PASS. The counters this script kept are handed over so no denominator moves.
python3 "$HERE/gate_register.py" --reconcile "$RAW_TSV" \
  --registers "$FRAMEWORK_REGISTER" "$BUNDLE_REGISTER" --bundle "$BUNDLE_ROOT" \
  --counts PASS=$PASS FAIL=$FAIL CNR=$CNR TOTAL=$TOTAL REPO_SUBJ=$REPO_SUBJ \
          BUNDLE_JUDGED=$((TOTAL - REPO_SUBJ)) ST_PASS=$ST_PASS ST_DECL=$ST_DECL ST_FAIL=$ST_FAIL \
          ST_CNR=$ST_CNR ST_NONE=$ST_NONE SECS=$((T1 - T0))
rc=$?
rm -f "$RAW_TSV"
exit $rc
