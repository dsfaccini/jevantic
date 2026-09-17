from typing import assert_type

from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question
from jevantic.pydantic_ai import GuardrailRejected, OutputGuardrail


async def accepts_text(ctx: RunContext[str], evaluation: Jevaluation[NoulAnswer]) -> bool:
    assert_type(ctx.deps, str)
    assert_type(evaluation.value, NoulAnswer)
    return evaluation.value.probability < 0.5


def build_guardrail(evaluator: Jevaluator) -> OutputGuardrail[str]:
    guardrail = OutputGuardrail(
        evaluator,
        Question.noul('Could this response disclose private data?'),
        accept=accepts_text,
    )
    assert_type(guardrail, OutputGuardrail[str])
    return guardrail


def inspect_rejection(error: GuardrailRejected) -> None:
    assert_type(error.evaluation, Jevaluation[NoulAnswer])
