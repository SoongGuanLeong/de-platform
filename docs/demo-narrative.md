# The interview and demo narrative

**Ticket:** [The interview and demo narrative](https://github.com/SoongGuanLeong/de-platform/issues/29), issue #29
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Base:** [the requirements matrix](requirements-matrix.md) section 4 fixes the interview order; [the roadmap](implementation-roadmap.md) section 7 fixes when each load-bearing row is first evidenced; [the completion bar](completion-bar.md) section 13 holds the fourteen gaps; [the incident laboratory](incident-laboratory.md) section 3 holds the live scenario.
**Decision records:** none of its own. Nothing here reverses a decision: the walkthrough order is the requirements matrix's, the phase order is the roadmap's, and the scenario set partitions artefacts the roadmap already produces.
**Deliverables:** mission deliverable 22 (interview/demo scenarios).

---

## 0. Status of this document

A script, not a result. It names the artefact each segment opens and the evidence item that will hold each number. It names no number the platform has not measured, and at the time of writing the platform has measured nothing: every value a segment would show is a declared budget or an arithmetic result over documented defaults, and the segment says which. Where a figure would only become true on a running system, the script names the evidence item and leaves the value out.

## 1. What this document settles

1. **The walkthrough for the load-bearing rows.** Six segments in the requirements matrix's interview order, each a three-beat of objection, artefact and number (section 2).
2. **The scenario set.** Six scenarios run live, one profile at a time, and seven are replayed from committed evidence items (section 3).
3. **The first questions.** The mission's own list, answered one artefact at a time (section 4).
4. **The EKS answer.** What is shown, what is never claimed, and the priced window (section 5).
5. **The gap script.** All fourteen completion-bar gaps, each raised deliberately rather than discovered, in three classes (section 6).

## 2. The walkthrough: six segments in the interview order

### 2.1 The three-beat shape of a segment

Every segment is the same three beats, because an interview is a sequence of objections rather than a tour.

1. **The objection.** The question the interviewer is about to ask, stated in their words, before they ask it.
2. **The artefact.** The one document or evidence item that answers it, opened on screen. One artefact per segment, never two.
3. **The number, or its absence.** The measured figure if one exists, and otherwise the declared budget plus the evidence item that will hold the measurement.

The walkthrough runs in the **interview order** - M5, M7, M2 and M3, M16, M13, then cost - which is [the requirements matrix](requirements-matrix.md) section 4's ranking. It is **not** the build order. The build order is the roadmap's, and it diverges: M2 and M3 are ranked third and first evidenced at Phase 5, because the `streaming` profile declares the RIPE Atlas collector and so the network spine must close under that profile first. **The divergence is stated in segment 3 rather than left to be found**, because a reviewer who notices it and is not told will read it as a contradiction between two documents.

### 2.2 Segment 1 - M5, physical table layout

- **The objection.** "Layout is a config detail. Anyone can copy the Iceberg documentation."
- **The artefact.** The B1 layout-sweep evidence item: three variants of `commerce.gold.fact_lineitem` - **A** monthly partitions sorted `(l_shipdate, l_partkey, l_suppkey)`, **B** daily partitions sorted as A, **C** monthly sorted `(l_suppkey, l_shipdate)` - each carrying write throughput, file count, size distribution, compaction duration and p50 and p95 serving latency, plus the decision record naming which axis won and which lost.
- **The number.** `docs/budgets.yaml`, the B1 budget ids. The figure is produced by the judged run at Phase 3, not by this document.
- **The trap, pre-answered.** Each variant re-materialises the ClickHouse copy, because a changed Iceberg layout changes what ClickHouse reads and the two sides are only comparable when both moved together. And the sweep is **one hot table, three variants**: the claim is one measured axis, not a general theory of layout.
- **Fallback if the live run fails.** The committed B1 evidence item.
- **Owned by.** [the serving layer](serving-layer.md) section 7, [the benchmark plan](benchmark-plan.md) section 4, [the roadmap](implementation-roadmap.md) Phase 3.

### 2.3 Segment 2 - M7, the materialised serving store

- **The objection.** "Materialisation is obviously faster. That is not a finding. And why not Trino?"
- **The artefact.** The B2 two-arm comparison evidence item: read-through against materialised, over C1 to C3 and N1 to N3.
- **The number.** `docs/budgets.yaml`, the B2 budget ids, measured at Phase 3.
- **The trap, pre-answered.** The comparison is **designed to test rather than assume** that materialisation wins on latency, and P3 is excluded from B2 so the freshness effect never confounds the latency effect. Read-through survives in the platform only as this measured comparison arm: [ADR-0003](adr/0003-materialised-serving-store-not-read-through.md) is the decision, and [the system architecture](system-architecture.md) section 7 carries the boundary that there is no federated query engine to reach for.
- **Fallback if the live run fails.** The committed B2 evidence item.
- **Owned by.** [the serving layer](serving-layer.md) sections 3 and 8, [the roadmap](implementation-roadmap.md) Phase 3.

### 2.4 Segment 3 - M2 and M3, end-to-end CDC correctness

- **The objection.** "Exactly-once is a marketing word."
- **The artefact.** The CDC evidence item: the four hard cases each asserted for topic, key and operation - NULL-to-value `UPDATE`, composite-primary-key `UPDATE`, `DELETE`, and out-of-order arrival - with reconciliation by primary key whose count is taken **from PostgreSQL rather than from the pipeline**, and the replication slot's `confirmed_flush_lsn` shown advancing.
- **The number.** The reconciliation output, from the Phase 5 run.
- **The trap, pre-answered.** It is **exactly-once effect**, not exactly-once. Iceberg has no `UPDATE`, so the Flink upsert sink writes a new data file plus a key-only equality delete, while the Spark batch path writes position deletes instead; and Flink checkpoints do not align with Postgres transactions, so the custom keyed operator holds the maximum `source.lsn` per key and drops strictly stale records. A primary-key change is a `DELETE` plus a tombstone plus a `CREATE`, and the tombstone is dropped.
- **The ordering question, pre-answered.** This is ranked third and evidenced fifth. The reason is the `streaming` profile's declared service set, not a preference: state it here.
- **Fallback if the live run fails.** The committed CDC evidence item, plus the LSN operator's unit test, which has run since Phase 1.
- **Owned by.** [the streaming job designs](streaming-jobs.md), [ADR-0011](adr/0011-flink-native-iceberg-sink-for-cdc.md), [ADR-0013](adr/0013-lsn-ordering-in-a-stateful-operator.md), [the roadmap](implementation-roadmap.md) Phase 5.

### 2.5 Segment 4 - M16, the incident laboratory

- **The objection.** "Anyone can wire an alert. The question is whether it fires when you did not arrange it."
- **The artefact.** The six incident records, each carrying the eight links, real machine timestamps, an unprompted alert at a real destination, measured MTTD and MTTR, a runbook and a blameless postmortem. **Live: incident 1, the Kafka consumer lag spike**, which is the only incident [the incident laboratory](incident-laboratory.md) section 3 admits as a live-stack injection.
- **The number.** MTTD and MTTR from the drill.
- **The trap, pre-answered.** **MTTD ends at the alert delivery timestamp, not at Alertmanager firing.** And the live injection is exactly one incident: the other five need their own session, one at a time, never co-resident with `benchmark`.
- **Fallback if the live run fails.** The committed incident 1 record. Note in passing that eight further scenarios were demoted to correctness tests rather than deleted, and that partial pipeline execution is out.
- **Owned by.** [the incident laboratory](incident-laboratory.md), [the roadmap](implementation-roadmap.md) Phase 8.

### 2.6 Segment 5 - M13, governance that stops something

- **The objection.** "Governance in a portfolio is usually a README."
- **The artefact.** The gate's own evidence: a failing input-evaluable check on the batch path means the downstream asset never writes; the streaming half fails into a dead-letter sink plus a Dagster sensor that savepoints and stops the job; the quarantine table, the check-result store, and a false-positive rate counted over fault-detection checks only.
- **The number.** The quarantine count and the false-positive rate, from the Phase 2 and Phase 4 runs.
- **The trap, pre-answered.** Severity is declared per instance and there is exactly one action per severity - warn records, quarantine diverts and continues, fail publishes nothing - and the gate escalates only on a declared quarantine budget. Enforcement is the claim; the taxonomy is the mechanism.
- **Fallback if the live run fails.** The committed gate evidence item.
- **Owned by.** [governance and data quality](governance-and-data-quality.md), [ADR-0016](adr/0016-gate-on-input-and-promote-through-a-branch.md), [the roadmap](implementation-roadmap.md) Phases 2 and 4.

### 2.7 Segment 6 - M18, cost, the deliberate sixth

- **The objection.** "What does this cost, and what would you remove first?"
- **The artefact.** [the cloud architecture](cloud-architecture.md), with its two tfvars arms, its cost model and the extrapolation list.
- **The number.** Exactly one measured axis: B5, the CDC ingest cost, at Phase 6. Everything else is arithmetic over documented defaults, and the extrapolation list says which rows those are.
- **The trap, pre-answered.** **The EKS control plane at $0.10 per cluster-hour is the only line item that cannot reach zero**, so the platform is free to run as a design, free as a demo only inside the credit window, and genuinely $0 only on the local stack. The minimal arm is $0.337 per hour, $2.02 for a six-hour session in ap-southeast-5; the reference arm is 3.45x it at $1.164 per hour.
- **Fallback if the live run fails.** n/a - this segment runs no live stack.
- **Owned by.** [the cloud architecture](cloud-architecture.md), [ADR-0027](adr/0027-self-host-what-the-platform-operates.md), [the roadmap](implementation-roadmap.md) Phase 6.

## 3. The scenario set: what runs live, what is replayed

The batch and streaming peaks cannot be co-resident (6976 MiB against 7168 MiB, against an enforceable 7168 MiB), so **a demo is a sequence of profile runs with declared teardowns, not one continuous stack**. Four sessions, and no scenario needs two path profiles at once.

| Session | Profile | Host tier | What it carries |
|---|---|---|---|
| **A, the batch session** | `batch`, reduced permitted | tier 2 or better | the commerce and network batch scenarios, then the batch benchmark replays |
| **B, the streaming session** | `streaming`, reduced permitted | tier 2 or better | the CDC and freshness scenarios, then the streaming benchmark replays |
| **C, the incident session** | a path profile, **non-reduced** | **tier 1 only** | the live lag-spike drill, then the other five incidents replayed |
| **D, the static session** | none | n/a | the upgrade drill and the cloud static checks |

| # | Scenario | Session | Live or replayed | Why |
|---|---|---|---|---|
| **S1** | C2, the fan-out demonstration: top suppliers by revenue against the `partsupp` trap | A | live | a query, and it is the M6 demonstration |
| **S2** | the data-quality gate quarantining a batch pipeline | A | live | enforcement is the claim, and a quarantined row is the evidence |
| **S3** | N2, probes whose nearest postcode has been terminated | A | live | the SCD2 point-in-time lookup joined to the spatial lookup |
| **S4** | the four CDC hard cases | B | live | the hardest thing on the list |
| **S5** | O1, orders in flight by warehouse right now | B | live | the only freshness-sensitive query, and the streaming exception's justification |
| **S6** | incident 1, the Kafka consumer lag spike | C | live | the only incident the live stack can carry with all eight links genuine |
| **R1** | B1, the layout sweep | A | replayed | its own judged run, with a proven reset |
| **R2** | B2, the two-arm comparison | A | replayed | same |
| **R3** | B6, B7 and B9: schema-evolution counters, batch wall-clock, the two swap drills | A | replayed | same |
| **R4** | B3 and B4: the tuning record and freshness | B | replayed | same |
| **R5** | B5, the CDC ingest cost | B | replayed | same |
| **R6** | incidents 2 to 6 | C | replayed | each needs its own tier-1 session |
| **R7** | the ClickHouse upgrade drill and the cloud static checks | D | replayed | no profile runs at all |

**The rule that separates the two columns.** A scenario runs **live** when it fits one profile, completes inside a session, and its evidence is a state rather than a statistic. It is **replayed** when it needs a judged run with a committed budget and a proven reset, or its own dedicated session. A benchmark is never run live for an audience, because a benchmark's co-tenancy must be the declared set and an audience is not in it.

**No scenario is live-only.** Every live scenario names the committed evidence item that stands in if the run fails, so a failed live run is a labelled fallback rather than a broken demo.

## 4. The sceptic's first questions

Each answer is one sentence and one artefact. The rule is that no answer needs a second document opened.

| The question | The answer in one line | The artefact |
|---|---|---|
| Is any of this real, or is it all documents? | Nothing is claimed as complete until it is a registered instance with a behaviour evidence item behind it, and the register ships empty. | [the completion bar](completion-bar.md) section 5 |
| Why Iceberg? | Open table format, the only component here that is genuinely irreplaceable, and the one the posting names. | [the technology selection](technology-selection.md) |
| Why Kafka? | The only other irreplaceable component, and the CDC transport the posting names. | [the technology selection](technology-selection.md) |
| Why Flink instead of Spark Streaming? | The upsert sink is native in Flink and the CDC path needs a stateful per-key operator, which the batch engine cannot give it. | [the streaming job designs](streaming-jobs.md) |
| Why ClickHouse? | It is the posting's named serving layer, and it is the arm that won a measured comparison rather than an assumed one. | [the serving layer](serving-layer.md) section 8 |
| How do you handle late events? | A two-minute out-of-orderness watermark, a one-minute tumbling window, five minutes of allowed lateness, and a side output for anything past it. | [the streaming job designs](streaming-jobs.md) |
| How do you guarantee idempotency? | You do not; you make the effect idempotent, by keying on a content hash and holding the maximum LSN per key. | [the streaming job designs](streaming-jobs.md) |
| How do you recover from failure? | Checkpoint, savepoint, restore, and a permanent fix that is a committed change with a SHA rather than a restart. | [the incident laboratory](incident-laboratory.md) section 4 |
| How do you detect data corruption? | Five check kinds with severity per instance, and a quarantine table that holds what they divert. | [governance and data quality](governance-and-data-quality.md) |
| How do you handle schema evolution? | Format v2 with a documented matrix for add, rename, drop and type change, and a contract version that breaks by major. | [data contracts](data-contracts.md) |
| How do you optimize an Iceberg table? | Partitioning, sort order and compaction, measured as three variants of one hot table rather than argued. | [the benchmark plan](benchmark-plan.md) section 4 |
| How do you optimize a ClickHouse query? | The layout baseline is scoped to nine named queries, and the ordering is named as a hypothesis for the sweep to test. | [the serving layer](serving-layer.md) sections 7 and 11 |
| How do you monitor Kafka, Flink and Spark? | Dashboards as code over throughput, consumer lag, checkpoint duration, compaction backlog, DQ pass rate and query latency, one alert rule per declared SLO. | [the roadmap](implementation-roadmap.md) Phase 8 |
| How would you deploy this to EKS? | Authored and statically validated, never applied as evidence; the only apply is a human inside a priced, torn-down window. | section 5 below |
| How would this architecture change at 10x or 100x? | One axis is measured and the rest is a labelled extrapolation, and the extrapolation list says which rows. | [the cloud architecture](cloud-architecture.md) section 6 |
| What would you remove if cost became a problem? | The reference arm's NAT, ALB and autoscaler first, then everything between Iceberg and Kafka, which is at most thirty days to swap. | [the technology selection](technology-selection.md) |
| Twenty components: is this a technology museum? | Every component carries a rejected alternative and a swap cost, and only Iceberg and Kafka are irreplaceable. | [the technology selection](technology-selection.md) |
| Is this the Olist project again? | No. The prior repository is reference and design evidence only, and no code is copied. | [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md) |
| Why not MinIO? | It went source-only and the repository was archived in April 2026, so it fails the longevity rubric on the observable-activity floor. | [the technology selection](technology-selection.md) |
| Why not Terraform? | BUSL since 2023, so OpenTofu, and the deviation from the posting's wording is recorded rather than glossed. | [ADR-0005](adr/0005-use-opentofu-instead-of-terraform.md) |
| Show me a number. | Every number is either a budget committed before its measurement or an arithmetic result over documented defaults, and no figure measured on TPC data is ever a TPC Benchmark Result. | [the benchmark plan](benchmark-plan.md) section 2.7 |

## 5. How the platform would be deployed to EKS

This is the answer the mission names explicitly, and it is answered with **authored artefacts rather than a running cluster**. The distinction is stated first, not conceded under questioning.

**What is shown.**

- The OpenTofu module set for the S3 layout, the IAM roles and policies, the VPC and subnets, the security groups, the RDS instance class and parameter group, and secrets handling, with the `reference` and `minimal` tfvars profiles and a committed `.terraform.lock.hcl`.
- `tofu validate`, `tflint`, `kubeconform`, the policy scan, the rendered-manifest drift check, and the committed rendered Helm manifests, with `image.registry`, `image.repository` and `image.digest` as values.
- The `images` job building the one self-built image, Marquez on arm64, because it is the single amd64-only component.

**The shape, in one breath.** Self-host on EKS everything the platform operates; managed only for the primitives, S3 and RDS. Graviton `m7g` throughout. IRSA with one role per component and no node-level S3 or Secrets Manager permissions. The vended-credential boundary mirrors the measured SeaweedFS result, with non-nesting prefixes enforced statically. Two arms: `minimal` at 2 AZs, public subnets, one managed node group, 2 to 3 `m7g.large`, no NAT, no ALB and no autoscaler; `reference` at 3 AZs with private subnets, NAT per AZ, separate general and data node groups, an ALB, and 3.45x the minimal arm.

**What is never claimed.** No real S3, no IAM policy evaluation, no VPC routing, no RDS failover, point-in-time recovery or read replicas, no EKS scheduling or rolling upgrade, and no Helm release. The only apply anywhere is a human running the demo runbook inside a priced, time-boxed, torn-down window, and **that is not an evidence item**. In its place: the static checks, and an explicit local-versus-cloud diff.

**The priced window, with its arithmetic.** The EKS control plane at $0.10 per cluster-hour is the only line item that cannot reach zero. The minimal arm prices at $0.337 per hour, so a six-hour session costs $2.02 in ap-southeast-5.

**What changes at 10x or 100x.** The extrapolation list, with its one measured axis, and nothing else. Production scale is completion-bar gap 1, and it is raised here rather than discovered later.

## 6. The honest-gap script

All fourteen gaps in [the completion bar](completion-bar.md) section 13 are raised by the script. None is left to be discovered, and the script is a standing section the walkthrough can be taken to at any point rather than a closing slide. The gaps fall into three classes, and the class decides the tone.

**Class 1 - self-disclosed before they are asked.** These are the gaps a probing question would expose, so the script raises them where the relevant claim is made, unasked.

| Gap | Raised in | How it is raised |
|---|---|---|
| 1. Production scale | segment 1 and segment 6 | "Every layout and cost conclusion beyond the single measured axis is extrapolation, and here is the list of which rows those are." |
| 3. AWS | segment 6 and section 5 | "Nothing here was deployed. Here is what is statically validated instead." |
| 11. Runtime parity beyond one provider | the bring-up, before session A | "The runbook targets one compose provider and has not been executed, and six images are unverified under podman until a runtime check actually runs." |
| 12. Unknown downstream consumers | segment 5 | "The regression guarantee covers declared consumers only." |
| 13. True multi-broker failure | segment 4 | "Single-node Kafka cannot evidence broker loss beyond a restart." |

**Class 2 - named with the substitute in the same breath.** These are real shortfalls, and each is raised where its substitute is already on screen.

| Gap | Raised in | The substitute named with it |
|---|---|---|
| 2. On-call as a human practice | segment 4 | the eight-link incident chain, as a property of the platform |
| 4. Open-table-format failure modes a laptop cannot reach | segment 1 | the reachable subset, and the admission that the rest is reasoning |
| 8. Continuous ClickHouse upgrade testing | segment 2 | a pin plus one upgrade drill, against monthly backward-incompatible releases |
| 9. Catalog-swap equivalence | segment 6 | the measured swap cost, and the CI assertion that no proprietary admin API is used |
| 10. SeaweedFS STS is not AWS STS | section 5 | the credential flow's shape, and the statement that AWS policy semantics are unevidenced |
| 14. Concurrency and backpressure at real throughput | segment 3 | engineering behaviour, with injection synthetic and the query set bounded |

**Class 3 - named without apology.** These are scope boundaries, not shortfalls: the destination never included them, so the absence is the decision.

| Gap | Raised in | Why no apology |
|---|---|---|
| 5. GDPR | segment 5 | technical measures only; the phrase "GDPR-shaped" is used deliberately |
| 6. Multi-region and cross-account | segment 6 | reasoning only, and the destination is one region by decision |
| 7. Formal compliance programmes | segment 5 | out of scope by decision |

**Three further surfaces are raised with the same discipline**, because a sceptic who reads the deliverable map will find them: the two limitations carried from the Iceberg v3 review (the read-through REST path, now closed by B2, and the unverified Flink v3 upsert writer), and the three deliverables with no owning document (observability, reliability and the complexity assessment, each decided and distributed).

## 7. Named constraints

1. **This is a script, not a result.** It names no measurement the platform has not made; where a figure would be a result, it names the evidence item and leaves the value out.
2. **The walkthrough order is the interview order**, and where it diverges from the build order the divergence is stated rather than hidden.
3. **No scenario needs two path profiles at once.** The batch and streaming peaks cannot be co-resident, so a demo is a sequence of profile runs with declared teardowns.
4. **Every live scenario names its fallback.** A failed live run is a labelled fallback, not a broken demo.
5. **No new component, no new profile, no new benchmark.** The narrative introduces no artefact the roadmap does not already produce.
6. **All fourteen gaps are raised.** None is left to be discovered.
7. **No em dashes, use a hyphen.**

## 8. What this document does not decide

- **The demo runbook.** [the roadmap](implementation-roadmap.md) Phase 10 owns the executable steps this narrative is spoken over. The narrative names the runbook; it is not one.
- **The register's instance ids and the evidence items' contents.** Those are written as the instances land, which is what makes the numbers in section 2 placeholders rather than commitments.
- **The local-versus-cloud diff.** [the local development architecture](local-development.md) owns the diff; section 5 only points at it.
- **The presentation framing.** [the proposal](../PROPOSAL.md) and [the README](../README.md) own the ten-minute surface and the route. This document is what is spoken over them.
