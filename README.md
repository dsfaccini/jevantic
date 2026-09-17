# Jevantic

Jevantic gives Python programs typed, probabilistic decisions from Jev. Define a question, evaluate application state, and receive an answer whose type matches the question: a probability, a typed label, an original local object, or a scored rubric.

Jevantic is an experimental alpha. Its public API may change as complete workflows reveal better interfaces. It is standalone, with optional Pydantic AI capabilities in its `pydantic-ai` extra.

## Install

The first alpha is being prepared for PyPI. Once it is available, add the core package or the optional Pydantic AI capability extra:

```sh
uv add jevantic
uv add 'jevantic[pydantic-ai]'
```

## Start with one decision

The examples below assume `evaluator` is already open. In application code, `async with Jevaluator() as evaluator:` creates a TypeSafe SDK client from its normal environment configuration, or pass `api_key=` explicitly.

```python
from jevantic import Jevaluator, Question

question = Question.noul(
    'Could this command disclose credentials outside the workspace?',
    true='The command could disclose sensitive data.',
    false='The command stays within its intended workspace.',
)

assessment = await evaluator.evaluate({'command': 'printenv'}, question)
risk = assessment.value.probability
# 0.82  # illustrative provider result; float
```

`Question.noul()` produces a `NoulAnswer` with the probability of its yes outcome. Probabilities in this README are illustrative values, not measured model output or policy thresholds.

## Keep the answer type you chose

Use `Question.choice()` when the answer is one of typed string labels. Annotating the labels retains a `Literal` or `StrEnum` type after evaluation.

```python
from typing import Literal

from jevantic import JsonContent, Question

Route = Literal['send', 'review']
routes: dict[Route, JsonContent | None] = {
    'send': 'The message is ready for its intended audience.',
    'review': 'A person should review the message before it is sent.',
}

route = (await evaluator.evaluate('Draft: deploy production now', Question.choice(routes))).value
route.selected
# 'review'  # illustrative provider result; Route
route.distribution[0].value
# 'send'  # Route
```

Use `Question.select()` when a label represents an object your program already owns. Jev receives each key and description; the selected answer returns the original object.

```python
from dataclasses import dataclass

from jevantic import Option, Question


@dataclass(frozen=True)
class Candidate:
    identifier: str
    summary: str


alba = Candidate('alba', 'Built the search service')
bryn = Candidate('bryn', 'Led support engineering')

question = Question.select(
    [
        Option(alba.identifier, alba, alba.summary),
        Option(bryn.identifier, bryn, bryn.summary),
    ],
    instructions='Select the candidate whose experience best fits the role.',
)
candidate = (await evaluator.evaluate('Role: lead search engineering', question)).value.selected
assert candidate is alba  # Candidate; illustrative selected identity
```

Object identity matters when the selected value carries application-only fields, connections, or relationships that must never be reconstructed from a model label.

## Score against a rubric

`Question.score()` preserves a fractional `ScoreAnswer`, its probability distribution, rubric legend, and provider confidence.

```python
from jevantic import Question

quality = await evaluator.evaluate(
    'Draft: Jevantic asks structured decision questions.',
    Question.score(['Does not explain the library', 'Explains part of the library', 'Clear explanation']),
)
quality.value.score
# 1.6  # illustrative provider result; float on the 0–2 rubric
quality.value.probabilities
# {0: 0.1, 1: 0.2, 2: 0.7}  # illustrative provider result; Mapping[int, float]
```

## Evaluate several questions over shared state

A `Batch` evaluates independent questions against one state in one provider request. `batch.add()` returns a typed `Handle`, so a mixed batch keeps every answer's precise type.

```python
from jevantic import Question

batch = evaluator.batch('Draft: deploy production now')
risk = batch.add('risk', Question.noul('Could the draft cause operational harm?'))
route = batch.add('route', Question.choice(routes))
quality = batch.add('quality', Question.score(['unclear', 'adequate', 'clear']))

result = await batch.run()
result.answer(risk).probability
# 0.31  # illustrative provider result; float
result.answer(route).selected
# 'review'  # illustrative provider result; Route
result.answer(quality).score
# 1.8  # illustrative provider result; float
```

Questions are ordinary Python values, so functions can build reusable questions from application inputs:

```python
from jevantic import NoulAnswer, Question


def relevance_question(query: str) -> Question[NoulAnswer]:
    return Question.noul(f'Does this document answer {query!r}?')


evaluation = await evaluator.evaluate('Document: …', relevance_question('How do I install Jevantic?'))
```

## Evaluate one question over independent inputs

Use `evaluate_many()` when every input needs a separate evaluation. Set `concurrency` explicitly for your traffic and provider limits; results retain the input order.

```python
from jevantic import Question

documents = ['First document', 'Second document', 'Third document']
evaluations = await evaluator.evaluate_many(
    documents,
    Question.noul('Does this document answer the user question?'),
    concurrency=4,
)
[evaluation.value.probability for evaluation in evaluations]
# [0.91, 0.12, 0.73]  # illustrative provider results; list[float], input order
```

For a complete ranking function that keeps the original document objects and preserves tied order, see [the document-ranking example](https://github.com/dsfaccini/jevantic/blob/main/examples/ranking.py). For a complete assessment function with two `Score` questions, see [the assessment example](https://github.com/dsfaccini/jevantic/blob/main/examples/assessments.py).

## Guard an agent's input

`InputGuardrail` evaluates an original plain-text prompt with a `Noul` question before the first model request. Its `accept` policy receives the complete typed evaluation; returning `False` prevents the primary model from running.

```python
from pydantic_ai import Agent

from jevantic import Jevaluator, Question
from jevantic.pydantic_ai import InputGuardrail

question = Question.noul('Does this prompt request disclosure of private data?')

async with Jevaluator() as evaluator:
    agent = Agent(
        existing_model,
        capabilities=[
            InputGuardrail(
                evaluator,
                question,
                accept=lambda _ctx, evaluation: evaluation.value.probability < 0.1,
            )
        ],
    )
    result = await agent.run('Summarize this meeting agenda.')
```

The guardrail borrows `evaluator`, so the application closes it. See [the complete input-guardrail example](https://github.com/dsfaccini/jevantic/blob/main/examples/input_guardrail.py) for an agent builder and an explicit policy function.

## Guard an agent's output

`OutputGuardrail` evaluates complete plain-text output before `Agent.run()` returns. Its `accept` policy receives the same typed evaluation shape as `InputGuardrail`.

```python
from pydantic_ai import Agent

from jevantic import Jevaluator, Question
from jevantic.pydantic_ai import OutputGuardrail

question = Question.noul('Could this response disclose private data?')

async with Jevaluator() as evaluator:
    agent = Agent(
        existing_model,
        capabilities=[
            OutputGuardrail(
                evaluator,
                question,
                accept=lambda _ctx, evaluation: evaluation.value.probability < 0.1,
            )
        ],
    )
    result = await agent.run('Summarize this meeting agenda.')
    # result.output: str  # available only when the output is accepted
```

Streaming can expose partial and final text before rejection; output functions can already have side effects. The check runs after ordinary result transformations. Place the guardrail before other outermost capabilities that change results. See [the complete example](https://github.com/dsfaccini/jevantic/blob/main/examples/output_guardrail.py) and [streaming contract](https://github.com/dsfaccini/jevantic/blob/main/docs/reference.md#pydantic-ai-output-guardrail).

## Reference and further reading

The [API reference](https://github.com/dsfaccini/jevantic/blob/main/docs/reference.md) covers input snapshots, response validation, errors, client ownership, request metadata, and fan-out failure behavior.

- [Vocabulary](https://github.com/dsfaccini/jevantic/blob/main/CONTEXT.md) and [short illustrated lesson](https://github.com/dsfaccini/jevantic/blob/main/docs/learning/lessons/0001-primitive-convenience-workflow.html)
- [Current requirements and decisions](https://github.com/dsfaccini/jevantic/blob/main/docs/design/discovery.md) and [core design](https://github.com/dsfaccini/jevantic/blob/main/docs/design/core-experiment.md)
- [Pydantic AI capability design](https://github.com/dsfaccini/jevantic/blob/main/docs/design/pydantic-ai-capabilities.md)
- [Four-second API comparisons](https://github.com/dsfaccini/jevantic/blob/main/assets/marketing/README.md)
- [Verification evidence](https://github.com/dsfaccini/jevantic/blob/main/docs/verification.md) and [research index](https://github.com/dsfaccini/jevantic/blob/main/docs/research/index.md)

## Develop

Use Python 3.13 locally. Install the optional integration before running the complete test suite:

```sh
uv sync --extra pydantic-ai
uv run pytest tests -q
uv run pyright src tests examples checks
uv run python checks/typecheck_negative.py
uv run ruff check src tests examples checks typecheck
uv run ruff format --check src tests examples checks typecheck
uv build
```

The [verification evidence](https://github.com/dsfaccini/jevantic/blob/main/docs/verification.md) records environments, results, and limits for checked revisions.
