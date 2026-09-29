#!/bin/bash
# Polaris 1.7.0 entrypoint for the security evidence harness.
#
# Polaris reads its configuration from Quarkus, and Quarkus has no file intake
# for the datasource password or the bootstrap credential. So the two secret
# files are read here, at process start, and rendered into a config file that
# lives under the container home (not a tracked file, not an environment
# value). This is the same pattern the ClickHouse service uses: a secret file
# in, a rendered config out, per ADR-0028.
#
# The container runs as the image non-root user (polaris, uid 10000), which
# is why the secret files must be mapped to 10000:10001 by
# profiles/polaris-fix-ownership.sh before bring-up.
set -euo pipefail

config_dir="${HOME}/config"
config_file="${config_dir}/application.properties"
mkdir -p "${config_dir}"

db_password="$(cat /run/secrets/polaris_db_password)"
bootstrap_secret="$(cat /run/secrets/polaris_bootstrap_secret)"

# The metastore is a dedicated PostgreSQL 18 instance in this profile. The
# schema (POLARIS_SCHEMA, including the events table) is created by Polaris on
# first start.
cat > "${config_file}" <<EOF
quarkus.datasource.jdbc.url=jdbc:postgresql://postgres:5432/deplatform
quarkus.datasource.username=deplatform
quarkus.datasource.password=${db_password}
quarkus.datasource.jdbc.max-size=8

# Persist catalog state, and the audit events, in the metastore rather than in
# memory, so the events table can be read back with SQL.
polaris.persistence.type=relational-jdbc
polaris.persistence.auto-bootstrap-types=relational-jdbc

# The opt-in event framework, pointed at the listener that persists events to
# the metastore. A short buffer makes the evidence test deterministic.
polaris.event-listener.type=persistence-in-memory-buffer
polaris.event-listener.persistence-in-memory-buffer.buffer-time=250ms
polaris.event-listener.persistence-in-memory-buffer.max-buffer-size=1

# The default "common" pattern does not carry the authenticated principal.
# This is the pattern ADR-0030 says to set. Whether the principal actually
# appears is what tests/polaris.sh decides.
quarkus.http.access-log.enabled=true
quarkus.http.access-log.pattern=%h %l %u %t "%r" %s %b

# Init-only root credential, taken from the secret file above.
polaris.bootstrap.credentials=POLARIS,root,${bootstrap_secret}
EOF

chmod 600 "${config_file}"

# The config location must be a JVM system property, not an argument after
# -jar, so it is passed through JAVA_OPTS_APPEND, which run-java.sh places
# before -cp/-jar. Passing it as a plain argument made Quarkus treat it as an
# application argument and silently fall back to the in-memory metastore.
export JAVA_OPTS_APPEND="-Dquarkus.config.locations=file:${config_file}"

exec /opt/jboss/container/java/run/run-java.sh
