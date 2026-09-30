# 03 - Longevity and governance audit

**Date of research:** 2026-09-27. All evidence accessed 2026-09-27 unless stated.
**Scope:** every component named in the job posting (ONL Biz Solutions, Senior Data Engineer — Data Lakehouse, cached at `career-ops/data/jd-cache/031.md`) plus the object-storage candidates being screened in place of MinIO.
**Question answered:** which dependencies survive a 5-year portfolio horizon under a hard admission test, and what must the container images pin.

---

## 0. The rubric, and how it was applied

> **foundation governance preferred; company-backed with funding and incentive acceptable; observable activity as a hard floor.** A component failing any leg is out.

Read as three independent legs, all of which must hold:

| Leg | Test | How it was judged |
|---|---|---|
| **L1 — governance** | Foundation, company, or individual steward; named | Project's own governance page, foundation project listing, or vendor's legal entity |
| **L2 — backing & incentive** | Foundation *or* company with disclosed funding *and* a commercial reason for the OSS core to stay healthy | Funding rounds, foundation membership, vendor revenue model |
| **L3 — observable activity (hard floor)** | Not archived, not maintenance-only; releases + commits in the last ~12 months | Release catalogs, GitHub releases, ASF release catalog |

**L3 is the leg MinIO failed.** MinIO Inc. had funding and incentive. `github.com/minio/minio` was archived by the owner on **25 April 2026** [github.com/minio/minio — archived banner, accessed 2026-09-27]. Its README now reads "**THIS REPOSITORY IS NO LONGER MAINTAINED.**" and the `mc`, `kes`, `operator` repos are archived too [github.com/minio org, accessed 2026-09-27]. The timeline: May 2025 key-management features moved to the commercial AIStor product; Oct 2025 community binaries and Docker images stopped; Dec 2025 explicit maintenance-mode messaging; **25 Apr 2026 archive**. Two security advisories were published on 14 and 25 April 2026 with no upstream fix path [github.com/minio/minio/security/advisories, accessed 2026-09-27: GHSA-hv4r-mvr4-25vw "High", GHSA-xh8f-g2qw-gcm7 "Moderate"]. Community edition is AGPLv3 source-only; the *licence* never changed, the *maintenance* did. That is the exact distinction this audit screens on.

**A note on the sceptics.** A widely-circulated claim is that MinIO was archived "in Feb 2026" and then again "in Apr 2026" [dev.to/arash_ezazy, 2025-12-26]. The authoritative record is the GitHub archive banner and the repo README: **25 April 2026**. Use that date.

---

## 1. Verdict summary

### FAIL — removed from consideration

| Component | Leg failed | Evidence |
|---|---|---|
| **MinIO Community Edition** | **L3** | Archived 25 Apr 2026, read-only, unpatched advisories. [S0] |
| **Terraform (upstream HashiCorp)** | **L1/L2** | Relicensed MPL-2.0 → BUSL 1.1 in Aug 2023; no foundation, and the licence is source-available, not open source. This is the JD's "Terraform" and it must be replaced by OpenTofu. [S24] |
| **Grafana OnCall OSS** | **L3** | Grafana Labs' own OSS page: "Grafana OnCall OSS is now in maintenance mode and will be archived on **2026-03-24**." [S9] Not in our target stack, but load-bearing evidence for the Grafana verdict. |
| **Podman 5.7 (the version installed on this host)** | **L3** | EOL **12 Feb 2026**, security support ended. [S25] The *component* passes; the *installed version* must be upgraded to 6.1.1. |

### PASS-WITH-CAUTION

| Component | One-line reason |
|---|---|
| **Apache Polaris** | Graduated to TLP 18 Feb 2026, but 7 minor versions in 13 months — a 6-week minor cadence will cost us upgrade cycles. |
| **Apache Spark** | Java 25 support exists **only in 4.2.0**, and 25.0.3 is deprecated; Java 26 is unsupported everywhere. |
| **ClickHouse** | Apache-2.0 intact and $1.05B funded, but the company is pivoting hard to LLM observability and ships backward-incompatible changes in **monthly** releases. |
| **Dagster** | Apache-2.0, but **Prefect acquired Dagster Labs on 13 Jul 2026** — the classic MinIO shape, just beginning. |
| **Debezium** | Now at Commonhaus, but the steering committee is still 4-of-5 Red Hat/IBM and the Red Hat *build* lags community by two minors. |
| **Apicurio Registry** | CNCF Sandbox, but 924 stars and the Red Hat build is OpenShift-only and one minor behind. |
| **Grafana** | OSS is alive and free, but Grafana Labs has just retired one OSS edition (OnCall) and is plugin-ifying core datasources. |
| **Helm** | v3 security fixes end **11 Nov 2026**; v3→v4 chart-format migration is the cost. |
| **SeaweedFS** | Very active, but bus factor 1 (Chris Lu) and ~60% S3 API coverage. |
| **RustFS** | 31.8k stars, still at **1.0.0-beta.10**; commercial steward selling "the MinIO replacement". |
| **Garage** | Real cadence (v2.3.0, 16 Apr 2026) but AGPLv3 and a 170-star association steward. |
| **Apache Ozone** | Passes the rubric cleanly; excluded on **environment fit**, not longevity — see §5.3. |
| **Docker Engine** | Company-backed and funded, but no foundation and a churny stewardship history. |

### PASS

Apache Iceberg · Apache Kafka · Apache Flink · Prometheus · Alertmanager · OpenLineage · OpenTofu · PostgreSQL · Podman (at 6.1.x) · Apache Polaris *(on L1/L2; caution on cadence)*

---

## 2. Environment baseline (measured, not assumed)

```
$ java -version
openjdk version "26.0.2" 2026-07-21
OpenJDK Runtime Environment Temurin-26.0.2+10

$ python3 --version
Python 3.14.4

$ podman --version
podman version 5.7.0

$ free -g  → Mem: 14 total, 7 free, 7 available
$ nproc   → 12
$ df -h / → 231G available on /dev/nvme1n1p3
```

**Correction to the assignment's premise (host JDK):** the host JDK is **26**, not 25. This makes the situation slightly worse than assumed — 26 is further from anything the JVM data stack supports. See §6.

---

## 3. Per-component audit

### 3.1 Apache Iceberg — **PASS**

- **Governance:** Apache Software Foundation Top-Level Project. Donated Nov 2018, **graduated May 2020** [Wikipedia, 2026-08-20 snapshot; iceberg.apache.org]. Steward: the ASF, via the Iceberg PMC.
- **Licence:** Apache-2.0. No relicensing history, no threat of one.
- **Last release:** **1.11.0, 15 May 2026** [ASF release catalog, last updated 26 Sep 2026]. Sub-libraries: PyIceberg latest 2026-09-01, iceberg-rust latest 2026-08-01, iceberg-cpp latest 2026-09-26.
- **Cadence (18 months):** 1.8.0 Feb 2025 → 1.8.1 Feb 2025 → 1.9.0 Apr 2025 → 1.9.1 May 2025 → 1.9.2 Jul 2025 → 1.10.0 **5 Sep 2025** → 1.10.1 16 Dec 2025 → 1.10.2 13 May 2026 → **1.11.0 15 May 2026**. Roughly two minors a year with frequent point releases. Mature and unhurried — the opposite of Polaris.
- **Activity / contributors:** Adopted by Snowflake, AWS, Google, Microsoft, Databricks, Netflix, Apple, LinkedIn, Airbnb, Expedia, Adobe, Lyft. The REST catalog spec is the industry's answer to catalog lock-in, which concentrates incentive on keeping it vendor-neutral.
- **Funding/incentive:** the ASF plus the widest commercial sponsor set in data. Strongly aligned.
- **Issues/PRs:** 3352 repos referencing the artefact on Maven Central.
- **Status:** **stable.** TLP since 2020.
- **Breaking changes:** the table-format spec is versioned separately from the library; 1.x has held API compatibility. Upgrades are additive.
- **Incentive toward our use case:** maximal. It *is* the vendor-neutral lakehouse.
- **Last two years:** no governance fight, no licence dispute.
- **Verdict: PASS.** All three legs hold, and the "preferred" leg (foundation) is met with the strongest possible incentive alignment.

---

### 3.2 Apache Polaris — **PASS-WITH-CAUTION** (deep dive, §5.1)

- **Governance:** ASF. **Graduated to Top-Level Project 15 Feb 2026**; announced 18–19 Feb 2026 [incubator.apache.org/projects/polaris.html: "2024-08-09 Project enters incubation. 2026-02-15 Graduation as TLP"; polaris.apache.org/blog/2026/02/19]. Site has moved to `polaris.apache.org`.
- **Licence:** Apache-2.0.
- **Last release:** **1.7.0, 2 Aug 2026** [polaris.apache.org/downloads].
- **Cadence — the caution:** 0.9.0 Mar 2025 → 1.0.0 9 Jul 2025 → 1.0.1 16 Aug 2025 → 1.1.0 19 Sep 2025 → 1.2.0 23 Oct 2025 → 1.3.0 16 Jan 2026 → 1.4.0 21 Apr 2026 → 1.4.1 1 May 2026 → 1.5.0 18 May 2026 → 1.6.0 8 Jul 2026 → **1.7.0 2 Aug 2026**. **Seven minor versions in 13 months.** 1.4 was the first post-graduation drop and was pure production hardening: storage-scoped AWS credentials, STS session tags, S3 KMS, CockroachDB as a persistence backend, Iceberg metrics [dev.to/alexmercedcoder, 8 Jun 2026].
- **Concentration:** co-created by **Dremio and Snowflake**; Dremio CTO Rahim Bhojani and Dremio's Jean-Baptiste Onofré are prominent ASF members [GlobeNewswire, 19 Feb 2026]. Snowflake's Horizon Catalog now runs its interoperability on Polaris. Incubation drew contributions from Google, Microsoft, Confluent and dozens of others [dev.to, 8 Jun 2026]. Two founders, many contributors — acceptable for a TLP but worth watching.
- **Breaking changes:** SemVer since 1.0, but see cadence.
- **Incentive:** both co-creators are *selling* Polaris, so it stays aligned. 1.11 added REST scan planning, letting the catalog do server-side scan planning [dev.to, 8 Jun 2026].
- **Verdict: PASS-WITH-CAUTION.** L1 and L2 are now satisfied and no longer debatable. L3 is satisfied with room to spare. The caution is *velocity*, not durability.

---

### 3.3 Apache Kafka — **PASS**

- **Governance:** ASF TLP. Apache-2.0.
- **Last release:** **4.3.1, 23 Jun 2026**; 4.4.0-rc0 cut 21 Aug 2026 [releasealert.dev/github/apache/kafka; kafka.apache.org/blog/releases]. Prior: 4.2.1 28 May 2026, 4.3.0 20 May 2026, 4.2.0 16 Feb 2026, 4.1.2 16 Mar 2026.
- **Cadence:** ~315 releases, roughly one every two weeks, plus parallel maintenance of 3.9.x/4.0.x/4.1.x/4.2.x/4.3.x. Extremely healthy.
- **Breaking-change history (this is the real cost):**
  - Kafka 4.0: **ZooKeeper removed**, KRaft only. Brokers must be ≥3.3.x and ZooKeeper-mode clusters must be migrated first [kafka.apache.org/43/getting-started/upgrade].
  - Kafka 4.0: **pre-2.1 client protocol API versions removed** (KIP-896). All clients, including Connect and Streams, must be ≥2.1 [kafka.apache.org/40/getting-started].
  - Kafka 4.0: new group-coordinator implementation; KIP-848 consumer rebalance GA. Once KIP-848 is used, **downgrade below 3.4.1 is impossible**.
  - Kafka 4.3: **`kafka-streams-scala` deprecated, removal in 5.0**.
  - Context: KIP-1100 (early access for old-protocol removal) was paused in Sept 2024 after community pushback and then shipped for real in 4.0. That is a governance process that worked, and it is worth knowing it exists.
- **Funding/incentive:** ASF, plus Confluent, AWS, Google, Microsoft, Redpanda and IBM all commercially dependent.
- **Status:** stable, LTP.
- **Verdict: PASS.** All three legs. Budget for a real migration at 4.x (ZooKeeper is already gone) and pin the client version.

---

### 3.4 Apache Flink — **PASS**

- **Governance:** ASF TLP. Apache-2.0.
- **Last release:** **2.3.0, 25 Jun 2026**; 2.3.0 on PyPI as `apache-flink` [pypi.org/project/apache-flink]. Prior: 2.2.1 11 May 2026, 2.1.3 11 Jun 2026, 2.0.2 9 May 2026.
- **Cadence:** 2.0 19 Mar 2025 → 2.1 29 Jul 2025 → 2.2 4 Dec 2025 → 2.3 25 Jun 2026. Two minors a year. Documented support policy: current and previous minor get bugfixes; the outgoing minor gets **one final bugfix release** for critical/blocker issues [flink.apache.org/downloads].
- **Breaking changes:** Flink 2.0 was a large break (removed the deprecated DataSet API, changed state internals). Since 2.0, per-minor. 2.2 and 2.3 release notes are both readable and specific [flink-2.2.md, flink-2.3.md].
- **Funding/incentive:** ASF, with Alibaba, Ververica and a broad user base. Flink's user mailing list is "consistently ranked as one of the most active of any Apache project."
- **Status:** stable, actively developed.
- **Verdict: PASS.** Note the support policy is tight — one final bugfix for the version you leave behind. Do not lag more than one minor.

---

### 3.5 Apache Spark — **PASS-WITH-CAUTION** (Java 25 only)

- **Governance:** ASF TLP. Apache-2.0.
- **Last release:** **4.2.0, 14 Jul 2026**; 4.1.3 15 Jul 2026; 4.0.4 15 Jul 2026; 3.5.9 16 Jul 2026 [spark.apache.org/news]. Four supported lines in one week — the 4.x train is moving fast.
- **Cadence:** 3.5.x (May 2023) → 4.0 → 4.1 (1 Jun 2026) → 4.2 (14 Jul 2026). Roughly 2–3 minors/year with a 5.x implied.
- **Breaking changes:** 4.0 removed Scala 2.12 (2.13 only since 4.0.0) and the R API is deprecated. Python moved to Spark Connect as the default client path in 4.x.
- **Java support — the caution:** Spark **4.2.0** docs state "Spark runs on **Java 17/21/25**, Scala 2.13, Python 3.10+, and R 4.0+ (Deprecated). **Java 25 prior to version 25.0.3 support is deprecated as of Spark 4.2.0.**" [spark.apache.org/docs/latest]. Spark **4.1.x** docs say only "Java 17/21". So Java 25 arrived *with* 4.2.0 and even then 25.0.3 is the floor. **Java 26 is not supported at all.**
- **Incentive:** maximal — Databricks, AWS, Google, Microsoft, NVIDIA, Databricks all upstream.
- **Verdict: PASS-WITH-CAUTION.** The caution is entirely the Java 25 story. Pin **17** and the caution evaporates.

---

### 3.6 ClickHouse — **PASS-WITH-CAUTION** (deep dive, §5.3)

- **Governance:** company. ClickHouse, Inc. (San Francisco, incorporated Sept 2021) and ClickHouse B.V. (Amsterdam). Steward: Alexey Milovidov (CTO) and Aaron Katz (CEO).
- **Licence:** **Apache-2.0, unchanged.** `LICENSE` reads "Copyright 2016-2026 ClickHouse, Inc. … Apache License Version 2.0" [github.com/ClickHouse/ClickHouse/blob/master/LICENSE, accessed 2026-09-27]. The project published a tenth-anniversary post on 16 Jun 2026 explicitly marking ten years of Apache 2.0.
- **Last release:** **26.8 LTS, 27 Aug 2026** [clickhouse.com/docs/resources/changelogs/oss/2026]. 26.7 release call 23 Jul 2026.
- **Cadence:** **monthly**, with a public release call each month. Very high.
- **Breaking changes — the caution.** The 26.8 changelog is headed with multiple "Backward Incompatible Change" entries: `X-ClickHouse-Format` now *overrides* the query's FORMAT clause; `SOURCE(LIBRARY(...))` now fails; **the Apache Arrow library-based reader and writer for Arrow/ArrowStream were removed** (native became the only implementation, obsoleting `input_format_arrow_use_native_reader`); TLS credentials can no longer be supplied as file paths from SQL; **`clickhouse-client` no longer pings before each query and no longer re-establishes the session**. That is a monthly release with five breaking changes in one version. Operationally this means: **read every changelog before upgrading, and do not skip minors.**
- **Funding — L2 is emphatically satisfied:** $350M Series C 29 May 2025 (Khosla-led) plus a $100M credit facility; **$400M Series D 16 Jan 2026** led by Dragoneer, with Bessemer, GIC, Index, Khosla, Lightspeed, T. Rowe Price and WCM. **Total $1.05B across 7 rounds; post-money valuation ~$15B; 623 employees as of 30 Jun 2026** [tracxn.com/companies/clickhouse; clickhouse.com/blog/clickhouse-raises-400-million-series-d-acquires-langfuse-launches-postgres, 16 Jan 2026].
- **Acquisitions in the last 18 months:** PeerDB (CDC), **HyperDX** (Mar 2025), **LibreChat** (Nov 2025), **Langfuse** (Jan 2026).
- **Alignment:** the acquisitions reveal a company pivoting toward an "agentic data stack" and LLM observability. But the pivot is *additive* to the OSS core, not subtractive from it: ClickStack is open source and HyperDX (Apache-2.0) is now its UI. The core stayed Apache-2.0 through a $1.05B raise and four acquisitions. That is the test the rubric asks about, and it passed.
- **Last two years:** no licence dispute, no governance fight. The direction of travel is toward AI, which is a *focus* risk, not a *licence* risk.
- **Verdict: PASS-WITH-CAUTION.** All three legs. The caution is the monthly breaking-change cadence and a corporate narrative that increasingly isn't "OLAP database."

---

### 3.7 Dagster — **PASS-WITH-CAUTION** (deep dive, §5.3)

- **Governance:** company → **company, and the company changed hands three months ago.** On **13 Jul 2026 Prefect acquired Dagster Labs** (Elementl, Inc. d.b.a. Dagster Labs), including the product, codebase, customer relationships and much of the team. "Following the close of the transaction, the combined company is expected to operate under the **Prefect** name beginning in August 2026" [dagster.io/prefect, letter from the Dagster and Prefect teams, 13 Jul 2026; BusinessWire 20260713065285]. Steward: Pete Hunt (CEO, Dagster Labs), Nick Schrock (founder/CTO), Jeremiah Lowin (founder/CEO, Prefect).
- **Licence:** **Apache-2.0, unchanged** [github.com/dagster-io/dagster/blob/master/LICENSE, "Copyright 2025 Dagster Labs, Inc."].
- **Last release:** **1.13.21, 3 Sep 2026** [pypi.org/project/dagster].
- **Cadence:** weekly patches. 1.13.9 (18 Jun) → 1.13.20 (27 Aug) → 1.13.21 (3 Sep). Extremely active.
- **Activity:** 16.1k stars, 2.3k forks, 2.1k open issues, 495 open PRs, 2,085 contributors in the last year [github.com/dagster-io/dagster].
- **Python:** `Requires-Python >=3.10,<3.15`; README claims "officially supports Python 3.9 through Python 3.14" [pypi.org/project/dagster, accessed 2026-09-27]. **Python 3.14 is in range.** Note the `Requires-Python` metadata (3.10 floor) is the authority, not the README's 3.9 claim.
- **The company's own written commitments** (from the 13 Jul 2026 letter, verbatim): "Dagster continues with full support under its own name and open-source license"; "**Name and open source licence remain unchanged.** We remain committed to the Dagster open source project and community"; "Dagster continues support with a full roadmap. Our focus is on **stability and continuity**."
- **Incentive alignment:** the *incentive* is now suspect in a way it was not before. Prefect's revenue comes from Prefect; Dagster+ is a *second* commercial product inside the same company. Two orchestrators, one P&L, is exactly the configuration that produces "we'll sunset the one with fewer users." The letter promises continuity, but the promise is 3 months old.
- **Last two years:** **major corporate pivot — this is the event.**
- **Verdict: PASS-WITH-CAUTION.** Licence leg: clean, Apache-2.0, so even a hostile move leaves you a forkable codebase. Activity leg: emphatic. The caution is that L1/L2 were re-written in July 2026 and the consolidation is not finished.

---

### 3.8 Debezium — **PASS-WITH-CAUTION** (deep dive, §5.4)

- **Governance:** **Commonhaus Foundation**, since **December 2024**. Move announced 4 Nov 2024 by Chris Cranford [debezium.io/blog/2024/11/04/debezium-moving-to-commonhaus]; completed and reported by InfoQ on 3 Feb 2025. **This is no longer a Red Hat project.** All projects under the `debezium` GitHub org moved; Red Hat donated the trademark and domain names. Commonhaus's IP policy "legally binds the project to remain open-source forever" [debezium.io/foundation/faq]. Steward: the Debezium Steering Committee, majority-vote self-governance [debezium.io/community/governance].
- **Licence:** Apache-2.0. DCO, not CLA. From **January 2026** Debezium only accepts contributions with `Signed-off-by` [debezium.io/blog/2025/12/12/contribution-requirements-changing, 12 Dec 2025].
- **Last release:** **3.6 GA 1 Jul 2026**; 3.6.1.Final 4 Aug 2026; 3.7 in development (26 Aug 2026) [debezium.io/releases; debezium.io/releases/3.6/release-notes]. 301 issues resolved in the 3.6 cycle.
- **Cadence:** 3.0 3 Mar 2025 → 3.1 24 Jun 2025 → 3.2 27 Feb 2026 → 3.3 28 Nov 2025 → 3.4 30 Mar 2026 → 3.5 2 Jun 2026 → 3.6 1 Jul 2026 → 3.7 dev. Roughly 3–4 minors a year.
- **Concentration / bus factor:** the Commonhaus project-representative list is dominated by Red Hat and IBM staff: Jorge Javier Perez Bolaño (IBM + Red Hat), Chris Cranford (IBM/Red Hat), Max Rydahl Andersen (Red Hat), Tako Schotanus (Red Hat), Sanne Grinovero (IBM), Keith Wall (IBM), Kim Joo Hyuk (Toss/FasterXML), Sergio del Amo (Oracle) [commonhaus.org/about, accessed 2026-09-27]. So: **the governance left Red Hat, the headcount did not.** The move is real and legally protective, but do not mistake it for de-Red-Hat-ing.
- **Red Hat build lag — the concrete "Red Hat priority shift" evidence:** Red Hat build of Debezium is at **3.4.3** (RHEA-2026:8348, issued 15 Apr 2026) while the community is at **3.6.1** (4 Aug 2026). Red Hat is shipping a two-minor-behind build. For *us* this is irrelevant — we take community builds from Maven/Docker — but it is the clearest available measure of Red Hat's current Debezium priority, and it has measurably cooled.
- **Breaking changes:** 3.0 required **Java 17 for source connectors and Java 21 for Debezium Server / Operator / Outbox Quarkus extension** [InfoQ, 3 Feb 2025]. 3.2 added Kafka 4.x support. 3.5 relocated the Quarkus extensions into a separate project. 2.7 split the MariaDB connector out of MySQL.
- **Incentive:** post-move, Commonhaus's stated purpose is a stable long-term home, not a product roadmap. The Debezium project still has no obvious commercial engine of its own beyond Red Hat's build. That is a mild *negative* for feature velocity but a strong positive for continuity.
- **Last two years:** governance migration (Nov 2024 → Dec 2024), Jira → GitHub Issues, DCO enforcement from Jan 2026. All in the project's favour. **No damage done.**
- **Verdict: PASS-WITH-CAUTION.** L1 satisfied (Commonhaus). L2: no funding vehicle of its own — funded via Red Hat and OpenCollective [opencollective.com/commonhaus-foundation/projects/debezium, fiscal host since 19 Sep 2025]. L3 emphatically satisfied. Caution = headcount concentration + Red Hat build lag.

---

### 3.9 Apicurio Registry — **PASS-WITH-CAUTION** (deep dive, §5.4)

- **Governance:** **CNCF Sandbox project**, "Copyright Apicurio Registry a Series of LF Projects, LLC" [github.com/apicurio/apicurio-registry README, accessed 2026-09-27]. **It is no longer Red Hat-governed** — the JD's framing is out of date. Development happens on `#apicurio` in CNCF Slack; mailing lists `cncf-apicurio-registry-dev@lists.cncf.io`. Red Hat ships the commercial "Red Hat build of Apicurio Registry" alongside.
- **Licence:** Apache-2.0.
- **Last release:** **3.3.0, 16 Jun 2026**; 3.3.3 on 9 Sep 2026; 3.2.6 on 3 Jul 2026 [apicur.io/blog/2026/06/16/registry-3.3.0-released; mvnrepository.com/artifact/io.apicurio].
- **Cadence:** 3.3.0 → 3.3.1 (28 Jul) → 3.3.2 (29 Aug) → 3.3.3 (9 Sep). Patch cadence is fine. Major cadence: 2.x → 3.0 → 3.1 → 3.2 → 3.3.
- **Activity:** **924 stars, 621 forks, 6,415 commits, 0.x to 3.x in about three years** [github.com/apicurio/apicurio-registry]. Container images are built for *every commit to main*.
- **Funding/incentive:** weak. The community project is a CNCF Sandbox project with 924 stars. The **Red Hat build is the funded artefact** and it lags: Red Hat build GA is at **3.2**, community at **3.3** [access.redhat.com/articles/7014952, updated 16 Jun 2026].
- **Red Hat build's constraints — and this is the "Red Hat priority shift" evidence for Apicurio:** the supported configuration is **OpenShift 4.16–4.20 and OpenShift Service on AWS 4.18 and Azure Red Hat OpenShift 4.17 only**, on **OpenJDK 17 or 11**, with PostgreSQL 13–18 or Red Hat Streams [access.redhat.com/articles/7014952]. So the *commercial build* has been narrowed to OpenShift. **A Red Hat priority shift has already touched Apicurio** — but it did not touch the community project, which is why moving it to CNCF mattered.
- **Breaking changes:** 2.x→3.x was a major break. 3.3.0 added Open Data Contract Standard v3.1 support, a revamped CLI, and HPA support in the operator.
- **Incentive toward our use case:** excellent. Apicurio implements the **Confluent Schema Registry v7 and v8 REST APIs**, so Confluent client libraries use it as a drop-in replacement [docs.redhat.com Apicurio Registry User Guide]. It also implements the IBM Event Streams v1 and CNCF CloudEvents v0 APIs. That is the vendor-neutrality we want.
- **Status:** incubating, but healthy.
- **Last two years:** governance migration (→ CNCF Sandbox). No damage.
- **Verdict: PASS-WITH-CAUTION.** L1 satisfied (CNCF). L2 is the weak leg — small community, funding flows through the Red Hat product, and that product is OpenShift-only. L3 satisfied.

---

### 3.10 OpenLineage — **PASS**

- **Governance:** **LF AI & Data Foundation, Graduate** maturity. "OpenLineage is an LF AI & Data Foundation Graduate project under active development" [openlineage.io/docs/1.46.0].
- **Licence:** Apache-2.0.
- **Last release:** **1.53.0, 1 Sep 2026** [pypi.org/project/openlineage-integration-common].
- **Cadence:** 1.44.0 17 Feb → 1.44.1 20 Feb → 1.45.0 11 Mar → 1.46.0 8 Apr → 1.47.0 8 May → 1.47.1 12 May → 1.48.0 2 Jun → 1.49.0 10 Jun → 1.50.0 18 Jun → 1.51.0 6 Jul → 1.52.0 23 Jul → **1.53.0 1 Sep 2026**. Twelve releases in eight months.
- **Engine coverage:** `openlineage-java`, `openlineage-spark` (Scala 2.13), `openlineage-flink`, `openlineage-sql-java`, `openlineage-hive` all released 23 Jul 2026 [mvnrepository.com/artifact/io.openlineage]. **This is exactly our Flink + Spark stack.**
- **Python:** `Requires-Python >=3.10`; classifiers through **3.14**.
- **Activity:** 3.9k stars. One gap: `openlineage-proxy` last released 19 May 2025, and `transports-dataplex` last released 4 Oct 2024 — those specific sub-projects are lagging. The core spec and the Flink/Spark integrations are not.
- **Incentive:** maximal — lineage is the one thing every vendor in the space wants to be the standard for, and they all implement OpenLineage rather than fork it. Reference implementation is **Marquez**, also LF AI & Data.
- **Status:** graduated, stable.
- **Verdict: PASS.**

---

### 3.11 Prometheus — **PASS**

- **Governance:** CNCF. **Graduated 9 Aug 2018** [cncf.io/projects/prometheus].
- **Licence:** Apache-2.0.
- **Last release:** **3.14.0, 17 Aug 2026**; 3.13.3 7 Sep 2026; 3.13.2 29 Jul; 3.13.1 10 Jul; 3.13.0 1 Jul; 3.12.0 28 May 2026.
- **Cadence:** 3.12.0 (May) → 3.13.0 (1 Jul) → 3.14.0 (17 Aug). One minor per ~6–8 weeks.
- **Activity:** 66k stars, 10.8k forks, **501 open issues, 395 open PRs**, 506 contributors in the past year.
- **Funding:** small commercial entity around it, but the project is CNCF-graduated and the incentive is universal.
- **Status:** stable. Note the 3.x series is the LTS line (3.5.5 9 Jul 2026) and is still receiving security fixes.
- **Verdict: PASS.**

---

### 3.12 Alertmanager — **PASS**

- **Governance:** Prometheus project under CNCF. Apache-2.0.
- **Last release:** **v0.34.1, published 17 Sep 2026** [pkg.go.dev/github.com/prometheus/alertmanager/api/v2/restapi]. v0.34.0 16 Aug 2026; v0.33.1 4 Jul 2026.
- **Cadence:** steady minor bumps. Helm chart `prometheus-community/alertmanager` at 1.42.0 with 1.41.x, 1.40.x, 1.39.x all maintained.
- **Activity:** 8.4k stars, 2.4k forks, 333 open issues, 86 open PRs.
- **Status:** stable. Still 0.x, which signals API caution rather than instability.
- **Verdict: PASS.**

---

### 3.13 Grafana — **PASS-WITH-CAUTION** (deep dive, §5.2)

Full detail in §5.2. Summary: AGPL-3.0-only since v8 (20 Apr 2021), no relicensing in 2025–26, Grafana 13 shipped 21 Apr 2026, Grafana OSS still free and still shipping features. Caution: Grafana OnCall OSS archived 2026-03-24; the Prometheus datasource was extracted to a standalone plugin in 13.2; core alerting, RBAC, audit and Vault integration are Enterprise.

---

### 3.14 Helm — **PASS-WITH-CAUTION**

- **Governance:** CNCF. **Graduated 1 May 2020** [cncf.io/projects/helm].
- **Licence:** Apache-2.0.
- **Last release:** **4.3.0, September 2026**; docs at 4.2.4; `helm` reference page 4.2.4 [helm.sh/docs, helm.sh]. **Helm 4.0 released 17 Nov 2025** [helm.sh/blog/helm-4-released], announced by CNCF on 12 Nov 2025 as the first major in six years.
- **Cadence:** majors every ~6 years, minors monthly.
- **Status:** stable, but in transition. **Helm v3 is in support mode: bug fixes until 8 Jul 2026, security fixes until 11 Nov 2026** [github.com/helm/helm README, accessed 2026-09-27]. That is **seven weeks from now**.
- **Breaking-change history:** Helm 2 → 3 (Nov 2020) was severe (labels → annotations, `helm init` gone, `requirements.yaml` → `Chart.yaml`). Helm 3 → 4 (Nov 2025) is smaller but real: chart API changes, client/server split. The `apiVersion: v2` chart format is Helm 3's; v4 charts use a new schema.
- **In our environment:** we have no `kubectl` and no cluster. Helm's role here is **rendering chart templates locally to produce manifests**, not deploying. That materially reduces the migration cost — we do not depend on Helm 3's Tiller-era release storage or on a live cluster handshake.
- **Verdict: PASS-WITH-CAUTION.** L1/L2/L3 all fine. Caution is a live major-version transition with a 7-week v3 security deadline.

---

### 3.15 OpenTofu — **PASS**

- **Governance:** **Linux Foundation** — "OpenTofu is a Series of LF Projects, LLC" [opentofu.org/docs/v1.11/intro/whats-new footer]. Created Sept 2023 specifically as the response to HashiCorp relicensing Terraform from MPL-2.0 to BUSL 1.1, with a founding commitment of "a minimum of 18 full-time developers over at least the next five years" from the founding companies [linuxfoundation.org/press/announcing-opentofu, 20 Sep 2023]. Note the founding commitment window is exactly our 5-year horizon — worth re-checking in 2028.
- **Licence:** **MPL-2.0** (file-level copyleft, weaker than AGPL; no network-use clause).
- **Last release:** **1.12.0** is current [opentofu.org/docs/v1.13/intro/whats-new banner: "🎉 OpenTofu 1.12.0 is released!"]; 1.11.0 in the stable docs; 1.13 in beta. 1.11 highlights: ephemeral/write-only values, SHA-1 signatures no longer accepted for TLS or SSH.
- **Cadence:** ~one minor per quarter. Healthy.
- **Activity:** 29.7k stars, 1.3k forks, 272 open issues, 50 open PRs, 286 contributors in the past year.
- **Infrastructure:** registry operational; status page shows one 1h57m degradation on 8 Jun 2026 and 100% uptime otherwise [status.opentofu.org, last updated 5 Sep 2026].
- **Incentive:** exists *because* open source is the product. Cleanest alignment in the audit.
- **Verdict: PASS.** This is the direct answer to the Terraform failure.

---

### 3.16 PostgreSQL — **PASS**

- **Governance:** the PostgreSQL Global Development Group — a traditional non-profit-style consortium of companies and individuals, not a foundation, but with 30+ years of unbroken governance and no corporate steward to pivot away.
- **Licence:** PostgreSQL License (BSD-2-Clause-like). No relicensing history.
- **Last release:** **18.6, 17.11, 16.15, 15.19, 14.24 and 19 Beta 3, all 13 Aug 2026** [postgresql.org/about/news/…-released-3365]. 28 security vulnerabilities and 110+ bugs fixed in one coordinated release.
- **Cadence:** annual major; quarterly-ish minors across all supported lines. **18.0 released 25 Sep 2025**; **18 support ends 14 Nov 2030**.
- **Policy:** 5 years of support per major [postgresql.org/support/versioning]. PostgreSQL **14 hits EOL 12 Nov 2026**.
- **Breaking changes:** annual major, low friction, `pg_upgrade` or `pg_dump`/restore. One honest datapoint: **18.5 was never shipped** because of a regression [13 Aug 2026 release note: "This release skips PostgreSQL 18 versions from PostgreSQL 18.4 to 18.6. 18.5 was not shipped due to a regression."]
- **Status:** stable, the most stable project in this audit.
- **Verdict: PASS.**

---

### 3.17 SeaweedFS — **PASS-WITH-CAUTION**

- **Governance:** **individual, patron-funded.** "SeaweedFS is an independent Apache-licensed open source project with its ongoing development made possible entirely thanks to the support of these awesome backers" — Patreon-funded, with a commercial SeaweedFS Enterprise Edition at seaweedfs.com [github.com/seaweedfs/seaweedfs README, accessed 2026-09-27].
- **Licence:** Apache-2.0.
- **Last release:** **4.45, 31 Aug 2026** [github.com/seaweedfs/seaweedfs/releases]. 4.39 was 10 Jul 2026.
- **Cadence:** 4.36 → 4.45 across roughly six weeks. Very high.
- **Activity:** **34.5k stars, 3k forks, 679 open issues, 89 open PRs.**
- **Bus factor / concentration — the caution:** the 4.45 release notes are dominated by `@chrislusf` across volume server, master, S3 API, gRPC and install scripts, with dependabot and a handful of outside contributors. Chris Lu (chrislusf) is the project. **Bus factor: 1.** This is the same structural shape as the MinIO failure, with the difference that SeaweedFS is Apache-2.0 and independently funded rather than a VC-backed company that can decide to stop.
- **Feature risk for us:** one 2026 comparison puts SeaweedFS at **~60% S3 API coverage**, with versioning, SSE, object lock, lifecycle policies and event notifications all unimplemented [dev.to/ethan-carter, 5 Aug 2026]. **Iceberg on S3 needs versioned writes and conditional PUT (`If-Match`) on `metadata.json`.** Versioning being absent is a genuine concern that must be tested before committing.
- **Incentive toward our use case:** SeaweedFS has now first-class **Iceberg table** support ("distributed storage system for object storage (S3), file systems, and Iceberg tables" [github.com/seaweedfs/seaweedfs, 2026]) plus a Lance catalog and a Rust worker. Incentive is aligned.
- **Last two years:** no licence dispute, no governance fight. Sole risk is the single maintainer.
- **Verdict: PASS-WITH-CAUTION.** L1 is "individual" — the weakest steward class. L2 is Patreon + an enterprise edition: real, small, and aligned. L3 is emphatic. The caution is that a bus factor of 1 is how SeaweedFS dies, even if it will not die the way MinIO died.

---

### 3.18 RustFS — **PASS-WITH-CAUTION**

- **Governance:** company. **RustFS**, rustfs.com. Steward: the RustFS org (27 public repositories).
- **Licence:** **Apache-2.0** — a genuine advantage over MinIO's AGPL and over Garage's.
- **Last release:** **1.0.0-beta.10, 17 Jul 2026** [rustfs.com blog listing]. Still pre-1.0 roughly a year after open-sourcing.
- **Cadence:** frequent commits (repo activity through 5–6 Sep 2026) but no 1.0 GA.
- **Activity:** **31.8k stars, 1.4k forks, 27 open issues, 6 open PRs.** The star-to-issue ratio is a red flag: an enormous audience with a very thin issue backlog, typical of a project whose star count was driven by "MinIO is dead, here's the replacement" search traffic rather than by production use.
- **Incentive:** RustFS's *entire* pitch is "the MinIO replacement." That is the same pitch MinIO itself ran, and it ended with MinIO's community edition retired. If the S3-object-store-for-AI market consolidates, the loser archives. **On-disk format is byte-compatible with MinIO**, which cuts both ways: it makes migration to/from trivial, and it means RustFS is a reimplementation whose differentiation is performance claims ("2.3x faster than MinIO for 4KB object payloads").
- **Funding:** no public funding round found. The rubric's L2 requires "funding **and** incentive" for company-backed projects. RustFS has the incentive but I found **no evidence of disclosed funding**. That is an L2 gap.
- **Status:** **pre-1.0 beta.** Object stores in beta hold data.
- **Last two years:** no licence dispute. The risk is maturity and an unfunded single-vendor posture.
- **Verdict: PASS-WITH-CAUTION.** It is the *best-licensed* of the three non-foundation options and its S3 fidelity is the best of the three, but it is a **beta** from a company with no disclosed funding whose entire go-to-market is "the thing that replaced MinIO." **Not eligible to hold data we cannot lose.**

---

### 3.19 Garage — **PASS-WITH-CAUTION**

- **Governance:** individual/association. Built by **Deuxfleurs**, described on its own Docker Hub page as "an experimental small-scale self hosted service provider, which has been using it in production since its first release in 2020" [hub.docker.com/r/dxflrs/garage]. No foundation, no VC.
- **Licence:** **AGPLv3** — "Garage is entirely free software released under the terms of the AGPLv3."
- **Last release:** **v2.3.0, 16 Apr 2026**; v2.2.0 and v1.3.1 both 24 Jan 2026; v2.0.0 14 Jun 2025; v2.0.0-beta1 17 Apr 2025 [git.deuxfleurs.fr/Deuxfleurs/garage/releases].
- **Cadence:** real. ~230 Docker image builds; latest image 3 Sep 2026; 255,665 pulls in the past week.
- **Activity:** **170 stars, 193 forks, 58 watchers, 170 open issues, 30 open PRs.** 5.12M Docker pulls.
- **Funding:** self-funded by Deuxfleurs' operations. This is **L2's weak point** — no external funding, and the company describes itself as "experimental."
- **Breaking changes:** 2.0.0 "contains the following breaking changes since the v1.x series" with particular impact on the admin API. v2.3.0 is explicitly non-breaking; 2.2.0 and 1.3.1 non-breaking; 2.1.0 had one admin-API break.
- **Fitness:** AGPLv3 (copyleft, network-use clause) and a **3-node minimum** for distributed operation. v2.3.0 added `garage server --single-node`, which makes a 1-node trial possible. Even so, running a 3-node cluster on a 12-CPU/14 GB box alongside Kafka, Spark, Flink and ClickHouse does not fit.
- **Incentive:** the maintainers are explicit that they are courting MinIO refugees ("relaxed requirements on imported access keys to allow easier transition from other S3 storage providers"). Aligned, but a small, self-funded team chasing a migration wave is a fragile base.
- **Last two years:** no licence dispute, no governance fight. Healthy and slow-moving.
- **Verdict: PASS-WITH-CAUTION.** L1 "association", L2 self-funded/experimental, L3 genuinely healthy. Excluded from our shortlist on **fit** (AGPL + 3 nodes + resource budget), not on longevity.

---

### 3.20 Apache Ozone — **PASS** (excluded on fit, not longevity)

- **Governance:** ASF TLP. Apache-2.0.
- **Last release:** **2.2.1, 27 Aug 2026**; 2.1.2 18 Sep 2026; 2.1.1 21 Jun 2026; 2.0.0 4 Apr 2025 [release-catalog.apache.org/ozone; ozone.apache.org/download].
- **Cadence:** 2.0.0 Apr 2025 → 2.1.1 Jun 2026 → 2.2.1 Aug 2026. Regular.
- **Activity:** 11,206 commits, but only **1.27k stars / 635 forks** — small for an ASF TLP.
- **Incentive:** the ASF, plus Cloudera embedding Ozone in CDP Private Cloud Base [docs.cloudera.com]. Hadoop-native rather than cloud-native.
- **Status:** stable and improving (2.0 added 1,700 changes; 2.1 added 805).
- **Last two years:** no governance fight, no licence dispute.
- **Verdict: PASS on all three rubric legs.** But see §5.3: it does not fit our hardware.

---

### 3.21 Container runtime — **Podman PASS (upgrade required) / Docker Engine PASS-WITH-CAUTION**

**Podman**
- **Governance:** Red Hat–developed, part of the `containers` community, Apache-2.0. Not a foundation project, but Red Hat is a durable 30-year steward with clear incentive and the project is upstream for RHEL, Fedora and CentOS.
- **Last release:** **6.1.1, 2 Sep 2026**; 6.1.0 12 Aug 2026 [endoflife.date/podman].
- **⚠️ The installed version is EOL.** **Podman 5.7 (released 11 Nov 2025) reached end of security support on 12 Feb 2026.** 6.0 went EOL 12 Aug 2026. **5.8's security support ends 26 Sep 2026 — tomorrow.** [endoflife.date/podman, updated 3 Sep 2026]
- **Support model:** upstream-first. Only the latest minor gets full support; older lines get best-effort backports from distros. [versionlog.com/podman, 22 Jul 2026] So this is a *recurring* obligation, not a one-off.
- **Verdict: PASS, conditional on upgrading to 6.1.x.** Podman 5.7 as installed **fails the L3 floor today**.

**Docker Engine**
- **Governance:** company. The `moby/moby` project is Apache-2.0 and community-run; the Docker *products* (Desktop, Engine as a distribution) are commercial, run by Mobara following Mirantis's acquisition of the Docker business. No foundation home.
- **Last release:** **Docker Engine 29.8.0, 3 Sep 2026**; 29.0 10 Nov 2025 [endoflife.date/docker-engine].
- **Cadence:** 29.x supported; 28.x EOL 13 May 2026; 25.0 support ends 4 Dec 2026. Aggressive EOL cadence — the 27→28→29 sequence burned three supported lines in 15 months.
- **Incentive:** Docker, Inc. pivoted away from the Engine (2023) and back to it. The Engine is now largely maintained to feed cloud vendors, not to serve users directly. Weak incentive.
- **Verdict: PASS-WITH-CAUTION.** L1 fails the "preferred" test (no foundation), L2 is satisfied on funding but weak on incentive, L3 is satisfied. Podman is the better choice here, and we already have it.

---

## 4. JDK and Python pinning — the concrete answer

### What the engines actually support

| Component | Java | Python |
|---|---|---|
| **Flink 2.3** (25 Jun 2026) | **Java 11** supported; **Java 17 is the default and the recommended version, and is the default in the official Docker images** since 2.0.0; **Java 21 is "experimental support"** since 2.0.0. **No Java 25. No Java 26.** [nightlies.apache.org/flink/flink-docs-stable/docs/deployment/java_compatibility; flink.apache.org/downloads] | **3.9, 3.10, 3.11 or 3.12 only.** "Note Python version (3.9, 3.10, 3.11 or 3.12) is required for PyFlink." **No 3.13. No 3.14.** [nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/installation] |
| **Spark 4.2.0** (14 Jul 2026) | **"Spark runs on Java 17/21/25"**, and "**Java 25 prior to version 25.0.3 support is deprecated as of Spark 4.2.0**." **No Java 26.** [spark.apache.org/docs/latest] | **PySpark: "Python 3.10 and above."** "PySpark requires Java 17 or later." [spark.apache.org/docs/latest/api/python/getting_started/install.html] |
| **Spark 4.1.x** | **Java 17/21 only.** No 25. [spark.apache.org/docs/4.1.1] | 3.10+ |
| **Debezium 3.x** | **Java 17** for source connectors; **Java 21** for Debezium Server, Operator, Outbox Quarkus extension. [InfoQ, 3 Feb 2025] | n/a (Java) |
| **Apicurio Registry (Red Hat build)** | **OpenJDK 17 or 11** [access.redhat.com/articles/7014952] | n/a (Java) |
| **Dagster 1.13.21** | n/a | `Requires-Python >=3.10,<3.15` — **3.14 supported** [pypi.org/project/dagster] |
| **OpenLineage 1.53.0** | n/a | `Requires-Python >=3.10`; classifiers through **3.14** [pypi.org/project/openlineage-integration-common] |
| **ClickHouse 26.8** | No JDK requirement — C++ binary. | ClickHouse client libs; no version floor published that binds us. |

### The answer

**Java 25 is not viable. Java 26 (what is actually installed) is further out still.**

- **Flink has no Java 25 support at all.** Its documented ceiling is Java 21, and Java 21 is explicitly labelled *experimental*. Java 17 is the documented default for the official images.
- **Spark's Java 25 support is brand new and conditional**: it arrived in 4.2.0 (14 Jul 2026) and is deprecated for anything below **25.0.3**. Spark 4.1.x, the version most ecosystem components are still built against, does not support it at all.
- **No project in the stack supports Java 26.**

> **Pin every JVM container image to JDK 17 (Eclipse Temurin 17).**
> JDK 17 is simultaneously the Flink default, the Flink-recommended version, the official-image default, a Spark-supported version, a Debezium-supported version, and an Apicurio-supported version. It is the only JDK that requires no caveat on any leg. **JDK 21 is the acceptable second choice** if you want a newer runtime — Debezium Server/Operator *require* 21 — but you then accept Flink's "experimental" label. **Do not use 25. Do not use 26.**

**Python 3.14 is not viable for the pipeline; 3.12 is the only version that satisfies everything.**

- **PyFlink caps at Python 3.12.** This is a hard, documented cap: "the version printed here must be 3.9, 3.10, 3.11 or 3.12." Python 3.13 and 3.14 are not supported by any current Flink release.
- **PySpark needs 3.10+.** 3.12 satisfies it.
- Dagster and OpenLineage both accept 3.12 (and also 3.14, but that does not help us).

> **Pin Python containers to 3.12.**
> 3.12 is the **only** interpreter in the intersection of {3.9, 3.10, 3.11, 3.12} ∩ {3.10, 3.11, 3.12, 3.13, …} that also gives you a currently-supported CPython. 3.11 is the second-best choice if you want maximum conservative distance from the edges. **3.14 works for Dagster and OpenLineage *only*, so it must never be the interpreter inside a Flink or Spark image.**

**Host vs image.** The host JDK 26 and host Python 3.14 can stay on the host for tooling, editors and linting. They must not be the runtime for any engine. Every container carries its own pinned interpreter, so the host version is irrelevant to the pipeline — but it is a live footgun for anyone who tries to run `flink` or `pyspark` directly on the host. Document the pin; do not rely on the host.

**Also pin:** `PYSPARK_PYTHON=3.12` / `PYSPARK_DRIVER_PYTHON=3.12` in Spark image env, and the Flink `--python.executable` / `python.client.executable` settings, because PyFlink resolves the interpreter separately from the TaskManager JVM.

---

## 5. The four deep dives

### 5.1 Apache Polaris — is depending on it a risk worth taking?

**No, not any more — the risk the assignment describes was resolved in February 2026.**

The job posting calls Polaris an "Apache *incubating* project." That framing is **out of date**.

- **Polaris entered incubation 9 Aug 2024 and graduated to a Top-Level Project on 15 Feb 2026** [incubator.apache.org/projects/polaris.html]. Announced publicly 18–19 Feb 2026 at the ASF, with Snowflake, Dremio, Google, Microsoft and Confluent all endorsing [GlobeNewswire, 19 Feb 2026; Snowflake engineering blog, 19 Feb 2026; Manila Times, 19 Feb 2026].
- The docs site has moved from `polaris.incubator.apache.org` to **`polaris.apache.org`**.
- Current version **1.7.0, 2 Aug 2026**. The 1.x line shipped 1.0.0 on 9 Jul 2025 — so the stable API surface is roughly **14 months old**.
- **Adoption is real, not theoretical.** Snowflake's Horizon Catalog "now runs its interoperability on Apache Polaris and enables bi-directional read and write access to Snowflake-managed Iceberg tables from outside engines." Dremio Cloud's Open Catalog is "the foundation of" Polaris, and Dremio "remains one of the project's most active participants." 1.4 added storage-scoped AWS credentials, STS session tags for CloudTrail correlation, S3 KMS, and CockroachDB as a persistence backend — i.e. production hardening, exactly what a newly-graduated TLP needs.

**The genuine risk is cadence, not survival.** Seven minor versions in thirteen months (1.0.0 Jul 2025 → 1.7.0 Aug 2026) is a ~6-week minor cadence. Polaris is where the ecosystem's newest thinking lands first, which means we will absorb churn upstream of anything else in the stack. That is a *maintenance-cost* risk, not a *longevity* risk.

**Realistic fallbacks and their migration cost**

| Fallback | Governance | Cost to switch from Polaris |
|---|---|---|
| **Lakekeeper** | Apache-2.0, Rust, maintained by Vakamo (German). 1.4k stars, active through Sep 2026. Implements the Iceberg REST spec on top of `apache/iceberg-rust`; default authorisation via **OpenFGA**; Postgres backend; open-source console. | **Low — hours.** Same REST spec, so Flink/Spark/Trino change only a `uri` and credentials. Polaris-specific surface to port: its role model and its credential-vending flows. |
| **Unity Catalog (OSS)** | Databricks-backed, Apache-2.0. | **Medium — days to weeks.** Different auth model, needs Spark Unity integrations; loses the "any engine" property. |
| **Apache Hudi / Hadoop catalog** | ASF. | **High.** Different catalog semantics entirely; only a target if you migrate the table format too. |
| **Project Nessie** | ASF incubating. | **Medium-high.** Git-style versioned catalog; different model. |
| **Dremio OSS** | Company, Apache-2.0 for OSS. | **Medium.** Works, but drags Dremio into the picture. |
| **OpenMetadata / DataHub** | LF AI & Data / Linux Foundation lineage. | **Medium-high.** Full metadata platforms, not just catalogs. |

**Recommendation: adopt Polaris, and architect so the swap is cheap.** Concretely — (a) talk to it **only** through the Iceberg REST spec, never through Polaris-proprietary admin APIs; (b) keep the catalog's own state in Postgres or CockroachDB, not in a Polaris-specific store; (c) if the 6-week minor cadence becomes painful, Lakekeeper is a same-spec escape hatch measured in hours. Polaris is cheap to leave *precisely because* it is a spec implementation, and that is also the strongest argument that it will not be abandoned.

---

### 5.2 Grafana — is Grafana OSS still maintained and still free?

**Yes on both counts. Grafana OSS is alive, is AGPL-3.0, and is free forever unless Grafana Labs changes its mind again.**

**Separate the three things that get conflated:**

1. **The licence.** Grafana relicensed its core projects from Apache-2.0 to **AGPLv3 on 20 April 2021** [grafana.com/licensing]. That is the last relicensing event — five years ago. **No relicensing, and no threat of one, in 2025 or 2026.** Grafana Labs is a private company, so there is no foundation fallback; the AGPL grant is the only protection, and it is a real one.
2. **The OSS edition.** The default `LICENSE` is **AGPL-3.0-only**, with **Apache-2.0 exceptions** for `packages/grafana-data/`, `packages/grafana-runtime/`, `packages/grafana-ui/`, `packaging/`, `kinds/`, `pkg/kinds/`, `pkg/kindsys/`, `pkg/registry/schemas/`, `grafana-mixin/` and some icon sets [github.com/grafana/grafana/blob/main/LICENSING.md, accessed 2026-09-27]. The Enterprise Plugin License explicitly defines "**Grafana OSS** shall be the open source version of Grafana, available **free of charge** under the AGPLv3 license" [grafana.com/legal/enterprise-plugins].
3. **The feature split.** RBAC, data-source permissions, query caching, recorded queries, Vault integration, auditing, request security, runtime settings updates and ~100 premium data sources are Enterprise. Core dashboards, PromQL, Explore, drilldown, transformations, dashboard-as-code and **Grafana Alerting (the unified, in-app alerting)** are OSS.

**Is OSS maintained? Yes, and it ships OSS-first features:**

- **Grafana 13.0.0 released 14 Apr 2026** (tag `v13.0.1` published 17 Apr 2026), launched at GrafanaCON 2026 in Barcelona on **21 Apr 2026** alongside 35M users and a redesigned Loki architecture. Grafana Labs also announced the acquisition of **Logline** that day [businesswire 20260421839174; grafana.com/blog/grafana-13-release-all-the-latest-features/]. **13.1.0 shipped in May 2026.**
- Features landing in **Grafana OSS** specifically: multi-property variables GA (Jun 2026), section-level variables GA (11 Jun 2026), quick filters and grouping GA (13 May 2026), dynamic dashboards GA, copy-and-paste panel styles GA (26 May 2026), table visualisation upgrades, time-series-to-table transformation GA, and **Grafana Assistant extended to Grafana OSS users** (21 Apr 2026) [grafana.com/whats-new, pages 2, 4, 5].
- **76.6k stars, 14.7k forks, 72,851 commits** on `grafana/grafana` [accessed 2026-09-27].

**So: is Grafana OSS still maintained and still free? Yes.** Separately from the enterprise/licensing debate, the OSS edition is actively developed and costs nothing.

**But the caution is real, and there is a dated precedent.** Grafana Labs' own OSS page now says: **"Grafana OnCall OSS is now in maintenance mode and will be archived on 2026-03-24."** [grafana.com/oss, accessed 2026-09-27]. That is the company retiring an OSS edition. Not the one we want — but it establishes the pattern is live, not theoretical.

Two more 2026 signals worth recording:
- **In Grafana 13.2 the Prometheus data source is no longer built into Grafana** — it ships as a standalone plugin (still preinstalled, still free, still Apache-2.0-ish, still auto-updatable) [github.com/grafana/grafana docs/sources/datasources/prometheus/_index.md, review_date 2026-08-04]. Practical impact is small; the *symbolic* impact is that Grafana Labs is now willing to move core datasources out of the AGPL core into a plugin layer.
- In Grafana 13, the core Prometheus data source **no longer supports SigV4 or Azure AD auth** — both moved to dedicated plugins. If we ever need SigV4 to reach a managed Prometheus, that is now a plugin.
- Grafana 13 also **tightened RBAC enforcement** for custom roles and Terraform-managed roles, flagged as a breaking change [5 May 2026].

**Alternatives that keep Prometheus and Alertmanager**

Prometheus and Alertmanager are **unaffected by any of this** — they are CNCF-graduated, Apache-2.0, and independently healthy. If Grafana became a problem, we would swap only the visualisation layer.

| Option | Governance | Licence | Keeps Prometheus? | Keeps Alertmanager? | Cost |
|---|---|---|---|---|---|
| **Perses** | **CNCF Sandbox** (accepted 29 Aug 2024). Health score **84 (Healthy)**. 1,319 contributors (+91% YoY), 469 contributing organisations (+64% YoY), 1,005 stars (+76% YoY), 268 forks (+201% YoY) [cncf.io/projects/perses, 25 Sep 2026] | Apache-2.0 | Yes — Prometheus/Thanos/Jaeger first class | **No.** Dashboards only. Run Alertmanager standalone and link out. | **Low now, high later.** No Grafana-dashboard import path; every dashboard is re-authored. But this project has ~zero dashboards, so the sunk cost is near zero. |
| **Nightingale** | Hosted by the CCF Open Source Development Committee. Apache-2.0 [n9e.github.io] | Apache-2.0 | Yes | Yes — has its own alerting (inhibit, mute, subscription) | **Medium.** Different dashboard model; built around Categraf/Telegraf collectors. |
| **OpenSearch Dashboards** | Apache-2.0, AWS | Apache-2.0 | Via Prometheus data source | Via Alertmanager data source | **High.** Heavy; drags in OpenSearch. |
| **Netdata / Uptime Kuma** | Community | Mixed | Partial | No | Not equivalent. |

**Recommendation: use Grafana OSS (13.x, AGPLv3).** Reasons: (a) it is genuinely maintained and genuinely free — the evidence above is unambiguous; (b) the AGPL grant is durable and only a full licence change could break us, and there is no sign of one; (c) for a *portfolio* project the Grafana dashboard ecosystem and the Prometheus integration are worth more than the licence purity; (d) the substitution cost is real but the substitution path is known. **But keep the dashboard definitions in Git as dashboard-as-code rather than as objects in a Grafana instance** — that is the single thing that makes a future Perses switch affordable, and it costs nothing today.

**One non-obvious risk to record:** the AGPL network-use clause means if we ever modify Grafana and serve it to users, we owe them our modifications. We will not modify it. Unmodified AGPL deployment as an internal tool is clean. Flagging it so nobody later "adds a small custom panel" and creates a distribution question.

---

### 5.3 ClickHouse and Dagster — company-backed, is the backing durable, and is the core being pulled?

These two look similar (company-backed, commercial cloud on top) and are in fact opposites.

#### ClickHouse — **backing is extremely durable; the core is not being pulled, but it is being outrun**

- **Backing durability: very high.** $1.05B raised across 7 rounds; **$400M Series D on 16 Jan 2026**; ~$15B post-money; 623 employees. Investors include Dragoneer, Bessemer, Khosla, Index, Lightspeed, GIC, T. Rowe Price, WCM, Benchmark, Coatue, FirstMark, Nebius. This is not a company that runs out of money and archives a repo [clickhouse.com/blog/clickhouse-raises-400-million-series-d…, 16 Jan 2026].
- **What the licence actually permits.** **Apache-2.0, unchanged since 15 June 2016** — verified against `LICENSE` on 27 Sep 2026, which reads "Copyright 2016-2026 ClickHouse, Inc. … Licensed under the Apache License, Version 2.0." Apache-2.0 grants perpetual, irrevocable rights to use, modify and redistribute, with an express patent grant. **Nothing ClickHouse has done since 2016 restricts what we can do with it.** The clickhousectl CLI, clickhouse-connect, clickhouse-java, pg_clickhouse and ClickStack are all separately Apache-2.0.
- **Is the core being pulled away from open-source users?** **No — but attention is shifting.** The acquisitions (PeerDB, HyperDX Mar 2025, LibreChat Nov 2025, Langfuse Jan 2026) plus the Jan 2026 launch of a **native Postgres service** show a company broadening into an "agentic data stack." The risk is that a very large engineering org starts optimising for LLM observability and AI-shaped features. The mitigations are real: the acquisitions were *of open-source projects*, HyperDX (Apache-2.0) became the ClickStack UI, ClickStack is open source, and the tenth-anniversary post (16 Jun 2026) re-affirmed Apache 2.0. **The direction of travel is additive, not subtractive.**
- **The actual operational risk is release cadence, not governance.** ClickHouse ships **monthly** and each release carries a "Backward Incompatible Change" section. 26.8 alone changed `X-ClickHouse-Format` semantics, removed the Arrow-library reader/writer, made `SOURCE(LIBRARY(...))` an error, forbade TLS credential paths from SQL, and changed `clickhouse-client`'s connection behaviour. **Rule: read the changelog on every monthly release, never skip a minor, and treat LTS releases (26.6, 26.8) as the upgrade target.**
- **Verdict: PASS-WITH-CAUTION.** All three legs, strongly. Caution = monthly breaking changes + an AI-pivoting corporate narrative.

#### Dagster — **the backing changed shape 3 months ago; the core licence is safe, the roadmap risk is not**

- **What happened, with dates.** **13 July 2026: Prefect acquired Dagster Labs** (Elementl, Inc. d.b.a. Dagster Labs) — the product, the codebase, customer relationships and much of the team [BusinessWire 20260713065285]. "The combined company is expected to operate under the **Prefect** name beginning in **August 2026**" [dagster.io/prefect]. Signed by Pete Hunt (CEO, Dagster Labs), Nick Schrock (founder/CTO, Dagster) and Jeremiah Lowin (founder/CEO, Prefect).
- **What they have committed to, in writing:** "**Name and open source licence remain unchanged.** We remain committed to the Dagster open source project and community." "Dagster continues support with a full roadmap. Our focus is on **stability and continuity**." "Dagster's open source project continues under its existing license, and Dagster+ remains a supported commercial offering." "Nothing about your Dagster deployment changes as a result of today's announcement."
- **What the licence actually permits.** **Apache-2.0**, verified on `master` on 27 Sep 2026. Prefect is also Apache-2.0. There is no CLA, no BUSL, no source-available clause, no CLA-assignment trap. **If Prefect ever relicensed Dagster to something hostile, we would still hold a perpetual, irrevocable right to the code we obtained under Apache-2.0.** This is the single most important fact in the Dagster assessment, and it is categorically different from MinIO (where the AGPL also survived, but there was nobody left shipping fixes) and from Terraform (where the BUSL actively removed rights we had once held).
- **Has either signalled moving the open-source core in a direction that would hurt us?** Dagster's framing is "asset orientation matters more every year as data becomes the foundation for AI" — that is a *thesis about data*, not a threat to the core. The risk is mundane and structural: **two orchestrators inside one company means product rationalisation.** Prefect and Dagster overlap heavily. The "stability and continuity" language is exactly what MinIO, and every other acquirer of an OSS project, says. It was also true on the day MinIO said it.
- **Backing durability:** Prefect is well-capitalised and the acquisition means Dagster now has a *larger* balance sheet behind it, plus a second commercial product to cross-sell. Durability of *funding* is high. Durability of *project identity* is what is in question, and it is unanswerable for another 2–4 quarters.
- **Activity in the meantime is not the problem:** 1.13.21 on 3 Sep 2026, weekly patches, 16.1k stars, 2,085 contributors in the past year, Python 3.10–3.14.
- **Verdict: PASS-WITH-CAUTION.** Licence leg: clean and permanently so. Activity leg: emphatic. The caution is a **fresh, unfinished corporate consolidation of exactly the MinIO shape**, with the difference that the licence means we keep the code. Treat Dagster as replaceable (see §7) and pin the version.

---

### 5.4 Debezium and Apicurio — has a Red Hat priority shift already damaged either?

**Short answer: no, and both have already escaped Red Hat governance. The one measurable Red Hat retreat is in the *commercial builds*, not the community projects.**

#### Debezium — moved to Commonhaus; Red Hat's *build* has cooled, the project has not

- **Governance timeline:** exclusively Red Hat-sponsored from 2015 → **4 Nov 2024** announcement of the move to Commonhaus [debezium.io/blog/2024/11/04/…] → **December 2024** completed [debezium.io/blog/2025/12/12/…] → **3 Feb 2025** reported by InfoQ. The donation included the **Debezium trademark and all related domain names**. Commonhaus's IP policy "**legally binds the project to remain open-source forever**" — the strongest available protection short of ASF neutral governance [debezium.io/foundation/faq].
- **The honest caveat: the headcount did not de-Red-Hat.** Of the eight Commonhaus project representatives listed for Debezium and neighbours, four are Red Hat and two more are IBM [commonhaus.org/about, 27 Sep 2026]. The Debezium Steering Committee is a majority-vote body of committers, but the committers are overwhelmingly Red Hat/IBM. The move gave the project *legal* independence and a durable home. It did not create a second employer of Debezium engineers.
- **The measurable Red Hat priority shift:** the **Red Hat build is at 3.4.3** (RHEA-2026:8348, issued 15 Apr 2026) while the **community is at 3.6.1** (4 Aug 2026) [access.redhat.com/errata/RHEA-2026:8348; debezium.io/releases/3.6/release-notes]. A ~2-minor lag, maintained across Debezium 3.0–3.6. Red Hat's Debezium *product* has cooled relative to the community *project*.
- **Has that damaged the community project? No.** The project shipped 3.0 (Mar 2025), 3.1 (Jun 2025), 3.2 (Feb 2026), 3.3 (Nov 2025), 3.4 (Mar 2026), 3.5 (Jun 2026), 3.6 (Jul 2026), with 301 issues resolved in 3.6 alone, and is developing 3.7. The changes in that window are *feature* changes — Debezium Server Quarkus extension, Docling SMT for document processing, Amazon SNS sink, OAuth2 for the HTTP sink, a new unbuffered LogMiner adapter for Oracle, CockroachDB and Ingres connectors, PostgreSQL 18 support, an OpenLineage output set for Debezium Server. **The project got more active after leaving Red Hat's exclusive sponsorship, not less.**
- **The governance changes that *did* land** are the Commonhaus compliance work: Jira → GitHub Issues, and **from January 2026, signed-off commits are mandatory** (DCO) [12 Dec 2025]. For us: sign off your fork commits.
- **Verdict: PASS-WITH-CAUTION.** L1 satisfied and legally protected. L2 is the weak leg — no funding vehicle of its own (Patreon-equivalent via OpenCollective plus Red Hat's build) — but the incentive is *continuity*, which is the right incentive. Caution = headcount concentration plus a Red Hat build that has visibly deprioritised. **For our purposes the Red Hat build is irrelevant; take community builds.**

#### Apicurio Registry — moved to CNCF Sandbox; the Red Hat build was narrowed to OpenShift, the community project was unharmed

- **Governance:** the current README states plainly: "**Apicurio Registry is a Cloud Native Computing Foundation Sandbox project.** … Copyright Apicurio Registry a Series of LF Projects, LLC" [github.com/apicurio/apicurio-registry, 27 Sep 2026]. Development is on CNCF Slack; the security list is `cncf-apicurio-registry-security@lists.cncf.io`. The repo also carries a `GOVERNANCE.md`, a `dco.txt` and a `GENERAL_TECHNICAL_REVIEW.md`. **This is a proper foundation home, not a Red Hat community project.** The JD's framing here is wrong in the project's favour.
- **The Red Hat priority shift, measured:** the "Red Hat build of Apicurio Registry" supported configuration is now **OpenShift 4.16, 4.17, 4.18, 4.19, 4.20 only**, plus OpenShift Service on AWS 4.18 and Azure Red Hat OpenShift 4.17 — with **OpenJDK 17 or 11** [access.redhat.com/articles/7014952, updated 16 Jun 2026]. **A Red Hat-supported product that requires OpenShift is a Red Hat product for OpenShift, not for Kubernetes generally.** And the Red Hat build is at **3.2 GA** while the community is at **3.3.3** (9 Sep 2026) — a one-minor lag.
- **Has that damaged the community project? No — the opposite.** 3.3.0 (16 Jun 2026) is a substantial release: **Open Data Contract Standard v3.1** support with a parser, projection engine, Contract REST API and export-from-artifacts; a fully revamped CLI (contexts, draft updates, Basic + OAuth2); HPA and auto-RBAC in the Kubernetes Operator; artifact references in the UI; a `MCP_TOOL` artifact type; and an API Lifecycle Governance capability (deprecation management, consumer tracking, impact analysis). Patch releases 3.3.1/3.3.2/3.3.3 landed 28 Jul, 29 Aug and 9 Sep 2026. **The community project is shipping faster and further than the Red Hat build.**
- **The real risks are smallness, not damage.** 924 stars, 621 forks, 6,415 commits. Community images are built for *every commit to main*, which is a sign of an unhurried but small CI. Three majors in three years (2.x → 3.0 → 3.3). **CNCF Sandbox is the lowest foundation maturity tier** — it means "we host it, the project governs itself," not "a large vendor depends on it."
- **What the licence permits:** Apache-2.0, full stop. And Apicurio Registry v2+ implements the **Confluent Schema Registry v7 and v8 REST APIs**, so Confluent client libraries use it as a drop-in replacement [Apicurio Registry User Guide, "Compatibility with other schema registry REST APIs"]. That is unusually good vendor-neutrality for a schema registry and it is the main reason to pick it.
- **Verdict: PASS-WITH-CAUTION.** L1 satisfied (CNCF Sandbox). L2 is the weak leg — funding flows through an OpenShift-only commercial product. L3 satisfied and improving. **No Red Hat priority shift has damaged either project. Both left Red Hat's governance in time.**

---

## 6. Which components should be treated as replaceable, and what does it cost?

Cost is expressed in **engineer-days** for a single competent engineer on our specific stack, including re-testing the paths the JD cares about (partitioning, compaction, state tuning, data-quality checks, alerting).

| Component | Replaceable? | Replacement cost | Why it costs what it costs | Isolation to build now |
|---|---|---|---|---|
| **Apache Iceberg** | **No** | n/a (effectively unbounded) | It is the storage contract. Flink, Spark, ClickHouse, Polaris and Dagster all hold references to Iceberg table metadata. Leaving means migrating the table format itself, not the tooling. | Non-negotiable core. |
| **Apache Kafka** | **No** | 30–60 d | Debezium sink config, Kafka Connect runtime, Flink sources/sinks, schema-registry integration, consumer groups, exactly-once semantics, partition strategy — all of it is Kafka-shaped. There is no Iceberg-flavoured substitute with equivalent semantics. | Treat as fixed. Design the topic/contract boundary as the abstraction. |
| **Grafana** | **Yes** | **2–5 d now, 25–40 d later** | Dashboards are the only asset, and Perses has **no Grafana-dashboard import path** — every panel is re-authored. Cheap today because we have almost no dashboards; expensive once we do. | **Dashboards as code in Git, not as objects in a Grafana DB.** Highest-value, zero-cost action in this entire report. |
| **Dagster** | **Yes** | **15–30 d** | The asset-oriented model (`@asset`, partitions, asset checks, lineage emission) *is* the value; Airflow/Prefect/Argo all require a rewrite of every asset definition, not a config change. Mitigated by Apache-2.0 — a fork is always available. | Emit **OpenLineage** events from Dagster rather than relying on Dagster's own lineage UI. That makes the lineage asset portable even if Dagster is not. |
| **Debezium** | **Yes** | **10–20 d** | Replacement is slot-based and connector-specific: source-connector config, schema history (which is Debezium-proprietary state), snapshot strategy, and the exact envelope format on the topic. Consumers downstream will notice any envelope change. | Pin the schema-history topic. Keep the CDC envelope documented in the repo. |
| **ClickHouse** | **Yes** | **8–20 d** | The cost is concentrated in the serving layer: SQL dialect, table-engine choice, and the ingestion path. Iceberg-on-ClickHouse is well-trodden; the alternatives (Trino over Iceberg, StarRocks, DuckDB for local, Druid/Pinot for real-time OLAP) each require re-tuning physical layout. | Keep gold-layer **SQL close to ANSI**; avoid ClickHouse-specific functions outside the serving layer. |
| **Object store (RustFS / SeaweedFS / Garage / Ozone / Ceph)** | **Yes, cheaply by design** | **1–3 d** | All speak S3. If every consumer goes through the S3 API and we avoid implementation-specific extensions, swapping is an endpoint change plus a data copy. **RustFS is byte-compatible with MinIO's on-disk format**, so a data migration is a volume copy, not a rewrite. | **Do not depend on non-S3 features.** Specifically: test versioned writes, conditional PUT (`If-Match`) on `metadata.json`, and LIST consistency — these are what Iceberg needs. |
| **Apache Polaris** | **Yes, cheaply by design** | **2–6 d** | It is an implementation of the Iceberg REST spec, so Flink/Spark/Trino change only a `uri` and credentials. **Lakekeeper** is the drop-in fallback (Apache-2.0, Rust, OpenFGA, Postgres). Cost is low *only if* we never build on Polaris-proprietary admin APIs. | Talk to it only via the REST spec. Keep catalog state in Postgres. |
| **Helm** | **Yes** | **2–5 d** | Charts are the asset. Helm 3→4 changes the chart API/schema. Our exposure is small because we have no cluster — we render templates locally. | Keep rendered manifests in Git as the artefact; treat charts as a convenience. |
| **Apicurio Registry** | **Yes** | **0.5–2 d** | It implements the **Confluent Schema Registry v7 and v8 REST APIs**, so Confluent clients treat it as a drop-in replacement. Lowest swap cost in the stack. | Use the standard Confluent-compatible client config, not Apicurio-specific endpoints. |
| **Prometheus + Alertmanager** | **Yes** | **< 1 d** | Scraping is pure configuration; alerts are YAML. Nothing in the data plane references them. | Keep alert rules in Git (they will be anyway). |
| **OpenLineage** | **Yes** | **1–3 d** | The *spec* is the asset and it is a foundation standard. Marquez, DataHub and OpenMetadata all consume it. | Emit the spec, not the backend. |
| **PostgreSQL** | **Yes** | **2–5 d** | Migrating Polaris/Dagster/Apicurio metadata off Postgres is a real but bounded job; several of them support alternatives. | Keep it a boring, plain Postgres 18. |
| **OpenTofu** | **Yes** | **< 1 d** | HCL is the lingua franca; the OpenTofu/Terraform state and provider ecosystems are compatible by design. | This *is* the replacement for the failed Terraform. |
| **Podman** | **Yes** | **< 1 d** | Docker-CLI-compatible. | Also: **upgrade 5.7 → 6.1.x now.** 5.7 has been EOL since 12 Feb 2026. |

**The two things that are not replaceable are Iceberg and Kafka.** Everything else is bounded work, and the two most important isolation moves — dashboards as code in Git, and OpenLineage emitted from Dagster — cost essentially nothing today and are what make the "replaceable" claims real rather than theoretical.

---

## 7. Source log

All URLs accessed **2026-09-27** unless the item carries its own date.

| ID | Source | Date on source |
|---|---|---|
| S0 | github.com/minio/minio — archive banner + README | archived 25 Apr 2026 |
| S0b | github.com/minio/minio/security/advisories | 14 & 25 Apr 2026 |
| S0c | stormdevelopments.ca — MinIO community edition archived | 2 Jul 2026 |
| S1 | incubator.apache.org/projects/polaris.html | graduation 15 Feb 2026 |
| S2 | polaris.apache.org/blog/2026/02/19/apache-polaris-graduates-to-top-level-project | 19 Feb 2026 |
| S3 | polaris.apache.org/downloads | 1.7.0 = 2 Aug 2026 |
| S4 | release-catalog.apache.org/polaris | updated 22 Sep 2026 |
| S5 | globenewswire.com/news-release/2026/02/19/3240735 | 18 Feb 2026 |
| S6 | snowflake.com/en/blog/apache-polaris-top-level-project | 19 Feb 2026 |
| S7 | dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026 | 8 Jun 2026 |
| S8 | polaris.apache.org | site live at TLP domain |
| S9 | grafana.com/oss — project list, incl. OnCall OSS archive date | OnCall archived 24 Mar 2026 |
| S10 | github.com/grafana/grafana/blob/main/LICENSE, LICENSING.md, docs/sources/datasources/prometheus/_index.md | AGPL-3.0-only; prom ds review_date 4 Aug 2026 |
| S11 | grafana.com/legal/enterprise-plugins — "Grafana OSS … free of charge" | current |
| S12 | grafana.com/licensing — 20 Apr 2021 relicensing to AGPLv3 | 20 Apr 2021 |
| S13 | businesswire 20260421839174 — GrafanaCON 2026, Grafana 13, Logline acquisition | 21 Apr 2026 |
| S14 | grafana.com/blog/grafana-13-release-all-the-latest-features/ | 21 Apr 2026 |
| S15 | grafana.com/whats-new pages 2, 4, 5 — per-feature edition gating | May–Jun 2026 |
| S16 | cncf.io/projects/perses — Sandbox 29 Aug 2024, health 84, contributor/org growth | 25 Sep 2026 |
| S17 | n9e.github.io — Nightingale, Apache-2.0, CCF | 16 Sep 2026 |
| S18 | devezium.io/releases + /releases/3.6/release-notes | 3.6 GA 1 Jul 2026; 3.6.1 4 Aug 2026 |
| S19 | debezium.io/blog/2024/11/04/debezium-moving-to-commonhaus | 4 Nov 2024 |
| S20 | devezium.io/foundation/faq + /community/governance + /blog/2025/12/12 | 12 Dec 2025 |
| S21 | infoq.com/news/2025/02/debezium-joins-commonhaus; commonhaus.org/about | 3 Feb 2025; 27 Sep 2026 |
| S22 | access.redhat.com/errata/RHEA-2026:8348 — Red Hat build of Debezium 3.4.3 | 15 Apr 2026 |
| S23 | github.com/apicurio/apicurio-registry README — CNCF Sandbox | 27 Sep 2026 |
| S24 | linuxfoundation.org/press/announcing-opentofu — LF formation, BUSL context, 18-FTE/5-yr pledge | 20 Sep 2023 |
| S25 | endoflife.date/podman | updated 3 Sep 2026 |
| S26 | endoflife.date/docker-engine | updated 5 Sep 2026 |
| S27 | iceberg.apache.org + release-catalog.apache.org/iceberg | 1.11.0 = 15 May 2026; catalog 26 Sep 2026 |
| S28 | kafka.apache.org/43/getting-started/upgrade; /40/getting-started | KRaft-only, KIP-896 |
| S29 | releasealert.dev/github/apache/kafka; kafka.apache.org/blog/releases | 4.3.1 = 23 Jun 2026 |
| S30 | flink.apache.org/downloads; nightlies.apache.org/flink/flink-docs-stable/docs/deployment/java_compatibility | 2.3.0 = 25 Jun 2026 |
| S31 | nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/installation | Python 3.9–3.12 |
| S32 | pypi.org/project/apache-flink (2.3.0); endoflife.date/apache-flink | 2.3.0 |
| S33 | spark.apache.org/docs/latest — "Java 17/21/25 … 25.0.3 deprecated as of Spark 4.2.0" | 4.2.0 |
| S34 | spark.apache.org/docs/4.1.1 — "Java 17/21" | 4.1.1 |
| S35 | spark.apache.org/docs/latest/api/python/getting_started/install.html — PyPI install, Python 3.10+ | 4.2.0 |
| S36 | spark.apache.org/news — 4.2.0 / 4.1.3 / 4.0.4 / 3.5.9 | Jul 2026 |
| S37 | github.com/ClickHouse/ClickHouse/blob/master/LICENSE — Apache 2.0, 2016-2026 | 27 Sep 2026 |
| S38 | clickhouse.com/docs/resources/changelogs/oss/2026 — 26.8 LTS backward-incompatible changes | 27 Aug 2026 |
| S39 | clickhouse.com/blog/what-a-difference-10-years-of-open-source-makes | 16 Jun 2026 |
| S40 | clickhouse.com/blog/clickhouse-raises-400-million-series-d-acquires-langfuse-launches-postgres | 16 Jan 2026 |
| S41 | tracxn.com/companies/clickhouse — $1.05B, $15B, 623 employees | Jun 2026 |
| S42 | dagster.io/prefect — Prefect acquisition letter | 13 Jul 2026 |
| S43 | businesswire.com/news/home/20260713065285 | 13 Jul 2026 |
| S44 | github.com/dagster-io/dagster/blob/master/LICENSE — Apache 2.0; github.com/dagster-io | 27 Sep 2026 |
| S45 | pypi.org/project/dagster — 1.13.21, Requires-Python >=3.10,<3.15 | 3 Sep 2026 |
| S46 | apicur.io/blog/2026/06/16/registry-3.3.0-released | 16 Jun 2026 |
| S47 | access.redhat.com/articles/7014952 — Red Hat build 3.2 GA, OpenShift 4.16–4.20, OpenJDK 17/11 | 16 Jun 2026 |
| S48 | mvnrepository.com/artifact/io.apicurio — 3.3.3 | 9 Sep 2026 |
| S49 | openlineage.io/docs/1.46.0 — LF AI & Data Graduate; openlineage.io | current |
| S50 | pypi.org/project/openlineage-integration-common — 1.53.0, >=3.10, classifiers to 3.14 | 1 Sep 2026 |
| S51 | mvnrepository.com/artifact/io.openlineage — java/spark/flink/sql/hive at 23 Jul 2026 | 23 Jul 2026 |
| S52 | github.com/prometheus/prometheus/releases — 3.14.0, 3.13.3 | 17 Aug / 7 Sep 2026 |
| S53 | cncf.io/projects/prometheus — Graduated 9 Aug 2018 | 25 Sep 2026 |
| S54 | pkg.go.dev/github.com/prometheus/alertmanager — v0.34.1 | 17 Sep 2026 |
| S55 | github.com/helm/helm README — v3 support dates; helm.sh/blog/helm-4-released | 17 Nov 2025 |
| S56 | cncf.io/announcements/2025/11/12/helm-marks-10-years-with-release-of-version-4 | 12 Nov 2025 |
| S57 | opentofu.org/docs/v1.11/intro/whats-new; /v1.13/; status.opentofu.org | 1.12.0 released; status 5 Sep 2026 |
| S58 | postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365; /support/versioning; /docs/18/release-18.html | 13 Aug 2026; 18.0 = 25 Sep 2025 |
| S59 | github.com/seaweedfs/seaweedfs/releases — 4.45 | 31 Aug 2026 |
| S60 | github.com/seaweedfs/seaweedfs — Apache-2.0, Patreon, Iceberg support, MinIO/RustFS comparison | 27 Sep 2026 |
| S61 | rustfs.com — 1.0.0-beta.10, Apache-2.0; github.com/rustfs org listing | 17 Jul 2026; Sep 2026 |
| S62 | git.deuxfleurs.fr/Deuxfleurs/garage/releases — v2.3.0; hub.docker.com/r/dxflrs/garage — AGPLv3, Deuxfleurs | 16 Apr 2026 |
| S63 | release-catalog.apache.org/ozone; ozone.apache.org/download; github.com/apache/ozone | 2.2.1 = 27 Aug 2026; 2.1.2 = 18 Sep 2026 |
| S64 | dev.to/ethan-carter — S3 API coverage comparison (SeaweedFS ~60%, RustFS versioning) | 5 Aug 2026 |
| S65 | youngju.dev — MinIO timeline, OpenMaxIO fork stall, Garage/SeaweedFS status | 17 Jul 2026 |

---

## 8. What this changes in the plan

1. **Drop Terraform, adopt OpenTofu.** Terraform fails L1/L2 on a BUSL licence. OpenTofu is LF-governed, MPL-2.0, and a drop-in for HCL.
2. **Keep Polaris.** The "incubating" risk in the assignment is resolved — it is a TLP as of 15 Feb 2026 — but pin the minor version and reach it only through the Iceberg REST spec so Lakekeeper stays a same-day escape.
3. **Keep Grafana, but hold the dashboards in Git.** Grafana OSS is maintained and free. The hedge is cheap and is the thing that keeps the Grafana/Perses switch affordable.
4. **Treat Dagster as the weakest link in an otherwise strong stack**, not because of the licence (Apache-2.0, safe) but because its owner changed hands on 13 Jul 2026 and the consolidation is unfinished. Emit OpenLineage from Dagster so lineage outlives it.
5. **Pin JDK 17 and Python 3.12 in every image.** Java 26 and Python 3.14 are not viable for any engine here.
6. **Upgrade podman 5.7 → 6.1.x now.** 5.7 has been EOL since 12 Feb 2026; 5.8's support ends 26 Sep 2026.
7. **Object storage: do not commit data to RustFS yet.** It is the best-licensed option and probably the best S3 fidelity, but it is pre-1.0 (beta.10) with no disclosed funding. Test SeaweedFS or keep the S3 endpoint swappable. If Iceberg writes and conditional PUTs behave correctly, migration later is 1–3 days.
