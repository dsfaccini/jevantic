"""Compare explicit and declarative Pydantic AI input guardrails."""

from __future__ import annotations

from jevantic import Jevaluator, Question
from jevantic.pydantic_ai import InputGuardrail


def input_guardrail_before(evaluator: Jevaluator, condition: str) -> InputGuardrail[None]:
    """Build an input guardrail with an explicit evaluator and decision policy."""
    # clip: input-guardrail-before-start
    return InputGuardrail(
        Question.noul(condition),
        evaluator=evaluator,
        accept=lambda _, evaluation: evaluation.value.probability < 0.1,
    )
    # clip: input-guardrail-before-end


def input_guardrail_after(condition: str) -> InputGuardrail[None]:
    """Build an input guardrail with its declarative blocking policy."""
    # clip: input-guardrail-after-start
    return InputGuardrail(block_if=condition, threshold=0.1)
    # clip: input-guardrail-after-end
