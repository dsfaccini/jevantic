import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping, Sequence
from typing import Literal

import httpx2
import pytest
import typesafe_sdk
from conftest import Backend, request_adapter
from pydantic import BaseModel, JsonValue

from examples.comparisons import (
    CANDIDATE_INSTRUCTIONS,
    Candidate,
    evaluate_many_after,
    evaluate_many_before,
    select_candidate_after,
    select_candidate_before,
)
from jevantic import Jevaluation, Jevaluator, JsonContent, NoulAnswer, Question, QuestionError

CandidateSelector = Callable[[Jevaluator, JsonContent | BaseModel, Iterable[Candidate]], Awaitable[Candidate]]


def noul_response(probability: float, request_id: str) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            'model': 'jev-comparison-version',
            'usage': {'input_tokens': 10, 'output_tokens': 3},
            'answers': {'answer': {'type': 'noul', 'noul': probability}},
        },
        headers={'x-typesafe-request-id': request_id},
    )


async def test_selection_comparison_preserves_identity_and_has_equal_wire_requests(backend: Backend) -> None:
    candidates = [
        Candidate('alba', 'Built the retrieval service', 'Private hiring feedback'),
        Candidate('bryn', 'Led customer-support engineering', 'Private hiring feedback'),
    ]
    state = {'role': 'Lead the retrieval team'}
    for _ in range(2):
        backend.respond(
            {
                'answer': {
                    'type': 'choice',
                    'choice': 'bryn',
                    'probabilities': {'alba': 0.1, 'bryn': 0.9},
                    'confidence': 0.8,
                }
            }
        )
    evaluator = Jevaluator(client=backend.client)
    assert await select_candidate_before(evaluator, state, candidates) is candidates[1]
    assert await select_candidate_after(evaluator, state, candidates) is candidates[1]
    assert (
        backend.transport.requests[0]
        == backend.transport.requests[1]
        == {
            'model': 'jev-sdk-default',
            'state': state,
            'questions': {
                'answer': {
                    'type': 'choice',
                    'instructions': CANDIDATE_INSTRUCTIONS,
                    'criteria': {'alba': 'Built the retrieval service', 'bryn': 'Led customer-support engineering'},
                }
            },
        }
    )


@pytest.mark.parametrize('selector', [select_candidate_before, select_candidate_after])
async def test_selection_comparison_rejects_duplicate_ids(
    backend: Backend,
    selector: CandidateSelector,
) -> None:
    candidates = [Candidate('same', 'First', 'Private'), Candidate('same', 'Second', 'Private')]
    with pytest.raises((ValueError, QuestionError), match='unique'):
        await selector(Jevaluator(client=backend.client), {'role': 'Engineer'}, candidates)
    assert backend.transport.requests == []


class GatedTransport(httpx2.AsyncBaseTransport):
    def __init__(self, responses: Mapping[str, Sequence[httpx2.Response]]) -> None:
        self.responses = {state: deque(items) for state, items in responses.items()}
        self.started = {state: asyncio.Event() for state in responses}
        self.release = {state: asyncio.Event() for state in responses}
        self.finalized = {state: asyncio.Event() for state in responses}
        self.requests: list[tuple[str, dict[str, JsonValue]]] = []
        self.active = 0
        self.peak_active = 0

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        content = request_adapter.validate_json(request.content)
        state = content['state']
        assert isinstance(state, str)
        self.requests.append((state, content))
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        self.started[state].set()
        try:
            await self.release[state].wait()
            response = self.responses[state].popleft()
            response.request = request
            return response
        finally:
            self.active -= 1
            self.finalized[state].set()


async def run_fanout(
    implementation: Literal['before', 'after'], evaluator: Jevaluator, states: Iterable[str]
) -> list[Jevaluation[NoulAnswer]]:
    if implementation == 'before':
        return await evaluate_many_before(evaluator, states, Question.noul(), concurrency=2)
    return await evaluate_many_after(evaluator, states, Question.noul(), concurrency=2)


@pytest.mark.parametrize('implementation', ['before', 'after'])
async def test_fanout_comparison_is_lazy_bounded_ordered_and_keeps_metadata(
    implementation: Literal['before', 'after'],
) -> None:
    transport = GatedTransport(
        {
            '0': [noul_response(0.1, 'request-0')],
            '1': [noul_response(0.2, 'request-1')],
            '2': [noul_response(0.3, 'request-2')],
        }
    )
    pulled: list[str] = []

    def states() -> Iterator[str]:
        for state in ('0', '1', '2'):
            pulled.append(state)
            yield state

    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-key',
        base_url='https://jevantic.invalid',
        transport=transport,
        retry=typesafe_sdk.RetryPolicy(max_retries=0),
    ) as client:
        task = asyncio.create_task(run_fanout(implementation, Jevaluator(client=client), states()))
        await asyncio.wait_for(transport.started['0'].wait(), timeout=2)
        await asyncio.wait_for(transport.started['1'].wait(), timeout=2)
        assert (pulled, transport.peak_active) == (['0', '1'], 2)
        transport.release['1'].set()
        await asyncio.wait_for(transport.started['2'].wait(), timeout=2)
        transport.release['2'].set()
        await asyncio.wait_for(transport.finalized['2'].wait(), timeout=2)
        transport.release['0'].set()
        results = await task
    assert [result.value for result in results] == [NoulAnswer(0.1), NoulAnswer(0.2), NoulAnswer(0.3)]
    assert [result.info.request_id for result in results] == ['request-0', 'request-1', 'request-2']
    assert [state for state, _ in transport.requests] == ['0', '1', '2']
    assert all(
        content['questions'] == {'answer': {'type': 'noul', 'criteria': {'true': None, 'false': None}}}
        for _, content in transport.requests
    )
    assert transport.peak_active == 2


class FailingInputs:
    def __init__(self, error: RuntimeError) -> None:
        self.error = error

    def __iter__(self) -> Iterator[str]:
        raise self.error


@pytest.mark.parametrize('implementation', ['before', 'after'])
async def test_fanout_comparison_groups_input_creation_failures(
    backend: Backend,
    implementation: Literal['before', 'after'],
) -> None:
    error = RuntimeError('Source failed')
    with pytest.raises(ExceptionGroup) as caught:
        await run_fanout(implementation, Jevaluator(client=backend.client), FailingInputs(error))
    assert caught.value.exceptions == (error,)
    assert backend.transport.requests == []


@pytest.mark.parametrize('implementation', ['before', 'after'])
async def test_fanout_comparison_cancels_unfinished_work_and_keeps_index_note(
    implementation: Literal['before', 'after'],
) -> None:
    transport = GatedTransport(
        {
            'failing': [httpx2.Response(401, json={'detail': 'No access'})],
            'blocked': [noul_response(0.5, 'unused')],
        }
    )
    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-key',
        base_url='https://jevantic.invalid',
        transport=transport,
        retry=typesafe_sdk.RetryPolicy(max_retries=0),
    ) as client:
        task = asyncio.create_task(run_fanout(implementation, Jevaluator(client=client), iter(['failing', 'blocked'])))
        await asyncio.wait_for(transport.started['failing'].wait(), timeout=2)
        await asyncio.wait_for(transport.started['blocked'].wait(), timeout=2)
        transport.release['failing'].set()
        with pytest.raises(ExceptionGroup) as caught:
            await task
    assert len(caught.value.exceptions) == 1
    error = caught.value.exceptions[0]
    assert isinstance(error, typesafe_sdk.TypeSafeAuthenticationError)
    assert error.__notes__ == ['Jevantic input index: 0']
    assert transport.finalized['blocked'].is_set()
