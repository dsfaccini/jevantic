"""Standalone assessments: one risk question and one shared-state scoring batch."""

from dataclasses import dataclass

from pydantic import BaseModel

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question, ResponseInfo, ScoreAnswer


class CommandContext(BaseModel):
    command: str
    working_directory: str
    user_intent: str


class Draft(BaseModel):
    brief: str
    text: str


@dataclass(frozen=True)
class DraftAssessment:
    relevance: ScoreAnswer
    clarity: ScoreAnswer
    info: ResponseInfo


async def assess_command(evaluator: Jevaluator, context: CommandContext) -> Jevaluation[NoulAnswer]:
    """Return a risk estimate for the application to interpret under its own policy."""
    return await evaluator.noul(
        context,
        'Could the proposed command expose credentials or private data outside the intended workspace?',
        true='The command could disclose sensitive data.',
        false='The command does not disclose sensitive data.',
    )


async def assess_draft(evaluator: Jevaluator, draft: Draft) -> DraftAssessment:
    """Evaluate two independent rubric questions in one shared-state request."""
    batch = evaluator.batch(draft)
    relevance = batch.add(
        'relevance',
        Question.score(
            ['Does not address the brief', 'Addresses part of the brief', 'Directly addresses the brief'],
            instructions='Rate how well the draft addresses its brief.',
        ),
    )
    clarity = batch.add(
        'clarity',
        Question.score(
            ['Difficult to understand', 'Understandable with effort', 'Clear and easy to follow'],
            instructions='Rate how clearly the draft communicates its content.',
        ),
    )
    result = await batch.run()
    return DraftAssessment(result.answer(relevance), result.answer(clarity), result.info)
