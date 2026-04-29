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


class ModelConfig(BaseModel):
    id: str
    provider: str
    name: str
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
        "agencybench",
        "cocoabench",
        "human",
        "custom",
    ]
    tier: ToolHarnessTier
    tools: list[str] = Field(default_factory=list)
    prompt_version: str = "v1"
    extra: dict[str, Any] = Field(default_factory=dict)


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


class TaskConfig(BaseModel):
    id: str
    benchmark: Literal[
        "browsergym",
        "agentlab",
        "agencybench",
        "domsteer",
        "online_mind2web",
        "cocoabench",
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
            "url_contains",
            "webjudge",
            "cocoabench_test_py",
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
    seeds: list[int] = Field(default_factory=lambda: [0])
    trials: int = 1
    max_steps: int | None = None
    output_dir: Path = Path("agentlens_results")
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
    tasks: list[TaskConfig]
    runs: list[RunConfig]

    @model_validator(mode="after")
    def validate_references(self) -> ExperimentConfig:
        model_ids = {item.id for item in self.models}
        tool_harness_ids = {item.id for item in self.tool_harnesses}
        memory_harness_ids = {item.id for item in self.memory_harnesses}
        task_ids = {item.id for item in self.tasks}

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

    return ExperimentConfig.model_validate(data)
