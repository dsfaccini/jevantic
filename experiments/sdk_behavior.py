"""Offline behavioral probe for typesafe-sdk 0.6.0 public async APIs.

Every request is routed to a local httpx2 transport; no request can reach
TypeSafe or another network service.
"""

import asyncio
import json
import platform

import httpx2
import msgspec
import typesafe_sdk
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    ChoiceAnswer,
    Noul,
    Question,
    RetryPolicy,
    TypeSafeAPIResponseValidationError,
    TypeSafeInternalServerError,
)


BASE_URL = 'https://typesafe.invalid'
API_KEY = 'offline-test-key'


def success_payload(answers: dict[str, object]) -> dict[str, object]:
    return {
        'model': 'jev-probe',
        'usage': {'input_tokens': 1, 'output_tokens': 1},
        'answers': answers,
    }


def noul_question() -> dict[str, Noul]:
    return {'q': Noul(instructions='Is this an offline probe?')}


def no_delay_retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_retries=1,
        backoff_initial=0.0,
        backoff_max=0.0,
        backoff_jitter=0.0,
        respect_retry_after=False,
        timeout=5.0,
    )


class BlockingTransport(httpx2.AsyncBaseTransport):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.handler_finalized = False
        self.closed = False
        self.attempts = 0
        self._never = asyncio.Event()

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.attempts += 1
        self.started.set()
        try:
            await self._never.wait()
        finally:
            self.handler_finalized = True
        return httpx2.Response(200, json=success_payload({}), request=request)

    async def aclose(self) -> None:
        self.closed = True


class SequenceTransport(httpx2.AsyncBaseTransport):
    def __init__(self, responses: list[tuple[int, dict[str, object], dict[str, str]]]) -> None:
        self.responses = responses
        self.attempts = 0
        self.retry_headers: list[str | None] = []
        self.closed = False

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.attempts += 1
        self.retry_headers.append(request.headers.get('x-typesafe-retry-count'))
        status, body, headers = self.responses.pop(0)
        return httpx2.Response(status, json=body, headers=headers, request=request)

    async def aclose(self) -> None:
        self.closed = True


async def probe_injected_client_lifecycle(results: dict[str, object]) -> None:
    transport = SequenceTransport([])
    injected = httpx2.AsyncClient(transport=transport)
    client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=injected)
    await client.aclose()
    assert injected.is_closed
    assert transport.closed
    results['injected_client_close'] = {
        'injected_is_closed': injected.is_closed,
        'transport_closed': transport.closed,
    }


async def probe_cancellation(results: dict[str, object]) -> None:
    transport = BlockingTransport()
    injected = httpx2.AsyncClient(transport=transport)
    client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=injected)
    task = asyncio.create_task(client.system_one('state', noul_question(), retry=no_delay_retry_policy()))
    await asyncio.wait_for(transport.started.wait(), timeout=1.0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        cancelled = True
    else:
        cancelled = False
    assert cancelled
    assert transport.attempts == 1
    assert transport.handler_finalized
    assert not injected.is_closed
    assert not transport.closed
    await client.aclose()
    assert injected.is_closed
    assert transport.closed
    results['cancellation'] = {
        'propagated': cancelled,
        'attempts': transport.attempts,
        'handler_finalized': transport.handler_finalized,
        'injected_is_closed': injected.is_closed,
        'transport_closed': transport.closed,
    }


async def probe_retries(results: dict[str, object]) -> None:
    rate_transport = SequenceTransport(
        [
            (429, {'detail': 'slow down'}, {'x-typesafe-request-id': 'rate-limit'}),
            (
                200,
                success_payload({'q': {'type': 'noul', 'noul': 0.4}}),
                {'x-typesafe-request-id': 'after-429'},
            ),
        ]
    )
    rate_http = httpx2.AsyncClient(transport=rate_transport)
    rate_client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=rate_http)
    rate_response = await rate_client.system_one('state', noul_question(), retry=no_delay_retry_policy())
    assert rate_transport.attempts == 2
    assert rate_transport.retry_headers == [None, '1']
    assert rate_response.request_id == 'after-429'
    await rate_client.aclose()

    error_transport = SequenceTransport(
        [
            (500, {'detail': 'first failure'}, {'x-typesafe-request-id': 'server-first'}),
            (500, {'detail': 'last failure'}, {'x-typesafe-request-id': 'server-last'}),
        ]
    )
    error_http = httpx2.AsyncClient(transport=error_transport)
    error_client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=error_http)
    try:
        await error_client.system_one('state', noul_question(), retry=no_delay_retry_policy())
    except TypeSafeInternalServerError as error:
        typed_error: dict[str, object] = {
            'type': type(error).__name__,
            'status': error.status,
            'request_id': error.request_id,
        }
    else:
        raise AssertionError('synthetic 500 should raise TypeSafeInternalServerError')
    assert typed_error == {
        'type': 'TypeSafeInternalServerError',
        'status': 500,
        'request_id': 'server-last',
    }
    assert error_transport.attempts == 2
    assert error_transport.retry_headers == [None, '1']
    await error_client.aclose()

    results['retries'] = {
        '429_then_success': {
            'attempts': rate_transport.attempts,
            'retry_headers': rate_transport.retry_headers,
            'request_id': rate_response.request_id,
            'noul': rate_response.nouls['q'].noul,
        },
        '500_then_typed_failure': {
            'attempts': error_transport.attempts,
            'retry_headers': error_transport.retry_headers,
            'error': typed_error,
        },
    }


async def probe_response_validation(results: dict[str, object]) -> None:
    malformed_transport = SequenceTransport(
        [
            (
                200,
                success_payload({'q': {'type': 'noul', 'noul': 'not-a-number'}}),
                {'x-typesafe-request-id': 'bad-known-answer'},
            )
        ]
    )
    malformed_http = httpx2.AsyncClient(transport=malformed_transport)
    malformed_client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=malformed_http)
    try:
        await malformed_client.system_one('state', noul_question())
    except TypeSafeAPIResponseValidationError as error:
        malformed_error: dict[str, object] = {
            'type': type(error).__name__,
            'status': error.status,
            'field_path': error.field_path,
            'request_id': error.request_id,
        }
    else:
        raise AssertionError('malformed known answer should fail validation')
    assert malformed_error == {
        'type': 'TypeSafeAPIResponseValidationError',
        'status': 200,
        'field_path': 'answers.q.noul',
        'request_id': 'bad-known-answer',
    }
    await malformed_client.aclose()

    unknown_transport = SequenceTransport(
        [
            (
                200,
                success_payload(
                    {
                        'q': {'type': 'noul', 'noul': 0.6},
                        'future': {'type': 'new-answer-type', 'value': 'ignored'},
                    }
                ),
                {'x-typesafe-request-id': 'unknown-answer-type'},
            )
        ]
    )
    unknown_http = httpx2.AsyncClient(transport=unknown_transport)
    unknown_client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=unknown_http)
    unknown_response = await unknown_client.system_one('state', noul_question())
    assert list(unknown_response.answers) == ['q']
    assert unknown_response.nouls['q'].noul == 0.6
    raw_body = msgspec.json.decode(unknown_response.raw_http_response.content, type=dict[str, msgspec.Raw])
    raw_answers = msgspec.json.decode(raw_body['answers'], type=dict[str, msgspec.Raw])
    assert set(raw_answers) == {'q', 'future'}
    await unknown_client.aclose()

    results['response_validation'] = {
        'malformed_known_answer': malformed_error,
        'unknown_answer_type': {
            'public_answer_keys': list(unknown_response.answers),
            'raw_answer_keys': list(raw_answers),
            'request_id': unknown_response.request_id,
        },
    }


async def probe_semantic_invariants(results: dict[str, object]) -> None:
    transport = SequenceTransport(
        [
            (
                200,
                success_payload(
                    {
                        'noul': {'type': 'noul', 'noul': 1.5},
                        'choice': {
                            'type': 'choice',
                            'choice': 'outside-requested-options',
                            'probabilities': {'outside-requested-options': 1.2},
                            'confidence': -0.25,
                        },
                    }
                ),
                {'x-typesafe-request-id': 'semantic-invariants'},
            )
        ]
    )
    injected = httpx2.AsyncClient(transport=transport)
    client = AsyncTypeSafeClient(api_key=API_KEY, base_url=BASE_URL, http_client=injected)
    questions: dict[str, Question] = {
        'noul': Noul(instructions='Is this a noul?'),
        'choice': Choice(instructions='Pick one.', criteria={'yes': None, 'no': None}),
        'missing': Noul(instructions='This response deliberately omits me.'),
    }
    response = await client.system_one(
        'state',
        questions,
    )
    choice = response.answers['choice']
    assert isinstance(choice, ChoiceAnswer)
    assert response.nouls['noul'].noul == 1.5
    assert choice.choice == 'outside-requested-options'
    assert choice.probabilities == {'outside-requested-options': 1.2}
    assert choice.confidence == -0.25
    assert 'missing' not in response.answers
    await client.aclose()

    results['unvalidated_semantic_invariants'] = {
        'noul': response.nouls['noul'].noul,
        'choice': choice.choice,
        'probabilities': choice.probabilities,
        'confidence': choice.confidence,
        'response_answer_keys': list(response.answers),
        'request_answer_keys': ['noul', 'choice', 'missing'],
    }


async def main() -> None:
    results: dict[str, object] = {
        'python': platform.python_version(),
        'httpx2': httpx2.__version__,
        'typesafe_sdk': typesafe_sdk.__version__,
        'network': 'all requests use injected local transports with typesafe.invalid base URL',
    }
    await probe_injected_client_lifecycle(results)
    await probe_cancellation(results)
    await probe_retries(results)
    await probe_response_validation(results)
    await probe_semantic_invariants(results)
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == '__main__':
    asyncio.run(main())
