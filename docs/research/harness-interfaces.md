# Harness integration interfaces

Observed: 2026-09-16. Source inspection only; no tests or model requests ran.

Snapshot: [pydantic-ai-harness 5f505ac7](https://github.com/pydantic/pydantic-ai-harness/commit/5f505ac77f9bb55d517ff9fd2ff6ad966f782d1b). The checkout is one commit behind locally fetched origin/main at 8e863b5b. That commit changes GitHub Actions workflow tooling and documentation, not these capability interfaces.

Core signatures were inspected in installed pydantic-ai 2.38.0 at /Users/david/pydantic/harness/base/.venv/lib/python3.14/site-packages/pydantic_ai/.

## Existing extension points

Paths below are relative to pydantic_ai_harness/ at the snapshot above.

| Surface | User-supplied judgment | Existing behavior and obligations | Source and tests |
| --- | --- | --- | --- |
| Guardrails | Sync or async callbacks, optionally receiving RunContext; return bool or GuardrailResult | Input, final output, tool arguments, and tool results have distinct hooks. Parallel input checks race the model and cancel it on rejection. Retry uses core's budget. Callback-bearing instances are not spec-serializable. | guardrails/_capability.py, _tool_guardrail.py, _shared.py; tests/test_input_guardrail.py, test_output_guardrail.py, test_tool_guardrail.py |
| PromptInjectionDefender | A configured StackOne PromptDefense can use a Tier3Provider classifier | on_detection is observational. Tool results are inspected per model-visible part; a block replaces the result. | prompt_injection_defender/_capability.py; tests/prompt_injection_defender/test_defender.py |
| TrajectoryJudge | A judge Agent can be supplied; there is no verdict-producing callback | Requires AllGood or Steer output. One evaluation runs alongside the main run. Shared usage is reserved, steering is enqueued, errors propagate, unfinished work is cancelled and reaped. Durable contexts are rejected. | trajectory_judge/_capability.py; tests/trajectory_judge/test_trajectory_judge.py |
| Skills | No judgment callback | Static skills become deferred capabilities; the parent model selects what to load. | skills/_capability.py; tests/skills/test_skills.py |
| Subagents | ToolResolver selects allowed child toolsets; child AbstractAgent is explicit | The parent chooses delegation and the child produces output. Supports child limits, timeout, usage sharing, and stream callbacks. | subagents/_capability.py, _toolset.py; tests/subagents/test_subagents.py |
| DynamicWorkflow | WorkflowAgent wrappers expose typed child-agent functions | The model generates sandboxed Python. The implementation owns fan-out limits, cancellation, error translation, and child usage policy. | dynamic_workflow/_capability.py, _toolset.py; tests/dynamic_workflow/test_dynamic_workflow.py |
| CodeMode | selector controls available tools; an OS callback supplies sandbox operations | The model generates Python. Nested calls retain core tool validation, approval, guards, budgets, and tracing. Per-run state and durable-engine tests are significant contracts. | code_mode/_capability.py, _toolset.py; tests/code_mode/test_code_mode.py, test_temporal.py, test_dbos.py |

## Guardrail callback shapes

The public aliases are InputGuardrailFunc, OutputGuardrailFunc, ToolGuardrailFunc, and ToolResultGuardrailFunc. Each accepts either the relevant value alone or RunContext followed by the value. The input value is respectively str, object, ToolCallInfo, or ToolResultInfo. Each callback returns GuardOutcome or an awaitable of it.

GuardOutcome is bool or GuardrailResult. Result constructors include allow, block, replace, retry, and approve. Tool-call and tool-result data include tool name, arguments, and call ID; result data also includes the returned value.

Source: [guardrails public exports](https://github.com/pydantic/pydantic-ai-harness/blob/5f505ac77f9bb55d517ff9fd2ff6ad966f782d1b/pydantic_ai_harness/guardrails/__init__.py), plus the implementation paths above.

## External injection classification

StackOne Defender exposes Tier3Provider.classify(text, *, ctx=None), accepting synchronous or asynchronous results. An instance-specific provider can be passed in PromptDefense's tier3 configuration. Harness accepts that configured object through PromptInjectionDefender(defense=...). The process-wide default provider is a different facility and need not be used.

Source: installed stackone_defender public exports and core/prompt_defense.py; harness prompt_injection_defender/_capability.py. The dependency version was not captured in this first inspection; re-check before an implementation depends on this seam.

## Design questions opened by the evidence

- Which integrations need only a verdict, and which need generated guidance after a verdict?
- How will additional inference be counted when a harness run shares a budget?
- Which decisions must be replayable under durable execution?
- Can existing callbacks express the first integration, or is a distinct capability contract needed?

These are questions, not a plan to change the existing capabilities.
