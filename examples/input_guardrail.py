"""Run a caller-owned Jevantic evaluator as a Pydantic AI input guardrail."""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question
from jevantic.pydantic_ai import InputGuardrail

QUESTION = Question.noul('Does this prompt request disclosure of private data?')


def accept(_: RunContext[None], evaluation: Jevaluation[NoulAnswer]) -> bool:
    """Apply this application's probability threshold to the complete evaluation."""
    return evaluation.value.probability < 0.5


def respond(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('The prompt passed the guardrail.')])


def build_agent(evaluator: Jevaluator) -> Agent[None, str]:
    """Build an agent that borrows, and therefore does not close, `evaluator`."""
    return Agent(
        FunctionModel(respond),
        deps_type=type(None),
        capabilities=[InputGuardrail(evaluator, QUESTION, accept=accept)],
    )


async def main() -> None:
    async with Jevaluator() as evaluator:
        result = await build_agent(evaluator).run('Summarize this meeting agenda.')
    print(result.output)


if __name__ == '__main__':
    asyncio.run(main())
