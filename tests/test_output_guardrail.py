import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx2
import pytest
import typesafe_sdk
from conftest import Backend
from pydantic_ai import Agent, AgentRunResult, AgentRunResultEvent
from pydantic_ai.capabilities import AbstractCapability, CapabilityOrdering, Hooks
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import AgentStreamEvent, ModelMessage, ModelResponse, PartStartEvent, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.output import OutputContext
from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question
from jevantic.pydantic_ai import GuardrailEvaluated, GuardrailRejected, OutputGuardrail

AcceptPolicy = Callable[[RunContext[object], Jevaluation[NoulAnswer]], bool | Awaitable[bool]]


def allow(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
    return True


def response(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('allowed')])


def output_guardrail(backend: Backend, accept: AcceptPolicy = allow) -> OutputGuardrail[object]:
    return OutputGuardrail(
        Question.noul('Could this response disclose private data?'),
        evaluator=Jevaluator(client=backend.client),
        accept=accept,
    )


async def test_allowed_output_is_evaluated_after_the_model(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
    calls = 0

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return response(messages, info)

    result = await Agent(FunctionModel(model), capabilities=[output_guardrail(backend)]).run('prompt')

    assert (result.output, calls) == ('allowed', 1)
    assert backend.transport.requests[0]['state'] == {'output': 'allowed'}


async def test_threshold_allows_an_output_below_the_threshold(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.09}})
    guardrail = OutputGuardrail(
        'Could this response disclose private data?',
        threshold=0.1,
        evaluator=Jevaluator(client=backend.client),
    )

    result = await Agent(FunctionModel(response), capabilities=[guardrail]).run('prompt')

    assert result.output == 'allowed'
    assert backend.transport.requests[0]['state'] == {'output': 'allowed'}


async def test_threshold_rejects_equality_and_closes_an_owned_evaluator(
    backend: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    created_api_keys: list[str | None] = []

    def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
        created_api_keys.append(api_key)
        return backend.client

    monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
    backend.respond({'answer': {'type': 'noul', 'noul': 0.1}})

    with pytest.raises(GuardrailRejected) as caught:
        await Agent(
            FunctionModel(response),
            capabilities=[OutputGuardrail('Could this response disclose private data?', threshold=0.1)],
        ).run('prompt')

    assert caught.value.evaluation.value == NoulAnswer(0.1)
    assert created_api_keys == [None]
    assert backend.transport.closed


async def test_no_evaluator_is_created_when_the_run_fails_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = False

    def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
        nonlocal created
        created = True
        raise AssertionError('The evaluator should not be created')

    def fail(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        raise RuntimeError('model failed')

    monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)

    with pytest.raises(RuntimeError, match='model failed'):
        await Agent(
            FunctionModel(fail),
            capabilities=[OutputGuardrail('Could this response disclose private data?', threshold=0.1)],
        ).run('prompt')

    assert not created


class ReplaceProcessedOutput(AbstractCapability[object]):
    async def after_output_process(
        self, ctx: RunContext[object], *, output_context: OutputContext, output: object
    ) -> object:
        return 'replacement text'


@dataclass
class ReplaceRunOutput(AbstractCapability[object]):
    outermost: bool = False

    def get_ordering(self) -> CapabilityOrdering | None:
        return CapabilityOrdering(position='outermost') if self.outermost else None

    async def after_run(self, ctx: RunContext[object], *, result: AgentRunResult[object]) -> AgentRunResult[object]:
        result.output = 'replacement text'
        return result


@pytest.mark.parametrize('replacement', [ReplaceProcessedOutput(), ReplaceRunOutput()])
@pytest.mark.parametrize('guard_first', [True, False])
async def test_guardrail_evaluates_output_after_other_capability_transformations(
    backend: Backend, replacement: AbstractCapability[object], guard_first: bool
) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
    guardrail = output_guardrail(backend)
    capabilities: list[AbstractCapability[object]] = (
        [guardrail, replacement] if guard_first else [replacement, guardrail]
    )

    result = await Agent(FunctionModel(response), capabilities=capabilities).run('prompt')

    assert result.output == 'replacement text'
    assert backend.transport.requests[0]['state'] == {'output': 'replacement text'}


async def test_guardrail_precedes_other_outermost_result_transformers(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.2}})
    result = await Agent(
        FunctionModel(response),
        capabilities=[output_guardrail(backend), ReplaceRunOutput(outermost=True)],
    ).run('prompt')

    assert result.output == 'replacement text'
    assert backend.transport.requests[0]['state'] == {'output': 'replacement text'}


async def test_rejection_retains_the_evaluation_after_the_model_ran(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.8}})
    calls = 0

    def reject(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return False

    def model(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart('blocked')])

    with pytest.raises(GuardrailRejected, match='Jevantic guardrail rejected the evaluation') as caught:
        await Agent(FunctionModel(model), capabilities=[output_guardrail(backend, reject)]).run('prompt')

    assert caught.value.stage == 'output'
    assert caught.value.evaluation.value == NoulAnswer(0.8)
    assert calls == 1
    assert backend.transport.requests[0]['state'] == {'output': 'blocked'}


async def test_evaluation_failures_propagate_after_the_model(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 1.2}})
    calls = 0

    def model(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart('invalid evaluation')])

    with pytest.raises(ValueError, match='between zero and one'):
        await Agent(FunctionModel(model), capabilities=[output_guardrail(backend)]).run('prompt')

    assert calls == 1


@pytest.mark.parametrize('async_policy', [False, True])
async def test_sync_and_async_accept_policies(backend: Backend, async_policy: bool) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.4}})

    async def accept_async(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return True

    policy = accept_async if async_policy else allow
    result = await Agent(FunctionModel(response), capabilities=[output_guardrail(backend, policy)]).run('prompt')

    assert result.output == 'allowed'


async def test_structured_output_is_rejected_before_evaluation(backend: Backend) -> None:
    def structured(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        assert info.output_tools is not None
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, '{"response": 1}')])

    with pytest.raises(UserError, match='final output to be plain text'):
        await Agent(FunctionModel(structured), output_type=int, capabilities=[output_guardrail(backend)]).run('prompt')

    assert backend.transport.requests == []


async def test_event_includes_metadata_and_keeps_usage_separate(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.3}}, usage={})
    listener_events: list[GuardrailEvaluated] = []
    stream_events: list[GuardrailEvaluated] = []
    stream_calls = 0

    async def collect(_: RunContext[object], stream: AsyncIterable[AgentStreamEvent]) -> None:
        async for event in stream:
            if isinstance(event, GuardrailEvaluated):
                stream_events.append(event)

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        nonlocal stream_calls
        stream_calls += 1
        yield 'allowed'

    hooks = Hooks()

    @hooks.on.event(GuardrailEvaluated)
    async def record(_: RunContext[object], event: GuardrailEvaluated) -> None:
        listener_events.append(event)

    result = await Agent(
        FunctionModel(response, stream_function=stream_response),
        capabilities=[output_guardrail(backend), hooks],
    ).run('private prompt', event_stream_handler=collect)

    assert len(listener_events) == 1
    event = listener_events[0]
    assert (event.stage, event.accepted, event.probability) == ('output', True, 0.3)
    assert (event.requested_model, event.model, event.request_id) == (
        'jev-sdk-default',
        'jev-fixture-version',
        'fixture-request',
    )
    assert (event.input_tokens, event.output_tokens) == (None, None)
    assert 'private prompt' not in repr(event)
    assert stream_events == []
    assert result.usage.requests == 1
    assert stream_calls == 1


async def test_streamed_deltas_can_precede_a_final_rejection(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.9}})
    deltas: list[str] = []

    def reject(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return False

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield 'first '
        yield 'second'

    agent = Agent(
        FunctionModel(response, stream_function=stream_response), capabilities=[output_guardrail(backend, reject)]
    )

    with pytest.raises(GuardrailRejected):
        async with agent.run_stream('prompt') as result:
            async for delta in result.stream_text(delta=True, debounce_by=None):
                deltas.append(delta)

    assert deltas == ['first ', 'second']
    assert backend.transport.requests[0]['state'] == {'output': 'first second'}


async def test_streamed_partial_and_final_outputs_precede_completion_check(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.9}})
    partial_outputs: list[str] = []

    def reject(_: RunContext[object], __: Jevaluation[NoulAnswer]) -> bool:
        return False

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield 'first '
        yield 'second'

    agent = Agent(
        FunctionModel(response, stream_function=stream_response), capabilities=[output_guardrail(backend, reject)]
    )

    with pytest.raises(GuardrailRejected):
        async with agent.run_stream('prompt') as result:
            async for output in result.stream_output(debounce_by=None):
                partial_outputs.append(output)
            assert await result.get_output() == 'first second'
            assert backend.transport.requests == []

    assert partial_outputs == ['first ', 'first second', 'first second']
    assert backend.transport.requests[0]['state'] == {'output': 'first second'}


async def test_rejected_event_stream_exposes_text_but_no_completed_result(backend: Backend) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': 0.9}})
    events: list[AgentStreamEvent | AgentRunResultEvent[str]] = []

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield 'unaccepted text'

    agent = Agent(
        FunctionModel(response, stream_function=stream_response),
        capabilities=[output_guardrail(backend, lambda _ctx, _evaluation: False)],
    )
    with pytest.raises(GuardrailRejected):
        async with agent.run_stream_events('prompt') as stream:
            async for event in stream:
                events.append(event)

    assert any(isinstance(event, PartStartEvent) and isinstance(event.part, TextPart) for event in events)
    assert not any(isinstance(event, AgentRunResultEvent) for event in events)


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
        guardrail = OutputGuardrail(Question.noul(), evaluator=evaluator, accept=allow)
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


async def test_active_durability_is_rejected_before_the_model(backend: Backend) -> None:
    calls = 0

    def model(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart('unreachable')])

    agent = Agent(
        FunctionModel(model),
        capabilities=[FakeDurability(True), output_guardrail(backend)],
    )
    with pytest.raises(UserError, match='cannot run inside durable execution'):
        await agent.run('prompt')

    assert (calls, backend.transport.requests) == (0, [])
