# The one self-built image goes to GitHub Container Registry

**Status:** accepted

Thirteen of the fourteen image-bearing components publish `linux/arm64` upstream and the design pins them by digest, so the platform authors exactly **one** image: the arm64 Marquez build from the upstream Dockerfile at 0.51.1, because Marquez publishes no arm64 tag. The design publishes that image to **GitHub Container Registry** at `ghcr.io/soongguanleong/de-platform/marquez`, built on the `ubuntu-24.04-arm` runner that GitHub provides free for public repositories, which makes the arm64 half native and QEMU unnecessary. The registry comparison decides it. GHCR public packages are free, container registry storage and bandwidth are currently free outright, anonymous pull is supported with no published rate limit, and the push uses the built-in token, so **no AWS credential enters CI**. ECR Public is always-free for 50 GB of storage but caps **anonymous pull at 1 per second and the cap is not adjustable**, which a node group starting its pods would hit in a burst, and its pushes require AWS authentication. ECR private is **$0.10 per GB-month** with only a 500 MB / 12-month new-customer free tier, so it is not free at rest and it too needs AWS credentials in CI.

**ECR's role is authored and unused, and no sentence may read otherwise.** ECR remains an authored OpenTofu resource in the cloud arm as the documented production target, and it belongs to the `reference` profile, which is never applied. The `minimal` tfvars the demo applies do not declare it, so **the demo window creates no ECR repository at all**. **No run uses it: not the local profiles, not CI, and not the demo**, which pulls from GHCR. It therefore has **no evidence path at all**, and nothing may cite it as demonstrated. The Helm chart takes `image.registry`, `image.repository` and `image.digest` as values, defaulting to GHCR, so switching the demo to ECR is a values change plus an image copy, and **that switch is itself unproven**.

## Considered options

- **Amazon ECR Public.** Rejected: the one-pull-per-second anonymous cap is a hard limit that is not adjustable, and pushing requires AWS authentication, which would put an AWS credential into CI for no benefit.
- **Amazon ECR private.** Rejected: $0.10 per GB-month is a recurring bill for an image that a public repository can host for nothing, and it fails the free-to-run gate outside a demo window.
- **Docker Hub.** Rejected: it is not the tracker's vendor, and it would add a third account and a third credential for one image.
- **Building locally and not publishing.** Rejected: the demo's nodes have to pull the image from somewhere, and an unpublished image makes the demo unreproducible.

## Consequences

The build runs on a pull request that touches the image context **without pushing**, which proves the Dockerfile compiles at review time, and pushes only on a `demo-*` tag or `workflow_dispatch`. Two limits are carried rather than hidden: a community action in the build path may not be arm64-compatible, and the resulting image **has never been executed**, because this host is x86_64. The build being produced is not the same claim as the image running on Graviton. [The cloud architecture](../cloud-architecture.md) already carries the second as a documented limitation, and this decision does not upgrade it.
