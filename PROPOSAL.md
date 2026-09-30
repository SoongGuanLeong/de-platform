# de-platform: research and architecture proposal

**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Status:** planning. No platform code exists. Nothing in this proposal was measured.

---

## 0. Read this first

This is a proposal, not a platform. Every number in it is a declared budget or an arithmetic result over documented defaults, and where a figure would need a running system to be true, the document that owns it says so and names the evidence that will produce it. The capability register at [`docs/completion-bar.yaml`](docs/completion-bar.yaml) ships empty, and that is its correct state rather than an unfinished task.

**The proposal in one paragraph.** Build a vendor-neutral lakehouse on two independent data spines: a **commerce spine** carrying TPC-C change data captured by Debezium from a live PostgreSQL and TPC-H SF100 for batch, and a **network spine** carrying the RIPE Atlas measurement stream and the UK ONSPD geography, with nothing joined across the two. Iceberg on SeaweedFS behind Polaris is the table layer, Kafka and Flink carry the stream, Spark carries the batch, ClickHouse serves, Dagster orchestrates, and a custom gated data-quality framework with OpenLineage and Marquez carries governance. Twenty components, of which only Iceberg and Kafka are irreplaceable. Every capability counts as finished only when it is a registered instance with a behaviour item behind it, so the proposal's claims are built to be checked rather than believed.

## 1. How to read this proposal

Two readers, two routes.

**Ten minutes.** Open [`README.md`](README.md), then read section 0 above, then three stops: [the requirements matrix](docs/requirements-matrix.md) section 4, [the technology selection](docs/technology-selection.md) section "The stack at a glance", and [the system architecture](docs/system-architecture.md) section 5.

**An hour.** Read this document top to bottom, then the suite in the order below. Each stop names what it settles and what it deliberately does not.

1. **The target.** [The requirements matrix](docs/requirements-matrix.md). The posting's requirements as 23 rows in the posting's own order, the evidence standard each row is judged by, the interview-facing ordering, and what is deliberately not done.
2. **The data.** [The dataset selection](docs/dataset-selection.md). Four sources, two spines, the sizes, the licences, and the candidates left out.
3. **The stack.** [The technology selection](docs/technology-selection.md). Twenty components, every candidate that was rejected and why, and the defence of the count.
4. **The architecture.** [The system architecture](docs/system-architecture.md), [the data architecture](docs/data-architecture.md), [the data-flow diagrams](docs/data-flow.md). The components and their planes, the gold inventory and its physical layout, and the three flows.
5. **The paths.** [The streaming job designs](docs/streaming-jobs.md), [the serving layer](docs/serving-layer.md), [governance and data quality](docs/governance-and-data-quality.md), [data contracts](docs/data-contracts.md), [the security model](docs/security-model.md).
6. **The evidence.** [The completion bar](docs/completion-bar.md), [the benchmark plan](docs/benchmark-plan.md), [the testing strategy](docs/testing-strategy.md), [the incident laboratory](docs/incident-laboratory.md). What makes a claim checkable, what may be measured, at what level, and what an incident must produce.
7. **The delivery.** [The repository decomposition](docs/repository-decomposition.md), [the local development architecture](docs/local-development.md), [the cloud architecture](docs/cloud-architecture.md), [the CI/CD strategy](docs/ci-cd-strategy.md), [the phased implementation roadmap](docs/implementation-roadmap.md).

**What is deliberately left out.** The ten-minute route carries no ADR, no budget and no measurement, because each needs the context its spec supplies. The suite carries no code walkthrough and no demo script: the walkthrough belongs to [the interview and demo narrative](https://github.com/SoongGuanLeong/de-platform/issues/29), issue #29, and the raw research reports under [`docs/research/`](docs/research/) are cited rather than reproduced. No document restates another's table; where two could claim a value, the owning document holds it and the other links.

Every architectural decision along the route is an ADR under [`docs/adr/`](docs/adr/). Section 9 is the index.

## 2. The problem

[The requirements matrix](docs/requirements-matrix.md) carries one row per discrete platform requirement in the posting's own order: seven key responsibilities, then the requirements, then the nice-to-haves, plus vendor neutrality, which the posting's About-the-role paragraph stakes out without enumerating it. Twenty-three rows, each with a claim, a platform component and the evidence that would settle it.

Four rows were re-specified rather than copied, because the posting's wording was unfalsifiable or false: **M2** ordering became convergence, **M3** exactly-once became exactly-once effect, **M7** "ClickHouse over Iceberg" became the materialised serving store, and **M10** "not bypassable" became two controls with a documented seam. [The requirements matrix](docs/requirements-matrix.md) section 6 records each correction.

## 3. The data

Four sources in two spines, and **nothing joins across them**. The commerce spine is TPC-C, whose change events are the only genuinely real CDC in any candidate dataset, and TPC-H SF100 for batch and serving. The network spine is the RIPE Atlas measurement stream and ONSPD, whose publisher documents its own defects. The only cross-spine link is a clock. Detail in [the dataset selection](docs/dataset-selection.md) and in [ADR-0008](docs/adr/0008-two-spines-with-no-cross-domain-join.md).

Olist is out: its data is CC BY-NC-SA 4.0, and share-alike would propagate to derived tables. [The prior repository](https://github.com/SoongGuanLeong/data_pipelines_batch_stream_vector) contributes reasoning and nothing else, recorded in [the salvage list](docs/salvage-list.md) and [ADR-0006](docs/adr/0006-reference-only-reuse-and-provenance.md).

## 4. The stack

Twenty components, each defended against the mission's sprawl test: twelve posting-named, three same-interface substitutions (OpenTofu for Terraform, SeaweedFS for S3, Podman for Docker), and five requirement-driven additions (PostgreSQL, the RIPE Atlas collector, Apicurio, OpenLineage, Marquez). Every component that was considered and dropped has a recorded disposition. Detail in [the technology selection](docs/technology-selection.md).

## 5. The architecture

One system, three views. [The system architecture](docs/system-architecture.md) holds the twenty components and the counting rule, the data-plane and control-plane cut, the boundaries, the diagram S1, and the mapping from every ADR to the element it attaches to. [The data architecture](docs/data-architecture.md) holds the two spines, the layer semantics and naming convention, the gold grains, and the consolidated physical layout for both the Iceberg side and the ClickHouse serving copies. [The data-flow diagrams](docs/data-flow.md) hold D1 commerce, D2 network and G1 the gate and quarantine, with the no-join seam drawn as an absence.

## 6. The paths

The cross-cutting specs, one per concern. [The streaming job designs](docs/streaming-jobs.md) settle the three jobs, the sink mode, the watermark and the lateness policy. [The serving layer](docs/serving-layer.md) settles the three personas, the nine-query benchmark set, the gold grain, and the two-arm comparison. [Governance and data quality](docs/governance-and-data-quality.md) settles the check taxonomy, the gate, quarantine, namespaces, retention and PII. [Data contracts](docs/data-contracts.md) settles the contract format, versioning and the consumer interface. [The security model](docs/security-model.md) settles secrets, authentication, TLS, the unauthenticated-surface register and the audit posture.

## 7. The evidence

The regime that makes the proposal's claims checkable. [The completion bar](docs/completion-bar.md) defines what finished means, as a register the CI validates without re-running any evidence. [The benchmark plan](docs/benchmark-plan.md) defines one protocol, its pre-registered arms and its budget register. [The testing strategy](docs/testing-strategy.md) fixes the four levels and the strongest claim each may support. [The incident laboratory](docs/incident-laboratory.md) fixes six scenarios, five injected, each owing an unprompted alert and a measured detection time.

## 8. The delivery

[The repository decomposition](docs/repository-decomposition.md) settles one repository split by engineering path with enforced import boundaries. [The local development architecture](docs/local-development.md) settles the five profiles and the host-anchored peak budget. [The cloud architecture](docs/cloud-architecture.md) settles the AWS shape, its two tfvars profiles and the cost model. [The CI/CD strategy](docs/ci-cd-strategy.md) settles the job graph and the delivery path. [The roadmap](docs/implementation-roadmap.md) settles the eleven phases, each closing on a declared run sequence, with the register as the definition of done.

## 9. The decisions: how to navigate 34 ADRs

Every architectural decision is an ADR under [`docs/adr/`](docs/adr/). The index below answers one question: **given a spec, which decisions produced it.** The other direction, **given an ADR, which element of the running system it attaches to**, is [the system architecture](docs/system-architecture.md) section 6, and it is not repeated here. No ADR is summarised in two places.

| Spec | ADRs it applies |
|---|---|
| [The requirements matrix](docs/requirements-matrix.md) | none of its own |
| [The dataset selection](docs/dataset-selection.md) | 0008, 0009 |
| [The salvage list](docs/salvage-list.md) | 0006 |
| [The technology selection](docs/technology-selection.md) | 0005, 0010, 0011, 0020, 0024, 0027, 0034 |
| [The system architecture](docs/system-architecture.md) | none of its own; it maps all 34 |
| [The data architecture](docs/data-architecture.md) | 0008, 0025 |
| [The data-flow diagrams](docs/data-flow.md) | none of its own |
| [The streaming job designs](docs/streaming-jobs.md) | 0001, 0002, 0011, 0013, 0014, 0015 |
| [The serving layer](docs/serving-layer.md) | 0003, 0012, 0015, 0021 |
| [Governance and data quality](docs/governance-and-data-quality.md) | 0016, 0017, 0018 |
| [Data contracts](docs/data-contracts.md) | 0019, 0020, 0021, 0022, 0023, 0025 |
| [The security model](docs/security-model.md) | 0004, 0028, 0029, 0030 |
| [The completion bar](docs/completion-bar.md) | 0007, 0032 |
| [The benchmark plan](docs/benchmark-plan.md) | none of its own |
| [The testing strategy](docs/testing-strategy.md) | 0032 |
| [The incident laboratory](docs/incident-laboratory.md) | none of its own |
| [The repository decomposition](docs/repository-decomposition.md) | 0026, 0034 |
| [The local development architecture](docs/local-development.md) | 0028, 0031 |
| [The cloud architecture](docs/cloud-architecture.md) | 0005, 0027, 0034 |
| [The CI/CD strategy](docs/ci-cd-strategy.md) | 0007, 0033 |
| [The roadmap](docs/implementation-roadmap.md) | none of its own |

An ADR that appears under two specs is a decision with two consequences, not a duplicate. [ADR-0022](docs/adr/0022-iceberg-format-v2-is-pinned.md) is superseded by [ADR-0025](docs/adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md); it is listed where its superseded decision still has a reader.

## 10. The deliverable map

The mission's Final Deliverables list ([`docs/mission/MISSION.md`](docs/mission/MISSION.md) section 32) has 23 items. Each is mapped to the artefact that carries it, so a reviewer can check the set is complete.

| # | Deliverable | Artefact |
|---|---|---|
| 1 | Target-job requirements matrix | [The requirements matrix](docs/requirements-matrix.md) |
| 2 | Dataset research | [The dataset selection](docs/dataset-selection.md) sections 4 and 11, with [research 01a](docs/research/01a-datasets-relational-cdc.md) and [01b](docs/research/01b-datasets-event-streaming.md) |
| 3 | Selected dataset architecture | [The dataset selection](docs/dataset-selection.md) section 3, with [the data architecture](docs/data-architecture.md) section 2 |
| 4 | System architecture | [The system architecture](docs/system-architecture.md) |
| 5 | Data architecture | [The data architecture](docs/data-architecture.md) |
| 6 | Technology-selection matrix | [The technology selection](docs/technology-selection.md) |
| 7 | Repository decomposition | [The repository decomposition](docs/repository-decomposition.md) |
| 8 | Local development architecture | [The local development architecture](docs/local-development.md) |
| 9 | Cloud architecture | [The cloud architecture](docs/cloud-architecture.md) |
| 10 | Security model | [The security model](docs/security-model.md), with [the security evidence plan](docs/security-evidence-plan.md) |
| 11 | Governance model | [Governance and data quality](docs/governance-and-data-quality.md) sections 5 to 7 |
| 12 | Data-quality strategy | [Governance and data quality](docs/governance-and-data-quality.md) sections 2 to 4 and 8 |
| 13 | Observability strategy | **No owning document, decided and distributed:** the class delta in [the completion bar](docs/completion-bar.md) section 6.10, the evidence M15 names in [the requirements matrix](docs/requirements-matrix.md), the alert-fires drill in [the incident laboratory](docs/incident-laboratory.md) section 4, the profile overlay in [the local development architecture](docs/local-development.md) section 4, and the build in [the roadmap](docs/implementation-roadmap.md) Phase 8 |
| 14 | Reliability strategy | **No owning document, decided and distributed:** the eight-link incident contract in [the incident laboratory](docs/incident-laboratory.md) section 4, M15 and M16 in [the requirements matrix](docs/requirements-matrix.md), the regression guarantee and profile reproducibility in [the completion bar](docs/completion-bar.md) sections 8 and 10, and the preflight refusal in [the local development architecture](docs/local-development.md) section 5 |
| 15 | Performance benchmark strategy | [The benchmark plan](docs/benchmark-plan.md) |
| 16 | Testing strategy | [The testing strategy](docs/testing-strategy.md) |
| 17 | CI/CD strategy | [The CI/CD strategy](docs/ci-cd-strategy.md) |
| 18 | Infrastructure/IaC strategy | [The cloud architecture](docs/cloud-architecture.md) sections 2 and 7 for OpenTofu, with [the local development architecture](docs/local-development.md) for compose. Split across two documents, no single owner |
| 19 | Phased implementation roadmap | [The roadmap](docs/implementation-roadmap.md) sections 3 and 4 |
| 20 | Definition of Done for every phase | [The roadmap](docs/implementation-roadmap.md) section 5, judged by [the completion bar](docs/completion-bar.md) and its register |
| 21 | Incident laboratory design | [The incident laboratory](docs/incident-laboratory.md) |
| 22 | Interview/demo scenarios | **Not yet produced.** [The interview and demo narrative](https://github.com/SoongGuanLeong/de-platform/issues/29), issue #29, open on the map |
| 23 | Final portfolio presentation strategy | This document, with [`README.md`](README.md) |

Two of the 23 have no owning document, items **13** and **14**, and one proposal item below does. That is a finding rather than an omission: every facet of each is decided and owned by one of the documents its row names, and giving any of them its own document would restate documents that already hold the authority. The check this asks of a reviewer is that no facet is undecided, not that a file exists. Item **18** is split across two named owners, which is a mapping rather than a gap.

The mission's other list, the 21 items of the Research & Architecture Proposal ([`docs/mission/MISSION.md`](docs/mission/MISSION.md) section 35), is not mapped separately because 17 of its 21 items are the same artefacts. The four that are not:

| Proposal item | Artefact |
|---|---|
| 1, detailed interpretation of the target job | [The requirements matrix](docs/requirements-matrix.md) section 1, against the cached posting |
| 9, what to reuse from the prior repository | [The salvage list](docs/salvage-list.md) |
| 16, complexity assessment | **No owning document, decided and distributed:** the sprawl defence in [the technology selection](docs/technology-selection.md) section "The count", the deferral table in [the roadmap](docs/implementation-roadmap.md) section 8, and what is deliberately not done in [the requirements matrix](docs/requirements-matrix.md) section 7 |
| 21, mapping back to every requirement | [The requirements matrix](docs/requirements-matrix.md) |

## 11. What this proposal does not claim

- **No platform code exists.** This is a planning artefact. Implementation is a separate effort, begun only after the proposal is approved.
- **Nothing was measured.** Every figure is a declared budget or an arithmetic result over documented defaults. [The system architecture](docs/system-architecture.md) section 0 states the rule the whole suite follows.
- **The capability register ships empty.** No capability is claimed as complete, and the empty register is the correct state.
- **The cloud arm is authored, not applied.** The AWS topology is statically validated and only ever run inside a priced, time-boxed demo window. Nothing in [the cloud architecture](docs/cloud-architecture.md) was deployed.
- **Fourteen gaps are named, each with a substitute.** [The completion bar](docs/completion-bar.md) section 13 lists them. They are registered rather than hidden, and this index does not restate them.
- **Three deliverables have no owning document.** Items 13 and 14 and proposal item 16 in section 10 are decided and distributed across the documents that own each facet, rather than carried by one. A reviewer checking the set should read those rows as findings: the test is that no facet is undecided, not that a file exists.
- **Deliverable 22 is not yet produced.** [The interview and demo narrative](https://github.com/SoongGuanLeong/de-platform/issues/29), issue #29, is open on the map.
- **No performance result measured on TPC data is a TPC Benchmark Result.** Every such figure is labelled a TPC-derived result.
- **Two limitations carried, not reopened.** From the Iceberg v3 review: the catalog read-through REST path was not exercised, and the Flink v3 upsert writer is unverified.
