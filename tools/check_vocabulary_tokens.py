#!/usr/bin/env python3
"""check_vocabulary_tokens.py — EVERY `mac.*` TOKEN RESOLVES IN THE VOCABULARY THAT DECLARES IT.

THE DEFECT THIS REPAIRS, and it is a standing law being ignored rather than a missing one.
`mac_vocabulary.yaml` declares 19 vocabularies and says of each whether it is CLOSED. `measure_type`
says `closed: true` with five terms. NOTHING READ THAT. `mac.schema.json` types the slot as a bare
string, so on 2026-09-27 I authored `mac.MeasureType.Level` into contoso4's Store concept — a member
that has never existed in any version of the vocabulary — and validate_schema reported 80 of 80 files
clean. The estate's own rule covers this exactly: check for an unread declaration before proposing a
new one. The declaration was there; the reader was not.

WHY NOT AN ENUM IN THE SCHEMA. Because that is the same defect one level over: the vocabulary would
then be declared in mac_vocabulary.yaml AND in mac.schema.json, two homes that drift. The vocabulary
is the one home and this gate is its one reader.

IT ENFORCES THREE THINGS, all of them already true of 18 of the 19 vocabularies:
  1. A NAMESPACE MUST EXIST.        `mac.nosuch.thing` fails.
  2. A CLOSED VOCABULARY IS CLOSED. `mac.concept.column.measure_type.level` fails; `mac.canon.*` (closed: false)
                                    admits anything, because the vocabulary says it may.
  3. A NAMESPACE IS snake_case.     Measured 2026-09-27: `MeasureType` was the ONLY CamelCase name of
                                    twenty, and the only one using `members:` where 18 said `terms:`.
                                    The inconsistency had already cost a bug — gen_column_bench.py
                                    read `MeasureType.terms`, a key that did not exist, and silently
                                    got nothing. Both are standardised now, and this rule is what
                                    stops the next one arriving.

It reads YAML only. A token in a `.md` is prose about a token, and prose is not a declaration.
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import re
import sys

#: The one home. Nothing here carries a copy of any vocabulary's members.
VOCAB_REL = "mac_vocabulary.yaml"

#: A complete token: `mac.` then a DOTTED PATH. The term must be non-empty — `mac.concept.rule.` appears in
#: prose mid-sentence and is a reference to the vocabulary, not a use of a term.
#:
#: THE NAMESPACE MAY ITSELF CONTAIN DOTS, which is new. Operator ruling 2026-09-27: the column-scoped
#: vocabularies were renamed into a hierarchy — `mac.concept.column.role`, `mac.concept.column.identity`,
#: `mac.concept.column.measure_type`, `mac.concept.column.ruling` — "so that i know (not only you know) where is
#: something belonging". Before that every one of 124 token uses in the estate was exactly three
#: segments, so a fixed `mac.<ns>.<term>` pattern was enough; now the split between namespace and term
#: cannot be found by counting dots and is resolved against the DECLARED namespaces instead. That is
#: the right way round anyway: the vocabulary says where the boundary is, not the punctuation.
TOKEN = re.compile(r"\bmac\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")


def split(path: str, vocab: dict) -> tuple:
    """(namespace, term) — the LONGEST declared namespace that prefixes `path`, and the rest.

    Longest-first, so `mac.concept.column.measure_type.flow` resolves to the namespace `column.measure_type`
    even if a `column` namespace also existed. With nothing declared matching, the first segment is
    reported as the namespace so an unknown one is still NAMED rather than swallowed."""
    for ns in sorted(vocab, key=len, reverse=True):
        if path == ns:
            return ns, ""
        if path.startswith(ns + "."):
            return ns, path[len(ns) + 1:]
    head, _, rest = path.partition(".")
    return head, rest

#: Namespaces the vocabulary does not declare AT ALL and that are not value domains — a token under
#: them is an identifier the bundle coins, not a term the framework closes. `sample` names a concept,
#: `project`/`schema` name a contract version.
#:
#: `field_role` IS DELIBERATELY NOT HERE, and that is the point of the list being short. The projection
#: writes `mac.field_role.<role>` and NO vocabulary declares that namespace — which is exactly why 141
#: `CONTOSO4.field_role.*` tokens sat inert through every gate. Leaving it out means this gate REPORTS
#: it, which is the finding rather than the noise.
UNDECLARED_IDENTIFIER_NAMESPACES = frozenset({"sample", "project", "schema"})

ACCEPTED_SHAPE = """\
ACCEPTED SHAPE — a bundle root holding ontology/ and/or data/ with YAML in it, beside a framework
checkout carrying mac_vocabulary.yaml.
usage: check_vocabulary_tokens.py [bundle]
"""


def vocabularies(root: pathlib.Path, yaml) -> dict:
    """`{namespace: (closed, frozenset(terms))}` from the vocabulary's own declarations.

    It accepts `terms:` and `members:` both, and that is not a concession — it is how this gate stays
    usable against a framework checkout from before the two were unified, so an older tree reports the
    same findings instead of refusing.
    """
    d = yaml.safe_load((root / VOCAB_REL).read_text(encoding="utf-8")) or {}
    out = {}
    for name, body in d.items():
        if not isinstance(body, dict) or "kind" not in body:
            continue
        block = body.get("terms")
        if block is None:
            block = body.get("members")
        if block is None:
            # A BLOCK WITH NO TERMS IS A REGISTERED NAMESPACE, not a missing one — `kind: registry`,
            # which `connector` is, deliberately: its own note says "This block registers the
            # NAMESPACE ONLY ... which first-party connectors exist is a fact about the MAC
            # DISTRIBUTION, not about meaning", and ends "This paragraph exists so nobody later
            # 'fixes' the omission." So it is read as OPEN rather than hardcoded into an exemption
            # list — the declaration says what it is, and this gate believes it.
            out[name] = (False, frozenset())
            continue
        names = set(block) if isinstance(block, dict) else {
            (x.get("term") if isinstance(x, dict) else x) for x in (block or [])}
        out[name] = (bool(body.get("closed")), frozenset(str(n) for n in names if n))
    return out


def scan(bundle: pathlib.Path) -> list:
    """Every (token, namespace, term, file) in the bundle's authored YAML, in a stable order."""
    hits = []
    for pat in ("ontology/**/*.yaml", "ontology/**/*.yml", "data/**/*.yaml", "data/**/*.yml",
                "*.yaml", "*.mac"):
        for f in sorted(glob.glob(str(bundle / pat), recursive=True)):
            p = pathlib.Path(f)
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = str(p.relative_to(bundle))
            for path in TOKEN.findall(text):
                hits.append((f"mac.{path}", path, rel))
    return hits


def verdicts(hits: list, vocab: dict) -> list:
    """One item per DISTINCT token: (token, state, detail, files). States: ok | unknown_namespace |
    not_a_term | not_snake_case | registry.

    DISTINCT, not per occurrence, because the finding is about the TOKEN — reporting one defect 141
    times is how the 141 inert field-role tokens became unreadable noise instead of one sentence.
    """
    by_token: dict = {}
    for tok, path, rel in hits:
        by_token.setdefault(tok, (path, set()))[1].add(rel)
    out = []
    for tok in sorted(by_token):
        path, files = by_token[tok]
        ns, term = split(path, vocab)
        fs = sorted(files)
        if not term:
            out.append((tok, "ok", f"{ns!r} named as a namespace, with no term used", fs))
            continue
        if ns in UNDECLARED_IDENTIFIER_NAMESPACES:
            out.append((tok, "registry", f"{ns!r} names a registry, not a closed value domain", fs))
        elif ns not in vocab:
            # NORMALISE THE SEPARATOR TOO, or the near-match never fires on the one token that
            # actually shipped: "measure_type".lower() is "measuretype" and never equals
            # "measure_type". A CamelCase name and its snake_case twin differ in case AND underscores.
            flat = lambda v: v.lower().replace("_", "").replace(".", "")
            # WITH A DOTTED NAMESPACE the boundary is unknown when nothing resolves, so assume the
            # LAST segment is the term and flat-compare everything before it. Without this,
            # `mac.Column.MeasureType.flow` reports its namespace as `Column` and the case hint
            # never fires — the very spelling a migration is most likely to produce.
            guess = path.rsplit(".", 1)[0] if "." in path else ns
            # A NAMESPACE THAT MOVED UNDER A PARENT, e.g. `measure_type` -> `column.measure_type`: match
            # on the LAST segment so the migration hint points at where it went rather than at nothing.
            moved = sorted(v for v in vocab if v.rsplit(".", 1)[-1] == ns)
            if moved:
                out.append((tok, "unknown_namespace",
                            f"namespace {ns!r} resolves to nothing — it MOVED to "
                            f"{moved[0]!r}; the token is now mac.{moved[0]}.{term}", fs))
                continue
            near = sorted(v for v in vocab if flat(v) in (flat(ns), flat(guess)))
            hint = (f" — the vocabulary declares {near[0]!r}, which differs only in CASE; namespaces "
                    f"are snake_case" if near else
                    f" — mac_vocabulary.yaml declares no such block (it has {len(vocab)})")
            out.append((tok, "not_snake_case" if near else "unknown_namespace",
                        f"namespace {ns!r} resolves to nothing{hint}", fs))
        elif not ns.islower():
            out.append((tok, "not_snake_case",
                        f"namespace {ns!r} is not snake_case; 18 of 19 vocabularies are", fs))
        else:
            closed, terms = vocab[ns]
            if not closed:
                out.append((tok, "ok", f"{ns!r} is declared OPEN, so any term is admissible", fs))
            elif term in terms:
                out.append((tok, "ok", f"{term!r} is a declared term of {ns!r}", fs))
            else:
                out.append((tok, "not_a_term",
                            f"{ns!r} is declared CLOSED and {term!r} is not one of its "
                            f"{len(terms)} term(s): {', '.join(sorted(terms))}", fs))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}\n\n{ACCEPTED_SHAPE}")
        return 2
    fw = pathlib.Path(__file__).resolve().parent.parent
    if not (fw / VOCAB_REL).is_file():
        print(f"COULD NOT RUN: {VOCAB_REL} is not beside this tool, so no token can be resolved. A "
              f"gate with no vocabulary must refuse, not pass.\n\n{ACCEPTED_SHAPE}")
        return 2
    bundle = pathlib.Path(a.bundle).resolve()
    vocab = vocabularies(fw, yaml)
    hits = scan(bundle)
    items = verdicts(hits, vocab)
    bad = [i for i in items if i[1] not in ("ok", "registry")]
    print(f"  VOCABULARY TOKENS — {bundle.name}\n"
          f"  {len(hits)} token use(s), {len(items)} distinct, against {len(vocab)} declared "
          f"vocabulary(ies) in {VOCAB_REL}\n")
    for tok, state, detail, files in items:
        mark = {"ok": "ok  ", "registry": "--  "}.get(state, "FAIL")
        print(f"  [{mark}] {tok:38} {detail}")
        if state not in ("ok", "registry"):
            print(f"           in: {', '.join(files[:4])}" + (" …" if len(files) > 4 else ""))
    if not items:
        print("  NOTHING TO CHECK — this bundle's YAML carries no mac.* token. That is not a pass: a "
              "concept with no vocabulary reference states no framework fact.")
        print(f"\nPASS: check_vocabulary_tokens — 0 token(s) to resolve")
        return 0
    if bad:
        print(f"\nFAIL: check_vocabulary_tokens — {len(bad)} of {len(items)} distinct token(s) resolve "
              f"to nothing; a token no vocabulary declares places no predicate and no resolver will "
              f"say so")
        return 1
    print(f"\nPASS: check_vocabulary_tokens — {len(items)} of {len(items)} distinct token(s) resolve, "
          f"over {len(hits)} use(s)")
    return 0


def _self_test() -> int:
    """A mutant per reject class (CORE.md §2), the real regression among them."""
    V = {"concept.column.measure_type": (True, frozenset({"flow", "stock", "intensive", "precomputed", "target"})),
         "concept.rule": (True, frozenset({"guarantee", "exclusion"})),
         "canon": (False, frozenset({"refuse"}))}
    def one(tok):
        return verdicts([(tok, tok[len("mac."):], "f.yaml")], V)[0]
    cases = []
    def case(label, cond):
        cases.append((label, bool(cond)))

    case("a declared term of a closed vocabulary passes",
         one("mac.concept.column.measure_type.flow")[1] == "ok")
    # THE REAL REGRESSION: `Level` was never a member, I authored it, and validate_schema said clean.
    case("MUTANT an undeclared term of a CLOSED vocabulary fails",
         one("mac.concept.column.measure_type.level")[1] == "not_a_term")
    case("the failure NAMES the admissible terms",
         "flow" in one("mac.concept.column.measure_type.level")[2] and "stock" in one("mac.concept.column.measure_type.level")[2])
    # THE CASE REGRESSION: the exact token that shipped. It must fail as a CASE error, not as an
    # unknown namespace, or the message sends a reader looking for a vocabulary that does exist.
    case("MUTANT a CamelCase namespace fails, and is diagnosed as a case error",
         one("mac.concept.column.MeasureType.flow")[1] == "not_snake_case"
         and "CASE" in one("mac.concept.column.MeasureType.flow")[2])
    # THE DOTTED NAMESPACE, which is the grammar change itself: the split comes from the DECLARATIONS
    # and not from counting dots, so a 4-segment token resolves where 3 segments used to be the shape.
    case("GRAMMAR a dotted namespace resolves against the declarations",
         one("mac.concept.column.measure_type.flow")[1] == "ok")
    case("GRAMMAR the regex matches a 4-segment token",
         TOKEN.findall("type: mac.concept.column.measure_type.flow,") == ["concept.column.measure_type.flow"])
    case("GRAMMAR the LONGEST declared namespace wins",
         split("concept.column.measure_type.flow", {"column": (True, frozenset()),
                                            "concept.column.measure_type": (True, frozenset())})
         == ("concept.column.measure_type", "flow"))
    r = one("mac.measure_type.flow")
    case("GRAMMAR a namespace that MOVED under a parent says where it went",
         r[1] == "unknown_namespace" and "concept.column.measure_type" in r[2] and "MOVED" in r[2])
    case("MUTANT an unknown namespace fails",
         one("mac.nosuch.thing")[1] == "unknown_namespace")
    case("an OPEN vocabulary admits a term it does not list",
         one("mac.canon.anything_at_all")[1] == "ok")
    case("a registry namespace is neither passed nor failed",
         one("mac.sample.concept")[1] == "registry")
    # DISTINCT, not per occurrence: 141 inert tokens must read as one finding, not 141.
    many = verdicts([("mac.concept.column.measure_type.level", "concept.column.measure_type.level", f"c{i}.yaml")
                     for i in range(9)], V)
    case("one defective token in nine files is ONE finding carrying nine files",
         len(many) == 1 and len(many[0][3]) == 9)
    # A PROSE REFERENCE TO A NAMESPACE, with no term. Before the hierarchy this could not match at all
    # — `mac.rule_kind` was a single segment and the regex needs two — so the old case asserted it was
    # not a token. With a DOTTED namespace it does match, and the right behaviour is not to ignore it
    # but to grade it as what it is: a namespace named, no term used. Neither a pass about a term nor a
    # finding. The case now asserts the behaviour rather than the old accident.
    case("a namespace named in prose with NO term is graded as a mention, not a defect",
         one("mac.concept.rule")[1] == "ok" and "no term" in one("mac.concept.rule")[2])
    case("a real token IS matched next to punctuation",
         TOKEN.findall("type: mac.concept.column.measure_type.flow, unit: x") == ["concept.column.measure_type.flow"])

    bad = [l for l, ok in cases if not ok]
    for l in bad:
        print(f"  FAIL  {l}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_vocabulary_tokens self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_vocabulary_tokens self-test — {n}/{n} case(s): a closed vocabulary rejects an "
          f"undeclared term and names the admissible ones, a CamelCase namespace is diagnosed as a "
          f"CASE error rather than an unknown one, an open vocabulary admits anything, a registry is "
          f"neither passed nor failed, and one bad token across nine files is ONE finding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
