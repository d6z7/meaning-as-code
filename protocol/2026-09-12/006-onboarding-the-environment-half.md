---
when: 2026-09-12T13:26:28
what: built the environment half of onboarding — a requirements contract, a doctor gate, and an estate installer that holds neither dependency list nor repository URL
topics: [method, gates, registers, harness]
kind: build
track: platform
repo: mac-integration-kit
commits: [mac-integration-kit:f40ae22, mac-integration-kit:0f47be5, mac-integration-kit:54eae07, mac-integration-kit:598f2aa]
---

## WHAT FORCED IT

`install_workspace.py` configured a REPOSITORY. Nothing configured an ENVIRONMENT, and the gap was
structural: the README's first instruction took a `--target <repo>` argument a newcomer does not yet
have, nothing enumerated the repositories to clone, and the layout they must form lived as prose
(`~/dev/...`) in two documents rather than as a checkable contract. The README's own Status section
already conceded the consequence — "has not yet been run end to end by someone other than its author"
— and all three strangers in the measured baseline said, unprompted, that they never used the kit.

The implicit layout contract had ALREADY failed: the framework was resolved as a sibling of a
checkout, the platform repo absorbed its packages, the import root stopped being the checkout root,
and the compile gate silently refused EVERY bundle for "compiler could not be run".

## EVIDENCE

`git show -s f40ae22 0f47be5 54eae07 598f2aa` (mac-integration-kit).

`doctor.py` FOUND SOMETHING ON ITS FIRST RUN: both installed projections were drifted, because that
session's genericity fixes changed the method and nothing re-projected. The manifest had carried a
sha256 per path all along and `--check` had never been run by anything.

The installer was then tested by cloning the estate into a scratch root with every repo under a
DIFFERENT name. Two bugs, both in tools written the same day, neither visible from the author's
machine:

> 1. THE PRODUCT REPO'S OWN INSTALL WAS SILENTLY SKIPPED. `plan()` resolved each repo's install path
>    from a filesystem snapshot taken BEFORE the clone stage ran, so a not-yet-cloned repo reported
>    "nothing declared to install" — a false statement, not a missing feature.
> 2. DOCTOR HARDCODED THE FRAMEWORK'S DIRECTORY NAME. It looked for `<estate>/meaning-as-code` while
>    the framework sat at `<estate>/lang-core`, so verify failed on an otherwise correct estate.

`Self-tests: install_estate 11/11 (7 mutants), doctor 11/11 (7 mutants). run_gates 12/12.`

## WHAT CHANGED

`BOOTSTRAP.md` (seven requirements, five required and two advisory), `tools/doctor.py` (one PASS:/FAIL:
line, exit 0/1, `--self-test` with 6 mutants plus three assertions that ADVISORIES stay non-blocking),
`tools/install_estate.py` (five idempotent stages), and `make install` as a thin named wrapper adding
no behaviour of its own.

TWO DELIBERATE REFUSALS, both one-fact-one-home:

* It holds NO dependency list. Every repo already declares how it is installed; the installer finds
  that declared path and RUNS it.
* It holds NO repository URLs. The repository set is an ESTATE fact — a public method naming one
  organisation's remotes has shipped somebody's configuration. The registry is a gitignored
  `estate.json` created from `estate.example.json`, the same pattern as the token registers.

Execution now RE-PLANS per stage, because stages mutate the filesystem the next stage reads.

## WHAT IT DOES NOT PROVE

That the estate installs. `install_estate` is proved by self-test and by a `--dry-run` over one
estate; nobody but its author has run it end to end, and the kit's own `BOOTSTRAP.md` §4 says so. It
also cannot automate the five things it refuses to pretend about: Python, git, an interactive agent
login, repository access and cloud credentials.
