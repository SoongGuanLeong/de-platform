#!/usr/bin/env bash
#
# Generate a local development TLS certificate authority and one leaf
# certificate per TLS-terminating listener in the de-platform stack.
#
# Everything is written under <repo>/runtime/certs/ (mode 0700), which is
# gitignored. The CA is created once and reused on later runs, so this
# script is safe to run repeatedly.
#
# Usage: bash deployment/certs/generate.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${REPO_ROOT}/runtime/certs"

CA_CN="de-platform local development CA"
CA_DAYS=3650
LEAF_DAYS=397
CA_KEY_BITS=4096
LEAF_KEY_BITS=2048

# TLS-terminating listeners that need a leaf certificate.
SERVICES=(kafka postgres clickhouse seaweedfs grafana)

mkdir -p "${OUT_DIR}"
chmod 0700 "${OUT_DIR}"

CA_KEY="${OUT_DIR}/ca.key"
CA_CRT="${OUT_DIR}/ca.crt"

ca_reused=0

if [[ -f "${CA_KEY}" && -f "${CA_CRT}" ]]; then
  ca_reused=1
  echo "Reusing existing CA: ${CA_CRT}"
else
  echo "Creating local CA: ${CA_CRT}"
  openssl genpkey -algorithm RSA -pkeyopt "rsa_keygen_bits:${CA_KEY_BITS}" -out "${CA_KEY}"
  openssl req -x509 -new -sha256 -days "${CA_DAYS}" \
    -key "${CA_KEY}" \
    -subj "/CN=${CA_CN}" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -out "${CA_CRT}"
fi

chmod 0600 "${CA_KEY}"

tmp_ext="$(mktemp)"
trap 'rm -f "${tmp_ext}"' EXIT

for svc in "${SERVICES[@]}"; do
  key="${OUT_DIR}/${svc}.key"
  crt="${OUT_DIR}/${svc}.crt"

  if [[ "${ca_reused}" -eq 1 && -f "${key}" && -f "${crt}" ]]; then
    echo "Reusing existing leaf certificate: ${crt}"
    chmod 0600 "${key}"
    continue
  fi

  echo "Issuing leaf certificate: ${crt}"

  # Unencrypted PKCS#8 private key, so Kafka PEM mode needs no keystore
  # and no key password.
  openssl genpkey -algorithm RSA -pkeyopt "rsa_keygen_bits:${LEAF_KEY_BITS}" -out "${key}.tmp"
  openssl pkcs8 -topk8 -nocrypt -in "${key}.tmp" -out "${key}"
  rm -f "${key}.tmp"

  csr="${OUT_DIR}/${svc}.csr"
  openssl req -new -key "${key}" -subj "/CN=${svc}" -out "${csr}"

  cat > "${tmp_ext}" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:${svc},DNS:localhost,IP:127.0.0.1
EOF

  openssl x509 -req -in "${csr}" \
    -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
    -days "${LEAF_DAYS}" -sha256 \
    -extfile "${tmp_ext}" \
    -out "${crt}"

  rm -f "${csr}"
  chmod 0600 "${key}"
done

echo
echo "Certificates written to ${OUT_DIR}"
echo "  ca.crt  ${CA_CRT}"
echo "  ca.key  ${CA_KEY}"
for svc in "${SERVICES[@]}"; do
  echo "  ${svc}.crt  ${OUT_DIR}/${svc}.crt"
  echo "  ${svc}.key  ${OUT_DIR}/${svc}.key"
done
