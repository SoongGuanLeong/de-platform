# The security evidence harness

Executes the deferred tests in [`docs/security-evidence-plan.md`](../../docs/security-evidence-plan.md) for ticket #18. It is not the platform's compose contract; the platform's bring-up is ticket #25.

## What it is

One compose file over the pinned component images, brought up one profile at a time because the whole stack does not fit in the available memory. It adds no component: every service is one of the nineteen, at its pinned version.

## Prerequisites

1. Generate the local certificates: `make -C deployment/certs certs`
2. Generate the local secrets: `deployment/compose/generate-secrets.sh`
3. Both write only under `runtime/`, which is gitignored (ADR-0028).

## Running

    podman-compose -f deployment/compose/compose.yml up -d postgres
    deployment/compose/tests/postgres.sh
    podman-compose -f deployment/compose/compose.yml down postgres

## Layout

- `compose.yml`: the services, one per deferred test profile
- `<service>/`: the per-service configuration that enables the control under test
- `tests/`: one script per component, each printing a pass or fail line per assertion and exiting non-zero on any failure
- `generate-secrets.sh`: writes the runtime secrets from openssl, refusing to overwrite an existing value
