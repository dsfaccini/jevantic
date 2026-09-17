"""Shared types for Jevantic Pydantic AI capabilities."""

from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

import typesafe_sdk
from pydantic import BaseModel
from pydantic_ai import CapabilityEvent
from pydantic_ai.capabilities import AbstractCapability, CombinedCapability, WrapperCapability
from pydantic_ai.exceptions import UserError
from pydantic_ai.tools import AgentDepsT, RunContext

from jevantic import Jevaluation, Jevaluator, JsonContent, NoulAnswer, Question

type GuardrailStage = Literal['input', 'output', 'tool']
type AcceptancePolicy[DepsT] = Callable[[RunContext[DepsT], Jevaluation[NoulAnswer]], bool | Awaitable[bool]]


@dataclass(kw_only=True)
class GuardrailEvaluated(CapabilityEvent, namespace='jevantic', name='guardrail_evaluated', dispatch='immediate'):
    """Record the non-content result of a Jevantic guardrail evaluation."""

    stage: GuardrailStage
    accepted: bool
    probability: float
    requested_model: str
    model: str
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None


class GuardrailRejected(Exception):
    """A guardrail rejected an evaluation before the protected operation ran."""

    stage: GuardrailStage
    evaluation: Jevaluation[NoulAnswer]
    tool_name: str | None
    tool_call_id: str | None

    def __init__(
        self,
        stage: GuardrailStage,
        evaluation: Jevaluation[NoulAnswer],
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        self.stage = stage
        self.evaluation = evaluation
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id
        super().__init__('Jevantic guardrail rejected the evaluation.')


def validate_guardrail[DepsT](
    block_if: str | Question[NoulAnswer],
    threshold: float | None,
    accept: AcceptancePolicy[DepsT] | None,
    *,
    defer_loading: bool,
) -> None:
    """Validate a blocking condition and one explicit decision policy before I/O."""
    if defer_loading:
        raise UserError('Jevantic guardrails cannot use deferred loading.')
    if isinstance(block_if, str):
        if not block_if.strip():
            raise UserError('A guardrail needs a nonempty blocking condition.')
    elif not isinstance(block_if.to_request(), typesafe_sdk.Noul):
        raise UserError('A guardrail requires a Noul question.')
    if (threshold is None) == (accept is None):
        raise UserError('Set exactly one of threshold or accept for the guardrail.')
    if threshold is not None and (
        isinstance(threshold, bool) or not math.isfinite(threshold) or not 0 <= threshold <= 1
    ):
        raise UserError('The guardrail threshold must be a finite probability between zero and one.')


async def evaluate_guardrail[DepsT](
    ctx: RunContext[DepsT],
    evaluator: Jevaluator | None,
    state: JsonContent | BaseModel,
    block_if: str | Question[NoulAnswer],
    accept: AcceptancePolicy[DepsT] | None,
    stage: GuardrailStage,
    threshold: float | None = None,
) -> None:
    """Apply one guardrail policy and report the same evidence on every boundary."""
    question = Question.noul(block_if) if isinstance(block_if, str) else block_if
    if evaluator is None:
        async with Jevaluator() as owned:
            evaluation = await owned.evaluate(state, question)
    else:
        evaluation = await evaluator.evaluate(state, question)
    if accept is None:
        assert threshold is not None
        accepted = evaluation.value.probability < threshold
    else:
        accepted = accept(ctx, evaluation)
        if inspect.isawaitable(accepted):
            accepted = await accepted
        if type(accepted) is not bool:
            raise TypeError('The guardrail acceptance policy must return a bool.')

    await ctx.emit(
        GuardrailEvaluated(
            stage=stage,
            accepted=accepted,
            probability=evaluation.value.probability,
            requested_model=evaluation.info.requested_model,
            model=evaluation.info.model,
            request_id=evaluation.info.request_id,
            input_tokens=evaluation.info.usage.input_tokens,
            output_tokens=evaluation.info.usage.output_tokens,
        )
    )
    if not accepted:
        raise GuardrailRejected(stage, evaluation, tool_name=ctx.tool_name, tool_call_id=ctx.tool_call_id)


@runtime_checkable
class _Durability(Protocol):
    """The public shape needed to identify an active durable capability."""

    in_durable_context: bool


def reject_durable(ctx: RunContext[AgentDepsT]) -> None:
    """Reject evaluations running inside a replayable durable context."""
    pending: list[AbstractCapability[AgentDepsT]] = list(ctx.capabilities.values())
    while pending:
        capability = pending.pop()
        has_durability_base = any(
            base.__module__.startswith('pydantic_ai.durable_exec') for base in type(capability).__mro__
        )
        if has_durability_base and isinstance(capability, _Durability) and capability.in_durable_context:
            raise UserError(
                'Jevantic capabilities cannot run inside durable execution because their evaluations are not '
                'checkpointed. Run the agent outside the durable workflow or flow.'
            )
        # Wrappers register as proxies and can hide the durable leaf from the run registry.
        if isinstance(capability, WrapperCapability):
            pending.append(capability.wrapped)
        elif isinstance(capability, CombinedCapability):
            pending.extend(capability.capabilities)
