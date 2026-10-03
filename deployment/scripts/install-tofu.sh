#!/usr/bin/env bash
#
# Installs the pinned OpenTofu and tflint, each fetched by version and SHA256 and
# verified before use (docs/ci-cd-strategy.md section 9). The deployment job needs
# both; the tofu check refuses to run against an unpinned binary.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# shellcheck source=../tools.lock
. deployment/tools.lock

bindir="${TOFU_BIN_DIR:-${HOME}/.local/bin}"
mkdir -p "${bindir}"

workdir="$(mktemp -d)"
cleanup() {
  find "${workdir}" -type f -exec rm -f {} + 2>/dev/null || true
  find "${workdir}" -depth -type d -exec rmdir {} + 2>/dev/null || true
}
trap cleanup EXIT

# install_one <binary> <version> <sha256> <url> <archive> <member>
install_one() {
  local name="$1" version="$2" sha256="$3" url="$4" archive="$5" member="$6"
  if [ -x "${bindir}/${name}" ] && "${bindir}/${name}" --version 2>/dev/null | grep -q "${version}"; then
    echo "${name} ${version} already installed"
    return
  fi
  curl -sSfL -o "${workdir}/${archive}" "${url}"
  echo "${sha256}  ${workdir}/${archive}" | sha256sum -c -
  unzip -o -q "${workdir}/${archive}" -d "${workdir}/extract"
  install -m 0755 "${workdir}/extract/${member}" "${bindir}/${name}"
  "${bindir}/${name}" --version | head -1
}

install_one tofu "${TOFU_VERSION}" "${TOFU_LINUX_AMD64_SHA256}" \
  "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_amd64.zip" \
  "tofu_${TOFU_VERSION}_linux_amd64.zip" tofu

install_one tflint "${TFLINT_VERSION}" "${TFLINT_LINUX_AMD64_SHA256}" \
  "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_amd64.zip" \
  "tflint_linux_amd64.zip" tflint

if [ -n "${GITHUB_PATH:-}" ]; then
  echo "${bindir}" >> "${GITHUB_PATH}"
fi
