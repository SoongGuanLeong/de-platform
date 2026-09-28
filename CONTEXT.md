# de-platform

The vocabulary this project uses in a specific sense. It records language, not decisions: the reasoning behind each term lives in `docs/adr/`, and the requirements it serves live in `docs/requirements-matrix.md`. Several entries exist because the obvious word for the concept is the wrong one, so the rejected word is listed rather than left to drift back in.

## Language

### Selection

**Substitution**:
A component that replaces a posting-named tool across the same interface, so the posting's requirement is still demonstrated without the posting's exact tool: OpenTofu for Terraform, SeaweedFS for S3, Podman for Docker and EKS.
_Avoid_: replacement, alternative, equivalent

**Addition**:
A component no posting line names, admitted only against a named requirement and counted as an addition rather than folded into the posting's stack: PostgreSQL as the CDC source, Apicurio, OpenLineage and Marquez.
_Avoid_: extra, nice-to-have, bonus

**Technology count**:
The number of components the platform runs, defended against the mission's sprawl test by showing each one is posting-named, a substitution, or an addition. Nineteen, of which Iceberg and Kafka are irreplaceable.
_Avoid_: component total, stack size

### Sources

**Spine**:
One of the platform's two independent data domains, each with its own sources, ingestion pattern and processing path: the commerce spine (TPC-C for CDC, TPC-H for batch and serving) and the network spine (RIPE Atlas for streaming, ONSPD for reference and SCD2). A spine is the unit of justification, so a source belongs to a spine and a source belonging to neither is not in the platform.
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
What a catalog authorises: which catalog entities a principal may see and act on. Contrast the data plane, the path that fetches table bytes directly from object storage and does not pass through the catalog.
_Avoid_: control plane, catalog layer

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

### Completion

**Capability instance**:
One concrete thing that must work, such as one topic, one pipeline, one table or one dashboard. It is the unit the completion bar applies to, and a class is complete only when all of its instances are.
_Avoid_: capability, component, feature

**Capability register**:
The machine-readable list of capability instances and their evidence, at `docs/completion-bar.yaml`. The CI validates the register without re-running evidence.
_Avoid_: checklist, inventory, manifest

**Budget**:
A threshold declared before the measurement it judges, and committed before it. Changing a budget creates a new entry and invalidates evidence that cited the old one.
_Avoid_: target, SLO, baseline

**Profile**:
The declared service set and resource budget an evidence item was produced under. Reproducibility is defined per profile, because the whole stack cannot be co-resident at 7 to 8 GB.
_Avoid_: environment, mode, tier
