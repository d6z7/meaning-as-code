---
when: 2026-09-12T09:34:28
what: ruled three repositories REFERENCE ONLY and made the prohibition a pre-commit guard instead of a README sentence
topics: [consolidation, method, gates, harness]
kind: ruling
track: core
repo: mac-integration-kit
commits: [mac-integration-kit:d9c7b87, mac-integration-kit:2b13266]
---

## WHAT FORCED IT

The harness runs checkers from one repo against a bundle in another, so ONE red panel invites edits
in three repositories, only one of which is live. A README saying "do not change this" is necessary
and insufficient — the pull to "just green this gate" is strong.

Operator ruling, 2026-09-12: three repositories stop changing. They are kept to see how something was
made and to scavenge an idea from. A red gate in one of them is not a defect to fix; it is a record
of where that repo stopped. The live repos, and the only ones that change, are the language
(meaning-as-code), the product (mac-platform) and the method (mac-integration-kit).

## EVIDENCE

`git show -s d9c7b87` and `2b13266` (mac-integration-kit). The freeze tool was LIVE-TESTED, not
`--check`ed, and two failures only a live test could find are recorded in the commit:

> 1. core.hooksPath. One repo here sets it to `.githooks`, so git never looks at .git/hooks. The
>    first version wrote there, reported "frozen", and blocked nothing — a hook present, executable,
>    and unreachable.
> 2. The freeze dirtied the repo it froze. When the hooks path is inside a TRACKED directory, the
>    hook shows as untracked forever — and the repo is now frozen, so the obvious remedy (commit it)
>    is the one thing no longer permitted.

And the author's own two wrong verifications, recorded rather than quietly fixed:

> I read a `git commit` exit 1 as "the hook blocked it" when it meant "nothing staged", and I ran a
> probe in the wrong working directory and read a live repo's success as a freeze failure. --check is
> not evidence; attempting the forbidden thing is.

`self-test 13/13 · run_gates 8/8`. Armed and live-tested on four reference repositories; each
actually refused a commit.

## WHAT CHANGED

`freeze_repo` installs a pre-commit hook that refuses with the reason, names the live repo to use
instead, chains any existing hook rather than clobbering it, adds itself to `.git/info/exclude`, and
offers a visible escape (`touch .repo-unfrozen`).

## WHAT IT DOES NOT PROVE

A pre-commit hook is a local convenience, not an access control: `--no-verify` still commits, and a
push from another clone is untouched. The escape hatch is deliberate — a freeze with no escape gets
bypassed the first time it is inconvenient and then nobody remembers it exists — so this stops
accidents, not intent.
