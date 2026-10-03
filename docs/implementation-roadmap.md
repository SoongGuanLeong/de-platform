# The phased implementation roadmap and the per-phase definition of done

**Ticket:** [The phased implementation roadmap and the per-phase definition of done](https://github.com/SoongGuanLeong/de-platform/issues/27)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Base:** [the completion bar](completion-bar.md) is the standard this roadmap applies, and [the benchmark plan](benchmark-plan.md) fixes the order the measurements run in.
**Decision records:** none of its own. It creates no ADR for the same reason [the benchmark plan](benchmark-plan.md) creates none: nothing here reverses a decision, the one contestable choice inside it is the phase order, and reordering phases is cheap to reverse.
**Deliverables:** mission deliverable 19 (the phased implementation roadmap) is section 3 with section 4; mission deliverable 20 (the definition of done for every phase) is section 5.

---

## 0. Status of this document

A plan, not a schedule. **No phase has been started, no profile has been run, and no benchmark has been measured.** Every figure below is a budget, an entitlement or an arithmetic result over a documented default. There are no dates and no time estimates anywhere in this document, because the roadmap is a dependency order rather than a calendar.

**Unproven is not undecided.** Where a decision is settled but its evidence is missing, this document says so and names the test that would produce it, rather than reopening the decision.

## 1. What this document settles

1. **The phase list and its gates**, replacing the twelve-block sketch in [the Project Mission](mission/MISSION.md) section 33. Every phase leaves a working system (section 3).
2. **The run sequence and the readiness assertion per phase**, so "phase complete" is a reproducible statement rather than a vague one (section 4).
3. **The ordering against the benchmark order**, which this roadmap does not diverge from, and the reason it does not (section 3).
4. **The definition of done per phase**, expressed as the register entries the phase completes rather than as prose (section 5).
5. **What is deferred, and what triggers a revisit**, including every limitation carried across the map (section 8).

## 2. The five principles

**1. A phase closes on a declared sequence of profile runs that are never co-resident.** `batch` peaks at 6976 MiB and `streaming` at 7168 MiB against an enforceable 7168 MiB, so the two path profiles never run together ([the local development architecture](local-development.md) section 4). A phase that needed both simultaneously would be unclosable on this host.

**2. A phase leaves a working system.** The documented bring-up reaches its readiness assertion at the end of the phase, with no manual step in between. This is the mission's own instruction, and it is why Phase 0 is a repository rather than a path: there is no profile that carries a minimal end-to-end path, because `smoke` runs one service at a time and never the stack.

**3. A phase gate is a register snapshot, not a new artefact.** A phase closes when every register instance it admits is `complete` with at least one `behaviour` evidence item, every budget it cites resolves and none is `pending`, and the `required` CI check is green on `main`. No per-phase document is written, because [the completion bar](completion-bar.md) is already the standard and a second statement of it could only drift.

**4. The benchmark order is a measurement order, not a build order.** P0, then B1, B2, B6, B7, B9, then B3, B4, B5, then the incident laboratory ([the benchmark plan](benchmark-plan.md) section 5.2). This roadmap draws its phase boundaries around those groups rather than across them, so it diverges nowhere. A phase may build a capability before the benchmark that measures it; no benchmark moves.

**5. No phase leaves the portfolio less demonstrable than it found it.** The system is demonstrable from Phase 1, at a labelled reduced volume where a volume-dependent claim is not yet earned.

## 3. The phase list

Eleven phases, named for what each leaves standing. The run sequence column is expanded in section 4, and the register column in section 5.

| Phase | Runs | Leaves standing | Rows |
|---|---|---|---|
| **0. The repository contract and the container set** | `smoke` | The layout of [ADR-0026](adr/0026-one-repository-path-first.md); the uv workspace with its five Python distributions and the packaging graph; `.importlinter` rules 1 to 5; every profile's compose files; `deployment/tools.lock` and `deployment/scripts/paths.sh`; `.github/workflows/ci.yml` with `changes`, the eleven jobs and `required`, with the existing `security.yml` absorbed and deleted; the register with its eleven classes and its first instance entries; the `platform/` core (the catalog connection reached only through the Iceberg REST specification, the contract loader, the naming conventions, the OpenLineage configuration) | none |
| **1. The commerce batch skeleton** | `batch`, reduced | The commerce batch path end to end at the correctness slice: TPC-H generation and the bronze load; `batch/commerce` silver and gold with the documented grain, the star schema, SCD2 and the single atomic `MERGE ... WHEN NOT MATCHED BY SOURCE THEN DELETE`; one contract per gold table; the `schema` check generated from each contract; the ClickHouse DDL, views and the batch partition-swap materialisation. Plus the LSN operator's unit test under Flink's test harness in the CI `java` job | M4, M17 (part), M21 (Python) |
| **2. Orchestration, contracts and the data-quality gate** | `batch`, reduced | The Dagster composition root with the asset graph, retries and backoff, and the asset checks; the five check kinds with severity declared per instance and one action per severity; the quarantine writer and the `platform.quarantine` table; the check-result store in PostgreSQL; the gate placement (input-evaluable upstream, output-only through an Iceberg branch, the streaming half deferred to Phase 4); the contract versioning rule and the CI breaking-change check | M13 (batch half), M14, M9 (contracts) |
| **3. The declared volume, the layout sweep and the serving comparison** | `batch`, then `benchmark` | P0 fixtures at the declared volume, each with its row count asserted against an independent count and a pinned snapshot or tag recorded; then B1, B2, B6, B7 and B9 in that order, each with its derived budget committed before the judged run and each with a proven reset | M5, M7, M6, M1, M17, M12 (measured half) |
| **4. The network spine** | `streaming`, then `batch` | The RIPE collector (the WebSocket subscription set, the rate limits, the persisted `timepoint` cursor, the REST backfill producer) and the RIPE ingestion job (watermark over the probe timestamp, a one-minute tumbling window per probe, five minutes of allowed lateness, the side output for past-watermark records and `lts == -1`, the content-hash key); the ONSPD loader; `dim_postcode` as SCD2 on `DOINTR` and `DOTERM`; the `postcode_geography` bridge; the spatial join; the network serving copy with its TTL and its hourly rollup; the source-hazard checks; the streaming half of the gate (the dead-letter sink and the Dagster sensor that savepoints and stops the job); the incident 6 collector-error-rate budget, declared with the alert rule it judges | M9 (network persona), M15 (part), M17 (SCD2), M13 (source-hazard half) |
| **5. The commerce CDC path in full** | `streaming`, then `batch` | The TPC-C driver at the declared volume with its scripted deterministic mode; the Debezium connector; the Avro schemas under `contracts/commerce/topics/` with the `BACKWARD_TRANSITIVE` rule enforced by the serializer; the CDC ingestion job in DataStream Java with the custom keyed LSN operator; the CDC serving job in Flink SQL writing the `ReplacingMergeTree` copies versioned by LSN; the equality-delete field sets; the tombstone handling for a primary-key change; the four hard cases; the reconciliation asset; the Dagster-owned Flink lifecycle | M2, M3, M21 (Java) |
| **6. The streaming measurements** | `benchmark`, then `streaming`, then `batch` | B3, B4 and B5, each with its derived budget committed before the judged run and its reset proven, with the `rewrite_data_files` compaction in a following window | M8, M18, M3 (tuning) |
| **7. Governance, lineage, retention and the security model** | `batch`, then `streaming` | The Polaris namespace and role layout, spine-then-layer; the ClickHouse namespace mirror with its column grants and its one row policy; the written authorisation map; the denial-attribution mechanisms; the vended-credential scope test and the session-policy size assertion; the PII inventory and classification; the deletion path terminating in Iceberg; the column-level lineage graph for one gold column; the retention policy per data class with snapshot expiry and ClickHouse TTLs applied | M10, M11, M12, M20 |
| **8. Observability and the incident laboratory** | a path profile, non-reduced | Dashboards as code covering throughput, consumer lag, checkpoint duration, compaction backlog, DQ pass rate and query latency; one alert rule per declared SLO; alert routing to a real destination with the delivery timestamp; and the six incidents, each with all eight links, real timestamps, an unprompted alert, measured MTTD and MTTR, a runbook and a blameless postmortem | M15, M16 |
| **9. Deployment artefact validation** | none | The OpenTofu modules for the S3 layout, the IAM roles and policies, the VPC and subnets, the security groups, the RDS instance class and parameter group, and secrets handling, with the `reference` and `minimal` tfvars profiles and a committed `.terraform.lock.hcl`; the Helm charts with `image.registry`, `image.repository` and `image.digest` as values, and the rendered manifests committed; the `images` job building the arm64 Marquez image; the policy scan, `tflint`, `kubeconform` and the rendered-manifest drift check | M19 |
| **10. Hardening, documentation and the demo** | none | The demo runbook; the extrapolation list; the gap script; the completed local-versus-cloud diff; the ClickHouse upgrade drill; the watch-list with its re-review triggers | M22, M23, M18 (extrapolation list), M20 (the GDPR-shaped statement) |

**Where the phase order diverges from the benchmark order: nowhere.** Phase 3 is exactly P0 plus the batch benchmark group, Phase 6 is exactly the streaming group plus its compaction window, and Phase 8 is the incident laboratory. Constraint 6 of the benchmark plan puts the incident laboratory after every benchmark, so no earlier phase can carry it.

**Three placements are forced by dependencies rather than chosen.**

- **The network spine precedes the commerce CDC path.** The `streaming` profile declares the RIPE Atlas collector as a resident ([profiles register](../deployment/budgets/profiles.yaml)), and the collector is the network spine's producer. The profile is the reproducibility unit an evidence item names, so the first phase to close under `streaming` must be one where the RIPE path exists. The alternative, amending the profile so a phase closes more easily, is rejected: the service list is fixed by [the completion bar](completion-bar.md) section 8, and the register's own relief valve for that residency is a measured ClickHouse workload that does not exist yet.
- **The data-quality gate precedes the observability class.** Completion bar 6.10 requires the dashboard set to cover DQ pass rate, so the check results must exist before the observability instances can be complete. The gate is therefore a prerequisite of the incident laboratory, not a peer of it.
- **The incident laboratory is last.** The benchmark plan puts it after every benchmark so a benchmark's co-tenancy is never polluted by an injected fault.

**One benefit of the network spine preceding the CDC path, worth recording.** The RIPE ingestion job is Flink SQL writing Iceberg in upsert mode, so it exercises the native Iceberg upsert sink at Phase 4. The CDC path at Phase 5 then inherits a sink that has already written merge-on-read upsert into a real table, and the only mechanism unique to it is the custom keyed LSN operator, whose logic is unit-tested from Phase 1.

## 4. The run sequence and the readiness assertion per phase

### 4.1 The runs

A run is one bring-up under one profile, following the four-phase runbook in [the local development architecture](local-development.md) section 6: preflight, ordered start, readiness confirmation, teardown and reset.

**The readiness assertion is the same for every run**, and this is what "the exact readiness assertion" means: the profile's assertions under `tests/<profile>/` pass, an OOM-killed profile service is surfaced as a profile-budget failure rather than as an application bug, the observed peak from `podman stats` is within the declared entitlement, and the resolved `podman-compose config` and the image digests actually pulled are captured. A profile that starts but fails its assertions is not ready. A benchmark run additionally proves its reset, by following the reset procedure and reaching the same assertion on a fresh bring-up.

| Phase | # | Profile | Purpose | Host tier | Reset proof |
|---|---|---|---|---|---|
| 0 | 0.1 | `smoke` | the repository contract, and each service's container check | any tier the preflight passes | no |
| 1 | 1.1 | `batch`, reduced permitted | the commerce batch path end to end at the correctness slice | tier 2 or better | no |
| 2 | 2.1 | `batch`, reduced permitted | the asset graph, the backfill and re-run assets, the batch gate | tier 2 or better | no |
| 3 | 3.1 | `batch` | P0 fixture establishment at the declared volume | tier 1 or 2 | no |
| 3 | 3.2 | `benchmark` | B1 the layout sweep as two bring-ups, a write and compaction run then a serving run; B2 the two-arm comparison; B6 the schema-evolution counters; B7 the batch wall-clock; B9 the two swap drills | tier 1 or 2 | **yes, per benchmark** |
| 4 | 4.1 | `streaming` | the network streaming half: the collector and the RIPE ingestion job | tier 2 or better | no |
| 4 | 4.2 | `batch` | the network batch half: ONSPD, SCD2, the spatial join, the network serving copy, the source-hazard checks | tier 2 or better | no |
| 5 | 5.1 | `streaming` | the commerce CDC path in full: the four hard cases, reconciliation, the replication slot, kill and restore, the savepoint, the exactly-once effect, the streaming half of the gate | tier 2 or better | no |
| 5 | 5.2 | `batch` | the Dagster-owned Flink lifecycle (deploy, restart, savepoint) against a Flink cluster brought up for the purpose | tier 2 or better | no |
| 6 | 6.1 | `benchmark` | B3 the tuning record, B4 freshness on both arms | tier 2 or better | **yes, per benchmark** |
| 6 | 6.2 | `streaming` | B5 the CDC ingest cost | tier 2 or better | **yes** |
| 6 | 6.3 | `batch` | the `rewrite_data_files` compaction window that B5's compaction counter needs | tier 2 or better | **yes** |
| 7 | 7.1 | `batch` | the batch-path denials, the lineage emission, retention and TTL | tier 2 or better | no |
| 7 | 7.2 | `streaming` | the CDC-path denials and lineage | tier 2 or better | no |
| 8 | 8.1 to 8.6 | a path profile, **non-reduced** | the six incidents, one at a time | **tier 1 only** | no |
| 9 | none | n/a | CI validation only | n/a | n/a |
| 10 | none | n/a | CI validation only | n/a | n/a |

**The host tiers are the preflight's, from [the local development architecture](local-development.md) section 5.** Tier 1 is 7.5 GiB free or more, where the full path profile fits. Tier 2 is between 7.0 and 7.5 GiB free, where the preflight offers the profile's declared reduced variant and **no alert drill can be produced**. Below 7.0 GiB the preflight refuses, and neither path profile fits.

**Tier 2 is sufficient for every phase except Phase 8.** Phases 4 to 7 need no alert to fire, so a reduced run is a legitimate closure for them, and its evidence item is labelled as reduced. Phase 8 is the only phase whose gate requires an unprompted alert reaching a real destination, and a reduced run drops the three services that make that possible. **Phase 8 therefore cannot close on a host with between 7.0 and 7.5 GiB free.** That is a property of the gate, not a caveat.

### 4.2 The never-co-resident constraints

- Phase 3's two runs never overlap: P0 under `batch` completes before any `benchmark` run starts, because a benchmark's co-tenancy must be the declared set.
- Phase 4's two runs never overlap: the streaming half is torn down before the batch half starts.
- Phase 5's two runs never overlap, for the same reason.
- Phase 6's runs never overlap, and the compaction window is a separate `batch` run because Spark and the streaming stack cannot be co-resident.
- Phase 7's two runs never overlap.
- Phase 8's incidents never overlap each other, and never run alongside `benchmark`.
- No `benchmark` run ever overlaps a path profile run.

## 5. The per-phase definition of done

**The definition of done is the register, not prose.** A phase is done when the instances it admits are `complete` with at least one `behaviour` evidence item, their failure modes were enumerated in the register before the work, every `not_applicable` entry carries a reason, and every budget they cite resolves to an entry that is not `pending`. [The completion bar](completion-bar.md) supplies the eight core-checklist items and the eleven class deltas; this section says only which instances land when.

The **representative** column is what makes "every populated class has exactly one representative instance" checkable phase by phase, and it is also when each class's mutation-note obligation is discharged.

| Phase | Register instances admitted | Class | Representative assigned |
|---|---|---|---|
| 0 | the compose and profile layer | `infrastructure-as-code` | no |
| 1 | the TPC-H silver and gold assets | `spark-batch` | no |
| 1 | `commerce.gold.fact_lineitem`, the commerce `dim_*` | `iceberg-table-management` | no |
| 1 | the P1 materialised copies | `clickhouse-serving` | no |
| 2 | the Dagster asset graph, the backfill and re-run assets | `orchestration` | **yes** |
| 2 | the batch gate | `data-quality` | **yes** |
| 3 | the P1 layout variants and the two-arm comparison | `clickhouse-serving` | **yes** |
| 3 | the layout variants and the schema-evolution counters | `iceberg-table-management` | **yes** |
| 3 | the TPC-H batch assets at the declared volume | `spark-batch` | **yes** |
| 4 | the RIPE topic | `kafka-ingestion` | no |
| 4 | the RIPE ingestion job | `flink-streaming` | no |
| 4 | `network.gold.fact_measurement_result` and the per-minute aggregate | `iceberg-table-management` | no |
| 4 | the P2 copies | `clickhouse-serving` | no |
| 4 | the source-hazard checks | `data-quality` | no |
| 5 | the TPC-C topics | `kafka-ingestion` | **yes** |
| 5 | the CDC ingestion and serving jobs | `flink-streaming` | **yes** |
| 5 | `commerce.gold.fact_order_line`, `fact_stock`, `fact_delivery` | `iceberg-table-management` | no |
| 5 | the TPC-C topics as a capability | `cdc-ingestion` | **yes** |
| 5 | the P3 copies | `clickhouse-serving` | no |
| 6 | the streaming tuning, freshness and ingest-cost records | (evidence on the Phase 4 and 5 instances) | no |
| 7 | the catalog and serving authorisation instances, the lineage instance, the retention instance, the PII instance | `governance-and-lineage` | **yes** |
| 8 | the dashboard set, the alert rules, the six incidents | `observability` | **yes** |
| 9 | the OpenTofu modules, the Helm charts | `infrastructure-as-code` | **yes** |
| 10 | the demo run, the extrapolation list, the watch-list | (no new class) | no |

**The core-checklist items that are genuinely hard, per phase.** Item 1 (the implementation is the only path) and item 7 (reproducible bring-up) are hard in every phase, so they are not repeated below.

| Phase | The items that need explicit attention |
|---|---|
| 0 | item 6, because every service's failure modes must be enumerated before the compose files are frozen, and the not-applicable discipline applies to the container checks |
| 1 | item 3, realistic data, because the correctness slice is a labelled reduction; item 2, the mutation note on the LSN operator's unit test |
| 2 | item 5, because the gate's own health needs a signal; item 6, because the quarantine budget is a declared expectation |
| 3 | item 8, the budget committed before the judged run, which is the whole point of the phase; item 4, because a benchmark record's controls are its documentation |
| 4 | item 3, because the RIPE source is at-most-once and the replay is the fixture; item 6, because the publisher's hazards are enumerated in advance |
| 5 | item 6, the failure modes enumerated in advance, which is where the four hard cases come from; item 5, the checkpoint and lag signals |
| 6 | item 8 again, since every streaming threshold is `derived` and must be committed before its judged run |
| 7 | item 2, because a denial test that cannot fail is not a test; item 5, because an unattributable denial is the documented limit |
| 8 | item 5 in full: an alert shown firing unprompted is the only thing that promotes an observability signal to behaviour |
| 9 | item 7, recorded as `not_applicable` with its reason, because nothing is applied and no profile runs |
| 10 | item 4, documentation, which is the phase's whole subject |

## 6. The mapping from the mission's twelve blocks

[the Project Mission](mission/MISSION.md) section 33 sketches twelve blocks, Phase 0 to Phase 11. This roadmap has eleven phases, and the mapping is not one to one.

| Mission block | Where it lands |
|---|---|
| Phase 0, research and architecture | **The map itself.** The map is planning-only, so this is not a build phase |
| Phase 1, core ingestion and Iceberg | Roadmap Phase 1 |
| Phase 2, batch processing | Roadmap Phase 1 (the path), Phase 2 (orchestration and the gate), Phase 3 (the declared volume and the measurements) |
| Phase 3, streaming and Flink | Roadmap Phase 1 (the operator's unit test), Phase 4 (the network half), Phase 5 (the commerce half) |
| Phase 4, serving and ClickHouse | Roadmap Phase 1 (the copy), Phase 3 (the comparison) |
| Phase 5, orchestration and DQ | Roadmap Phase 2 |
| Phase 6, governance and lineage | Roadmap Phase 7 |
| Phase 7, observability and alerting | Roadmap Phases 4 to 7 author the rules; Phase 8 completes the class and fires the alerts |
| Phases 8 and 9, Kubernetes with Helm, and Terraform with AWS | Roadmap Phase 9, merged because both are authored and statically validated with no profile |
| Phase 10, performance and failure engineering | Roadmap Phase 3 and Phase 6 (the measurements), Phase 8 (failure engineering) |
| Phase 11, hardening and documentation | Roadmap Phase 10 |
| **not named by the sketch** | **Roadmap Phase 4, the network spine.** The sketch predates the two-spine dataset decision, so it has no network phase |

## 7. The interview-facing mapping

**This is a mapping, not an ordering driver.** The phase order is fixed by engineering dependencies, and section 3 records the three that are forced. [the requirements matrix](requirements-matrix.md) section 4 ranks the five load-bearing rows, and that ranking decides where the roadmap's emphasis and demo effort goes, not when a phase runs.

| Rank | Row | First evidenced | Why there and not earlier |
|---|---|---|---|
| 1 | M5, physical table layout | Phase 3 | the benchmark order puts P0 and B1 first |
| 2 | M7, the materialised serving store | Phase 3 | B2 needs B1's winning layout, so the two share a phase |
| 3 | M2 and M3, end-to-end CDC correctness | Phase 5 | the `streaming` profile declares the RIPE collector, so the network spine must close under that profile first |
| 4 | M16, the incident laboratory | Phase 8 | the benchmark plan puts the incident laboratory after every benchmark |
| 5 | M13, governance that stops something | Phase 2 for the batch gate, Phase 4 for the source-hazard checks | the gate is a prerequisite of the observability class and of the CDC path's dead-letter sink |
| 6 | M18, cost at scale | Phase 6 | its measured axis is B5, the last streaming benchmark |

The one visible consequence is that M2 and M3 are evidenced fifth rather than third, and that M13's batch half is evidenced before both. That is the dependencies-primary rule working, and it is recorded here so the two documents do not read as contradicting each other.

## 8. What is deferred, and what triggers a revisit

A limitation with a substitute gets a phase. A limitation that waits on the world gets a trigger. Nothing here is a new decision; every row is a limitation some other ticket already recorded.

| Limitation | Disposition |
|---|---|
| `sqlfluff` cannot parse ClickHouse `PROJECTION` clauses | **Phase 3**, where the ClickHouse DDL is executed against the pinned engine. That execution is the substitute and it is already the completion bar's standard. The permanence claim is superseded: PR 8585 merged on 2026-09-28 and is unreleased as of 2026-09-30, the latest release being 4.3.0. Trigger: a release carrying 8585, which is when the pin should be taken and the limitation retires |
| The Phase 1 TPC-H bronze load under the declared batch profile | **Closed, 2026-10-03 (issue #34).** The declared 256 MiB SeaweedFS ceiling carries the load once the store's volume index is on disk and the Go heap is bounded; the load peaks at 171.9 MiB anonymous and `tests/batch/test_tpch_bronze.py::test_the_bronze_load_is_correct_and_idempotent` passes under the declared profile. The measurement is in [`docs/local-development.md`](local-development.md) section 11. The declared volume SF100 remains a Phase 3 run, and the volume used is recorded in [`tests/fixtures.yaml`](../tests/fixtures.yaml) |
| The read-through REST path was not exercised ([ADR-0025](adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md)) | **Closed, not deferred.** B2's comparison arm at Phase 3 exercises it |
| The Flink v3 upsert writer is unverified ([ADR-0025](adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md)) | **Phase 5** covers the v2 upsert writer. Trigger: a table that needs v3 upsert, or the ClickHouse LTS that reads deletion vectors (27.3, late March 2027) |
| The arm64 Marquez image has never been executed | **Phase 9** authors and pushes it on a `demo-*` tag. Trigger: the priced demo window, where it is pulled on arm64 EKS. The limit stands: the build being produced is not the image running |
| The ECR path is authored and unused | **Phase 9** authors it in the `reference` arm, which is never applied and which the demo does not create. Trigger: a decision to move the demo to ECR, which is a values change plus an image copy and is itself unproven |
| Cloud evidence is unreachable: no real S3, IAM evaluation, VPC routing, RDS failover, EKS scheduling or Helm release | **Phase 9** for the authored and statically validated half, **Phase 10** for the demo runbook. Trigger: the priced window. The demo is never an evidence item |
| Incident 6 cites no budget for a collector error rate | **Phase 4**, where the collector's own metrics first exist. The threshold is declared with the alert rule it judges, which precedes its Phase 8 run |
| The engine-pin re-review: Iceberg 1.12.0 reaching GA with the Flink 2.3 and Spark 4.2 connector artifacts on Maven Central | **Trigger only, no phase.** This was the map's last fog patch and it lives here now |
| The CI protection-surface gaps: no merge queue, no required workflows, no team reviewers, no push rulesets on a user-owned repository | **Phase 0** records them. Trigger: if the repository moves to an organisation, three of the four become available at once |
| The Dagster acquisition risk (Prefect, 13 July 2026) | Trigger: B9's catalog and storage swap drills at Phase 3 price the cheapest layer; a longevity re-review re-runs the rubric |
| `tflint`'s BUSL-1.1 component reported but not confirmed | **Phase 9**, folded into the licence audit's scope |
| The lint tool list is proposed, not measured | **Phase 0**, as each job lands |
| `sha_pinning_required` is currently `false` | **Phase 0** switches it on, and records that SHA pinning trades Dependabot action alerts for immutability |
| The whole runbook is unexecuted, and only one compose provider is named | **Phase 0** is the first execution, and its failures are Phase 0 work rather than Phase 1 surprises |
| The reduced variant cannot produce an alert drill | **Phase 8** is tier 1 only. This is a gate condition rather than a deferral |
| The completion bar's fourteen named gaps | Not in this table. They are the register's `not_applicable` fields and are resolved per instance as the instances land |

## 9. Named constraints

1. **No new component and no new profile.** Every phase is expressed in the twenty components and the five profiles already settled.
2. **This is a plan, not a schedule.** No dates, no durations, no time estimates, and no measured result.
3. **No benchmark moves.** The measurement order is the benchmark plan's, and this roadmap's phase boundaries are drawn around it.
4. **The register is the definition of done.** No per-phase DoD document is written, and the completion bar is not restated.
5. **Every phase leaves a working system**, and every run reaches its readiness assertion before any evidence is captured.
6. **Entitlements are not thresholds.** Resource ceilings live in `deployment/budgets/profiles.yaml`; thresholds live in `docs/budgets.yaml` ([ADR-0031](adr/0031-the-local-execution-model-is-profile-scoped-and-host-anchored.md)).

## 10. What this document does not decide

- **The demo narrative.** [The interview and demo narrative](https://github.com/SoongGuanLeong/de-platform/issues/29) owns the walkthrough, the scenario set and the gap script. This document says only when each load-bearing row is first evidenced.
- **`PROPOSAL.md` and the presentation.** [PROPOSAL.md and the portfolio presentation](https://github.com/SoongGuanLeong/de-platform/issues/28) owns the index and the framing.
- **The register's instance ids and the budget ids each instance cites.** Those are written as the instances land, which is what makes the register an artefact of implementation rather than of planning.
- **The pipeline job graph and the CI job contents.** [The CI/CD strategy](ci-cd-strategy.md) owns those; this document names the runs and the profiles.

## 11. Impact items for approval

One, found while writing the run sequences, and not applied here.

**The `benchmark` profile's description is narrower than its own worked example.** [the completion bar](completion-bar.md) section 8 describes `benchmark` as "One component at a time under a declared resource budget. Never the whole stack", while `deployment/budgets/profiles.yaml`'s worked example for the M5 layout benchmark is three services (ClickHouse 6144 MiB, PostgreSQL 384, SeaweedFS 256, peak 6784 MiB), and [the benchmark plan](benchmark-plan.md) section 5.2 calls that example the precedent for B1. This roadmap reads `benchmark` as **a narrowed bring-up of the path's services with the component under test sized up, never the whole path profile**, which is what the worked example already demonstrates. On that reading the only amendment needed is one clause in completion-bar section 8: "one component under test at a time, never the whole path profile". Flagged rather than applied, because it edits a closed ticket's artefact.

---

*Resolved by [the roadmap ticket](https://github.com/SoongGuanLeong/de-platform/issues/27) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Inputs: [`docs/completion-bar.md`](completion-bar.md), [`docs/benchmark-plan.md`](benchmark-plan.md), [`docs/local-development.md`](local-development.md), [`docs/ci-cd-strategy.md`](ci-cd-strategy.md), [`docs/repository-decomposition.md`](repository-decomposition.md), [`docs/incident-laboratory.md`](incident-laboratory.md), [`docs/requirements-matrix.md`](requirements-matrix.md), [`docs/testing-strategy.md`](testing-strategy.md), [`docs/data-architecture.md`](data-architecture.md), [`docs/streaming-jobs.md`](streaming-jobs.md), [`deployment/budgets/profiles.yaml`](../deployment/budgets/profiles.yaml) and [`docs/mission/MISSION.md`](mission/MISSION.md).*
