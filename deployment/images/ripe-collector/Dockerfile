# The RIPE Atlas collector image (issue #48).
#
# The base is python:3.12-slim, pinned by the digest of its multi-arch index so
# one reference resolves on the x86_64 host and on a Graviton node. The compose
# service references localhost/de-platform/ripe-collector:0.0.0 and
# deployment/scripts/check-compose.sh asserts that reference. Build from the
# repository root: podman build -t localhost/de-platform/ripe-collector:0.0.0
# -f deployment/images/ripe-collector/Dockerfile .
FROM docker.io/library/python:3.12-slim@sha256:6b1f85a08c199d29d5b6d71ab9c27bd5b3b393492e01216a15758ff69c4be8b8

# The workspace is installed from the repository root: platform and governance
# first, then ingestion, so pip sees the local dependencies already satisfied
# rather than looking for them on an index. uv_build is the build backend each
# package declares, so it is fetched at build time.
COPY platform /build/platform
COPY governance /build/governance
COPY ingestion /build/ingestion
RUN pip install --no-cache-dir /build/platform /build/governance /build/ingestion \
    && rm -rf /build

# The timepoint cursor is written under this path, so it lives on a volume and
# survives a restart, which is the point of persisting it.
VOLUME ["/var/lib/de-platform"]
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092

ENTRYPOINT ["python", "-m", "de_ingestion.network.ripe"]
