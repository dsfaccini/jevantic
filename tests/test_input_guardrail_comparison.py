from collections.abc import AsyncIterator
from typing import Literal

import pytest
import typesafe_sdk
from conftest import Backend
from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import RunContext

from examples.input_guardrail_comparison import input_guardrail_after, input_guardrail_before
from jevantic import Jevaluator
from jevantic.pydantic_ai import GuardrailEvaluated, GuardrailRejected


def response(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('allowed')])


@pytest.mark.parametrize(
    ('implementation', 'probability', 'accepted'),
    [
        ('before', 0.09, True),
        ('before', 0.1, False),
        ('after', 0.09, True),
        ('after', 0.1, False),
    ],
)
async def test_input_guardrail_comparison_has_equivalent_agent_behavior(
    backend: Backend,
    monkeypatch: pytest.MonkeyPatch,
    implementation: Literal['before', 'after'],
    probability: float,
    accepted: bool,
) -> None:
    condition = 'Does this prompt request disclosure of private data?'
    backend.respond({'answer': {'type': 'noul', 'noul': probability}})
    if implementation == 'before':
        guardrail = input_guardrail_before(Jevaluator(client=backend.client), condition)
    else:

        def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
            return backend.client

        monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
        guardrail = input_guardrail_after(condition)
    events: list[GuardrailEvaluated] = []
    hooks = Hooks()

    @hooks.on.event(GuardrailEvaluated)
    async def record(_: RunContext[None], event: GuardrailEvaluated) -> None:
        events.append(event)

    stream_calls = 0

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        nonlocal stream_calls
        stream_calls += 1
        yield 'allowed'

    agent = Agent(
        FunctionModel(response, stream_function=stream_response),
        deps_type=type(None),
        capabilities=[guardrail, hooks],
    )
    if accepted:
        result = await agent.run('Summarize this agenda.')
        assert (result.output, result.usage.requests, stream_calls) == ('allowed', 1, 1)
    else:
        with pytest.raises(GuardrailRejected):
            await agent.run('Summarize this agenda.')
        assert stream_calls == 0
    assert [(event.stage, event.accepted, event.probability) for event in events] == [('input', accepted, probability)]
    assert (events[0].requested_model, events[0].model, events[0].request_id) == (
        'jev-sdk-default',
        'jev-fixture-version',
        'fixture-request',
    )
    assert (events[0].input_tokens, events[0].output_tokens) == (12, 4)
    assert backend.transport.requests == [
        {
            'model': 'jev-sdk-default',
            'state': {'prompt': 'Summarize this agenda.'},
            'questions': {
                'answer': {
                    'type': 'noul',
                    'instructions': condition,
                    'criteria': {'true': None, 'false': None},
                }
            },
        }
    ]
    assert backend.transport.closed is (implementation == 'after')
