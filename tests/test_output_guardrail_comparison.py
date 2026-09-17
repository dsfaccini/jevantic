from collections.abc import AsyncIterator

import pytest
import typesafe_sdk
from conftest import Backend
from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import RunContext

from examples.output_guardrail_comparison import output_guardrail_after, output_guardrail_before
from jevantic import Jevaluator
from jevantic.pydantic_ai import GuardrailEvaluated, GuardrailRejected


def response(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('completed output')])


@pytest.mark.parametrize('declarative', [False, True], ids=['explicit', 'declarative'])
@pytest.mark.parametrize(('probability', 'accepted'), [(0.09, True), (0.1, False)])
async def test_output_guardrail_builders_make_the_same_completed_output_decision(
    backend: Backend,
    monkeypatch: pytest.MonkeyPatch,
    declarative: bool,
    probability: float,
    accepted: bool,
) -> None:
    backend.respond({'answer': {'type': 'noul', 'noul': probability}})
    condition = 'Could this response disclose private data?'
    if declarative:

        def create_client(*, api_key: str | None) -> typesafe_sdk.AsyncTypeSafeClient:
            return backend.client

        monkeypatch.setattr(typesafe_sdk, 'AsyncTypeSafeClient', create_client)
        guardrail = output_guardrail_after(condition)
    else:
        guardrail = output_guardrail_before(Jevaluator(client=backend.client), condition)

    events: list[GuardrailEvaluated] = []
    hooks = Hooks()

    @hooks.on.event(GuardrailEvaluated)
    async def record(_: RunContext[None], event: GuardrailEvaluated) -> None:
        events.append(event)

    calls = 0

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        nonlocal calls
        calls += 1
        yield 'completed output'

    agent = Agent(
        FunctionModel(response, stream_function=stream_response),
        deps_type=type(None),
        capabilities=[guardrail, hooks],
    )
    if accepted:
        result = await agent.run('prompt')
        assert result.output == 'completed output'
        assert result.usage.requests == 1
    else:
        with pytest.raises(GuardrailRejected) as caught:
            await agent.run('prompt')
        assert caught.value.evaluation.value.probability == probability

    assert calls == 1
    assert backend.transport.requests[0]['state'] == {'output': 'completed output'}
    assert [(event.stage, event.accepted, event.probability) for event in events] == [('output', accepted, probability)]
    assert (events[0].input_tokens, events[0].output_tokens) == (12, 4)
