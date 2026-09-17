# Developing Pydantic AI capabilities

Read the [shared contract](../design/pydantic-ai-capabilities.md) before extending `jevantic.pydantic_ai`. The input guardrail is the first executed reference implementation.

## Lessons from the pilot

Verified on Python 3.13 with Pydantic AI 2.38.0 and 2.44.0 on 2026-09-17:

- Verify the complete application call site at the minimum supported version. `CapabilityEvent` and immediate dispatch exist in 2.38.0; `Agent.on_event` does not. Register portable listeners with `Hooks()` and `@hooks.on.event(EventType)`.
- Use immediate dispatch when a listener must observe rejection before an exception leaves the hook. A rejected run may discard its queued raw stream events. Keep the complete evaluation on `GuardrailRejected` as well.
- Supply `FunctionModel.stream_function` in event-observation tests. Registering an event listener or handler can select the streaming model path.
- Exercise valid framework paths. `Agent.run(None)` without instructions or history fails in core preflight. A promptless-run test needs instructions or continuation history to reach a capability.
- Keep the guard at the operation it protects. Validate the original prompt once, immediately before the first Jev evaluation. Do not infer a new prompt from earlier message history.
- Test policy direction in the complete example. A question about risk pairs with acceptance below the application's threshold; a question about acceptability reverses that inequality.
- Prefer a blocking question and explicit threshold for the usual guardrail call site. Keep the complete typed evaluation available to custom policies; require a threshold or policy rather than selecting an application threshold for the caller.
- Keep an owned evaluator local to the decision and close it there. An agent context does not manage arbitrary capability resources. A supplied evaluator is borrowed. Verify both forms through concurrent runs and cancellation.
- Traverse public `WrapperCapability.wrapped` and `CombinedCapability.capabilities` when inspecting durable capabilities. The run registry can contain a wrapper proxy that hides its durable child. Test active and inactive contexts through nested wrappers.
- Reject `defer_loading=True` for guardrails. Deferred lifecycle hooks do not run until the model loads the capability, so an agent can otherwise complete without its guardrail evaluating anything.
- Check final output in an outermost `after_run` hook. Both output-processing hooks and `wrap_run` finish before other `after_run` transformations. Among outermost capabilities, list the guardrail first so its check runs last.
- Test streaming independently from `Agent.run()`. A completion check runs after `run_stream()` consumers can observe partial and final output. In `run_stream_events()`, rejection prevents the final `AgentRunResultEvent`, but raw text events have already escaped.
- Receive completion events with `Hooks.on.event`. An `after_run` check emits after the raw event stream has finished, so its typed listeners still receive the decision while an event-stream handler does not.

The [input guardrail tests](../../tests/test_input_guardrail.py) verify these behaviors through `Agent` and a real SDK client with deterministic HTTP responses. They also cover cancellation, concurrent runs, separate usage, and unsupported durable contexts.

## Adding a capability

Own one module, its example, and its tests. Coordinate edits to shared exports, helpers, dependencies, and CI with the integrating author.

Choose a public hook based on an executed `FunctionModel` probe. Similar names need not imply similar coverage: in 2.38.0, text output bypasses the structured-output validation hooks. The [capability design](../design/pydantic-ai-capabilities.md) records the integration boundaries.

Prove the protected operation runs only when the policy accepts. Exercise failures through the public agent boundary. Preserve typed domain objects and complete evaluation metadata without adding request content to events.

Run the targeted suite on the locked version and the supported version floor. Keep local runs on Python 3.13; CI owns other interpreters.
