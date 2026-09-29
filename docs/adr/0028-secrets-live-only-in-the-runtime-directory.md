# Keep every secret value out of tracked files, and put the control in the write path rather than the scanner

**Status:** accepted

No secret value exists in a tracked file. Locally a secret lives in a gitignored `.env` or under `runtime/`, and reaches a container as a read-only file at `/run/secrets/<name>`; in the modelled cloud it lives in AWS Secrets Manager and is projected by the Secrets Store CSI driver with `filePermission: "0400"` set explicitly, because the driver's default is 0644. The rule exists because of the failure [ADR-0006](0006-reference-only-reuse-and-provenance.md) records: a bootstrap script in the prior repository copied a tracked file to `.bak` and minted a fresh Polaris client secret into it on every run, and `.gitignore` did not exclude `*.bak`, so a PostgreSQL password, two Polaris OAuth2 client secrets, MinIO credentials and a Polaris administrator password were committed to a public repository.

The load-bearing part of this decision is not the storage location but the write path. **No secret scanner would reliably have caught that leak.** The values were self-minted, so they match no provider pattern: GitHub native scanning knows partner patterns only and custom patterns need a paid plan, gitleaks is format and entropy, and trufflehog verifies only the providers it supports. Scanning is a backstop for the common case of a real third-party token. The control is that the bootstrap route can write secret values only inside `runtime/`, which is gitignored, so the ADR-0006 mechanism has nowhere to land. The honest limit is recorded rather than glossed: the control is structural, and the scanner is not what makes it true.

## Considered options

- **Environment variables for secret values.** Rejected: readable by every process in the container and visible in `podman inspect`, and they were the prior repository's delivery mechanism.
- **Compose `secrets:` with an `environment:` source.** Rejected: podman-compose 1.5.0 raises `ValueError: ERROR: unparsable secret`. The source is Docker-Compose-only, so it breaks the portability rule the map carries.
- **Native `podman secret`.** Rejected: no Docker equivalent outside swarm, and its file driver is unencrypted on disk.
- **SOPS with age, encrypted in Git.** Not rejected, and recorded as the alternative if Git-encrypted secrets are ever required. Not adopted, because the runtime directory solves the same problem with no extra tool and no key-distribution question.
- **SSM Parameter Store instead of Secrets Manager.** Not rejected, and recorded as the lower-cost fallback: SSM Standard is free against Secrets Manager's $0.40 per secret per month, which at the cloud document's budget of one secret and five secrets is $0.40 and $2.00 per month. Secrets Manager is kept because it is the only one of the two with managed rotation, and because the cloud document already budgets it. The swap is a `SecretProviderClass` change.

## Consequences

Rotation becomes a property of the component rather than a promise: every secret is assigned a rotation class of reload, restart or init, and only one secret, the Polaris client secret, is to be demonstrated end to end, because it is the one that rotates through the Polaris management API without a restart. The rest are documented rather than claimed.

Kafka runs PEM mode, where keystore and truststore passwords are not supported, so its keystore password is designed out and only the private key file remains a secret. Flink is the single exception: its SSL options are Java keystore only, so its keystore password must be materialised into `flink-conf.yaml` by an entrypoint reading a projected file.

The secret inventory, the rotation class of each entry, the local and cloud mechanisms and the evidence plan are in [`docs/security-model.md`](../security-model.md). The facts behind them, including the dated prices, the per-component intake keys and the CSI driver's verified 0644 default, are in [`docs/research/25-security-facts-secrets-auth-tls-audit.md`](../research/25-security-facts-secrets-auth-tls-audit.md).
