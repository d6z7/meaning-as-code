# PROPOSED-2026-09-13 — Testing strategy: what is tested, how, and what a green is allowed to mean

**Status: PROPOSED.** Written by an agent; an agent may only write PROPOSED. Ratification — every
ruling in §9, every required key, every floor — is the operator's. Nothing here was built. Analysis
was **offline**: nothing reached AWS, Bedrock or a warehouse.

**REVISION 2, 2026-09-13.** Two adversarial passes attacked revision 1. **One survived and one did
not**, and §12 records every objection, what changed, and the four I rejected with the measurement
that rejects them. The short version: **the diagnosis held almost entirely and the instrument did
not.** The §8 ratchet was movable ~90 % in one day by three commits that add no test, its floors were
the numeric shape this estate ruled defective on the same day, four of six proposed shapes could not
be expressed in the shape language at all, and the number the whole plan was steered by came off the
wrong bundle.

**IF YOU READ ONE THING, READ §1.3 — six rows, about thirty lines of code, two rulings.** It was
§11, an appendix; the measured carrying capacity of this estate (47 initiative folders, 3 done, eight
untouched for 66–71 days) says the first list is the only list, so it is now the second thing in the
document. **§1.1 is the other thing that changed:** the operator's *"always some 40 %"* is **42,7 %**,
it is his own bundle's last committed verdict, it is sixty days old, and **no console view reads the
file it lives in.**

**What this revision did to the document, stated plainly, since it got longer and not shorter.** Cut:
the dashboard from three specified levels to one (§6), the analyst archaeology (§10.2), the withdrawn
46,2 %↔40 % identification (§1.1, §4.1), two authored widgets that failed this document's own new
admission test (§6.1), and the single summed ratchet total that mixed four units. Grown: §5.4 and §8,
because the brief was to *replace* the checks that admit a false green rather than wrap them in prose —
every shape now names the engine that runs it, the comparison it **computes**, and the mutant that
must trip. Added: §12. **The action surface shrank; the specification of the instruments grew, which
is the only direction that answers an adversary.**

**This document merges six independent measurement passes** (prior art · ontology · MAC/SDK ·
GUI/platform · dashboard · strategy) into one plan, then two adversarial ones. Where the prior art
already rules something it is **cited and extended, never restated as new**. Where today's
measurements **falsify** the prior art, §10.1 says so explicitly and names the document to correct.

**Token-floor substitution.** This file lives in the PUBLIC framework repo, whose instance-token floor
is ZERO (`tools/check_mac_public.py` → `PASS: check_mac_public — 0 leak(s) over 588 tracked file(s)
examined`; the denied-token register is `registers/public_tokens.txt`, gitignored, 40 lines, and it
denies the live instance's short name). Instance bundles are therefore written as **`<REF>`** (the
reference bundle in the sources repo — the only bundle with a complete acceptance plane), **`<LIVE>`**
(the working instance), **`<B2>`/`<B3>`** (two further instance bundles), **`<PLATFORM>`** and
**`<CONSOLE_PKG>`** (the platform repo and its console package), **`<WORKBENCH>`** (the initiative
repo) and **`<ESTATE_ROOT>`**; domain relations, question ids, column names, engine product names and
filesystem home paths are elided or generalised. **Revision 2 introduced two token classes the gate
did not catch and removed them before writing: one absolute home path and one engine product name.
That is a second witness for §5.5's finding that the denied-token register has a hole**, and it is
recorded here rather than quietly fixed. Every command below reproduces once those
four placeholders are substituted with the paths the operator holds. **This substitution is a
requirement, not a convenience: §10.1(f) records that one shipped framework module currently carries
instance-domain tokens past a gate that reports zero leaks.**

---

## 1 · THE ANSWER TO "ALWAYS SOME 40% DOES NOT WORK"

### 1.1 The 40 % is real, it is measured, and it is sitting in the bundle the operator clicks

**The first version of this document said the operator's number was `<REF>`'s 46,2 % authored
not-green rate. That identification was unsupported and is WITHDRAWN** (§12, objection W-2): `<REF>`
is a bundle in another repo whose board no console view has ever rendered. Measuring `<LIVE>` — the
bundle the operator actually opens — gives a better answer, and it is his number almost exactly:

```bash
python3 -c "import json; s=json.load(open('<LIVE>/acceptance/runs/latest.json'))['summary']; \
print(s['total'], s['by_overall'], s['b_oracle_green'], s['with_b_divergent'])"
# 82 {'PASSED': 47, 'not-passed': 35} 41 46
#    -> 35/82 = 42,7 % NOT PASSED · 41/82 green on the oracle axis · 46/82 channels disagree
```

`<LIVE>` **has** a testing plane: a grouped corpus of 82 blessed questions, 110 oracles, 92 captured
second-channel answers, **22 committed run records**, and one SME spreadsheet. Its own last run says
**42,7 % not passed.** Two facts about that record are the whole finding:

1. **It is dated 2026-07-15 — sixty days old** on the day this was written.
2. **No console view reads it.** The console's testing pages read `acceptance/questions_dashboard.json`
   (`console_api.py:2565`) and `acceptance/<suite>_runs.json` (`views/PropertySuiteView.jsx:42-48`).
   `<LIVE>` has neither filename. `grep -rn 'acceptance/runs\|acceptance/master' <CONSOLE_PKG>` →
   **no output.**

**So the operator's "always some 40 %" is his own bundle's last committed verdict — true, sixty days
stale, and displayed nowhere.** It is not "unknown rendered as broken". It is a real number that
nothing shows, so nothing shows it moving. The dialect gap of §4.1 is not a tidiness problem: **it is
the reason the operator cannot see his own 42,7 % fall.**

**This re-ranks the work, and it is the single most important edit in this revision.** The route from
"40 %" to "not 40 %" does not start with 379 lines of new grammar or a 184-rule prose conversion. It
starts with the console telling the truth about the bundle in front of it, and with `<LIVE>`'s board
being legible to a host at all. §1.3 is ordered accordingly.

### 1.2 The rest of the estate is not 40 % broken — it is UNKNOWN, and the ladder says how unknown

**A small red column, a minority demonstrated, and a large majority never run — with the reporting
surface collapsing those three states into one, so "unknown" arrives on screen looking like
"broken".** How large the majority is depends on which denominator you declare, and the spread is
itself the finding: over the ladder below roughly **18 %** of declared items are observed; a
companion pass over a narrower capability-shaped population put it at **33 %, or 25 %** once
frozen-engine captures are excluded as proof. Three honest answers to one question, and the estate
publishes **none** of them.

Every one of the fourteen measured defects lived at a **seam** — two artifacts that must agree, with
nothing reading both — and a unit test cannot see a seam, because it holds one side and mocks the
other with a mock that agrees by construction. That is how 131 tests passed while eight things did
not work. The fix is therefore not more tests: it is (a) **print the denominator and separate
never-run from green**, (b) **gate the seams rather than the sides**, and (c) **derive the
enumeration and author the oracle** (§1.4).

**The number that will track it** is not a health percentage. It is a **per-class ladder, never
averaged** — and, per §12 objection F-1, the ratchet target is **not** "observed" but
**DEMONSTRATED-FALSIFIABLE**: an item counts only when a seeded mutant has made its check fail and
the record names the mutant. "Observed" is gameable to an ~90 % improvement in one day by adding
nothing that can fail; falsifiable is not. This is the estate's own gate contract
(`--self-test with a mutant per reject class`) and the plane's instruction 27 (*"A RULE IS COVERED
WHEN SOMETHING COMPOSES IT AND CAN FAIL"*) applied to the ladder itself.

**Today's ladder, measured.** Three columns per class, and **the UNIT is declared on every row** —
because summing a test function, a route, a component and a corpus question into one headline is the
same sin as averaging seven meanings of green (§8):

| # | class | UNIT | declared | observed | **falsifiable** | never run |
|---|---|---|---|---|---|---|
| ① STRUCTURE — gates | gate script | 45 (36 `tools/check_*.py` + 9 `sdk/gate/check_*.py`) | 22 named in the compiler's inventory | **≤ 13** satisfy all three contract clauses; **0** print a mutant count | 23 unobserved |
| ② MUTANT — gate self-tests | reject class | 45 gates × their own classes, **never enumerated** | **0 recorded in any artefact** | **2** — the two in the one shared helper, both of the empty-plane class | undeclared |
| ③ UNIT — in-process | test function | 1 273 (131 here + 1 142 platform) | **0 committed records** | **28** — the gate/harness meta-tests that seed a mutant (§3.1) | 1 273 |
| ④ SEAM — producer ↔ consumer | producer/consumer pair | **undeclared** (478 mechanically enumerable candidates) | 0 | 0 | ? |
| ⑤ PROPERTY — SQL invariants | property | 293 in `<REF>` | 293 run | **≤ 264** — 29 properties carry 59 assertions that cannot fail | 0 |
| ⑥ CORPUS — question → verdict | question | 96 questions (101 oracles · 21 anchors) | 25 run | **0** on the value axis — 0 `sme`, 0 value oracles | 71, of which the cost-gated tier is a **disclosed budget** (§8) |
| ⑦ CONSOLE — **three units, never one number** | see below | 114 lintable files · 20 views · 46 backend routes | **0 tested, 0 linted** | 0 | all |

**Two corrections this revision makes to its own table**, both found while verifying the adversaries:

- **⑤ is 59 assertions over 29 DISTINCT PROPERTIES**, not "59 of 293" — that phrasing compared
  assertions against properties, a units error inside the sentence that states the units law.
  `python3 tools/check_vacuous_assertions.py <REF> --json` → 59 findings over 29 distinct
  `(file, id)` pairs. The **assertion denominator is never printed by anything**, so the honest
  falsifiable ceiling for this class is "≤ 264 of 293 properties", and the gate must print which
  unit it counted.
- **⑦'s old single figure of 153 was 79 + 20 + 54 — three units summed.** And the 54 does not
  reproduce: `_ROUTES` in `console_api.py` holds **46** tuples today (23 GET · 18 POST · 3 DELETE ·
  2 PUT). A ratchet cannot stand on a denominator that neither reproduces nor declares its unit, so
  ⑦ ratchets as **three separate rows**.

> **THIS TABLE IS ALREADY STALE, AND §12.4 SAYS BY HOW MUCH.** Two gates landed on another track
> while this revision was being written — a seam enumerator and an entry-point invoker — so rows ③
> and ④ have moved and row ④ now *has* a denominator. **The ladder must be regenerated by command,
> never transcribed**, which is the whole argument for §8.6 and the reason this document refuses to
> publish a single headline number.

Read the table and the operator's sentence is answered twice over: for `<LIVE>` the red column is
real and invisible (§1.1); for the estate the never-run column is nearly everything, **the
falsifiable column is smaller than the observed column in every single class**, and **class ④ — the
one that produced every measured defect — has no denominator at all.**

### 1.3 THE FIRST WEEK — hoisted out of the appendix, because on the evidence it is the whole plan

**Why this sits here and not at the back.** The estate's carrying capacity is measured:
`<WORKBENCH>/specs` holds **47 initiative folders — 3 done**, 9 at a
human gate, and **eight with no commit since 2026-07-05..07-09** (66–71 days). The estate moves
about five things at once. A 940-line plan's realistic output is its first list and nothing else, so
**the first list has to be the strategy, not the appendix** (§12, objection W-1).

**The ordering rule applied here:** a repair that catches a measured defect outranks an instrument
that measures, and an instrument outranks a grammar. Of the five `catches N live` annotations in this
document, **all five sat in §4.2 and §4.3** — none in the 379 lines of ladder, grammar and dashboard
the old first-week list drew three of its six items from.

| # | do this | size | ruling needed | catches |
|---|---|---|---|---|
| **0** | **Delete `mac-sdk` from `mac-platform/Makefile:16`.** It names a package retired in "retire the SDK fork"; `ls -d packages/mac-sdk` → *No such file or directory*; `.DEFAULT_GOAL := check` and `install` is a prerequisite of every gate target, so **`make install`, `make test` and `make check` all fail today** — which blocks item 4's own wiring clause | one line | none | unblocks every item below |
| **1** | **Make an unmatched GET loud.** `console_api.py:3302-3307` is *already* fail-closed for non-GET ("adversary finding") and still returns `200, {}` for an unmatched GET, while `ui/src/lib/api.js:16` throws only on `!res.ok`. **A renamed endpoint therefore fails by rendering an empty widget with no error anywhere.** Extend the branch that is already there | ~3 lines | none | the mechanism behind **3 of the 14** |
| **2** | **Wrap the 11 unwrapped section branches** in `ViewErrorBoundary`, which already exists and whose own header says *"wrap each section's body"* after recording that the window *"went blank AND stayed blank … indistinguishable from a failed load"*. `grep -c '<ViewErrorBoundary' App.jsx` → **2**, against 13 `section === "…"` branches — under a comment at `App.jsx:1595` asserting *"Each branch carries its own ViewErrorBoundary"*, which is false | ~22 lines of an existing component | none | every future blank window; and the comment is itself a class-F drift defect |
| **3** | **Fix NAV ↔ switch ↔ push** — 2 missing NAV entries and the one `push({section:…})` target with no branch, including the live user-visible defect where clicking a non-concept node on the grounding graph lands the user in Chat. **The fix before the gate that measures it** | hours | **R13** (restore or retire) | 3 live, one user-visible |
| **4** | **Point the console lint at the files that exist**, exclude vendor, wire `npm run lint` into `make check` and CI. `eslint.config.js:11` scopes every block to `**/*.{ts,tsx}`; the tree holds **0** of those and **114** `.js`/`.jsx`. **Floor THREE numbers, not the file count alone** (§12, objection F-11): files linted · active ERROR-severity rule count · per-line suppression count. `--self-test` writes the measured mutant (a `useState` below an early return) into a temp `.jsx` and requires exit ≠ 0 | hours | **R12** (the 187) | the 14th defect's whole class, forever |
| **5** | **Give the two testing-plane checkers the gate contract and list them in the compiler** — one PASS/FAIL line, printed denominator, **exit 2 on zero subjects AND on a missing analysis dependency in the same commit**, a mutant per reject class. Today `check_vacuous_assertions.py:233` returns **PASS when sqlglot is absent**, and pointed at a zero-subject bundle it prints a tick and exits 0 | days | **R14(a) FIRST** — exit 2 must be ruled blocking before this lands, or the repair converts fails into invisibles | 59 uncheckable assertions + a rule-coverage red, from invisible to blocking |

**Week two, and not before:** `check_console_routes` as a gate (item 3 is the fix; the gate protects
it), the seam register (§9-R5), the gate-contract meta-gate that **executes rather than greps**
(§8), `question_id` on every anchor (§11), the gate-contract skill body (§11). **The ladder is last**
(§8), because its job is to print denominators and four of its rows have no data source until the
above exists.

### 1.4 The 18× is a SENSITIVITY measurement, not a budget argument — and this is a correction

The original document read `<REF>`'s authored-vs-derived split (**46,2 % vs 2,5 % not green, 18×**)
as a reason to *"prefer derived tests wherever a derivation exists"*. **An adversary showed that
reading inverts the estate's own doctrine, and it is corrected here** (§12, objection F-14). The
framework's own vocabulary states the mechanism in as many words:

> *"a test rendered entirely from the ontology AGREES WITH THE ONTOLOGY, so a wrong declaration
> produces a green suite."* — `mac_vocabulary.yaml`, `test_kind` preamble

**A test rendered from the artifact it tests cannot disagree with that artifact.** 241 of 293 derived
at 2,5 % not-green is what a population that *cannot disagree* looks like. And the plane's own
worked example proves it from the other end: `S-GRAIN-KPI` — **an AUTHORED property**, i.e. in the
46,2 % half — caught a descriptor claiming `VERIFIED … 0 multi-row` against a warehouse that had
reached 11.689.530, and `testing.md:128` says flatly that *"a conformance test rendered from that
same declaration would have confirmed the stale claim."*

**The boundary, stated as a rule an agent can apply:**

> **DERIVE THE ENUMERATION. AUTHOR THE ORACLE.** Derivation is legitimate for populating *subjects* —
> which concepts, which columns, which profiled facts get a test. It is illegitimate for supplying
> the *expected value on the axis under test*, because there the test inherits the claim it exists to
> challenge.

So the 18× is retained as a **steering signal for `<REF>`'s own red column** and as evidence that the
authored half is where the sensitivity lives. It is **not** a spend instruction. **Report authored and
derived not-green rates separately, and treat a FALLING AUTHORED SHARE as a regression on its own
line** — otherwise the cheapest way to improve the number is to generate more tests that cannot fail,
and this document's steering signal becomes a dilution instruction.

---
## 2 · THE FOURTEEN, AND THE FOURTEEN MORE FOUND WHILE MEASURING

### 2.1 How each of the fourteen was found

| channel | count | what it tells us |
|---|---|---|
| the **operator**, clicking through the console | **8** | the only instrument currently pointed at the console at all |
| **gates** | **3** | including three gates catching their *own* bugs — the mutant discipline working |
| **verifier agents** reviewing other agents' work | **3** | cold review over real artifacts, with a denominator |
| the **131 unit tests** | **0** | — |

*(Attribution taken from the brief, not independently re-derived. Counts verified: 131 pytest
functions, all under `sdk/` — `grep -rhoE '^\s*(async )?def test_[a-z_]+' $(find sdk -name 'test_*.py') | wc -l` → 131.)*

**All fourteen were at a seam.** The five named shapes: a producer writing `<field>_used` while the
consumer read `<field>`; a grammar declaring one credential-mode term while the connector declared
another; a config handle and a code default that were **the same fact**, each independently removed as
dead; two libraries verifying TLS against two different trust stores; a React hook below an early
return. Two of those are *name* disagreements, one is a *default* disagreement, one an *environment*
disagreement, one a *control-flow* invariant — different surfaces, one class.

**Why the 131 could not see them, stated mechanically:** a unit test is authored **from the same
document as the code it tests**, so it inherits that code's misunderstanding, and it mocks the far
side of every seam with a mock the test author wrote. The proof is in the estate's own history: one
commit added 22 passing grammar tests **in the same commit** as a connector declaring a different
vocabulary for the same fact, and the repair commit four commits later says it in its own message —
*"Two agents wrote the two halves in parallel and neither read the other."* And the design that makes
the unit tests clean is stated in the estate's own docstring: *"flags.py stays pure and is handed the
already-resolved anchor. That separation is what lets the evaluator be unit-tested from synthetic
dicts"* — which is good engineering and is **structurally incapable** of noticing that 0 of 21 real
anchors carry the key the resolver ranks highest.

### 2.2 The second measurement, and it is the argument for this whole plan

**Six agents reading for one day, with no browser, no warehouse and no new test framework, found
fourteen MORE defects.** Not projections — each reproduced by a command:

1. **The skill that teaches the gate contract has no gate-contract body.** `platform/skills/gates-and-checks/SKILL.md` frontmatter says `name: gates-and-checks`; its H1 reads `# 2 · SCOPE AND ACCEPTANCE — define "done" before building`; and `diff <(tail -n +5 gates-and-checks/SKILL.md) <(tail -n +5 scope-and-acceptance/SKILL.md)` is **empty**. The estate's most load-bearing law is missing from the only artifact an agent would load to learn it. *A frontmatter/body seam, inside the artifact that teaches seam discipline.*
2. **The console lint examines zero components.** `ui/eslint.config.js:11` scopes every block, `react-hooks` included, to `files: ['**/*.{ts,tsx}']`; the tree holds **0** `.ts`/`.tsx` and **79 `.jsx` + 35 `.js`**. `npm run lint` exits 0 having applied zero rules to zero components. Fed the *exact shape* of defect #1 (a `useState` below an early return), eslint ignores it as `.jsx` and reports `react-hooks/rules-of-hooks … Did you accidentally call a React Hook after an early return?` as `.tsx`. **The instrument that catches the fourteenth defect is installed, configured, and aimed at an empty set.**
3. **Three console sections are unreachable.** `App.jsx:851` derives the selectable set from the NAV table; `:934` falls back to chat. NAV holds **21** keys; the render switch holds **13** `section === "…"` branches; two branches (`benchmark`, `guardrails`) have no NAV key and one `push({section:…})` target (`objects`) has no branch. ~104 KB of view code, including the entire benchmark surface, plus a **live user-visible defect**: in the grounding graph, clicking any non-concept node pushes `objects` and lands the user in Chat, directly under a comment saying every node on the map must be reachable.
4. **A gate raises on its own success path.** `check_sql.py:246` in the frozen workbench repo prints an f-string containing `{sources,datasets}`, which an f-string evaluates as names → `NameError`. Line 240 has the identical text and is *not* an f-string, which is how it survived review.
5. **The verifier written today has a false-positive class.** The AST scope checker lifted verbatim over 564 modules / 119 404 loaded names returns 6 findings; **4 are one bug in the scanner** (a walrus in a comprehension's `if`, read in the `elt`, is never harvested into the comprehension scope), latent only because the one file it was written for contains no such construct.
6. **`mac.test_kind` is declared closed and typed open.** `mac_vocabulary.yaml:175-196` says `closed: true` with two terms; `mac.schema.json` types it `{"type": "string"}`. Probed: a bogus value **validates clean**. `severity` in the same file *is* a proper enum and correctly rejects a bogus value — the schema knows how, and did not for the one vocabulary the whole ground-truth/conformance split rests on.
7. **The property runner implements seven assertion kinds; the grammar closes four.** Probed: three of the runner's kinds are REJECTED by the schema and IMPLEMENTED by the runner. An author following the runner writes a property that runs green and fails structural validation.
8. **Anchor independence is asserted, not computed.** `derivation.agree` is an authored boolean: one anchor cross-checks 2 of its 4 derived keys and says `true`; one compares a 12-month dict against a scalar and says `true`; one has the string `no_evidence` against a null and says `true`. And the grader reads `anchor.expected.value`, never `derivation.raw_value` — they differ on **5 of 21**. *The graded number is a typed literal, in the plane's only proof of value.*
9. **Three shipped example bundles advertise a corpus file none of them has.** Each registers a corpus object pointing at `acceptance/questions.yaml`; `test -f` fails on all three; each ships a byte-identical all-zeros dashboard. **Zero-of-everything renders identically to clean.**
10. **`CONFORMANCE.md` §5.4 contradicts the schema it governs** (§10.1(a)).
11. **The platform gate runner cannot pass.** `Makefile:16 PACKAGES` names a package removed in a commit titled "retire the SDK fork"; `ls -d packages/mac-sdk` → *No such file or directory*; so `make install`, `make test` and `make check` all fail. Also CI runs 6 of 8 targets under a comment claiming it *"Mirrors `make check` exactly"* — the two it omits are the model-authored-SQL invariant gate and the target that runs every gate's own self-test.
12. **8,6 % of generated links are dead.** 122 of 1 426 static local `href`/`src` targets in generated HTML do not exist on disk — including a dead link on the dashboard's own landing page.
13. **The corpus grader dies at setup**, so the board a completed epic delivered cannot be built: the grader raises `FileNotFoundError: no oracle file for <qid>` before writing any results, and the board's output HTML does not exist on disk. Producer permits oracle-less questions (documented, `proposed: true`); consumer hard-requires one per question. *A seam.*
14. **The host-contract version disagrees with its own docstring.** `sdk/project/questions.py:73` sets `SCHEMA = "mac.questions_dashboard/4"`; the module docstring at `:6` still says `mac.questions_dashboard/3`. The same module's comment states the stake: *"a server-only change that the browser silently papers over is the worst failure mode available, because it looks exactly like nothing happened."*

**Conclusion that should govern the budget.** The cheap, offline, denominator-printing instruments are
**nowhere near exhausted**. Fourteen more defects, in one day, with grep and a parser. Nothing in §4's
build order requires a browser or a warehouse before the first four items are done.

---

## 3 · THE DEFECT TAXONOMY, AND THE CHEAPEST INSTRUMENT PER KIND

Seven classes. Each is measured here today; each has one cheapest instrument; each names what is
**not** worth catching automatically, because a strategy that tests everything is one nobody follows.

| class | measured today | cheapest instrument | deliberately NOT caught |
|---|---|---|---|
| **A · SEAM MISMATCH** — producer writes X, consumer reads Y | 14 of 14 defects; 478 enumerable candidates; 0 gated | A **seam manifest** plus one gate that reads **both sides** and asserts the key sets agree. ~40 lines per seam | Nothing. This is the class to spend on. **A unit test does not discharge it** — the mock agrees by construction |
| **B · WRONG READING** — correct engine, valid query, plausible number | 7 of 96 questions proven; `value` = `na` on 15 of 25 graded rows; 0 `sme` oracles | An **independently derived anchor**: derivation SQL against raw, the same logic re-run against the served view, `agree` **computed**, `question_id` declared. ~1 SME-hour each | The prose never-clauses (74 of 83). Report `unchecked` with the clause **verbatim**; a structural guess manufactures a false green on the one axis that must stay honest |
| **C · VACUOUS GREEN** — passed having examined nothing | **59 assertions over 29 of 293 properties** cannot fail (corrected in this revision — §12.2 item 1); a zero-subject bundle gets a tick and exit 0; 9 of 67 panel cases skipped and counted as not-failed | A **printed denominator** + `declared/examined/skipped` + a mutant per reject class + **exit 2 for could-not-run** | Nothing. This is the estate's named dominant defect and the cheapest to close |
| **D · ARTIFACT NEVER PARSED** — emitted and never read back | 122 of 1 426 links dead; 0 of 201 HTML files have failing inline JS (this half was fixed once and **held**) | The producing command **parses its own output before exit**: `node --check` emitted JS, `exists()` every emitted local href, load every emitted YAML/JSON. ~30 lines | Pixel and screenshot comparison — most expensive, most brittle, and would have caught **none** of the 122 |
| **E · INVOCATION CONTRACT** (renamed — §12, objection W-6: the class was named after the one *environment* defect among the fourteen, and neither instrument would catch a process whose two TLS clients trust different stores. That defect is now §7's eleventh refusal; the class keeps its real, measured content) | 7 of 10 `sdk/gate` gates exit 1 with `ModuleNotFoundError` when invoked the way the runner invokes them — **and exit 1 IS FAIL**, so a crash is read as a verdict; 4 framework tools treat `--help` as a path | `--help` must exit 0 on every registered entry point; every gate invoked exactly as its runner invokes it | Every flag combination. The contract is *"it can be asked what it does"*, not CLI coverage |
| **F · DOCTRINE DRIFT** — the law disagrees with itself | 1 of 15 skills has a body that is another skill's; `CONFORMANCE.md` §5.4 vs the schema; a "No skills" claim in a blueprint that is now false; a waiver reason that is factually false | Assert **declared identity == content**: frontmatter `name` ↔ H1; a schema `$def` ↔ a changelog entry naming it; no two skill bodies identical. ~15 lines | Prose quality, tone, completeness. A machine can only check that it is *the* doctrine |
| **G · BLAST RADIUS** — a test destroying what it tests | one recorded incident: a renderer test staged into and `rmtree`'d the real served output directory, blanking the live board; operator-reported | every test and generator writes to a temp dir and moves on success; a path-allowlist gate forbidding any writer targeting a served path. ~25 lines | Nothing. One incident cost the live board |

### 3.1 The one anti-instrument, and it should be a review bounce

> **A unit test that exercises one side of a seam with a mock on the other is NEGATIVE value in this
> estate.** It is not merely insufficient. It produces green that is *causally* why eight defects
> shipped, and it consumes the budget the both-sides gate needs. Under §9-R6 this becomes a bounce at
> review, not a preference.

This does **not** condemn unit tests as a form. The 131 split cleanly by what they hold: 28 gate/harness
meta-tests seed a mutant and assert the gate trips — **both halves, and these are the ones that
worked**; ~20 exercise pure functions where no seam exists; 20 run against real fixtures. The
condemned shape is the remaining ~17 across 5 files that write the far side themselves. One of them
synthesises a module whose function signature is **typed into the test**, while the real module lives
in another repo.

### 3.2 Where A and B are the same event

A *meaning* defect and a *seam* defect are one event seen from two ends: **a wrong reading survives
because the declaration that would contradict it is read by nothing.** A field-name divergence is a
seam; *the answer being wrong* is the meaning. One instrument closes both — make the two sides be read
by one check — which is why §4 puts the seam register before the value anchors even though the value
axis is the larger gap.

---

## 4 · THE THREE DOMAINS

### 4.1 ONTOLOGY — the doctrine is sound; the grammar underneath it is nearly absent

**What exists, measured.** The reference bundle `<REF>` carries a complete acceptance plane: 7 suites,
**293** properties (`test_kind` stamped on **293 of 293** — 245 `ground_truth`, 48 `conformance`), 10
`not_expressible` entries honestly declaring tests decided against, **96** questions, **101** oracles,
**21** anchors, 25 captured answers, a rule-coverage projection, an append-only trend and a derived
card projector. Three generators produce **241 of the 293**. Committed state:
`PASS 263 · FAIL 17 · FROZEN 11 · ACCEPTED 1 · ERROR 1`, every declared property carrying a run record.

**THE measurement nobody had quoted.** Split those 293 by CORE §7's own distinction, from the suites'
own run records (command in §8):

|  | total | PASS | not green |
|---|---|---|---|
| **AUTHORED** (`property`, `retrieval`, `data_sanity`, `ontology`) | 52 | 28 | **24 = 46,2 %** |
| **DERIVED** (`*_generated`) | 241 | 235 | 6 = **2,5 %** |

`FAIL 12 · FROZEN 11 · ACCEPTED 1` authored; `FAIL 5 · ERROR 1` derived.

> **CORRECTED IN THIS REVISION.** The first draft read this split two ways that both had to go
> (§12, objections W-2 and F-14). It said *"that 46,2 % is the operator's always some 40 %"* — an
> identification with no evidence behind it, now **withdrawn**: the operator's number is `<LIVE>`'s
> own last verdict, **42,7 % not passed**, and §1.1 measures it. And it read the 18× as a *budget
> argument* for spending on derived tests — which **inverts the framework's own doctrine**, because a
> test rendered from the artifact it tests cannot disagree with it. §1.4 states the replacement rule:
> **derive the enumeration, author the oracle.** The split stays as `<REF>`'s own steering signal and
> as evidence that **the authored half is where the sensitivity lives**, which is an argument for
> authoring *better* oracles, never fewer.

**What is missing — and each stop is a design gap, not a resourcing gap.**

- **The `sme` authority tier was never designed, only named.** `derived` has three generators, a
  runner, a run record, a trend, a projector and a dashboard. `sme` has **a string in a YAML field**:
  `grep -h '^authority:' <REF>/acceptance/oracle/*.yaml | sort | uniq -c` → **101 derived, 0 sme, 0
  baseline**. The estate's only SME artifact is a 170 KB binary spreadsheet from 2026-07-07 that no
  gate can read and that **did not carry forward** to the newer bundle. Meanwhile the framework has
  already built the missing home without telling the plane: `mac.schema.json` `$defs.SmeLedgerFile`
  exists, is in the root `oneOf`, is routed by `tools/validate_schema.py:67`, and is described as
  *"THE DOUBT CHANNEL"*. Nothing in the plane, in 0008 or in CONFORMANCE.md mentions it.
- **Zero value oracles, stopped on a missing key.** All 96 hand-authored oracles carry `value: null`;
  value proof lives in a separate `anchors/` plane whose files carry **no `question_id`** (0 of 21), so
  the anchor→question link is **inferred by scanning English** for `variant` / `instead of` /
  `different`. Instruction 16 of the plane already rules the fix and quotes the reason:
  *"inference on the one axis that is supposed to be honest is where a false green does the most
  damage."* Written, never adopted.
- **71 of 96 questions never run** is the one genuine *resourcing* stop, and it is **already a ruled
  budget**: 0008 §6 costs the top tier at ~6 h 40 min and ~144 $ per pass — *"not a feedback loop, a
  monthly event"* — and the standing law is that nothing may reach AWS or Bedrock in analysis. **Do not
  propose closing it.** Propose what the policy itself points at: *"the tiering is affordable exactly
  to the degree the corpus avoids needing values."*
- **The plane is not gated.** `grep -n "vacuous\|rule_coverage" tools/mac_compile.py` → **no output**:
  neither of the plane's two checkers is in the compiler's native register or its legacy table. The
  compiler's own comment beside that table already ruled on exactly this for eight other gates —
  *"a gate that exists and is not listed is worse than a wrapped one, because the report's silence
  reads as coverage."* Run offline today, those two checkers say:
  `✗ 59 assertion(s) over 293 properties cannot fail for the reason stated` (exit **1**) — **and that
  line is itself a units defect the gate-contract repair must fix: it counts 59 ASSERTIONS and prints
  293 PROPERTIES as their denominator, when the 59 sit on 29 properties and the assertion denominator
  is computed by nothing** (§12.2 item 1) — and
  `rule_coverage` exit **1** — **behind a green compile.** Neither prints a `PASS:`/`FAIL:` line (0
  occurrences in either file), `check_vacuous_assertions.py` has **no `--self-test`**, and pointed at a
  zero-subject example bundle it prints `✓ OK — every assertion over 0 properties depends on the
  warehouse` and exits **0**.
- **THE number, estate-wide: 194 ontology rules, 10 covered, ceiling 8** — and all eight in the one
  bundle the framework does not ship. `composed` (a property that renders the rule's own fragment at
  run time and can therefore fail when the rule changes) is **0 of 298**. One instance bundle carries
  **76 rules and a ceiling of zero**. **184 of 194 rules state their directive in prose, so they are
  ungeneratable by construction and no amount of test-writing moves the number.** Converting prose
  rules to machine-readable directives is the *gating* work; everything else is finishing work.
  Instruction 27 already says it: *"A RULE IS COVERED WHEN SOMETHING COMPOSES IT AND CAN FAIL."*
- **Three incompatible dialects across eight bundles — and this is now known to be the reason the
  operator cannot see his own red column (§1.1).** `<REF>` has flat `questions.yaml` + `anchors/` +
  seven SQL suites + `*_runs.json`; `<LIVE>`, `<B2>` and `<B3>` have a grouped `master.yaml` +
  captured-answer directories + `runs/` + a spreadsheet, and **zero anchors, zero properties**; the
  shipped examples have an all-zeros stub. `<REF>` and `<LIVE>` model the **same source** and share
  **not one filename** — and the console reads only `<REF>`'s filenames, which is why `<LIVE>`'s
  42,7 % is invisible. No host can render all three; no agent can be told what to produce. **That is
  the operator's "an agent precisely needs to know what tests are required", answered with evidence —
  and §9-R3 is therefore not a tidiness ruling, it is what makes the operator's own number
  displayable.**

**Build order for this domain.** **(0) Rule §9-R3 (the dialect)** — until it lands, the bundle the
operator clicks cannot be rendered by any host, and every item below improves a board he cannot see.
**(1)** Close `mac.test_kind`'s value and unify the assertion vocabulary (hours; §5.3) — but note
§5.3.1: closing the enum makes the *value* valid, not the *classification* true, so it ships with the
mirror shape of §5.4. **(2)** Give the two plane checkers the full gate contract and wire them into
the compiler — **after §9-R0** (days). **(3)** `question_id` on every anchor, heuristic retained as a
second opinion (days; §11.4). **(4)** Compute `agree` — the computed kind of §5.4, not a required key
(days). **(5)** The `$defs`, each passing the admission test (§5.2). **(6)** Rule conversion — the
long pole, the only work that raises the ceiling, and **the item this revision explicitly declines to
put in front of §1.3** (§12, objection W-2).

### 4.2 MAC / SDK — the tests address a surface users do not

**What exists.** 131 pytest functions, all under `sdk/`. **45 gates** — 36 `tools/check_*.py` + 9
`sdk/gate/check_*.py` — of which **31 carry `--self-test`** (22 of the 36, 9 of the 9). That mutant
discipline is the one instrument the brief measured as *working*. Two correctly-shaped seam tests
exist, both written yesterday, each pointed at **one file**: a closed-vocabulary pin across two
declarations, and an AST scope + required-keyword check that carries its own denominator and mutants.

**What is missing.**

- **Nothing executes an entry point.** 0 of 30 `sdk/` modules carrying a `main()` are invoked by any
  test; **21 of 30 are imported by no test at all** (AST-resolved). The single mention of `main()` in
  the suite asserts the *string* `"supplies no main()"`. An import smoke does not close this: 30 of 30
  import clean and it would have caught **0 of 14**.
- **The user-reachable surface is 284 invocations** — 99 entry points estate-wide and 185 declared
  flags — and the tested fraction is 0. **478 seams are mechanically enumerable today** (339
  cross-module dict-key, 35 closed-vocabulary pairs, 104 definition × call-site keyword pairs) and the
  tested fraction is 0.
- **No coverage instrumentation at all.** `coverage.py` is not installed, there is no `.coveragerc`, no
  `pytest-cov`, no `--cov`. The **"coverage 100 %"** quoted on four wiki pages is another repo's
  Makefile measuring **two modules of 41**, printed beside "260 passed" so it reads as the suite's
  coverage. That is the estate's own law — never quote a PASS without its denominator — broken in the
  estate's own wiki.
- **The gate contract is not itself gated.** Measured in this repo just now: of the 45 gates, **20**
  print a `PASS:`/`FAIL:` token, **31** carry `--self-test`, **25** have an exit-2 path, and **13
  satisfy all three**. Estate-wide across five repos a companion pass counted 106 gate-shaped scripts
  with **24** conforming, and found two *dialects inside one repo* — 11 gates with a PASS line and a
  self-test but no exit 2, 7 with a self-test and exit 2 but no PASS line. Each half missing exactly
  one clause, in opposite directions, with nothing checking. (Population difference disclosed in
  §10.2(c).)
- **`sdk/gate/` is in no runner**, and 7 of its 10 gates exit 1 with `ModuleNotFoundError` when invoked
  the way the estate's runner invokes gates. **Exit 1 is FAIL**: a crash is being read as a verdict.
  One gate also sits permanently red **at its declared floor** (`0 cleared, 0 added`) — a gate that can
  never be green trains a reader to ignore red, which is one mechanism behind the felt 40 %.

**Build order.** (1) Gate-invocation smoke, clearing `PYTHONPATH` and asserting its own gate count
against `ls` (days; catches 7 live). (2) Generalise the AST scope check — **fix its walrus
false-positive class first**, else it ships at 67 % false positives (hours; catches 2 live). (3) The
closed-vocabulary seam gate (days). (4) The orphan-read gate: 89 orphan reads over 784 keys, after
crediting the grammar and corpus as producers (days; catches 1 live). (5) Entry-point execution smoke
against a committed fixture, with AWS-touching entry points excluded **by name** and the exclusion
count printed (weeks). (6) Coverage measured once and reported as a fraction with its module
denominator — **never as a gate**, because both sides of a name divergence were fully covered and
disagreed.

### 4.3 GUI / PLATFORM — 35 000 lines, zero tests, and a lint pointed at nothing

**Measured.** The console frontend is **110 files / 35 123 lines** (`.js`/`.jsx`, vendor excluded), **0
test files, 0 test runner, 0 `test` script, no playwright/vitest/jest anywhere**. The Python side of the
same repo has **1 142** test functions; the console package itself has **0**, and its API module is
3 894 lines. **`mac-console` is the least-tested component in the estate by every available measure, and
it is the surface where 8 of 14 defects were found.**

**The two findings that outrank any layout question.**

1. **The API seam is unchecked and has a false-green generator built into it.** 54 backend routes
   against 63 distinct frontend call sites: **24 frontend calls address no backend route**; 19 routes
   have no caller. And the dispatcher's unmatched-GET branch returns **HTTP 200 with an empty body**
   (the comment defends it honestly: *"a GET still degrades to `{}` so a benign auxiliary read never
   crashes a view"*), while the frontend helper throws only on `!res.ok`. **So a removed or renamed
   endpoint currently fails by rendering an empty widget with no error anywhere** — mechanically three
   of today's fourteen: a flag that did not light, a result rendered in the wrong place, a view that
   renders nothing.
2. **The check that would have caught the fourteenth defect is installed and examines nothing** (§2.2
   item 2). Aimed correctly at `**/*.{js,jsx}` it surfaces **187 errors and 16 warnings over 114
   files**, two of them correctness-grade rather than style (*"Cannot access refs during render"*;
   *"`pump` is accessed before it is declared"*). **This is the cheapest single intervention in the
   entire analysis: one line.**

**And a boundary that was never finished.** The error boundary's own header records why it exists — a
render throw unmounted the whole tree, so the window went blank **and stayed blank**, indistinguishable
from a failed load. Its instruction is *"wrap each section's body"*. It wraps **2 of 13** branches. The
11 unwrapped include the largest views.

**Does a component test catch a hook-order violation? No — and that changes the proposal.** A hook-order
violation does not throw on first render: the early-return path calls zero hooks and renders fine. React
raises only on a **subsequent render of the same instance with different props**. So a mount-once smoke
**misses it**; a component test catches it **only if the author thought to re-render**, which is exactly
the foresight testing is supposed to replace; and **eslint catches it statically with no render, no
fixture and no runner**. *Do not buy a component-test framework to catch a defect a lint glob already
catches.* Buy a runner, if at all, for the classes lint cannot see.

**Where the line between worth-it and theatre falls, as a rule an agent can apply:**

> **Assert that a view MOUNTED, not what it says.** If a test would have to change when a designer
> changes a label, it is theatre. If it can only fail when a user would see something broken, buy it.

A browser test asserting content re-encodes design decisions in a second place, so every deliberate
change breaks tests that found nothing — and a habitually-red GUI suite teaches people that red means
nothing, which is **worse than no suite**. Today's *"a button whose placement was wrong"* is in that
class: a human clicking is the correct and cheapest instrument for "does this look right", and it stays
the operator's job.

**The kit's own GUI doctrine is orphaned and describes a different application.**
`grep -rn 'webapp-testing' platform` returns **nothing outside that skill's own directory** — no seat,
no command, no method step cites it; the frontend and QA seats both list other skills. And it rules
coverage for a declarative chart spec and a four-section answer shape that **do not exist**
(`grep -ic vega package.json` → 0; the console uses a different chart stack across 21 sections). That is
the platform blueprint's own *"the seats are inherited, not validated"*, still live, in the two seats
that own this dimension — while the blueprint line that would flag it (*"No skills. … This track has
none"*, `BLUEPRINT.md:75`) is itself **false**: there are 15.

**Build order.** **(0) Delete `mac-sdk` from `mac-platform/Makefile:16`** — it names a retired package, so `make install`/`make test`/`make check` all fail today and item 1 cannot complete until this does (§12, objection W-4). One line. **(1)** Fix the eslint glob, exclude vendor, wire `npm run lint` into `make check` and CI
with its **file count printed and a floor asserted** (hours). (2) `check_console_routes` — NAV ↔ render
switch ↔ push targets ↔ error-boundary coverage, one AST walk over one file (hours; catches 3 live). (3)
`check_api_seam` — both tables, with an allowlist **only** if §9-R8 rules the local API a declared
subset (days; catches 24 live). (4) Make an unmatched route **loud** and give every view an empty state
that distinguishes *no such endpoint* from *no rows* (days). (5) Repair the platform gate runner before
adding gates to it — the removed package, the two disagreeing test-path denominators, the two missing CI
targets (hours). (6) A **mount-only** headless smoke over the reachable sections against the pinned
offline fixture, printing `N/N sections mounted` (days). (7) Rewrite the GUI-testing skill against the
application that exists and add a kit gate asserting **every skill is cited by at least one seat,
command or method step** (hours).

---

## 5 · WHAT MOVES INTO THE MAC STANDARD

The purpose is the operator's sentence: *"an agent precisely needs to know what tests are required and
how to provide them so that the GUI can show them."* That is a **grammar** problem, not a doctrine
problem. Today the standard defines **one** `$def` for the whole testing plane (`PropertiesFile`, the
SQL half only) and **one** vocabulary entry (`mac.test_kind`, declared closed and typed as a free
string). `ProjectFile.acceptance` is `{"type": "object"}` with a one-line description and **no keys** —
and it is the only place a host can learn what a bundle's testing plane contains. The estate's sole
machine-readable claim that a bundle is tested is a free-form boolean whose meaning is a YAML comment
saying *a file exists* — and that file is then declared **out of scope**.

### 5.1 The four closed vocabularies to EXTEND, never to replace

Already ruled, already load-bearing; cited so no sibling is invented:

1. **`authority`** — `sme` · `derived` · `baseline`, **never aggregated**. 0008 §2(a):
   *"A suite that is 90 % green on `baseline` oracles is 0 % proven."*
2. **`mac.test_kind`** — `ground_truth` · `conformance`, `closed: true`. *"The two kinds have OPPOSITE
   rules about where their numbers come from, and a property that tries to be both can be trusted for
   neither."*
3. **The four flags** — `outcome` · `pins` · `value` · `rules`, five states, eight verdicts, with the
   roll-up order fixed at `sdk/acceptance/flags.py:1031` (`_rollup`; docstring at `:219`) and the
   invariant *a question whose `value` flag is `na` can NEVER be `proven`*.
4. **`accepted:` vs `frozen:`** — *"ACCEPTED … a defect we have consciously accepted and protocolled.
   FROZEN — a red nobody has judged… It must NOT be ACCEPTED."*

### 5.2 Seven `$defs` to add — each subject to THE ADMISSION TEST

> **THE ADMISSION TEST, and it governs every new artifact and every new key in this document.**
> *Name the gate that exits 2 when this artifact is absent or stale, in the same paragraph that
> proposes it — or do not create it.*

This test exists because the estate has measured what happens to an authored channel with no gate
behind it, three times over (§12, objection W-3): `authority: sme` is **0 of 101** oracles;
`question_id` is **0 of 21** anchors; `QUALITY.md` declares itself *"maintained and append-only"* and
has **one commit, 2026-06-29, with 183 commits since**. The counter-example proves the shape:
`accepted:` / `frozen:` **is** adopted — 26 blocks across `<REF>`'s authored suites, with `dq_id`s
resolving into a real register — *because `run_properties.py` refuses to move a red without one.*
**The human input is adopted when it is the only way past a red, and ignored when it is a field a gate
never reads.**

| `$def` | governs | required keys that change behaviour | **the gate that exits 2 without it** |
|---|---|---|---|
| **`AcceptanceManifest`** | the `acceptance:` block in `mac.project.yaml` (today `{"type": "object"}` with no keys) | `suites[]` (`id`, `file`, `runs`, `test_kind`, `tier`, `engine_required`); `corpus` (`file`, `dashboard`) **or** `corpus: none` **from a closed vocabulary** (below); `coverage`. **This is the host contract** — the only thing that lets a GUI render a bundle it does not know | `check_test_ladder` (§8): a bundle with no manifest enumerates no population, and **a class whose declared population enumerates as zero is exit 2**, never a green zero |
| **`QuestionCorpusFile`** | the corpus | `id` **pattern-constrained** (an id is a filename; containment is already enforced in code after a path-traversal id arrived in a spreadsheet), `question`, `regression` | `validate_schema.py` — already routes `/acceptance/*.yaml`; the `$def` turns 148 silent out-of-scope files into named ones (§5.6) |
| **`OracleFile`** | one oracle per question | `kind`, `authority`, `authority_note`, `expected{…}`, **`exercises[]` typed as an array of rule ids, never prose**, `rationale`, `value`, `stable` | `check_rule_coverage` — **and only after the fix in §5.4, without which typing this key makes coverage worse, not better** |
| **`AnchorFile`** | one value anchor | `question_id` (**WARN-with-printed-count first, not required in the generation it is invented** — §9-R4), `derivation{sql, raw_value, cross_check_sql, cross_check_value, agree}`, `expected{shape, value, tolerance, pinned}`, `assumptions`, `captured_at` | `check_shapes` via the four computed anchor kinds in §5.4, each with its own mutant fixture |
| **`AnswerCaptureFile`** | one captured answer | `ontology_fingerprint`, `engine{}`, **`route` typed as a disposition enum, not a channel**, **`sql_probe[]` separate from `sql_final`** | the corpus grader's setup, which today dies with `FileNotFoundError` before writing any result (§2.2 item 13) |
| **`SuiteRunFile`** | `<suite>_runs.json` | `run_at`, `source_watermark`, `engine`, `declared` / `examined` / `skipped`, `results[]` with a closed status enum | **a checker that RECOMPUTES `examined` from the record's own evidence and FAILS when the header disagrees** — see the box below |
| **`TestCoverageFile`** | the coverage projection | `rules`, `covered`, `composed`, `derived`, `corpus`, `named_only`, **`machine_readable` (the ceiling, REQUIRED)**, `detail[]` | `check_rule_coverage`, reporting a fraction with its ceiling — **not a gate that goes green when the fraction closes** (§5.4) |

> **`declared` / `examined` / `skipped` MUST BE RECOMPUTED, NEVER ACCEPTED.** The original document
> called this pair *"the single field that ends the PASS-on-zero class in this plane"* — while
> specifying three producer-authored integers that nobody recomputes. That is the authored-boolean
> defect this document correctly kills for `derivation.agree`, reintroduced at the top of every run
> record (§12, objection F-6). A runner writing `examined = declared` regardless of what it looked at
> satisfies the `$def`, the W2 column and the ladder simultaneously.
>
> **The repair, and it is feasible from the record alone:** `testing.md:206` shows `results[]`
> carrying `rows[]` and an engine block of `{query_execution_id, millis, bytes_scanned}`. A checker counts
> results with a non-null row grid or non-zero `bytes_scanned` and **fails on disagreement with the
> header**. Same rule as `agree`: *compute it, never accept it.*
>
> **And the `$def` must say WHICH POPULATION `examined` counts — subjects, not rules.** Both are in
> live use here and they fail differently: `sdk/gate/test_bundle_secrets.py:28` and
> `test_host_coupling.py:52` pass `examined=len(_DEFAULT_DENY)` — defensibly, with the reason in a
> comment — but **a rule-set denominator is non-zero over an empty subject tree, which is the
> zero-denominator pass wearing the anti-zero-denominator helper.**

> **`corpus: none` TAKES A CLOSED VOCABULARY, NOT A SENTENCE** (§12, objection F-7). A free-string
> reason is exactly the construct that already launders 101 route oracles as human rulings
> (§10.1(f)), and combined with a zero-declared pass it makes *"declare `corpus: none` and be green"*
> the cheapest migration for `<LIVE>`, `<B2>`, `<B3>` and the three shipped examples — the all-zeros
> dashboard of §2.2 item 9 promoted into the grammar. So: `no-answering-engine` ·
> `retired` · `superseded-by:<bundle>`, plus a **named owner and a review date** (the
> `engine_coupling_floor.txt` header shape), and every bundle declaring it lands in a
> **DECLARED-ABSENT column on the ladder whose count may only shrink.**

### 5.3 Vocabularies to add or close

1. **Close `mac.test_kind`'s value** — an enum, not a string. `mac_vocabulary.yaml:175-196` says `closed: true`; `mac.schema.json:2410-2413` types it `{"type": "string"}`. One line. Probed today: a bogus value validates clean. **Note the limit of this fix: closing the enum makes the VALUE valid, it does not make the CLASSIFICATION true** — see the mirror shape in §5.4.
2. **`mac.assertion_kind`** — the runner's seven terms, **one definition**, cited by the grammar and every runner. Ends the proven 4-vs-7 divergence.
3. **`mac.test_status`** — `PASS | FAIL | ACCEPTED | FROZEN | ERROR | NOT_RUN`. **`NOT_RUN` is the missing member**: today a declared property with no result is simply *absent*, and absence reads as nothing-to-report. Cheapest fix in this document.
4. **`mac.oracle_authority`** — `sme | derived | baseline`, closed, **with the never-aggregate rule attached to the vocabulary**.
5. **`mac.oracle_kind`** — `route | property | value`.
6. **`mac.flag_state` · `mac.verdict` · `mac.disposition` · `mac.corpus_warning`** — relocated verbatim out of `sdk/acceptance/flags.py:83-117` into the grammar, **plus a seam gate asserting set equality in BOTH directions** (a one-way check misses the direction drift actually travels, since the code is where the work happens).
7. **`mac.test_tier`** — `T0..T3`. Today the tiers are prose and no run record carries a tier, so *"run the cheap tier on every ontology change"* is a policy nothing can enforce. **§8 depends on this**: without a tier the corpus row contains 71 items nobody is permitted to move.

**The phasing rule that applies to all seven** (§9-R4, and the platform Makefile's own precedent —
*"mac-sdk 731 … This is a BURN-DOWN, not an exemption"*): **no key becomes REQUIRED in the same
generation it is invented.** It lands as WARN with a printed count, and the count may only shrink.

### 5.4 SEVEN shapes — and every one of them is a COMPUTED kind, because the shape language cannot express them otherwise

**This subsection was rewritten wholesale.** As originally specified, four of six shapes were
unimplementable and, written into the shape language as it stands, **degrade to presence checks that
pass the exact defects they name** (§12, objection F-3). The measurement:

```bash
sed -n '1,16p' mac_shapes.yaml    # "Constraint kinds: required | in | subset_of"
grep -oE 'kind: [a-z_]+' mac_shapes.yaml | sort | uniq -c
# 5 required · 1 in · 1 field_roles_grounded · 1 join_rule_grounded · 1 rule_binds_grounded
```

`tools/check_shapes.py:141-202` dispatches seven kinds; the three relational ones are **hardcoded
Python**, not data. **There is no computed-comparison kind and no way to declare one.** So
`anchor-agree-derived` written as `kind: required, path: derivation.agree` passes on every authored
`agree: true` — including the anchor that compares a 12-month dict against a scalar (§2.2 item 8).

**Therefore: each shape below names the engine that runs it, the comparison it COMPUTES, and the
mutant fixture that must trip.** A shape whose check the gate cannot execute is a sentence, not a
shape.

| shape | engine | the computation — not a presence test | mutant that must trip |
|---|---|---|---|
| `conformance-renders-no-literal` | new computed kind in `check_shapes.py` | the **asserted value** resolves from a render marker (`@cols:`/`@n:`/`@frag:`), AND every numeric literal in the SQL is either inside a marker resolution or on an allowlist **with a reason**. A marker-presence test passes a property with one decorative `@cols:` in an unasserted column while the asserted number stays typed | type the asserted value; add a decorative marker elsewhere |
| **`ground-truth-renders-no-declaration` (NEW — the mirror)** | same kind, opposite direction | the asserted value does **NOT** resolve from a declaration marker, and any measured literal carries `measured_on` **plus a re-derivation command a checker can re-run**. **The two shapes must be exhaustive and mutually exclusive**, so `test_kind` is decided by the property's own SQL rather than the author's choice of word | stamp a conformance property `ground_truth` — it must fail **both** shapes, not escape one |
| `property-has-vacuity-guard` | **delegates to `check_vacuous_assertions.py`** — never restates it | the assertion's column must not be LITERAL-ONLY, NEVER-ZERO, CONSTANT or ABSENT **by that checker's own classification**. Written as `required: assertion.columns` it passes `SELECT 0 AS vacuity_failures`, which that checker already classifies as CONSTANT | each of the four reject classes, one fixture apiece |
| `anchor-agree-derived` | new computed kind | `agree` **equals** `raw_value == cross_check_value`, AND both values are present, non-null and type-compatible, AND `cross_check_sql` differs from `sql` **with a disjoint base-relation set** (sqlglot proves this offline) — otherwise "independent" is satisfied by copying the query | `agree: true` with a dict against a scalar; `agree: true` with a null; `cross_check_sql` copied from `sql` |
| `anchor-value-is-derived` | new computed kind | `expected.value` equals `derivation.raw_value`, **or** a `projection:` from a CLOSED VOCABULARY OF REDUCTIONS THE CHECKER APPLIES to `raw_value` to reproduce it. The original escape — *"unless a `projection:` names the reduction"* — was an unchecked authored key, i.e. the free-form-boolean defect this section opens by condemning | the 5 of 21 anchors where graded ≠ derived; a `projection:` the checker cannot execute |
| `anchor-question-resolves` | new computed kind | `question_id` resolves **and** `expected.pinned`'s axes are a **subset of that question's declared pins** — resolvability alone is satisfied by any existing id, so it passes the bulk-fill §11 refuses. **Keep the English-scanning heuristic as an independent SECOND OPINION**: every disagreement between declared key and heuristic requires a recorded ruling, and the disagreement count prints and may only shrink | a resolvable id whose pins are disjoint from the anchor's |
| `oracle-exercises-resolves` | `check_rule_coverage.py`, **rewritten** | **exact id match against a typed list, never substring.** Today `:124` stringifies the field and `:166` tests `r["id"] in c["exercises"]` over prose, so a rule is credited by any oracle naming a longer id that contains it. **And coverage is credited only when a GRADED RUN EXISTS for that question whose `rules` flag for that id is pass or fail — never `na`, never `unchecked`** | a substring-only match; an `exercises` entry on a question that never ran |

> **WHY `oracle-exercises-resolves` IS THE MOST DANGEROUS ITEM IN THIS DOCUMENT IF SHIPPED AS FIRST
> WRITTEN** (§12, objection F-4). Typing `exercises[]` as rule ids — the ruled fix, instruction 13 —
> takes rule coverage from 10/194 toward 194/194 **by editing YAML**, because the consumer credits a
> rule on a substring hit with no requirement that the question ever ran, and **71 of 96 have never
> run**. `check_rule_coverage.py:215` then returns `0 if covered == len(rules)`. **The estate was
> already burned by this exact class on this exact metric and says so in the same file at `:78-82`:**
>
> > *"As first written this counted any rule carrying `realized_by`, so binding a rule to a canon with
> > no generator moved the headline 8 → 9 while covered stayed 8 — the metric was easiest to move by
> > adding nothing that can fail."*
>
> **So: separate the exit condition from the headline.** Coverage is a reported fraction with its
> ceiling printed beside it, **not a gate that goes green when a field is filled.**

The **marker grammar** (`@cols:` / `@n:` / `@frag:`) and the resolver's path vocabulary belong in the
standard, because two of the seven shapes cannot be checked without knowing what a render looks like.
The **concept names resolved through it do not.**
### 5.5 What does NOT belong in the standard

A standard that describes one bundle's habits is not a standard. Named, with the measurement:

- **The question complexity/category taxonomy.** One shipped framework module hardcodes an instance's
  domain-language tokens alongside generic phrases, in a tracked file in the public repo, and
  `check_mac_public.py` reports `0 leak(s) over 588 tracked file(s)` **and does not see them** — the
  denied-token register has a hole. The standard should define only that a question **may** carry a
  `category` and a `complexity`, and where a bundle declares its own rubric.
- Question id namespaces; property `family` names (routing, not meaning); tolerances and roll-up
  thresholds (runner policy); SQL dialect, engine blocks and warehouse specifics; the test-runner shell
  script, the card format, the trend glyphs; *"budget roughly twenty value anchors"* (a doctrine
  heuristic, never a conformance rule); **and the dialect choice itself** — that is §9-R3.
- **The GUI standard, as console nouns.** The abstract contract is MAC-normative and the nouns are not:
  *every view is URL-addressable · every producer/consumer pair is machine-extractable · every
  unmatched route fails loudly · every run record carries declared/examined/skipped.* Twenty-one named
  sections and a chart library are the kit's platform track. (§9-R9.)

### 5.6 The conformance consequence, and it is the lever

`CONFORMANCE.md` §5.3 states it in the framework's own words: a declaration *"works for an artifact MAC
has no definition for … It does **not** work for a key inside a file MAC does define, because there the
declaration competes with a definition and loses."* **So defining the files removes the escape.** Today
the reference bundle validates with `0 error(s), 0 warning(s); 104/105 checked file(s) clean; 256 yaml in
bundle, 0 undefined, 151 declared out of scope` — **59 % of that bundle's YAML is out of scope and 148 of
the 151 are the acceptance corpus.** The gate reports `0 undefined` — clean — over the estate's most
important testing artifacts. And §5.3's own worked example of a legitimate waiver is, verbatim,
`acceptance/**` with the reason *"testing plane; MAC has no schema for it"*. **The standard question has
already been answered, in the standard's own voice. This dimension is about reversing that answer.**

The bill, per bundle: `<REF>` pays the largest and is the only one that can (everything exists in some
form); `<LIVE>`, `<B2>`, `<B3>` must first choose a dialect (§9-R3) and then face rule conversion; the
three shipped examples need a minimal conforming plane each, because **QUALITY.md point 1 is
append-only by rule and says a construct exercised in only one example is not done** — and the
acceptance plane is exercised in one bundle, in another repo, that is not shipped. One shipped example
bundle contains **zero files**: an empty bundle in a public framework repo is a claim.

**Phase it, or it becomes a wall.** Land all seven `$defs` with required keys held to what bundles
already carry — the escape closes and the compiler starts *naming* the 148 files. Promote `question_id`,
`exercises[]`-as-ids, the disposition `route` and the probe/final split in the next generation, against a
written migration. **Ship the two gate-contract repairs FIRST**, because a required key with no gate
behind it is the free-form-boolean defect repeated.

---

## 6 · THE TESTING DASHBOARD — **LEVEL 1 ONLY**, and why the other two levels were cut

**CUT IN THIS REVISION.** The original §6 specified three full levels — 6 widgets, 7 class instances
with 8 filter segments and 2 new columns, 7 detail blocks and a new field — **to be built into the
least-tested surface in the estate, with more than half the cells having no data source** (§12,
objection W-5). The console is *"110 files / 35 123 lines … 0 test files, 0 test runner, 0 `test`
script"*, and §6.3 concedes four of seven ladder rows are empty until §1.3 lands. Specifying L2 and
L3 now put the largest new build in the document into the only place with no instrument at all.

**So Level 1 only, and it answers the operator's sentence exactly as asked** — *"you have not
overview on the highest level; high level dashboard does not even exist."*

**The architectural fact that governs every choice.** The console's dashboard reader is
`readSourceFile(domain, dataset, path)` followed by `JSON.parse`, and the UI computes nothing by
explicit law (*"The UI computes NO flag, NO state and NO verdict"*). **Every widget is a committed
JSON file; a widget with no file cannot exist.** That is why *"the widgets are bad"* is mostly a
**data** finding.

**Credit where it is due, because it changes what to build.** The two existing testing pages are
better than the verdict suggests: one carries a trend, a "what moved" list naming changed ids, a
rule-coverage bar **with an honest ceiling marker**, and a per-property proof-of-search badge; the
other **already refuses percentages and prints every denominator**, with the reason in its source —
*"the previous header read '4 %' while 72 of 96 questions had never executed."* **The defect is that
those two pages cover 2 of 7 classes, nothing composes them, and the class that found 14 of 14
defects has no page.** They are also labelled *"Testing"* and *"Testing 2"*, the compiler lives under
*"Quality"*, and there is no overview at all (`grep -icE '"(dashboard|overview|home)"' App.jsx` → 0).

### 6.1 LEVEL 1 — one screen, four widgets, one file, three laws

> **LAW 1 · No percentage anywhere. LAW 2 · No tile shows a count without printing, on the same
> tile, what it examined. LAW 3 · No class is averaged into another.** All three are already law in
> this codebase; the overview **inherits** them.

One new artifact: **`acceptance/testing_overview.json`** — one read, not nine.

| widget | what it shows | absence handled how |
|---|---|---|
| **W1 · PROVENANCE BAR** (a required header, not a widget) | every artifact the screen read, present **or absent**, with `generated_at` and **age**; for an absent one, **the exact command that produces it**. **Absence is a value, never a blank** | see the box below — absence must be *unrepresentable as zero* |
| **W2 · THE LADDER** | one row per class: `UNIT · declared · observed · **falsifiable** · green · red · accepted · frozen · **cannot-fail** · NEVER RUN · src`. A class with no artifact prints `—` in green/red and its count in NEVER RUN — **never `0 red`**, which reads as *nothing wrong* | a class whose population enumerates as zero renders **EXIT 2 / COULD NOT ENUMERATE**, never a green zero |
| **W3 · THE NEVER-RUN WALL** | one bar per class, width = **declared**, segments green ▸ red ▸ accepted ▸ frozen ▸ **CANNOT-FAIL (own segment)** ▸ never-run (hatched), each labelled with an absolute count, sorted by never-run. **A class whose denominator is unknown gets NO bar** | ditto |
| **W4 · MOVEMENT** | X = recorded run (commit + date); one line per class; **Y = never-run count, not pass rate**; under it, the ids that changed. With fewer than two runs: *"one recorded run — direction unknown"* (a rule the existing page already holds) | partial today (one class) |

**`CANNOT-FAIL` is a distinct segment and a distinct column, and this is a fix, not a nicety**
(§12, objection F-8). Class ⑤ is the ladder's only fully-observed class and **29 of its 293
properties carry assertions that cannot fail** — so the one class that has finished running is the
one where a tenth of the greens are known to be meaningless, and a bar without this segment draws it
solid green. Sourced from `check_vacuous_assertions.py`, **counting AGAINST exactly like skipped and
exit-2**, and printing which unit it counted (assertions or properties — the two differ by 30 here).

> **ABSENCE MUST BE UNREPRESENTABLE AS ZERO** (§12, objection F-18). §2.2 item 9 measured the
> failure: three shipped bundles each ship a byte-identical all-zeros dashboard, and **zero-of-
> everything renders identically to clean.** So in `testing_overview.json`: every class carries
> `source_present`, `source_sha` and `source_mtime`; **the schema REJECTS a count of `0` when
> `source_present: false`**; and the projector's own `--self-test` points at an empty bundle and
> asserts **ABSENT × 7 with exit 2.**

**Two widgets from the original list are DEFERRED, by this document's own admission test (§5.2):**
`W4 · what a green does not prove` (`acceptance/test_classes.yaml`, *"authored once"*) and
`W6 · who found the last defects` (`quality/defect_provenance.yaml`, *"authored per defect"*) are
**authored files with no gate and no consumer**, which is precisely `QUALITY.md`'s measured fate —
nine points, 183 commits, zero appends. They return when they pass the admission test: a
`defect_provenance` entry must **cite the artifact that found the defect** (a gate run-record id, a
review artifact path, a commit sha) with a gate asserting it resolves, keyed append-only like
`suite_history`, and tied to the defect register so a fix landing without provenance **fails**.

### 6.2 Levels 2 and 3 — DEFERRED, with the gate that unlocks them named

**Level 2** (the class view: `declared · observed · last run · source`, then GREEN MEANS / CANNOT
PROVE / RUN IT, with the `anchored to` and `examined` columns) and **Level 3** (the detail, whose
genuinely new construct is a **field** — *what this does not prove*: the axes this test does not
judge, the half of its own assertion that cannot fail, and the authority ceiling) are both **retained
as design intent and not scheduled.**

**They unlock when, and only when:** (a) the ladder carries real data for **at least 5 of 7 rows**,
and (b) `npm run lint` is green at a declared floor — i.e. when §1.3 items 4 and 5 have landed. Until
then Level 2's `examined` column would render three producer-authored integers nobody recomputes
(§5.2) and Level 3 would be built on a surface with no runner.

**Two things from Level 3 are cheap enough to take now, and should be:** `source_watermark` and
`run_at` in the existing pages' headers. The watermark field **exists because of a named incident** —
a figure read off a dashboard was wrong because the source had loaded overnight — and
`grep -n "watermark"` over the page that shows those figures returns **nothing**, while `run_at`
survives only inside a tooltip. **The artifact carries the field that exists to prevent exactly that
incident, and the page drops it.**

### 6.3 The widgets with NO data source today — which IS the finding

`gate self-tests` (the runner prints one line and writes no file) · `unit tests` (no junit, no
coverage XML, no JSON report in any repo checked) · `the 23 unwired gates` (derivable only by
differencing the filesystem against the compile report) · `seams` (no register, no denominator) ·
`console views` (no runner exists) · `defect provenance` (nothing).

**And the first obligation of the screen is not a chart.** Pointed at `<LIVE>`, **every testing page
renders empty** — and §1.1 now says why: the bundle has 22 committed run records and 110 oracles
under filenames no console view reads. So the overview must say, on the first screen, **which bundle
it is looking at, that it found nothing, and the command for each absence.** A board rendering zeros
over a bundle it cannot read is *"correct engine, plausible number, wrong reading"* applied to the
testing plane itself.
## 7 · WHAT WE WILL NOT TEST

Refusals, with reasons. Each is a line an agent may cite to decline work.

1. **Warehouse arithmetic.** *"Is this number what the warehouse says it is?"* is a tautology (0008 §1). The engine executes exactly what it is given.
2. **Row counts and latest dates as assertions.** Already ruled inside a generator: *"Asserting a row count would fire on every load and be switched off within a week, taking the real checks with it."* **Recorded, never asserted.**
3. **The 74 of 83 prose never-clauses.** Reported `unchecked` with the clause **verbatim**. A structural guess manufactures a false green on the honesty axis.
4. **GUI pixels, layout and screenshots.** No visual-diff suite. It would have caught **none** of the 122 dead links, **none** of the 24 unmatched routes, and **not** the blank board. The GUI gets reachability + mount + data-presence + artifact-parse only.
5. **LLM phrasing.** Grade disposition, pins, value and rule violation — **never wording**. Four flags, never one status.
6. **One side of a seam with a mock on the other.** Not an omission — a **prohibition** (§3.1, §9-R6).
7. **Cross-source questions inside either source's denominator.** A question answerable only by combining two sources is not either source's question (0008 §7).
8. **Third-party library behaviour.** We test our *use* of a library, never the library.
9. **Anything reaching AWS or Bedrock in the default run.** Cost-gated tiers stay cost-gated — but they exit **2**, never 0, and the panel renders exit 2 as *could not run*, never as green.
10. **Button placement, labels, column order, tooltip text.** A human clicking is the correct and cheapest instrument, and it stays the operator's job.
11. **Divergent third-party ENVIRONMENT assumptions.** We test our *use* of a library (refusal 8); we do not test **two libraries' agreement with each other.** Added in this revision (§12, objection W-6) because the trust-store defect among the original fourteen — two clients verifying TLS against two different stores — is unreachable by the instrument the taxonomy's class E offers, and a class claiming a defect its instrument cannot reach is this document's own vacuous green written in prose. **The one honest instrument, and it is cheap:** a startup assertion that names each declared environment assumption and its **single source**, plus §8.5's requirement that every gate print the analysis dependency and version it used.

---

## 8 · THE RATCHET — rewritten, because the first version was gameable to ~90 % in one day

**THE ONE LAW THAT GOVERNS EVERYTHING ABOVE IT:**

> **No item may enter a numerator until a seeded mutant has made its check fail, and the record names
> the mutant.**

### 8.1 Why the first version is withdrawn

The original §8 ratcheted the **never-run count per class**, where *observed* meant "a committed run
record exists". An adversary moved it from **1 565 never-run to ~162 — an 89,7 % "improvement" — in
one day, with three commits, none of which adds a test** (§12, objection F-1):

| commit | effect on the old metric | tests added | of the 14 defects, catches |
|---|---|---|---|
| commit `pytest --junitxml` output | unit **1 273 → 0** | none | 0 |
| run and record the 31 gates that already carry `--self-test` | mutant **45 → 14** | none | 0 |
| fix the eslint glob | console **153 → 54** | none | 1 (the hook class) |

**The gate exits 0 at every step, because no class rose.** A metric that falls 90 % on three commits
that add nothing which can fail is not a ratchet; it is a scoreboard.

**The repair is this document's own law applied to its own metric.** Three columns per class —
**declared · observed · FALSIFIABLE** — and **the ratchet is on the third alone.** Under it, the
junit file moves nothing (there is no mutation tooling in the estate:
`grep -rliE 'mutmut|cosmic.ray' --include='*.py' --include='*.toml' --include='*.cfg' .` → nothing);
the 9 discovery-only self-tests move nothing; the eslint glob moves its 114 files **only once its
mutant fixture trips.**

### 8.2 Every floor is an ID SET, not an integer — and this estate ruled that TODAY

The original §8 said *"no class's never-run count may rise"* and *"the manifest sizes may only
GROW"*. **Both are numeric floors, which are IDENTITY-BLIND: retire one never-run item and add
another in the same commit and the count never moves, while an item silently left the population.**
This estate paid for that exact shape on the day this document was written, and built the
replacement — which the first draft cited nowhere
(`grep -ciE 'engine_coupling|silent headroom|identity-blind|mac_public_floor'` on the original → **0**).

The precedent, verbatim:

> `protocol/2026-09-13/059-the-floor-was-a-ratchet-in-name-only.md`: *"146 was measured after the
> first pass and nobody lowered it while the count fell to 4 — **141 findings of silent headroom** in
> the instrument that keeps this estate's identity out of a public repository."*
>
> `tools/mac_public_floor.txt`: *"A floor above the measurement is not a ratchet."*
>
> `sdk/gate/check_engine_coupling.py:11-20`: *"A numeric floor is IDENTITY-BLIND. Fix one driver
> import and add another elsewhere in the same commit and the count is unchanged… So the floor is a
> **SET OF PATHS**, compared by identity, and moving coupling from a declared path to an undeclared
> one is its own reject class: `coupling-relocated`."*

**So: reuse `check_engine_coupling`'s `Floor` loader — do not write a second one.** Every floor file
in this plan carries its header (`DECLARED` · `OWNER` as a **role**, since the repo is public ·
`RECORD` · `REVIEW BY` · `STANDING`), **a floor file missing a header is refused with exit 2, not
read with a shrug** (`:246-256`), and every PASS line prints **cleared/added by identity plus the
slack (floor − measured)** (`:622`) — the repair 059 made to `check_mac_public`. **A retire-and-add
then reports as a RELOCATION finding instead of free progress.**

### 8.3 The four guards that travel with the metric

- **A declared denominator may never shrink without a recorded reason.** (Measured precedent:
  `test_kind` coverage reached 100 % partly because 11 properties were retired and 12 frozen — one
  suite went 19 → 11. **Coverage rose by shrinking the denominator.**)
- **Skipped · crashed (exit 2) · unregistered · `baseline`-only · and CANNOT-FAIL all count
  AGAINST.** (Measured precedent: one panel reads `54 passed / 67` — 81 % green — while **9 are
  skipped and the 9 include every end-to-end check** of the GUI, the corpus grader and the value
  anchors.)
- **A class whose declared population enumerates as ZERO is exit 2, never a green zero.** This is
  the estate's dominant defect and two live instances are in this repo:
  `check_vacuous_assertions.py` pointed at a zero-subject bundle prints a tick and exits 0, and at
  `:233` returns **PASS when sqlglot is absent**. `check_rule_coverage.py:140-143` already refuses
  correctly and states why — *"ZERO IS NOT A SCORE… reported complete coverage of nothing at exit
  0"* — so the pattern exists and needs copying, not inventing.
- **THE CORPUS ROW SPLITS BY TIER, and the cost-gated remainder leaves the never-run column
  entirely** (§12, objection F-9). The original ratcheted `corpus 71/96` while §4.1 says *"do not
  propose closing it"* and §7.9 rules cost-gated tiers exit 2 — **a permanently frozen row inside the
  instrument built to fix permanently-red gates**, which is the §9-R7 defect reproduced. So:
  `mac.test_tier` (§5.3.7) splits the denominator, **only the offline/cheap tier ratchets**, and the
  cost-gated remainder prints as a **DISCLOSED BUDGET with its dollar figure** — 0008 §6 costs a full
  pass at ≈ 6 h 40 min and **≈ 144 $**. *A number nobody is permitted to move does not belong in a
  ratchet.*

**The population is PROJECTED, never authored** — the discipline a generator already states: *"a
data-sanity test is not written, it is PROJECTED — which means it cannot be skipped and cannot invent
a standard."* **One exception, ruled:** the seam register (§9-R5). Its handling is below, because
"may only grow" was the weakest line in the original document.

### 8.4 The seam register — ratchet on DISPOSITIONED, not on register size

The original made the authored register the denominator and said it **may only grow**. That is
precisely the metric the operator warned about, and worse than no metric: **the cheapest growth is
the trivial intra-module pair, and 478 mechanically-enumerated candidates guarantee unlimited
supply.** An authored register that may only grow, with no falsifiability requirement per entry, is a
coverage claim that rises by typing (§12, objection F-15).

**The shape instead:**

- **Denominator = the MECHANICALLY ENUMERATED candidate set** (478 today), and **that denominator is
  itself floored, with exit 2 below the floor** — so a broken analyzer cannot empty the population
  and score 100 %.
- **Numerator = candidates DISPOSITIONED**: `gated` · `not-a-seam, with a reason` · `queued`.
- **An entry counts as `gated` only when its mutant fixture (rename the key on one side) trips the
  gate.** An entry without a tripping mutant is *declared*, not covered.
- **Every entry names two distinct artifacts, at least one crossing a repo, language or process
  boundary.** All five measured shapes do; an intra-module pair does not qualify.

### 8.5 The gate-contract meta-gate EXECUTES; it does not grep

Every conformance count in the original §8 was a grep (`grep -l -- '--self-test'`,
`grep -c 'PASS:|FAIL:'`). **A wrong gate passes all four clauses:**
`print('PASS: foo — 0 items over 0 files')`, a `--self-test` that prints PASS and exits 0, and a
`sys.exit(2)` in a dead branch. **This is not hypothetical** (§12, objection F-10): of the 31 gates
carrying `--self-test`, **nine delegate entirely** to one shared helper —

```bash
grep -ln "selftest_discovery" tools/check_*.py sdk/gate/check_*.py | wc -l    # 9
for f in $(grep -ln selftest_discovery tools/check_*.py); do grep -ci mutant "$f"; done  # 0 ×9
```

— and that helper (`tools/mac_project.py:164-170`) seeds exactly **two mutants, both of the
empty-plane class**. `check_shapes.py` is one of the nine: **0 of its seven constraint kinds has a
mutant.**

**So the meta-gate, as four executed clauses:**

(a) `--self-test` must **print `mutants: N`**, and the meta-gate asserts **N ≥ the reject-class count
the gate declares**. (b) Run each gate **against an empty subject tree** and assert **exit 2**.
(c) **Parse the PASS line** and require an integer denominator **equal to the examined count**.
(d) Run each gate **exactly as its runner does, with `PYTHONPATH` cleared** — which is how 7 of 10
`sdk/gate` gates were found exiting 1 with `ModuleNotFoundError`.

Keep `selftest_discovery` as the empty-denominator mutant and **require the gate's own reject classes
on top of it.** And **every gate prints the analysis dependency and version it used** — two
environments producing one verdict is the trust-store defect from the original fourteen.

### 8.6 The command (proposed)

```
python3 tools/check_test_ladder.py --estate <ESTATE_ROOT>
# PASS: test_ladder — no class's FALSIFIABLE set lost a member
#   class      unit             declared  observed  falsifiable   never-run   floor slack
#   structure  gate script            45        22        <=13          23     +0 (0 cleared, 0 added)
#   mutant     reject class           ??         0           2          ??     EXIT 2 — population not enumerable
#   unit       test function       1 273         0          28       1 273     +0
#   seam       producer/consumer     478         0           0      478-d      denominator floor 478
#   property   property              293       293        <=264           0     cannot-fail 29 (59 assertions)
#   corpus T0  question                 ?         ?           ?           ?     tier unimplemented -> EXIT 2
#   corpus T3  question                71   DISCLOSED BUDGET ~144 $/pass — outside the never-run column
#   console-a  lintable file          114         0           0         114
#   console-b  view                    20         0           0          20
#   console-c  backend route           46         0           0          46
#   0 populations shrank · 0 floors missing a header · 9 skipped NOT counted as green
# exit 0 if no class's falsifiable SET lost a member by identity
# exit 1 if any did
# exit 2 if ANY population could not be enumerated, or ANY floor file lacks its header
```

**The ratchet is PER CLASS and PER IDENTITY. There is no total.** The original printed
`1 565 of 1 905` as a "disclosed" sum; this revision **deletes that sum**, because the console row
alone was three units added together (§1.2) and one of its three figures does not reproduce. The
shape of the problem is visible from ten rows without inventing an eleventh number that means
nothing.

### 8.7 Today's floor — the reproducing commands (substitute the placeholders; nothing touches a warehouse)

```bash
# THE OPERATOR'S 40 %: <LIVE>'s own last committed verdict  (§1.1)
python3 -c "import json;s=json.load(open('<LIVE>/acceptance/runs/latest.json'))['summary'];\
print(s['total'], s['by_overall'], s['b_oracle_green'], s['with_b_divergent'])"
# 82 {'PASSED': 47, 'not-passed': 35} 41 46      -> 42,7 % not passed, run dated 2026-07-15
grep -rn 'acceptance/runs\|acceptance/master' <CONSOLE_PKG>                  # (no output — nothing reads it)

# THE SENSITIVITY SIGNAL, not a budget argument (§1.4): authored vs derived in <REF>
cd <REF> && python3 - <<'EOF'
import json, glob, collections
GEN={'data_sanity_generated','ontology_generated','rules_generated'}; t=collections.Counter()
for j in glob.glob('acceptance/*_runs.json'):
    s=j.split('/')[-1].replace('_runs.json','')
    b='DERIVED' if s in GEN else 'AUTHORED'
    for r in json.load(open(j))['results']: t[(b, r['status'])]+=1
for b in ('AUTHORED','DERIVED'):
    n=sum(v for (x,_),v in t.items() if x==b); p=t[(b,'PASS')]
    print(f"{b:9s} {n:4d} total {p:4d} PASS {100*(n-p)/n:5.1f}% not green")
EOF
# AUTHORED   52 total   28 PASS  46.2% not green     (12 FAIL · 11 FROZEN · 1 ACCEPTED)
# DERIVED   241 total  235 PASS   2.5% not green     ( 5 FAIL ·  1 ERROR)

# the four vocabularies as they stand
grep -h '^authority:' <REF>/acceptance/oracle/*.yaml | sort | uniq -c        # 101 derived, 0 sme, 0 baseline
grep -l '^value: null' <REF>/acceptance/oracle/*.yaml | wc -l                # 96
ls <REF>/acceptance/anchors/*.yaml | wc -l                                   # 21
grep -l 'question_id' <REF>/acceptance/anchors/*.yaml | wc -l                # 0
grep -c 'accepted:\|frozen:' <REF>/acceptance/*.yaml                         # 26 total, ALL in authored suites

# the cannot-fail unit, stated correctly (§1.2)
python3 tools/check_vacuous_assertions.py <REF> --json | python3 -c \
  "import sys,json;f=json.load(sys.stdin)['findings'];print(len(f),'assertions over',
   len({(x['file'],x['id']) for x in f}),'distinct properties')"             # 59 assertions over 29 properties
python3 tools/check_vacuous_assertions.py <REF>; echo "exit=$?"              # exit=1
sed -n '233p' tools/check_vacuous_assertions.py                             # `return 0` when sqlglot is absent

# the plane is ungated, and both checkers are non-conforming gates
grep -n "vacuous\|rule_coverage" tools/mac_compile.py                        # (no output)
grep -c "PASS:\|FAIL:" tools/check_vacuous_assertions.py tools/check_rule_coverage.py   # 0 and 0
grep -c -- "--self-test" tools/check_vacuous_assertions.py                   # 0
python3 tools/check_vacuous_assertions.py example_tpch_ontology; echo "exit=$?"   # tick over 0 properties; exit=0

# the gate contract is not gated, and nine self-tests seed no class of their own
ls tools/check_*.py | wc -l; ls sdk/gate/check_*.py | wc -l                  # 36, 9
grep -l -- "--self-test" tools/check_*.py sdk/gate/check_*.py | wc -l        # 31
grep -ln "selftest_discovery" tools/check_*.py sdk/gate/check_*.py | wc -l   # 9  (0 mention "mutant")
sed -n '164,170p' tools/mac_project.py                                       # 5 fixtures, 2 MUTANT, both empty-plane
# PASS|FAIL token 20/45 · --self-test 31/45 · exit-2 path 25/45 · ALL THREE 13/45

# the floor shape this plan reuses instead of inventing
head -20 sdk/gate/engine_coupling_floor.txt                                  # DECLARED/OWNER/RECORD/REVIEW BY/STANDING
grep -n "isdigit" tools/check_mac_public.py                                  # :114 — the int floor, the shape NOT to copy

# the doctrine disagrees with itself
grep -n "L2 (execution-validated) is NOT implemented" CONFORMANCE.md         # :318
grep -c "PropertiesFile\|SmeLedgerFile" CONFORMANCE.md                       # 0
git log --format='%h %ad' --date=short -- QUALITY.md; git rev-list --count 63de1b7..HEAD  # 1 commit 2026-06-29; 183 since
cd ../mac-integration-kit/platform/skills && diff <(tail -n +5 gates-and-checks/SKILL.md) <(tail -n +5 scope-and-acceptance/SKILL.md)   # identical

# the console: the lint examines nothing, the runner cannot start, the boundary is 2 of 13
U=../mac-platform/packages/mac-console/src/mac_console/ui
sed -n '11p' $U/eslint.config.js                                             # files: ['**/*.{ts,tsx}']
find $U/src \( -name '*.ts' -o -name '*.tsx' \) | wc -l                      # 0
find $U/src -name '*.jsx' | wc -l ; find $U/src -name '*.js' | wc -l         # 79, 35
grep -oE 'key: "[a-z0-9]+"' $U/src/App.jsx | sort -u | wc -l                 # 21 nav keys
grep -oE 'section === "[a-z0-9]+"' $U/src/App.jsx | sort -u | wc -l          # 13 render branches
grep -c '<ViewErrorBoundary' $U/src/App.jsx                                  # 2   (comment at :1595 claims all)
grep -c '\${' $U/src/lib/api.js                                              # 67  — the UNRESOLVABLE bucket (§9-R8)
sed -n '3302,3307p' <CONSOLE_PKG>/console_api.py                             # unmatched GET -> `return 200, {}`
grep -c 'unmatched' <CONSOLE_PKG>/console_api.py                             # :3305 — the free both-sides instrument
sed -n '16p' <PLATFORM>/Makefile; ls -d <PLATFORM>/packages/mac-sdk           # PACKAGES names it; it does not exist
```

**Today's floor, stated honestly:** **there is no single number, and the absence of one is the
finding.** Ten rows, ten units, three of them not enumerable at all until a ruling lands. Red is
small in the framework and **42,7 % in the bundle the operator clicks** (§1.1). **The falsifiable
column is smaller than the observed column in every class.** That is a work queue, not a feeling —
and every row of it is a line an agent can be pointed at.
## 9 · OPERATOR RULINGS REQUIRED

Numbered. Each option carries its consequence. **R0 blocks everything; R1–R4 block the first week;
R5–R9 the second; R10–R17 can wait but not silently.** Three rulings were added and one promoted in
this revision (§12).

**R0 · DOES EXIT 2 BLOCK THE BUILD? — promoted out of R14(a), and it now gates §1.3 item 5.**
*(§12, objection F-17.)* Today 7 of 10 `sdk/gate` gates exit 1 with `ModuleNotFoundError` when invoked
the way the runner invokes them, and **exit 1 IS FAIL**, so a crash is read as a verdict — genuinely
bad. But the repair makes them exit **2**, and **if exit 2 lands non-blocking, the cheapest way to
green any gate in this estate becomes making it could-not-run.** The measured precedent is already in
this document: one panel reads 54 passed / 67 while **9 are skipped, and the 9 include every
end-to-end check.** A second live instance: `tools/check_vacuous_assertions.py:233` returns **PASS**
when its parser is absent — the checker §1.3 item 5 makes blocking is *itself* exit-2-shaped today.
**Recommend: BLOCKING but distinguishable** — exit 2 fails the build and prints as its own ladder
segment, never folded into red and never into green. **This must be ruled before the gate-contract
repair lands, not after.**

**R1 · Does the testing plane BIND the platform track?** Today `planes/` exists under the ontology track
only, and the platform track's entire testing law is CORE §7's 20 lines.
(a) **Extend the existing plane** — the four vocabularies generalise as written, and CORE §7 already says
*"route, MECHANISM and value"*, not SQL. (b) Author a second plane — creates the second home CORE §9
forbids. (c) Rule CORE §7 sufficient — leaves the 100 %-authored track ungoverned at its measured 46 %
drift rate. **Recommend (a).**

**R2 · Does a capability whose only oracle is a frozen engine capture count as WORKING or UNKNOWN?**
0008 §2(a)'s own table answers *"counts as proof of meaning? no — regression only."* Ruling **UNKNOWN**
is honest and **will look like a regression on the day it lands** (one instance board's headline greens
go to near zero and the estate's demonstrated fraction drops by roughly eight points). Ruling **WORKING**
keeps the number comfortable and makes every green uninterpretable. **Recommend UNKNOWN — and rule it
BEFORE the gate is built, not after.**

**R3 · THE DIALECT.** Three incompatible acceptance planes across eight bundles; two model the same
source and share not one filename. (a) Standardise the artifact set that actually has anchors and
properties, and **admit the grouped corpus as an optional `group` key on a flat list** — three bundles
then migrate by adding a key rather than restructuring. (b) Standardise the grouped dialect — but it has
zero anchors and zero properties to standardise. (c) Admit both — no host can render both.
**Recommend (a).** This decides migration cost for four live bundles and is not an agent's call.

**R4 · PHASING OF REQUIRED KEYS.** Defining the seven `$defs` removes the out-of-scope escape for **148
files in the reference bundle alone**. (a) Land with required keys held to what bundles already carry,
promote the rest next generation against a written migration — safer. (b) Land at full strength with a
dated migration debt — the only version that changes behaviour this quarter. Note the wider consequence
either way: the schema router already sends **every** `/acceptance/*.yaml` to the property definition, so
a bundle that has not declared its corpus out of scope fails structural validation on 130+ files today.

**R5 · THE SEAM DENOMINATOR — authored or derived?** (a) **Authored register**, seeded with the 14 measured
pairs: honest, slow, starts at 14, and every entry is real. (b) **Derived by static analysis**: 478
candidates immediately, and it will over-count every function boundary until the class is as
uninformative as the 1 273 unit tests. **Recommend (a) as the DENOMINATOR and (b) as a triage QUEUE, with
both printed on the gate's PASS line** — manifest size (may only grow) beside unexamined candidates.
Until this is ruled, the never-run wall cannot draw a bar for the class that caused every measured defect.

**R6 · Is the mock-on-the-other-side prohibition a BOUNCE or a PREFERENCE?** I have argued it is
negative-value and should be a review bounce. That is a ruling about how people work, not a technical
fact, and it is the one item here that changes what a reviewer is allowed to reject.

**R7 · Is a gate sitting AT its declared floor a PASS or a FAIL?** One gate prints FAIL with `0 cleared,
0 added` — permanently red by design — so any aggregate containing it is permanently red and red stops
carrying information. (a) A third verdict, `AT-FLOOR`, exit 0 with the standing count printed. (b) It
stays FAIL and the aggregate stays red. **Recommend (a)**, but it changes the gate contract, which is
yours.

**R8 · Is the local console API a FULL MIRROR of the deployed API, or a DECLARED SUBSET?** Its docstring
reads as a full mirror; three route families are absent entirely. The API-seam gate **cannot be written
until this is one fact with one home**: either those 24 calls are defects, or the gate needs an allowlist
file naming which routes live only on the deployed side (with its size printed, and grandfathering that
may only shrink).

**R9 · MAC-NORMATIVE or KIT-NORMATIVE for the GUI?** Your words were *"they should become part of the MAC
standard"* — for ontology tests that is right (§5). For GUI tests my reading is the opposite: this repo
is public with a token floor of zero and the console is instance-specific. **Recommend: the abstract
contract in MAC (URL-addressable views · machine-extractable producer/consumer pairs · unmatched route
fails loudly · declared/examined/skipped), the nouns in the kit's platform track.** If you intend a
MAC-normative GUI standard, it must be stated with **zero console nouns**.

**R10 · Is the 46,2 % authored not-green rate ACCEPTED (with a protocol) or a BLOCKER?** 12 FAIL, 11
FROZEN and 1 ACCEPTED sit in the authored suites, and by the plane's own rule a FROZEN red is *"a red
nobody has judged"*. **Eleven unjudged reds is a standing operator decision either way, and no artifact
records which.** This is exactly the `accepted:`/`frozen:` channel the plane built and nobody has used at
scale.

**R11 · Where does `authority: sme` live, and who is the named SME?** The schema already ships
`SmeLedgerFile` ("THE DOUBT CHANNEL"), which is adjacent to but not the same as a ratification record.
**Recommend: the ledger, plus one required `ruled_by`/`ruled_on` pair on the oracle** — the ruling
single-homed, the oracle carrying only a pointer. Second half of the same ruling: **is the estate's only
SME artifact (a 170 KB binary spreadsheet, 2026-07-07, unreadable by any gate, not carried forward) still
authoritative?** If stale, saying so retires the estate's only claim to a human-ruled tier. If live, it
is the seed for the ledger. **I can propose the shape; I cannot create the authority.**

**R12 · The 187 eslint findings — block, or accept with a named burn-down?** The same repo already holds
the precedent for the second option: its type-check target names a measured count per package and states
*"This is a BURN-DOWN, not an exemption."* Applying that shape means the glob is fixed and green on day
one with a named debt; blocking means the console cannot merge until 187 clear. **Per CORE, accepting a
known failure is an operator authority act.** Related: a rule disabled to reach zero must be disabled
**per-line with a reason**, never in the config, and the suppression count must print beside the file
count.

**R13 · The unreachable sections — restore or retire?** ~104 KB of view code, including the entire
benchmark surface, behind branches the router cannot select, plus a legacy alias deliberately pointing at
one of them. Restoring is one NAV entry each; retiring deletes the code and its push sites. **An agent
may not choose to delete 104 KB of an operator-facing surface.** If benchmark returns, the ladder grows a
row.

**R15 · Is the ratchet on OBSERVED or on DEMONSTRATED-FALSIFIABLE?** *(New — §12, objection F-1.)*
On *observed*, an adversary moved the headline **1 565 → ~162 in one day with three commits that add
no test**, exit 0 throughout. On *falsifiable*, an item counts only when a seeded mutant made its
check fail. **Recommend FALSIFIABLE** — it is the estate's own gate contract and instruction 27
applied to the ladder. The consequence to accept with open eyes: **the number gets much worse on the
day it lands** (class ② goes from 45 declared to *undeclared*; class ⑤'s green ceiling drops by 29),
and it will read as a regression. It is not one; it is the first honest reading.

**R16 · THE ADMISSION TEST — is it binding on every new artifact?** *(New — §12, objection W-3.)*
*"Name the gate that exits 2 when this artifact is absent or stale, in the same paragraph that
proposes it, or do not create it."* On that test `test_classes.yaml` and `defect_provenance.yaml`
fail today and are deferred (§11). Ruling it binding costs two widgets now and saves the estate its
fourth zero-adoption channel; ruling it advisory means it will be cited when convenient. **The
measured basis: `authority: sme` 0 of 101 · `question_id` 0 of 21 · `QUALITY.md` 9 points, 183
commits, zero appends — against `accepted:`/`frozen:` at 26 blocks, adopted because a red cannot move
without one.**

**R17 · Does the corpus row leave the ratchet?** *(New — §12, objection F-9.)* The 71 unrun are
cost-gated at ≈144 $ per pass and §4.1 says do not propose closing it. **Recommend: split by
`mac.test_tier`, ratchet the offline tier only, and print the cost-gated remainder as a disclosed
budget with its dollar figure — outside the never-run column entirely.** A number nobody is permitted
to move does not belong in a ratchet; leaving it in reproduces §9-R7 inside the instrument built to
fix §9-R7.

**R14 · Two smaller ones that must not be settled by default.**
(b) **The trend's Y-axis** — I propose never-run count, because the estate's own record shows a pass-rate
line drawing a redefinition as improvement. Confirm, or name the number you want to watch.
(c) **Stale runs** — when a run's ontology fingerprint differs from the bundle's, does the row render
stale-and-amber or **drop out of the green count**? The plane says no result may be older than the thing
it is about; dropping could take 25 graded rows to a much smaller number overnight, and that is your call.
(d) **A frozen reference repo holds a live crash on a gate's success path** (§2.2 item 4). Does a frozen
repo get a fix, or a recorded defect with no code change?

---

## 10 · MERGE NOTES — what today falsifies, where analysts disagreed, and what was not read

### 10.1 What today's measurements FALSIFY in the prior art. Plainly, with the document to correct.

**(a) `CONFORMANCE.md` §5.4 is now false, and it is the normative document.** It states at `:318`:
*"**L2 (execution-validated) is NOT implemented in MAC.** No gate, shape, or diagnostic code in this
framework runs the query a model implies and checks the answer. The taxonomy has no code for it and the
compiler will never emit one."* The schema disagrees: `$defs.PropertiesFile` is in the root `oneOf`,
described as *"v0.1.14: WAREHOUSE INVARIANTS — the L2 (execution-validated) evidence"*, and requires
`['id','family','test_kind','severity','statement','assertion','sql','validates']`. `grep -c
"PropertiesFile\|SmeLedgerFile" CONFORMANCE.md` → **0**: no changelog entry for nine v0.1.14 file-type
definitions or the v0.1.15 ledger. **Under the framework's own taxonomy this is a fact-contradiction, in
the document that defines fact-contradiction.** §9-R4 rules which side gives way.

**(b) `QUALITY.md`'s append-only rule has never once been exercised.** Its own lines 4-5:
*"This list is maintained and append-only — when a new failure mode is found, a new point is added
here."* It has been **9 points since the initial public release** (`63de1b7`, 2026-06-29);
`git rev-list --count 63de1b7..HEAD` → **183** commits since, a schema move of four minor versions, four
changes to CONFORMANCE.md, **zero** to QUALITY.md. Fourteen failure modes were found in one session, and
fourteen more while writing this. Its own rule says twenty-eight points. Separately its point 3 requires
a changelog entry on every schema bump and point 5 requires *"Docs reflect the change; nothing stale"* —
both violated by (a). **That is what an unenforced checklist looks like.**

**(c) `QUALITY.md` gates the examples, not the tools — which is why half the entry points have never
run.** Point 4 names exactly five things: three checkers against two example bundles, plus two test
files. The repo holds **75 `tools/*.py`, 36 of them `check_*`**. The checklist's printed denominator is
**3 of 75**, and nothing in the nine points says *run the tool you changed*. The 30-modules-with-a-main
finding is not an oversight **against** the checklist; it is the checklist's scope, working as written.

**(d) The plane's own `test_kind` gap claim is a grep artifact.** The plane states *"8 retrieval
properties declare nothing"*. Parsed rather than grepped: `test_kind` is stamped on **293 of 293**; the 8
and 2 are `not_expressible` entries — the honest disclosure of tests decided against — which correctly
carry no `test_kind`. **The gap is not that the field is missing; it is that its value is unchecked**
(§2.2 item 6). That is a worse defect and a cheaper fix, so the correction matters.

**(e) `platform/BLUEPRINT.md:75` "No skills. … This track has none" is false** — there are 15, one of
which has the wrong body. The document that would flag the miss is itself stale.

**(f) One waiver reason is factually false and must be corrected before it is cited.** The reference
bundle waives its oracle directory as *"SME rulings, one per question — authored independently of the
ontology."* **Not one of the 101 is an SME ruling**; all are `authority: derived`. CONFORMANCE.md §5.3
makes the reason load-bearing — *"it is what makes the debt arguable in review"* — so this waiver
currently launders 101 route oracles as human rulings.

**(g) Two "closed" gaps were closed by retirement, not authorship.** `test_kind` reached 100 % partly
because one commit retired 11 properties and another froze 12; one suite went 19 → 11. **Coverage rose by
shrinking the denominator** — the pattern the operator's standing rule already forbids. §9-R10 asks
whether that was a loss to restore or a cleanup to record as such; the commits do not say, and the
plane's gap register was not updated either way.

**What today does NOT falsify, and this is the larger half.** Every headline number in the plane's own
*"Gaps — the 40%"* section (`testing.md:366` — **the plane named the operator's number before the
operator did**) reproduces today: 96 questions, 101 oracles, 101 derived / 0 sme, 96 `value: null`, 71
unrun, 7 proven, rule coverage 8/31 with `composed: 0`, 73 advisory warnings. **The gap register is
trustworthy.** The doctrine is sound. **Every gap measured here is a gap between that doctrine and its
enforcement.**

### 10.2 Where the six analysts disagreed, and which reading this document takes

**Compressed in this revision.** Six disagreements were adjudicated; each ruling now lives where it
acts, so only the ruling and its reason are kept here.

| disagreement | ruling taken | why |
|---|---|---|
| **The headline number**: one working fraction over a summed population of 261 · the authored/derived split · rule coverage 10/194 · a per-class ladder | **The ladder, per class, never averaged** — and after §12 objection F-1, ratcheted on **falsifiable**, not observed | Seven classes with seven meanings of *green* cannot be averaged, and two of the scalar's four populations are instance-specific, so the scalar cannot live in MAC. The authored/derived split is **retained as the steering signal** (§1.4); rule coverage is retained as the **capacity ceiling** — it says whether writing more tests can help at all |
| **The seam denominator**: authored (14 real pairs) vs mechanically enumerated (478 candidates) | **Enumerated as the denominator, dispositioned as the numerator, both printed** — revised from the original "authored register, may only grow" after §12 objection F-15 | An authored-only register reads as perfect coverage of exactly the defects already fixed; an enumerated-only one is as uninformative as the 1 273 unit tests. **Printing both is the only shape where neither failure mode hides.** Surfaced as §9-R5 |
| **Gate-contract conformance counts**: 49 scripts / 17 conforming vs 45 / 13 | **45 / 13 for MAC**, with the estate-wide 106 / 24 cited and **the population difference disclosed** | Both are correct over different populations, and *a conformance number whose population is undeclared is the defect this whole document is about.* Also resolved: **22** of 36 `check_*` carry a self-test (**25** over all `tools/*.py`), and **9** gates live in `sdk/gate/` — the tenth file is a helper |
| **Anchors: 21 or 22, "0 anchored" or "14 anchored"** | All true, of different things: **21 anchor files** (+1 README) · **0 carry `question_id`** · **14 of 96 questions** are linked by the English-scanning heuristic | The confusion is itself the argument for instruction 16 |
| **Buying a component-test framework for the hook-order class** | **Lint first, mount-only smoke second, no content assertions ever.** The framework is **deferred, not refused** | One pass proved by running the same file under two extensions that lint catches the class statically for one line of config, while a mount-once smoke misses it by React's own semantics |
| **Whether `ground_truth` needs splitting** (197 of 245 are profile-projected *data contracts*, not tests of meaning) | **Diagnosis agreed; the proposed third vocabulary term NOT adopted** | Naming a third member of a settled vocabulary and re-stamping 197 files is an operator act, not an agent's. Folded into §9-R4's phasing. *Note the tension this leaves standing: `263 PASS of 293` is partly data-contract greens wearing an ontology badge, and no honest ontology-coverage denominator exists until they separate* |

**And the two "fifteenth defects".** Two passes each nominated one (the orphaned nav target; the
duplicated skill body). Both are real, both are in §2.2, and the session count is therefore **14
measured + 14 found while measuring.** Nothing was double-counted into the fourteen.
### 10.3 What was not read, declared

Five of the six ontology planes beyond greps (~212 KB); the bulk of the 63 KB flag evaluator beyond its
constants and roll-up; the SQL-role extraction that decides how `pins` grades a column; the per-family
property walkthrough; the 79 console components individually; the benchmark report format and whether it
deserves a class of its own once reachable; the platform packages' own test surfaces beyond counting
them; whether the live bundle's grouped corpus is migratable or superseded; and the discovery-channel
attribution of the original fourteen, which is taken from the brief rather than re-derived.

**Added for revision 2.** Every adversary claim that carries a consequence in §12 was re-run here
against the live files, and four did not survive (§12.2). **Not** re-derived: the original fourteen's
discovery channels; the 478 seam candidates; the 261-capability population; the 122 dead links; the
1 142 platform test functions; and `<LIVE>`'s 22 run records beyond the latest one — the 42,7 % is
that single newest record's own summary, not a trend, and **whether the number has moved since
2026-07-15 is unknown to this document because nothing has run since.** **Nothing read contradicted
anything above, and nothing executed here reached AWS, Bedrock or a warehouse — every measurement in
this revision is a read of a committed file or a static parse.**

---

## 11 · WEEK TWO, AND WHAT WAS DEFERRED

**The first week moved to §1.3**, because on the measured evidence — 47 initiative folders, 3 done,
eight untouched for 66–71 days — the first list *is* the strategy and an appendix is where plans go
to be admired. What follows is what comes after it, in order, and each item now carries the ruling it
waits on.

1. **`check_console_routes` as a gate** — NAV ↔ render switch ↔ push targets ↔ boundary coverage, one
   AST walk over one file. **The FIX is §1.3 item 3; this is the gate that protects it.** Per §12
   objection F-11 it floors **four key SETS compared by identity** — NAV keys, `section ===` branches,
   `push({section:…})` targets, boundary-wrapped branches — **not four counts**, because a
   rename-plus-add leaves every count unchanged. Mutant per direction. Hard floor so a non-matching
   walk fails rather than reporting zero orphans.
2. **The gate-contract meta-gate that EXECUTES** (§8.5) — four executed clauses, not four greps.
   *Blocked on §9-R14(a): exit 2 must be ruled blocking first, or this converts 45 fails into
   invisibles.*
3. **The seam register** (§8.4) — enumerated denominator with its own floor, numerator = dispositioned,
   an entry counting only when its mutant trips. *Blocked on §9-R5.*
4. **`question_id` on every anchor** — instruction 16, already ruled, offline, mechanical. **The false
   green to refuse: bulk-filling the key by running the very heuristic it replaces.** Each added key
   carries the evidence line naming what in the anchor's own derivation binds it to that question, and
   a verifier who did not write them re-derives a sample cold. **Per §12 objection F-16, the
   English-scanning heuristic is RETAINED as an independent second opinion** — every disagreement
   between declared key and heuristic requires a recorded ruling and the disagreement count may only
   shrink. *This is not a contradiction of instruction 16: what the plane forbids is the link being
   INFERRED; a second opinion that must agree with the declared key is the opposite of inference.*
5. **Restore the gate-contract skill's body**, and add the kit gate asserting every skill's H1 matches
   its frontmatter name, that no two bodies are identical, and that every skill is cited by a seat,
   command or method step (which also catches the orphaned GUI-testing skill). **Per §12 objection
   F-18 both doctrine checks are weaker than they read:** "no two bodies identical" passes after a
   one-character edit — so use **normalized similarity with a printed threshold and the
   pairs-compared denominator** — and "cited by a seat, command or method step" is satisfied by one
   index file citing all 15 — so **the citation must come from a seat or method file and must resolve
   as a link.**
6. **Then, and only then, the ladder** (§8) — because its job is to print denominators and four of its
   rows have no data source until the above exists.

**DEFERRED by this document's own admission test (§5.2), and named so they are not quietly dropped:**

| deferred | why | what unlocks it |
|---|---|---|
| `acceptance/test_classes.yaml` (W4) | authored once, no gate, no consumer — `QUALITY.md`'s measured fate | a gate that exits 2 when it is absent or stale |
| `quality/defect_provenance.yaml` (W6) | authored per defect, no gate; an all-zeros W6 renders identically to clean | entries citing the finding artifact, a gate asserting it resolves, keyed append-only, tied to the defect register |
| Dashboard Levels 2 and 3 | the largest new build in the document, into the estate's least-tested surface, with over half its cells sourceless | ladder real for ≥ 5 of 7 rows **and** `npm run lint` green at a floor |
| A component-test framework | measured: lint catches the hook class statically for one line of config; a mount-once smoke misses it by React's own semantics | a named class that lint and mount cannot see |
| Rule conversion (184 of 194 prose rules) | the genuine long pole and the only work that raises the ceiling — but it is months, and it moves nothing the operator can see this quarter | §9-R4, and the ladder carrying the ceiling honestly first |

**The uncomfortable summary, unchanged and now better evidenced: the top of the list is not a single
new test.** Items 0–3 of §1.3 are about thirty lines of code and two rulings. **The 40 % that does not
work is not under-tested. It is tested on one side of each seam, by checks whose denominators nobody
printed, in a bundle whose own verdict no screen displays.**

---

## 12 · WHAT THE ADVERSARIES FOUND

Two adversarial passes attacked this document after the first draft. **One survived it and one did
not, and both changed it.**

- **FALSE GREEN** — *"for every check the strategy proposes, write a wrong implementation that passes
  it."* **The document did NOT survive.** Its verdict: *"the DIAGNOSIS survives almost entirely; the
  INSTRUMENT does not."* Three fatal findings, fourteen major, two minor.
- **WILL ANYONE ACTUALLY DO THIS** — *carrying capacity, ruling bandwidth, whether a smaller
  intervention captures most of the benefit.* **The document SURVIVED**, with the verdict *"right-sized
  where it spends agent time, over-specified where it spends operator attention."*

**The composite reading, and it is why this revision cuts more than it adds: the diagnosis was
right and the instrument was a scoreboard.** Every law in §7, the refusal to gate coverage, the
no-average and print-the-denominator rules, the seam argument and the ten refusals held under attack.
What did not hold was everything that *counted* — and the two adversaries converged from opposite
directions on the same sentence: **a metric that can be moved by typing will be moved by typing.**

### 12.1 ACCEPTED — what changed, and where

| id | objection | what changed |
|---|---|---|
| **F-1** *(fatal)* | The ratchet number is gameable to an ~90 % improvement in one day by adding almost nothing that can fail: `--junitxml` (unit 1 273→0), recording 31 existing self-tests (mutant 45→14), the eslint glob (console 153→54) — 1 565 → ~162, exit 0 throughout, catching 1 of the 14 defects | **§8 rewritten.** Ratchet on **DEMONSTRATED-FALSIFIABLE**, never "observed": an item enters a numerator only when a seeded mutant made its check fail and the record names the mutant. Three columns per class (§1.2, §8.6). The governing one-liner is now the first sentence of §8 |
| **F-2** *(fatal)* | A numeric floor is identity-blind — and this estate ruled that **on the day the document was written**, citing none of it (`grep -ciE 'engine_coupling\|silent headroom\|identity-blind\|mac_public_floor'` → 0) | **§8.2 added.** Every floor is an **ID SET**, reusing `check_engine_coupling`'s `Floor` loader with its `DECLARED`/`OWNER`/`RECORD`/`REVIEW BY`/`STANDING` header, exit 2 on a missing header, cleared/added **by identity** plus slack on every PASS line. Protocol 059 and `mac_public_floor.txt` now cited verbatim |
| **F-3** *(fatal)* | Four of six proposed shapes cannot be expressed in the shape language (`required \| in \| subset_of` plus five hardcoded kinds, **none computing**) and degrade to presence checks that pass the exact defects they name | **§5.4 rewritten wholesale.** Seven shapes, each naming its **engine**, the **comparison it computes**, and the **mutant that must trip**. `property-has-vacuity-guard` now **delegates** to `check_vacuous_assertions.py` instead of restating it more weakly |
| **F-4** *(major)* | `oracle-exercises-resolves` converts rule coverage from a measurement into an editable field: substring match over stringified prose (`:124`, `:166`), no requirement the question ever ran, and `:215` exits 0 when `covered == len(rules)`. The estate was burned by this exact class on this exact metric and says so at `:78-82` | **§5.4 last row + the box under it.** Exact id match against a typed list; `by_corpus` credits only where a **graded run exists** whose `rules` flag is pass or fail — never `na`, never `unchecked`; **the headline fraction is separated from the exit condition** |
| **F-5** *(major)* | `test_kind: ground_truth` is a one-word exemption from the only shape enforcing the doctrine's central rule — the wrong implementation is "stamp it `ground_truth`, type the number." Closing the enum makes the **value** valid, not the **classification** true | **New mirror shape `ground-truth-renders-no-declaration`**, required to be **exhaustive and mutually exclusive** with the conformance direction, so a mis-stamp fails **both** shapes instead of escaping one. §5.3.1 now states the limit of closing the enum |
| **F-6** *(major)* | `declared / examined / skipped` is three producer-authored integers nobody recomputes — the authored-boolean defect correctly killed for `agree`, reintroduced and called *"the single field that ends the PASS-on-zero class"* | **§5.2 box.** A checker **recomputes `examined`** from the record's own per-result evidence (`rows[]`, `bytes_scanned`) and **fails on disagreement**. The `$def` must state the population — **subjects, not rules** — with the live `examined=len(_DEFAULT_DENY)` case disclosed as the one defensible exception |
| **F-7** *(major)* | `corpus: none` with a free-string reason reopens the escape §5.6 exists to close, and the ladder pays it as green | **§5.2 box.** Closed vocabulary (`no-answering-engine \| retired \| superseded-by:<bundle>`), named owner, review date, and a **DECLARED-ABSENT column that may only shrink**; **exit 2 on any class whose population enumerates as zero** |
| **F-8** *(major)* | The ladder's healthiest row is its most vacuous and W3 draws it fully green — no cannot-fail segment exists | **CANNOT-FAIL is now its own W2 column and W3 segment**, counting against like skipped and exit-2 (§6.1). *The arithmetic in this objection is rejected — see §12.2* |
| **F-9** *(major)* | The corpus row can never move by ruling, so the headline contains a permanently-frozen class — the §9-R7 defect inside the instrument built to fix it | **§8.3.** The corpus denominator **splits by `mac.test_tier`**; only the offline tier ratchets; the cost-gated remainder prints as a **DISCLOSED BUDGET with its ≈144 $ figure, outside the never-run column** |
| **F-10** *(major)* | The gate-contract meta-gate is greppable, and 9 gates already pass it with a self-test seeding no mutant of their own reject classes (all nine delegate to one helper seeding two empty-plane mutants; `check_shapes.py` has 0 of 7 kinds covered) | **§8.5.** The meta-gate **executes** four clauses: `mutants: N` printed and ≥ declared reject-class count; empty subject tree → exit 2; PASS-line denominator parsed and equal to examined; invoked as the runner does with `PYTHONPATH` cleared. Every gate prints its analysis dependency and version |
| **F-11** *(major)* | The eslint repair is floored on the wrong axis — `eslint .` with every rule at `warn` exits 0 with the file count high | **§1.3 item 4.** Three floored numbers: files linted · **active ERROR-severity rule count** · per-line suppression count; `--self-test` writes the measured mutant. **`check_console_routes` floors four key SETS by identity, not four counts** (§11.1) |
| **F-12** *(major)* | *"N/N sections mounted"* is green over a wholly disconnected console: unmatched GET → `200, {}` and the frontend throws only on `!res.ok` | **§1.3 item 1 (the repair, hoisted to week one, ~3 lines, no ruling).** The smoke classifies **DATA \| DECLARED-EMPTY \| ERROR** from a required `data-state` marker, only DATA counts as demonstrated, and it **asserts zero `unmatched` log lines** — the free both-sides instrument already at `console_api.py:3305` |
| **F-13** *(major)* | `check_api_seam`'s third bucket is where everything hides: 67 template literals in one client file; drop them and report 0 unmatched, or wildcard them and match the wrong route | **§9-R8 restated as blocking.** Three buckets — matched / unmatched / **UNRESOLVABLE**, the last floored and permitted only to shrink; **query-parameter name sets compared as well as paths** (the same shape as the field-name defect); mutant per direction |
| **F-14** *(major)* | *"Prefer derived wherever a derivation exists"* is a false-green generator, and the 18× is low sensitivity read as high quality — the estate's own vocabulary states the mechanism, and the plane's worked example of a test that caught a real stale claim is AUTHORED | **§1.4 added, §4.1 corrected.** The rule is now **DERIVE THE ENUMERATION, AUTHOR THE ORACLE**; authored and derived not-green rates report separately; **a falling authored share is a regression on its own line** |
| **F-15** *(major)* | The seam register's "may only grow" is the metric the operator warned about — the cheapest growth is the trivial intra-module pair, with 478 candidates guaranteeing supply | **§8.4 added.** Ratchet on **candidates DISPOSITIONED** over the enumerated denominator; **that denominator itself floored with exit 2 below it**; an entry counts only when its mutant trips; every entry names two artifacts, one crossing a repo, language or process boundary |
| **F-16** *(major)* | The anchor repairs name their false greens in prose while the shapes cannot detect them — any existing id resolves, and `projection:` is an unchecked authored key | **§5.4 rows 6 and 5.** `expected.pinned` must be a **subset of the question's declared pins**; `projection:` is a **closed vocabulary of reductions the checker APPLIES**; the heuristic is retained as a **second opinion with an only-shrinking disagreement count** (§11.4, with the reading against instruction 16 made explicit) |
| **F-17** *(major)* | Exit 2 must be ruled blocking **before** the contract repair, or the repair converts 45 fails into invisibles — and `check_vacuous_assertions.py:233` already returns PASS when its parser is absent | **§9-R14(a) promoted into the R1 tranche and named as a blocker on §1.3 item 5.** The missing-dependency path and the zero-subject path are fixed **in the same commit**; the exit-2 count prints as its own ladder segment |
| **F-18** *(minor)* | Three authored widgets inherit `QUALITY.md`'s fate; an all-zeros W6 renders identically to clean; two doctrine checks pass on a one-character edit | **W4 and W6 DEFERRED** under the admission test (§6.1, §11). **Absence made unrepresentable**: `source_present`/`source_sha`/`source_mtime` required, `0` rejected when absent, projector self-test asserts ABSENT ×7 exit 2. Skill checks use **normalized similarity with a printed threshold**; citations must resolve from a seat or method file (§11.5) |
| **F-19** *(minor, "what holds")* | Six load-bearing items could not be broken and should be kept verbatim | **Kept verbatim**, and the one line the objection asked for is now the **first sentence of §8** |
| **W-1** *(major)* | §11 is the only part that will happen and it is mis-composed: three of six slots catch none of the fourteen, while three ~30-line repairs behind eight of them appear nowhere — one named as work nowhere in the document | **§11 recomposed and HOISTED to §1.3**, in the objection's order: Makefile → unmatched GET → the 11 boundaries → NAV/switch/push → eslint → the plane checkers. The boundary repair was indeed named nowhere; it is now item 2. The two displaced items moved to week two |
| **W-2** *(major)* | The 46,2 % is identified with the operator's felt 40 % without evidence, and that identification steers 379 lines plus the declared long pole | **The identification is WITHDRAWN (§1.1)** and replaced with a stronger, reproducible one. *The objection's supporting evidence is partly rejected — see §12.2* |
| **W-3** *(major)* | Four new authored-forever channels, while three existing channels of that shape measure zero adoption — and two of the new ones become REQUIRED keys | **THE ADMISSION TEST added as a standing rule at the head of §5.2**: *name the gate that exits 2 when this artifact is absent, in the same paragraph, or do not create it.* W4 and W6 fail it and are deferred. **No key becomes required in the generation it is invented** — WARN-with-printed-count first (§5.3) |
| **W-4** *(minor)* | §4.3's build order inverts its own dependency: item 1 wires the lint into `make check`; item 5 repairs the runner `make check` is | **The Makefile repair is now item 0 of both §1.3 and §4.3** — a one-line deletion, the cheapest item in the document |
| **W-5** *(minor)* | The dashboard is specified at three levels into the least-tested surface, with over half its cells sourceless | **§6 CUT to Level 1** (99 lines → 98 including the rationale and the deferrals). L2 and L3 retained as intent, **gated on the ladder carrying 5 of 7 rows and lint green at a floor** |
| **W-6** *(minor)* | Defect class E is named after the one environment defect among the fourteen and neither instrument would catch it | **Class E renamed INVOCATION CONTRACT** (its measured content is real); the trust-store defect **moved to §7 as the eleventh refusal**, with the honest instrument named |

### 12.2 REJECTED — and why, since an unexamined objection is no better than an unexamined green

**1 · F-8's arithmetic: "the property row falls from 293 to at most 234 because 59 assertions cannot
fail."** **Rejected.** The **segment** is accepted and added; the **number** is a units error of
exactly the kind this document legislates against. Measured:

```bash
python3 tools/check_vacuous_assertions.py <REF> --json | python3 -c \
  "import sys,json;f=json.load(sys.stdin)['findings'];print(len(f),'assertions over',
   len({(x['file'],x['id']) for x in f}),'distinct properties')"
# 59 assertions over 29 distinct properties
```

**59 assertions sit on 29 properties.** Subtracting an assertion count from a property count is not a
valid operation, so the falsifiable ceiling for class ⑤ is **≤ 264 properties of 293**, not 234 — and
the honest statement is that **the assertion denominator is printed by nothing**, which is itself the
finding. **The original document's own "59 of 293" phrasing is corrected on the same grounds** (§1.2).
The gate must print which unit it counted.

**2 · W-2's supporting evidence: "the live bundle has zero properties, zero anchors and zero run
records… the 46,2 % cannot be a number the operator has ever been shown."** **The conclusion is
accepted; this evidence is half wrong, and the wrong half matters more than the right half.**
`<LIVE>` has zero properties and zero anchors — correct. It has **22 committed run records**, 110
oracles, 92 captured second-channel answers and an SME spreadsheet, and **its own last run says 35 of
82 not passed = 42,7 %**. So the operator's number is not merely *not* the 46,2 %; **it is a real
measured verdict on his own bundle that no screen displays** (§1.1). The objection's proposed
replacement — *"name the felt 40 % as a console that renders an empty widget"* — is accepted as **half**
the mechanism. The other half is that **the board exists and the console cannot read its filenames**,
which makes the dialect question (§9-R3) a week-one-adjacent concern rather than a tidiness project.
**Had this objection's evidence been accepted as given, the revision would have concluded there was
nothing to show, and the strongest finding in this document would have been missed.**

**3 · W-1's population figure: "49 initiative folders."** **Corrected to 47** (`ls -d specs/*/ | wc -l`
→ 47; statuses 14 backlog · 9 building · 9 awaiting-G · 5 awaiting-merge · 3 done · 2 review · 2
blocked · 2 analyzing). The conclusion is **unaffected and accepted**: 3 done, eight folders with no
commit since 2026-07-05..07-09 (66–71 days), the estate moves ~5 things at once.

**4 · F-4's fix, taken only in part.** *"Coverage is a reported fraction with its ceiling, not a gate"*
is accepted for the **headline**. It is **not** accepted as a reason to remove the gate's exit
entirely: `check_rule_coverage.py:140-143` already refuses an empty population with the right words
(*"ZERO IS NOT A SCORE"*), and deleting the exit would delete that refusal. **The reading taken: the
fraction never gates; exit is reserved for could-not-enumerate (2) and for a floor losing a member by
identity (1).**

### 12.3 What neither adversary found, and this revision adds

1. **The ladder's console row summed three different units** — `153 = 79 components + 20 views + 54
   routes` — **inside the table that states the units law**, and one of the three does not reproduce:
   `_ROUTES` in `console_api.py` holds **46** tuples today (23 GET · 18 POST · 3 DELETE · 2 PUT), not
   54. Class ⑦ now ratchets as **three rows** (§1.2, §8.6).
2. **`<LIVE>`'s own board says 42,7 % not passed, is sixty days old, and is read by nothing** — the
   finding that reorders the whole plan (§1.1).
3. **A false comment asserting the very coverage that is missing.** `App.jsx:1595` reads *"Each branch
   carries its own ViewErrorBoundary: boundaries here are per-branch and a new sibling inherits
   nothing"* — against `grep -c '<ViewErrorBoundary' App.jsx` → **2** of 13 branches. That is a class-F
   doctrine-drift defect sitting on top of the class-D repair, and it is why §1.3 item 2 fixes the code
   and the comment together.

### 12.4 WHAT LANDED WHILE THIS WAS BEING REVISED — and it falsifies this document's own §4.2

**Found by re-measuring rather than trusting the draft, and recorded here because the alternative is
a strategy proposing work that already exists.** Two gates were built on a concurrent track during
this revision:

| what landed | what it falsifies | status |
|---|---|---|
| **`sdk/gate/check_seam_agreement.py`** — *"THE SEAM INVENTORY. Enumerate every place two things must agree, then check the ones that can be checked and REFUSE TO SCORE the ones that cannot"* | §4.2's *"478 seams are mechanically enumerable today and the tested fraction is 0"*, and the draft's claim that no seam enumerator exists (`ls tools/ \| grep -iE 'seam\|orphan'` → nothing — **it is under `sdk/gate/`, not `tools/`**). Class ④ **now has a denominator** | **§9-R5 is partly pre-empted.** Read the gate before ruling it; its "refuse to score what cannot be checked" is the UNRESOLVABLE bucket of §8.4 already built |
| **`sdk/gate/check_entry_points.py`** + **`entry_point_floor.txt`** — measured first run: *"4 violation(s) over 28 entry point(s) examined, 68 invocation(s) … 28 of 32 entry points exercised, 4 skipped as billed, 2 crashed"* | §4.2's *"0 of 30 `sdk/` modules carrying a `main()` are invoked by any test"* and its build-order item 5 (*"entry-point execution smoke … weeks"*). **It is done, and it cost a day, not weeks** | Build-order item 5 is **retired**; the floor is what to review |
| The unit population | §1.2 row ③ and §2.1's *"131 pytest functions"*. Re-measured: **150** | the ladder regenerates; see the box in §1.2 |

**And the entry-point floor is a THIRD independent witness for objection F-2, arriving at §8.2's
conclusion from its own measurement** — quoted because it states the case better than this document
did:

> *"WHY THIS FLOOR NAMES ITS WITNESSES, WHICH `tools/mac_public_floor.txt` DOES NOT. That file
> declares a COUNT. A count-only floor has a hole: at a floor of 4, fixing one crash and introducing
> a different one keeps the count at 4 and the gate still prints PASS. At 300 findings that hole is a
> rounding error; at 4 it is 100 % of the signal."*

It also records the exact event §8.2 predicts and handles correctly: *"a concurrent track added
`sdk/gate/check_seam_agreement.py` and the denominator went 32 → 33 … while the crash count stayed at
4. A floor on the DENOMINATOR would have fired there; a floor on the crash WITNESSES correctly did
not."* **Three floors in this estate now agree on the shape. Adopt it; do not design a fourth.**

### 12.5 One defect this revision found in its OWN verification, and it is the dominant class

**`python3 tools/check_mac_public.py .` printed `PASS: check_mac_public — 0 leak(s) over 588 tracked
file(s) examined` for this document — while this document was UNTRACKED and therefore not in the
population.** The gate reads `git ls-files` (`:131-133`), for a good and recorded reason (*"311 of its
611 findings were in `build/`, which holds ZERO tracked files"*). **But a PASS whose denominator
excludes the file you are asking about is the estate's dominant defect, and it nearly shipped two
token classes into a public repo**: one absolute filesystem home path and one engine product name,
both introduced by this revision, both caught only by the manual sweep recorded in the header.
**Proposed repair, and it is small:** `check_mac_public` takes an explicit path argument and, when
given one, examines it **whether or not it is tracked** — and prints `N tracked + M explicit`. Until
then, **no new file in this repo may be offered for review on the strength of that gate's PASS
alone.**

### 12.6 What survived both passes unchanged, because it is the load-bearing half

Kept verbatim, on the adversary's own finding that no passing-but-wrong implementation could be
written for them: **(1)** coverage measured once and reported as a fraction with its module
denominator, **never as a gate** — because both sides of the measured name divergence were fully
covered and disagreed. **(2)** No percentage anywhere; no tile shows a count without printing what it
examined; the seven classes are never averaged. **(3)** The refusal of pixel and screenshot diffing,
on the measurement that it would have caught none of the 122 dead links. **(4)** The prohibition on
one-side-with-a-mock, with the honest split of the 131 that credits the 28 meta-tests which seed a
mutant — *"these are the ones that worked."* **(5)** `mac.test_status`'s `NOT_RUN` member. **(6)** The
ordering principle: instruments before the ladder.

**The gap was never the doctrine. It was that this document's anticipation of false greens lived in
prose while its checks did not implement it.** §5.4, §8 and §11 now carry those refusals as
executable clauses rather than remembered ones.
---

*PROPOSED — 2026-09-13, revision 2 (post-adversarial). **No artifact outside this file was modified
to produce it**, and every measurement is a read of a committed file or a static parse — nothing
reached AWS, Bedrock or a warehouse. **The public-token gate's PASS does not cover this file** (§12.5);
the manual sweep recorded in the header does. Ratification — every ruling in §9, every required key,
every floor — is the operator's; an agent may only write PROPOSED. STOPPING.*
