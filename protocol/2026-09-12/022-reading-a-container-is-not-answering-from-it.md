---
when: 2026-09-12T20:45:42
what: split the container loader's trust model so a bundle can be opened to be LOOKED at without meeting the strictness required to ANSWER from it
topics: [containers, capabilities, gates, the-public-boundary]
kind: build
track: platform
repo: mac-platform
---

## WHAT FORCED IT

The task was "open an ontology and inspect it, like a file". `open_container` already existed and
already took a `require_trust` floor whose docstring says "a host that ANSWERS should pass
require_trust='signed-verified'" — but it applied answering-grade strictness to EVERY mount, so the
floor governed only the trust rank and nothing else.

Measured on the reference bundle: capabilities `readable` and `renderable` are both BACKED,
`answerable` is NOT. So the bundle is perfectly inspectable and unfit to answer from, and the loader
collapsed that into one `ok=False`.

## EVIDENCE

`git show -s ac29f7d` (mac-platform):

```
before   ok=False, 11 errors   (1 unbacked capability + 10 infra handles)
after    ok=True,  0 errors, 11 warnings the caller can see and decide about
         and with a trust floor: ok=False, 12 errors — still refused
```

The account-id class is NOT softened, and that is ASSERTED rather than assumed: the secrets gate
forbids account ids everywhere including config, and a planted account id refuses even a read-only
mount.

```
make check: all green · 82 passed · run_all_gates 14/14
```

Four tests pin the split, in a package that had 100 test functions for 65 modules: a clean bundle
reads; a leaked handle warns a reader and refuses an answering host; an account id refuses both; an
unbacked capability claim does not block a read.

## WHAT CHANGED

Naming a trust floor makes you an ANSWERING host and gets the strict reading. Naming none makes you a
READER, and a leaked handle or an unbacked capability claim becomes a warning the caller can see.

## WHAT IT DOES NOT PROVE

Stated in the commit rather than left for a reader to discover: **there is no answering path in this
estate.** `POST /ask` returns 500 unconditionally and every agent module fails to import, so the
answer-mount half governs a capability that does not exist today. Its only value is that the refusal
is already in place if answering is ever wired. The deliverable is the READ path, and that one works.
