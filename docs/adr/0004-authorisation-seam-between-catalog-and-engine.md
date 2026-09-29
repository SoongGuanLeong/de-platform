# Enforce access control in two systems and document the seam, not in the catalog alone

**Status:** accepted

Access control is enforced by two independent systems with the seam between them written down: Polaris governs Iceberg-native access and vends a per-table, prefix-scoped storage credential, while ClickHouse users, roles and row policies govern the materialised serving copy. The earlier draft claimed a single catalog control that could not be bypassed through the serving layer, which is not true of a catalog: authorising a catalog authorises metadata, not bytes, and a reader holding a credential opens files directly from object storage without asking the catalog again. Polaris in particular has no column-level or row-level enforcement at all, so column-level control exists only in ClickHouse.

## Considered options

- **Claim the catalog control is not bypassable.** Rejected: false. One broad storage credential configured inside ClickHouse defeats it, and Polaris's own threat model disclaims stronger delegated-credential isolation than the storage provider supports.
- **Enforce everything in ClickHouse and treat Polaris as decorative.** Rejected: it discards the prefix-scoped credential, which is a real data-layer boundary and the reason the seam can be narrow at all.
- **Wait for Polaris column-level support.** Rejected: the feature request has been open since 2024 and the only implementation attempt is unmerged.

## Consequences

The vended credential is a prefix boundary, not a table identity, so overlapping or nested table locations widen it, and the generated session policy is capped at 2048 bytes. Evidence therefore asserts the credential's scope by measurement (vend for table A, prove a read of table B's prefix is refused, with the unscoped baseline recorded) and asserts the policy size. Column-level tests are ClickHouse-only. Matrix rows M10 and M20. The seam has an auditability consequence that this ADR records but does not solve: because the vended credential is a prefix-scoped storage credential, a read that uses it does not pass through the catalog, so the catalog cannot attribute it to a user. What can and cannot be attributed is settled in [`docs/security-model.md`](../security-model.md) and ADR-0030.
