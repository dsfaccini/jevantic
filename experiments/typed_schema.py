"""Offline result-schema typing probe, not request assembly or provider validation."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError
from typing_extensions import assert_type


OptionT = TypeVar('OptionT', bound=str)
ResultT = TypeVar('ResultT', bound=BaseModel)


class ChoiceAnswer(BaseModel, Generic[OptionT]):
    selected: OptionT
    probabilities: dict[OptionT, float]


class NoulAnswer(BaseModel):
    probability: float


class ScoreAnswer(BaseModel):
    score: float


@dataclass(frozen=True)
class ChoiceQuestion:
    options: tuple[str, ...]


@dataclass(frozen=True)
class NoulQuestion:
    instructions: str


@dataclass(frozen=True)
class ScoreQuestion:
    instructions: str


Question = ChoiceQuestion | NoulQuestion | ScoreQuestion


class Review(BaseModel):
    route: Annotated[
        ChoiceAnswer[Literal['allow', 'block']],
        ChoiceQuestion(('allow', 'block')),
    ]
    risk: Annotated[NoulAnswer, NoulQuestion('Could the action expose a secret?')]
    severity: Annotated[ScoreAnswer, ScoreQuestion('Assess the impact')]
    owner: ChoiceAnswer[str]


class ContradictoryReview(BaseModel):
    route: Annotated[
        ChoiceAnswer[Literal['allow', 'block']],
        ChoiceQuestion(('review', 'skip')),
    ]


@dataclass(frozen=True)
class Evaluation(Generic[ResultT]):
    value: ResultT


def hydrate(result_type: type[ResultT], answers: Mapping[str, object]) -> Evaluation[ResultT]:
    return Evaluation(result_type.model_validate(answers))


def declared_questions(result_type: type[BaseModel]) -> dict[str, Question]:
    questions: dict[str, Question] = {}
    for name, field in result_type.model_fields.items():
        for metadata in field.metadata:
            if isinstance(metadata, (ChoiceQuestion, NoulQuestion, ScoreQuestion)):
                if name in questions:
                    raise ValueError('Duplicate question metadata')
                questions[name] = metadata
    return questions


def demonstrate() -> None:
    payload: dict[str, object] = {
        'route': {'selected': 'allow', 'probabilities': {'allow': 0.8, 'block': 0.2}},
        'risk': {'probability': 0.05},
        'severity': {'score': 1.75},
        'owner': {'selected': 'team-a', 'probabilities': {'team-a': 1.0}},
    }
    result = hydrate(Review, payload)
    assert_type(result, Evaluation[Review])
    assert_type(result.value.route.selected, Literal['allow', 'block'])
    assert_type(result.value.route.probabilities, dict[Literal['allow', 'block'], float])
    assert_type(result.value.risk, NoulAnswer)
    assert_type(result.value.severity.score, float)
    assert_type(result.value.owner.selected, str)
    assert result.value.route.selected == 'allow'
    assert result.value.severity.score == 1.75
    assert declared_questions(Review).keys() == {'route', 'risk', 'severity'}

    wrong_payload: dict[str, object] = {
        'route': {'selected': 'review', 'probabilities': {'review': 0.8, 'skip': 0.2}},
    }
    assert declared_questions(ContradictoryReview)['route'] == ChoiceQuestion(('review', 'skip'))
    try:
        hydrate(ContradictoryReview, wrong_payload)
    except ValidationError:
        pass
    else:
        raise AssertionError('The literal output type rejects the contradictory metadata response')
    print('Typed schema probe passed: named fields, literals, dynamic strings, runtime mismatch')


if __name__ == '__main__':
    demonstrate()
