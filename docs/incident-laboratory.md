# The incident laboratory: the scenario set and the evidence contract

**Ticket:** [The incident laboratory's scenario set: which scenarios, and what evidence each produces](https://github.com/SoongGuanLeong/de-platform/issues/10)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Base:** the evidence standard in [`docs/requirements-matrix.md`](requirements-matrix.md) section 3, row M16, and the completion bar in [`docs/completion-bar.md`](completion-bar.md).

---

## 1. What this document is

The decision record for the incident laboratory: which failure scenarios the platform commits to demonstrating, and the evidence contract each one produces. It is a plan, not a result. No incident has been run, and no MTTD, MTTR or row count appears here.

The mission names fourteen candidate scenarios (`docs/mission/MISSION.md:584-597`). This document decides their fate: in, demoted, or out.

## 2. The admission test

A candidate is admitted as an incident only if all three hold.

1. **A real running component.** It exercises something the platform actually runs, not a hypothetical.
2. **A genuine unprompted alert.** Its Detection link can be an alert that fires from the real Prometheus and Alertmanager stack, routed to a real destination. A scenario with no plausible unprompted alert is a correctness test, not an incident.
3. **A distinct operational lesson.** It adds a failure mode whose operational chain (alert, MTTD, MTTR, runbook, permanent fix) is not already an end-to-end behaviour test in the completion bar.

The test optimises for distinct operational lessons, not for incident count. A scenario that fails (3) is **demoted**, not deleted: it stays in the platform as a correctness or feature test, and is named in section 5.

## 3. The set

Five injected incidents and one separately labelled source hazard.

| # | Incident | Type | Profile | Components |
|---|---|---|---|---|
| 1 | Kafka consumer lag spike | injected | streaming | RIPE Atlas collector, Kafka, Flink, Iceberg |
| 2 | Flink checkpoint timeout | injected | streaming | Flink, SeaweedFS, Iceberg |
| 3 | Iceberg small-file explosion | injected | streaming or batch | Iceberg on SeaweedFS, Flink or Spark |
| 4 | ClickHouse query regression | injected | batch (+ serving) | ClickHouse, Spark or Flink materialisation |
| 5 | Object-storage outage | injected | streaming or batch | SeaweedFS, Polaris, Flink, Spark, ClickHouse |
| 6 | RIPE Atlas source hazard | source hazard, not injected | streaming | RIPE Atlas collector, Kafka |

**Incident 1 is the live-stack injection M16 requires.** It is the only one where all eight links are genuine without stopping the platform: the injection is a real action on the running stack, the alert is a real rule on `records-lag-max` (already required by `docs/completion-bar.md:75`), and the diagnosis, mitigation, recovery, correctness check and permanent fix are all real. Its Detection link reuses the observability drill the completion bar already requires; its added value is the diagnosis-to-permanent-fix chain.

**Incident 6 is a source hazard, not an injected fault.** `docs/dataset-selection.md:239` requires injected faults and publisher defects to be kept apart, so its write-up is labelled a source hazard. The injected requirement of M16 is carried by incidents 1 to 5.

## 4. The evidence contract

The eight links are fixed by M16 and defined in `CONTEXT.md`. For every incident: **inject**, then Detection, Alert, Diagnosis, Root cause, Mitigation, Recovery, Data correctness verification, Permanent fix, plus the inspectable artefact. MTTD is measured from the injection timestamp to the alert **delivery** timestamp at the real destination, not to Alertmanager firing, because `docs/completion-bar.md:179-180` requires the delivery timestamp captured. MTTR is from delivery to the recovery assertion passing. Both use machine timestamps.

Every incident runs under one profile plus the observability overlay, one at a time, never co-resident with `benchmark`. Every evidence item cites a budget id declared in `docs/budgets.yaml` before the run.

### Incident 1: Kafka consumer lag spike

- **Inject:** pause the consumer group (or reduce Flink parallelism) while the RIPE Atlas collector keeps producing. Record the injection timestamp.
- **Detection:** `records-lag-max` exceeds the declared lag budget.
- **Alert:** the lag alert fires unprompted and is routed to the webhook receiver; delivery timestamp captured.
- **Diagnosis:** `kafka-consumer-groups.sh --describe` shows per-partition lag; correlate with Flink backpressure and sink commit latency.
- **Root cause:** consumer throughput below produce rate, not a source fault.
- **Mitigation:** restore consumer capacity to stop the bleed.
- **Recovery:** lag returns under budget, asserted from `--describe`.
- **Data correctness verification:** the reconciliation query diffs source against Iceberg by primary key; assert convergence.
- **Permanent fix:** a committed durable change (partition count, consumer parallelism, or the lag budget) with its commit SHA.
- **Artefact:** the runbook, the postmortem, the Alertmanager delivery log, the lag chart.

### Incident 2: Flink checkpoint timeout

- **Inject:** make a checkpoint exceed its window by enlarging the commit (more files per checkpoint) or slowing the sink commit. Record the injection timestamp.
- **Detection:** checkpoint duration exceeds budget, or `elapsedSecondsSinceLastSuccessfulCommit` grows.
- **Alert:** the checkpoint-duration alert fires unprompted.
- **Diagnosis:** `/jobs/:id/checkpoints` shows duration and size; correlate with the single committer subtask and Iceberg commit latency.
- **Root cause:** checkpoint duration coupled to the Iceberg commit path (commit size and the single committer), not merely a short timeout.
- **Mitigation:** raise the timeout or reduce the checkpoint's data volume to restore progress.
- **Recovery:** checkpoints complete within budget, asserted.
- **Data correctness verification:** replay the checkpoint and assert the Iceberg snapshot's `flink.max-committed-checkpoint-id` is unchanged; kill-after-checkpoint-before-commit leaves no partial state visible.
- **Permanent fix:** change the Iceberg table properties that bound commit size (`target-file-size-bytes`, `write-parallelism`, `distribution-mode`, see `docs/research/06-iceberg-flink-sink-write-modes.md:59`), so a commit cannot exceed the checkpoint window, plus the commit-lag alert. This is a layout and commit-path change, **not** the Flink parameter tuning the completion bar's 6.3 already requires.
- **Artefact:** the runbook, the postmortem, the checkpoint history, the commit-lag chart.

### Incident 3: Iceberg small-file explosion

- **Inject:** drive a high commit rate at a partition granularity that produces files below the target size, so file count grows without bound. Record the injection timestamp.
- **Detection:** file count or compaction backlog exceeds budget.
- **Alert:** the compaction-backlog alert fires unprompted.
- **Diagnosis:** the Iceberg `files` metadata table shows the file-size distribution; correlate with commit rate and partition transform.
- **Root cause:** a write rate and partition granularity producing undersized files, with no compaction policy to bound them.
- **Mitigation:** run a compaction to restore query health.
- **Recovery:** file count and p50/p95 latency return to budget.
- **Data correctness verification:** row counts are unchanged across compaction and snapshots remain intact.
- **Permanent fix:** a scheduled, Dagster-owned compaction and retention policy with a declared target file size and a backlog bound, **not** the one-off `rewrite_data_files` procedure the completion bar's 6.5 requires. Dagster owns retention and snapshot expiry but ships no policy, so it must be built (`docs/technology-selection.md:89`, `:105`).
- **Artefact:** the runbook, the postmortem, the compaction policy, the file-count chart.

### Incident 4: ClickHouse query regression

- **Inject:** apply a change that regresses a named query, such as a bad `ORDER BY`, a dropped projection, or a data-distribution change. This is deliberately **not** a bad SQL statement. Record the injection timestamp.
- **Detection:** query latency breaches the declared p50/p95 SLO.
- **Alert:** the query-latency alert fires unprompted.
- **Diagnosis:** `system.query_log` shows the regressed query and its plan; compare before and after `EXPLAIN`.
- **Root cause:** a physical-layout or data-distribution change, not the SQL.
- **Mitigation:** revert the layout change or add a projection.
- **Recovery:** latency returns within budget.
- **Data correctness verification:** result sets are identical before and after.
- **Permanent fix:** the layout change is committed with a SHA, and a guard is added (a layout assertion in CI, or a declared sorting key).
- **Artefact:** the runbook, the postmortem, `system.query_log` extracts, before and after `EXPLAIN`.
- **Distinct from the completion bar's bad-query rewrite** (`docs/completion-bar.md:135`): the root cause is layout, not SQL.

### Incident 5: Object-storage outage

- **Inject:** `podman stop seaweedfs`. Record the injection timestamp.
- **Detection:** Iceberg and Polaris read and write failures; Flink and Spark job failures.
- **Alert:** the storage-error alerts fire unprompted.
- **Diagnosis:** SeaweedFS container state; S3 API errors in the pipeline logs.
- **Root cause:** the storage service is unreachable.
- **Mitigation:** restart SeaweedFS.
- **Recovery:** writes and reads resume and the streaming path catches up.
- **Data correctness verification:** reconcile after catch-up and assert Iceberg's atomic commit left no partial state.
- **Permanent fix:** a committed durable change, such as a `healthcheck` with a restart policy (both inside the portable compose subset, `docs/completion-bar.md:251`) plus a documented degraded-mode procedure.
- **Artefact:** the runbook, the postmortem, the container state log, the recovery reconciliation.
- **Note:** the materialised ClickHouse MergeTree copy keeps serving while Iceberg is unreachable, which demonstrates the M7 architecture decision under fault.
- **Honesty limit:** SeaweedFS STS is not AWS STS, so this evidences a local data-plane outage, not an AWS S3 outage.

### Incident 6: RIPE Atlas source hazard

- **Type:** source hazard, labelled separately from injected faults (`docs/dataset-selection.md:239`).
- **Inject:** no injection. Drive the collector against the publisher's documented limits, or observe the documented hazard. Record the trigger timestamp.
- **Detection:** ingestion stall, freshness lag, or collector error rate.
- **Alert:** the freshness or collector-error alert fires unprompted.
- **Diagnosis:** collector logs show `429`, `416` on a stale timepoint, or a disconnect; correlate with the publisher's limits (600 requests per 5 minutes per key, 2 concurrent streaming connections, an IP-ban policy, `docs/research/01a-datasets-relational-cdc.md:1082`).
- **Root cause:** the publisher's rate limits and reconnect policy.
- **Mitigation:** exponential back-off and a single long-lived connection.
- **Recovery:** the stream resumes from the persisted `timepoint` cursor.
- **Data correctness verification:** assert the cursor is persisted and the gap is bounded; the source is at-most-once, so no loss is claimed beyond that.
- **Permanent fix:** a committed back-off policy and persisted cursor with a SHA.
- **Artefact:** the runbook, the postmortem, the collector log, the cursor record.

## 5. The demoted scenarios

Demoted, not deleted. Each stays in the platform as a correctness or feature test, owned by the completion-bar item named.

| Mission scenario | Fate | Where it lives |
|---|---|---|
| 3. Flink worker failure | demoted | completion bar 6.3: kill mid-checkpoint, kill after checkpoint before commit, restart under an injected failure |
| 4. Duplicate events | demoted | completion bar 6.3 redelivery test; 6.2 reordered replay |
| 5. Late-arriving events | demoted | completion bar 6.3 late-event injection with `numLateRecordsDropped` |
| 7. Failed Iceberg write | demoted | the failure mode of incident 5; a storage fault is how a write fails here |
| 9. Upstream schema change | demoted | completion bar 6.2 add-NOT-NULL survives; 6.5 schema-evolution matrix. The real ONSPD 2022Q4 to 2023Q1 geography-vintage break carries it as a **source hazard**, not a synthetic column add |
| 10. Source/target row-count mismatch | demoted | the data-correctness-verification link of incident 1; completion bar 6.2 reconciliation by primary key |
| 11. Dagster job failure | demoted | completion bar 6.7 retries and backoff, one failed-then-recovered run |
| 13. Corrupt input file | demoted | completion bar 6.8 corrupted batch quarantined, gold unchanged, critical failure blocks downstream |

## 6. Out of scope

- **14. Partial pipeline execution.** Underspecified, no natural unprompted alert, and completion bar 6.7 already covers the backfill and re-run correctness. Recorded here rather than admitted.

## 7. Resource and profile mapping

The profiles are the reproducibility unit (`docs/completion-bar.md:215-223`); incidents are Tier B (`:225`).

| Profile | Contains | Incidents |
|---|---|---|
| `streaming` + observability | Postgres, Debezium, Kafka, Flink, SeaweedFS, Polaris, ClickHouse, Prometheus, Grafana, Alertmanager | 1, 2, 6 |
| `batch` + observability | Postgres, SeaweedFS, Polaris, Spark, ClickHouse, Dagster, Prometheus, Grafana, Alertmanager | 3 (batch arm), 4 |
| either, heaviest | the data plane goes down | 5 |

Reductions are permitted and recorded: incident 3 runs at a declared reduced scale because it needs many files; incident 4 reuses the M7 materialised set rather than rebuilding. No incident runs alongside `benchmark`. The whole set fits the 7 to 8 GB envelope only one incident at a time.

## 8. Scenario 12 injection feasibility

Feasible, medium risk, the heaviest of the six. The mechanism is `podman stop seaweedfs`, the only injection available at the compose and podman level with no Kubernetes and no chaos tooling. It takes down the data plane, so Flink and Spark writes and Polaris-mediated Iceberg reads fail; the materialised ClickHouse copies survive, so serving keeps answering, which is the point worth demonstrating. It requires a dedicated window, and recovery time is bounded by the backlog that accumulates. If the budget bites, incident 5 is the one to drop, and incident 7 (a transient failed Iceberg write) can be promoted in its place as a narrower test.

## 9. The two conditional permanent fixes

Incidents 2 and 3 were admitted only because their permanent fixes add something beyond the completion bar. The demotion trigger is recorded here: if either fix collapses to a parameter or a one-off procedure, that incident is demoted.

- **Incident 2.** The completion bar's 6.3 tuning record already changes checkpoint interval, timeout, parallelism, state backend and sink flush size. The admitted permanent fix is instead an Iceberg table-property change (`target-file-size-bytes`, `write-parallelism`, `distribution-mode`) that bounds commit size, because the committer is forced to a single subtask (`docs/research/06-iceberg-flink-sink-write-modes.md:199`). The distinct lesson: checkpoint health is coupled to table layout.
- **Incident 3.** The completion bar's 6.5 already requires compaction with before/after file counts. The admitted permanent fix is instead a scheduled, Dagster-owned compaction policy with a target file size and a backlog bound. The distinct lesson: small-file growth is a rate problem fixed by a policy.

## 10. Open items

- The MTTD and MTTR budgets are declared per incident in `docs/budgets.yaml` as `m16-mttd-incident-<n>` and `m16-mttr-incident-<n>`, with the reasoning in [the benchmark plan](benchmark-plan.md) section 6. An earlier revision of this document said the file ships empty; it held five M17 entries by the time the full set was written.
- The runbooks, postmortems and dashboards are out of scope for this ticket and are produced later.
- The RIPE Atlas collector is the ingestion path (`docs/dataset-selection.md:36`) but is not one of the nineteen counted components; the proposal's technology count should be checked for consistency.
