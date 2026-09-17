# Jevantic API reference

This page records the current alpha contracts behind the examples in the [README](../README.md). These details can change as the public interface evolves.

## Questions and content

`Question.noul()` asks for the probability of a yes outcome and returns a `NoulAnswer`.

`Question.choice()` accepts a mapping of string labels to descriptions and returns a `ChoiceAnswer` whose `selected` value and distribution entries retain the mapping's literal-string or `StrEnum` type.

`Question.select()` accepts `Option(key, value, description)` values. Jev receives only their keys and descriptions; `ChoiceAnswer.selected` is the exact local `value` object associated with the returned key. Option keys must be unique, and a `Choice` question needs between one and 255 options.

`Question.score()` accepts a nonempty sequence of ordered rubric descriptions and returns a `ScoreAnswer`. Its levels are numbered from zero. Jevantic accepts at most ten levels; live provider observations accept one level and reject eleven, while provider guidance recommends at least two.

State and question content accept text, JSON objects, and JSON arrays. State also accepts a Pydantic model and follows its JSON serialization configuration. Jevantic snapshots state when `Jevaluator.batch()` is called and question content when a `Question` is constructed.

`Question.to_request()` builds an independent TypeSafe SDK question, and `Question.decode()` validates and decodes an SDK answer for callers that manage SDK execution themselves.

## Batches and single evaluations

`Jevaluator.evaluate(state, question)` evaluates one question and returns `Jevaluation`, containing the typed `value` and `ResponseInfo` metadata.

`Jevaluator.batch(state)` creates a `Batch` for several questions over one shared state. Keep the typed handles returned by `batch.add(name, question)` and retrieve answers through `result.answer(handle)`. A batch needs at least one uniquely named question. Its first `run()` freezes registration; later `run()` calls deliberately repeat the same batch and produce independent results. SDK retry policy can make additional HTTP attempts within a run.

Each `Batch.run()` validates every returned answer before it returns a `BatchResult`. The provider must return exactly the requested names and answer kinds. A `ResponseValidationError` includes the relevant question name, when one exists, and the provider request ID.

## Independent-input fan-out

`Jevaluator.evaluate_many(states, question, concurrency=...)` evaluates the same question over independent states with a bounded worker pool. `concurrency` must be a positive integer. Inputs are consumed lazily, and returned `Jevaluation` values retain input order and per-request metadata.

If an input iterator or evaluation fails, unfinished work is cancelled and an `ExceptionGroup` retains the original errors. Failures from individual inputs receive a zero-based input-index note without the input content. The call returns no partial list. A request may already have completed or reached the provider, and successful work is not repeated automatically; SDK retries still apply separately to each request.

Shared-state batches and independent-input fan-out are different operations: a batch sends several questions with one state, while fan-out sends one question for each state.

## Response validation

Probabilities and provider confidence must be finite and between zero and one. Probability distributions must have exactly the requested keys and sum to one within an absolute tolerance of `1e-6`.

A `Choice` answer's selected option must have maximal probability, allowing ties within `1e-6`. `Score` values must be finite, within the requested rubric bounds, and match the probability-weighted rubric within `1e-6` per level. A `Score` legend must exactly match the requested rubric. These experimental tolerances preserve reported values; Jevantic does not normalize them. Provider confidence and an option's selected probability are separate values.

`QuestionError` reports invalid question or batch definitions before a provider request. `ResponseValidationError` reports a semantically invalid response. Single evaluations preserve the TypeSafe SDK's transport, HTTP, and structural decoding errors; `evaluate_many()` preserves them inside its exception group. Cancellation propagates through the SDK.

## Client lifecycle, metadata, and observability

Without `client=`, `Jevaluator` creates an asynchronous TypeSafe SDK client using `api_key=` or the SDK's environment configuration. `async with Jevaluator(...)` closes that owned client. A supplied `typesafe_sdk.AsyncTypeSafeClient` remains owned by the caller and stays open after the evaluator closes; configure its timeouts, retries, base URL, and transport there.

Owned-client shutdown completes before cancellation leaves `aclose()`. Cleanup uses AnyIO and supports asyncio and Trio, including direct asyncio task cancellation. Close failures retain their original exception.

Each `Jevaluation` or `BatchResult` retains `ResponseInfo`: provider-reported usage, the model sent after SDK configuration, the model returned by the provider, request ID, and raw HTTP response. Missing usage counts remain `None`. Access to raw responses is explicit. Jevantic adds no telemetry, although TypeSafe SDK logging configuration still applies, including its option to log bodies at debug level.

## Pydantic AI input guardrail

Install this optional capability with the `pydantic-ai` extra. `InputGuardrail[DepsT](evaluator, question, *, accept=...)` accepts an `Jevaluator`, a `Question[NoulAnswer]`, and a synchronous or asynchronous policy. The policy receives `RunContext[DepsT]` and `Jevaluation[NoulAnswer]`, and must return a plain `bool`. The guardrail borrows the supplied evaluator; it never closes it.

For each run, `InputGuardrail` evaluates only the first model request. It sends exactly `{'prompt': original_plain_text}` as Jevantic state, then calls the primary model when the policy returns `True`. A `False` result raises `GuardrailRejected` with `stage == 'input'` and the complete `evaluation`; its `evaluation.info` retains the response metadata. The protected model request does not run. New plain-text prompts with explicit history are supported. `None` and multimodal prompts are rejected before an evaluator request.

`InputGuardrail.get_serialization_name()` returns `None`, so the capability is excluded from serializable agent specifications. An active durable-execution capability is rejected before evaluation because Jevantic evaluations are not checkpointed. Guardrails reject `defer_loading=True`: their checks must be active when the run begins.

Each evaluation emits an immediate, content-free `GuardrailEvaluated` event containing the stage, acceptance decision, probability, model metadata, request ID, and token counts. Register `Hooks.on.event(GuardrailEvaluated)` to receive it on Pydantic AI 2.38 or later. An event-stream handler can miss the event when a rejection ends the run, while the immediate hook has already received it.

## Pydantic AI output guardrail

`OutputGuardrail[DepsT](evaluator, question, *, accept=...)` uses the same typed policy, borrowed `Jevaluator`, event, serialization, and durable-execution rules as `InputGuardrail`. It accepts only a `Question[NoulAnswer]` and a final plain-text agent output.

The guardrail evaluates exactly `{'output': final_text}` in `after_run`, before `Agent.run()` returns. Its outermost ordering checks the result after ordinary output-processing and `after_run` transformations. When another capability also requests outermost ordering and changes results, place the guardrail first in the capabilities list so its check runs last. A rejected evaluation raises `GuardrailRejected` with `stage == 'output'`; its `evaluation.info` retains the response metadata. Structured final output is rejected before an evaluator request.

Streaming exposes text before acceptance. Inside `run_stream()`, raw deltas, partial and final `stream_output()` values, and `get_output()` can be observed before context exit raises `GuardrailRejected`. With `run_stream_events()`, rejection prevents the final `AgentRunResultEvent`, but earlier text events have already been emitted. Output functions also run before the check, so their side effects can already have occurred.

Register `Hooks.on.event(GuardrailEvaluated)` for output decisions and accounting. The final check occurs after the raw event stream has finished; an event-stream handler does not receive this completion event.

## Evidence and limits

The [verification record](verification.md) distinguishes local and hosted checks, deterministic transport tests, and paid live-provider observations. Typed answer shapes and response validation do not establish the correctness, calibration, or policy threshold of a model judgment; applications must evaluate those properties for their own use case.
