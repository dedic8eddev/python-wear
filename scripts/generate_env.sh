#!/usr/bin/env bash
set -euf -o pipefail

uuid () {
    python3 -c "import uuid; print(uuid.uuid4().hex, end='')"
}

tee $1 <<EOF > /dev/null
export SPYNL_2FA_JWT_SECRET=$(uuid)
EOF
