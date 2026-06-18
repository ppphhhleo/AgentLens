# Act-onomy Taxonomy Snapshot

This directory contains a pinned snapshot of the Act-onomy taxonomy used by
AgentLens trajectory-analysis adapters.

- Upstream repository: https://github.com/gaojie058/Act-onomy
- Snapshot source files:
  - `1_data/2_taxonomy/act-onomy_taxonomy.csv`
  - `1_data/2_taxonomy/act-onomy_taxonomy.json`
- License for taxonomy/codebook content: CC BY 4.0, see `LICENSE-codebook`.

The AgentLens adapter does not vendor or execute the Act-onomy Claude Code
skill. It loads this taxonomy snapshot and applies an AgentLens-specific,
deterministic mapping from captured GUI/code/file/browser actions to
Act-onomy action-subaction-instance labels. This keeps the method separable
from Wang-style workflow induction and makes the mapping auditable.
