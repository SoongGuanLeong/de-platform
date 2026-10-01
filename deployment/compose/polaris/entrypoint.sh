#!/bin/bash
# Polaris 1.7.0 entrypoint for the platform's profiles.
#
# Polaris reads its configuration from Quarkus, and Quarkus has no file intake
# for the datasource password or the bootstrap credential, so the two secret
# files are read here, at process start, and rendered into a config file that
# lives under the container home. A secret file in, a rendered config out, per
# ADR-0028; nothing is written outside the container.
#
# The container runs as the image's non-root user (polaris, uid 10000), which is
# why deployment/scripts/fix-secret-ownership.sh maps the two secret files to
# 10000:10001 before bring-up. See docs/security-model.md section 2.4.
set -euo pipefail

config_dir="${HOME}/config"
config_file="${config_dir}/application.properties"
mkdir -p "${config_dir}"

db_password="$(cat /run/secrets/polaris_db_password)"
bootstrap_secret="$(cat /run/secrets/polaris_bootstrap_secret)"

cat > "${config_file}" <<EOF
quarkus.datasource.jdbc.url=jdbc:postgresql://postgres:5432/polaris
quarkus.datasource.username=polaris
quarkus.datasource.password=${db_password}
quarkus.datasource.jdbc.max-size=8

polaris.persistence.type=relational-jdbc
polaris.persistence.auto-bootstrap-types=relational-jdbc

polaris.bootstrap.credentials=POLARIS,root,${bootstrap_secret}
EOF

chmod 600 "${config_file}"

# The config location must be a JVM system property, not an argument after -jar,
# so it is passed through JAVA_OPTS_APPEND, which run-java.sh places before
# -cp/-jar. Passing it as a plain argument made Quarkus treat it as an
# application argument and silently fall back to the in-memory metastore.
export JAVA_OPTS_APPEND="-Dquarkus.config.locations=file:${config_file}"

exec /opt/jboss/container/java/run/run-java.sh
