# 07 - ClickHouse Iceberg credential intake: catalog-vended vs static credentials

**Date of research:** 2026-09-27. All evidence accessed 2026-09-27 unless stated.
**Scope:** How ClickHouse obtains and scopes credentials for Iceberg metadata and data-file reads, with the target stack in view (Apache Polaris REST catalog over SeaweedFS object storage, ClickHouse as the serving layer).
**Question answered:** Can ClickHouse's Iceberg support consume short-lived credentials vended by an Iceberg REST catalog, or does it require static credentials configured inside ClickHouse?

---

## 0. Version under test

| Fact | Evidence |
|---|---|
| Latest stable release at time of writing | `v26.9.3.38-stable`, published **2026-09-26T16:08:23Z** [S23] |
| Docs revision read | DataLakeCatalog page, "last modified on September 25, 2026" [S1] |
| Source read | `ClickHouse/ClickHouse` at tag `v26.9.3.38-stable` (raw files, exact tag pinned in every source URL) |

All source-code line numbers below refer to that tag. Where I could only read `master` I say so.

---

## 1. The short answer

ClickHouse **does** support catalog-vended credentials, and it uses them for the data-plane reads, not just for metadata. It is also able to run on static credentials instead. So the answer is not "static only". But the REST path is the least mature of the catalog paths, it supports only one of the two Iceberg access-delegation modes, and there is an open bug history specifically for Polaris and for static-credential fallback. Details and caveats follow.

---

## 2. (a) The exact credential mechanisms ClickHouse has today

ClickHouse has **five** distinct credential sources for Iceberg. They are resolved in a fixed order in `DatabaseDataLake::tryGetTableImpl` [S3:783-835].

**1. Catalog-vended credentials (the default).**

- `DataLakeCatalog` setting `vended_credentials` defaults to `true`: `DECLARE(Bool, vended_credentials, true, "Use vended credentials (storage credentials) from catalog", 0)` [S2:23].
- When enabled, ClickHouse asks the catalog for storage credentials. On the `loadTable` read path the header `X-Iceberg-Access-Delegation: vended-credentials` is added only when `result.requiresCredentials()` holds, which `DatabaseDataLake` sets from this same `vended_credentials` setting [S4:1685-1693, S3:736-738]. Two further sends are unconditional but are not the read path: the catalog DDL and mutation path in `RestCatalog::sendRequest` [S4:1786], and the credential-refresh callback, which is not registered when vending is off [S4:2143, S3:925-936]. The comment is explicit that the header has two possible values, `vended-credentials` and `remote-signing`, and that **ClickHouse currently supports only the first** [S4:1688-1691].
- The catalog response is parsed for `s3.access-key-id`, `s3.secret-access-key`, `s3.session-token`, `s3.endpoint`, and (for GCS) `gcs.oauth2.token` [S4:2069-2094].
- The parsed credential is an `S3Credentials` object carrying **access key, secret key, and session token** [S5]. It is appended into the internal Iceberg table engine arguments via `addCredentialsToEngineArgs` [S5, S3:809-818]. That is the object-storage client the data-file reads use.

**2. Static S3 credentials in the database `SETTINGS`.**

- `aws_access_key_id` and `aws_secret_access_key`, described in source as "forwarded as a static S3 storage credential for non-Glue DataLakeCatalog table reads when `vended_credentials = false`" [S2:29-30]. Backward-compatible `storage_aws_access_key_id` / `storage_aws_secret_access_key` also exist [S3, DataLakeStorageSettings.h].
- These are read by `DataLake::tryGetStaticStorageCredentials` and used when the catalog does not return vended credentials [S3:823-827].

**3. AWS STS assume-role from the database `SETTINGS`.**

- `aws_role_arn`, `aws_role_session_name` (default `ClickHouseSession`), and `aws_external_id` [S2:32-34]. ClickHouse calls STS `AssumeRole` using base credentials from `aws_access_key_id`/`aws_secret_access_key` when both are present, otherwise from the default AWS credential chain [S1, S2:32].

**4. Server `<s3>` configuration and named collections.**

- Standalone Iceberg tables (`ENGINE = IcebergS3(...)`, `Iceberg`) and the `iceberg()` / `icebergS3()` table functions can take credentials from an explicit argument list, a named collection, or the server `<s3>` config [S6, S7].
- Table-function signature: `icebergS3(url [, NOSIGN | access_key_id, secret_access_key, [session_token]] [,format] [,compression_method] [,extra_credentials])` and `icebergS3(named_collection[, option=value [,..]])` [S6:18]. Named collection example in the docs uses `access_key_id` / `secret_access_key` keys [S6:52-101].
- `extra_credentials` can pass a `role_arn` for role-based access in ClickHouse Cloud [S6:36].
- Issue #111529 documents that a standalone `Iceberg` table **does** pick up server-level `<s3>` credentials, while the same table created through `DataLakeCatalog` did not [S15].

**5. Environment / instance metadata / IRSA / instance profile / AWS config file (the default AWS credential chain).**

- These are the "ambient" credentials. Since 26.7 they are **blocked for user SQL by default**: session setting `s3_allow_server_credentials_in_user_queries` has default `0` [S9]. The docs list "DataLake table-data reads, and `DataLakeCatalog` databases (Glue, BigLake)" among the affected paths [S9]. `role_arn`-based STS assume-role stays allowed even when the setting is disabled [S9].

**Resolution order in code** [S3:809-835]: vended credentials win if present; otherwise static credentials from database settings are applied; otherwise, if the storage requires credentials and the catalog is not one of the catalogs that manage their own provider chain, ClickHouse throws `BAD_ARGUMENTS` ("Either vended credentials need to be enabled or storage credentials need to be specified...") [S3:829-834].

---

## 3. (b) Is a credential-vending REST catalog supported, and whose credential is used for file reads?

**Supported, yes, and it is the default.** The `vended_credentials` setting is documented as "Boolean indicating whether to use vended credentials from the catalog (supports AWS S3 and Azure ADLS Gen2)" [S1].

**Whose credential is used for the data files: the vended one.** The code path is explicit. If `table_metadata.hasStorageCredentials()` is true, ClickHouse injects those credentials into the engine args and does **not** fall through to the static settings [S3:809-822]. The static branch is an `else if` [S3:823-827]. So when a REST catalog vends a working credential, ClickHouse reads the data with the vended credential, not with a credential configured in ClickHouse.

The symmetric case is also handled: when the user sets `vended_credentials = false` and supplies static credentials, ClickHouse suppresses the catalog-vended refresh callback so a vended credential cannot silently override the static pair [S3:922-937]. PR #96910 added this behaviour plus `tryGetStaticStorageCredentials`, and shipped an integration regression test using **Lakekeeper**, which is a REST catalog, asserting that a wrong static pair fails rather than being rescued by vended credentials [S20, S20 test `tests/integration/test_database_iceberg_lakekeeper_catalog/test.py`, function `test_static_credentials_when_vended_credentials_disabled`].

**The bug history matters for a Polaris-on-prem stack.** Every relevant issue is still open as of 2026-09-27:

| Issue | What it says | Version reported |
|---|---|---|
| [#105166](https://github.com/ClickHouse/ClickHouse/issues/105166) | `DataLakeCatalog` REST catalog ignores `vended_credentials=false`; ClickHouse still sends `X-Iceberg-Access-Delegation: vended-credentials` and ignores the configured static keys, then hits S3 with null credentials and gets 403. Root cause named as `RestCatalog::getCredentialsAndEndpoint` [S14] | 26.4.2.10 |
| [#111529](https://github.com/ClickHouse/ClickHouse/issues/111529) | `DataLakeCatalog` (REST/Nessie) does not pass S3 credentials to the underlying Iceberg table engines; `SHOW TABLES` works, `SELECT` fails 403 [S15] | 26.6.2.81 |
| [#111839](https://github.com/ClickHouse/ClickHouse/issues/111839) | On-prem Apache Polaris with vended credentials and STS: "ClickHouse does not appear to persist or use these credentials", 403 [S16] | (on-prem Polaris) |
| [#93283](https://github.com/ClickHouse/ClickHouse/issues/93283) | Polaris REST catalog: S3 path prefix duplicated in `ICatalog::constructLocation`, 404 on query [S18] | Polaris 1.2.0-incubating |

Against that, the **current source at v26.9.3.38-stable** contains the static-credential fallback and the refresh-callback suppression that #105166 asked for [S3:783-835, S3:922-937], and PR #96910 was cherry-picked to 25.8, 26.3, 26.5, and 26.6 [S20 and its backports #116275/#116277/#116279/#116280]. **Inference (medium confidence):** the behaviour #105166 and #111529 describe is fixed in recent releases, but the issues were never closed, so the issue tracker is not a reliable guide to current behaviour. This should be re-verified against the exact deployed build.

One more constraint: ClickHouse only implements the `vended-credentials` delegation mode, not `remote-signing` [S4:1688-1691]. A REST catalog configured for remote signing (Nessie's `S3V4RestSigner` in #111529) is therefore not a supported configuration. Polaris vends credentials by default, so it is on the supported side.

---

## 4. (c) Does OAuth2 to the catalog change the data-plane credential story?

**For S3 REST catalogs: no. The OAuth2 credential covers the catalog (metadata) plane only.**

- Documented in the ClickHouse SeaweedFS catalog guide: "The engine arguments carry the S3 credentials ClickHouse uses to read table data, while `catalog_credential` and `oauth_server_uri` authenticate to the catalog itself through the OAuth2 client-credentials flow." [S12]
- In code, `RestCatalog::getAuthHeaders` builds `Authorization: Bearer <token>` from the OAuth client-credentials flow and attaches it to **catalog HTTP requests** [S4:301-332]. The object-storage client is built separately from the injected `StorageCredentials` [S5, S3:809-818]. `auth_scope` defaults to `PRINCIPAL_ROLE:ALL` [S2:24].
- So authenticating to Polaris with OAuth2 tells ClickHouse which tables exist and where their metadata is. It does not authenticate the Parquet reads. Those need either a vended storage credential or a static one.

**One documented exception, not applicable to S3 REST:** the OneLake path reuses the catalog access token for Azure Blob data access as well, and does not refresh a pre-obtained bearer token (`onelake_bearer_token`), so the database must be recreated after it expires [S1, S4:508-518, S3:875-883]. That is Azure-specific. There is no equivalent token passthrough for S3.

---

## 5. (d) Scope of object-storage access: whole warehouse, or per table / per prefix?

Three separate scopes are in play and they are often conflated.

**1. The vended credential is table-prefix scoped, and this is now verified for Polaris.** ClickHouse's own RFC for its embedded Iceberg REST catalog describes the intended vending behaviour: "To vend S3 credentials, the catalog calls STS AssumeRole with a session policy scoped to the table's storage prefix and returns short-lived credentials in the load-table response." [S19]. Polaris does the same. Verified against Polaris primary source at tag `apache-polaris-1.7.0` [S27]:

- Polaris mints an AWS STS `AssumeRole` session with an inline session policy limited to the table's read/list/write location prefixes, and returns `s3.access-key-id`, `s3.secret-access-key`, `s3.session-token`, `s3.session-token-expires-at-ms`, `s3.endpoint`, and `s3.path-style-access` [S25]. Default duration is 3600 s.
- The `prefix` in the response is the table's own location, and the scope is a set of **storage prefixes**, not a set of table file identities. Overlapping or nested table locations can widen the scope; the catalog-wide `allowedLocations` is the real ceiling. Full analysis in `docs/research/04-polaris-authorisation-model.md` sections 4 and 5 [S29].
- The dedicated endpoint is `GET /v1/{prefix}/namespaces/{ns}/tables/{table}/credentials` (`operationId: loadCredentials`), or `X-Iceberg-Access-Delegation: vended-credentials` on `loadTable` [S29]. Note that ClickHouse sends the delegation header rather than calling `/credentials` directly, which is the path Polaris supports.

**1b. On a store with no STS, Polaris vends nothing at all.** Polaris's own docs say to set `stsUnavailable: true` "when the backend does not implement STS"; "Polaris will then skip subscoped credential vending entirely, and the client must omit `X-Iceberg-Access-Delegation: vended-credentials` and authenticate to the object store directly." The named examples are the Apache Ozone S3 gateway and Ceph RGW without STS enabled; MinIO is explicitly named as an S3-compatible backend that exposes the STS API and should leave `stsUnavailable` unset [S26]. This is the configuration that forces ClickHouse back onto static credentials.

That "must omit" is a **client-side contract, and ClickHouse honours it only when the setting is turned off**. With the default `vended_credentials = true`, `RestCatalog` adds `X-Iceberg-Access-Delegation: vended-credentials` on the `loadTable` read path, so a no-STS Polaris is asked for credentials it cannot mint. Setting `vended_credentials = false` suppresses the header on reads and also suppresses the vended credential-refresh callback [S4:1685-1693, S3:736-738, S3:925-936]. The remaining unconditional sends are the catalog DDL and mutation path and the refresh callback [S4:1786, S4:2143], neither of which is the read path. Issue #105166 reports the older behaviour where the header was sent even with the setting off [S14]; the guarded code above is what prevents that on reads now. Polaris's page also references MinIO and RustFS guides alongside the Ozone and Ceph ones [S26], so Polaris treats RustFS as STS-capable in its own examples.

**1c. On a no-STS Polaris, that mismatch is a hard error, not a silent fallback.** Verified against Polaris source at tag `apache-polaris-1.7.0`:

- `AwsCredentialsStorageIntegration.compute` calls STS `AssumeRole` and populates credential properties only when `shouldUseSts` is true; otherwise the returned `StorageAccessConfig` carries non-credential properties only (`s3.endpoint`, `client.region`, `s3.path-style-access`) [S30].
- `StorageAccessConfig.supportsCredentialVending()` is a `@Value.Default` returning `true`, and the AWS integration never sets it false [S31]. The only paths that set it false are `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION=true` (documented test/dev-only) and no storage integration being found [S32]. `stsUnavailable` does **not** set it false.
- Both `IcebergCatalogHandler.loadCredentials` and the load-table delegation path assert `!supportsCredentialVending() || skipCredIndirection` and throw `IllegalArgumentException` with the message "Credential vending was requested for table %s, but no credentials are available" otherwise [S33].
- `IcebergExceptionMapper` maps `IllegalArgumentException` to HTTP **400 Bad Request**, returning an Iceberg `ErrorResponse` with `responseCode: 400` and `type: "IllegalArgumentException"` [S34].

Consequence: with ClickHouse's **default** `vended_credentials = true`, the delegation header is sent and a no-STS Polaris answers the load-table call with a **400 before any credential resolution happens**. The failure is loud rather than a silent downgrade. It is also avoidable: setting `vended_credentials = false` stops the header being sent on reads and disables the vended refresh callback [S4:1685-1693, S3:736-738, S3:925-936], after which the static-credential path in `SETTINGS` works normally. So on a no-STS backend the required configuration is `vended_credentials = false` plus static credentials, which is a supported configuration rather than a workaround. Also note Polaris rejects a requested `remote-signing` mode outright [S33], so remote signing is not a middle ground for this pair, since neither side supports it.

**2. A static credential has whatever scope the key has, typically bucket-wide.** ClickHouse does not narrow a static credential per table. If the service account key can read the whole warehouse bucket, ClickHouse will use it for every table in the catalog database.

**3. ClickHouse-side prefix filtering exists for table functions and engines, but not for `DataLakeCatalog`.**

- `GRANT READ ON S3('regexp_pattern') TO user` is documented as a "Source Filter Grant", available from 25.8 with server setting `access_control_improvements.enable_read_write_grants` [S8:672-735]. Examples: `GRANT READ ON S3('s3://foo/.*') TO john` [S8:693-697].
- Iceberg engines register a source access type: `registerStorageIceberg` sets `.source_access_type = AccessTypeObjects::Source::S3`, with the source comment "This source access type is probably a bug which was overlooked and we do not know how to fix it simply, so we keep it as it is." [S21]. Table functions enforce it via `ITableFunction::checkSourceAccess`, which calls `checkAccessWithFilter(READ|WRITE, "S3", getFunctionURINormalized())` [S22]. So `iceberg()` / `IcebergS3` reads are gated by the `S3` source grant and its regexp filter.
- **`DataLakeCatalog` does not register a source access type.** The database factory registration carries an explicit TODO: "DataLakeCatalog is polymorphic - underlying source (S3, Azure, HDFS, etc.) depends on the catalog type chosen at runtime. Consider adding `source_access_type` once a mechanism for runtime-dependent or composite source checks exist." [S3:1710-1712]. Consequence (inference, medium-high confidence): the `GRANT READ ON S3('s3://...prefix.*')` prefix filter does **not** apply to reads through a `DataLakeCatalog` database.

**Practical reading:** with vended credentials the per-table scoping is the catalog's responsibility; with a static credential ClickHouse needs read on whatever the key covers; and ClickHouse's own S3-prefix grant cannot be used to fence a `DataLakeCatalog` read.

---

## 6. (e) What ClickHouse-side control limits which Iceberg tables a user can read?

Enumerating what exists:

| Control | What it does | Scoped per Iceberg table? |
|---|---|---|
| Users, roles, `GRANT SELECT ON db.table` | Standard engine-agnostic SQL RBAC. `DataLakeCatalog` returns a storage with `StorageID(database, table, uuid)` [S3:945, S3:981], so the normal SELECT check applies to the table name. | **Yes, by table name** (see caveat below) |
| Row policies (`CREATE ROW POLICY ... ON db.table`) | A per-table read filter [S24]. The docs say a policy "applies where the table data is read locally" and warn that for remote-backed tables the policy must be defined on the underlying tables [S24]. | Not table-selection; filters rows, not tables. **UNVERIFIED for Iceberg / DataLakeCatalog** - I found no first-party test or doc confirming row policies are enforced on Iceberg reads. |
| Quotas | Resource limits (queries, rows read, bytes read, execution time), attached to users/roles [S24]. | No. Resource limits, not table selection. |
| `GRANT NAMED COLLECTION ON <name> TO user` | Controls which named collection a user may use [S8:758-770]. Relevant to `iceberg()` table-function credentials, not to `DataLakeCatalog`. | No (per collection, not per table). |
| `GRANT READ ON S3('regexp')` source filter | Per-prefix read control for S3-backed table functions/engines [S8:672-735]. | Per S3 prefix, **but not applied to `DataLakeCatalog`** [S3:1710-1712]. |
| `s3_allow_server_credentials_in_user_queries` (session, default 0 since 26.7) | Blocks user SQL from resolving the server's ambient credentials; explicit static credentials and `role_arn` STS still work [S9]. | No. Global. |
| `s3_load_table_anonymously_if_credentials_restricted` (server, default 1) | On startup/RESTORE, load a credential-restricted `DataLakeCatalog` without credentials rather than abort startup [S10]. | No. Availability behaviour. |
| `database_datalake_require_metadata_access` (session, default 1) | Whether a catalog-side metadata fetch failure aborts a listing or is ignored [S11, S3:1085-1135]. | No. It is about catalog metadata errors, not ClickHouse grants. |
| `show_data_lake_catalogs_in_system_tables` | Whether `DataLakeCatalog` tables appear in system tables [S3:1066]. | No. Visibility. |
| Engine gating: `allow_experimental_database_iceberg` / `allow_database_iceberg`, `allow_database_unity_catalog`, `allow_database_glue_catalog` [S1] | Whether the engine can be used at all. | No. Server/session feature flag. |

**Plain answer:** ClickHouse can gate which *catalog table names* a user may `SELECT` through ordinary SQL grants, but it has **no control that scopes a warehouse-wide object-storage credential per Iceberg table**. The object-storage credential is a database-level setting (or a catalog-vended value), shared by every table in that catalog database. A user who can call the `iceberg()` / `s3()` table functions with a named collection that holds the same credential can read any prefix that credential covers, bypassing the catalog table grants entirely. The one prefix-level control that exists, the `GRANT READ ON S3(...)` source filter, does not cover `DataLakeCatalog`.

**Caveat on the "yes" row:** that `GRANT SELECT ON db.table` is enforced for `DataLakeCatalog` tables is an **inference** from the fact that the resolved storage carries a normal `StorageID` and ClickHouse's access check is engine-agnostic [S3:945, S3:981]. I did not find a first-party doc, test, or issue that demonstrates it for `DataLakeCatalog`, and the DataLakeCatalog docs page does not mention access control at all [S1]. Confidence: medium. This is the single easiest thing to falsify with a live test.

---

## 7. Relevance to the de-platform stack (Polaris over SeaweedFS)

- **Polaris is on the supported side of the delegation-mode constraint**: it vends credentials, so ClickHouse's `vended-credentials`-only limitation is not a blocker in principle [S4:1688-1691].
- **The ClickHouse Polaris guide uses OAuth2 for the catalog and does not show static S3 settings** [S13]. It also warns that the integration is experimental and requires `allow_experimental_database_unity_catalog` in the version it was written for; the current docs use `allow_database_iceberg` / `allow_experimental_database_iceberg` [S1, S13].
- **For SeaweedFS specifically, the first-party guide uses the same access key/secret for both the catalog OAuth flow and the data reads, and states that the data-read credentials ride in the engine arguments while the catalog credentials ride in `catalog_credential` / `oauth_server_uri`** [S12]. SeaweedFS is also the one catalog where ClickHouse documents a working end-to-end recipe with versions (SeaweedFS 4.42+, ClickHouse 26.8+ to create tables; back to 25.8 to read) [S12].
- **SeaweedFS and STS: unresolved, and the source evidence leans toward SeaweedFS having STS.** SeaweedFS 4.47 (published 2026-09-14) ships an STS implementation in its own source: `weed/iam/sts/` (STS service, session policy, session claims, temporary-credential token generation) and `weed/s3api/s3api_sts.go`, which handles `AssumeRole` and `AssumeRoleWithWebIdentity` [S28]. Polaris's `stsUnavailable` docs name Ozone and Ceph as the no-STS cases and explicitly name MinIO as an S3-compatible backend that does expose STS [S26]. The claim that SeaweedFS forces `stsUnavailable: true` (and therefore no vended credentials) is **not supported by the source I read**. What remains unverified is whether Polaris's AWS SDK STS client interoperates with SeaweedFS's STS endpoint and whether SeaweedFS honours the inline session policy. That single test decides whether Polaris-over-SeaweedFS can vend at all.
- **Polaris path handling needs care**: `force_add_bucket` exists specifically for "catalogs that hand back paths without the bucket and expect it to be added at URL construction (Polaris-style paths)" [S2:53], and issue #93283 is exactly a Polaris path-duplication 404 [S18]. `storage_uri_style` and `flat_namespaces` are the other Polaris-adjacent knobs [S2:36, S2:54].
- **Design consequence:** do not assume a warehouse-wide ClickHouse service account can be fenced per Iceberg table on the ClickHouse side. If per-table isolation is required, it has to come from the catalog's credential vending (per-prefix STS session policy) plus a ClickHouse user that is not allowed to call `iceberg()`/`s3()` directly, because those table functions bypass the catalog.

---

## 8. What I could not verify

- Whether Polaris-over-SeaweedFS can actually vend credentials. Polaris's vending is verified (prefix-scoped STS session, exact property names) [S25, S26], but SeaweedFS ships its own STS implementation [S28], and Polaris only skips vending when `stsUnavailable: true` [S26]. Whether the two interoperate, and whether SeaweedFS honours the inline session policy, is untested. **UNVERIFIED.**
- Whether `GRANT SELECT ON db.table` is enforced for `DataLakeCatalog` tables, and whether row policies apply to Iceberg reads. No first-party test or doc found. **UNVERIFIED, medium confidence in the inference.**
- Whether issues #105166 / #111529 / #111839 are actually fixed in `v26.9.3.38-stable`. The source contains the fix and a regression test exists, but the issues remain open. **Inference only; needs a live test.**
- The exact release in which the REST static-credential fallback landed. PR #96910 (merged 2026-07-06) introduced the mechanism and backported to 25.8/26.3/26.5/26.6 [S20], and the current source generalizes it to "Unity/REST" [S3:783-835], but I did not pin the exact commit that widened it from Unity to all non-Glue catalogs.

---

## Verdict

ClickHouse can consume short-lived credentials vended by an Iceberg REST catalog. It asks for them by default (`vended_credentials = true`), parses the S3 access key, secret key, and **session token** out of the `loadTable` response, and injects them into the object-storage client that reads the Parquet files. It does not require static credentials. When vended credentials are present they take precedence over anything configured in ClickHouse; when they are absent, ClickHouse falls back to static `aws_access_key_id` / `aws_secret_access_key` in the database `SETTINGS`, or to an STS assume-role via `aws_role_arn`. OAuth2 to the catalog authenticates only the metadata plane for S3 catalogs, and does not authenticate the data reads. On the Polaris side the vended credential is a prefix-scoped STS session (default 3600 s) covering the table's read/list/write location prefixes rather than its file set [S25, S29]; if the backing store has no STS and Polaris is configured `stsUnavailable: true`, Polaris vends nothing at all and the client must authenticate to the object store itself [S26]; worse, if the client still sends the delegation header, Polaris throws and the request fails with HTTP 400 on the load-table call [S33, S34]. ClickHouse sends that header on reads by default [S4], so a no-STS Polaris answers the load-table call with HTTP 400 under the default configuration; setting `vended_credentials = false` suppresses the header on reads, after which the static-credential path in `SETTINGS` works normally [S3:736-738, S3:925-936].

The caveats are what matter operationally. ClickHouse implements only the `vended-credentials` delegation mode, not `remote-signing`, and it always sends that header. There is an open, still-unclosed bug history for exactly this area, including a bug titled "DataLakeCatalog REST catalog ignores vended_credentials=false" and one for on-prem Polaris where vended credentials were not used at all. The source at v26.9.3.38-stable contains the static-credential fallback and a Lakekeeper-based regression test, which suggests the reported behaviour is fixed, but I could not confirm that from the issue tracker. On the access-control side, ClickHouse can gate which catalog table names a user may SELECT, but it cannot scope a warehouse-wide object-storage credential per Iceberg table, and its one prefix-level control, the `GRANT READ ON S3('regexp')` source filter, does not apply to `DataLakeCatalog` because that engine registers no source access type.

**Confidence:** high for (a), (b), and (c); medium for (d) and (e).

**What would raise it:**
1. A live test against `v26.9.3.38-stable` with Polaris over SeaweedFS, checking (i) whether a vended session token is used for reads and (ii) whether `vended_credentials=false` plus static keys works.
2. A first-party test or doc showing `GRANT SELECT ON db.table` enforcement for a `DataLakeCatalog` table, and whether row policies apply to Iceberg reads.
3. A live Polaris 1.7.0 over SeaweedFS 4.47 test to settle whether Polaris's STS `AssumeRole` call and inline session policy work against SeaweedFS's own STS implementation, or whether `stsUnavailable: true` (and therefore static credentials in ClickHouse) is required.

---

## Sources

- **S1** ClickHouse docs, `DataLakeCatalog` database engine. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/reference/engines/database-engines/datalake.mdx` (rendered: `https://clickhouse.com/docs/reference/engines/database-engines/datalake`, last modified 2026-09-25).
- **S2** `src/Databases/DataLake/DatabaseDataLakeSettings.cpp` at `v26.9.3.38-stable`. Setting declarations for `vended_credentials` (line 23, default `true`), `auth_scope` (24), `aws_access_key_id` / `aws_secret_access_key` (29-30), `aws_role_arn` / `aws_role_session_name` / `aws_external_id` (32-34), `storage_uri_style` (36), `force_add_bucket` (53), `flat_namespaces` (54).
- **S3** `src/Databases/DataLake/DatabaseDataLake.cpp` at `v26.9.3.38-stable`. Credential resolution order 783-835; refresh-callback suppression 922-937; catalog unavailability 449-490; `show_data_lake_catalogs_in_system_tables` 1066; metadata-access handling 1085-1135; `DataLakeCatalog` factory registration and `source_access_type` TODO 1710-1712.
- **S4** `src/Databases/DataLake/RestCatalog.cpp` at `v26.9.3.38-stable`. `X-Iceberg-Access-Delegation: vended-credentials` at 1687-1693, 1786, 2143; `getAuthHeaders` OAuth bearer 301-332; OneLake token reuse 508-518; `getCredentialsAndEndpoint` 2069-2094.
- **S5** `src/Databases/DataLake/StorageCredentials.h` at `v26.9.3.38-stable`. `S3Credentials` carrying access key, secret key, session token, and `addCredentialsToEngineArgs`.
- **S6** ClickHouse docs, `iceberg` table function. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/reference/functions/table-functions/iceberg.mdx`.
- **S7** ClickHouse docs, Named collections. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/concepts/features/configuration/server-config/named-collections.mdx`.
- **S8** ClickHouse docs, `GRANT`. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/reference/statements/grant.mdx`. `SOURCES` 631-671; Source Filter Grants 672-735; `NAMED COLLECTION ADMIN` 758-770.
- **S9** ClickHouse docs, `s3_allow_*` session settings. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/reference/settings/session-settings/s3-allow.mdx`. `s3_allow_server_credentials_in_user_queries` default `0`, new in 26.7.
- **S10** ClickHouse docs, `s3_*` server settings. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/reference/settings/server-settings/settings/s3.mdx`. `s3_load_table_anonymously_if_credentials_restricted` default `1`.
- **S11** ClickHouse docs, `database_*` session settings. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/reference/settings/session-settings/database.mdx`. `database_datalake_require_metadata_access` default `1`, new in 26.1.
- **S12** ClickHouse docs, SeaweedFS catalog guide. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/guides/use-cases/data-warehousing/seaweedfs-catalog.mdx`. Catalog-vs-data credential statement at the `CREATE DATABASE lake` step.
- **S13** ClickHouse docs, Polaris catalog guide. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/guides/use-cases/data-warehousing/polaris-catalog.mdx`.
- **S14** ClickHouse issue #105166, "DataLakeCatalog REST catalog ignores vended_credentials=false", opened 2026-05-17, open as of 2026-09-27, reported on 26.4.2.10. `https://github.com/ClickHouse/ClickHouse/issues/105166`.
- **S15** ClickHouse issue #111529, "DataLakeCatalog (REST/Nessie) does not pass S3 credentials to underlying Iceberg table engines", opened 2026-07-23, open as of 2026-09-27, reported on 26.6.2.81. `https://github.com/ClickHouse/ClickHouse/issues/111529`.
- **S16** ClickHouse issue #111839, "Apache Polaris REST Catalog with Vended Credentials on On-Prem Deployment", opened 2026-07-24, open as of 2026-09-27. `https://github.com/ClickHouse/ClickHouse/issues/111839`.
- **S17** ClickHouse issue #93981, "Issue with vended credentials for long running queries", opened 2026-01-12, closed 2026-02-09, resolved by PR #95069, merged into 26.2.1.487. `https://github.com/ClickHouse/ClickHouse/issues/93981`.
- **S18** ClickHouse issue #93283, "DataLakeCatalog() with Polaris REST catalog duplicates S3 path prefix causing 404 errors", opened 2025-12-31, open as of 2026-09-27. `https://github.com/ClickHouse/ClickHouse/issues/93283`.
- **S19** ClickHouse issue #114697, "RFC: Iceberg REST Catalog Support", opened 2026-08-13, open as of 2026-09-27. Credential-vending design and non-goals. `https://github.com/ClickHouse/ClickHouse/issues/114697`.
- **S20** ClickHouse PR #96910, "Forward static S3 credentials for Unity DataLakeCatalog tables", merged 2026-07-06 (merge commit `d5648e82d6d6626f2d52b52828805b62c8cdbbdf`); backports #116275 (25.8), #116277 (26.3), #116279 (26.5), #116280 (26.6). `https://github.com/ClickHouse/ClickHouse/pull/96910`. Regression test: `tests/integration/test_database_iceberg_lakekeeper_catalog/test.py`, `test_static_credentials_when_vended_credentials_disabled`.
- **S21** `src/Storages/ObjectStorage/registerStorageObjectStorage.cpp` at `v26.9.3.38-stable`, `registerStorageIceberg` sets `.source_access_type = AccessTypeObjects::Source::S3` (around line 1145) with the "probably a bug" comment.
- **S22** `src/TableFunctions/ITableFunction.cpp` at `v26.9.3.38-stable`, `getSourceAccessObject` and `checkSourceAccess` (lines 29-46).
- **S23** GitHub REST API, `repos/ClickHouse/ClickHouse/releases/latest`, tag `v26.9.3.38-stable`, published 2026-09-26T16:08:23Z. `https://api.github.com/repos/ClickHouse/ClickHouse/releases/latest`.
- **S24** ClickHouse docs, Access rights (row policies) and `CREATE ROW POLICY`. `https://github.com/ClickHouse/ClickHouse/blob/v26.9.3.38-stable/docs/concepts/features/security/access-rights.mdx` and `.../docs/reference/statements/create/row-policy.mdx`.
- **S25** Apache Polaris 1.7.0, `polaris-core/src/main/java/org/apache/polaris/core/storage/StorageAccessProperty.java` (credential property names `s3.access-key-id`, `s3.secret-access-key`, `s3.session-token`, `s3.session-token-expires-at-ms`, `s3.endpoint`, `s3.path-style-access`, `gcs.oauth2.token`, `adls.sas-token-expires-at-ms`). `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/polaris-core/src/main/java/org/apache/polaris/core/storage/StorageAccessProperty.java`.
- **S26** Apache Polaris 1.7.0 docs, "Configuring AWS S3 cloud storage specific", the `stsUnavailable` setting and the no-STS fallback. `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/site/content/in-dev/unreleased/configuration/configuring-polaris-for-production/configuring-aws-s3-cloud-storage-specific.md`.
- **S27** GitHub REST API, `repos/apache/polaris/releases/latest`, tag `apache-polaris-1.7.0`, published 2026-08-02T05:02:20Z. `https://api.github.com/repos/apache/polaris/releases/latest`.
- **S28** SeaweedFS 4.47 (published 2026-09-14) STS implementation: `weed/iam/sts/` and `weed/s3api/s3api_sts.go` (`AssumeRole`, `AssumeRoleWithWebIdentity`). `https://github.com/seaweedfs/seaweedfs/tree/4.47/weed/iam/sts`, `https://github.com/seaweedfs/seaweedfs/blob/4.47/weed/s3api/s3api_sts.go`. Release: `https://api.github.com/repos/seaweedfs/seaweedfs/releases/latest`.
- **S29** de-platform internal research note, `docs/research/04-polaris-authorisation-model.md` (Polaris 1.7.0 credential vending: response shape, prefix semantics, session policy, and the prefix-vs-file-set gap). Cross-referenced, not a substitute for the Polaris primary sources above.
- **S30** Apache Polaris 1.7.0, `polaris-core/src/main/java/org/apache/polaris/core/storage/aws/AwsCredentialsStorageIntegration.java` (`compute`, `shouldUseSts`; credentials populated only in the STS branch). `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/polaris-core/src/main/java/org/apache/polaris/core/storage/aws/AwsCredentialsStorageIntegration.java`.
- **S31** Apache Polaris 1.7.0, `polaris-core/src/main/java/org/apache/polaris/core/storage/StorageAccessConfig.java` (`supportsCredentialVending` is `@Value.Default` true). `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/polaris-core/src/main/java/org/apache/polaris/core/storage/StorageAccessConfig.java`.
- **S32** Apache Polaris 1.7.0, `runtime/service/src/main/java/org/apache/polaris/service/catalog/io/StorageAccessConfigProvider.java` (the only `supportsCredentialVending(false)` paths: `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION`, or no storage integration found). `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/runtime/service/src/main/java/org/apache/polaris/service/catalog/io/StorageAccessConfigProvider.java`.
- **S33** Apache Polaris 1.7.0, `runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/IcebergCatalogHandler.java` (the `Preconditions.checkArgument` "Credential vending was requested..." at the loadCredentials and load-table delegation paths; and the rejection of `REMOTE_SIGNING`). `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/IcebergCatalogHandler.java`.
- **S34** Apache Polaris 1.7.0, `runtime/service/src/main/java/org/apache/polaris/service/exception/IcebergExceptionMapper.java` (`case IllegalArgumentException e -> Status.BAD_REQUEST`). `https://github.com/apache/polaris/blob/apache-polaris-1.7.0/runtime/service/src/main/java/org/apache/polaris/service/exception/IcebergExceptionMapper.java`.
