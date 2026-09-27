**Provenance.** Extracted 2026-09-27 from `~/.local/share/opencode/opencode.db`, table `part`, row `prt_0e136fb80001IJ93X34JcMc8WW` (session `ses_f1ec904a3ffezVIiibroTtAu6a`). The stored part held two documents concatenated: the wayfinder skill text, then this brief beginning at its own `# Project Mission` heading. Only the brief is reproduced, verbatim and unedited, from that heading to the end of the part.

The source contains two em dashes, in the target job title and in the mission statement quote. They are retained rather than converted to hyphens, because they fall inside quoted material and this file is a preservation copy. Nothing else in this file has been changed.

---

# Project Mission

Design and build a serious, production-oriented **vendor-neutral data lakehouse / data platform** whose primary purpose is to demonstrate that I can perform the kind of work required by this job:

**Target job:** Senior Data Engineer — Data Lakehouse
**JobStreet:** https://my.jobstreet.com/job/94703893

The platform should be designed around the actual requirements of the job posting, not around a generic tutorial or a collection of disconnected technologies.

The ultimate goal is:

> Build the closest realistic open-source/vendor-neutral equivalent of the data platform described in the target job, using sufficiently complex real-world datasets to demonstrate ingestion, streaming, batch processing, lakehouse management, serving, orchestration, governance, data quality, observability, reliability, performance tuning, and infrastructure engineering.

This is a portfolio project, but it should be engineered as if it were a small production platform.

---

# 1. First: Research Before Designing

Before proposing the architecture, thoroughly research:

1. The target JobStreet posting:

   * responsibilities
   * required technologies
   * nice-to-have technologies
   * expected engineering practices
   * AWS/Kubernetes requirements
   * lakehouse requirements
   * streaming requirements
   * governance requirements
   * observability/reliability requirements
   * performance-tuning requirements

2. `sindresorhus/awesome` Big Data:

   * https://github.com/sindresorhus/awesome#big-data

3. `awesomedata/awesome-public-datasets`:

   * https://github.com/awesomedata/awesome-public-datasets#readme

4. Kaggle datasets where appropriate.

5. Relevant official documentation for technologies being considered.

Do not blindly copy the technology lists from Awesome repositories.

The Awesome repositories are references for discovering technologies and datasets, not shopping lists.

For every proposed technology, explain:

* What problem does it solve?
* Why is it needed in this platform?
* Why this technology instead of the obvious alternatives?
* Which target-job requirement does it demonstrate?
* Is it genuinely necessary?
* Could an existing component already solve the problem?
* Does adding it create unnecessary operational complexity?

Prefer a smaller number of technologies used deeply over a huge number of technologies used superficially.

---

# 2. Target Job Alignment

Create a detailed requirements matrix:

| Job requirement  | Required capability              | Platform component | Demonstration | Status |
| ---------------- | -------------------------------- | ------------------ | ------------- | ------ |
| Kafka / Debezium | CDC ingestion                    | Kafka + Debezium   | ...           | ...    |
| Iceberg          | Open table lakehouse             | Iceberg            | ...           | ...    |
| Polaris          | REST catalog                     | Polaris            | ...           | ...    |
| Flink            | Real-time processing             | Flink              | ...           | ...    |
| Spark            | Batch processing                 | Spark              | ...           | ...    |
| ClickHouse       | Analytical serving               | ClickHouse         | ...           | ...    |
| Dagster          | Orchestration                    | Dagster            | ...           | ...    |
| AWS              | Cloud infrastructure             | S3/EKS/etc.        | ...           | ...    |
| Terraform        | IaC                              | Terraform          | ...           | ...    |
| Helm             | Kubernetes packaging             | Helm               | ...           | ...    |
| Prometheus       | Metrics                          | Prometheus         | ...           | ...    |
| Grafana          | Observability                    | Grafana            | ...           | ...    |
| Alertmanager     | Alerting                         | Alertmanager       | ...           | ...    |
| Governance       | Catalog/access/lineage/retention | ...                | ...           | ...    |
| Data quality     | Automated DQ                     | ...                | ...           | ...    |
| Performance      | Query/job optimization           | ...                | ...           | ...    |

Also identify requirements that cannot realistically be demonstrated in a personal project and propose credible substitutes.

Do not claim that a portfolio implementation is equivalent to years of production experience.

---

# 3. Dataset Selection Is a Core Architecture Decision

Do NOT simply choose a convenient dataset such as a small CSV.

The datasets must be sufficiently complex to create realistic data-engineering problems.

Search:

1. `awesomedata/awesome-public-datasets`
2. Kaggle
3. Other authoritative public sources when necessary

Prefer datasets that provide combinations of:

* large volume
* multiple related tables
* high cardinality
* timestamps
* event/order/fact data
* slowly changing dimensions
* updates
* deletes
* duplicate records
* late-arriving records
* schema evolution
* nested/semi-structured data
* geographical data
* time-series data
* historical records
* categorical dimensions
* realistic analytical questions
* relationships between datasets

Avoid datasets that only demonstrate:

> download CSV → clean CSV → create dashboard.

The data should force us to solve real engineering problems.

---

# 4. Use Multiple Datasets If Necessary

Do not force the entire platform to revolve around one dataset.

If no single dataset naturally provides enough complexity, construct a coherent multi-source data ecosystem.

For example, the platform may combine:

* a transactional dataset
* a high-volume event/time-series dataset
* a public API
* a geographic dataset
* a reference/dimension dataset
* a CDC-like source
* an event stream

The datasets must have a meaningful reason to coexist.

Do not combine datasets arbitrarily merely to increase the number of technologies.

The final platform should tell a coherent data story.

For every dataset, document:

* source
* license
* download/API mechanism
* size
* update frequency
* schema
* primary keys
* natural/business keys
* relationships
* timestamp semantics
* expected data quality problems
* expected ingestion mode
* expected processing mode
* why it is useful for demonstrating the target job requirements

---

# 5. Design the Platform Around Multiple Ingestion Patterns

The platform should demonstrate several realistic ingestion patterns where justified.

Potential patterns include:

### Batch files

```text
Public dataset
    ↓
Object storage
    ↓
Spark
    ↓
Iceberg Bronze
```

### REST/API ingestion

```text
Public API
    ↓
Python ingestion service
    ↓
Kafka or object storage
    ↓
Lakehouse
```

### CDC

```text
PostgreSQL
    ↓
Debezium
    ↓
Kafka
    ↓
Flink
    ↓
Iceberg
```

### Event streaming

```text
Event source
    ↓
Kafka
    ↓
Flink
    ↓
Iceberg
```

Do not implement every pattern unless the selected datasets actually justify them.

---

# 6. Lakehouse Architecture

The core lakehouse should use:

* Apache Iceberg
* object storage
* Apache Polaris or another appropriate Iceberg REST catalog
* Parquet where appropriate

The design should explicitly demonstrate:

* Bronze / Silver / Gold
* schema evolution
* partition evolution
* table evolution
* snapshots
* time travel
* MERGE / UPSERT
* deletes
* compaction
* small-file management
* retention
* historical correctness
* idempotent processing
* replay
* backfills

Do not merely store Parquet files and call it a lakehouse.

Demonstrate why Iceberg exists.

---

# 7. Streaming Architecture

Where the data supports it, implement:

```text
Source
  ↓
Kafka
  ↓
Flink
  ↓
Iceberg
```

Demonstrate realistic streaming concerns:

* event time
* processing time
* watermarks
* late events
* duplicate events
* idempotency
* checkpointing
* recovery
* replay
* consumer lag
* state management
* schema evolution
* partitioning
* backpressure
* failure recovery

Create controlled failure scenarios.

For example:

* Kafka consumer falls behind
* Flink checkpoint becomes slow
* worker crashes
* duplicate events arrive
* late events arrive
* malformed events arrive
* schema changes
* downstream Iceberg write fails

Document what happens and how the platform recovers.

---

# 8. Batch Processing

Use Apache Spark for meaningful batch workloads.

Demonstrate:

* Bronze → Silver transformations
* Silver → Gold transformations
* joins
* aggregations
* incremental processing
* partition pruning
* predicate pushdown
* shuffle management
* skew handling
* caching only where justified
* file sizing
* compaction
* incremental backfills

Do not manufacture meaningless Spark jobs just to show that Spark exists.

Every Spark job should solve an actual platform requirement.

---

# 9. Analytical Serving

Use ClickHouse as a primary analytical serving layer if it is appropriate for the selected workload.

Also evaluate whether Trino should remain part of the platform.

Demonstrate:

```text
Iceberg
   ↓
Trino / ClickHouse
   ↓
BI / analytical consumers
```

Investigate:

* Iceberg querying
* ClickHouse ingestion/query patterns
* physical table design
* partitioning
* ORDER BY
* primary keys
* materialized views
* aggregation strategies
* query profiling
* query latency
* concurrency
* analytical workload characteristics

Create representative analytical queries and benchmark them.

Where possible, deliberately create a poorly optimized implementation and then improve it.

Document:

> Problem → measurement → change → measurement → result

Do not fabricate performance improvements.

---

# 10. Orchestration

Use Dagster if it remains the best fit for the target architecture.

Or evaluate alternatives such as Airflow if research shows a stronger reason.

The orchestration layer should handle:

* batch pipelines
* dependencies
* retries
* backfills
* schedules
* sensors where appropriate
* asset/data awareness
* failure handling
* pipeline observability
* data-quality gates

Pipelines should not depend on manually running shell commands.

---

# 11. Data Quality

Build a real data-quality layer.

At minimum consider:

### Schema checks

* required columns
* type correctness
* schema compatibility
* schema evolution

### Record checks

* null rates
* uniqueness
* duplicate detection
* referential integrity
* valid ranges
* valid timestamps

### Pipeline checks

* row-count reconciliation
* source/target reconciliation
* freshness
* completeness
* late-data detection

### Business checks

Examples should be derived from the actual datasets.

DQ failures should be able to stop or quarantine downstream processing when appropriate.

Do not make DQ purely a collection of unit tests.

Show how DQ participates in an actual production pipeline.

---

# 12. Governance

Implement realistic governance capabilities.

Investigate and, where appropriate, implement:

* catalog organization
* namespaces
* ownership
* data classification
* access control
* retention policies
* lineage
* metadata
* data contracts
* schema compatibility
* auditability

Evaluate:

* Polaris catalog capabilities
* OpenLineage
* Marquez or another lineage backend
* dbt where useful
* Great Expectations / Soda / custom SQL/Python checks where useful

Do not add governance tools simply because they are popular.

The final architecture should clearly explain why each governance component exists.

---

# 13. Observability

Build production-style observability.

Use appropriate combinations of:

* Prometheus
* Grafana
* Alertmanager
* application metrics
* structured logs
* traces where useful

Monitor things such as:

### Kafka

* consumer lag
* throughput
* broker health

### Flink

* checkpoint duration
* checkpoint failures
* task failures
* backpressure
* throughput
* state size

### Spark

* job duration
* failed jobs
* input/output records
* shuffle
* resource usage

### Iceberg

* file counts
* file sizes
* snapshot counts
* metadata growth
* compaction requirements

### ClickHouse

* query latency
* failed queries
* resource usage
* slow queries

### Dagster

* failed assets
* retries
* freshness
* execution duration

### Data quality

* failed checks
* freshness violations
* schema violations
* reconciliation failures

Create dashboards that tell an operator whether the platform is healthy.

---

# 14. Reliability Engineering

Treat reliability as a first-class feature.

Design and test:

* retries
* idempotency
* checkpoint/recovery
* replay
* backfill
* dead-letter/quarantine paths
* failure isolation
* partial failure
* data reconciliation
* recovery after restart
* corrupted input
* schema changes

Create an "incident laboratory".

At minimum include scenarios such as:

1. Kafka consumer lag spike
2. Flink checkpoint timeout
3. Flink worker failure
4. Duplicate events
5. Late-arriving events
6. Iceberg small-file explosion
7. Failed Iceberg write
8. ClickHouse query regression
9. Upstream schema change
10. Source/target row-count mismatch
11. Dagster job failure
12. Object-storage outage simulation
13. Corrupt input file
14. Partial pipeline execution

For each incident document:

```text
Detection
↓
Alert
↓
Diagnosis
↓
Root cause
↓
Mitigation
↓
Recovery
↓
Data correctness verification
↓
Permanent fix
```

---

# 15. Infrastructure

The platform should be local-first but designed for cloud deployment.

Local development may use:

* Docker
* Kubernetes where justified
* MinIO
* PostgreSQL
* Kafka
* Flink
* Spark
* Iceberg
* Polaris
* ClickHouse
* Dagster
* Prometheus
* Grafana

Cloud deployment should map the architecture to AWS concepts:

```text
Local                     AWS

MinIO             →       S3
PostgreSQL        →       RDS
Kubernetes        →       EKS
IAM equivalent    →       IAM
VPC networking    →       AWS VPC
```

Use:

* Terraform
* Helm
* Kubernetes manifests where appropriate

The architecture should make it clear which components are application-level and which are infrastructure-level.

---

# 16. AWS / Cloud Readiness

Do not simply say "AWS compatible."

Create an explicit cloud deployment design.

Document:

* S3 layout
* IAM roles/policies
* VPC
* subnets
* security groups
* EKS
* node groups
* storage
* secrets
* networking
* observability
* cost considerations

If deploying the entire system to AWS is financially impractical, provide:

1. fully reproducible local deployment
2. Terraform infrastructure design
3. a minimal-cost cloud deployment
4. documented differences between local and cloud execution

Do not spend excessive money merely to demonstrate AWS.

---

# 17. Kubernetes

Use Kubernetes because the target job explicitly mentions EKS.

Do not Kubernetes-ify everything without reason.

Demonstrate:

* deployments
* services
* config
* secrets
* health checks
* resource requests/limits
* persistent storage where necessary
* horizontal scaling where meaningful
* Helm packaging
* rolling updates
* failure/restart behaviour

Explain which workloads benefit from Kubernetes and which do not.

---

# 18. Security

Include practical security controls:

* secrets management
* credentials outside source control
* least-privilege access
* network boundaries
* TLS where appropriate
* service authentication
* catalog permissions
* database permissions
* auditability

Do not turn this into a security-specialist project.

The goal is to demonstrate that the platform was designed with production security in mind.

---

# 19. Testing

Build multiple levels of tests:

### Unit

Transformation and business logic.

### Integration

Kafka, Flink, Spark, Iceberg, ClickHouse, etc.

### Data quality

Expected dataset invariants.

### End-to-end

Source → ingestion → lakehouse → serving.

### Failure tests

Restart components and inject failures.

### Performance

Benchmark realistic workloads.

### Regression

Ensure schema and pipeline changes do not silently break downstream consumers.

The platform should have automated CI.

---

# 20. Infrastructure and Application Repository Design

First determine whether the entire platform should be one repository.

If the platform becomes too large, split it into logical subprojects.

Use the same philosophy we used for `footprint-messaging`:

> Split by meaningful engineering boundary, not arbitrarily.

Possible decomposition:

```text
platform/
    architecture/
    docs/
    deployment/
```

and separate repositories such as:

```text
lakehouse-ingestion
lakehouse-streaming
lakehouse-processing
lakehouse-serving
lakehouse-governance
lakehouse-observability
lakehouse-infrastructure
```

But do NOT automatically create all of these.

First determine the actual dependency boundaries.

A subproject should have:

* a clear responsibility
* independent testing
* clear interfaces
* meaningful documentation
* reproducible local execution
* a reason to exist independently

Avoid creating microservices/micro-repositories simply for appearance.

---

# 21. Repository Architecture

Propose the repository structure only after determining the platform boundaries.

For each repository/project specify:

* purpose
* ownership boundary
* inputs
* outputs
* APIs/interfaces
* dependencies
* configuration
* tests
* CI
* documentation
* deployment mechanism

The final repository structure should be something an engineer could realistically maintain.

---

# 22. Documentation

Documentation is part of the deliverable.

Produce:

### Architecture

* system architecture
* data-flow diagrams
* deployment architecture
* network architecture

### Data

* source catalogue
* schema documentation
* data contracts
* lineage
* data-quality rules

### Operations

* deployment guide
* runbook
* incident response
* troubleshooting
* backup/recovery
* scaling

### Engineering

* ADRs
* technology decisions
* trade-offs
* performance benchmarks
* failure testing

### User/consumer

* how analysts query data
* example SQL
* data catalogue
* dashboard documentation

---

# 23. Architecture Decision Records

For every major technology decision, create an ADR.

Examples:

```text
ADR-001: Why Apache Iceberg?
ADR-002: Why Kafka?
ADR-003: Why Flink?
ADR-004: Why Spark?
ADR-005: Why Polaris?
ADR-006: Why ClickHouse?
ADR-007: Why Dagster?
ADR-008: Why MinIO locally?
ADR-009: Why Kubernetes?
ADR-010: Why AWS/EKS?
```

Also document rejected alternatives.

For example:

```text
Kafka vs Redpanda
Flink vs Spark Streaming
Dagster vs Airflow
Iceberg vs Delta Lake
ClickHouse vs Trino
MinIO vs local filesystem
Polaris vs alternative catalogs
```

The point is to demonstrate engineering judgment, not tool collecting.

---

# 24. Performance Engineering

Performance must be measurable.

Define benchmarks for:

* ingestion throughput
* streaming throughput
* end-to-end latency
* batch processing time
* query latency
* concurrent queries
* file counts
* compaction effectiveness
* resource utilization

For each optimization:

```text
Baseline
↓
Hypothesis
↓
Change
↓
Benchmark
↓
Result
↓
Trade-off
```

Never invent benchmark results.

---

# 25. Cost Engineering

Because the target job mentions operating platforms at scale, include cost reasoning.

Evaluate:

* object storage cost
* compute cost
* Kafka cost
* EKS cost
* data transfer
* query cost
* storage growth
* compaction cost

Document:

> What would become expensive first if this platform grew 10×?

And:

> What architectural change would be required at 100×?

Do not actually build a 100× system.

Demonstrate that you understand the scaling problem.

---

# 26. Data Consumer Layer

The platform should eventually expose useful analytical products.

Examples:

* operational analytics
* time-series analytics
* dimensional analytics
* customer/order behaviour
* geographic analytics
* event analytics

Use an open-source BI tool such as Superset if appropriate.

Power BI can remain an optional external consumer to demonstrate Microsoft ecosystem compatibility.

The analytical layer should be driven by actual questions that the datasets can answer.

---

# 27. Dataset Selection Output

Before implementation begins, produce a dataset-selection report.

For every candidate dataset:

```text
Dataset
Source
License
Size
Format
Update frequency
Tables/files
Relationships
Timestamp characteristics
Potential CDC/event simulation
Data-quality problems
Streaming suitability
Batch suitability
Lakehouse suitability
Analytical suitability
Expected engineering challenges
Target-job capabilities demonstrated
```

Then select the smallest coherent dataset combination that provides broad coverage.

Do not select datasets merely because they are large.

Complexity should come from realistic engineering problems, not artificially inflating row counts.

---

# 28. Final Architecture Requirement

The final architecture should ideally demonstrate this overall capability:

```text
                  ┌──────────────────┐
                  │ Public Datasets  │
                  │ APIs / DB / CDC  │
                  │ Event Sources    │
                  └────────┬─────────┘
                           │
                    Ingestion Layer
                           │
              ┌────────────┴────────────┐
              │                         │
            Batch                    Streaming
              │                         │
            Spark                  Kafka + Flink
              │                         │
              └────────────┬────────────┘
                           │
                    Apache Iceberg
                           │
                  Polaris REST Catalog
                           │
             ┌─────────────┴─────────────┐
             │                           │
          Trino                     ClickHouse
             │                           │
             └─────────────┬─────────────┘
                           │
                     Data Consumers
                           │
                     Superset / SQL


Surrounding the platform:

Dagster
Data Quality
OpenLineage / Lineage
Prometheus
Grafana
Alertmanager
IAM / RBAC
Terraform
Helm
Kubernetes
AWS / EKS / S3 / RDS / VPC
```

This diagram is a starting hypothesis, not a fixed requirement.

Modify it if research shows that another architecture is technically superior.

---

# 29. Critical Constraint: Avoid Technology Sprawl

Do NOT implement technologies simply because they appear in:

* Awesome Big Data
* Awesome Data Engineering
* Awesome Streaming
* Awesome Spark
* Kaggle
* job descriptions

The goal is not:

> "I used 40 technologies."

The goal is:

> "I built a coherent platform that solves realistic data-engineering problems and can explain every architectural decision."

If two technologies solve the same problem, normally choose one.

If a second technology is included, there must be a concrete reason such as:

* different workload
* interoperability demonstration
* migration scenario
* comparison benchmark
* target-job alignment

---

# 30. Existing Olist Project

I already have an Olist lakehouse project containing substantial work around:

* PostgreSQL
* Debezium
* Kafka/KRaft
* Apicurio
* PySpark
* Iceberg
* MinIO
* Polaris
* Trino
* SCD2
* CDC

Do not automatically throw this work away.

Evaluate what can be:

1. reused
2. generalized
3. refactored
4. extracted into reusable infrastructure
5. replaced because it does not fit the new platform

The new platform should build on existing work where technically sensible rather than duplicating everything.

---

# 31. Definition of "Complete"

The project is NOT complete merely because all services start.

A capability is complete only when it has:

* implementation
* automated test
* realistic data
* documentation
* observability
* failure handling where applicable
* reproducible deployment
* measurable acceptance criteria

For every major component define a Definition of Done.

Example:

```text
Kafka ingestion is complete when:

[ ] producer/source implemented
[ ] schema defined
[ ] messages validated
[ ] retries handled
[ ] duplicate handling documented
[ ] consumer lag observable
[ ] failure recovery tested
[ ] integration tests pass
[ ] documentation exists
[ ] deployment is reproducible
```

---

# 32. Final Deliverables

The planning phase should produce:

1. Target-job requirements matrix
2. Dataset research
3. Selected dataset architecture
4. System architecture
5. Data architecture
6. Technology-selection matrix
7. Repository decomposition
8. Local development architecture
9. Cloud architecture
10. Security model
11. Governance model
12. Data-quality strategy
13. Observability strategy
14. Reliability strategy
15. Performance benchmark strategy
16. Testing strategy
17. CI/CD strategy
18. Infrastructure/IaC strategy
19. Phased implementation roadmap
20. Definition of Done for every phase
21. Incident laboratory design
22. Interview/demo scenarios
23. Final portfolio presentation strategy

---

# 33. Implementation Strategy

Do NOT attempt to build everything simultaneously.

Create a dependency-aware roadmap.

Each phase should produce a working system.

Prefer:

```text
Phase 0
Research + architecture

Phase 1
Core ingestion + Iceberg

Phase 2
Batch processing

Phase 3
Streaming + Flink

Phase 4
Serving + ClickHouse

Phase 5
Orchestration + DQ

Phase 6
Governance + lineage

Phase 7
Observability + alerting

Phase 8
Kubernetes + Helm

Phase 9
Terraform + AWS

Phase 10
Performance + failure engineering

Phase 11
Hardening + documentation
```

Adjust the phases based on actual dependencies.

---

# 34. Optimize for Employability

This project is ultimately a portfolio project intended to improve my ability to demonstrate senior-level data-engineering concepts despite not having six years of professional data-engineering experience.

Therefore prioritize capabilities that are:

* directly relevant to the target job
* technically substantial
* explainable in an interview
* demonstrable with evidence
* measurable
* reusable across other data-engineering jobs

Do not optimize for GitHub star count, number of services, or architectural complexity for its own sake.

The project should allow me to explain things such as:

> "Why Iceberg?"

> "Why Kafka?"

> "Why Flink instead of Spark Streaming?"

> "Why ClickHouse?"

> "How do you handle late events?"

> "How do you guarantee idempotency?"

> "How do you recover from failure?"

> "How do you detect data corruption?"

> "How do you handle schema evolution?"

> "How do you optimize an Iceberg table?"

> "How do you optimize a ClickHouse query?"

> "How do you monitor Kafka/Flink/Spark?"

> "How would you deploy this to EKS?"

> "How would this architecture change at 10× or 100× scale?"

> "What would you remove if cost became a problem?"

Every major architectural decision should therefore be defensible.

---

# 35. First Task

Do NOT start coding yet.

First produce a **Research & Architecture Proposal** containing:

1. Detailed interpretation of the target job
2. Capability matrix
3. Dataset candidates from Awesome Public Datasets and Kaggle
4. Dataset comparison
5. Recommended dataset combination
6. Why those datasets create realistic engineering problems
7. Proposed end-to-end architecture
8. Technology-selection matrix
9. What should be reused from my existing Olist project
10. What should be new
11. Proposed repository/subproject boundaries
12. Local architecture
13. AWS architecture
14. Data-flow diagrams
15. Major risks
16. Complexity assessment
17. Implementation phases
18. Definition of Done for each phase
19. Benchmark plan
20. Incident/failure-testing plan
21. Final mapping back to every important requirement in the target job

Only after this proposal is reviewed should implementation begin.

The guiding principle is:

> **Build a coherent, production-minded, vendor-neutral lakehouse platform that demonstrates real engineering depth—not a technology museum.**
