import asyncio
from collections import deque
from collections.abc import Iterator, Mapping, Sequence

import anyio
import httpx2
import pytest
import typesafe_sdk
from conftest import Backend, request_adapter

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question

exception_group_type: type[ExceptionGroup[Exception]] = ExceptionGroup


def noul_response(probability: float, request_id: str, *, name: str = 'answer') -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            'model': 'jev-fanout-version',
            'usage': {'input_tokens': 11, 'output_tokens': 3},
            'answers': {name: {'type': 'noul', 'noul': probability}},
        },
        headers={'x-typesafe-request-id': request_id},
    )


class GatedTransport(httpx2.AsyncBaseTransport):
    def __init__(self, responses: Mapping[str, Sequence[httpx2.Response]]) -> None:
        self.responses = {state: deque(values) for state, values in responses.items()}
        self.started = {state: anyio.Event() for state in responses}
        self.release = {state: anyio.Event() for state in responses}
        self.finalized = {state: anyio.Event() for state in responses}
        self.requests: list[tuple[str, httpx2.Request]] = []
        self.completed: list[str] = []
        self.active = 0
        self.peak_active = 0
        self.closed = False

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        state = request_adapter.validate_json(request.content)['state']
        assert isinstance(state, str)
        self.requests.append((state, request))
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        self.started[state].set()
        try:
            await self.release[state].wait()
            response = self.responses[state].popleft()
            response.request = request
            self.completed.append(state)
            return response
        finally:
            self.active -= 1
            self.finalized[state].set()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize('async_backend', ['asyncio', 'trio'])
def test_evaluate_many_orders_results_bounds_work_and_pulls_lazily(async_backend: str) -> None:
    async def scenario() -> None:
        transport = GatedTransport(
            {
                '0': [noul_response(0.1, 'request-0')],
                '1': [noul_response(0.2, 'request-1')],
                '2': [httpx2.Response(429, json={'detail': 'Retry'}), noul_response(0.3, 'request-2')],
            }
        )
        pulled: list[str] = []

        def states() -> Iterator[str]:
            for state in ('0', '1', '2'):
                pulled.append(state)
                yield state

        retry = typesafe_sdk.RetryPolicy(
            max_retries=1, backoff_initial=0, backoff_max=0, backoff_jitter=0, respect_retry_after=False
        )
        async with typesafe_sdk.AsyncTypeSafeClient(
            api_key='offline-key', base_url='https://jevantic.invalid', transport=transport, retry=retry
        ) as client:
            evaluator = Jevaluator(client=client)
            results: list[Jevaluation[NoulAnswer]] = []

            async def evaluate() -> None:
                results.extend(await evaluator.evaluate_many(states(), Question.noul(), concurrency=2))

            with anyio.fail_after(2):
                async with anyio.create_task_group() as group:
                    group.start_soon(evaluate)
                    await transport.started['0'].wait()
                    await transport.started['1'].wait()
                    assert pulled == ['0', '1']
                    assert transport.peak_active == 2
                    transport.release['1'].set()
                    await transport.started['2'].wait()
                    transport.release['2'].set()
                    await transport.finalized['2'].wait()
                    transport.release['0'].set()
            assert [result.value for result in results] == [NoulAnswer(0.1), NoulAnswer(0.2), NoulAnswer(0.3)]
            assert [result.info.request_id for result in results] == ['request-0', 'request-1', 'request-2']
            assert [
                request_adapter.validate_json(result.info.raw_http_response.request.content)['state']
                for result in results
            ] == ['0', '1', '2']
            assert all(result.info.model == 'jev-fanout-version' for result in results)
            assert transport.completed[0] == '1'
            assert transport.peak_active == 2
            retry_headers = [
                request.headers.get('x-typesafe-retry-count') for state, request in transport.requests if state == '2'
            ]
            assert retry_headers == [None, '1']

    anyio.run(scenario, backend=async_backend)


class ForbiddenInputs:
    def __iter__(self) -> Iterator[str]:
        raise AssertionError('Invalid concurrency must not consume the input')


@pytest.mark.parametrize(
    ('concurrency', 'error_type'),
    [(0, ValueError), (-1, ValueError), (False, ValueError), (True, ValueError), (1.5, TypeError)],
)
async def test_evaluate_many_validates_concurrency_before_input_or_io(
    backend: Backend, concurrency: object, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        await Jevaluator(client=backend.client).evaluate_many(
            ForbiddenInputs(),
            Question.noul(),
            concurrency=concurrency,  # pyright: ignore[reportArgumentType]
        )
    assert backend.transport.requests == []


async def test_evaluate_many_empty_input_makes_no_request(backend: Backend) -> None:
    results = await Jevaluator(client=backend.client).evaluate_many((), Question.noul(), concurrency=2)
    assert (results, backend.transport.requests) == ([], [])


class FailingInputs(Iterator[str]):
    def __init__(self, error: Exception, *, at_creation: bool) -> None:
        self.error = error
        self.at_creation = at_creation

    def __iter__(self) -> Iterator[str]:
        if self.at_creation:
            raise self.error
        return self

    def __next__(self) -> str:
        raise self.error


@pytest.mark.parametrize('at_creation', [False, True])
async def test_evaluate_many_groups_input_iterator_failures(backend: Backend, at_creation: bool) -> None:
    error = RuntimeError('Source failed')
    with pytest.raises(exception_group_type) as caught:
        await Jevaluator(client=backend.client).evaluate_many(
            FailingInputs(error, at_creation=at_creation), Question.noul(), concurrency=1
        )
    assert caught.value.exceptions == (error,)
    assert backend.transport.requests == []


async def test_evaluate_many_cancels_workers_and_annotates_original_error() -> None:
    private_state = 'synthetic-private-input'
    transport = GatedTransport(
        {
            private_state: [httpx2.Response(401, json={'detail': 'No access'})],
            'blocked': [noul_response(0.5, 'unused')],
        }
    )
    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-key',
        base_url='https://jevantic.invalid',
        transport=transport,
        retry=typesafe_sdk.RetryPolicy(max_retries=0),
    ) as client:
        task = asyncio.create_task(
            Jevaluator(client=client).evaluate_many([private_state, 'blocked'], Question.noul(), concurrency=2)
        )
        await asyncio.wait_for(transport.started[private_state].wait(), timeout=2)
        await asyncio.wait_for(transport.started['blocked'].wait(), timeout=2)
        transport.release[private_state].set()
        with pytest.raises(exception_group_type) as caught:
            await task
        assert len(caught.value.exceptions) == 1
        error = caught.value.exceptions[0]
        assert isinstance(error, typesafe_sdk.TypeSafeAuthenticationError)
        assert error.__notes__ == ['Jevantic input index: 0']
        assert private_state not in '\n'.join(error.__notes__)
        assert transport.finalized['blocked'].is_set()
        assert not transport.closed


@pytest.mark.parametrize('owned', [False, True])
async def test_evaluate_many_cancellation_cleans_workers_and_preserves_ownership(
    owned: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = GatedTransport(
        {
            '0': [noul_response(0.1, 'unused-0')],
            '1': [noul_response(0.2, 'unused-1')],
            'probe': [noul_response(0.7, 'probe', name='q')],
        }
    )
    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-key', base_url='https://jevantic.invalid', transport=transport
    ) as client:

        def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
            return client

        monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
        evaluator = Jevaluator() if owned else Jevaluator(client=client)

        async def evaluate() -> None:
            async with evaluator:
                await evaluator.evaluate_many(['0', '1'], Question.noul(), concurrency=2)

        task = asyncio.create_task(evaluate())
        await asyncio.wait_for(transport.started['0'].wait(), timeout=2)
        await asyncio.wait_for(transport.started['1'].wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.finalized['0'].is_set() and transport.finalized['1'].is_set()
        assert transport.closed is owned
        if not owned:
            transport.release['probe'].set()
            probe = await client.system_one('probe', {'q': typesafe_sdk.Noul()})
            assert probe.nouls['q'].noul == 0.7
    assert transport.closed
