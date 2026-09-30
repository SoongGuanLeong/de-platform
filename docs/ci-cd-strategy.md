# The CI/CD strategy: the job graph, the required checks, and the delivery path

**Ticket:** [The CI/CD strategy and the delivery path](https://github.com/SoongGuanLeong/de-platform/issues/24)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Decision records:** [ADR-0033](adr/0033-delivery-is-validated-artefacts-not-a-gitops-controller.md) (the delivery path) and [ADR-0034](adr/0034-the-one-built-image-is-published-to-ghcr.md) (the built image and its registry)
**Boundary:** this document fixes the CI platform, the workflow shape, the job graph, the path filters, the required checks and branch protection, the delivery path, the local-to-CI relationship, and the image build and registry. The test levels and the CI-versus-profile split are [the testing strategy](testing-strategy.md); the repository layout and the check inventory are [the repository decomposition](repository-decomposition.md); the cloud shape and what is authored versus applied are [the cloud architecture](cloud-architecture.md); the profiles and the host anchor are [the local development architecture](local-development.md).

---

## 0. Status of this document

A plan, not a build. **No job of the graph proposed below has run and no check it describes has produced a result, with one exception.** The repository contains one workflow file, `.github/workflows/security.yml`, written during the security round, and **that one has run**: section 4 records its history. The existing check is therefore exercised, while everything proposed below is not. Every statement below about a job, a filter or a protection rule is a statement about a plan.

The lint tool list is **proposed, not measured**, which is the gap [the repository decomposition](repository-decomposition.md) already records; the one entry checked against its source is `sqlfluff`, which cannot parse ClickHouse `PROJECTION` clauses (issue 8583, September 2026), so it covers ClickHouse query SQL and the subset of DDL it parses. Nothing in this document was measured, and no cloud bill was observed.

**Unproven is not undecided.** Where a decision is settled but its evidence is missing, this document says so and names the test that would produce the evidence, rather than reopening the decision.

**None of the structure this document describes exists yet.** `.github/workflows/ci.yml`, `deployment/scripts/`, `deployment/tools.lock`, `deployment/rendered/`, `contracts/`, `tests/` and the Python and Java distributions are all part of the plan, named here so the plan is reviewable. The only path named in this document that exists today is `deployment/budgets/profiles.yaml`, `docs/budgets.yaml` and the one existing workflow file.

## 1. What this document settles

1. **The CI platform**, and why it is infrastructure rather than a component or an addition (section 2).
2. **The workflow shape and the required-check mechanism** (section 3).
3. **The job graph**: which jobs exist, what each checks, and what triggers them (section 4).
4. **The path filters**, stated per job rather than as one blanket rule (section 5).
5. **The required checks and how `main` is protected**, including what a red check does (section 6).
6. **The delivery path**: what "delivery" means when nothing is applied (section 7).
7. **The image build and registry** (section 8).
8. **The local-to-CI relationship** (section 9).
9. **The CI tool set and its rejected alternatives** (section 10).
10. **What is unproven** (section 11) and **when this is reconsidered** (section 12).

## 2. The CI platform, and the protection surface it actually gives us

**GitHub Actions.** It is neither a component nor an addition and needs no research ticket. The reasoning is that it is the same vendor as the issue tracker, it is already in the repository, and it is free **only because the repository is public**: GitHub documents standard GitHub-hosted runners as "free and unlimited on public repositories", with a cap of 20 concurrent jobs on the Free plan. It is recorded as **infrastructure** in the sense [`CONTEXT.md`](../CONTEXT.md) already fixes: what exists only because the cloud needs it. Rejected alternatives, recorded in one line each:

- **A self-hosted runner.** Rejected: it fails the free-to-run gate and the footprint gate at once, and it would make the portfolio depend on a machine being awake.
- **A second CI vendor** (GitLab CI, Jenkins, CircleCI). Rejected: no requirement names one, and it would duplicate an integration the tracker already provides.

**The repository is user-owned and public, and that narrows the protection surface.** This is a discovered constraint rather than a choice, and it is worth stating because a normal CI design assumes the opposite:

| Capability | Status on this repo | Consequence |
|---|---|---|
| Require a pull request before merging | available | the merge path is a PR |
| Required status checks | available | the aggregator in section 3 is enforced |
| Require branches to be up to date | available | strict mode is on |
| Require linear history | available | squash merge only |
| Block force pushes and deletions | available, on by default | history on `main` is append-only |
| Bypass list | available for **roles** on rulesets | the repository-admin role is the only bypass actor |
| Merge queue | **unavailable** (organisation-only) | no queue; a stale PR is rebased by hand |
| Required workflows (ruleset rule) | **unavailable** (organisation/GHEC only) | the aggregator job does this job instead |
| Required reviewers named as a team | **unavailable** (user-owned repos have no teams) | approvals are counted, not named |
| Push rulesets (restrict paths or size) | **unavailable** (paid tiers) | no push-side file restriction |

Each unavailable row is a documented gap with one trigger: **if the repository ever moves to an organisation, revisit this table**, because three of the four become available at once. None of them is needed for the strategy to work.

## 3. The workflow shape, and the required-check mechanism

**One workflow, `.github/workflows/ci.yml`, with no top-level `paths:` filter anywhere.** GitHub documents the trap precisely: a workflow skipped by a top-level `paths` filter leaves its checks **Pending** and blocks the merge indefinitely ("Waiting for status to be reported"), while a job skipped by a **job-level `if`** reports **Success** and does not block. So path detection cannot be done by the trigger; it has to be done inside the workflow and consumed by job-level conditionals.

Three mechanisms follow.

**The `changes` job.** It runs first, always, and produces one boolean output per filtered job. It computes them with `git diff --name-only` against the merge base plus a filter map held in `deployment/scripts/paths.sh`. It uses **no third-party action**, which keeps the supply chain to GitHub's own actions and makes the filter map reviewable as a diff rather than as YAML nested three levels deep.

**The `required` job.** It `needs` every other job, runs with `if: always()`, and is the **only** status check the ruleset requires. It fails on any `failure` or `cancelled` result and passes on `success` or `skipped`, so a legitimately skipped path-filtered job does not block a merge while a real failure always does.

**The name is `required`, not `gate`.** [`CONTEXT.md`](../CONTEXT.md) already defines **gate** as the orchestration consequence of a severity, the thing that stops or diverts a pipeline. A CI aggregator is a different concept and must not borrow the word, so the job is named for what it is: the required check.

**Workflow hygiene, applied uniformly to the new workflow:**

- `permissions: contents: read` at workflow level, elevated per job only where a job must write. The only job that elevates is `images`, which needs `packages: write` because the default `GITHUB_TOKEN` on a personal-account repository is read-only for contents and packages.
- `concurrency` keyed on the ref with `cancel-in-progress: true`, so an outdated run is cancelled rather than queued.
- An explicit `timeout-minutes` on every job.
- Every third-party action is to be pinned to a full commit SHA, and the repository's SHA-pinning policy is to be switched on. The live repository currently has `sha_pinning_required=false`, so this is a change rather than a description. A commit SHA is the only way to use an action as an immutable release, and it costs one thing: Dependabot generates action alerts only for semantic-versioned references, so SHA pinning trades alert coverage for immutability. Dependabot version updates still work and still update the SHA.
- **No job needs a repository secret.** Every check is static, and the image push uses the built-in token. That property is worth protecting, and it is one of the reasons the registry choice in section 8 went the way it did.

Two notes on the existing file, so the list above is not read as a description of the repository today. `.github/workflows/security.yml` does not meet it: it uses `actions/checkout@v4`, a moving tag, and declares neither `timeout-minutes` nor `concurrency`. This design absorbs and deletes that file, so the list is the standard for `ci.yml`. The gitleaks pin in the old file is a downloaded release binary rather than an actions reference, so Dependabot will not track it and it stays a manual maintenance surface.

## 4. The job graph

Eleven jobs plus the aggregator. They are grouped by toolchain so each job pays for one setup, and the always-running set is the cheap one, which is the fail-safe posture [the repository decomposition](repository-decomposition.md) asked for.

| # | Job | Runner | What it checks | Trigger |
|---|---|---|---|---|
| 0 | `changes` | ubuntu-latest | computes the path-filter outputs; checks nothing itself | always |
| 1 | `secrets` | ubuntu-latest | `gitleaks detect` over the full history, pinned by version and SHA256 | always |
| 2 | `boundaries` | ubuntu-latest | `ruff`; the packaging graph; `import-linter` rules 1 to 4; the notebook path check (rule 5) | always |
| 3 | `governance` | ubuntu-latest | contract-file validation and the breaking-change check; the completion-bar register validator; the budget validator; the cross-path agreement validator; the layout-agreement check | always |
| 4 | `compose` | ubuntu-latest | the compose-subset lint; every declared limit resolving against `deployment/budgets/profiles.yaml`; every profile peak recomputed from its ceilings | always |
| 5 | `lint` | ubuntu-latest | `sqlfluff`; `yamllint`; `actionlint` | always |
| 6 | `unit` | ubuntu-latest, matrix | `pytest` per Python distribution: `platform`, `ingestion`, `batch`, `governance`, `orchestration` | path, fail-safe |
| 7 | `java` | ubuntu-latest | Spotless with google-java-format; Gradle compile and tests of `streaming/` | path |
| 8 | `deployment` | ubuntu-latest | `tofu fmt -check`; `tofu init -lockfile=readonly` then `tofu validate`; `tflint`; the policy scan; `helm lint`; `helm template`; `kubeconform`; the rendered-manifest drift check | path |
| 9 | `observability` | ubuntu-latest | `promtool check rules`; the dashboard JSON schema | path |
| 10 | `images` | ubuntu-24.04-arm | the arm64 Marquez build; pushes only on a `demo-*` tag or `workflow_dispatch` | path |
| 11 | `required` | ubuntu-latest | aggregates; the only required status check | always |

**The `secrets` job is to absorb `.github/workflows/security.yml`.** The gitleaks job moves into `ci.yml` and the old file is deleted in the same change, so one required check covers everything. Keeping it separate would have made it a second required check, which is safe (it always runs, so it cannot be left Pending) but leaves two places to read.

**The history of the file it absorbs.** `.github/workflows/security.yml` declares `push`, `pull_request` and `workflow_dispatch` with no branch filter, and every run it has had since it landed on 2026-09-29 has been a push to `main`, one per push, and has passed - 58 runs up to `ee49848` - with no `pull_request` or `workflow_dispatch` run yet. Its single job is `gitleaks` 8.30.1, pinned by version and SHA256, scanning the full history. The scan has one real catch to its name, made by the same check run locally during the security round: two temporary SeaweedFS STS credentials in `docs/research/08-seaweedfs-sts-interop.md`, committed in `1d184c1` and redacted forward on 2026-09-29. Their two historical occurrences are suppressed by fingerprint in [`.gitleaksignore`](../.gitleaksignore) rather than by disabling a rule or exempting a path, and the suppression landed in the same commit as the workflow, so no CI run has ever been red. That is the case a scanner is good at, and it is the complement of [ADR-0028](adr/0028-secrets-live-only-in-the-runtime-directory.md)'s limit: the self-minted ADR-0006 leak would not have matched.

**`governance` carries the one evidence-adjacent validator.** The cross-path agreement check from [the testing strategy](testing-strategy.md) section 8 reads two **already committed** artifacts and asserts a tolerance declared in [`docs/budgets.yaml`](budgets.yaml). It re-derives a comparison; it does not re-run either path and it does not re-measure. That distinction is the guard in section 6.

**`governance` also carries the layout-agreement check.** [The data architecture](data-architecture.md) consolidates the physical-layout values that [the serving layer](serving-layer.md) and [the streaming jobs](streaming-jobs.md) decide, so the same value exists in two documents by design. The check parses the three committed tables and fails when the keyed set disagrees on the partition transform, the sort order or the format version for a table. It is a **document-consistency check, not an evidence check**: it reads three files and compares strings, and it never touches the stack. It exists because a consolidated view that can silently disagree with its sources is worse than no consolidated view at all, and the alternative, citing the source from every cell, would cost the single-view property the consolidation exists to provide.

**`deployment` is to commit `.terraform.lock.hcl`.** Without it, `tofu init` resolves providers from the registry on every run and `tofu validate` stops being deterministic.

**The rendered-manifest drift check, not a bot commit.** CI regenerates the Helm render and fails if it differs from the committed copy under `deployment/rendered/`. This satisfies the completion bar's "rendered manifests committed" without a workflow writing to the repository, and it respects the house rule against hand-editing auto-generated files: the committed copy is a build output, and the check is what proves it is in sync.

## 5. The path filters, stated per job

[The repository decomposition](repository-decomposition.md) wrote the rule as "a change to `platform/` or `contracts/` triggers everything". That is over-broad: `platform/` is not an input to the Java job, so a Python change would run the Java formatter. This document states each job's **actual input set** instead. The fail-safe property is preserved, because each job's set includes every shared artefact the job really consumes. [`docs/repository-decomposition.md`](repository-decomposition.md) is amended in the same change so the two documents agree: its blanket sentence becomes a pointer to the table below, and the fail-safe principle it states is kept.

| Job | Triggers on | Fail-safe override |
|---|---|---|
| `unit` | the changed distribution's own path | `platform/` or `contracts/` runs all five matrix entries |
| `java` | `streaming/` and the Avro schema files | none: the Flink jobs do not import Python |
| `deployment` | `deployment/` | `contracts/`, because charts reference contract-derived configuration |
| `observability` | `observability/` | `deployment/`, because the rule files are rendered alongside the charts |
| `images` | the image context under `deployment/` | none |

**Where the Avro schema files live, decided here.** [The repository decomposition](repository-decomposition.md) never says. They belong under `contracts/`, at `contracts/<spine>/topics/<topic>.avsc`, because `contracts/` is already defined as data with no executable content, the Avro schema is data shared by the producer (Debezium) and the consumers (Flink and Spark), and putting it there satisfies the rule that cross-path communication goes through `contracts/`, `platform/` or the catalog. It also means a schema change triggers every job that consumes the topic, which is the fail-safe behaviour we want.

## 6. The required checks, and what a red check does

**The ruleset on `main`**, applied as a repository ruleset rather than classic branch protection because rulesets carry a bypass list on a user-owned repository:

- require a pull request before merging, with **0 required approvals**, because a solo dev cannot approve their own PR and required-team reviewers are unavailable on a user-owned repository;
- require the `required` status check;
- require branches to be **up to date** before merging;
- require **linear history**, so the merge is a squash;
- block force pushes and deletions (on by default);
- **no merge queue** and **no required workflows**, both unavailable, both recorded in section 2.

**What a red check does, in four rules.**

1. A red `required` **blocks the merge**. There is no routine path around it.
2. A red check is **never** resolved by disabling, deleting or loosening the check. A check that is wrong is fixed, or removed by a pull request that says why.
3. The bypass list names the **repository-admin role only**, the sole bypass actor available on a user-owned repository. A bypass is recorded in the pull request with its reason, and it must be followed by a green run before any further change.
4. **The required set contains no evidence re-run.** The register validator, the budget validator, the cross-path agreement validator and the layout-agreement check read committed artefacts and re-derive from them. None re-measures, and none needs the stack. The required set is a structural gate and must not quietly become an evidence gate, which is the constraint this ticket was given.

## 7. The delivery path

**No GitOps controller.** This is [ADR-0033](adr/0033-delivery-is-validated-artefacts-not-a-gitops-controller.md), and the reasoning is arithmetic rather than taste.

**"Never applied" means never applied as evidence.** Three states need separating, because earlier documents use the phrase loosely and this decision depends on the distinction. **Authored** means written and statically validated in CI. **Applied** means a human runs the runbook, and it happens only inside a priced, time-boxed, torn-down demo window. **Evidenced** means the result is a reproducible evidence item. Nothing here is applied by CI, and nothing applied inside a window is evidenced: the demo has not been run, and its cost is arithmetic rather than an observed bill. A controller's only possible target therefore exists for a few hours and is never evidenced, and the platform would carry a component, or a capability plus a prerequisite, that is exercised nowhere else.

- **Self-hosted Argo CD** would be an addition with **no local evidence path at all**, because it needs a cluster and the local host cannot run one. That is the same failure this map already names for the old repository's Trino, which was wired and never queried. Its footprint also cannot be cited honestly: Argo CD publishes **no recommended resource requests or limits**, its manifests set none, and the numbers in its Helm values that look like recommendations are VPA `minAllowed` examples. Any sizing would be our invention.
- **Managed Argo CD** (EKS Capabilities) is real and priced, and the ticket's figures are exact: **$0.029108 per capability-hour plus $0.001452 per Argo CD Application hour in ap-southeast-5**, where an Application hour is counted per Application per target-cluster deployment and each ApplicationSet-generated instance counts as one Application. One capability and one Application for a 6-hour demo is **6 x 0.029108 = $0.174648** plus **6 x 0.001452 = $0.008712**, so **$0.18336**, which is **9.1% on the two-node minimal arm's $2.02** and **7.0% on the three-node demo's $2.61**. But it is **not a cluster add-on**: it is a capability resource on an existing cluster, and it **requires AWS Identity Center, which is mandatory and does not support local users**, plus an IAM capability role and per-target-cluster RBAC, because the auto-created access entry does not grant permission to deploy. It is also a managed service the platform operates, which contradicts [ADR-0027](adr/0027-self-host-what-the-platform-operates.md)'s self-host line and would need its own justification.

**What delivery means instead.** The deployable artefact is **the commit on `main` whose `required` check is green and whose `deployment/` tree renders and pins its inputs**. A `demo-<YYYY-MM-DD>` tag names the commit a priced window is run from, and it is the identifier the runbook records. There is no environment, no promotion and no rollback machinery, because there is no running environment to promote into.

| Category | What is in it | Who runs it |
|---|---|---|
| Authored, statically validated in CI, **never applied by anything** | the `reference` tfvars, because the reference arm is never applied; the policy scan; the rendered manifests; the compose files | CI validates; nobody applies |
| Authored and statically validated in CI, **applied only inside the priced demo window** | the OpenTofu modules with the `minimal` tfvars; the Helm charts | a human, following the runbook |
| Run in CI | the structural jobs; the arm64 image build | GitHub runners |
| Run locally under a profile | `tests/<profile>/`; every benchmark; the incident laboratory | this host, per [the local development architecture](local-development.md) |

The demo window's commands are `tofu apply`, `helm install` or `helm upgrade`, the smoke checks against EKS, and `tofu destroy`, all run by hand from the runbook.

**No `tofu plan`, no `apply` in CI, no LocalStack**, restating [the cloud architecture](cloud-architecture.md) section 7 rather than re-deciding it. **No Actions artifacts are uploaded**: the rendered manifests are committed, raw evidence lives under `docs/evidence/<class>/<instance>/raw/`, and `runtime/runs/` is gitignored. The design therefore never touches the artifact-storage allowance.

## 8. The image build and the registry

**The design has exactly one built image.** Thirteen of the fourteen image-bearing components publish `linux/arm64` upstream and the design pins them by digest from [research 24](research/24-arm64-image-availability.md); the fourteenth is Marquez, which is amd64-only, so the arm64 build from the upstream Dockerfile at 0.51.1 is the one image the platform authors. "The same path as the rest" is therefore not a question: there is one build job, and the other thirteen are pinned rather than built.

**The build publishes to GitHub Container Registry**, at `ghcr.io/soongguanleong/de-platform/marquez`. This is [ADR-0034](adr/0034-the-one-built-image-is-published-to-ghcr.md), and the comparison is:

| Registry | Storage at rest | Pull | Push from CI | Verdict |
|---|---|---|---|---|
| **GHCR** | free for public packages; container registry storage and bandwidth currently free outright | anonymous pull supported, no published rate limit | built-in token, no AWS credential | **chosen** |
| ECR Public | 50 GB per month always-free | anonymous pull capped at **1 per second, not adjustable** | requires AWS authentication | rejected |
| ECR private | **$0.10 per GB-month**, only a 500 MB / 12-month new-customer free tier | authenticated | requires AWS credentials | rejected |

ECR Public's one-pull-per-second anonymous cap is the decisive detail, because a node group starting its pods pulls in a burst. GHCR is also the only option that is free at rest, and the only one that keeps AWS credentials out of CI, which preserves the no-secret property in section 3.

**The ECR wording, tightened.** ECR is **authored and unused**. Concretely:

- ECR is an authored OpenTofu resource in the cloud arm, and it stays there as the **documented production target**.
- **The demo does not create it.** The ECR resource belongs to the `reference` profile, which is never applied, and the `minimal` tfvars the demo applies do not declare it. So the demo window creates no ECR repository at all, and this is a decision of this document rather than an inference: [the cloud architecture](cloud-architecture.md) lists ECR as infrastructure with no arm qualifier, and that one line needs a one-line amendment to say so, recorded as an impact item for approval rather than applied here.
- **No run uses it.** Not the local profiles, not CI, and **not the demo**: the demo pulls from GHCR.
- Because no run uses it, ECR has **no evidence path at all**, and nothing in this document or in the cloud architecture may be read as demonstrating it. It is a target, not a result.
- Switching the demo to ECR is a values change plus an image copy, and **that switch is itself unproven**; it is recorded as a target with a named mechanism, never as a validated path.
- The Helm chart therefore takes `image.registry`, `image.repository` and `image.digest` as values, defaulting to GHCR, so the ECR path is a values change rather than a chart edit.

**When the build runs.** On a pull request that touches the image context, the job **builds without pushing**, which is the only way to prove the Dockerfile compiles at review time. On a `demo-*` tag or `workflow_dispatch`, it builds and pushes. This is the one job in the graph that is not a cheap structural check, and it earns its place because it is the only artefact the platform authors rather than pins.

**The arm64 runner is native.** `ubuntu-24.04-arm` is a standard GitHub-hosted runner, free on public repositories, so no QEMU emulation is needed for the arm64 half. Two honest limits: a **community action in the build path may not be arm64-compatible** (GitHub's own actions are), and the build produces an arm64 image that **has never been executed**, because this host is x86_64. The build being produced is not the same claim as the image running, and [the cloud architecture](cloud-architecture.md) already carries the second as a documented limitation.

## 9. The local-to-CI relationship

**One script per check, invoked identically by CI and by the developer.** Each check lives in `deployment/scripts/`, and every tool version is pinned in one file, `deployment/tools.lock`. A script fetches its pinned tool by **version plus SHA256** and verifies the digest before use, which is the pattern `.github/workflows/security.yml` already uses in this repository. CI calls the same script the developer calls, so there is no second implementation to drift and no host install to document.

**What CI deliberately cannot run**, restating [the testing strategy](testing-strategy.md) section 6 and [the local development architecture](local-development.md) section 9 rather than re-deciding them:

- anything under `tests/<profile>/`, including the container half of `smoke`;
- every benchmark, under `benchmark`;
- the incident laboratory, which needs a path profile plus the observability overlay;
- any evidence re-run;
- docker compose, because the design names podman-compose as its one verified provider and docker compose is authored for and untested;
- arm64 execution of any image;
- anything requiring AWS credentials or a real account.

**The one thing CI does that is evidence-adjacent** is the cross-path agreement validator, which reads two committed artifacts. It is stated explicitly, in section 4 and in section 6, so that no reader mistakes the required set for an evidence gate.

**No pre-commit hook.** [The security model](security-model.md) already records that a pre-commit hook is bypassable with `git commit --no-verify` and covers staged content only. This document does not reopen that.

## 10. The CI tool set, and the rejected alternatives

[The cloud architecture](cloud-architecture.md) section 7 left the policy scan as "`checkov` or `trivy config`", which is an unresolved either/or, and the mission's sprawl test admits one tool for one problem.

**`trivy config` is chosen.** The repository is Apache-2.0, maintained by Aqua Security, and distributed as a self-contained binary with no interpreter or package-manager step, so the same artefact runs on the runner and on this host. Its IaC coverage is confirmed for Terraform (`*.tf`, `*.tf.json`, `*.tfvars`, plus Terraform plan) and for Kubernetes manifests (`*.yml`, `*.yaml`, `*.json`), and the same binary scans container images and the filesystem, so one tool covers the policy scan, the image scan and a filesystem scan instead of three.

**`checkov` is rejected on repository scope, not on quality.** It is Apache-2.0 and maintained by Prisma Cloud (Palo Alto Networks), with a commercial platform behind it, and it installs through `pip` on Python 3.9 to 3.13, so it needs a runtime the other tools do not. Its input coverage is genuinely wider than `tflint` plus `kubeconform` taken together, and the honest statement of the overlap is at the **input** level rather than the finding level: the three read some of the same files and report different classes of result, because `tflint` is a Terraform-only provider linter, `kubeconform` is a Kubernetes schema validator, and `checkov` is a security and compliance policy scanner. The rejection is that most of that extra coverage is dead weight here: this platform authors no CloudFormation, AWS SAM, Bicep, ARM, Serverless or Ansible, its Dockerfile coverage has no counterpart but the `images` job compiles the Dockerfile on every pull request that touches it, which is a stronger check than a lint, and its CI-workflow coverage overlaps `actionlint`. It is a reasonable tool for a repository that spans those inputs; this one does not.

Three caveats are recorded rather than hidden, because each could bite later. `trivy config` on Terraform **downloads remote modules by default and this cannot be turned off from the CLI**, which is a supply-chain consideration if the scanned configuration ever stops being ours. Its Kubernetes support covers Helm fully and **Kustomize only partially, with overlays unsupported**, which is acceptable because this platform's charts are Helm. And **the CI tool set sits outside the licence and cost audit**, which covers the twenty components and the four fallbacks rather than the linters: `trivy` and `checkov` are both Apache-2.0, while `tflint` is MPL-2.0 in its licence file with a BUSL-1.1 component reported but not confirmed, which is an open item to confirm and fold into the audit's scope rather than a blocker.

This is a CI linter rather than a platform component, so it is recorded here with its rejected alternative and not as a research ticket; the tool list as a whole stays **proposed, not measured**, which is the gap the repository decomposition already carries.

The rest of the tool set is inherited from [the repository decomposition](repository-decomposition.md) and is not re-opened: `ruff` and `import-linter` for Python, Spotless with google-java-format for the Flink jobs, `sqlfluff` for SQL, `yamllint` for compose and contracts, `actionlint` for the workflows, and the repository's own compose-subset lint in `deployment/` because no off-the-shelf tool enforces a custom subset.

## 11. What this document does not claim

- **No job of the planned graph has run and no check it describes has produced a result, with one exception.** The `gitleaks` check that already exists **has run**, and section 4 records its history. The job graph is a plan, and the first implementation task is to make each script pass locally before the workflow is written.
- **The lint tool list is unmeasured**, except that `sqlfluff` cannot parse ClickHouse `PROJECTION` clauses (sqlfluff issue 8583, September 2026), which is carried as a documented limitation.
- **The arm64 Marquez build has not been built or run.** The build job is the mechanism that would produce it; the image running on Graviton is a separate claim with no local evidence path.
- **ECR is authored and unused**, the demo does not create it, and the switch to it is unproven (section 8).
- **The managed Argo CD figures are AWS list prices read on 2026-09-29**, not an invoice. The demo has not been run.
- **The protection surface in section 2 is a reading of GitHub's documentation on 2026-09-29**, and GitHub changes this surface; the rows marked unavailable are the ones to re-check if the repository moves to an organisation.
- **The rendered-manifest drift check, the policy scan and the compose lint have never been executed**, so whether each has a usable configuration for its target is unverified.

## 12. Reconsideration triggers

1. **The repository moves to an organisation.** This unlocks merge queue, required workflows and named reviewers at once, and section 2's table is re-read.
2. **The repository goes private.** Free standard runners and free GHCR both end, which re-opens section 8 and the CI platform question in section 2 together.
3. **The arm64 build fails on the free arm64 runner**, whether because of a community action or a toolchain limit. The fallback is a QEMU `buildx` build on an x64 runner, with the slowdown recorded rather than hidden.
4. **The engine-pin re-review of [ADR-0024](adr/0024-engine-pins-follow-the-iceberg-connector-matrix.md) fires** (Iceberg 1.12.0 reaching GA with its Flink 2.3 and Spark 4.2 connectors resolving). It re-opens the Gradle and Java tool pins with it.
5. **A `demo-*` window actually runs.** The first real demo is the first test of section 7's authored-versus-run split, and any row that turns out to need a step nobody wrote is a correction to this document.

## 13. Sources

- GitHub Actions runner availability, free use on public repositories, runner specifications and the 20-job concurrency cap: `https://docs.github.com/en/actions/reference/runners/github-hosted-runners` and `https://docs.github.com/en/actions/reference/limits`, read 2026-09-29.
- The pending-status trap for path-filtered required workflows: `https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks`, read 2026-09-29.
- Rulesets and protected branches available on a user-owned public repository, including the organisation-only rows: `https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets` and `.../managing-protected-branches/about-protected-branches`, read 2026-09-29.
- SHA pinning, the default token permission model and workflow hardening: `https://docs.github.com/en/actions/reference/security/secure-use` and `https://docs.github.com/en/actions/concepts/security/github_token`, read 2026-09-29.
- Dependabot's behaviour on SHA-pinned actions, action alerts and version updates: `https://docs.github.com/en/actions/reference/security/secure-use` and `https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-alerts`, read 2026-09-29.
- GitHub Packages and container registry billing, and anonymous pull: `https://docs.github.com/en/billing/concepts/product-billing/github-packages` and `https://docs.github.com/en/packages/working-with-the-container-registry`, read 2026-09-29.
- EKS Capabilities managed Argo CD, its prerequisites and its stated limits: `https://docs.aws.amazon.com/eks/latest/userguide/capabilities.html`, `.../create-argocd-capability.html` and `.../argocd-considerations.html`, read 2026-09-29.
- The Argo CD capability prices, read from the AWS Price List Bulk API offer `AmazonEKS` in ap-southeast-5 and us-east-1 (publication date 2026-09-28T19:42:55Z): $0.029108 and $0.001452 per hour in ap-southeast-5, $0.030000 and $0.0015000 in us-east-1.
- Argo CD's absence of published resource recommendations: `https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/` and the `argo-helm` chart's `values.yaml`, read 2026-09-29.
- ECR private and public pricing, quotas and the anonymous pull rate limit: `https://aws.amazon.com/ecr/pricing/` and `https://docs.aws.amazon.com/AmazonECR/latest/public/public-service-quotas.html`, read 2026-09-29.
- The pinned component digests and the Marquez arm64 gap: [research 24](research/24-arm64-image-availability.md), read 2026-09-29.
- Trivy's licence, distribution and scanning targets: `https://github.com/aquasecurity/trivy/blob/main/LICENSE`, `https://raw.githubusercontent.com/aquasecurity/trivy/main/README.md` and `https://trivy.dev/latest/docs/getting-started/installation/`, read 2026-09-29.
- Trivy's IaC coverage, including the Terraform remote-module behaviour and the partial Kustomize support: `https://raw.githubusercontent.com/aquasecurity/trivy/main/docs/guide/coverage/iac/index.md`, `.../terraform.md` and `.../kubernetes.md`, read 2026-09-29.
- Checkov's licence, maintainer, commercial platform and Python requirement: `https://github.com/bridgecrewio/checkov/blob/master/LICENSE` and `https://raw.githubusercontent.com/bridgecrewio/checkov/master/README.md`, read 2026-09-29.
- The tflint and kubeconform scopes the comparison rests on, and tflint's licence file: `https://raw.githubusercontent.com/terraform-linters/tflint/master/README.md`, `https://raw.githubusercontent.com/yannh/kubeconform/master/Readme.md` and `https://github.com/terraform-linters/tflint/blob/master/LICENSE`, read 2026-09-29.
