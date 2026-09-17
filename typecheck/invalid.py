"""Negative static fixtures; each marked expression must fail strict checking."""

from dataclasses import dataclass

from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question, ScoreAnswer
from jevantic.pydantic_ai import InputGuardrail, OutputGuardrail


@dataclass
class State:
    text: str


async def invalid_calls(evaluator: Jevaluator) -> None:
    result = await evaluator.evaluate('state', Question.noul())
    wrong: ScoreAnswer = result.value  # expect: reportAssignmentType
    print(wrong)
    print(result.value.selected)  # expect: reportAttributeAccessIssue
    await evaluator.evaluate(42, Question.noul())  # expect: reportArgumentType
    await evaluator.noul(State, 'Ready?')  # expect: reportArgumentType
    Question.choice({1: None})  # expect: reportArgumentType
    Question.select(['item'], key=lambda item: len(item))  # expect: reportArgumentType
    await evaluator.choice('state', [1, 2])  # expect: reportArgumentType
    await evaluator.select('state', ['item'], describe=lambda item: len(item))  # expect: reportArgumentType
    await evaluator.evaluate_many(['one'], Question.noul(), concurrency='two')  # expect: reportArgumentType


def accepts_text(ctx: RunContext[str], evaluation: Jevaluation[NoulAnswer]) -> bool:
    return evaluation.value.probability < len(ctx.deps)


def invalid_policy(ctx: RunContext[str], evaluation: Jevaluation[NoulAnswer]) -> str:
    return f'{ctx.deps}: {evaluation.value.probability}'


def invalid_guardrails(evaluator: Jevaluator) -> None:
    InputGuardrail(Question.score(['poor', 'good']), accept=accepts_text)  # expect: reportArgumentType
    OutputGuardrail(Question.choice({'a': None}), accept=accepts_text)  # expect: reportArgumentType
    InputGuardrail(Question.noul(), evaluator=evaluator, accept=invalid_policy)  # expect: reportArgumentType
    OutputGuardrail[int](Question.noul(), evaluator=evaluator, accept=accepts_text)  # expect: reportArgumentType
