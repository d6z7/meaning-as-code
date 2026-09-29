# PROPOSED 2026-09-29 — what the ontology guard should ask, and what else it should ask it about

Two changes to `ontology_guard.py`, which **no agent may write** — including the agent proposing
this. That is the point of it, and it is why this is a proposal rather than a commit.

---

## A — the guard asks the wrong question about the path

**What happened.** Writing `meaning-as-code/guardrails/ontology/concepts.yaml` — the guardrail that
would govern the ontology plane — was denied `gate_unreachable`. The guard saw `/ontology/`, looked
for a manifest to judge the bundle by, found none, and denied. *Unknown means deny* is the right
default; the path is simply not a meaning plane.

**It is a name collision, and the guard has met this class twice already.** Its own source records
both, and the note it left is the general form:

> *"a guard that makes its own mechanism unfixable protects nothing and costs a day."*

The guardrail tree is that mechanism. Blocking it is the same recursion, one layer out.

**The obvious fix is WRONG, and the estate proves it.** *"Resolve the bundle; no manifest means it
is not a plane; allow"* — nine directories named `ontology` have no manifest above them, and they
are three different things:

```
archive-SystemB/ontology            real meaning plane
public/estate/ontology                    real meaning plane
archive/archive-poc/SystemB/…       real meaning plane
mac-integration-kit/ontology           the method track          (already exempted)
meaning-as-code/guardrails/ontology    specs ABOUT the plane     (this case)
archive/terraform/modules/…       a terraform module
archive/tests/unit/ontology       unit tests
archive/images/ontology           images
```

A manifest-absence rule would open the first three to unlock the fifth. **The substring test is
crude but it fails SAFE: it over-denies.** Any replacement must be a POSITIVE identification, never
an absence test.

### The change

`is_protected` already carries two exemptions — `_SOURCE_TREES` (a fragment list) and
`_is_method_track` (self-identifying). This is a third, in the same clause, of the second kind:

```python
if "/ontology/" in path:
    if (any(marker in path for marker in _SOURCE_TREES)
            or _is_method_track(path)
            or _is_guardrail_tree(path)):        # NEW
        return False
    return path.endswith(_MEANING_SUFFIXES)
```

```python
_SCHEMA_REL = "mac.schema.json"

def _is_guardrail_tree(path):
    """True for `<framework>/guardrails/ontology/…` — rules ABOUT the plane, never meaning IN it.

    SELF-IDENTIFYING, like `_is_method_track`, and for the same stated reason: a list of directory
    names would have to grow every time the framework did. Two conditions, both positive, neither
    acquirable by a bundle —
      * the `ontology/` directory sits directly under a `guardrails/` directory, and
      * the repository root carries `mac.schema.json`, which makes it the FRAMEWORK.
    Measured 2026-09-29: 0 of the 9 bundle repositories in this estate carry that file, and a
    bundle cannot acquire the exemption without shipping the framework itself.
    """
    p = path.replace(os.sep, "/")
    i = p.find("/guardrails/ontology/")
    if i == -1:
        return False
    root = p[:i]
    return os.path.isfile(os.path.join(root.replace("/", os.sep), _SCHEMA_REL))
```

**Why both conditions.** `/guardrails/ontology/` alone is acquirable — a bundle could create one.
`mac.schema.json` alone over-exempts the whole framework repository. Together they name one thing.

**What it does not change.** Every real meaning plane stays protected. The `.ontology-unlocked`
marker, the sign-off and the lock's two halves stay unconditionally denied to every agent.

---

## B — should the guard cover the data plane?

**Not the plane. Two acts in it.**

The data plane is almost entirely MEASURED and declared `re-derived`: descriptors, profiles,
references, registers, samples, pages. Guarding those would block the pipeline that regenerates
them and protect nothing — a re-derived artifact is *supposed* to be overwritten.

But two things there are HUMAN ACTS, and neither is protected today. Both are writable by any agent
right now, including this one.

### B1 — a `ruled` transform

`transform_sql` is, by its own guardrail, *"the only authored artifact in the data plane"*. Since
2026-09-29 it declares who decided its shape: `mac.transform.driven_by` ∈ {passthrough, proposed,
ruled}.

Nothing stops an agent replacing a person's decision with a generated one. That is not
hypothetical — it is what wiring `mac_passthrough` into the pipeline did within the hour it was
tried, and it is what `mac_lookups._stem` records from 2026-09-28: a generator silently overwriting
hand-authored work, and the loser's content preserved nowhere.

> **Deny an agent write to `data/transforms/*.sql` when the file ON DISK declares
> `driven_by: ruled`.**

Read the **existing** file, never the incoming content — otherwise an agent rewrites `ruled` to
`proposed` in the same write that replaces the statement. Same shape as the sign-off: you cannot
rewrite the thing that authorises you. `passthrough` and `proposed` stay agent-writable, so the
generator and the proposing path keep working.

### B2 — a finding's terminal disposition — **the more serious hole**

`data/quality/data_quality_register.yaml` is agent-written by design: `mac_dq_findings` raises
findings, and that is a DESCRIPTION. But a finding's disposition —

```yaml
status: accepted        # or wont_fix, resolved
ruled_by: <a person's name>
reason: <why>
```

— is a claim **that a person acted**. Nothing stops an agent writing it.

This matters more than B1 because of what reads it. `check_data_plane_approved` takes the data
pipeline's exit to be *its own register, fully dispositioned* — every finding at a terminal status
with `ruled_by` and a reason. So an agent that can write dispositions **can manufacture its own
approval to start the ontology.** The sign-off artifact is unwritable precisely so this cannot
happen, and the register is the same authority through an unguarded door.

The rule already exists in words, on `DataPlaneApprovalFile.submitted_via`:

> *"an agent may write a DESCRIPTION; only a human may write a DISPOSITION."*

> **Deny an agent write to the register that introduces or alters a terminal `status`, `ruled_by`
> or `reason` on any issue. Raising, re-measuring and re-describing findings stay allowed.**

This is a field-level rule, not a path-level one, so it is more work than A — the guard would have
to diff the incoming document against the one on disk. It is also the only one of the three whose
absence lets an agent open a gate.

---

## What I am not proposing

- Not guarding the measured data plane. It is re-derived by design.
- Not weakening `unknown means deny`. A is an exemption for one positively-identified directory.
- Not implementing any of it. The guard denies writes to itself, always, and an agent editing a gate
  so the agent gets past the gate is the exact thing gates exist to prevent — a correct fix made by
  me is still the wrong precedent.

**Ordering.** B2 first: it is the only one where the absence lets an agent manufacture an approval.
A is a one-function convenience that unblocks the ontology guardrails. B1 is cheap and can ride with
either.

## Addendum 2026-09-29 — a false positive, measured three times

`$C/ontology/concepts/x.yaml` in a shell command trips the guard's `gate_unreachable` branch: the
variable is not expanded when the hook reads the command, so the path does not resolve and the guard
denies as unreachable. Three denials in one session, each a read. Literal paths pass. Either the guard
expands `$VAR` against the caller's environment before judging reachability, or it says "unexpanded
variable" instead of "unreachable" — the second is the honest minimum, because the current message
sends the author to look for a missing file that exists.
