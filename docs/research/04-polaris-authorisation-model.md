# 04 - Polaris authorisation model and credential vending: what the catalog actually governs, and what it hands back

**Date of research:** 2026-09-27. All evidence accessed 2026-09-27 unless stated.
**Scope:** Apache Polaris 1.7.0 (the current release) as the Iceberg REST catalog in a vendor-neutral lakehouse, with particular attention to what authorisation covers and what the credential-vending path returns.
**Question answered:** In the current release of Apache Polaris, what does the authorisation model actually govern, and what does credential vending actually return?

---

## 1. Version read, and how the evidence was gathered

| Fact | Value | Source |
|---|---|---|
| Latest release at 2026-09-27 | **Apache Polaris 1.7.0**, tag `apache-polaris-1.7.0`, published **2026-08-02T05:02:20Z** | GitHub REST API `repos/apache/polaris/releases/latest` [S1] |
| Version file at that tag | `1.7.0` | `version.txt` [S1] |
| Next version | `apache-polaris-1.8.0-rc2` exists as a **tag only**, no release object. Not a release. | GitHub tags API [S1] |
| Docs location in-repo | The repo-root `docs` is a symlink (mode `120000`) to `site/content/in-dev/unreleased/`. The docs pages read below are therefore the pages shipped at the 1.7.0 tag. | GitHub contents API + `git/trees` [S1] |

Everything below is read from the `apache-polaris-1.7.0` tag of `github.com/apache/polaris`, the `apache-iceberg-1.11.0` tag of `github.com/apache/iceberg` (the current Iceberg release, published 2026-05-20), and the project's own issue tracker. Where I read the Iceberg `main` branch I say so. The published docs site mirrors the in-repo pages and was used only to confirm the pages are live [S22].

**A note on the phrase "metadata plane".** I use it to mean: Polaris authorises *catalog operations on catalog objects* (create/drop/list/read-properties/read-data-credential for a catalog, namespace, table, view, policy, principal, role). Polaris is not in the query path and never sees the rows or columns a client reads. Section 5 shows exactly where that boundary sits.

**Version sensitivity, and a warning about downstream guides.** Every claim in this report is pinned at tag `apache-polaris-1.7.0`. The privilege enumeration, the credential-vending response shape, and the storage-scope behaviour have all changed across Polaris releases and will change again, so re-verify against whatever version is actually deployed rather than trusting this file. This matters because at least one first-party integration guide lags badly: ClickHouse's own Polaris catalog guide, last modified 2026-07-25, links **Apache Polaris 1.1.0** (`https://polaris.apache.org/releases/1.1.0/getting-started/using-polaris/#setup`) and configures `DataLakeCatalog` with `catalog_type='rest'`, `storage_endpoint`, and `catalog_credential`, without mentioning `X-Iceberg-Access-Delegation` or `vended_credentials` [S26]. That guide is a **secondary source for Polaris** and describes a catalog six minor releases behind the one documented here; do not use it to infer Polaris 1.7.0 behaviour. Pin the deployed Polaris version before drawing conclusions from any integration guide.

---

## 2. (a) Column-level access control: absent. Authorisation is metadata-plane only.

**Verdict: Polaris 1.7.0 has no column-level access control, and no row-level access control. Authorisation is confined to the metadata plane.**

The evidence is three independent primary sources that agree:

**2.1 The securable-object list is entity-level.** The access-control page states: "A securable object is an object to which access can be granted. Polaris has the following securable objects: Catalog, Namespace, Iceberg table, View, Policy." [S3] There is no column, row, field, tag, or data-classification securable.

**2.2 The privilege enumeration has no column or row privilege.** The built-in RBAC authorizer enumerates **102 privileges** in `PolarisPrivilege` [S2]. Every one of them is bound to a `PolarisEntityType` securable (`ROOT`, `CATALOG`, `NAMESPACE`, `TABLE_LIKE`, `PRINCIPAL`, `PRINCIPAL_ROLE`, `CATALOG_ROLE`, `POLICY`) and, where relevant, an entity subtype (`ICEBERG_TABLE`, `GENERIC_TABLE`, `ICEBERG_VIEW`). There is no privilege whose securable is a column, and no privilege name containing `COLUMN` or `ROW`. The class Javadoc is explicit that "a *securable* is a Polaris entity (such as a catalog, namespace, table, or policy) on which access may be controlled by granting privileges to a grantee" [S2].

**2.3 The data-access privilege is all-or-nothing per table.** The only privileges that grant access to actual data are `TABLE_READ_DATA` ("Enables reading data from the table by receiving short-lived read-only storage credentials") and `TABLE_WRITE_DATA` ("Enables writing data to the table by receiving short-lived read+write storage credentials") [S3, S2]. Both are table-scoped. There is no projection, predicate, or filter attached to either.

**2.4 The project's own issue tracker confirms this is a missing feature, not an undocumented one.** Issue **#137, "[FEATURE REQUEST] Add Row Level and Column Level access control"**, was opened **2024-08-10**, is still **open**, last updated **2026-01-13**, labelled `enhancement` and `proposal`. Its body asks exactly the question: "Is there a way to define row/column level access control through the RBAC defined here?" and requests "data masking to certain columns for a given Role" [S16].

**2.5 A proposed implementation exists but is not merged and is not server-side enforcement.** PR **#2048, "Part 1 : Adds RLS and CLS control Policies"** was opened **2025-07-14**, is still **open**, `merged: false`, last updated **2026-09-24** [S17]. It proposes expressing row filters and column projections as Iceberg expressions inside Polaris *policies*, with `$current_principal` and `$current_principal_role` context variables resolved at the catalog. Crucially, the PR body says it "is for engines who wants to get the policies directly! rather than getting the secu[re]..." [S17]. In other words, even the proposed design returns a policy to the engine for the engine to apply; the catalog does not filter rows or mask columns itself.

**2.6 Polaris's policies in 1.7.0 are lifecycle policies, not security policies.** The policy framework supports four predefined system types: `system.data-compaction`, `system.metadata-compaction`, `system.orphan-file-removal`, `system.snapshot-expiry`. The doc says "Support for additional predefined system policy types and custom policy type definitions is in progress." [S18] None of the four is a security or masking policy.

**2.7 The Iceberg REST protocol has a row/column restriction mechanism, and Polaris 1.7.0 does not implement it.** Iceberg's `main` branch REST spec defines `ReadRestrictions` with `required-column-projections` (by field-id, with actions such as `show-last-4`) and `required-row-filter`, and says a reader that cannot apply a restriction "must fail the query and must not silently return raw, partial, or empty results" [S23]. Polaris 1.7.0's vendored copy of the same spec, `spec/iceberg-rest-catalog-open-api.yaml`, contains **no** occurrence of `ReadRestrictions`, `required-row-filter`, or `required-column-projections` [S4]. The released Iceberg 1.11.0 spec does not have them either; they are newer than 1.11.0 [S11, S23].

**Inference (labelled):** an external PDP such as OPA, which Polaris supports [S3], also cannot enforce column-level policy from catalog traffic, because a catalog operation carries no column or predicate context. OPA would see a `loadTable` or `updateTable` operation, not a query. This is my inference from the operation-level authorizer interface described in [S2], not a statement in the docs.

---

## 3. (b) The full privilege set, and its granularity

### 3.1 Roles

Two role types, plus principals:

- **Principal role**: realm-scoped, used to group principals and to carry catalog roles. Many-to-many with principals and with catalog roles. Privileges are *not* granted directly to principal roles [S3].
- **Catalog role**: belongs to exactly one catalog, holds the privileges on that catalog and the objects inside it. Many-to-many with principal roles [S3].
- **Principal**: the identity (service principal or user) that is granted principal roles [S3].

The grant chain is: **privilege -> catalog role -> principal role -> principal** [S3]. A `PRINCIPAL_ROLE_USAGE` privilege (code 4) governs the principal-role-to-principal link, and `CATALOG_ROLE_USAGE` (code 3) governs the catalog-role-to-principal-role link [S2].

### 3.2 The 102 privileges, by securable

Authoritative source: `polaris-core/src/main/java/org/apache/polaris/core/entity/PolarisPrivilege.java`, enum `PolarisPrivilege`, codes 1 to 102 contiguous [S2]. The doc page [S3] documents the table, view, namespace, catalog and policy privileges in prose; the enum is the complete machine-readable set and includes more (principal, role, grant-management, and the per-metadata-operation table privileges).

**Root securable (7):** `SERVICE_MANAGE_ACCESS` (1), `CATALOG_CREATE` (25), `CATALOG_LIST` (27), `PRINCIPAL_CREATE` (44), `PRINCIPAL_LIST` (46), `PRINCIPAL_ROLE_CREATE` (54), `PRINCIPAL_ROLE_LIST` (56).

**Catalog securable (13):** `CATALOG_MANAGE_ACCESS` (2), `CATALOG_DROP` (26), `CATALOG_READ_PROPERTIES` (28), `CATALOG_WRITE_PROPERTIES` (29), `CATALOG_FULL_METADATA` (30), `CATALOG_MANAGE_METADATA` (31), `CATALOG_MANAGE_CONTENT` (32), `CATALOG_LIST_GRANTS` (36), `CATALOG_MANAGE_GRANTS_ON_SECURABLE` (40), `CATALOG_ROLE_CREATE` (62), `CATALOG_ROLE_LIST` (64), `CATALOG_ATTACH_POLICY` (78), `CATALOG_DETACH_POLICY` (81).

**Namespace securable (16):** `NAMESPACE_CREATE` (5), `TABLE_CREATE` (6), `VIEW_CREATE` (7), `NAMESPACE_DROP` (8), `NAMESPACE_LIST` (11), `TABLE_LIST` (12), `VIEW_LIST` (13), `NAMESPACE_READ_PROPERTIES` (14), `NAMESPACE_WRITE_PROPERTIES` (17), `NAMESPACE_FULL_METADATA` (22), `NAMESPACE_LIST_GRANTS` (37), `NAMESPACE_MANAGE_GRANTS_ON_SECURABLE` (41), `POLICY_CREATE` (70), `POLICY_LIST` (74), `NAMESPACE_ATTACH_POLICY` (79), `NAMESPACE_DETACH_POLICY` (82).

**Table-like securable, subtypes `ICEBERG_TABLE` and `GENERIC_TABLE` (37):** `TABLE_DROP` (9), `TABLE_READ_PROPERTIES` (15), `TABLE_WRITE_PROPERTIES` (18), `TABLE_READ_DATA` (20), `TABLE_WRITE_DATA` (21), `TABLE_FULL_METADATA` (23), `TABLE_LIST_GRANTS` (38), `TABLE_MANAGE_GRANTS_ON_SECURABLE` (42), `TABLE_ATTACH_POLICY` (80), `TABLE_DETACH_POLICY` (83), `TABLE_ASSIGN_UUID` (85), `TABLE_UPGRADE_FORMAT_VERSION` (86), `TABLE_ADD_SCHEMA` (87), `TABLE_SET_CURRENT_SCHEMA` (88), `TABLE_ADD_PARTITION_SPEC` (89), `TABLE_ADD_SORT_ORDER` (90), `TABLE_SET_DEFAULT_SORT_ORDER` (91), `TABLE_ADD_SNAPSHOT` (92), `TABLE_SET_SNAPSHOT_REF` (93), `TABLE_REMOVE_SNAPSHOTS` (94), `TABLE_REMOVE_SNAPSHOT_REF` (95), `TABLE_SET_LOCATION` (96), `TABLE_SET_PROPERTIES` (97), `TABLE_REMOVE_PROPERTIES` (98), `TABLE_SET_STATISTICS` (99), `TABLE_REMOVE_STATISTICS` (100), `TABLE_REMOVE_PARTITION_SPECS` (101), `TABLE_MANAGE_STRUCTURE` (102). The remaining nine table-like privileges are the view ones below, which share the `TABLE_LIKE` securable with subtype `ICEBERG_VIEW`.

**View securable, subtype `ICEBERG_VIEW` (9):** `VIEW_DROP` (10), `VIEW_READ_PROPERTIES` (16), `VIEW_WRITE_PROPERTIES` (19), `VIEW_FULL_METADATA` (24), `VIEW_LIST_GRANTS` (39), `VIEW_MANAGE_GRANTS_ON_SECURABLE` (43). Note the view privileges are `TABLE_LIKE` securables; the enum models "table-like" as one securable type with table and view subtypes [S2].

**Policy securable (7):** `POLICY_READ` (71), `POLICY_DROP` (72), `POLICY_WRITE` (73), `POLICY_FULL_METADATA` (75), `POLICY_ATTACH` (76), `POLICY_DETACH` (77), `POLICY_MANAGE_GRANTS_ON_SECURABLE` (84).

**Principal securable (11):** `PRINCIPAL_DROP` (45), `PRINCIPAL_READ_PROPERTIES` (47), `PRINCIPAL_WRITE_PROPERTIES` (48), `PRINCIPAL_FULL_METADATA` (49), `PRINCIPAL_MANAGE_GRANTS_ON_SECURABLE` (50), `PRINCIPAL_MANAGE_GRANTS_FOR_GRANTEE` (51), `PRINCIPAL_ROTATE_CREDENTIALS` (52), `PRINCIPAL_RESET_CREDENTIALS` (53), `PRINCIPAL_LIST_GRANTS` (33), `PRINCIPAL_ROLE_LIST_GRANTS` (34), `CATALOG_ROLE_LIST_GRANTS` (35).

**Principal-role securable (7):** `PRINCIPAL_ROLE_USAGE` (4), `PRINCIPAL_ROLE_DROP` (55), `PRINCIPAL_ROLE_READ_PROPERTIES` (57), `PRINCIPAL_ROLE_WRITE_PROPERTIES` (58), `PRINCIPAL_ROLE_FULL_METADATA` (59), `PRINCIPAL_ROLE_MANAGE_GRANTS_ON_SECURABLE` (60), `PRINCIPAL_ROLE_MANAGE_GRANTS_FOR_GRANTEE` (61).

**Catalog-role securable (7):** `CATALOG_ROLE_USAGE` (3), `CATALOG_ROLE_DROP` (63), `CATALOG_ROLE_READ_PROPERTIES` (65), `CATALOG_ROLE_WRITE_PROPERTIES` (66), `CATALOG_ROLE_FULL_METADATA` (67), `CATALOG_ROLE_MANAGE_GRANTS_ON_SECURABLE` (68), `CATALOG_ROLE_MANAGE_GRANTS_FOR_GRANTEE` (69).

(Counts overlap where a privilege is listed under both a broad securable and a subtype; the authoritative count is 102 enum constants, codes 1 to 102 [S2].)

### 3.3 Granularity

- **Object granularity**: entity level only (catalog, namespace, table, view, policy, principal, role). No sub-object granularity. Data access is per table via `TABLE_READ_DATA` / `TABLE_WRITE_DATA`.
- **Aggregation**: `TABLE_FULL_METADATA`, `VIEW_FULL_METADATA`, `NAMESPACE_FULL_METADATA`, `CATALOG_MANAGE_METADATA`, `CATALOG_MANAGE_CONTENT` aggregate other privileges. Notably `TABLE_FULL_METADATA` "Grants all table privileges, except TABLE_READ_DATA and TABLE_WRITE_DATA, which need to be granted individually" [S3]. This is a deliberate separation of metadata rights from data rights.
- **Fine-grained metadata operations**: Polaris 1.7.0 also exposes 18 per-update table privileges (`TABLE_ADD_SCHEMA`, `TABLE_ADD_SNAPSHOT`, `TABLE_SET_LOCATION`, `TABLE_MANAGE_STRUCTURE`, and so on, codes 85 to 102) [S2]. These are finer than the doc tables in [S3] suggest, but they are still *table-scoped metadata operations*, not column-scoped.
- **External PDP alternative**: the enum Javadoc notes that "Alternative authorizer implementations such as the OPA-based authorizer may not use these privileges. They operate at the `PolarisAuthorizableOperation` level and delegate all privilege/permission logic to external PDPs." [S2] So OPA can replace the privilege model but still receives operation-level inputs.

---

## 4. (c) What the credential-vending endpoint returns

### 4.1 The two endpoints

There are two ways credentials leave Polaris, and they share one implementation path.

1. **Dedicated endpoint.** `GET /v1/{prefix}/namespaces/{namespace}/tables/{table}/credentials`, `operationId: loadCredentials`, defined identically in Polaris 1.7.0's vendored spec and in the released Iceberg 1.11.0 spec [S4, S11]. The `{prefix}` path parameter is the **catalog prefix**, described in the spec as "An optional prefix in the path"; it is *not* the storage prefix returned in the credential [S4]. The endpoint is implemented in `IcebergCatalogAdapter.loadCredentials`, which builds a refresh endpoint and calls `IcebergCatalogHandler.loadCredentials` [S20, S5].
2. **Inline on table/view load, create and update.** The header `X-Iceberg-Access-Delegation` carries a comma-separated list from the enum `vended-credentials`, `remote-signing` [S4, S11]. When a client sends `vended-credentials` on `loadTable`, `loadView`, `createTable` or `updateTable`, Polaris attaches the credential to the normal response [S20, S5].

**Of the two protocol delegation modes, Polaris 1.7.0 implements only one.** The enum allows `vended-credentials` and `remote-signing` [S4, S11], but `IcebergCatalogHandler.resolveAccessDelegationModes` rejects a resolved `REMOTE_SIGNING` mode outright: `Preconditions.checkArgument(resolvedMode.orElse(null) != AccessDelegationMode.REMOTE_SIGNING, "Unsupported access delegation mode: %s", ...)`, under a `TODO remove when remote signing is implemented` comment [S5]. Remote signing is therefore not a middle ground: a client that requests it (or resolves to it) gets an error, and the only working delegated-access mode in 1.7.0 is `vended-credentials`.

### 4.2 The response object, and what "prefix" means

The response schema is `LoadCredentialsResponse { storage-credentials: [StorageCredential] }`, where `StorageCredential` is `{ prefix: string, config: map<string,string> }` [S4, S11]. The spec describes `prefix` as: "Indicates a storage location prefix where the credential is relevant. Clients should choose the most specific prefix (by selecting the longest prefix) if several credentials of the same type are available." [S4, S11]

Polaris's implementation sets that prefix to the **table's own location**:

- On the `loadCredentials` path: `ImmutableCredential.builder().prefix(baseLocation).config(credentialConfig)`, where `baseLocation` is the table entity's `location` internal property [S5].
- On the `loadTable` path: `ImmutableCredential.builder().prefix(tableMetadata.location()).config(credentialConfig)` [S5].

So the object the credential is scoped to is **one table**, identified by its storage location prefix. It is not scoped to the whole warehouse and not to the namespace. (Section 5 covers the case where a table's location is itself a broad prefix.)

### 4.3 What kind of credential, per storage type

Polaris is a delegating credential vendor. It does not hand out its own long-lived keys; it asks the cloud provider for a short-lived, scoped credential.

| Storage | Credential kind | Returned property names | Scoped to | Source |
|---|---|---|---|---|
| AWS S3 | **STS `AssumeRole` temporary session credentials** plus an **inline IAM session policy** | `s3.access-key-id`, `s3.secret-access-key`, `s3.session-token`, `s3.session-token-expires-at-ms`, `client.region`, `s3.endpoint`, `s3.path-style-access` | the specific table locations and operations (read, list, write) | [S6, S9, S19] |
| Azure ADLS / Blob | **User Delegation SAS token** (user delegation key, not the account key) | `adls.sas-token`, `adls.sas-token.<account-host>`, `adls.sas-token.<account-name>`, `adls.account-name` | the container and path prefix the caller is authorised to access | [S15, S9, S19] |
| Google Cloud Storage | **Downscoped OAuth2 access token** via Google's Credential Access Boundary | `gcs.oauth2.token`, `gcs.oauth2.token-expires-at` | the specific buckets and path prefixes | [S9, S19] |

All three forms are documented on the vended-credentials page [S9]. For AWS the implementation is `AwsCredentialsStorageIntegration.compute`, which calls `StsClient.assumeRole` with `roleArn`, `externalId`, `roleSessionName`, `policy` (the inline session policy), `durationSeconds`, and optional session tags [S6].

### 4.4 The AWS session policy, in detail

`AwsCredentialsStorageIntegration.policyString` builds the inline policy from three sets of locations derived from the table: `readLocations`, `listLocations`, `writeLocations` [S6].

- **read**: `s3:GetObject`, `s3:GetObjectVersion` on `arn:<partition>:s3:::<bucket>/<path>/*`
- **list**: `s3:ListBucket` on the bucket, with a `StringLike` condition on `s3:prefix` = `<path>/*`
- **write**: `s3:PutObject`, `s3:DeleteObject` on `arn:<partition>:s3:::<bucket>/<path>/*`
- **all three**: `s3:GetBucketLocation` on each bucket
- **KMS** (when configured): `kms:DescribeKey`, `kms:Decrypt`, and for writes `kms:Encrypt`, `kms:GenerateDataKey`, `kms:GenerateDataKeyWithoutPlaintext` on the configured key ARNs (or `arn:aws:kms:<region>:<account>:key/*` for read-only AWS S3 with no specific key configured)

Two defensive details worth recording. First, the code escapes IAM glob metacharacters (`*`, `?`, `$`) in caller-controlled paths so they stay literal [S6]. Second, if the resulting policy would have no statements, the code emits an explicit `Deny *` rather than an empty policy, with the comment: "Avoid sending an empty policy to STS, which would cause the assumed role to fall back to its full privileges." [S6] This is a deliberate guard against a known STS behaviour.

The **locations** in that policy are computed by `StorageUtil.getLocationsUsedByTable`: the table's base location, plus the values of the Iceberg properties `write.data.path` and `write.metadata.path`, with nested locations collapsed to their parent by `removeRedundantLocations` ("so {/a/b/, /a/b/c, /a/b/d} will be reduced to just {/a/b/}") [S12]. This is important for section 5: the scope is a set of **storage prefixes**, not a set of table file identities.

### 4.5 Lifetime

| Setting | Default | Notes | Source |
|---|---|---|---|
| `STORAGE_CREDENTIAL_DURATION_SECONDS` | **3600** (1 hour) | "The duration of time that vended storage credentials are valid for. Support for longer (or shorter) durations is dependent on the storage provider. GCS current does not respect this value." | [S8] |
| `STORAGE_CREDENTIAL_CACHE_DURATION_SECONDS` | **1800** (30 minutes) | Server-side credential cache lifetime; must be less than the credential duration | [S8] |
| Azure cap | min(configured duration, 7 days minus 60 s) | Azure strictly requires the user-delegation-key end time to be at most 7 days out; Polaris subtracts 60 s for clock skew | [S15] |
| GCS | ignores `STORAGE_CREDENTIAL_DURATION_SECONDS` | Stated in the config description | [S8] |

### 4.6 Session name and session tags

- **Session name**: configurable via `SESSION_NAME_FIELDS_IN_SUBSCOPED_CREDENTIAL` (supported fields: realm, catalog, namespace, table, principal), default prefix `p-`, truncated to the AWS 64-character limit. When unset, it falls back to `INCLUDE_PRINCIPAL_NAME_IN_SUBSCOPED_CREDENTIAL` (default false), which yields `polaris-<principal>`; the fallback default is `PolarisAwsCredentialsStorageIntegration` [S6, S8].
- **Session tags**: configurable via `SESSION_TAGS_IN_SUBSCOPED_CREDENTIAL` (supported fields: `realm`, `catalog`, `namespace`, `table`, `principal`, `roles`, `trace_id`), **default empty**. The config description states their purpose plainly: "These tags appear in CloudTrail events, enabling correlation between catalog operations and S3 data access." [S7, S8] The code marks them transitive for role chaining [S6]. They are an **audit/correlation** mechanism, not a policy condition. Polaris does not use the tags to constrain the session.

### 4.7 The authorisation gate before vending

`loadCredentials` calls `authorizeLoadTable(tableIdentifier, true)` [S5]. That method resolves the table and then tries `LOAD_TABLE_WITH_WRITE_DELEGATION` first; if that throws `ForbiddenException` it falls back to `LOAD_TABLE_WITH_READ_DELEGATION`. The returned action set starts as `{READ, LIST}` and gains `WRITE` only if the write-delegation check passes [S5]. The underlying privileges are `TABLE_WRITE_DATA` and `TABLE_READ_DATA` respectively [S3].

Before vending on the `loadTable` path, `validateTableLocations` re-validates the table's locations against the catalog's **current** `allowedLocations`: "This protects against cases where allowedLocations were tightened after the table was created." [S5] `CatalogUtils.validateLocationsForTableLike` performs the check [S14], delegating to `LocationRestrictions.validate`, which validates against the catalog-level `allowedLocations` (and, if configured, a structured `parentLocation` under which new tables must be created) [S13].

### 4.8 Credential refresh

When the client requests vended credentials, Polaris also returns a credential-refresh endpoint URL per storage type. Iceberg clients that support the refresh protocol can call it to obtain fresh credentials before expiry without reloading the table [S9]. `IcebergCatalogAdapter.loadCredentials` constructs that endpoint as `PolarisResourcePaths(...).credentialsPath(tableIdentifier)`, i.e. the same `/credentials` path [S20].

---

## 5. (d) Once the credential is vended, what constrains it at the storage layer?

**The short answer:** the only Polaris-imposed constraint on a vended credential is the provider-side scope described in section 4 (the STS session policy, the SAS path scope, or the GCS access boundary). That scope is expressed as **storage location prefixes**, not as a table identity or a file set. After vending, Polaris is not in the data path and has no further control over the credential. Whether a client can reach a *different* table's files therefore reduces to: is that other table's data under a prefix the vended credential covers?

### 5.1 The normal case: sibling tables are not reachable

Table locations in Iceberg are per-table directories. If table A is at `s3://bucket/warehouse/ns/table_a` and table B at `s3://bucket/warehouse/ns/table_b`, the credential for A carries a session policy for `s3://bucket/warehouse/ns/table_a/*`. B's files are outside that prefix, so the credential cannot read them. This is the intended design and it is the common case.

### 5.2 The gap: the scope is a prefix, not the table's file set

Polaris never checks that the files under the vended prefix belong to the authorised table. It cannot: the credential is minted before the client reads anything, from the table's *declared* locations. Three concrete ways the prefix can be broader than the authorised table:

**(i) Overlapping or nested table locations.** `StorageUtil.getLocationsUsedByTable` collapses a nested location to its parent: "{/a/b/, /a/b/c, /a/b/d} will be reduced to just {/a/b/}" [S12]. So if one table's base location is a parent of another's, or if two tables share a prefix, a credential for the narrower table is widened to the parent and reaches the other table's files. Polaris's threat model acknowledges this class directly (section 6).

**(ii) A writer can choose a broad location, then vend against it. (Inference.)** A principal that holds `TABLE_WRITE_DATA` on a table, and can therefore set the Iceberg `write.data.path` or `write.metadata.path` properties (`TABLE_SET_PROPERTIES`, code 97, or `TABLE_SET_LOCATION`, code 96 [S2]), can point those properties at a prefix that contains another table's files, provided the prefix is inside the catalog's `allowedLocations`. `getLocationsUsedByTable` will include that prefix [S12], the session policy will be built over it [S6], and `validateTableLocations` will pass because it only checks against the catalog's `allowedLocations`, not against other tables' locations [S5, S14]. This is my inference from reading the code paths together; I found no doc or test that states or refutes it.

**(iii) The catalog `allowedLocations` is the real ceiling, and it is catalog-wide.** A table's locations only have to be inside the catalog's `allowedLocations` list [S13, S14]. If an operator configures that list as a broad prefix (for example the whole warehouse bucket, which is the natural configuration for a multi-tenant catalog), then any table's location can be placed anywhere in that bucket by a principal with the relevant table privileges, and credentials will be vended for those prefixes. The narrower the `allowedLocations` and the stricter the use of `parentLocation`, the smaller this gap.

### 5.3 The non-STS case removes the boundary entirely (but is not this project's case by default)

The no-STS branch is real, and Polaris documents exactly when it applies. `stsUnavailable: true` on the storage config is "set to `true` when the backend does not implement STS"; Polaris "will then skip subscoped credential vending entirely, and the client must omit `X-Iceberg-Access-Delegation: vended-credentials` and authenticate to the object store directly." The same page names **Apache Ozone S3 gateway and Ceph RGW without STS enabled** as the no-STS cases, and names **MinIO** as an S3-compatible backend that does expose STS, where `stsUnavailable` should be left unset [S24]. In the code, `AwsCredentialsStorageIntegration.shouldUseSts` returns false and `compute` skips `AssumeRole` altogether, so no `s3.access-key-id` / `s3.secret-access-key` / `s3.session-token` are put into the response [S6, S21]. There is then **no Polaris-minted, prefix-scoped credential at all**: if the client follows the documented contract and omits the delegation header, it falls back to whatever S3 credentials it already has. What happens if it does not is covered in the next paragraph. The config description for the related dev-only switch is blunt about the failure mode: `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION` (default false, "Test/dev-only") "bypass[es] credential subscoping entirely: FileIO falls back to the server's ambient credentials... those credentials are handed to every client, breaking defense-in-depth." [S8]

**The no-STS fallback is only graceful if the client omits the header. If the client sends it, Polaris 1.7.0 errors.** This is worth stating precisely because the docs phrase it as a client obligation. When `X-Iceberg-Access-Delegation: vended-credentials` is requested and the returned `StorageAccessConfig` has an empty `credentials()` map, both `IcebergCatalogHandler.loadCredentials` and `buildLoadTableResponseWithDelegationCredentials` run:

```
Preconditions.checkArgument(
    !storageAccessConfig.supportsCredentialVending() || skipCredIndirection,
    "Credential vending was requested for table %s, but no credentials are available", ...)
```

For an S3 config with `stsUnavailable: true`, the AWS integration's `compute` puts only non-credential properties (`s3.endpoint`, `client.region`, `s3.path-style-access`, the refresh endpoint) into the config, so `credentials()` is empty [S6, S19]. `supportsCredentialVending()` is a `@Value.Default` that returns **true**, and the only places it is set to false are when `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION` is true or when no storage integration is found at all; `stsUnavailable` does not set it false [S27, S5]. So the argument evaluates to `false` and `Preconditions.checkArgument` throws `IllegalArgumentException`. The result is that a no-STS backend plus a client that sends the delegation header produces an error, not a silent empty-credential response. Whether a given client sends that header is a client-side question, and for ClickHouse it is configuration-dependent, not unconditional: I verified at ClickHouse tag `v26.9.3.38-stable` that `RestCatalog.cpp` adds the header on the loadTable read path only inside `if (result.requiresCredentials())` (line 1685, header at 1693), and `requiresCredentials()` reflects `with_storage_credentials` (`ICatalog.h` lines 61, 92, 145), which `DatabaseDataLake.cpp` sets only when the `vended_credentials` setting is true (lines 736-738) [S28]. So with the default `vended_credentials = true` ClickHouse sends the header and hits the HTTP 400 above; with `vended_credentials = false` it omits the header on reads and proceeds with static credentials. The remaining unconditional send in ClickHouse is on the catalog DDL/mutation path (`RestCatalog::sendRequest`, line 1786), not on reads [S28]. **Verified (was UNVERIFIED in the first draft): the HTTP status is 400 Bad Request.** `IcebergExceptionMapper implements ExceptionMapper<RuntimeException>` and `mapExceptionToResponseCode` maps `case IllegalArgumentException e -> Status.BAD_REQUEST.getStatusCode()`; `IllegalArgumentException` is not a `PolarisException`, so the Polaris-specific mapper does not claim it [S29]. The response body is an Iceberg `ErrorResponse` with `responseCode 400` and the "Credential vending was requested for table %s, but no credentials are available" message. So a client that sends the delegation header to a no-STS backend gets an HTTP 400 on the load-table call, before any credential resolution.

**Correction (2026-09-27, after peer review): SeaweedFS is not a confirmed no-STS case.** An earlier draft of this report asserted that "the likely SeaweedFS case" was no-STS. That was unsupported, and I have removed it. SeaweedFS 4.47 (published 2026-09-14) ships an STS implementation in its own source: `weed/s3api/s3api_sts.go` handles `AssumeRole`, `AssumeRoleWithWebIdentity` and `AssumeRoleWithLDAPIdentity`, with a 12-hour maximum for `AssumeRole` and a 2048-byte inline session policy budget, and `weed/iam/sts/` contains `sts_service.go`, `session_policy.go`, `session_claims.go` and `token_utils.go` [S25]. SeaweedFS is named neither as an STS-capable nor as a no-STS backend in Polaris's own page [S24]. **UNVERIFIED:** whether Polaris's AWS SDK STS client can actually call SeaweedFS's STS endpoint, and whether SeaweedFS honours the inline session policy Polaris sends. That interop is the single test that decides whether Polaris-over-SeaweedFS can vend a scoped credential at all, and it is not settled by either project's documentation.

### 5.4 Conclusion for (d)

- **Is there a Polaris mechanism that constrains the vended credential at the storage layer?** Yes, exactly one: the provider-side scope Polaris mints (STS session policy / SAS / downscope). It is real and it is narrow in the common case.
- **If the vended credential is broader than the authorised table, can the client read other tables' files?** Yes, to the extent the other tables' files fall under the covered prefixes. Polaris does not, and cannot from the catalog, prevent this. The catalog is not a data-plane authorisation system: it authorises the *operation* and mints a *prefix-scoped* credential, then leaves enforcement to the object store's policy engine.
- **Revocation**: I found no mechanism for Polaris to revoke an already-vended cloud credential. The credential is a cloud-provider session with a fixed expiry; Polaris's cache and the refresh endpoint control future issuance, not the live credential. UNVERIFIED whether any provider-specific revocation path exists; I did not find one in the source I read.

---

## 6. (e) Does Polaris document this limitation?

**Yes, but as a threat-model boundary statement, not as a dedicated "scope limitations" page.**

`SECURITY-THREAT-MODEL.md` at the 1.7.0 tag [S10] states, in its own words:

- On the trust boundary: "Credential vending crosses from Polaris authorization into object-store or external-system authorization; delegated credentials must be scoped to the authorized actor, operation, and storage locations." [S10]
- On narrowness: "Temporary storage credentials must be scoped as narrowly as the configured storage provider and documented mode allow. Provider-specific limitations that broaden scope must be explicit to operators." [S10]
- On overlap: "Within the applicable realm and configured storage-policy scope, reused, overlapping, or ambiguous storage locations must not create an unintended authorization bypass. Explicitly configured overlap modes, table clones, and documented credential-vending scope limitations should be treated according to their documented behavior, not reported solely because overlap exists." [S10]
- On the threat: one of the enumerated threats is "Credential-vending behavior that grants broader storage access than the caller's authorized operation or effective storage boundary." [S10]
- And as an explicit **non-property**: "Polaris does not, by itself, provide the following security properties: ... **Stronger delegated-credential isolation than the selected storage provider, configured policy model, and documented deployment mode can support.**" [S10]
- Also out of scope: "Storage-provider limitations that are accurately documented and do not give Polaris callers more access than the deployment intentionally configured." [S10]

The vended-credentials doc reinforces the same framing by describing each credential as "scoped to the specific table locations and operations" (AWS), "scoped to the container and path prefix" (Azure), and "scoped to the specific GCS buckets and path prefixes" (GCS) [S9]. It does not spell out the overlap case.

**What is missing.** The threat model repeatedly refers to "documented credential-vending scope limitations" as if such documentation exists, but I did not find a page that enumerates them. I searched the in-repo docs tree and the published docs site for a page on credential-vending scope and found none. **UNVERIFIED**: whether such a page exists outside the paths I read (for example in a wiki, a design doc in `docs/` on another branch, or a mailing-list thread). I looked at `site/content/in-dev/unreleased/` (the complete docs tree at the tag), the threat model, and the vended-credentials page, and none of them enumerate the table-overlap case as a named limitation.

---

## 7. Summary table

| Question | Answer | Confidence |
|---|---|---|
| (a) Column-level access control? | No. No row-level either. Authorisation is metadata-plane: catalog, namespace, table, view, policy, principal, role. | **High** |
| (b) Privileges and roles | 102 privileges, codes 1 to 102, each bound to an entity securable and optionally a subtype. Two role types: principal role (realm) and catalog role (per catalog), chained privilege -> catalog role -> principal role -> principal. | **High** |
| (c) What vending returns | A provider-scoped short-lived credential in a `StorageCredential { prefix, config }`. Prefix = the table's own location. AWS: STS AssumeRole session with an inline IAM session policy scoped to the table's read/list/write location prefixes; default 1 hour. Azure: user-delegation SAS scoped to container and path prefix, capped at 7 days minus 60 s. GCS: downscoped OAuth2 token scoped to bucket and path prefixes, duration not respected. | **High** |
| (d) Storage-layer constraint after vending | Only the provider-side scope Polaris mints. It is prefix-based, not file-set-based. Sibling tables in distinct directories are unreachable; tables sharing or nesting prefixes are reachable. A `TABLE_WRITE_DATA` holder can point `write.data.path` at a broader prefix inside the catalog's `allowedLocations` and vend against it (inference). With `stsUnavailable: true` (Ozone S3 gateway, Ceph RGW without STS) there is no scoped credential at all, and a client that sends `X-Iceberg-Access-Delegation: vended-credentials` gets **HTTP 400** rather than a silent fallback (ClickHouse sends it only when its `vended_credentials` setting is true, which is the default) [S24, S27, S29, S28]; SeaweedFS is not a confirmed no-STS case [S25]. No revocation of live credentials found. | **High** for the mechanism; **Medium** for the write-path escalation, which is inference from code rather than documented |
| (e) Documented limitation? | Yes, in the threat model: credential vending crosses into object-store authorisation; credentials must be as narrow as the provider allows; Polaris explicitly does not provide "stronger delegated-credential isolation than the selected storage provider ... can support". No dedicated page enumerating the scope limitations was found. | **High** for the statements; **Medium** for the claim that no such page exists anywhere |

---

## Sources

All URLs accessed 2026-09-27. GitHub source files are cited at tag `apache-polaris-1.7.0` (published 2026-08-02) unless stated. Base URL for raw source: `https://raw.githubusercontent.com/apache/polaris/apache-polaris-1.7.0/`.

**S1. Apache Polaris release and repository facts.**
GitHub REST API: `https://api.github.com/repos/apache/polaris/releases/latest` (tag `apache-polaris-1.7.0`, `published_at` 2026-08-02T05:02:20Z); `https://api.github.com/repos/apache/polaris/tags`; `https://api.github.com/repos/apache/polaris/git/trees/apache-polaris-1.7.0?recursive=1`; `https://api.github.com/repos/apache/polaris/contents/docs?ref=apache-polaris-1.7.0` (symlink target `site/content/in-dev/unreleased/`); `version.txt` at the tag.

**S2. Privilege enumeration and RBAC securable model.**
`polaris-core/src/main/java/org/apache/polaris/core/entity/PolarisPrivilege.java` (tag `apache-polaris-1.7.0`), enum `PolarisPrivilege`, 102 constants, codes 1 to 102. Class Javadoc describes the securable model and notes the OPA alternative operates at `PolarisAuthorizableOperation` level.

**S3. Access-control documentation.**
`site/content/in-dev/unreleased/managing-security/access-control.md` (tag `apache-polaris-1.7.0`). Securable objects; role model; table, view, namespace, catalog, policy privilege tables; `TABLE_READ_DATA` and `TABLE_WRITE_DATA` descriptions; `TABLE_FULL_METADATA` exclusion of the data privileges; OPA external-PDP note. Published copy: `https://polaris.apache.org/in-dev/unreleased/managing-security/access-control/`.

**S4. Polaris's vendored Iceberg REST catalog OpenAPI spec.**
`spec/iceberg-rest-catalog-open-api.yaml` (tag `apache-polaris-1.7.0`). `/v1/{prefix}/namespaces/{namespace}/tables/{table}/credentials` with `operationId: loadCredentials`; `prefix` path parameter ("An optional prefix in the path"); `X-Iceberg-Access-Delegation` header enum `vended-credentials`, `remote-signing`; `StorageCredential` (`prefix`, `config`); `LoadCredentialsResponse`; `LoadTableResult.storage-credentials`. No occurrence of `ReadRestrictions`, `required-row-filter`, or `required-column-projections`.

**S5. Credential-vending implementation in the Iceberg catalog handler.**
`runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/IcebergCatalogHandler.java` (tag `apache-polaris-1.7.0`). `loadCredentials(TableIdentifier, Optional<String>)`; `authorizeLoadTable` (write-delegation first, read fallback, `{READ, LIST}` plus `WRITE`); `ImmutableCredential.builder().prefix(baseLocation)` and `.prefix(tableMetadata.location())`; `StorageUtil.getLocationsUsedByTable`; `validateTableLocations` and the "allowedLocations were tightened after the table was created" comment; `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION` precondition.

**S6. AWS credential vending and inline session policy.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/aws/AwsCredentialsStorageIntegration.java` (tag `apache-polaris-1.7.0`). `compute` calls `assumeRole` with `roleArn`, `externalId`, `roleSessionName`, inline `policy`, `durationSeconds`, optional transitive session tags; `policyString` builds `s3:GetObject`/`s3:GetObjectVersion`, `s3:ListBucket` with `s3:prefix` StringLike, `s3:PutObject`/`s3:DeleteObject`, `s3:GetBucketLocation`, and KMS actions; `escapeIamGlobLiteral`; explicit `Deny *` when no statements would be emitted; `shouldUseSts` honours `stsUnavailable`.

**S7. AWS session tags.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/aws/AwsSessionTagsBuilder.java` and `SessionTagField.java` (tag `apache-polaris-1.7.0`). Tags: realm, catalog, namespace, table, principal, roles, trace_id; documented as appearing in CloudTrail for correlation.

**S8. Feature configuration defaults.**
`polaris-core/src/main/java/org/apache/polaris/core/config/FeatureConfiguration.java` (tag `apache-polaris-1.7.0`). `STORAGE_CREDENTIAL_DURATION_SECONDS` default `60 * 60`; `STORAGE_CREDENTIAL_CACHE_DURATION_SECONDS` default `30 * 60`; `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION` default false with "Test/dev-only" and "breaking defense-in-depth" text; `INCLUDE_PRINCIPAL_NAME_IN_SUBSCOPED_CREDENTIAL` default false; `SESSION_TAGS_IN_SUBSCOPED_CREDENTIAL` default empty list; `SESSION_NAME_FIELDS_IN_SUBSCOPED_CREDENTIAL`; supported session tag and session name fields.

**S9. Vended-credentials documentation.**
`site/content/in-dev/unreleased/vended-credentials.md` (tag `apache-polaris-1.7.0`). AWS STS AssumeRole with inline session policy scoped to table locations and operations; Azure user-delegation SAS scoped to container and path prefix, 7-day Azure maximum; GCS downscoped OAuth2 token scoped to buckets and path prefixes; credential refresh endpoint; client compatibility table. Published copy: `https://polaris.apache.org/in-dev/unreleased/vended-credentials/`.

**S10. Polaris security threat model.**
`SECURITY-THREAT-MODEL.md` (tag `apache-polaris-1.7.0`). Trust-boundary statement on credential vending; invariants on narrow scoping and overlapping locations; enumerated threat of broader-than-authorised storage access; explicit non-property "Stronger delegated-credential isolation than the selected storage provider, configured policy model, and documented deployment mode can support"; out-of-scope item on accurately documented storage-provider limitations.

**S11. Iceberg REST catalog OpenAPI spec, released version.**
`https://raw.githubusercontent.com/apache/iceberg/apache-iceberg-1.11.0/open-api/rest-catalog-open-api.yaml` (Apache Iceberg 1.11.0, published 2026-05-20; latest release per `https://api.github.com/repos/apache/iceberg/releases/latest`). Same `/credentials` endpoint, `StorageCredential`, `LoadCredentialsResponse`, and `X-Iceberg-Access-Delegation` definitions as [S4]. No `ReadRestrictions`.

**S12. Location derivation for a table.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/StorageUtil.java` (tag `apache-polaris-1.7.0`). `getLocationsUsedByTable` returns base location plus `write.data.path` and `write.metadata.path`; `removeRedundantLocations` collapses nested locations to the parent.

**S13. Location restrictions and catalog allowed-locations boundary.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/LocationRestrictions.java` and `PolarisStorageConfigurationInfo.java` (tag `apache-polaris-1.7.0`). `allowedLocations` is catalog-level; optional `parentLocation` for structured table enforcement; `validate` throws `ForbiddenException` for locations outside the boundary.

**S14. Table-location validation before vending.**
`runtime/service/src/main/java/org/apache/polaris/service/catalog/common/CatalogUtils.java` (tag `apache-polaris-1.7.0`). `validateLocationsForTableLike` validates against the entity hierarchy's storage configuration and its `LocationRestrictions`.

**S15. Azure credential vending.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/azure/AzureCredentialsStorageIntegration.java` (tag `apache-polaris-1.7.0`). `BlobSasPermission` / `PathSasPermission` per read/list/write; user delegation key; intended end time from `STORAGE_CREDENTIAL_DURATION_SECONDS` capped at `Period.ofDays(7).minusSeconds(60)`; SAS scoped to container name plus blob path.

**S16. Row/column-level access control feature request.**
GitHub issue `apache/polaris#137`, "[FEATURE REQUEST] Add Row Level and Column Level access control.", opened 2024-08-10, state open, updated 2026-01-13, labels `enhancement`, `proposal`. `https://github.com/apache/polaris/issues/137`.

**S17. Proposed RLS/CLS policy implementation.**
GitHub pull request `apache/polaris#2048`, "Part 1 : Adds RLS and CLS control Policies", opened 2025-07-14, state open, `merged: false`, updated 2026-09-24. Body describes Iceberg-expression row filters and column projections, `$current_principal` / `$current_principal_role` context variables, and states it is "for engines who wants to get the policies directly". `https://github.com/apache/polaris/pull/2048`.

**S18. Policy documentation.**
`site/content/in-dev/unreleased/policy.md` (tag `apache-polaris-1.7.0`). Four predefined system policy types (`system.data-compaction`, `system.metadata-compaction`, `system.orphan-file-removal`, `system.snapshot-expiry`); inheritance; "Support for additional predefined system policy types and custom policy type definitions is in progress."

**S19. Vended property names.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/StorageAccessProperty.java` (tag `apache-polaris-1.7.0`). `s3.access-key-id`, `s3.secret-access-key`, `s3.session-token`, `s3.session-token-expires-at-ms`, `s3.endpoint`, `s3.path-style-access`, `client.region`; `gcs.oauth2.token`, `gcs.oauth2.token-expires-at`; `adls.sas-token` (bare, account-host, account-name), `adls.account-name`; refresh-endpoint properties.

**S20. REST adapter for the credentials endpoint.**
`runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/IcebergCatalogAdapter.java` (tag `apache-polaris-1.7.0`). `loadCredentials` builds the refresh endpoint via `PolarisResourcePaths(...).credentialsPath(tableIdentifier)` and calls `catalog.loadCredentials`; `parseAccessDelegationModes` reads `X-Iceberg-Access-Delegation`.

**S21. AWS storage configuration flags.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/aws/AwsStorageConfigurationInfo.java` (tag `apache-polaris-1.7.0`). `getStsUnavailable` and `getKmsUnavailable` abstract accessors, "modeled in the negative to simplify support for unset values"; `getStsEndpoint`; path-style access flag.

**S22. Published documentation site (locator only).**
`https://polaris.apache.org/in-dev/unreleased/managing-security/access-control/` and `https://polaris.apache.org/in-dev/unreleased/vended-credentials/`, both HTTP 200 on 2026-09-27. Used to confirm the in-repo pages are published; all content citations are to the in-repo files at the tag.

**S23. Iceberg REST spec on the main branch, for the row/column restriction mechanism.**
`https://raw.githubusercontent.com/apache/iceberg/main/open-api/rest-catalog-open-api.yaml`, accessed 2026-09-27. `ReadRestrictions` schema with `required-column-projections` and `required-row-filter`; reader must fail the query if it cannot apply a restriction. Read on `main` because the feature is newer than the 1.11.0 release; it is cited only to establish that the mechanism exists in the protocol and is absent from Polaris 1.7.0's vendored spec [S4].

**S24. Which S3-compatible backends have STS, per Polaris.**
`site/content/in-dev/unreleased/configuration/configuring-polaris-for-production/configuring-aws-s3-cloud-storage-specific.md` (tag `apache-polaris-1.7.0`). `stsUnavailable` "set to `true` when the backend does not implement STS"; with it true "Polaris will then skip subscoped credential vending entirely, and the client must omit `X-Iceberg-Access-Delegation: vended-credentials` and authenticate to the object store directly." Names Apache Ozone S3 gateway and Ceph RGW without STS enabled as the no-STS cases; names MinIO as an S3-compatible backend that exposes STS, where `stsUnavailable` should be left unset. SeaweedFS is not named. Read after a peer correction on 2026-09-27; it replaced an unsupported claim about SeaweedFS in section 5.3.

**S25. SeaweedFS STS implementation.**
`https://github.com/seaweedfs/seaweedfs/blob/4.47/weed/s3api/s3api_sts.go` and `https://github.com/seaweedfs/seaweedfs/tree/4.47/weed/iam/sts`, SeaweedFS tag `4.47` (published 2026-09-14), accessed 2026-09-27. `s3api_sts.go` (1162 lines) dispatches `AssumeRole`, `AssumeRoleWithWebIdentity` and `AssumeRoleWithLDAPIdentity`; constants include `maxDurationSeconds = 43200` (12 hours for `AssumeRole`) and `sessionPolicyBudgetBytes = 2048` for inline session policies. `weed/iam/sts/` contains `sts_service.go`, `session_policy.go`, `session_claims.go`, `token_utils.go`. Cited to establish that SeaweedFS is not a no-STS backend by source. Interop with Polaris's AWS SDK STS client remains UNVERIFIED.

**S26. ClickHouse Polaris catalog guide (SECONDARY source, cited only for the version-lag warning in section 1).**
`https://clickhouse.com/docs/guides/use-cases/data-warehousing/polaris-catalog`, last modified 2026-07-25, accessed 2026-09-27. Links `https://polaris.apache.org/releases/1.1.0/getting-started/using-polaris/#setup` and configures `DataLakeCatalog` with `catalog_type='rest'`, `storage_endpoint`, `catalog_credential`; does not mention `X-Iceberg-Access-Delegation` or `vended_credentials`. This is ClickHouse's own documentation, first-party for ClickHouse but secondary for Polaris, and it describes Polaris 1.1.0. Cited only to justify the version-pinning warning; no Polaris behaviour in this report is sourced from it.

**S27. `supportsCredentialVending` default and where it is set false.**
`polaris-core/src/main/java/org/apache/polaris/core/storage/StorageAccessConfig.java` (tag `apache-polaris-1.7.0`): `@Value.Default default boolean supportsCredentialVending() { return true; }`. `runtime/service/src/main/java/org/apache/polaris/service/catalog/io/StorageAccessConfigProvider.java` (same tag): sets `supportsCredentialVending(false)` only when `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION` is true or when no storage integration is found; otherwise returns the integration's config unchanged. `AwsCredentialsStorageIntegration.compute` never sets it, so an S3 config with `stsUnavailable: true` still reports `supportsCredentialVending() == true` with an empty `credentials()` map.

**S28. ClickHouse delegation-header behaviour at tag `v26.9.3.38-stable` (read directly to settle two conflicting peer measurements).**
ClickHouse source at `https://raw.githubusercontent.com/ClickHouse/ClickHouse/v26.9.3.38-stable/`: `src/Databases/DataLake/RestCatalog.cpp`, `src/Databases/DataLake/ICatalog.h`, `src/Databases/DataLake/DatabaseDataLake.cpp`, accessed 2026-09-27. The string `X-Iceberg-Access-Delegation` occurs four times in `RestCatalog.cpp`: line 1687 (a comment), line 1693 (inside `if (result.requiresCredentials())` at 1685, the loadTable read path), line 1786 (in `RestCatalog::sendRequest`, whose callers are catalog DDL/mutation such as createTable, updateMetadata and dropTable), and line 2143 (in `getCredentialsConfigurationCallback`). `ICatalog.h` defines `withStorageCredentials()` (61), `requiresCredentials()` (92), and the default `with_storage_credentials = false` (145). `DatabaseDataLake.cpp` sets the flag only under `if (with_vended_credentials) table_metadata = table_metadata.withStorageCredentials()` (736-738), where `with_vended_credentials` is the `vended_credentials` setting (74), and the refresh callback is not registered when vending is off (925-936). **Conclusion: on the read path, ClickHouse sends the delegation header only when `vended_credentials` is true (default true).** An earlier draft of this report, relaying a peer measurement, claimed the header is sent unconditionally in four places and that a no-STS backend therefore hard-fails; that was wrong and is corrected here. Two peers measured the same tag and disagreed, so I read the source myself rather than pick a side. The one genuinely unconditional send is on the catalog DDL path (line 1786); a peer attributed ClickHouse issue #105166 to that mismatch, which I did not verify.

**S29. Exception-to-HTTP mapping for the section 5.3 error.**
`runtime/service/src/main/java/org/apache/polaris/service/exception/IcebergExceptionMapper.java` (tag `apache-polaris-1.7.0`): class declaration `implements ExceptionMapper<RuntimeException>`; `mapExceptionToResponseCode` contains `case IllegalArgumentException e -> Status.BAD_REQUEST.getStatusCode()`. Independently verified by me after ch-iceberg-credentials reported it, and it resolves the HTTP-status item that was UNVERIFIED in the first draft.

---

## Verdict

**What the authorisation model governs.** In Apache Polaris 1.7.0, authorisation is entirely a **metadata-plane** concern. It governs catalog operations on catalog entities: catalogs, namespaces, Iceberg tables, views, policies, principals, principal roles, and catalog roles. The built-in RBAC authorizer defines exactly **102 privileges** (codes 1 to 102 in `PolarisPrivilege`), each attached to an entity securable and optionally an entity subtype. Roles come in two kinds: a realm-scoped **principal role** that groups principals, and a per-catalog **catalog role** that holds the actual privileges; grants chain privilege -> catalog role -> principal role -> principal. Data access is a per-table, all-or-nothing pair of privileges, `TABLE_READ_DATA` and `TABLE_WRITE_DATA`. **There is no column-level access control, and no row-level access control.** The project's own issue #137 requesting both has been open since 2024-08-10, and the only proposed implementation (PR #2048) is unmerged and returns policies to the query engine rather than enforcing them in the catalog.

**What credential vending returns.** A short-lived, provider-scoped credential wrapped as `StorageCredential { prefix, config }`, where `prefix` is the **table's own storage location**. On AWS it is an STS `AssumeRole` session (temporary access key, secret, session token) accompanied by an **inline IAM session policy** that allows only `s3:GetObject`/`GetObjectVersion`, `s3:ListBucket` with an `s3:prefix` condition, `s3:PutObject`/`DeleteObject`, and `GetBucketLocation`, over the read, list, and write location prefixes derived from the table. Default lifetime is **1 hour**. On Azure it is a **user-delegation SAS** scoped to the container and blob path, capped at 7 days minus 60 s. On GCS it is a **downscoped OAuth2 token** scoped to buckets and path prefixes, with the duration config ignored. Session tags (realm, catalog, namespace, table, principal, roles, trace_id; empty by default) exist for CloudTrail correlation, not for enforcement.

**The load-bearing limitation.** The vended credential is scoped to **storage location prefixes**, not to a table's file set and not to a table identity. Polaris never verifies that the files under the prefix belong to the authorised table. In the normal case, where each table owns its own directory, this is fine and sibling tables are unreachable. But if table locations overlap or nest (the code even collapses nested locations to the parent), or if a `TABLE_WRITE_DATA` holder points `write.data.path` at a broader prefix inside the catalog's `allowedLocations` and then vends, the credential can reach another table's files. Once the credential is vended, Polaris is out of the data path: the object store's policy engine is the boundary, and I found no way for Polaris to revoke a live cloud session. For S3-compatible stores without STS, `stsUnavailable: true` means Polaris mints no scoped credential at all [S24], and a client that sends the delegation header anyway gets an error, not a fallback [S27]. Polaris says this itself: it "does not, by itself, provide ... stronger delegated-credential isolation than the selected storage provider, configured policy model, and documented deployment mode can support" [S10].

**Confidence: high** for (a), (b), (c) and for the mechanism in (d), and for the fact that Polaris documents the boundary in its threat model in (e). **Medium** for two things: the specific write-path escalation in (d)(ii), which is my inference from reading `StorageUtil.getLocationsUsedByTable`, the session-policy builder, and `validateTableLocations` together rather than a documented or tested behaviour; and the claim in (e) that no dedicated scope-limitations page exists, which is a negative I can only assert over the docs paths I read.

**What would raise it.** For (d)(ii): an integration test against a real S3 endpoint that grants `TABLE_WRITE_DATA` on table A, sets `write.data.path` to table B's prefix, requests `vended-credentials`, and attempts to read table B's files. That test would convert the inference into a measured result. For (e): a search of the Polaris mailing list, the design-doc repository, and the `apache/polaris-tools` docs for a credential-vending scope page. For the project's actual stack: a live test of whether Polaris's AWS SDK STS client can call SeaweedFS's STS endpoint and whether SeaweedFS honours the inline session policy Polaris sends. SeaweedFS 4.47 does ship STS [S25], so this is an interop question, not a no-STS certainty; if it fails, `stsUnavailable: true` leaves the platform with no catalog-scoped storage boundary at all [S24].

**Concrete assertions for that interop test**, so the result is a measured pass or fail rather than an impression. Configure a Polaris catalog against SeaweedFS S3 with `stsEndpoint` pointed at SeaweedFS's STS and `stsUnavailable` left unset, then: (1) assert the `AssumeRole` call succeeds and the response carries `s3.access-key-id`, `s3.secret-access-key` and a non-empty `s3.session-token` [S19]; (2) assert SeaweedFS accepts the returned session token on an S3 read of the table's own files; (3) assert the inline session policy is actually enforced, by vending for table A and attempting to read table B's prefix, which must fail with AccessDenied; (4) if session tags are enabled, assert SeaweedFS accepts `sts:TagSession`, since Polaris marks tags transitive [S6, S7]; (5) with `stsUnavailable: true`, assert both directions: with the client sending the delegation header (ClickHouse default `vended_credentials = true`) Polaris returns **HTTP 400** (section 5.3) [S27, S29], and with the header omitted (ClickHouse `vended_credentials = false`) reads succeed using static credentials [S28]. Record which configuration the deployment requires, since that determines how the ClickHouse catalog connection is provisioned. Assertion (3) is the one that decides whether the vended credential is a real boundary or merely a convenience.
