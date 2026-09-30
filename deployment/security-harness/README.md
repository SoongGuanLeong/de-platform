# The security evidence harness

Executes the deferred tests in [`docs/security-evidence-plan.md`](../../docs/security-evidence-plan.md) for ticket #18. It is not the platform's compose contract; the platform's bring-up is ticket #25.

## What it is

One compose file over the pinned component images, brought up one profile at a time because the whole stack does not fit in the available memory. It adds no component: every service is one of the twenty, at its pinned version.

## Prerequisites

1. Generate the local certificates: `make -C deployment/certs certs`
2. Generate the local secrets: `deployment/security-harness/generate-secrets.sh`
3. Both write only under `runtime/`, which is gitignored (ADR-0028).

## Running

One profile at a time, because the whole stack does not fit in the available memory.

    podman-compose -f deployment/security-harness/compose.yml up -d postgres
    until podman exec de-platform-security-postgres pg_isready -h 127.0.0.1 -p 5432 -U deplatform >/dev/null 2>&1; do sleep 1; done
    deployment/security-harness/tests/postgres.sh
    podman-compose -f deployment/security-harness/compose.yml down postgres

    podman-compose -f deployment/security-harness/profiles/seaweedfs.yml up -d seaweedfs
    until [ "$(curl -s -o /dev/null -w '%{http_code}' --cacert runtime/certs/ca.crt https://127.0.0.1:58333/)" = 403 ]; do sleep 1; done
    deployment/security-harness/tests/seaweedfs.sh
    podman-compose -f deployment/security-harness/profiles/seaweedfs.yml down seaweedfs

`tests/static.sh` needs no running service: it checks the gitignore rules, the tracked tree and the secret declarations.

### Wait for readiness before the test

`podman-compose up -d` returns when the container is created, not when the service inside it accepts connections. A test run in that window reports refused connections, which read as control failures but are not: PostgreSQL fails its six authentication and TLS assertions with `Connection refused`, and passes all of them unchanged about three seconds later. Poll the service before running its test, and bound the loop so a service that never starts fails the run rather than hanging it.

| Profile | Probe, run from the repository root | Ready when |
| --- | --- | --- |
| PostgreSQL | `podman exec de-platform-security-postgres pg_isready -h 127.0.0.1 -p 5432 -U deplatform` | exits 0 |
| ClickHouse | `podman exec de-platform-security-clickhouse clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password "$(cat runtime/secrets/clickhouse_svc_password)" -q 'select 1'` | exits 0 |
| Kafka | `podman exec de-platform-security-kafka sh -c 'grep -q "Kafka Server started" /opt/kafka/logs/server.log'` | exits 0 |
| SeaweedFS | `curl -s -o /dev/null -w '%{http_code}' --cacert runtime/certs/ca.crt https://127.0.0.1:58333/` | prints `403` |
| Grafana | `curl -s -o /dev/null -w '%{http_code}' --cacert runtime/certs/ca.crt https://127.0.0.1:53000/api/health` | prints `200` |
| Polaris | `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:58181/api/catalog/v1/config` | prints `401` |

Each probe waits on the listener the test then exercises, so a service that answers its probe has passed the test's own precondition. Kafka is the exception: its client needs a rendered SASL_SSL config, so the probe reads the broker's startup line instead. The two probes that expect a refusal status - SeaweedFS `403` and Polaris `401` - are waiting for the listener to answer at all, not for the request to succeed.

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
