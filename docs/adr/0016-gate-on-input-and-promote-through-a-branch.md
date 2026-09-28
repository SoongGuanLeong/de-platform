# Gate on the input, and promote output through an Iceberg branch

**Status:** accepted

A failed data-quality check must not publish its output, so the gate is placed by where the check can be evaluated rather than by attaching every check to the asset it judges. A check evaluable on the input is placed on the **upstream** asset, so a fail means the downstream asset never writes and no publish problem exists. A check evaluable only on the output writes to an **Iceberg branch**, is checked there, and fast-forwards `main` only on pass; on fail the branch is discarded and `main` is unchanged. A blocking `@asset_check` stops downstream materialisation but does not stop the failing asset's own write, so blocking alone does not satisfy the severity contract.

## Considered options

- **Blocking asset check on the producing asset, output already written.** Rejected: it blocks downstream assets but leaves the failing output published, which contradicts the `fail` action.
- **Branch and promote for every check.** Rejected: correct but more expensive than needed, since most checks are evaluable on the input and can simply gate the downstream asset.
- **Staging table plus rename.** Rejected in favour of the branch: both are atomic, but the branch is Iceberg-native and exercises the branch and rollback semantics M17 already requires.

## Consequences

The streaming path has no Dagster run to stop, so `fail` becomes a dead-letter sink plus a Dagster sensor that takes a savepoint and stops the Flink job when a breach persists past a declared window. A promote step now sits on every gated output asset, and the gate boundary is the layer edge. Evidence: ticket [Governance and data-quality specifics](https://github.com/SoongGuanLeong/de-platform/issues/14).
