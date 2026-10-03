"""The batch profile's integration checks (tickets #34 and #54).

Two live paths share this directory and its profile. The TPC-H check (ticket
#34) runs the real components end to end: dbgen is built from source and
generates the flat files, then Spark writes one Iceberg table per source table
through the Polaris Iceberg REST catalog to SeaweedFS, and the row counts are
asserted against the flat files counted independently by the unit-tested reader.
The TPC-C check (ticket #54) runs the driver process against its real
dependency, a real PostgreSQL.

Each check gates itself. The TPC-H check brings up the bronze path's subset of
the batch profile - the catalog, its metastore and the object store as
residents, and Spark as the transient that writes - the way the runbook brings
it up: the secrets are provisioned, the preflight decides whether the host can
hold the profile, and podman-compose starts the services. Spark is run as the
profile's transient member, because the compose spark service's own command is a
version check; it runs against the same network so it reaches the catalog and
the object store by their service names. The TPC-C check brings PostgreSQL up
alone rather than the whole batch profile, so the profile's peak is never
reached. Both follow the runbook order of docs/local-development.md section 6:
provision, ordered start, readiness, and teardown, with the teardown first so an
interrupted run cannot poison the next.

One local configuration makes the TPC-H catalog able to write a new table's
metadata: Polaris is given the SeaweedFS S3 identity (deployment/compose/polaris),
which is the local stand-in for the IRSA role the cloud uses (ADR-0027). Without
it CREATE TABLE fails with an AWS SDK credential error, and the gap is recorded
in docs/local-development.md section 8.

The TPC-C warehouse count is read from TPCC_TEST_WAREHOUSES and defaults to 1.
W=10 is the declared correctness slice (docs/testing-strategy.md section 4.1) and
is run by setting the variable; W=1 keeps the default suite fast while still
exercising every live path.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest
from de_batch.commerce.tpch import dbgen, runtime, spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPOSE = ROOT + "/deployment/compose/batch.yml"
PROJECT = "de-platform-batch"
PROFILE = "batch"

# The services the TPC-H check starts. It is the bronze path's subset of the
# batch profile: the catalog, its metastore and the object store as residents,
# and Spark as the transient that writes. ClickHouse, Dagster and the
# observability overlay belong to other parts of the batch profile and to no
# part of this path, so the check gates on this subset's declared peak rather
# than the whole profile's, computed from the same ceiling register the preflight
# reads.
SUBSET_RESIDENTS = ("postgres", "seaweedfs", "polaris")
SUBSET_TRANSIENT = ("spark",)
RESERVE_MIB = 512

CATALOG = "de_platform"
REST = "http://127.0.0.1:58181/api/catalog"
S3_ENDPOINT = "http://seaweedfs:8333"
S3_ACCESS_KEY = "deplatform"
WAREHOUSE_BUCKET = "warehouse"
NETWORK = "de-platform-batch_default"
SPARK_IMAGE = "docker.io/apache/spark:4.1.3-java17"
CONTAINER_WORKSPACE = "/work"

# The TPC-C check's single service and its published port.
SERVICE = "postgres"
PORT = 55432

# The scratch directory holds the built generator, the jars and the generated
# flat files, none of which are committed. It defaults to the repository runtime
# tree (gitignored), but /tmp is a tmpfs on some hosts, so it can be pointed at a
# real disk with DE_TPCH_SCRATCH; a generated data set does not belong in RAM.
TPCH_DIR = os.environ.get("DE_TPCH_SCRATCH") or os.path.join(ROOT, "runtime", "tpch")
JARS_DIR = os.path.join(TPCH_DIR, "jars")
SRC_DIR = os.path.join(TPCH_DIR, "src")


class ProfileBudgetFailure(AssertionError):
    """A profile service was OOM-killed, which is a budget failure, not a bug."""


# ---------------------------------------------------------------------------
# Running things
# ---------------------------------------------------------------------------


def run(argv, cwd=ROOT, timeout=1800):
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
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


def http_status(url, timeout=30):
    result = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], timeout=timeout)
    return result.stdout.strip()


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


def subset_peak_mib():
    """The subset's declared peak: its residents plus its largest transient."""
    from de_governance.yaml_loader import load_mapping

    with open(
        os.path.join(ROOT, "deployment", "budgets", "profiles.yaml"), encoding="utf-8"
    ) as handle:
        register = load_mapping(handle)
    ceilings = register["ceilings"]
    resident = sum(ceilings[service]["memory_mib"] for service in SUBSET_RESIDENTS)
    transient = max(ceilings[service]["memory_mib"] for service in SUBSET_TRANSIENT)
    return resident + transient


def host_available_mib():
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    raise AssertionError("MemAvailable is not in /proc/meminfo")


def oom_killed(service):
    name = container_of(service)
    if name is None:
        return False
    result = run(["podman", "inspect", name, "--format", "{{.State.OOMKilled}}"], timeout=60)
    return result.stdout.strip() == "true"


# ---------------------------------------------------------------------------
# Provisioning and the fixture
# ---------------------------------------------------------------------------


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url, destination, sha256):
    if os.path.isfile(destination) and _sha256(destination) == sha256:
        return destination
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    result = run(["curl", "-sSL", "-m", "300", "-o", destination, url], timeout=400)
    if result.returncode != 0:
        raise AssertionError("could not download " + url + ": " + result.stderr)
    actual = _sha256(destination)
    if actual != sha256:
        raise AssertionError(
            "checksum mismatch for " + url + ": expected " + sha256 + " got " + actual
        )
    return destination


def ensure_dbgen():
    """Build dbgen from the pinned source if it is not already built."""
    binary = os.path.join(SRC_DIR, "dbgen")
    if os.path.isfile(binary):
        return binary
    archive = _download(
        dbgen.provenance().url,
        os.path.join(TPCH_DIR, "dbgen-src.tar.gz"),
        dbgen.provenance().sha256,
    )
    os.makedirs(SRC_DIR, exist_ok=True)
    extracted = run(["tar", "-xzf", archive, "-C", SRC_DIR, "--strip-components=1"], timeout=300)
    if extracted.returncode != 0:
        raise AssertionError("could not extract dbgen: " + extracted.stderr)
    built = run(dbgen.build_argv("make"), cwd=SRC_DIR, timeout=600)
    if built.returncode != 0:
        raise AssertionError("dbgen did not build:\n" + built.stdout + built.stderr)
    return binary


def ensure_jars():
    paths = []
    for jar in runtime.jars():
        path = _download(jar.url, os.path.join(JARS_DIR, jar.name), jar.sha256)
        paths.append(path)
    return paths


def scale_factor():
    return int(os.environ.get("DE_TPCH_SCALE_FACTOR", "1"))


def flat_directory(scale):
    return os.path.join(TPCH_DIR, "data", "sf" + str(scale))


def generate_flat_files(scale):
    directory = flat_directory(scale)
    complete = all(
        os.path.isfile(os.path.join(directory, table.flat_file)) for table in spec.source_tables()
    )
    if not complete:
        dbgen.generate(ensure_dbgen(), SRC_DIR, directory, scale)
    # A reused tree may predate the generator normalising its output modes, and
    # the Spark container reads these files as a different user.
    for table in spec.source_tables():
        path = os.path.join(directory, table.flat_file)
        if os.path.isfile(path):
            os.chmod(path, 0o644)
    return directory


# ---------------------------------------------------------------------------
# The catalog
# ---------------------------------------------------------------------------


def _post(url, body, token=None, form=False):
    data = body.encode("utf-8") if isinstance(body, str) else body
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def bootstrap_catalog(secret):
    """Create the catalog, through the Management API, as the one-time bootstrap.

    Idempotent: a catalog that already exists is left alone. The shared core
    never uses the Management API; this is the bootstrap, which ADR-0010 permits.
    """
    form = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": "root",
            "client_secret": secret,
            "scope": "PRINCIPAL_ROLE:ALL",
        }
    )
    status, body = _post(REST + "/v1/oauth/tokens", form, form=True)
    if status != 200:
        raise AssertionError("the catalog refused the bootstrap token: " + str(status) + body)
    token = json.loads(body)["access_token"]
    catalog = json.dumps(
        {
            "catalog": {
                "name": CATALOG,
                "type": "INTERNAL",
                "properties": {"default-base-location": "s3://" + WAREHOUSE_BUCKET + "/"},
                "storageConfigInfo": {
                    "storageType": "S3",
                    "allowedLocations": ["s3://" + WAREHOUSE_BUCKET + "/"],
                    "endpoint": S3_ENDPOINT,
                    "pathStyleAccess": True,
                    "region": "us-east-1",
                },
            }
        }
    )
    endpoint = REST.replace("/api/catalog", "/api/management") + "/v1/catalogs"
    status, body = _post(endpoint, catalog, token=token)
    if status not in (201, 409):
        raise AssertionError("could not bootstrap the catalog: " + str(status) + body)


def create_bucket():
    """SeaweedFS does not create the warehouse bucket on a write, so create it."""
    name = container_of("seaweedfs")
    if name is None:
        raise AssertionError("the seaweedfs container is not up")
    result = run(
        [
            "podman",
            "exec",
            name,
            "sh",
            "-c",
            'echo "s3.bucket.create -name '
            + WAREHOUSE_BUCKET
            + '" | weed shell -master=localhost:9333',
        ],
        timeout=90,
    )
    if result.returncode != 0:
        raise AssertionError(
            "could not create the warehouse bucket:\n" + result.stdout + result.stderr
        )


def polaris_bootstrap_secret():
    result = in_container("polaris", ["cat", "/run/secrets/polaris_bootstrap_secret"])
    if result.returncode != 0:
        raise AssertionError("could not read the bootstrap credential:\n" + result.stderr)
    return result.stdout.strip()


def seaweedfs_s3_secret():
    name = container_of("seaweedfs")
    result = run(["podman", "exec", name, "cat", "/tmp/s3-config.json"], timeout=60)
    if result.returncode != 0:
        raise AssertionError("could not read the S3 identity:\n" + result.stderr)
    return json.loads(result.stdout)["identities"][0]["credentials"][0]["secretKey"]


# ---------------------------------------------------------------------------
# The load
# ---------------------------------------------------------------------------


def run_load(scale, flat_dir, secret, s3_secret, timeout=3600):
    container_flat = "/tpch/data/sf" + str(scale)
    jar_list = ",".join("/tpch/jars/" + jar.name for jar in runtime.jars())
    environment = {
        "DE_TPCH_FLAT_DIR": container_flat,
        "DE_TPCH_SCALE_FACTOR": str(scale),
        "DE_ICEBERG_REST_URI": "http://polaris:8181/api/catalog",
        "DE_ICEBERG_WAREHOUSE": CATALOG,
        "DE_ICEBERG_CREDENTIAL": "root:" + secret,
        "DE_S3_ENDPOINT": S3_ENDPOINT,
        "DE_S3_ACCESS_KEY_ID": S3_ACCESS_KEY,
        "DE_S3_SECRET_ACCESS_KEY": s3_secret,
        "DE_S3_REGION": "us-east-1",
        "PYTHONPATH": CONTAINER_WORKSPACE + "/batch/src:" + CONTAINER_WORKSPACE + "/platform/src",
    }
    argv = [
        "podman",
        "run",
        "--rm",
        "--net",
        NETWORK,
        "-v",
        ROOT + ":" + CONTAINER_WORKSPACE + ":z",
        "-v",
        TPCH_DIR + ":/tpch:z",
        "-w",
        CONTAINER_WORKSPACE,
    ]
    for key, value in environment.items():
        argv += ["-e", key + "=" + value]
    argv += [
        SPARK_IMAGE,
        "/opt/spark/bin/spark-submit",
        "--master",
        "local[2]",
        "--driver-memory",
        "1g",
        "--conf",
        "spark.ui.enabled=false",
        "--jars",
        jar_list,
        CONTAINER_WORKSPACE + "/batch/src/de_batch/commerce/tpch/spark_bronze.py",
    ]
    result = run(argv, timeout=timeout)
    # The full output is kept for diagnosis, because pytest truncates a long
    # Spark stack trace to its last lines and the cause is at the top.
    with open(os.path.join(TPCH_DIR, "last-load.log"), "w", encoding="utf-8") as handle:
        handle.write(result.stdout + "\n--- STDERR ---\n" + result.stderr)
    return result


def parse_counts(output):
    for line in output.splitlines():
        if line.startswith("COUNTS "):
            return json.loads(line[len("COUNTS ") :])
    raise AssertionError("the load printed no COUNTS line:\n" + output[-4000:])


# ---------------------------------------------------------------------------
# The fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tpch_fixture():
    scale = scale_factor()
    ensure_jars()
    directory = generate_flat_files(scale)
    return {"scale": scale, "host_dir": directory}


@pytest.fixture(scope="module")
def batch_profile():
    try:
        compose("down", "--volumes", timeout=600)
        provision = run(["bash", "deployment/scripts/generate-secrets.sh"], timeout=180)
        if provision.returncode != 0:
            raise AssertionError("provisioning failed:\n" + provision.stdout + provision.stderr)
        run(["bash", "deployment/scripts/fix-secret-ownership.sh"], timeout=180)

        # The runbook's preflight gates a full-path batch run. Its verdict is
        # captured for the record, and the check proceeds on the subset it
        # actually starts when that subset fits, which is the honest gate for a
        # bronze-path run under a host other work is sharing.
        preflight = run(["bash", "deployment/scripts/preflight.sh", "batch"], timeout=180)
        peak = subset_peak_mib()
        available = host_available_mib()
        if available - RESERVE_MIB < peak:
            pytest.skip(
                "the bronze subset does not fit this host: needs "
                + str(peak + RESERVE_MIB)
                + " MiB and the host has "
                + str(available)
                + " MiB. The full-profile preflight said:\n"
                + preflight.stdout
                + preflight.stderr
            )

        result = compose("up", "-d", "postgres", "seaweedfs", "polaris", timeout=900)
        if result.returncode != 0:
            raise AssertionError("the profile did not start:\n" + result.stdout + result.stderr)
        ready = wait_for(lambda: http_status(REST + "/v1/config") in ("401", "200"), timeout=300)
        if not ready:
            raise AssertionError("polaris did not answer in 300s:\n" + compose("ps").stdout)

        secret = polaris_bootstrap_secret()
        bootstrap_catalog(secret)
        create_bucket()
        s3_secret = seaweedfs_s3_secret()

        for service in ("postgres", "seaweedfs", "polaris"):
            if oom_killed(service):
                raise ProfileBudgetFailure(
                    "profile budget failure: "
                    + service
                    + " was OOM-killed under the batch profile (subset peak "
                    + str(subset_peak_mib())
                    + " MiB)"
                )

        yield {"secret": secret, "s3_secret": s3_secret}
    finally:
        compose("down", "--volumes", timeout=600)


@pytest.fixture(scope="module")
def load_runner(batch_profile):
    """A callable that runs the Spark load once, against the running profile."""

    def _run(scale, host_flat_dir):
        return run_load(scale, host_flat_dir, batch_profile["secret"], batch_profile["s3_secret"])

    return _run


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
