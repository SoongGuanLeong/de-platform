# 08 - SeaweedFS STS Interop Test

**Date of research:** 2026-09-27. All evidence measured 2026-09-27 unless stated.
**Scope:** Whether Apache Polaris 1.7.0 can vend a scoped storage credential against SeaweedFS 4.47's STS endpoint, and whether SeaweedFS enforces the inline session policy Polaris attaches. This is the live interop test that doc 04 ("Polaris authorisation model and credential vending") names as the thing that would raise its confidence, and it selects the M10 (data governance) matrix wording.
**Question answered:** Can Polaris's AWS SDK STS client call SeaweedFS 4.47's STS endpoint, and does SeaweedFS honour the inline session policy Polaris sends? This is not the same as "does a credential come back": the dangerous case is a credential that comes back with the policy ignored.

---

## 1. Versions and environment

| Component | Version | Evidence |
|---|---|---|
| Host | Linux, podman 5.7.0, crun, cgroups v2 | `podman --version` |
| SeaweedFS | 4.47, commit c50733600, linux amd64 | `weed version` in image `docker.io/chrislusf/seaweedfs:4.47` |
| Apache Polaris | 1.7.0 (Quarkus 3.37.4) | container log `polaris-server 1.7.0 ... started in 3.122s. Listening on: http://0.0.0.0:8181` |
| Python | 3.14.4 | `python3 --version` |
| boto3 / botocore | 1.43.103 / 1.43.103 | installed via `get-pip.py` then `pip install boto3 --break-system-packages` (no pip or boto3 was present on the host) |

All containers ran locally on the same host. Polaris used the image's default in-memory metastore (`polaris.persistence.type` unset), which the Polaris startup log flags as "intended for tests only". The metastore type is irrelevant to the STS interop question; a Postgres 16 metastore is available but was not needed to exercise credential vending.

---

## 2. Phase 1 - SeaweedFS with S3 and STS

### 2.1 The IAM config file

SeaweedFS's advanced IAM config is a single JSON file. Its shape was taken from the project's own Polaris integration test (`test/s3tables/polaris/polaris_env_test.go` at tag 4.47) and the example configs under `test/s3/iam/`. The file below was written to `/tmp/ststest/iam.json` and mounted into the container at `/etc/seaweedfs/iam.json`. It is passed to both `-s3.config` (which reads the `identities` array) and `-s3.iam.config` (which reads `sts`, `roles`, `policies`); JSON unmarshalling ignores the keys each loader does not use, which is exactly what SeaweedFS's own test does.

```json
{
  "identities": [
    {
      "name": "admin",
      "credentials": [{ "accessKey": "admin", "secretKey": "admin-secret-key-1234567890" }],
      "actions": ["Admin", "Read", "List", "Tagging", "Write"]
    },
    {
      "name": "reader",
      "credentials": [{ "accessKey": "reader", "secretKey": "reader-secret-key-1234567890" }],
      "actions": ["Read", "List"]
    }
  ],
  "sts": {
    "tokenDuration": "1h",
    "maxSessionLength": "12h",
    "issuer": "seaweedfs-sts",
    "signingKey": "dGVzdC1zaWduaW5nLWtleS1mb3Itc3RzLWludGVncmF0aW9uLXRlc3Rz"
  },
  "roles": [
    {
      "roleName": "PolarisVendedRole",
      "roleArn": "arn:aws:iam::000000000000:role/PolarisVendedRole",
      "trustPolicy": {
        "Version": "2012-10-17",
        "Statement": [{ "Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole" }]
      },
      "attachedPolicies": ["FullAccess"],
      "description": "Role Polaris assumes to vend scoped credentials"
    }
  ],
  "policies": [
    {
      "name": "FullAccess",
      "document": {
        "Version": "2012-10-17",
        "Statement": [{ "Effect": "Allow", "Action": "*", "Resource": "*" }]
      }
    }
  ]
}
```

Notes on the design of this file:
- The `admin` identity carries the native `Admin@@ action. A native admin passes `CanDo` for any action, which is what lets it call `sts:AssumeRole` when it assumes a session for itself. This is the identity Polaris uses.
- The `reader` identity is deliberately non-admin with only `Read`/`List`, to test whether a non-admin can assume-self (it cannot, section 6.3).
- `PolarisVendedRole` is the role Polaris assumes by ARN. Its trust policy is `Principal: "*"`, matching SeaweedFS's own Polaris test. Its attached `FullAccess` policy becomes the session's base policy, so the inline session policy Polaris adds is the only thing narrowing the session. This is the correct shape for testing whether the narrowing is real.

### 2.2 The exact container command

```bash
podman run -d --name ststest   -p 8333:8333 -p 9333:9333 -p 8888:8888 -p 8080:8080   -v /tmp/ststest:/etc/seaweedfs:Z   docker.io/chrislusf/seaweedfs:4.47   mini -dir=/data   -s3.config=/etc/seaweedfs/iam.json   -s3.iam.config=/etc/seaweedfs/iam.json   -s3.iam.readOnly=false   -s3.port.iceberg=0 -s3.port.lance=0   -ip.bind=0.0.0.0   -master.port=9333 -volume.port=8080 -filer.port=8888 -s3.port=8333
```

`weed mini` is the single-node all-in-one. The relevant flags, read from `weed/command/mini.go` and `weed/command/server.go` at tag 4.47, are `-s3.config` (S3 identities), `-s3.iam.config` (advanced IAM config, including the `sts` block), and `-s3.iam.readOnly=false` (the flag defaults to true). `-s3.port.iceberg=0` disables SeaweedFS's own Iceberg REST catalog so port 8181 stays free for Polaris. On startup the log confirms the advanced IAM path is active:

```
I0927 08:42:11.056935 s3.go:340 Starting S3 API Server with advanced IAM integration
```

STS is mounted on the S3 port at the root (`POST /?Action=AssumeRole`); this is how `weed/s3api/s3api_server.go` registers it and how boto3's STS client reaches it with `endpoint_url=http://127.0.0.1:8333`.

### 2.3 Seeding the data

Two objects were created with the static admin credentials, under a single bucket `warehouse`:

```python
import boto3
from botocore.config import Config
EP = "http://127.0.0.1:8333"
cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 1})
s3 = boto3.client("s3", endpoint_url=EP, region_name="us-east-1",
                  aws_access_key_id="admin", aws_secret_access_key="admin-secret-key-1234567890", config=cfg)
s3.create_bucket(Bucket="warehouse")
for key in ["warehouse/table_a/data.parquet", "warehouse/table_b/data.parquet"]:
    s3.put_object(Bucket="warehouse", Key=key, Body=b"payload-" + key.encode())
```

---

## 3. Phase 2, assertion (1): AssumeRole returns a session credential

**Measured: PASS.**

The inline session policy below is the shape Polaris builds in `AwsCredentialsStorageIntegration.policyString`: `s3:GetObject`/`GetObjectVersion` on the table prefix, `s3:ListBucket` gated on `s3:prefix`, and `s3:GetBucketLocation`. It is scoped to `warehouse/table_a/`.

```python
import json, boto3
from botocore.config import Config
EP = "http://127.0.0.1:8333"; REGION = "us-east-1"
ROLE_ARN = "arn:aws:iam::000000000000:role/PolarisVendedRole"

def policy_for(prefix):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["s3:GetObject", "s3:GetObjectVersion"],
             "Resource": ["arn:aws:s3:::warehouse/%s/*" % prefix]},
            {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": ["arn:aws:s3:::warehouse"],
             "Condition": {"StringLike": {"s3:prefix": ["%s/*" % prefix]}}},
            {"Effect": "Allow", "Action": ["s3:GetBucketLocation"], "Resource": ["arn:aws:s3:::warehouse"]}
        ]}, separators=(",", ":"))

sts = boto3.client("sts", endpoint_url=EP, region_name=REGION,
                   config=Config(signature_version="v4", retries={"max_attempts": 1}),
                   aws_access_key_id="admin", aws_secret_access_key="admin-secret-key-1234567890")
resp = sts.assume_role(RoleArn=ROLE_ARN, RoleSessionName="polaris-session", Policy=policy_for("warehouse/table_a"))
```

Measured result:

```
ASSUME_ROLE_OK access_key=ASIA9301de4ea897cdd7 session_token_len=1411
has_secret=True has_token=True expiration=2026-09-27 09:42:40+00:00
```

The response carries a non-empty `s3.access-key-id`, `s3.secret-access-key` and a 1411-character `s3.session-token` (a SeaweedFS-signed JWT). This is the credential Polaris's `AwsCredentialsStorageIntegration` consumes.

---

## 4. Phase 2, assertion (2): the credential reads its own prefix

**Measured: PASS.**

Using the temporary credentials from assertion (1) on an S3 client:

```
READ table_a -> ALLOW | payload-warehouse/table_a/data.parquet
```

---

## 5. Phase 2, assertion (3): the inline session policy is enforced

**Measured: PASS.** This is the decisive assertion.

Using the same temporary credentials, an attempt to read the sibling prefix:

```
READ table_b -> DENY | AccessDenied: Access Denied.
```

The baseline confirms the denial is caused by the inline policy and not by the role being read-only: the same `admin` caller assuming the same `PolarisVendedRole` with **no** inline policy can read both prefixes.

```
named-role + NO policy:   READ table_a -> ALLOW | payload-warehouse/table_a/data.parquet
named-role + NO policy:   READ table_b -> ALLOW | payload-warehouse/table_b/data.parquet
```

Listing is also scoped, not just `GetObject`:

```
Vended for table_a list boundary:
  list prefix db/table_a/ -> ALLOW  [db/table_a/data/data.parquet, db/table_a/metadata/00000-...metadata.json]
  list prefix db/table_b/ -> DENY   AccessDenied: Access Denied.
  list prefix '' (whole bucket) -> DENY  AccessDenied: Access Denied.
```

---

## 6. The `is_admin` red flag

Doc 04 and the source flag a specific risk: when a caller with no `RoleArn` assumes a session for itself and the caller is a native admin, `handleAssumeRole` sets `is_admin = true` in the session claims, and a source comment says this "lets the session bypass base policy evaluation". If that bypass also skipped the inline session policy, an admin-driven Polaris deployment would silently lose its boundary (outcome B). boto3's STS client refuses to send `AssumeRole` without `RoleArn` (client-side `ParamValidationError`), so this path was driven with a hand-rolled SigV4 POST.

### 6.1 Admin assume-self still enforces the policy

**Measured: PASS.** The raw call returned HTTP 200 and the issued JWT literally contains `"req_ctx":{"is_admin":true}` alongside the `spol` claim holding the inline policy. Despite `is_admin` being true:

```
admin-assume-self (NO RoleArn) + policy(table_a):
  READ table_a -> ALLOW | payload-warehouse/table_a/data.parquet
  READ table_b -> DENY  | AccessDenied: Access Denied.
admin-assume-self (NO RoleArn) + NO policy:
  READ table_a -> ALLOW | payload-warehouse/table_a/data.parquet
  READ table_b -> ALLOW | payload-warehouse/table_b/data.parquet
```

This is consistent with the code: in `weed/iam/integration/iam_manager.go`, `IsActionAllowed` uses `is_admin` only to short-circuit the **base** policy evaluation (`baseResult = &policy.EvaluationResult{Effect: policy.EffectAllow}`); the inline session policy is evaluated unconditionally afterwards, and a non-Allow result denies. The base-policy bypass is real, but it does not extend to the inline session policy. The red flag did not materialise in SeaweedFS 4.47.

### 6.2 Named-role and non-admin callers

Both were also measured, with the same enforcement:

```
admin  + explicit RoleArn + policy(table_a): READ table_a ALLOW / READ table_b DENY
reader + explicit RoleArn + policy(table_a): READ table_a ALLOW / READ table_b DENY
```

### 6.3 Non-admin assume-self is refused (as designed)

A non-admin identity with no attached policies and no `RoleArn` cannot assume a session for itself. SeaweedFS returns HTTP 403 and logs:

```
W0927 08:42:54.236113 s3api_sts.go:436 AssumeRole: caller reader attempted to assume role without RoleArn and lacks global sts:AssumeRole permission
```

This is expected behaviour, not a defect: the assume-self path requires a global `sts:AssumeRole` allow, which the legacy `Read`/`List` actions do not grant. Polaris does not use this path; it always sends a `RoleArn`.

---

## 7. Oversized inline policy

**Measured: rejected.** An inline policy of 2348 bytes was refused before any session was issued:

```
OVERSIZED_POLICY_DENIED MalformedPolicyDocument
  invalid Policy document: session policy exceeds maximum size of 2048 characters
```

The 2048-byte budget is enforced as `sessionPolicyBudgetBytes` in `weed/s3api/s3api_sts.go` and `NormalizeSessionPolicy` in `weed/iam/sts/session_policy.go`. Polaris's own policy builder keeps the policy small, so this is a boundary that should not be hit in normal operation, but it is a real hard limit on how finely a table's locations can be enumerated in one session policy.

---

## 8. Phase 3 - Polaris in the loop

**Measured: PASS.** Polaris 1.7.0 successfully obtained a scoped credential from SeaweedFS's STS, and the scope is enforced.

### 8.1 Polaris container

```bash
podman run -d --name polaris --network host   -e POLARIS_BOOTSTRAP_CREDENTIALS=POLARIS,root,s3cr3t   -e polaris.realm-context.realms=POLARIS   -e AWS_REGION=us-east-1   -e AWS_ACCESS_KEY_ID=admin   -e AWS_SECRET_ACCESS_KEY=admin-secret-key-1234567890   -e quarkus.otel.sdk.disabled=true   docker.io/apache/polaris:1.7.0
```

`--network host` lets Polaris reach SeaweedFS at `127.0.0.1:8333` directly. The `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are the static SeaweedFS admin credentials Polaris uses as its own identity when calling `AssumeRole`; this mirrors how a real deployment configures the catalog's ambient credential.

### 8.2 Catalog configuration

The catalog was created through the management API with `stsUnavailable` left unset and `stsEndpoint` pointed at SeaweedFS's STS (the same port as S3):

```json
{
  "catalog": {
    "type": "INTERNAL",
    "name": "swfs",
    "properties": { "default-base-location": "s3://warehouse/" },
    "storageConfigInfo": {
      "storageType": "S3",
      "roleArn": "arn:aws:iam::000000000000:role/PolarisVendedRole",
      "region": "us-east-1",
      "endpoint": "http://127.0.0.1:8333",
      "stsEndpoint": "http://127.0.0.1:8333",
      "pathStyleAccess": true,
      "allowedLocations": ["s3://warehouse/"]
    }
  }
}
```

A namespace `db` and tables `table_a`/`table_b` were created (Polaris placed them at `s3://warehouse/db/table_a` and `s3://warehouse/db/table_b`), objects were seeded at those locations, a catalog role was granted `TABLE_READ_DATA` on both tables, and the role was attached to the `service_admin` principal role. Without the `TABLE_READ_DATA` grant, `loadTable` with delegation is refused with `ForbiddenException ... not authorized for op LOAD_TABLE_WITH_READ_DELEGATION`, which is the expected metadata-plane gate.

### 8.3 The vended credential

`GET /api/catalog/v1/swfs/namespaces/db/tables/table_a` with header `X-Iceberg-Access-Delegation: vended-credentials` returned HTTP 200 with:

```json
"storage-credentials": [
  {
    "prefix": "s3://warehouse/db/table_a",
    "config": {
      "s3.access-key-id": "ASIA6f30e3a41a3c0b58",
      "s3.secret-access-key": "<redacted>",
      "s3.session-token": "<redacted>",
      "s3.session-token-expires-at-ms": "1790502320000"
    }
  }
]
```

**Correction, 2026-09-29 (ticket #18).** The `s3.secret-access-key` and `s3.session-token` values in the response above were redacted under [ADR-0028](../adr/0028-secrets-live-only-in-the-runtime-directory.md). They were temporary STS credentials minted by this local interop test. The test stack was never deployed, so no running service accepts them, and the record is otherwise unchanged.

Decoding the session token (a SeaweedFS-signed JWT) shows Polaris's role and its inline policy landed in the token:

```
JWT claims: iss=seaweedfs-sts
            role=arn:aws:iam::000000000000:role/PolarisVendedRole
            snam=PolarisAwsCredentialsStorageIntegration
            pol=["FullAccess"]              (base policy inherited from the role)
JWT spol (inline session policy):
  s3:ListBucket on arn:aws:s3:::warehouse, Condition StringLike s3:prefix = "db/table_a/*"
  s3:GetObject, s3:GetObjectVersion on arn:aws:s3:::warehouse/db/table_a/*
  s3:GetBucketLocation on arn:aws:s3:::warehouse
  kms:DescribeKey, kms:Decrypt on arn:aws:kms:us-east-1:000000000000:key/*
```

This is Polaris's AWS SDK STS client calling SeaweedFS 4.47's `AssumeRole` with `roleArn=PolarisVendedRole` and an inline session policy, and SeaweedFS accepting both.

### 8.4 The decisive Phase 3 assertion

Using the Polaris-vended credential:

```
READ table_a own file (db/table_a/data/data.parquet) -> ALLOW | payload-table_a
READ table_b file     (db/table_b/data/data.parquet) -> DENY  | AccessDenied: Access Denied.
```

Symmetric check, vending for `table_b` instead:

```
Vended for table_b:
  read table_b -> ALLOW | payload-table_b
  read table_a -> DENY  | AccessDenied: Access Denied.
```

The boundary Polaris claims is real against SeaweedFS: a credential vended for one table cannot read a sibling table's files.

---

## 9. Supplementary - the `stsUnavailable: true` branch

Not required by the assignment, but doc 04 lists it as assertion (5) and it directly informs how the ClickHouse connection must be provisioned, so it was measured. A second catalog `swfs_nosts` was created with `"stsUnavailable": true` (in a separate bucket to satisfy Polaris's location-overlap validation).

```
[stsUnavailable=true] loadTable WITH delegation header    -> HTTP 400
  {"error":{"message":"Credential vending was requested for table db.t, but no credentials are available",
            "type":"IllegalArgumentException","code":400}}
[stsUnavailable=true] loadTable WITHOUT delegation header -> HTTP 200
  storage-credentials: None
  config: {"client.region":"us-east-1","s3.path-style-access":"true","s3.endpoint":"http://127.0.0.1:8333"}
```

This matches doc 04 section 5.3 exactly: with no STS, a client that sends the delegation header gets HTTP 400, and a client that omits it gets a normal response with no credential. One timing detail was observed and is recorded here rather than smoothed over: for a short window immediately after the catalog was created (before the storage integration was loaded/cached), the same delegated `loadTable` returned HTTP 200 with no `storage-credentials` rather than the 400. After about a minute it settled permanently to 400, and repeated calls (3x) were consistently 400. The transient 200 is a warmup artefact, not a stable behaviour, but a client that only ever calls once immediately after catalog creation could observe it.

---

## 10. Sources

**S1.** SeaweedFS 4.47, tag `4.47`, commit `c50733600`, cloned from `https://github.com/seaweedfs/seaweedfs.git`. Files read: `weed/s3api/s3api_sts.go` (`handleAssumeRole`, `prepareSTSCredentials`, `sessionPolicyBudgetBytes`, the `is_admin` comment), `weed/iam/sts/session_policy.go` (`NormalizeSessionPolicy`, 2048-byte limit), `weed/iam/integration/iam_manager.go` (`IsActionAllowed`, the `is_admin` base-policy bypass and the unconditional session-policy evaluation), `weed/s3api/auth_credentials.go` (`isAdmin`, `CanDo`, `authorizationRoute`, `authorizeWithIAM`, `isActionExplicitlyDeniedByIAM`), `weed/s3api/auth_signature_v4.go` (`validateSTSSessionToken`), `weed/s3api/s3_iam_middleware.go` (`AuthorizeAction`), `weed/s3api/s3api_server.go` (STS route registration), `weed/command/mini.go` and `weed/command/server.go` (flag names).

**S2.** SeaweedFS 4.47 test suite, tag `4.47`: `test/s3tables/polaris/polaris_env_test.go` (the project's own Polaris integration setup: combined identities+sts+roles+policies file passed to both `-s3.config` and `-s3.iam.config`, `PolarisVendedRole` with `Principal: "*"`, the Polaris container invocation), `test/s3/iam/iam_config.json` and `test/s3/iam/iam_config_docker.json` (advanced IAM config shape), `docker/compose/s3.json` (static identity shape), `test/s3/iam/s3_sts_assume_role_test.go` (AssumeRole contract).

**S3.** Apache Polaris 1.7.0 management API spec, tag `apache-polaris-1.7.0`: `spec/polaris-management-service.yml`, fetched from `https://raw.githubusercontent.com/apache/polaris/apache-polaris-1.7.0/spec/polaris-management-service.yml`. Used for `AwsStorageConfigInfo` (`roleArn`, `stsEndpoint`, `stsUnavailable`, `pathStyleAccess`, `endpoint`, `allowedLocations`), `Catalog@@, and the `AddGrantRequest`/`TableGrant`/`GrantResource` schemas.

**S4.** Container images: `docker.io/chrislusf/seaweedfs:4.47`, `docker.io/apache/polaris:1.7.0`. Version strings read from `weed version` and the Polaris startup log.

**S5.** Host tools: `podman 5.7.0`, `Python 3.14.4`, `boto3 1.43.103` / `botocore 1.43.103`.

**S6.** Internal: `docs/research/04-polaris-authorisation-model.md` (the credential-vending mechanism, the assertion list, and the confidence note naming this interop test as the thing that would raise it).

---

## Verdict

**Assertions, measured.**

| # | Assertion | Result |
|---|---|---|
| 1 | Polaris-style `AssumeRole` (named role + inline session policy) succeeds and returns `s3.access-key-id`, `s3.secret-access-key`, non-empty `s3.session-token` | **PASS** (HTTP 200; 1411-char JWT token) |
| 2 | The temporary credential reads a real object under the allowed prefix | **PASS** (`ALLOW`, payload returned) |
| 3 | The same credential is denied on a sibling prefix | **PASS** (`DENY AccessDenied`); baseline with no policy reads both |
| 4 | `is_admin` assume-self session still honours the inline policy | **PASS** (token has `is_admin: true`, `table_b` still denied) |
| 5 | Inline policy over the 2048-byte budget is rejected | **PASS** (`MalformedPolicyDocument`) |
| 6 | Polaris 1.7.0 obtains a real SeaweedFS STS credential on `loadTable` with `vended-credentials` | **PASS** (HTTP 200, `storage-credentials` with prefix `s3://warehouse/db/table_a`) |
| 7 | The Polaris-vended credential is denied on a sibling table | **PASS** (`DENY AccessDenied`, both directions) |
| 8 | `stsUnavailable: true` + delegation header returns HTTP 400 | **PASS** (after a brief post-creation warmup window; section 9) |

**Outcome: C.** `AssumeRole` succeeds and the inline session policy is enforced. This is the narrow-seam case, not outcome A (AssumeRole fails) and not outcome B (vending appears to work but the policy is ignored). Outcome B was the case tested hardest for: the decisive assertion (3) was run directly, and again under the `is_admin` path that the source flagged as a potential bypass, and in both cases the sibling prefix was denied. The Polaris-in-the-loop test confirms the same result through the real integration rather than only through a direct STS call.

**M10 branch selected.** M10 (data governance) can claim a real control: Polaris vending against SeaweedFS is a genuine per-table storage boundary, and the deployment does **not** need to fall back to static warehouse-wide credentials. The wording should describe a scoped, enforced credential (outcome C), not the wide-open seam of outcome A.

**Two qualifications to carry into the M10 wording.**
1. The boundary is a **prefix** boundary, not a table-identity boundary, exactly as doc 04 section 5.2 states. It holds because Polaris places each table at its own prefix. If two tables' locations overlap or nest, or if a writer points a table's `write.data.path` at a broader prefix inside the catalog's `allowedLocations`, the vended credential's scope widens with the prefix. This test confirms the mechanism works; it does not close that pre-existing scope limitation.
2. The `stsUnavailable: true` fallback is a hard error, not a graceful degradation: a client that sends `X-Iceberg-Access-Delegation: vended-credentials` against a no-STS catalog gets HTTP 400. This matters for the ClickHouse connection, which sends the header by default (`vended_credentials = true`). Since outcome C holds, `stsUnavailable` should be left **unset** and SeaweedFS's STS used, which is what this test configured.

**Confidence: high.** Every result above is a measured HTTP response or a decoded token from a live run on 2026-09-27, with the exact commands, config files and client scripts recorded in sections 2 to 9. The one non-deterministic observation (the post-creation warmup on the no-STS catalog) is recorded explicitly rather than averaged away. The main residual uncertainty is that SeaweedFS's `Principal: "*"` trust policy and the admin caller are a permissive test configuration; a production deployment would tighten both, but that does not change whether the inline session policy is enforced, which is the question this test answers.
