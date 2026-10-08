#!/usr/bin/env bash
# Regenerate every BIRD dev bundle ON DEMAND. The output is NOT checked in.
#
# WHY THIS EXISTS, AND WHY ITS PREMISE CHANGED ON 2026-10-08. It used to read "`bundlegen/generated/
# bird/` is checked in, which is only useful if it can be reproduced". The operator then ruled that a
# generic framework ships no ontology, and the 394 committed files went: eleven complete bundles, all
# eleven failing this repository's own validator because three column-surface shapes had been retired
# under them without anything checking. A committed artefact nobody can regenerate is a claim rather
# than evidence — but a committed artefact that silently rots against its own schema is worse, and
# that is what eleven of them were.
#
# So read the DIFF the way you always did, just against a local run rather than against git: emit
# once before your change to the generator and once after, and diff the two trees. 11 real schemas,
# 84 concepts and 106 edges will tell you what the change actually did, which a passing self-test
# will not.
#
# The databases are NOT in this repo (1.4 GB). benchmark/SOURCES.md carries the URL and the
# sha256; unpack them anywhere and point BIRD_DB at the `dev_databases` directory.
set -euo pipefail

BIRD_DB="${BIRD_DB:-$HOME/dev/benchmarks/bird/dev_20240627/dev_databases}"
OUT="$(cd "$(dirname "$0")" && pwd)/generated/bird"
PY="${PY:-$HOME/dev/mac-platform/.venv/bin/python}"
GEN="$(cd "$(dirname "$0")" && pwd)/generate.py"

if [ ! -d "$BIRD_DB" ]; then
  echo "REFUSED: no databases at $BIRD_DB"
  echo "  benchmark/SOURCES.md has the URL and the sha256. Set BIRD_DB to the unpacked"
  echo "  dev_databases directory. Regenerating nothing and reporting success is the one"
  echo "  outcome this script must never have."
  exit 2
fi

n=0
for db in "$BIRD_DB"/*/*.sqlite; do
  name="$(basename "$db" .sqlite)"
  # NOT `| head -1`. That swallowed the generator's own load check -- the line that says whether
  # what it wrote can actually be parsed -- so the script reported 11 successes over 11 bundles
  # that all failed to load.
  "$PY" "$GEN" --db "$db" --out "$OUT/${name}_L1" --tier L1 --namespace "$name" \
    | grep -E "^tier |loads|UNLOADABLE|NOT CHECKED"
  n=$((n + 1))
done
echo
echo "regenerated $n bundle(s) into $OUT"
[ "$n" -eq 11 ] || { echo "EXPECTED 11 databases, generated $n — the corpus is incomplete"; exit 1; }
