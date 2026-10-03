#!/usr/bin/env bash
#
# The java job (docs/ci-cd-strategy.md section 4): the streaming distributions'
# unit tests under Flink's test harness. The Gradle wrapper is committed, so the
# CI runs the same Gradle the developer runs (docs/ci-cd-strategy.md section 9),
# and the engine pin is the one docs/adr/0024 sets.
#
# Usage: run-java-tests.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)/streaming"

./gradlew --no-daemon test
