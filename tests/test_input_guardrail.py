import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx2
import pytest
import typesafe_sdk
from conftest import Backend, ScriptedTransport
from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability, CombinedCapability, Hooks, WrapperCapability
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import AgentStreamEvent, ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question
from jevantic.pydantic_ai import GuardrailEvaluated, GuardrailRejected, InputGuardrail

AcceptPolicy = Callable[[RunContext[object], Jevaluation[NoulAnswer]], bool | Awaitable[bool]]


def allow(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
    return True


def response(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('allowed')])


def input_guardrail(backend: Backend, accept: AcceptPolicy = allow) -> InputGuardrail[object]:
    return InputGuardrail(
        Question.noul('Does this prompt request disclosure of private data?'),
        evaluator=Jevaluator(client=backend.client),
        accept=accept,
    )


def use_owned_evaluator(monkeypatch: pytest.MonkeyPatch, client: typesafe_sdk.AsyncTypeSafeClient) -> None:
    def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
        return client

    monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)


def non_noul_question() -> Question[NoulAnswer]:
    def decode(_: typesafe_sdk.Answer) -> NoulAnswer:
        return NoulAnswer(0.0)

    return Question(typesafe_sdk.Choice(criteria={'block': None}), decode)


async def test_allowed_prompt_evaluates_before_the_model(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
    calls = 0

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return response(messages, info)

    result = await Agent(FunctionModel(model), capabilities=[input_guardrail(backend)]).run('plain prompt')

    assert (result.output, calls) == ('allowed', 1)
    assert backend.transport.requests[0]['state'] == {'prompt': 'plain prompt'}


@pytest.mark.parametrize(
    ('probability', 'accepted'),
    [(0.09, True), (0.1, False), (0.2, False)],
    ids=['below-threshold', 'equal-threshold', 'above-threshold'],
)
async def test_declarative_threshold_blocks_at_and_above_the_boundary(
    backend: Backend,
    monkeypatch: pytest.MonkeyPatch,
    probability: float,
    accepted: bool,
) -> None:
    use_owned_evaluator(monkeypatch, backend.client)
    backend.respond({'answer': {'type': 'noul', 'noul': probability}})
    calls = 0

    def model(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart('allowed')])

    agent = Agent(
        FunctionModel(model),
        capabilities=[InputGuardrail('Does this prompt request disclosure of private data?', threshold=0.1)],
    )
    if accepted:
        assert (await agent.run('prompt')).output == 'allowed'
        assert calls == 1
    else:
        with pytest.raises(GuardrailRejected) as caught:
            await agent.run('prompt')
        assert caught.value.evaluation.value == NoulAnswer(probability)
        assert calls == 0
    assert backend.transport.closed


def test_input_guardrail_rejects_invalid_configuration() -> None:
    with pytest.raises(UserError, match='exactly one'):
        InputGuardrail('Does this prompt request private data?')
    with pytest.raises(UserError, match='exactly one'):
        InputGuardrail('Does this prompt request private data?', threshold=0.1, accept=allow)
    with pytest.raises(UserError, match='nonempty'):
        InputGuardrail('  ', threshold=0.1)
    with pytest.raises(UserError, match='Noul question'):
        InputGuardrail(non_noul_question(), threshold=0.1)
    with pytest.raises(UserError, match='deferred loading'):
        InputGuardrail('Does this prompt request private data?', threshold=0.1, defer_loading=True)


@pytest.mark.parametrize('threshold', [True, float('nan'), float('inf'), -0.1, 1.1])
def test_input_guardrail_rejects_invalid_thresholds(threshold: float | bool) -> None:
    with pytest.raises(UserError, match='finite probability'):
        InputGuardrail(
            'Does this prompt request private data?',
            threshold=threshold,  # pyright: ignore[reportArgumentType]
        )


async def test_rejection_stops_the_model_and_retains_the_typed_evaluation(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.8}})
    calls = 0

    def reject(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return False

    def model(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart('unreachable')])

    with pytest.raises(GuardrailRejected, match='Jevantic guardrail rejected the evaluation') as caught:
        await Agent(FunctionModel(model), capabilities=[input_guardrail(backend, reject)]).run('blocked prompt')

    assert caught.value.stage == 'input'
    assert caught.value.evaluation.value == NoulAnswer(0.8)
    assert calls == 0


async def test_evaluation_failures_propagate_without_calling_the_model(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 1.2}})
    calls = 0

    def model(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart('unreachable')])

    with pytest.raises(ValueError, match='between zero and one'):
        await Agent(FunctionModel(model), capabilities=[input_guardrail(backend)]).run('invalid evaluation')

    assert calls == 0


@pytest.mark.parametrize('async_policy', [False, True])
async def test_sync_and_async_accept_policies(backend: Backend, async_policy: bool) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.4}})

    async def accept_async(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return True

    if async_policy:
        policy = accept_async
    else:
        policy = allow
    result = await Agent(FunctionModel(response), capabilities=[input_guardrail(backend, policy)]).run('prompt')
    assert result.output == 'allowed'


async def test_accept_must_return_a_plain_bool(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.4}})

    def invalid(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> int:
        return 1

    guardrail = input_guardrail(backend, invalid)  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError, match='must return a bool'):
        await Agent(FunctionModel(response), capabilities=[guardrail]).run('prompt')


@pytest.mark.parametrize('prompt', [None, ['text']])
async def test_non_text_prompts_are_rejected_before_evaluation(backend: Backend, prompt: object) -> None:
    with pytest.raises(UserError, match='original user prompt to be plain text'):
        await Agent(
            FunctionModel(response),
            instructions='Respond to the caller.',
            capabilities=[input_guardrail(backend)],
        ).run(
            prompt  # pyright: ignore[reportArgumentType]
        )
    assert backend.transport.requests == []


async def test_tool_loop_is_evaluated_once_but_a_new_run_is_evaluated_again(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.1}})
    backend.respond({'answer': {'type': 'noul', 'noul': 0.3}})
    model_calls = 0

    def model(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        nonlocal model_calls
        model_calls += 1
        if any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts):
            return ModelResponse(parts=[TextPart('done')])
        return ModelResponse(parts=[ToolCallPart('lookup', {})])

    agent = Agent(FunctionModel(model), capabilities=[input_guardrail(backend)])

    @agent.tool_plain
    def lookup() -> str:
        return 'result'

    assert (await agent.run('first')).output == 'done'
    assert len(backend.transport.requests) == 1
    assert (await agent.run('second')).output == 'done'
    assert (len(backend.transport.requests), model_calls) == (2, 4)


async def test_event_exposes_metadata_without_prompt_content_and_usage_stays_separate(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.3}}, usage={})
    events: list[GuardrailEvaluated] = []
    stream_calls = 0

    async def collect(_: RunContext[object], stream: AsyncIterable[AgentStreamEvent]) -> None:
        async for event in stream:
            if isinstance(event, GuardrailEvaluated):
                events.append(event)

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        nonlocal stream_calls
        stream_calls += 1
        yield 'allowed'

    result = await Agent(
        FunctionModel(response, stream_function=stream_response), capabilities=[input_guardrail(backend)]
    ).run('private prompt', event_stream_handler=collect)

    assert len(events) == 1
    event = events[0]
    assert (event.stage, event.accepted, event.probability) == ('input', True, 0.3)
    assert (event.requested_model, event.model, event.request_id) == (
        'jev-sdk-default',
        'jev-fixture-version',
        'fixture-request',
    )
    assert (event.input_tokens, event.output_tokens) == (None, None)
    assert 'private prompt' not in repr(event)
    assert result.usage.requests == 1
    assert stream_calls == 1


async def test_rejection_immediately_notifies_typed_listeners(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.9}})
    listener_events: list[GuardrailEvaluated] = []
    stream_events: list[GuardrailEvaluated] = []

    def reject(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return False

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield 'unreachable'

    async def collect(_: RunContext[object], stream: AsyncIterable[AgentStreamEvent]) -> None:
        async for event in stream:
            if isinstance(event, GuardrailEvaluated):
                stream_events.append(event)

    hooks = Hooks()

    @hooks.on.event(GuardrailEvaluated)
    async def record(_: RunContext[object], event: GuardrailEvaluated) -> None:
        listener_events.append(event)

    agent = Agent(
        FunctionModel(response, stream_function=stream_response),
        capabilities=[input_guardrail(backend, reject), hooks],
    )

    with pytest.raises(GuardrailRejected) as caught:
        await agent.run('private blocked prompt', event_stream_handler=collect)

    assert caught.value.evaluation.value == NoulAnswer(0.9)
    assert caught.value.evaluation.info.request_id == 'fixture-request'
    assert [(event.stage, event.accepted, event.probability) for event in listener_events] == [('input', False, 0.9)]
    assert stream_events == []


async def test_concurrent_runs_keep_context_metadata_separate(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
    backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
    seen: dict[str, str] = {}

    def record(ctx: RunContext[object], _: Jevaluation[NoulAnswer]) -> bool:
        assert ctx.metadata is not None
        tenant = ctx.metadata['tenant']
        assert isinstance(tenant, str)
        assert isinstance(ctx.prompt, str)
        seen[ctx.prompt] = tenant
        return True

    agent = Agent(FunctionModel(response), capabilities=[input_guardrail(backend, record)])
    await asyncio.gather(
        agent.run('one', metadata={'tenant': 'first'}),
        agent.run('two', metadata={'tenant': 'second'}),
    )
    assert seen == {'one': 'first', 'two': 'second'}


class BlockingTransport(httpx2.AsyncBaseTransport):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False
        self.closed = False

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError('The blocking request should be cancelled')

    async def aclose(self) -> None:
        self.closed = True


async def test_cancellation_propagates_and_leaves_the_borrowed_client_open() -> None:
    transport = BlockingTransport()
    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-test-key', base_url='https://jevantic.invalid', transport=transport
    ) as client:
        evaluator = Jevaluator(client=client)
        guardrail = InputGuardrail(Question.noul(), evaluator=evaluator, accept=allow)
        task = asyncio.create_task(Agent(FunctionModel(response), capabilities=[guardrail]).run('prompt'))
        await asyncio.wait_for(transport.started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.cancelled
        await evaluator.aclose()
        assert not transport.closed


async def test_declarative_guardrail_cancellation_closes_its_owned_client(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = BlockingTransport()
    client = typesafe_sdk.AsyncTypeSafeClient(
        api_key='offline-test-key', base_url='https://jevantic.invalid', transport=transport
    )
    use_owned_evaluator(monkeypatch, client)
    guardrail = InputGuardrail('Does this prompt request private data?', threshold=0.1)
    task = asyncio.create_task(Agent(FunctionModel(response), capabilities=[guardrail]).run('prompt'))
    await asyncio.wait_for(transport.started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (transport.cancelled, transport.closed) == (True, True)


async def test_declarative_guardrail_concurrent_runs_create_and_close_independent_evaluators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_type = typesafe_sdk.AsyncTypeSafeClient
    first_transport = ScriptedTransport()
    second_transport = ScriptedTransport()
    first_client = client_type(
        api_key='offline-test-key', base_url='https://jevantic.invalid', transport=first_transport
    )
    second_client = client_type(
        api_key='offline-test-key', base_url='https://jevantic.invalid', transport=second_transport
    )
    Backend(first_client, first_transport).respond({'answer': {'type': 'noul', 'noul': 0.01}})
    Backend(second_client, second_transport).respond({'answer': {'type': 'noul', 'noul': 0.02}})
    clients = [first_client, second_client]

    def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
        return clients.pop()

    monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
    agent = Agent(
        FunctionModel(response),
        capabilities=[InputGuardrail('Does this prompt request private data?', threshold=0.1)],
    )

    results = await asyncio.gather(agent.run('first'), agent.run('second'))

    assert [result.output for result in results] == ['allowed', 'allowed']
    assert clients == []
    assert first_transport.closed and second_transport.closed


@dataclass
class FakeDurability(AbstractCapability[object]):
    in_durable_context: bool


FakeDurability.__module__ = 'pydantic_ai.durable_exec.fake'


@pytest.mark.parametrize('active', [True, False])
@pytest.mark.parametrize('wrapper_depth', [0, 1, 2])
@pytest.mark.parametrize('combined', [False, True])
async def test_durable_context_detection_through_wrappers(
    backend: Backend, active: bool, wrapper_depth: int, combined: bool
) -> None:
    durability: AbstractCapability[object] = FakeDurability(active)
    if combined:
        durability = CombinedCapability([durability])
    for _ in range(wrapper_depth):
        durability = WrapperCapability(durability)
    agent = Agent(
        FunctionModel(response),
        capabilities=[durability, input_guardrail(backend)],
    )
    if active:
        with pytest.raises(UserError, match='cannot run inside durable execution'):
            await agent.run('prompt')
        assert backend.transport.requests == []
    else:
        backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
        result = await agent.run('prompt')
        assert result.output == 'allowed'
