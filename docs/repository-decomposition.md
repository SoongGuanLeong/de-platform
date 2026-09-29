# Repository decomposition: one repository, path-first, with strict domain boundaries

**Status:** the repository-boundaries decision behind [ADR-0026](adr/0026-one-repository-path-first.md). It answers the mission's Final Deliverables item 7 and its sections 20 and 21, and it is the artefact the proposal's repository/subproject boundaries come from.
**Evidence:** ticket [Repository decomposition](https://github.com/SoongGuanLeong/de-platform/issues/16) on map [#9](https://github.com/SoongGuanLeong/de-platform/issues/9).

## The decision

**One repository, `de-platform`, holding both the proposal suite and the platform code. The top-level split is by engineering path, not by data layer. The two spines are a second-level dimension. Every path depends on one shared core, and the commerce/network boundary is absolute.**

One repository, because the platform is one system rather than a set of independently deployable services. Every path depends on the same Iceberg catalog, the same `contracts/<spine>/<table>.yml` set and the same budget and capability ids, so a capability split would force those shared artefacts to be duplicated or versioned across repositories, which is the arbitrary split the mission's section 20 forbids. A reviewer should also be able to follow an ADR in `docs/adr/` to the code it justifies without changing clone, and [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md)'s provenance claim ("every line in this repository is authored here") is far easier to keep true when there is one repository to make the claim about.

Path-first, because the mission's own test for a real subproject is independent testing and reproducible local execution, and the boundary where that is true here is the toolchain and runtime: Flink is a Java streaming service with a checkpoint lifecycle, the batch jobs are PySpark run as Dagster assets, serving is ClickHouse SQL plus a materialisation, and the platform is compose, OCI images, Helm and OpenTofu. That is four different test runners and four different lint sets. The spine is a genuine *domain* boundary ([ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md)) but not an *engineering* one, since both spines use the same PySpark test runner, so a spine-first split would buy no independent testing while smearing the Java/Python boundary.

The mission's suggested `lakehouse-ingestion` / `lakehouse-streaming` / ... repository list is explicitly not adopted, on the mission's own instruction not to create micro-repositories for appearance. The dependency boundaries do not isolate: every one of those would depend on the same catalog, contracts and budgets.

## The layout

```text
de-platform/
├── PROPOSAL.md                  the proposal index
├── CONTEXT.md                   the glossary
├── pyproject.toml               uv workspace root
├── uv.lock                      one lock for the workspace
├── .importlinter                the dependency-boundary rules
├── .sqlfluff  .yamllint         repo-wide lint config
├── docs/                        the proposal suite: specs, adr/, evidence/, research/
├── contracts/<spine>/<table>.yml   data only, no executable content
├── platform/                    shared Python core            (distribution)
├── ingestion/                   Debezium config, OLTP DDL and load, RIPE collector  (distribution)
│   ├── commerce/                Debezium connector, OLTP DDL, staging and load
│   └── network/                 the RIPE Atlas collector, the ONSPD loader
├── streaming/                   Flink jobs (Java, one Gradle project)
│   ├── commerce/                the CDC ingestion job and the CDC serving job
│   └── network/                 the RIPE job
├── batch/                       PySpark jobs                  (distribution)
│   ├── commerce/                TPC-H silver and gold, SCD2, MERGE, compaction
│   └── network/                 ONSPD SCD2, the RIPE rollups, the spatial join
├── serving/                     ClickHouse DDL and views, serving-writers.yaml
├── governance/                  the DQ framework, the gate, retention, validators  (distribution)
├── orchestration/               the Dagster code location, the composition root   (distribution)
├── observability/               Prometheus rules, Grafana dashboards as code
├── deployment/                  compose files, OCI images, Helm charts, OpenTofu
└── tests/                       profile-scoped tests that need the stack
```

Four top-level directories were added to the mission's own sketch: `contracts/`, `governance/`, `orchestration/` and `deployment/`. They are separate because they have separate owners. `contracts/` is data, `governance/` is the framework that reads it, `orchestration/` is the composition root, and `deployment/` is a different toolchain (YAML, HCL, Dockerfile) from the shared Python core in `platform/`.

## The packaging model

One `uv` workspace, one Python **distribution** per path that contains Python: `platform/`, `ingestion/`, `batch/`, `governance/` and `orchestration/`. `streaming/` is a single Gradle project with three job classes, since the three jobs share one runtime image and one Iceberg runtime dependency.

The packaging graph is the first line of defence: a distribution that is not declared as a dependency cannot be imported, so the inter-path rules become structural rather than conventional. `import-linter` carries the rules the packaging graph cannot express, which are the intra-distribution ones: the commerce/network split inside `batch/` and `ingestion/`, and `platform/` staying a leaf.

`serving/` and `observability/` get no distribution, because they hold SQL, YAML and JSON rather than code. Adding one later is a two-line change to the workspace, so this is a reversible call.

## The boundary rules

The rules are split by whether a tool can decide them. A rule no tool can check is a written obligation and is labelled as one, rather than assumed enforced.

| # | Rule | Enforcement |
|---|---|---|
| 1 | `commerce` must not import `network`, in any path, in either direction | `import-linter`, CI |
| 2 | No path distribution may import another path's code; cross-path communication is only through `contracts/`, `platform/` or the catalog | packaging graph, CI |
| 3 | `platform/` must not import any path (it is a leaf) | packaging graph, CI |
| 4 | `governance/`'s framework must not import a path; paths may import the framework | packaging graph, CI |
| 5 | No `.ipynb` under any code path, and no pipeline logic in a notebook anywhere | CI path check |
| 6 | No shared Iceberg writer abstraction between batch and streaming | review |
| 7 | No shared conformed dimension; geography belongs to the network spine | review |
| 8 | Exactly one writer per serving copy, the streaming exception named | review, with `serving/serving-writers.yaml` making it auditable |

Rule 5 is the prior repository's failure made into a check. Its real pipeline lived in 17 notebooks while `src/` held only silver and gold logic and `jobs/` held one truncated dead file, so the module boundary was not a boundary anything could test or import. Rules 6 to 8 are judgements about write semantics and ownership that no linter can make, so they stay review obligations, but rule 8's `serving/serving-writers.yaml` at least makes "one writer per copy" auditable rather than only reviewable.

## What the paths share, and what they must never share

**Shared, defined exactly once, consumed by all paths:**

- the contract files, from which the `schema` check is generated ([ADR-0019](adr/0019-contracts-are-contract-first-and-break-by-version.md));
- one catalog and warehouse connection module, reached only through the Iceberg REST specification so the Lakekeeper fallback stays a URI and credential change ([ADR-0010](adr/0010-polaris-behind-the-rest-spec.md));
- the budget ids in `docs/budgets.yaml` and the capability-register ids in `docs/completion-bar.yaml`;
- the `catalog.layer.table` and topic naming conventions, including the time-bounded CDC retention of [ADR-0018](adr/0018-time-bounded-kafka-retention-for-cdc.md);
- the OpenLineage emission configuration and the dataset namespace;
- the portable compose subset and the OCI image definitions, both owned by `deployment/`.

**Never shared:**

- transformation code across the spines, including any conformed dimension, since geography lives only in the network spine ([ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md));
- an Iceberg *writer*, because the batch path writes position deletes through `MERGE INTO` while the streaming path writes key-only equality deletes through the Flink upsert sink, so the two share the table's format version and equality fields and never the writer code;
- a serving copy's writer, with the one named streaming exception ([ADR-0012](adr/0012-flink-writes-the-serving-copy.md));
- pipeline logic in a notebook.

## Ownership of the shared artefacts

`contracts/` holds data only: the per-table YAML. `governance/` holds the framework and the validators: the check kinds and severities, the gate wiring, the quarantine writer and the result-store schema, the retention and erasure logic, the data-class definitions, the contract validator and breaking-change check, the completion-bar register and budget validator, and the layout-agreement validator that keeps the consolidated architecture tables in step with the per-domain specs they restate. `platform/` holds the shared Python core.

**Check instances live with the asset they gate**, in the path package, not in `governance/`. This follows from [ADR-0016](adr/0016-gate-on-input-and-promote-through-a-branch.md): an input-evaluable check has to sit upstream of the asset it stops, so the instance is bound to the asset and only the framework is shared.

## Orchestration and deployment

`orchestration/` is the repository's **composition root**: the single Dagster code location, the only module permitted to import both spines, and a place that holds no business logic. It is what lets the commerce/network prohibition stay absolute everywhere else while the orchestrator still schedules both. This matches the division of labour already fixed in [`docs/technology-selection.md`](technology-selection.md): Dagster owns the batch jobs, the data-quality gate, retention and snapshot expiry, the serving materialisation and the streaming job's deploy, restart and savepoint operations, but not the running Flink runtime.

`deployment/` holds the compose files, the OCI image definitions, the Helm charts and the OpenTofu. It is separate from `platform/` because it is a different toolchain and a different owner, and because the compose subset is the executable contract of [ADR-0007](adr/0007-completion-bar-as-a-gate.md) rather than a helper of the Python core.

## Tests

Unit tests are **co-located inside each distribution**, which is what makes "run this distribution's tests" a real command and what lets the packaging graph and the boundary rules point at the same boundary. The tests that need the stack are not unit tests: they are the completion bar's **profiles** (smoke, then the path-scoped batch and streaming halves, then the single-component benchmark), so they live in the root `tests/` organised by profile, and they are the runs [ADR-0007](adr/0007-completion-bar-as-a-gate.md) deliberately keeps out of CI. Exploratory notebooks, if any, live outside every code path.

## The CI consequence

CI runs the cheap structural checks on every pull request, and never re-runs evidence, because the load-bearing evidence needs the streaming or benchmark profile and cannot run at 7 to 8 GB.

**Runs:** the boundary rules 1 to 5; the contract validator and breaking-change check; the completion-bar register and budget validation; the layout-agreement check; the compose-subset lint; `tofu validate`; `helm lint` and `helm template`; `promtool check rules`; `sqlfluff`; `yamllint`; `actionlint`; and the per-distribution unit tests.

**Does not run:** any part of the stack, any benchmark, any streaming job, any evidence re-run. Those stay human-judged from the committed raw artifacts, per ADR-0007.

Linters are one pinned version per toolchain, with the configs at the root: `ruff` for Python (pinned, unlike the prior repository's unpinned linter whose green badge was an artifact rather than a gate), `import-linter` for the boundaries, Spotless with google-java-format for the Flink jobs, `sqlfluff` for SQL, `yamllint` for compose and contracts, and `actionlint` for the workflows. The compose-subset lint is a repository script in `deployment/`, since no off-the-shelf tool enforces a custom subset.

Path filters are **fail-safe**: the cheap validators always run, and the heavier per-path test jobs are path-filtered. The per-job input sets and their overrides are stated in [the CI/CD strategy](ci-cd-strategy.md) section 5, and the principle is that a job's filter includes every shared artefact that job really consumes, so a change to a shared artefact can never skip a check it invalidates.

## How a capability instance points at its module

Each entry in `docs/completion-bar.yaml` carries a `module` field naming the distribution that implements it, and CI asserts the module resolves and is importable, alongside the field and link checks ADR-0007 already requires. The capability **classes** become a machine-readable list, so "every class has a representative instance" is checkable without parsing prose. There is deliberately **no bijection** in either direction: neither "every module appears in the register" nor its converse is achievable, and claiming either would be exactly the kind of unfalsifiable completeness claim this effort avoids. The register ships empty, so this is a convention plus a gate that activates as entries land.

## What the prior repository teaches

The prior repository was already a single repository, and its top-level shape (`src/pipeline/batch/{common,silver,gold}`, `infra/docker/{cdc_stack,lakehouse_stack}`, `configs/`, `notebooks/`, `jobs/`) was reasonable. Repository count was never its problem. The problem was that the boundary between "notebook" and "module" was not a boundary: the pipeline was orchestrated by 17 notebooks, `src/` held only silver and gold logic, and `jobs/` held one truncated file, so nothing could be imported or tested end to end. That is the lesson this decomposition is built around, and it is why rule 5 exists. Two secondary patterns are worth keeping: the per-stack compose split survives as the profile-based compose files in `deployment/`, and the single `configs/` location survives as the shared `platform/` core.

## Honest gaps

- **The layout is a plan, not a build.** No directory in this document exists yet. The map is planning-only.
- **The packaging model is unexercised.** The claim that the packaging graph enforces rules 1 to 4 has not been run, because there is no code to run it against.
- **`sqlfluff`'s ClickHouse dialect is incomplete.** ClickHouse `PROJECTION` clauses in `CREATE TABLE`, `ALTER TABLE` and `GRANT` are unparsable (sqlfluff issue 8583, September 2026), so `sqlfluff` covers ClickHouse query SQL and the subset of DDL it parses. The DDL's real validation is execution against the pinned ClickHouse in the serving profile, which is a behaviour rather than a signal and is consistent with the completion bar's split. Recorded as a documented limitation rather than a reason to change the tool.
- **The lint tool list is proposed, not measured.** Whether every named linter has a usable configuration for its target is unverified except for the `sqlfluff` finding above.
- **The full CI/CD strategy and the testing strategy are not settled here.** This document fixes the layout's CI consequence and the test *location*, not the pipeline's job graph, branch protection, delivery path or test levels. Those are recorded on the map.
