#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${AGENTLENS_WORKFLOW_DESKTOP_APPS_CONFIG:-configs/experiments/workflow_desktop_apps_poc.yaml}"
IMAGE="${AGENTLENS_DESKTOP_APPS_IMAGE:-agentlens/desktop-apps-poc:latest}"
BASE_IMAGE="${AGENTLENS_DESKTOP_APPS_BASE_IMAGE:-agentlens/desktop-poc:latest}"
RUN_PLAN="${AGENTLENS_WORKFLOW_DESKTOP_APPS_RUN_PLAN:-agentlens_results/workflow_desktop_apps_poc/run_plan.json}"
AGENTLENS_CLI="${AGENTLENS_CLI:-.venv/bin/agentlens}"
AGENTLENS_SOURCE_DIR="${AGENTLENS_SOURCE_DIR:-$(pwd)/src}"
BUILD_TIMEOUT_SEC="${AGENTLENS_DOCKER_BUILD_TIMEOUT_SEC:-300}"

build_with_dockerfile() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "${BUILD_TIMEOUT_SEC}" docker build \
      --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
      -t "${IMAGE}" docker/desktop-apps-poc
  else
    docker build \
      --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
      -t "${IMAGE}" docker/desktop-apps-poc
  fi
}

build_with_commit_fallback() {
  local tmp_container="agentlens-desktop-apps-build-$$"
  docker rm -f "${tmp_container}" >/dev/null 2>&1 || true
  trap 'docker rm -f "${tmp_container}" >/dev/null 2>&1 || true' RETURN
  docker run --name "${tmp_container}" --user root --entrypoint bash "${BASE_IMAGE}" -lc '
    set -e
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends blender default-jre weka
    mkdir -p /workspace/data /workspace/output
    if test -f /usr/share/doc/weka/examples/iris.arff; then
      cp /usr/share/doc/weka/examples/iris.arff /workspace/data/iris.arff
    elif test -f /usr/share/weka/data/iris.arff; then
      cp /usr/share/weka/data/iris.arff /workspace/data/iris.arff
    fi
    command -v blender
    command -v weka || test -f /usr/share/java/weka.jar
  '
  docker commit \
    --change 'ENTRYPOINT ["/opt/gem/run.sh"]' \
    --change 'CMD []' \
    --change 'USER root' \
    "${tmp_container}" "${IMAGE}"
  docker rm "${tmp_container}" >/dev/null
  trap - RETURN
}

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
  echo "Desktop apps image already exists: ${IMAGE}"
else
  echo "Building ${IMAGE}"
  if ! build_with_dockerfile; then
    echo "Dockerfile build failed or timed out; falling back to run-plus-commit build." >&2
    build_with_commit_fallback
  fi
fi

echo "Verifying Weka and Blender commands in ${IMAGE}"
docker run --rm --entrypoint bash "${IMAGE}" -lc '
  set -e
  command -v blender
  command -v weka || test -f /usr/share/java/weka.jar
'

echo "Writing dry-run plan to ${RUN_PLAN}"
mkdir -p "$(dirname "${RUN_PLAN}")"
"${AGENTLENS_CLI}" run "${CONFIG}" --dry-run --output "${RUN_PLAN}"

echo "Ready. To execute one smoke run:"
echo ".venv/bin/agentlens run ${CONFIG} --execute --max-runs 1 --log-actions"
