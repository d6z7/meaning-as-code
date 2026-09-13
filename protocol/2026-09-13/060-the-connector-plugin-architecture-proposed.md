---
when: 2026-09-13T09:51:04
what: proposed the connector plugin architecture, after three measured facts overturned the brief it was written against
topics: [connectors, capabilities, gates, grammar, the-public-boundary]
kind: decision
track: core
repo: meaning-as-code
commits: [6d07081]
---

## WHAT FORCED IT

The operator's picture, and the shape it borrows:

```
<data source of xy type> — <MAC's plug-in connector> — <generic ontology>
```

MAC is the common denominator: standard, SDK, and the connectors it ships. **It holds no credential
and no estate's configuration.** A bundle NAMES a connector; the connector owns how to reach the
source; the ontology stays generic.

## EVIDENCE

`git show -s 6d07081` (meaning-as-code). Eight architects, one dimension each; three adversaries; one
revision. THREE MEASURED FACTS OVERTURNED THE BRIEF:

> * A bundle DOES declare its connection (`mac.project.yaml` `runtime.connection`). The defect is
>   worse than "nobody declares it": `sdk/authoring/connection.py:35` hardcodes the filename and
>   never opens the manifest, and the declared value is byte-identical to the fallback. **A
>   declaration that looks governed and is not.**
> * The flagship bundle is ALREADY failing validation — `spec.validate()` returns `ok=False`,
>   "capability 'answerable' claimed but NOT backed" — and has been served anyway for a month because
>   `open_container(require_trust=None)` downgrades that exact error to a warning.
> * The Athena path in THIS repo is dead. AST-verified: `workgroup` is unbound in
>   `data_plane.process()` (a live NameError), and the other import does not resolve because its
>   package does not exist. **Extraction therefore removes nothing that works**, which reframes the
>   migration risk.

ALL THREE ADVERSARIAL LENSES FAILED THE DRAFT — six fatal objections, and the fixes were mostly
SUBTRACTIVE:

> The draft had put two engine names into `mac_vocabulary.yaml` as a member list: the vendor enum
> relocated into the canon, which is precisely what MAC must not carry. Deleted — the first-party set
> is a shipped, diffable index instead, and the vocabulary schema is NOT widened to admit it. Three
> gates were shown to admit a false green and were replaced rather than reworded.

The record carries six gates each with its printed denominator AND its named false-green, four
acceptance mutants that must NOT fire, the zero-change test with both limbs and its honest boundary,
seven revertible stages, five kill criteria, and fourteen numbered operator rulings.

Sanitised before tracking: the draft quoted a real workgroup and an SSO profile carrying a person's
name. `check_mac_public — 0 leak(s) over 488 tracked file(s), floor 0`.

## WHAT CHANGED

One tracked record, 2270 lines, Status PROPOSED. **Per the estate's own law an agent may only
propose; ratification is the operator's.**

Ruling #8 is flagged to answer FIRST: what a control-plane probe actually costs is UNMEASURED,
because measuring means calling — and the answer may collapse the whole billing tension that shaped
the three-tier design.

## WHAT IT DOES NOT PROVE

Nothing in it is built. The zero-change test named in the record has a stated boundary that it
measures the SECOND connector onward and never the first, so the thing most worth proving — that the
seam is in the right place — cannot be proved by the first connector. And the document's own most
expensive question is the one it could not answer without spending money.
