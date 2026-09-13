---
when: 2026-09-13T00:19:47
what: stopped the console's runtime mount state — 151M of it, including a checked-in warehouse — from appearing as committable repository content
topics: [the-public-boundary, console, containers]
kind: defect
track: platform
repo: mac-platform
commits: [mac-platform:e3c7be8]
---

## WHAT FORCED IT

`mounts/` and `mount_pins.yaml` record which containers THIS machine has open, and hold a full copy
of each under `artifacts/<version>/`. They appeared as untracked the moment anyone opened a bundle —
**151M at the time of writing, including a checked-in 21M warehouse.**

## EVIDENCE

`git show -s e3c7be8` (mac-platform):

> Per-operator state, not repository state. Committing it would push one person's open bundles into
> the product repo and then have every other operator's console fight it for the same paths.

This surfaced the same evening the console gained `GET /browse` and `POST /open`
(`2026-09-12/027`) — the feature that makes opening cheap is the feature that makes this state
appear.

## WHAT CHANGED

Both paths ignored.

## WHAT IT DOES NOT PROVE

Ignoring is not a guard. Nothing prevents a future mount directory under a different name from
appearing, and nothing measures the size or the content of what a mount copies onto an operator's
disk. A customer bundle's full contents sitting in a product checkout is exactly the shape the public
boundary exists to prevent, and here it is prevented by one `.gitignore` line and an operator reading
`git status`.
