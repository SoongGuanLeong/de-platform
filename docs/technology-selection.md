# Technology selection: what goes in, what stays out, and why

This is the technology-selection matrix the mission's Final Deliverables item 6 requires, produced by ticket [The technology-selection matrix](https://github.com/SoongGuanLeong/de-platform/issues/8) on map #9. It answers the seven questions for every component, records the disposition of every candidate that was considered and dropped, settles the four positions the ticket named, and ends with the technology count and its defence.

It rests on the research in `docs/research/`, in particular the support-and-longevity audit (03), object storage (02), the catalog and serving research (04, 05, 07, 08), the Flink sink research (06), and the four comparisons commissioned for this ticket: the write path (10), the schema registry (11), the orchestrator (12) and the lineage backend (13).

## The method

Three filters, applied in order, to every component.

1. **The support-and-longevity rubric.** Foundation governance preferred; a company-backed project with disclosed funding and a commercial incentive acceptable; observable activity as a hard floor. A component failing any leg is out. Evidence is dated and cited, in `docs/research/03-longevity-audit.md`.
2. **The mission's sprawl test (section 29).** If two technologies solve the same problem, choose one. A second is admitted only for a concrete reason: a different workload, an interoperability demonstration, a migration scenario, a comparison benchmark, or target-job alignment.
3. **The requirement mapping.** Every component names the requirement it demonstrates, in `docs/requirements-matrix.md`. A tool the posting names still has to pass filters 1 and 2. A tool the posting does not name is admitted only against a named requirement, and is recorded as an **addition** rather than folded into the posting's stack.

Every surviving choice carries at least one rejected alternative with a reason. A component chosen without a documented rejected alternative is not a decision.

## The stack at a glance

| Component | Pin | Problem it solves | Why needed here | Chosen over | Requirement | Longevity |
|---|---|---|---|---|---|---|
| Apache Iceberg | 1.11.0 | Open table format | The lakehouse itself: one table that Flink, Spark and ClickHouse all read and write without copying | Delta Lake, Hudi | M17, M3, M5 | PASS, irreplaceable |
| Apache Polaris | 1.7.0 | Iceberg REST catalog, governance namespace, credential vending | The posting names it; measured to vend a prefix-scoped SeaweedFS credential whose session policy is enforced | Lakekeeper, Unity Catalog OSS, Nessie, Hudi/Hadoop, Dremio | M9, M10, M17 | PASS with caution (6-week cadence) |
| SeaweedFS | 4.47 (`weed mini`) | S3-compatible object storage with an embedded Iceberg REST catalog | MinIO is dead; this is the only option that fits the host and has a first-party ClickHouse guide | RustFS, Garage, Ozone, Ceph, LocalStack | M19, M1 | PASS with caution (bus factor 1) |
| Apache Kafka | 4.3.1, KRaft | Durable, replayable log | Debezium's sink; the replayable source the streaming correctness claim needs | Redpanda, Pulsar, Kinesis | M2 | PASS, irreplaceable |
| Debezium | 3.6.1 | CDC from the Postgres binlog | The only T1 source: real change events, including the NULL-to-value updates that break naive upserts | Flink CDC, triggers | M2 | PASS with caution (Red Hat build lags) |
| Apache Flink | 2.3.0 | Stateful streaming, upsert into Iceberg | The real-time path, and the only Iceberg writer that emits key-only equality deletes | Kafka Connect Iceberg sink, Spark Structured Streaming | M3, M8 | PASS |
| Apache Spark | 4.2.0 | Batch silver and gold, compaction, serving load | The posting names it; batch MERGE, `rewrite_data_files`, and the batch arm of the serving feed | (none serious) | M4, M5 | PASS with caution (Java story) |
| ClickHouse | 26.8 LTS | Analytical serving store | The posting names it; the only place column-level and row-level enforcement exists | Druid, Pinot, StarRocks, Trino, DuckDB | M7, M8, M20 | PASS with caution (monthly breaking changes) |
| PostgreSQL | 18.x | OLTP source and metadata store | The CDC source must be a real database; it also holds Polaris, Dagster, Apicurio and Marquez metadata | MySQL, CockroachDB | M2, M19 | PASS |
| Dagster | 1.13.x | Orchestration | `@asset_check` is the only first-class data-quality gate among the candidates | Airflow, Prefect, Argo Workflows, Flyte | M13, M14 | PASS with caution (Prefect acquisition) |
| Apicurio Registry | 3.3.x | Schema registry | The schema-versioning evidence the contract requirement demands; Confluent v7/v8 compatible | Confluent SR, Karapace, Redpanda SR, Glue, none | M9, M17 | PASS with caution (weak L2) |
| OpenLineage | 1.53.0 | Lineage emission spec | The portable asset: the spec outlives any backend | (none) | M11 | PASS |
| Marquez | 0.51.x | Lineage backend | The reference OpenLineage consumer; the posting names it | DataHub, OpenMetadata, no backend | M11 | PASS with caution (stalled cadence) |
| Prometheus | 3.14.0 | Metrics | The posting names it | VictoriaMetrics, InfluxDB | M15 | PASS |
| Grafana | 13.x | Dashboards | The posting names it; dashboards held as code in Git | Perses | M15 | PASS with caution (AGPL, Enterprise split) |
| Alertmanager | 0.34.x | Alerting | The posting names it | (none) | M15 | PASS |
| Helm | 4.3.0 | Packaging | The posting names it; charts authored and lint-checked, never applied | Kustomize | M19 | PASS with caution (v3 support ends Nov 2026) |
| OpenTofu | 1.12.0 | Infrastructure as code | Terraform failed the rubric on licence; OpenTofu is the same-HCL drop-in | Terraform, Pulumi | M19 | PASS |
| Podman | 6.1.x | Container runtime | The host has no Docker; the compose contract stays portable | Docker | M19 | PASS (5.7 is EOL) |

Nineteen components. The count and its defence are below.

## Rejected candidates and their disposition

Grouped by the problem they would have solved. Every candidate the effort considered is listed, with the reason it is out.

**Table format.** Delta Lake and Hudi: rejected. Neither matches Iceberg's cross-engine read and write parity for this stack, the posting names Iceberg, and the mission's sprawl test admits one format. Iceberg is also one of the two components the audit calls genuinely irreplaceable.

**Catalog.** Lakekeeper is **not rejected**; it is the documented fallback (Apache-2.0, Rust, the same REST spec, hours to switch). Unity Catalog OSS: rejected, a different auth model, loses the any-engine property, days-to-weeks to adopt. Nessie: rejected, a different versioning model, medium-high cost. Hudi/Hadoop catalog: rejected, different catalog semantics, only sensible alongside a format migration. Dremio OSS: rejected, it drags a query engine into the picture. OpenMetadata and DataHub as catalogs: rejected, they are metadata platforms, not catalogs.

**Object storage.** MinIO: rejected, archived 25 April 2026 with the container image withdrawn, fails the rubric's hard floor. RustFS: **fallback, not rejected**, but the audit rules it ineligible to hold data that cannot be lost (discretionary CLA, Iceberg catalog Preview, no disclosed funding). Garage: rejected, no bucket policies, no versioning, no SSE, no object lock, AGPL, and a three-node minimum. Apache Ozone: rejected on footprint, roughly 1.7 TB RAM minimum and containers not recommended. Ceph: rejected on footprint, roughly 28 GB minimum against a 14 GB machine. LocalStack: rejected, archived and no longer licensed for hobby use; moto and S3Mock cover the testing need. Cloudflare R2 and Backblaze B2: not rejected, recorded as the CI and demo runway rather than the local store.

**CDC and transport.** Flink CDC and database triggers: rejected, Debezium is the posting's tool, is now Commonhaus-governed, and TPC-C on live Postgres is the only source that yields real binlog events. Redpanda: rejected, adopting its schema registry would mean replacing Kafka with Redpanda. Pulsar and Kinesis: rejected, neither is the posting's tool and neither is locally justified.

**The Flink-to-Iceberg write path.** The Kafka Connect Iceberg sink: rejected. It is append-only, so a redelivered change becomes a duplicate row and the convergence claim fails; it would break ADR-0002. Two specific claims died under research: "Confluent's iceberg-kafka-connect" does not exist (the repository returns 404, and Confluent's Iceberg product is Tableflow, a managed cloud feature), and the maintained-looking Databricks fork is explicitly not maintained, its code donated to Apache. The Apache `kafka-connect` module is real and active but append-only, with its own open issue #17542 saying so. Spark Structured Streaming: rejected for the real-time path, append-only, needing `foreachBatch` plus `MERGE INTO`, which is batch work wearing a streaming label. Note that the posting's "Kafka Connect" mention is satisfied by Debezium running as a Kafka Connect source connector, so it does not force a second Iceberg writer.

**Serving.** Trino and any federated query engine: rejected, out of scope, the posting names only ClickHouse, and an unexercised Trino proves nothing. Druid and Pinot: rejected, they duplicate ClickHouse's job for a real-time-OLAP need ClickHouse already meets. StarRocks: rejected, same duplication. DuckDB: rejected as a serving engine, though it stays a local analysis convenience.

**Orchestrator.** Apache Airflow: **fallback, not rejected**, the safer longevity bet as an ASF TLP, but it has no asset checks and a heavier local footprint. Prefect: rejected on fit, no partitions, no asset checks, asset health not event-backed, no OpenLineage. Argo Workflows: rejected, it requires a Kubernetes cluster, is YAML-first against the posting's Python requirement, and has no asset or partition model. Flyte: rejected on fit, well-governed and Python-first but Kubernetes-based and task-oriented rather than asset-oriented.

**Schema registry.** Confluent Schema Registry: rejected on licence, the Confluent Community License is source-available and not OSI-approved, with an excluded-purpose non-compete. Redpanda Schema Registry: rejected, it is built into the Redpanda broker, so adopting it replaces Kafka. Karapace: **the verified Apache-2.0 exit**, Aiven-governed, with a Schema Registry 6.1.1 compatibility target. AWS Glue Schema Registry: rejected, a serverless AWS service that cannot run locally. No registry: rejected, it removes the schema-versioning evidence the contract requirement needs. One correction recorded: Apicurio's Confluent compatibility is API v7 and v8, not v6 as an earlier draft stated.

**Lineage backend.** DataHub: rejected on the operational envelope, its own documentation states 8 GB RAM and 13 GB disk for the quickstart, which is the whole host. OpenMetadata: rejected on the operational envelope, its server minimum alone is 16 GiB against a 14 GB machine. No backend: the explicit fallback, zero footprint but it loses the lineage view and the directly named "Marquez" posting hit.

**Metrics, dashboards and alerting.** VictoriaMetrics and InfluxDB: rejected, the posting names Prometheus. Perses: rejected, Grafana is the posting's tool and the dashboards-as-code hedge already makes the Grafana-to-Perses move cheap.

**Infrastructure as code.** Terraform: rejected, relicensed to BUSL in 2023, fails the rubric. Pulumi: rejected, a different language model for no benefit over same-HCL OpenTofu.

**Container runtime.** Docker: rejected as a requirement, the host has no Docker, the compose and OCI contract keeps the platform portable, and podman 6.1.x is the local runtime. Docker-compatible authoring is retained deliberately so nothing is podman-only.

**Out of scope by prior decision, not revisited here.** dbt, Great Expectations and Soda (custom gated checks instead); Superset, Power BI and any BI tool; a vector database or RAG pipeline; cross-region and multi-account design; HIPAA and SOC 2 programmes.

## The four positions, settled

### 1. The catalog

**Depend on Apache Polaris, reached only through the Iceberg REST specification, with Lakekeeper as the documented fallback.** Polaris is the posting's tool and an ASF Top-Level Project since 15 February 2026. The risk that would have forced the fallback is closed by measurement: research 08 ran Polaris 1.7.0 against SeaweedFS 4.47 and confirmed it vends a real prefix-scoped credential whose inline session policy is enforced, with a sibling-prefix read refused. The cost of switching to Lakekeeper is hours, because both implement the same spec and the engines change only a URI and credentials, and it stays hours **only if** the running platform never calls Polaris-proprietary admin APIs. The one-time bootstrap may use the Management API. Catalog state stays in Postgres, and the Polaris minor is pinned. Recorded in ADR-0010.

### 2. How Iceberg reaches ClickHouse

**Batch by default, streaming for selected tables, with catalog read-through retained only as the comparison arm.** ADR-0003 already fixed the mechanism: shaped MergeTree copies rather than reading in place. The feed is Spark batch for every gold table, as a full refresh or a partition swap, idempotent and authoritative. A Flink streaming feed is admitted only for the small set of tables the real-time persona needs, upserted by key. The rule is "batch by default, streaming by exception, each exception named", because the seam fails when every table acquires two writers. Consistency and replay: the batch arm replaces whole partitions atomically, the streaming arm upserts by key and converges under replay, and the read-through arm is read-only and exists to be measured against. The concrete per-table pattern belongs to ticket [The serving layer's concrete shape](https://github.com/SoongGuanLeong/de-platform/issues/12).

### 3. The Flink-to-Iceberg write path

**Flink's native Iceberg sink, in upsert mode with declared equality fields on format v2 or later.** It is the only candidate that writes key-only equality deletes, so it is the only one whose committed state converges under Debezium's at-least-once redelivery, and it carries the checkpoint-id idempotency (`flink.max-committed-checkpoint-id`) that ADR-0002 rests on. The Kafka Connect Iceberg sink is rejected as append-only, and its rejection is now evidenced rather than asserted, which matters because the prior repository declared a Kafka Connect Iceberg sink that never existed. Sink configuration, equality fields and format version belong to ticket [The streaming job designs](https://github.com/SoongGuanLeong/de-platform/issues/13). Recorded in ADR-0011.

### 4. What Dagster orchestrates

**Dagster owns the batch Spark jobs, the data-quality gate, retention and snapshot expiry, the serving-layer materialisation, and the streaming job's deploy, restart and savepoint operations. It does not own the running Flink job's runtime.** A long-lived streaming service has its own lifecycle; orchestrating it means orchestrating its boundary operations, never a shell loop, which is the failure the prior repository exhibited with `nbclient` over notebooks. Failure propagation: a failed asset check with `blocking=True` quarantines its output and blocks downstream assets, and a failed asset fails the run and alerts, so nothing advances past a red gate. Two constraints the research added: Dagster's OpenLineage support is a community package, so Spark and Flink are the primary emitters and Dagster lineage is secondary; and Dagster ships no retention policy, so the retention requirement must be built as a documented pattern rather than assumed.

## The count

**Nineteen components.** Twelve are named by the posting: Debezium, Kafka, Iceberg, Polaris, Flink, Spark, ClickHouse, Dagster, Helm, Prometheus, Grafana and Alertmanager. Three are same-interface **substitutions** for a named tool: OpenTofu for Terraform, SeaweedFS for S3, Podman for Docker and EKS. Four are **additions** that a named requirement demands: PostgreSQL as the CDC source, Apicurio for the contract requirement, and OpenLineage with Marquez for the lineage requirement.

**One-line defence:** every component is a posting-named tool, a same-interface substitution for one, or an addition that a named requirement demands; two of them, Iceberg and Kafka, are irreplaceable, and the other seventeen each carry a recorded swap cost of between half a day and thirty days.

Against the mission's sprawl test, the pairs that look like duplication and their reasons: Flink and Spark are a genuinely different workload, real-time versus batch; ClickHouse's read-through and its MergeTree copy are an architecture and its comparison arm; Kafka Connect appears only as Debezium's runtime, not as a second Iceberg writer; Polaris and SeaweedFS both expose an Iceberg REST catalog, but SeaweedFS's is the dev convenience and Polaris is the governance plane, which is why the catalog is a swappable URI.

## Honest gaps

- **No benchmark was run and no footprint was measured.** Every threshold, memory figure and swap cost in this document is a plan or an estimate, not a result. Marquez's lean footprint in particular must be measured before it is committed.
- **Dagster's OpenLineage emitter is community-supported** (`dagster-openlineage` 0.2.1). It is pinned and watched, and the lineage guarantee is carried by the first-party Spark and Flink emitters instead.
- **Marquez's release cadence has stalled**, last GitHub release October 2024 with the most recent commit April 2026. It is treated as a swappable backend behind the OpenLineage transport, not an architectural commitment.
- **SeaweedFS has a bus factor of one** and its write amplification under Iceberg load is unmeasured. Its Iceberg catalog is the dev path only, not the governance path.
- **Dagster retention must be built.** The orchestrator has no built-in retention policy.
- **The Kafka Connect Iceberg sink comparison is closed** (research 10), but it was a gap when this ticket opened; the record is kept because the prior repository made a false claim here.

## Research this rests on

`docs/research/02-object-storage.md`, `03-longevity-audit.md`, `04-polaris-authorisation-model.md`, `05-clickhouse-polaris-integration.md`, `06-iceberg-flink-sink-write-modes.md`, `07-clickhouse-iceberg-credential-intake.md`, `08-seaweedfs-sts-interop.md`, `10-iceberg-write-path-comparison.md`, `11-schema-registry-comparison.md`, `12-orchestrator-comparison.md`, `13-lineage-backend-comparison.md`.
