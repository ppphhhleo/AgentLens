#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${AGENTLENS_WORKFLOW_DESKTOP_CONFIG:-configs/experiments/workflow_desktop_poc.yaml}"
IMAGE="${AGENTLENS_DESKTOP_IMAGE:-agentlens/desktop-poc:latest}"
BASE_IMAGE="${AGENTLENS_DESKTOP_BASE_IMAGE:-ghcr.io/agent-infra/sandbox:latest}"
RUN_PLAN="${AGENTLENS_WORKFLOW_DESKTOP_RUN_PLAN:-agentlens_results/workflow_desktop_poc/run_plan.json}"
AGENTLENS_CLI="${AGENTLENS_CLI:-.venv/bin/agentlens}"
AGENTLENS_SOURCE_DIR="${AGENTLENS_SOURCE_DIR:-$(pwd)/src}"

export PYTHONPATH="${AGENTLENS_SOURCE_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ ! -x "${AGENTLENS_CLI}" ]]; then
  echo "Missing executable AgentLens CLI: ${AGENTLENS_CLI}" >&2
  echo "Set AGENTLENS_CLI=/path/to/agentlens if using a shared virtualenv." >&2
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

echo "Validating ${CONFIG}"
"${AGENTLENS_CLI}" validate-config "${CONFIG}"

if docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "Desktop image already exists: ${IMAGE}"
else
  echo "Desktop image ${IMAGE} is missing."
  echo "Checking whether base image ${BASE_IMAGE} already has desktop automation tools."
  docker pull "${BASE_IMAGE}"
  if docker run --rm --entrypoint bash "${BASE_IMAGE}" -lc '
      command -v xdotool >/dev/null 2>&1 &&
      (
        command -v gnome-screenshot >/dev/null 2>&1 ||
        command -v scrot >/dev/null 2>&1 ||
        (command -v import >/dev/null 2>&1 && command -v convert >/dev/null 2>&1) ||
        (command -v xwd >/dev/null 2>&1 && command -v convert >/dev/null 2>&1)
      )
    '; then
    echo "Base image has required desktop tools; tagging ${BASE_IMAGE} as ${IMAGE}."
    docker tag "${BASE_IMAGE}" "${IMAGE}"
  else
    echo "Base image is missing desktop automation tools; building ${IMAGE}."
    docker build -t "${IMAGE}" docker/desktop-poc
  fi
fi

echo "Verifying desktop tools in ${IMAGE}"
docker run --rm --entrypoint bash "${IMAGE}" -lc '
  set -e
  command -v xdotool
  (
    command -v gnome-screenshot ||
    command -v scrot ||
    (command -v import && command -v convert) ||
    (command -v xwd && command -v convert)
  )
'

echo "Writing dry-run plan to ${RUN_PLAN}"
mkdir -p "$(dirname "${RUN_PLAN}")"
"${AGENTLENS_CLI}" run "${CONFIG}" --dry-run --output "${RUN_PLAN}"

echo "Ready. To execute one smoke run:"
echo ".venv/bin/agentlens run ${CONFIG} --execute --max-runs 1 --log-actions"
