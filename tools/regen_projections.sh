#!/usr/bin/env bash
# regen_projections.sh — regenerate ALL MAC projections for a project root (every projector), and render
# .svg companions for each .mmd WHEN a Mermaid renderer (mmdc) is available (skipped gracefully otherwise).
#
# Used for two QUALITY.md gates: the cross-projector impact check (regenerate all, then git-diff — only the
# intended outputs may move) and the applied-instance test (point it at an applied ontology, e.g. shop/tpch).
#
#   tools/regen_projections.sh <project_root>
#
# The project display name is the lowercased metadata.source (fallback: the dir basename), matching the
# name each projector embeds in its output filenames.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${1:?usage: regen_projections.sh <project_root>}" && pwd)"
PROJ="$ROOT/projections"
PY="${PYTHON:-python3}"
mkdir -p "$PROJ"

NAME="$("$PY" - "$ROOT" <<'PYEOF'
import sys, glob, os, yaml
root = sys.argv[1]
src = None
pats = [os.path.join(root, 'ontology', 'concepts', '**', '*.yaml'),
        os.path.join(root, 'concepts', '**', '*.yaml')]
for pat in pats:
    for f in sorted(glob.glob(pat, recursive=True)):
        d = yaml.safe_load(open(f)) or {}
        s = (d.get('metadata') or {}).get('source')
        if s:
            src = str(s); break
    if src:
        break
print((src or os.path.basename(root)).lower())
PYEOF
)"
echo "regenerating projections for '$NAME'  ($ROOT)"

gen () {  # gen <label> <tool.py> <output> [extra-args...]
  echo "  → $3"
  "$PY" "$HERE/$2" "$ROOT" -o "$PROJ/$3" "${@:4}"
}

gen osi   mac_to_osi.py     "$NAME.osi.yaml"
gen rdf   mac_to_rdf.py     "$NAME.ttl"
gen graph mac_to_graph.py   "$NAME.graph.cypher"
gen shacl mac_to_shacl.py   "$NAME.shacl.ttl"
# Mermaid views (one exporter, mode by flag). Flowcharts use --direction LR (portrait for wide projects).
gen onto  mac_to_mermaid.py "$NAME.mmd" --ontology --direction LR
gen er    mac_to_mermaid.py "$NAME.er.mmd" --er
gen pher  mac_to_mermaid.py "$NAME.physical.er.mmd" --physical
gen okf   mac_to_okf.py     "$NAME.okf"

# operator manual (docs/manual.md, from docs/manual.template.md + the ontology) — a source-side doc, NOT a
# projections/ artifact, so it is generated in place rather than via gen(). Runs BEFORE the explorer so the
# fresh manual is embedded in the Manual tab. A project with no template is a graceful no-op (exit 0).
echo "  → docs/manual.md (regenerated when the project ships a template)"
"$PY" "$HERE/mac_to_manual.py" "$ROOT"

gen expl  mac_to_explorer.py "$NAME.explorer.html"

# data-plane lineage — only emits when the project declares a data plane with transforms
if "$PY" "$HERE/mac_to_mermaid.py" "$ROOT" --lineage --direction LR -o "$PROJ/$NAME.data_lineage.mmd" 2>/dev/null; then
  echo "  → $NAME.data_lineage.mmd"
else
  echo "  (no data/transforms — skipping lineage projection)"
fi

# optional .svg companions for every .mmd (QUALITY.md point 2) — graceful when no renderer is present.
# mmdc drives a headless browser via puppeteer; auto-discover a LOCAL chrome-headless-shell so applied-ontology/example
# bytes never leave the machine (no remote renderer). One-time browser install:
#   npx puppeteer browsers install chrome-headless-shell
if command -v mmdc >/dev/null 2>&1; then
  BROWSER="${PUPPETEER_EXECUTABLE_PATH:-$(find "$HOME/.cache/puppeteer" -type f -name chrome-headless-shell 2>/dev/null | head -1)}"
  PCFG=""
  if [ -n "$BROWSER" ]; then
    PCFG="$(mktemp -t pptr).json"
    printf '{"executablePath":"%s","args":["--no-sandbox","--disable-gpu"]}' "$BROWSER" > "$PCFG"
  fi
  for f in "$PROJ"/*.mmd; do
    [ -e "$f" ] || continue
    if mmdc ${PCFG:+-p "$PCFG"} -i "$f" -o "${f%.mmd}.svg" >/dev/null 2>&1; then
      echo "  → $(basename "${f%.mmd}.svg")"
    else
      echo "  (svg render failed for $(basename "$f") — install a headless Chrome: npx puppeteer browsers install chrome-headless-shell)"
    fi
  done
  [ -n "$PCFG" ] && rm -f "$PCFG"
else
  echo "  (mmdc not installed — .mmd only; brew install mermaid-cli for .svg companions)"
fi
echo "done."
