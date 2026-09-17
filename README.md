# Jevantic

A Python library for typed, probabilistic decisions with Jev. Compose questions, evaluate shared state, and retain the types of answers and selected application objects.

This is the first developing alpha. The public API can change as complete workflows expose better interfaces. Jevantic is standalone; Pydantic AI Harness is an intended downstream consumer.

## Install from the checkout

```sh
uv add /path/to/jevantic
```

The package has not been published to PyPI. Local development uses Python 3.13; Python 3.12 and 3.14 checks are configured in CI.

## Use

```python
from jevantic import Evaluator, Question

async def assess(text: str) -> float:
    async with Evaluator() as evaluator:
        result = await evaluator.evaluate(text, Question.noul('Does the text contain personal information?'))
    return result.value.probability
```

`Evaluator()` creates an asynchronous TypeSafe SDK client using the SDK's environment configuration. Supply `api_key` explicitly or pass a configured `typesafe_sdk.AsyncTypeSafeClient` through `client`. An injected client remains the caller's responsibility to close. Configure timeouts, retries, base URLs, and transports on that SDK client.

See [complete assessment functions](examples/assessments.py) for a command risk estimate and two rubric scores sharing one request. The application decides what action follows an answer. The examples are exercised against local HTTP responses in [their tests](tests/test_examples.py).

## Composition

`Question.noul()` returns a probability. `Question.choice()` preserves typed string labels, including literals and string enums. `Question.select()` associates labels with arbitrary local objects and returns the original selected object; only labels and descriptions are sent to Jev. `Question.score()` retains a fractional rubric score, its distribution, the rubric legend, and provider confidence.

For several questions over the same state, use `batch = evaluator.batch(state)`, retain the typed handles returned by `batch.add(name, question)`, then obtain each value with `(await batch.run()).answer(handle)`. Every run validates all answers. The first run freezes registration; later runs explicitly evaluate the same batch again, producing independent results. SDK retry policy can add HTTP attempts within a run.

Plain Python functions can build questions from application dependencies. `Question.to_request()` and `Question.decode()` also support callers that manage SDK execution themselves.

## Data and failures

State and question content accept text, JSON objects, and JSON arrays. State also accepts a Pydantic model and follows its JSON serialization configuration. State is captured when a batch is created; question content is captured at construction. Local choice objects retain their identity and remain owned by the application.

Answers must match the requested names, kinds, options, and rubric. Probabilities and confidence must be finite and within zero and one. A selected Choice must have maximal probability, allowing ties within `1e-6`; a Score must match the probability-weighted rubric within `1e-6` per level. Distributions use an absolute sum tolerance of `1e-6`. These experimental tolerances preserve the reported values without normalization. Provider confidence and the selected option's probability are distinct values.

`QuestionError` reports invalid definitions. `ResponseValidationError` identifies a semantic response failure and retains the question name and request ID. SDK transport, HTTP, and structural decoding errors retain their original SDK types. Cancellation propagates through the SDK. Context exit closes an owned client and leaves a supplied client open.

Results retain provider-reported usage, the model identifier actually sent and the model returned, request ID, and the raw HTTP response. Missing usage counts remain `None`. Access to raw responses is explicit; Jevantic adds no telemetry. SDK logging configuration still applies, including its option to log bodies at debug level.

Owned-client shutdown finishes before cancellation leaves `aclose()`. Cleanup uses AnyIO to support asyncio and Trio, including direct asyncio task cancellation. Close failures retain their original exception. The caller remains responsible for the lifecycle of an injected SDK client.

## Checks

Run from this directory after `uv sync`:

Local development is pinned to Python 3.13. The CI matrix covers Python 3.12, 3.13, and 3.14; additional interpreter runs belong in CI.

```sh
uv run coverage run -m pytest tests/test_evaluation.py tests/test_questions.py tests/test_lifecycle.py tests/test_examples.py -q
uv run coverage report --show-missing
uv run pyright src/jevantic tests/conftest.py tests/test_evaluation.py tests/test_questions.py tests/test_lifecycle.py tests/test_examples.py tests/typed_api.py examples/assessments.py checks
uv run python checks/typecheck_negative.py
uv run ruff check src tests examples checks typecheck
uv run ruff format --check src tests examples checks typecheck
uv build
```

`typecheck/invalid.py` deliberately fails strict Pyright checking at its marked expressions. Its dedicated check requires those errors; the positive check excludes it.

Tests use the real SDK with deterministic local HTTP transports, fake credentials, and a `.invalid` endpoint. Separate opt-in checks have exercised the live API and the documented workflows. See [verification evidence](docs/verification.md) for commands, versions, results, and limits.

The observed API accepts a one-level Score and rejects more than ten levels. Jevantic follows those observed bounds, while provider guidance recommends at least two. Live examples have satisfied the numerical tolerances; a small set of responses cannot establish every future rounding behavior. Judgment quality, calibration, performance, and remote cancellation remain separate verification work.

## Design and learning

- [Vocabulary](CONTEXT.md) and [short illustrated lesson](docs/learning/lessons/0001-primitive-convenience-workflow.html)
- [Requirements and current decisions](docs/design/discovery.md)
- [Core design](docs/design/core-experiment.md) and [interface comparison](docs/design/interface-comparison.md)
- [Requirements and verification](docs/design/verification-plan.md)
- [Research index](docs/research/index.md), including cookbook patterns and harness interfaces
- [Initial design experiments](experiments/README.md)
