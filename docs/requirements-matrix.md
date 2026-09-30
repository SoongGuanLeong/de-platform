# The requirements matrix

**Ticket:** [The requirements matrix: what the platform must actually demonstrate](https://github.com/SoongGuanLeong/de-platform/issues/4)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.

---

## 1. What this document is

One row per discrete platform requirement in the posting, in the posting's own order: seven key responsibilities, then the requirements, then the nice-to-haves. One addition beyond the posting: vendor neutrality, which the posting's About-the-role paragraph stakes out but does not enumerate.

The mission's matrix was keyed on the posting's named *technologies*. This one is keyed on *requirements*, so the stack mapping moves into the `Platform component` column. The technology rows survive there.

**The rule that governs every cell: nothing here is a result.** No cell contains a measured number, because nothing is built while the map is open. The `Demonstration` column specifies the evidence that will be produced, and the evidence standard in section 3 fixes what will make that evidence believable. Thresholds and definitions of done are permitted; outcomes are not.

### Scope filter

Rows are only included where the subject is the platform or how data flows through it. Three classes of posting clause are **excluded by decision**, and section 5 records them:

- Claims about experience and duration: "6+ years", "deep, hands-on experience on data engineering practices".
- Claims about personal conduct: "excellent communication and stakeholder-management skills".
- Claims about a person or an organisation rather than a system: on-call, "stakeholder management".

Nothing in this matrix stands in for a claim about the person who built it. The matrix is about the platform.

### `Status` legend

| Value | Meaning |
|---|---|
| `specified` | The capability and its evidence are settled here; the component may or may not be decided yet. |
| `pending component decision` | The capability is wanted, but the component that would deliver it is still an open question on the map. |
| `not demonstrable` | Kept for a requirement the technology honestly cannot deliver, with the substitute named. Section 6. |
| `out of scope` | Deliberately not built. A positive boundary, recorded in section 7. |

---

## 2. The matrix

| ID | Job requirement | Required capability | Platform component | Demonstration (evidence to be produced) | Status |
|---|---|---|---|---|---|
| **M1** | "building a possible vendor neutral lakehouse" (About the role) | Every layer is replaceable without a rewrite, so only Iceberg and Kafka are irreplaceable. | Polaris (Iceberg REST catalog) over SeaweedFS; OpenLineage emitted by Dagster; dashboards as code in Git. | Two timed swap drills, each producing a run log with wall-clock hours and the diff required: catalog Polaris → Lakekeeper, storage SeaweedFS → RustFS. Neither drill touches anything else in the platform. A CI assertion that no code path calls a Polaris-proprietary admin API, which is the precondition that makes the catalog swap cheap. | specified |
| **M2** | Own, operate and harden the streaming platform for **correctness**; production experience with an open table format | Change events are captured from a live source without loss, and the destination converges on the correct state when arrival is duplicated or reordered. Ordering is not claimed: per-key order is a consequence of keying, and it is not preserved across a partition-count change or a primary-key update. | Debezium CDC → Kafka (KRaft); Apicurio schema registry; live PostgreSQL as the CDC source. Every event carries the source LSN as an ordering token, and the sink applies last-write-wins against it. | An assertion suite over real TPC-C binlog traffic covering NULL → value UPDATE, composite-PK UPDATE, DELETE, and out-of-order arrival, each checked for the expected topic, key and operation. An idempotence test: replay a partition from offset 0 and assert an identical Iceberg snapshot state. A convergence test: feed a deliberately shuffled and duplicated event stream and assert an identical final state. A reconciliation asset that diffs source against target by primary key. A schema-change test: add a NOT NULL column upstream, restart the connector, assert topic and downstream survive. | specified |
| **M3** | Build and tune the processing layers: **real-time streaming jobs in Flink**, including job/state tuning | Streamed changes land in Iceberg with exactly-once effect on the committed table state, achieved by checkpoint-id idempotency in the sink rather than by transactional writes to Iceberg. Iceberg has no UPDATE: an upsert is a new data file plus a key-only equality delete, so correctness is convergence plus a bounded delete-file count that compaction collapses. Source-transaction atomicity is not claimed, because Flink checkpoints do not align with Postgres transaction boundaries. | Flink; Iceberg sink in upsert mode with declared equality fields and table format v2 or later. Engine and API choice is a later ticket. | A kill-mid-checkpoint test: restore and assert an identical final state. A kill-after-checkpoint-before-commit test: assert no partial state is visible to a concurrent reader. A row count asserted against an independent count from Postgres rather than a number the pipeline produced. A redelivery test proving upsert mode absorbs duplicate delivery from Debezium while append mode does not. A compaction record showing the equality delete-file count stays bounded. A tuning record changing at least three of {checkpoint interval, checkpoint timeout, parallelism, state backend, sink flush size}, each with its measured effect on throughput, checkpoint duration and end-to-end latency. A written watermark and lateness policy, and the reason for each bound. | specified |
| **M4** | Build and tune the processing layers: **batch transformations in Spark** (silver/gold models) | Batch models are built on Iceberg through the same catalog as the streaming path, and are correct rather than merely finishing. | Spark (PySpark, Python 3.12) reading and writing Iceberg. | A gold model answering a named business question, with its result asserted against an independently computed expected value. A reconciliation check: a metric computed by the Flink path and by the Spark path agrees within a stated tolerance, which is the only honest proof the two paths share a definition. Recorded batch wall-clock and resource use at a stated data volume. | specified |
| **M5** | **Design data models and physical table layout (partitioning, sort order, compaction, retention) to balance write throughput, query performance, and storage cost** (stated emphasis) | Partitioning, sort order, compaction and retention are chosen as a trade-off and the trade-off is measured, not asserted. | Iceberg table properties, partition transforms, sort order, `rewrite_data_files` / `rewrite_manifests`, snapshot expiry. | At least three layout variants of one hot table. Each carries a recorded protocol: data volume, engine versions, exact command, raw output committed. For each variant: write throughput, file count and size distribution, compaction duration, and p50/p95 ClickHouse query latency. A decision record naming which axis won and which axis lost, and what was given up. A retention policy with storage reclaimed by snapshot expiry measured. | specified |
| **M6** | Expert SQL, dimensional/data modeling | A model an analyst would recognise, and SQL good enough to be worth reading. | Iceberg gold tables; hand-written SQL; the ClickHouse view layer. | A star schema documented grain by grain in the data dictionary, with conformed dimensions and SCD handling named explicitly. A slow-query record: at least three queries rewritten, each with before and after `EXPLAIN` and measured latency. One query where the correct grain is the whole point, shown next to the fan-out-trap version of itself. | specified |
| **M7** | **Develop and optimize the serving layer (ClickHouse over Iceberg) so analysts and product teams get fast, reliable query access** | The serving store is fast under a declared budget, and stays fast, with the performance coming from a tuned physical layout rather than from reading Iceberg in place. Two architectures are measured rather than assumed: catalog read-through of Iceberg, which is read-only and gets none of MergeTree, and materialised MergeTree tables, which is the architecture adopted. | MergeTree tables in ClickHouse materialised from Iceberg by Spark and Flink, with catalog read-through retained as the comparison arm. The read-through path is read-only and in beta. | The named analyst query set from M9, with p50/p95 budgets declared before measurement, measured at a stated volume and concurrency, run against **both** arms with the delta recorded. A declared physical layout naming the `ORDER BY` key, projections, codecs and TTL, with the reason for each. One deliberately bad query diagnosed from `system.query_log` and fixed, before and after. A serving-reliability test: interrupt the serving path mid-session and assert the documented recovery behaviour. | specified |
| **M8** | Real-time OLAP experience (nice to have) | Change events reach the materialised serving copy in near-real time under a stated objective. This is the cost side of M7's architecture: the read-through arm is fresher but slower, the materialised copy is faster but lags, and this row measures that lag. | Streaming ingestion from Kafka into the materialised MergeTree copy. The mechanism is an open choice between Flink writing into ClickHouse and ClickHouse's Kafka engine with a materialised view; whichever is chosen is recorded with the reason. | An end-to-end latency measurement from source commit timestamp to row visible in the materialised ClickHouse copy, p50 and p99 over a stated window, with the derivation method for lateness stated and the threshold declared before the run. The same measurement recorded on the read-through arm as the freshness baseline the materialised copy is traded against. | specified |
| **M9** | **Collaborate with data analysts, product teams, and backend engineers to ensure discoverable, well-documented, and usable data access** | The people downstream can find the right table and use it correctly without the author in the room. | Polaris catalog; data dictionary; written contracts; persona query sets. | Three named analyst personas with their actual questions, each with a latency budget. A discoverability test: someone unfamiliar with the platform is given a business question and must find the right table unaided; time-to-table and wrong-table rate recorded. A data contract per gold table. A backend-facing interface contract with explicit versioning rules. | specified |
| **M10** | Establish and enforce data governance: **catalog organization, access control** | Two independent controls with the seam between them documented. Polaris governs Iceberg-native access and vends a per-table, prefix-scoped storage credential; ClickHouse users, roles and row policies independently govern the materialised serving copy. Polaris authorises metadata only and enforces no column-level or row-level access, so column-level control exists only in ClickHouse. The storage credential is the real data-layer boundary. | Polaris namespaces, roles and principals over SeaweedFS STS with `stsUnavailable` left unset so vending is active; ClickHouse users, roles and row policies on the serving copy. | A namespace and role layout diagram. A written authorisation map naming which system governs which path, and stating that Polaris enforces no column-level access. An enforcement suite where a denied principal is refused and the refusal is attributable, with the mechanism named per system: ClickHouse records the querying user in `system.query_log`, and Polaris returns 403 and records the request in its access log with the authenticated principal. Polaris emits no denial event of its own (ADR-0030). A column-level test on a PII column in ClickHouse, the only engine that can enforce it. A measured credential-scope test: vend for table A, assert a read of table B's prefix is refused with AccessDenied, and record the unscoped baseline that proves the denial comes from the policy. The generated session policy size is asserted against the 2048-byte limit. A documented scope limitation: the boundary is a prefix, not a table identity, so overlapping or nested table locations widen it, and a broad storage credential configured inside ClickHouse bypasses catalog authorisation entirely. | specified |
| **M11** | Establish and enforce data governance: **data lineage** | Lineage that is emitted by the pipeline rather than maintained by hand. | OpenLineage emitted from Dagster, Spark and Flink; a Marquez-compatible sink. | A captured column-level graph for one gold column, spanning CDC topic → silver → gold → ClickHouse view, with the emitting run id tied to the Dagster run and the OpenLineage event id. A test asserting lineage is emitted on the streaming path as well as the batch path. | specified |
| **M12** | Establish and enforce data governance: **retention/compliance** | A retention policy that is actually applied, and demonstrably not over-applied. | Iceberg snapshot expiry; a Dagster retention asset; ClickHouse TTLs. | A policy per data class with its rationale. A dry run reporting what would be deleted, then the real run, then an assertion that expired snapshots are gone **and** that a snapshot inside the retention window survived. Storage reclaimed, measured. | specified |
| **M13** | Establish and enforce data governance: **automated data-quality checks** | Checks with severity that stop or quarantine a pipeline. A dashboard of green ticks is not enforcement. | Custom check framework; quarantine tables; Dagster gate. | A check catalogue where each check declares a severity and each severity declares its action (warn / quarantine / fail). A test proving a deliberately corrupted batch is quarantined and never reaches gold. A test proving a critical failure blocks the downstream Dagster run. A measured false-positive rate over N consecutive clean runs. | specified |
| **M14** | Workflow orchestration (nice to have) | DAGs that are idempotent, re-runnable and backfillable. | Dagster. | A dated-window backfill asserting the result is identical to the original run. A re-run of a failed run asserting no double counting. Configured retries and backoff, with one failed-then-recovered run recorded. | specified |
| **M15** | A production-reliability mindset: **monitoring, alerting**; observability stacks (Prometheus, Grafana, Alertmanager) | The platform reports its own health, and alerts fire before a human notices. | Prometheus, Grafana, Alertmanager, plus pipeline-level metrics. | Dashboards as code in Git covering throughput, consumer lag, checkpoint duration, compaction backlog, DQ pass rate, query latency. Declared SLOs with one alert rule per SLO, each shown firing in a recorded drill. Alert routing to a real destination with the delivery timestamp. | specified |
| **M16** | A production-reliability mindset: **incident root-cause analysis** | The full chain from detection to permanent fix, demonstrated end to end. | The incident laboratory. | Every incident carries all eight links (Detection, Alert, Diagnosis, Root cause, Mitigation, Recovery, Data correctness verification, Permanent fix) with real timestamps, an alert that fired unprompted, measured MTTD and MTTR, and a runbook a stranger can follow. At least one scenario injected into the running stack rather than a test double. One blameless postmortem each. | specified |
| **M17** | Production experience with an **open table format / lakehouse** | Operating an open table format, not only reading one: schema evolution, snapshot and branch semantics, rollback. | Iceberg; Polaris. | A schema-evolution matrix covering add-optional, add-required-with-default, rename, drop and type change, each applied with its read paths verified. add-required-with-default is demonstrated on `commerce.gold.fact_lineitem`, which is Iceberg format v3 with copy-on-write row-level operations so that it carries no deletion vector and stays readable by the pinned ClickHouse 26.8 LTS; the column is added through the Iceberg API because Spark SQL cannot express it (ADR-0025). A time-travel and rollback to a prior snapshot id. A measured cost for each operation: metadata growth, commit latency, orphan-file cleanup. Design in `docs/data-contracts.md`, thresholds in `docs/budgets.yaml`. | specified |
| **M18** | Harden for **cost at scale**; balance ... storage cost; cost optimization for cloud data/streaming platforms (nice to have) | Knowing what becomes expensive first at 10×, and what must change at 100×, with one axis genuinely measured rather than all of them reasoned. | Local Spark/Flink/Iceberg/ClickHouse for measurement; explicit cost arithmetic for the model. | A cost model naming, per layer, the unit cost driver and the first thing to get expensive at 10×, with the arithmetic shown and assumptions dated. A 10× and 100× reasoning section naming the required architectural change. **One** measured experiment on **one** axis, protocol recorded. An explicit list of which conclusions are extrapolations. | specified |
| **M19** | Solid AWS fundamentals: **S3, IAM, VPC/networking, and RDS**; AWS, Amazon EKS, Helm | An AWS topology designed correctly enough to be reviewable, even though it is never applied as evidence. | OpenTofu (never Terraform); Helm charts covering the streaming ingestion path into the serving store; SeaweedFS exercising the S3 API and the STS API locally. | OpenTofu modules for S3 layout, IAM roles and policies, VPC and subnets, security groups, the RDS instance class and parameter group, and secrets handling - committed and `tofu validate`d in CI. Helm charts for the EKS deployment, authored and never applied as evidence. A written local-versus-cloud diff naming what the local run cannot exercise, including that SeaweedFS STS is not AWS STS: the local run uses a permissive trust policy and no IAM policy simulation, so it evidences the shape of the credential flow rather than AWS policy semantics. Evidence that the S3 API and the STS API are genuinely exercised by the local stack: Polaris vends a per-table credential against SeaweedFS STS, and a read outside the vended prefix is refused with AccessDenied. | specified |
| **M20** | Security and compliance frameworks (GDPR and similar) (nice to have) | PII is identified, classified and access-controlled, with the enforcement mechanism named per path rather than assumed uniform. Polaris enforces table-level access on the Iceberg-native path; column-level enforcement exists only in ClickHouse. Technical measures only. | Column-level classification; Polaris table-level RBAC; ClickHouse column-level grants and row policies on the materialised serving copy; masking in the serving layer. | A PII inventory for the chosen datasets naming each column, its purpose and its treatment. A test proving an unauthorised principal is refused at **table level** through the Polaris-governed Spark path, and at **column level** through ClickHouse on the serving copy, where `GRANT SELECT(col)` is the mechanism. A stated limitation: Polaris cannot enforce column or row level, so any column-level control on the Spark path would need a named alternative such as a restricted view, and this matrix does not claim one. A data-subject deletion path traced end to end on one table. | specified |
| **M21** | Proficiency in at least one of **Python, Java, or Scala** | Pipeline and streaming code in a language the posting names. | Python for Dagster, checks, lineage and tooling. Java for Flink. Scala deliberately not used. | The code, plus one non-trivial algorithmic component per language with its test suite: a stateful or custom Flink operator in Java, the check framework in Python. An ADR recording why Scala was declined. | specified |
| **M22** | Multi-region and/or cross-account data platform experience (nice to have) | Not attempted. | none. | A written reasoning section only: what breaks, what the topology would be, what it costs. No deployment and no claim of experience. | out of scope |
| **M23** | Stay current with the lakehouse ecosystem and propose targeted improvements | Judgement about the ecosystem, evidenced by dated research and recorded decisions. | `docs/research/`; `docs/adr/`. | The longevity audit, with dated and cited evidence per component against a stated rubric. One ADR per substitution or rejection, each recording the trade-off. A named watch-list with a re-review trigger. | specified (largely satisfied by `docs/research/` already) |

**Ordering.** M23 is last because the research behind it is done, not because it is unimportant.

---

## 3. The evidence standard

One standard applies to every row. A demonstration is evidence only if all of the following hold.

The standard is operationalised by [`docs/completion-bar.md`](completion-bar.md), which turns these seven rules into a per-class definition of done, a fixed evidence-item schema, and a capability register the CI validates without re-running evidence.

1. **Inspectable without the author.** A clone plus a command. If it needs me in the room, it is a demo, not evidence.
2. **A benchmark has a recorded protocol.** Hardware as actually configured (12 CPU, 7-8 GB usable RAM, 231 GB disk), data volume, engine versions, the exact command, and the raw output committed. Repeatable by a script, not by memory.
3. **Every number is measured here and labelled as such.** A number without a source artifact does not go in the document.
4. **Thresholds are declared before the measurement.** A budget written after seeing the result is a description, not an objective.
5. **Diagrams and prose are evidence for design decisions only.** Never for a performance or correctness claim.
6. **An incident is not evidence until all eight links exist with real timestamps**, the alert fired unprompted, and a post-recovery correctness check ran as part of the incident.
7. **One number, one command.** A figure that cannot be regenerated by a command in the repository is a figure I typed.

---

## 4. Interview-facing ordering

If only five things can be excellent, these five, in this order.

1. **M5, physical table layout.** The posting's stated emphasis, and the row that answers "how do you balance write throughput, query performance and storage cost" with measurements rather than opinions.
2. **M7, the materialised serving store.** The posting's second emphasis, and the one most easily faked with synthetic benchmarks. Real personas and real query sets are the difference, and the two-arm comparison is what makes the numbers defensible.
3. **M2 + M3, end-to-end CDC correctness.** Debezium → Kafka → Flink upsert into Iceberg, proven against NULL-to-value updates and composite keys. The hardest thing on the list, and the reason TPC-C was chosen over everything else.
4. **M16, streaming reliability and the incident laboratory.** The eight-link chain, with unprompted alerts and measured MTTD/MTTR.
5. **M13, governance that stops something.** A DQ gate that actually quarantines a pipeline. Documentation of governance is cheap; enforcement is the claim.

**Cost (M18) is a deliberate sixth.** It is named three times in the posting, so it cannot be ignored, but it is a document and documents are cheap to make excellent. Items 1 to 3 are demonstrations that cost real engineering time, which is why they rank above it. Recorded here so the ordering reads as a decision rather than an oversight.

**Supporting, not load-bearing:** M6, M9, M10, M11, M12, M14, M15, M17, M19, M20, M21, M23.

---

## 5. Excluded by decision, and the substitute

These posting clauses are deliberately absent from the matrix. They are recorded here so the omission is legible rather than an oversight.

| Posting clause | Why excluded | What stands in its place |
|---|---|---|
| 6+ years in data engineering or backend data-intensive roles | A claim about a person's history. No artifact can evidence it, and manufacturing one would be a lie. | Nothing. It is a claim the CV makes and the interview tests. |
| Deep, hands-on experience on data engineering practices | An experience claim, not a capability. | The 21 specified rows. The practice is visible in the artifacts; the duration is not. |
| Excellent communication and stakeholder-management skills | A personal trait. | Nothing, deliberately. M9 evidences the *outputs* of collaboration - discoverability, documentation, usable access - not the skill. |
| On-call, as a person or a rotation | Belongs to a person and an organisation, not to a platform. | M16's eight-link incident chain, executed against a runbook a stranger can follow. See section 6.2 for what that still does not prove. |
| Production scale ("at scale", "cost at scale") | See section 6.1. | M18: a cost model plus one measured axis, with extrapolations labelled as extrapolations. |

---

## 6. Where the technology cannot honestly deliver

The posting asks for things a 12-CPU pod with 7-8 GB of usable RAM and 231 GB of disk cannot evidence. Said plainly, per the ticket.

### 6.1 Scale

Every layout and cost conclusion beyond the single measured axis is extrapolation. Iceberg planning cost, per-partition file counts, compaction behaviour and ClickHouse part merging at the volumes a real deployment reaches are reasoned, not observed. I can demonstrate that I understand the scaling problem and that I measured one dimension of it. I cannot demonstrate a platform that runs at scale. The posting's §25-equivalent guidance agrees: demonstrate the reasoning, do not build the system.

### 6.2 On-call

The incident laboratory demonstrates that the *system* detects a fault, alerts on it, and can be recovered by a stranger following a runbook. It never demonstrates a human being woken at 03:00, triaging under pressure, or an actual pager. "Production-reliability mindset" is evidenced here as a property of the platform. The human half is not evidenced at all.

### 6.3 AWS

The OpenTofu modules are authored and `tofu validate`d. They are never applied as evidence. So there is no evidence any of it works in a real account: no real S3, no real IAM policy evaluation, no real VPC, no real subnet routing. SeaweedFS proves the S3 **API** is exercised; it proves nothing about S3.

RDS specifically: Multi-AZ, point-in-time recovery, read replicas, parameter groups, failover. None are exercised. The local PostgreSQL is the same engine and nothing more.

EKS and Helm: charts are authored and never applied to a cluster as evidence. Nothing is demonstrated about scheduling, resource limits, disruption budgets, or a rolling upgrade.

### 6.4 Production experience with an open table format

We can operate Iceberg and inject synthetic open-table-format failures. But every failure mode is one I chose. The faults that actually bite in production - a bad `rewrite_manifests`, a catalog split-brain, an orphan-file storm after a killed job, a stale metadata pointer after a partial commit - are only partly reachable in a lab on a laptop.

### 6.5 GDPR

The matrix can evidence technical measures: a PII inventory, enforced access control, a deletion path. It cannot evidence a lawful basis, a data protection officer, a DPIA, a defensible retention *decision*, or a data-subject request process. What M20 demonstrates is "GDPR-shaped". What it does not demonstrate is GDPR.

### 6.6 Stack risks that cap the honesty ceiling

Not posting mismatches, but real limits on what this stack can promise.

- **Dagster was acquired by Prefect on 13 July 2026.** Two orchestrators in one P&L is the shape that preceded MinIO's death. The insurance is that orchestration is the cheapest layer to replace, but "hours, not days" is reasoning until a swap is timed under M1.
- **ClickHouse ships monthly releases with backward-incompatible changes.** A pin plus one upgrade drill is the ceiling of what a local project can honestly claim about operating it.
- **Polaris is a Top-Level Project on a six-week minor cadence.** The catalog swap in M1 is cheap only if no proprietary admin API is ever touched, which is exactly why that CI assertion exists.
- **Polaris's vended session policy is capped at 2048 bytes.** The vended scope is a prefix boundary, and the generated policy grows with the number of prefixes a table occupies. A table whose policy exceeds the cap fails with `MalformedPolicyDocument` rather than degrading, so the M10 scope test asserts the policy size as well as its effect.

---

## 7. Deliberately not done

Mapped against the posting, not against the mission. The mission proposed all of the following; the posting asks for none of it, and each addition was surface area without engineering depth.

| Not doing | Posting clause it would have served | Why |
|---|---|---|
| Trino or any federated query engine | none | The posting names ClickHouse as the serving layer. An unexercised Trino proves nothing. |
| dbt, Great Expectations, Soda | Data quality tooling (nice to have) | The posting says OpenLineage, Great Expectations, **or** dbt tests. Custom gated checks with severity were chosen instead, because the interesting claim is enforcement. |
| Superset, Power BI, any BI tool | none | Not asked for. It would consume the budget that M5 and M7 need. |
| A vector database or RAG pipeline | none | Advertised in the old repo's README, absent from the posting, unrelated to data flow. |
| MinIO, in any form | S3 (nice to have) | Archived upstream 25 April 2026. SeaweedFS was chosen instead. |
| Terraform | Platform / IaC | Relicensed to BUSL in 2023. OpenTofu instead, recorded as a deliberate deviation from the posting's wording. |
| A built multi-region or cross-account platform | Multi-region (nice to have) | Reasoning only, M22. It cannot be evidenced at this scale. |
| Formal compliance programmes (HIPAA, SOC 2) | Security and compliance frameworks | GDPR-shaped technical measures only, M20. |
| An actually built 10× or 100× system | cost at scale | Explicitly out of scope. The reasoning is the deliverable, M18. |

---

## 8. What this unblocks

- **[The completion bar](completion-bar.md)** is now the standard rather than a ticket. Each M-row above names its evidence in the `Demonstration` cell; the standard adds what a cell cannot carry, namely a register of named capability instances, an eight-item core checklist, and the signal-versus-behaviour rule that stops an observable metric standing in for demonstrated behaviour.
- **[The technology-selection matrix](https://github.com/SoongGuanLeong/de-platform/issues/8)** is now testable row by row: every component it admits must appear in some `Platform component` cell or justify its absence.
- **New ticket:** the incident laboratory's scenario set. The eight-link standard is now fixed, so the remaining decision is which of the mission's fourteen scenarios are demonstrable inside a 7-8 GB budget and what evidence each one produces.
- **Unblocked, then resolved:** the serving layer's concrete shape and the benchmark plan waited on [The dataset combination and the data story](https://github.com/SoongGuanLeong/de-platform/issues/7), which is now closed. The tables are settled in [`docs/dataset-selection.md`](dataset-selection.md), and the serving layer's shape is a live ticket rather than fog.
