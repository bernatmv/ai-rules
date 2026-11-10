#!/bin/bash
# Thin wrapper so `record.sh shot s01 ...` works from anywhere. See record.py --help.
exec python "$(cd "$(dirname "$0")" && pwd)/record.py" "$@"
