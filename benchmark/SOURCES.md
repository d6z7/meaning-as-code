<!-- PIPELINE_TESTING.md §8.2 stage 0: "download BIRD dev + Spider; pin versions; record
     checksums". The checksums half was never done, and this file exists because that turned out
     to matter by 9.6 points. -->

# BENCHMARK SOURCES — pinned, with checksums

## Why this file exists

The C1 number was measured for a full day against a file called `bird_dev.json` (not shipped in any repository) that nobody had
recorded the origin of. When the OFFICIAL BIRD dev set was finally downloaded and compared, the
two differed in **182 of 1 534 questions (12 %)** — same count, same fields, different content,
so a different release. Measured on the same classifier, the same day:

| file | reachable |
|---|---|
| the unrecorded `bird_dev.json` (not shipped) | **71.8 %** |
| official `dev_20240627` | **81.4 %** |

**9.6 points between two files both called "BIRD dev".** A headline number quoted without naming
which one is not a measurement, and an external reviewer would ask this first.

## BIRD — dev set

| | |
|---|---|
| source | `https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip` |
| downloaded | 2026-09-24 |
| sha256 (dev.zip) | `cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630` |
| size | 346 207 293 bytes |
| release inside | `dev_20240627/` |
| questions | 1 534, in `dev.json` (not shipped — it lives outside every repository, see below) |
| databases | 11 SQLite files, 1.4 GB unpacked, in `dev_databases.zip` (not shipped) |

Each question carries `evidence` — a hand-written hint. **That field is the C4 control**: it is
the per-question way of supplying meaning, and the claim MAC has to beat.

```
   card_games              191      codebase_community      186
   formula_1               174      thrombosis_prediction   163
   student_club            158      toxicology              145
   superhero               129      european_football_2     129
   financial               106      california_schools       89
   debit_card_specializing  64
```

## Where it lives on this machine

`$HOME/dev/benchmarks/bird/` — OUTSIDE every repository, because 2.0 GB does not belong in git
and a benchmark corpus is an input, not source. `$BIRD_DB` overrides it; that default is
`bundlegen/regenerate_bird.sh`'s, which is the one home for the path.

```
benchmarks/bird/dev.zip                          the download, kept beside its checksum
benchmarks/bird/sha256.txt
benchmarks/bird/dev_20240627/dev.json            1 534 questions + gold SQL + evidence
benchmarks/bird/dev_20240627/dev_databases/      11 SQLite databases, 1.4 GB
benchmarks/bundles/<db>_L1/                      GENERATED bundles, one per database
```

The bundles are regenerable from the databases in seconds and the databases are re-fetchable from
the URL and checksum above, so nothing here is precious — but nothing here is reproducible from
the repos alone either, which is why the URL and the sha256 are recorded and not just the path.

## Spider

`spider_dev.parquet` (1 034) and `spider_train.parquet` (7 000). **Origin not recorded**, same
defect as the BIRD file above. They have not been re-pinned against an official release, so any
Spider figure carries the same caveat until they are.

## The headline, against pinned sources

| corpus | n | reachable |
|---|---|---|
| bird_dev (official 20240627) | 1 534 | 81.4 % |
| spider_dev | 1 034 | 86.8 % |
| spider_train | 7 000 | 86.1 % |
| **ALL** | **9 568** | **85.4 %** |

Quote the 85.4 % only with this table beside it, and never without saying which BIRD.
