"""Compare explicit output-guardrail wiring with declarative configuration."""

from __future__ import annotations

from jevantic import Jevaluator, Question
from jevantic.pydantic_ai import OutputGuardrail


def output_guardrail_before(evaluator: Jevaluator, condition: str) -> OutputGuardrail[None]:
    # clip: output-guardrail-before-start
    return OutputGuardrail(
        Question.noul(condition),
        evaluator=evaluator,
        accept=lambda _ctx, evaluation: evaluation.value.probability < 0.1,
    )
    # clip: output-guardrail-before-end


def output_guardrail_after(condition: str) -> OutputGuardrail[None]:
    # clip: output-guardrail-after-start
    return OutputGuardrail(block_if=condition, threshold=0.1)
    # clip: output-guardrail-after-end
