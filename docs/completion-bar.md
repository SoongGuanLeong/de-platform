# The completion bar

**Ticket:** [The completion bar: what makes a capability genuinely finished](https://github.com/SoongGuanLeong/de-platform/issues/6)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Base:** the evidence standard in [`docs/requirements-matrix.md`](requirements-matrix.md) section 3 is the foundation this document operationalises.
**Decision record:** [`docs/adr/0007-completion-bar-as-a-gate.md`](adr/0007-completion-bar-as-a-gate.md)

---

## 0. Status of this document

This document defines the evidence a capability must produce before it counts as finished. It is a standard, not a build order.

No platform code exists while the map is open, so nothing here is a result. Every item below specifies evidence that will be produced during implementation. The capability register at [`docs/completion-bar.yaml`](completion-bar.yaml) ships empty and is filled in as work happens.

## 1. What this document is, and what it is not

It is the definition of done, per capability class, and the mechanism that makes a claim checkable by someone who does not trust the author.

It is not a build plan, a schedule, or a claim that any of it exists. It is also not a per-capability document set. The checklists below are the standard; what they demand is evidence items and contracts, not prose about the work.

The failure mode this document exists to resist is a portfolio project that looks finished from the outside: every service starts, every dashboard is green, and nothing has been shown to behave correctly under a fault.

## 2. Terms

- **Capability instance**: one concrete thing that must work, such as one topic, one pipeline, one table or one dashboard. This is the unit the bar applies to.
- **Capability class**: one of the eleven families in section 6. A class is a template; instances are what get registered and completed.
- **Capability register**: the machine-readable list of instances and their evidence, at [`docs/completion-bar.yaml`](completion-bar.yaml).
- **Evidence item**: one small file under `docs/evidence/` recording a claim, the command that produced it, and the raw artifact.
- **Signal**: the observable exists and is reachable.
- **Behaviour**: the platform was shown to do the thing, under a fault or a boundary condition, and the result was recorded.
- **Budget**: a threshold declared in [`docs/budgets.yaml`](budgets.yaml) before the measurement it judges.
- **Profile**: the declared service set and resource budget an evidence item was produced under. One of `smoke`, `batch`, `streaming`, `observability`, `benchmark`.
- **Observed-once**: a measurement whose environment cannot be reproduced. Recordable, never citable as evidence for a claim.
- **Declared consumer**: a downstream reader named in the repository, and therefore covered by the regression guarantee.

## 3. The unit of the bar: instances, not classes

A class is complete only when every instance in its register entry is complete. The register is what makes the claim falsifiable: it turns "Kafka ingestion is done" into a named list of topics, each with its evidence.

Each class carries one **representative** instance holding the deeper, benchmark-grade evidence. The remaining instances carry the core evidence. This bounds the cost of the bar without letting one working instance speak for a class.

## 4. The core checklist

Eight items apply to every registered instance. Each is falsifiable by a sceptic with a clone and the command in the evidence item.

1. **Implementation exists and is the only path.** The documented bring-up runs the capability with no manual step. Falsifiable: a clean checkout plus the documented command produces the result, with no hand-run shell command in between.
2. **An automated test at the right level.** Unit for logic, integration for wiring, end-to-end for the path. Falsifiable: the test fails when the behaviour is removed.
3. **Realistic data.** The real dataset or a documented representative slice, never a hand-built toy that avoids the awkward cases.
4. **Documentation.** What it does, how to run it, how to read its output, and its known limits.
5. **Observability.** The signal exists, and where the capability can fail silently an alert fires on it.
6. **Failure handling.** The failure modes are enumerated in the register in advance. Each enumerated mode is either demonstrated end to end or explicitly deferred with a recorded reason.
7. **Reproducible bring-up.** It runs from a clean checkout under a named profile (section 8).
8. **A measurable acceptance criterion.** Its budget is declared in `docs/budgets.yaml` before the measurement.

**The not-applicable discipline.** "Where applicable" is not self-certified. Item 6 requires the failure modes to be listed before the work, and a mode that is not demonstrated must appear in the register's `not_applicable` field with a reason. The CI surfaces unresolved deferrals.

## 5. Signal versus behaviour

Every evidence item declares `proves: signal` or `proves: behaviour`.

A capability may only be marked complete on at least one behaviour item. Observability items count as signals unless accompanied by a recorded drill in which the alert fired unprompted.

This distinction exists because most available metrics prove the mechanism is observable rather than that the claim holds. Consumer lag being visible is not recovery from a lag spike. A checkpoint-duration metric is not a restore that preserved state.

## 6. The eleven class deltas

Core items 1 to 8 apply to every instance and are not repeated. Each delta is class-specific only. Where a concrete key or value depends on the dataset ticket or the technology-selection ticket, the delta states the evidence required and leaves the value to be filled in during implementation.

### 6.1 Kafka ingestion

- The topic design is declared: the key, why that key, and what ordering it does and does not give. Falsifiable: the observed message key matches the declaration, and a primary-key update moves the key.
- Retention and replication are declared with their consequence, and a broker restart produces the declared behaviour.
- The schema is registered with a compatibility rule set. Falsifiable: a backward-incompatible schema is rejected by the serializer, and the same payload passes under `NONE`.
- Consumer lag is observable and bounded: an alert fires unprompted when lag exceeds a declared budget.
- A Connect task failure and its restart are observed, not merely configured.

*Artifacts:* `kafka-consumer-groups.sh --describe`; the JMX beans `MessagesInPerSec`, `UnderReplicatedPartitions`, `records-lag-max`; the Connect REST endpoint `/connectors/{name}/status`; the Apicurio rules API response.

### 6.2 CDC ingestion

- Both phases are evidenced: the snapshot completes, and the topic then carries `op=r` followed by `op=c/u/d` for the same table.
- Every event carries `source.lsn`, and the sink applies last-write-wins against it. Falsifiable: a deliberately reordered replay converges.
- The four hard cases are each asserted for topic, key and operation: NULL-to-value UPDATE, composite-PK UPDATE, DELETE, and out-of-order arrival.
- Source and target are reconciled by primary key, with the count taken from PostgreSQL rather than from the pipeline.
- An upstream schema change survives: add a NOT NULL column, restart the connector, and assert the topic and downstream survive.
- The replication slot does not stall: `confirmed_flush_lsn` advances and lag stays bounded.

*Artifacts:* the Debezium JMX contexts `snapshot` and `streaming` with `SnapshotCompleted` and `MilliSecondsBehindSource`; a `pg_replication_slots` query; the reconciliation query output.

### 6.3 Flink streaming

- Checkpoint evidence: duration, size, completed count and failed count.
- Kill mid-checkpoint, restore, and assert an identical final state.
- Kill after checkpoint but before commit: assert no partial state is visible to a concurrent reader.
- Backpressure and restart observed under one injected failure (`numRestarts`, `backPressuredTimeMsPerSecond`).
- The watermark and lateness policy is written, with late-event injection showing `numLateRecordsDropped` and the declared consequence.
- Exactly-once effect: replaying a checkpoint leaves the Iceberg snapshot's `flink.max-committed-checkpoint-id` unchanged.
- A savepoint is taken and restored.
- Upsert mode is declared, and a redelivery test shows it absorbs a duplicate where append mode does not.
- The equality delete-file count stays bounded, with a compaction record.
- A tuning record changes at least three of checkpoint interval, checkpoint timeout, parallelism, state backend and sink flush size, each with its measured effect.

*Artifacts:* the Flink REST endpoints `/jobs/:id/checkpoints` and `/metrics`; the Iceberg `snapshots` metadata table; the compaction output.

### 6.4 Spark batch

- Bronze to silver to gold runs through the same catalog as the streaming path, and the batch writes are visible to it.
- A gold model answers a named business question, and its result is asserted against an independently computed expected value.
- Cross-path agreement: a metric computed by Flink and by Spark agrees within a stated tolerance.
- MERGE writes position deletes, not equality deletes. Falsifiable: the `files` metadata table shows `content=1` rows and no `content=2` rows.
- Incremental-read discipline holds: append-only tables are read through the DataFrame API with `start-snapshot-id` and `end-snapshot-id`, while MERGE-maintained tables use the watermark control table and are never fed to the incremental reader.
- Wall-clock and resource use are recorded at a stated volume.

*Artifacts:* the Spark event-log JSON and History Server; `metrics/prometheus`; the `files` metadata table.

### 6.5 Iceberg table management

- The format version and the table-property baseline are declared and applied consistently.
- A schema-evolution matrix covers add-optional, add-required-with-default, rename, drop and type change, each with its read paths verified.
- Time travel and rollback to a prior snapshot id.
- Tags are used where a watermark needs a pinned snapshot, since tags never expire while `expire_snapshots` would remove the snapshot.
- Layout is a measured trade-off: at least three variants of one hot table, each with write throughput, file count and size distribution, compaction duration and p50/p95 serving latency, plus a decision record naming which axis won and which lost.
- Compaction and small-file management run through `rewrite_data_files` and `rewrite_manifests`, with before and after file counts.
- Retention is a dry run followed by the real run, asserting that expired snapshots are gone **and** that an in-window snapshot survived, with storage reclaimed measured.
- Per-operation metadata growth cost is measured.

*Artifacts:* the `snapshots`, `history`, `files`, `manifests`, `partitions`, `refs` and `metadata_log_entries` metadata tables; procedure output.

### 6.6 ClickHouse serving

- Both arms are measured: catalog read-through against materialised MergeTree, with the delta recorded.
- The named analyst query set carries p50 and p95 budgets declared before measurement, at a stated volume and concurrency.
- The physical layout is declared (the `ORDER BY` key, projections, codecs, TTL) with a reason for each, and the declaration matches `system.tables.sorting_key`, `system.tables.primary_key` and `SHOW CREATE TABLE`.
- One deliberately bad query is diagnosed from `system.query_log` and fixed, with before and after recorded.
- Near-real-time lag is measured end to end, from the source commit timestamp to the row being visible in the materialised copy, p50 and p99, with the lateness derivation stated and the threshold declared first; the same is measured on the read-through arm as the freshness baseline.
- Serving reliability: interrupt the serving path mid-session and assert the documented recovery.
- TTL is actually applied: `system.parts` rows and bytes fall after the boundary.

*Artifacts:* `system.query_log`, `system.parts`, `system.metrics`, `system.events`, `system.asynchronous_metric_log`, `system.projections`, `EXPLAIN`, and the Prometheus endpoint.

### 6.7 Orchestration

- No manual shell step is needed: the documented bring-up runs the pipeline end to end.
- A dated-window backfill asserts the result is identical to the original run.
- Re-running a failed run asserts no double counting.
- Retries and backoff are configured, with one failed-then-recovered run recorded.
- Data-quality gates are wired as orchestration gates, not as side effects.
- Asset materializations, run logs and freshness are queryable.

*Artifacts:* the Dagster instance's `asset_materializations` and `event_logs`; `dagster run logs`; asset-check results; the GraphQL API.

### 6.8 Data quality

- Every check declares an id, a severity, and the severity-to-action mapping across warn, quarantine and fail.
- The quarantine contract holds: bad rows carry `_quarantined_at`, `_check_id` and `_reason`, and the assertion is that the quarantine count is greater than zero **and** that gold is unchanged.
- A deliberately corrupted batch is quarantined and never reaches gold.
- A critical failure blocks the downstream Dagster run, proven by the downstream run not starting.
- Check results are persisted and queryable by run id.
- A false-positive rate is measured over a stated number of consecutive clean runs.

*Artifacts:* the check-result table; the quarantine table; the Dagster run that never started.

### 6.9 Governance and lineage

- A namespace and role layout, plus a written authorisation map naming which system governs which path and stating that Polaris enforces no column-level access.
- A denied principal is refused and the refusal is audited in both engines, each traceable to the system that made it.
- A column-level test on a PII column in ClickHouse, the only engine that can enforce it.
- A vended-credential scope test: vend for table A, assert that a read of table B's prefix is refused with `AccessDenied`, and record the unscoped baseline that proves the policy caused it.
- The generated session policy size is asserted against the 2048-byte limit.
- The scope limitation is documented: the boundary is a prefix, not a table identity, and a broad storage credential configured inside ClickHouse bypasses catalog authorisation.
- A column-level lineage graph for one gold column spans the CDC topic, silver, gold and the ClickHouse view, with the emitting run id tied to the Dagster run and the OpenLineage event id, emitted on the streaming path as well as the batch path.

*Artifacts:* Polaris management API responses; the `AccessDenied` traces; OpenLineage events, schema-validated in CI; the Marquez read-back.

### 6.10 Observability

- Dashboards as code in Git cover throughput, consumer lag, checkpoint duration, compaction backlog, DQ pass rate and query latency.
- Declared SLOs carry one alert rule per SLO, and every alert is shown firing in a recorded drill. The signal-versus-behaviour rule applies in full here.
- Alert routing reaches a real destination, with the delivery timestamp captured.
- Prometheus rules are validated in CI with `promtool check rules`, and Grafana datasources and dashboards are provisioned from Git.

*Artifacts:* `prometheus.yml` and the rule files; Grafana provisioning YAML and dashboard JSON; the Alertmanager `/api/v2/alerts` endpoint; the webhook receiver log with timestamps.

### 6.11 Infrastructure as code

- OpenTofu modules cover the S3 layout, IAM roles and policies, VPC and subnets, security groups, the RDS instance class and parameter group, and secrets handling, committed and validated in CI with `tofu validate`.
- Helm charts for the EKS deployment are authored and never applied, with `helm lint` and `helm template` in CI and the rendered manifests committed.
- Compose files are restricted to the portable subset (section 11), linted in CI, with the compose provider the bring-up was verified against named.
- A written local-versus-cloud diff names what the local run cannot exercise.

*Artifacts:* `tofu validate` output; rendered Helm manifests; the compose lint result; the local-versus-cloud diff.

## 7. Where evidence lives, and the evidence item schema

One file per item at `docs/evidence/<class>/<instance>/<item>.md`, with raw artifacts committed under `raw/` beside it. A per-instance `INDEX.md` lists the matrix rows the instance satisfies.

| Field | Meaning |
|---|---|
| `id` | Stable identifier, unique across the repository. |
| `capability` | The register instance id this evidence belongs to. |
| `matrix_rows` | The M-rows of `docs/requirements-matrix.md` this evidence answers. |
| `claim` | One falsifiable sentence. If it cannot fail, it is not a claim. |
| `proves` | `signal` or `behaviour`. |
| `command` | The exact command that produced the artifact. |
| `profile` | The profile it was produced under. |
| `commit` | The commit the evidence was produced at. |
| `date` | The date of the run. |
| `budget_ref` | Optional. The budget id this evidence is judged against. |
| `artifact` | Path to the raw output under `raw/`. |
| `observed_once` | Default `false`. See section 9. |

## 8. Profiles and reproducibility

Full co-residency of the stack is impossible at roughly 7 to 8 GB of free RAM, so "reproducible on a clean checkout" cannot mean "run everything". It means the reviewer can run a declared profile.

| Profile | Contains | Entitlement |
|---|---|---|
| `smoke` | The CI-checkable set plus per-service lightweight container checks. No full stack. | Re-run in CI or on a laptop from a clean checkout, deterministic, minutes. |
| `batch` | PostgreSQL, SeaweedFS, Polaris, Spark, ClickHouse, Dagster. | Re-run the batch path end to end. |
| `streaming` | PostgreSQL, Debezium, Kafka, Flink, SeaweedFS, Polaris, ClickHouse. | Re-run the streaming path end to end. |
| `observability` | Prometheus, Grafana, Alertmanager. An overlay on either path. | Open the dashboards and see an alert fire. |
| `benchmark` | One component at a time under a declared resource budget. Never the whole stack. | Re-run a benchmark if the reviewer matches the declared profile. |

Two tiers of evidence follow. **Tier A** is correctness and contract evidence, re-runnable from a clean checkout by one command under `smoke`. **Tier B** is benchmarks, incidents and load tests, recorded with a protocol and regenerable only under their declared profile.

Every evidence item names the profile that produced it. A claim that fits no profile is a design claim, not evidence.

Time and resource figures in this document are budgets and definitions of done, never measurements.

## 9. The honesty rule

Thresholds live in [`docs/budgets.yaml`](budgets.yaml), one entry per threshold, and each evidence item cites the budget id it is judged against. A budget is committed before the measurement it judges; the CI resolves the citation to the commit that introduced the budget, so the order is visible in history. Changing a budget creates a new entry, and evidence citing a superseded budget is invalid.

A benchmark record states its hardware as configured, its data volume, its engine versions, its exact command, its run count, and its raw output, with the commit and the date.

A measurement whose environment cannot be reproduced may be recorded, but it is labelled `observed_once: true` and may never be cited as evidence for a claim. The claim must rest on a reproducible measurement or be downgraded to an observation.

## 10. The regression guarantee

Three mechanisms together, and the guarantee is limited to declared consumers.

- **Registry compatibility.** The CDC topics carry an Apicurio compatibility rule, so a backward-incompatible schema is rejected before it reaches a consumer.
- **Gold contracts.** One contract file per gold table, next to its definition, carrying the table, its grain in one sentence, its columns with types and nullability, its business keys, its invariants, the persona query ids that must run against it, the versioning rule naming what counts as breaking, and the compatibility rule enforced. The contract test runs in CI and fails on a schema or invariant break.
- **Consumer simulation.** The persona queries from the analyst work double as the simulation, so they are not written twice.

The honest limit: an external consumer nobody registered is not protected, and ClickHouse's monthly backward-incompatible releases cap what can be promised about the serving engine.

## 11. The portable runtime subset

Bring-up must not depend on one compose provider. Compose files are restricted to the portable subset: OCI images, ports, `environment` and `env_file`, volumes, networks, `healthcheck` with `start_period`, `restart`, `profiles`, `extra_hosts` with `host-gateway`, and `depends_on` without `condition`. Services self-retry rather than depending on health-based start ordering. The provider the bring-up was verified against is named in the runbook, and a CI lint rejects the forbidden keys.

The explicit `host.docker.internal:host-gateway` entry is kept: podman adds that hostname automatically, Docker on Linux does not.

The Docker-versus-podman technology decision itself belongs to the technology-selection ticket, not here.

## 12. What the CI validates

The CI never re-runs expensive evidence. It checks that the paperwork is honest:

- every class in the register has at least one representative instance;
- every `complete` instance has at least one `behaviour` evidence item;
- every evidence link resolves, and every evidence item carries all required fields;
- every `budget_ref` resolves to an entry in `docs/budgets.yaml`;
- every `not_applicable` entry carries a reason;
- no `complete` instance has an unresolved deferral;
- compose files contain none of the keys outside the portable subset.

## 13. What we explicitly do not test, and why

Each entry names the gap, the reason, and what stands in its place. Naming these is part of the deliverable.

1. **Production scale.** Every layout and cost conclusion beyond the single measured axis is extrapolation: Iceberg planning cost, per-partition file counts, compaction and part merging at real volumes are reasoned, not observed. *In its place:* the reasoning plus one genuinely measured axis, labelled as extrapolation.
2. **On-call as a human practice.** The system detects, alerts, and can be recovered by a stranger with a runbook. There is no pager and no human triage under pressure. *In its place:* the eight-link incident chain, as a property of the platform.
3. **AWS.** OpenTofu is never applied, so there is no real S3, no IAM policy evaluation, no VPC routing, no RDS failover, point-in-time recovery or read replicas, no EKS scheduling or rolling upgrade, and no Helm release. *In its place:* `tofu validate`, rendered charts, and an explicit local-versus-cloud diff.
4. **Open-table-format failure modes a laptop cannot reach.** Catalog split-brain, an orphan-file storm after a killed job, a stale metadata pointer after a partial commit. *In its place:* the reachable subset, and the admission that the rest is reasoning.
5. **GDPR.** Technical measures only: no lawful basis, no DPIA, no data-subject request process. *In its place:* the phrase "GDPR-shaped", used deliberately.
6. **Multi-region and cross-account.** Reasoning only, no deployment.
7. **Formal compliance programmes** such as HIPAA and SOC 2. Out of scope by decision.
8. **Continuous ClickHouse upgrade testing.** A pin plus one upgrade drill is the ceiling, against monthly backward-incompatible releases.
9. **Catalog-swap equivalence.** The swap drills time the swap; they do not prove the replacement is production-equivalent. *In its place:* the measured swap cost and the CI assertion that no proprietary admin API is used.
10. **SeaweedFS STS is not AWS STS.** The local run uses a permissive trust policy and no IAM policy simulation, so it evidences the shape of the credential flow, not AWS policy semantics.
11. **Runtime parity beyond one provider.** The bring-up is verified against one compose provider; the other provider's behaviour is untested. The Flink, ClickHouse, Dagster, Debezium Connect, Apicurio and Alertmanager images are unverified under podman until a runtime check is actually run.
12. **Unknown downstream consumers.** The regression guarantee covers declared consumers only.
13. **True multi-broker failure.** Single-node Kafka cannot evidence broker-loss behaviour beyond a restart; replication and in-sync replica settings are configured but not exercised at real redundancy.
14. **Concurrency and backpressure at real throughput.** Injection is synthetic and the query set is bounded; the claim is engineering behaviour, not throughput at production volume.

## 14. Where this is applied

The standard is applied during implementation, not while the map is open. The phased roadmap and its gates are the fog item that consumes it, and the interview-facing ordering in `docs/requirements-matrix.md` section 4 decides which capabilities are evidenced first.
