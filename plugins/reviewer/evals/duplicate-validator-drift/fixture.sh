#!/usr/bin/env bash
# Materialize the shared fixture into the workspace as an uncommitted diff.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
"$HERE/../setup_fixture.sh" "$HERE/../fixtures/duplicate-validator-drift" "$PWD" >/dev/null
