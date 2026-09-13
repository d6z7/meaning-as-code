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
