"""Negative static fixtures; each marked expression must fail strict checking."""

from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question, ScoreAnswer
from jevantic.pydantic_ai import InputGuardrail, OutputGuardrail


async def invalid_calls(evaluator: Jevaluator) -> None:
    result = await evaluator.evaluate('state', Question.noul())
    wrong: ScoreAnswer = result.value  # expect: reportAssignmentType
    print(wrong)
    print(result.value.selected)  # expect: reportAttributeAccessIssue
    await evaluator.evaluate(42, Question.noul())  # expect: reportArgumentType
    Question.choice({1: None})  # expect: reportArgumentType
    Question.select([object()])  # expect: reportArgumentType
    await evaluator.evaluate_many(['one'], Question.noul(), concurrency='two')  # expect: reportArgumentType


def accepts_text(ctx: RunContext[str], evaluation: Jevaluation[NoulAnswer]) -> bool:
    return evaluation.value.probability < len(ctx.deps)


def invalid_policy(ctx: RunContext[str], evaluation: Jevaluation[NoulAnswer]) -> str:
    return f'{ctx.deps}: {evaluation.value.probability}'


def invalid_guardrails(evaluator: Jevaluator) -> None:
    InputGuardrail(evaluator, Question.score(['poor', 'good']), accept=accepts_text)  # expect: reportArgumentType
    OutputGuardrail(evaluator, Question.choice({'a': None}), accept=accepts_text)  # expect: reportArgumentType
    InputGuardrail(evaluator, Question.noul(), accept=invalid_policy)  # expect: reportArgumentType
    OutputGuardrail[int](evaluator, Question.noul(), accept=accepts_text)  # expect: reportArgumentType
