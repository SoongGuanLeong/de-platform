# de-platform

A vendor-neutral data lakehouse, designed in public as a Research and Architecture Proposal for the ONL Biz Solutions Senior Data Engineer (Data Lakehouse) posting.

**Status: planning.** No platform code exists yet, and nothing in this repository was measured.

---

## The proposal in three sentences

Two independent data spines that never join: a commerce spine on real TPC-C change data captured by Debezium, and a network spine on the RIPE Atlas measurement stream and UK ONSPD. Iceberg on SeaweedFS behind Polaris is the table layer, Kafka and Flink carry the stream, Spark the batch, ClickHouse serves, Dagster orchestrates, with a custom gated data-quality framework and OpenLineage for governance. Twenty components, only Iceberg and Kafka irreplaceable, and every claim built to be checked rather than believed.

The full framing paragraph, the status rule and the reading route are [the proposal](PROPOSAL.md) section 0 and section 1. They are not repeated here.

## Start here

| If you have | Read |
|---|---|
| Ten minutes | This page, then [the proposal](PROPOSAL.md) section 0, then [the requirements matrix](docs/requirements-matrix.md) section 4, [the technology selection](docs/technology-selection.md) section "The stack at a glance", and [the system architecture](docs/system-architecture.md) section 5 |
| An hour | [The proposal](PROPOSAL.md) top to bottom, then the suite in the order its section 1 gives |
| A specific question | The map in [the proposal](PROPOSAL.md) section 1, or the ADR index in its section 9 |

## The five load-bearing decisions

The posting's own emphasis, and where each one is settled.

| Decision | Where |
|---|---|
| **M5, physical table layout** | Partitioning, sort order, compaction and retention, with the variants pre-registered before measurement. [The data architecture](docs/data-architecture.md) section 5, [the benchmark plan](docs/benchmark-plan.md) section 4 |
| **M7, the serving layer** | Materialised MergeTree rather than reading Iceberg in place, tested as a two-arm comparison rather than assumed. [The serving layer](docs/serving-layer.md) section 8 |
| **M2 and M3, convergence and exactly-once effect** | Iceberg has no UPDATE, so the claims are re-specified around what the engine can actually hold. [ADR-0001](docs/adr/0001-convergence-not-ordering.md), [ADR-0002](docs/adr/0002-exactly-once-effect-not-delivery.md) |
| **M16, the incident laboratory** | Six scenarios, five injected into the running stack, each owing an unprompted alert and a measured detection time. [The incident laboratory](docs/incident-laboratory.md) |
| **M13, the data-quality gate** | Custom checks with severity that stop or quarantine a pipeline, never a report nobody reads. [Governance and data quality](docs/governance-and-data-quality.md) section 3 |

## What it runs on

Twenty components, counted by the rule in [the system architecture](docs/system-architecture.md) section 2, which is also where the full list and the diagram S1 live. In one line: the RIPE Atlas collector, Debezium, Kafka, Flink, Spark, SeaweedFS, ClickHouse and PostgreSQL in the data plane; Polaris, Dagster, Apicurio, Marquez, Prometheus, Grafana and Alertmanager in the control plane; Iceberg, OpenLineage, Helm and OpenTofu as libraries and CLIs; and Podman as the runtime.

## What this is not

- **Not a technology museum.** Every component is posting-named, a same-interface substitution, or a requirement-driven addition, and each rejected candidate has a recorded disposition.
- **Not a build.** This repository holds a proposal. Implementation is a separate effort, begun only after the proposal is approved.
- **Not measured.** Every figure is a declared budget or an arithmetic result over documented defaults, and the capability register ships empty.
- **Not a finished claim.** [The proposal](PROPOSAL.md) section 11 names what it does not claim, including three mission deliverables with no owning document and the one not yet produced.

## Where to go next

- [The proposal](PROPOSAL.md), the index and reading route for the whole suite.
- [The requirements matrix](docs/requirements-matrix.md), the posting's requirements and the evidence each is judged by.
- [The decisions](docs/adr/), 34 ADRs, indexed by spec in [the proposal](PROPOSAL.md) section 9.
- [The mission](docs/mission/MISSION.md), reproduced verbatim, which is the brief this proposal answers.
