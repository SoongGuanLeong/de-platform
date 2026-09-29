# 26 - Compose resource limits and provider portability

**Date of research:** 2026-09-29. Every spec, source, release and registry fact below was read on 2026-09-29 from the owning project's own repository, documentation site or registry API. File paths, line numbers and commit SHAs are given so a sceptic can re-read the same bytes.

**Scope:** ticket #25 asks how a profile's declared CPU and memory entitlement is actually enforced. The completion bar (docs/completion-bar.md section 11) restricts compose files to a portable runtime subset, and that subset as written has no key that can express a resource budget. This note answers six questions: (1) what the Compose Specification and Docker Compose do with resource limits, (2) what podman-compose does with the same keys, (3) what podman itself can express, (4) which key or keys belong in the portable subset, (5) whether the ban on depends_on: condition is a real portability constraint, and (6) the published sizes of the pinned images.

**Question answered:** which compose key or keys can carry a per-service CPU and memory budget such that both docker compose and podman-compose enforce it, and what are the exact limits of that portability?

**Ticket:** [The local development architecture](https://github.com/SoongGuanLeong/de-platform/issues/25), map #9.

**Method.** No container was run, nothing was measured on the host. Every claim is a read of: the compose-spec source of truth (spec.md, 05-services.md, deploy.md, schema/compose-spec.json) at its main commit; the Docker docs markdown that generates docs.docker.com; the docker/compose Go source; the podman-compose Python source at three tagged releases; the podman CLI option docs and troubleshooting guide; and the registries' own manifest APIs. Where a release or EOL date is claimed, the project's GitHub release list and the project's own release-cadence document are quoted, not a third-party tracker.

---

## 1. The Compose Specification and Docker Compose

### 1.1 The specification defines resource limits, in the Deploy Specification

The Compose Specification defines resource constraints under deploy.resources, split into limits (a hard ceiling the platform must enforce) and reservations (a floor the platform must guarantee). The exact keys are deploy.resources.limits.cpus, deploy.resources.limits.memory and deploy.resources.limits.pids, with deploy.resources.reservations.cpus and deploy.resources.reservations.memory [S1].

deploy.md says verbatim:

> resources configures physical resource constraints for container to run on platform. Those constraints can be configured as:
> - limits: The platform must prevent the container to allocate more.
> - reservations: The platform must guarantee the container can allocate at least the configured amount.

and then defines cpus as "a limit or reservation for how much of the available CPU resources, as number of cores, a container can use", memory as "a limit or reservation on the amount of memory a container can allocate, set as a string expressing a byte value", and pids as "a container's PIDs limit" [S1].

**Deploy is optional, and that matters.** spec.md says:

> Deploy support is an optional aspect of the Compose Specification, and is described in detail in the Compose Deploy Specification documentation. If not implemented the deploy section is ignored and the Compose file is still considered valid.

So a provider may conform to the spec and silently ignore the whole deploy block. Portability of deploy.resources.limits therefore rests on the named providers actually implementing it, not on a spec guarantee. Both named providers do, as sections 1.2 and 2 show.

### 1.2 docker compose (non-swarm) honours deploy.resources.limits

Yes. This is not an inference from a docs page; it is in the source that runs docker compose up. In docker/compose, pkg/compose/create.go, getDeployResources() builds the container's HostConfig resources and then applies the deploy block [S2]:

    func getDeployResources(s types.ServiceConfig) container.Resources {
        ...
        resources := container.Resources{
            Memory:            int64(s.MemLimit),        // line 740
            MemorySwap:        int64(s.MemSwapLimit),    // line 741
            MemoryReservation: int64(s.MemReservation),  // line 743
            CPUCount:          s.CPUCount,               // line 745
            CPUShares:         s.CPUShares,              // line 750
            NanoCPUs:          int64(s.CPUS * 1e9),      // line 751
            ...
        }
        if s.PidsLimit != 0 { resources.PidsLimit = &s.PidsLimit }   // line 757-758
        ...
        if s.Deploy != nil {
            setLimits(s.Deploy.Resources.Limits, &resources)               // line 764
            setReservations(s.Deploy.Resources.Reservations, &resources)   // line 765
        }

and setLimits() maps the deploy keys onto the same HostConfig fields [S2]:

    func setLimits(limits *types.Resource, resources *container.Resources) {
        if limits == nil { return }
        if limits.MemoryBytes != 0 { resources.Memory = int64(limits.MemoryBytes) }      // 851
        if limits.NanoCPUs != 0    { resources.NanoCPUs = int64(limits.NanoCPUs * 1e9) }  // 854
        if limits.Pids > 0         { resources.PidsLimit = &limits.Pids }                // 857
    }

Two consequences worth recording. First, deploy.resources.limits is applied **after** the top-level fields, so if both are set the deploy value wins (and only a non-zero deploy value overrides). Second, setReservations() carries the comment "Cpu reservation is a swarm option and PIDs is only a limit", so deploy.resources.reservations.cpus is **not** applied by docker compose outside swarm; only reservations.memory is [S2]. Docker Compose's current release is v5.5.1, published 2026-09-03 [S3].

### 1.3 The legacy v2 keys are now part of the Specification, not only of the legacy format

The keys mem_limit, memswap_limit, mem_reservation, cpus, cpu_shares, cpu_count, cpu_percent, cpuset and pids_limit are **top-level service keys in the current Compose Specification**, and docker compose honours them.

The decisive evidence is compose-spec commit 65422a1f0186cecb170afacd012711f9bb8d79ae, "un-deprecate cpus/mem_limit/pids_limit", committed 2024-03-21 by Nicolas De Loof, touching spec.md and 05-services.md [S4]. The diff removes the old deprecation lines and replaces them with a consistency requirement. For example, for mem_limit the diff is:

    -_DEPRECATED: use [deploy.limits.memory](deploy.md#memory)_
    +mem_limit configures a limit on the amount of memory a container can allocate, set as a string expressing a byte value.
    +When both are set, mem_limit must be consistent with the limits.memory attribute in the [Deploy Specification](deploy.md#memory)

and the same treatment is applied to cpus ("must be consistent with the cpus attribute in the Deploy Specification") and pids_limit ("must be consistent with the pids attribute in the Deploy Specification") [S4]. The keys are present in the current spec.md and 05-services.md [S1], and in the machine-readable schema schema/compose-spec.json, under the container_spec definition's properties (mem_limit at line 435, cpu_shares at 215, cpus at 250, pids_limit at 605; the service definition is allOf: [container_spec, workload_spec], so these are valid service keys) [S5].

docker compose applies them: getDeployResources() reads s.MemLimit, s.MemSwapLimit, s.MemReservation, s.CPUCount, s.CPUShares, s.CPUS and s.PidsLimit from the service config, as the block quoted in 1.2 shows [S2]. So mem_limit, memswap_limit, cpus, cpu_shares and pids_limit are all honoured by docker compose today.

**Answer to question 1.** The spec defines deploy.resources.limits.cpus and deploy.resources.limits.memory (plus .pids), and docker compose v2+ honours them in non-swarm mode. The keys mem_limit, memswap_limit, cpus, cpu_shares, pids_limit are **not** legacy-only: the spec un-deprecated them in March 2024 and docker compose honours them as top-level service keys. If both forms are present the spec requires them to be consistent and docker compose lets the deploy form win. The top-level version key is obsolete; Compose always validates against the most recent schema regardless of it [S6].

---

## 2. podman-compose

**Current release: v1.6.0, published 2026-06-03** [S7]. The project's own docs reference podman-compose 1.5.0 (docs/security-model.md line 71), so both 1.5.0 and 1.6.0 were read. The implementation is identical in the relevant function across 1.4.0 (2025-05-10), 1.5.0 (2025-07-07) and 1.6.0 (2026-06-03) [S7].

The function is container_to_cpu_res_args(), at podman_compose.py lines 968-1026 in v1.6.0 (lines 772-827 in v1.5.0, 736-790 in v1.4.0). It is reached on the live path: container_to_res_args() calls it at line 1450 of v1.6.0 [S8]. It reads and emits [S8]:

| compose key | podman flag emitted | supported? |
|---|---|---|
| deploy.resources.limits.cpus | --cpus | yes |
| deploy.resources.limits.memory | -m (--memory) | yes |
| deploy.resources.limits.pids | --pids-limit | yes |
| deploy.resources.reservations.memory | --memory-reservation | yes |
| deploy.resources.reservations.cpus | (none) | no, commented out in source |
| cpus (top level) | --cpus | yes |
| cpu_shares (top level) | --cpu-shares | yes |
| mem_limit (top level) | -m (--memory) | yes |
| mem_reservation (top level) | --memory-reservation | yes |
| pids_limit (top level) | --pids-limit | yes |
| memswap_limit (top level) | (none) | **no** |

The precedence in the source is deploy over top level: cpus = cpus_limit_v3 or cpus_limit_v2, and mem = mem_limit_v3 or mem_limit_v2. If both pids_limit and deploy.resources.limits.pids are set and differ, podman-compose raises a ValueError rather than picking one [S8].

**Does deploy.resources.limits.memory become a cgroup limit?** Yes, indirectly: podman-compose emits -m <value>, and podman's --memory "allows the memory available to a container to be constrained" [S10]. podman-compose itself does not touch cgroups; it translates the compose key into the podman CLI flag that does.

**What is broken or partial.**

1. **memswap_limit is not implemented at all.** The string memswap does not appear in podman_compose.py in v1.4.0, v1.5.0 or v1.6.0 (grep count 0 in each). docker compose honours it (create.go line 741). So memswap_limit is a Docker-only key and cannot go in the portable subset.
2. **deploy.resources.reservations.cpus is not implemented** (the assignment line is commented out in the source), and docker compose does not apply it outside swarm either. Neither provider enforces a CPU reservation, so a CPU floor is not portable.
3. **The swarm-only deploy keys are absent.** endpoint_mode, placement, update_config, rollback_config and restart_policy have zero occurrences in podman_compose.py v1.6.0. replicas and mode appear only in a narrow handling path (lines 2753-2759). So if deploy is admitted to the portable subset at all, only the resources.limits slice is portable.
4. **No declarative cgroup knob.** Open issue #1382 (created 2026-01-25, still open) asks for x-podman.cgroup_conf so that memory.high can be set declaratively; today it is only reachable through the podman-compose --podman-run-args escape hatch [S9]. That is a podman-only extension, so it is outside the portable subset by the completion bar's own rule.

**Tracker history, checked rather than assumed.** Issue #120 "Add support for resource constraints" (opened 2020-02-29, closed 2021-06-22) is the request that introduced deploy.resources translation; it uses exactly the deploy.resources.limits.{cpus,memory} example [S9]. Issue #417 "Memory restriction" (opened 2022-02-02, closed 2022-02-12) reported that --memory did not appear in the generated podman run command; the code today emits -m, so that report is historical, not current [S9]. No open issue was found for deploy.resources (GitHub issue search for "deploy.resources" in the repo returns 0 results).

**Two operational caveats that are podman's, not podman-compose's, and that bear on a rootless host.**

- **cgroups v1 rootless.** podman's --memory and --cpus option docs both say "This option is not supported on cgroups V1 rootless systems" [S10].
- **Resource-limit delegation.** podman's troubleshooting guide section 26, "Running containers with resource limits fails with a permissions error", says that on some systemd-based systems non-root users lack resource limit delegation, and --cpus / --cpu-shares fail with "the requested cgroup controller cpu is not available". The documented fix is a systemd drop-in at /etc/systemd/system/user@.service.d/delegate.conf containing Delegate=memory pids cpu cpuset, followed by a re-login [S11]. This is the difference between "the compose key is portable" and "the host can enforce it", and it belongs in ticket #25's runbook as a precondition check.
- **Pods.** podman-compose defaults to in_pod = True, creating one pod named pod_<project> for the whole project (resolve_pod_name() returns pod_<project_name> when in_pod is unset, podman_compose.py line 2417-2432), and it emits the resource flags on podman run (container level), not on pod create. podman's pod-create docs say resource flags "work by setting the limits explicitly in the pod's cgroup parent for all containers joining the pod. A container can override the resource limits when joining a pod" [S12], so a per-container limit is the effective limit. This was read from source and docs, not executed.

**Answer to question 2.** podman-compose 1.6.0 (and 1.5.0, and 1.4.0) maps deploy.resources.limits.memory to podman -m and deploy.resources.limits.cpus to podman --cpus, and also supports the top-level mem_limit / cpus / cpu_shares / mem_reservation / pids_limit keys. It does **not** support memswap_limit, and neither provider enforces deploy.resources.reservations.cpus. Nothing in the supported set was found to be broken in the source; the only open gap is the podman-only cgroup_conf extension.

---

## 3. podman itself

**podman run / podman create can express both limits.** The option documentation files in the podman repository (docs/source/markdown/options/) define [S10]:

- --memory, -m=number[unit] : "Memory limit. A unit can be b, k, m, or g. Allows the memory available to a container to be constrained." "This option is not supported on cgroups V1 rootless systems."
- --memory-reservation=number[unit] : memory soft limit.
- --memory-swap=number[unit] : "A limit value equal to memory plus swap. Must be used with the -m (--memory) flag."
- --cpus=number : "Number of CPUs. The default is 0.0 which means no limit. This is shorthand for --cpu-period and --cpu-quota." "This option is not supported on cgroups V1 rootless systems."
- --cpu-shares, -c=shares : relative CPU weight, default 1024.
- --pids-limit=limit : "Tune the container's pids limit. Set to -1 to have unlimited pids."

So the full set that podman-compose would have to emit exists in podman. The only key in the compose portable candidate set that podman could express but podman-compose does not translate is memswap_limit (podman has --memory-swap).

**Current stable podman release and date.** As of 2026-09-29 the newest stable release is **v6.1.2, published 2026-09-16**. v6.1.1 was published 2026-09-02, so a 6.1.1 or later release does exist, and 6.1.2 is one patch newer. The 5.x line's newest patch is v5.8.7 (2026-09-16) [S13].

**The 5.7 EOL claim is confirmed.** The map says the host's podman 5.7 has been end-of-life since 2026-02-12. The project's own RELEASE_PROCESS.md says "Upstream major or minor releases occur the 2nd week of February, May, August, November", and podman only maintains the newest minor branch [S14]. The release dates fit exactly: v5.7.0 was published 2025-11-11 and v5.8.0 was published 2026-02-12 [S13]. 5.7 therefore ceased to be the current minor on 2026-02-12, which is the date the map records. The recommendation to pin 6.1.1 or later is correct; on 2026-09-29 the current pin would be 6.1.2.

**Answer to question 3.** Yes, podman run/create express memory and CPU limits with --memory and --cpus (plus --memory-reservation, --memory-swap, --cpu-shares and --pids-limit). Current stable is 6.1.2 (2026-09-16); 6.1.1 exists (2026-09-02); 5.7's end of life on 2026-02-12 is confirmed by the project's release cadence and the 5.8.0 release date.

---

## 4. The portability consequence, and what to put in the subset

**Both providers honour the same pair.** docker compose applies deploy.resources.limits.cpus and .memory to the container HostConfig [S2]; podman-compose translates the same two keys to --cpus and -m [S8]. Both also honour the top-level cpus and mem_limit keys. So there is no provider split on CPU and memory limits, and no need to fall back to a provider-specific key.

**The single portable pair:** deploy.resources.limits.cpus and deploy.resources.limits.memory. Add deploy.resources.limits.pids if a PID ceiling is wanted; both providers translate it to --pids-limit [S2, S8].

**What does not port, stated plainly.**

- memswap_limit : docker compose honours it (create.go line 741), podman-compose silently ignores it (absent from source in 1.4.0 through 1.6.0). Do not put it in the subset.
- deploy.resources.reservations.cpus : neither provider enforces it outside swarm. Do not rely on it for a CPU floor. reservations.memory does port (docker compose maps it to MemoryReservation, podman-compose to --memory-reservation), so a memory floor is portable if wanted.
- The rest of deploy (mode, replicas, placement, endpoint_mode, update_config, rollback_config, restart_policy) : swarm-only, not implemented by podman-compose. Keep them rejected.

**The honest caveat on the pair.** deploy is the *optional* Deploy Specification; a conforming provider is allowed to ignore it (section 1.1). The portability of deploy.resources.limits therefore comes from the two named providers both choosing to implement it, which was verified in source on 2026-09-29, not from a spec mandate. If the subset prefers a key the *core* service spec defines rather than the optional deploy spec, the alternative pair is the top-level cpus and mem_limit, which both providers also honour [S2, S8]. The trade-off between the two is: deploy.resources.limits is the canonical grouping that Docker's docs and the spec point at, while top-level cpus/mem_limit sits in the core service model rather than the optional one. The spec requires the two forms to be consistent if both are present, so mixing them in one file is a hazard rather than a strategy [S4].

**Design consequence for the completion bar.** The subset currently lists no deploy key at all. Admitting deploy.resources.limits means admitting a narrow slice of the deploy subtree, so the CI lint named in completion-bar.md section 12 ("compose files contain none of the keys outside the portable subset") must be changed from "no deploy" to "deploy allowed only at resources.limits.{cpus,memory,pids}" and must continue to reject the swarm-only deploy subtrees. This is a lint change, not a new mechanism.

**Answer to question 4.** The portable pair is deploy.resources.limits.cpus and deploy.resources.limits.memory, optionally plus .pids. Both docker compose and podman-compose enforce it. The only compose limit key that does not port is memswap_limit, and no provider enforces a CPU reservation outside swarm.

---

## 5. depends_on with condition, and start_period

**condition is part of the Compose Specification.** spec.md defines the depends_on long syntax with a condition field taking service_started, service_healthy or service_completed_successfully, alongside restart and required [S1]:

> - condition: Sets the condition under which dependency is considered satisfied
>   - service_started: An equivalent of the short syntax described above
>   - service_healthy: Specifies that a dependency is expected to be "healthy" (as indicated by healthcheck) before starting a dependent service.
>   - service_completed_successfully: Specifies that a dependency is expected to run to successful completion before starting a dependent service.

**Both providers implement it.** docker compose applies the condition when bringing services up. podman-compose also implements it, which is the less obvious half: it maps the three conditions to ServiceDependencyCondition (podman_compose.py lines 1574-1576), normalises a bare depends_on entry to condition service_started (lines 2046-2062), and enforces the condition by calling podman wait --condition=healthy|running|stopped on the dependency containers (check_dep_conditions(), lines 3498-3530). It only skips the check on podman older than 4.6.0, logging a warning; the host is pinned to 6.1.x, so that path does not apply [S8].

**healthcheck with start_period is supported by both.** podman-compose maps start_period to --health-start-period (line 1512-1513), and interval, timeout, start_interval and retries as well [S8]. docker compose supports the same fields.

**Answer to question 5.** depends_on with condition is a Compose Specification feature and both providers honour it; the ban in the completion bar is a deliberate architectural choice, not a portability constraint. The stated reason ("services self-retry rather than depending on health-based start ordering") is a resilience property: a self-retrying service survives a dependency that later restarts, whereas a one-shot condition check only helps at first start. That is a defensible reason to keep the ban, but it should be recorded as a design decision rather than as a claim that the providers cannot do it. The same applies to start_period, which the subset already permits and both providers support.

---

## 6. Published image sizes for the pinned images

Sizes are the sum of the amd64 image manifest's layer blob sizes, read from each image's own manifest through the registry API on 2026-09-29. This is the compressed download size, which is what the manifest actually publishes [S15].

| image | tag checked | amd64 compressed size |
|---|---|---|
| postgres | 18-alpine | 120.0 MB |
| apache/kafka | 4.3.1 | 238.9 MB |
| clickhouse/clickhouse-server | 26.8.13.2 | 278.6 MB |
| apache/polaris | 1.7.0 | 413.1 MB |
| chrislusf/seaweedfs | 4.47 | 195.2 MB |
| grafana/grafana | 13.2.2 | 475.7 MB |
| apache/flink | 2.1.3-java17 | 668.0 MB |
| apache/spark | 4.1.3-java17 | 796.6 MB |

Sum of the eight: approximately 3.19 GB compressed. Against the host's 231 GB disk this is not a constraint; the disk question for ticket #25 is volumes and data, not images.

**Tags used for flink and spark.** The assignment named apache/flink and apache/spark without tags. The tags checked are the pins recorded in research 24 (2.1.3-java17 and 4.1.3-java17). A different tag is a different manifest and a different size.

**Uncompressed sizes are not published, so none is claimed.** An OCI image manifest carries only the compressed layer sizes; the image config blob carries rootfs.diff_ids, which are digests without sizes. The uncompressed size is only known after pulling and decompressing, which this note did not do. Docker Hub's tag API does expose a full_size field, but it is not an uncompressed figure: for postgres, kafka, clickhouse, polaris, grafana, flink and spark it returns exactly the compressed sum, and for chrislusf/seaweedfs it returns 91.6 MB while the manifest's layers sum to 195.2 MB, so it is not even internally consistent for that repository. It is recorded here only as a discrepancy to be aware of, not as a size.

**Answer to question 6.** Compressed sizes are in the table above, from the registries' own manifests. Uncompressed sizes could not be confirmed from any primary source and are not estimated.

---

## 7. Not confirmed, and limitations

- **Nothing was executed.** No compose file was run under either provider, no container was created, and no limit was observed to take effect. The podman-compose and docker compose claims are reads of their source at named commits and tags. A runtime check that a declared limit actually lands in the container's cgroup is a container-verification step, not a source-read step, and is not claimed here.
- **The exact compose-spec revision read.** compose-spec publishes no releases or tags (the tags and releases API endpoints both return empty), so the spec is cited at main commit 914ec15d1fa498969c0df5c1d672306db3256089, dated 2026-09-17, and the specific un-deprecation is cited at commit 65422a1f, dated 2024-03-21. The spec has no version number to pin to.
- **docker/compose was read at main, last commit touching pkg/compose/create.go 063ef45da1f1 (2026-09-10); the repository head on 2026-09-29 was 32bddfc4c693 (2026-09-25).** Line numbers are from the main revision read on 2026-09-29 and may drift.
- **"docker compose v2" is the Go-plugin generation, and it is now versioned 5.x.** The current release is v5.5.1 (2026-09-03) [S3]. The question's phrasing "docker compose v2, non-swarm" was answered against this current release.
- **podman-compose's default pod mode was read but not exercised.** The source and podman's pod-create docs both indicate a per-container limit overrides the pod cgroup, but no container was run to confirm the emitted flags are accepted when the container joins the pod.
- **The podman option docs are branch documentation.** They were read from containers/podman main (head 602de6d1d027, 2026-09-29), not from the pinned 6.1.2 tag. The flags are long-standing and stable, but the exact wording is main's.
- **Image sizes are a point-in-time registry read.** A tag can be repushed. Each row is the manifest at 2026-09-29.
- **The Docker Hub full_size field for SeaweedFS is inconsistent with the manifest and was not resolved.** It is possible the Hub value is stale for that repository. The manifest layer sum is treated as authoritative for the download size.

---

## 8. Sources

All accessed 2026-09-29.

- [S1] Compose Specification, main commit 914ec15d1fa498969c0df5c1d672306db3256089 (2026-09-17):
  - spec.md - https://raw.githubusercontent.com/compose-spec/compose-spec/main/spec.md (deploy optional at lines 230-234; cpus at 360-366; cpu_shares at 326-328; mem_limit at 1432-1437; memswap_limit at 1456-1467; pids_limit at 1778-1786; depends_on long syntax and condition at 580-670; healthcheck and start_period at 1226-1242)
  - deploy.md - https://raw.githubusercontent.com/compose-spec/compose-spec/main/deploy.md (resources, limits, reservations, cpus, memory, pids at lines 104-143)
  - 05-services.md - https://raw.githubusercontent.com/compose-spec/compose-spec/main/05-services.md (cpus at 149; cpu_shares at 115; mem_limit at 1221; memswap_limit at 1245; pids_limit at 1567)
- [S2] docker/compose source, pkg/compose/create.go - https://raw.githubusercontent.com/docker/compose/main/pkg/compose/create.go (getDeployResources at line 732; top-level fields at 740-751 and 757-758; setLimits/setReservations calls at 764-765; setReservations at 825-844 with the "Cpu reservation is a swarm option" comment; setLimits at 846-858). Last commit touching this file: 063ef45da1f1, 2026-09-10.
- [S3] docker/compose releases - https://api.github.com/repos/docker/compose/releases (v5.5.1, 2026-09-03).
- [S4] compose-spec commit 65422a1f0186cecb170afacd012711f9bb8d79ae, "un-deprecate cpus/mem_limit/pids_limit", Nicolas De Loof, 2024-03-21 - https://api.github.com/repos/compose-spec/compose-spec/commits/65422a1f01 (diff against spec.md and 05-services.md).
- [S5] compose-spec JSON schema, schema/compose-spec.json - https://raw.githubusercontent.com/compose-spec/compose-spec/main/schema/compose-spec.json (container_spec properties: cpu_shares line 215, cpus line 250, mem_limit line 435, pids_limit line 605; service is allOf container_spec + workload_spec).
- [S6] Docker docs, Version and name top-level elements - https://raw.githubusercontent.com/docker/docs/main/content/reference/compose-file/version-and-name.md ("The top-level version property ... is only informative ... Compose always uses the most recent schema to validate the Compose file, regardless of the version field").
- [S7] podman-compose releases and tags - https://api.github.com/repos/containers/podman-compose/releases (v1.6.0, 2026-06-03; v1.5.0, 2025-07-07; v1.4.0, 2025-05-10).
- [S8] podman-compose source, podman_compose.py, read at tags v1.6.0, v1.5.0 and v1.4.0:
  - https://raw.githubusercontent.com/containers/podman-compose/v1.6.0/podman_compose.py (container_to_cpu_res_args 968-1026; call site 1450; healthcheck 1471-1519; dependency conditions 1555-1576; depends_on normalisation 2046-2062; check_dep_conditions 3498-3530; in_pod default 2417-2432)
  - https://raw.githubusercontent.com/containers/podman-compose/v1.5.0/podman_compose.py (container_to_cpu_res_args 772-827)
  - https://raw.githubusercontent.com/containers/podman-compose/v1.4.0/podman_compose.py (container_to_cpu_res_args 736-790)
- [S9] podman-compose issue tracker - https://api.github.com/repos/containers/podman-compose/issues (issue #120 "Add support for resource constraints", closed 2021-06-22; issue #417 "Memory restriction", closed 2022-02-12; issue #1382 "support cgroup-conf in compose yaml file", open, created 2026-01-25). Issue search for "deploy.resources" returns 0 results.
- [S10] podman option documentation, main branch - https://raw.githubusercontent.com/containers/podman/main/docs/source/markdown/options/ (memory.md; memory-reservation.md; memory-swap.md; cpus.container.md; cpu-shares.md; pids-limit.md).
- [S11] podman troubleshooting guide, section 26 - https://raw.githubusercontent.com/containers/podman/main/troubleshooting.md ("Running containers with resource limits fails with a permissions error"; symptom "the requested cgroup controller cpu is not available"; fix Delegate=memory pids cpu cpuset in /etc/systemd/system/user@.service.d/delegate.conf).
- [S12] podman pod create documentation, main branch - https://raw.githubusercontent.com/containers/podman/main/docs/source/markdown/podman-pod-create.1.md.in (lines 26-28: resource flags set the pod cgroup parent and a container can override; examples at 225-252).
- [S13] podman releases - https://api.github.com/repos/containers/podman/releases (v6.1.2, 2026-09-16; v6.1.1, 2026-09-02; v5.8.7, 2026-09-16; v5.8.0, 2026-02-12; v5.7.0, 2025-11-11).
- [S14] podman release process and cadence - https://raw.githubusercontent.com/containers/podman/main/RELEASE_PROCESS.md ("Upstream major or minor releases occur the 2nd week of February, May, August, November").
- [S15] Registry manifest APIs, read 2026-09-29: Docker Hub token at https://auth.docker.io/token?service=registry.docker.io&scope=repository:<repo>:pull and manifests at https://registry-1.docker.io/v2/<repo>/manifests/<tag>, with the OCI index, Docker manifest list, OCI manifest and Docker v2 manifest media types accepted. Used for library/postgres:18-alpine, apache/kafka:4.3.1, clickhouse/clickhouse-server:26.8.13.2, apache/polaris:1.7.0, chrislusf/seaweedfs:4.47, grafana/grafana:13.2.2, apache/flink:2.1.3-java17, apache/spark:4.1.3-java17. Docker Hub tag API https://hub.docker.com/v2/repositories/<repo>/tags/<tag> for the full_size cross-check.
- [S16] docs/completion-bar.md section 11 (the portable runtime subset) and section 12 (the CI lint) - the constraint this note is answering.
- [S17] docs/security-model.md line 71 - records podman-compose 1.5.0 as the version in use, which is why 1.5.0 was read as well as 1.6.0.
- [S18] docs/research/24-arm64-image-availability.md - the flink and spark tags checked here (2.1.3-java17, 4.1.3-java17) are the pins recorded there.
