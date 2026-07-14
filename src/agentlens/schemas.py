from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolHarnessTier(StrEnum):
    HUMAN = "human"
    BROWSER_ONLY = "browser_only"
    BROWSER_FILES = "browser_files"
    FULL_SANDBOX = "full_sandbox"
    NO_GUI_TOOL_ONLY = "no_gui_tool_only"


class MemoryScope(StrEnum):
    NONE = "none"
    IN_TASK = "in_task"
    CROSS_TRIAL = "cross_trial"
    CROSS_TASK_SAME_SITE = "cross_task_same_site"
    CROSS_BENCHMARK = "cross_benchmark"


class TrajectoryEventType(StrEnum):
    BROWSER_OBSERVATION = "browser_observation"
    BROWSER_ACTION = "browser_action"
    MODEL_MESSAGE = "model_message"
    TOOL_CALL = "tool_call"
    FILE_EDIT = "file_edit"
    SHELL_COMMAND = "shell_command"
    SCREENSHOT = "screenshot"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    VALIDATION_EVENT = "validation_event"
    ARTIFACT_CREATED = "artifact_created"
    USER_FEEDBACK = "user_feedback"
    GATING_VIOLATION = "gating_violation"
    SESSION_BOUNDARY = "session_boundary"
    USER_INTERVENTION = "user_intervention"


class UserActionType(StrEnum):
    NO_INTERVENTION = "no_intervention"
    ACCEPT = "accept"
    REJECT = "reject"
    SEND_MESSAGE = "send_message"
    REQUEST_CLARIFICATION = "request_clarification"


class ModelConfig(BaseModel):
    id: str
    provider: str
    name: str
    auth_mode: Literal["api_key", "codex_oauth"] | None = None
    temperature: float = 0.1
    vision: bool = False
    context_window: int | None = None
    max_output_tokens: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ToolHarnessConfig(BaseModel):
    id: str
    runner: Literal[
        "agentlab",
        "browsergym_direct",
        "browsergym_bridge",
        "screenshot_react",
        "desktop_react",
        "agencybench",
        "cocoabench",
        "human",
        "custom",
        "workflow_gym",
        "arb_judge",
    ]
    tier: ToolHarnessTier
    tools: list[str] = Field(default_factory=list)
    prompt_version: str = "v1"
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_no_gui_tier(self) -> ToolHarnessConfig:
        if self.tier != ToolHarnessTier.NO_GUI_TOOL_ONLY:
            return self

        gui_tools = [
            tool
            for tool in self.tools
            if tool.startswith("browser.") or tool.startswith("desktop.")
        ]
        if gui_tools:
            raise ValueError(
                "tier 'no_gui_tool_only' must not expose browser.* or desktop.* tools: "
                f"{gui_tools}"
            )

        input_modes = self.extra.get("input_modes")
        if not isinstance(input_modes, list) or not input_modes:
            raise ValueError(
                "tier 'no_gui_tool_only' must set extra.input_modes to non-visual modes "
                "such as ['axtree']"
            )

        visual_modes = sorted(
            str(mode) for mode in input_modes if str(mode) in {"screenshot", "set_of_marks"}
        )
        if visual_modes:
            raise ValueError(
                "tier 'no_gui_tool_only' must not expose visual input modes: "
                f"{visual_modes}"
            )
        return self


class MemoryHarnessConfig(BaseModel):
    id: str
    kind: Literal[
        "none",
        "short_context",
        "sliding_window",
        "summary_memory",
        "episodic_trace_memory",
        "semantic_vector_memory",
        "workflow_memory",
        "curriculum_memory",
    ]
    scope: MemoryScope = MemoryScope.NONE
    read_policy: str | None = None
    write_policy: str | None = None
    max_items: int | None = None
    storage: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_none_scope(self) -> MemoryHarnessConfig:
        if self.kind == "none" and self.scope != MemoryScope.NONE:
            raise ValueError("memory kind 'none' must use scope 'none'")
        return self


class UserHarnessConfig(BaseModel):
    """Optional user-side actor that observes the agent and intervenes.

    When a `RunConfig.user_harness` references one of these, the adapter
    runs the agent loop as usual, then dispatches to a UserActor (LLM-
    driven for now; CLI / VNC for human runners later). The user's
    `accept` / `reject` / `send_message` decision is recorded as a
    `USER_INTERVENTION` trajectory event and (depending on policy) can
    influence the run's success / score.

    `mode` controls which UserActor implementation is built:
      - none                    : no-op (used for default single-actor runs)
      - simulated_final_judge   : LLM-driven judge that intervenes once,
                                  on the agent's final_answer

    `model` references a ModelConfig.id (the LLM driving the user actor).
    `tools` is the allow-list of user actions (`user.accept`, etc.) the
    actor may emit — same gating contract as agent tools, separate map.
    """

    id: str
    mode: Literal["none", "simulated_final_judge", "simulated_dialogue"] = "none"
    model: str | None = None
    tools: list[str] = Field(default_factory=list)
    persona: str | None = None
    intervention_policy: Literal["final_only", "every_turn"] = "final_only"
    combine_with_validator: Literal["and", "override", "annotate_only"] = "annotate_only"
    max_turns: int = 1                  # 1 for final_judge; >1 for dialogue
    extra: dict[str, Any] = Field(default_factory=dict)


class TaskConfig(BaseModel):
    id: str
    benchmark: Literal[
        "browsergym",
        "agentlab",
        "agencybench",
        "domsteer",
        "online_mind2web",
        "the_agent_company",
        "cocoabench",
        "workflow_gym",
        "arb",
        "gui_vs_cli",
        "custom",
    ]
    task_id: str
    goal: str | None = None
    start_url: str | None = None
    capability_required: list[str] = Field(default_factory=list)
    validator: str | None = None
    expected_answer: str | None = None
    answer_validator: (
        Literal[
            "exact",
            "contains",
            "number_exact",
            "url_contains",
            "webjudge",
            "cocoabench_test_py",
            "arb_judge",
            "semantic_pending",
            "manual_pending",
        ]
        | None
    ) = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    id: str
    model: str
    tool_harness: str
    memory_harness: str
    task: str
    user_harness: str | None = None  # references UserHarnessConfig.id; None = single-actor
    seeds: list[int] = Field(default_factory=lambda: [0])
    trials: int = 1
    max_steps: int | None = None
    output_dir: Path = Path("runs")
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> RunConfig:
        if not self.seeds:
            raise ValueError("run must include at least one seed")
        if self.trials < 1:
            raise ValueError("trials must be >= 1")
        return self


class ExperimentConfig(BaseModel):
    schema_version: str = "0.1"
    id: str
    description: str | None = None
    models: list[ModelConfig]
    tool_harnesses: list[ToolHarnessConfig]
    memory_harnesses: list[MemoryHarnessConfig]
    user_harnesses: list[UserHarnessConfig] = Field(default_factory=list)
    task_files: list[Path] = Field(default_factory=list)
    tasks: list[TaskConfig]
    runs: list[RunConfig]

    @model_validator(mode="after")
    def validate_references(self) -> ExperimentConfig:
        model_ids = {item.id for item in self.models}
        tool_harness_ids = {item.id for item in self.tool_harnesses}
        memory_harness_ids = {item.id for item in self.memory_harnesses}
        user_harness_ids = {item.id for item in self.user_harnesses}
        task_ids = {item.id for item in self.tasks}

        # User harnesses must reference a known model when mode != "none".
        for uh in self.user_harnesses:
            if uh.mode != "none" and uh.model and uh.model not in model_ids:
                raise ValueError(
                    f"user harness '{uh.id}' references unknown model '{uh.model}'"
                )

        for run in self.runs:
            if run.model not in model_ids:
                raise ValueError(f"run '{run.id}' references unknown model '{run.model}'")
            if run.tool_harness not in tool_harness_ids:
                raise ValueError(
                    f"run '{run.id}' references unknown tool harness '{run.tool_harness}'"
                )
            if run.memory_harness not in memory_harness_ids:
                raise ValueError(
                    f"run '{run.id}' references unknown memory harness '{run.memory_harness}'"
                )
            if run.user_harness is not None and run.user_harness not in user_harness_ids:
                raise ValueError(
                    f"run '{run.id}' references unknown user harness '{run.user_harness}'"
                )
            if run.task not in task_ids:
                raise ValueError(f"run '{run.id}' references unknown task '{run.task}'")

        return self


class TrajectoryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: TrajectoryEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    step_index: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: list[Path] = Field(default_factory=list)


class RunMetrics(BaseModel):
    success: bool | None = None
    score: float | None = None
    duration_ms: int | None = None
    steps: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None
    tool_calls: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Trajectory(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    trajectory_id: str = Field(default_factory=lambda: str(uuid4()))
    experiment_id: str
    run_id: str
    seed: int
    trial: int
    model: ModelConfig
    tool_harness: ToolHarnessConfig
    memory_harness: MemoryHarnessConfig
    task: TaskConfig
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    events: list[TrajectoryEvent] = Field(default_factory=list)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    raw_result_path: Path | None = None
    artifact_dir: Path | None = None


def load_experiment_config(path: Path) -> ExperimentConfig:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"expected mapping at top level of {path}")

    task_files = data.get("task_files") or []
    if task_files:
        tasks = list(data.get("tasks") or [])
        for task_file in task_files:
            task_path = _resolve_include_path(Path(task_file), config_path=path)
            with task_path.open("r", encoding="utf-8") as file:
                task_data = yaml.safe_load(file)
            if isinstance(task_data, list):
                tasks.extend(task_data)
            elif isinstance(task_data, dict):
                tasks.append(task_data)
            else:
                raise ValueError(f"expected task mapping or list in {task_path}")
        data = {**data, "tasks": tasks}

    return ExperimentConfig.model_validate(data)


def _resolve_include_path(include_path: Path, *, config_path: Path) -> Path:
    if include_path.is_absolute() and include_path.exists():
        return include_path
    if include_path.exists():
        return include_path
    candidate = config_path.parent / include_path
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"could not resolve include path '{include_path}' from {config_path}")
