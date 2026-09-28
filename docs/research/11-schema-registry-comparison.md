# 11 - Schema registry comparison and recommendation

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** the schema-registry slot in the vendor-neutral lakehouse platform. Candidates compared: Apicurio Registry 3.x, Confluent Schema Registry, Karapace, Redpanda Schema Registry, AWS Glue Schema Registry, and "no registry at all".
**Question answered:** which schema registry, if any, should the platform use?

This is primary-source research. Every licence, release date, API claim and integration claim below is traced to the source that owns it (the project's own LICENSE, README, docs, ADR, source tree, or release API). No secondary blog is the deciding source. Nothing here is a measured benchmark unless it is explicitly labelled as a figure the vendor itself published, and every such figure is attributed.

---

## 0. Method, the rubric, and three corrections to the brief

### 0.1 The rubric applied

The standing support-and-longevity rubric, read as three legs that must all hold:

| Leg | Test | How it was judged here |
|---|---|---|
| **L1 - governance** | Foundation, company, or individual steward; named | The project's own governance page, foundation listing, or vendor legal entity |
| **L2 - backing and incentive** | Foundation, or a company with disclosed funding *and* a commercial reason for the OSS core to stay healthy | Funding evidence, foundation membership, vendor revenue model |
| **L3 - observable activity (hard floor)** | Not archived, not maintenance-only; releases and commits in the last ~12 months | GitHub repository metadata, release API, commit API |

### 0.2 Corrections to the brief, stated up front

Three premises in the task brief do not survive contact with the primary sources. They are corrected here and then used consistently below.

**Correction 1 - the target job posting does not name a schema registry at all.** The cached posting ([S34]) lists, under ingestion and streaming, "Debezium CDC -> Apache Kafka" and names no registry, no Avro, and no schema-compatibility tool. Its governance line is "catalog organization, access control, data lineage, retention/compliance, and automated data-quality checks", and its governance nice-to-have is "OpenLineage/Marquez, Great Expectations, dbt tests, catalog-based access control". So the honest answer to "which JD requirement does a registry demonstrate" is: **none by name**. A registry is justified, if at all, by the *data-contracts and schema-compatibility* requirement the platform has adopted for itself (map issue #9, ticket #15, M9 and M17), not by a line in the posting. A registry is therefore a platform choice, not a JD compliance item, and it must earn its place on merit.

**Correction 2 - Apicurio's Confluent compatibility is v7 and v8, not v6.** The brief and the prior audit ([S] 03-longevity-audit section 3.9) both say "v6". Apicurio's own documentation says "Confluent Schema Registry API v7" ([S5]), and its own accepted ADR dated **2026-05-09** states: "The compatibility layer exposes the Confluent v7 and v8 REST API at `/apis/ccompat/v7/` and `/apis/ccompat/v8/`" ([S7]). Both are marked "Fully supported" in the shipped docs ([S8]). Use v7/v8, not v6.

**Correction 3 - Karapace's "Apache-2.0 exit" claim is verified on licence, but it is not a foundation project.** The map records Karapace as "the Apache-2.0 exit" with no research behind it ([S36]). The licence claim is **true**: `Aiven-Open/karapace` ships an Apache License 2.0 `LICENSE` ([S16]) and the package metadata declares the "Apache Software License" classifier ([S21]). But Karapace is a single-company project under the Aiven-Open organisation ([S18], [S20]), so its L1 is company governance, not foundation governance. The claim survives as an *exit*; it does not survive as a *foundation-grade primary*. See section 2c.

---

## 1. Verdict summary

| Option | L1 governance | L2 backing and incentive | L3 activity | Local-first fit | Confluent API compatibility | Verdict |
|---|---|---|---|---|---|---|
| **Apicurio Registry 3.x** | **CNCF Sandbox**, LF Projects LLC ([S2]) | Weak leg: no funding vehicle of its own; funded via Red Hat's commercial build, which is OpenShift-only ([S2], prior audit [S] 03) | Pass: 3.3.3 on 2026-09-08; >=100 commits in 12 months; not archived ([S3], [S4]) | Pass: single Quarkus container; in-memory, SQL/Postgres and KafkaSQL storage ([S2], [S9]) | **v7 and v8, "Fully supported"**; harness 52/53 = 98% (vendor-published) ([S7], [S8]) | **RECOMMENDED (primary)** |
| **Karapace** | Company (Aiven) ([S18], [S20]) | Aiven is a funded commercial Kafka vendor; Karapace is part of its Kafka product ([S20], [S35 secondary]) | Pass: 6.2.3 on 2026-09-15; >=100 commits in 12 months; not archived ([S18], [S19]) | Pass: Python/aiohttp, "moderate memory"; needs Kafka ([S17]) | Confluent SR **6.1.1** level, "all operations", with stated caveats ([S17]) | **Verified exit (secondary)** |
| **Confluent Schema Registry** | Company (Confluent, Inc.), no foundation ([S11], [S12]) | Public company, clear incentive | Pass: tags v64.7.7.2-2; not archived; pushed 2026-09-28 ([S14], [S15]) | Pass technically (JVM), but see licence | It *is* the reference API | **REJECTED - licence** |
| **Redpanda Schema Registry** | Company (Redpanda Data, Inc.) ([S22], [S23]) | Funded company | Pass ([S29]) | Not a standalone service: **built into the broker**; adopting it means adopting Redpanda as the Kafka broker ([S25]) | Confluent-compatible serializers/endpoints, with enterprise-only ACLs ([S26], [S27]) | **REJECTED - broker lock-in and BSL** |
| **AWS Glue Schema Registry** | Company (Amazon); proprietary managed service ([S30]) | Commercial incentive to keep it alive | N/A (SaaS) | **Fail: serverless AWS service, cannot run on podman** ([S30]) | Its own API, not the Confluent REST API ([S30]) | **REJECTED - cannot run locally** |
| **No registry** | N/A | N/A | N/A | Trivially fits | N/A | **REJECTED - loses the evidence ticket #15 needs** |

---

## 2. Per-option detail

### 2a. Apicurio Registry 3.x - RECOMMENDED

**Licence.** Apache License 2.0. The repository `LICENSE` is the unmodified Apache 2.0 text ([S1]); the GitHub licence classifier reports `Apache-2.0` ([S3]). No relicensing history was found.

**Governance (L1).** Foundation. The README states: "Apicurio Registry is a [Cloud Native Computing Foundation](https://cncf.io) Sandbox project", with "Copyright Apicurio Registry a Series of LF Projects, LLC", a CNCF Slack channel and `cncf-apicurio-registry-*` mailing lists ([S2]). CNCF Sandbox is early maturity (not Incubating, not Graduated), which is the honest limit of the L1 claim, but it is genuine foundation governance.

**Backing and incentive (L2) - the weak leg.** The community project has no funding vehicle of its own. Funding flows through Red Hat's commercial "Red Hat build of Apicurio Registry", which the prior audit already established is narrowed to OpenShift (4.16-4.20 and the AWS/Azure OpenShift services) on OpenJDK 11/17, and lags the community build by one minor ([S] 03-longevity-audit section 3.9, citing Red Hat article 7014952). The community project is small: 939 stars, 747 open issues ([S3]). This leg passes only in the sense that a commercial entity has an incentive for the core to stay healthy; it is the weakest of the three and should be stated as such in the ADR.

**Activity (L3).** Pass, comfortably. Not archived, not disabled; last push 2026-09-27 ([S3]). Releases: **3.3.3 on 2026-09-08**, 3.3.2 on 2026-08-27, 3.3.1 on 2026-07-27, 3.3.0 on 2026-06-08, 3.2.6 on 2026-07-03 ([S4]). The commit API returns the full 100-item page for commits since 2025-09-28 (the query cap), so there are at least 100 commits in the trailing 12 months ([S3] metadata plus commit query). The README also documents a real support policy: the two most recent minors get patch releases, older minors are end-of-life ([S2]).

**Confluent Schema Registry API compatibility - and how complete it is.** This is the load-bearing technical question, and Apicurio answers it in primary sources at two levels.

- The 3.0.x product docs state: "Apicurio Registry also provides compatibility with the following schema registries by including implementations of their respective REST APIs: ... **Confluent Schema Registry API v7**" and "Applications using Confluent client libraries can use Apicurio Registry as a drop-in replacement." ([S5]). The docs also list Apicurio's own Core Registry API v3 and v2 among the compatible APIs ([S5], [S8]).
- The shipped compatibility reference lists exactly what is and is not supported ([S8]). **Fully supported API endpoints:** Schemas API (`GET /schemas`, `/schemas/ids/{id}`, `/schemas/types`, `/schemas/ids/{id}/subjects`, `/schemas/ids/{id}/versions`, `/schemas/ids/{id}/schema`, with pagination); Subjects API (full CRUD, lookup by content, lookup by version, deletion, pagination); Compatibility API (against a version or all versions, `verbose` and `normalize` parameters, default `BACKWARD` matching Confluent); Config API (global and subject-level, `defaultToGlobal`); Mode API (`READWRITE`, `READONLY`, `READONLY_OVERRIDE`, `IMPORT`); Contexts API (static default context). **Supported schema types:** Avro, JSON Schema and Protobuf, all "Fully supported".
- **Unsupported features, named by the project itself ([S8]):** Schema Linking / Exporters (`GET /exporters` returns an empty list; other exporter operations error); KEKs (Key Encryption Keys) and DEKs (Data Encryption Keys) endpoints are absent (404); the Cluster Metadata API (`/v1/metadata/id`, `/v1/metadata/config`) is absent; and Data Contracts metadata/rules sent through the ccompat API are accepted but **not enforced or stored**. For contract metadata and rulesets, Apicurio directs users to its **native Data Contracts feature** (`apicurio.contracts.enabled=true`), with `contract/metadata` and `contract/ruleset` REST APIs.
- **Behavioural differences to expect ([S8]):** the `PUT /config` response uses the field name `compatibility` rather than `compatibilityLevel`; Avro schemas are returned as compact single-line JSON; the compatibility check endpoint defaults to `BACKWARD` when no rule is configured; schema IDs map to Apicurio `contentId` by default (identical content returns the same ID, matching Confluent), controllable via `apicurio.ccompat.legacy-id-mode.enabled`.
- **A vendor-published completeness figure, clearly attributed.** Apicurio's accepted ADR (dated **2026-05-09**) records that its own "Apicurio Compatibility Harness" runs the same requests against both Confluent and Apicurio and compares responses, and that coverage went from "26 of 53 tests passed (49%)" before the change to "52 of 53 pass (98%)" after ([S7]). **This is a vendor-published, self-run figure, not an independent measurement. I did not reproduce it.** It is cited because it is a dated, specific, first-party claim, and it should be presented that way in the ADR, not as an independent benchmark.

**Formats.** Apicurio is an API registry as well as a schema registry. Documented artifact types ([S6]): `AVRO`, `PROTOBUF`, `JSON` (JSON Schema), `OPENAPI`, `ASYNCAPI`, `WSDL`, `XSD`. The three that matter for this platform (Avro, Protobuf, JSON Schema) are fully supported through the ccompat layer ([S8]).

**Debezium integration.** Documented by Debezium itself. Debezium's Avro configuration page states that to use Avro serialization "you must deploy a schema registry", and lists the available options as "the [Apicurio Registry] as well as the Confluent Schema Registry. Both are described here." ([S31]). It documents Apicurio's Kafka Connect converters (`io.apicurio.registry.utils.converter.AvroConverter`), the `apicurio.registry.url` setting, and an **Apicurio Confluent compatibility mode** enabled with `as-confluent: true` that serialises "using the same wire format as Confluent Schema Registry (including the magic byte and 4-byte schema ID)", making Apicurio "a drop-in replacement without requiring changes to producers or consumers" ([S31]). This is a first-party Debezium statement, not a vendor claim.

**Flink integration.** Flink's Kafka connector documents a "Confluent Avro" format among its formats ([S32]), which is served by the `flink-avro-confluent-registry` module and expects a Confluent-compatible registry. Because Apicurio exposes the Confluent v7/v8 API ([S7], [S8]), it can back that format. **Important nuance for this platform:** the platform's chosen CDC path is Flink's `debezium-json` format, which needs no registry at all (prior research [S] 06-iceberg-flink-sink-write-modes section 6.2). So the registry's Flink relevance is conditional: it matters only if the platform elects the `avro-confluent` wire format. The registry is needed unconditionally by the Debezium (Kafka Connect) producer side and by any Kafka client using Avro/Protobuf SerDes.

**Operational footprint for local podman.** Apicurio is a Quarkus (JVM) service. The shipped in-memory compose example is a single container, `apicurio/apicurio-registry`, exposing port 8080, with no external database ([S9]). Storage options documented in the tree: **in-memory** ("the simplest persistence option", which "uses RAM to store the data"; the operator defaults to it and states it "is not suitable for production"), **SQL** (`apicurio.storage.kind=sql`, the config default, with H2 or PostgreSQL), **KafkaSQL** (Kafka Streams-backed), and an experimental **GitOps** store that loads from Git into in-memory ([S2], [S9], [S10]). For this host, the single container plus in-memory (smoke profile) or SQL on the **existing PostgreSQL** (persistent profile, no new datastore) both fit the 12-CPU / ~7-8 GB envelope. **I did not measure the container's resident memory; no number is claimed.**

**Vendor-neutrality.** Strong. Apache-2.0, CNCF-governed, and multi-API by design: it implements its own Core Registry API alongside the Confluent v7/v8 API and other compatible APIs ([S5], [S8]). The migration path *away* is also first-party: an export utility exists to move from Confluent to Apicurio, and Apicurio documents its own import/export API for the reverse direction ([S8]).

**JD requirement demonstrated.** None by name (correction 1). It evidences the platform's own governance and data-contract requirements: a central schema store with compatibility rules, version history, and (via its native Data Contracts feature) contract metadata and rulesets. It is the mechanism by which ticket #15's "registry-side version change" is captured.

### 2b. Confluent Schema Registry - REJECTED on licence

**Licence, stated precisely.** The repository `LICENSE` reads: "The project is licensed under the Confluent Community License, except some modules such as the client-* and avro-* libs, which are licensed under the Apache 2.0 license." ([S11]). The Confluent Community License Version 1.0 grants use, modification and distribution but **not** for an "Excluded Purpose", defined as "making available any software-as-a-service, platform-as-a-service, infrastructure-as-a-service or other similar online service that competes with Confluent products or services that provide the Software" ([S12]). The licence text is headed "Copyright (c) Confluent, Inc. 2014-2026" ([S12]).

**It is not OSI-approved.** It does not appear on the Open Source Initiative's approved-licences list; the only `BSL-1.0` entry there is the Boost Software License, an unrelated licence ([S33]). Confluent Community License is a **source-available** licence, not an open-source one. This is the material fact: the platform is explicitly vendor-neutral, and adopting the reference implementation of the Confluent API under a licence that forbids competing hosted offerings and is not OSI-approved is the opposite of the stated goal.

**Governance and activity.** Company (Confluent, Inc.), no foundation ([S11], [S12]). Activity passes: the repository is not archived and was pushed on 2026-09-28 ([S14]); recent tags are `v64.7.7.2-2`, `v64.7.7.2-1`, `v53.7.7.3-1` ([S15]). Longevity is not the problem; licence and neutrality are.

**Formats and API.** It is the reference: "A REST service for validating, storing, and retrieving Avro, JSON Schema, and Protobuf schemas", with Kafka SerDes for all three ([S13]). Its own API is the one everyone else implements.

**Why rejected.** A component can pass L2 and L3 and still be the wrong choice. Here L1 is a proprietary, non-OSI licence with an explicit non-compete restriction, which fails the platform's vendor-neutrality premise and its "open" expectation even though the rubric's literal wording ("company-backed with disclosed funding and a commercial incentive acceptable") might let it through. The recommendation is to reject it on licence and neutrality, not on longevity, and to say so in the ADR.

### 2c. Karapace - VERIFIED EXIT, not the primary

**Licence.** Apache License 2.0 ([S16]); the package declares the "Apache Software License" classifier ([S21]). The map's "Apache-2.0 exit" claim is **verified**.

**Governance and backing (L1/L2).** Single-company. The project lives in the `Aiven-Open` GitHub organisation; karapace.io is footed "Copyright (c) 2026 Aiven" and describes Karapace as "actively developed by some of the biggest Apache Kafka service providers around" ([S18], [S20]). Aiven is a commercial managed-Kafka vendor, so there is a clear commercial incentive for Karapace to stay healthy as part of its Kafka product ([S20]). **Honest limitation:** I did not read a first-party Aiven funding announcement in this pass. Third-party trackers report roughly $420M raised and a ~$3B valuation ([S35]), but those are secondary sources and are flagged as such. L1 is company governance, which is weaker than Apicurio's CNCF leg.

**Activity (L3).** Pass. Not archived; last push 2026-09-25; 637 stars; 94 open issues ([S18]). Releases: **6.2.3 on 2026-09-15**, 6.2.2 on 2026-08-05, 6.2.1 on 2026-07-17, 6.2.0 on 2026-06-05, 6.1.4 on 2026-04-20 ([S19]). At least 100 commits in the trailing 12 months (commit query capped at 100) ([S18]). One documentation defect worth noting: the in-repo `NEWS` changelog stops at 2.0.1 (2020-07-06) ([S? Karapace NEWS]), so the changelog is not maintained even though releases are active; judge activity by the release API, not by `NEWS`.

**Confluent API compatibility.** The README states: "Karapace is compatible with Schema Registry 6.1.1 on API level. When a new version of SR is released, the goal is to support it in a reasonable time. **Karapace supports all operations in the API.**" It then names the caveats honestly: "some caveats regarding the schema normalization, and the error messages being the same as in Schema Registry, which cannot be always fully guaranteed." ([S17]). So it claims full operation coverage against the **Confluent SR 6.1.1** level, which is a specific, older reference point than Apicurio's v7/v8.

**Formats and integrations.** Supports "Avro, JSON Schema, and Protobuf" ([S17]). It is a drop-in on "pre-existing Schema Registry / Kafka Rest Proxy client and server-sides" ([S17]). Debezium does **not** document Karapace as a supported registry; Debezium's Avro page names only Apicurio and Confluent ([S31]). Because Karapace is Confluent-API-compatible, Debezium's Confluent converter should work, but that is an inference, not a documented Debezium statement, and should be labelled as such.

**Footprint.** Python/aiohttp, "moderate memory consumption", leader/replica for HA, needs a Kafka connection ([S17]). Lighter than a JVM registry in principle. **No memory number measured.**

**Why not primary.** It is a legitimate Apache-2.0 exit and it passes the rubric, but it loses to Apicurio on the two things this platform weights: foundation governance (CNCF vs single company) and API breadth (Confluent v7/v8 plus Apicurio's own v3 API and native Data Contracts feature, vs Confluent SR 6.1.1 level only). Keep it documented as the exit; do not make it the primary.

### 2d. Redpanda Schema Registry - REJECTED on broker lock-in and licence

**Licence.** Not Apache-2.0. Redpanda's own licences directory documents two licences: the core is under the **Redpanda Business Source License 1.1** ("BSL 1.1", licensor Redpanda Data, Inc., with an Additional Use Grant barring use for a "Streaming or Queuing Service", a Change Date four years from release, and a Change License of Apache 2.0), and enterprise features are under the **Redpanda Community License (RCL)** ([S22], [S23], [S24]). The repository's GitHub licence classifier reports no OSI licence ([S29]). This is source-available, not open source.

**It is not a standalone registry.** Redpanda's own docs are explicit: "The Schema Registry is built directly into the Redpanda binary. It runs out of the box with Redpanda's default configuration, and it requires no new binaries to install and no new services to deploy or maintain." ([S25]). It stores schemas in an internal `_schemas` topic and serves on port 8081 ([S25]). The practical consequence is decisive for this platform: **adopting Redpanda Schema Registry means adopting Redpanda as the Kafka broker**, replacing Apache Kafka. That is broker-level lock-in and a large architectural change to a platform whose stated premise is vendor-neutrality and whose Kafka is already an ASF TLP component.

**Editions.** Core registry features are in the BSL Community Edition, but Redpanda's own licensing table lists **Schema Registry Authorization** (ACLs) and **Server-Side Schema ID Validation** as **enterprise** features requiring a licence key ([S28]); the schema-registry authorization page carries the enterprise-licence banner ([S27]).

**Formats and API.** Supports "Avro, Protobuf, and JSON serialization formats" with normalization for all three ([S25]); it is Confluent-compatible at the serializer and endpoint level (its examples use the `confluent-kafka` Python client and endpoints such as `POST /subjects/{subject}/versions` and `/compatibility/subjects/{subject}/versions/{version}`) ([S26]).

**Why rejected.** Two independent disqualifiers: (i) it cannot be adopted without replacing the broker, which is lock-in the platform has ruled out; (ii) the licence is BSL/RCL, not OSI-approved, failing the same neutrality test as Confluent. Longevity is not the issue.

### 2e. AWS Glue Schema Registry - REJECTED, cannot run locally

**Nature and licence.** A proprietary, fully managed AWS service. Its own docs state: "The Schema registry is serverless and free to use." ([S30]). There is no self-hosted or on-premises deployment and no OCI image; it cannot run on this podman host. This alone fails the operational envelope, which is a hard requirement.

**Formats and integrations.** Supports Avro (v1.11.4), JSON Schema (Draft-04, Draft-06, Draft-07) and Protobuf (proto2/proto3), with compatibility modes and IAM integration, and first-party integrations with Apache Kafka, Amazon MSK, Kinesis Data Streams, Amazon Managed Service for Apache Flink and AWS Lambda ([S30]). It exposes **its own** API, not the Confluent Schema Registry REST API ([S30]).

**Why rejected.** It cannot run locally, so it cannot be part of a local-first platform, and it is AWS-specific, so it is the strongest available expression of the vendor lock-in the platform exists to avoid. It is also the wrong shape for a portfolio whose whole premise is a runnable local lakehouse.

### 2f. No registry at all - REJECTED, but note the cost honestly

**Is it technically feasible?** Yes, for the wire formats this platform has chosen. Debezium can run with JSON and inline schemas rather than a registry, and the platform's Flink CDC path uses `debezium-json`, which needs no registry (prior research [S] 06 section 6.2). A registry is not required to move bytes.

**What is lost.** Without a registry there is no central schema store, no version history, no server-side compatibility enforcement, and no artifact to point at when the platform claims a data-contract and schema-compatibility policy. Ticket #15 explicitly requires "the registry-side version change, captured with evidence" and a "genuinely validated schema-evolution demonstration, where a column is added, written, read and dropped, with the registry-side version change captured" ([S36]). "No registry" would force that ticket to either invent an equivalent or drop the evidence. It also weakens the governance story the platform has chosen to tell (M9 data contracts, M17 schema-evolution matrix).

**Why rejected.** The platform has already committed to a data-contract and schema-compatibility requirement for its own reasons. A registry is the cheapest credible way to evidence it, and the leading candidate runs as a single local container. Dropping the registry would remove demonstrable governance depth for no operational gain.

---

## 3. Cross-cutting comparison

| Dimension | Apicurio 3.x | Karapace | Confluent SR | Redpanda SR | Glue SR |
|---|---|---|---|---|---|
| Licence | Apache-2.0 | Apache-2.0 | Confluent Community License (not OSI) | BSL 1.1 + RCL (not OSI) | Proprietary AWS |
| Steward | CNCF Sandbox (LF Projects) | Aiven | Confluent, Inc. | Redpanda Data, Inc. | Amazon |
| Latest release (as read) | 3.3.3, 2026-09-08 | 6.2.3, 2026-09-15 | tag v64.7.7.2-2 | v26.2.2, 2026-08-22 | SaaS |
| Confluent API | v7 and v8, "Fully supported" | SR 6.1.1 level, "all operations" | reference | Confluent-compatible | its own API |
| Avro / Protobuf / JSON Schema | yes / yes / yes | yes / yes / yes | yes / yes / yes | yes / yes / yes | yes / yes / yes |
| Debezium-documented | yes ([S31]) | no (inferred) | yes ([S31]) | no (inferred) | yes (via AWS SerDe) |
| Flink | via `avro-confluent` (conditional) | via `avro-confluent` (conditional) | via `avro-confluent` | via `avro-confluent` | Managed Flink only |
| Runs on local podman | yes, single container | yes, needs Kafka | yes, needs Kafka | only as part of the broker | no |
| Vendor-neutral | strong | good | weak | weak (broker lock-in) | none |
| Native data-contract feature | yes | no | enterprise | no | no |

---

## 4. Recommendation

**Keep a schema registry, and make Apicurio Registry 3.x the primary, with Karapace recorded and evidenced as the Apache-2.0 exit.**

Concretely:

1. **Adopt Apicurio Registry 3.x** (pin a 3.3.x release; 3.3.3 as read). It is the only candidate that satisfies all three rubric legs, runs as a single local container, is Apache-2.0 under foundation governance, and implements the Confluent v7/v8 API plus its own Core Registry API and a native Data Contracts feature.
2. **Point Confluent-compatible clients at the ccompat endpoint** `/apis/ccompat/v7` ([S8]). This covers the Debezium Kafka Connect converters (using Apicurio's converters directly, or the `as-confluent` mode) and any Kafka client using Avro/Protobuf SerDes. Use Apicurio's native v3 API for registry administration and for the data-contract metadata that ticket #15 wants.
3. **Storage profile.** In-memory for the smoke profile (single container, no datastore). For the persistent profile, use SQL on the **existing PostgreSQL** (`apicurio.storage.kind=sql`) so no new datastore is introduced; KafkaSQL is the alternative that reuses the existing Kafka. Record that Apicurio itself calls in-memory "not suitable for production" ([S10]).
4. **Record the weak leg honestly in the ADR.** Apicurio's L2 is the weak leg: no funding vehicle of its own, and the Red Hat commercial build is OpenShift-only and one minor behind. The mitigation is already cheap: the exit to Karapace is a URL change for Confluent-compatible clients, and Apicurio ships an import/export API for migration ([S8]).
5. **Record the ccompat gaps.** Schema Linking/Exporters, KEK/DEK, Cluster Metadata, and ccompat-level Data Contract rule enforcement are unsupported ([S8]). None of these is required by this platform. The one that is adjacent to a platform requirement (contract metadata and rulesets) is covered by Apicurio's native Data Contracts feature, not by ccompat.
6. **Do not claim a JD requirement for the registry.** State plainly that the posting names no schema registry, and that the registry exists to evidence the platform's own data-contract and schema-compatibility requirement.

### Rejected alternatives, named

- **Confluent Schema Registry** - rejected on licence: Confluent Community License v1.0 is source-available, not OSI-approved, and carries a non-compete "Excluded Purpose" restriction ([S11], [S12], [S33]). Longevity is fine; neutrality is not.
- **Redpanda Schema Registry** - rejected on broker lock-in (it is built into the broker, so adopting it means replacing Apache Kafka) and on licence (BSL 1.1 / RCL, not OSI) ([S22]-[S25]).
- **AWS Glue Schema Registry** - rejected because it is a serverless AWS service that cannot run locally, and because it is AWS-specific lock-in ([S30]).
- **No registry** - rejected because it removes the schema-versioning and compatibility evidence that ticket #15 and the platform's own data-contract requirement depend on ([S36]).
- **Karapace** - not rejected; it is the verified Apache-2.0 exit, ranked second because its governance is a single company rather than a foundation and its Confluent API target is the older SR 6.1.1 level ([S17], [S18], [S20]).

---

## 5. What this changes in the plan

1. **Ratify the Apicurio 3.x slot in the technology-selection matrix**, but on researched grounds, not on the map's unsupported assertion. The prior audit already passed it with caution; this research confirms the pass and supplies the evidence.
2. **Correct the recorded API version.** Anywhere the proposal says Apicurio implements "the Confluent Schema Registry v6 API", change it to **v7 and v8** ([S5], [S7], [S8]). The v6 wording in the prior audit ([S] 03 section 3.9) and in the ticket brief is wrong.
3. **Upgrade the map's Karapace note from assertion to evidence.** The "Apache-2.0 exit" claim is verified ([S16]), and the exit should additionally record that Karapace is Aiven-governed and targets Confluent SR 6.1.1 compatibility ([S17], [S20]).
4. **Feed ticket #15.** Its point 5 ("The registry-side version change, captured with evidence") is now backed by a ratified component and a concrete endpoint: register a schema version, add an optional column, write, read, and drop, capturing the registry-side version change through the ccompat v7 API. Ticket #15's assumption of Apicurio 3.x is **confirmed**, with the API version corrected.
5. **No change to the Flink plan.** The `debezium-json` CDC path needs no registry; the registry is required by the Debezium producer side and by Kafka SerDes clients, and is available to Flink only if the `avro-confluent` format is chosen.

---

## 6. Unverified and limitations

- **Apicurio's 52/53 (98%) compatibility-harness figure is vendor-published and self-run** ([S7]). It is not an independent measurement and was not reproduced here. It is cited as a dated first-party claim only.
- **No memory or CPU measurement was taken** for any candidate. The operational-fit judgements are structural (single container vs needs-Kafka vs needs-the-broker vs SaaS), not measured.
- **Karapace's funding is supported only by secondary trackers** ([S35]); no first-party Aiven funding announcement was read in this pass. Its L2 rests on Aiven being a commercial Kafka vendor with a product incentive ([S20]).
- **Debezium and Karapace / Redpanda are not documented integrations.** Debezium's Avro page names only Apicurio and Confluent ([S31]). That Karapace and Redpanda work with Debezium's Confluent converter is an inference from their Confluent API compatibility, labelled as such, not a documented statement.
- **Karapace's in-repo `NEWS` changelog is stale** (last entry 2.0.1, 2020-07-06); activity was judged from the GitHub release API instead ([S19]).
- **"Not OSI-approved" is established by absence** from the OSI approved-licences list ([S33]) plus the licence text's own restrictions ([S12]); it is not a statement OSI makes about these licences by name.

---

## Sources

All accessed 2026-09-28 unless a date is stated. "GitHub API" means the authenticated `gh api` REST calls made on 2026-09-28.

| Id | Source | Date / detail |
|---|---|---|
| S1 | `github.com/Apicurio/apicurio-registry/blob/main/LICENSE` | Apache License 2.0, unmodified |
| S2 | `github.com/Apicurio/apicurio-registry/blob/main/README.md` | "CNCF Sandbox project"; "Copyright Apicurio Registry a Series of LF Projects, LLC"; in-memory quick start; support policy (two most recent minors) |
| S3 | GitHub API, `repos/Apicurio/apicurio-registry` and commit query since 2025-09-28 | licence Apache-2.0; archived false; pushed 2026-09-27; 939 stars; 747 open issues; >=100 commits in 12 months |
| S4 | GitHub API, `repos/Apicurio/apicurio-registry/releases` | 3.3.3 = 2026-09-08; 3.3.2 = 2026-08-27; 3.3.1 = 2026-07-27; 3.3.0 = 2026-06-08; 3.2.6 = 2026-07-03 |
| S5 | `apicur.io/registry/docs/apicurio-registry/3.0.x/getting-started/assembly-intro-to-the-registry.html` | "Confluent Schema Registry API v7"; "drop-in replacement"; Core Registry API v3 and v2 |
| S6 | `apicur.io/registry/docs/apicurio-registry/3.0.x/getting-started/assembly-artifact-reference.html` | Artifact types ASYNCAPI, AVRO, JSON, OPENAPI, PROTOBUF, WSDL, XSD |
| S7 | `github.com/Apicurio/apicurio-registry/blob/main/adr/0001-confluent-schema-registry-compatibility.md` | ADR dated 2026-05-09; v7/v8 at `/apis/ccompat/v7` and `/v8`; harness 26/53 (49%) -> 52/53 (98%), vendor-run |
| S8 | `github.com/Apicurio/apicurio-registry/blob/main/docs/modules/ROOT/pages/getting-started/assembly-confluent-schema-registry-compatibility.adoc` | Supported endpoints; Avro/JSON Schema/Protobuf "Fully supported"; unsupported features (exporters, KEK/DEK, cluster metadata, ccompat data contracts); behavioural differences; native Data Contracts feature |
| S9 | `github.com/Apicurio/apicurio-registry/blob/main/distro/docker-compose/in-memory-no-auth/docker-compose.yml` | Single `apicurio/apicurio-registry` container on port 8080, no external DB |
| S10 | `.../operator/docs/modules/ROOT/partials/proc-persistence-mem.adoc` and `.../operator/model/.../StorageSpec.java` | In-memory "uses RAM"; "not suitable for production" |
| S11 | `github.com/confluentinc/schema-registry/blob/master/LICENSE` | "Confluent Community License, except some modules such as the client-* and avro-* libs, which are licensed under the Apache 2.0 license" |
| S12 | `confluent.io/confluent-community-license` | Confluent Community License v1.0; "Excluded Purpose" non-compete clause; Copyright 2014-2026 |
| S13 | `docs.confluent.io/platform/current/schema-registry/index.html` | REST service for Avro, JSON Schema, Protobuf; SerDes for all three |
| S14 | GitHub API, `repos/confluentinc/schema-registry` | not archived; pushed 2026-09-28; 2465 stars; 395 open issues; licence NOASSERTION |
| S15 | GitHub API, `repos/confluentinc/schema-registry/tags` | v64.7.7.2-2, v64.7.7.2-1, v53.7.7.3-1 |
| S16 | `github.com/Aiven-Open/karapace/blob/main/LICENSE` | Apache License 2.0 |
| S17 | `github.com/Aiven-Open/karapace/blob/main/README.rst` | "compatible with Schema Registry 6.1.1 on API level"; "supports all operations in the API"; caveats on normalization and error messages; Avro/JSON Schema/Protobuf; "moderate memory consumption" |
| S18 | GitHub API, `repos/Aiven-Open/karapace` and commit query since 2025-09-28 | licence Apache-2.0; archived false; pushed 2026-09-25; 637 stars; 94 open issues; >=100 commits in 12 months |
| S19 | GitHub API, `repos/Aiven-Open/karapace/releases` | 6.2.3 = 2026-09-15; 6.2.2 = 2026-08-05; 6.2.1 = 2026-07-17; 6.2.0 = 2026-06-05; 6.1.4 = 2026-04-20 |
| S20 | `karapace.io` | "free and Open Source drop-in replacement for Confluent Schema Registry and the Kafka REST Proxy"; "actively developed by some of the biggest Apache Kafka service providers"; "Copyright (c) 2026 Aiven" |
| S21 | `github.com/Aiven-Open/karapace/blob/main/pyproject.toml` | `requires-python >=3.12,<3.15`; classifier "License :: OSI Approved :: Apache Software License" |
| S22 | `github.com/redpanda-data/redpanda/blob/dev/licenses/bsl.md` | Redpanda Business Source License 1.1; licensor Redpanda Data, Inc.; Additional Use Grant bars "Streaming or Queuing Service"; Change Date 4 years; Change License Apache 2.0 |
| S23 | `github.com/redpanda-data/redpanda/blob/dev/licenses/rcl.md` | Redpanda Community License (enterprise features) |
| S24 | `github.com/redpanda-data/redpanda/blob/dev/licenses/README.md` | "There are 2 licenses for Redpanda. BSL covers our core and RCL ... which covers enterprise features." |
| S25 | `docs.redpanda.com/current/manage/schema-reg/schema-reg-overview.md` | "built directly into the Redpanda binary ... no new binaries ... no new services"; Avro/Protobuf/JSON; `_schemas` topic; port 8081; 128KB schema caution |
| S26 | `docs.redpanda.com/current/manage/schema-reg/schema-reg-api.md` | Confluent-compatible serializers and endpoints; `/subjects/{subject}/versions`, `/compatibility/subjects/{subject}/versions/{version}`, `/schemas/types` |
| S27 | `docs.redpanda.com/current/manage/schema-reg/schema-reg-authorization.md` | Schema Registry ACLs require an enterprise licence |
| S28 | `docs.redpanda.com/current/get-started/licensing/overview.md` | Community (BSL) vs Enterprise (RCL); "Schema Registry Authorization" and "Server-Side Schema ID Validation" listed as enterprise features |
| S29 | GitHub API, `repos/redpanda-data/redpanda` | licence none/BSL; not archived; pushed 2026-08-22; 12577 stars |
| S30 | `docs.aws.amazon.com/glue/latest/dg/schema-registry.html` | "serverless and free to use"; Avro v1.11.4, JSON Schema Draft-04/06/07, Protobuf proto2/proto3; integrations with Kafka/MSK/Kinesis/Managed Flink/Lambda; its own API |
| S31 | `github.com/debezium/debezium/blob/main/documentation/modules/ROOT/pages/configuration/avro.adoc` | Debezium lists Apicurio Registry and Confluent Schema Registry as the registry options; Apicurio converters; `as-confluent: true` Confluent wire-format mode |
| S32 | `nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/formats/overview/` | "Confluent Avro" listed among Flink formats |
| S33 | `opensource.org/licenses` | No Confluent Community License entry; the only `BSL-1.0` is the Boost Software License |
| S34 | `~/projects/career-ops/data/jd-cache/031.md` (ONL Biz Solutions, job 94703893) | No schema registry, Avro, or compatibility tool named |
| S35 | Third-party funding trackers (tracxn, getlatka, startupintros) | Aiven reported at ~$420M raised, ~$3B valuation. **Secondary; not independently verified.** |
| S36 | Repo issue tracker: map #9 body; ticket #15 body | Registry slot "filled by Apicurio 3.x on its CNCF Sandbox governance, with Karapace recorded as the Apache-2.0 exit"; ticket #15 requires the "registry-side version change, captured with evidence" |
