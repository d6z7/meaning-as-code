---
title: The Seam Contract — mac.seam/1 (how a framework tool answers a host)
version: '0.1.14'
date: 2026-09-19
status: DRAFT — normative for every framework-side seam; the ENFORCING copy is tools/check_seam_contract.py
companions:
  - tools/check_seam_contract.py   # the gate. IT holds the seam registry; this document holds no rows
  - tools/project_objects.py       # seam 1 — the object index
  - tools/project_edges.py         # seam 2 — the edge index
  - tools/project_concept_page.py  # seam 3 — one concept page
  - CONFORMANCE.md                 # the same discipline one plane down: a closed vocabulary, enforced
  - sdk/gate/check_seam_agreement.py  # the estate's existing seam-inventory gate, whose house style this follows
audience: whoever writes seam #4 — and the host that calls it
scope: GENERIC — domain-neutral. No bundle, source, brand or person is named here.
---

# The Seam Contract (`mac.seam/1`)

A **seam** is a framework-side executable that DERIVES an answer from a bundle and prints it, so that
a host which may not import the framework can ask a question instead of reading a build artifact.
There are three today. This document is what the fourth must obey, and
`tools/check_seam_contract.py` is the copy that refuses.

---

## 0. WHY THIS DOCUMENT IS HERE, AND NOT IN THE HOST OR IN THE KIT

Three homes were available and two are wrong.

* **The host repository** (the console) owns the *caller*, and most of the defects this contract
  closes are the caller's. That is an argument for putting the *host clauses* where the host is —
  §7 says so, and it is the one part of this contract this repository cannot enforce. It is not an
  argument for putting the *seam standard* there: the seams are files in `tools/` of THIS repo,
  released on THIS repo's version, and a standard whose subject lives in another repository is the
  shape that produced `sdk/gate/check_boundaries.py` — a gate that NAMES a contract file in its
  docstring, never reads it, and examines 100 files of which 0 are the tree the contract is about.
* **The integration kit** owns METHOD docs — how an estate runs an ingestion, which steps exist, who
  signs what. A wire format is not a method. Putting it there would separate the rule from the
  three files that implement it and from the gate that judges them.
* **Here.** The framework owns the seams, owns the grammar the seams read, and owns the gate. One
  home for one fact is this estate's whole discipline; `CONFORMANCE.md` is the precedent — the
  normative prose sits beside `mac.schema.json`, and the enforcer reads the schema rather than
  restating it.

The same rule applies INSIDE this contract: **this document declares the COLUMNS, the gate declares
the ROWS.** The registry of seams — their tool names, argv, subjects and interpreter floor — lives
in `tools/check_seam_contract.py` as `SEAMS`, and nowhere else. A seam that is not a row is not
checked; a row that is not called is a finding. If this document listed the seams too, the estate
would own two inventories of one fact, which is the defect class (see §1) that each of the last five
incidents has been an instance of.

---

## 1. WHAT FORCED THIS

Five incidents in one working day, every one the same act: **a surface served something it could not
vouch for, and nothing in what the reader saw said so.**

1. An object created in a bundle did not appear in the index — the page was reading a build artifact.
2. An edge page showed 6 relationships while the declared file held 17 — same cause, one plane over.
3. A concept page's Fields table read a descriptor key no column carries, and rendered empty rather
   than absent.
4. A concept page vanished when its projected `.md` was deleted — the page WAS the artifact.
5. A route returned "no such route on this API" because the running server predated the code on disk.
   The server reported a fact about the API when the truth was a fact about the PROCESS.

The repair for 1–4 was three tools — `project_objects.py` (244 lines), `project_edges.py` (216),
`project_concept_page.py` (287) — each written by copying the previous one, inside one session. On
the host side each needed its own handler, its own cache, its own lock table and its own fallback.
**That duplication IS the API being asked for, arrived at three times by copy instead of once by
design.** Two more seams are queued (rule pages, an index page), so the contract pays for itself
immediately or never.

And the copies do not agree. Measured today by running all three against this repository's own
public example bundle (91 files) on a 3.12 interpreter:

| | top-level keys on success | keys on a named failure | bundle files it opened | `state`/`status` token |
|---|---|---|---|---|
| object index | **6** | **3** (3 of the 6 vanish) | 20 | none |
| edge index | **5** | 5 | 1 | none |
| concept page | **3** | 3 | 17 | 8 values, 6 documented |

Four fields and one discipline are all three agree on: `ok`, `derived_at`, `root`, `absent[]`, and
`json.dumps(..., ensure_ascii=False, sort_keys=True)`. `absent[]` — the one field all three agree on
the NAME of — enumerates 6 planes in one, 2 files in another and 2 paths in the third, so a bare
`absent: []` carries three different denominators and therefore none.

---

## 2. THE CROSSING — AND WHAT IT INHERITS

### 2.1 The transport is not a choice

From the host repository's `boundaries.yaml`, the tree the console lives in:

```yaml
    may_import: [wiki]                   # NEVER sdk.{authoring,engine,gate,project}
    may_not_import: [sdk]
    may_sys_path_mutate: false
    reads:   ["the path each configured entry names (its pin's tree_hash enforced on read)"]
    forbidden_reads: [sources/*/*/data/**, sources/*/*/ontology/**]
    dispatcher: fail-closed              # unknown route -> 404/403, never a permissive 200
    sole_ssot_writer: sdk/authoring/operations.py   # (declared on the framework tree)
```

Three clauses land on this contract:

1. **`may_not_import: [sdk]` forbids the call and `may_sys_path_mutate: false` forbids the
   workaround.** So a seam is a SUBPROCESS: argv in, one JSON object on stdout, an exit code, prose
   on stderr. No long-lived worker holding framework objects is permissible. This is fixed by the
   boundary, not chosen for convenience.
2. **A seam is therefore self-contained and invocable by absolute path.** Because the host may not
   put the framework on its path, each seam performs its own `sys.path` setup from
   `Path(__file__).resolve().parent.parent` — legal only because the seam lives on the framework
   side of the line. That is a required clause, not an implementation detail.
3. **Read-only is a boundary property, not a seam courtesy.** The sole SSOT writer is named
   elsewhere; a seam takes no `out_dir` and writes nothing inside the bundle.

> **CORRECTION TO THE RECORD, because three of three seam docstrings get it wrong.** That file is at
> the HOST REPOSITORY ROOT, not under the console package, and the tree carrying these rules is
> named `wiki` (`role: gui`), not `console`. All three seams cite a correct rule under a name the
> contract file does not use. Cite the tree by its real name or the clause cannot be looked up.

### 2.2 The CLI shape

```
  <interpreter> <absolute path to the seam> <bundle-root> [--<subject> ID] [--out PATH]

  stdout   exactly one JSON object, json.dumps(..., ensure_ascii=False, sort_keys=True) + "\n"
  stderr   prose for a human, never the answer
  exit     0 | 2 | 3   (1 is reserved; see §4.3)
```

* `<bundle-root>` is the BUNDLE ROOT, never the data directory. A seam that resolves
  `evidence/…` off the root and is handed `<root>/data` reports everything unproved and refuses
  nothing — measured as a live trap when the edge index was written.
* A SUBJECT seam (one that answers about one member, e.g. a page) takes its id as a NAMED argument
  and validates it as a bare id, never a path. Both halves of that guard exist today — one in the
  seam, one in the host — and only one of the two will be updated when the rule changes; the seam's
  is the trust boundary and is the one that must stay.
* **`--out` writes the CALLER's file and never one inside the bundle, and stdout still carries the
  envelope.** What went wrong without it: all three seams promise this in prose, **0 of 3 validate
  the path**, and with `--out` set nothing at all goes to stdout — so a successful `--out` run is
  indistinguishable from a failure over the host's `if out:` test. 0 of 3 seam call sites pass
  `--out` today and 2 of 2 lineage call sites do, so the trap is latent, not live — and it arms the
  moment the call path is unified.

---

## 3. THE ENVELOPE

One JSON object. **The reserved keys are invariant: they are present on EVERY exit, at their empty
value when there is nothing to put in them.** Everything a seam wants to publish beyond them goes in
one bag (`aux`) whose contract is that nothing in it may be relied on.

| field | req | type | what it is, and what went wrong without it |
|---|---|---|---|
| `envelope` | **R** | `"mac.seam/1"` | The version of THIS contract. A host that does not know the version refuses intelligibly instead of raising `KeyError` on a key that moved. |
| `mode` | **R** | `"index"` \| `"document"` | Constant per seam, declared by the seam and **verified against `result` by the gate** (§5). Today 0 of 3 declare anything; the host infers the same fact from an emptiness heuristic, and the branch it infers is unreachable. |
| `status` | **R** | one closed token (§4) | The one field the host branches on. Today 1 of 3 seams carries a token at all, and it has 8 values in code, 6 in its own docstring and 5 in the host's comment: the estate's one closed vocabulary is stated as 5, 6 and 8 in three files. |
| `reason` | **R** | string \| `null` | `null` **iff** `status == "derived"`; a sentence otherwise. Always PRESENT. Today 1 of 3 always sets it and 2 of 3 set it only on failure, so a consumer cannot tell "key absent" from "reason: null". The token set is closed; the sentence is open, and the sentence is what a person acts on. |
| `result` | **R** | list (index) \| str or object (document) | The principal result under a FIXED key. Empty value of its own type whenever the status is not serve-eligible. This is what removes "which key holds the content" and "what does an empty one look like" from the host; today those are 3 hand-written literals in 3 host functions. |
| `counts` | **R in index mode** | `{returned: int, declared: int}` | **N of M.** `declared` may never be absent or `null` under a serve-eligible status. What went wrong without it: an index seam pointed at a bundle with no ontology plane returns `result: []`, exit 0 — a zero that means "nothing is authored" published in the same envelope as a zero that means "all of them are unmeasured". A zero with no denominator is the defect at the root of incident 1 and incident 2. |
| `inputs` | **R** | list of `{path, role, present, parsed, count}` | Every file the seam reads, declared. `role ∈ {spine, row, attribute, framework}`; `path` is root-relative, or `framework:<name>` for a framework-side input. It replaces `absent[]`'s three different denominators, `unparsed[]`'s two different item keys (`{path,error}` in one seam, `{path,reason}` in another) and the per-file blocks, and it is the evidence the cache rule (§6) is checked against. **It is verified against a measured open-trace, not trusted** — see §8, clause 10, and the reason there. |
| `partial` | **R in index mode** (may be `[]`); **must be `[]` in document mode** | list of `{input, role, effect, reason}` | `partial != []` **iff** `status == "degraded"`. The host must never infer degradation from an empty result: today's predicate is `not content and (reason or ok is False)`, and **every path that sets `ok:false` also empties the content**, so across 2 index routes and 3 failure causes the number of reachable "served payload with top-level ok false" states is **0**. The estate has never actually shipped the degrade it argues about. |
| `seam` | **R** | `{tool, version, framework_root, code_id}` | The identity of the code that answered. `code_id` digests the seam file plus every `role: "framework"` input. The host's locator prefers an installed framework root and silently falls back to a sibling checkout, so WHICH framework answered is an unstated variable today; nothing in any payload names it. Free to compute — one seam already opens the framework's `VERSION` on every call. |
| `subject` | **R** | `{kind, id}` \| `null` | `null` for whole-bundle seams. Retires the ad-hoc per-seam id keys and gives the host ONE cache-key element instead of a hand-built string. |
| `derived_at` | **R** | ISO-8601 `Z`, second precision | The single field all three already agree on. Keep the NAME: on the wire today the same fact appears as `derived_at`, `snapshot_at`, `observed_at` and `at` across six routes. |
| `aux` | **R, may be `{}`** | object | Everything else the seam publishes. Declared optional AS A WHOLE, so no client may treat a member as mandatory. This is the structural fix for "3 of 6 top-level keys vanish on failure": reserved keys never vanish, and the keys that may vanish live in a bag whose contract says they may. |
| `local` | O | `{root, argv}` | **The only place an absolute filesystem path may appear**, and the host MUST drop the whole block before the wire. Today all 3 of 3 stamp the operator's absolute disk path at `derivation.root`, and the only thing keeping it off the wire is that the host happens to discard the block wholesale. |

---

## 4. THE CLOSED FAILURE VOCABULARY

### 4.1 It is partitioned by who may mint it

A flat list cannot be closed, because **a seam that cannot start cannot report on itself**. So the
vocabulary is one set, partitioned by emitter, and each half is grep-able against a literal tuple.

**SEAM-MINTED (7) — the seam ran and printed an envelope. A host may never invent one of these.**

| token | means | exit |
|---|---|---|
| `derived` | the payload is complete | 0 |
| `degraded` | served, and `partial[]` names every piece that is missing. **Index mode only.** | 0 |
| `absent_input` | a declared input is not there, so M is knowably 0 | 0 in index mode, 3 in document mode |
| `unparsed_input` | a declared input exists and will not parse, so M is UNKNOWN | 3 |
| `not_found` | `subject.id` names no member of the enumeration | 3 |
| `author_failed` | the one author raised; `traceback` (limit 6) goes in `local` | 3 |
| `bad_request` | a caller error before any derivation: root is not a directory, a malformed subject id, a bad flag | 2 |

**HOST-MINTED (4) — the seam did not speak, or spoke unusably.** The host already computes all four
distinctions today and throws them away into free prose (an `/objects` failure can reach a reader as
any of ~11 prose shapes, none machine-readable): `seam_missing`, `seam_failed`, `seam_timeout`,
`seam_unreadable`.

### 4.2 Why exactly these, so the next author cannot argue

**A token exists only where a caller BRANCHES; everything else is `reason`.** That is why
`empty_input` is not a token (index mode says `derived` with `counts: {returned: 0, declared: 0}`;
document mode says `not_found` and puts the count in the sentence) and why "this id is not a member"
and "this id names something that is not a member" are ONE token with two reasons. Tokens are
additive-only, and adding one bumps `envelope`.

Every state in the code today maps onto exactly one token with no residue: the page seam's 8 `state`
values, the object index's `unparsed[]` / `lineage.ok` / `register.reason`, the edge index's
`measurements.present` and its parse-error path, and all three `absent[]` lists.

### 4.3 The exit-code law

```
  exit 0  ⇔  status is SERVE-ELIGIBLE for this seam's declared mode
  exit 2  ⇔  status == bad_request  — AND the envelope is still printed on stdout
  exit 3  =  every other seam-minted token
  exit 1  =  RESERVED. Never produced deliberately; the host reads it as seam_failed.
```

**What went wrong without the exit-2 clause.** All three seams promise in their docstrings that
"even then a structured reason goes to stdout". Measured today: at exit 2 all **3 of 3** print prose
to stderr and **0 bytes** to stdout. The promise is false in the only place it matters, and the host
then reconstructs from `returncode != 0` a distinction the exit code already carried.

**What went wrong without exit 1 being named.** It is an undeclared fourth exit code that all three
can produce: any failure at or before import. Measured today on the interpreter one seam's own usage
line documents (`/usr/bin/python3`, which is 3.9.6 on this machine): that seam exits **1 with 0 bytes
on stdout** and an `AttributeError` for a `datetime` alias that is 3.11+. The other two carry an
explicit comment about that exact alias and run clean there — **the fix was written twice and
back-applied zero times.** A seam's promise "a failure is named, never silent" holds only AFTER
import, and one framework module validates the grammar schema AT import, so the window is real.

### 4.4 The interpreter floor is a clause, not a habit

Every seam declares a floor, and the gate runs it there as well as on `sys.executable`. The floor in
the registry today is **3.9**, because that is what two of three seams already code against by
explicit comment and what three of three usage lines imply by writing `python3`. **Raising it to
3.11 is a live alternative and is the operator's call** (§10): it fixes 1 of 3 seams by fiat and
makes the usage line in 3 of 3 docstrings wrong.

---

## 5. THE PARTIAL-RESULT RULE

> **Index mode may serve a payload whose status is not `derived`; document mode may not — where a
> seam is index mode if and only if its `result` is a list of independently derived members for
> which it can publish `returned of declared`, and where a failure of the input that ENUMERATES the
> members refuses in BOTH modes.**

### 5.1 The property is the payload's shape, and the gate re-derives it

The author declares `mode`; **the gate verifies the declaration against the bytes the seam actually
emitted**, so taste cannot enter and a wrong declaration is a FAILURE, not a judgment call:

* `mode: "index"` ⇒ `result` is a list ∧ `counts.declared` is an int ∧ `partial` is present ∧ at
  least one `inputs[]` entry has `role: "spine"`.
* `mode: "document"` ⇒ `result` is NOT a list ∧ `partial == []` ∧ `status != "degraded"`.

### 5.2 Why it is the right property, and why it is not invented

It reproduces every choice the three seams already made, including the one they made without
noticing. The edge index refuses on an unparseable `edges.yaml` **not** because an edge index is
somehow document-like, but because that file is its SPINE: when the enumerating input cannot be read,
"0 rows" and "the list could not be read" have the same shape on screen, and a degraded answer is a
lie with a denominator of zero. The same seam DEGRADES when its measurement record is missing,
because membership is intact and only a per-member attribute is unknown. One seam, both sides,
correctly — that is the evidence the rule is real rather than imposed.

### 5.3 The useful half: it tells you which SHAPE to choose

A seam #4 author never argues about pages versus lists. They answer one question — *can I publish N
of M?* — and if the honest answer is no, the shape they must return is a document and the rule
follows. The two queued seams settle with no conversation:

* **rule pages** — one composed artifact → document → refuses.
* **an index page** — decided by what it RETURNS. `result: "<markdown>"` is a document and refuses;
  `result: [entries…]` is an index and may degrade. **If you want to degrade, return a collection,
  not a rendered document.**

### 5.4 The clause where today's code is actually wrong

The switch must be EXPLICIT. Replace the host's `not result and ok is False` heuristic with the
closed token plus `partial[]`. And the completeness of a degrade is **not the author's to assert**:
see §8 clause 10 and clause 15 — measured today, a document-mode seam that is already on the
refusing side still stamps `derived` while silently dropping a quarter of one section's content,
because refusal keyed on a hand-written list of states is not a completeness invariant over the
inputs.

---

## 6. THE CACHE RULE

> **The cache key is `(bundle fingerprint, FRAMEWORK fingerprint, declared extra key material)`.
> The framework half is computed by the HOST — it is the host's cache — and every seam stamps
> `seam.code_id` as the cross-check. Every file a seam reads appears in `inputs[]`.**

### 6.1 Which planes a seam must declare

Every file the seam opens, on either side of the line:

* **bundle-side**, root-relative, with a `role`: the plane that ENUMERATES members is `spine`; a
  plane whose files each contribute members is `row`; a plane that decorates members already
  enumerated is `attribute`.
* **framework-side**, as `framework:<name>`, `role: "framework"`: the grammar schema, the version
  file, a vocabulary file, a register directory — anything read from the framework tree that is not
  the seam's own code. The seam's own code and its imported modules are covered by `seam.code_id`
  instead, and must not be listed one by one.

**What went wrong without it.** The host's fingerprint stats the BUNDLE tree only. Measured today by
tracing every `open` with an audit hook while running each seam against the public example bundle:
one seam opens **2 framework data files on every call** (a schema and a version file, both at import
time) and a third conditionally, depending on WHICH subject is asked for — so one route's key covers
a different input set for different subjects. Edit the framework and the host keeps serving payloads
derived under the old rules until an unrelated bundle file's mtime moves. That is incident 5 one
plane down, and it is live rather than hypothetical whenever the framework tree is dirty.

### 6.2 What the host owes in return (stated here because the seam cannot do it)

* The exclusion list for the fingerprint is **derived, not written**: it is exactly the set of
  declared fallback artifacts. Today the host's hand-written exclusion covers 1 of the 3 artifacts it
  itself reasons about, so one projection run moves dozens of fingerprinted files and invalidates
  all three caches for output no seam reads.
* Every seam cache is **registered**, so one clear covers all of them. Today the host's close path
  clears 3 of 7 derivation caches while promising nothing lingers; the 4 that linger are exactly the
  4 seam routes, and 0 of their 4 lock tables are ever cleared.
* Per-subject caches are **bounded**. One of them holds one payload and one lock per subject ever
  requested, for process life; the eviction helper exists and is called at 2 sites, 0 of them seam
  routes.
* The host must state **which root** a seam is handed. The derive path and the fallback path resolve
  the root through two different functions that are the same function today and are documented as
  kept apart for a future split — which would silently make the derived answer and its fallback
  describe different directories.

---

## 7. WHAT THE CONSOLE HOST MAY ASSUME

### 7.1 The serve table — the host stops guessing

```
  serve the payload   iff   status == "derived"
                       or   (mode == "index" and status in {"degraded", "absent_input"})
  otherwise            fall back: the declared artifact → else unavailable
```

Everything else — `partial`, `inputs`, `counts`, `reason` — is **forwarded verbatim, never
re-curated per route**. That single clause repairs a measured defect: each of 3 of 3 seam routes
lifts its own hand-picked subset of the derivation into its own block and **all three drop `reason`**,
so a reason that survived into a served payload is unreachable by the client.

### 7.2 What the host may assume

1. Exactly one JSON object on stdout, on exits 0, 2 and 3. Nothing else is ever on stdout.
2. The reserved key set of §3 is present on all of them, including failures.
3. `status` is from the closed seam-minted set, and the host may branch on it alone.
4. The seam wrote nothing. The bundle is unchanged by the call.
5. The seam is never stale relative to disk: it is re-executed per call.

### 7.3 What the host may NOT assume, and must carry itself

1. **That an absent envelope means an absent route.** *Correction to the record, and it reverses the
   ruling three prior analyses reached:* the dispatcher's fail-closed clause is held for non-GET and
   **deliberately not held for GET** — an unmatched GET returns **200** with a body that names itself
   unmatched, with the rationale in the dispatcher's own docstring, and the sentence the operator saw
   in incident 5 is manufactured CLIENT-side from that 200. So incident 5 involved no 404, no seam
   and no framework. **The obligation is the host's alone**: carry the host's own identity (process
   start time plus a digest of the route table it compiled) on a route that cannot itself be missing,
   and embed it in BOTH failure bodies — the non-GET 404 and the unmatched-GET 200 — so that
   "no such route on this API" becomes "this server started at T from build X; that route is not in
   it". The material is free (the route table is already a list in memory and its length is already
   printed once, to the terminal, to no client ever) and there is no such route today: 0 of 53
   handlers expose build, start time or route set. **This contract states it; it does not build it.**
2. **That a payload served under a different fingerprint is current.** The single-flight branch on
   3 of 3 seam routes returns the last good payload stamped `derived` and carrying the OLD
   fingerprint. Mid-ingestion that is the common path. The wire needs a distinct token for it.
3. **That a field forwarded is a field rendered.** Measured: the host forwards 10 index sub-fields
   over 3 routes and the client reads 6. The field written specifically so that "a count of zero can
   be read as 'not authored' rather than as a measurement" is dropped at the last mile on the route
   whose own comment says so. **A field the client does not render does not count as naming the gap**
   — which is incident 1 reproduced inside the repair for incident 1.

---

## 8. THE GATE, AND HOW TO REGISTER SEAM #4

`tools/check_seam_contract.py <bundle-root> [--json] [--self-test]`. One PASS/FAIL line, exit 0/1,
exit 2 when it could not run, every count with its denominator, and `--self-test` seeding one mutant
per reject class. Add a row to its `SEAMS` table and the seam is judged; a seam with no row is not
checked, and that is the only way to be unchecked.

**The reject classes are the clauses of this document, one for one.** The judge is pure: it takes
the probes and returns findings, so every class is exercised offline against a seeded envelope.

| # | class | the clause it enforces |
|---|---|---|
| 1 | `ENVELOPE_UNVERSIONED` | §3 `envelope` |
| 2 | `RESULT_UNKEYED` | §3 `result` under a fixed key |
| 3 | `MODE_UNDECLARED` | §5.1 |
| 4 | `MODE_CONTRADICTED` | §5.1 — the declaration is re-derived from the payload |
| 5 | `STATUS_UNCLOSED` | §4.1 |
| 6 | `REASON_UNBOUND` | §3 `reason`, the biconditional |
| 7 | `PARTIAL_UNBOUND` | §3 `partial`, the biconditional, and document mode's `[]` |
| 8 | `DENOMINATOR_MISSING` | §3 `counts` — the zero with no denominator |
| 9 | `SHAPE_VARIES` | §3 — reserved keys invariant across every exit |
| 10 | `INPUT_UNDECLARED` | §6.1, **verified against a measured open-trace** |
| 11 | `FRAMEWORK_UNDECLARED` | §6.1 framework plane — the cache hole |
| 12 | `SEAM_UNSTAMPED` | §3 `seam` |
| 13 | `PATH_LEAKED` | §3 `local` — no absolute path anywhere else |
| 14 | `ARGV_SILENT` | §4.3 — exit 2 with an empty stdout |
| 15 | `FLOOR_BROKEN` | §4.4 |
| 16 | `DEGRADE_UNSIGNALLED` | §5.4 — corrupt one declared input; the payload must change |

**The first run, 2026-09-19, against this repository's public example bundle (91 files), the three
registered seams, every traced input corrupted in turn — 54 probes, 10.6 s:**

```
FAIL: check_seam_contract — 31 finding(s) — 0 of 3 seam(s) conform, of 3 registered;
      8 of 39 judged clause-check(s) pass over 16 clause(s) × 3 seam(s) = 48 declared
```

That is the point of writing the check before anything is migrated: **a gate that passed everything
on day one would have measured nothing.** Four clause-checks of 48 could not be judged on this
fixture and are printed as such, never as passes — including the key-set clause on 2 of 3 seams,
because no probe reached those seams' failure exit and comparing success to success proves nothing.

**Why 10 and 16 exist, and why they are the two that matter.** A declaration is only as good as the
author's memory of what the code reads, and the measurement says authors forget: one seam enumerates
6 planes in `absent[]` and parse-checks only 4 of them, so a broken file on 2 of those 6 planes is
reported NOWHERE; and two framework readers swallow a failed parse with a bare `except`, so a
truncated input can cost a whole view class while the payload stays byte-identical to a clean run.
Class 10 measures what the process actually opened with an audit hook and compares it to what the
payload declares. Class 16 corrupts each of those traced inputs in turn, in a COPY of the bundle in a
temporary directory, and fails a seam whose answer does not change. Neither can be satisfied by
remembering harder.

---

## 9. CORRECTIONS TO THE RECORD

Carried here because each was cited wrongly in the analysis that produced this document, and a
contract quoting a wrong count is a contract nobody can check against.

* The host's boundary file is at the host REPOSITORY ROOT, not under the console package, and the
  tree is named `wiki`, not `console` (§2.1).
* The dispatcher does NOT 404 an unmatched GET; it answers 200 with a self-naming body, deliberately
  (§7.3.1).
* There are **6** `_run_framework_tool` call sites, not 7 — the 7th textual hit is the definition.
* The host's eviction helper is called at **2** sites, not 4.
* One seam's docstring lists a third input plane it never opens; its own absence list, and the
  measured trace, both say two.

---

## 10. WHAT THIS CONTRACT DOES NOT DECIDE

Named, not smoothed over. Each needs an operator ruling before the migration step.

1. **The boundary file contradicts itself, and the fallback path sits in the gap.**
   `forbidden_reads` is written in an addressing the same block's own comment declares retired, while
   `reads:` has been rewritten to "the path each configured entry names". As literally written, 2 of
   3 host fallbacks read a forbidden tree, and the fingerprint STATS both planes on every request.
   The rule the code actually follows, written nowhere a gate can see it, is: **the host may read a
   build artifact only as a LABELLED FALLBACK, never as the primary answer.** Adopt that as the
   interim clause, or restate `forbidden_reads` against the configured root. Note that this
   contract's refusing modes route MORE traffic there, not less.
2. **The interpreter floor as a number** (§4.4): 3.9 as registered, or 3.11 with three docstrings
   rewritten.
3. **The host's own `sys.path` mutations.** The console mutates `sys.path` at 2 sites against
   `may_sys_path_mutate: false`, unseen by the boundary gate, which examines 0 of the 12 files in
   that tree because it runs in the other repository. If the shared seam machinery is reached through
   one of those inserts, the repair for five incidents ships resting on an unenforced clause it
   itself quotes. Carve it out and date it, or fix it first.
4. **Snapshot provenance is unknowable.** `seam.code_id` proves which framework answered a DERIVED
   payload. A fallback artifact carries no such stamp and its producing framework is unrecorded, so
   the host must render snapshot provenance as UNKNOWN rather than absent. Writing a stamp into the
   artifact at projection time is the fix, and projection work is suspended.
5. **Contract-version skew across two repositories.** `envelope: "mac.seam/1"` needs a rule for what
   a `/1` host does with a `/2` seam on disk, who may bump it, and whether the host's supported set
   is part of the host identity in §7.3.1. A version field with no skew rule is incident 5 with a
   version number on it.
6. **The denominator can be confidently wrong.** `counts.declared` is only a fact if the spine parses
   STRICTLY. A spine loader that returns an empty list for a document missing its expected top-level
   key publishes "N of M" with a wrong M and a clean status. A partly-readable spine must be
   `unparsed_input`, never a `declared` inferred from the members that happened to parse.
