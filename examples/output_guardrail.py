"""Check Pydantic AI text output with a declarative Jevantic guardrail.

The guardrail evaluates the completed result before `Agent.run()` returns. Streaming consumers
can receive partial and final text before context exit raises; output functions may already have run.
"""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from jevantic.pydantic_ai import OutputGuardrail


def respond(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('The meeting starts at 10:00.')])


def build_agent() -> Agent[None, str]:
    """Build an agent that blocks output at this application's disclosure-risk threshold."""
    return Agent(
        FunctionModel(respond),
        deps_type=type(None),
        capabilities=[OutputGuardrail('Could this response disclose private data?', threshold=0.1)],
    )


async def main() -> None:
    result = await build_agent().run('Summarize this meeting agenda.')
    print(result.output)


if __name__ == '__main__':
    asyncio.run(main())
