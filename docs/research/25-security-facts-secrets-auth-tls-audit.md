# Security facts: secrets intake, per-component authentication, TLS and auditability

**Date:** 2026-09-29
**Ticket:** [The security model beyond governance](https://github.com/SoongGuanLeong/de-platform/issues/18) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Purpose:** the evidence base for [`docs/security-model.md`](../security-model.md) and ADR-0028, ADR-0029 and ADR-0030. Facts only, verified against the pinned versions on the date above. Where something could not be verified it is listed in section 10 rather than asserted.

**Pinned versions this was checked against:** Kafka 4.3.1 (KRaft), ClickHouse 26.8 LTS, Polaris 1.7.0, SeaweedFS 4.47, PostgreSQL 18, Grafana 13, Prometheus 3.14, Alertmanager 0.34, Apicurio 3.3.x, Marquez 0.51.x, Dagster 1.13.x, Flink 2.1.3, Spark 4.1.3, Debezium 3.6.1, OpenLineage 1.53.0, Iceberg 1.11.0, Podman 6.1.x.

---

## 1. Local secret injection, tested on this host

Tested against rootless podman 5.7.0 with podman-compose 1.5.0, not against the pinned 6.1.x. The pinned row is an unverified gap (section 10).

| Mechanism | podman-compose 1.5.0 | docker compose v2 | Note |
|---|---|---|---|
| Top-level `secrets:` with a `file:` source | Works. Bind-mounts read-only at `/run/secrets/<name>` | Works | The only mechanism in the portable intersection. `uid`, `gid` and `mode` are ignored with a warning |
| Top-level `secrets:` with an `environment:` source | **Fails** with `ValueError: ERROR: unparsable secret` | Works | A real divergence. The source is documented as Docker-Compose-only |
| Top-level `secrets:` with `external: true` | Works, mapped to `podman --secret` | Not supported outside swarm | A divergence in the other direction |
| `env_file:` | Works | Works | Read by the CLI, not the daemon |
| Plain `environment:` | Works | Works | Use `$$` to pass a literal `$VAR` through |
| A bind-mounted file via `volumes:` | Works | Works | The lowest-common-denominator mechanism |
| `podman secret` native | Works via `external: true` | No direct equivalent | The file driver is unencrypted on disk at `~/.local/share/containers/storage/secrets/filedriver` (verified with `podman secret inspect`) |

## 2. Per-component secret intake and rotation class

"Restart" means the component re-reads the value only at process start.

| Component | Intake | Keys | Rotation class |
|---|---|---|---|
| Polaris 1.7.0 | env and config | `POLARIS_BOOTSTRAP_CREDENTIALS=realm,principal,secret`; `quarkus.oidc.client-id`; `AWS_ACCESS_KEY_ID` and secret for S3 | Bootstrap is init-only; principals rotate through the management API without a server restart |
| SeaweedFS 4.47 | JSON config file | `weed s3 -config=...` with `accessKey` and `secretKey`. "Environment variables are only used when no S3 configuration file is provided" | Restart |
| Kafka 4.3.1 | JAAS file or inline `sasl.jaas.config`; PEM or keystore files | `ssl.keystore.location`; `config.providers` externalises connector values | Restart or rolling restart |
| Debezium 3.6.1 | Connector JSON with Kafka Configuration Providers | `config.providers=env,file`; the connector then references `${env:...}` or `${file:...}` | Reload: the connector config is updated with a `PUT` on the Connect REST API |
| Flink 2.1.3 | `flink-conf.yaml` and env vars | No native secret store; the Kubernetes operator consumes Secrets as env or volume | Restart |
| Spark 4.1.3 | `core-site.xml`, `spark-defaults.conf`, env | S3A keys in core-site, or the Hadoop AWS environment variables | Restart, per submit |
| ClickHouse 26.8 LTS | `users.xml` or `users.d/*.xml`, or SQL | `<password>` or `<password_sha256_hex>` | Reload: `SYSTEM RELOAD USERS` and `SYSTEM RELOAD CONFIG` avoid a restart |
| PostgreSQL 18 | env with `_FILE` variants | `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, and `POSTGRES_PASSWORD_FILE`. `_FILE` is documented as supported only for `POSTGRES_INITDB_ARGS`, `POSTGRES_PASSWORD`, `POSTGRES_USER` and `POSTGRES_DB` | Init: the entrypoint value is consumed once; changing it needs `ALTER USER` plus a restart |
| Dagster 1.13.x | env, the `EnvVar` class, `.env` | `dg.EnvVar("NAME")`; the value is not visible in the UI | Restart |
| Apicurio 3.3.x | Quarkus env vars | `QUARKUS_OIDC_CLIENT_ID` and `QUARKUS_OIDC_CLIENT_SECRET`; the UI client is public and has no secret | Restart |
| OpenLineage 1.53.0 | env or YAML | `OPENLINEAGE__TRANSPORT__AUTH`; legacy `OPENLINEAGE_URL` and `OPENLINEAGE_API_KEY` | Restart, read at client creation |
| Marquez 0.51.x | `marquez.yml` with env override | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` override the config file | Restart |
| Prometheus 3.14.0 | Config with `*_file` fields | `password_file`, `credentials_file`, `client_secret_file`, `token_file`, `ca_file`, `cert_file`, `key_file` | Reload: `*_file` contents are re-read per scrape; config reload by SIGHUP or `/-/reload` |
| Grafana 13.x | Env with a `__FILE` suffix, and provisioning files | `GF_<Section>_<Key>__FILE`, for example `GF_SECURITY_ADMIN_PASSWORD__FILE` | Restart |
| Alertmanager 0.34.x | Config with `*_file` fields | `smtp_auth_password_file`, `auth_password_file`, `api_key_file`, `bot_token_file`, `slack_api_url_file` and other receiver-specific `*_file` fields | Reload by SIGHUP or `/-/reload` |

## 3. Cloud secret storage and its dated prices

The cloud document budgets one secret in the minimal arm and five in the reference arm.

| Option | Storage | Interaction | 1 secret per month | 5 secrets per month | Source |
|---|---|---|---|---|---|
| AWS Secrets Manager | $0.40 per secret per month | $0.05 per 10,000 requests | $0.40 | $2.00 | research 21, offer publication 2026-09-11 |
| SSM Parameter Store, Standard | No charge | Free at standard throughput | $0.00 | $0.00 | AWS Systems Manager pricing page, read 2026-09-29 |
| SSM Parameter Store, Advanced | $0.05 per parameter per month | $0.05 per 10,000 interactions | $0.05 | $0.25 | Same page |
| SOPS with age, encrypted in Git | $0 | $0 | $0.00 | $0.00 | getsops.io, read 2026-09-29 |

At six hours, Secrets Manager for one secret is about $0.003 and for five about $0.016, which reconciles with the cloud document's $0.000548 and $0.002740 per hour.

**The Secrets Store CSI driver versus External Secrets Operator.** The CSI driver mounts values as files in the pod through a CSI inline volume. Its sync-to-Kubernetes-Secret and auto-rotation features are both labelled Alpha upstream. The AWS provider supports IRSA and requires an EC2 node group. ESO instead writes a Kubernetes Secret, so the value materialises as a base64 object that is not encrypted at rest unless the cluster uses KMS envelope encryption. The cloud document's choice of the CSI driver avoids that materialisation.

**The CSI projection, verified from source** (`kubernetes-sigs/secrets-store-csi-driver` and `aws/secrets-store-csi-driver-provider-aws`, main, read 2026-09-29): the volume is **tmpfs**, mounted by `pkg/secrets-store/nodeserver.go` (`mounter.Mount("tmpfs", targetPath, "tmpfs", ...)` at lines 173 and 239), so it is memory-backed and does not persist on node disk after the pod goes away. The mount is **enforced read-only** (lines 211 to 213 reject a request whose `Readonly` is false). The default file mode is **0644**, hardcoded at `nodeserver.go:54`, and the AWS provider also defaults to 0644 (`provider/secret_descriptor.go:19`), with a per-object `filePermission` override validated against `^[0-7]{4}$` (line 16). Hence the design sets `filePermission: "0400"` explicitly.

## 4. Leak prevention, and the honest limit of scanning

The failure being prevented is recorded in ADR-0006: a bootstrap script copied a tracked file to `.bak` and minted a fresh Polaris client secret into it on every run, and `.gitignore` did not exclude `*.bak`, so a PostgreSQL password, two Polaris OAuth2 client secrets, MinIO credentials and a Polaris administrator password were committed.

| Control | What it catches | Honest limit |
|---|---|---|
| A correct `.gitignore` plus a bootstrap script that writes only inside an ignored directory | The ADR-0006 vector exactly | Opt-out rather than a guarantee; `git add -f` and a renamed extension defeat it |
| A committed `.env.example` | Makes a missing variable visible in review | Does nothing if the real file is also committed under another name |
| gitleaks (MIT) | Known token formats plus entropy heuristics, over full history | A self-minted secret matches no provider format and is usually missed |
| trufflehog | Finds and verifies credentials against providers | Verification only works for supported providers; a self-minted value is unverifiable |
| GitHub native secret scanning | Free for public repositories, full history, push protection | Knows **partner patterns only**. Custom patterns need a paid plan. This repository's `secret_scanning_non_provider_patterns` is **disabled**, confirmed by `gh api repos/SoongGuanLeong/de-platform --jq '.security_and_analysis'` on 2026-09-29 |
| A pre-commit hook | Blocks a staged secret before it leaves the machine | Bypassable with `git commit --no-verify`; covers staged content, not history |

**Conclusion.** No scanner would reliably have caught the ADR-0006 leak, because the values were self-minted. The decisive control is the write path: a bootstrap route that can write secret values only inside the gitignored runtime directory.

**Verified on this repository, 2026-09-29.** gitleaks v8.30.1 over 30 commits found 5 findings, of which **one was a genuine committed secret value**: a temporary SeaweedFS STS secret access key in `docs/research/08-seaweedfs-sts-interop.md`. It was redacted forward under ADR-0028. The historical occurrence remains in commit `1d184c1` and is suppressed by fingerprint in `.gitleaksignore` with the reason recorded, because ADR-0006 rejects history rewriting. The other four were a GHSA advisory identifier, a self-describing test signing key, an STS access key ID with a token length, and a truncated token.

## 5. Authentication per component at the pinned version

Components whose only boundary is the network, because authentication is absent or off by default:

| Component | State | Evidence |
|---|---|---|
| Marquez 0.51.x | **No authentication of any kind.** A maintainer states it is not present and is not due until 0.52.0 (issue #2947, 2024-10-24); the latest tag is 0.51.1 and there is no 0.52 tag | `github.com/MarquezProject/marquez` issue #2947, tags list, `build.gradle` at 0.51.1 |
| Dagster 1.13.x webserver | No built-in authentication in OSS; SSO and RBAC are a paid edition | Community wrappers state plainly that "Dagster OSS has no auth" and that anyone with the URL has full admin access |
| Flink 2.1.3 REST and UI | "The server will, however, accept connections from any client by default, meaning the REST endpoint does not authenticate the client." Only optional client-certificate auth exists | `release-2.1` SSL deployment docs |
| Alertmanager 0.34.x | No authentication unless `--web.config.file` is supplied, then basic auth and TLS. One global config and one alert namespace, with no per-tenant isolation | `prometheus/alertmanager` `docs/https.md` and `docs/configuration.md` |
| Prometheus 3.14.0 | No authentication unless `--web.config.file` is supplied. No RBAC | `prometheus/prometheus` `docs/configuration/https.md` |
| SeaweedFS 4.47 S3 | Open by default: "Default Effect: Allow ... It does not secure your data by default" | SeaweedFS wiki, `S3-Credentials.md` and `S3-Configuration.md` |
| Apicurio 3.3.x | "authentication and authorization settings are disabled by default"; `quarkus.oidc.tenant-enabled` defaults to false | `v3.3.3` `assembly-configuring-registry-security.adoc` and `ref-registry-all-configs.adoc` |
| Kafka 4.3.1 KRaft | The default listener is PLAINTEXT and `security.inter.broker.protocol` defaults to PLAINTEXT | `kafka.apache.org/43/security/` |
| Kafka Connect REST | Open by default; basic authentication is an opt-in extension | `connect_config.html`; `BasicAuthSecurityRestExtension.java` and `JaasBasicAuthFilter.java` at tag 4.3.1 |
| ClickHouse 26.8 LTS | The `default` user has an empty password and SQL-driven access control is off by default; `allow_no_password=1` and `allow_implicit_no_password=1` ship set | ClickHouse access-rights and settings-users docs |
| Podman 6.1.x | No authentication on the API socket; access control is Unix socket permissions | Podman documentation |

Mechanisms available where they are turned on:

- **Kafka 4.3.1**: listener protocols PLAINTEXT, SSL, SASL_PLAINTEXT and SASL_SSL; SASL mechanisms GSSAPI, PLAIN, SCRAM-SHA-256, SCRAM-SHA-512 and OAUTHBEARER. No extra service is needed in KRaft. Client credentials are seeded with `kafka-configs.sh --add-config 'SCRAM-SHA-256=[iterations=8192,password=...]'`. Debezium, Flink and Spark all act as Kafka clients with the same three client-side keys (`security.protocol`, `sasl.mechanism`, `sasl.jaas.config`).
- **ClickHouse 26.8 LTS**: users, roles, row policies, settings profiles and quotas; password types including `sha256_password` (the default), `bcrypt_password`, `ldap`, `kerberos`, `ssl_certificate` and `ssh_key`. TLS is configured by uncommenting `tcp_port_secure` and `https_port` and adding an `<openSSL>` block. ClickHouse reaches a REST catalog through `DataLakeCatalog` with `catalog_type='rest'`.
- **Polaris 1.7.0**: OAuth2 client credentials through `/api/catalog/v1/oauth/tokens`, in internal, external or mixed mode, with a token broker using an RSA key pair or a symmetric key. Clients are Spark (`rest.auth.type=oauth2`), Flink and ClickHouse. Polaris calls AWS STS AssumeRole with an inline session policy for the vended credential, and `stsEndpoint` exists for MinIO-style backends.
- **SeaweedFS 4.47**: S3 access keys from a JSON config, an advanced IAM and STS path with `defaultEffect: Deny`, filer JWT signing keys, and gRPC mutual TLS.
- **PostgreSQL 18**: SCRAM-SHA-256, described as the most secure of the shipped password methods, with `ssl=on` and `hostssl` in `pg_hba.conf`.
- **Spark 4.1.3**: the Iceberg REST catalog client supports `none` (the default), `basic`, `oauth2`, `sigv4` and `google`; object storage credentials come from S3A keys or the Hadoop Credential Provider.
- **Grafana 13.x**: basic auth, anonymous, auth proxy, OAuth providers and LDAP are in the OSS edition. SAML, team sync, enhanced LDAP and SCIM are Enterprise and Cloud only, as is the audit log.

## 6. TLS per listener, and the certificate tooling

| Listener | TLS available | Configuration | Worth it locally? |
|---|---|---|---|
| Kafka broker | Yes | `listeners=SASL_SSL://...`, `ssl.truststore.location`, `sasl.enabled.mechanisms=SCRAM-SHA-256` (SCRAM-SHA-512 is also available). In PEM mode, `ssl.keystore.type=PEM` with `ssl.keystore.location` pointing at one file that holds the key and the chain. `ssl.keystore.key` and `ssl.keystore.certificate.chain` take PEM **content**, not a path, so a path in either is parsed as PEM text and fails with `No matching PRIVATE KEY entries in PEM file`. Verified 2026-09-29 by `deployment/compose/tests/kafka.sh` | **Yes.** One negative test covers encryption and authentication. With an authorizer enabled the controller listener must be authenticated too, or the broker never registers |
| PostgreSQL | Yes | `ssl=on`, `ssl_cert_file`, `ssl_key_file`, and `hostssl` in `pg_hba.conf` for enforcement | **Yes**, because `hostssl` turns it into a refusal |
| ClickHouse | Yes | `tcp_port_secure` (default 9440) or `https_port`, with an `<openSSL>` block | **Yes** |
| SeaweedFS S3 | Yes | `s3.cert.file`, `s3.key.file`, `s3.cacert.file`, `s3.tlsVerifyClientCert`. **Do not also set `s3.port.https`**: in `weed/command/s3.go` at tag 4.47 the plaintext listener starts when `tlsPrivateKey == ""` **or** `portHttps > 0` (s3.go:529), so setting `s3.port.https` alongside a key starts an unencrypted listener on `s3.port` as well. Setting the key and leaving `s3.port.https` unset is what makes the endpoint TLS-only. Verified 2026-09-29 by `deployment/compose/tests/seaweedfs.sh` | **Yes.** This is where the vended credential lands |
| Grafana | Yes | `protocol=https`, `cert_file`, `cert_key` | **Yes**, because a browser makes the chain visible |
| Kafka Connect REST | Yes | The `listeners.https.` prefix with the SSL properties | Ceremony: a loopback admin API |
| Flink REST | Yes | `security.ssl.rest.enabled`, `security.ssl.rest.authentication-enabled` for client certificates, `security.ssl.internal.enabled`, all Java keystore based | Ceremony unless REST is exposed |
| Polaris | Quarkus level | `quarkus.http.ssl.certificate.*` with `quarkus.http.insecure-requests=disabled`; not in the shipped defaults | Low local value |
| Prometheus, Alertmanager | Yes | `--web.config.file` with `tls_server_config`, which the docs mark experimental for Prometheus | Low local value |
| Dagster webserver | **No** | The CLI exposes host, port, path-prefix and read-only; it runs uvicorn with no TLS options | A proxy would be needed |
| Marquez | None found | No TLS code in the API module | A proxy would be needed |
| Apicurio | Expected at the Quarkus level | Not documented on its security page | Unverified (section 10) |

**Certificate tooling against a 14 GB host.** `openssl` adds nothing and is already present. `mkcert` is a binary that issues a local CA and leaf certificates and can expose its root for JVM truststores. `step-ca` is a real CA daemon with ACME and rotation. `cfssl` is a CA API with JSON configuration. Caddy and Traefik would add a proxy and an internal CA. Only `openssl` and `mkcert` add no runtime component.

**Ceremony versus demonstrable.** Demonstrable, because a reviewer can run a pass or fail check: Kafka SASL_SSL (a plaintext client is rejected and a wrong-CA client fails), PostgreSQL with `hostssl` (a non-TLS client is rejected, which is enforcement rather than availability), ClickHouse `tcp_port_secure`, SeaweedFS S3 over HTTPS, and Grafana over HTTPS with a locally trusted CA. Ceremony on a single host: TLS on loopback admin and UI listeners, ClickHouse HTTPS when a native secure port exists, and service-to-service TLS between containers on one podman network, where a self-signed CA trusted by every client is not a boundary.

**The keystore-password question.** Kafka's PEM mode documents that keystore and truststore passwords "are not supported for PEM format", and `ssl.keystore.key` and `ssl.keystore.certificate.chain` are declared as password type so their values are redacted in logs. Kafka's own `ssl.*` broker properties are plaintext in `server.properties` and are not externalisable by Kafka Configuration Providers, so a password-based keystore would force an entrypoint to materialise the password. **Flink cannot do this**: `SecurityOptions.java` defines only Java keystore options and imports `java.security.KeyStore`, and the Flink SSL documentation converts a keystore to PEM only for use as a `curl` client. Flink's keystore password therefore needs an entrypoint. PostgreSQL, ClickHouse and Grafana use raw PEM key files, so the key file is the secret and there is no keystore password.

**Cloud termination.** ACM holds public certificates and they are not exportable; an ALB terminates client TLS, so ALB termination encrypts the client-to-ALB hop only. End-to-end requires re-encryption behind the load balancer or an NLB in TCP pass-through with TLS terminating in the pod.

## 7. Auditability per component

| Component | Trail | Location | Default retention | Actor captured |
|---|---|---|---|---|
| ClickHouse | `system.query_log` | A MergeTree table on local disk | **Unbounded.** "ClickHouse does not automatically delete data from this table" | Yes: `user`, `initial_user`, `authenticated_user`, `os_user`, `client_hostname`, `address`, `query`. There is no row-policy outcome column |
| Polaris | An opt-in event framework plus an HTTP access log | stdout, or Kafka, CloudWatch or a database if a listener is enabled | The container lifetime, or wherever a listener stores | Events carry the principal when enabled; the access log's default "common" pattern does not |
| PostgreSQL | `log_statement=none` and `log_connections` off by default; `logging_collector` off | stderr to the container log | The container lifetime | No, by default. `pgaudit` would be needed and is not bundled |
| Kafka | The broker log and `kafka.authorizer.logger` | A separate `kafka-authorizer.log` | The container lifetime | Denials name the principal at INFO once an authorizer is configured. Without an authorizer there is nothing |
| Dagster | Run and event logs, asset materialisations | SQLite locally, PostgreSQL in production | Indefinite; the retention configuration covers schedules and sensors rather than runs | Run level, not necessarily human |
| OpenLineage and Marquez | Run, job and dataset lineage | The Marquez PostgreSQL database | Indefinite | **No.** The specification has no user, author or principal field, only a producer |
| Flink, Debezium Connect | Job and worker logs | stdout | The container lifetime | No |
| Spark | An event log only when `spark.eventLog.enabled=true`, which defaults to false | Wherever configured | n/a | No |
| Prometheus | A TSDB including the `ALERTS` and `ALERTS_FOR_STATE` series | The local TSDB | 15 days by default | n/a |
| Alertmanager | The notification log and silences | Its storage path | 120 hours by default | n/a |
| Grafana | The audit log is Enterprise and Cloud only; alert state history is in OSS but needs Loki or Prometheus | A file, Loki or the console | Per configuration | The audit log does, but it is not in the OSS edition |

**Local log destination.** There is no log store. Logs are container stdout and `podman logs`, plus ClickHouse's system tables and Dagster's metadata database. A real log store costs at least two components, Loki plus a shipper, and Grafana's alert state history already wants Loki or Prometheus.

## 8. The Polaris denial-audit finding

The claim under test, made in the governance document, was that a denied access is "audited in Polaris". **It is not supported.**

Verified against `apache/polaris` tag `apache-polaris-1.7.0` on 2026-09-29:

- 1.7.0 does have a real event framework. `PolarisEventType` enumerates `BEFORE_` and `AFTER_` events for catalog, namespace, table, view, policy, principal, role, credential, transaction, notification, config, task and rate limit, with listeners for persistence, Kafka, CloudWatch, OpenTelemetry and in-memory.
- The enum contains **no denial, error or forbidden event type**. Events bracket successful operations, and a denial throws before the closing event is emitted.
- Every event-listener setting is **commented out** in `runtime/defaults/.../application.properties` (lines 164 to 203). With no listener configured, nothing is emitted or persisted.
- A denial yields HTTP 403 or 401 through `IcebergExceptionMapper` and an SLF4J line. `quarkus.http.access-log.enabled` is true by default, so an access-log line exists, but the default pattern is "common", which does **not** include the authenticated principal.

So Polaris can audit successful catalog operations with configuration, and a denial is at best an HTTP status line plus an application log line, both in container stdout with no retention.

## 9. Sources

- Kafka: `kafka.apache.org/43/security/listener-configuration/`, `/authentication-using-sasl/`, `/security-overview/`, `generated/connect_config.html`; sources at tag 4.3.1 (`BasicAuthSecurityRestExtension.java`, `JaasBasicAuthFilter.java`, `SslConfigs.java`). Docs page last modified 22 May 2026.
- ClickHouse: `ClickHouse/ClickHouse` docs for access rights, users settings, `CREATE USER`, the `DataLake` database engine, and `programs/server/config.xml`; release 26.08 confirmed 2026-09-11.
- Polaris: `polaris.apache.org/releases/1.7.0/`; tag `apache-polaris-1.7.0` for `managing-security/external-idp`, `vended-credentials`, the AWS S3 production configuration and the MinIO catalog guide.
- SeaweedFS: the wiki pages `S3-Credentials`, `S3-Configuration`, `Amazon-IAM-API`, `OIDC-Integration` and `Security-Configuration`; `weed/command/s3.go` and `filer.go` at tag 4.47.
- PostgreSQL: `postgresql.org/docs/18/auth-password.html` and `/ssl-tcp.html`.
- Prometheus and Alertmanager: `docs/configuration/https.md` and `docs/configuration.md`.
- Grafana: `configure-authentication` docs for 13.x.
- Apicurio: tag `v3.3.3`, `assembly-configuring-registry-security.adoc` and `ref-registry-all-configs.adoc`.
- Marquez: issue #2947 (2024-10-24), the tags list and `build.gradle` at 0.51.1.
- Flink: `release-2.1` `security-ssl.md` and `SecurityOptions.java`.
- Spark: `branch-4.1` `docs/security.md`; Iceberg `docs/rest-catalog.md`.
- OpenLineage: the Python client configuration documentation.
- Secrets Store CSI driver and the AWS provider: `kubernetes-sigs/secrets-store-csi-driver` and `aws/secrets-store-csi-driver-provider-aws`, main, read 2026-09-29.
- Cloud pricing: research 21 (published 2026-09-11) and the AWS Systems Manager pricing page read 2026-09-29.

## 10. Unverified gaps

1. **Podman 6.1.x behaviour.** The host runs podman 5.7.0 with podman-compose 1.5.0, so the pinned row in section 1 is inferred rather than tested.
2. **Polaris TLS on its own listener**, which is Quarkus level and not in the security documentation.
3. **Polaris signing-key rotation** schedule or mechanism at 1.7.0.
4. **Polaris and SeaweedFS STS AssumeRole compatibility.** Both sides are documented separately with no joint integration document. The local interop test in research 08 exercised it, and the permissive trust policy it used is itself recorded as a local-only residual uncertainty.
5. **Apicurio TLS on its listener.**
6. **Marquez TLS on its own listener**; none was found, so proxy termination is assumed.
7. **Alertmanager's multi-tenancy wording** was not found in the documentation; the single global configuration was verified instead.
8. **An official Dagster statement** that the OSS webserver has no authentication was not located; the evidence is community wrappers.
9. **Whether a refused ClickHouse query appears in `system.query_log`.** That the table records a query's user is verified; the denial case is not.
10. **Grafana plain LDAP** OSS versus Enterprise: the methods table lists enhanced LDAP as Enterprise and the explicit split for plain LDAP was not quoted.
