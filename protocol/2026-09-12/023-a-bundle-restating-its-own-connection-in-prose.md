---
when: 2026-09-12T20:45:43
what: removed an account id and nine infra handles from a customer bundle's tracked files, each one a restatement of what its connection declaration already says
topics: [containers, the-public-boundary, connectors, registers]
kind: defect
track: ontology
repo: customer-bundle (<domain>/<bundle>)
---

## WHAT FORCED IT

An AWS ACCOUNT ID and nine infra handles sat in tracked files of a served bundle — a reproduction
guide, two documentation files and a runtime model catalogue. Every one was a restatement of what
`connection.yaml` already declares.

The container spec permits a credential HANDLE only in its declared home and forbids a VALUE
anywhere. The account id was a value.

## EVIDENCE

`git show -s 70c9e3f` (the customer-bundle repo):

> Each site now cites the declaration instead of copying it. The account id is gone from tracked
> content: `git grep <account-id>` -> 0 files.

> This is what let the bundle be OPENED for inspection at all.

The loader change on the same minute (`2026-09-12/022`) measured `11 errors` on this bundle, of which
10 were infra handles; this commit is the bundle-side half of that pair.

## WHAT CHANGED

Prose cites the declaration rather than copying its value. One fact, one home — the same rule the
registers apply to the instruments, applied to the bundle.

## WHAT IT DOES NOT PROVE

Zero grep hits for one account id is not "no credentials in this bundle". The handles were not
removed, only de-duplicated back to their declared home, and `connection.yaml` itself remains the
thing an operator must write and must not publish. The gate that measures this class on the bundle
side is the container secrets check, and it is only as good as the gitignored handle register it
reads — absent on a fresh clone.
