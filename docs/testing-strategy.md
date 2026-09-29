# The testing strategy

**Ticket:** [The testing strategy: test levels, fixtures, and how a test becomes a behaviour item](https://github.com/SoongGuanLeong/de-platform/issues/23)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Base:** the evidence standard in [`docs/requirements-matrix.md`](requirements-matrix.md) section 3, operationalised by [`docs/completion-bar.md`](completion-bar.md).
**Decision record:** [`docs/adr/0032-the-level-determines-the-strongest-claim-a-test-may-support.md`](adr/0032-the-level-determines-the-strongest-claim-a-test-may-support.md)
**Boundary:** this document fixes the test levels, the fixtures, and which tests run inside CI. The benchmark protocol is [the benchmark plan](benchmark-plan.md); the pipeline job graph, branch protection and the delivery path are [the CI/CD strategy](https://github.com/SoongGuanLeong/de-platform/issues/24).

---

## 0. Status of this document

A standard, not a build. No platform code exists while the map is open, so **no test described here has been written or run**, and none may be claimed to have run. The capability register at [`docs/completion-bar.yaml`](completion-bar.yaml) ships empty, and this document does not fill it.

## 1. What this document is, and what it is not

It fixes four things: the test levels and the strongest claim each may support, the fixtures those tests consume, which tests run in CI and which need a profile, and the rule that turns a passing test into a behaviour item.

It is not a test plan with a named test per claim. The named obligations already exist in the completion bar's class deltas and in the incident laboratory's demoted set; this document places them at a level and a profile. Naming the rest happens in the register, as instances land.

## 2. The four levels, and the strongest claim each may support

| Level | Runs against | Strongest `proves` | May carry a behaviour item |
|---|---|---|---|
| **unit** | the distribution's own code; no container, no network | `signal` | no |
| **contract** | `contracts/` and the Avro schema files; no container | `signal` | no |
| **integration** | one component plus its real dependency, at most two containers, under `smoke` | `signal`, or `behaviour` when a declared boundary condition is present | yes, under that condition |
| **end-to-end** | a full path profile, `batch` or `streaming` | `behaviour` | yes |

**A drill is not a level.** The incident laboratory runs a path profile plus the observability overlay, and it is the only thing that promotes an observability item from signal to behaviour, per [`docs/completion-bar.md`](completion-bar.md) section 5. It is listed separately because it is an incident, not a test.

**Ownership.** Unit owns logic: transform functions, key and content-hash derivation, the watermark and lateness arithmetic, contract parsing, DQ check evaluation. Contract owns the declaration: that the contract and schema files are well-formed and internally consistent. Integration owns one boundary: that a component and its real dependency behave as declared, which is where the vended-credential `AccessDenied` scope test, an Avro rejection by the serializer, and a NULL-to-value `UPDATE` through real Debezium live. End-to-end owns the path claim, which is where M2 and M3's convergence claims are actually made.

**The ceiling is the point.** A unit test can be excellent and still prove only that a mechanism is reachable. Making the ceiling a property of the level rather than of the author's confidence is what stops a green unit suite from being cited as a behaviour item.

## 3. How a test becomes a behaviour item

Three conditions, all required. An evidence item may declare `proves: behaviour` only when:

1. **The real component or components on the path of the claim ran.** A double is not a component (section 5).
2. **A fault or a boundary condition was declared before the run and was present.** The declaration is a budget or a written expectation; the presence is visible in the artifact.
3. **The evidence item's `command` names a test path or a repository script that exists.** CI resolves the reference.

**CI checks condition 3 and nothing else.** It cannot check that the component was real or that the condition was present, so it does not pretend to. The honest limit is recorded rather than papered over: a green CI proves the cited test exists, never that it was the right test. Conditions 1 and 2 are judged by a human from the raw artifact, which is what ADR-0007 already says expensive evidence is for.

**Item 2's falsifiability is demonstrated once per class.** [`docs/completion-bar.md`](completion-bar.md) core item 2 says "Falsifiable: the test fails when the behaviour is removed", which is otherwise an author's assertion. The **representative instance** of each of the eleven classes carries a one-line **mutation note** in its evidence item, naming what was removed and recording that the test failed. Eleven notes, one per class, not one per item. Everything else stays asserted, and the register's `representative` flag is what makes the obligation findable.

## 4. Fixtures

**No fixture bytes are committed to git.** Every fixture is either generated by a pinned script or fetched from a pinned URL, and every evidence item names the generator that produced it. Three reasons: TPC-H is 26 GB at SF100 and cannot be committed; the TPC EULA requires the official tools and the notice; and a committed fixture is a fixture nobody regenerates, so it silently stops matching the generator it came from.

`tests/fixtures.yaml` is the manifest: one entry per fixture, carrying the name, the source, the generator, the checksum, the declared volume and the reduced slice. The generators live in the distribution that owns them, which the existing layout already accommodates: the TPC-C loader in `ingestion/commerce/`, the ONSPD loader in `ingestion/network/`, TPC-H generation in `batch/commerce/`, and the RIPE replay fetcher in `ingestion/network/`. `tests/` holds the manifest rather than a new top-level directory.

### 4.1 Volumes, and the reduction rule

| Source | Declared volume | Correctness slice | Volume-dependent? |
|---|---|---|---|
| TPC-C | W=100, approximately 30M rows, 10 GB in PostgreSQL | W=10, approximately 3M rows, about 1 GB by linear scaling | yes for compaction and layout, no for the four CDC hard cases |
| TPC-H | SF100, 26 GB (documented step-down SF30, 7.6 GB) | SF1, about 0.26 GB by linear scaling from the verified SF100 figure | yes for M5, M6, M7 and M18 |
| RIPE Atlas | a 24-hour capture, capped at 5 GB | a declared N-hour REST replay window | yes for throughput and cardinality, no for correctness |
| ONSPD | two releases, 235 MB each | the same two releases, already small enough | no |

**The reduction rule.** A fixture may be reduced only when the evidence item **labels the reduction** and the claim is **not volume-dependent**. The volume-dependent claims are M5's layout trade-off, M6's file counts and fan-out, M7's serving latency and freshness, M18's cost, and every compaction measurement; those are evidenced only at the declared volume, under `benchmark` or a path profile. The honest answer to "which fixtures cannot be shrunk" is that nothing is unshrinkable and **the claim** is what cannot be shrunk, which is what the rule says. SF1's 0.26 GB and W=10's 1 GB are derived by linear scaling from verified or budgeted figures rather than measured, and are labelled as derived wherever they appear.

**The TPC-C driver has two modes.** The four CDC hard cases (NULL-to-value `UPDATE`, composite-PK `UPDATE`, `DELETE`, out-of-order arrival) must not depend on a random workload happening to produce them, so the driver carries a **scripted deterministic mode** that emits each case on demand, labelled as not a TPC-C workload, alongside the specified transaction mix used for volume evidence. TPC-C has no official loader, so this driver is authored here, which makes its seed and its pinned version part of the fixture rather than an implementation detail.

**RIPE Atlas is replayed, never live, for correctness.** The live stream is at-most-once and nondeterministic, so it can never be a correctness fixture. The REST replay from ADR-0014 is the fixture, and it is the same producer that writes the backfill into the same topic, so the test path and the backfill path are one path. Live ingestion is exercised only under `observability`, as incident 6.

## 5. Test doubles

A double may stand in for a component **off** the path of the claim, never for one on it, and every double is declared in the test. A mocked Kafka cannot evidence a Kafka claim, and this is the specific temptation that produced the prior repository's problem, where the pipeline ran through notebooks and nothing was importable or testable end to end.

## 6. What runs in CI, and what runs under a profile

CI runs the static set plus the one artefact the platform authors, and nothing else. This is [`docs/repository-decomposition.md`](repository-decomposition.md)'s CI consequence, amended by [the CI/CD strategy](ci-cd-strategy.md) section 4, which adds the arm64 image build as the single non-static job; [`docs/local-development.md`](local-development.md) section 9 already states that `tests/<profile>/` is never in CI and that `smoke` stays a one-command local re-run.

| Runs in CI | Needs a profile |
|---|---|
| unit tests, per distribution | `tests/smoke/` container checks |
| contract-file validation (section 7a) | `tests/batch/` |
| the register and budget validators | `tests/streaming/` |
| the cross-path comparison (section 8) | the incident laboratory, under a path profile plus `observability` |
| the structural lints of `#16`, including the compose-subset lint, and the arm64 image build | every benchmark, under `benchmark` |

**One runner, one directory per profile.** `pytest tests/smoke`, `pytest tests/batch` and `pytest tests/streaming` are the commands, so a profile names a command rather than a convention, and the preflight in `deployment/` runs before the suite rather than beside it.

**A correction to the completion bar's smoke row.** [`docs/completion-bar.md`](completion-bar.md) section 8 described `smoke` as "Re-run in CI or on a laptop". The container half is not a CI job, as `#25` and ADR-0031 already settled, so the row now reads as a laptop re-run and this document is the reason.

## 7. The contract tests

The completion bar's sentence "the contract test runs in CI" is true of one half and false of the other, because a test asserting the **live** gold table's schema needs the stack and CI has none. The contract test is therefore two tests.

- **(a) Contract-file validation**, no stack, in CI: the YAML schema, the required fields, the versioning rule, at most two majors coexisting, the `pii_class` requirement from ADR-0017, and that the generated `schema` DQ check matches the contract.
- **(b) Contract conformance**, under `batch` or `streaming`, not CI: column types, nullability, invariants, the persona query ids resolving, and the fan-out grain assertion. This is an integration test at the path level and is capable of carrying `behaviour`.

## 8. Cross-path agreement

Completion bar 6.4 requires a metric computed by Flink and by Spark to agree within a stated tolerance, and the two paths never run together: the batch and streaming peaks are 6976 and 7168 MiB against an enforceable ceiling of 7168 MiB. So the agreement is not one test. Each path writes its artifact under its own profile, both artifacts are committed, and a **third step** reads only the two committed artifacts and asserts the tolerance. That step is a `governance/` validator, which means it runs in CI, which is what makes an otherwise unperformable item performable. The tolerance is a budget in [`docs/budgets.yaml`](budgets.yaml), declared before the comparison.

## 9. Streaming determinism

A streaming test that waits on a clock is a test that will be deleted. Every streaming assertion is on **state, never on timing**: a bounded replay source, a wait on a condition with a declared timeout that is itself a budget, and no sleeps. The assertions are final-state equality, `flink.max-committed-checkpoint-id` unchanged across a replay, lag under its budget, and file counts bounded. This is also what makes the replay fixture in section 4 worth having.

## 10. The demoted scenarios, placed

The incident laboratory's eight demoted scenarios stay in the platform as correctness tests, and this is where each one sits.

| Mission scenario | Level | Profile | Owner |
|---|---|---|---|
| 3. Flink worker failure | end-to-end | streaming | 6.3 |
| 4. Duplicate events | integration plus end-to-end | streaming | 6.3, 6.2 |
| 5. Late-arriving events | end-to-end | streaming | 6.3 |
| 7. Failed Iceberg write | integration | batch or streaming | incident 5's failure mode |
| 9. Upstream schema change | integration plus end-to-end | streaming | 6.2, 6.5 |
| 10. Row-count mismatch | end-to-end | streaming | 6.2 reconciliation, incident 1's correctness link |
| 11. Dagster job failure | end-to-end | batch | 6.7 |
| 13. Corrupt input file | integration plus end-to-end | batch | 6.8 |

## 11. What the prior repository's test absence teaches

Three design inputs, none of them copied, all recorded in the salvage list.

1. **A green badge over lint only is an artifact, not a gate** (asset 20). CI's gate therefore contains at least one check that can fail on something other than style: the per-distribution unit tests, the contract-file validation, and the register and budget validators. The load-bearing evidence stays human-judged from committed artifacts, and that limit is stated rather than implied.
2. **The linter was unpinned** (asset 20). Every toolchain version is pinned, which `#16` already fixed; it is restated here because it is a property of the gate rather than of the layout.
3. **17 notebooks orchestrated the pipeline while `src/` held only silver and gold** (asset 22, boundary rule 5). The testing consequence is that no test may import a notebook and every test targets an importable module. The lesson is that the boundary came second, not that tests were forgotten, which is why the boundary is a check and this document is not.

## 12. What this strategy does not settle, and the honest gaps

- **The benchmark protocol.** The baseline, hypothesis, change and result protocol is [the benchmark plan](benchmark-plan.md). This document says which tests are benchmarks; it does not say how one is recorded.
- **The pipeline job graph, branch protection and the delivery path.** [The CI/CD strategy](https://github.com/SoongGuanLeong/de-platform/issues/24) owns those. This document names which tests run inside CI, not how CI is wired.
- **No test has been written or run.** The register ships empty and nothing here is a result.
- **The fixture volumes are budgets, not measurements.** They come from [`docs/dataset-selection.md`](dataset-selection.md) section 7, which labels every figure an initial budget, and the two slice sizes are derived by scaling rather than measured.
- **The mutation notes are obligations, not results.** Eleven are required and none exists.
- **`tests/fixtures.yaml` is a plan.** No fixture has been generated, and the checksum column is empty by construction.
