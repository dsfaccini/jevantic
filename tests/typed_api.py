"""Strict type assertions for complete public-interface call sites."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, assert_type

from jevantic import (
    ChoiceAnswer,
    Evaluation,
    Evaluator,
    Handle,
    JsonContent,
    NoulAnswer,
    Option,
    Question,
    ScoreAnswer,
)

Route = Literal['allow', 'block']


class Team(StrEnum):
    SUPPORT = 'support'
    ENGINEERING = 'engineering'


@dataclass
class Candidate:
    identifier: str


async def typed_workflows(evaluator: Evaluator, candidates: list[Candidate]) -> None:
    routes: dict[Route, JsonContent | None] = {'allow': None, 'block': None}
    teams: dict[Team, JsonContent | None] = {Team.SUPPORT: None, Team.ENGINEERING: None}
    risk_question = Question.noul('Could this expose a secret?')
    assert_type(risk_question, Question[NoulAnswer])
    direct = await evaluator.evaluate('state', risk_question)
    assert_type(direct, Evaluation[NoulAnswer])
    assert_type(direct.value.probability, float)

    batch = evaluator.batch('state')
    risk = batch.add('risk', risk_question)
    route = batch.add('route', Question.choice(routes))
    team = batch.add('team', Question.choice(teams))
    score = batch.add('score', Question.score(['low', 'high']))
    candidate = batch.add('candidate', Question.select(Option(item.identifier, item) for item in candidates))
    assert_type(risk, Handle[NoulAnswer])
    result = await batch.run()
    assert_type(result.answer(risk), NoulAnswer)
    assert_type(result.answer(route), ChoiceAnswer[Route])
    assert_type(result.answer(route).selected, Route)
    assert_type(result.answer(route).distribution[0].value, Route)
    assert_type(result.answer(team).selected, Team)
    assert_type(result.answer(score), ScoreAnswer)
    assert_type(result.answer(candidate).selected, Candidate)
