"""A Jevantic-backed output guardrail for Pydantic AI agents."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai import AgentRunResult
from pydantic_ai.capabilities import AbstractCapability, CapabilityOrdering
from pydantic_ai.exceptions import UserError
from pydantic_ai.tools import AgentDepsT, RunContext

from jevantic import Jevaluator, NoulAnswer, Question

from ._common import AcceptancePolicy, evaluate_guardrail, reject_durable


@dataclass
class OutputGuardrail(AbstractCapability[AgentDepsT]):
    """Evaluate complete text output before [`Agent.run`][pydantic_ai.Agent.run] returns.

    The caller owns the supplied [`Jevaluator`][jevantic.Jevaluator]. Its `accept` policy receives
    the typed Jev evaluation and returns a bare `bool`; returning `False` raises
    [`GuardrailRejected`][jevantic.pydantic_ai.GuardrailRejected].

    Streaming consumers can receive partial and complete output before this check rejects the run.
    The guardrail also runs after output functions, so it cannot prevent their side effects.
    Place it before other outermost capabilities that change the final result.
    """

    evaluator: Jevaluator
    question: Question[NoulAnswer]
    accept: AcceptancePolicy[AgentDepsT] = field(kw_only=True)

    def __post_init__(self) -> None:
        if self.defer_loading:
            raise UserError('Jevantic guardrails cannot use deferred loading.')

    @classmethod
    def get_serialization_name(cls) -> None:
        """Exclude callback- and client-bearing guardrails from agent specs."""
        return None

    def get_ordering(self) -> CapabilityOrdering:
        """Check the result after ordinary capabilities finish transforming it."""
        return CapabilityOrdering(position='outermost')

    async def before_run(self, ctx: RunContext[AgentDepsT]) -> None:
        """Reject unsupported run contexts before an evaluator request begins."""
        reject_durable(ctx)

    async def after_run(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        result: AgentRunResult[object],
    ) -> AgentRunResult[object]:
        """Evaluate the completed result without changing its output or metadata."""
        output = result.output
        if not isinstance(output, str):
            raise UserError('`OutputGuardrail` requires the final output to be plain text.')
        await evaluate_guardrail(ctx, self.evaluator, {'output': output}, self.question, self.accept, 'output')
        return result
