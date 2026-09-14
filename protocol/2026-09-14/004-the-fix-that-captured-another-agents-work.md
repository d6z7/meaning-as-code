---
when: 2026-09-14T13:50:00
what: the stage-then-check rule introduced yesterday caused one agent's commit to silently capture another agent's staged work, under a message that describes neither
topics: [method, harness, gates, denominators]
kind: fix
track: core
repo: meaning-as-code
commits: [57b9106]
---

## WHAT FORCED IT

An agent finishing a task reported, unprompted:

> *"Another agent's commit swept up my staged work. I committed nothing. But commit 57b9106 landed
> from a concurrent session and captured my three staged files. My work is now in HEAD under a
> message that describes only PLAN.yaml and protocol corrections and does not mention the vocabulary
> or the gate."*

## EVIDENCE

Verified. `git show --stat 57b9106`:

    CONFORMANCE.md                          26 +
    decisions/PLAN.yaml                     65 +          <- what the message describes
    mac_vocabulary.yaml                     80 +
    protocol/2026-09-14/003-....md          17 +-         <- what the message describes
    tools/check_dq_resolution_sync.py      617 ++++---

**A 617-line gate rewrite and an 80-line vocabulary addition went into a public repository under a
commit message that mentions neither.**

## THE CAUSE, AND IT IS THE PREVIOUS DAY'S FIX

Protocol entry 001 recorded that `check_mac_public` reads `git ls-files` and therefore cannot see an
unstaged file, so the gate must be run **after** `git add`, never before. That rule is correct and it
caught a real leak within the hour.

But it was written for a single worker. Handed to a subagent it reads as *"stage your files, then
check"* — which is exactly what the agent did, correctly, having been told to **commit nothing**.
Staging is not committing, so the agent obeyed. Then the parent session staged two of its own files
and ran `git commit`, which commits **everything staged, by anyone**.

    the fix for one hazard          run the gate AFTER `git add`
    created another                 a subagent's staged work is invisible to the parent's intent
    and the parent's `git commit`   takes the union without announcing it

**Neither party did anything wrong.** The instruction was followed and the commit was ordinary. The
index is shared state between concurrent workers and nothing in the workflow treats it as such.

## WHAT CHANGED

Nothing in the tree, and that is the point: **the defect is in the WORKFLOW, not in the code.** What changes
is a rule, recorded here, and one line of the entry that created the hazard.

## THE RULE

> **BEFORE ANY COMMIT, READ `git diff --cached --stat` AND CONFIRM IT MATCHES WHAT THE MESSAGE SAYS.**
> One command. It would have caught this, and it costs nothing.

And the sharper form, for delegated work:

> **A SUBAGENT MUST NOT LEAVE WORK STAGED.** If the stage-then-check order is required — and it is —
> the agent stages, checks, and then **unstages** (`git reset`), leaving the tree dirty and the index
> clean. Dirty is visible to the parent; staged is invisible to the parent's intent.

## WHY IT IS NOT BEING FIXED BY REWRITING HISTORY

`57b9106` is pushed. Amending it would rewrite a published commit to correct a message, which trades
a wrong description for a rewritten history on a branch other clones may hold. **The content in HEAD
is correct and complete** — the gate self-tests 17/17 and the framework runner is byte-identical to
its baseline — so the defect is the description alone. It is corrected by this entry and by the
following commit's message, both of which name what `57b9106` actually contained.

## WHAT IT DOES NOT PROVE

That this is rare. It is the FIRST commit made while three agents were writing in one repository, and
it captured work on the first attempt. Every parallel session since the tactics rule landed has had
this hazard; it has simply not been looked for. **No gate detects it** — a commit whose message omits
half its diff is invisible to every instrument in the estate, and `check_protocol` would count it as
covered because the sha is cited by an entry.
