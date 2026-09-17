"""Complete comparisons between manual orchestration and Jevantic conveniences."""

from collections.abc import Iterable
from dataclasses import dataclass

import anyio
from pydantic import BaseModel

from jevantic import Jevaluation, Jevaluator, JsonContent, Option, Question


@dataclass(frozen=True)
class Candidate:
    """An application-owned candidate whose private data is never sent to Jev."""

    identifier: str
    summary: str
    private_note: str


CANDIDATE_INSTRUCTIONS = 'Select the candidate whose experience best matches the role requirements.'


async def select_candidate_before(
    evaluator: Jevaluator, state: JsonContent | BaseModel, candidates: Iterable[Candidate]
) -> Candidate:
    """Select a candidate by manually recovering its local object from a ``Choice`` label."""
    candidates_by_id: dict[str, Candidate] = {}
    for candidate in candidates:
        if candidate.identifier in candidates_by_id:
            raise ValueError('Candidate identifiers must be unique')
        candidates_by_id[candidate.identifier] = candidate
    # clip: choice-before-start
    question = Question.choice(
        {key: c.summary for key, c in candidates_by_id.items()},
        instructions=CANDIDATE_INSTRUCTIONS,
    )
    evaluation = await evaluator.evaluate(state, question)
    return candidates_by_id[evaluation.value.selected]
    # clip: choice-before-end


async def select_candidate_after(
    evaluator: Jevaluator, state: JsonContent | BaseModel, candidates: Iterable[Candidate]
) -> Candidate:
    """Select a candidate while Jevantic retains the original local object."""
    # clip: choice-after-start
    question = Question.select(
        (Option(c.identifier, c, c.summary) for c in candidates),
        instructions=CANDIDATE_INSTRUCTIONS,
    )
    evaluation = await evaluator.evaluate(state, question)
    return evaluation.value.selected
    # clip: choice-after-end


async def evaluate_many_before[AnswerT](
    evaluator: Jevaluator,
    states: Iterable[JsonContent | BaseModel],
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
    states: Iterable[JsonContent | BaseModel],
    question: Question[AnswerT],
    *,
    concurrency: int,
) -> list[Jevaluation[AnswerT]]:
    """Repeat one evaluation with Jevantic's bounded worker pool."""
    # clip: fanout-after-start
    return await evaluator.evaluate_many(states, question, concurrency=concurrency)
    # clip: fanout-after-end
