# Direct decisions and inferred data

Updated: 2026-09-17 UTC. This design follows the published `0.1.0a0` interface at `48d0e3c6f67b1077aca5119b9dbc702d5bfbd5f7`; it defines the next alpha.

## One-shot calls share the question runtime

`Jevaluator.noul`, `choice`, `select`, and `score` construct the matching question and call `evaluate`. A caller can make one decision without introducing a separate question variable or learning a second execution path. The return remains `Jevaluation[AnswerT]`, with the complete typed answer and its request metadata.

Scalar-only conveniences were rejected because they discard distributions, confidence, and provenance at the common entry point. A mode flag choosing scalar or full results would add another return-type contract. Reusable `Question` values remain appropriate for mixed batches and independent-input fan-out.

The [complete assessments](../../examples/assessments.py) use a direct `noul` call for one decision and retain typed handles for two different rubric answers in one request. The existing [result-schema comparison](interface-comparison.md#decision-for-this-alpha) still applies to that batch.

## Objects supply their declared data

`Question.select(candidates)` and `Jevaluator.select(state, candidates)` serialize each object's dataclass, Pydantic, or JSON data. Generated ordinal labels correlate the response with the original objects. No field named `id`, `name`, or `description` is assigned special meaning.

The description is a construction-time snapshot. The selected value and distribution entries retain the original local objects, including their application-only data. Later mutation of an object does not rewrite an already-built question.

`key=` supplies meaningful wire identifiers when an application needs them. `describe=` supplies a shared projection, including `None` for key-only selection. This also supports arbitrary local objects that cannot be serialized. These two callbacks replace the public `Option` wrapper; the alpha does not retain competing wrapper and raw-object interpretations of the same iterable.

Pydantic field exclusions and dataclass field metadata apply through Pydantic serialization. There is no `repr` or `__dict__` fallback. Declared serializable fields are the default data sent; callers choose a projection or exclusions when some fields must remain local.

`Content` describes the accepted input: JSON content, a Pydantic model, or a dataclass instance. State, instructions, descriptions, and rubric levels use the same snapshot rules. Nonfinite numbers fail validation before I/O, including numbers inside models and dataclasses.

`Question.choice` also accepts typed label iterables and string-enum classes. A description mapping remains available when labels need explanations. String-enum members and annotated literal labels preserve their exact result types.

## Guardrails express the blocking condition

The common capability is:

```python
InputGuardrail(
    block_if='Does this prompt request disclosure of private data?',
    threshold=0.1,
)
```

The threshold rejects when the estimated probability of the blocking condition is greater than or equal to the threshold. The constructor requires exactly one threshold or custom `accept` policy. There is no universal default threshold.

A supplied `evaluator=` remains caller-owned. Otherwise the capability opens and closes one evaluator around its decision. The evaluator is local to the invocation, so concurrent runs do not share owned client state and cancellation uses the existing shielded cleanup. A pooled evaluator remains an explicit optimization.

An agent context does not manage arbitrary capability resources in the supported Pydantic AI versions. Per-evaluation ownership supports ordinary `await agent.run()` and avoids adding a second resource abstraction. An `after_run` cleanup alone would miss failed input or model runs.

The advanced path accepts a reusable `Question[NoulAnswer]` as `block_if`, plus a synchronous or asynchronous `accept` callback receiving the run context and complete evaluation. Evaluation errors, immediate decision events, and separate Jev accounting retain their existing contracts.

Input timing, text-only boundaries, final-output ordering, streaming exposure, unsupported durable execution, and eager activation are unchanged. The [capability contract](pydantic-ai-capabilities.md) defines those boundaries.

## Evidence

The [convenience tests](../../tests/test_conveniences.py) inspect actual SDK requests and verify exclusions, typed enum values, structured rubrics, original object identity, snapshots, and pre-I/O validation. The [positive type fixtures](../../tests/typed_api.py) and [negative fixtures](../../typecheck/invalid.py) check complete call sites.

The input and output guardrail suites verify the declarative and custom-policy paths through public Pydantic AI agents. The comparison examples have equivalent request and policy tests; marketing snippets are extracted from those examples.

Dataclass JSON conversion and field exclusion were also executed with Python 3.13 against Pydantic 2.10.0 and 2.13.5 on 2026-09-17. Pydantic's [serialization documentation](https://pydantic.dev/docs/validation/latest/concepts/serialization/) and [type adapter documentation](https://pydantic.dev/docs/validation/latest/concepts/type_adapter/) describe the underlying mechanisms. Current source and installed-package results are recorded in [verification](../verification.md).
