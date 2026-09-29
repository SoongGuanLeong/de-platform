# The performance benchmark plan: the baseline, hypothesis, change and result protocol

**Ticket:** [The performance benchmark plan: the baseline, hypothesis, change and result protocol](https://github.com/SoongGuanLeong/de-platform/issues/21)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decision records:** none of its own. This plan applies [ADR-0007](adr/0007-completion-bar-as-a-gate.md) (the completion bar as a gate) and inherits M18's measured axis from [ADR-0027](adr/0027-self-host-what-the-platform-operates.md). It creates no ADR because nothing in it reverses a decision, and the one genuinely contestable choice inside it, the axis, is already recorded elsewhere. The reconsideration trigger is recorded in section 9: a benchmark result that contradicts a layout or architecture decision supersedes that ADR rather than being quietly explained away in an evidence item.

---

## 1. What this document is

The protocol every benchmark on this platform follows, the inventory of which work carries a benchmark and which carries only a correctness test, the order the benchmarks run in, the register of thresholds they are judged against, and the axis M18 measures.

It resolves [the benchmark-plan ticket](https://github.com/SoongGuanLeong/de-platform/issues/21) on the map. It is the missing half of [the testing strategy](testing-strategy.md), which says which tests are benchmarks and defers how one is recorded to here.

It is a plan, not a result. Nothing has been measured. No latency, throughput, file count, byte figure or row count appears in this document, and every number in [`docs/budgets.yaml`](budgets.yaml) is a threshold declared before the measurement that judges it. **Nothing is measured while the map is open**: the benchmarks run during implementation, after the proposal is approved.

**One correction this document carries.** [`docs/incident-laboratory.md`](incident-laboratory.md) recorded that `docs/budgets.yaml` ships empty. It held five M17 entries when this plan was written, and this plan takes it to the full set of 58 entries. The stale sentence is corrected in place.

**What a benchmark is not.** A benchmark is not a test. A test asserts a behaviour; a benchmark measures a magnitude and compares it against a threshold declared in advance. The completion bar's core checklist requires both, and they are recorded separately, because a passing benchmark and a passing test answer different questions.

## 2. The protocol

### 2.1 The record is an evidence item

The tempting mistake is a second, benchmark-only record schema. It would drift from the completion bar's evidence-item schema the first time a field changed, and a reviewer would then be reading two documents to check one claim.

The benchmark record **is** an evidence item. It lives at `docs/evidence/<class>/<instance>/<item>.md` with its raw output committed under `raw/` beside it, it carries the fields fixed in [completion-bar section 7](completion-bar.md), and it adds a benchmark block described below. There is one schema, one directory layout, one CI validator.

### 2.2 The three modes

A protocol that only knows A/B cannot record a sweep, and one that only knows single-arm cannot carry a "faster than" claim. The three modes are:

| Mode | Arms | What it may support |
|---|---|---|
| **Comparison** | Two: a baseline and a change | A directional claim, "arm B is faster than arm A", when nothing but the declared change differs |
| **Sweep** | Three or more | A "which axis won and which lost" claim, with a decision record naming the trade-off |
| **Characterisation** | One | A magnitude only, and never a comparison |

Only comparison and sweep may be cited for a "faster than" claim. A characterisation run is still evidence, because it establishes a magnitude no other run establishes, but a single arm cannot show that a change caused anything.

### 2.3 The required fields

The completion bar's fields (`id`, `capability`, `matrix_rows`, `claim`, `proves`, `command`, `profile`, `commit`, `date`, `budget_ref`, `artifact`, `observed_once`) plus the benchmark block:

| Field | Meaning |
|---|---|
| `mode` | `comparison`, `sweep` or `characterisation` |
| `arms` | The arms by name, with the baseline named explicitly |
| `hypothesis` | One falsifiable sentence, written **before** the run |
| `change` | What differs between the arms, and the statement that nothing else does |
| `controls` | The controls block, section 2.5 |
| `runs` | The run count, the statistic reported, and the per-run values |
| `result` | The observed figures, each labelled as measured |
| `trade_off` | What the winning arm gave up. A sweep that reports only the winner has not recorded the trade-off |
| `verdicts` | One pass or fail per `budget_ref` |
| `reset_proof` | The readiness assertion that followed the reset |
| `tpc_label` | Present and true for any figure measured on TPC-C or TPC-H data: a **TPC-derived result**, never a TPC Benchmark Result (ADR-0009) |

The hypothesis is written before the run and never edited afterwards. A hypothesis written after the result is a description.

### 2.4 Runs, statistic and concurrency

One run of a 600-million-row layout benchmark on a shared 12-CPU host is noise, and reporting the best run is the standard way a benchmark lies.

- **Latency: 5 runs, the first discarded as warm-up.** Report the median and the p95 per query, plus the raw per-run values. The budget is judged on the p95.
- **Throughput and counters: 3 runs.** Report the median and the spread. A spread above 10% is recorded as noise rather than hidden, and a run whose spread is that wide may still be valid evidence, with the noise stated.
- **Two concurrency points for the nine-query set.** `c=1` for the per-query latency budgets, and `c=4` for the mission's concurrent-queries family, with the degradation between them judged as a ratio. Four is chosen because the worked example in [local-development section 4](local-development.md) gives ClickHouse 8 vCPU in the benchmark profile, so four concurrent queries keep the engine above the queueing knee instead of measuring a queue.

### 2.5 The controls block

Declared with every record, because a figure without them is a figure the reviewer cannot check:

- Hardware as configured: 12 vCPU, and the profile's declared entitlement in MiB, with `MemAvailable` recorded at start.
- Data volume per source, at the declared volume in section 5.
- Engine versions: the pinned set, Iceberg 1.11.0, Flink 2.1.3, Spark 4.1.3, ClickHouse 26.8 LTS, Polaris 1.7.0, and the JDK 17 and Python 3.12 image pins.
- The exact command, which is the literal invocation of the benchmark's entry point (section 8).
- Concurrency, and the query set where one applies.
- The pinned Iceberg snapshot id, or a tag, since tags never expire while `expire_snapshots` would remove the snapshot.
- Cache settings where a cache exists, including the ClickHouse read-through arm's metadata cache, which is measured on with one uncached run recorded as well ([serving-layer section 8](serving-layer.md)).
- Co-tenancy: only the profile's resident services plus the declared transient. The host's desktop applications are named as an uncontrolled variable rather than claimed away.

### 2.6 What invalidates a record

A record is invalid, and may not be cited for a claim, when any of these holds:

1. The commit that introduced the cited budget is not an ancestor of the run commit. The CI resolves the citation to the commit, which is what makes the order visible in history.
2. The cited budget was superseded.
3. The raw output is missing, or the command cannot be re-run.
4. The reset was not proven by a readiness assertion.
5. An undeclared component was co-resident.
6. A service restarted mid-run, unless the benchmark is about restart.
7. More than one variable differs between the arms of a comparison.

A benchmark whose environment cannot be reproduced is still recorded, with `observed_once: true`, and may never be cited as evidence for a claim. The claim must rest on a reproducible measurement or be downgraded to an observation. This is the completion bar's honesty rule, applied to benchmarks specifically.

### 2.7 The TPC label

Every throughput, latency or file-count figure measured on TPC-C or TPC-H data is a **TPC-derived result** and is labelled as one. It is never a TPC Benchmark Result. The TPC EULA restricts publication of performance results, and ADR-0009 carries the obligation; the `tpc_label` field makes the obligation a property of the record rather than of the author's memory.

## 3. The inventory

### 3.1 The mission's nine benchmark families, mapped

[MISSION.md section 24](mission/MISSION.md) names nine families to define benchmarks for. None may be dropped silently, and none may be double-counted.

| Mission family | Benchmark | Profile | Matrix rows |
|---|---|---|---|
| Ingestion throughput | **B5** CDC ingest cost per GB: objects written, bytes written, compaction work per GB ingested | streaming, plus a compaction window | M18, M17 |
| Streaming throughput | **B3** the Flink state and checkpoint tuning record, throughput per arm | streaming | M3 |
| End-to-end latency | **B4** source commit timestamp to row visible in the materialised copy, p50 and p99, on both arms | streaming | M8, M7 |
| Batch processing time | **B7** Spark batch wall-clock and resource use at the declared volume | batch | M4, M18 |
| Query latency | **B2** the two-arm comparison, C1 to C3 and N1 to N3, p50 and p95 | batch | M7, M9, M6 |
| Concurrent queries | **B2** at `c=4`, same query set, judged as the degradation against `c=1` | batch | M7, M9 |
| File counts | **B1** the layout sweep, file count and size distribution per variant | batch | M5, M6 |
| Compaction effectiveness | **B1**'s compaction duration and equality-delete collapse, and **B5**'s compaction work per GB | batch and streaming | M5, M3 |
| Resource utilisation | Recorded inside every benchmark, as the declared peak against the observed use. No separate run, because a resource figure without a workload is not a benchmark | n/a | M18 |

Two further benchmarks, outside the nine families because the mission names them elsewhere:

- **B6** the schema-evolution per-operation cost counters (M17, batch profile), whose thresholds already exist as the five `m17-*` entries.
- **B9** the two timed component-swap drills (M1, batch profile), which produce a wall-clock figure each.

### 3.2 Correctness only, no benchmark

These carry tests, and a budget only where a threshold exists. They are listed so the absence of a benchmark is a decision rather than an omission: the CDC hard cases, the watermark and lateness policy, the exactly-once effect, the kill and restore behaviour, contract conformance, the DQ gate's blocking behaviour, the schema-evolution read paths, the retention assertions, lineage emission, backfill identity, re-run idempotency, the security denials, the vended-credential scope, and TTL application.

**M13's false-positive rate is not a performance benchmark.** It is a repeated-run statistic over a declared number of consecutive clean runs, so it sits under the batch profile with its own budget and does not appear in this plan's benchmark set. Recording it as a benchmark would let a correctness property be judged by a latency protocol.

**The benchmark identifiers therefore run B1 to B7 and B9.** The identifier B8 was assigned to the false-positive rate while this plan was being written, and it is deliberately retired rather than reused, so a reader who notices the gap knows it was a decision rather than a lost section.

## 4. The pre-registered arms

Choosing arms after seeing results is the same failure as writing a budget after seeing the number. The arms are fixed here.

**B1, the layout sweep: three variants of `commerce.gold.fact_lineitem`.**

| Variant | Partitioning | Sort order | What it tests |
|---|---|---|---|
| **A** (baseline) | `toYYYYMM(l_shipdate)` | `(l_shipdate, l_partkey, l_suppkey)` | The [serving-layer](serving-layer.md) baseline, declared as the reference the other two are compared against |
| **B** | `toYYYYMMDD(l_shipdate)` | as A | Partition granularity against file count and partition pruning |
| **C** | `toYYYYMM(l_shipdate)` | `(l_suppkey, l_shipdate)` | The `proj_supplier` hypothesis named as an open measurement in [serving-layer section 11](serving-layer.md) |

Each variant re-materialises the ClickHouse copy, because a changed Iceberg layout changes what ClickHouse reads, and the p50 and p95 figures are only comparable when both sides moved together.

**B2, the two-arm comparison:** read-through against materialised, on C1 to C3 and N1 to N3, with P3 excluded. Fixed by [serving-layer section 8](serving-layer.md).

**B3, the tuning record:** checkpoint interval 10 / 60 / 180 s, parallelism 2 / 4, sink flush size 64 / 128 / 256 MiB. The state backend is declared as the baseline rather than varied, because changing it changes the state representation and would confound the other two axes. Fixed by [streaming-jobs section 7](streaming-jobs.md).

**B4, freshness:** one arm, the materialised CDC copy, with the read-through arm measured as its baseline. Fixed by M8.

**B5, the CDC ingest cost:** one arm, the CDC path at the declared volume.

## 5. The declared volume, and the order the benchmarks run

### 5.1 The declared volume

Every benchmark runs at the declared volume, because the volume-dependent claims cannot be reduced: M5's layout trade-off, M6's file counts and fan-out, M7's serving latency and freshness, M18's cost, and every compaction measurement. The declared volumes are TPC-C W=100 (about 30M rows, target 10 GB in PostgreSQL), TPC-H SF100 (26 GB, a 600M-row `lineitem`), the RIPE Atlas 24-hour replay (target cap 5 GB), and ONSPD whole (a 235 MB multi-CSV zip). The working-set arithmetic is in [dataset-selection section 4](dataset-selection.md) and fits the 140 GB data ceiling against 231 GB of disk.

A reduced run at SF30 or W=10 is permitted only as a labelled reduction that cannot evidence a volume-dependent claim. That rule is [testing-strategy section 4](testing-strategy.md)'s and this plan applies it rather than restating it.

### 5.2 The order, given the profiles cannot be co-resident

Batch peaks at 6976 MiB and streaming at 7168 MiB against an enforceable 7168 MiB, so the two path profiles never run together, and the incident laboratory is never co-resident with `benchmark` at all.

**P0, fixture establishment, once, under `batch`:** load TPC-C W=100 into PostgreSQL, TPC-H SF100 into Iceberg bronze, the RIPE 24-hour replay, and ONSPD. Every benchmark afterwards reads the same pinned snapshot or tag, which is what makes two benchmarks comparable.

**Then the batch benchmarks, in this order:**

1. **B1**, the layout sweep. First, because B2's materialised arm must carry B1's winning layout: if it does not, the two-arm delta confounds layout with architecture and measures neither.
2. **B2**, the two-arm comparison, at `c=1` and `c=4`.
3. **B6**, the M17 per-operation cost counters.
4. **B7**, the batch wall-clock and resource use.
5. **B9**, the two swap drills, which need the whole batch path standing.

**Then the streaming benchmarks:**

6. **B3**, the tuning record.
7. **B4**, freshness.
8. **B5**, the CDC ingest cost, with the `rewrite_data_files` compaction procedure in a following window, because Spark and the streaming stack cannot co-reside.

**Then the incident laboratory**, which needs both paths plus the observability overlay and runs after every benchmark, so a benchmark's co-tenancy is never polluted by an injected fault.

Each benchmark declares its own resource entitlement inside its protocol, within the `benchmark` profile's rule of at most 7168 MiB and 12 vCPU. The worked example in [local-development section 4](local-development.md) is the precedent for B1: ClickHouse 6144 MiB / 8 vCPU, PostgreSQL 384 / 1, SeaweedFS 256 / 1, peak 6784 MiB / 10 vCPU. **An entitlement is not a threshold**, and the ceilings live in `deployment/budgets/profiles.yaml` rather than in `docs/budgets.yaml` (ADR-0031).

A reset is proven before each benchmark, not asserted: the reset procedure followed by a fresh bring-up that reaches the same readiness assertion. The `--keep` flag exists for a benchmark run that has to survive inspection.

## 6. The budget register

### 6.1 The policy

`docs/budgets.yaml` holds one entry per threshold, and every evidence item cites the budget id it is judged against. This plan adds the following policy on top of the completion bar's honesty rule.

**Naming:** `<row>-<metric>[-<statistic>]`, lower-case, so `m7-c1-p50`, `m5-compaction-duration`, `m18-objects-per-gb`, `m16-mttd-incident-1`. The five existing `m17-*` ids already fit.

**One entry where two rows judge the same number.** The nine-query p50 set is cited by both B1 (per variant) and B2 (per arm). The storage-reclaimed threshold is cited by both M5's retention policy and M12. A second copy of a shared threshold is a second number that can drift, so the shared entry is cited twice rather than duplicated.

**A `supersedes` field.** The completion bar says a changed budget creates a new entry, but the file had no way to express which entry the new one replaces, so the CI could not flag evidence citing a superseded id. New entries gain `supersedes: <id>`.

**A `commitment` field.** Every entry declares how its value is committed, in one of two classes.

### 6.2 The two classes of commitment

Both classes satisfy the evidence standard's rule that a threshold is declared before the measurement it judges. They differ in when the number becomes knowable.

**Class `fixed`.** The threshold is a design constraint: it comes from an external limit, a declared architectural target, or a mechanism that must work at all. The value is committed with this plan. Examples: the per-incident MTTD and MTTR ceilings, the consumer-lag band, the freshness p99 band, the checkpoint-duration ceiling, the persona latency classes, the cross-path tolerance, the session-policy size, the swap-drill hours, the median file size, the small-file share, the rewrite improvement ratio, the quarantine share, and storage-reclaimed greater than zero.

**Class `derived`.** The threshold is relative: it can only be set once the baseline arm exists on this hardware. The **derivation rule** is committed with this plan and the **value** is committed in a commit that precedes the run that is judged. Examples: the nine per-query p50 budgets, the M5 write throughput and compaction duration, the two-arm delta, the batch wall-clock, the freshness p50, and the three M18 counters. The derivation rule is what stops the number being free once the run happens: [serving-layer section 9](serving-layer.md) already ruled that a per-query threshold invented before the workload is measured on this hardware would be a guess wearing a threshold's clothes, and a rule committed in advance is the honest alternative to a number committed in advance.

A `derived` entry carries `threshold: pending` until its value lands. **An evidence item citing an entry whose threshold is `pending` fails CI**, which is the mechanism that stops a derived budget being cited before it exists.

### 6.3 The benchmark-to-budget map

| Benchmark | Budgets it is judged against |
|---|---|
| B1 layout sweep | `m5-write-throughput`, `m5-compaction-duration`, `m5-median-file-size`, `m5-small-file-share`, `m7-<query>-p50` per query, the persona p95 class, `m12-storage-reclaimed` |
| B2 two-arm | `m7-<query>-p50` per query, the persona p95 class, `m7-arm-delta`, `m7-concurrent-degradation-<persona>`, `m6-query-improvement-ratio` |
| B3 tuning record | `m3-checkpoint-duration`, `m3-checkpoint-failed-count` |
| B4 freshness | `m8-freshness-p50`, `m8-freshness-p99` |
| B5 CDC ingest cost | `m18-objects-per-gb`, `m18-bytes-per-gb`, `m18-compaction-work-per-gb`, `m3-equality-delete-files`, `m2-replication-lag` |
| B6 schema-evolution cost | the five `m17-*` entries |
| B7 batch wall-clock | `m4-batch-wallclock`, `m4-cross-path-tolerance` |
| B9 swap drills | `m1-catalog-swap-hours`, `m1-storage-swap-hours` |

## 7. M18's measured axis, and what stays an extrapolation

**The axis is inherited, not chosen here.** [`docs/cloud-architecture.md` section 6.5](cloud-architecture.md) already fixes it: **cost per GB ingested**, measured locally as objects written, bytes written and compaction work per GB of CDC ingested. Section 6.2 records why: file count rises superlinearly with ingest rate, so S3 request cost and compaction compute are the two lines that dominate a lakehouse bill at 10x, and neither is a function of stored bytes. ADR-0027 carries it. This plan supplies the protocol and the budgets, and does not reopen the choice.

**B5 is the measured experiment.** One arm, the CDC path, at the declared volume, under the streaming profile, with the `rewrite_data_files` procedure in a following window. The three counters are `m18-objects-per-gb`, `m18-bytes-per-gb` and `m18-compaction-work-per-gb`.

**The extrapolation list, recorded explicitly.** Everything below is labelled an extrapolation wherever it appears:

1. Every AWS unit price, dated, from [research 21 to 23](research/).
2. The 10x and 100x volumes, and the per-layer cost growth classification (object storage linear, compute with rate, S3 requests superlinear, catalog metadata superlinear).
3. The 100x architectural changes: the Iceberg metadata plane, Polaris catalog contention, ClickHouse merge throughput, Kafka per-broker partition and replication throughput.
4. Egress and NAT, and the managed-service lines.
5. The EKS control-plane floor, which is arithmetic over a list price and not a measured bill.
6. Anything measured at a reduced volume.

**The limit of the measurement, stated once.** The local run produces three counters per GB of CDC ingested. It cannot produce a cloud bill, because nothing is applied on AWS (ADR-0027), and it cannot produce a 10x curve, because the host cannot hold 10x the data. What it can do is evidence the **shape** of the curve at one point, which is what makes the extrapolation arithmetic rather than assertion.

## 8. The invocation interface

The evidence standard requires one number, one command, and the protocol requires the exact command in the record. Neither can exist before implementation, so the interface is fixed here and the bodies are implementation.

One committed entry point per benchmark at `benchmarks/<name>/run.sh`, with a fixed flag set:

| Flag | Meaning |
|---|---|
| `--arm <name>` | Which pre-registered arm to run |
| `--runs <n>` | The run count, defaulting to the protocol's 5 for latency and 3 for counters |
| `--profile <name>` | The profile to run under, which the script checks against the preflight |
| `--snapshot <id-or-tag>` | The pinned Iceberg snapshot |
| `--out <dir>` | Where the per-run JSON and the summary land |

The script emits one JSON record per run plus a summary, and the raw output lands under the evidence item's `raw/`. The record's `command` field is the literal invocation. **A benchmark whose entry point is not committed cannot produce evidence**, which is the mechanical form of "one number, one command".

The script list, named now so the interface is not invented per benchmark: `benchmarks/b1-layout-sweep`, `b2-two-arm`, `b3-flink-tuning`, `b4-freshness`, `b5-cdc-ingest-cost`, `b6-schema-evolution-cost`, `b7-batch-wallclock`, `b9-swap-drills`.

## 9. Named constraints

1. **Nothing here is measured.** Every figure in this document is a threshold, a control or a declared volume.
2. **No measured result may be fabricated, and no benchmark may be reported without its raw output.** The plan contains plans, thresholds and definitions of done.
3. **A benchmark result that contradicts a layout or architecture decision supersedes that ADR.** It is not explained away in an evidence item, and the ADR is not edited.
4. **The TPC label is a property of the record**, not of the author's memory.
5. **Entitlements are not thresholds.** Resource ceilings live in `deployment/budgets/profiles.yaml` (ADR-0031).
6. **The incident laboratory runs after the benchmarks**, so a benchmark's co-tenancy is never polluted by an injected fault.
7. **The declared volume is the evidence volume** for every volume-dependent claim.

## 10. What this document does not decide

- **The pipeline job graph, branch protection and the delivery path.** [The CI/CD strategy](https://github.com/SoongGuanLeong/de-platform/issues/24) owns those.
- **Which tests are benchmarks.** [The testing strategy](testing-strategy.md) owns that; this document says how one is recorded.
- **The phased implementation roadmap.** Which phase each benchmark lands in depends on the roadmap, which is fog on the map rather than a ticket.
- **The results.** Every number this plan describes is produced during implementation, and none of them exists yet.

---

*Resolved by [the benchmark-plan ticket](https://github.com/SoongGuanLeong/de-platform/issues/21) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Inputs: [`docs/requirements-matrix.md`](requirements-matrix.md), [`docs/completion-bar.md`](completion-bar.md), [`docs/testing-strategy.md`](testing-strategy.md), [`docs/serving-layer.md`](serving-layer.md), [`docs/streaming-jobs.md`](streaming-jobs.md), [`docs/data-contracts.md`](data-contracts.md), [`docs/cloud-architecture.md`](cloud-architecture.md), [`docs/local-development.md`](local-development.md), [`docs/incident-laboratory.md`](incident-laboratory.md) and [`docs/mission/MISSION.md`](mission/MISSION.md).*
