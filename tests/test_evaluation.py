import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import httpx2
import pytest
import typesafe_sdk
from conftest import Backend
from pydantic import BaseModel, JsonValue, ValidationError

from jevantic import (
    ChoiceAnswer,
    ChoiceProbability,
    Handle,
    Jevaluator,
    JsonContent,
    NoulAnswer,
    Question,
    QuestionError,
    ResponseValidationError,
    ScoreAnswer,
    Usage,
)


class Team(StrEnum):
    SUPPORT = 'support'
    ENGINEERING = 'engineering'


@dataclass
class Candidate:
    identifier: str
    private_value: str


async def test_mixed_batch_preserves_types_values_and_request_shape(backend: Backend) -> None:
    backend.respond(
        {
            'risk': {'type': 'noul', 'noul': 0.04},
            'team': {
                'type': 'choice',
                'choice': 'support',
                'probabilities': {'engineering': 0.25, 'support': 0.75},
                'confidence': 0.6,
            },
            'candidate': {
                'type': 'choice',
                'choice': 'b',
                'probabilities': {'b': 0.8, 'a': 0.2},
                'confidence': 0.7,
            },
            'relevance': {
                'type': 'score',
                'score': 1.75,
                'legend': {'0': 'unrelated', '1': 'partly related', '2': 'directly related'},
                'probabilities': {'0': 0.0, '1': 0.25, '2': 0.75},
                'confidence': 0.6,
            },
        }
    )
    candidates: list[Candidate] = [Candidate('a', 'local-a'), Candidate('b', 'local-b')]
    teams: dict[Team, JsonContent | None] = {Team.SUPPORT: 'Customer help', Team.ENGINEERING: None}
    evaluator = Jevaluator(client=backend.client, model='jev-request-alias')
    batch = evaluator.batch({'document': 'example'})
    risk = batch.add('risk', Question.noul('Could this expose a secret?', true='Yes', false='No'))
    team = batch.add('team', Question.choice(teams, instructions='Which team should handle this?'))
    candidate = batch.add(
        'candidate',
        Question.select(candidates, key=lambda item: item.identifier, describe=lambda item: item.identifier),
    )
    relevance = batch.add(
        'relevance', Question.score(['unrelated', 'partly related', 'directly related'], instructions='Rate relevance')
    )
    result = await batch.run()
    assert result.answer(risk) == NoulAnswer(0.04)
    assert result.answer(team) == ChoiceAnswer(
        selected=Team.SUPPORT,
        selected_key='support',
        distribution=(
            ChoiceProbability('support', Team.SUPPORT, 0.75),
            ChoiceProbability('engineering', Team.ENGINEERING, 0.25),
        ),
        confidence=0.6,
    )
    assert result.answer(candidate).selected is candidates[1]
    assert result.answer(relevance) == ScoreAnswer(
        score=1.75,
        probabilities={0: 0.0, 1: 0.25, 2: 0.75},
        legend={0: 'unrelated', 1: 'partly related', 2: 'directly related'},
        confidence=0.6,
    )
    assert (result.info.model, result.info.requested_model, result.info.request_id, result.info.usage) == (
        'jev-fixture-version',
        'jev-request-alias',
        'fixture-request',
        Usage(input_tokens=12, output_tokens=4),
    )
    assert backend.transport.requests == [
        {
            'model': 'jev-request-alias',
            'state': {'document': 'example'},
            'questions': {
                'risk': {
                    'type': 'noul',
                    'instructions': 'Could this expose a secret?',
                    'criteria': {'true': 'Yes', 'false': 'No'},
                },
                'team': {
                    'type': 'choice',
                    'instructions': 'Which team should handle this?',
                    'criteria': {'support': 'Customer help', 'engineering': None},
                },
                'candidate': {'type': 'choice', 'criteria': {'a': 'a', 'b': 'b'}},
                'relevance': {
                    'type': 'score',
                    'instructions': 'Rate relevance',
                    'criteria': ['unrelated', 'partly related', 'directly related'],
                },
            },
        }
    ]


async def test_single_question_and_unknown_usage(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.8}}, usage={})
    evaluator = Jevaluator(client=backend.client)
    result = await evaluator.evaluate('state', Question.noul())
    assert result.value == NoulAnswer(0.8)
    assert result.info.usage == Usage(None, None)
    assert result.info.requested_model == 'jev-sdk-default'
    assert result.info.raw_http_response.status_code == 200


class InputRecord(BaseModel):
    text: str
    labels: list[str]


async def test_state_and_question_definitions_are_snapshotted(backend: Backend) -> None:
    state = InputRecord(text='original', labels=['first'])
    instructions: dict[str, JsonValue] = {'question': 'original', 'examples': ['one']}
    level: dict[str, JsonValue] = {'meaning': 'low'}
    criteria: list[JsonContent] = [level, 'high']
    question = Question.score(criteria, instructions=instructions)
    evaluator = Jevaluator(client=backend.client)
    batch = evaluator.batch(state)
    handle = batch.add('q', question)
    state.text = 'changed'
    state.labels.append('later')
    instructions['question'] = 'changed'
    level['meaning'] = 'changed'
    criteria.append('extra')
    backend.respond(
        {
            'q': {
                'type': 'score',
                'score': 0.3,
                'probabilities': {'0': 0.7, '1': 0.3},
                'legend': {'0': {'meaning': 'low'}, '1': 'high'},
                'confidence': 0.4,
            }
        }
    )
    result = await batch.run()
    assert result.answer(handle).legend == {0: {'meaning': 'low'}, 1: 'high'}
    assert backend.transport.requests[0]['state'] == {'text': 'original', 'labels': ['first']}
    assert backend.transport.requests[0]['questions'] == {
        'q': {
            'type': 'score',
            'criteria': [{'meaning': 'low'}, 'high'],
            'instructions': {'question': 'original', 'examples': ['one']},
        }
    }


async def test_tuple_content_matches_its_json_array_legend(backend: Backend) -> None:
    backend.respond(
        {
            'answer': {
                'type': 'score',
                'score': 0.5,
                'probabilities': {'0': 0.5, '1': 0.5},
                'legend': {'0': ['low', 'example'], '1': 'high'},
                'confidence': 0.0,
            }
        }
    )
    question = Question.score([('low', 'example'), 'high'])
    result = await Jevaluator(client=backend.client).evaluate(('array', 'state'), question)
    assert result.value.legend == {0: ['low', 'example'], 1: 'high'}
    assert backend.transport.requests[0]['state'] == ['array', 'state']
    assert backend.transport.requests[0]['questions'] == {
        'answer': {'type': 'score', 'criteria': [['low', 'example'], 'high']}
    }


async def test_batch_registration_and_foreign_handles(backend: Backend) -> None:
    evaluator = Jevaluator(client=backend.client)
    batch = evaluator.batch('state')
    with pytest.raises(QuestionError, match='at least one'):
        await batch.run()
    question = Question.noul('Ready?')
    handle = batch.add('q', question)
    with pytest.raises(QuestionError, match='unique'):
        batch.add('q', question)
    backend.respond({'q': {'type': 'noul', 'noul': 0.2}})
    result = await batch.run()
    with pytest.raises(QuestionError, match='cannot be changed'):
        batch.add('other', question)
    foreign = evaluator.batch('other state').add('q', question)
    recreated = Handle('q', question)
    for invalid in (foreign, recreated):
        with pytest.raises(ValueError, match='does not belong'):
            result.answer(invalid)
    assert result.answer(handle) == NoulAnswer(0.2)


async def test_repeated_concurrent_evaluations_have_separate_results(backend: Backend) -> None:
    evaluator = Jevaluator(client=backend.client)
    batch = evaluator.batch(['shared', 'state'])
    handle = batch.add('q', Question.noul('Ready?'))
    backend.respond({'q': {'type': 'noul', 'noul': 0.1}})
    backend.respond({'q': {'type': 'noul', 'noul': 0.9}})
    results = await asyncio.gather(batch.run(), batch.run())
    assert [result.answer(handle).probability for result in results] == [0.1, 0.9]
    assert backend.transport.requests[0] == backend.transport.requests[1]


@pytest.mark.parametrize(
    'answers',
    [
        {},
        {'q': {'type': 'noul', 'noul': 0.5}, 'extra': {'type': 'noul', 'noul': 0.5}},
        {'q': {'type': 'new-kind', 'value': 0.5}},
        {'q': {'type': 'noul', 'noul': 0.5}, 'extra': {'type': 'new-kind', 'value': 0.5}},
    ],
    ids=['missing', 'extra-known', 'requested-unknown-kind', 'extra-unknown-kind'],
)
async def test_answer_names_are_exact(backend: Backend, answers: dict[str, JsonValue]) -> None:
    backend.respond(answers)
    batch = Jevaluator(client=backend.client).batch('state')
    batch.add('q', Question.noul())
    with pytest.raises(ResponseValidationError, match='answer names') as caught:
        await batch.run()
    assert (caught.value.question, caught.value.request_id) == (None, 'fixture-request')


async def test_invalid_answer_is_rejected_before_result_is_returned(backend: Backend) -> None:
    backend.respond({'q': {'type': 'noul', 'noul': 1.5}})
    batch = Jevaluator(client=backend.client).batch('state')
    batch.add('q', Question.noul())
    with pytest.raises(ResponseValidationError, match='between zero and one') as caught:
        await batch.run()
    assert (caught.value.question, caught.value.request_id) == ('q', 'fixture-request')
    assert isinstance(caught.value.__cause__, ValueError)


async def test_sdk_errors_keep_their_categories_and_metadata(backend: Backend) -> None:
    backend.transport.responses.append(
        httpx2.Response(401, json={'detail': 'No access'}, headers={'x-typesafe-request-id': 'auth-failure'})
    )
    evaluator = Jevaluator(client=backend.client)
    with pytest.raises(typesafe_sdk.TypeSafeAuthenticationError) as caught:
        await evaluator.evaluate('state', Question.noul())
    assert (caught.value.status, caught.value.request_id) == (401, 'auth-failure')
    backend.respond({'answer': {'type': 'noul', 'noul': 'invalid'}})
    with pytest.raises(typesafe_sdk.TypeSafeAPIResponseValidationError):
        await evaluator.evaluate('state', Question.noul())


async def test_invalid_json_content_fails_before_io(backend: Backend) -> None:
    evaluator = Jevaluator(client=backend.client)
    with pytest.raises(ValidationError):
        await evaluator.evaluate({'number': float('nan')}, Question.noul())
    assert backend.transport.requests == []


Route = Literal['allow', 'block']


async def test_literal_choice(backend: Backend) -> None:
    routes: dict[Route, JsonContent | None] = {'allow': None, 'block': None}
    backend.respond(
        {
            'answer': {
                'type': 'choice',
                'choice': 'allow',
                'probabilities': {'allow': 0.9, 'block': 0.1},
                'confidence': 0.8,
            }
        }
    )
    result = await Jevaluator(client=backend.client).evaluate('state', Question.choice(routes))
    assert result.value.selected == 'allow'
