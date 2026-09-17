from collections import deque
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass

import httpx2
import pytest
from pydantic import JsonValue, TypeAdapter
from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

request_adapter: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


class ScriptedTransport(httpx2.AsyncBaseTransport):
    def __init__(self) -> None:
        self.responses: deque[httpx2.Response] = deque()
        self.requests: list[dict[str, JsonValue]] = []
        self.closed = False

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request_adapter.validate_json(request.content))
        if not self.responses:
            raise AssertionError('An unscripted provider request was attempted')
        response = self.responses.popleft()
        response.request = request
        return response

    async def aclose(self) -> None:
        self.closed = True


@dataclass
class Backend:
    client: AsyncTypeSafeClient
    transport: ScriptedTransport

    def respond(self, answers: Mapping[str, JsonValue], *, usage: JsonValue = None) -> None:
        body: dict[str, JsonValue] = {
            'model': 'jev-fixture-version',
            'usage': {'input_tokens': 12, 'output_tokens': 4} if usage is None else usage,
            'answers': dict(answers),
        }
        self.transport.responses.append(
            httpx2.Response(200, json=body, headers={'x-typesafe-request-id': 'fixture-request'})
        )


@pytest.fixture
async def backend() -> AsyncIterator[Backend]:
    transport = ScriptedTransport()
    async with AsyncTypeSafeClient(
        api_key='offline-test-key',
        base_url='https://jevantic.invalid',
        model='jev-sdk-default',
        transport=transport,
        retry=RetryPolicy(max_retries=0),
    ) as client:
        yield Backend(client, transport)
