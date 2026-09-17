# First harness integration

Proposal grounded in source inspected on 2026-09-17. Jevantic stands independently as an installable alpha; no harness code or dependencies have been changed, and this integration has not been executed.

## Start with an input guardrail callback

The first integration should adapt Jevantic to the existing `InputGuardrail` callback interface. It does not need a new capability base class. The application supplies an existing `Evaluator`, a `Question[NoulAnswer]`, and a policy function taking `Evaluation[NoulAnswer]` and returning `GuardrailResult`.

The callback shape is `async (ctx: RunContext[DepsT], prompt: str) -> GuardrailResult`. It evaluates `{'prompt': prompt}` and passes the complete evaluation to the policy function. The application registers it with `InputGuardrail(guard=callback, parallel=False)` inside the lifetime of the evaluator.

Use sequential guarding first: the primary model request should start only after the input is allowed. The first example should demonstrate `allow` and `block`. Existing harness semantics continue to govern the validity and behavior of other guardrail outcomes.

Source: harness [guardrails capability](https://github.com/pydantic/pydantic-ai-harness/blob/5f505ac77f9bb55d517ff9fd2ff6ad966f782d1b/pydantic_ai_harness/guardrails/_capability.py), especially `InputGuardrail`, its callback alias, and `wrap_model_request`.

## Ownership and boundaries

| Concern | Initial contract |
| --- | --- |
| Client lifetime | The bridge borrows an already-created evaluator and never closes it. The application scopes it with `async with`; an injected SDK client remains caller-owned. |
| Model input | Send the callback's plain prompt as a named field. Do not serialize run context, dependencies, history, or opaque tool data. |
| Decision policy | Application code chooses the question, threshold, action, and block message. The full evaluation exposes probabilities and request metadata to that code. |
| Errors | SDK errors, Jevantic validation errors, and policy exceptions propagate. Failure does not silently allow the prompt. |
| Cancellation | The bridge introduces no background task or cancellation handler. Cancellation propagates through the evaluator; its owner handles closure. |
| Accounting | Jev usage stays separate from `ctx.usage` and Pydantic AI `UsageLimits`. Report Jev's actual metadata to the policy; do not pretend a provider-specific token count is interchangeable with another model's budget. |
| Configuration | Caller-configured SDK timeouts and retries remain effective. Any shared monetary or cross-provider request budget needs an explicit subsequent design. |
| Serialization | A callback-bearing guardrail is not spec-serializable. Do not advertise persisted capability specifications for this bridge. |

Jevantic evidence: local commit `b8ab4479c31f6f6c02a2af6d85e36f77e0082077`, [evaluator implementation](../../src/jevantic/_client.py), [lifecycle tests](../../tests/test_lifecycle.py), and [verification record](../verification.md). Jevantic has no hosted source URL at the time of this proposal.

## Invocation and durable execution

The inspected `InputGuardrail` calls its guard only when `ctx.run_step <= 1`. Core advances that step for later model requests, including requests caused by output retries and tool loops. The proposed bridge therefore makes at most one logical Jev evaluation per ordinary, non-durable `Agent.run` invocation. Another run may evaluate again, and SDK retries can make multiple HTTP attempts within one evaluation.

Initially reject durable execution before sending a Jev request. There is no public `RunContext.is_durable` flag in the inspected core. `ctx.capabilities` is public; harness's `TrajectoryJudge` scans it for durability capabilities exposing `in_durable_context`. Follow that existing detection approach when implementing the bridge, and revisit it if core supplies a dedicated context API. Do not imply an ordinary callback request is journaled or replay-safe.

Sources: [TrajectoryJudge's existing durability and lifecycle handling](https://github.com/pydantic/pydantic-ai-harness/blob/5f505ac77f9bb55d517ff9fd2ff6ad966f782d1b/pydantic_ai_harness/trajectory_judge/_capability.py); Pydantic AI 2.38.0 source inspected in the harness environment, `_run_context.py::RunContext.capabilities`, `_agent_graph.py::ModelRequestNode`, and `durable_exec/_base.py::BaseDurabilityCapability.in_durable_context`. The installed Python 3.14 source was read; no additional Python 3.14 run was performed.

## Proof before a harness change

First make an end-to-end example against the harness checkout using Python 3.13, a core `FunctionModel`, and Jevantic's deterministic SDK transport. The integration must establish:

1. An allowed prompt reaches the primary model; Jev receives exactly the documented state and policy receives response metadata.
2. A blocked prompt never starts the primary model request.
3. SDK and semantic validation failures propagate before the primary model runs.
4. Cancelling the agent cancels the assessment; the bridge leaves a borrowed evaluator and client open.
5. Durable execution is rejected before any Jev request.
6. Later model requests within the same run do not repeat the guard; a new run does. Jev accounting remains explicitly separate.

After that proof and a distributable Jevantic prerelease, add an optional harness dependency and a small callback factory, with tests under `tests/guardrails/test_jevantic.py`. Avoid committing a local path dependency to harness. The public factory name and package location remain proposals for that implementation task.

## Subsequent capabilities

A Jev-backed StackOne `Tier3Provider` is a plausible next adapter for `PromptInjectionDefender`. It can classify tool-result text while StackOne retains its configured threshold and verdict handling. Before implementation, verify the dependency version and define call volume, input sizing, evaluator ownership, and treatment of unknown usage counts. Keep raw response capture opt-in.

`TrajectoryJudge` requires a different design. It produces actionable `Steer.message` text and owns background scheduling, one-in-flight control, usage reservations, steering queues, error handling, and cancellation. Jev could provide a structured signal inside a composed judge; it does not supply the generated guidance or replace that lifecycle.

The [source-level interface map](../research/harness-interfaces.md) records those existing contracts. These later integrations are planning candidates, not implemented or verified capabilities.
