# The OpenTofu modules and the two arms

The authored, never-applied cloud shape for M19: the S3 layout, the IAM roles and
policies, the VPC and subnets, the security groups, the RDS instance class and
parameter group, and secrets handling. Both arms are rendered from one module set
and two tfvars profiles, and every check is static. See
[the cloud architecture](../docs/cloud-architecture.md) for the shape and
[ADR-0005](../docs/adr/0005-use-opentofu-instead-of-terraform.md) for the choice
of OpenTofu over Terraform.

## The two arms

| | `profiles/minimal.tfvars` | `profiles/reference.tfvars` |
|---|---|---|
| Availability Zones | 2 | 3 |
| VPC | 10.0.0.0/16 | 10.1.0.0/16 |
| Subnets | public only | public and private, per AZ |
| Egress | internet gateway | one NAT gateway per AZ |
| RDS | db.t4g.micro, Single-AZ, 20 GB | db.t4g.micro, Multi-AZ, 50 GB |
| S3 budget | 100 GB | 500 GB |
| Secrets | 1 | 5 |
| ALB, ECR | no | yes |

## Layout

- `modules/` - `network`, `storage`, `iam`, `security`, `rds` and `secrets`, each
  called once from the root.
- `policies/` - the IAM role topology as data, so the boundary is reviewable as
  a diff: `iam.json` holds the node role, one policy per component and the
  vending role; `secrets.json` is the secret inventory with its rotation class;
  the two trust templates are the only trust policies.
- `secrets/secret-projection.yaml.tmpl` - the Secrets Store CSI projection,
  setting `filePermission: "0400"` explicitly because the driver's default is
  0644 ([the security model](../docs/security-model.md) section 2.6).
- `.terraform.lock.hcl` - the committed lock file, pinned to the AWS provider
  the check resolves.

## The cluster is a prerequisite

The EKS cluster and its IAM OIDC provider are **not** authored here: the
ticket's scope is the six areas above, and the cluster is assumed to exist. Both
profiles therefore set `cluster_oidc_provider_arn` and
`cluster_oidc_issuer_url`, and every IRSA trust policy federates to that
provider. The node instance profile is authored, and it carries no S3 and no
Secrets Manager permission, so a compromised pod cannot borrow the node's
identity.

## Running the checks

```
bash deployment/scripts/install-tofu.sh
bash deployment/scripts/check-tofu.sh
bash deployment/scripts/test-check-tofu.sh
```

`check-tofu.sh` runs `tofu fmt -check`, `tofu init -backend=false` against the
committed lock file, `tofu validate` and `tflint` on both profiles, and the
structural policy scan. **No `tofu plan` and no apply runs anywhere in CI, and
no LocalStack is used** ([the cloud architecture](../docs/cloud-architecture.md)
section 7). The minimal arm is applied only by a human inside a priced demo
window, never as evidence, and the reference arm is never applied.
