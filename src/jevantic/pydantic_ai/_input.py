"""A Jevantic-backed input guardrail for Pydantic AI agents."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai.capabilities import AbstractCapability, WrapModelRequestHandler
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import AgentDepsT, RunContext

from jevantic import Jevaluator, NoulAnswer, Question

from ._common import AcceptancePolicy, evaluate_guardrail, reject_durable


@dataclass
class InputGuardrail(AbstractCapability[AgentDepsT]):
    """Evaluate the original text prompt before the first model request.

    The caller owns the supplied [`Jevaluator`][jevantic.Jevaluator]. Its `accept` policy receives
    the typed Jev evaluation and returns a bare `bool`; returning `False` raises
    [`GuardrailRejected`][jevantic.pydantic_ai.GuardrailRejected] before the primary model runs.
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

    async def before_run(self, ctx: RunContext[AgentDepsT]) -> None:
        """Reject unsupported run contexts before an evaluator request begins."""
        reject_durable(ctx)

    async def wrap_model_request(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        request_context: ModelRequestContext,
        handler: WrapModelRequestHandler,
    ) -> ModelResponse:
        """Evaluate exactly the first request, then invoke the wrapped model request."""
        if ctx.run_step != 1:
            return await handler(request_context)

        prompt = ctx.prompt
        if not isinstance(prompt, str):
            raise UserError('`InputGuardrail` requires the original user prompt to be plain text.')
        await evaluate_guardrail(ctx, self.evaluator, {'prompt': prompt}, self.question, self.accept, 'input')
        return await handler(request_context)
