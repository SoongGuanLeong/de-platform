# The security evidence plan: the minimum substrate per deferred test

**Ticket:** [The security model beyond governance](https://github.com/SoongGuanLeong/de-platform/issues/18)
**Model:** [`docs/security-model.md`](security-model.md), section 12
**Purpose:** to execute the deferred security evidence without building the platform. This document identifies the minimum service set each deferred test needs, so that each test runs as a single-component or path-scoped profile rather than a full stack.

## 1. The constraint that shapes this

**Before this round there were no Compose services in this repository.** `deployment/` held only the certificate target, so the minimum set was not a subset of anything that already existed: it was authored here, from the pinned components, for evidence only. It now exists as `deployment/compose/`, and section 6 reports what it produced. It is deliberately not the platform's compose contract, which is the open ticket [The local development architecture: profile budgets, bring-up and the local-versus-cloud diff](https://github.com/SoongGuanLeong/de-platform/issues/25).

What makes a single-component profile legitimate rather than a shortcut is that the profile model is already decided: the completion bar fixes reproducibility per profile (smoke, then the path-scoped halves, then single-component), because the whole stack cannot be co-resident in 7 to 8 GB. Each test below therefore runs the smallest profile that can produce it.

Host budget: 12 CPU, 14 GB RAM with about 8 GB available, 228 GB free disk. One JVM service plus one or two light services fits; the full stack does not.

## 2. The mapping

| Deferred evidence | Minimum services | Profile | Platform code needed |
|---|---|---|---|
| Secrets arrive at `/run/secrets` | PostgreSQL (native `POSTGRES_PASSWORD_FILE`) | single | none |
| `.env.example` covers every variable | none running: a static cross-check against the compose file | none | none |
| Secrets absent from tracked files | none running: `git check-ignore` plus a history scan | none | none |
| Data-plane credentials refused when wrong: PostgreSQL | PostgreSQL | single | none |
| Data-plane credentials refused when wrong: ClickHouse | ClickHouse | single | none |
| Data-plane credentials refused when wrong: Kafka | Kafka | single | none |
| TLS refused when plaintext: PostgreSQL | PostgreSQL | single | none |
| TLS refused when plaintext: ClickHouse | ClickHouse | single | none |
| TLS refused when plaintext: Kafka | Kafka | single | none |
| TLS refused when plaintext: SeaweedFS S3 | SeaweedFS | single | none |
| TLS chain verifiable: Grafana | Grafana | single | none |
| ClickHouse query-log retention bounded | ClickHouse | single | none |
| Kafka denial logged | Kafka | single | none |
| Polaris rotation end to end | Polaris, PostgreSQL | path-scoped | none, configuration only |
| Polaris successful events audited | Polaris, PostgreSQL | path-scoped | none |
| Polaris denial attributable | Polaris, PostgreSQL | path-scoped | none |
| Quarantine deletion exercised | Polaris, SeaweedFS, Spark, PostgreSQL | path-scoped | **yes**: a table and a deletion job |
| Cloud secrets through the CSI driver | a cluster and the priced demo window | cloud | **not reachable locally** |

The three Polaris rows originally named Polaris, PostgreSQL and SeaweedFS. SeaweedFS was dropped once the tests were written: all three assertions are metadata-plane, covering token issue, principal create, rotate and reset, namespace creation and grants, and no assertion reaches object storage. Carrying a component in the evidence path that no assertion touches would overstate what the profile proves. PostgreSQL stays because the successful-event assertion is a SQL read of `POLARIS_SCHEMA.events`.

## 3. What this plan refuses to do

- **No new component.** Every service below is one of the nineteen pinned components. No identity provider, no proxy, no log store, no certificate authority daemon.
- **No architecture change to make a test pass.** If a component cannot do something the model claims, the finding is recorded and the model is corrected, rather than the component being swapped or the test weakened.
- **No platform code**, with one named exception: the quarantine deletion test needs an Iceberg table and a deletion statement, which is a slice of the pipeline. That item is marked above and is not silently absorbed into a harness.
- **No test reported that did not run.** Each result below carries the exact command and its raw output.

## 4. The two items that cannot be produced here

1. **Cloud secrets through the CSI driver.** It needs a Kubernetes cluster. The cloud shape is authored and never applied, and the demo is time-boxed and priced, so this stays deferred and is labelled as such rather than approximated with a local secret store.
2. **Quarantine deletion.** The deletion path is pipeline behaviour on an Iceberg table. Exercising it means writing the table and the deletion statement, which is the implementation this round is explicitly not doing. It stays deferred until the deletion path exists, and the security model already says its deletion path must be exercised rather than assumed.

## 5. The findings this plan expects to produce, and did

Findings are recorded as they are produced, in `docs/security-model.md` section 9 where they are limitations, or as corrections to the model where a claim was wrong. A test that passes without changing anything is still reported, because a green negative test is the evidence.

---

## 6. The results

Every row below was executed against the pinned component images on this host. The numbers are assertion lines from the final run of each script, and every script exits non-zero if any assertion fails. Nothing here is a projection or a plan.

| Deferred evidence | Profile | Test | Result |
|---|---|---|---|
| Secrets arrive at `/run/secrets` | PostgreSQL, ClickHouse, Kafka | `tests/postgres.sh`, `tests/clickhouse.sh`, `tests/kafka.sh` | 11, 19 and 8 assertions pass. Each component reads its password from a file, and each test asserts that no plaintext password variable is present in the environment |
| `.env.example` covers every variable | none | `tests/static.sh` | Passes: every `*_FILE` value points under `/run/secrets` |
| Secrets absent from tracked files | none | `tests/static.sh` | Passes: all 11 secret values were read and found nowhere in the tracked tree, none was skipped as unreadable, and every secret-shaped path is gitignored |
| Credentials refused when wrong: PostgreSQL, ClickHouse, Kafka | each | as above | A wrong password is refused by all three, with the expected refusal message |
| TLS refused when plaintext: PostgreSQL, ClickHouse, Kafka | each | as above | Refused by all three. Kafka additionally asserts the broker's own `SSL handshake failed` line, because a client-side timeout alone does not show why the request failed |
| TLS refused when plaintext: SeaweedFS S3 | SeaweedFS | `tests/seaweedfs.sh` | 11 assertions pass: a signed request returns 200, an unsigned TLS request returns 403, and a plaintext request is refused with the server's own message plus a matching `TLS handshake error` line |
| TLS chain verifiable: Grafana | Grafana | `tests/grafana.sh` | 16 assertions pass: the chain verifies against the local CA with `Verify return code: 0 (ok)`, the served leaf's issuer is that CA, and the same handshake against the system trust store is refused |
| ClickHouse query-log retention bounded | ClickHouse | `tests/clickhouse.sh` | Passes: a TTL is applied, a row dated 60 days back is written, and `optimize ... final` leaves zero rows |
| Kafka denial logged | Kafka | `tests/kafka.sh` | Passes: the denial is refused, and a line naming the principal, the operation and the resource is read back from `kafka-authorizer.log` |
| Polaris rotation end to end | Polaris, PostgreSQL | `tests/polaris.sh` | 28 assertions pass, twice: `/rotate` is two-phase, a root `/reset` refuses the previous secret at once, the new secret works, and the container start time is unchanged |
| Polaris successful events audited | Polaris, PostgreSQL | `tests/polaris.sh` | Passes: an `AFTER_CREATE_NAMESPACE` row naming the principal is read back from `polaris_schema.events` with SQL |
| Polaris denial attributable | Polaris, PostgreSQL | `tests/polaris.sh` | Passes: the 403, the `PolarisAuthorizerImpl` line naming the principal, the operation and the missing privilege, and an unmatched `BEFORE_*` row are all read back |
| Quarantine deletion exercised | none | not run | **Not reachable.** It needs the deletion path, which does not exist. Section 4 |
| Cloud secrets through the CSI driver | none | not run | **Not reachable.** It needs a cluster. Section 4 |

145 assertions ran and passed across the six component profiles and the static check.

### 6.1 What the tests changed

The evidence was not only confirmatory. Each item below was produced by running a test, and each is recorded in `docs/security-model.md` or in ADR-0030 rather than left as a claim.

1. **Kafka's PEM configuration has two mutually exclusive styles.** `ssl.keystore.key` with `ssl.keystore.certificate.chain` takes PEM *content*; `ssl.keystore.location` takes a *path* to one file holding the key and the chain. A path placed in a content slot is parsed as PEM text and fails with `No matching PRIVATE KEY entries in PEM file`, which reads like a corrupt key rather than a misconfiguration.
2. **Enabling `StandardAuthorizer` forces the controller listener to be authenticated.** A plaintext controller listener presents `User:ANONYMOUS`, which is denied `CLUSTER_ACTION` on the broker's own registration, so the broker never becomes active.
3. **Kafka's authorizer denial log is a separate file with no retention bound**: `/opt/kafka/logs/kafka-authorizer.log`, mode 0600, rotated hourly and never deleted, inside the container's writable layer.
4. **SeaweedFS's mini mode starts a plaintext Iceberg REST catalog and Lance namespace server by default.** An unauthenticated catalog inside the object store would let a client resolve table metadata without passing Polaris, routing around the authorisation seam. Both are now disabled, and the unauthenticated surfaces register names the consequence.
5. **`openssl s_client` exits 0 on a failed verification unless `-verify_return_error` is passed**, so a negative TLS test written without it is a failure printed underneath a success exit.
6. **curl 8.18 words a refused connection as `Could not connect to server`, not `Connection refused`**, so a negative test grepping for the latter fails even when the port is correctly closed.
7. **An assertion against a rotating log must not depend on a position in that log.** A line-count marker in the Kafka test failed at an hour boundary while the control it was testing had worked. This one was found by re-running a test that had already passed twice.
8. **Polaris `/rotate` is two-phase.** It retains the previous secret as a secondary that keeps authenticating until the next rotate, so the previous secret is refused only after a second rotate. A root `/reset` refuses it immediately, and that is the path demonstrated end to end.
9. **Polaris leaves an unmatched `BEFORE_*` row for a denied operation**, but the row alone means "attempted and did not complete" rather than "denied", because a 404 leaves one too. The precise denial record is the `PolarisAuthorizerImpl` line naming the principal, the operation and the missing privilege.
10. **The Quarkus access-log default pattern already carries the authenticated principal.** Only *enabling* the log is required, which corrects a premise in ADR-0030.
11. **A Polaris client secret can be human-authored**, through the reset endpoint's optional `clientSecret`. This was proposed as a finding and then falsified by an independent verifier, so it is recorded as a capability rather than as a limitation.
12. **A TLS-terminating container must be given its own leaf and the CA certificate, not the certificate directory**, which is mode 0700 and also holds `ca.key`.
13. **A container running as a non-root user cannot read a root-owned compose secret.** Either the entrypoint starts as root and re-materialises the file, or the host file is remapped with `podman unshare chown`, which makes it unreadable from the host.

---

*Authored by ticket #18 on map #9. The harness lives in `deployment/compose/` and the tests in `deployment/compose/tests/`. See `deployment/compose/README.md` for how to run them.*
