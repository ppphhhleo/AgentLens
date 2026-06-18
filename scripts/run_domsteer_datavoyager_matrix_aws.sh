#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="configs/experiments/domsteer_datavoyager_matrix.yaml"
TRAJECTORY_ROOT="agentlens_results/domsteer_datavoyager_matrix"
REPORT_ROOT="agentlens_results/method_comparison/domsteer_datavoyager_matrix"
DASHBOARD="${TRAJECTORY_ROOT}/dashboard.html"
ANALYSIS_MODEL="${AGENTLENS_ANALYSIS_MODEL:-gpt-5.4-mini}"
SANDBOX_IMAGE="${AGENTLENS_SANDBOX_IMAGE:-ghcr.io/agent-infra/sandbox:latest}"

if [[ ! -f ".env" ]] && [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Missing .env or OPENAI_API_KEY. Add the API key before running." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running or this user cannot access it." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/agentlens" ]]; then
  echo "Missing .venv/bin/agentlens. Create/install the project virtualenv first." >&2
  exit 1
fi

echo "Validating ${CONFIG}"
.venv/bin/agentlens validate-config "${CONFIG}"

echo "Pulling sandbox image ${SANDBOX_IMAGE}"
docker pull "${SANDBOX_IMAGE}"

echo "Writing dry-run plan"
.venv/bin/agentlens run "${CONFIG}" \
  --dry-run \
  --output "${TRAJECTORY_ROOT}/run_plan.json"

echo "Running matrix trajectories on this AWS host"
.venv/bin/agentlens run "${CONFIG}" \
  --execute \
  --log-actions

echo "Regenerating dashboard and per-trajectory method reports"
.venv/bin/agentlens matrix-dashboard "${CONFIG}" \
  --trajectory-root "${TRAJECTORY_ROOT}" \
  --output "${DASHBOARD}" \
  --report-root "${REPORT_ROOT}" \
  --generate-reports \
  --annotation-mode llm \
  --llm-provider openai \
  --llm-model "${ANALYSIS_MODEL}"

echo "Done: ${DASHBOARD}"
