import math

import pytest
import typesafe_sdk
from pydantic import JsonValue, ValidationError

from jevantic import JsonContent, NoulAnswer, Question, QuestionError


@pytest.mark.parametrize('probability', [0.0, 0.4, 1.0])
def test_low_level_noul_decode(probability: float) -> None:
    question = Question.noul('Ready?')
    assert question.decode(typesafe_sdk.NoulAnswer(noul=probability)) == NoulAnswer(probability)


@pytest.mark.parametrize('probability', [-0.01, 1.01, math.inf, -math.inf, math.nan])
def test_non_probabilities_are_rejected(probability: float) -> None:
    with pytest.raises(ValueError, match='finite values between zero and one'):
        Question.noul().decode(typesafe_sdk.NoulAnswer(noul=probability))


@pytest.mark.parametrize(
    ('question', 'answer'),
    [
        (
            Question.noul(),
            typesafe_sdk.ChoiceAnswer(choice='a', probabilities={'a': 1.0}, confidence=1.0),
        ),
        (Question.choice({'a': None}), typesafe_sdk.NoulAnswer(noul=0.5)),
        (Question.score(['low', 'high']), typesafe_sdk.NoulAnswer(noul=0.5)),
    ],
    ids=['noul', 'choice', 'score'],
)
def test_answer_kind_must_match(question: Question[object], answer: typesafe_sdk.Answer) -> None:
    with pytest.raises(ValueError, match='Expected a'):
        question.decode(answer)


@pytest.mark.parametrize(
    ('selected', 'probabilities', 'confidence', 'message'),
    [
        ('other', {'a': 0.5, 'b': 0.5}, 0.5, 'not requested'),
        ('a', {'a': 1.0}, 1.0, 'keys do not match'),
        ('a', {'a': 0.5, 'other': 0.5}, 0.5, 'keys do not match'),
        ('a', {'a': 0.2, 'b': 0.2}, 0.5, 'sum to one'),
        ('a', {'a': 0.8, 'b': 0.8}, 0.5, 'sum to one'),
        ('a', {'a': 1.2, 'b': -0.2}, 0.5, 'between zero and one'),
        ('a', {'a': 0.5, 'b': 0.5}, -0.1, 'between zero and one'),
        ('a', {'a': 0.5, 'b': 0.5}, 1.1, 'between zero and one'),
        ('a', {'a': 0.5, 'b': 0.5}, math.nan, 'finite'),
        ('a', {'a': 0.1, 'b': 0.9}, 0.8, 'highest-probability'),
    ],
)
def test_choice_checks_the_question_and_distribution(
    selected: str, probabilities: dict[str, float], confidence: float, message: str
) -> None:
    question = Question.choice({'a': None, 'b': None})
    answer = typesafe_sdk.ChoiceAnswer(choice=selected, probabilities=probabilities, confidence=confidence)
    with pytest.raises(ValueError, match=message):
        question.decode(answer)


def test_small_distribution_roundoff_is_preserved_without_normalizing() -> None:
    question = Question.choice({'a': None, 'b': None, 'c': None})
    probabilities: dict[str, float] = {'a': 0.3333333, 'b': 0.3333333, 'c': 0.3333333}
    answer = question.decode(typesafe_sdk.ChoiceAnswer(choice='a', probabilities=probabilities, confidence=0.0))
    assert [entry.probability for entry in answer.distribution] == [0.3333333, 0.3333333, 0.3333333]


@pytest.mark.parametrize('score', [-0.01, 2.01, math.inf, math.nan])
def test_score_must_be_within_rubric(score: float) -> None:
    question = Question.score(['low', 'middle', 'high'])
    answer = typesafe_sdk.ScoreAnswer(
        score=score,
        probabilities={0: 0.1, 1: 0.3, 2: 0.6},
        legend={0: 'low', 1: 'middle', 2: 'high'},
        confidence=0.5,
    )
    with pytest.raises(ValueError, match='outside the requested rubric'):
        question.decode(answer)


@pytest.mark.parametrize(
    ('legend', 'message'),
    [
        ({0: 'low'}, 'Legend keys'),
        ({0: 'low', 2: 'high'}, 'Legend keys'),
        ({0: 'wrong', 1: 'high'}, 'legend differs'),
    ],
)
def test_score_legend_preserves_rubric_identity(legend: dict[int, str], message: str) -> None:
    answer = typesafe_sdk.ScoreAnswer(score=0.5, probabilities={0: 0.5, 1: 0.5}, legend=dict(legend), confidence=0.0)
    with pytest.raises(ValueError, match=message):
        Question.score(['low', 'high']).decode(answer)


def test_one_level_score() -> None:
    question = Question.score(['only'])
    answer = question.decode(
        typesafe_sdk.ScoreAnswer(score=0.0, probabilities={0: 1.0}, legend={0: 'only'}, confidence=1.0)
    )
    assert answer.score == 0.0


def test_question_definition_errors() -> None:
    with pytest.raises(QuestionError, match='at least one option'):
        Question.choice({})
    with pytest.raises(QuestionError, match='unique'):
        Question.select([1, 2], key=lambda _: 'a', describe=lambda _: None)
    with pytest.raises(QuestionError, match='255'):
        Question.select(range(256), describe=lambda _: None)
    with pytest.raises(QuestionError, match='single string'):
        Question.choice('allow')
    with pytest.raises(QuestionError, match='unique'):
        Question.choice(['same', 'same'])
    with pytest.raises(QuestionError, match='nonempty rubric'):
        Question.score([])
    with pytest.raises(QuestionError, match='single string'):
        Question.score('low')
    with pytest.raises(QuestionError, match='at most 10'):
        Question.score(['level'] * 11)
    assert isinstance(Question.score(['level'] * 10).to_request(), typesafe_sdk.Score)
    question = Question.select(range(255), describe=lambda _: None)
    request = question.to_request()
    assert isinstance(request, typesafe_sdk.Choice)
    assert len(request.criteria) == 255


@pytest.mark.parametrize('probability', [0.5, 0.4999999])
def test_choice_accepts_ties_and_rounding(probability: float) -> None:
    answer = Question.choice({'a': None, 'b': None}).decode(
        typesafe_sdk.ChoiceAnswer(choice='a', probabilities={'a': probability, 'b': 1 - probability}, confidence=0.0)
    )
    assert answer.selected == 'a'
    assert answer.distribution[0].probability == probability


def test_score_checks_weighted_mean_without_replacing_provider_value() -> None:
    question = Question.score(['low', 'high'])
    invalid = typesafe_sdk.ScoreAnswer(
        score=0.0, probabilities={0: 0.0, 1: 1.0}, legend={0: 'low', 1: 'high'}, confidence=1.0
    )
    with pytest.raises(ValueError, match='probability-weighted'):
        question.decode(invalid)
    rounded = typesafe_sdk.ScoreAnswer(
        score=0.5000001, probabilities={0: 0.5, 1: 0.5}, legend={0: 'low', 1: 'high'}, confidence=0.0
    )
    assert question.decode(rounded).score == 0.5000001


def test_low_level_requests_are_independent_copies() -> None:
    descriptions: dict[str, JsonContent | None] = {'a': {'meaning': 'original'}}
    question = Question.choice(descriptions, instructions='original instructions')
    descriptions['a'] = 'changed'
    first = question.to_request()
    assert isinstance(first, typesafe_sdk.Choice)
    first.instructions = 'changed instructions'
    first.criteria = {'b': 'changed criteria'}
    second = question.to_request()
    assert isinstance(second, typesafe_sdk.Choice)
    assert second.instructions == 'original instructions'
    assert second.criteria == {'a': {'meaning': 'original'}}


def test_invalid_structured_question_content_is_rejected() -> None:
    instructions: dict[str, JsonValue] = {'value': math.inf}
    with pytest.raises(ValidationError):
        Question.noul(instructions)
