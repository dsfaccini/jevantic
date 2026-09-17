import pytest
from conftest import Backend
from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import UserError

from jevantic import Jevaluator, Question
from jevantic.pydantic_ai import InputGuardrail, OutputGuardrail


@pytest.mark.parametrize('capability_type', [InputGuardrail, OutputGuardrail])
def test_callback_capabilities_reject_spec_registration(capability_type: type[AbstractCapability[object]]) -> None:
    with pytest.raises(ValueError, match=f'Custom capability class {capability_type.__name__} has opted out'):
        Agent.from_spec({}, custom_capability_types=[capability_type])


@pytest.mark.parametrize('guardrail_type', [InputGuardrail, OutputGuardrail])
def test_guardrails_reject_deferred_loading(
    backend: Backend, guardrail_type: type[InputGuardrail[object] | OutputGuardrail[object]]
) -> None:
    with pytest.raises(UserError, match='cannot use deferred loading'):
        guardrail_type(
            Jevaluator(client=backend.client),
            Question.noul(),
            accept=lambda _ctx, _evaluation: True,
            id='guard',
            defer_loading=True,
        )
    assert backend.transport.requests == []
