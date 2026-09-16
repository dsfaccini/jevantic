# Pydantic AI reference patterns

Observed: 2026-09-16. Source and test inspection only; the cited tests were not run.

Snapshot: [pydantic-ai 4e013c51](https://github.com/pydantic/pydantic-ai/commit/4e013c51a50659aba2adf7853bfb22bb77f6a518). Paths below are relative to the repository root. These are concrete reference mechanisms, not an accepted Jevantic architecture.

| User benefit | Mechanism and source | Verification surface |
| --- | --- | --- |
| Inputs and results retain useful static types | Agent[AgentDepsT, OutputDataT], AgentRunResult[OutputDataT]; pydantic_ai_slim/pydantic_ai/agent/__init__.py and run.py | tests/typed_agent.py |
| Dependencies are explicit and replaceable | RunContext[DepsT], deps propagation, scoped overrides; _run_context.py | tests/test_deps.py |
| Backend behavior and authenticated transport can vary separately | Model.request and Provider lifecycle; models/__init__.py and providers/__init__.py | test_provider_lifecycle_closes_client in tests/test_agent.py |
| Sync and async behavior remain aligned | AbstractAgent.run_sync delegates to run after checking nested-loop restrictions | tests/test_nested_sync_agent.py |
| Public behavior can be tested without paid inference | FunctionModel and TestModel satisfy the same Model contract | Structured-output integration cases in tests/test_agent.py |
| Validation has an accountable owner | OutputValidator and explicit exception classes; _output.py and exceptions.py | Invalid and corrected result cases in tests/test_agent.py |
| Budgets constrain further work | UsageLimits and checks before requests; usage.py | tests/test_run_context_usage_limits.py |
| Cancellation cleans up work and resources | CancellationToken and response closure; _cancel.py and models/__init__.py | tests/test_run_cancellation.py, tests/test_streaming.py |
| Telemetry capture is configurable | InstrumentationSettings and InstrumentedModel; models/instrumented.py | Content/request-parameter flag assertions in tests/test_images.py |
| Optional integrations need not enlarge the core installation | Package extras and deferred model imports | pydantic_ai_slim/pyproject.toml; optional example handling |
| Documentation and typing are checked artifacts | Strict Pyright, typed fixtures, executable examples, combined branch coverage, strict-no-cover | pyproject.toml, .github/workflows/ci.yml, tests/test_examples.py |

Implementation paths without a full prefix are under pydantic_ai_slim/pydantic_ai/.

## Transfer limits

- The generative agent loop, tool transcript, and streaming response lifecycle solve agent-specific problems.
- ModelRetry means corrective feedback to a generative model; it is distinct from transport retries or local result validation.
- TestModel's tool-calling heuristic is not a decision-model testing contract.
- Provider abstraction has value when behavior really varies; its presence in Pydantic AI does not settle Jevantic's backend scope.
- Input-token and request accounting remain relevant to Jev. Units and budget ownership need to match actual work.
- Instrumentation is off by default, but enabled InstrumentationSettings defaults to include_content=True. Any Jevantic default needs a deliberate choice.
- The process-wide ALLOW_MODEL_REQUESTS override is an existing test control, not evidence that process-wide mutable settings are suitable everywhere.

These qualifications distinguish transferable engineering discipline from reproducing Pydantic AI's full feature surface.

## Design questions opened by the evidence

- Can a caller's question definitions determine exact answer types without repeated narrowing?
- What can callers replace in tests without bypassing result validation?
- Which layer owns cancellation, HTTP closure, retries, accounting, and telemetry?
- Which guarantees should be expressed as typed fixtures, public behavior tests, and executable examples?

No new public classes or release gates have been selected yet.
