"""Complete comparisons between manual orchestration and Jevantic conveniences."""

from collections.abc import Iterable
from dataclasses import dataclass, field

import anyio

from jevantic import Content, Jevaluation, Jevaluator, JsonContent, Question


@dataclass(frozen=True)
class Candidate:
    """An application-owned candidate whose private data is never sent to Jev."""

    identifier: str
    summary: str
    private_note: str = field(metadata={'exclude': True})


CANDIDATE_INSTRUCTIONS = 'Select the candidate whose experience best matches the role requirements.'


async def select_candidate_before(evaluator: Jevaluator, state: Content, candidates: Iterable[Candidate]) -> Candidate:
    """Select a candidate by manually recovering its local object from a ``Choice`` label."""
    # clip: choice-before-start
    by_key: dict[str, Candidate] = {str(index): candidate for index, candidate in enumerate(candidates)}
    criteria: dict[str, JsonContent | None] = {
        key: {'identifier': c.identifier, 'summary': c.summary} for key, c in by_key.items()
    }
    question = Question.choice(criteria, instructions=CANDIDATE_INSTRUCTIONS)
    evaluation = await evaluator.evaluate(state, question)
    return by_key[evaluation.value.selected]
    # clip: choice-before-end


async def select_candidate_after(evaluator: Jevaluator, state: Content, candidates: Iterable[Candidate]) -> Candidate:
    """Select a candidate while Jevantic retains the original local object."""
    # clip: choice-after-start
    evaluation = await evaluator.select(state, candidates, instructions=CANDIDATE_INSTRUCTIONS)
    return evaluation.value.selected
    # clip: choice-after-end


async def evaluate_many_before[AnswerT](
    evaluator: Jevaluator,
    states: Iterable[Content],
    question: Question[AnswerT],
    *,
    concurrency: int,
) -> list[Jevaluation[AnswerT]]:
    """Repeat one evaluation with a caller-managed bounded worker pool."""
    worker_slots = range(concurrency)
    if isinstance(concurrency, bool) or concurrency < 1:
        raise ValueError('Concurrency must be a positive integer')
    results: dict[int, Jevaluation[AnswerT]] = {}

    async def worker() -> None:
        for index, state in inputs:
            try:
                results[index] = await evaluator.evaluate(state, question)
            except Exception as error:
                error.add_note(f'Jevantic input index: {index}')
                raise

    # clip: fanout-before-start
    async with anyio.create_task_group() as group:
        inputs = enumerate(states)
        for _ in worker_slots:
            group.start_soon(worker)
    return [results[index] for index in range(len(results))]
    # clip: fanout-before-end


async def evaluate_many_after[AnswerT](
    evaluator: Jevaluator,
    states: Iterable[Content],
    question: Question[AnswerT],
    *,
    concurrency: int,
) -> list[Jevaluation[AnswerT]]:
    """Repeat one evaluation with Jevantic's bounded worker pool."""
    # clip: fanout-after-start
    return await evaluator.evaluate_many(states, question, concurrency=concurrency)
    # clip: fanout-after-end
