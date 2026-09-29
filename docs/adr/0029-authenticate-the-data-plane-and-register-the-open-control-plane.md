# Authenticate the data plane, encrypt only where a refusal can be shown, and register the surfaces left open

**Status:** accepted

Most components in this stack ship with authentication disabled or absent by default, and several have none at all: Marquez states it has none and will not until 0.52, the Dagster OSS webserver has none, the Flink REST API authenticates no client, Prometheus and Alertmanager have none unless a web config is supplied, and the SeaweedFS S3 endpoint is open by default. The platform closes four data-plane surfaces (Kafka, ClickHouse, SeaweedFS's S3 endpoint and PostgreSQL) and deliberately leaves the rest open locally.

**Authenticated.** Every path that moves data carries a credential: Debezium to PostgreSQL over SCRAM-SHA-256; Debezium and Flink to Kafka over SASL_SSL with SCRAM-SHA-256; Flink, Spark and ClickHouse to Polaris over OAuth2 client credentials; Spark, Flink and Dagster to ClickHouse as SQL users with sha256 passwords; Dagster to PostgreSQL; Polaris to SeaweedFS over AssumeRole with an inline session policy; and the engines to SeaweedFS using the vended, prefix-scoped credential. Each row carries at least one negative test, and configuration alone is not accepted as proof of enforcement.

**Encrypted.** Five listeners terminate TLS, each because a refusal can be demonstrated on it: Kafka (a plaintext client and a wrong-CA client are both refused), PostgreSQL (`hostssl` refuses a non-TLS client, so this is enforcement rather than availability), ClickHouse's secure TCP port, SeaweedFS's S3 endpoint, which is where the vended credential lands, and Grafana, whose chain a browser can be seen completing. Everything else stays plaintext, because a self-signed CA trusted by every client on one host and one rootless podman network is not a security boundary, and wrapping a loopback development UI in TLS is ceremony.

**Registered.** The control plane stays unauthenticated locally, bound to loopback and the compose network, and each surface is entered in an unauthenticated-surfaces register naming what is open, why that is acceptable locally, what bounds it, and what protects it in the cloud. A basic-auth layer in front of a loopback UI would be visible to a reviewer as theatre, and the component carrying it would fail the mission's sprawl test.

**One path is not invented.** Dagster does not authenticate to Polaris, because Dagster OSS is not an Iceberg REST catalog client. Dagster orchestrates: it launches Spark and Flink jobs, and those engines authenticate to Polaris.

## Considered options

- **Authenticate everything locally, with an identity provider and a reverse proxy.** Rejected: an identity provider is a twentieth component admitted to switch on a feature nothing depends on, and proxy authentication over loopback buys no boundary a reviewer would credit.
- **Authenticate nothing and document the absences only.** Rejected: the data plane is where a credential is a real boundary, and the vended prefix-scoped credential is the platform's strongest access claim.
- **Mutual TLS between every pair.** Rejected: no certificate lifecycle story exists to justify it, and it is the same ceremony in a different mechanism.
- **TLS on every listener.** Rejected on the same ground as the proxy, with two additional facts: the Dagster webserver has no native TLS option and Marquez documents none, so both would need a proxy.
- **`mkcert` or `step-ca` for certificates.** Rejected: `mkcert` is an extra tool for what `openssl` already does here, and `step-ca` is a CA daemon for a rotation story nothing in this platform needs.

## Consequences

The register is the artefact, and it is what makes the absence of a control a decision rather than an omission. The negative tests are the evidence, and each TLS and authentication row is a test rather than a configuration claim.

Two asymmetries are recorded rather than smoothed over. Kafka runs PEM mode, where keystore and truststore passwords are not supported, so its keystore password is designed out; Flink is the one component whose keystore password must be materialised by an entrypoint, because its SSL options are Java keystore only. And in the cloud, ALB TLS termination encrypts the client-to-ALB hop only, so the encryption claim is labelled client-to-ALB for the browser surfaces, with the data plane reached by TCP pass-through and TLS terminating in the pod.

No component is added. The technology count stays at nineteen. The matrices, the register and the local-versus-cloud differences are in [`docs/security-model.md`](../security-model.md); the per-component authentication and TLS facts are in [`docs/research/25-security-facts-secrets-auth-tls-audit.md`](../research/25-security-facts-secrets-auth-tls-audit.md).
