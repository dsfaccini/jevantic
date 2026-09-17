import asyncio

import anyio
import httpx2
import pytest
import typesafe_sdk
from conftest import Backend

from jevantic import Jevaluator, Question


async def test_borrowed_client_remains_usable_after_evaluator_closes(backend: Backend) -> None:
    async with Jevaluator(client=backend.client) as evaluator:
        backend.respond({'answer': {'type': 'noul', 'noul': 0.5}})
        await evaluator.evaluate('state', Question.noul())
        with pytest.raises(RuntimeError, match='cannot be nested'):
            async with evaluator:
                raise AssertionError('Nested context should not enter')
    assert not backend.transport.closed
    await evaluator.aclose()
    backend.respond({'q': {'type': 'noul', 'noul': 0.8}})
    response = await backend.client.system_one('state', {'q': typesafe_sdk.Noul()})
    assert response.nouls['q'].noul == 0.8
    with pytest.raises(RuntimeError, match='closed'):
        await evaluator.evaluate('state', Question.noul())
    with pytest.raises(RuntimeError, match='closed'):
        async with evaluator:
            raise AssertionError('Closed evaluator should not enter')


async def test_created_client_is_closed(backend: Backend, monkeypatch: pytest.MonkeyPatch) -> None:
    api_keys: list[str | None] = []

    def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
        api_keys.append(api_key)
        return backend.client

    monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
    async with Jevaluator(api_key='offline-key') as evaluator:
        backend.respond({'answer': {'type': 'noul', 'noul': 0.5}})
        await evaluator.evaluate('state', Question.noul())
    assert api_keys == ['offline-key']
    assert backend.transport.closed


def test_borrowed_client_credentials_are_not_overridden(backend: Backend) -> None:
    with pytest.raises(ValueError, match='supplied SDK client'):
        Jevaluator(client=backend.client, api_key='different-key')


class BlockingTransport(httpx2.AsyncBaseTransport):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.finalized = False
        self.closed = False
        self.attempts = 0

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.attempts += 1
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.finalized = True
        raise AssertionError('The blocking request should be cancelled')

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize('owned', [False, True])
async def test_cancellation_and_ownership(owned: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = BlockingTransport()
    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-key', base_url='https://jevantic.invalid', transport=transport
    ) as client:

        def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
            return client

        monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
        evaluator = Jevaluator() if owned else Jevaluator(client=client)

        async def evaluate() -> None:
            async with evaluator:
                await evaluator.evaluate('state', Question.noul())

        task = asyncio.create_task(evaluate())
        await asyncio.wait_for(transport.started.wait(), timeout=1.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.finalized
        assert transport.attempts == 1
        assert transport.closed is owned
    assert transport.closed


class DelayedCloseTransport(httpx2.AsyncBaseTransport):
    def __init__(self, error: Exception | None = None) -> None:
        self.started = anyio.Event()
        self.release = anyio.Event()
        self.closed = False
        self.error = error
        self.attempts = 0

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        raise AssertionError('No request expected')

    async def aclose(self) -> None:
        self.attempts += 1
        self.started.set()
        await self.release.wait()
        if self.error is not None:
            raise self.error
        self.closed = True


@pytest.fixture
def closing_transport(monkeypatch: pytest.MonkeyPatch) -> DelayedCloseTransport:
    transport = DelayedCloseTransport()
    client = typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-key', base_url='https://jevantic.invalid', transport=transport
    )

    def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
        return client

    monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
    return transport


async def test_direct_cancellation_waits_for_owned_client_to_close(closing_transport: DelayedCloseTransport) -> None:
    evaluator = Jevaluator()
    task = asyncio.create_task(evaluator.aclose())
    await asyncio.wait_for(closing_transport.started.wait(), timeout=1.0)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    closing_transport.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await evaluator.aclose()
    assert (closing_transport.closed, closing_transport.attempts) == (True, 1)


@pytest.mark.parametrize('backend_name', ['asyncio', 'trio'])
def test_cancel_scope_waits_for_owned_client_to_close(
    backend_name: str, closing_transport: DelayedCloseTransport
) -> None:
    async def scenario() -> None:
        evaluator = Jevaluator()
        with anyio.CancelScope() as scope:

            async def cancel_close() -> None:
                await closing_transport.started.wait()
                scope.cancel()
                closing_transport.release.set()

            async with anyio.create_task_group() as group:
                group.start_soon(cancel_close)
                await evaluator.aclose()
            await anyio.lowlevel.checkpoint()
        assert scope.cancelled_caught
        assert (closing_transport.closed, closing_transport.attempts) == (True, 1)

    anyio.run(scenario, backend=backend_name)


async def test_close_failure_keeps_original_exception(closing_transport: DelayedCloseTransport) -> None:
    closing_transport.error = RuntimeError('Transport close failed')
    closing_transport.release.set()
    with pytest.raises(RuntimeError) as caught:
        await Jevaluator().aclose()
    assert caught.value is closing_transport.error
