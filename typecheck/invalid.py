"""Negative static fixtures; each marked expression must fail strict checking."""

from jevantic import Evaluator, Question, ScoreAnswer


async def invalid_calls(evaluator: Evaluator) -> None:
    result = await evaluator.evaluate('state', Question.noul())
    wrong: ScoreAnswer = result.value  # expect: reportAssignmentType
    print(wrong)
    print(result.value.selected)  # expect: reportAttributeAccessIssue
    await evaluator.evaluate(42, Question.noul())  # expect: reportArgumentType
    Question.choice({1: None})  # expect: reportArgumentType
    Question.select([object()])  # expect: reportArgumentType
    await evaluator.evaluate_many(['one'], Question.noul(), concurrency='two')  # expect: reportArgumentType
