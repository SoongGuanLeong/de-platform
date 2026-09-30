# The level determines the strongest claim a test may support

**Status:** accepted

The completion bar requires every complete capability instance to carry at least one behaviour item, and leaves what counts as behaviour to a definition rather than to a mechanism. A definition alone lets a green unit test be cited as evidence that the platform does the thing, which is the failure mode the bar exists to resist. So the claim ceiling is a property of the test **level**: unit and contract tests prove a signal at most, an integration test proves behaviour only when a declared boundary condition is present, and end-to-end and drill runs are the only ones that may carry a behaviour item without qualification. The alternative, letting the author declare the strength of proof per item, makes the strongest sentence in the bar self-certified.

Three conditions gate a behaviour item: the real components on the path of the claim ran, a fault or boundary condition was declared before the run and was present, and the evidence item's `command` names a test path or repository script that exists. CI resolves the third and cannot check the first two, so the honest limit is recorded rather than implied: a green CI proves the cited test exists, never that it was the right test. Conditions one and two are judged by a human from the raw artifact, which is what [ADR-0007](0007-completion-bar-as-a-gate.md) already says expensive evidence is for.

Two consequences are not obvious. **Fixtures are generated or fetched, never committed**, because a committed fixture is one nobody regenerates and TPC-H at SF100 is 26 GB. And **a fixture may be reduced only when the evidence item labels the reduction and the claim is not volume-dependent**, which is why M5, M6, M7, M18 and every compaction measurement are evidenced only at the declared volume.

## Considered options

- **Leaving behaviour as a definition with no level ceiling.** Rejected: it is what lets a unit suite be cited as proof, and it makes "at least one behaviour item" unfalsifiable in the direction that matters.
- **A per-item self-declaration of proof strength.** Rejected: self-certification of the bar's strongest claim.
- **Requiring a mutation note on every behaviour item.** Rejected: real cost for little gain. One note on each class's representative instance is eleven notes and covers every class.
- **Running the container half of `smoke` in CI.** Rejected: it contradicts the CI scope boundary in `#16` and the profile split in `#25`, and buys nothing a one-command local run does not.
- **Committing fixture bytes.** Rejected: 26 GB for TPC-H, a licence obligation to reproduce the TPC notice alongside the data, and a fixture that would drift from its generator.
- **One test for cross-path agreement.** Rejected as unperformable: the batch and streaming peaks cannot be co-resident against the 7168 MiB ceiling, so the comparison has to read two committed artifacts.
- **Leaving the contract test as a single CI test.** Rejected: a test asserting the live gold table's schema needs the stack, so the sentence was true of one half and false of the other.

## Consequences

The standard lives in [`docs/testing-strategy.md`](../testing-strategy.md). [`docs/completion-bar.md`](../completion-bar.md) is amended in two places: the `smoke` row of section 8 is a laptop re-run rather than a CI job, and section 10's contract test splits into file validation in CI and live conformance under a path profile. [the data contracts](../data-contracts.md) section 4's compatibility table is aligned with the split. `tests/fixtures.yaml` becomes the fixture manifest, with generators in the distributions that own them rather than in a new top-level directory. Two terms join [`CONTEXT.md`](../../CONTEXT.md): **test level** and **fixture**.

The regression guarantee is unaffected: it remains registry compatibility, the gold contracts and the analyst persona queries, and it still covers declared consumers only. What changes is that the contract half of it is now two tests with different homes, and one of them cannot run in CI.
