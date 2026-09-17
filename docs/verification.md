# Alpha verification

Observed: 2026-09-17 UTC. Results below describe the checked source and recorded service responses, not guarantees about every future model response or application.

## Current package

The standalone `jevantic` package builds as a source distribution and wheel, version `0.1.0a0`. It includes `py.typed`. The wheel is installed and tested separately from the source checkout. It has not been published to PyPI.

| Check | Result and environment |
| --- | --- |
| Behavioral suite | Pass on CPython 3.13.3 with Pydantic 2.13.5, typesafe-sdk 0.6.0, httpx2 2.13.0 |
| Branch coverage | Pass: 100%, no missing source lines or branches |
| Strict static checks | Pass with Pyright 1.1.414 across source, tests, public type assertions, examples, and check scripts |
| Invalid caller checks | Pass: every marked invalid expression is rejected with its expected diagnostic category |
| Style | Ruff 0.16.8 lint and format checks pass |
| Distribution build | Source distribution and wheel build successfully |
| Installed wheel | The same behavioral suite and full branch-coverage check pass using the installed wheel on CPython 3.13.3 with the declared minimum Pydantic 2.10.0 |
| Cancellation during close | Pass for repeated direct asyncio task cancellation and AnyIO scope cancellation on asyncio and Trio; owned closure completes, cancellation remains effective, original close failures propagate |
| Independent-input fan-out | Pass on asyncio and Trio: ordered typed results, bounded in-flight work, lazy input, SDK retry reuse, iterator and provider errors, sibling cancellation, and caller-owned client reuse |
| CI | The [Checks workflow](https://github.com/dsfaccini/jevantic/actions/workflows/checks.yml) tests Python 3.12, 3.13, and 3.14; consult the run for a specific commit for its result |

The installed-package check imported Jevantic from the isolated environment's `site-packages`, without a source-path override. Local development and checks now use Python 3.13 only. Earlier exploratory runs on other interpreters are not evidence for the current package's compatibility; the configured CI matrix owns that check.

Ruff and Pyright target the declared minimum Python 3.12 while running locally under Python 3.13. This checks the minimum syntax and typing contract without installing or running another local interpreter.

The final source archive and wheel were rebuilt from the committed repository. Every packaged source file and `py.typed` matched the tested installation byte-for-byte. The source archive excluded the local `.env` and virtual environment.

## Reproduce offline

From the repository root:

```sh
uv sync --locked
uv run coverage run -m pytest tests/test_evaluation.py tests/test_questions.py tests/test_lifecycle.py tests/test_examples.py tests/test_fanout.py -q
uv run coverage report --show-missing
uv run pyright src/jevantic tests examples checks
uv run python checks/typecheck_negative.py
uv run ruff check src tests examples checks typecheck
uv run ruff format --check src tests examples checks typecheck
uv build
```

The tests inject local transports into the real SDK. Fake keys and `.invalid` endpoints make their request path explicit. They verify wire payloads and response decoding through the public API, including mixed results, option identity, snapshots, malformed answers, repeatable batches, ownership, failures, and cancellation.

Negative type fixtures are intentionally excluded from the ordinary positive project check. Their dedicated script requires every marked diagnostic and rejects errors on unmarked lines.

## Live provider observations

Nine synthetic requests were made with explicit credentials and SDK retries disabled. Seven exercised service contracts; two exercised complete assessment functions through a separately installed prototype wheel. No real user or business data was sent. The returned model was `jev-1.13.0`.

| Observation | Evidence |
| --- | --- |
| Mixed Choice, Score, and Noul answers validate in one request | [Contract responses](observations/live-contract.json) |
| Object and array rubric descriptions round-trip successfully | [Contract responses](observations/live-contract.json) |
| Omitted instructions and a one-level Score are accepted | [Contract responses](observations/live-contract.json) |
| An eleven-level Score is rejected with an explicit maximum of ten | [Boundary response](observations/live-boundary.json) |
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
- Numeric tolerances are explicit alpha policy: `1e-6` for probability sums and Choice maxima, `1e-6` per level for a weighted Score. Recorded live responses satisfy them; the service has not promised a universal rounding bound.
- SDK retry and cancellation probes use deterministic local transports. They do not prove that a cancelled request stops computation on the provider's server.
- Python 3.12 and 3.14 verification belongs to the linked CI runs; the local execution evidence above is Python 3.13. No performance or calibration benchmark has been replicated.
- The HTML lesson has been authored and its local references checked; visual browser verification is pending because the shared Chrome DevTools connection was unavailable.

See the [SDK behavior probe](../experiments/sdk_behavior.py), [provider contract research](research/jev-api-contract.md), and [requirements audit](design/verification-plan.md) for the distinction between source inspection, executed behavior, and pending scope.
