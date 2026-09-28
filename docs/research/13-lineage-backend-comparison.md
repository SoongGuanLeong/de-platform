# 13 - Lineage Backend Comparison

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Question answered:** which lineage backend should the platform run, if any?
**Decision context:** the emission contract is already fixed. The platform emits **OpenLineage** (LF AI & Data Foundation Graduate, Apache-2.0, latest `openlineage-integration-common` **1.53.0** uploaded 2026-09-01 [S1]). OpenLineage passed the longevity audit in `03-longevity-audit.md`. What is not decided is the backend that consumes the events, and whether running one is worth the RAM on this host.

**Scope:** Marquez (the OpenLineage reference implementation), DataHub, OpenMetadata, and running no backend at all. MinIO-class failures are not at issue here: all three projects are alive, non-archived and licensed Apache-2.0. The screening axis is therefore **operational footprint**, with licence/governance/longevity documented as a secondary filter and the portfolio/JD value documented as the third.

---

## 0. Method and the operational envelope

The envelope is from the project brief and the measured baseline in `03-longevity-audit.md` §2:

- 12 CPU, **~7-8 GB free RAM** (host measured 14 GB total, 7 GB free / 7 GB available on 2026-09-27), 231 GB disk.
- podman 6.1.x target (5.7.0 is installed and EOL; upgrade pending).
- Local-first. The platform already runs Kafka, Flink, ClickHouse, Polaris, PostgreSQL, Dagster, Prometheus/Grafana/Alertmanager, Apicurio and SeaweedFS on this host. **The lineage backend does not get the whole 7 GB; it gets the slack the rest of the stack leaves.**

Every footprint figure below is either (a) a documented requirement quoted from the project's own docs, or (b) derived from the project's own compose file, Dockerfile and published image sizes. **I did not run any of the three and did not measure RSS.** Estimates are labelled as estimates. No benchmark or memory number here is measured.

The house rubric (foundation preferred; company-backed with disclosed funding acceptable; observable activity as a hard floor) is applied, but it is not what decides this question. All three candidates pass it. Footprint decides it.

---

## 1. Verdict summary

| Option | Licence | Governance / backing | Activity (latest evidence) | Documented footprint | Verdict |
|---|---|---|---|---|---|
| **Marquez** | Apache-2.0 | LF AI & Data **Graduate** | last release 0.51.1 **27 Mar 2025**; last main-branch commit **12 Apr 2026** | API + Web + Postgres; OpenSearch optional. No documented RAM floor. **Est. ~1-1.5 GB** lean | **ADOPT (lean)** |
| **DataHub** | Apache-2.0 | company (Acryl/DataHub), $35M Series B | releases weekly; v1.6.0.3 **25 Sep 2026** | **7 services**; docs: "**2 CPUs, 8GB RAM, 2GB Swap area, and 13GB disk space**" | **REJECT - does not fit** |
| **OpenMetadata** | Apache-2.0 | company (Collate), $10M Series A | releases monthly; 2.0.2 **16 Sep 2026** | **5 services**; docs: server **4 vCPU / 16 GiB**, DB **4 vCPU / 16 GiB**, ES **2 vCPU / 8 GiB**, Airflow **4 vCPU / 16 GiB** | **REJECT - does not fit** |
| **No backend** | n/a | n/a | n/a | zero | **FALLBACK, not primary** |

---

## 2. The contract that makes the backend swappable

This is the load-bearing fact for the whole decision, and it was already recorded in `03-longevity-audit.md` §6 ("OpenLineage ... Emit the spec, not the backend"):

- OpenLineage is a **foundation standard**, not a vendor API. The same emitted event can be pointed at Marquez, DataHub, OpenMetadata or a file, because all three consume the spec (sections 3-5 below) and Marquez is the reference implementation of it.
- The transport is a config value: HTTP `POST` to a backend endpoint, or a Kafka topic. Nothing in the platform's Flink, Spark or Dagster code changes when the backend changes.
- Therefore the backend is a **presentation and storage choice, not an architectural one**. A weak or stalled backend costs a swap, not a rewrite. That asymmetry is what allows a light, slightly-stale backend to be the right call over a heavy, healthy one.

### 2.1 The emitter leg is not uniform

The backend is swappable, but the **emitters** the platform depends on are not equally first-party. This does not change the backend decision, but it changes where the lineage demo actually rests:

- **Spark and Flink:** first-party OpenLineage integrations, released with the core project (`openlineage-spark`, `openlineage-flink`, both 23 Jul 2026 [S3]). These are the load-bearing emitters.
- **Airflow:** the only orchestrator with a first-party OpenLineage provider, `apache-airflow-providers-openlineage` **2.20.1** (2026-08-23), maintained inside the `apache/airflow` monorepo [S36]. Airflow is not the platform's orchestrator, but it is the reference case for first-party orchestrator emission.
- **Dagster (the platform's orchestrator):** OpenLineage support is a **community package**, `dagster-openlineage` **0.2.1** (2026-05-22), hosted in `dagster-io/community-integrations` and marked "community-supported" by Dagster's own docs [S37; cross-reference `12-orchestrator-comparison.md`]. It emits asset-centric events with schema, column-lineage, data-quality-assertion and partition nominal-time facets.

**Consequence for this decision:** the "emission contract is fixed, backend is swappable" argument still holds, but the Dagster emitter leg rests on a v0.2.1 community package. If Dagster is adopted, name and watch that dependency; the fallback is to treat **Spark and Flink as the primary emitters** (both first-party) and Dagster lineage as secondary. The backend choice below is unaffected: Marquez, DataHub, OpenMetadata and no-backend all consume the same spec-conformant events regardless of which emitter produced them.

---

## 3. Marquez - the OpenLineage reference implementation

### 3.1 What it is, and how completely it consumes OpenLineage

Marquez is "an open source **metadata service** for the **collection**, **aggregation**, and **visualization** of a data ecosystem's metadata", "released and open sourced by WeWork" [S2, README]. It is the **reference implementation of OpenLineage** [S3, prior audit §3.10].

Consumption is native and complete, because Marquez is where the spec's semantics were first implemented:

- "Run-level metadata is tracked via HTTP API calls to `/lineage` using OpenLineage" [S4, quickstart `index.mdx`]. The canonical endpoint is `POST /api/v1/lineage`.
- The data model is the OpenLineage model: datasets, jobs, runs, run states, dataset versions and schema versions [S4].
- **Column-level lineage is supported**, backed by `ColumnLineageDao.java` and a dedicated web UI page [S5, CHANGELOG: "A new page for column lineage and an updated view for lineage"; "optimize column lineage query performance"].
- Deployment docs list exactly four components: "Marquez Web UI", "Marquez HTTP API" ("the core API used to collect metadata using OpenLineage"), "Database", and user-provided scheduler/workflow [S6, `deployment.mdx`]. This maps cleanly onto the platform: Dagster is the scheduler, Flink/Spark are the workflows, Iceberg datasets are the nodes.

**Completeness:** full. Marquez is the least likely of the three to silently drop an OpenLineage facet, because the facets are its native model rather than a mapping target.

### 3.2 Operational footprint (the decisive section)

Primary evidence:

- Compose stack [S7, `docker-compose.yml`, `docker-compose.web.yml`, `docker-compose.search.yml`]:
  - `api` - `marquezproject/marquez`
  - `db` - `postgres:14`
  - `web` - `marquezproject/marquez-web` (started by default; `--no-web` disables)
  - `opensearch` - `opensearchproject/opensearch:2.5.0` (started by default; `--no-search` disables), heap pinned `-Xms512m -Xmx512m`
- Published image sizes [S8, Docker Hub API]: `marquezproject/marquez:0.51.1` = **277.7 MB** (2025-03-27); `marquezproject/marquez-web:0.51.1` = **227.1 MB** (2025-03-27).
- Runtime: `FROM eclipse-temurin:17`; the entrypoint sets no `-Xmx`, so the JVM takes its default (a quarter of visible RAM) unless capped [S9, `Dockerfile` + `docker/entrypoint.sh`].

**Estimate (not measured):** API with `JAVA_OPTS=-Xmx512m` is roughly 0.7-1.0 GB RSS; web is a static React bundle behind a small server, roughly 50-100 MB; PostgreSQL roughly 200 MB or **zero extra** if the platform's existing PostgreSQL instance hosts a separate `marquez` database. That is a lean footprint of **~1-1.5 GB**. Adding OpenSearch for advanced search adds ~1 GB and is the one component worth dropping.

**Runnability on podman:** the compose files are ordinary Compose. `docker/up.sh` shells out to `docker compose`, so on this host run the compose files directly with `podman compose -f docker-compose.yml -f docker-compose.web.yml up` (or use the podman-docker shim). No Docker-specific feature is required. Marquez is the easiest of the three to stand up without Docker.

**Caveat on the database:** the compose pins `postgres:14` and the docs list PostgreSQL 14 as the tested version. The platform runs PostgreSQL 18. Reusing it is plausible (Marquez takes `POSTGRES_HOST`), but it is **untested by me**; the safe default is a dedicated `postgres:14` container, which is small. Verify 18 compatibility before reusing.

### 3.3 Licence, governance, longevity

- **Licence:** Apache-2.0 [S10, repo `LICENSE`; S11, GitHub API `license.spdx_id = apache-2.0`].
- **Governance:** "Marquez is an [LF AI & Data Foundation] **Graduated** project under active development" [S2, README status line]. The README carries the LF AI & Data graduate badge. This is the **preferred** leg of the rubric: foundation governance.
- **Activity - the honest caveat:**
  - Last GitHub *release*: **0.50.0, published 2024-10-24** [S12, GitHub Releases API; CHANGELOG dates it 2024-10-23].
  - Tags `0.51.0` (2025-03-25) and `0.51.1` (2025-03-27) exist but were **not published as GitHub releases**; the current `docker/up.sh` pins `VERSION=0.51.1` and Docker Hub carries a 0.51.1 image dated 2025-03-27 [S13, tags API; S8; S9].
  - The CHANGELOG's newest section is still `[Unreleased] compare 0.50.0...HEAD`; there is no 0.51.x section [S5].
  - Last commit on the default branch: **2026-04-12** [S14, commits API], roughly five months before this report.
  - Stars: **2,283** [S11].
- **Read:** Marquez is **not archived and not maintenance-only** (there were substantive commits in 2026, including a React 19 upgrade and a query-performance fix), but it has **shipped no release in about 18 months** and its release process has visibly drifted. Under the rubric's "releases/commits in the last ~12 months" floor this is a **caution, not a fail**: commits are inside 12 months, releases are not. It is the weakest release cadence of the three.

### 3.4 Portfolio value and JD mapping

- The target JD's nice-to-have names lineage tooling as "**OpenLineage/Marquez**, Great Expectations, dbt tests, catalog-based access control" [S15, JD cache 031.md]. **Marquez is named in the posting.**
- The JD responsibility "establish and enforce data governance: catalog organization, access control, **data lineage**, retention/compliance" [S15] is directly served by a working Marquez graph over the platform's Iceberg tables.
- It demonstrates: OpenLineage emission from Spark and Flink (both first-party) plus Dagster (community package, see section 2.1), a real lineage graph, dataset/run history, and column-level lineage across bronze -> silver -> gold. That is a concrete, screenshot-able artifact tied to the named requirement, at the lowest RAM cost of any option.

---

## 4. DataHub - rejected on footprint

### 4.1 Licence, governance, activity

- **Licence:** Apache-2.0 [S16, `LICENSE`; S17, GitHub API `spdx_id = apache-2.0`]. NOTICE records "(c) 2015 LinkedIn Corp" [S18].
- **Governance/backing:** company-backed by Acryl Data / DataHub (datahub.com). Disclosed funding: **$21M Series A (Jun 2023)** and **$35M Series B announced 21 May 2025** [S19, datahub.com news]. Commercial incentive: DataHub Cloud [S16]. This is the rubric's acceptable "company-backed with disclosed funding and a commercial reason for the OSS core to stay healthy" leg.
- **Activity:** the healthiest of the three. Releases `v1.6.0.3` (2026-09-25) and `v1.8.0rc3` (2026-09-07); commits to `master` on 2026-09-26; **12,769** stars [S20, releases API; S21, commits API; S17].
- **Longevity verdict: PASS.** Nothing here disqualifies DataHub.

### 4.2 How it consumes OpenLineage

DataHub supports OpenLineage, but as an integration rather than its native model:

- A REST endpoint: "`POST GMS_SERVER_HOST:GMS_PORT/openapi/openlineage/api/v1/lineage`", with a Spark Event Listener plugin for tighter Spark/Airflow integration [S22, docs.datahub.com/docs/lineage/openlineage].
- It maps to DataFlow/DataJob/Dataset entities, with column-level lineage and a rich set of `datahub.openlineage.*` config options [S22].
- The docs explicitly steer Spark and Airflow users to DataHub's own Spark Lineage / Airflow plugin instead of the generic OpenLineage path [S22]. So OpenLineage is supported but is the **second-class** ingestion route for the two engines the platform actually uses (Flink has no DataHub-native plugin at all).

### 4.3 Operational footprint - the disqualifier

- The quickstart is **7 services**: `datahub-actions-quickstart`, `datahub-gms-quickstart`, `frontend-quickstart`, `kafka-broker`, `mysql`, `opensearch`, `system-update-quickstart` [S23, `docker/quickstart/docker-compose.quickstart-profile.yml`].
- Heap settings in that file: GMS `-Xms1g -Xmx1g`, frontend `-Xms512m -Xmx512m`, Kafka `-Xms512m -Xmx512m`, OpenSearch `-Xms768m -Xmx1024m` [S23]. Heaps alone total ~2.8-3 GB; JVM overhead, MySQL, Kafka page cache and OpenSearch bring the real working set well above that.
- The project's own documented, tested allocation [S24, docs.datahub.com/docs/quickstart]:

  > "Make sure to allocate enough hardware resources for Docker engine. Tested & confirmed config: **2 CPUs, 8GB RAM, 2GB Swap area, and 13GB disk space**."

**This is the whole host's free RAM, for DataHub alone.** The platform's Kafka, Flink, ClickHouse, Polaris, Dagster and the rest are not accounted for. On a 7-8 GB-free host there is no configuration of DataHub quickstart that coexists with the platform. DataHub is rejected on operational envelope, not on merit.

**Runnability:** `datahub docker quickstart` requires Docker + Compose v2 and a Python 3.10+ CLI [S24]; on podman you would download the compose file and run it with `podman compose`, which is possible but is the highest-friction of the three and is moot given the RAM verdict.

---

## 5. OpenMetadata - rejected on footprint

### 5.1 Licence, governance, activity

- **Licence:** Apache-2.0 [S25, `LICENSE`; S26, GitHub API `spdx_id = apache-2.0`].
- **Governance/backing:** company-backed by Collate. Disclosed funding: **$10M Series A, 15 July 2025** [S27, getcollate.io press release / PRNewswire]. Commercial incentive: Collate Cloud. Acceptable under the rubric.
- **Activity:** very active. Releases `2.0.2-release` (2026-09-16), `1.13.6-release` (2026-09-11), `2.0.0-release` (2026-08-24); commits on 2026-09-27; **15,344** stars [S28, releases API; S29, commits API; S26].
- **Longevity verdict: PASS.** Nothing here disqualifies OpenMetadata.

### 5.2 How it consumes OpenLineage

OpenMetadata's OpenLineage support is first-class and broader than DataHub's on the ingestion side:

- A **server-side REST resource** (`OpenLineageResource.java`) plus OpenLineage spec schemas in `openmetadata-spec` (`openLineageRunEvent.json`, `openLineageBatchRequest.json`, `openLineageFacets.json`) [S30, repo tree].
- An **OpenLineage pipeline connector** (`ingestion/src/metadata/ingestion/source/pipeline/openlineage/`) that consumes from **Kafka or Kinesis** brokers, with entity resolvers, a dataset-name normaliser and an ownership resolver [S30, repo tree].
- The docs expose it as a connector with a YAML configuration path [S31, docs.open-metadata.org connectors/pipeline/openlineage].
- It also advertises column-level lineage and 130+ connectors [S25, README].

So OpenMetadata consumes OpenLineage at least as completely as DataHub, including the Kafka transport the platform's Flink/Spark emitters would naturally use.

### 5.3 Operational footprint - the disqualifier

- The quickstart compose has **5 services**: `postgresql`, `elasticsearch`, `execute-migrate-all`, `openmetadata-server`, `ingestion` (Airflow) [S32, `docker/docker-compose-quickstart/docker-compose-postgres.yml`].
- Even the trimmed quickstart heaps are heavy: Elasticsearch `-Xms1024m -Xmx1024m`, OpenMetadata server `OPENMETADATA_HEAP_OPTS=-Xmx1G -Xms1G`, plus the Airflow ingestion container [S32].
- The project's own **minimum** and **production-ready** requirement pages are unambiguous [S33, docs.open-metadata.org minimum-requirements; S34, production-ready-requirements]:
  - OpenMetadata Server: **4 vCPUs, 16 GiB RAM**, 100 GiB storage.
  - Database (MySQL/PostgreSQL): **4 vCPUs, 16 GiB RAM**, 100 GiB.
  - Elasticsearch/OpenSearch: **2 vCPUs, 8 GiB RAM**, 100 GiB.
  - Apache Airflow (ingestion): **4 vCPU, 16 GiB RAM**, 100 GiB.

**The documented server requirement alone (16 GiB) is more than this host's total RAM (14 GiB).** OpenMetadata is rejected on operational envelope, decisively and without ambiguity.

**Runnability:** Docker 20.10+ and Compose v2.2.3+ [S35, docs deployment/docker]. Podman-compatible in principle; moot given the RAM verdict.

---

## 6. Running no backend - the fallback, not the answer

**What it is:** emit OpenLineage to a file or a Kafka topic and stop. Parse it ad hoc or render it in a notebook when needed.

**What it keeps:** the portable asset (the spec-conformant events), zero RAM, zero operational surface, zero upgrade cadence. This is exactly the hedge `03-longevity-audit.md` already recommended.

**What it loses:**
- The lineage **UI**: no graph, no run history, no column-level lineage view. The demo becomes a JSON file or a bespoke notebook.
- The direct JD hit: the posting names "OpenLineage/**Marquez**" [S15]. Running no backend still satisfies "OpenLineage" but demonstrates nothing visual.
- The "lineage" half of the JD's governance responsibility is asserted rather than shown.

**Verdict:** correct as a **fallback** if RAM must go elsewhere, but it leaves the cheapest, most directly-named portfolio win on the table. It is not the primary recommendation while Marquez fits.

---

## 7. Decision matrix

| Dimension | Marquez | DataHub | OpenMetadata | No backend |
|---|---|---|---|---|
| Licence | Apache-2.0 | Apache-2.0 | Apache-2.0 | n/a |
| Governance | **LF AI & Data Graduate** (foundation) | company (Acryl/DataHub) | company (Collate) | n/a |
| Disclosed funding | n/a (foundation) | $21M A + **$35M B** | **$10M A** | n/a |
| Last release | 0.51.1 **27 Mar 2025** | v1.6.0.3 **25 Sep 2026** | 2.0.2 **16 Sep 2026** | n/a |
| Activity floor | caution (no release 18 mo; commits Apr 2026) | pass | pass | n/a |
| Services | 2 core (+1 web, +1 optional search) | **7** | **5** | 0 |
| Documented RAM | none (est. ~1-1.5 GB lean) | **8 GB** tested config | **16 GiB server** minimum | 0 |
| OpenLineage fidelity | reference implementation | REST + Spark plugin (2nd-class vs native) | REST resource + Kafka/Kinesis connector | spec only |
| Column-level lineage | yes | yes | yes | n/a |
| podman friction | lowest | highest (CLI assumes Docker) | medium | none |
| JD hit | **named ("OpenLineage/Marquez")** | governance/catalog | governance/catalog | partial |
| Fit on this host | **yes** | **no** | **no** | yes |

---

## 8. Recommendation

**Run Marquez, deployed lean.**

Concretely:

1. Bring up **`marquezproject/marquez:0.51.1`** (API) and **`marquezproject/marquez-web:0.51.1`** (UI) via the repo's compose files with `podman compose`. Skip the OpenSearch service (`--no-search`): it only powers advanced search, and dropping it saves ~1 GB.
2. Cap the JVM explicitly, for example `JAVA_OPTS=-Xmx512m`. The entrypoint sets no `-Xmx`, so without this the JVM will size its heap to the host and quietly eat the platform's RAM.
3. Database: default to a dedicated `postgres:14` container (small, matches the pinned/tested version). Reusing the platform's PostgreSQL 18 instance with a separate database is a later optimisation, to be done only after verifying compatibility. **Untested by me.**
4. Point the existing OpenLineage HTTP transport at `http://marquez:5000/api/v1/lineage`. The Flink, Spark and Dagster emitters do not change; only the endpoint does. Note that the Dagster leg is a community package (see section 2.1): prefer Spark and Flink as the primary emitters, and treat Dagster lineage as secondary.

**Why Marquez and not the others:**

- **It is the only option that fits.** Marquez lean is an estimated ~1-1.5 GB. DataHub's own tested configuration is 8 GB and OpenMetadata's documented server minimum is 16 GiB; either consumes the entire host with nothing left for Kafka, Flink, ClickHouse or Polaris. This is a hard envelope decision, not a preference.
- **It is the OpenLineage reference implementation.** The platform emits OpenLineage; the backend that owns that spec's semantics is the lowest-risk consumer of every facet, including column-level lineage.
- **It is named in the target JD.** "OpenLineage/Marquez" is the posting's own phrase, and the JD's governance responsibility explicitly includes "data lineage". This is the highest JD-hit-per-megabyte of any option.
- **It is foundation-governed and Apache-2.0.** LF AI & Data Graduate is the rubric's preferred leg.

**The honest caveats, stated plainly:**

- **Marquez's release cadence has stalled.** Last published release 0.51.1 on 27 Mar 2025; last main-branch commit 12 Apr 2026. It is not archived and not maintenance-only, but it is the weakest cadence of the three. Treat Marquez as a **swappable backend behind the OpenLineage transport**, not as an architectural commitment. If it stops entirely, the same events go to DataHub, OpenMetadata, or a file.
- **My footprint figures for Marquez are estimates**, derived from image sizes, heap defaults and component counts. I did not measure RSS. Before committing, measure the lean stack's actual resident memory on this host with the platform already running.
- **If the measured footprint does not fit**, drop the web UI first (keep the API, query it directly), and if even that is too much, fall back to **no backend** and keep emitting OpenLineage to a file or topic. The emission contract is the asset; the backend is replaceable by design.

**Rejected:**

- **DataHub - rejected on operational envelope.** Excellent project, healthiest cadence, acceptable governance. Its documented quickstart allocation (2 CPU, 8 GB RAM, 2 GB swap) and 7-service stack cannot coexist with the platform on a 7-8 GB-free host.
- **OpenMetadata - rejected on operational envelope.** Also a healthy, well-governed project with first-class OpenLineage support. Its documented minimum server requirement (4 vCPU, 16 GiB) exceeds this host's total RAM. It cannot run here.
- **No backend - not primary.** Kept as the explicit fallback. It preserves the portable spec asset but forgoes the visual lineage demo and the JD's named "Marquez" hit.

---

## 9. What I could not verify

- **No measured memory.** I did not deploy any of the three, on podman or otherwise. All footprint figures are documented requirements or estimates from primary artefacts (compose heaps, image sizes, component counts). The Marquez lean estimate (~1-1.5 GB) is mine, not the project's.
- **Marquez on PostgreSQL 18.** The project pins and tests PostgreSQL 14. Whether 0.51.1 runs correctly against the platform's PostgreSQL 18 is untested.
- **Marquez 0.51.x release status.** Tags 0.51.0 and 0.51.1 exist with Docker images, but they were never published as GitHub releases and never added to the CHANGELOG. I could not find a primary statement explaining why; I have reported the observable facts rather than infer a cause.
- **OpenMetadata's docs source repository** for the user-facing site was not located under the `open-metadata` org (the doc content is served from a Mintlify site and the repo was not found by name). I read the requirements and connector pages from the live documentation, which is first-party.
- **OpenLineage spec facet file.** A direct grep of `spec/OpenLineage.json` for `ColumnLineageDatasetFacet` returned nothing (the facet may live in a separate file or a differently-pathed schema). Marquez's own column-level lineage is independently confirmed by its CHANGELOG and `ColumnLineageDao.java`.

---

## 10. Source log

All URLs accessed **2026-09-28** unless the item carries its own date.

| ID | Source | Date on source |
|---|---|---|
| S1 | pypi.org/pypi/openlineage-integration-common/json - latest 1.53.0 | uploaded 2026-09-01 |
| S2 | github.com/MarquezProject/marquez - README (LF AI & Data Graduate badge + status line) | accessed 2026-09-28 |
| S3 | docs/research/03-longevity-audit.md §3.10 - OpenLineage PASS, "reference implementation is Marquez" | 2026-09-27 |
| S4 | github.com/MarquezProject/marquez - docs/docs/quickstart/index.mdx (data model, /lineage via OpenLineage) | accessed 2026-09-28 |
| S5 | github.com/MarquezProject/marquez - CHANGELOG.md (column lineage UI, ColumnLineageDao; top section [Unreleased] vs 0.50.0) | 0.50.0 dated 2024-10-23 |
| S6 | github.com/MarquezProject/marquez - docs/docs/deployment/deployment.mdx (components table, Postgres-only) | accessed 2026-09-28 |
| S7 | github.com/MarquezProject/marquez - docker-compose.yml, docker-compose.web.yml, docker-compose.search.yml | accessed 2026-09-28 |
| S8 | hub.docker.com/v2/repositories/marquezproject/marquez and /marquez-web tags API | images 0.51.1 = 2025-03-27 |
| S9 | github.com/MarquezProject/marquez - Dockerfile (eclipse-temurin:17), docker/entrypoint.sh (no -Xmx), docker/up.sh (VERSION=0.51.1) | accessed 2026-09-28 |
| S10 | github.com/MarquezProject/marquez - LICENSE | accessed 2026-09-28 |
| S11 | api.github.com/repos/MarquezProject/marquez - license.spdx_id apache-2.0, stars 2283 | accessed 2026-09-28 |
| S12 | api.github.com/repos/MarquezProject/marquez/releases - latest 0.50.0 | published 2024-10-24 |
| S13 | api.github.com/repos/MarquezProject/marquez/tags + commits?sha=0.51.1 / 0.51.0 | 0.51.1 = 2025-03-27; 0.51.0 = 2025-03-25 |
| S14 | api.github.com/repos/MarquezProject/marquez/commits (default branch) - last commit | 2026-04-12 |
| S15 | ~/projects/career-ops/data/jd-cache/031.md - "OpenLineage/Marquez"; governance responsibility | fetched 2026-09-27 |
| S16 | github.com/datahub-project/datahub - README + LICENSE (Apache-2.0) | accessed 2026-09-28 |
| S17 | api.github.com/repos/datahub-project/datahub - license.spdx_id apache-2.0, stars 12769, pushed 2026-09-27 | accessed 2026-09-28 |
| S18 | github.com/datahub-project/datahub - NOTICE ("(c) 2015 LinkedIn Corp") | accessed 2026-09-28 |
| S19 | datahub.com/news/series-b-announcement/ - $35M Series B; prior $21M Series A (Jun 2023) | Series B 2025-05-21 |
| S20 | api.github.com/repos/datahub-project/datahub/releases - v1.6.0.3, v1.8.0rc3 | 2026-09-25; 2026-09-07 |
| S21 | api.github.com/repos/datahub-project/datahub/commits - last commits to master | 2026-09-26 |
| S22 | docs.datahub.com/docs/lineage/openlineage - REST endpoint, Spark plugin, config | accessed 2026-09-28 |
| S23 | github.com/datahub-project/datahub - docker/quickstart/docker-compose.quickstart-profile.yml (7 services + heaps) | accessed 2026-09-28 |
| S24 | docs.datahub.com/docs/quickstart - "2 CPUs, 8GB RAM, 2GB Swap area, and 13GB disk space"; CLI prereqs | accessed 2026-09-28 |
| S25 | github.com/open-metadata/OpenMetadata - README + LICENSE (Apache-2.0) | accessed 2026-09-28 |
| S26 | api.github.com/repos/open-metadata/OpenMetadata - license.spdx_id apache-2.0, stars 15344, pushed 2026-09-28 | accessed 2026-09-28 |
| S27 | getcollate.io/blog/pr-collate-raises-10m-series-a... (+ PRNewswire mirror) - $10M Series A | 2025-07-15 |
| S28 | api.github.com/repos/open-metadata/OpenMetadata/releases - 2.0.2-release, 1.13.6-release | 2026-09-16; 2026-09-11 |
| S29 | api.github.com/repos/open-metadata/OpenMetadata/commits - last commits | 2026-09-27 |
| S30 | github.com/open-metadata/OpenMetadata - git tree: OpenLineageResource.java, openlineage ingestion source (Kafka/Kinesis), openmetadata-spec OL schemas | accessed 2026-09-28 |
| S31 | docs.open-metadata.org/v2.0.x/connectors/pipeline/openlineage - connector + YAML config | accessed 2026-09-28 |
| S32 | github.com/open-metadata/OpenMetadata - docker/docker-compose-quickstart/docker-compose-postgres.yml (5 services + heaps) | accessed 2026-09-28 |
| S33 | docs.open-metadata.org/v2.0.x/deployment/minimum-requirements - server/DB/ES/Airflow minimums | accessed 2026-09-28 |
| S34 | docs.open-metadata.org/v2.0.x/deployment/production-ready-requirements - server 4 vCPU/16 GiB etc. | accessed 2026-09-28 |
| S35 | docs.open-metadata.org/v2.0.x/deployment/docker - Docker 20.10+, Compose v2.2.3+ | accessed 2026-09-28 |
| S36 | pypi.org/pypi/apache-airflow-providers-openlineage/json - 2.20.1, source github.com/apache/airflow | uploaded 2026-08-23 |
| S37 | pypi.org/pypi/dagster-openlineage/json - 0.2.1; dagster-io/community-integrations; cross-ref docs/research/12-orchestrator-comparison.md | uploaded 2026-05-22 |
