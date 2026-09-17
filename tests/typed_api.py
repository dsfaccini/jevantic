"""Strict type assertions for complete public-interface call sites."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, assert_type

from jevantic import (
    ChoiceAnswer,
    Handle,
    Jevaluation,
    Jevaluator,
    JsonContent,
    NoulAnswer,
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


async def typed_workflows(evaluator: Jevaluator, candidates: list[Candidate]) -> None:
    routes: dict[Route, JsonContent | None] = {'allow': None, 'block': None}
    teams: dict[Team, JsonContent | None] = {Team.SUPPORT: None, Team.ENGINEERING: None}
    risk_question = Question.noul('Could this expose a secret?')
    assert_type(risk_question, Question[NoulAnswer])
    direct = await evaluator.evaluate('state', risk_question)
    assert_type(direct, Jevaluation[NoulAnswer])
    assert_type(direct.value.probability, float)
    many = await evaluator.evaluate_many(['one', 'two'], Question.choice(teams), concurrency=2)
    assert_type(many, list[Jevaluation[ChoiceAnswer[Team]]])
    assert_type(many[0].value.selected, Team)

    batch = evaluator.batch('state')
    risk = batch.add('risk', risk_question)
    route = batch.add('route', Question.choice(routes))
    team = batch.add('team', Question.choice(teams))
    score = batch.add('score', Question.score(['low', 'high']))
    candidate = batch.add('candidate', Question.select(candidates))
    assert_type(risk, Handle[NoulAnswer])
    result = await batch.run()
    assert_type(result.answer(risk), NoulAnswer)
    assert_type(result.answer(route), ChoiceAnswer[Route])
    assert_type(result.answer(route).selected, Route)
    assert_type(result.answer(route).distribution[0].value, Route)
    assert_type(result.answer(team).selected, Team)
    assert_type(result.answer(score), ScoreAnswer)
    assert_type(result.answer(candidate).selected, Candidate)

    single_risk = await evaluator.noul('state', 'Could this expose a secret?')
    assert_type(single_risk, Jevaluation[NoulAnswer])
    single_team = await evaluator.choice('state', Team)
    assert_type(single_team, Jevaluation[ChoiceAnswer[Team]])
    typed_routes: list[Route] = ['allow', 'block']
    single_route = await evaluator.choice('state', typed_routes)
    assert_type(single_route.value.selected, Route)
    assert_type(Question.choice(Team), Question[ChoiceAnswer[Team]])
    assert_type(Question.choice(typed_routes), Question[ChoiceAnswer[Route]])
    single_score = await evaluator.score('state', ['low', 'high'])
    assert_type(single_score, Jevaluation[ScoreAnswer])
    single_candidate = await evaluator.select('state', candidates)
    assert_type(single_candidate, Jevaluation[ChoiceAnswer[Candidate]])
    projected = await evaluator.select(
        'state', candidates, key=lambda item: item.identifier, describe=lambda item: item.identifier
    )
    assert_type(projected.value.selected, Candidate)
    structured_state = await evaluator.noul(Candidate('example'), 'Ready?')
    assert_type(structured_state, Jevaluation[NoulAnswer])
