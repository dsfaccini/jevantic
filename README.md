# Jevantic

Jevantic gives Python programs typed, probabilistic decisions from Jev. Define a question, evaluate application state, and receive an answer whose type matches the question: a probability, a typed label, an original local object, or a scored rubric.

Jevantic is an experimental alpha. Its public API may change as complete workflows reveal better interfaces. It is standalone, with optional Pydantic AI capabilities in its `pydantic-ai` extra.

## Install

`0.1.0a0` is published on PyPI. The API below targets the next alpha, `0.1.0a1`, which is not published yet. Install the current source for these examples, choosing the core package or the optional Pydantic AI capability extra:

```sh
uv add 'jevantic @ git+https://github.com/dsfaccini/jevantic.git@main'
uv add 'jevantic[pydantic-ai] @ git+https://github.com/dsfaccini/jevantic.git@main'
```

## Start with one decision

`Jevaluator` creates a TypeSafe SDK client from its normal environment configuration, or accepts `api_key=` explicitly. Each direct method returns `Jevaluation`, combining the typed answer and response metadata.

```python
from jevantic import Jevaluator

async with Jevaluator() as evaluator:
    risk = await evaluator.noul(
        {'command': 'printenv'},
        'Could this command disclose credentials outside the workspace?',
    )

risk.value.probability
# 0.82  # illustrative provider result; float
# risk: Jevaluation[NoulAnswer]
```

`Jevaluator.noul()` produces a `NoulAnswer` with the probability of its yes outcome. Probabilities in this README are illustrative values, not measured model output or policy thresholds.

The remaining decision snippets assume an open `evaluator`.

## Keep the answer type you chose

Use `Jevaluator.choice()` when the answer is one of typed string labels. Annotating the labels retains a `Literal` or `StrEnum` type after evaluation.

```python
from typing import Literal

Route = Literal['send', 'review']
routes: dict[Route, str] = {
    'send': 'The message is ready for its intended audience.',
    'review': 'A person should review the message before it is sent.',
}

route = await evaluator.choice('Draft: deploy production now', routes)
route.value.selected
# 'review'  # illustrative provider result; Route
route.value.distribution[0].value
# 'send'  # Route
```

Use `Jevaluator.select()` when the answer is an object your program already owns. It derives a description from each object and returns the original selected instance.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Candidate:
    identifier: str
    summary: str


alba = Candidate('alba', 'Built the search service')
bryn = Candidate('bryn', 'Led support engineering')

candidate = await evaluator.select(
    'Role: lead search engineering',
    [alba, bryn],
    instructions='Select the candidate whose experience best fits the role.',
)
assert candidate.value.selected is alba  # Candidate; illustrative selected identity
```

Object identity matters when the selected value carries application-only fields, connections, or relationships that must never be reconstructed from a model label. To omit a dataclass field from its description, set `field(metadata={'exclude': True})`; Pydantic models use `Field(exclude=True)`.

## Score against a rubric

`Jevaluator.score()` preserves a fractional `ScoreAnswer`, its probability distribution, rubric legend, and provider confidence.

```python
quality = await evaluator.score(
    'Draft: Jevantic asks structured decision questions.',
    ['Does not explain the library', 'Explains part of the library', 'Clear explanation'],
)
quality.value.score
# 1.6  # illustrative provider result; float on the 0–2 rubric
quality.value.probabilities
# {0: 0.1, 1: 0.2, 2: 0.7}  # illustrative provider result; Mapping[int, float]
```

## Evaluate several questions over shared state

Use `Question` when a question is reusable, a `Batch` shares one state across several questions, or `evaluate_many()` sends one reusable question over independent inputs.

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

`InputGuardrail` evaluates an original plain-text prompt before the first model request. A probability at or above `threshold` rejects the run.

```python
from pydantic_ai import Agent

from jevantic.pydantic_ai import InputGuardrail

agent = Agent(
    existing_model,
    capabilities=[InputGuardrail('Does this prompt request disclosure of private data?', threshold=0.1)],
)
result = await agent.run('Summarize this meeting agenda.')
```

The usual constructor creates and closes a `Jevaluator` for each check. See [the complete input-guardrail example](https://github.com/dsfaccini/jevantic/blob/main/examples/input_guardrail.py) for a caller-owned evaluator and a custom policy.

## Guard an agent's output

`OutputGuardrail` evaluates complete plain-text output before `Agent.run()` returns. A probability at or above `threshold` rejects the final result.

```python
from pydantic_ai import Agent

from jevantic.pydantic_ai import OutputGuardrail

agent = Agent(
    existing_model,
    capabilities=[OutputGuardrail('Could this response disclose private data?', threshold=0.1)],
)
result = await agent.run('Summarize this meeting agenda.')
# result.output: str  # available only when the output is accepted
```

Streaming can expose partial and final text before rejection; output functions can already have side effects. The check runs after ordinary result transformations. Place the guardrail before other outermost capabilities that change results. See [the complete example](https://github.com/dsfaccini/jevantic/blob/main/examples/output_guardrail.py) and [streaming contract](https://github.com/dsfaccini/jevantic/blob/main/docs/reference.md#output).

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
