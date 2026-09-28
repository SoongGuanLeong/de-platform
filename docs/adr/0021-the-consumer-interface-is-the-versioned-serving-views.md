# The consumer interface is the versioned serving views

**Status:** accepted

The consumer-facing interface is the ClickHouse serving views, versioned by view name, with the Iceberg gold tables named as the second, read-only interface reachable through the catalog. A breaking change is a new `_vN` view with the old one kept and marked deprecated; the persona query ids in the gold contract are the consumer simulation that proves the old view still answers.

## Considered options

- **A documented schema plus a semver string, with no separate artefact.** Rejected: a version string is a promise, a versioned view is a mechanism.
- **A REST or API surface.** Rejected: no requirement names one, and inventing one is surface area without engineering depth.

## Consequences

`contracts/interface.yml` is an index with a policy, carrying the view name, the contract reference, the version and the status, and no per-column detail, so nothing is written twice. Evidence: ticket [Data contracts and schema compatibility policy](https://github.com/SoongGuanLeong/de-platform/issues/15).
