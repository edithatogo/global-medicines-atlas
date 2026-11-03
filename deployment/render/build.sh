#!/usr/bin/env bash
# Build on Render; preserve the existing app lock and runtime contract.
set -euo pipefail
export SSL_CERT_FILE="$PWD/.ci/trust/cacert.pem"
test "$(uv --version | cut -d ' ' -f 2)" = 0.13.6
uv sync --python 3.15.1 --locked --no-default-groups --extra server
.venv/bin/python -c 'import platform; assert platform.python_version() == "3.15.1"'
