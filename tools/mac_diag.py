#!/usr/bin/env python3
"""mac_diag — the diagnostic contract. One shape for every finding the compiler can make.

WHY THIS EXISTS
---------------
Before this, MAC had eleven separate checkers: eleven invocations, eleven output formats, eleven exit
codes, run one at a time. That is not a compiler. A compiler is ONE invocation, ONE diagnostic list,
ONE verdict — and it tells you the state of the whole program, not the part it happened to look at.

Every finding is a `Diagnostic`. Every diagnostic is ADDRESSABLE (file, and a path/line where the
artifact has one) so a reader goes to the place rather than hunting for it, and every one carries a
CODE from the closed taxonomy below so findings can be counted, suppressed by class, and argued about
as categories rather than as sentences.

THE TAXONOMY answers the question the operator asked five times: what is the state of the ontology —
what is defined, what is defined redundantly, what is not defined, what else can we say.

FANOUT IS COLLAPSED, ALWAYS. A finding with 156 witnesses is ONE diagnostic carrying 156 witnesses,
never 156 diagnostics. A gate that prints one line per file is muted within a week and its root cause
dies with it; that has been observed on this toolchain and it is the reason `witnesses` exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── severity ──────────────────────────────────────────────────────────────────────────────────────
# error   — the bundle does not conform. Nothing may run on it.
# warning — conformant, but carrying a defect that will become an error under a stated condition.
# info    — a fact about the bundle worth reporting. Never blocks.
ERROR, WARNING, INFO = "error", "warning", "info"
ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

# ── the closed diagnostic taxonomy ────────────────────────────────────────────────────────────────
# READ, NOT RESTATED. The taxonomy lives in mac_vocabulary.yaml#diagnostic_code, the one home for
# every closed vocabulary this framework owns. It used to be a dict right here while ALSO being
# tabulated in CONFORMANCE.md — two hand-maintained copies of a set whose own comment called it
# CLOSED, which is exactly what check_vocabulary_drift exists to forbid. The framework was breaking
# its own rule about its own error codes.
#
# The CODE is the contract. Its text may be reworded; its meaning may not change without a version
# bump, because suppressions and counts are keyed on it.

def _load_codes() -> dict:
    """{code: (kind, description)} from the vocabulary. A framework that cannot read its own taxonomy
    must fail LOUDLY here: every diagnostic downstream is keyed on these, and silently degrading to an
    empty map would render every finding as `unknown` while still reporting the bundle."""
    import yaml
    from pathlib import Path as _P
    doc = yaml.safe_load((_P(__file__).resolve().parent.parent / "mac_vocabulary.yaml")
                         .read_text(encoding="utf-8")) or {}
    terms = (doc.get("diagnostic_code") or {}).get("terms") or {}
    if not terms:
        raise RuntimeError("mac_vocabulary.yaml#diagnostic_code is missing or empty — the diagnostic "
                           "taxonomy has no home, so no finding can be classified")
    return {c: (m.get("kind", "unknown"), m.get("description", "")) for c, m in terms.items()}


CODES = _load_codes()
SEVERITY_DEFAULT = None      # filled below; a check may override per finding and says why when it does


def _load_severities() -> dict:
    import yaml
    from pathlib import Path as _P
    doc = yaml.safe_load((_P(__file__).resolve().parent.parent / "mac_vocabulary.yaml")
                         .read_text(encoding="utf-8")) or {}
    return {c: m.get("severity", WARNING)
            for c, m in ((doc.get("diagnostic_code") or {}).get("terms") or {}).items()}


SEVERITY_DEFAULT = _load_severities()


@dataclass(frozen=True)
class Witness:
    """One place a diagnostic is evidenced. Carries enough to navigate to it."""
    file: str
    path: str = ""
    line: int | None = None
    detail: str = ""

    def __str__(self) -> str:
        loc = self.file + (f"#{self.path}" if self.path else "") + (f":{self.line}" if self.line else "")
        return loc + (f"  {self.detail}" if self.detail else "")


@dataclass
class Diagnostic:
    code: str
    severity: str
    summary: str                       # one sentence, the finding itself — never a category label
    witnesses: list = field(default_factory=list)
    note: str = ""                     # what to do about it, when that is not obvious
    source: str = ""                   # which check produced it, for provenance

    @property
    def kind(self) -> str:
        return CODES.get(self.code, ("unknown", ""))[0]

    def location(self) -> str:
        return str(self.witnesses[0]) if self.witnesses else "(bundle)"


def render(diags: list, root: str, *, show: str = WARNING) -> str:
    """Compiler-style output: one line per finding, sorted by severity then code then location,
    witnesses indented beneath. `show` is the least severity printed."""
    cutoff = ORDER.get(show, 1)
    out, shown = [], [d for d in diags if ORDER.get(d.severity, 2) <= cutoff]
    for d in sorted(shown, key=lambda x: (ORDER.get(x.severity, 2), x.code, x.location())):
        out.append(f"{d.location()}: {d.severity}[{d.code} {d.kind}]: {d.summary}")
        for w in d.witnesses[:12]:
            out.append(f"    {w}")
        if len(d.witnesses) > 12:
            out.append(f"    … and {len(d.witnesses) - 12} more")
        if d.note:
            out.append(f"    note: {d.note}")
    return "\n".join(out)


def summarise(diags: list) -> dict:
    by_sev, by_code = {}, {}
    for d in diags:
        by_sev[d.severity] = by_sev.get(d.severity, 0) + 1
        by_code[d.code] = by_code.get(d.code, 0) + 1
    return {"total": len(diags), "by_severity": by_sev, "by_code": by_code,
            "errors": by_sev.get(ERROR, 0), "warnings": by_sev.get(WARNING, 0),
            "witnesses": sum(len(d.witnesses) for d in diags)}
