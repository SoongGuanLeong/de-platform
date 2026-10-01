#!/usr/bin/env bash
#
# The secrets job (docs/ci-cd-strategy.md section 4). It absorbs the gitleaks
# scan that used to live in .github/workflows/security.yml, so one required
# check covers the whole graph.
#
# The tool is fetched by version and SHA256 and the digest is verified before
# use, which is the pattern the old workflow used and the one every check script
# follows (docs/ci-cd-strategy.md section 9).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# shellcheck source=../tools.lock
. deployment/tools.lock

workdir="$(mktemp -d)"
archive="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
trap 'rm -f "${workdir}/${archive}"; rm -f "${workdir}/gitleaks"; rmdir "${workdir}" 2>/dev/null || true' EXIT

url="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${archive}"
curl -sSfL -o "${workdir}/${archive}" "${url}"
echo "${GITLEAKS_LINUX_X64_SHA256}  ${workdir}/${archive}" | sha256sum -c -
tar -xzf "${workdir}/${archive}" -C "${workdir}" gitleaks

"${workdir}/gitleaks" version
"${workdir}/gitleaks" detect --source . --log-opts="--all" --redact --exit-code 1 --verbose
