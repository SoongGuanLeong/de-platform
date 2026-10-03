"""The batch profile's TPC-C driver integration test (ticket #54).

The driver's live path is the driver process plus its real dependency, a real
PostgreSQL: the integration level of docs/testing-strategy.md section 2. The
suite brings PostgreSQL up alone rather than the whole batch profile, so the
profile's peak is never reached. It follows the runbook order of
docs/local-development.md section 6: provision, ordered start, readiness, and
teardown, with the teardown first so an interrupted run cannot poison the next.

The warehouse count is read from TPCC_TEST_WAREHOUSES and defaults to 1. W=10 is
the declared correctness slice (docs/testing-strategy.md section 4.1) and is run
by setting the variable; W=1 keeps the default suite fast while still exercising
every live path.
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPOSE = ROOT + "/deployment/compose/batch.yml"
PROJECT = "de-platform-batch"
SERVICE = "postgres"
PORT = 55432


def run(argv, timeout=600):
    return subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
    )


def compose(*args, timeout=900):
    return run(["podman-compose", "-f", COMPOSE, *args], timeout=timeout)


def container_of(service):
    result = run(
        [
            "podman",
            "ps",
            "-a",
            "--filter",
            "label=com.docker.compose.service=" + service,
            "--filter",
            "label=io.podman.compose.project=" + PROJECT,
            "--format",
            "{{.Names}}",
        ],
        timeout=60,
    )
    names = [line for line in result.stdout.split() if line]
    return names[0] if names else None


def in_container(service, argv, timeout=180):
    return compose("exec", "-T", service, *argv, timeout=timeout)


def wait_for(predicate, timeout, interval=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except Exception:
            value = None
        if value:
            return value
        time.sleep(interval)
    return None


def postgres_ready():
    result = in_container(SERVICE, ["pg_isready", "-h", "127.0.0.1", "-U", "deplatform"])
    return result.returncode == 0


@pytest.fixture(scope="module")
def tpcc_dsn():
    # An existing database can be named instead of bringing the profile's
    # PostgreSQL up, so the suite can run against an isolated instance and not
    # contend for the shared de-platform-batch project.
    override = os.environ.get("TPCC_TEST_DSN")
    if override:
        yield override
        return
    run(["bash", "deployment/scripts/generate-secrets.sh"])
    compose("down", "--volumes", timeout=600)
    try:
        result = compose("up", "-d", SERVICE, timeout=900)
        if result.returncode != 0:
            raise AssertionError(
                "podman-compose up failed for postgres:\n" + result.stdout + result.stderr
            )
        if not wait_for(postgres_ready, timeout=300):
            raise AssertionError(
                "postgres did not become ready in 300s:\n" + compose("ps", timeout=120).stdout
            )
        password = in_container(SERVICE, ["cat", "/run/secrets/postgres_superuser_password"])
        if password.returncode != 0:
            raise AssertionError("could not read the superuser password:\n" + password.stderr)
        yield (
            "postgresql://deplatform:"
            + password.stdout.strip()
            + "@127.0.0.1:"
            + str(PORT)
            + "/deplatform"
        )
    finally:
        compose("down", "--volumes", timeout=600)
