# Alpha verification

Observed: 2026-09-17 UTC. Results below describe the checked source and recorded service responses, not guarantees about every future model response or application.

Checked implementation: [`03125f427f605082f900b628dc990a936f8364b6`](https://github.com/dsfaccini/jevantic/commit/03125f427f605082f900b628dc990a936f8364b6). The following documentation-only update records its verification; it does not change the tested implementation.

## Current package

The prepared `jevantic` alpha builds as a source distribution and wheel, version `0.1.0a1`, with `py.typed`. This version is not yet published; `0.1.0a0` remains the published [PyPI release](https://pypi.org/project/jevantic/). Its core stays independently installable; the optional `pydantic-ai` extra supplies `InputGuardrail` and `OutputGuardrail`. The current [installation instructions](../README.md#install) use the source repository for the simplified API.

| Check | Result and environment |
| --- | --- |
| Behavioral suite | Pass on CPython 3.13.3 with Pydantic 2.13.5, typesafe-sdk 0.6.0, httpx2 2.13.0 |
| Branch coverage | Pass: 100%, no missing source lines or branches |
| Strict static checks | Pass with Pyright 1.1.414 across source, tests, public type assertions, examples, check scripts, and the comparison renderer |
| Invalid caller checks | Pass: every marked invalid expression is rejected with its expected diagnostic category |
| Style | Ruff 0.16.8 lint and format checks pass |
| Distribution build | Source distribution and wheel build successfully |
| Installed wheel | The complete suite and 100% branch-coverage check pass from an isolated wheel installation on CPython 3.13.3 with Pydantic 2.13.5 and Pydantic AI 2.44.0 |
| Base installation and Pydantic floor | The complete core suite passes from an isolated wheel with Pydantic 2.10.0 and no Pydantic AI package installed; structured serialization and field exclusions work at the declared floor |
| Capability version floor | Public agent tests for both guardrails, spec construction, and complete comparison examples pass with Pydantic AI 2.38.0 and its matching `pydantic-graph` |
| Direct decisions and inferred data | Pass for full-result convenience methods, enum/literal choices, dataclass/Pydantic inputs and exclusions, original selected objects, construction-time snapshots, explicit projections, and nonfinite values rejected before I/O |
| Guardrail boundaries | Pass for declarative thresholds and custom policies, owned and borrowed evaluators, accepted/rejected decisions, separate usage/events, cancellation, wrapped durable contexts, deferred-loading rejection, and output transformations before completion |
| Streaming contract | Tests verify that partial/final streamed text can precede an output rejection, while a rejected event stream omits `AgentRunResultEvent`; typed event listeners receive completion decisions |
| Cancellation during close | Pass for repeated direct asyncio task cancellation and AnyIO scope cancellation on asyncio and Trio; owned closure completes, cancellation remains effective, original close failures propagate |
| Independent-input fan-out | Pass on asyncio and Trio: ordered typed results, bounded in-flight work, lazy input, SDK retry reuse, iterator and provider errors, sibling cancellation, and caller-owned client reuse |
| Marketing comparisons | Executed examples compare object identity, equivalent wire questions, bounded concurrency, input ordering, lazy iteration, failure cleanup, and equivalent guardrail decisions/events. All four rendered clips are 1920×1080, 30 fps, and exactly four seconds; before/after posters were visually checked |

The installed-package check imported Jevantic from the isolated environment's `site-packages`, without a source-path override. Local development and checks now use Python 3.13 only. Earlier exploratory runs on other interpreters are not evidence for the current package's compatibility; the configured CI matrix owns that check.

Ruff and Pyright target the declared minimum Python 3.12 while running locally under Python 3.13. This checks the minimum syntax and typing contract without installing or running another local interpreter.

The [Checks workflow](https://github.com/dsfaccini/jevantic/actions/workflows/checks.yml) runs Python 3.12, 3.13, and 3.14 with the optional integration and a 100% branch-coverage gate. Its Python 3.13 job also checks typing, invalid callers, lint, formatting, builds, the integration version floor, and base-only installation. Inspect the run for the exact commit being reviewed.

The source archive excludes the local `.env` and virtual environment. The wheel includes the Python modules and `py.typed`, without repository instruction files.

## Historical core checks

[Run 35218750382](https://github.com/dsfaccini/jevantic/actions/runs/35218750382) checked the earlier core-only commit `b7c2b6d626d438213e339f7d8c91ee32ea552aeb` on Python 3.12, 3.13, and 3.14. That core wheel was also tested with Pydantic 2.10.0. These results predate the optional capabilities and public type rename; they do not establish compatibility for a later revision.

## Reproduce offline

From the repository root:

```sh
uv sync --locked --extra pydantic-ai --python 3.13
uv run --extra pydantic-ai coverage run -m pytest tests -q
uv run --extra pydantic-ai coverage report --show-missing
uv run --extra pydantic-ai pyright src/jevantic tests examples checks assets/marketing/build.py
uv run --extra pydantic-ai python checks/typecheck_negative.py
uv run --extra pydantic-ai ruff check src tests examples checks typecheck assets/marketing
uv run --extra pydantic-ai ruff format --check src tests examples checks typecheck assets/marketing
uv build --no-sources
```

The tests inject local transports into the real SDK. Fake keys and `.invalid` endpoints make their request path explicit. They verify wire payloads and response decoding through the public API, including mixed results, option identity, snapshots, malformed answers, repeatable batches, ownership, failures, and cancellation. Capability tests exercise Pydantic AI's public `Agent`, `FunctionModel`, event, spec, and streaming interfaces.

Negative type fixtures are intentionally excluded from the ordinary positive project check. Their dedicated script requires every marked diagnostic and rejects errors on unmarked lines.

## Live provider observations

Nine synthetic requests were made with explicit credentials and SDK retries disabled. Seven exercised service contracts; two exercised complete assessment functions through a separately installed prototype wheel. No real user or business data was sent. The returned model was `jev-1.13.0`.

| Observation | Evidence |
| --- | --- |
| Mixed `Choice`, `Score`, and `Noul` answers validate in one request | [Contract responses](observations/live-contract.json) |
| Object and array rubric descriptions round-trip successfully | [Contract responses](observations/live-contract.json) |
| Omitted instructions and a one-level `Score` are accepted | [Contract responses](observations/live-contract.json) |
| An eleven-level `Score` is rejected with an explicit maximum of ten | [Boundary response](observations/live-boundary.json) |
| Ambiguous answers satisfy the numeric checks without normalization | [Precision responses](observations/live-precision.json) |
| Command-risk and two-rubric draft assessment run through the public interface | [Workflow observations](observations/live-examples.json) |

The workflow observation records the earlier prototype's installed path under Python 3.10, before the Python-version scope changed. It establishes that the public assessment functions reached the live provider through an installed package. The current alpha's installed-distribution check is the separate Python 3.13 offline check above.

The opt-in commands below send paid provider requests. They are separate from the default suite and CI:

```sh
uv run python -m checks.live_contract --env-file /path/to/.env --output /tmp/jevantic-contract.json
uv run python -m checks.live_examples --env-file /path/to/.env --output /tmp/jevantic-examples.json
```

The environment file supplies `TYPESAFE_API_KEY`. Scripts load it in process; recorded observations contain synthetic inputs, answers, statuses, and request identifiers, without authorization headers. `--case` on the contract script limits execution to one named case. Its eleven-level case deliberately uses the SDK directly because Jevantic rejects that rubric before I/O.

The live-check commands use Python's module form so that the repository's example modules are importable. Both command-line parsers were checked with `--help`, without sending another provider request. The new fan-out and ranking example use the same evaluated primitive path and are covered offline; no new live accuracy or performance result is claimed for them.

## Evidence limits

- Finite, bounded probabilities and question/answer consistency are library guarantees. Correct real-world judgments and calibrated policy thresholds require application evaluations.
- Numeric tolerances are explicit alpha policy: `1e-6` for probability sums and `Choice` maxima, `1e-6` per level for a weighted `Score`. Recorded live responses satisfy them; the service has not promised a universal rounding bound.
- SDK retry and cancellation probes use deterministic local transports. They do not prove that a cancelled request stops computation on the provider's server.
- Python 3.12 and 3.14 verification belongs to the linked CI runs; the local execution evidence above is Python 3.13. No performance or calibration benchmark has been replicated.
- The HTML lesson has been authored and its local references checked; visual browser verification is pending because the shared Chrome DevTools connection was unavailable.

See the [SDK behavior probe](../experiments/sdk_behavior.py), [provider contract research](research/jev-api-contract.md), and [requirements audit](design/verification-plan.md) for the distinction between source inspection, executed behavior, and pending scope.
