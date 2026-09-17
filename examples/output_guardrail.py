"""Run a caller-owned Jevantic evaluator as a Pydantic AI output guardrail.

The guardrail evaluates the completed result before `Agent.run()` returns. Streaming consumers
can receive partial and final text before context exit raises; output functions may already have run.
"""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import RunContext

from jevantic import Jevaluation, Jevaluator, NoulAnswer, Question
from jevantic.pydantic_ai import OutputGuardrail

QUESTION = Question.noul('Could this response disclose private data?')


def accept(_: RunContext[None], evaluation: Jevaluation[NoulAnswer]) -> bool:
    """Allow only responses below this application's disclosure-risk threshold."""
    return evaluation.value.probability < 0.5


def respond(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart('The meeting starts at 10:00.')])


def build_agent(evaluator: Jevaluator) -> Agent[None, str]:
    """Build an agent that borrows, and therefore does not close, `evaluator`."""
    return Agent(
        FunctionModel(respond),
        deps_type=type(None),
        capabilities=[OutputGuardrail(evaluator, QUESTION, accept=accept)],
    )


async def main() -> None:
    async with Jevaluator() as evaluator:
        result = await build_agent(evaluator).run('Summarize this meeting agenda.')
    print(result.output)


if __name__ == '__main__':
    asyncio.run(main())
