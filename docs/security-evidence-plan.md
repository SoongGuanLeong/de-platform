# The security evidence plan: the minimum substrate per deferred test

**Ticket:** [The security model beyond governance](https://github.com/SoongGuanLeong/de-platform/issues/18)
**Model:** [`docs/security-model.md`](security-model.md), section 12
**Purpose:** to execute the deferred security evidence without building the platform. This document identifies the minimum service set each deferred test needs, so that each test runs as a single-component or path-scoped profile rather than a full stack.

## 1. The constraint that shapes this

**There are no Compose services in this repository.** Before this round, `deployment/` held only the certificate target. So the minimum set is not a subset of anything that exists: it is authored here, from the pinned components, for evidence only. It is deliberately not the platform's compose contract, which is the open ticket [The local development architecture: profile budgets, bring-up and the local-versus-cloud diff](https://github.com/SoongGuanLeong/de-platform/issues/25).

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
| Polaris rotation end to end | Polaris, PostgreSQL, SeaweedFS | path-scoped | none, configuration only |
| Polaris successful events audited | Polaris, PostgreSQL, SeaweedFS | path-scoped | none |
| Polaris denial attributable | Polaris, PostgreSQL, SeaweedFS | path-scoped | none |
| Quarantine deletion exercised | Polaris, SeaweedFS, Spark, PostgreSQL | path-scoped | **yes**: a table and a deletion job |
| Cloud secrets through the CSI driver | a cluster and the priced demo window | cloud | **not reachable locally** |

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

*Authored by ticket #18 on map #9. The harness lives in `deployment/compose/` and the tests in `deployment/compose/tests/`. See `deployment/compose/README.md` for how to run them.*
