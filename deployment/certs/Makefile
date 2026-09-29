# Thin wrapper around generate.sh. All output lands in runtime/certs/,
# which is gitignored.

CERTS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT := $(abspath $(CERTS_DIR)/../..)

.PHONY: certs clean

certs:
	bash "$(CERTS_DIR)generate.sh"

clean:
	rm -rf "$(REPO_ROOT)/runtime/certs"
