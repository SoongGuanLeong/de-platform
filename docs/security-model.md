# The security model: secrets, service authentication, TLS, auditability and the privacy boundary

**Ticket:** [The security model beyond governance: secrets, TLS, service authentication and auditability](https://github.com/SoongGuanLeong/de-platform/issues/18)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Decision records:** [ADR-0028](adr/0028-secrets-live-only-in-the-runtime-directory.md), [ADR-0029](adr/0029-authenticate-the-data-plane-and-register-the-open-control-plane.md), [ADR-0030](adr/0030-audit-what-exists-and-name-what-cannot-be-attributed.md)
**Evidence base:** [`docs/research/25-security-facts-secrets-auth-tls-audit.md`](research/25-security-facts-secrets-auth-tls-audit.md), verified against the pinned versions on 2026-09-29. Every capability claim and price below traces to it, or is listed in section 9 as unverified.
**Inputs:** [`docs/governance-and-data-quality.md`](governance-and-data-quality.md), [`docs/cloud-architecture.md`](cloud-architecture.md), [ADR-0004](adr/0004-authorisation-seam-between-catalog-and-engine.md), [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md), [`docs/technology-selection.md`](technology-selection.md).

**Status.** This document settles decisions. It contains no measured result. Every capability claim is verified against the pinned version or listed in section 9 as unverified. Every price is a dated list price. The executable evidence these decisions call for is enumerated in section 12 and belongs to the implementation phase, because no platform code exists yet and the cloud shape is authored and never applied as evidence. Nothing here should be read as a produced test.

---

## 1. The security model

### 1.1 What is protected, in priority order

1. The Iceberg tables, which are the record.
2. The PII-bearing columns named in the gold contracts, and the quarantine table, which carries them.
3. The credentials that reach 1 and 2.
4. The correctness of what an analyst reads, which is an integrity asset rather than a confidentiality one.

### 1.2 The adversaries this design says something about

- **An over-privileged or mistaken internal principal.** The realistic case: an analyst principal that should see commerce gold reaches a PII column, or reaches another spine's data. This is what the authorisation seam (ADR-0004) and the ClickHouse grants exist for.
- **A leaked credential.** The prior repository's failure (ADR-0006): four classes of credential committed to a public Git repository, from a mechanical cause. The repository was never deployed, so no running service accepted the values, but the failure class is real and section 2 exists to make it structurally impossible rather than to detect it.
- **A compromised workload** that borrows a broader identity than it needs. This is what IRSA with one role per component, and a node role carrying no S3 or Secrets Manager permission, exist for.
- **A curious party on the development host.** Locally the boundary is the host account and the rootless podman network.

### 1.3 What is out of the threat model, stated rather than implied

- A hostile cloud provider or a compromised hypervisor.
- An attacker holding the developer's own account. Rootless podman means the runtime is not root, but the developer account is the trust anchor and it can read the runtime directory.
- A determined insider holding the `engineer` principal. That principal is deliberately all-powerful and its use is not restricted.
- Supply-chain compromise of an upstream image. Digests are pinned where they are pinned, but no signature verification and no admission policy is authored.
- Physical access, side channels and denial of service.

### 1.4 The two claims, and nothing stronger

1. **The data plane is authenticated.** Every path that moves data between components carries a credential, and each is refused without it.
2. **Transport is encrypted where a refusal can be demonstrated.** Five listeners terminate TLS, each with a negative test. Everything else is plaintext inside one podman network, for the stated reason.

Everything else is either an honest gap (section 9) or a shape-only measure (section 8).

### 1.5 The rule that decides where a control goes

**A control is applied where a negative test can show it working.** Where a control could only be asserted in configuration, it is recorded as shape-only rather than counted as a security property. This is the completion bar's signal-versus-behaviour rule applied to security: a signal proves the mechanism is visible, a behaviour proves it works.

---

## 2. The secrets model

### 2.1 The rule

**No secret value ever exists in a tracked file.** That is the whole of the local rule; everything below is mechanism.

A secret is one of: a password, an OAuth2 client secret, an access key, a private key, or a token signing key. Configuration that is not a secret (a hostname, a port, a username, a topic name, a bucket name) lives in ordinary config and may be committed.

### 2.2 Where a secret lives locally

| Layer | Mechanism | Why |
|---|---|---|
| Authoring | A human writes the value once into `.env` or `runtime/secrets/<name>`, both gitignored | No other path is writable by the bootstrap route |
| Storage | `.env` for compose-level values, `runtime/secrets/` for file-shaped values | `.env` is a file rather than an exported environment, so it does not appear in a process listing |
| Injection | A Compose top-level `secrets:` entry with a `file:` source, or a read-only bind mount, mounted at `/run/secrets/<name>` | The only mechanism verified to work on both podman-compose and docker compose v2 |
| Consumption | The component reads a file path | Env-var intake is used only where a component has no file intake |

### 2.3 What was rejected, and why

| Rejected | Reason |
|---|---|
| Compose `secrets:` with an `environment:` source | podman-compose fails with `ValueError: ERROR: unparsable secret` (observed at 1.5.0; not re-verified at the pinned 1.6.0); the source is Docker-Compose-only, so it breaks the portability rule |
| Native `podman secret` | Works on podman only, with no Docker equivalent outside swarm. Its file driver is also unencrypted on disk |
| Environment variables for secret values | Readable by every process in the container and visible in `podman inspect` |
| SOPS plus age, encrypted in Git | A real option and the documented alternative if Git-encrypted secrets are ever required. Not adopted, because the runtime directory solves the same problem with no extra tool and no key-distribution question |

### 2.4 The controls, and the honest limit

1. `.gitignore` covers `*.bak`, `.env`, `.env.*` (except `.env.example`), `*.pem`, `*.key`, `*.jks`, `*.p12` and `runtime/`.
2. `.env.example` is committed and lists every variable with a placeholder, so a variable missing from the real `.env` is visible in review.
3. Bootstrap and setup scripts may write secret values only inside `runtime/`. No script may create a tracked `.bak`, config, YAML, JSON or source file containing a secret. This is the specific mechanical failure in ADR-0006, where a bootstrap script minted a fresh secret into a tracked `.bak` on every run.
4. CI runs gitleaks over the full history; GitHub native secret scanning is a secondary backstop.

5. Compose's `secrets:` mechanism with a `file:` source mounts the file with the host's owner and mode, and podman-compose ignores a secret's `mode`, `uid` and `gid` fields, so under rootless podman the file appears in the container owned by container-root. **A container that runs as a non-root user therefore cannot read its own secret.** There are two mechanisms and both cost something: an entrypoint that starts as root and re-materialises the file with the right owner (PostgreSQL and ClickHouse here), or remapping the host file with `podman unshare chown` (Kafka here, whose image runs as `appuser` and cannot start as root). The remap makes the file **unreadable from the host**, so anything needing the value must read it inside the container. Neither mechanism is free, and the cost is recorded rather than hidden.

**The honest limit, which is the important part.** No secret scanner would reliably have caught the ADR-0006 leak. The leaked values were self-minted by the bootstrap script, so they match no provider pattern: GitHub native scanning knows partner patterns only and custom patterns need a paid plan, gitleaks is format and entropy, and trufflehog's verification works only for providers it supports. The decisive control is structural, not detective: gitignore correctness, plus a bootstrap path that cannot write outside the runtime directory. Scanning is a backstop that catches the common case of a real third-party token, not the self-minted case. A pre-commit hook is additionally bypassable with `git commit --no-verify` and covers staged content only.

### 2.5 The inventory and its rotation class

Rotation class is one of three, and it is a property of the component rather than a hope:

- **Reload** - the component re-reads without a restart.
- **Restart** - the value is read at process start, so rotation needs a restart or a rolling restart.
- **Init** - the value is consumed once at first initialisation and cannot be rotated by re-reading.

| Secret | Component | Intake | Class | Rotation mechanism |
|---|---|---|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL 18 | env, `POSTGRES_PASSWORD_FILE` | Init | `ALTER USER` plus a restart; the entrypoint value is init-only |
| Kafka SCRAM credentials | Kafka 4.3.1 | `sasl.jaas.config`, rendered by the entrypoint because Kafka has no file intake for it | Restart | `kafka-configs.sh --alter` for client credentials; broker credentials need a rolling restart |
| Kafka TLS private key | Kafka 4.3.1 | PEM file (`ssl.keystore.location`, one file holding the key and the chain) | Restart | Replace the projected file and restart. PEM mode means there is deliberately no keystore or key password |
| `POLARIS_CLIENT_SECRET_<service>` | Polaris 1.7.0 | env or config | **Reload** | Through the management API, with no server restart. `/rotate` is two-phase: it issues a new secret and retains the previous one as a secondary that keeps authenticating until the next rotate, so the previous secret is refused only after a second rotate. A root `/reset` refuses the previous secret immediately, and that is the path demonstrated end to end. The reset endpoint also accepts a caller-supplied secret, so the value can be human-authored even though creation generates one |
| `POLARIS_BOOTSTRAP_CREDENTIALS` | Polaris 1.7.0 | env | Init | Bootstrap-only, at first start |
| `SEAWEEDFS_S3_ACCESS_KEY` and secret | SeaweedFS 4.47 | JSON config file | Restart | Rewrite the config and restart |
| ClickHouse passwords | ClickHouse 26.8 | `users.d/*.xml` or SQL | **Reload** | `SYSTEM RELOAD USERS` |
| Grafana admin password | Grafana 13 | `GF_SECURITY_ADMIN_PASSWORD__FILE` | Restart | Restart with a new projected file |
| Alertmanager SMTP and webhook | Alertmanager 0.34 | `*_file` config fields | **Reload** | Config reload via `/-/reload`; `*_file` contents are re-read |
| Debezium source password | Debezium 3.6.1 | Connector config via the Connect REST API | **Reload** | `PUT /connectors/<name>/config`, no worker restart |
| `RIPE_ATLAS_API_KEY` | RIPE Atlas collector | Read-only file at `/run/secrets`, read at process start | Restart | Replace the projected file and restart the collector. It is the platform's only third-party credential, and the only one a scanner would reliably match, so it must never be baked into an image or a compose file |
| AWS credentials | all, cloud | IRSA | n/a | Not a long-lived secret: IRSA issues short-lived STS credentials per pod |

The count of genuinely long-lived secrets in the cloud shape is therefore small, and no static AWS key is among them.

### 2.6 The cloud form

```
AWS Secrets Manager
      |
      v
Secrets Store CSI Driver   (SecretProviderClass, filePermission: "0400")
      |
      v
/run/secrets/<name>        (tmpfs, read-only)
      |
      v
container
```

- **AWS Secrets Manager, not SSM Parameter Store.** Secrets Manager is $0.40 per secret per month against SSM Parameter Store Standard at no charge, which at the cloud document's budget of one secret in the minimal arm and five in the reference arm is $0.40 and $2.00 per month, or roughly $0.003 and $0.016 for a six-hour demo. Cost is therefore not the discriminator. Secrets Manager is kept because it is the only one of the two with managed rotation, and because the cloud document already budgets it. SSM Parameter Store Standard is recorded as the lower-cost fallback, and the swap is a `SecretProviderClass` change.
- **`filePermission: "0400"` is set explicitly.** The driver's default is 0644 and its AWS provider also defaults to 0644. The driver projects into a tmpfs mount that is enforced read-only, and the value is gone when the pod goes away, but a world-readable private key inside the container is still wrong.
- **No static AWS credentials in the cluster.** Every workload assumes its own IAM role through its service account. The node instance role carries no S3 and no Secrets Manager permission, and IMDS is restricted to a hop length of 1.

---

## 3. The authentication matrix

### 3.1 The data plane, authenticated

| Path | Mechanism | Version detail | Negative test |
|---|---|---|---|
| Debezium to PostgreSQL | SCRAM-SHA-256 | `password_encryption = scram-sha-256`; the source user is not a superuser | Wrong password refused at connect |
| Debezium to Kafka | SASL_SSL, SCRAM-SHA-256 | Connect worker and connector producer and consumer configs | Wrong SCRAM credential refused |
| Flink to Kafka | SASL_SSL, SCRAM-SHA-256 | Kafka connector properties | Wrong SCRAM credential refused |
| The RIPE Atlas collector to Kafka | SASL_SSL, SCRAM-SHA-256 | The collector's own SCRAM principal, distinct from Debezium's and Flink's | Wrong SCRAM credential refused |
| Flink to Polaris | OAuth2 client credentials | Iceberg REST catalog, `rest.auth.type=oauth2` | Wrong client secret refused with 401 |
| Spark to Polaris | OAuth2 client credentials | `spark.sql.catalog.<c>.rest.auth.type=oauth2` | Wrong client secret refused with 401 |
| ClickHouse to Polaris | OAuth2 client credentials | `DataLakeCatalog`, `catalog_type='rest'`, `catalog_credential` | Wrong credential refused |
| Spark to ClickHouse | ClickHouse SQL user and password | sha256 password; the batch load principal is `svc_platform` | Wrong password refused at handshake |
| Flink to ClickHouse | ClickHouse SQL user and password | sha256 password; the serving feed principal is `svc_platform` | Wrong password refused at handshake |
| Dagster to ClickHouse | ClickHouse SQL user and password | `svc_platform` to write, `dq_reader` to read check results | Wrong password refused |
| Dagster to PostgreSQL | SCRAM-SHA-256 | Dagster's metadata store | Wrong password refused |
| Polaris to SeaweedFS | AssumeRole with an inline session policy | `stsEndpoint` pointed at SeaweedFS STS; the vended credential is prefix-scoped | A read outside the vended prefix refused with `AccessDenied`, which is M10's test as measured in research 08 rather than in this document |
| Spark and Flink to SeaweedFS | The vended, prefix-scoped credential | S3FileIO using the Polaris-vended credential | A read outside the prefix refused with `AccessDenied` |
| Debezium to Apicurio | none, deliberately | See section 5 | n/a |

### 3.2 The path that does not exist, stated rather than invented

**Dagster does not authenticate to Polaris, because Dagster OSS is not an Iceberg REST catalog client.** Dagster orchestrates: it launches Spark and Flink jobs, and those engines authenticate to Polaris. There is no Dagster-to-Polaris credential to configure and none is authored. A future Dagster asset needing catalog access would reach it through the engine it launches.

### 3.3 The mechanisms, per component

- **PostgreSQL 18**: SCRAM-SHA-256, which is the most secure of the shipped password methods, with `hostssl` in `pg_hba.conf` so a non-TLS connection is refused rather than merely unprotected.
- **Kafka 4.3.1**: `SASL_SSL` listeners with `SCRAM-SHA-256`, no extra service required in KRaft mode. Client credentials are seeded with `kafka-storage.sh format --add-scram` or `kafka-configs.sh`. **The controller listener must itself be authenticated once an authorizer is enabled**, which is a forced consequence rather than a choice: a plaintext controller listener presents `User:ANONYMOUS`, `StandardAuthorizer` denies it `CLUSTER_ACTION` on the broker's own `BROKER_REGISTRATION`, and the broker then never becomes active. The controller listener therefore runs `CONTROLLER:SASL_SSL` as the admin principal, which is a super user. Enabling an authorizer hardens the controller listener as a side effect instead of leaving it as internal plaintext.
- **Polaris 1.7.0**: OAuth2 client credentials through the Iceberg REST catalog's token endpoint, one client per engine, with a token lifetime of `PT1H` by default.
- **ClickHouse 26.8 LTS**: SQL-driven access control with sha256 passwords, the users and roles fixed in [`docs/governance-and-data-quality.md`](governance-and-data-quality.md), and `tcp_port_secure` for the encrypted path.
- **SeaweedFS 4.47**: S3 access keys from its JSON config, with the platform's engines using the Polaris-vended prefix-scoped credential rather than the static key.
- **RIPE Atlas collector**: produces to Kafka over `SASL_SSL` with `SCRAM-SHA-256` under its own principal, and reads the publisher's API over TLS using `RIPE_ATLAS_API_KEY` from a read-only file. It is the platform's only third-party credential and its only component whose upstream is outside this host. Its negative test is the refused Kafka connection; the publisher-side key is not negatively tested, because driving RIPE Atlas with an invalid key risks the publisher's documented IP-ban policy, and that is stated rather than implied.

---

## 4. The TLS matrix

### 4.1 Encrypted, each with a negative test

| Listener | Configuration | Negative test |
|---|---|---|
| Kafka broker | SASL_SSL in PEM mode: `ssl.keystore.type=PEM` with `ssl.keystore.location` pointing at one file that holds the private key and the chain | A plaintext client is refused, and a client trusting the wrong CA is refused |
| PostgreSQL | `ssl=on`, `ssl_cert_file`, `ssl_key_file`, and `hostssl` in `pg_hba.conf` | A non-TLS client is refused, because `hostssl` is enforcement rather than availability |
| ClickHouse | `tcp_port_secure` with an `<openSSL>` certificate, key and CA | A client without TLS is refused |
| SeaweedFS S3 | `s3.cert.file`, `s3.key.file`, `s3.cacert.file`, and deliberately **no** `s3.port.https`: in 4.47 a plaintext listener starts when the key is unset **or** an HTTPS port is configured, so adding `s3.port.https` would open an unencrypted path to the same endpoint | A plain HTTP request to the S3 endpoint is refused, and the server records the same refusal as a TLS handshake error. This is the listener the vended credential lands on, so it is the one that matters most |
| Grafana | `protocol=https`, `cert_file`, `cert_key` | An `openssl s_client` handshake trusting the local CA exits 0, reports `Verify return code: 0 (ok)`, and the served leaf's issuer is the local CA; the same handshake against the system trust store is refused, with `-verify_return_error` making that a non-zero exit |

### 4.2 Plaintext, with the reason

Everything else: Polaris, Apicurio, Marquez, Flink REST, the Kafka Connect REST API, Dagster, Prometheus and Alertmanager.

The reason is one sentence: **a self-signed CA trusted by every client on the same host, on a single rootless podman network, is not a security boundary, and wrapping a loopback development UI in TLS is ceremony.** What TLS on those listeners would buy is a demonstration that a configuration surface exists, which is not a claim this platform needs to make.

Two of them have a second reason: Dagster's webserver has no native TLS option at all, and Marquez documents none, so both would need a reverse proxy, which is a component admitted only to encrypt loopback traffic.

### 4.3 The certificate tooling

An `openssl`-based target generates a local CA and one leaf per TLS listener into the gitignored `runtime/certs/`. No runtime component is added: `mkcert` is an extra tool for what `openssl` already does here, and `step-ca` is a CA daemon for a rotation story nothing in this platform needs. Kafka's key is emitted as an unencrypted PKCS#8 PEM, because PEM mode has no keystore or key password, which designs that secret out entirely. Kafka's PEM configuration then has **two mutually exclusive styles that are not interchangeable**: `ssl.keystore.key` and `ssl.keystore.certificate.chain` take PEM **content**, whereas `ssl.keystore.location` takes a **path** to one file holding both the key and the chain. A path placed in a content slot is parsed as PEM text and fails with `No matching PRIVATE KEY entries in PEM file`, which reads like a corrupt key rather than a misconfiguration. The file style is used here so the key stays in the mounted file instead of being copied into the rendered server properties.

One tooling trap is worth naming because it silently inverts a negative test: **`openssl s_client` exits 0 even when certificate verification fails, unless `-verify_return_error` is passed.** A refusal assertion written without that flag is a verification failure printed underneath a success exit code, which is precisely the failure mode the negative tests exist to prevent. Every TLS assertion in the harness passes `-verify_return_error` so that a failed verification is a non-zero exit.

### 4.4 The Kafka and Flink asymmetry

Kafka can run PEM mode, so it has no keystore password. It still needs an entrypoint, for a different reason: Kafka has no file intake for a SASL password, so the SCRAM credential must be rendered into the server properties. **Flink needs one too**: its SSL options are Java keystore only, and its own documentation converts a keystore to PEM solely for use as a `curl` client rather than as a server keystore. Flink's keystore password therefore has to be materialised into `flink-conf.yaml` by an entrypoint that reads a projected file. Two components in twenty needing an entrypoint step, for two different reasons, is an explainable exception; a password sitting in a tracked file would not be.

### 4.5 The cloud distinction, stated so it cannot be misread

**ALB TLS termination encrypts the client-to-ALB hop only. It does not encrypt the ALB-to-pod hop.** A claim of end-to-end encryption needs either re-encryption behind the load balancer or an NLB in TCP pass-through mode with TLS terminating in the pod. The reference arm authors an ALB for the browser-facing surfaces, so its encryption claim is client-to-ALB and is labelled as such; the data-plane listeners are reached by TCP pass-through with TLS terminating in the pod.

---

## 5. The unauthenticated surfaces register

Most components in this stack ship with authentication disabled or absent by default, and several have none at all. Four data-plane surfaces are closed (Kafka, ClickHouse, SeaweedFS's S3 endpoint and PostgreSQL), and the table below names every surface that stays open locally. This is deliberately a register rather than a set of proxies: a basic-auth layer in front of a loopback UI would be visible to a reviewer as theatre, and the sprawl test would reject the component that carried it.

| Component | Surface | What is unauthenticated | Why acceptable locally | Network boundary | Cloud protection | Known limitation |
|---|---|---|---|---|---|---|
| Dagster | Webserver UI and GraphQL API | Everything. OSS has no built-in authentication; SSO is a paid edition | A single local operator, loopback-bound | Loopback and the compose network | ALB with proxy or OIDC authentication in front; an IRSA role scoped to its own writes | No RBAC inside Dagster: any reachable client is an admin |
| Marquez | REST API and UI | Everything. The maintainers state authentication is absent and is not due until 0.52 | Lineage is read-only metadata and carries no PII | Loopback and the compose network | ALB with proxy authentication; an IRSA role read-only on its own metadata database | The OpenLineage HTTP transport's bearer token is not verified by the server, so it is shape-only |
| Flink | REST API and web UI | Client authentication. TLS and optional client-certificate auth exist and are off | Job submission is a development action on the host | Loopback and the compose network | ClusterIP only, no ingress; jobs submitted by Dagster inside the cluster | A reachable REST endpoint can submit or cancel jobs |
| Kafka Connect (Debezium) | REST API | Connector management. Basic authentication is an opt-in extension | It configures connectors and holds no PII itself | Loopback and the compose network | ClusterIP only; the source database credential is projected into the connector, not into the API | A reachable REST endpoint can read connector configuration, which contains a database username |
| Apicurio | REST API and UI | Everything. Authentication is disabled by default at 3.3.x | The registry holds schemas, which are public interfaces | Loopback and the compose network | OIDC is the documented path and is not authored; section 9 records the gap | No registry authentication is exercised, so the path is unproven |
| Prometheus | UI and query API | Everything unless `--web.config.file` is supplied | Metrics only, and the query API is read-only | Loopback and the compose network | ClusterIP only, scraped by Grafana inside the cluster | A reachable query API discloses metric labels |
| Alertmanager | UI and API | Everything unless `--web.config.file` is supplied | Silences and alert state only | Loopback and the compose network | ClusterIP only | No multi-tenancy and no RBAC: one global config and one silence namespace |
| SeaweedFS | Filer, master and admin endpoints; the bundled **Iceberg REST catalog** (8181) and **Lance namespace server** (9101); WebDAV (7333) | Everything on those ports. The S3 endpoint is the only authenticated surface | The platform uses only the S3 endpoint, and the other ports are not published to the host | Loopback and the compose network; only the S3 port is published | Security groups and a cluster-internal service only, and the catalog surfaces are disabled outright with `-s3.port.iceberg=0 -s3.port.lance=0 -webdav=false` | **An exposed Iceberg REST catalog would bypass Polaris, not merely the S3 key check**: a client could resolve table metadata without passing the authorisation seam. Verified 2026-09-29 — `weed mini` starts all of these by default |
| RIPE Atlas collector | Prometheus metrics endpoint | Everything. A metrics listener with no authentication | Metrics only: counters and gauges, not measurement data | Loopback and the compose network | ClusterIP only, scraped by Prometheus inside the cluster | The endpoint is the only place the collector's error rate is observable, and no alert threshold is declared for it yet; the incident laboratory records that as a gap |
| Podman | API socket | The socket itself; access control is Unix socket permissions | It is the local container runtime, rootless | A Unix socket owned by the developer account | Not applicable: the cloud runtime is EKS rather than podman | Any process running as the developer can control the local runtime |
| OpenLineage client | Outbound transport | No authorization by default | It is a client, not a listener | n/a | Marquez is cluster-internal | See Marquez |

Two surfaces are deliberately absent from this register, and the reason matters: **Grafana** has authentication on by default and is one of the five TLS listeners, and **ClickHouse's `default` user** is closed during bring-up rather than left with its shipped empty password.

---

## 6. The audit matrix

### 6.1 What each system records

| System or action | Attributed? | Evidence source | Retention | Limitation |
|---|---|---|---|---|
| A query through ClickHouse | Yes, to the ClickHouse user | `system.query_log` (`user`, `initial_user`, `client_hostname`, `query`) | Bounded by section 7 | Whether a refused query appears there is confirmed during implementation; the row policy's outcome is not a column |
| A denied catalog operation | Yes, in three records, none of them a denial event | The `PolarisAuthorizerImpl` line `Authorization denied for principal '<p>' on operation '<OP>': missing <PRIVILEGE> on <RESOURCE>`; the access log, which carries the principal in `%u` once the log is enabled; and an unmatched `BEFORE_*` row in the metastore | The access log and the authorizer line live in the container log; the metastore follows section 7 | There is no denial event *type*, and an unmatched `BEFORE_*` row means "attempted and did not complete" rather than specifically "denied", because a 404 leaves one too. The OAuth token endpoint sits outside the event framework, so a failed token request leaves no event row at all |
| A successful catalog operation | Yes, once the listener is enabled | The Polaris event framework persisted to its metastore, as a matched `BEFORE_*`/`AFTER_*` pair (`AFTER_*` for catalog, namespace, table, policy, principal, role, credential and transaction) | The operational window in section 7 | Opt-in. With no listener configured, nothing is emitted or persisted |
| A Kafka authorisation denial | Yes: the principal, the operation, the resource and the host | `/opt/kafka/logs/kafka-authorizer.log`, written by `StandardAuthorizer` to a separate file rather than to stdout | Unbounded: rotated hourly by Kafka's shipped `log4j2.yaml` but never deleted, and held in the container's writable layer | Only once an authorizer is configured; without one there is no authorisation audit line at all |
| A read of a lakehouse table's bytes | **No** | none | n/a | The vended credential is a prefix-scoped storage credential, so the read does not pass through the catalog. This is the auditability consequence of ADR-0004 |
| A job's inputs and outputs | Partly | Marquez lineage, from OpenLineage | The Marquez metadata database | The OpenLineage spec has no user or author field, so lineage records what ran and never who ran it |
| A Dagster run and asset materialisation | Yes, at run level | The Dagster metadata database | Indefinite by default; Dagster's retention configuration covers schedules and sensors rather than runs | Run-level rather than necessarily human-level |
| A Spark job's execution | No, by default | none unless `spark.eventLog.enabled=true`, which defaults to false | n/a | No actor identity by default |
| A Flink or Debezium job's behaviour | No | Container logs | The container log | Operational logs rather than an audit trail |
| A Grafana configuration change | No | none | n/a | Grafana's audit log is an Enterprise and Cloud feature and is not in the OSS edition |
| Alert firing history | n/a | The Prometheus `ALERTS` series | Prometheus retention, 15 days by default | Serves Grafana's alert history without adding Loki |

### 6.2 The auditor's questions, answered honestly

| Question | Verdict |
|---|---|
| Who read customer PII in the last 30 days? | **Cannot** on the lakehouse path, because the vended credential bypasses the catalog. Partial for ClickHouse reads, through `system.query_log` |
| Show every denied access attempt in the last 30 days | **Partly.** Polaris leaves structured principal-bearing records: the `PolarisAuthorizerImpl` line and an unmatched `BEFORE_*` row. But there is no denial event type, an unmatched `BEFORE_*` row cannot be told from a 404 by the row alone, and the records are unbounded, living in the container log or the metastore. The Kafka line needs an authorizer and survives only as long as the container log, and there is no log store |
| Who was granted access to a namespace in the last 90 days? | **Yes** once the Polaris event listener persists to the metastore. Current state only without it |
| Who dropped or overwrote a table, and when? | **Partly.** An Iceberg snapshot gives a timestamp rather than an actor; the Polaris `AFTER_DROP_TABLE` and `AFTER_COMMIT_TRANSACTION` events give the principal once the listener is on |
| What did job J read and write? | **Partly**, through Marquez, for instrumented jobs only, and without the actor |
| Which principal produced to which topic, and what was denied? | **Partly.** The authorizer log names the principal for denials; producer identity in the data is not recorded |
| Prove encryption was on for all data-plane traffic | **Partly.** The TLS configuration and its negative tests are the evidence; there is no central record of the negotiated protocol per connection |

### 6.3 The wording the platform uses

> A denial is refused and attributable, with the attribution mechanism explicitly identified for each system.

That sentence replaces the earlier "audited in both engines", which was not true of Polaris. The attribution mechanism is named per system in 6.1, and what cannot be attributed at all is named in 6.2 and section 9.

---

## 7. The retention policy

| Trail | Location | Retention | Mechanism |
|---|---|---|---|
| ClickHouse query log | `system.query_log` | A declared window, set by a TTL | A TTL on the table. The default is unbounded, which is the defect this policy exists to fix |
| Polaris catalog events | PostgreSQL, the operational database | The operational window | The scheduled delete and vacuum the operational database already uses |
| Polaris access log, Kafka authorizer log, and the Flink, Debezium and Spark logs | The container log | The container or pod lifetime | none locally. Bounded by the container, and by CloudWatch Logs retention in the cloud |
| Dagster runs and materialisations | The Dagster metadata database | The operational window | Dagster's own retention for schedules and sensors; runs trimmed by the Dagster retention asset |
| Lineage | The Marquez metadata database | The operational window | The same scheduled job |
| Prometheus metrics | The Prometheus TSDB | 15 days by default | Prometheus retention flags |
| Alertmanager state | Its storage path | 120 hours by default | Alertmanager's own retention |
| Quarantine rows | Iceberg `platform.quarantine` | 30 days | A scheduled `DELETE` plus snapshot expiry, because Iceberg has no TTL |

**No log store is introduced.** Loki plus a shipper is two components bought to give container logs a retention policy, and Grafana's alert history is served from Prometheus instead. The honest position is that container logs are bounded by the container's life unless a cloud logging service with a declared retention is added, and that is stated rather than hidden behind a stack.

**ClickHouse's `system.query_log` is explicitly bounded.** It is the one native audit trail that is unbounded out of the box and that records a user, so leaving it unbounded would be the easiest way to make the audit claim quietly false.

---

## 8. Privacy: the GDPR-shaped boundary

**No claim of compliance.** There is no lawful basis, no data protection impact assessment and no subject-request process, and none can be evidenced on a laptop. The term for what follows is GDPR-shaped, used deliberately.

### 8.1 Real and testable

| Measure | Where | Test |
|---|---|---|
| Minimisation: a PII column no query needs is dropped from gold | The gold contracts and the gold tables | The column is absent from gold and present in silver |
| Column-level grants | ClickHouse | `analyst_ops` is refused `SELECT(c_phone)`; `engineer` is allowed the same column |
| Row-level policy | ClickHouse, one policy on the CDC serving facts | `analyst_ops_wh1` returns its own warehouse's rows and other warehouses' rows are absent |
| Table-level authorisation on the Iceberg path | Polaris | `analyst_commercial` is refused `commerce.silver.customer` |
| The deletion path | Iceberg, from a source delete through Debezium to a `MERGE ... WHEN MATCHED THEN DELETE` | The key is absent from the current snapshot |
| The erasure window | Shorter snapshot retention on PII tables | The historical snapshots containing the key expire, asserted by the retention dry run |
| Quarantine access restriction | `engineer` and `dq_reader` only | An analyst principal is refused the quarantine table |

### 8.2 Shape-only, and not counted as a control

| Claim | Status |
|---|---|
| A lawful basis for processing | Absent. Not evidenced and not claimed |
| A data protection impact assessment | Absent |
| A data-subject request process | Absent. The deletion path is a technical mechanism, not a request process |
| A defensible legal retention decision | Absent. The retention figures are engineering policy with a stated reason, not a legal determination |
| Compliance with any named framework | Absent by decision. HIPAA and SOC 2 are out of scope on the map |

### 8.3 The two technical limitations that matter

1. **PII read attribution on the lakehouse path is partial.** A read using the vended credential does not pass through the catalog, so no system attributes it to a user. ClickHouse reads are attributable; lakehouse reads are not. This is the auditability counterpart of the authorisation seam, and it is a structural property of a catalog that authorises metadata rather than bytes, not a configuration gap that more logging would close.
2. **Quarantine contains PII.** The `_record` payload is the rejected row, so a quarantined customer row carries a name and a phone. Its access is the tightest in the platform and its retention the shortest, at 30 days, and **its deletion path must be exercised rather than assumed**: the same end-to-end test that proves the gold deletion must be run against the quarantine table, because a deletion path that works on gold and is never run on the table holding the rejected rows has proved nothing about the table holding the rejected rows.

---

## 9. Known limitations and honest gaps

1. **Polaris has no denial event type.** A denial is never recorded *as* a denial. It leaves three principal-bearing records instead: an HTTP 403, a `PolarisAuthorizerImpl` line naming the principal, the operation and the missing privilege, and an unmatched `BEFORE_*` row in the metastore. Recorded, with the correction applied wherever the opposite was claimed, and with the earlier over-correction also corrected: the claim that Polaris leaves no structured record was as wrong as the original claim that it audits denials.
2. **Lakehouse reads are not attributable to a user.** Structural, per ADR-0004.
3. **OpenLineage carries no actor.** Lineage records what ran, never who ran it, so Marquez cannot answer a who question.
4. **No central log store.** Container logs are bounded by the container's life.
5. **Grafana's audit log is Enterprise only**, so Grafana configuration changes are not audited in the OSS edition.
6. **Apicurio's authentication path is unexercised.** OIDC is the documented cloud path and no identity provider is authored.
7. **Marquez has no authentication at all**, and the OpenLineage bearer token it receives is not verified.
8. **Two components need entrypoint-based secret injection**: Kafka, because it has no file intake for a SASL password, and Flink, because its SSL options are Java keystore only.
9. **No local TLS on the unauthenticated surfaces register**, for the reason in 4.2. The demonstration value is not there.
10. **`system.query_log` denial capture is unverified.** That the table records a query's user is verified; whether a refused query appears in it is confirmed during implementation rather than asserted here.
11. **The cloud security shape is authored and never applied as evidence.** IRSA, security groups, the ALB and Secrets Manager are validated and rendered, not exercised. Section 10 names the difference.
12. **No image signature verification and no admission policy.** Digests are pinned; provenance is not verified at admission.
13. **The unverified research gaps carry forward**: Apicurio's and Marquez's own listener TLS surfaces, Polaris's signing-key rotation schedule, and whether Polaris's AssumeRole calls are fully compatible with SeaweedFS STS.
14. **The Kafka authorizer denial log has no retention bound.** `StandardAuthorizer` writes denials to `/opt/kafka/logs/kafka-authorizer.log` rather than to stdout, at `INFO`, mode 0600 owned by the container user. Kafka's shipped `log4j2.yaml` rotates that file hourly and deletes nothing, and the file lives in the container's writable layer, so it is lost when the container is removed. The audit line exists; a durable audit destination does not.
15. **A client-side refusal is not by itself evidence of why a request failed.** A plaintext client against a TLS listener fails as a client-side timeout, which is indistinguishable from an unreachable broker. The evidence for TLS enforcement is therefore the broker's own `SSL handshake failed` line, and the tests assert both rather than the timeout alone.
16. **A TLS-terminating container must be given its own leaf and the CA certificate, not the certificate directory.** The local certificate directory is mode 0700 and also holds `ca.key`, which can forge a certificate for any listener in the stack, so a directory mount both fails for a non-root container user, which cannot traverse a 0700 directory, and grants far more than the listener needs. Each service mounts the individual files it uses.
17. **A negative test is only as good as its tool's exit code and wording.** Two traps of this class were found while producing the evidence. `openssl s_client` exits 0 on a failed verification unless `-verify_return_error` is passed (section 4.3), and curl 8.18 reports a refused connection as `Failed to connect ... Could not connect to server` rather than `Connection refused`, so a negative test that greps for the latter fails even when the port is correctly closed. Both were caught only because every refusal assertion here requires the exit code **and** the message, and because each is paired with a positive control that proves the probe can still distinguish an open port from a closed one.
18. **The Polaris events table is unbounded in the harness.** Section 7 assigns the catalog events the operational window of the platform's metastore, but the harness runs no trimming job, so the evidence profile's `polaris_schema.events` grows without limit. The retention policy is the platform's; what was exercised here is the record's content, not its bound.
19. **An assertion against a rotating log must not depend on a position in that log.** The Kafka authorizer assertion originally recorded the file's line count before the denial and read only the lines after that marker. It broke at an hour boundary: Kafka rotates `kafka-authorizer.log` hourly, the marker was taken from the file that was current at the time, and the denial landed in the freshly rotated file, so the assertion failed while the control it was testing had worked. Freshness now comes from a run-scoped resource name and the search spans the rotated siblings. The general lesson is that a marker-based assertion encodes an assumption about a file's continuity, and a rotating log does not offer one.

---

## 10. Local versus cloud security differences

| Concern | Local | Cloud | What the difference means |
|---|---|---|---|
| Workload identity | none. Each container runs as a local process | IRSA, one IAM role per component, and a node role with no S3 or Secrets Manager permission | The local run evidences the shape of the credential flow, not IAM policy semantics |
| Secret storage | Files under a gitignored `runtime/` | AWS Secrets Manager projected by the Secrets Store CSI driver into tmpfs | The local file mode and the cloud `filePermission` are different mechanisms serving the same rule |
| Network boundary | One rootless podman network, with loopback for the UIs | A VPC with public and private subnets, security groups, and no NAT in the minimal arm | Local isolation is real but weaker, and it is the only thing standing behind the unauthenticated surfaces |
| Transport | Five listeners with TLS and a negative test each | TLS terminated at the ALB for the browser surfaces, and TCP pass-through with in-pod TLS for the data plane | ALB termination is client-to-ALB only, and is labelled as such |
| Storage credential | Polaris vends against SeaweedFS STS, with a permissive trust policy and no IAM policy simulation | Polaris vends against AWS STS, with the vending role's trust policy naming Polaris's IRSA role as the only principal | SeaweedFS STS is not AWS STS |
| Audit destination | Container logs, the ClickHouse system tables, and the Dagster and Marquez metadata databases | The same, plus CloudWatch Logs with a declared retention | The cloud adds a retention mechanism, not an attribution mechanism |
| Container runtime | Podman, rootless | Not used; EKS | The podman API socket has no authentication and is bounded by Unix permissions |

---

## 11. What this document does not contain

No measured result. Every price is a dated list price. Every capability claim is verified against the pinned version or listed in section 9 as unverified. No test result is reported here, because no platform code exists yet: the executable evidence in section 12 is the implementation phase's obligation, recorded so that it can be demanded rather than assumed.

---

## 12. The evidence plan

The decisions above are settled. This table is what will prove them, and it is deliberately separate from them: a decision is not evidence, and the completion bar's signal-versus-behaviour rule applies here as everywhere.

| Decision | Evidence it will produce | Depends on |
|---|---|---|
| Secrets live only in the runtime directory | `git check-ignore` proves the path ignored, a history scan finds nothing, and the bootstrap script's write path is asserted to be inside `runtime/` | The bootstrap script existing |
| `.env.example` documents every variable | Every variable in the compose files resolves to a key in `.env.example` | The compose files |
| Secrets arrive at `/run/secrets` | A container reads its secret from the mounted path | A running compose profile |
| Cloud secrets arrive through the CSI driver | A rendered `SecretProviderClass` carrying `filePermission: "0400"`, applied only inside the priced demo | A cluster, inside the demo window |
| Rotation works end to end | The Polaris client secret is rotated through the management API and a client reconnects without a restart | A running Polaris |
| The data plane refuses bad credentials | One negative test per row of section 3.1 | The relevant profile running |
| The TLS boundaries refuse plaintext and wrong CAs | One negative test per row of section 4.1 | The relevant profile running |
| Polaris successful events are audited | A grant change is made and read back from the metastore | A running Polaris with the listener enabled |
| Polaris denials are attributable | A denied request appears in the access log with the principal, in the `PolarisAuthorizerImpl` line, and as an unmatched `BEFORE_*` row | The access log enabled |
| Kafka denials are logged | A denied produce appears in `kafka-authorizer.log` | `StandardAuthorizer` configured |
| ClickHouse query-log retention is bounded | The TTL exists and rows older than the window are gone | A running ClickHouse carrying the TTL |
| Quarantine deletion is exercised | The deletion test run against `platform.quarantine` as well as against gold | The deletion path implemented |
| No unnecessary component was introduced | The technology count is still twenty, plus infrastructure | The implementation |

---

*Resolved by [the security-model ticket](https://github.com/SoongGuanLeong/de-platform/issues/18) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Decision records [ADR-0028](adr/0028-secrets-live-only-in-the-runtime-directory.md), [ADR-0029](adr/0029-authenticate-the-data-plane-and-register-the-open-control-plane.md) and [ADR-0030](adr/0030-audit-what-exists-and-name-what-cannot-be-attributed.md). Inputs: [`docs/governance-and-data-quality.md`](governance-and-data-quality.md), [`docs/cloud-architecture.md`](cloud-architecture.md), [`docs/requirements-matrix.md`](requirements-matrix.md), [ADR-0004](adr/0004-authorisation-seam-between-catalog-and-engine.md), [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md), [`docs/research/04-polaris-authorisation-model.md`](research/04-polaris-authorisation-model.md), [`docs/research/08-seaweedfs-sts-interop.md`](research/08-seaweedfs-sts-interop.md).*
