#!/usr/bin/env python3
"""
validate_schema.py — CI/local validator for the YAML ontology framework (schema v0.4).

Checks an ontology authored under this framework: concept files (<source>/concepts/**/*.yaml)
and edge files (<source>/edges.yaml, federation/edges.yaml).

Scope: structural + naming-contract + edge level/type legality. NOT a full JSON-Schema — a
focused rule-checker. A clean run (exit 0) means WELL-FORMED, not CORRECT (correctness is earned
by execution validation, not the validator). Exit code 0 = clean, 1 = violations found.

Usage:  python3 tools/validate_schema.py [--root <repo_root>]
        (defaults to scanning <root>/**/concepts and <root>/**/edges.yaml)
"""
import sys, glob, os, argparse
try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml"); sys.exit(2)

# ---- rule tables ---------------------------------------------------------
LEVEL_TYPES = {
    'physical':   {'foreign_key', 'composite_key', 'value_mapped_key'},
    'business':   {'identity'},
    'federation': {'same_real_world_event'},
}
BANISHED_EDGE_TYPES = {'containment', 'derivation'}      # now concept structure, not edges
VALID_CARDINALITY = {'0..1', '1', '0..N', '1..N', None}
# physical-name fields whose VALUES are allowed to be physical names
PHYSICAL_VALUE_FIELDS = {'column', 'code', 'grounds_column', 'eav_attribute',
                         'column_string_prefix', 'primary_table', 'source_table',
                         'primary_key_column', 'primary_tables', 'columns', 'join_rule',
                         'sql_assertion', 'grounds_column'}
CLOSURE_VALUES = {'open', 'closed', 'unknown', None}

errors, warnings = [], []
def err(f, msg): errors.append(f"ERROR  {f}: {msg}")
def warn(f, msg): warnings.append(f"WARN   {f}: {msg}")

# ---- edge validation -----------------------------------------------------
def validate_edge(f, e):
    eid = e.get('edge_id', '<no id>')
    where = f"{f} [{eid}]"
    level = e.get('level'); typ = e.get('type')
    if level is None:
        err(where, "missing required `level:` (physical|business|federation)")
    elif level not in LEVEL_TYPES:
        err(where, f"unknown level '{level}'")
    if typ == 'containment':
        err(where, "type 'containment' is banished in v0.3 — it is concept structure (contains_brands:), not an edge")
    elif typ == 'derivation':
        if level == 'federation':
            err(where, "federation edge must use type 'same_real_world_event', not legacy 'derivation'")
        else:
            err(where, "type 'derivation' is banished for intra-source edges in v0.3 — it is concept structure (derivation: block)")
    elif level in LEVEL_TYPES and typ not in LEVEL_TYPES[level]:
        err(where, f"type '{typ}' is not legal for level '{level}' (allowed: {sorted(LEVEL_TYPES[level])})")
    # payload by level
    if level == 'physical' and not e.get('join_rule'):
        # A physical edge is complete if it EITHER carries join_rule OR is realized_by a
        # concrete tables-layer FK (the FK supplies the join). Only a stub (TODO / nothing) warns.
        rb = e.get('realized_by')
        rb_str = str(rb)
        if rb and 'TODO' not in rb_str:
            pass  # realized by a concrete FK — the join lives at L1; OK
        elif 'TODO' in rb_str or not rb:
            warn(where, "physical edge not yet enriched — no `join_rule:` and realized_by is a TODO (enrichment pending)")
        else:
            err(where, "physical edge requires `join_rule:` or a concrete `realized_by:` FK")
    if level == 'business':
        if not e.get('realized_by'):
            err(where, "business identity edge requires `realized_by:` (point at the physical edge / FK)")
        if e.get('join_rule'):
            err(where, "business edge must NOT restate `join_rule:` — reference the physical edge via realized_by")
    if level == 'federation':
        if not e.get('derivation_rule'):
            err(where, "federation edge requires `derivation_rule:`")
        if not e.get('federation_concept_id'):
            err(where, "federation edge requires `federation_concept_id:`")
        if e.get('join_rule'):
            err(where, "federation edge must not carry a raw `join_rule:` (refers, never joins)")
    # cardinality — now lives under endpoints.from / endpoints.to as `cardinality:`
    eps = e.get('endpoints', {}) or {}
    for side in ('from', 'to'):
        v = (eps.get(side) or {}).get('cardinality')
        if v is not None and str(v) not in {'0..1','1','0..N','1..N'}:
            err(where, f"endpoints.{side}.cardinality='{v}' is not a valid multiplicity (0..1|1|0..N|1..N)")
    if 'cardinality_at_to' in e or 'cardinality_at_from' in e:
        warn(where, "top-level cardinality_at_to/_at_from is retired in v0.3 — move under endpoints.from/to as `cardinality:`")
    if 'required_at_from' in e:
        warn(where, "`required_at_from` is retired in v0.3 — use endpoints.from.cardinality (min 0|1)")

# ---- concept validation (naming contract + closure) ----------------------
SCHEMA_VOCAB_KEYS = None   # any bareword key is schema vocab; we check VALUES not keys

def check_closure(f, node, path):
    if isinstance(node, dict):
        if 'values' in node and 'closure' not in node and node.get('grounds_column') is not None:
            warn(f, f"enumeration at {path} grounds a column but has no `closure:` (open|closed|unknown)")
        if 'closure' in node and node['closure'] not in CLOSURE_VALUES:
            err(f, f"closure='{node['closure']}' at {path} invalid")
        for k, v in node.items():
            check_closure(f, v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, it in enumerate(node):
            check_closure(f, it, f"{path}[{i}]")

def validate_concept(f, d):
    # naming contract spot-check: enumerations: entries must use name: + grounds_column,
    # never a top-level key equal to a physical column name. We can't know all column names
    # here, but we CAN flag the known-collision pattern: a top-level key that looks physical.
    if isinstance(d, dict):
        for k in d:
            if isinstance(k, str) and (k.startswith('fpl_') or k.endswith('_concept')
                                       or k in {'is_actual_expectation_kpi','order_type','order_status'}):
                warn(f, f"top-level key '{k}' looks like a physical/ad-hoc name — v0.3 naming contract: "
                        f"author as a name:-bearing list entry (e.g. enumerations:) with grounds_column")
    check_closure(f, d, 'root')

# ---- v0.4 checks: rules layer + interpretive placement -------------------
RULE_RENDER_KINDS = {'sql_expression', 'sql_view', 'derived_set', 'spark_udf', 'spec_only'}
INTERPRETIVE_KEYS = {'purpose', 'scope', 'additivity', 'null_semantics', 'unit'}  # belong in semantics:
RULE_NAMES = set()          # populated from rules.yaml files
DERIVED_BY_RULE_REFS = []   # (file, rule_name) to resolve after all rules loaded

def validate_rule(f, r):
    rid = r.get('rule', '<no id>')
    where = f"{f} [rule {rid}]"
    if rid != '<no id>': RULE_NAMES.add(rid)
    rk = r.get('render_kind')
    if rk is None:
        err(where, "rule missing required `render_kind:`")
    elif rk not in RULE_RENDER_KINDS:
        err(where, f"render_kind '{rk}' not in {sorted(RULE_RENDER_KINDS)}")
    # payload by render_kind
    if rk in ('sql_expression', 'derived_set') and not (r.get('template') or r.get('sql') or r.get('sql_predicate')):
        err(where, f"render_kind {rk} requires a `template:` (or sql/sql_predicate) — the injected canonical SQL")
    if rk == 'sql_view' and not r.get('view_ref'):
        err(where, "render_kind sql_view requires `view_ref:` (the pre-deposited view)")
    if rk != 'spec_only' and not r.get('logic'):
        warn(where, "rule has a canonical form but no `logic:` spec — hybrid expects both")
    # injected rules should declare what to validate columns against
    if rk in ('sql_expression', 'derived_set') and not r.get('validated_against'):
        warn(where, "injected rule should carry `validated_against:` (tables whose columns the snippet uses)")

def check_interpretive_placement(f, d):
    # interpretive keys must live inside a `semantics:` block on a concept, not loose at concept top-level.
    concept = d.get('concept') if isinstance(d, dict) else None
    if isinstance(concept, dict):
        stray = [k for k in INTERPRETIVE_KEYS if k in concept]
        if stray:
            err(f, f"v0.4: interpretive keys {stray} are loose on `concept:` — move into `concept.semantics:`")
    # closure must not be a top-level key (value-set-level → value_set: or a nested enum block)
    if isinstance(d, dict) and 'closure' in d:
        err(f, "v0.4: top-level `closure:` — move into a `value_set:` block beside `values:`")
    # collect derived_by_rule refs for cross-file resolution
    for blk in (d.get('individual_kpis') if isinstance(d, dict) else None) or []:
        if isinstance(blk, dict) and blk.get('derived_by_rule'):
            DERIVED_BY_RULE_REFS.append((f, blk['derived_by_rule']))
    # v0.4: `rule` is reserved for derivations (rules.yaml). A constraints[] entry must use `assert:`,
    # never `rule:` — guards against the rename regressing.
    for cs in (d.get('constraints') if isinstance(d, dict) else None) or []:
        if isinstance(cs, dict) and 'rule' in cs:
            err(f, "v0.4: constraints[] entry uses `rule:` — rename to `assert:` ('rule' is reserved for derivations in rules.yaml)")

# ---- driver --------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    a = ap.parse_args()
    root = a.root

    # Layout-agnostic discovery: find concept/edge/rule files anywhere under --root, so the validator
    # works both standalone (e.g. example_shop_ontology/concepts/...) and when embedded in a larger
    # repo with its own directory layout. Skips VCS / tooling noise dirs.
    SKIP = {'.git', 'node_modules', '.venv', '__pycache__'}
    def _skip(path):
        return any(part in SKIP for part in path.split(os.sep))

    edge_files = [f for f in glob.glob(os.path.join(root, '**/edges.yaml'), recursive=True) if not _skip(f)]
    rule_files = [f for f in glob.glob(os.path.join(root, '**/rules.yaml'), recursive=True) if not _skip(f)]
    concept_files = [f for f in glob.glob(os.path.join(root, '**/concepts/**/*.yaml'), recursive=True) if not _skip(f)]

    for f in sorted(set(edge_files)):
        try: d = yaml.safe_load(open(f))
        except Exception as e: err(f, f"YAML parse failed: {e}"); continue
        for e in (d.get('edges') or []):
            validate_edge(f, e)

    for f in sorted(rule_files):           # v0.4 rules layer
        try: d = yaml.safe_load(open(f))
        except Exception as e: err(f, f"YAML parse failed: {e}"); continue
        for r in (d.get('rules') or []):
            validate_rule(f, r)

    for f in sorted(concept_files):
        try: d = yaml.safe_load(open(f))
        except Exception as e: err(f, f"YAML parse failed: {e}"); continue
        validate_concept(f, d)
        check_interpretive_placement(f, d)   # v0.4

    # resolve derived_by_rule refs now that all rule names are known
    for f, rname in DERIVED_BY_RULE_REFS:
        if rname not in RULE_NAMES:
            err(f, f"v0.4: derived_by_rule '{rname}' does not resolve to any rule in a rules.yaml")

    for w in warnings: print(w)
    for e in errors:   print(e)
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) "
          f"across {len(set(edge_files))} edge + {len(rule_files)} rules + {len(concept_files)} concept file(s).")
    sys.exit(1 if errors else 0)

if __name__ == '__main__':
    main()
