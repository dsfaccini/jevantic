"""Offline typing probe, not a Jevantic implementation or provider adapter."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Literal, TypeVar

from typing_extensions import assert_type


@dataclass(frozen=True)
class WireChoice:
    selected: str
    probabilities: Mapping[str, float]


@dataclass(frozen=True)
class WireScore:
    score: float


@dataclass(frozen=True)
class WireNoul:
    probability: float


WireAnswer = WireChoice | WireScore | WireNoul
ValueT = TypeVar('ValueT')
ValueT_co = TypeVar('ValueT_co', covariant=True)
AnswerT = TypeVar('AnswerT')
AnswerT_co = TypeVar('AnswerT_co', covariant=True)


@dataclass(frozen=True)
class Option(Generic[ValueT_co]):
    key: str
    value: ValueT_co


@dataclass(frozen=True)
class WeightedValue(Generic[ValueT_co]):
    value: ValueT_co
    probability: float


@dataclass(frozen=True)
class ChoiceAnswer(Generic[ValueT_co]):
    selected: ValueT_co
    distribution: tuple[WeightedValue[ValueT_co], ...]


@dataclass(frozen=True)
class Question(Generic[AnswerT_co]):
    decode: Callable[[WireAnswer], AnswerT_co]


@dataclass(frozen=True)
class Handle(Generic[AnswerT_co]):
    name: str
    owner: object
    question: Question[AnswerT_co]


def choice(options: Sequence[Option[ValueT]]) -> Question[ChoiceAnswer[ValueT]]:
    by_key: dict[str, ValueT] = {option.key: option.value for option in options}
    if not by_key or len(by_key) != len(options):
        raise ValueError('Choice keys must be unique and nonempty')

    def decode(answer: WireAnswer) -> ChoiceAnswer[ValueT]:
        if not isinstance(answer, WireChoice):
            raise ValueError('Expected Choice')
        if answer.selected not in by_key or answer.probabilities.keys() != by_key.keys():
            raise ValueError('Choice response does not match supplied options')
        return ChoiceAnswer(
            selected=by_key[answer.selected],
            distribution=tuple(
                WeightedValue(by_key[key], probability)
                for key, probability in answer.probabilities.items()
            ),
        )

    return Question(decode)


def decode_noul(answer: WireAnswer) -> WireNoul:
    if not isinstance(answer, WireNoul):
        raise ValueError('Expected Noul')
    return answer


def decode_score(answer: WireAnswer) -> WireScore:
    if not isinstance(answer, WireScore):
        raise ValueError('Expected Score')
    return answer


class Batch:
    def __init__(self) -> None:
        self.owner = object()
        self.handles: dict[str, Handle[object]] = {}

    def add(self, name: str, question: Question[AnswerT]) -> Handle[AnswerT]:
        if name in self.handles:
            raise ValueError('Duplicate question name')
        handle = Handle(name, self.owner, question)
        self.handles[name] = handle
        return handle

    def complete(self, answers: Mapping[str, WireAnswer]) -> 'CompletedBatch':
        if not answers or answers.keys() != self.handles.keys():
            raise ValueError('Answer names do not match a nonempty batch')
        for name, handle in self.handles.items():
            handle.question.decode(answers[name])
        return CompletedBatch(self.owner, dict(self.handles), dict(answers))


@dataclass(frozen=True)
class CompletedBatch:
    owner: object
    handles: Mapping[str, Handle[object]]
    answers: Mapping[str, WireAnswer]

    def answer(self, handle: Handle[AnswerT]) -> AnswerT:
        if handle.owner is not self.owner or self.handles.get(handle.name) is not handle:
            raise ValueError('Handle does not belong to this completed batch')
        return handle.question.decode(self.answers[handle.name])


Route = Literal['allow', 'block']


class Team(str, Enum):
    SUPPORT = 'support'
    ENGINEERING = 'engineering'


@dataclass(frozen=True)
class Candidate:
    identifier: str


def build_candidate_question(
    candidates: Sequence[Candidate],
) -> Question[ChoiceAnswer[Candidate]]:
    return choice([Option(candidate.identifier, candidate) for candidate in candidates])


def demonstrate() -> None:
    options: list[Option[Route]] = [Option('allow', 'allow'), Option('block', 'block')]
    candidates: list[Candidate] = [Candidate('a'), Candidate('b')]
    teams: list[Option[Team]] = [Option(team.value, team) for team in Team]
    batch = Batch()
    route = batch.add('route', choice(options))
    candidate = batch.add('candidate', build_candidate_question(candidates))
    team = batch.add('team', choice(teams))
    risk = batch.add('risk', Question(decode_noul))
    score = batch.add('score', Question(decode_score))
    answers: dict[str, WireAnswer] = {
        'route': WireChoice('allow', {'allow': 0.8, 'block': 0.2}),
        'candidate': WireChoice('b', {'a': 0.3, 'b': 0.7}),
        'team': WireChoice('support', {'support': 0.6, 'engineering': 0.4}),
        'risk': WireNoul(0.05),
        'score': WireScore(1.75),
    }
    completed = batch.complete(answers)
    assert_type(completed.answer(route), ChoiceAnswer[Route])
    assert_type(completed.answer(route).selected, Route)
    assert_type(completed.answer(route).distribution[0].value, Route)
    assert_type(completed.answer(candidate).selected, Candidate)
    assert_type(completed.answer(team).selected, Team)
    assert_type(completed.answer(risk), WireNoul)
    assert_type(completed.answer(score), WireScore)
    assert completed.answer(candidate).selected is candidates[1]
    assert completed.answer(team).selected is Team.SUPPORT
    assert completed.answer(route).selected == 'allow'
    assert completed.answer(score).score == 1.75
    foreign = Batch().add('risk', Question(decode_noul))
    try:
        completed.answer(foreign)
    except ValueError:
        pass
    else:
        raise AssertionError('A handle from another batch must be rejected')
    print('Typed question probe passed: literal, enum, object, mixed batch, handle identity')


if __name__ == '__main__':
    demonstrate()
