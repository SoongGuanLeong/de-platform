# The security evidence harness

Executes the deferred tests in [`docs/security-evidence-plan.md`](../../docs/security-evidence-plan.md) for ticket #18. It is not the platform's compose contract; the platform's bring-up is ticket #25.

## What it is

One compose file over the pinned component images, brought up one profile at a time because the whole stack does not fit in the available memory. It adds no component: every service is one of the nineteen, at its pinned version.

## Prerequisites

1. Generate the local certificates: `make -C deployment/certs certs`
2. Generate the local secrets: `deployment/compose/generate-secrets.sh`
3. Both write only under `runtime/`, which is gitignored (ADR-0028).

## Running

One profile at a time, because the whole stack does not fit in the available memory.

    podman-compose -f deployment/compose/compose.yml up -d postgres
    deployment/compose/tests/postgres.sh
    podman-compose -f deployment/compose/compose.yml down postgres

    podman-compose -f deployment/compose/profiles/seaweedfs.yml up -d seaweedfs
    deployment/compose/tests/seaweedfs.sh
    podman-compose -f deployment/compose/profiles/seaweedfs.yml down seaweedfs

`tests/static.sh` needs no running service: it checks the gitignore rules, the tracked tree and the secret declarations.

## Layout

- `compose.yml`: the first three profiles (PostgreSQL, ClickHouse, Kafka), one service each
- `profiles/<name>.yml`: a self-contained compose file for one further profile, including its own top-level `secrets:` block. One file per profile so that a profile can be brought up, and authored, independently of the others
- `<service>/`: the per-service configuration that enables the control under test
- `tests/`: one script per component, each printing a pass or fail line per assertion and exiting non-zero on any failure
- `generate-secrets.sh`: writes the runtime secrets from openssl, refusing to overwrite an existing value
- `fix-secret-ownership.sh`: remaps a secret or key to the uid its container runs as, for services that cannot start as root

## The two rootless-podman costs this harness pays

1. A compose secret is mounted with the host's owner and mode, and podman-compose ignores a secret's `mode`, `uid` and `gid` fields, so a container running as a non-root user cannot read its own secret. Either the entrypoint starts as root and re-materialises the file with the right owner, or the host file is remapped with `podman unshare chown`, which makes it unreadable from the host. Recorded in `docs/security-model.md` section 2.4.
2. `runtime/certs` is mode 0700, so a non-root container user cannot traverse a directory mount of it, and such a mount would also hand the container `ca.key`, which can forge any certificate in the stack. Each service mounts the individual files it needs. Recorded in `docs/security-model.md` section 9.
