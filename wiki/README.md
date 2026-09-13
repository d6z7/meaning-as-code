# The wiki — compiled knowledge, by audience

Three audiences, and the third is not like the other two.

| group | answers | lives |
|---|---|---|
| **`wiki/ontology-builder/`** | how do I build an ontology? | HERE — method, generic |
| **`wiki/platform-builder/`** | how do I build the platform? | HERE — method, generic |
| **`wiki/core/`** | what do both obey? | HERE — shared law |
| **an ontology's own documentation** | what does THIS ontology mean? | **IN THAT BUNDLE**, never here |

## Why the third group is not in this repo

It is INSTANCE knowledge. A page describing what one ontology's concepts mean, which relations it
grounds on, which rules govern its measures — that is the bundle's content, and this repository is
the generic instrument. The rule the whole estate is built on applies to documentation exactly as it
applies to code: **no instance specifics live in MAC.**

It also already exists, derived rather than authored: a bundle's read-view — `objects.json`,
`index.md`, the concept and rule pages, `ontology/vocabulary.json`, the `knowledge/` register — is
projected from the ontology by `sdk/project/`, and the console renders it. That is the ontology's
documentation, and it is regenerated from the source of truth rather than maintained beside it.

So: the first two groups are compiled HERE from the protocol and the decision records. The third is
compiled IN EACH BUNDLE from its own ontology, by machinery that already exists.

## Compiled, never authored

Every page here is generated and carries what it was compiled from. A page written by hand drifts
from the thing it describes, and nothing catches it — the same defect `mac_resources.py` exists to
prevent for bundle descriptions:

> A description maintained by hand drifts from the tree it describes, and there is nothing to catch
> it.

Each claim cites its source — a protocol entry, a decision section, or `file:line` — verbatim, so
`check_wiki_citations` can assert the cited span still exists. When the code moves, the page goes RED
rather than quietly becoming false.

That is `sdk/project/knowledge.py`'s rule, turned on ourselves:

> VERBATIM OR NOTHING ... it makes the register mechanically verifiable — a gate can assert that each
> span still appears in the source, which is impossible once someone has summarised it.

## The claims layer, and what forced it

The first compile produced 15 pages that were verbatim, checkable and unreadable to anyone who was
not in the conversation. Measured on `core/connectors.md`: 6 entries, 24 spans, and the span that
says what a connector IS sat third of six under a heading about a brief being overturned. The only
structure the compiler had was TIME, and time is not a semantic.

The missing piece is the one `sdk/project/knowledge.py` already names:

> Judgement about WHICH statements are normative belongs in a separate claims layer, so that
> extraction and interpretation never blur.

`protocol/claims.yaml` is that layer. A claim is an ADDRESS and a ROLE — `rule` (this span still
governs) or `boundary` (this limit is still open) — and it carries no prose of its own, so marking
a span cannot reword it. The compiler lifts THOSE SAME BYTES to the top of the page with the same
anchor and the same verifiable line range, and both gates check them exactly as they check the
body. It is a separate file rather than new front matter because `protocol/README.md` says entries
are never edited, only superseded.

A page with no marked span SAYS SO on its face, and `--check` prints the coverage denominator. An
uninterpreted page is an honest anthology; one that reads as compiled knowledge without being it is
the confident wrong answer this estate exists to remove.

## The front door

`wiki/index.md` is compiled too, and it carries the cross-cut the directory layout cannot. A topic
two audiences touched is filed as shared law, which measured on the real protocol put 13 of 15
pages in `core/` and left `platform-builder/` listing ONE page while twelve topics carried platform
entries. The index lists, per audience, every page carrying at least one entry of that track, with
that audience's count beside the page's own — so the door leads somewhere without any file being
filed where it does not belong.
