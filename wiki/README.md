# The wiki — compiled knowledge, by audience

Three audiences, and the third is not like the other two.

| group | answers | lives |
|---|---|---|
| **`wiki/ontology-builder/`** | how do I build an ontology? | HERE — method, generic |
| **`wiki/platform-builder/`** | how do I build the platform? | HERE — method, generic |
| **`wiki/core/`** | what do both obey? | HERE — shared law |
| **an ontology's own documentation** | what does THIS ontology mean? | **IN THAT BUNDLE**, never here |

Every directory listing is complete for its audience, and the next section is how — because
"lives HERE" was, for one compile, not true.

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

## One home per page, one door per audience

A page lives in ONE directory, and the rule that puts it there is a derivation, not a preference:

* every entry on the topic that declares a track declares the SAME one -> that audience's directory;
* two or more different tracks -> `core/`, because a topic both audiences touch IS shared law;
* nobody declared one -> `core/`, and the page discloses that nobody said.

Measured on the real protocol, that rule filed 13 of 15 pages in `core/` and left
`platform-builder/` listing ONE page while twelve topics carried platform entries — against
`core 29, ontology 8, platform 12` entries per track. Every page was defensibly filed and the SET
was useless: this document said the platform builder's method "lives HERE" and the directory
listing said one page. A directory listing is the only navigation a filesystem gives a reader, so
that contradiction could not be repaired from another file.

**It is not repaired by moving pages.** A topic the platform builder needs is not thereby not
shared law, and majority-rules routing was measured too: `core 10 / ontology 3 / platform 2`, five
pages moved, `connectors` decided by a margin of ONE entry, each moved page evicted from the other
audiences — and the platform builder still reaching 2 of the 12 topics they wrote on.

So every audience that wrote on a topic filed elsewhere gets a **compiled stub** in its own
directory: the page's address, that audience's entry count as a fraction of the page's, and the
list of that audience's entries on it. A stub quotes NOTHING — no span exists at two addresses, so
no copy can drift from another — and it says on its face that it is a door and not a subset,
because `core/` is the law both audiences obey and a filtered view would hide exactly that. Files
per audience directory are now `core 13, ontology-builder 8, platform-builder 12`: the shape of the
entry counts.

A stub is derived from ONE page and carries no repository-wide number, so an unrelated topic can
never restamp it. `mac_wiki --check` judges a stub with the same five predicates as a page, and
`stale-stub` is the class for a door whose audience has stopped writing on the topic.

## The front door

`wiki/index.md` is compiled too, and it is the only output derived from every page — so it is the
only one allowed to carry the repository-wide counts: pages, stubs, files per audience directory
beside entries per track, and, per audience, what is filed there and what is reachable through a
stub. `stale-index` is the class that stops it becoming the one hand-maintained file in a compiled
tree.
