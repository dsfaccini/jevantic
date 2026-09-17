import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx2
import pytest
import typesafe_sdk
from conftest import Backend
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
        Jevaluator(client=backend.client),
        Question.noul('Does this prompt request disclosure of private data?'),
        accept=accept,
    )


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
        guardrail = InputGuardrail(evaluator, Question.noul(), accept=allow)
        task = asyncio.create_task(Agent(FunctionModel(response), capabilities=[guardrail]).run('prompt'))
        await asyncio.wait_for(transport.started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.cancelled
        await evaluator.aclose()
        assert not transport.closed


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
