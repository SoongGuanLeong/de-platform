# The container set and the profile compose files

One self-contained compose file per profile. Self-contained on purpose: a
reviewer reads one file and sees everything that profile runs, and the
alternative — a base file plus per-profile overlays — makes the resolved set
something a reader has to compute. The cost is that a shared service body
appears in more than one file, so `deployment/scripts/check-compose.sh` asserts
that every limit resolves against the register and that every image reference is
the one `deployment/tools.lock` holds.

| File | Profile | Services |
|---|---|---|
| `smoke.yml` | `smoke` | the thirteen services with a published image, one at a time |
| `batch.yml` | `batch` | PostgreSQL, SeaweedFS, Polaris, ClickHouse, Dagster, Spark, the observability overlay |
| `streaming.yml` | `streaming` | PostgreSQL, SeaweedFS, Polaris, ClickHouse, Kafka, Debezium Connect, Flink, the RIPE collector, the observability overlay |
| `observability.yml` | `observability` | Prometheus, Grafana, Alertmanager |
| `benchmark.yml` | `benchmark` | the ClickHouse layout benchmark's serving bring-up |

## Running one

    deployment/smoke                       # the documented smoke command
    deployment/scripts/preflight.sh batch  # refuse-or-offer, before anything starts
    podman-compose -f deployment/compose/batch.yml config
    podman-compose -f deployment/compose/batch.yml up -d
    podman-compose -f deployment/compose/batch.yml down --volumes

`deployment/smoke` is the only command a reader needs: it provisions the
secrets, runs the preflight and then the suite, with no step in between.

## What is pinned, and where

Every image reference is `repo:tag@sha256:<index digest>`. The index digest is
pinned rather than a platform-specific digest so one reference resolves on the
x86_64 local host and on a Graviton node. The same string is in
`deployment/tools.lock`, and the lint fails when the two disagree.

The JDK each JVM image carries is declared per service in the same file.
Research 03 recommended pinning every JVM image to JDK 17; three of the pinned
images ship JDK 21 and publish no JDK-17 variant, so the declaration is what is
asserted, and the lint fails on a value outside 17 and 21. `tests/smoke` asserts
each container reports its declared value.

Four services are backed by platform-authored images that do not exist yet:
`dagster-webserver`, `dagster-daemon`, `dagster-user-code` and
`ripe-collector`. Their compose entries are here so `podman-compose config`
resolves the profile, but nothing brings them up, because there is no code for
them to run until issues #39 and #48 land. `deployment/tools.lock` names them
under `UNPINNED_BUILT_SERVICES` so the reason is visible rather than inferred
from an absence.

## Secrets

Secrets are read-only files under `runtime/` (gitignored), mounted at
`/run/secrets/<name>`, per ADR-0028. They are bind mounts rather than the
compose `secrets` mechanism because podman-compose ignores a compose secret's
`uid`, `gid` and `mode`, so a container running as a non-root user cannot read
its own secret either way; the bind mount at least makes the mount point
explicit. `deployment/scripts/fix-secret-ownership.sh` applies the ownership
remap the design records as a cost of the mechanism.

## What the compose files deliberately do not carry

TLS. Every listener in the security model terminates TLS in its container, and
the security evidence harness demonstrates it for six of them; the smoke profile
is a liveness and version check rather than a security check, and the TLS matrix
belongs to the phase that owns the security model. Recorded as a limitation
rather than left to be inferred.
