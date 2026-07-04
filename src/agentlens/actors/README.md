# Actors

This folder is not cache. It contains the optional multi-actor layer for
human, simulated-user, and user-judge workflows.

The current single-agent collection path mostly uses `src/agentlens/models/`
and the harness adapters directly. The actor layer remains useful for:

- simulated final judges,
- dialogue-style user feedback,
- future human-in-the-loop intervention,
- collaborative trajectories where a user actor and agent actor alternate.

Do not delete this folder unless the orchestrator and user-harness code paths
are removed at the same time.
