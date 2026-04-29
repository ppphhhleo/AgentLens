# AgentLens: Project Specification

## Vision

We introduce a unified capture and analysis pipeline for comparing human and agent trajectories on live visual interfaces, showing that **agents are opportunistic problem-solvers rather than interface-faithful users**.

Humans navigate UIs by building a mental model of the interface: they learn layouts, develop spatial memory, follow visual hierarchy, read labels, and build cumulative familiarity with the environment over time. They are *interface-faithful* — their behavior respects and adapts to the design intent of the UI.

Agents, by contrast, are *opportunistic*. They target elements by selector or accessibility tree lookup, skip visual scanning entirely, ignore spatial layout, and treat each page as a fresh action space to be solved. They don't "use" an interface — they solve through it. This fundamental behavioral difference has consequences for how we design UIs, how we evaluate agents, how we train them, and how we think about human-AI collaboration on the web.

AgentLens makes this difference observable, measurable, and actionable. It extends the BrowserGym/AgentLab ecosystem from agent-only benchmark evaluation to a full human-agent trajectory research platform with continuous DOM capture, multi-trial support, learning curve analysis, and RL-compatible data export — all on live websites, not sandboxed benchmarks.

---

## Core Thesis

> Humans are interface-faithful users. Agents are opportunistic problem-solvers. By capturing both in the same format on the same live interfaces, we can (1) precisely characterize where and how their strategies diverge, (2) identify what agents miss by not being interface-faithful (learning curves, spatial memory, error recovery via UI affordances), (3) identify what agents gain by being opportunistic (speed, consistency, parallelism), and (4) use human trajectory data to train agents that are both efficient and interface-aware.

This thesis connects three research threads:
- **DOMSteer** (your UIST 2026 work) — shows that in-situ UI assistance bridges the gap between human intent and interface complexity
- **Agent trajectory analysis** — shows that agents navigate UIs fundamentally differently from humans
- **RL from human demonstrations** — uses the captured behavioral gap as a training signal to make agents more interface-faithful

---

## Goals

### G1: Unified Human-Agent Trajectory Capture
Capture both human and agent interactions on the same live websites in the same trace format. Humans interact via headed browser (noVNC for remote), agents via Playwright automation. Both produce identical ExpResult-compatible directories with step observations, screenshots, and continuous DOM events. The unified format is what makes the "opportunistic vs. interface-faithful" comparison rigorous — same tasks, same pages, same capture granularity, different actors.

### G2: Continuous DOM Capture & Replay
Inject rrweb into every page to record the full DOM mutation stream — not just snapshots at action boundaries. This captures what happens *between* actions: loading states, animations, mouse movements, scroll patterns, hesitation. This layer is critical for characterizing interface-faithful behavior — humans exhibit rich micro-interactions (hovering, scanning, scrolling to orient) that agents skip entirely. Without continuous capture, these behavioral signatures are invisible.

### G3: Behavioral Trajectory Analysis — Opportunistic vs. Interface-Faithful
Compare how humans vs. agents navigate the same tasks, with specific attention to the behavioral divergence:
- **Interface-faithful signals**: Do humans follow visual hierarchy? Read labels before acting? Build spatial memory across tasks? Use hover/tooltip affordances? Exhibit systematic scanning patterns?
- **Opportunistic signals**: Do agents jump directly to target elements? Skip navigation that humans consider necessary? Use shorter but less interpretable paths? Fail at tasks that require understanding layout or visual context?
- **Metrics**: action sequence similarity, divergence points, exploration-exploitation ratio, error recovery patterns, attention patterns (mouse/scroll from rrweb), efficiency (steps, time, backtracking), path optimality vs. human-likeness.

### G4: Learning Curve & Task Ordering — How Familiarity Develops
Study how performance changes across sequential tasks on the same website. Humans naturally become interface-faithful *over time* — they learn where things are, develop muscle memory, build expectations. This is the essence of environment familiarity. Compare:
- Human learning curves (natural, interface-faithful familiarity)
- Agent learning curves with different memory mechanisms (do they develop interface-faithful behavior, or just faster opportunistic behavior?)
- Whether task ordering affects the rate and nature of learning

### G5: Multi-Trial Error Recovery — Strategies Under Failure
Support multiple attempts per task with configurable feedback between trials. Capture the full trial-and-error progression: failed trajectories, error reflections, strategy changes across retries. Key questions:
- When humans fail, do they adjust their interface model (interface-faithful recovery)? When agents fail, do they just try a different element (opportunistic recovery)?
- Does providing agents with interface-aware feedback (key-node progress, UI state description) shift them toward more interface-faithful retry strategies?
- Can human error-recovery patterns be distilled into agent training data?

### G6: RL-Compatible Data Export — Training Interface-Aware Agents
Export trajectories as (state, action, reward, next_state) tuples for offline RL training. The key insight: human trajectories encode *interface-faithful* behavior that agents currently lack. By training on human demonstrations, we can push agents from purely opportunistic toward interface-aware problem-solving — maintaining their efficiency while respecting UI design intent. This connects to:
- Behavioral cloning from human demonstrations
- RLHF preference learning (human trajectory preferred over agent trajectory)
- Reward shaping from interface-faithful behavioral priors
- Knowledge distillation from DOMSteer-assisted human interactions

---

## Resource Map

### Foundation Layer

| Resource | Role | What to use |
|----------|------|-------------|
| **BrowserGym** (ServiceNow, 1.2k★) | Environment engine | `BrowserEnv`, `AbstractBrowserTask`, action space, DOM/AXTree/screenshot observations, task registration |
| github.com/servicenow/browsergym | | `headless=False` for human mode, `record_video_dir`, `pw_context_kwargs` for rrweb injection |
| **AgentLab** (ServiceNow, 527★) | Experiment runner | `Study`, `make_study()`, Ray parallel execution, `ExpResult`, `load_result_df()`, AgentXRay trace viewer, `GenericAgent`, reproducibility tracking |
| github.com/ServiceNow/AgentLab | | Fork and extend — add AgentLens modules alongside existing code |

### Task Sources

| Resource | Role | What to use |
|----------|------|-------------|
| **Online-Mind2Web** (OSU-NLP, 147★) | 300 tasks on 136 live websites | Batch-import as BrowserGym tasks. Diverse domains (clothing, food, housing, transport). Actively maintained (36 tasks updated Nov 2025). |
| github.com/OSU-NLP-Group/Online-Mind2Web | | **WebJudge / WebJudge-7B** — LLM-as-judge evaluator (86% human agreement), usable as `validate()` for open-web tasks AND as RL reward model |
| **Your DOMSteer tasks** | 8 tasks across DataVoyager + TF Playground | Register as BrowserGym `AbstractBrowserTask` subclasses with programmatic `validate()` using DOM state inspection + CheckEval rubric |
| **WebCanvas / Mind2Web-Live** (iMeanAI, 281★) | 542 tasks, key-node evaluation | **Key-node intermediate checkpoints** — evaluate task progress, not just completion. **JS event listener evaluation** — decoupled from action space, works for both human and agent |
| github.com/iMeanAI/WebCanvas | | |
| **AgentTrek** (xlang-ai, ICLR 2025 Spotlight) | Synthetic trajectory generation | Pipeline for auto-generating tasks from web tutorials. Reference for task scaling beyond manually authored tasks. $0.55/trajectory. |
| github.com/xlang-ai/AgentTrek | | |

### Human Trajectory & Trial-and-Error

| Resource | Role | What to use |
|----------|------|-------------|
| **TEC** (Tsinghua, Apr 2026) | Human trial-and-error dataset | 46 participants, 58 tasks, 5,370 trial trajectories with error reflections. Reference for multi-trial annotation platform design, retry UX flow, and reflection schema. |
| github.com/Serendipity0429/TEC | | |
| **rrweb** (18k★) | Continuous DOM recording | ~26KB tracker. Inject via `page.addInitScript()`. Captures all DOM mutations, mouse movements, scrolls, keystrokes as timestamped JSON events. You already have experience with this. |
| github.com/rrweb-io/rrweb | | |
| **WebLINX** (McGill-NLP) | Human web interaction traces | Real-world human demonstrations with conversational context. BrowserGym integration exists. Reference for human trajectory data schema. |
| github.com/McGill-NLP/weblinx | | |

### Agent Memory & Learning

| Resource | Role | What to use |
|----------|------|-------------|
| **PolySkill** (Oct 2025) | Polymorphic skill abstraction | Transferable skills across websites. Reference for memory agent that learns generalizable interaction patterns, not memorized sequences. |
| **AWM (Agent Workflow Memory)** | Workflow extraction from past experiences | Library of reusable interaction patterns ("how to fill a form", "how to navigate a menu"). Reference for knowledge-base-style agent memory. |
| **ACuRL** (OSU-NLP, Feb 2026) | Autonomous curriculum RL | Curriculum task generation + CUAJudge + continual learning with sparse parameter updates. Reference for curriculum-based task ordering and autonomous environment adaptation. |
| github.com/OSU-NLP-Group/ACuRL | | |

### RL Training Infrastructure (Future Layer)

| Resource | Role | What to use |
|----------|------|-------------|
| **OpenEnv** (Meta, 1.5k★) | RL post-training environment interface | Client-server architecture, Docker containers, HuggingFace Hub integration, MCP-native environments. Wrapping BrowserGym in OpenEnv spec = bridge to TorchForge/TRL/veRL training frameworks. |
| github.com/meta-pytorch/OpenEnv | | |
| **WebAgent-R1** (May 2025) | End-to-end multi-turn RL reference | Async GRPO rollouts, Qwen-2.5-3B: 6.1%→33.9% on WebArena-Lite. Reference implementation for "how to actually do GRPO on web tasks." |
| **WebServ** (Oct 2025) | Scalable container orchestration | 200+ concurrent browsers, 5× faster launch, 240× less storage. Reference for scaling browser environments for RL training. |
| **CUARewardBench** (Oct 2025) | Reward model evaluation | Step-level + trajectory-level annotations. Validates reliability of your evaluation/reward pipeline. |

### Trajectory Analysis & Observability

| Resource | Role | What to use |
|----------|------|-------------|
| **Laminar** (open-source) | Agent observability platform | Browser-agent session replay syncing DOM state to spans. Agent rollout debugger (re-run from any span, change prompt mid-run). OpenTelemetry-native. |
| **AgentPrism** (Evil Martians) | Agent trace visualization | React component library for visualizing agent traces. Could be used as building blocks for AgentLens UI. |
| **langchain-ai/agentevals** | Trajectory evaluation | LLM-as-judge evaluators for agent trajectories. `TRAJECTORY_ACCURACY_PROMPT` as reference for your evaluation pipeline. |

---

## Architecture

```
AgentLab (forked) ──────────────────────────────────────────────────
│
├── src/agentlab/           [EXISTING — keep all]
│   ├── agents/             GenericAgent, MostBasicAgent
│   ├── experiments/        Study, make_study, parallel execution
│   ├── analyze/            inspect_results, load_result_df
│   └── xray/               AgentXRay (keep as baseline viewer)
│
├── src/agentlens/          [YOUR ADDITIONS]
│   │
│   ├── capture/            ── Trajectory Capture Layer ──
│   │   ├── rrweb_wrapper.py        BrowserEnv wrapper, inject rrweb
│   │   ├── human_runner.py         Headed browser + noVNC + action segmentation
│   │   ├── trial_runner.py         Multi-trial loop with feedback injection
│   │   ├── trajectory_store.py     Unified storage: steps + rrweb + trials
│   │   └── js_listeners.py         Key-node evaluation (WebCanvas-style)
│   │
│   ├── agents/             ── Agent Harness Engineering ──
│   │   ├── stateless_agent.py      No memory (AgentLab baseline)
│   │   ├── memory_agent.py         Sliding window / summarized context
│   │   ├── cached_agent.py         Stagehand-style DOM hash → action cache
│   │   ├── curriculum_agent.py     Picks next task based on failures
│   │   └── human_agent.py          Wraps human input as "agent" for unified API
│   │
│   ├── tasks/              ── Task Definitions at Scale ──
│   │   ├── datavoyager/            Your DOMSteer tasks
│   │   ├── tfplayground/           Your DOMSteer tasks
│   │   ├── mind2web_live/          Import Online-Mind2Web 300 tasks
│   │   ├── webcanvas/              Import WebCanvas/Mind2Web-Live 542 tasks
│   │   └── task_generator.py       LLM-based task generation (ACuRL-style)
│   │
│   ├── evaluation/         ── Rich Evaluation Layer ──
│   │   ├── key_nodes.py            Intermediate checkpoint evaluation
│   │   ├── web_judge.py            WebJudge-7B integration
│   │   ├── check_eval.py           Your CheckEval rubric
│   │   └── trajectory_metrics.py   Efficiency, backtracking, exploration metrics
│   │
│   ├── analysis/           ── AgentLens Analysis ──
│   │   ├── comparison.py           Human vs. agent trajectory alignment
│   │   ├── learning_curve.py       Performance over task sequences
│   │   ├── trial_analysis.py       Multi-trial error recovery patterns
│   │   ├── transfer_analysis.py    Cross-website transfer
│   │   └── export_rl.py            Export to (s,a,r,s') for offline RL
│   │
│   ├── live/               ── Live Study Platform ──
│   │   ├── participant_server.py   Web server for remote participants
│   │   ├── task_router.py          Condition assignment, counterbalancing
│   │   ├── vnc_bridge.py           noVNC for remote headed browser
│   │   └── consent_flow.py         IRB consent + demographics
│   │
│   └── ui/                 ── AgentLens Viewer ──
│       ├── app.py                  Extends/replaces AgentXRay
│       ├── replay.py               rrweb continuous replay component
│       ├── side_by_side.py         Trajectory comparison view
│       └── dashboard.py            Experiment-level overview
│
└── pyproject.toml
    extends agentlab dependencies + rrweb + noVNC
```

---

## Trajectory Data Schema

```python
trajectory = {
    # Identity
    "experiment_id": "exp_042",
    "actor_type": "human" | "agent_stateless" | "agent_memory" | ...,
    "actor_config": { ... },            # agent args or participant ID

    # Task context
    "task_id": "mind2web.a3f2b1c",
    "task_goal": "Find flights from NYC to LA under $300",
    "website_url": "https://united.com",

    # Sequence context
    "task_sequence_id": "seq_007",
    "position_in_sequence": 3,
    "prior_tasks": ["task_a", "task_b"],
    "accumulated_context": "...",       # what memory the agent has

    # Trial context
    "trial_number": 2,
    "max_trials": 5,
    "previous_trial_result": {
        "success": False,
        "key_nodes_completed": [1, 2, 3],
        "key_nodes_failed": [4],
        "error_reflection": "...",
    },
    "feedback_type": "key_node_progress",

    # Step-level data (BrowserGym-compatible)
    "steps": [
        {
            "step_index": 0,
            "timestamp": "2026-04-27T14:32:01Z",
            "observation": {
                "dom_html": "...",
                "axtree": "...",
                "screenshot_path": "step_0.png",
                "url": "https://united.com",
                "open_tabs": [...],
            },
            "action": "click(bid='a46')",
            "action_metadata": {           # agent-only
                "llm_prompt": "...",
                "llm_response": "...",
                "reasoning": "...",
                "confidence": 0.85,
            },
            "reward": 0.0,
            "key_nodes_hit": [],
            "rrweb_events_since_last_step": [...],   # continuous DOM stream
            "dwell_time_ms": 3200,                    # time before acting
        },
        ...
    ],

    # Outcome
    "success": True,
    "total_steps": 8,
    "total_time_ms": 45000,
    "final_reward": 1.0,
    "key_nodes_completed": [1, 2, 3, 4, 5, 6],
}
```

---

## Prototype Plan (4-week sprint)

### Week 1: Foundation
- [ ] Fork AgentLab, set up dev environment
- [ ] Install BrowserGym, run demo agent on DataVoyager via `openended` mode
- [ ] Register 2 DataVoyager + 2 TF Playground tasks as `AbstractBrowserTask`
- [ ] Write `validate()` using DOM state inspection for these 4 tasks
- [ ] Run `agentlab-xray` to see what traces look like
- [ ] **Deliverable:** agent traces for 4 tasks viewable in AgentXRay

### Week 2: Capture Layer
- [ ] Build `rrweb_wrapper.py` — inject rrweb via `page.addInitScript()`
- [ ] Capture rrweb events alongside BrowserGym step data
- [ ] Build `human_runner.py` — headed browser, segment actions by click/type/navigate events
- [ ] Output human traces in same ExpResult directory structure as agent traces
- [ ] **Deliverable:** one human, one agent doing same task, both with rrweb + step data

### Week 3: Multi-Trial + Scale
- [ ] Build `trial_runner.py` — retry loop with feedback injection between trials
- [ ] Import 20-50 Online-Mind2Web tasks as BrowserGym tasks (WebJudge as validator)
- [ ] Build `memory_agent.py` — agent with sliding window of past task traces
- [ ] Run: stateless agent vs. memory agent × 20 tasks × 3 trials each
- [ ] **Deliverable:** multi-trial trajectory data with memory ablation

### Week 4: Analysis + Viewer
- [ ] Build basic trajectory comparison (align by DOM state, compute divergence)
- [ ] Build learning curve plot (steps-to-completion over task sequence)
- [ ] Build rrweb replay component (play back DOM stream synchronized with steps)
- [ ] Wire into Gradio app (or extend AgentXRay) with side-by-side view
- [ ] **Deliverable:** working AgentLens viewer showing human vs. agent comparison

### Post-prototype
- Scale to full Online-Mind2Web 300 tasks
- Build live study platform (noVNC, participant routing, consent flow)
- Run formal human study (N=20+ participants)
- Implement RL export (behavioral cloning from human trajectories)
- OpenEnv wrapper for training framework integration
- Paper: target UIST 2026 or CHI 2027

---

## Research Contributions (what's novel)

### Core finding
**Agents are opportunistic problem-solvers, not interface-faithful users.** We provide the first empirical evidence at scale, with continuous behavioral capture, that humans and agents exhibit fundamentally different interaction paradigms on the same live interfaces — and that this gap has concrete implications for agent training, UI design, and human-AI collaboration.

### Infrastructure contributions
1. **First unified platform** for capturing human and agent trajectories in the same format on live websites (not benchmark sandboxes), making the opportunistic-vs-faithful comparison rigorous
2. **Continuous DOM capture for agents** — rrweb recording between action boundaries, revealing the micro-interaction layer (scanning, hovering, hesitation) where interface-faithful behavior lives and opportunistic behavior is absent
3. **Multi-trial comparative analysis pipeline** — captures how humans vs. agents retry under failure, showing different recovery paradigms (interface-model adjustment vs. opportunistic re-targeting)

### Empirical contributions
4. **First study of learning curve dynamics** — showing that humans develop interface-faithful familiarity (spatial memory, layout expectations) while agents with memory develop faster opportunistic strategies but not interface awareness
5. **Behavioral divergence taxonomy** — characterizing where and how human and agent trajectories split, linking divergence patterns to UI design features (visual hierarchy, spatial layout, affordance visibility)
6. **Bridge between DOMSteer (in-situ UI assistance) and autonomous agents** — showing that DOMSteer-assisted humans produce trajectories that are more "teachable" to agents than unassisted human trajectories, because DOMSteer makes interface-faithful behavior more explicit and structured

### Training contributions
7. **RL-compatible human demonstration pipeline** — turning interface-faithful human trajectories into training signal that pushes agents from purely opportunistic toward interface-aware problem-solving, closing the behavioral gap without sacrificing efficiency

---

## Key Papers to Cite

- BrowserGym ecosystem (Chezelles et al., TMLR 2025)
- WorkArena (Drouin et al., ICML 2024)
- Online-Mind2Web (Xue et al., COLM 2025)
- WebCanvas (Pan et al., 2024)
- TEC (Zhang et al., 2026)
- ACuRL (Xue et al., 2026)
- WebAgent-R1 (2025)
- PolySkill (2025)
- AgentTrek (ICLR 2025 Spotlight)
- OpenEnv (Meta + HuggingFace, 2025)
- rrweb (open source)
- DOMSteer (your work, UIST 2026)