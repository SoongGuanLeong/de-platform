"""The smoke profile's container checks (issue #31, acceptance criteria 1 and 2).

The smoke profile runs one service at a time and never the stack
(docs/local-development.md section 4), so each case brings its own unit up, waits
for it, runs the check, asserts the unit was not OOM-killed, and tears the unit
down again. A unit is either one service or a service plus the single dependency
its check needs, which is the integration level of docs/testing-strategy.md
section 2.

Every check is a real request to the running service or a real command inside
it, never a container-is-running assertion, and every JVM unit additionally
asserts that the container reports the JDK deployment/tools.lock declares for its image.

The preflight runs before this suite rather than beside it: deployment/smoke
calls it first, so a host that cannot hold the run never reaches a case.

The helpers and the cases live here rather than in test_smoke.py because the
workspace collects with --import-mode=importlib, under which a test module
cannot import its own conftest by name. test_smoke.py therefore holds the test
and nothing else.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPOSE = ROOT + "/deployment/compose/smoke.yml"
PROJECT = "de-platform-smoke"
PROFILE = "smoke"

# The profile's declared peak, from deployment/budgets/profiles.yaml. An OOM
# kill is reported against it, so the failure names a budget rather than an
# application bug (docs/local-development.md section 11).
PEAK_MIB = 2048


def load_lock():
    """deployment/tools.lock, parsed as its KEY="value" assignments."""
    values = {}
    with open(ROOT + "/deployment/tools.lock", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            values[key.strip()] = raw.strip().strip('"')
    return values


LOCK = load_lock()


class ProfileBudgetFailure(AssertionError):
    """A profile service was OOM-killed, which is a budget failure, not a bug."""


# ---------------------------------------------------------------------------
# Running a container
# ---------------------------------------------------------------------------


def run(argv, timeout=600):
    return subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
    )


def compose(*args, timeout=900):
    return run(["podman-compose", "-f", COMPOSE, *args], timeout=timeout)


def container_of(service):
    """The container a compose service runs as, found by label rather than by
    assuming a naming scheme."""
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
    """Run argv inside a service's container. podman-compose exec is interactive,
    so stdin is closed or it waits for a terminal that never comes."""
    return compose("exec", "-T", service, *argv, timeout=timeout)


def http_status(url, timeout=30):
    result = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], timeout=timeout)
    return result.stdout.strip()


def http_body(url, timeout=30):
    return run(["curl", "-s", url], timeout=timeout).stdout


def oom_killed(service):
    name = container_of(service)
    if name is None:
        return False
    result = run(["podman", "inspect", name, "--format", "{{.State.OOMKilled}}"], timeout=60)
    return result.stdout.strip() == "true"


def wait_for(predicate, timeout, interval=2.0):
    """Poll a predicate until it returns a truthy value or the deadline passes.

    A refused connection is an expected transient while a service starts, so a
    raising predicate counts as not-ready rather than as a failure.
    """
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


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def exec_ok(service, argv, expect=None, timeout=180):
    def check():
        result = in_container(service, argv, timeout=timeout)
        text = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            return None
        if expect is not None and expect not in text:
            return None
        return text

    return check


def http_is(url, expect):
    def check():
        return http_status(url) == expect

    return check


def exited_with(service, needles):
    """A run-to-completion service: assert its exit code and its output."""

    def check():
        name = container_of(service)
        if name is None:
            return None
        state = run(
            ["podman", "inspect", name, "--format", "{{.State.ExitCode}}"], timeout=60
        ).stdout.strip()
        if state != "0":
            return None
        logs = run(["podman", "logs", name], timeout=60)
        text = logs.stdout + logs.stderr
        return text if all(needle in text for needle in needles) else None

    return check


def jdk(service):
    """The container's JVM must report the JDK deployment/tools.lock declares.

    Research 03 recommended pinning every JVM image to JDK 17. Three of the
    pinned upstream images ship JDK 21 and publish no JDK-17 variant, so what is
    asserted here is the declared value per image, and check-compose.sh
    constrains every declaration to 17 or 21. The measurement behind each
    declaration is recorded in deployment/tools.lock.
    """
    declared = LOCK["JVM_JDK_" + service.replace("-", "_")]

    def check():
        result = in_container(service, ["java", "-version"])
        text = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            return None
        return text if 'version "' + declared in text else None

    return check


def kafka_broker():
    def check():
        result = in_container(
            "kafka",
            ["/opt/kafka/bin/kafka-broker-api-versions.sh", "--bootstrap-server", "127.0.0.1:9092"],
        )
        return result if result.returncode == 0 else None

    return check


def flink_taskmanager_registered():
    def check():
        if http_status("http://127.0.0.1:58081/overview") != "200":
            return None
        body = http_body("http://127.0.0.1:58081/taskmanagers")
        return body if '"taskmanagers":[' in body and '"id"' in body else None

    return check


def grafana_health():
    def check():
        if http_status("http://127.0.0.1:53000/api/health") != "200":
            return None
        body = http_body("http://127.0.0.1:53000/api/health")
        return body if '"database":"ok"' in body.replace(" ", "") else None

    return check


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    name: str
    services: list
    checks: list = field(default_factory=list)
    timeout: int = 300


UNITS = [
    Unit(
        "postgres",
        ["postgres"],
        checks=[
            (
                "psql answers select 1",
                exec_ok(
                    "postgres",
                    ["psql", "-U", "deplatform", "-d", "deplatform", "-tAc", "select 1"],
                    expect="1",
                ),
            ),
        ],
    ),
    Unit(
        "seaweedfs",
        ["seaweedfs"],
        checks=[
            (
                "the master answers its cluster status",
                http_is("http://127.0.0.1:59333/cluster/status", "200"),
            ),
            (
                "the S3 gateway refuses an unauthenticated request",
                http_is("http://127.0.0.1:58333/", "403"),
            ),
        ],
    ),
    Unit(
        "polaris",
        ["postgres", "polaris"],
        checks=[
            (
                "the catalog REST endpoint refuses an unauthenticated config read",
                http_is("http://127.0.0.1:58181/api/catalog/v1/config", "401"),
            ),
            ("the JVM reports the JDK tools.lock declares", jdk("polaris")),
        ],
    ),
    Unit(
        "clickhouse",
        ["clickhouse"],
        checks=[
            (
                "clickhouse-client answers select 1",
                exec_ok("clickhouse", ["clickhouse-client", "--query", "select 1"], expect="1"),
            ),
            (
                "the server's memory ceiling is the register's, not the image default",
                exec_ok(
                    "clickhouse",
                    [
                        "clickhouse-client",
                        "--query",
                        "select value from system.server_settings"
                        " where name = 'max_server_memory_usage'",
                    ],
                    expect="872415232",
                ),
            ),
        ],
    ),
    Unit(
        "kafka",
        ["kafka"],
        checks=[
            ("the broker answers the API-versions request", kafka_broker()),
            ("the JVM reports the JDK tools.lock declares", jdk("kafka")),
        ],
    ),
    Unit(
        "debezium-connect",
        ["kafka", "debezium-connect"],
        checks=[
            (
                "the Connect REST API answers an empty connector list",
                http_is("http://127.0.0.1:58083/connectors", "200"),
            ),
            ("the JVM reports the JDK tools.lock declares", jdk("debezium-connect")),
        ],
    ),
    Unit(
        "flink",
        ["flink-jobmanager", "flink-taskmanager"],
        checks=[
            (
                "the jobmanager answers its overview",
                http_is("http://127.0.0.1:58081/overview", "200"),
            ),
            ("the taskmanager registers with the jobmanager", flink_taskmanager_registered()),
            ("the jobmanager JVM reports the JDK tools.lock declares", jdk("flink-jobmanager")),
            ("the taskmanager JVM reports the JDK tools.lock declares", jdk("flink-taskmanager")),
        ],
    ),
    Unit(
        "flink-client",
        ["flink-jobmanager", "flink-client"],
        checks=[
            (
                "the client reports the pinned Flink version",
                exited_with("flink-client", ["Version: 2.1.3"]),
            ),
        ],
    ),
    Unit(
        "spark",
        ["spark"],
        checks=[
            (
                "spark-submit reports the pinned Spark version",
                exited_with("spark", ["version 4.1.3"]),
            ),
        ],
    ),
    Unit(
        "prometheus",
        ["prometheus"],
        checks=[
            ("prometheus is healthy", http_is("http://127.0.0.1:59090/-/healthy", "200")),
            ("prometheus is ready", http_is("http://127.0.0.1:59090/-/ready", "200")),
        ],
    ),
    Unit(
        "grafana",
        ["grafana"],
        checks=[
            ("grafana reports a healthy database", grafana_health()),
        ],
    ),
    Unit(
        "alertmanager",
        ["alertmanager"],
        checks=[
            ("alertmanager is healthy", http_is("http://127.0.0.1:59093/-/healthy", "200")),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Running a case
# ---------------------------------------------------------------------------


class Running:
    """A brought-up unit, with the assertion that turns an OOM kill into a
    profile-budget failure rather than an application bug."""

    def __init__(self, unit):
        self.unit = unit

    def verify(self):
        for description, check in self.unit.checks:
            ready = wait_for(check, timeout=self.unit.timeout)
            self.assert_no_oom()
            assert ready, (
                self.unit.name
                + ": "
                + description
                + " did not pass within "
                + str(self.unit.timeout)
                + "s under the "
                + PROFILE
                + " profile (declared peak "
                + str(PEAK_MIB)
                + " MiB).\n"
                + compose("ps", timeout=120).stdout
            )

    def assert_no_oom(self):
        killed = [service for service in self.unit.services if oom_killed(service)]
        if not killed:
            return
        raise ProfileBudgetFailure(
            "profile budget failure: "
            + ", ".join(killed)
            + " was OOM-killed under the "
            + PROFILE
            + " profile. Its ceiling in deployment/budgets/profiles.yaml was reached, and a ceiling"
            " is a hard limit, so this is the profile's budget being exceeded rather than an"
            " application bug. The peak "
            "the profile declares is "
            + str(PEAK_MIB)
            + " MiB; see docs/local-development.md section 11."
        )


def pytest_generate_tests(metafunc):
    # The parametrised name is unit_spec rather than unit on purpose: pytest
    # resolves a test argument that is also a fixture name to the fixture, so a
    # parametrisation called unit would be shadowed and the raw case object
    # handed to the test.
    if "unit_spec" in metafunc.fixturenames:
        metafunc.parametrize("unit_spec", UNITS, ids=[u.name for u in UNITS])


@pytest.fixture
def running(unit_spec):
    """Brings the case up, yields it, and always tears it down, so one failure
    cannot poison the next case.

    Bring-up is inside the try as well as teardown. A podman-compose up that
    fails part way has already started the services it reached, and an up that
    times out leaves whatever it started running, so a teardown that only ran
    after a successful up would leave that unit's containers behind for the next
    case to trip over.
    """
    try:
        result = compose("up", "-d", *unit_spec.services, timeout=900)
        if result.returncode != 0:
            raise AssertionError(
                "podman-compose up failed for "
                + unit_spec.name
                + ":\n"
                + result.stdout
                + result.stderr
            )
        yield Running(unit_spec)
    finally:
        compose("down", "--volumes", timeout=600)
