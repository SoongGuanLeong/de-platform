# 12 - Orchestrator comparison: which workflow engine should the platform run?

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Question answered:** which orchestrator should the platform use, judged on merit, given that the target JD names Dagster and the longevity audit already records Dagster as PASS-WITH-CAUTION after Prefect acquired Dagster Labs on 2026-07-13?
**Candidates compared:** Dagster, Apache Airflow, Prefect, Argo Workflows, Flyte.
**Decision context:** the JD names Dagster in its stack and lists workflow orchestration as a nice-to-have ("Dagster, Airflow, or equivalent"), explicitly adding that "if you've done ... Airflow instead of Dagster, that transfers" [S42]. The requirements matrix already binds four rows to an orchestrator: M1 (OpenLineage emitted by Dagster), M11 (lineage from Dagster, Spark, Flink), M12 (a Dagster retention asset), M13 (a Dagster gate that stops or quarantines), M14 (idempotent, re-runnable, backfillable DAGs) [S40]. Mission section 10 says to use Dagster "if it remains the best fit ... Or evaluate alternatives such as Airflow if research shows a stronger reason" [S41]. The lineage research (doc 13) already fixed the emission contract as OpenLineage and assumed Dagster as the emitter [S44].

---

## 0. Method, envelope and rubric

**Primary sources only.** Every factual claim below is traced to one of: the project's own documentation, its source repository at a named release, its published package metadata (PyPI, the GitHub releases API), a foundation's own announcement, or the vendor's own press page. Where a claim is my analysis rather than a sourced fact, it is labelled **inference**.

**Operational envelope.** 12 CPU, ~7-8 GB free RAM, 231 GB disk, podman 6.1.x (no Docker), local-first [S39 section 2, S40 section 0]. A component that cannot run locally is a problem. I did **not** run any orchestrator for this comparison and I measured no RSS; every footprint statement is derived from the project's own documented component list and storage defaults, and is labelled as such. No benchmark or memory number here is measured.

**Longevity rubric** (from doc 03): foundation governance preferred; company-backed with disclosed funding **and** a commercial incentive acceptable; observable activity (not archived, not maintenance-only, releases/commits in the last ~12 months) is a hard floor [S39 section 0].

**One correction to the brief's framing.** The brief says "the JD names Dagster" as if that settles the stack. The JD's *requirements* section does not require any orchestrator; orchestration appears only under "Nice to have" as "Dagster, Airflow, or equivalent", and the About-the-role paragraph is the only place the stack names Dagster [S42]. A JD mention is therefore weak evidence and is not treated as a reason to pick a tool. It is used only in section 3.9 as a portfolio tiebreaker.

---

## 1. Verdict summary

| Candidate | Licence | Governance / backing | Latest activity | Asset model fit | OpenLineage emission | Local footprint (documented) | Verdict |
|---|---|---|---|---|---|---|---|
| **Dagster** | Apache-2.0 | company, **Dagster Labs acquired by Prefect 2026-07-13** | 1.13.24, **2026-09-21** (weekly) | **Best**: assets, rich partitions, first-class blocking asset checks | community package, v0.2.1 (2026-05-22) | 2-3 services; SQLite default; light | **ADOPT** |
| **Apache Airflow** | Apache-2.0 | **ASF Top-Level Project since 2019-01-08** | 3.3.2, **2026-09-17** | Good but weaker: assets + asset partitions (3.2.0); **no asset checks** | **first-party provider** 2.20.1 | 4+ services; metadata DB required; moderate | **FALLBACK** |
| **Prefect** | Apache-2.0 | company, now owns Dagster; disclosed $11.5M Series A (2021-02-09) | 3.8.7, **2026-09-26** + nightlies | Weak: assets, but health is visual-only; no partitions, no checks | **none found** | server + services; SQLite single-server; light | **REJECT** |
| **Argo Workflows** | Apache-2.0 | **CNCF Graduated 2022-12-06** | v4.1.4 / v4.0.12, **2026-09-18** | None: Kubernetes CRD, templates | **none found** | **requires a Kubernetes cluster** | **REJECT** |
| **Flyte** | Apache-2.0 | **LF AI & Data Graduated**; Union.ai commercial | v2.0.50, **2026-09-24** | Weak: typed tasks/runs; no asset/partition/check model | **none found** | devbox cluster (containers); production k8s | **REJECT** |

**Headline answer.** Dagster is still the right pick **on merit**. It wins the dimensions that actually decide this platform (asset model, partitions, a DQ gate that blocks, Python-first, local footprint), and the acquisition does not cross the rejection threshold because the licence is Apache-2.0, activity is emphatic, and orchestration is the cheapest layer to replace. Airflow is the **safer longevity bet** and is the named fallback, with a documented switch trigger. It loses on fit, not on health.

---

## 2. What the orchestrator would own here

Mission section 10 and the requirements matrix give the orchestrator five concrete jobs. The comparison below is scoped to these, not to generic "workflow orchestration" [S40, S41].

1. **Batch Spark jobs** (M4): run the bronze -> silver -> gold PySpark jobs, with dependencies, retries and backfills.
2. **A data-quality gate that must actually stop or quarantine** (M13): each check declares a severity (warn / quarantine / fail); a critical failure must block the downstream run, and a corrupted batch must never reach gold. This is named in the matrix as one of the five interview-critical items ("governance that stops something").
3. **Retention** (M12): a policy per data class, applied, with a dry run, and provably not over-applied.
4. **Serving materialisation** (M7): materialise the ClickHouse MergeTree tables from Iceberg, with dependencies and re-runnability.
5. **Streaming-job lifecycle operations** (M2/M3): start, stop, restart and observe Flink jobs. This is operational, not asset-shaped, and every candidate needs glue for it.

The asset model matters because jobs 1, 3 and 4 are naturally expressed as "produce this data asset for this partition"; the DQ gate matters because job 2 must halt a graph, not merely record a red tick.

---

## 3. Dimension-by-dimension

### 3.1 Programming and asset model, partitions, and asset checks

**Dagster.** Dagster's model is software-defined assets: you declare the data that should exist and let the system work out how to produce it [S25]. Assets are Python objects with an asset graph, metadata, owners and kinds.

- **Partitions.** Four first-class kinds: time-based, static, two-dimensional (`MultiPartitionsDefinition`, key form `2024-08-01|us`), and dynamic (keys added at runtime). Partition mappings connect an upstream partition scheme to a downstream one, and backfills are partition-aware [S14]. The docs recommend staying under 100,000 partitions per asset for UI load [S14].
- **Asset checks.** `@asset_check` and `@multi_asset_check` are first-class. By default a job targeting an asset also runs its checks. Crucially for M13, "By default, if a parent's asset check fails during a run, the run will continue and downstream assets will be materialized. To prevent this behavior, set the `blocking` argument to `True`" [S13]. Checks carry severity levels and can be scheduled separately from the asset job (for example, all checks once a day with an alert) [S13]. This is the exact primitive M13 asks for.
- **Retention.** Dagster has **no built-in retention policy**: "Dagster does not automatically clean up partition metadata when the underlying data is deleted, and there is no built-in retention policy that coordinates data deletion with partition management." The documented pattern pairs a data-deletion sensor with a partition-synchronisation sensor over dynamic partitions [S15]. That is a primitive plus a recipe, not a feature, and it must be built for M12.

**Apache Airflow.** The model is a DAG of tasks (TaskFlow `@task` / `@dag`, or classic operators and hooks).

- **Assets.** Airflow 3 assets are "a logical grouping of data. Upstream producer tasks can update assets, and asset updates contribute to scheduling downstream consumer Dags", identified by URI. The concept was added in 2.4 and renamed from "Dataset" in 3.0 [S5]. Airflow treats the URI as an opaque string: it "makes no assumptions about the content or location of the data" [S5].
- **Asset partitions.** Added in **3.2.0**: "Asset events can include a `partition_key` to make it _partitioned_." A producer uses `CronPartitionTimetable`; a consumer uses `PartitionedAssetTimetable`; the docs distinguish pre-determined from runtime partitioning and describe rollup mappers, wait policies and segment rollups [S5]. So Airflow has closed much of the partition gap as of 3.2.0.
- **Asset checks: none.** I found no first-class asset-check concept in the Airflow 3.3.2 asset documentation; the word "check" appears only in example task code where the user writes their own test [S5]. Airflow's gate mechanism is task failure plus trigger rules: the default `trigger_rule` is `all_success`, and a failed upstream task causes "a cascaded skip" to downstream tasks [S7]. That is a real, if blunt, gate: a DQ task that raises stops the pipeline. It is not an asset check with severity and blocking semantics.

**Prefect.** The model is flows and tasks. Prefect 3 assets are "objects your workflows produce", keyed by URI, with three states (materialized / referenced / external), declared with a `@materialize` decorator; dependencies are inferred from the task graph or declared with `asset_deps` [S23]. There is **no partition concept** in the assets documentation, and **no asset-check concept**. Asset health is explicitly a presentation-only feature: "Currently asset health provides a _visual_ indicator of the operational status of data artifacts based on their most recent materialization attempt ... Soon these statuses will be backed by a corresponding event" [S23]. For M13 that is the opposite of what is needed: the health signal is not yet an event, and nothing blocks on it.

**Argo Workflows.** The model is a Kubernetes custom resource: "The Workflow spec is a list of templates and an entrypoint. templates can be loosely thought of as 'functions'" [S30]. Workflows are authored as YAML, executed as pods, and templated with steps or DAG tasks. There is no data-asset model, no partition model and no check model. A DQ gate is a step that exits non-zero; failure propagation is a step-level concern.

**Flyte.** The model is typed Python tasks in a `TaskEnvironment`, composed by calling tasks from tasks; there is no `@workflow` decorator in Flyte 2 [S33 search result, union.ai docs]. It has caching (`cache="auto"`), retries, timeouts, triggers, traces and fanout [S33 search result]. It is task/run-oriented: no data-asset graph, no partitions, no asset checks. It is explicitly built on Kubernetes [S37].

### 3.2 OpenLineage emission support

The platform emits OpenLineage; doc 13 fixed that contract and assumed Dagster as the emitter [S44]. Emission support differs sharply by candidate, and this is the single clearest technical differentiator after the asset model.

| Candidate | Integration | Owner | Version / date | Status |
|---|---|---|---|---|
| **Airflow** | `apache-airflow-providers-openlineage` | **Apache Airflow project (first-party)** | **2.20.1**, 2026-08-23 (repo README tracks 2.20.2) [S9, S8] | Actively maintained inside the Airflow monorepo; listed in OpenLineage's own integrations docs [S38] |
| **Dagster** | `dagster-openlineage` | **community**, hosted in `dagster-io/community-integrations` | **0.2.1**, 2026-05-22 [S18, S19, S20] | Dagster's own docs mark it "community-supported"; emits asset-centric events including schema, column-lineage, data-quality-assertion and partition nominal-time facets [S18] |
| **Prefect** | none | - | - | No `prefect-openlineage` package on PyPI (HTTP 404); not listed in OpenLineage's integrations docs [S38] |
| **Argo Workflows** | none | - | - | Not listed in OpenLineage's integrations docs [S38] |
| **Flyte** | none | - | - | Not listed in OpenLineage's integrations docs [S38] |

The OpenLineage project's own integrations tree lists exactly `airflow`, `dbt`, `feast`, `flink`, `great-expectations`, `hive`, `presto` and `spark` [S38]. Dagster's integration is community-owned and not in that list; its docs are first-party but label the package community-supported [S18]. This is a point **in Airflow's favour**: it is the only candidate with a first-party OpenLineage provider maintained by the orchestrator's own project. For Dagster, M11's "OpenLineage emitted from Dagster" rests on a community package at v0.2.1, which is a real dependency risk that the current plan does not record.

**Inference:** for a platform whose lineage requirement is load-bearing (M11 is in the top-five interview list), Airflow's first-party emitter is materially safer than Dagster's community package. If Dagster is chosen, the plan should name `dagster-openlineage` v0.2.1 explicitly as the emitter and treat it as a watched dependency.

**Cross-reference:** the lineage research has independently verified this finding and folded it into `13-lineage-backend-comparison.md` section 2.1 ("The emitter leg is not uniform"), which names Spark and Flink as the primary emitters and Dagster lineage as secondary. The backend recommendation there (Marquez, lean) is unaffected, because Marquez consumes spec-conformant events regardless of which emitter produced them.

### 3.3 Scope: the five jobs

| Job | Dagster | Airflow | Prefect | Argo | Flyte |
|---|---|---|---|---|---|
| Batch Spark (M4) | Strong: assets + backfills | Strong: operators + backfills | Adequate: flows/tasks | Strong: k8s jobs | Strong: typed tasks |
| DQ gate that blocks (M13) | **Strongest**: blocking asset checks + severity | Workable: failing task + default `all_success` skip | Workable: failing task blocks downstream | Workable: failing step | Workable: failing task |
| Retention (M12) | Primitives + documented sensor recipe, no built-in | Operators/sensors, no built-in | No | No | No |
| Serving materialisation (M7) | Strong: assets with dependencies | Strong: operators | Adequate | Strong: k8s jobs | Adequate |
| Streaming-job lifecycle (M2/M3) | Ops/jobs + sensors; can launch processes or k8s pods | Mature operator/sensor ecosystem; strongest glue | Tasks/flows | **Strongest k8s-native** job lifecycle | Tasks |

The pattern: for the **data-shaped** jobs (batch, DQ gate, retention, serving) Dagster and Airflow are the two real contenders, and Dagster is crisper on the DQ gate and partitions while Airflow is richer on operator glue. For the **ops-shaped** streaming lifecycle, Argo would be strongest if the platform were Kubernetes-native, but the platform is local-first with podman, and Argo requires a cluster (section 3.5). No candidate manages Flink job lifecycle natively; all need glue.

### 3.4 Failure propagation

- **Dagster:** an asset/op failure blocks downstream assets. Asset checks are non-blocking by default; `blocking=True` makes a failed check prevent downstream materialisation [S13].
- **Airflow:** the default `trigger_rule` is `all_success`; a failed upstream task cascades a skip to downstream tasks [S7]. Other trigger rules (`all_done`, `one_done`, `none_failed`, etc.) are configurable [S7].
- **Prefect:** state-based; a failed task blocks downstream by default, with configurable retries.
- **Argo:** a failed step fails the workflow; `continueOn` and retry strategies are configurable per template.
- **Flyte:** a failed task fails its node and the workflow, with configurable retries.

All five can stop a pipeline on failure. The differentiator is not "can it stop" but "does it model a data-quality assertion as a first-class object with severity and blocking semantics". Only Dagster does.

### 3.5 Local footprint on podman in ~7-8 GB free RAM

All figures are the projects' own documented component lists and storage defaults. **No RSS was measured.**

- **Dagster.** A full OSS deployment has "three long-running services": `dagster-webserver`, `dagster-daemon`, and a code-location server. The default run storage is `SqliteRunStorage`, swappable for Postgres [S17]. For local development, `dg dev` "launches the Dagster UI and the Dagster daemon", using an ephemeral temporary directory unless `DAGSTER_HOME` is set [S16]. So the local floor is two Python processes plus SQLite, with Postgres optional. Light.
- **Apache Airflow.** The runtime components are a scheduler (which contains the executor), a DAG processor, an API server, and a metadata database that "is required for Airflow to work", usually PostgreSQL or MySQL, plus workers [S4]. `airflow standalone` "initializes the database, creates a user, and starts all components" in one command for local use [S6-search/start page]. Even locally the metadata database is mandatory. Moderate.
- **Prefect.** A single self-hosted server can run on SQLite; multi-server deployments "require PostgreSQL database version 14.9 or higher (SQLite does not support multi-server synchronization)" plus Redis [S24]. Light for a single server.
- **Argo Workflows.** "Before installing Argo, you need a Kubernetes cluster and kubectl configured" [S29]. On this host that means kind or k3s under podman, which is heavy, awkward, and competes for the same RAM as Kafka, Flink, ClickHouse and Polaris. Poor fit.
- **Flyte.** Flyte 2 has a local devbox: `pip install flyte; flyte start devbox` runs "a real local Flyte cluster" that "spins up the scheduler, object store, and UI locally" at `localhost:30080` [S35]. That is a genuine local option, but it is a cluster-in-containers, and production is Kubernetes/Union.ai [S37]. Moderate-to-heavy.

**Verdict on envelope:** Dagster, Airflow and Prefect all fit locally. Argo is the worst fit because it mandates Kubernetes. Flyte is feasible via devbox but is the heaviest of the Python options and is cluster-shaped.

### 3.6 Licence, governance and longevity (dated)

| Candidate | Licence | Steward | Evidence of backing | Latest release |
|---|---|---|---|---|
| **Dagster** | Apache-2.0 [S43] | Dagster Labs, **acquired by Prefect on 2026-07-13** [S25, S26] | Company; the acquirer is itself VC-backed | 1.13.24, 2026-09-21 [S11] |
| **Apache Airflow** | Apache-2.0 [S43] | **The Apache Software Foundation, TLP announced 2019-01-08** [S10] | Foundation | 3.3.2, 2026-09-17 [S1] |
| **Prefect** | Apache-2.0 [S43] | Prefect Technologies | Company; disclosed $11.5M Series A, 2021-02-09 [S27] | 3.8.7, 2026-09-26 [S21] |
| **Argo Workflows** | Apache-2.0 [S43] | **CNCF, Graduated 2022-12-06** [S31] | Foundation | v4.1.4 / v4.0.12, 2026-09-18 [S28] |
| **Flyte** | Apache-2.0 [S43] | **LF AI & Data, Graduated** [S36] | Foundation + Union.ai commercial | v2.0.50, 2026-09-24 [S32] |

All five pass the **activity floor** (L3) emphatically; none is archived or maintenance-only. On the **preferred** leg (foundation governance), Airflow, Argo and Flyte are foundation-governed; Dagster and Prefect are company-backed.

**The Dagster L2 question.** The rubric's middle leg allows "company-backed with disclosed funding AND a commercial incentive acceptable". Before 2026-07-13 Dagster Labs was an independent company with a direct incentive to grow Dagster and Dagster+. After the acquisition, Dagster is a **second product inside Prefect's P&L**. That is exactly the configuration that produces "we will sunset the one with fewer users" [S39 section 3.7]. Both parties publicly commit to continuity: Prefect's page says "Dagster stays Dagster ... Dagster and Dagster+ are here to stay. They're phenomenal products, and we're fully committed to their long-term maintenance, investment, and growth" [S25]. The promise is real but it is a promise, and it is roughly two and a half months old at the date of this report. I read this as **L2 impaired, not failed**: the funding is disclosed, the incentive is weaker but not absent, and the hard floor is met. It matches doc 03's PASS-WITH-CAUTION.

**Prefect's incentive.** Prefect now owns both products. Its incentive to keep *Prefect* healthy is maximal, which would make Prefect the "safe" company-backed choice if governance were the only axis. It is rejected below on technical fit, not on health.

### 3.7 Python-first fit

- **Dagster:** Python-native. PyPI `Requires-Python >=3.10,<3.15`; the host runs Python 3.14.4 [S12, S39 section 2]. In range.
- **Airflow:** Python DAGs. PyPI `Requires-Python !=3.15,>=3.10`; the docs state "Starting with Airflow 3.2.0, Airflow supports Python 3.10, 3.11, 3.12, 3.13, 3.14" [S3, S6]. In range.
- **Prefect:** Python-native. PyPI `Requires-Python >=3.10,<3.15` [S22]. In range.
- **Argo:** **not Python-first.** Authoring is YAML; the runtime is Go on Kubernetes. There is no first-party Python SDK. This conflicts with M21, which commits the platform to Python for orchestration, checks, lineage and tooling.
- **Flyte:** Python-first. The Flyte 2 SDK `flyte` is on PyPI at 2.10.2, `Requires-Python >=3.10`; the older `flytekit` 1.16.28 caps below 3.13 [S33, S34]. Use the Flyte 2 SDK on this host.

### 3.8 The Prefect acquisition risk

The event: Prefect acquired Dagster Labs (Elementl, Inc. d.b.a. Dagster Labs) on **2026-07-13**, announced on both companies' sites the same day [S25, S26]. Doc 03 records the same event and grades Dagster PASS-WITH-CAUTION [S39 section 3.7].

How much does it change the decision?

- **It does not change the code.** The licence is Apache-2.0 and has not changed [S43]. Even a hostile move leaves a forkable codebase.
- **It does not touch the activity floor.** Dagster shipped 1.13.17 through 1.13.24 between 2026-08-07 and 2026-09-21, roughly weekly [S11]. The acquisition has not slowed it.
- **It weakens L2.** Two orchestrators, one P&L, is the classic pre-sunset shape. The public commitment is explicit but young.
- **It is bounded by the platform's own design.** The requirements matrix already treats orchestration as "the cheapest layer to replace" and M1 already includes a timed swap drill [S40 section 6.6]. A swap is a planned activity, not an emergency.

**Inference:** the acquisition is a reason to monitor Dagster and to keep the swap drill honest, not a reason to reject it. Rejecting a weekly-released Apache-2.0 project for a corporate event would be over-correcting, and it would trade away the best asset model for a governance improvement the project does not currently need.

### 3.9 Portfolio and interview value against the JD

- The JD names Dagster in its stack and accepts Airflow explicitly as a transferable alternative [S42]. Both are named or blessed. Prefect, Argo and Flyte are "equivalent" at best.
- M13, the DQ gate that stops something, is one of the five interview-critical rows [S40 section 4]. Dagster's blocking asset check is the crispest possible demonstration; Airflow's version is a failing task plus a trigger rule, which is correct but less quotable.
- Airflow has the broadest deployment base of any candidate, so interviewing on Airflow transfers to more shops. Dagster's asset model is the more distinctive talking point.
- The JD's emphasis is streaming, batch, serving, governance, DQ and physical layout, not orchestration [S42]. Orchestration is a supporting layer here; the orchestrator should be chosen for how well it carries the DQ gate and the batch/serving graph, not for its own sake.

### 3.10 Migration cost between them

**Analysis, not measurement.** No migration was performed.

- **Dagster <-> Airflow: medium.** Both Python, both graph-based. The translation is assets to tasks-plus-assets; Airflow 3's own assets and asset partitions (3.2.0) reduce the gap, and its first-party OpenLineage provider removes the emitter rewrite. The DQ gate must be rebuilt from blocking checks to failing tasks plus trigger rules.
- **Dagster <-> Prefect: medium.** Both Python; Prefect's `@materialize` assets map to Dagster assets, but Prefect has no partitions or checks, so the retention and gate logic must be rebuilt as custom tasks.
- **Dagster <-> Flyte: medium-high.** Python on both sides, but Flyte's typed task model, Kubernetes substrate and devbox cluster are a different operational shape, and there is no asset/partition/check equivalent.
- **Dagster <-> Argo: high.** A YAML/Kubernetes rewrite with no asset model. The Python asset definitions would become container steps.

The practical point: Dagster, Airflow and Prefect are mutually cheap to swap because they are all Python and all run locally. Argo and Flyte are expensive to swap to or from, because both are cluster-shaped.

---

## 4. Per-candidate verdicts

### 4.1 Dagster - ADOPT

Best fit on the dimensions that matter: the only candidate with first-class blocking asset checks, the richest partition model, Python-native assets, and a light local footprint (two processes plus SQLite). Apache-2.0. Activity is weekly and current (1.13.24, 2026-09-21). Two honest caveats: retention is a documented sensor recipe rather than a built-in feature, and its OpenLineage emitter is a community package at v0.2.1, not first-party. The L2 leg is impaired by the 2026-07-13 acquisition, but the hard floor is met and the licence makes the code forkable.

### 4.2 Apache Airflow - FALLBACK

The safest longevity choice: ASF Top-Level Project since 2019-01-08, Apache-2.0, and the only candidate with a first-party OpenLineage provider. Airflow 3.2.0 added asset partitions, closing much of the model gap. It loses to Dagster on two things: no first-class asset checks (the DQ gate is a failing task plus the default `all_success` trigger rule), and a heavier local footprint (scheduler, DAG processor, API server, workers, and a mandatory metadata database). It is the correct fallback and is explicitly accepted by the JD.

### 4.3 Prefect - REJECT (technical fit)

Foundation-clean and healthy, and now the owner of Dagster, but the weakest asset model of the Python candidates. Its assets have no partitions and no checks, and asset health is a visual indicator that is not yet backed by an event [S23]. It has no OpenLineage integration. For a platform whose load-bearing requirement is a DQ gate that blocks, Prefect is a step backwards from Dagster and from Airflow.

### 4.4 Argo Workflows - REJECT (envelope and model)

CNCF Graduated and healthy, and the strongest option for Kubernetes-native job lifecycle. Rejected because it mandates a Kubernetes cluster (poor on a podman local-first host), is YAML-first rather than Python-first (conflicts with M21), has no data-asset/partition/check model, and has no OpenLineage integration.

### 4.5 Flyte - REJECT (fit)

Well-governed (LF AI & Data Graduated) and Python-first, with a genuine local devbox. Rejected because it is built on Kubernetes, is task/run-oriented rather than asset-oriented, has no partition or asset-check model, and has no OpenLineage integration. It is an ML/AI orchestration platform; this platform's needs are data-asset-shaped.

---

## 5. Decision matrix

| Dimension | Dagster | Airflow | Prefect | Argo | Flyte |
|---|---|---|---|---|---|
| Data-asset model | **assets** | assets (2.4/3.0) | assets (3.x) | none | none |
| Partitions | **time/static/multi/dynamic** | asset partitions (3.2.0) | none | none | none |
| Asset checks | **yes, blocking + severity** | no | no | no | no |
| DQ gate that blocks | **blocking check** | failing task + all_success | failing task | failing step | failing task |
| Retention primitives | sensors + dynamic partitions | operators/sensors | none | none | none |
| OpenLineage emitter | community v0.2.1 | **first-party 2.20.1** | none | none | none |
| Batch Spark | strong | strong | adequate | strong | strong |
| Streaming lifecycle | ops/jobs | **mature operators** | tasks | **k8s-native** | tasks |
| Failure propagation | blocks downstream | cascades skip | blocks downstream | fails workflow | fails workflow |
| Local footprint | light (2 proc + SQLite) | moderate (4+ proc + DB) | light (SQLite) | **needs k8s** | devbox cluster |
| Licence | Apache-2.0 | Apache-2.0 | Apache-2.0 | Apache-2.0 | Apache-2.0 |
| Governance | company (acquired 2026-07-13) | **ASF TLP** | company | **CNCF Graduated** | **LF AI & Data Graduated** |
| L2 incentive | impaired | strong | strong (Prefect) | strong | strong |
| Activity (latest) | 1.13.24, 2026-09-21 | 3.3.2, 2026-09-17 | 3.8.7, 2026-09-26 | v4.1.4, 2026-09-18 | v2.0.50, 2026-09-24 |
| Python-first | yes | yes | yes | **no** | yes |
| JD hit | stack names it | explicitly accepted | "equivalent" | "equivalent" | "equivalent" |
| Migration cost (from Dagster) | - | medium | medium | high | medium-high |

---

## 6. Recommendation

**Adopt Dagster. Keep Apache Airflow as the named, pre-approved fallback, with a documented switch trigger.**

Why Dagster on merit:

1. **It is the only candidate with a DQ gate that is a first-class object.** `@asset_check` with `blocking=True` and severity is exactly M13's requirement, and M13 is one of the five interview-critical rows [S13, S40].
2. **Its partition model is the richest of the five** (time, static, two-dimensional, dynamic, with partition mappings and backfills), which is what M4, M7 and M12 need [S14].
3. **It is Python-native and light locally**, running as two processes plus SQLite with Postgres optional [S16, S17], inside the 7-8 GB envelope.
4. **It is Apache-2.0 and actively developed** (weekly releases through 2026-09-21), so the acquisition does not fail the rubric's hard floor [S11, S43].
5. **Orchestration is the cheapest layer to replace**, and the plan already includes a swap drill, so the acquisition risk is bounded and already budgeted for [S40 section 6.6].

Why not Airflow as the primary: it is the safer governance choice, but it has no first-class asset checks, its DQ gate is a failing task plus a trigger rule, and its local footprint is heavier. Choosing it would trade the platform's strongest governance demonstration (a gate that blocks) for a longevity improvement Dagster does not currently need. Airflow remains the fallback precisely because it is healthy, foundation-governed and cheap to migrate to.

**Two actions that must accompany this choice:**

- **Record the OpenLineage emitter dependency.** M11 currently assumes Dagster emits OpenLineage. That rests on `dagster-openlineage` v0.2.1, a community package, not a first-party one [S18, S19]. The plan should name it, pin it, and watch it. If it stalls, the fallback is to emit from Spark and Flink (both first-party OpenLineage integrations) and treat Dagster lineage as secondary, or to switch the orchestrator to Airflow.
- **Build retention, do not assume it.** Dagster has no built-in retention policy; M12 must be built as the documented data-deletion plus partition-sync sensor pattern over dynamic partitions [S15].

**Switch to Airflow if any of these triggers fire:** the Dagster repository is archived or moved to maintenance-only; release cadence falls below roughly one release a month for two consecutive quarters; the licence moves away from Apache-2.0; Dagster or Dagster+ is announced as sunsetting; or the M1 swap drill shows the migration is cheap and the risk appetite is low.

**Rejected, and why:**

- **Prefect - rejected on technical fit.** Healthy and foundation-clean in licence terms, but no partitions, no asset checks, asset health not yet event-backed, and no OpenLineage integration.
- **Argo Workflows - rejected on envelope and model.** Requires Kubernetes (poor local-first fit on podman), YAML-first (conflicts with M21), no asset/partition/check model, no OpenLineage.
- **Flyte - rejected on fit.** Well-governed and Python-first, but Kubernetes-based, task/run-oriented rather than asset-oriented, and no OpenLineage.

---

## 7. What I could not verify

- **No measured footprint.** I ran no orchestrator and measured no RSS. All footprint claims are from the projects' documented component lists and storage defaults.
- **Dagster's OpenLineage integration depth.** `dagster-openlineage` v0.2.1 is documented as emitting schema, column-lineage, data-quality-assertion and partition nominal-time facets [S18], but I did not inspect its source or test an emission. The claim is the package's own documentation.
- **Prefect's funding history beyond the Series A.** I found a first-party $11.5M Series A press release from 2021-02-09 [S27] but no first-party announcement of later rounds; aggregator sites report more but are secondary. I have not cited an unverified total.
- **Airflow's asset-partition maturity.** Asset partitions were added in 3.2.0 and the docs describe rollup mappers, wait policies and runtime partitioning [S5]. I did not test them, and I do not know how they behave at scale or under backfill.
- **Migration costs are analysis, not measurement.** No migration was performed; the medium/high labels are my judgement from the model differences.
- **Prefect's exact asset semantics under failure.** The docs describe materialization events and visual health [S23]; whether a failed materialization can block a downstream flow without custom code is not stated in the assets page. I did not read the full Prefect failure-semantics documentation.

---

## 8. Source log

All URLs accessed **2026-09-28** unless the item carries its own date.

| ID | Source | Date on source |
|---|---|---|
| S1 | `api.github.com/repos/apache/airflow/releases/tags/3.3.2` - Apache Airflow 3.3.2 | published 2026-09-17 |
| S2 | `api.github.com/repos/apache/airflow/releases` - 3.3.0 | published 2026-07-06 |
| S3 | `pypi.org/pypi/apache-airflow/json` - 3.3.2, `Requires-Python !=3.15,>=3.10`, classifiers 3.10-3.14 | uploaded 2026-09-17 |
| S4 | `airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html` - scheduler, executor, DAG processor, API server, metadata database (required), workers | accessed 2026-09-28 |
| S5 | `airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html` - assets (added 2.4, renamed 3.0), asset partitions (added 3.2.0), `CronPartitionTimetable`, pre-determined vs runtime partitioning, no asset checks | accessed 2026-09-28 |
| S6 | `airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html` - DAG bundles and versioning (LocalDagBundle not versioned; GitDagBundle versioned); `airflow.apache.org/docs/apache-airflow/stable/start.html` - `airflow standalone`; Python 3.10-3.14 supported from 3.2.0 | accessed 2026-09-28 |
| S7 | `airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html` - default `trigger_rule` `all_success`, cascaded skip, trigger-rule list | accessed 2026-09-28 |
| S8 | `github.com/apache/airflow` - `providers/openlineage/README.rst` - `apache-airflow-providers-openlineage` Release 2.20.2, OpenLineage framework | accessed 2026-09-28 |
| S9 | `pypi.org/pypi/apache-airflow-providers-openlineage/json` - 2.20.1, `Requires-Python >=3.10` | uploaded 2026-08-23 |
| S10 | `news.apache.org/foundation/entry/the-apache-software-foundation-announces44` - Apache Airflow as a Top-Level Project, 8 January 2019 | 2019-01-08 |
| S11 | `api.github.com/repos/dagster-io/dagster/releases` - 1.13.24 and the 1.13.17-1.13.24 cadence | 1.13.24 published 2026-09-21 |
| S12 | `pypi.org/pypi/dagster/json` - 1.13.24, `Requires-Python <3.15,>=3.10` | uploaded 2026-09-21 |
| S13 | `github.com/dagster-io/dagster` - `docs/docs/guides/test/asset-checks.md` - `@asset_check`, `blocking=True`, severity, Dagster+ alerting, separate scheduling | accessed 2026-09-28 |
| S14 | `github.com/dagster-io/dagster` - `docs/docs/guides/build/partitions-and-backfills/partitioning-assets.md` - time/static/two-dimensional/dynamic partitions | accessed 2026-09-28 |
| S15 | `github.com/dagster-io/dagster` - `docs/docs/guides/build/partitions-and-backfills/data-retention.md` - "no built-in retention policy"; data-deletion + sync sensor pattern | accessed 2026-09-28 |
| S16 | `github.com/dagster-io/dagster` - `docs/docs/deployment/oss/deployment-options/running-dagster-locally.md` - `dg dev` launches UI + daemon; ephemeral/SQLite default | accessed 2026-09-28 |
| S17 | `github.com/dagster-io/dagster` - `docs/docs/deployment/oss/oss-deployment-architecture.md` - three long-running services; `SqliteRunStorage` default | accessed 2026-09-28 |
| S18 | `github.com/dagster-io/dagster` - `docs/docs/integrations/libraries/openlineage.md` - community-supported `dagster-openlineage`, two emission mechanisms, asset-centric facets | accessed 2026-09-28 |
| S19 | `pypi.org/pypi/dagster-openlineage/json` - 0.2.1 | uploaded 2026-05-22 |
| S20 | `github.com/dagster-io/community-integrations/tree/main/libraries/dagster-openlineage` - community package source | accessed 2026-09-28 |
| S21 | `api.github.com/repos/PrefectHQ/prefect/releases/tags/3.8.7` - Prefect 3.8.7 (nightly dev releases also current) | published 2026-09-26 |
| S22 | `pypi.org/pypi/prefect/json` - 3.8.7, `Requires-Python <3.15,>=3.10` | uploaded 2026-09-27 |
| S23 | `docs.prefect.io/v3/concepts/assets` - assets, materialize/reference/external, `@materialize`, no partitions, no checks, health "visual" only | accessed 2026-09-28 |
| S24 | `docs.prefect.io/v3/advanced/self-hosted` - multi-server requires PostgreSQL 14.9+; SQLite not for multi-server; Redis for events | accessed 2026-09-28 |
| S25 | `prefect.io/prefect-acquires-dagster` - "Dagster stays Dagster"; commitments to long-term maintenance, investment and growth | 2026-07-13 |
| S26 | `dagster.io/blog/prefect-is-acquiring-dagster` - Dagster's own announcement | 2026-07-13 |
| S27 | `prnewswire.com/news-releases/prefect-raises-11-5m-in-series-a-funding...` - $11.5M Series A | 2021-02-09 |
| S28 | `api.github.com/repos/argoproj/argo-workflows/releases` - v4.1.4 and v4.0.12 | published 2026-09-18 |
| S29 | `argo-workflows.readthedocs.io/en/latest/quick-start/` - "you need a Kubernetes cluster and kubectl configured" | accessed 2026-09-28 |
| S30 | `argo-workflows.readthedocs.io/en/latest/workflow-concepts/` - "workflow engine for Kubernetes"; Workflow spec = templates + entrypoint | accessed 2026-09-28 |
| S31 | `cncf.io/announcements/2022/12/06/the-cloud-native-computing-foundation-announces-argo-has-graduated/` - Argo graduated | 2022-12-06 |
| S32 | `api.github.com/repos/flyteorg/flyte/releases` - v2.0.50 and v1.16.9 | v2.0.50 published 2026-09-24 |
| S33 | `pypi.org/pypi/flyte/json` - 2.10.2, `Requires-Python >=3.10`; `docs.flyte.org` Flyte 2 TaskEnvironment/tasks/caching/triggers | 2.10.2 uploaded 2026-09-26 |
| S34 | `pypi.org/pypi/flytekit/json` - 1.16.28, `Requires-Python <3.13,>=3.10` | uploaded 2026-08-18 |
| S35 | `flyte.org/devbox` - `pip install flyte; flyte start devbox`; local scheduler, object store and UI | accessed 2026-09-28 |
| S36 | `github.com/flyteorg/community/blob/main/GOVERNANCE.md` - "a graduated LF AI&Data Foundation project" | accessed 2026-09-28 |
| S37 | `github.com/flyteorg/flyte` README - "leveraging Kubernetes as its underlying platform" | accessed 2026-09-28 |
| S38 | `github.com/OpenLineage/OpenLineage` - `website/docs/integrations` tree - integrations are airflow, dbt, feast, flink, great-expectations, hive, presto, spark; no prefect/argo/flyte/dagster | accessed 2026-09-28 |
| S39 | `docs/research/03-longevity-audit.md` - Dagster PASS-WITH-CAUTION (section 3.7), OpenLineage PASS (3.10), environment baseline (section 2), stack risks (6.6) | 2026-09-27 |
| S40 | `docs/requirements-matrix.md` - M1, M4, M7, M11, M12, M13, M14, M21; interview ordering (section 4); stack risks (6.6) | 2026-09-27 |
| S41 | `docs/mission/MISSION.md` - section 10 (Orchestration), section 13 (Dagster observability), section 28 (architecture diagram) | extracted 2026-09-27 |
| S42 | `~/projects/career-ops/data/jd-cache/031.md` - stack names Dagster; orchestration as nice-to-have; "Airflow instead of Dagster, that transfers" | fetched 2026-09-27 |
| S43 | `api.github.com/repos/{apache/airflow, dagster-io/dagster, PrefectHQ/prefect, argoproj/argo-workflows, flyteorg/flyte}` - licence.spdx_id = Apache-2.0 for all five; stars, pushed_at, archived flags | accessed 2026-09-28 |
| S44 | `docs/research/13-lineage-backend-comparison.md` - OpenLineage is the fixed emission contract; section 2.1 ("The emitter leg is not uniform") records Spark/Flink as first-party emitters, Airflow as the only first-party orchestrator provider, and Dagster as a v0.2.1 community package | 2026-09-28 |
