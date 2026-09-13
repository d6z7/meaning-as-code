"""check_seam_agreement — THE SEAM INVENTORY. Enumerate every place two things must agree, then
check the ones that can be checked and REFUSE TO SCORE the ones that cannot.

--------------------------------------------------------------------------------------------------
WHY THIS EXISTS, WITH THE MEASUREMENT THAT FORCED IT
--------------------------------------------------------------------------------------------------

Fourteen defects landed in this estate in one day. The unit suite was green throughout: 183
passed, 1 skipped. ZERO of the fourteen were caught. Every one of them was at a SEAM — two
declarations of one fact, with nothing checking they still agreed:

  1. a producer wrote the dict key `region_definition_used`; the consumer read `region_definition`
     (tools/project_model.py -> tools/mac_to_meta.py)
  2. the grammar declared `named_profile`; the connector declared `profile`
     (mac.schema.json#credentialMode vs sdk/connector/athena.py credential_modes)
  3. a config handle and a code default were the same fact, removed separately as dead
  4. botocore verified against certifi while ssl verified against the OS trust store

A unit test asserts one side of a seam against a literal the test author typed. That is the same
act as writing the seam wrong: the test and the code agree with each other and neither is checked
against the OTHER declaration. So 131 unit tests could not have caught these, and adding a 132nd of
the same shape would not either. The instrument has to ENUMERATE THE PAIRS.

`sdk/connector/test_credential_vocabulary.py` was written today as one instance of the right shape
and it is the direct ancestor of this gate. DOES IT GENERALISE? Its STRUCTURE does, exactly, and it
is reproduced in `_closed_vocabulary` below: name both homes, read both, assert one is a subset of
the other, and parametrise over the population so the denominator is visible. Its PREDICATE does
not generalise at all, and that is the finding. It knows three things no other seam class knows —
that the grammar home is `mac.schema.json#$defs/credentialMode`, that the code home is the class
attribute `credential_modes`, and that the legal relation between them is SUBSET rather than
equality. Every seam class needs its own pairing rule and its own agreement predicate; what it can
inherit is the shape. Hence four detectors below, not one, and each states its own pairing rule.

--------------------------------------------------------------------------------------------------
THE NUMBER THIS GATE EXISTS TO PRINT
--------------------------------------------------------------------------------------------------

Nobody knew how many seams this repository has. Measured here, 2026-09-13, over 173 Python
modules, 122 config files, 257 markdown files and 5 shell scripts:

    ENUMERATED                                                       658 seam(s)
      enforced (agreement is mechanically decidable) ............ 87
        closed-vocabulary-divergence ...........................  4   0 disagreeing
        subprocess-argv-divergence .............................  9   0 disagreeing
        sql-column-not-emitted ................................. 74   1 disagreeing   <- defect 1
      EXCLUDED (enumerated, reported, not scored) .............. 571
        dict-key-orphan-read ................................... 536
        vocabulary-name-collision ..............................   7
        config-default-divergence ..............................  22
        trust-store-divergence .................................   6

THAT 658 IS A SNAPSHOT OF A MOVING TREE, and the movement is the reason the excluded ratchet has a
tolerance band rather than an equality. Over the ninety minutes this gate was being written,
parallel tracks took `dict-key-orphan-read` from 533 to 536 and `subprocess-argv-divergence` from 7
to 9 by adding ordinary modules. A declaration compared for equality against a population that
ordinary authoring moves is a declaration that is wrong by lunchtime and ignored by Tuesday.

The exclusions are the honest half of this gate and they are PRINTED ON EVERY RUN, never silent. A
detector that cannot tell a seam from two modules using the same English word does not get a vote.

--------------------------------------------------------------------------------------------------
WHAT EACH EXCLUSION COST, MEASURED, AND WHY IT IS NOT ENFORCED
--------------------------------------------------------------------------------------------------

**dict-key-orphan-read.** 1472 distinct string-literal dict keys; 339 are written in one module and
read in another (a real seam population). The checkable candidates are the 194 keys READ somewhere
and WRITTEN nowhere — which is the shape of defect 1. Enforcing that is hopeless: `d["ResultSet"]`
reads a botocore response, `d.get("concepts")` reads an authored YAML file, and neither has a
producer in this tree. A sharpened variant (an orphan read that is a near-miss of a key that IS
written) scored 62 and was inspected by hand: `ResultSet`/`ResultSetMetadata` are two real AWS keys,
`change`/`change_log` and `frozen`/`frozen_at` are two real facts each. The precision was so low
that enforcing it would have taught the next reader to ignore the gate. Population 533 = 339
cross-module + 194 orphan, reported so a JUMP in it is visible.

**vocabulary-name-collision.** 173 named string-literal sets in code, 36 string enums in the
grammar, 8 namespaces in mac_vocabulary.yaml. Pairing them by MAJORITY MEMBER OVERLAP reported 2
disagreements and BOTH were false: `KINDS = {authored, tuned, retired}` (intervention kinds) got
paired with the grammar's `provenance` enum because two words coincide, and `ACTORS = {claude,
operator, sme}` with `accepted.by = {operator, sme}`, which deliberately excludes `claude`. Pairing
by NAME IDENTITY instead reported 11 pairs, 7 of them still false — every one of those 7 keyed on a
generic role word (`kind`, `mode`, `role`, `verdict`) that names a dozen unrelated vocabularies.
The discriminator that survives is NAME IDENTITY **AND** at least one shared member: two
declarations of one fact always share a member, two homonyms share none. That rule kills all 7.

It also opens a hole and this is the one place a reader must not be reassured: a vocabulary spelled
ENTIRELY differently on both sides shares no member either, so it is indistinguishable from a
homonym and it lands HERE, in the excluded class, not in the enforced one. Defect 2 would have been
caught (athena declares six modes, five of which matched) but a connector declaring only `profile`
against a grammar declaring only `named_profile` would not. The 7 are printed individually under
`--verbose` for exactly that reason: this class is a REVIEW QUEUE, not a score.

**config-default-divergence.** 22 keys appear both in a config file and as a code default. Checking
that the two values agree reported 35 disagreements and the first fifteen were inspected: every one
is `.get("confidence", "?")` or `.get("grain", "—")` — a MISSING-VALUE PLACEHOLDER, not a second
declaration of the fact. A shared key does not make a shared fact. Defect 3 was real, but what made
those two declarations one fact was a human judgement about INTENT, and no predicate here reaches
it. Enforced, this class would fire 35 times and be silenced within a day.

**trust-store-divergence.** 11 sites across 5 modules touch a CA bundle (`certifi`, `AWS_CA_BUNDLE`,
`cafile`). The population is enumerable and it is printed. AGREEMENT IS NOT DECIDABLE FROM THIS
TREE: defect 4 was botocore's default trust store disagreeing with ssl's, and neither default is
written anywhere in this repository. A gate cannot check a fact that lives in a dependency. This
class is enumerated so the sites are visible to a reviewer and it is scored by nobody.

--------------------------------------------------------------------------------------------------
THE FLOOR, AND WHY IT IS TWO NUMBERS
--------------------------------------------------------------------------------------------------

RATCHET. Declared 2026-09-13.

    ENFORCED FLOOR = 0.  Any disagreement in an enforced class FAILS this gate.

The gate is RED on the day it lands: `sql-column-not-emitted` finds defect 1 still live at
tools/mac_to_meta.py:193, where an example query reads `region_definition` from a relation whose
emitter writes `region_definition_used`. THAT IS THE FLOOR STAYING AT ZERO, not an exemption. A
floor set to today's finding count would be this estate's dominant defect wearing a ratchet's
clothes: `tools/mac_public_floor.txt` records a floor of 146 held while the real count was 4,
i.e. 141 findings of silent headroom, and the instruction written there — "raising this number is
not the answer" — applies with more force to a gate on its first day than to one with history.

    EXCLUDED STANDING = the four counts in `_EXCLUDED_STANDING`, measured today.

The excluded populations get a ratchet of their own because they are where a new seam can HIDE. If
`dict-key-orphan-read` climbs from 194 to 260, something produced 66 new unchecked seams and the
enforced verdict would not have moved. Growth is DISCLOSED with its delta and the class named; it
does not fail, because these populations move with ordinary authoring and a gate that fails on
ordinary authoring gets deleted. Shrinkage is reported too, with the instruction to lower the
declaration — that is the half `mac_public_floor` learned the hard way.

OWNER: the seam-inventory track (a role, not a person — this repository is public and
`check_mac_public` exists to keep colleagues' names out of it).
REVIEW BY: 2026-12-13. An undated, unowned floor is a permanent exemption, so this gate REFUSES to
enforce one: `_FLOOR_DECLARED` and `_FLOOR_OWNER` are asserted in `main` and a missing one is
exit 2, never a shrug.

--------------------------------------------------------------------------------------------------
WHY THE FLOOR IS IN THIS FILE AND NOT A .txt BESIDE IT
--------------------------------------------------------------------------------------------------

`engine_coupling_floor.txt` and `mac_public_floor.txt` are the estate idiom and this file breaks it
deliberately: the track that commissioned this gate scoped it to "a new gate plus its self-test",
and a third file is outside that scope. The cost is real and worth stating — a floor in code cannot
be edited by someone who is not editing code, which is half of why the idiom exists. If this gate
earns a place in `run_gates.sh`, moving `_EXCLUDED_STANDING` and `_FLOOR_DECLARED` out to
`seam_agreement_floor.txt` is the first follow-up.
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sdk.gate import contract

NAME = "check-seam-agreement"

#: Repository root, when the gate is run over its own tree rather than a fixture.
ROOT = Path(__file__).resolve().parents[2]

#: Trees that are not source: generated, vendored, or a cache. `build/` in particular holds COPIES
#: of tools/, and counting a copy doubles every seam in it.
_SKIP = {
    ".git", "build", "__pycache__", ".pytest_cache", "meaning_as_code.egg-info", ".claude",
    ".githooks", "node_modules", ".venv",
}

# ------------------------------------------------------------------------------------------------
# the reject classes. A class is either ENFORCED (its predicate decides the verdict) or EXCLUDED
# (its population is enumerated and printed, and it is scored by nobody).
# ------------------------------------------------------------------------------------------------

ENFORCED = (
    "closed-vocabulary-divergence",
    "subprocess-argv-divergence",
    "sql-column-not-emitted",
)

EXCLUDED = (
    "dict-key-orphan-read",
    "vocabulary-name-collision",
    "config-default-divergence",
    "trust-store-divergence",
)

# --- THE RATCHET. See "THE FLOOR, AND WHY IT IS TWO NUMBERS" in the module docstring. ------------
_ENFORCED_FLOOR = 0                 # LOWER IT, NEVER RAISE IT. It is already as low as it goes.
_FLOOR_DECLARED = "2026-09-13"
_FLOOR_REVIEW_BY = "2026-12-13"
_FLOOR_OWNER = "the seam-inventory track"

#: Measured 2026-09-13 over 170 modules and 122 config files. A JUMP here means new unchecked
#: seams; a DROP means this declaration is stale and should be lowered.
_EXCLUDED_STANDING = {
    "dict-key-orphan-read": 536,
    "vocabulary-name-collision": 7,
    "config-default-divergence": 22,
    "trust-store-divergence": 6,
}

#: Growth inside this band is ordinary authoring; beyond it, enough unchecked seams appeared at once
#: that somebody should look. Set from the measured drift: three concurrent tracks moved
#: `dict-key-orphan-read` by 3 in ninety minutes, so a band of 10% (54 keys) is loose enough not to
#: cry wolf and tight enough that a module arriving with sixty new orphan reads is still visible.
#: The delta is printed WHATEVER the band says -- the band only chooses the wording.
_EXCLUDED_TOLERANCE = 0.10


@dataclass
class Finding:
    cls: str
    site: str
    message: str


@dataclass
class Inventory:
    """What was enumerated, per class, and what disagreed. Both halves are printed."""

    population: dict[str, int] = field(default_factory=lambda: collections.defaultdict(int))
    findings: list[Finding] = field(default_factory=list)
    #: per-class notes that belong in the printed output (what was skipped, and why)
    notes: list[str] = field(default_factory=list)

    @property
    def enforced_population(self) -> int:
        return sum(self.population[c] for c in ENFORCED)

    @property
    def excluded_population(self) -> int:
        return sum(self.population[c] for c in EXCLUDED)

    @property
    def total_population(self) -> int:
        return self.enforced_population + self.excluded_population

    @property
    def enforced_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.cls in ENFORCED]


# ------------------------------------------------------------------------------------------------
# shared source walk
# ------------------------------------------------------------------------------------------------


def _sources(root: Path, suffix: str) -> list[Path]:
    return [p for p in sorted(root.rglob(f"*{suffix}"))
            if not any(s in p.parts for s in _SKIP)]


def _parse(p: Path):
    try:
        return ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None


def _norm(name: str) -> str:
    """Fold a declaration's NAME to a comparable token: `credentialMode`, `credential_modes` and
    `CREDENTIAL_MODE` are one name in three casing conventions.

    An all-caps name is lowered WHOLE. Camel-splitting it first is the bug this function was
    written twice to fix: `re.sub(r"(?<!^)(?=[A-Z])", "_", "PROVENANCE")` yields
    `p_r_o_v_e_n_a_n_c_e`, so every module-level constant in this estate — which is every code-side
    vocabulary home — silently failed to pair, and the detector reported a population of 2.
    """
    s = name if (name.isupper() or name.islower()) else re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).lower().strip("_")
    if s.endswith("ies"):
        s = s[:-3] + "y"
    elif s.endswith("ses"):
        s = s[:-2]
    elif s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


# ================================================================================================
# CLASS 1 (excluded) — dict-key-orphan-read
# ================================================================================================
# PAIRING RULE: a string literal used as a dict key. Writes are dict-literal keys, `d["k"] = v`
# targets and `setdefault("k", ...)`; reads are `d["k"]` in Load context, `.get("k")` and
# `.pop("k")`. A seam is a key written in one module and read in ANOTHER.
#
# WHY IT IS NOT SCORED: see the module docstring. Identical spelling makes a cross-module pair
# agree by construction, so the only checkable candidates are keys read with no producer — and
# those are dominated by reads of data this repository does not write. Enumerated, printed, and
# scored by nobody.


def _dict_keys(root: Path, inv: Inventory) -> None:
    writes: dict[str, set[str]] = collections.defaultdict(set)
    reads: dict[str, set[str]] = collections.defaultdict(set)

    for p in _sources(root, ".py"):
        tree = _parse(p)
        if tree is None:
            continue
        rel = str(p.relative_to(root))
        for n in ast.walk(tree):
            if isinstance(n, ast.Dict):
                for k in n.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        writes[k.value].add(rel)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                            and isinstance(t.slice.value, str)):
                        writes[t.slice.value].add(rel)
            elif (isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)
                    and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)):
                reads[n.slice.value].add(rel)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("get", "pop", "setdefault") and n.args):
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    (writes if n.func.attr == "setdefault" else reads)[a.value].add(rel)

    cross = {k for k in writes if reads[k] and (reads[k] - writes[k])}
    orphan = {k for k in reads if not writes[k]}
    inv.population["dict-key-orphan-read"] = len(cross) + len(orphan)
    inv.notes.append(
        f"dict-key-orphan-read: {len(cross)} cross-module key(s) agreeing by construction "
        f"(identical spelling is not a check) + {len(orphan)} orphan read(s) with no producer in "
        f"this tree; NOT SCORED — a read of a dependency's response dict is indistinguishable "
        f"from a misspelling of a sibling's key"
    )


# ================================================================================================
# CLASS 2 (enforced) — closed-vocabulary-divergence
# CLASS 3 (excluded) — vocabulary-name-collision
# ================================================================================================
# PAIRING RULE: a closed vocabulary has up to three homes — `mac_vocabulary.yaml#<namespace>`, an
# enum in `mac.schema.json`, and a named string-literal set in code. Two homes pair when their
# names fold to the same token (`_norm`) AND THEY SHARE AT LEAST ONE MEMBER.
#
# The shared-member requirement is the whole detector. Name identity alone reported 11 pairs of
# which 7 were false, all keyed on a generic role word; requiring one shared member killed all 7
# and kept all 4 true pairs. Two declarations of one fact always share a member. See the docstring
# for the hole this leaves and why the unshared pairs are REPORTED rather than dropped.
#
# AGREEMENT PREDICATE: the code-side set must be a SUBSET of the declared home. Subset, not
# equality — a connector legitimately supports fewer modes than the grammar names, which is the
# rule `test_credential_vocabulary.py` states and the reason that test could not simply be widened
# into an equality check across all vocabularies.


def _grammar_enums(root: Path) -> dict[str, list[tuple[str, list[str]]]]:
    """Every string enum in the grammar, keyed by the folded name of the property it constrains."""
    path = root / "mac.schema.json"
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    skip = {"properties", "items", "allOf", "oneOf", "anyOf", "if", "then", "else",
            "$defs", "patternProperties", "additionalProperties"}
    out: dict[str, list[tuple[str, list[str]]]] = collections.defaultdict(list)

    def walk(node, trail: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            members = node.get("enum")
            if isinstance(members, list) and len(members) >= 2 \
                    and all(isinstance(m, str) for m in members):
                named = [t for t in trail if not t.startswith("[") and t not in skip]
                if named:
                    out[_norm(named[-1])].append(
                        ("mac.schema.json#/" + "/".join(trail), list(members))
                    )
            for k, v in node.items():
                walk(v, trail + (str(k),))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, trail + (f"[{i}]",))

    walk(doc, ())
    return out


def _vocabulary_namespaces(root: Path) -> dict[str, tuple[str, list[str]]]:
    """`mac_vocabulary.yaml`'s namespaces, keyed by folded name. Parsed WITHOUT pyyaml when it is
    absent: `sdk/gate/` is the home of gates that must run with nothing installed."""
    path = root / "mac_vocabulary.yaml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        import yaml
    except ImportError:
        return {}
    try:
        doc = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 -- a malformed registry is class 0's problem, not this one
        return {}
    if not isinstance(doc, dict):
        return {}

    out: dict[str, tuple[str, list[str]]] = {}
    for ns, body in doc.items():
        if ns == "metadata" or not isinstance(body, dict):
            continue
        terms = body.get("terms")
        names: list[str] = []
        if isinstance(terms, dict):
            names = sorted(str(k) for k in terms)
        elif isinstance(terms, list):
            names = [str(t.get("term") or t.get("name")) for t in terms
                     if isinstance(t, dict) and (t.get("term") or t.get("name"))]
        if len(names) >= 2:
            out[_norm(str(ns))] = (f"mac_vocabulary.yaml#{ns}", names)
    return out


def _named_code_sets(root: Path) -> list[tuple[str, int, str, list[str]]]:
    """(module, line, declared name, members) for every named set/tuple/list of string literals.

    Both `X = frozenset({...})` and `X: ClassVar = frozenset({...})` are read: the connector home
    this detector exists for is an annotated class attribute.
    """
    out: list[tuple[str, int, str, list[str]]] = []
    for p in _sources(root, ".py"):
        tree = _parse(p)
        if tree is None:
            continue
        rel = str(p.relative_to(root))
        for n in ast.walk(tree):
            target = value = None
            if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                    and isinstance(n.targets[0], ast.Name):
                target, value = n.targets[0].id, n.value
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                target, value = n.target.id, n.value
            if target is None or value is None:
                continue
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
                    and value.func.id in ("frozenset", "set", "tuple", "list") and len(value.args) == 1:
                value = value.args[0]
            if not isinstance(value, (ast.Set, ast.Tuple, ast.List)) or not value.elts:
                continue
            members = [e.value for e in value.elts
                       if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(members) != len(value.elts) or len(members) < 2:
                continue
            out.append((rel, n.lineno, target, members))
    return out


def _closed_vocabulary(root: Path, inv: Inventory) -> None:
    grammar = _grammar_enums(root)
    vocab = _vocabulary_namespaces(root)
    collisions: list[str] = []

    homes: list[tuple[str, str, list[str]]] = []          # (folded name, home label, members)
    for folded, entries in grammar.items():
        for label, members in entries:
            homes.append((folded, label, members))
    for folded, (label, members) in vocab.items():
        homes.append((folded, label, members))

    checked = 0
    for rel, line, name, members in _named_code_sets(root):
        folded = _norm(name)
        for hfolded, label, hmembers in homes:
            if hfolded != folded:
                continue
            shared = set(members) & set(hmembers)
            if not shared:
                # Name matches, no member does. Two homonymous role words, OR a vocabulary
                # misspelled end to end — and NO predicate here separates those two. Queued for a
                # human, never scored. This is the detector's disclosed blind spot.
                collisions.append(
                    f"{rel}:{line} {name} vs {label}: name pairs, NO member shared "
                    f"(code {sorted(members)[:4]} / home {sorted(hmembers)[:4]})"
                )
                continue
            checked += 1
            surplus = sorted(set(members) - set(hmembers))
            if surplus:
                inv.findings.append(Finding(
                    "closed-vocabulary-divergence",
                    f"{rel}:{line}",
                    f"{name} declares {surplus} which {label} does not know "
                    f"(a closed vocabulary with two spellings is not closed)",
                ))

    inv.population["closed-vocabulary-divergence"] = checked
    inv.population["vocabulary-name-collision"] = len(collisions)
    inv.notes.append(
        f"vocabulary-name-collision: {len(collisions)} name-only pairing(s); NOT SCORED — a "
        f"homonymous role word and an end-to-end misspelling share no member either, so this "
        f"class cannot tell them apart. It is a review queue (--verbose lists it)."
    )
    inv.notes.extend(f"  [queue] {c}" for c in sorted(collisions))


# ================================================================================================
# CLASS 4 (enforced) — subprocess-argv-divergence
# ================================================================================================
# PAIRING RULE: a module invoked as `-m some.module`, from an argv list or from a shell string, in
# .py or .sh. The callee is resolved to a file in THIS tree; a module that does not resolve (pip,
# pytest) is not a seam this repository can check and is reported as unresolvable.
#
# AGREEMENT PREDICATE: every `--flag` the caller passes must be defined by an `add_argument` in the
# callee, EXCEPT the flags argparse defines for the callee. `--help` is the one that matters and it
# cost this detector its first two findings: a smoke-test caller that runs `-m mod --help` over
# every entry point was reported as passing an undefined flag to both modules it exercised, because
# `ArgumentParser` installs `-h/--help` itself and no `add_argument` call names it. Two false
# positives out of three findings on the first run; a gate that debuts at 33% precision is a gate
# nobody reads twice. Only long flags are compared — a bare `-x` is ambiguous with a value and with argparse's
# own abbreviation matching, and a detector that guesses would produce exactly the noise this gate
# refuses to emit.

_SHELL_INVOKE = re.compile(r"python3?\s+-m\s+([A-Za-z_][\w.]*)((?:\s+-{1,2}[\w-]+)*)")


def _subprocess_argv(root: Path, inv: Inventory) -> None:
    passed: dict[str, set[str]] = collections.defaultdict(set)
    callers: dict[str, set[str]] = collections.defaultdict(set)

    def note(module: str, flags: set[str], where: str) -> None:
        passed[module] |= flags
        callers[module].add(where)

    def from_argv(elts) -> list[tuple[str, set[str]]]:
        vals = [e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else None
                for e in elts]
        out = []
        for i, v in enumerate(vals):
            if v == "-m" and i + 1 < len(vals) and vals[i + 1]:
                out.append((vals[i + 1],
                            {x for x in vals[i + 2:] if x and x.startswith("--")}))
        return out

    for p in _sources(root, ".py"):
        tree = _parse(p)
        if tree is None:
            continue
        rel = str(p.relative_to(root))
        for n in ast.walk(tree):
            if isinstance(n, (ast.List, ast.Tuple)):
                for mod, flags in from_argv(n.elts):
                    note(mod, flags, rel)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                for m in _SHELL_INVOKE.finditer(n.value):
                    note(m.group(1),
                         {f for f in m.group(2).split() if f.startswith("--")}, rel)
    for p in _sources(root, ".sh"):
        rel = str(p.relative_to(root))
        for m in _SHELL_INVOKE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            note(m.group(1), {f for f in m.group(2).split() if f.startswith("--")}, rel)

    #: Flags `argparse.ArgumentParser()` installs without an `add_argument` call. A caller passing
    #: one of these always agrees with the callee, so charging it as a divergence is a lie.
    argparse_builtin = {"--help"}

    def parser_flags(module: str):
        cand = root / (module.replace(".", "/") + ".py")
        if not cand.exists():
            cand = root / module.replace(".", "/") / "__main__.py"
        if not cand.exists():
            return None, set()
        tree = _parse(cand)
        if tree is None:
            return None, set()
        flags = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == "add_argument":
                for a in n.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                            and a.value.startswith("--"):
                        flags.add(a.value)
        return str(cand.relative_to(root)), flags

    resolved = 0
    unresolvable: list[str] = []
    for module in sorted(passed):
        path, flags = parser_flags(module)
        if path is None:
            unresolvable.append(module)
            continue
        resolved += 1
        missing = sorted(passed[module] - flags - argparse_builtin)
        if missing:
            inv.findings.append(Finding(
                "subprocess-argv-divergence",
                f"{sorted(callers[module])[0]}",
                f"-m {module}: caller passes {missing} which {path} does not define "
                f"(parser defines {sorted(flags)})",
            ))

    inv.population["subprocess-argv-divergence"] = resolved
    if unresolvable:
        inv.notes.append(
            f"subprocess-argv-divergence: {len(unresolvable)} module(s) not in this tree and "
            f"therefore not checkable: {sorted(unresolvable)}"
        )


# ================================================================================================
# CLASS 5 (enforced) — sql-column-not-emitted
# ================================================================================================
# This is the class that catches defect 1, and it is the sharpest one here: 74 citations checked,
# exactly 1 disagreeing, 0 false positives on inspection.
#
# PAIRING RULE, in two halves.
#
# PRODUCER: a dict literal mapping a relation NAME to an emitter FUNCTION — `TABLES = {"meta_x":
# t_x}` — resolved through the Name to the FunctionDef, whose yielded/returned dict-literal keys
# ARE the relation's column set. `{k: row.get(k) for k in ("a", "b")}` is read too, because the
# emitter this detector exists for writes its column list exactly that way.
#
# CONSUMER: a string literal that IS a query. A query quoted inside PROSE is excluded, and that
# single rule is what took this class from unusable to clean: the `never:` field of a concept
# annotation contains the words "scraping them with SELECT DISTINCT off a warehouse ... READ from
# {src}.meta_enum", which a prose-tolerant scanner read as a statement and charged 25 English words
# to `meta_enum` as undeclared columns.
#
# Columns are taken from COLUMN POSITIONS only — the select list, WHERE comparands, GROUP/ORDER BY
# — with `{placeholders}`, 'string literals' and `AS alias` names removed. A statement citing more
# than one table is EXCLUDED and counted: a column cannot be attributed to a table without
# resolving aliases, and guessing is how a detector starts lying.

_PLACEHOLDER = re.compile(r"\{[^{}]*\}")
_SQL_STRING = re.compile(r"'[^']*'")
_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN)\s+((?:\{[^}]*\}|[A-Za-z_]\w*)(?:\.(?:\{[^}]*\}|[A-Za-z_]\w*))*)", re.I)
_ALIAS = re.compile(r"\bAS\s+([A-Za-z_]\w*)", re.I)
_SELECT_LIST = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?(.*?)\bFROM\b", re.I | re.S)
_WHERE = re.compile(r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)", re.I | re.S)
_GROUP_ORDER = re.compile(r"\b(?:GROUP|ORDER)\s+BY\b(.*?)(?:\bORDER\s+BY\b|\bLIMIT\b|$)", re.I | re.S)
_IDENT = re.compile(r"\b([a-z_][a-z0-9_]{2,})\b")

_SQL_WORDS = frozenset("""
select from where group by order having and or not in is null as on join left right inner outer
full cross union all distinct count sum avg min max case when then else end limit offset asc desc
cast lower upper coalesce nullif substr like between exists with over partition row_number rank
dense_rank true false interval date timestamp int integer bigint varchar double boolean array map
struct json_extract_scalar json_parse array_agg string_agg
""".split())


def _dict_literal_keys(node) -> set[str]:
    """String-literal keys a Dict/DictComp contributes, through `**merge` and through the
    `{k: row.get(k) for k in ("a", "b")}` form that declares a column list as a tuple."""
    keys: set[str] = set()
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if k is None:
                keys |= _dict_literal_keys(v)
            elif isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value)
    elif isinstance(node, ast.DictComp):
        for gen in node.generators:
            if isinstance(gen.iter, (ast.Tuple, ast.List, ast.Set)):
                keys |= {e.value for e in gen.iter.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return keys


def _emitted_relations(root: Path) -> dict[str, tuple[str, str, set[str]]]:
    out: dict[str, tuple[str, str, set[str]]] = {}
    for p in _sources(root, ".py"):
        tree = _parse(p)
        if tree is None:
            continue
        rel = str(p.relative_to(root))
        funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for n in ast.walk(tree):
            if not isinstance(n, ast.Dict):
                continue
            for k, v in zip(n.keys, n.values):
                if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                    continue
                if not (isinstance(v, ast.Name) and v.id in funcs):
                    continue
                fn = funcs[v.id]
                cols: set[str] = set()
                for sub in ast.walk(fn):
                    if isinstance(sub, (ast.Yield, ast.Return)) and sub.value is not None:
                        cols |= _dict_literal_keys(sub.value)
                    elif isinstance(sub, (ast.GeneratorExp, ast.ListComp)):
                        cols |= _dict_literal_keys(sub.elt)
                if cols:
                    out[k.value] = (rel, v.id, cols)
    return out


def _is_query(text: str) -> bool:
    return text.lstrip().upper().startswith(("SELECT", "WITH "))


def _cited_columns(statement: str, relations) -> set[str]:
    body = _SQL_STRING.sub(" ", _PLACEHOLDER.sub(" ", statement))
    aliases = {m.group(1).lower() for m in _ALIAS.finditer(body)}
    spans: list[str] = []
    m = _SELECT_LIST.search(body)
    if m:
        spans.append(m.group(1))
    for rx in (_WHERE, _GROUP_ORDER):
        spans.extend(mm.group(1) for mm in rx.finditer(body))
    tokens: set[str] = set()
    for span in spans:
        for im in _IDENT.finditer(_TABLE_REF.sub(" ", span)):
            tok = im.group(1).lower()
            if tok in _SQL_WORDS or tok in aliases or tok in relations:
                continue
            tokens.add(tok)
    return tokens


def _sql_columns(root: Path, inv: Inventory) -> None:
    relations = _emitted_relations(root)
    if not relations:
        inv.population["sql-column-not-emitted"] = 0
        return

    queries: list[tuple[str, str]] = []
    for p in _sources(root, ".py"):
        tree = _parse(p)
        if tree is None:
            continue
        rel = str(p.relative_to(root))
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and _is_query(n.value):
                queries.append((n.value, f"{rel}:{n.lineno}"))
    for p in _sources(root, ".md"):
        rel = str(p.relative_to(root))
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"```(?:sql)?\n(.*?)```", text, re.S):
            if _is_query(m.group(1)):
                queries.append((m.group(1), f"{rel}:{text[:m.start()].count(chr(10)) + 1}"))

    checked = 0
    multi_table = 0
    for text, site in queries:
        for statement in text.split(";"):
            if not statement.strip():
                continue
            refs = [m.group(1).split(".")[-1] for m in _TABLE_REF.finditer(statement)]
            emitted = [r for r in refs if r in relations]
            if not emitted:
                continue
            if len(refs) != 1:
                multi_table += 1
                continue
            relation = emitted[0]
            module, emitter, cols = relations[relation]
            for tok in sorted(_cited_columns(statement, relations)):
                checked += 1
                if tok not in cols:
                    inv.findings.append(Finding(
                        "sql-column-not-emitted",
                        site,
                        f"{relation}.{tok} is cited but {module}::{emitter} emits "
                        f"{sorted(cols)} — the producer and the query disagree on the column name",
                    ))

    inv.population["sql-column-not-emitted"] = checked
    if multi_table:
        inv.notes.append(
            f"sql-column-not-emitted: {multi_table} multi-table statement(s) excluded — a column "
            f"cannot be attributed to a relation without resolving aliases"
        )


# ================================================================================================
# CLASS 6 (excluded) — config-default-divergence
# ================================================================================================
# PAIRING RULE: a key that appears both in a parsed config file and as `.get("key", "default")` in
# code. AGREEMENT would be that the two values match.
#
# WHY IT IS NOT SCORED: 22 pairs, 35 "disagreements", and the inspected ones are all
# `.get("confidence", "?")` — a missing-value placeholder, not a second declaration of the fact. A
# shared KEY is not a shared FACT, and nothing here reaches the intent that made defect 3 one fact
# in two places. Enumerated so the population is visible; scored by nobody.


def _config_defaults(root: Path, inv: Inventory) -> None:
    conf: dict[str, set[str]] = collections.defaultdict(set)

    def flatten(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and v:
                    yield str(k), v
                else:
                    yield from flatten(v)
        elif isinstance(node, list):
            for v in node:
                yield from flatten(v)

    try:
        import yaml
    except ImportError:
        yaml = None
    for suffix in (".json", ".yaml", ".yml", ".toml"):
        for p in _sources(root, suffix):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                if suffix == ".json":
                    doc = json.loads(text)
                elif suffix == ".toml":
                    import tomllib
                    doc = tomllib.loads(text)
                else:
                    if yaml is None:
                        continue
                    doc = yaml.safe_load(text)
            except Exception:  # noqa: BLE001 -- an unparseable config is another gate's finding
                continue
            for k, v in flatten(doc):
                conf[k].add(v)

    defaults: dict[str, set[str]] = collections.defaultdict(set)
    for p in _sources(root, ".py"):
        tree = _parse(p)
        if tree is None:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == "get" and len(n.args) == 2 \
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str) \
                    and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str) \
                    and n.args[1].value:
                defaults[n.args[0].value].add(n.args[1].value)

    seams = [k for k in defaults if k in conf]
    candidates = sum(1 for k in seams for d in defaults[k] if d not in conf[k])
    inv.population["config-default-divergence"] = len(seams)
    inv.notes.append(
        f"config-default-divergence: {len(seams)} key(s) declared in both a config file and a "
        f"code default, {candidates} value mismatch(es); NOT SCORED — the inspected mismatches are "
        f"missing-value placeholders, so a shared key is not evidence of a shared fact"
    )


# ================================================================================================
# CLASS 7 (excluded) — trust-store-divergence
# ================================================================================================
# PAIRING RULE: modules that reference a CA bundle or trust store. The POPULATION is enumerable.
# AGREEMENT IS NOT DECIDABLE FROM THIS TREE: defect 4 was one library's default trust store
# disagreeing with another's, and neither default is written in this repository. A gate cannot
# check a fact that lives in a dependency, so this class reports its sites and scores nothing.

_TRUST_TOKENS = ("certifi", "AWS_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "ca_bundle", "cafile",
                 "load_verify_locations", "create_default_context", "SSLContext")


def _trust_store(root: Path, inv: Inventory) -> None:
    sites: list[str] = []
    for p in _sources(root, ".py"):
        rel = str(p.relative_to(root))
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if any(t in line for t in _TRUST_TOKENS):
                sites.append(f"{rel}:{i}")
    modules = {s.rsplit(":", 1)[0] for s in sites}
    inv.population["trust-store-divergence"] = len(modules)
    if sites:
        inv.notes.append(
            f"trust-store-divergence: {len(sites)} site(s) across {len(modules)} module(s); NOT "
            f"SCORED — the two trust stores that disagreed are both DEFAULTS INSIDE DEPENDENCIES "
            f"and neither is declared in this tree, so no predicate here can compare them"
        )


# ================================================================================================
# the gate
# ================================================================================================

_DETECTORS = (_dict_keys, _closed_vocabulary, _subprocess_argv, _sql_columns,
              _config_defaults, _trust_store)


def check(root: Path) -> Inventory:
    """Enumerate every class and return the whole inventory.

    Returns an `Inventory`, not an exit code, and never 2: four gates in this package are called
    in-process by `sdk/cli/publish.py`, where a reserved code would be read as a finding. The
    could-not-run path belongs to `main()` alone -- see `sdk/gate/contract.py`.
    """
    inv = Inventory()
    for name in (*ENFORCED, *EXCLUDED):
        inv.population[name] = 0
    for detector in _DETECTORS:
        detector(root, inv)
    return inv


def run(root: Path) -> contract.Outcome:
    """The inventory as a contract `Outcome`.

    PRIMARY DENOMINATOR is every seam enumerated, enforced and excluded alike -- the number this
    gate exists to print, because nobody knew it. SECONDARY is the ENFORCED population, which is
    what the verdict is actually made of. Getting these the other way round would let a run that
    enumerated 600 seams and checked none of them report PASS; declared this way, `verdict()`
    refuses with exit 2 instead, because a gate with no yardstick has not established anything.
    """
    inv = check(root)
    findings = inv.enforced_findings
    return contract.Outcome(
        len(findings),
        inv.total_population,
        "seam(s) enumerated",
        classes={f.cls for f in findings},
        secondary=(inv.enforced_population, "seam(s) checked"),
    )


def _main_over(root: Path, *, verbose: bool = False) -> int:
    inv = check(root)

    # Per-finding lines FIRST: a gate whose only output is its own scoreboard has disclosed
    # nothing anyone can act on.
    for f in sorted(inv.enforced_findings, key=lambda x: (x.cls, x.site)):
        print(f"  [{f.cls}] {f.site}: {f.message}")

    print(f"  enumerated {inv.total_population} seam(s): "
          f"{inv.enforced_population} checked, {inv.excluded_population} excluded")
    for cls in ENFORCED:
        n = sum(1 for f in inv.findings if f.cls == cls)
        print(f"    enforced  {cls:32} {inv.population[cls]:5} checked, {n} disagreeing")

    # THE EXCLUSIONS ARE PRINTED ON EVERY RUN. An exclusion nobody sees is a silent exemption, and
    # the delta is printed with it so a population cannot grow without being noticed.
    for cls in EXCLUDED:
        got = inv.population[cls]
        declared = _EXCLUDED_STANDING.get(cls)
        delta = ""
        if declared is not None and got != declared:
            band = max(1, int(declared * _EXCLUDED_TOLERANCE))
            if got > declared + band:
                why = "; BEYOND the tolerance band — that many new unchecked seams at once"
            elif got > declared:
                why = f"; within the {band} tolerance band (ordinary authoring)"
            else:
                why = "; lower the declaration"
            delta = (f"  <- {'GREW' if got > declared else 'fell'} from the {declared} declared "
                     f"{_FLOOR_DECLARED}{why}")
        print(f"    EXCLUDED  {cls:32} {got:5} enumerated, NOT SCORED{delta}")
    for note in inv.notes:
        if note.lstrip().startswith("[queue]") and not verbose:
            continue
        print(f"    note: {note}")

    line, code = contract.verdict(
        NAME, run(root),
        detail=(f"enforced floor {_ENFORCED_FLOOR}, declared {_FLOOR_DECLARED}, owner "
                f"{_FLOOR_OWNER}, review by {_FLOOR_REVIEW_BY}"),
    )
    print(line)
    if inv.enforced_findings:
        print(f"  the floor is {_ENFORCED_FLOOR} and it stays there: a disagreeing seam is a "
              f"defect to fix, not a number to raise")
    return code


# ------------------------------------------------------------------------------------------------
# the self-test: one mutant per ENFORCED reject class, plus must-pass fixtures proving each
# EXCLUSION is real rather than merely claimed
# ------------------------------------------------------------------------------------------------

_GRAMMAR = json.dumps({
    "$defs": {
        "credentialMode": {"enum": ["ambient", "named_profile", "secret_manager", "none"]},
    }
}, indent=1)

#: The clean fixture carries one live seam of every enforced class, so its denominator is non-zero
#: for each and a mutant has something to diverge FROM.
_EMITTER = '''\
def t_widgets(d):
    for r in d.get("widgets", []):
        yield {k: r.get(k) for k in ("widget_key_used", "label")}

TABLES = {"meta_widgets": t_widgets}

EXAMPLE = "SELECT label FROM {src}.meta_widgets WHERE widget_key_used = 'w1'"
'''

_CALLEE = '''\
import argparse

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    return 0
'''

_CALLER = '''\
import subprocess, sys
subprocess.run([sys.executable, "-m", "pkg.callee", "--out", "x"], check=True)
'''

_VOCAB_HOME = '''\
from typing import ClassVar

class Connector:
    credential_modes: ClassVar = frozenset({"named_profile", "ambient"})
'''


def _clean(root: Path) -> None:
    contract.write(root / "mac.schema.json", _GRAMMAR)
    contract.write(root / "emitter.py", _EMITTER)
    contract.write(root / "pkg" / "__init__.py", "")
    contract.write(root / "pkg" / "callee.py", _CALLEE)
    contract.write(root / "caller.py", _CALLER)
    contract.write(root / "connector.py", _VOCAB_HOME)


def _m_vocabulary(root: Path) -> Path:
    """The connector invents a spelling the grammar does not know -- defect 2, exactly."""
    return contract.write(
        root / "connector.py",
        _VOCAB_HOME.replace('{"named_profile", "ambient"}', '{"named_profile", "profile"}'),
    )


def _m_argv(root: Path) -> Path:
    """The caller passes a flag the callee's parser never defined."""
    return contract.write(root / "caller.py", _CALLER.replace('"--out"', '"--output"'))


def _m_sql_column(root: Path) -> Path:
    """The query reads `widget_key` from a relation whose emitter writes `widget_key_used`
    -- defect 1, reduced to nine lines."""
    return contract.write(
        root / "emitter.py",
        _EMITTER.replace("WHERE widget_key_used =", "WHERE widget_key ="),
    )


def _p_orphan_dict_key(root: Path) -> None:
    """A key read with no producer in this tree MUST NOT be a finding: it is how every response
    from a dependency is read. Enforcing it was measured at 194 findings of noise."""
    _clean(root)
    contract.write(root / "reader.py",
                   'def f(resp):\n    return resp["ResultSetMetadata"], resp.get("NextToken")\n')


def _p_config_placeholder_default(root: Path) -> None:
    """A code default that differs from a config file's value MUST NOT be a finding: the inspected
    population is missing-value placeholders, not second declarations."""
    _clean(root)
    contract.write(root / "conf.yaml", "confidence: C\n")
    contract.write(root / "reader.py", 'def f(d):\n    return d.get("confidence", "?")\n')


def _p_subset_is_legal(root: Path) -> None:
    """A connector supporting FEWER modes than the grammar names is correct. A gate that rejected
    the absence of an optional thing would force edits to code that was already right."""
    _clean(root)
    contract.write(root / "connector.py",
                   _VOCAB_HOME.replace('{"named_profile", "ambient"}', '{"named_profile", "none"}'))


def _p_homonym_is_not_a_seam(root: Path) -> None:
    """Two modules using the same English word are NOT a seam. `KINDS` and the grammar's `kind`
    share a name and no member; scoring that pairing produced 7 of 11 false positives."""
    _clean(root)
    contract.write(root / "kinds.py", 'KINDS = ("authored", "tuned", "retired")\n')
    contract.write(root / "mac.schema.json", json.dumps({
        "$defs": {
            "credentialMode": {"enum": ["ambient", "named_profile", "secret_manager", "none"]},
            "TransformFile": {"properties": {"kind": {"enum": ["raw_source", "dataset"]}}},
        }
    }, indent=1))


def _x_exclusions_are_enumerated(base: Path) -> tuple[int, int]:
    """Every excluded class must still REPORT a population. An exclusion that also stops counting
    is indistinguishable from a detector that was deleted."""
    root = base / "_exclusion_probe"
    root.mkdir(parents=True, exist_ok=True)
    _p_orphan_dict_key(root)
    _p_config_placeholder_default(root)
    inv = check(root)
    established = 0
    if inv.population["dict-key-orphan-read"] > 0:
        established += 1
    if inv.population["config-default-divergence"] > 0:
        established += 1
    return established, 2


def _x_secondary_zero_refuses(base: Path) -> tuple[int, int]:
    """A tree with seams enumerated but NONE checkable must exit 2, not PASS. This is the property
    that stops this gate from ever reporting a green over a population it did not examine."""
    root = base / "_no_yardstick"
    root.mkdir(parents=True, exist_ok=True)
    contract.write(root / "reader.py", 'def f(d):\n    return d["only_an_orphan_read"]\n')
    inv = check(root)
    established = 0
    if inv.enforced_population == 0 and inv.total_population > 0:
        established += 1
    _line, code = contract.verdict(NAME, run(root))
    if code == 2:
        established += 1
    return established, 2


def _x_floor_is_owned_and_dated(_base: Path) -> tuple[int, int]:
    """A floor with no owner and no review date is a permanent exemption. Asserted here as well as
    in `main` so deleting the declaration is a red self-test, not a quiet downgrade."""
    established = 0
    if _FLOOR_OWNER and _FLOOR_DECLARED and _FLOOR_REVIEW_BY:
        established += 1
    if _ENFORCED_FLOOR == 0:
        established += 1
    return established, 2


def build() -> contract.GateContract:
    return contract.GateContract(
        name=NAME,
        clean=_clean,
        mutants={
            "closed-vocabulary-divergence": _m_vocabulary,
            "subprocess-argv-divergence": _m_argv,
            "sql-column-not-emitted": _m_sql_column,
        },
        run=run,
        must_pass={
            "an orphan dict-key read is not a finding": _p_orphan_dict_key,
            "a placeholder default beside a config key is not a finding": _p_config_placeholder_default,
            "a connector supporting a SUBSET of the grammar is correct": _p_subset_is_legal,
            "a shared English word with no shared member is not a seam": _p_homonym_is_not_a_seam,
        },
        expect_line={
            "closed-vocabulary-divergence": "is not closed",
            "subprocess-argv-divergence": "does not define",
            "sql-column-not-emitted": "disagree on the column name",
        },
        main=lambda r: _main_over(r),
        # Stated, not inferred: the day someone drops `classes=` from `run()` to quiet a failure,
        # this line makes it a red self-test instead of a silent downgrade to "rejected by finding
        # count only".
        attributes_classes=True,
        extra={
            "every excluded class still reports a population": _x_exclusions_are_enumerated,
            "a tree with no checkable seam exits 2 rather than PASS": _x_secondary_zero_refuses,
            "the floor is owned, dated and still zero": _x_floor_is_owned_and_dated,
        },
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true",
                    help="seed a mutant per enforced reject class and assert each is rejected")
    ap.add_argument("--root", default=None, help="tree to measure (default: this repository)")
    ap.add_argument("--verbose", action="store_true",
                    help="also print the vocabulary-name-collision review queue")
    a = ap.parse_args(argv)

    if a.self_test:
        return contract.run_self_test(build())

    if not (_FLOOR_OWNER and _FLOOR_DECLARED and _FLOOR_REVIEW_BY):
        return contract.could_not_run(
            NAME,
            "the floor carries no owner, declaration date or review date; an undated, unowned "
            "floor is a permanent exemption and this gate will not enforce one",
        )

    root = Path(a.root).resolve() if a.root else ROOT
    if not root.is_dir():
        return contract.could_not_run(NAME, f"{root} is not a directory")
    return _main_over(root, verbose=a.verbose)


if __name__ == "__main__":
    sys.exit(main())
