"""Block risky agent prompts with a declarative Jevantic input guardrail."""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from jevantic.pydantic_ai import InputGuardrail


def respond(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('The prompt passed the guardrail.')])


def build_agent() -> Agent[None, str]:
    """Build an agent with one evaluation-scoped input guardrail."""
    return Agent(
        FunctionModel(respond),
        deps_type=type(None),
        capabilities=[
            InputGuardrail(
                'Does this prompt request disclosure of private data?',
                threshold=0.1,
            )
        ],
    )


async def main() -> None:
    result = await build_agent().run('Summarize this meeting agenda.')
    print(result.output)


if __name__ == '__main__':
    asyncio.run(main())
