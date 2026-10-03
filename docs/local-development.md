# The local development architecture: profile budgets, bring-up and the local-versus-cloud diff

**Ticket:** [The local development architecture](https://github.com/SoongGuanLeong/de-platform/issues/25)
**Map:** [The Research & Architecture Proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Decision record:** [ADR-0031](adr/0031-the-local-execution-model-is-profile-scoped-and-host-anchored.md)
**Research:** [research 26](research/26-compose-resource-limits-and-portability.md) (how a resource limit is expressed portably) and [research 27](research/27-local-profile-memory-defaults.md) (what the images default to)
**Ceiling register:** [`deployment/budgets/profiles.yaml`](../deployment/budgets/profiles.yaml)

## 0. Status

No platform code exists while the map is open. **Nothing in this document was measured.** Every figure is a declared budget, an arithmetic result over documented defaults, or a published price with a date. The host was not measured, no container was run, and the compose bring-up described in section 6 has not been executed.

**Correction, 2026-10-01 (issue #31).** The container set and the smoke profile now exist, and section 6's bring-up has been executed under the `smoke` profile. `deployment/compose/` holds one self-contained compose file per profile, `deployment/tools.lock` pins every image by the digest of its multi-arch index, `deployment/scripts/preflight.sh` implements section 5, and `deployment/smoke` is the one-command run. The figures above stay declared budgets: the host was measured for free memory and for the toolchain it actually carries, and **no profile's declared peak was measured against a co-resident run** - `smoke` never runs two services at once. The 512 MiB reserve and every ceiling remain arithmetic.

## 1. What this document settles

The completion bar defines reproducibility by profile ([section 8](completion-bar.md)) and requires a written local-versus-cloud diff ([section 6.11](completion-bar.md)). It does not say what a profile's entitlement actually is, how a run is brought up and torn down, or what the local run cannot exercise. This document supplies those three things:

- the per-profile resource budget and the anchor it derives from (sections 2 to 4);
- the bring-up runbook, including the preflight that refuses a run the host cannot hold (sections 5 to 7);
- the local-versus-cloud diff (section 8), and what a profile run produces as evidence (section 9).

## 2. The anchor

**The anchor is the local host's declared free memory: 7.5 GiB (7680 MiB), against 12 vCPU.** A reserve of 512 MiB for podman, conmon and host drift comes off the top, so **the enforceable peak of any profile is 7168 MiB and 12 vCPU**.

The anchor is the free figure rather than the 14 GiB total, because free memory is what a profile actually runs against and it is the binding constraint. The alternative anchors are recorded and rejected:

| Candidate anchor | Figure | Why not |
|---|---|---|
| Host total memory | 14 GiB | Not available to a profile; the operating system and the desktop already hold the difference |
| ADR-0027's minimal cloud arm | 2 to 3 `m7g.large` = 4 to 6 vCPU, 16 to 24 GiB | The cloud node shapes are an **input** fixed by ADR-0027, and this ticket does not re-litigate the cloud topology, so they can be checked against the table but never derived from it |
| A single per-service table with no host anchor | n/a | The table still has to be summed against something, and the only something that binds is the host |

**The cloud comparison, stated once so no sentence reads the local run as cloud evidence.** The local peak of 7168 MiB is about **44%** of the minimal arm's 16 GiB at two nodes, and about **29%** of 24 GiB at three. The local run evidences the shape of the entitlement and never the cloud capacity.

**At the bottom of the ticket's stated range, neither path profile fits.** At 7.0 GiB free the enforceable peak is 6656 MiB, below both the batch peak (6976 MiB) and the streaming peak (7168 MiB). The runbook's reduced variant is the documented fallback rather than a silent degradation; see section 5.

## 3. The ceilings

One ceiling per service, in `deployment/budgets/profiles.yaml`. A ceiling is a hard limit, not a target: a service that reaches it is OOM-killed rather than slowed down.

| Service | Memory (MiB) | CPU | Documented default, and the override |
|---|---|---|---|
| postgres | 384 | 1 | Image tunes nothing; `shared_buffers` defaults to 128 MB, which fits |
| seaweedfs | 256 | 1 | No default published; `weed mini` is auto-tuned for one node |
| polaris | 768 | 1 | No default (Helm `resources: {}`); the production recommendation is 8 GiB / 4 CPU, which is a production figure |
| clickhouse | 832 streaming / 1792 batch | 1.75 / 3 | Documented default is a **ceiling of 90% of available memory** (6.3 to 7.2 GiB here), which would consume the whole budget; `max_server_memory_usage` is set explicitly. The streaming figure is 832 rather than 1024 to admit the RIPE Atlas collector as a resident of that profile |
| kafka | 768 | 1 | Heap defaults to `-Xmx1G`; overridden to `-Xmx512M` |
| debezium-connect | 640 | 1 | Worker heap defaults to `-Xmx2G`; overridden to `-Xmx384M` |
| flink-jobmanager | 640 | 1 | `jobmanager.memory.process.size` has **no default**; Flink's own component defaults (128 MB framework heap, 256 MB metaspace, 192 MB minimum JVM overhead) put the floor near 576 MB, which is why the ceiling is 640 and not 384 |
| flink-taskmanager | 1280 | 2 | `taskmanager.memory.process.size` has **no default**; 1280m leaves about 832 MiB of task heap |
| prometheus | 384 | 0.5 | No default; no published minimum |
| grafana | 384 | 0.5 | Published recommended minimum is 512 MB. **A deliberate deviation**, justified below |
| alertmanager | 128 | 0.25 | No default; no published guidance |
| dagster-webserver | 320 | 0.5 | No default; no published guidance for self-hosted OSS |
| dagster-daemon | 256 | 0.5 | As above |
| dagster-user-code | 256 | 0.5 | As above |
| spark | 2048 | 3 | Defaults are a 1g driver plus a 1g executor plus 10% overhead, 2252.8 MiB; `--master local[3]` with `spark.driver.memory=1536m` puts both in one JVM at 1690 MiB |
| flink-client | 512 | 0.5 | The `flink run` client, transient |
| ripe-collector | 192 | 0.25 | **No documented default**: the service is this platform's own code, so the ceiling is declared rather than derived |

**The Grafana deviation, recorded rather than hidden.** Grafana publishes 512 MB as a recommended minimum. Grafana's own guidance attributes the headroom to image rendering at about 1 GB per renderer worker, and this platform provisions dashboards as code and does not use image rendering, so the 384 MiB ceiling is defensible. The trigger for reconsideration is enabling image rendering, or any render exceeding the ceiling.

**Six of these require an explicit override of a documented default, and the register records each one with its reason.** They are collected under `documented_default_overrides` in `deployment/budgets/profiles.yaml` so a reviewer sees the deviation rather than discovering it.

**One ceiling has no documented default to override, because the service is platform-authored.** The RIPE Atlas collector is the platform's own code, so 192 MiB is a declared budget rather than a derived one. Its stated basis is a Python 3.12 interpreter holding at most 16 concurrent WebSocket subscriptions, which is RIPE Atlas's documented per-IP cap, with a bounded in-flight buffer. It is collected under `declared_ceilings` in the same register, with the trigger that would revisit it: the first measured capture, where the collector's peak RSS is recorded.

## 4. The five profiles

A profile's peak is **the sum of its resident ceilings plus the largest single transient ceiling**. A resident service is up for the whole run; a transient is a run-to-completion member the profile starts, and it overlaps the resident set while it runs. The observability overlay is **folded into** the two path profiles rather than declared alongside them, because an alert firing on a path that is not running is not an alert.

| Profile | Resident | Transient | Peak | Headroom against 7680 MiB | Reduced variant |
|---|---|---|---|---|---|
| `smoke` | none | none | 2048 MiB / 3 vCPU | 5632 MiB | none |
| `batch` | postgres, seaweedfs, polaris, clickhouse, dagster-webserver, dagster-daemon, dagster-user-code, prometheus, grafana, alertmanager | spark | 6976 MiB / 11.75 vCPU | 704 MiB | 6080 MiB, overlay dropped |
| `streaming` | postgres, seaweedfs, polaris, clickhouse, kafka, debezium-connect, flink-jobmanager, flink-taskmanager, ripe-collector, prometheus, grafana, alertmanager | flink-client | 7168 MiB / 11.75 vCPU | 512 MiB | 6272 MiB, overlay dropped |
| `observability` | prometheus, grafana, alertmanager | none | 896 MiB / 1.25 vCPU | 6784 MiB | none |
| `benchmark` | declared per run | declared per run | rule: <= 7168 MiB / 12 vCPU | n/a | none |

- **`smoke`** runs one service at a time and never the stack, so its peak is the largest single ceiling in the register, Spark's 2048 MiB.
- **`batch`** carries the larger ClickHouse ceiling because it owns the serving materialisation. Spark runs as `spark-submit --master local[3]` with `spark.driver.memory=1536m`.
- **`streaming`** carries the smaller ClickHouse ceiling because it serves one CDC table, and that ceiling is 832 MiB rather than 1024 because the profile's peak already equals the enforceable peak: the RIPE Atlas collector is a resident of this profile, so the space for it had to come from an existing resident, and ClickHouse is the resident whose reduction cannot confound the evidence. **The collector is here because incidents 1 and 6 run under this profile with the collector among their components**, and incident 1 is the live-stack injection M16 requires; before it was admitted, the profile could not evidence them. **Dagster is deliberately absent**: the completion bar fixes this profile's service list and this ticket does not re-litigate it, so the profile script starts the Flink job, and the Dagster-owned lifecycle (deploy, restart, savepoint) is exercised in `batch` against a Flink cluster brought up for the purpose. The seam is a row in the diff (section 8).
- **`observability`** is the overlay alone, for dashboard authoring and for reading a dashboard without a path.
- **`benchmark`** takes its definition from [the completion bar](completion-bar.md) section 8: one component under test at a time, never the whole path profile. Its budget is declared in each benchmark's protocol rather than as a fixed peak. Worked example, the serving bring-up of the ClickHouse layout benchmark that M5 and [section 6.5](completion-bar.md) need: ClickHouse 6144 MiB / 8 vCPU plus SeaweedFS 256 / 1, peak **6400 MiB / 9 vCPU**.

## 5. The preflight, and the refusal policy

The run refuses rather than degrades, in two tiers.

**Tier 1 - refuse.** If `MemAvailable` is below the profile's declared peak plus the 512 MiB reserve, the run does not start and names the shortfall in MiB. It does not start the services it can and hope. This is the honest answer to "what happens when a profile exceeds the host": the run refuses, it does not thrash.

**Tier 2 - offer the reduced variant.** Between 7.0 and 7.5 GiB free, the runbook offers the profile's declared reduced variant, which is the same ceilings with the observability overlay dropped: `streaming` falls to 6272 MiB and `batch` to 6080 MiB. A reduced run is **labelled as reduced in its evidence item**, and the consequence is stated in the register rather than left to be inferred: **no alert drill can be produced from a reduced run**, so the incident-laboratory items are not evidenced there.

The preflight also checks, and refuses on, each of these:

| Check | Why it is a precondition |
|---|---|
| podman >= 5.7.0 | **Correction, 2026-10-01 (issue #31).** This row declared 6.1.2, which was current stable when it was written, but 6.1.2 is not obtainable on this host: Ubuntu 26.04 packages podman 5.7.0, conda-forge stops at 5.8.3, and upstream v6.1.3 publishes only `podman-remote-static`, a remote client rather than a runtime. The floor is now the version the bring-up was executed against. Every breaking change podman 6.0.0 lists is already satisfied here - cgroups v2, the netavark network backend, the pasta rootless network stack, the sqlite database backend and nftables - so nothing the platform uses regresses. Reconsider when a podman 6.x package is available for this distribution |
| podman-compose >= 1.6.0 | 1.6.0 (2026-06-03) is current; 1.4.0, 1.5.0 and 1.6.0 were read in source and the resource-limit translation is identical across them |
| cgroups v2 | podman documents `--memory` and `--cpus` as unsupported on cgroups v1 rootless systems |
| Resource-limit delegation | On some systemd hosts a non-root user cannot set a CPU limit and `--cpus` fails with "the requested cgroup controller cpu is not available". The documented fix is a `Delegate=memory pids cpu cpuset` drop-in at `/etc/systemd/system/user@.service.d/delegate.conf` plus a re-login. This is the difference between the compose key being portable and the host being able to enforce it |
| The profile's ports free | A bind failure mid-bring-up leaves a half-started profile |
| `runtime/secrets/` complete and mode-correct | ADR-0028: a secret is a read-only file, so the preflight asserts each one exists and is mode 0600. podman-compose ignores a secret's `uid`, `gid` and `mode`, so the ownership remap has to have run as well - that is `deployment/scripts/fix-secret-ownership.sh`'s job, and the preflight does not assert it |

## 6. The bring-up runbook

One entry point per profile, in `deployment/`, in six phases; `deployment/smoke` is the smoke profile's. **The named provider is podman-compose**, named here as [section 11](completion-bar.md) requires. Its resource-limit translation was verified in its source ([research 26](research/26-compose-resource-limits-and-portability.md)), and the smoke profile's bring-up has now been executed against it (section 0). docker compose is authored for but not verified, and that is [section 13 item 11](completion-bar.md).

1. **Reset** - the profile's own containers and named volumes are removed before anything starts. **Correction, 2026-10-01 (issue #31):** the phases below were written before the runbook was executed, and the first execution showed this one was missing. A run that is interrupted leaves a port its own next run then refuses on, because the preflight cannot tell that port from another process's, and a check that passed against a previous run's data is evidence of the wrong thing.
2. **Provision** - the secret values are generated if absent and never overwritten, and the ownership remap is applied. Both are preconditions of the preflight's own secret check rather than steps a reader has to remember.
3. **Preflight** - every check in section 5. Refuse with the shortfall named, and offer the reduced variant rather than applying it.
4. **Ordered start** - dependency order, each service gated by its own readiness probe in the profile script, **never by a compose condition**. The ban stands: a self-retrying service survives a dependency that later restarts, whereas a one-shot condition check only helps at first start. Services self-retry, and the script waits.
5. **Readiness confirmation** - the profile's assertions under `tests/<profile>/` run and must pass before any evidence is captured. A profile that starts but fails its assertions is not ready. The smoke suite performs phases 4 and 5 in one pass per service, which is the isolation level [the testing strategy](testing-strategy.md) section 2 gives the profile.
6. **Teardown and reset** - section 7.

**One podman-compose behaviour the runbook depends on.** `in_pod` defaults to true, so the whole project becomes one pod named `pod_<project>`, and podman-compose emits the resource flags on `podman run` rather than on `pod create`. The per-container limit is therefore the effective limit, and no pod-level ceiling is relied on.

## 7. Teardown and reset to a known state

`podman-compose down --volumes` plus removal of the profile's scratch directories, with a `--keep` flag for a benchmark run that has to survive inspection. **Reset is proven, not asserted**: the procedure is followed by a fresh bring-up that must reach the same readiness assertion. A reset that leaves a volume behind shows up as a readiness failure on the next run rather than as a quietly different result.

## 8. The local-versus-cloud diff

What a local run cannot exercise, per [`docs/cloud-architecture.md`](cloud-architecture.md) and [the completion bar](completion-bar.md) section 13. Every row names the mechanism, the gap, and what stands in its place.

| Aspect | Local | Cloud (ADR-0027) | What the local run cannot exercise | What stands in its place |
|---|---|---|---|---|
| Object storage | SeaweedFS 4.47 `weed mini` S3 gateway | S3 | S3 request accounting and per-request cost, lifecycle transitions, storage classes, versioning semantics | The measured credential-vending shape and the local request counts, extrapolated and labelled as extrapolation |
| IAM policy evaluation | none | Real IAM | Any policy evaluation at all (M19 records it) | `tofu validate`, the static non-nesting prefix scan, and the measured `AccessDenied` on a read outside the vended prefix |
| Credential vending | Polaris vends a prefix-scoped credential against SeaweedFS STS, with a permissive `Principal: "*"` trust policy and an admin caller | Polaris assumes an IRSA role whose trust policy names Polaris's IRSA role as the only principal | Role assumption chains and the trust-policy boundary. SeaweedFS STS is not AWS STS ([section 13 item 10](completion-bar.md)) | The prefix-scope result and the 2048-byte session-policy assertion, both measured locally |
| Catalog write identity | Polaris is given the SeaweedFS S3 identity through the environment and its entrypoint (`deployment/compose/polaris`), and the catalog writes a new table's metadata with it | Polaris assumes an IRSA role | Role assumption, trust-policy evaluation and credential rotation for the catalog's own writes, as distinct from the credentials it vends to readers | The static local identity; without it a `CREATE TABLE` fails with an AWS SDK credential error, so the bronze load is gated rather than run |
| Secrets | Read-only file at `/run/secrets` from a gitignored `runtime/` | Secrets Manager projected by the CSI driver at `filePermission: "0400"` | Managed rotation, versioned retrieval, the CSI mount | The rotation classes (ADR-0028) and the one rotation demonstrated end to end |
| Compute platform | podman on one host | EKS, managed node groups | Scheduling, bin-packing, rolling upgrades, pod eviction, node loss, a Helm release | `helm lint` and `helm template` with rendered manifests committed, `kubeconform` against a pinned schema, and the compose bring-up as the runtime evidence |
| Networking | One flat compose network | A VPC with public and private subnets, NAT per AZ in the reference arm, an ALB | Routing, security groups, ingress, cross-AZ traffic | The authored topology and the static policy scan |
| TLS termination | Every listener terminates in its container | The ALB terminates the client-to-ALB hop only | The ALB-to-pod hop, which is plaintext unless re-encrypted | The five local listeners where a refusal is demonstrated, and the recorded statement of which hop is encrypted |
| Database | One PostgreSQL container | RDS | Failover, point-in-time recovery, read replicas, parameter groups, backup | The authored RDS configuration, validated statically |
| Replication | Single replica of everything | 3 Kafka brokers, 2 ClickHouse replicas, 2 Polaris replicas in the reference arm | Broker loss, replica failover, in-sync-replica behaviour | Recorded as a gap, [section 13 item 13](completion-bar.md) |
| Keys | No KMS | One CMK per bucket | Key policies and envelope encryption | Nothing; recorded as absent |
| Architecture | x86_64 host | Graviton arm64 | arm64 execution of any image | Verified arm64 manifests for 13 of 14 components, and Marquez's self-build recorded as unbuilt and unrun |
| Streaming lifecycle | The profile script starts the Flink job | Dagster owns deploy, restart and savepoint | The Dagster-driven lifecycle on the `streaming` profile | Exercised in `batch`, where Dagster is resident, against a Flink cluster brought up for the purpose |
| Provider parity | podman-compose only | containerd via EKS | docker compose behaviour | none; [section 13 item 11](completion-bar.md) records it |
| Cost | $0 | The EKS control plane at $0.10 per cluster-hour is the one unbudgeable line | Any AWS bill | The priced cost model, which is arithmetic rather than an observed invoice |

Two rows are **not** differences and are recorded so they are not mistaken for gaps: neither environment has an autoscaler ([the cloud architecture](cloud-architecture.md) section 2.3 rejects Cluster Autoscaler and Karpenter), and neither uses Spot.

## 9. What a profile run produces

Raw output goes to `runtime/runs/<profile>/<utc-timestamp>/`, which is gitignored because it is raw. A committed evidence item goes to `docs/evidence/<class>/<instance>/<item>.md` per [section 7](completion-bar.md), promoting a raw artifact into `raw/` beside it only when the artifact is small and is the thing being cited.

Captured per run:

- the resolved `podman-compose config`, which is the file the provider actually read rather than the file on disk;
- the image digests actually pulled, so a repushed tag is visible;
- the profile's declared budget and its **observed peak**, from `podman stats --no-stream` at a declared sample point;
- the assertion output from `tests/<profile>/`.

**The split between root `tests/` and CI.** `tests/<profile>/` is the only thing a reviewer runs and is **never in CI**, because CI has no stack and the load-bearing evidence does not fit in a CI runner. CI keeps running the cheap structural checks listed in [`docs/repository-decomposition.md`](repository-decomposition.md), plus the amended compose-subset lint. `smoke` stays a one-command local re-run rather than a CI job, for the same reason.

## 10. Entitlements are not budgets

Two registers, two kinds of thing, and they must not be merged.

| | `deployment/budgets/profiles.yaml` | `docs/budgets.yaml` |
|---|---|---|
| Holds | resource entitlements | measurement thresholds |
| Has a `direction` | no | yes |
| Cited by an evidence item | no | yes, through `budget_ref` |
| Judged by | the preflight, and the compose lint | the completion bar's honesty rule, [section 9](completion-bar.md) |
| Changes when | the host, the profiles or the components change | a threshold is re-declared before a new measurement |

An entitlement admitted into `docs/budgets.yaml` would let a resource ceiling be cited as the threshold a measurement is judged against, which is exactly the confusion [section 9](completion-bar.md) exists to prevent. The compose-subset lint recomputes every peak from the ceilings and fails on a mismatch, and checks that each compose file's `deploy.resources.limits` resolves to the value declared in the register.

## 11. Documented limitations

- **No CPU floor anywhere.** `deploy.resources.reservations.cpus` is enforced by neither docker compose nor podman-compose outside swarm, so every `cpus` figure is a ceiling only and a service on a busy host can be starved with no guarantee.
- **The ceilings are hard limits, so an exceedance is an OOM kill, not a slowdown.** **Correction, 2026-10-01 (issue #31):** this holds for the memory-plus-swap total and not for memory alone, per the next bullet, so "an OOM kill" is the outcome once the host's swap is exhausted. The run's assertion phase surfaces an OOM-killed profile service as a profile-budget failure rather than as an application bug.
- **The local peak is not cloud capacity.** About 44% of the minimal arm's 16 GiB, and about 29% of 24 GiB at three nodes.
- **At 7.0 GiB free, neither path profile fits.** The reduced variant is the fallback, and it cannot produce an alert drill.
- **A ceiling is enforced against memory plus swap, not against memory.** `podman run --memory=X` leaves the container's `memory.swap.max` at X as well, so a service that exceeds its ceiling can swap rather than being OOM-killed, and `memswap_limit` is exactly the compose key that does not port (completion bar section 11). The ceilings are therefore hard limits on the memory-plus-swap total, and an OOM kill is only guaranteed once the host's swap is exhausted. This is recorded rather than hidden because the register's own limitation says an exceedance is an OOM kill rather than a slowdown, and on a host with swap that is not yet true. Found and measured on 2026-10-01 by issue #31: `podman inspect` reports `Memory=67108864 MemorySwap=134217728` for a `--memory=64m` container, and `/sys/fs/cgroup/memory.swap.max` reads 67108864.
- **Only one compose provider is named.** The bring-up targets podman-compose, whose resource-limit translation was verified in its source ([research 26](research/26-compose-resource-limits-and-portability.md)); docker compose is authored for and untested. **Correction, 2026-10-01 (issue #31):** the bring-up has now been executed under podman-compose, so the untested half is docker compose alone.
- **The runbook has been executed for `smoke` and for no other profile.** Section 6's six phases ran end to end under the `smoke` profile on 2026-10-01, one service at a time. `batch`, `streaming`, `observability` and `benchmark` resolve under `podman-compose config` and pass the preflight, and **no co-resident run of any of them has happened**, so every peak in section 4 is still a budget rather than a measurement.
- **The JVM images are not all JDK 17.** Three of the five ship JDK 21 - Kafka 4.3.1, Polaris 1.7.0 and Debezium Connect 3.6.1 - and none of the three publishes a JDK-17 variant, so `deployment/tools.lock` declares the JDK each image carries and the smoke check asserts the declared value rather than one version. The measurement, the tag-list evidence and the reasoning are in the register under `jdk-17-is-a-target-not-a-universal-image-property`.
- **Four of the seventeen services are authored here and have no image yet.** `dagster-webserver`, `dagster-daemon`, `dagster-user-code` and `ripe-collector` run images whose code lands with issues #39 and #48. Their compose entries exist so every profile resolves under `podman-compose config`, but nothing brings them up, so the smoke profile's container checks cover thirteen of the seventeen ceilings. There is no digest to pin, so they are the one group `check-compose.sh` accepts without one: they are named in `UNPINNED_BUILT_SERVICES` in `deployment/tools.lock` and must reference `localhost/de-platform/`. The check that does bite now is the base image - a `FROM` under `deployment/images/` must be `python:3.12` or a JDK 17 or 21 base, and it fails on the first Dockerfile that is not.
- **The platform core emits lineage but no run reads it back from Marquez.** Marquez is in no profile: it lands with the lineage work in Phase 7. The platform core's smoke run posts one OpenLineage event to a local receiver, so the emission is proven and the read-back that would make it *visible in Marquez* is not. Trigger: Marquez admitted to a profile, which is the run that can read the event back. Recorded by issue #33.
- **The platform core's smoke run loads a contract fixture, not a gold contract.** The gold contract set lands with the contract work in Phase 1, so the loader is proven on the worked example [the data contracts](data-contracts.md) section 2 gives, committed under `tests/smoke/fixtures/`. The loader is the real one; only its input is a fixture. Trigger: the first gold contract, which the loader then reads unchanged. Recorded by issue #33.
- **The platform core resolves the table endpoint but creates no table.** Polaris writes a new table's metadata to the warehouse, which needs the catalog's region, the SeaweedFS STS role and the catalog grants the credential-vending work sets up in Phase 7. The smoke run asserts the Iceberg REST specification's own `NoSuchTableException`, so the table is addressed through REST and the create-and-load path is gated rather than skipped. Trigger: the catalog bootstrap that creates a namespace, a table and a vended-credential read. Recorded by issue #33.
- **The portable subset gained two keys.** [The completion bar](completion-bar.md) section 11 did not name `command` or `entrypoint`, and the compose-subset lint permits them. A service whose role is chosen by its command - Flink's `jobmanager` and `taskmanager`, SeaweedFS's `mini` - has no other way to declare it, and both named providers implement both keys identically. **Correction, 2026-10-01 (issue #31):** section 11 now carries the two keys and the reason, so the lint and the standard agree rather than the lint carrying a deviation. Nothing else was added, and `deploy` is still permitted only at `resources.limits.{cpus,memory,pids}`.

## 12. Sources

- [research 26](research/26-compose-resource-limits-and-portability.md): compose-spec at main commit `914ec15d`, the 2024-03-21 un-deprecation commit `65422a1f`, docker/compose `pkg/compose/create.go` (`getDeployResources`, `setLimits`), podman-compose `podman_compose.py` at tags v1.4.0, v1.5.0 and v1.6.0, podman's option documentation, and the registries' own manifests. All read 2026-09-29.
- [research 27](research/27-local-profile-memory-defaults.md): each component's own documentation, image Dockerfile or entrypoint, and source repository. All read 2026-09-29.
- [`docs/cloud-architecture.md`](cloud-architecture.md) and [ADR-0027](adr/0027-self-host-what-the-platform-operates.md): the cloud shape, the node counts and the priced arms.
- [`docs/completion-bar.md`](completion-bar.md): the profiles (section 8), the evidence schema (section 7), the honesty rule (section 9), the portable subset (section 11), the CI checks (section 12) and the named gaps (section 13).
