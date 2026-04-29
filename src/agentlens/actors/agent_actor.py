"""AgentActor — the agent-side counterpart of UserActor.

Mirrors tau2-bench's two-method pattern (`get_init_state` + `act`) so the
orchestrator can swap between agent implementations (screenshot ReAct,
function-calling, future DOM-ReAct, future Human-as-agent for control
studies) without knowing anything about Playwright, OpenAI, screenshots,
or sandboxes.

Key differences from tau2 (intentional):
  - We do NOT use a universal text Message type. Our agents emit
    coordinate-based ComputerActions over screenshots, plus tool calls
    (web_search/run_python/etc.). We keep AgentObservation / AgentResponse
    distinct from UserAction so each side is typed correctly.
  - We do NOT model Environment as a 3rd participant. The browser/sandbox
    state is mutated in place by agent actions; the adapter owns those
    resources and passes them into the agent at construction.

The orchestrator only ever calls `agent_actor.act(observation, state)`
and `agent_actor.get_init_state(observation)`. It never reaches into
Playwright, OpenAI, or any per-agent specifics.
"""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from agentlens.models.base import ModelStep
from agentlens.schemas import TrajectoryEvent


class AgentState(BaseModel):
    """Typed agent state — passed in/out explicitly per turn.

    The orchestrator calls `agent.get_init_state(observation)` once at
    the start of a run, then `agent.act(observation, state)` each turn.
    The returned state carries forward.
    """

    cumulative_user_messages: list[str] = Field(default_factory=list)
    # Per-step decisions made so far in this run (across all turns).
    # Useful for prompt construction and post-hoc analysis.
    history: list[ModelStep] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class AgentObservation(BaseModel):
    """What the orchestrator hands the agent at the start of each turn.

    The protocol stays generic — agent-specific resources (screenshot
    paths, sandbox handles, model wrappers) go in `extra`. A future
    DOMReactAgent would consume DOM/AXTree from extra; a HumanAgent
    might consume a CLI prompt callback.
    """

    task_goal: str
    user_messages: list[str] = Field(default_factory=list)
    turn_index: int = 1
    max_turns: int = 1
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """What the agent returns each turn."""

    answer: str | None = None
    events: list[TrajectoryEvent] = Field(default_factory=list)
    state: AgentState
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class AgentActor(Protocol):
    """Symmetric to UserActor on the user side."""

    def get_init_state(self, *, observation: AgentObservation) -> AgentState: ...

    def act(
        self,
        *,
        observation: AgentObservation,
        state: AgentState,
    ) -> AgentResponse: ...


class OpenAIConfigMixin(BaseModel):
    """Reusable LLM-config block — borrows tau2's LLMConfigMixin pattern.

    Concrete agents that wrap an OpenAI-style model can compose this in
    via Pydantic inheritance, keeping LLM specifics out of the actor
    contract.
    """

    model_name: str
    temperature: float = 0.0
    max_output_tokens: int | None = None

    model_config = {"arbitrary_types_allowed": True}
