# Audit what exists, name the attribution mechanism per system, and record what cannot be attributed

**Status:** accepted

The governance document stated that a denied access is "audited in Polaris". That claim is not supported by the pinned version and is corrected. Polaris 1.7.0 has an opt-in event framework whose event types bracket successful operations (catalog, namespace, table, view, policy, principal, role, credential, transaction and others) and which contains no denial or error event; a denial throws before the closing event is emitted. Every listener is commented out in the shipped configuration, so with no listener configured nothing is emitted or persisted at all. A denial is an HTTP 403 plus an application log line, and the access log's default pattern does not include the authenticated principal.

The decision has four parts.

**Correct the claim.** The wording becomes "a denial is refused and attributable, with the attribution mechanism explicitly identified for each system". A denial is attributed by the Polaris access log carrying the authenticated principal, once the access-log pattern is changed to include it; by ClickHouse's query log, which records the querying user; and by Kafka's authorizer log, once an authorizer is configured. Polaris's own structured audit covers successful catalog operations, which are enabled by turning on the event listener that persists to its metastore.

**Enable what exists.** The Polaris event listener persisting successful catalog operations is enabled, so that a grant, role or table change is reconstructable rather than only current-state visible. The Quarkus access-log pattern is set to include the authenticated principal. Kafka's `StandardAuthorizer` is enabled so authorisation denials reach the authorizer log.

**Bound the trails that are unbounded.** ClickHouse's `system.query_log` never deletes by default and is the one native audit trail that records a user, so it gets a declared TTL. Quarantine keeps its 30-day retention. Everything else is assigned a retention in the security model's retention table, and container logs are honestly recorded as bounded by the container's life.

**Name what cannot be attributed.** The audit matrix answers the auditor's questions one at a time, and the answers that are "cannot" stay "cannot".

## Considered options

- **Add a log store so denial records become durable.** Rejected: Loki plus a shipper is two components bought for a retention policy, and it would still not attribute the reads that matter, because a lakehouse read using the vended credential never passes through the catalog.
- **Keep the claim and rely on the access log.** Rejected: it is not what the words said, and the distinction between an HTTP status line and a structured audit event is exactly the distinction a sceptical reviewer would find.
- **Do nothing and leave the gap implicit.** Rejected: the claim was already written into the governance document, the completion bar and the requirements matrix, so silence would have preserved a false statement in three places.
- **Attribute lakehouse reads by putting a proxy in front of object storage.** Rejected: it would add a component into the data path of the whole platform to answer one audit question, and it would not cover engines reading directly from storage with a vended credential.

## Consequences

The auditability boundary is now the same boundary as the authorisation seam, and that is the point: because Polaris authorises metadata and vends a prefix-scoped storage credential, a read that uses the credential does not pass through the catalog, so the catalog cannot attribute it to a user. This is a structural property of the architecture rather than a configuration gap that more logging would close, and it is recorded as the platform's most significant audit limitation.

Two further limits follow from the components rather than from this decision. The OpenLineage specification has no user or author field, so Marquez lineage records what ran and never who ran it. Grafana's audit log is an Enterprise and Cloud feature, so Grafana configuration changes are not audited in the OSS edition.

The audit matrix, the retention table, the cannot-list and the evidence plan are in [`docs/security-model.md`](../security-model.md).

## Correction, 2026-09-29 (ticket #18)

Two factual premises in this record were checked against the running components while the runtime evidence was produced, and both are wrong. The decision is unaffected; the prerequisites change.

- **"The access log's default pattern does not include the authenticated principal."** Wrong for Quarkus 3.37.4. `AccessLogConfig` defaults `pattern` to `common`, and `AccessLogHandler` maps `common` to `%h %l %u %t "%r" %s %b`, which contains `%u`, the authenticated principal. What is required is to **enable** the access log, since `quarkus.http.access-log.enabled` defaults to `false`; the pattern does not need changing, and the explicit pattern this harness sets is a no-op. The attribution mechanism is unchanged, but the prerequisite becomes "enable the log" rather than "change the pattern".
- **"The framework brackets successful operations only."** Wrong. The framework emits `BEFORE_*` unconditionally for every operation it brackets and `AFTER_*` only on success, so a denied operation leaves an **unmatched `BEFORE_*` row** carrying the authenticated principal and the request, with no closing event. What remains true is that there is no denial event *type*, and that an unmatched `BEFORE_*` row means "attempted and did not complete" rather than specifically "denied", because a 404 leaves one too. A 403 line is therefore still what makes a row a denial.

A third record was found and is now named in the audit matrix: `PolarisAuthorizerImpl` logs `Authorization denied for principal '<principal>' on operation '<OPERATION>': missing <PRIVILEGE> on <RESOURCE>`, naming the principal, the operation and the missing privilege in one line. That is the most precise denial record Polaris emits.
