"""Question definitions and their typed, question-aware answer decoders."""

import math
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, TypeVar

import typesafe_sdk

from ._errors import QuestionError
from ._json import JsonContent, content_snapshot

AnswerT_co = TypeVar('AnswerT_co', covariant=True)
ValueT = TypeVar('ValueT')
LabelT = TypeVar('LabelT', bound=str)

# This experimental tolerance accommodates arithmetic noise, not semantic repair.
DISTRIBUTION_TOLERANCE = 1e-6


@dataclass(frozen=True)
class NoulAnswer:
    """The model's probability of the question's yes outcome."""

    probability: float


@dataclass(frozen=True)
class Option[ValueT_co]:
    """Associate a wire label with a local value and an optional model description.

    The local value is never sent to the model. Its identity is retained in results.
    """

    key: str
    value: ValueT_co
    description: JsonContent | None = None


@dataclass(frozen=True)
class ChoiceProbability[ValueT_co]:
    """One allowed option and the model's probability for it."""

    key: str
    value: ValueT_co
    probability: float


@dataclass(frozen=True)
class ChoiceAnswer[ValueT_co]:
    """A selected local value, its full distribution, and provider confidence.

    Confidence is the provider's summary statistic, not the selected probability.
    Distribution entries follow the question's option order.
    """

    selected: ValueT_co
    selected_key: str
    distribution: tuple[ChoiceProbability[ValueT_co], ...]
    confidence: float


@dataclass(frozen=True)
class ScoreAnswer:
    """A potentially fractional rubric score and its uncertainty information."""

    score: float
    probabilities: Mapping[int, float]
    legend: Mapping[int, JsonContent]
    confidence: float


def validate_probability(value: float) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Probabilities and confidence must be finite values between zero and one')


def validate_distribution[KeyT: (str, int)](values: Mapping[KeyT, float], expected: Collection[KeyT]) -> None:
    if set(values) != set(expected):
        raise ValueError('Distribution keys do not match the requested options or rubric levels')
    for probability in values.values():
        validate_probability(probability)
    if not math.isclose(math.fsum(values.values()), 1.0, rel_tol=0.0, abs_tol=DISTRIBUTION_TOLERANCE):
        raise ValueError('The probability distribution does not sum to one')


# Explicit covariance also covers the factory methods returning concrete questions.
@dataclass(frozen=True)
class Question(Generic[AnswerT_co]):  # noqa: UP046
    """A reusable Jev question whose definition determines its answer type.

    Construct questions with ``noul``, ``choice``, ``select``, or ``score``.
    Question construction performs no provider request.
    """

    _definition: typesafe_sdk.Question
    _decode: Callable[[typesafe_sdk.Answer], AnswerT_co]

    def to_request(self) -> typesafe_sdk.Question:
        """Build an independent SDK question for callers managing their own requests."""
        return deepcopy(self._definition)

    def decode(self, answer: typesafe_sdk.Answer) -> AnswerT_co:
        """Validate and decode an SDK answer; raise ``ValueError`` for invalid values."""
        return self._decode(answer)

    @staticmethod
    def noul(
        instructions: JsonContent | None = None,
        *,
        true: JsonContent | None = None,
        false: JsonContent | None = None,
    ) -> 'Question[NoulAnswer]':
        """Ask for the probability of a yes outcome, with optional outcome descriptions."""
        definition = typesafe_sdk.Noul(
            instructions=content_snapshot(instructions) if instructions is not None else None,
            criteria={
                'true': content_snapshot(true) if true is not None else None,
                'false': content_snapshot(false) if false is not None else None,
            },
        )

        def decode(answer: typesafe_sdk.Answer) -> NoulAnswer:
            if not isinstance(answer, typesafe_sdk.NoulAnswer):
                raise ValueError('Expected a Noul answer')
            validate_probability(answer.noul)
            return NoulAnswer(answer.noul)

        return Question(definition, decode)

    @staticmethod
    def choice(
        criteria: Mapping[LabelT, JsonContent | None],
        *,
        instructions: JsonContent | None = None,
    ) -> 'Question[ChoiceAnswer[LabelT]]':
        """Choose a label while retaining literal or string-enum types in the answer."""
        return Question.select(
            (Option(key, key, description) for key, description in criteria.items()),
            instructions=instructions,
        )

    @staticmethod
    def select(
        options: Iterable[Option[ValueT]],
        *,
        instructions: JsonContent | None = None,
    ) -> 'Question[ChoiceAnswer[ValueT]]':
        """Choose a local typed value using labels and descriptions sent to Jev."""
        values: dict[str, ValueT] = {}
        criteria: dict[str, typesafe_sdk.JSONContent | None] = {}
        for option in options:
            if option.key in values:
                raise QuestionError('Choice option keys must be unique')
            if len(values) == 255:
                raise QuestionError('Jev Choice questions accept at most 255 options')
            values[option.key] = option.value
            criteria[option.key] = content_snapshot(option.description) if option.description is not None else None
        if not values:
            raise QuestionError('A Choice question needs at least one option')
        definition = typesafe_sdk.Choice(
            criteria=criteria,
            instructions=content_snapshot(instructions) if instructions is not None else None,
        )

        def decode(answer: typesafe_sdk.Answer) -> ChoiceAnswer[ValueT]:
            if not isinstance(answer, typesafe_sdk.ChoiceAnswer):
                raise ValueError('Expected a Choice answer')
            if answer.choice not in values:
                raise ValueError('The selected option was not requested')
            validate_distribution(answer.probabilities, values.keys())
            validate_probability(answer.confidence)
            if max(answer.probabilities.values()) - answer.probabilities[answer.choice] > DISTRIBUTION_TOLERANCE:
                raise ValueError('The selected option is not a highest-probability option')
            return ChoiceAnswer(
                selected=values[answer.choice],
                selected_key=answer.choice,
                distribution=tuple(
                    ChoiceProbability(key, value, answer.probabilities[key]) for key, value in values.items()
                ),
                confidence=answer.confidence,
            )

        return Question(definition, decode)

    @staticmethod
    def score(
        criteria: Sequence[JsonContent],
        *,
        instructions: JsonContent | None = None,
    ) -> 'Question[ScoreAnswer]':
        """Score against ordered descriptions, retaining fractional scores and the rubric.

        Levels are numbered from zero. The observed API accepts one to ten levels;
        its documentation recommends at least two.
        """
        if isinstance(criteria, str):
            raise QuestionError('A Score rubric must be a sequence of level descriptions, not a single string')
        if not criteria:
            raise QuestionError('A Score question needs a nonempty rubric')
        if len(criteria) > 10:
            raise QuestionError('Jev Score questions accept at most 10 levels')
        levels = tuple(content_snapshot(level) for level in criteria)
        definition = typesafe_sdk.Score(
            criteria=levels,
            instructions=content_snapshot(instructions) if instructions is not None else None,
        )

        def decode(answer: typesafe_sdk.Answer) -> ScoreAnswer:
            if not isinstance(answer, typesafe_sdk.ScoreAnswer):
                raise ValueError('Expected a Score answer')
            expected = range(len(levels))
            validate_distribution(answer.probabilities, expected)
            validate_probability(answer.confidence)
            if not math.isfinite(answer.score) or not 0 <= answer.score <= len(levels) - 1:
                raise ValueError('The score is outside the requested rubric')
            weighted_score = math.fsum(level * probability for level, probability in answer.probabilities.items())
            if not math.isclose(
                answer.score,
                weighted_score,
                rel_tol=0.0,
                abs_tol=DISTRIBUTION_TOLERANCE * len(levels),
            ):
                raise ValueError('The score does not match the probability-weighted rubric')
            if answer.legend.keys() != set(expected):
                raise ValueError('Legend keys do not match the requested rubric')
            legend: dict[int, JsonContent] = {
                key: content_snapshot(description) for key, description in answer.legend.items()
            }
            if tuple(legend[key] for key in expected) != levels:
                raise ValueError('The returned legend differs from the requested rubric')
            return ScoreAnswer(
                score=answer.score,
                probabilities=MappingProxyType(dict(answer.probabilities)),
                legend=MappingProxyType(legend),
                confidence=answer.confidence,
            )

        return Question(definition, decode)
