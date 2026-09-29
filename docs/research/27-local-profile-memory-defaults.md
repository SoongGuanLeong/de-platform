# Local profile memory defaults: documented figures for the 19 pinned components

**Date read: 2026-09-29.** Ticket #25 ("The local development architecture"), wayfinder map #9.

**Scope and method.** This file records, for each component the ticket asks about, the documented default memory setting, any published minimum or recommendation, the JVM heap default where applicable, and whether the component is a long-running server or a run-to-completion client. Every figure is taken from a primary source: the component's official documentation, its official image Dockerfile/entrypoint, or its source repository. Nothing here is measured. No container was run and the host was not measured, per the ticket constraint that "nothing is measured while the map is open". Where a figure could not be confirmed, this file says **not published** rather than estimating.

**One caveat that applies throughout.** Heap settings are not process RSS. A JVM process adds metaspace, thread stacks, code cache and GC headroom on top of its heap, and a Go or C++ server has its own allocator overhead. So the sums in the arithmetic section are lower bounds on resident memory, not totals. They are still the only figures the documentation supports.

---

## 1. Apache Kafka 4.3.1 (KRaft, single broker) - `apache/kafka`

**(a) Documented/default memory setting.** The official image does **not** set a heap. The image's `docker/jvm/Dockerfile` contains no `KAFKA_HEAP_OPTS` (its only `ENV` lines are base-image settings), and the image's entrypoint, `docker/jvm/launch`, `exec`s `/opt/kafka/bin/kafka-server-start.sh` without setting `KAFKA_HEAP_OPTS`. The default therefore comes from Kafka's own `bin/kafka-server-start.sh`:

```sh
if [ "x$KAFKA_HEAP_OPTS" = "x" ]; then
    export KAFKA_HEAP_OPTS="-Xmx1G -Xms1G"
fi
```

`bin/kafka-run-class.sh` separately defaults `KAFKA_HEAP_OPTS="-Xmx256M"` for CLI tools that do not go through `kafka-server-start.sh`.

**(b) Published minimum/recommendation.** The image's own documentation page (hub.docker.com/r/apache/kafka) publishes **no memory figure**. It documents only that broker configuration can be overridden with `KAFKA_`-prefixed environment variables, and that supplying any override disables the image's default configuration set. **Not published.**

**(c) JVM heap default.** `KAFKA_HEAP_OPTS` = `-Xmx1G -Xms1G` for the broker (1 GiB heap), via `bin/kafka-server-start.sh`.

**(d) Server or client.** Long-running server.

**Citations.** `raw.githubusercontent.com/apache/kafka/trunk/bin/kafka-server-start.sh` lines 28-29; `.../bin/kafka-run-class.sh` lines 273-274; `.../docker/jvm/Dockerfile`; `.../docker/jvm/launch` line 68; `hub.docker.com/r/apache/kafka`. All read 2026-09-29.

---

## 2. ClickHouse 26.8 LTS - `clickhouse/clickhouse-server`

**(a) Documented/default memory setting.** Two settings govern the footprint, and neither is a fixed number:

- `max_server_memory_usage` - "The maximum memory consumption of the server is further restricted by setting `max_server_memory_usage_to_ram_ratio`. As a special case, a value of `0` (default) means the server may consume all available memory (excluding further restrictions imposed by `max_server_memory_usage_to_ram_ratio`)."
- `max_server_memory_usage_to_ram_ratio` - default `0.9`: "a value of `0.9` (default) means that the server may consume 90% of the available memory."
- `max_memory_usage` (per query, session setting) - default `0`, and "A value of `0` means unlimited."

So the documented default is a **ceiling of 90% of the memory available to the server**, not a fixed allocation. On a 14 GB host that is about 12.6 GB; on the ticket's 7-8 GB free it is 6.3-7.2 GB.

**(b) Published minimum/recommendation.** The official sizing guide states, for the memory-to-storage ratio: "For low data volumes, a 1:1 memory-to-storage ratio is acceptable but total memory shouldn't be below 8GB." It also gives memory-to-CPU-core ratios: M-type 4 GB:1 core, R-type 8 GB:1 core, C-type 2 GB:1 core.

**(c) JVM heap.** Not a JVM service (C++). No heap default.

**(d) Server or client.** Long-running server.

**Citations.** `clickhouse.com/docs/reference/settings/server-settings/settings/max-server-memory-usage` (read 2026-09-29); `.../session-settings/max-memory-usage` (read 2026-09-29); `clickhouse.com/docs/guides/oss/best-practices/sizing-and-hardware-recommendations` (read 2026-09-29).

---

## 3. Apache Polaris 1.7.0 - `apache/polaris`

**(a) Documented/default memory setting.** None. The Quarkus image's `runtime/server/src/main/docker/Dockerfile.jvm` sets no `JAVA_OPTS`, no `MaxRAMPercentage` and no `-Xmx`; its only `ENV` block is `LANGUAGE`, `USER`, `UID`, `HOME`, `AB_JOLOKIA_OFF` and `JAVA_APP_JAR`. The Helm chart is explicit: "`resources: {}` - This chart does not specify default resources and leaves this as a conscious choice for the user."

**(b) Published minimum/recommendation.** The official production guide recommends, for a production deployment: requests and limits of `memory: "8Gi"` and `cpu: "4"`. That is a production recommendation, not a local-development minimum, and the same page says to "Adjust these values based on expected workload and available cluster resources."

**(c) JVM heap.** No documented heap env var or flag, and no default. The JVM heap is left to the base image (`registry.access.redhat.com/ubi9/openjdk-21-runtime`) and the container's memory limit.

**(d) Server or client.** Long-running server.

**Citations.** `raw.githubusercontent.com/apache/polaris/main/runtime/server/src/main/docker/Dockerfile.jvm`; `.../helm/polaris/values.yaml` lines 501-515; `polaris.apache.org/releases/1.7.0/helm-chart/production/` (the 8Gi/4 figure was read on the pinned-version page). All read 2026-09-29.

---

## 4. PostgreSQL 18 - `postgres:18-alpine`

**(a) Documented/default memory setting.** The official image does **not** tune memory. Its Dockerfile (`docker-library/postgres`, `18/alpine3.23/Dockerfile`, `PG_VERSION 18.6`) sets no `shared_buffers` or other memory parameter. The upstream defaults therefore apply:

- `shared_buffers` - "The default is typically 128 megabytes (128MB)". Minimum: 128 kB.
- `work_mem` - default 4 MB.
- `maintenance_work_mem` - default 64 MB.
- `hash_mem_multiplier` - default 2.0.
- `effective_cache_size` - a planner estimate, not an allocation; it is not part of the resident footprint.

The docs add sizing advice rather than a default: "If you have a dedicated database server with 1GB or more of RAM, a reasonable starting value for shared_buffers is 25% of the memory in your system."

**(b) Published minimum/recommendation.** PostgreSQL publishes **no minimum system RAM**. The only documented minimum is for the `shared_buffers` setting itself (128 kB). **Not published** for a system minimum.

**(c) JVM heap.** Not a JVM service.

**(d) Server or client.** Long-running server.

**Citations.** `postgresql.org/docs/18/runtime-config-resource.html` lines 249-293 (read 2026-09-29); `raw.githubusercontent.com/docker-library/postgres/master/18/alpine3.23/Dockerfile` (read 2026-09-29).

---

## 5. SeaweedFS 4.47 - `chrislusf/seaweedfs`, `weed mini`

**(a) Documented/default memory setting.** None that bounds memory. `weed/command/mini.go` fixes volume sizing, not memory: `defaultMiniVolumeSizeMB = 128`, `minVolumeSizeMB = 64`, `maxVolumeSizeMB = 1024`, and the documented flags `-volume.fileSizeLimitMB 256`, `-s3.cacheCapacityMB 0` (in-memory chunk cache disabled), `-s3.readerCacheSizeMB 0` (unlimited reader buffers). The volume index is in memory by default (`-volume.index=memory`) and is rebuilt on restart. There is no documented memory ceiling or default.

**(b) Published minimum/recommendation.** The README states "`weed mini` is auto-tuned for one node and is fine for single-node production". The `weed mini` wiki page says it "starts all essential components in a single process with auto-tuned defaults" and is appropriate for development, testing and single-node production. No RAM minimum or figure is published. **Not published.**

**(c) JVM heap.** Not a JVM service (Go).

**(d) Server or client.** Long-running server. `weed mini` runs one Go process containing master, volume server, filer, S3 gateway, Iceberg REST catalog, WebDAV gateway, admin UI and a maintenance worker.

**Citations.** `raw.githubusercontent.com/seaweedfs/seaweedfs/master/weed/command/mini.go` lines 51-55, 205-215; `.../README.md` line 87; `raw.githubusercontent.com/wiki/seaweedfs/seaweedfs/Quick-Start-with-weed-mini.md`. All read 2026-09-29.

---

## 6. Apache Flink 2.1.3 - JobManager and TaskManager

**(a) Documented/default memory setting.** The two process-size keys have **no default value**:

- `jobmanager.memory.process.size` - documented default **"(none)"**. The Flink 2.1 source declares it `.noDefaultValue()`.
- `taskmanager.memory.process.size` - documented default **"(none)"**, also `.noDefaultValue()`.
- `taskmanager.numberOfTaskSlots` - default **1**.
- `taskmanager.memory.framework.heap.size` - default 128 MB.
- Task heap memory has "a default value of 128MB only for the local execution mode"; otherwise it is derived.

Because the process sizes are unset, the operator must supply them; Flink derives the component sizes from whichever of total-process or total-Flink memory is configured.

**(b) Published minimum/recommendation.** No minimum RAM is published. The docs say only: "The default memory sizes support simple streaming/batch applications, but are too low to yield good performance for more complex applications."

**(c) JVM heap.** There is no `-Xmx` default for JobManager or TaskManager. Heap is derived from the memory model, driven by `jobmanager.memory.process.size` / `taskmanager.memory.process.size` (both unset by default).

**(d) Server or client.** Both long-running: the JobManager is a server, the TaskManager a long-running worker. The `flink run` client is run-to-completion.

**Citations.** `nightlies.apache.org/flink/flink-docs-release-2.1/docs/deployment/config/` (read 2026-09-29); `raw.githubusercontent.com/apache/flink/release-2.1/flink-core/src/main/java/org/apache/flink/configuration/JobManagerOptions.java` lines 132-135; `.../TaskManagerOptions.java` lines 296-299; `.../docs/deployment/memory/mem_setup_tm/`. All read 2026-09-29.

---

## 7. Apache Spark 4.1.3 - driver and executor

**(a) Documented/default memory setting.**

- `spark.driver.memory` - default **1g**.
- `spark.executor.memory` - default **1g**.
- `spark.executor.cores` - "1 in YARN mode, all the available cores on the worker in standalone mode".
- `spark.driver.memoryOverheadFactor` and `spark.executor.memoryOverheadFactor` - default **0.10** (except Kubernetes non-JVM jobs).

The total process memory is heap plus overhead: "the memory for a running executor is determined by the sum of `spark.executor.memoryOverhead`, `spark.executor.memory`, `spark.memory.offHeap.size` and ...".

**(b) Published minimum/recommendation.** The configuration reference publishes no minimum RAM. **Not published.**

**(c) JVM heap.** `spark.driver.memory` and `spark.executor.memory` are the heap settings, both defaulting to 1g.

**(d) Server or client.** The driver is a long-running process for the life of the application; executors are long-running workers for the application's duration; `spark-submit` is run-to-completion.

**Citations.** `spark.apache.org/docs/4.1.3/configuration.html` (driver memory, executor memory, executor cores, memoryOverheadFactor entries). Read 2026-09-29.

---

## 8. Dagster 1.13.x - webserver + daemon + user-code

**(a) Documented/default memory setting.** None published. The OSS deployment documentation describes the webserver and daemon as processes to run and how to configure the instance, but sets no memory parameter or default.

**(b) Published minimum/recommendation.** No RAM or CPU guidance is published for self-hosted OSS Dagster. **Not published.** (Dagster+ is a separate managed product; its guidance, if any, is not applicable to the OSS compose profile.)

**(c) JVM heap.** Not a JVM service (Python).

**(d) Server or client.** The webserver and daemon are long-running servers; the user-code location server is long-running; individual runs are run-to-completion.

**Citations.** `docs.dagster.io/deployment/oss/deployment-options/deploying-dagster-as-a-service`; `docs.dagster.io/deployment/execution/dagster-daemon`; `docs.dagster.io/guides/operate/webserver`. Read 2026-09-29.

---

## 9. Apicurio Registry 3.3.x

**(a) Documented/default memory setting.** None published. The getting-started page documents storage variants (in-memory, SQL, Kafka, GitOps) and environment variables, and shows `docker run -it -p 8080:8080 apicurio/apicurio-registry:3.3.3`, but sets no heap or memory default.

**(b) Published minimum/recommendation.** No RAM/CPU guidance found in the official docs or the image README. **Not published.**

**(c) JVM heap.** It is Quarkus-based, but no documented heap env var or default is published. The heap is left to the JVM/container defaults.

**(d) Server or client.** Long-running server.

**Citations.** `apicur.io/registry/getting-started/` (read 2026-09-29); `raw.githubusercontent.com/Apicurio/apicurio-registry/main/distro/docker/README.md`; `.../docs/modules/ROOT/pages/getting-started/assembly-configuring-the-registry.adoc`. Read 2026-09-29.

---

## 10. Marquez 0.51.x

**(a) Documented/default memory setting.** None published. The Helm chart's `resources` block is empty, with commented examples only (`limits: memory: 1Gi`, `requests: memory: 256Mi`) and the comment "Typically best to not specify these settings, unless you've got a specific reason to customize."

**(b) Published minimum/recommendation - the quickstart RAM figure could not be confirmed.** The task states that Marquez's own docs give a quickstart RAM figure. I could not find one. The README's "Requirements" section lists only Java 17 and PostgreSQL 14. The quickstart prerequisites list only Docker 17.05+ and Docker Compose. The deployment and AWS pages give no memory figure. **Not published.** This is a documented gap, not an estimate: no RAM number is asserted here.

**(c) JVM heap.** JVM service, but no documented heap default. The entrypoint sets no `-Xmx`, which the project's own prior research already flagged (see `docs/research/13-lineage-backend-comparison.md` line 217: "The entrypoint sets no `-Xmx`, so without this the JVM will size its heap to the host").

**(d) Server or client.** Long-running server.

**Citations.** `raw.githubusercontent.com/MarquezProject/marquez/main/README.md` ("Requirements", read 2026-09-29); `.../docs/docs/quickstart/index.mdx`; `.../chart/values.yaml` lines 59-69 and 98-109; `marquezproject.ai/docs/quickstart/`. Read 2026-09-29.

---

## 11. Prometheus 3.14.0

**(a) Documented/default memory setting.** No memory setting. The storage default that determines long-run footprint is retention: "`--storage.tsdb.retention.time`: How long to retain samples in storage. If neither this flag nor `storage.tsdb.retention.size` is set, the retention time defaults to `15d`."

**(b) Published minimum/recommendation.** No minimum RAM is published. The storage documentation gives a disk-sizing formula (`needed_disk_space = retention_time_seconds * ingested_samples_per_second * bytes_per_sample`) and a retention-size recommendation ("we recommend setting the retention size to, at most, 80-85% of your [allocated disk]"), not a memory minimum. **Not published.**

**(c) JVM heap.** Not a JVM service (Go).

**(d) Server or client.** Long-running server.

**Citations.** `raw.githubusercontent.com/prometheus/prometheus/main/docs/storage.md` lines 94-96 and 141-149 (read 2026-09-29).

---

## 12. Grafana 13.x

**(a)/(b) Documented minimum.** The official installation page states: "Grafana requires the following minimum system resources: **Minimum recommended memory: 512 MB; Minimum recommended CPU: 1 core.**" It adds: "Some features might require more memory or CPUs", and gives a sizing table - Small: 2 cores / 2-4 GB; Medium: 4-8 cores / 8-16 GB; Large: 8-16+ cores / 16-32+ GB. Image rendering uses about 1 GB per renderer worker.

**(c) JVM heap.** Not a JVM service (Go).

**(d) Server or client.** Long-running server.

**Citations.** `grafana.com/docs/grafana/next/setup-grafana/installation.md` (read 2026-09-29). Note: this is the `next` documentation branch; confirm the same figures against the 13.x release docs at implementation time.

---

## 13. Alertmanager 0.34.x

**(a) Documented/default memory setting.** None.

**(b) Published minimum/recommendation.** No memory or resource guidance is published. The repository documentation covers configuration, the alerts API, high availability, HTTPS, notifications and integrations, but no sizing. **Not published.**

**(c) JVM heap.** Not a JVM service (Go).

**(d) Server or client.** Long-running server.

**Citations.** `raw.githubusercontent.com/prometheus/alertmanager/main/docs/alertmanager.md`; `.../docs/overview.md`; repository `docs/` tree. Read 2026-09-29.

---

## 14. Debezium 3.6.1 as a Kafka Connect distributed worker

**(a) Documented/default memory setting.** The Connect worker heap default comes from Kafka's own scripts, not from Debezium. `bin/connect-distributed.sh` (and `bin/connect-standalone.sh`) contain:

```sh
if [ "x$KAFKA_HEAP_OPTS" = "x" ]; then
  export KAFKA_HEAP_OPTS="-Xms256M -Xmx2G"
fi
```

The Debezium image chain sets no override: `debezium/docker-images` `connect/3.6/Dockerfile` is `FROM connect-base:3.6`, which is `FROM debezium/kafka:3.6` (a Kafka distribution); neither Dockerfile sets `KAFKA_HEAP_OPTS`. So a Debezium Connect distributed worker defaults to a **2 GiB max heap**.

**(b) Published minimum/recommendation.** Debezium's official documentation publishes no memory figure for the Connect worker. **Not published.**

**(c) JVM heap default.** `KAFKA_HEAP_OPTS` = `-Xms256M -Xmx2G` (2 GiB max heap) for the Connect worker.

**(d) Server or client.** Long-running server (distributed worker).

**Citations.** `raw.githubusercontent.com/apache/kafka/trunk/bin/connect-distributed.sh` lines 29-31; `.../bin/connect-standalone.sh` lines 29-31; `raw.githubusercontent.com/debezium/docker-images/main/connect/3.6/Dockerfile`; `.../connect-base/3.6/Dockerfile`. Read 2026-09-29.

---

## Table A - component, default, published minimum, server/client, citation

| Component | Default memory key and value | Published minimum | Server or client | Citation (read 2026-09-29) |
|---|---|---|---|---|
| Kafka 4.3.1 (`apache/kafka`) | `KAFKA_HEAP_OPTS=-Xmx1G -Xms1G` (broker, from `kafka-server-start.sh`; image sets none) | None published | Server | `apache/kafka` `bin/kafka-server-start.sh` L28-29, `docker/jvm/Dockerfile`, `docker/jvm/launch`; hub.docker.com/r/apache/kafka |
| ClickHouse 26.8 LTS | `max_server_memory_usage=0` (all available) x `max_server_memory_usage_to_ram_ratio=0.9` (90%); `max_memory_usage=0` (unlimited) | "total memory shouldn't be below 8GB" (sizing guide) | Server | clickhouse.com max-server-memory-usage, max-memory-usage, sizing-and-hardware-recommendations |
| Polaris 1.7.0 | None; Helm `resources: {}` by design; Dockerfile.jvm sets no heap | Production recommendation 8Gi memory / 4 CPU (requests and limits) | Server | polaris `Dockerfile.jvm`, `helm/polaris/values.yaml` L501-515, polaris.apache.org/releases/1.7.0/helm-chart/production/ |
| PostgreSQL 18 (`postgres:18-alpine`) | `shared_buffers=128MB`; `work_mem=4MB`; `maintenance_work_mem=64MB`; image tunes nothing | None published (setting minimum 128 kB) | Server | postgresql.org/docs/18/runtime-config-resource.html L249-293; docker-library/postgres 18/alpine3.23/Dockerfile |
| SeaweedFS 4.47 (`weed mini`) | None; `defaultMiniVolumeSizeMB=128`, `s3.cacheCapacityMB=0`, `s3.readerCacheSizeMB=0`, `volume.index=memory` | None published; "auto-tuned for one node" | Server | seaweedfs README L87, weed/command/mini.go L51-55, wiki Quick-Start-with-weed-mini |
| Flink 2.1.3 JM | `jobmanager.memory.process.size` default **(none)** | None published | Server | flink-docs-release-2.1 config; JobManagerOptions.java L132-135 |
| Flink 2.1.3 TM | `taskmanager.memory.process.size` default **(none)**; `taskmanager.numberOfTaskSlots=1`; framework heap 128MB | None published | Server (worker) | flink-docs-release-2.1 config; TaskManagerOptions.java L296-299 |
| Spark 4.1.3 | `spark.driver.memory=1g`; `spark.executor.memory=1g`; `spark.executor.cores=1` (YARN) / all (standalone); overhead factor 0.10 | None published | Driver/executor long-running; `spark-submit` client | spark.apache.org/docs/4.1.3/configuration.html |
| Dagster 1.13.x | None published | None published | Webserver/daemon server; runs client | docs.dagster.io deployment/oss, dagster-daemon, webserver |
| Apicurio Registry 3.3.x | None published (Quarkus; no heap default) | None published | Server | apicur.io/registry/getting-started/; apicurio-registry distro/docker/README.md |
| Marquez 0.51.x | None; Helm `resources` empty (commented 1Gi/256Mi examples) | **Quickstart RAM figure not found** | Server | marquez README Requirements; docs/docs/quickstart/index.mdx; chart/values.yaml L59-69 |
| Prometheus 3.14.0 | No memory setting; `--storage.tsdb.retention.time` default `15d` | None published | Server | prometheus docs/storage.md L94-96, L141-149 |
| Grafana 13.x | No memory setting | **512 MB memory, 1 CPU core** (recommended minimum) | Server | grafana.com/docs/grafana/next/setup-grafana/installation.md |
| Alertmanager 0.34.x | None published | None published | Server | alertmanager docs/alertmanager.md, docs/overview.md |
| Debezium 3.6.1 (Connect distributed) | `KAFKA_HEAP_OPTS=-Xms256M -Xmx2G` (worker, from `connect-distributed.sh`; image sets none) | None published | Server | apache/kafka `bin/connect-distributed.sh` L29-31; debezium docker-images connect/3.6 and connect-base/3.6 Dockerfiles |

---

## Table B - components with no confirmable documented figure

These are listed plainly. No figure is estimated or interpolated for them.

| Component | What is missing | What was searched |
|---|---|---|
| Kafka 4.3.1 | Image-level memory guidance / minimum | Image docs page (hub.docker.com/r/apache/kafka), Dockerfile, entrypoint, examples README |
| ClickHouse 26.8 | A fixed default allocation in MB | Settings reference, sizing guide (only a RAM-relative ceiling and an 8GB floor are published) |
| Polaris 1.7.0 | A default heap or default resource request; only a production recommendation exists | Dockerfile.jvm, Helm values.yaml, 1.7.0 production guide |
| PostgreSQL 18 | A minimum system RAM | runtime-config-resource docs, Docker official image docs |
| SeaweedFS 4.47 | A memory minimum or default ceiling | README, weed mini wiki, weed/command/mini.go |
| Flink 2.1.3 | A default JobManager/TaskManager process size | Flink 2.1 config reference and source (both are `.noDefaultValue()`) |
| Spark 4.1.3 | A minimum RAM | Spark 4.1.3 configuration reference |
| Dagster 1.13.x | Any RAM/CPU guidance for self-hosted OSS | docs.dagster.io deployment, daemon and webserver pages |
| Apicurio Registry 3.3.x | Any memory guidance or heap default | Getting-started page, image README, configuring-the-registry docs |
| Marquez 0.51.x | **The quickstart RAM figure the task asserts exists** | README Requirements, quickstart docs, deployment docs, AWS page, Helm values.yaml, site quickstart page |
| Prometheus 3.14.0 | A minimum RAM | Storage docs, FAQ |
| Alertmanager 0.34.x | Any memory guidance | Repository docs tree |
| Debezium 3.6.1 | A Debezium-published worker memory figure | Debezium docs, image Dockerfiles |

---

## Arithmetic: do the documented defaults fit 7-8 GB?

This is arithmetic over documented defaults only, not a measurement. The profiles are fixed by `docs/completion-bar.md` section 8.

**Documented fixed-MB defaults, where they exist:**

| Component | Documented default used | MiB |
|---|---|---|
| PostgreSQL | `shared_buffers` 128 MB | 128 |
| Kafka broker | `KAFKA_HEAP_OPTS` `-Xmx1G` | 1024 |
| Debezium Connect worker | `KAFKA_HEAP_OPTS` `-Xmx2G` | 2048 |
| Spark | `spark.driver.memory` 1g + `spark.executor.memory` 1g (one executor) + 10% overhead | 2252.8 |
| ClickHouse | **no fixed default** - a ceiling of 90% of available memory | n/a |
| Flink | **no default** (`process.size` = none) | n/a |
| Polaris | **no default** (Helm `resources: {}`); production rec 8Gi | n/a |
| SeaweedFS, Dagster, Prometheus, Alertmanager, Apicurio, Marquez | **no default** | n/a |
| Grafana | 512 MB (a recommended minimum, not an allocation) | (512) |

### Profile `batch` - PostgreSQL, SeaweedFS, Polaris, Spark, ClickHouse, Dagster

- Sum of documented fixed defaults: **128 + 2252.8 = 2380.8 MiB ~= 2.32 GiB**.
- Components with **no documented default**: SeaweedFS, Polaris, ClickHouse (no fixed figure), Dagster - **4 of the 6**.
- Add ClickHouse's documented default ceiling, 90% of available memory:
  - host-relative (14 GB host): 0.9 x 14 GiB = 12.6 GiB -> **sum ~= 14.9 GiB**, exceeding 8 GiB by **~6.9 GiB** and 7 GiB by **~7.9 GiB**.
  - budget-relative (90% of the 8 GiB free): 7.2 GiB -> **sum ~= 9.5 GiB**, exceeding 8 GiB by **~1.5 GiB** and 7 GiB by **~2.5 GiB**.
- **Does it fit? No.** Even the fixed-default floor (2.32 GiB) omits four of the six services, one of which (Polaris) is recommended at 8 GiB in production.

### Profile `streaming` - PostgreSQL, Debezium, Kafka, Flink, SeaweedFS, Polaris, ClickHouse

- Sum of documented fixed defaults: **128 + 2048 + 1024 = 3200 MiB ~= 3.13 GiB**.
- Components with **no documented default**: Flink, SeaweedFS, Polaris, ClickHouse (no fixed figure) - **4 of the 7**.
- Add ClickHouse's documented default ceiling, 90% of available memory:
  - host-relative (14 GB host): 12.6 GiB -> **sum ~= 15.7 GiB**, exceeding 8 GiB by **~7.7 GiB** and 7 GiB by **~8.7 GiB**.
  - budget-relative (90% of the 8 GiB free): 7.2 GiB -> **sum ~= 10.3 GiB**, exceeding 8 GiB by **~2.3 GiB** and 7 GiB by **~3.3 GiB**.
- **Does it fit? No.** The fixed-default floor (3.13 GiB) is lower than the batch floor only because Flink has no default at all; its real footprint is whatever the operator sets.

### Conclusion

**Neither profile fits in 7-8 GB on documented defaults alone, and the exceedance cannot be stated as a single number because four components per profile publish no default.** Under the most defensible reading - counting ClickHouse's documented 90%-of-available-memory ceiling - the batch sum exceeds 8 GiB by roughly 1.5-6.9 GiB and the streaming sum by roughly 2.3-7.7 GiB, depending on whether the ClickHouse ceiling is read against the host's 14 GB or the profile's 8 GiB. Excluding ClickHouse, the fixed documented defaults are a floor of 2.32 GiB (batch) and 3.13 GiB (streaming) that omits four services per profile. This is exactly the case for ticket #25's explicit per-service ceilings: the documentation does not supply a set of defaults that fits, so the budget has to be declared rather than inherited.

**One residual caveat.** Heap defaults are not resident memory. Each JVM (Kafka, Connect, Spark, Flink, Polaris, Marquez, Apicurio) adds metaspace, thread stacks, code cache and GC headroom above its heap, so every sum above understates the real working set. No measurement is offered to close that gap, per the ticket constraint.

---

## Source index

| Ref | Source | URL | Read |
|---|---|---|---|
| S1 | Apache Kafka `bin/kafka-server-start.sh` | https://raw.githubusercontent.com/apache/kafka/trunk/bin/kafka-server-start.sh | 2026-09-29 |
| S2 | Apache Kafka `bin/kafka-run-class.sh` | https://raw.githubusercontent.com/apache/kafka/trunk/bin/kafka-run-class.sh | 2026-09-29 |
| S3 | Apache Kafka `docker/jvm/Dockerfile` and `docker/jvm/launch` | https://raw.githubusercontent.com/apache/kafka/trunk/docker/jvm/Dockerfile | 2026-09-29 |
| S4 | `apache/kafka` image documentation | https://hub.docker.com/r/apache/kafka | 2026-09-29 |
| S5 | ClickHouse `max_server_memory_usage` reference | https://clickhouse.com/docs/reference/settings/server-settings/settings/max-server-memory-usage | 2026-09-29 |
| S6 | ClickHouse `max_memory_usage` reference | https://clickhouse.com/docs/reference/settings/session-settings/max-memory-usage | 2026-09-29 |
| S7 | ClickHouse sizing and hardware recommendations | https://clickhouse.com/docs/guides/oss/best-practices/sizing-and-hardware-recommendations | 2026-09-29 |
| S8 | Apache Polaris `Dockerfile.jvm` | https://raw.githubusercontent.com/apache/polaris/main/runtime/server/src/main/docker/Dockerfile.jvm | 2026-09-29 |
| S9 | Apache Polaris Helm `values.yaml` | https://raw.githubusercontent.com/apache/polaris/main/helm/polaris/values.yaml | 2026-09-29 |
| S10 | Apache Polaris 1.7.0 production guide | https://polaris.apache.org/releases/1.7.0/helm-chart/production/ | 2026-09-29 |
| S11 | PostgreSQL 18 resource configuration | https://www.postgresql.org/docs/18/runtime-config-resource.html | 2026-09-29 |
| S12 | PostgreSQL official image Dockerfile 18/alpine3.23 | https://raw.githubusercontent.com/docker-library/postgres/master/18/alpine3.23/Dockerfile | 2026-09-29 |
| S13 | SeaweedFS README | https://raw.githubusercontent.com/seaweedfs/seaweedfs/master/README.md | 2026-09-29 |
| S14 | SeaweedFS `weed/command/mini.go` | https://raw.githubusercontent.com/seaweedfs/seaweedfs/master/weed/command/mini.go | 2026-09-29 |
| S15 | SeaweedFS wiki, Quick Start with `weed mini` | https://raw.githubusercontent.com/wiki/seaweedfs/seaweedfs/Quick-Start-with-weed-mini.md | 2026-09-29 |
| S16 | Flink 2.1 configuration reference | https://nightlies.apache.org/flink/flink-docs-release-2.1/docs/deployment/config/ | 2026-09-29 |
| S17 | Flink 2.1 `JobManagerOptions.java` | https://raw.githubusercontent.com/apache/flink/release-2.1/flink-core/src/main/java/org/apache/flink/configuration/JobManagerOptions.java | 2026-09-29 |
| S18 | Flink 2.1 `TaskManagerOptions.java` | https://raw.githubusercontent.com/apache/flink/release-2.1/flink-core/src/main/java/org/apache/flink/configuration/TaskManagerOptions.java | 2026-09-29 |
| S19 | Spark 4.1.3 configuration reference | https://spark.apache.org/docs/4.1.3/configuration.html | 2026-09-29 |
| S20 | Dagster OSS deployment docs | https://docs.dagster.io/deployment/oss/deployment-options/deploying-dagster-as-a-service | 2026-09-29 |
| S21 | Apicurio Registry getting started | https://www.apicur.io/registry/getting-started/ | 2026-09-29 |
| S22 | Marquez README (Requirements) | https://raw.githubusercontent.com/MarquezProject/marquez/main/README.md | 2026-09-29 |
| S23 | Marquez quickstart docs | https://raw.githubusercontent.com/MarquezProject/marquez/main/docs/docs/quickstart/index.mdx | 2026-09-29 |
| S24 | Marquez Helm `values.yaml` | https://raw.githubusercontent.com/MarquezProject/marquez/main/chart/values.yaml | 2026-09-29 |
| S25 | Prometheus storage documentation | https://raw.githubusercontent.com/prometheus/prometheus/main/docs/storage.md | 2026-09-29 |
| S26 | Grafana installation requirements | https://grafana.com/docs/grafana/next/setup-grafana/installation.md | 2026-09-29 |
| S27 | Alertmanager docs | https://raw.githubusercontent.com/prometheus/alertmanager/main/docs/alertmanager.md | 2026-09-29 |
| S28 | Apache Kafka `bin/connect-distributed.sh` | https://raw.githubusercontent.com/apache/kafka/trunk/bin/connect-distributed.sh | 2026-09-29 |
| S29 | Debezium `docker-images` connect / connect-base Dockerfiles | https://raw.githubusercontent.com/debezium/docker-images/main/connect/3.6/Dockerfile | 2026-09-29 |
| S30 | Project completion bar, profiles | docs/completion-bar.md section 8 | 2026-09-29 |
