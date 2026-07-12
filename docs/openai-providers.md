# OpenAI providers

## Authentication modes

`api_key` is the default and retains the existing `OPENAI_API_KEY` and optional
`OPENAI_BASE_URL` behavior. `codex_oauth` reuses credentials created by
`codex login`. Authentication resolves in this order: a model's `auth_mode`,
`AGENTLENS_OPENAI_AUTH_MODE`, then `api_key`.

AgentLens reads `AGENTLENS_CODEX_AUTH_FILE` when set, otherwise
`$CODEX_HOME/auth.json` or `~/.codex/auth.json`. Paths support `~` expansion.
Non-model helpers require `AGENTLENS_CODEX_MODEL` unless their caller supplies
a model. AgentLens intentionally does not maintain aliases for volatile Codex
model names.

The OAuth path supports strict function tools, legacy vision/JSON actions,
simulated dialogue and judge users, WebJudge vision evaluation, and JSON
analysis calls. It does not support native OpenAI computer-use, the external
GUI-vs-CLI ChatGPT computer agent, or built-in `web.openai_search`; those
combinations fail explicitly and never fall back to an API key.

OAuth ignores `OPENAI_BASE_URL` and sends its bearer credential only to the
fixed ChatGPT Codex endpoint. Tokens refresh shortly before expiry and once
after a 401. Refresh writes are locally locked, atomic, preserve unrelated auth
file fields, and use owner-only permissions. Treat `auth.json` as a password:
never commit it, copy it into run artifacts, or share it between machines that
may refresh concurrently. If credentials are missing or broken, run
`codex login` again.

The adapter maps Chat Completions messages and function tools onto streaming
Codex Responses. Temperature and output-token limits are unsupported by this
backend and are intentionally omitted; the omission is recorded in model
telemetry. This ChatGPT backend and refresh protocol are internal, unstable,
reference-derived integrations rather than a documented public OpenAI API
contract. Prefer API-key authentication for durable unattended automation.

## Live smoke test

After running `codex login`, exercise text, image, JSON, parallel function
calls, function results, usage reporting, parameter-omission telemetry, and the
expected native-search rejection with human-readable output:

```bash
AGENTLENS_LIVE_CODEX_OAUTH=1 \
AGENTLENS_OPENAI_AUTH_MODE=codex_oauth \
AGENTLENS_CODEX_MODEL=<exact-model-id> \
  .venv/bin/pytest -s tests/test_codex_oauth_live.py
```

This test is skipped by default because it uses live credentials and spends
model quota. It never prints credentials or auth-file contents.
