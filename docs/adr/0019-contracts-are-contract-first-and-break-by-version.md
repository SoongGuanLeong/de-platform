# Contracts are contract-first and break by version

**Status:** accepted

Each gold table carries one machine-readable YAML contract at `contracts/<spine>/<table>.yml`, authored with the table, and it is the interface the producer must satisfy rather than a description of the table. A breaking change (drop, rename, narrow, optional-to-required, grain change, key change) is never made in place: it lands as a new major contract version, at most two majors coexist, and a deprecated major is retained until the next breaking version supersedes it. CI hard-fails a breaking change unless the same commit bumps the major.

## Considered options

- **Additive-only forever.** Rejected: it cannot express a genuine correction, and M17's matrix needs a drop to be demonstrable.
- **A new table per break, such as `_v2`.** Rejected: it multiplies tables for a platform whose consumer set is declared and tiny.
- **A calendar deprecation window.** Rejected: the platform has no release cadence, so a date would be a guess wearing a policy's clothes. The window is a count.

## Consequences

The CI guard is the prior repository's additive-only check rewritten under [ADR-0006](0006-reference-only-reuse-and-provenance.md), not copied, and extended with the version-bump escape. The `schema` DQ check is generated from the contract, so the column list is written once. Evidence: ticket [Data contracts and schema compatibility policy](https://github.com/SoongGuanLeong/de-platform/issues/15).
