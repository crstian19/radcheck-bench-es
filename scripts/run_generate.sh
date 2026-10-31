#!/usr/bin/env bash
# Generate reports for the specs in data/specs.jsonl.
#
# The key is read from RADCHECK_BENCH_API_KEY and only ever lives in this process's environment.
# Point RADCHECK_BENCH_BASE_URL at any OpenAI-compatible endpoint to use a different server.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${RADCHECK_BENCH_API_KEY:-}" ]; then
  echo "RADCHECK_BENCH_API_KEY is not set" >&2
  exit 1
fi

exec uv run --extra gen python scripts/generate.py generate "$@"
