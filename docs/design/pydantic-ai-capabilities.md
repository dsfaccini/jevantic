# Pydantic AI capabilities

Jevantic owns its Pydantic AI integrations in `jevantic.pydantic_ai`. The `pydantic-ai` extra depends on `pydantic-ai-slim>=2.38.0,<3`; importing the core package does not import Pydantic AI. Install the optional integration with `uv add 'jevantic[pydantic-ai]'`, or use a local checkout path before publication.

The [Harness capabilities](../research/harness-interfaces.md) provide design precedent. These integrations use Pydantic AI's public capability API directly and do not depend on Harness.

## Shared contract

- Borrow the supplied `Jevaluator`; the application owns its lifetime and SDK configuration.
- Keep the evaluation question and acceptance policy explicit. A probability does not define a universal threshold.
- Await evaluations inline. Preserve SDK failures, response-validation errors, and cancellation.
- Keep each `Jevaluation` and its provenance together. Report Jev usage separately from the agent model's `RunUsage` and `UsageLimits`.
- Emit typed events containing decision and accounting fields, without prompt text, documents, tool arguments, or raw HTTP responses.
- Keep capability instances free of mutable run results. Pydantic AI may share an instance across concurrent runs.
- Disable spec construction for callbacks and live clients. Reject active durable execution before making an uncheckpointed evaluation.

## Input guardrail pilot

`InputGuardrail` accepts a `Jevaluator`, a `Question[NoulAnswer]`, and an `accept` callback. The callback receives the typed `RunContext` and complete `Jevaluation[NoulAnswer]`; it may return a `bool` synchronously or asynchronously.

The first model request evaluates `{'prompt': ctx.prompt}`. Acceptance permits the model request; rejection raises `GuardrailRejected` with the evaluation attached. Later requests in the same run do not repeat the assessment. Another run assesses its own prompt.

The initial contract requires a plain-text prompt. A new prompt with message history is supported. A promptless continuation or a sequence of multimodal content is rejected: retrieving an older textual prompt from history would assess a different input. This is a deliberate boundary, not an implicit multimodal conversion.

Blocking uses an exception rather than `SkipModelRequest`: the latter creates a successful agent response and would make policy denial indistinguishable from ordinary output.

## Evidence informing the pilot

On 2026-09-17, Python 3.13 probes against released `pydantic-ai-slim==2.38.0` verified the public `AbstractCapability.wrap_model_request`, `RunContext.emit`, and `CapabilityEvent` APIs. A `FunctionModel` tool loop observed `ctx.run_step` values `1` and `2`, with the original prompt unchanged. A history run observed its new prompt; a promptless continuation observed `None` and only older text in its messages. A custom rejection exception prevented the model call; `SkipModelRequest` returned a successful output.

Sources: Pydantic AI [capability hooks at `v2.38.0`](https://github.com/pydantic/pydantic-ai/blob/v2.38.0/pydantic_ai_slim/pydantic_ai/capabilities/abstract.py), [run context](https://github.com/pydantic/pydantic-ai/blob/v2.38.0/pydantic_ai_slim/pydantic_ai/_run_context.py), and [Harness durability detection precedent](https://github.com/pydantic/pydantic-ai-harness/blob/5f505ac77f9bb55d517ff9fd2ff6ad966f782d1b/pydantic_ai_harness/trajectory_judge/_capability.py).

The deterministic integration tests use a real TypeSafe SDK client with a local HTTP transport and Pydantic AI's `FunctionModel`. Their results and package checks belong in the [verification record](../verification.md).

## Complete output

`OutputGuardrail` checks `{'output': result.output}` in an outermost `after_run` hook. This boundary includes ordinary output-processing and final-result transformations. A `wrap_run` check would run before `after_run`, and an output-processing check would run earlier still. Another outermost capability that transforms the result must follow the guardrail in the attachment list so the guardrail's check runs last.

The contract protects successful `Agent.run()` completion. It does not buffer streaming output: `run_stream()` can expose partial and final text before context exit raises. A rejected `run_stream_events()` omits its final `AgentRunResultEvent` but has already emitted raw text events. Typed event listeners receive the completed guardrail decision; the raw event stream has already ended at that boundary.

## Extending the integration

Further capabilities reuse the ownership, events, cancellation, and policy boundaries. Document retrieval must keep the application's retrieval callback distinct from Jev's ranking work; protecting a tool requires evaluating validated arguments before its function runs. Each new boundary needs a complete application probe before implementation.

Durable support needs a separate design with registered durable operations, worker-side evaluator construction, and replay tests. Ordinary hook execution does not establish replay safety.
