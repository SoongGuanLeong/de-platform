#!/bin/sh
# Starts the SeaweedFS S3 gateway with TLS for the security evidence harness.
#
# The image's own entrypoint drops privileges to the non-root "seaweed" user,
# and a rootless podman bind mount presents the host owner as container root,
# so the seaweed user cannot read /certs or /run/secrets directly. This script
# runs as root, re-materialises the three files it needs with the seaweed
# owner, then hands off to the image entrypoint, which does the privilege drop.
# This mirrors the PostgreSQL service in ../../compose.yml and is a real cost of
# the file-based secret mechanism, recorded in docs/security-model.md.
set -eu

seaweed_uid="$(id -u seaweed)"
seaweed_gid="$(id -g seaweed)"

# The secret arrives as a file at /run/secrets/seaweedfs_s3_secret_key
# (ADR-0028). It is interpolated into the S3 config, which exists only in the
# container's /tmp and is never written to a tracked file.
secret="$(cat /run/secrets/seaweedfs_s3_secret_key)"
sed "s|__SEAWEEDFS_S3_SECRET_KEY__|${secret}|" \
  /harness/s3-config.json.tmpl > /tmp/s3-config.json

mkdir -p /tmp/tls
cp /certs/seaweedfs.crt /tmp/tls/seaweedfs.crt
cp /certs/seaweedfs.key /tmp/tls/seaweedfs.key
cp /certs/ca.crt /tmp/tls/ca.crt
chown -R "${seaweed_uid}:${seaweed_gid}" /tmp/tls /tmp/s3-config.json
chmod 600 /tmp/tls/seaweedfs.key /tmp/s3-config.json
chmod 644 /tmp/tls/seaweedfs.crt /tmp/tls/ca.crt

# -admin.port is pinned out of the ephemeral range: the admin gRPC port is
# derived from it, and issue #10838 is that the derived default can land inside
# the ephemeral range.
#
# mini mode also starts a plaintext Iceberg REST catalog (8181), a plaintext
# Lance namespace server (9101) and WebDAV (7333) by default. The catalog is the
# serious one: an unauthenticated catalog inside the object store would let a
# client resolve table metadata without going through Polaris, routing around
# the authorisation seam the platform depends on (ADR-0004, ADR-0010). All three
# are disabled, so the TLS S3 endpoint is the only listener this profile serves.
exec /entrypoint.sh mini \
  -dir=/data \
  -s3.config=/tmp/s3-config.json \
  -s3.cert.file=/tmp/tls/seaweedfs.crt \
  -s3.key.file=/tmp/tls/seaweedfs.key \
  -s3.cacert.file=/tmp/tls/ca.crt \
  -admin.port=12646 \
  -s3.port.iceberg=0 \
  -s3.port.lance=0 \
  -webdav=false
