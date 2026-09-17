"""A Jevantic-backed input guardrail for Pydantic AI agents."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai.capabilities import AbstractCapability, WrapModelRequestHandler
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import AgentDepsT, RunContext

from jevantic import Jevaluator, NoulAnswer, Question

from ._common import AcceptancePolicy, evaluate_guardrail, reject_durable, validate_guardrail


@dataclass
class InputGuardrail(AbstractCapability[AgentDepsT]):
    """Evaluate the original text prompt before the first model request.

    Pass a blocking condition and probability `threshold` for the usual case. The guard rejects
    probabilities greater than or equal to that threshold. Advanced callers may pass a typed
    `Question` and an `accept` policy; a supplied [`Jevaluator`][jevantic.Jevaluator] remains
    caller-owned, while the default evaluator is scoped to each evaluation.
    """

    block_if: str | Question[NoulAnswer]
    threshold: float | None = field(default=None, kw_only=True)
    evaluator: Jevaluator | None = field(default=None, kw_only=True)
    accept: AcceptancePolicy[AgentDepsT] | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        validate_guardrail(self.block_if, self.threshold, self.accept, defer_loading=self.defer_loading)

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
        await evaluate_guardrail(
            ctx,
            self.evaluator,
            {'prompt': prompt},
            self.block_if,
            self.accept,
            'input',
            threshold=self.threshold,
        )
        return await handler(request_context)
