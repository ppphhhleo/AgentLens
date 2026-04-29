from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from agentlens.schemas import Trajectory


class SingleRunResult(BaseModel):
    """Result for one model x harness x task x seed x trial run."""

    trajectory: Trajectory
    score: float | None = None
    metrics: dict[str, float | int | bool | None] = Field(default_factory=dict)
    html: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    """Aggregated result for an AgentLens experiment."""

    experiment_id: str
    score: float | None = None
    metrics: dict[str, float | int | bool | None] = Field(default_factory=dict)
    run_results: list[SingleRunResult] = Field(default_factory=list)


class TaskEval(Protocol):
    """Callable evaluation unit, inspired by simple-evals' Eval interface."""

    def __call__(self) -> ExperimentResult:
        """Run the eval and return aggregate results."""

