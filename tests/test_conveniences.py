from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

import pytest
from conftest import Backend
from pydantic import BaseModel, Field, ValidationError

from jevantic import ChoiceAnswer, ChoiceProbability, Content, Jevaluator, NoulAnswer, Question, ScoreAnswer, Usage


@dataclass
class Author:
    name: str
    private_note: str = field(metadata={'exclude': True})


@dataclass
class Draft:
    author: Author
    written: date
    paragraphs: tuple[str, ...]


class Instructions(BaseModel):
    question: str
    internal_note: str = Field(exclude=True)


async def test_noul_serializes_declared_content_and_keeps_metadata(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.25}})
    result = await Jevaluator(client=backend.client).noul(
        Draft(Author('Alba', 'local only'), date(2026, 9, 17), ('A draft.',)),
        Instructions(question='Is the draft ready?', internal_note='local only'),
        true={'meaning': 'Ready to publish'},
        false='Needs review',
    )
    assert result.value == NoulAnswer(0.25)
    assert (result.info.model, result.info.requested_model, result.info.request_id, result.info.usage) == (
        'jev-fixture-version',
        'jev-sdk-default',
        'fixture-request',
        Usage(12, 4),
    )
    assert backend.transport.requests == [
        {
            'model': 'jev-sdk-default',
            'state': {'author': {'name': 'Alba'}, 'written': '2026-09-17', 'paragraphs': ['A draft.']},
            'questions': {
                'answer': {
                    'type': 'noul',
                    'instructions': {'question': 'Is the draft ready?'},
                    'criteria': {'true': {'meaning': 'Ready to publish'}, 'false': 'Needs review'},
                }
            },
        }
    ]


class Team(StrEnum):
    SUPPORT = 'support'
    ENGINEERING = 'engineering'


@pytest.mark.parametrize('labels', [Team, (Team.SUPPORT, Team.ENGINEERING)])
async def test_choice_infers_enum_labels(backend: Backend, labels: type[Team] | tuple[Team, ...]) -> None:
    backend.respond(
        {
            'answer': {
                'type': 'choice',
                'choice': 'engineering',
                'probabilities': {'support': 0.1, 'engineering': 0.9},
                'confidence': 0.8,
            }
        }
    )
    result = await Jevaluator(client=backend.client).choice('Search outage', labels, instructions='Route the issue.')
    assert result.value == ChoiceAnswer(
        Team.ENGINEERING,
        'engineering',
        (
            ChoiceProbability('support', Team.SUPPORT, 0.1),
            ChoiceProbability('engineering', Team.ENGINEERING, 0.9),
        ),
        0.8,
    )
    assert result.value.selected is Team.ENGINEERING
    assert result.info.request_id == 'fixture-request'
    assert backend.transport.requests[0]['questions'] == {
        'answer': {
            'type': 'choice',
            'instructions': 'Route the issue.',
            'criteria': {'support': None, 'engineering': None},
        }
    }


@dataclass
class Level:
    description: str


async def test_score_infers_structured_rubrics_and_preserves_uncertainty(backend: Backend) -> None:
    backend.respond(
        {
            'answer': {
                'type': 'score',
                'score': 0.75,
                'probabilities': {'0': 0.25, '1': 0.75},
                'legend': {'0': {'description': 'Unclear'}, '1': {'description': 'Clear'}},
                'confidence': 0.5,
            }
        }
    )
    result = await Jevaluator(client=backend.client).score(
        'A draft.', [Level('Unclear'), Level('Clear')], instructions='Rate clarity.'
    )
    assert result.value == ScoreAnswer(
        0.75, {0: 0.25, 1: 0.75}, {0: {'description': 'Unclear'}, 1: {'description': 'Clear'}}, 0.5
    )
    assert result.info.request_id == 'fixture-request'
    assert backend.transport.requests[0]['questions'] == {
        'answer': {
            'type': 'score',
            'instructions': 'Rate clarity.',
            'criteria': [{'description': 'Unclear'}, {'description': 'Clear'}],
        }
    }


@dataclass(slots=True)
class Candidate:
    name: str
    summary: str
    private_note: str = field(metadata={'exclude': True})


class CandidateModel(BaseModel):
    name: str
    summary: str
    private_note: str = Field(exclude=True)


async def test_select_infers_fields_and_returns_original_objects(backend: Backend) -> None:
    candidates: list[Candidate | CandidateModel] = [
        Candidate('Alba', 'Search engineering', 'local first'),
        CandidateModel(name='Bryn', summary='Support engineering', private_note='local second'),
    ]
    backend.respond(
        {'answer': {'type': 'choice', 'choice': '1', 'probabilities': {'0': 0.1, '1': 0.9}, 'confidence': 0.8}}
    )
    result = await Jevaluator(client=backend.client).select(
        'Support lead', candidates, instructions='Select a candidate.'
    )
    assert result.value.selected is candidates[1]
    assert result.value.selected.private_note == 'local second'
    assert result.value.distribution == (
        ChoiceProbability('0', candidates[0], 0.1),
        ChoiceProbability('1', candidates[1], 0.9),
    )
    assert result.info.request_id == 'fixture-request'
    assert backend.transport.requests[0]['questions'] == {
        'answer': {
            'type': 'choice',
            'instructions': 'Select a candidate.',
            'criteria': {
                '0': {'name': 'Alba', 'summary': 'Search engineering'},
                '1': {'name': 'Bryn', 'summary': 'Support engineering'},
            },
        }
    }


async def test_inferred_descriptions_are_snapshots_but_values_retain_identity(backend: Backend) -> None:
    candidate = Candidate('Alba', 'Original description', 'local')
    candidates = [candidate]
    question = Question.select(candidates)
    candidate.summary = 'Changed after construction'
    candidates.clear()
    backend.respond({'answer': {'type': 'choice', 'choice': '0', 'probabilities': {'0': 1.0}, 'confidence': 1.0}})
    result = await Jevaluator(client=backend.client).evaluate('state', question)
    assert result.value.selected is candidate
    assert result.value.selected.summary == 'Changed after construction'
    assert backend.transport.requests[0]['questions'] == {
        'answer': {'type': 'choice', 'criteria': {'0': {'name': 'Alba', 'summary': 'Original description'}}}
    }


async def test_explicit_projection_supports_arbitrary_local_values(backend: Backend) -> None:
    local = object()
    backend.respond(
        {'answer': {'type': 'choice', 'choice': 'stable', 'probabilities': {'stable': 1.0}, 'confidence': 1.0}}
    )
    result = await Jevaluator(client=backend.client).select(
        'state', [local], key=lambda _: 'stable', describe=lambda _: None
    )
    assert result.value.selected is local
    assert backend.transport.requests[0]['questions'] == {'answer': {'type': 'choice', 'criteria': {'stable': None}}}
    backend.transport.requests.clear()
    with pytest.raises(ValidationError):
        await Jevaluator(client=backend.client).select('state', [local])
    assert backend.transport.requests == []


@dataclass
class NumericRecord:
    value: float


class NumericModel(BaseModel):
    value: float


@pytest.mark.parametrize('state', [NumericRecord(float('nan')), NumericModel(value=float('inf'))])
async def test_structured_nonfinite_values_fail_before_io(backend: Backend, state: Content) -> None:
    with pytest.raises(ValidationError):
        await Jevaluator(client=backend.client).noul(state, 'Valid?')
    assert backend.transport.requests == []


async def test_dataclass_class_is_not_serialized_as_an_instance(backend: Backend) -> None:
    with pytest.raises(ValidationError):
        await Jevaluator(client=backend.client).select('state', [NumericRecord])
    assert backend.transport.requests == []
