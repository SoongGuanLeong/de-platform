#!/bin/sh
# SeaweedFS entrypoint for the platform's profiles.
#
# One job before the store starts: render the S3 identity from its secret file.
# Without an S3 configuration weed mini serves the S3 gateway anonymously, which
# would put an unauthenticated object store inside the platform and let a client
# read or write the warehouse without going through Polaris. The secret arrives
# as a file at /run/secrets, per ADR-0028, and the rendered config lives only in
# the container's /tmp.
#
# The image's own entrypoint drops privileges to the non-root seaweed user, so
# the rendered config is handed over with that owner.
set -eu

seaweed_uid="$(id -u seaweed)"
seaweed_gid="$(id -g seaweed)"

secret="$(cat /run/secrets/seaweedfs_s3_secret_key)"
sed "s|__SEAWEEDFS_S3_SECRET_KEY__|${secret}|" \
  /harness/s3-config.json.tmpl > /tmp/s3-config.json
chown "${seaweed_uid}:${seaweed_gid}" /tmp/s3-config.json
chmod 600 /tmp/s3-config.json

# -admin.port is pinned out of the ephemeral range: the admin gRPC port is
# derived from it, and issue #10838 is that the derived default can land inside
# the ephemeral range. The Iceberg REST catalog, the Lance namespace server and
# WebDAV are disabled: an unauthenticated catalog inside the object store would
# let a client resolve table metadata without going through Polaris, routing
# around the authorisation seam the platform depends on (ADR-0004, ADR-0010).
exec /entrypoint.sh mini \
  -dir=/data \
  -s3.config=/tmp/s3-config.json \
  -admin.port=12646 \
  -s3.port.iceberg=0 \
  -s3.port.lance=0 \
  -webdav=false
