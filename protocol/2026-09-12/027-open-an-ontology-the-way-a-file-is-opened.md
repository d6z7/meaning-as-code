---
when: 2026-09-12T23:57:22
what: made the console open and close an ontology the way an editor opens a file, and gave the object palette one colour per type with connectors that follow their tables
topics: [containers, console, capabilities]
kind: build
track: platform
repo: mac-platform
commits: [mac-platform:233492e, mac-platform:5059297]
---

## WHAT FORCED IT

The console could only see bundles it was started against. Opening one meant restarting the server,
which is not what "open" means to anyone who has used an editor.

Underneath, the bundle graph answered `{nodes: 0, edges: 0}` for any bundle filing concepts by domain
— the reason the ontology graph sat empty telling the user to run a harvest that would not have
helped.

In the views, the same four object types were being styled independently in four places and drifting;
the lineage view carried the chain all the way back from data sources, which made the ONE
relationship it exists to show — what grounds what — the hardest thing on the screen to find; and an
ER connector kept the handles it was born with, so moving a table left its lines anchored on the far
side and routed around the box.

## EVIDENCE

`git show -s 233492e 5059297` (mac-platform).

> `GET /browse` walks the filesystem for openable containers; `POST /open` takes a resource
> description and resolves its identity, so the thing a user picks in a file dialog is the thing that
> opens; `.mac` joins the source extensions and language map — it was whitelisted everywhere except
> the one dialog that decides whether a file is selectable at all; an unpublished mount gets a
> derived version (`v{tree_hash[:12]}`) and a synthesised MANIFEST, because refusing to open a bundle
> for lacking a published version is refusing to open every bundle anyone is actually working on.

`make check: all green.`

On the palette: **one colour per TYPE, not per class.** Every concept shares a background and is told
apart by its icon. The commit records getting that wrong twice by varying the background per concept
class, and that lookups and datasets were separated by lightness rather than hue, which is what made
them indistinguishable.

On the connectors: each column carries four handles and the edge picks the pair that FACES the other
table — re-picked DURING the drag, because the cached route used to win until the drag ended and the
line visibly resisted the move.

## WHAT CHANGED

`lib/objectKind.js` is the single source of truth for what each object type looks like. The lineage
view was renamed Grounding and now shows datasets to concepts and stops there. The bundle graph reads
concepts recursively and BOTH grounding shapes, and carries `derived-over` and `discriminates` edges.

## WHAT IT DOES NOT PROVE

Opening is not answering. This is the READ path over a container whose `answerable` capability is
measurably unbacked (`2026-09-12/022`), and the console's Connection page still hardcodes thirteen
fields of one engine — the requirement to fix that was not written until the next morning
(`2026-09-13/061`).
