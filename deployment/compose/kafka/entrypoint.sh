#!/bin/sh
# Kafka entrypoint for the security evidence harness.
#
# The container runs as appuser, so this script does not chown anything: the
# ownership mapping is done from the host by fix-secret-ownership.sh, because
# podman-compose ignores a secret's mode and owner.
#
# Kafka has no file intake for a SASL password. The broker's own credentials go
# into server.properties as a JAAS string, and the broker's ssl.* properties are
# plaintext in that file and are not externalisable by Kafka Configuration
# Providers, so the values are rendered here from the mounted files. This is a
# third instance of the entrypoint exception the model records for Flink.
set -eu

# The rendered config carries the broker's SCRAM password, and the keystore
# bundle below carries the private key. Neither should be world-readable.
umask 077

KAFKA_HOME=/opt/kafka
DATA=/tmp/kafka-data
CONF=/tmp/kafka-server.properties

mkdir -p "$DATA"

# Kafka's file-based PEM keystore wants one file holding both the certificate
# chain and the private key. It is assembled here, inside the container, so the
# host's runtime/certs gains no extra key-bearing file.
cat /certs/kafka.crt /certs/kafka.key > /tmp/kafka-keystore.pem

admin_pw="$(cat /run/secrets/kafka_admin_password)"
app_pw="$(cat /run/secrets/kafka_svc_password)"

cat > "$CONF" <<EOF
process.roles=broker,controller
node.id=1
controller.quorum.voters=1@127.0.0.1:9094

# The client listener is SASL_SSL.
#
# The controller listener is SASL_SSL too, not plaintext. This is forced by
# the authorizer rather than chosen for its own sake: with StandardAuthorizer
# enabled, a plaintext controller listener presents User:ANONYMOUS, which is
# denied CLUSTER_ACTION on the broker's own BROKER_REGISTRATION and on the
# controller's CONTROLLER_REGISTRATION, so the broker never becomes active and
# the broker logs CLUSTER_AUTHORIZATION_FAILED on every retry. Authenticating
# it as the admin principal, which is a super user, is what lets an authorised
# broker start at all.
listeners=SASL_SSL://0.0.0.0:9093,CONTROLLER://127.0.0.1:9094
advertised.listeners=SASL_SSL://127.0.0.1:9093
listener.security.protocol.map=CONTROLLER:SASL_SSL,SASL_SSL:SASL_SSL
inter.broker.listener.name=SASL_SSL
controller.listener.names=CONTROLLER

sasl.enabled.mechanisms=SCRAM-SHA-256
sasl.mechanism.inter.broker.protocol=SCRAM-SHA-256
sasl.mechanism.controller.protocol=SCRAM-SHA-256
listener.name.sasl_ssl.scram-sha-256.sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="admin" password="${admin_pw}";
listener.name.controller.scram-sha-256.sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="admin" password="${admin_pw}";

# PEM mode, so there is deliberately no keystore or truststore password.
#
# Kafka's PEM support has two mutually exclusive styles and they are not
# interchangeable: ssl.keystore.key + ssl.keystore.certificate.chain take the
# PEM *content*, whereas ssl.keystore.location takes a *path* to one file that
# holds both the private key and the chain. A path placed in the content style
# is parsed as PEM text and fails with "No matching PRIVATE KEY entries in PEM
# file". The file style is used here so the key stays in the mounted file.
ssl.keystore.type=PEM
ssl.keystore.location=/tmp/kafka-keystore.pem
ssl.truststore.type=PEM
ssl.truststore.location=/certs/ca.crt
ssl.client.auth=none

# The authorizer that makes a denial a logged event rather than silence.
authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer
allow.everyone.if.no.acl.found=false
super.users=User:admin

log.dirs=$DATA
num.partitions=1
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
EOF

if [ ! -f "$DATA/cluster.id" ]; then
  cid="$("$KAFKA_HOME/bin/kafka-storage.sh" random-uuid)"
  printf '%s' "$cid" > "$DATA/cluster.id"
  "$KAFKA_HOME/bin/kafka-storage.sh" format -t "$cid" -c "$CONF" \
    --add-scram "SCRAM-SHA-256=[name=admin,password=${admin_pw}]" \
    --add-scram "SCRAM-SHA-256=[name=svc_platform,password=${app_pw}]"
fi

exec "$KAFKA_HOME/bin/kafka-server-start.sh" "$CONF"
