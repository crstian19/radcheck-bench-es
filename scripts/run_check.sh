#!/usr/bin/env bash
# Independent verification pass: a second model, with a different prompt, sees only the report.
#
# Use a model from a DIFFERENT family than the generator so the second opinion is independent.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${RADCHECK_BENCH_API_KEY:-}" ]; then
  echo "RADCHECK_BENCH_API_KEY is not set" >&2
  exit 1
fi

# Defaults documented in prompts/MODEL.md; override with the environment.
export RADCHECK_BENCH_CHECK_MODEL="${RADCHECK_BENCH_CHECK_MODEL:-qwen3.8-flash}"

exec uv run --extra gen python scripts/check.py "$@"
