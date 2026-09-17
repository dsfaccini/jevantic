# Typed core design

Updated: 2026-09-17 UTC. First developing alpha, following an independently reviewed interface experiment.

The [standalone package](../../README.md) uses typed questions as the shared foundation for single evaluations, mixed batches, and ordinary Python assessment functions. The [verification record](../verification.md) gives reproducible evidence and limits.

## The caller's interface

```python
batch = evaluator.batch(state)
risk = batch.add('risk', Question.noul('Could this expose private data?'))
quality = batch.add('quality', Question.score(['Incomplete', 'Usable', 'Complete']))
result = await batch.run()

risk_answer = result.answer(risk)        # NoulAnswer
quality_answer = result.answer(quality)  # ScoreAnswer
```

`Evaluator.evaluate(state, question)` handles one question. `Question.choice()` preserves typed string labels, and `Question.select()` recovers original local objects from returned labels. Their probabilities and confidence remain available. [Complete assessment functions](../../examples/assessments.py) demonstrate a command-risk question and two rubric scores in one request.

The scoring example returns an ordinary dataclass with named fields. This is a concrete baseline for deciding whether a Pydantic schema declaration saves enough caller code to justify a compiler and its preflight checks.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| `Question[T]` | Capture a question definition and validate/decode an SDK answer into `T` |
| `Handle[T]` | Correlate a registered question with its typed answer in the originating batch |
| `Batch` | Snapshot shared state, freeze registration at execution, perform an explicit repeatable evaluation |
| `Evaluator` | Execute through one configured SDK client, validate answer names and kinds, retain response metadata |
| TypeSafe SDK | HTTP, authentication, timeout configuration, transport injection, retries, structural response decoding |
| Application | Build questions with ordinary functions and decide what action follows an answer |

The evaluator closes a client it creates and leaves a supplied client open. Raw SDK requests and answer decoding remain available through `to_request()` and `decode()`.

## Review findings addressed

- Contradictory Choice and Score fields could pass scalar validation. The core now checks the highest-probability option and weighted rubric score with explicit rounding tolerances.
- A tuple rubric description serialized as an array but failed comparison with the returned array. Content snapshots now use canonical JSON forms.
- A bare string rubric became one level per character. Construction now rejects it.
- Live validation established the ten-level Score maximum. Construction rejects larger rubrics before I/O; one level remains accepted because the service accepted it.
- Cancelling shutdown could interrupt SDK closure after the SDK marked itself closed. A shielded AnyIO child now finishes closure before cancellation exits the evaluator, with asyncio and Trio regressions.
- Recording only the evaluator's model override lost a model configured on an injected client. Response metadata now reads the actual request's model identifier.

Each change has an offline regression. Numerical tolerances passed the recorded live examples, which is narrower evidence than a provider guarantee for every response.

## Deliberate alpha boundaries

Jev is the first backend. The package provides an async API and the three Jev primitives. Typed question composition is the initial foundation; a result-schema compiler, synchronous convenience methods, and telemetry hooks require concrete caller benefit before becoming public surface. Bounded fan-out is the next small convenience supported by cookbook evidence.

No harness capability has changed. The [existing integration map](../research/harness-interfaces.md) is the reference for a plan grounded in the standalone interface.
