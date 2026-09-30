# de-platform

The vocabulary this project uses in a specific sense. It records language, not decisions: the reasoning behind each term lives in `docs/adr/`, and the requirements it serves live in `docs/requirements-matrix.md`. Several entries exist because the obvious word for the concept is the wrong one, so the rejected word is listed rather than left to drift back in.

## Language

### Selection

**Substitution**:
A component that replaces a posting-named tool across the same interface, so the posting's requirement is still demonstrated without the posting's exact tool: OpenTofu for Terraform, SeaweedFS for S3, Podman for Docker and EKS.
_Avoid_: replacement, alternative, equivalent

**Addition**:
A component no posting line names, admitted only against a named requirement and counted as an addition rather than folded into the posting's stack: PostgreSQL as the CDC source, the RIPE Atlas collector, Apicurio, OpenLineage and Marquez.
_Avoid_: extra, nice-to-have, bonus

**Technology count**:
The number of components the platform runs, defended against the mission's sprawl test by showing each one is posting-named, a substitution, or an addition. Twenty, of which Iceberg and Kafka are irreplaceable.
_Avoid_: component total, stack size

**Application component**:
One of the twenty things the platform runs, and the only kind of thing the technology count counts. A component is a service the platform runs, resident or transient, whether it is a selected third-party technology or platform-authored code; a library, a CLI, a framework or a bespoke job is not a component. A component may take a different form in the cloud without becoming a different component, or a twenty-first.
_Avoid_: service, workload, deployment unit

**Cloud form**:
The managed service a component takes in the cloud deployment. It is a change of runtime, not of component: S3 is SeaweedFS's cloud form and RDS is PostgreSQL's, and neither is an addition.
_Avoid_: cloud equivalent, managed version, hosted variant

**Data plane**:
The components and paths that move or store data: the RIPE Atlas collector, Debezium, Kafka, Flink, Spark, SeaweedFS and the Iceberg bytes it holds, ClickHouse, and PostgreSQL as the CDC source. Contrast the control plane, which describes, schedules, authorises and observes.
_Avoid_: data layer, hot path, runtime plane

**Control plane**:
The components that describe, schedule, authorise or observe data: Polaris, Dagster, Apicurio, Marquez, Prometheus, Grafana and Alertmanager. A component has a primary plane, and a crossing into the other plane is drawn rather than resolved away: Polaris vends a prefix-scoped credential into the data plane, and Dagster starts work in it.
_Avoid_: metadata plane, catalog layer, orchestration layer, EKS control plane

**Infrastructure**:
What exists only because the cloud needs it, and is therefore neither a component nor an addition: the container registry, the ingress controller and its load balancer, NAT gateways, VPC endpoints, the secrets store, the CSI drivers, the Flink Kubernetes Operator, Spark-on-Kubernetes, the node groups, and the OpenTofu state store. The RIPE Atlas collector is deliberately not infrastructure: it runs locally, and it is a service the platform runs rather than something the cloud needs.
_Avoid_: platform component, supporting service, dependency

### Sources

**Spine**:
One of the platform's two independent data domains, each with its own sources, ingestion pattern and processing path: the commerce spine (TPC-C for CDC, TPC-H for batch and serving) and the network spine (RIPE Atlas for streaming, ONSPD for reference and SCD2). A spine is the unit of justification, so a source belongs to a spine and a source belonging to neither is not in the platform. A streaming source is reached through its spine's ingestion service: Debezium for TPC-C's change events, the RIPE Atlas collector for the live measurement stream.
_Avoid_: domain, workstream, pipeline, subject area

**Cross-domain join**:
A join between tables from different spines. The platform contains none, and the absence is deliberate: the two spines share only a clock.
_Avoid_: cross-source join, enrichment join, federated join

### Correctness

**Convergence**:
The property that a destination reaches the correct final state even when changes arrive duplicated or out of order. This is the claim the project makes in place of ordering.
_Avoid_: ordering preserved, in-order delivery, ordered stream

**Idempotence**:
The property that processing the same input a second time leaves the committed result unchanged. Idempotence is about replay; convergence is about arrival order.
_Avoid_: deduplication, at-least-once

**Exactly-once effect**:
The guarantee that committed output reflects each source change once, even though the processing may have replayed it. It is a property of committed state, not of delivery.
_Avoid_: exactly-once delivery, exactly-once semantics

**Source-transaction atomicity**:
The guarantee that a destination never exposes a partially applied source transaction. Explicitly not claimed by this platform.
_Avoid_: transactional end to end, atomic pipeline

**Upsert**:
An update expressed as an insertion plus the marking of the superseded row. The storage layer has no in-place update, so this is what the word means here.
_Avoid_: update, merge, modify

### Modelling

**Grain**:
What one row of a table represents. Order-grain and line-grain measures sitting side by side is the error the fan-out demonstration exists to expose.
_Avoid_: level, granularity, detail

**Fan-out**:
The multiplication of fact rows caused by joining to a dimension that has several rows per key, which silently inflates an aggregate. The trap is invisible in the result: the query runs and returns a plausible number.
_Avoid_: blow-up, row explosion, cartesian

**Layer**:
One of the three fidelities a spine's data passes through, each with its own namespace: bronze holds the source's own records as they arrived, silver holds them cleansed and conformed at the source's own grain, and gold holds the modelled tables with declared grains and contracts. A layer is not a spine and not a component, and the `platform` namespace holds control-plane tables and is neither.
_Avoid_: zone, tier, stage, medallion

**Physical layout**:
The choices that decide how a table is stored and read: the partition transform, the sort order, the format version, the compaction policy and the retention. It is the posting's stated emphasis, and every value is a baseline until a benchmark measures it.
_Avoid_: schema, table design, DDL

### Serving

**Serving copy**:
A MergeTree table in ClickHouse that answers analyst queries, derived from an Iceberg table rather than read from it. The copy is the architecture; the Iceberg table stays the record.
_Avoid_: cache, replica, serving layer

**Straight copy**:
A serving copy whose shape matches the gold table it is derived from.
_Avoid_: passthrough, raw copy

**Shaped copy**:
A serving copy whose shape is changed for the workload, by denormalising a resolved value onto it or by holding it at a coarser grain.
_Avoid_: denormalised table, wide table

**Rollup**:
A serving copy held at a coarser grain than its source and maintained as an aggregate, so the trend query never rescans raw rows.
_Avoid_: summary table, aggregate table, cube

**Materialised serving store**:
The architecture in which the serving engine holds shaped copies of lakehouse tables rather than reading them in place. Physical-layout tuning exists only in the copy, which is why the copy is the architecture.
_Avoid_: serving layer, query cache

**Read-through**:
Reading lakehouse tables in place through the catalog, with no copy made. Retained here only as a comparison arm.
_Avoid_: direct query, federated query

**Comparison arm**:
A rejected alternative that is still built and measured, so that an architecture decision rests on a recorded delta rather than on a preference.
_Avoid_: baseline, control

### Governance

**Authorisation seam**:
The boundary between the systems that enforce access control, together with the statement of which system governs which path. Naming the seam is itself the deliverable, because no single system covers both paths.
_Avoid_: access control layer, security boundary

**Metadata plane**:
What a catalog authorises: which catalog entities a principal may see and act on. Contrast the data plane, the path that fetches table bytes directly from object storage and does not pass through the catalog. This is an axis of a read rather than a grouping of components, and it is not the same cut as the control plane.
_Avoid_: catalog layer

**Check**:
One assertion over data, carrying an id, a kind, a subject and a severity. A check produces a result; on its own it stops nothing.
_Avoid_: rule, test, validation

**Severity**:
The declared consequence of a failed check, one of warn, quarantine or fail. Declared on each check instance, with the kind supplying a default.
_Avoid_: priority, level, criticality

**Gate**:
The orchestration consequence of a severity: a check reports, a gate stops or diverts. Keeping the two words apart is what stops a green dashboard being mistaken for enforcement.
_Avoid_: check, validation, guard

**Quarantine**:
Diverting a batch's offending rows while its clean rows continue, as distinct from failing the batch and distinct from dropping the rows.
_Avoid_: reject, dead-letter, drop

**Minimisation**:
Removing a sensitive column from a table because no query needs it, as distinct from masking it in place.
_Avoid_: masking, redaction, anonymisation

**Source hazard**:
A defect the publisher documents in its own data, as distinct from a fault the platform injects deliberately. The two are never presented as the same thing.
_Avoid_: injected fault, data bug

**Data class**:
A group of tables sharing one retention rule and one erasure bound: static oracle, live OLTP mirror, reference SCD2, live capture, or control.
_Avoid_: category, tier, type

**Erasure window**:
The interval between a row's deletion and the expiry of the snapshots that still contain it, during which the deletion is not complete.
_Avoid_: retention period, deletion lag

**Unauthenticated surface**:
A listener or interface that deliberately carries no authentication locally, entered in a register with the reason it is acceptable, the network boundary that bounds it, and the control that protects it in the cloud. It is a decision with a written reason, not an omission.
_Avoid_: insecure, exposed, unprotected

**Rotation class**:
How a component re-reads a credential: reload (it re-reads without a restart), restart (the value is read at process start), or init (the value is consumed once at first initialisation and cannot be rotated by re-reading). It is a property of the component, so it is declared rather than assumed.
_Avoid_: rotation policy, secret lifecycle

**Audit gap**:
A question an auditor would ask that the platform cannot answer, named with its reason rather than left implicit. The largest is structural: a read using the vended, prefix-scoped credential does not pass through the catalog, so no system attributes it to a user.
_Avoid_: blind spot, limitation, caveat

### Contracts

**Contract**:
One machine-readable YAML file per gold table, at `contracts/<spine>/<table>.yml`, that is the table's authoritative interface: its columns with types, nullability and PII class, its business keys, invariants, persona query ids, and its versioning and compatibility rules. Authored in Git; the registry holds a pushed mirror, never the source.
_Avoid_: schema doc, data dictionary, specification

**Contract version**:
The `major.minor` version of a contract. A minor bump is an additive change; a major bump is required for a breaking one, and at most two majors live at once.
_Avoid_: revision, release, iteration

**Breaking change**:
A change a declared consumer cannot absorb without changing: drop a column, rename one, narrow a type, turn an optional column required, change the grain, or change the business key. It lands as a new major version, never in place.
_Avoid_: incompatible change, major change, schema break

**Compatibility rule**:
The declared rule governing whether a new schema may be registered against a subject, such as `BACKWARD_TRANSITIVE` for the CDC topics. It is enforced by the serializer, not by review.
_Avoid_: compatibility mode, compatibility level, compatibility setting

**Interface contract**:
The consumer-facing surface and its versioning rule: the versioned ClickHouse serving views, with the Iceberg gold tables as the read-only second interface. Distinct from the per-table contract, which is the producer's interface.
_Avoid_: API contract, service contract, external schema

### Evidence

**Demonstration**:
What a matrix row commits to producing. Evidence counts only if a sceptical interviewer can inspect it: a passing test, a dashboard, a benchmark with a recorded protocol, an incident writeup, a runbook, a diagram, or a query.
_Avoid_: proof, deliverable, implementation

**Status**:
A verdict on whether a requirement can be honestly evidenced, not a build-state tracker. No status cell carries a measured number.
_Avoid_: progress, done, complete

**Re-specification**:
Rewriting a requirement from the posting because the posting's wording is unfalsifiable or false, rather than copying it through. Four rows are re-specifications.
_Avoid_: rewording, interpretation, clarification

**Load-bearing**:
A row whose claim the portfolio's credibility rests on, ranked in the interview-facing ordering. Contrast supporting rows, which are evidenced but are not where the effort concentrates.
_Avoid_: important, priority, critical path

**Eight links**:
The evidence standard for an incident: detection, alert, diagnosis, root cause, mitigation, recovery, data-correctness verification, and permanent fix, each with a real timestamp.
_Avoid_: incident report

**Postmortem**:
The per-incident write-up that carries the eight links, written blameless. The runbook is a separate artefact. M16 requires one per incident.
_Avoid_: incident report, retrospective

**Honest gap**:
A requirement the platform cannot evidence, recorded as such alongside a credible substitute rather than quietly omitted. The term exists so that an omission reads as a decision.
_Avoid_: limitation, caveat, non-goal

**GDPR-shaped**:
Describing technical measures that resemble a compliance posture without constituting compliance, since a lawful basis, a DPIA and a request process cannot be evidenced locally.
_Avoid_: GDPR compliant, privacy compliant

**Signal**:
An observable that exists and is reachable. A signal proves the mechanism can be seen, not that the claim holds.
_Avoid_: evidence, proof, metric

**Behaviour**:
The platform was shown to do the thing under a fault or a boundary condition, and the result was recorded. A capability may only be marked complete on at least one behaviour item.
_Avoid_: functional test, works, demo

**Observed-once**:
A measurement whose environment cannot be reproduced. It may be recorded, but it can never be cited as evidence for a claim.
_Avoid_: unreproducible result, anecdote, one-off

### Testing

**Test level**:
One of unit, contract, integration or end-to-end, fixing what a test runs against and therefore the strongest claim it may support. Unit and contract prove a signal at most; integration proves behaviour only when a declared boundary condition is present; end-to-end does. A **drill** is not a level: it is an incident run under a path profile plus the observability overlay, and it is the only thing that promotes an observability signal to behaviour.
_Avoid_: test type, test tier, test category

**Fixture**:
A test input that is generated by a pinned script or fetched from a pinned URL, with its generator, checksum and declared volume recorded in `tests/fixtures.yaml`. Never committed as bytes. A fixture may be reduced only when the evidence item labels the reduction and the claim is not volume-dependent.
_Avoid_: test data, sample, seed data

### Completion

**Capability instance**:
One concrete thing that must work, such as one topic, one pipeline, one table or one dashboard. It is the unit the completion bar applies to, and a class is complete only when all of its instances are.
_Avoid_: capability, component, feature

**Capability register**:
The machine-readable list of capability instances and their evidence, at `docs/completion-bar.yaml`. The CI validates the register without re-running evidence.
_Avoid_: checklist, inventory, manifest

**Representative instance**:
The one instance in a capability class whose evidence carries the class's **mutation note**, a one line record of what was removed and that the test failed. Exactly one per populated class, and the register's `representative` flag is what makes the obligation findable. The CI checks that the note exists; whether the mutation actually fails the test is a reviewer's judgement.
_Avoid_: exemplar instance, sample instance, lead instance

**Budget**:
A threshold declared before the measurement it judges, and committed before it. Changing a budget creates a new entry and invalidates evidence that cited the old one. Contrast a **ceiling**, which is a resource entitlement rather than a threshold and lives in its own register.
_Avoid_: target, SLO, baseline

**Profile**:
The declared service set and resource budget an evidence item was produced under. Reproducibility is defined per profile, because the whole stack cannot be co-resident at 7 to 8 GB. Its concrete entitlement is the **profile peak**, declared in `deployment/budgets/profiles.yaml`.
_Avoid_: environment, mode, tier

**Ceiling**:
The hard limit one service's container is entitled to inside a profile, declared in `deployment/budgets/profiles.yaml`. An exceedance is an OOM kill rather than a slowdown, which is what makes a ceiling a real constraint. A ceiling is not a budget.
_Avoid_: quota, allocation, limit, cap

**Profile peak**:
A profile's declared entitlement: the sum of its resident ceilings plus the largest single transient ceiling. The preflight compares it against the host's free memory and refuses the run when it does not fit.
_Avoid_: total, footprint, resource sum

**Resident set**:
The services a profile keeps up for the whole run, as distinct from its transient members.
_Avoid_: long-running services, core services

**Transient member**:
A run-to-completion member of a profile, counted at its ceiling in the peak and not resident, such as `spark-submit` or the `flink run` client.
_Avoid_: job, batch step, one-shot

**Reduced variant**:
A profile's declared fallback when the host cannot hold the full peak: the same ceilings with the observability overlay dropped. A reduced run is labelled as reduced, and it cannot evidence an alert drill.
_Avoid_: degraded mode, lite profile, fallback

**Local-versus-cloud diff**:
The written statement of what a local run cannot exercise, one row per mechanism, each naming what stands in its place. A required artefact rather than a caveat list.
_Avoid_: limitations, caveats, known issues

### Continuous integration

**Deployable artefact**:
The commit on `main` whose required check is green and whose `deployment/` tree renders and pins its inputs. A `demo-<YYYY-MM-DD>` tag names the one a priced window is run from. Delivery is defined by this artefact rather than by a deployment, because no cloud arm is ever applied.
_Avoid_: release, build, deployment

**Structural check**:
A check that needs no stack, no credential and no evidence re-run, and that reads committed artefacts and re-derives from them. It is what the structural jobs run; the one job in the graph that is not a structural check is the arm64 image build. It is why a green pipeline is never a behaviour item.
_Avoid_: check, lint, static test, fast test

**Required-check aggregator**:
The single job a branch ruleset requires, which fails on any failure or cancellation and passes on success or skipped, so a legitimately path-filtered job cannot block a merge. Named `required` and never `gate`, because gate already means the orchestration consequence of a severity.
_Avoid_: gate, umbrella job, checks job
