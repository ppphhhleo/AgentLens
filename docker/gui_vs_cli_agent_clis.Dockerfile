FROM paraverse-agent-runtime:latest

USER root

SHELL ["/bin/bash", "-lc"]

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
    install -d -m 0755 /etc/apt/keyrings; \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends nodejs; \
    npm install -g @anthropic-ai/claude-code @openai/codex; \
    rm -f /usr/local/bin/claude /usr/local/bin/codex; \
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      'set -euo pipefail' \
      'if [[ -f /home/user/.agentlens_cli_env ]]; then' \
      '  source /home/user/.agentlens_cli_env' \
      'fi' \
      'export HOME=/home/user' \
      'mkdir -p /home/user/.claude /home/user/.codex' \
      'if [[ "$(id -u)" == "0" ]]; then' \
      '  chown -R user:user /home/user/.claude /home/user/.codex /home/user/.agentlens_cli_env 2>/dev/null || true' \
      '  exec runuser -u user -- env HOME="$HOME" PATH="$PATH" OPENAI_API_KEY="${OPENAI_API_KEY:-}" OPENAI_BASE_URL="${OPENAI_BASE_URL:-}" ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-}" GEMINI_API_KEY="${GEMINI_API_KEY:-}" GOOGLE_AI_STUDIO_API_KEY="${GOOGLE_AI_STUDIO_API_KEY:-}" /usr/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe "$@"' \
      'fi' \
      'exec /usr/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe "$@"' \
      > /usr/local/bin/claude; \
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      'set -euo pipefail' \
      'if [[ -f /home/user/.agentlens_cli_env ]]; then' \
      '  source /home/user/.agentlens_cli_env' \
      'fi' \
      'export HOME=/home/user' \
      'mkdir -p /home/user/.claude /home/user/.codex' \
      'if [[ "$(id -u)" == "0" ]]; then' \
      '  chown -R user:user /home/user/.claude /home/user/.codex /home/user/.agentlens_cli_env 2>/dev/null || true' \
      '  exec runuser -u user -- env HOME="$HOME" PATH="$PATH" OPENAI_API_KEY="${OPENAI_API_KEY:-}" OPENAI_BASE_URL="${OPENAI_BASE_URL:-}" ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-}" GEMINI_API_KEY="${GEMINI_API_KEY:-}" GOOGLE_AI_STUDIO_API_KEY="${GOOGLE_AI_STUDIO_API_KEY:-}" /usr/lib/node_modules/@openai/codex/bin/codex.js "$@"' \
      'fi' \
      'exec /usr/lib/node_modules/@openai/codex/bin/codex.js "$@"' \
      > /usr/local/bin/codex; \
    chmod +x /usr/local/bin/claude /usr/local/bin/codex; \
    node --version; \
    npm --version; \
    claude --version || true; \
    codex --version || true; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*
