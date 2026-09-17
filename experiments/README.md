# Design experiments

The initial offline experiments test whether candidate interfaces preserve useful Python types. The later [standalone alpha](../README.md) packages the typed-question approach with real SDK execution and validation. The public interface continues to develop.

The separate SDK behavior probe checks the dependency through its public interface with deterministic local HTTP responses.

The [core verification record](../docs/verification.md) covers offline behavioral tests, static checks, Python compatibility, package installation, and opt-in live evidence. These broader checks are separate from the small typing probes below.

| Probe | Question | Observed result |
| --- | --- | --- |
| [Typed questions](typed_questions.py) | Can one heterogeneous batch return the answer type associated with each question? | Strict Pyright accepts precise literal, enum, and application-object results without casts or locally declared `Any`; execution preserves the selected local object and rejects a foreign handle |
| [Typed schema](typed_schema.py) | Can a caller-owned Pydantic model describe a precisely typed result? | Strict Pyright accepts named fields and literal-valued results; execution constructs the model and reads question metadata |
| Contradictory metadata in the schema probe | Does static checking reject a question whose options disagree with its result annotation? | No. The fixture type-checks; Pydantic rejects a response containing the contradictory choices at runtime |

The third observation establishes a design obligation: a schema interface needs preflight checks that compare question definitions with result annotations, before spending a provider request. The experiment does not implement those checks.

## Reproduce

The experiments require Pydantic 2, `typing_extensions`, and Pyright. No provider credentials or network requests are used.

```sh
pyright experiments/typed_questions.py experiments/typed_schema.py --project experiments/pyrightconfig.json
python experiments/typed_questions.py
python experiments/typed_schema.py
```

Observed on 2026-09-16 with CPython 3.13.3, Pydantic 2.13.4, and Pyright 1.1.411. Pyright used strict mode and a Python 3.10 target. Both scripts completed successfully and the type check passed. Python 3.10 runtime compatibility has not been tested.

The commands were executed using the existing `/Users/david/pydantic/ai/base/.venv` environment, with its interpreter passed to Pyright through `--pythonpath`. This did not install dependencies or establish Jevantic's supported Python or dependency versions.

## Limits

- Wire answer classes are deliberately simplified local data, not the TypeSafe SDK's response types.
- State encoding, instructions, confidence, usage, request provenance, HTTP errors, resource ownership, retries, and cancellation are absent.
- Numerical validation, mutation safety, repeated evaluation, and batch freezing are not established.
- The question probe decodes answers during completion and retrieval. This proves the typing mechanism; it does not choose a caching or decoding strategy.
- A dynamic list retains its common item type. Static typing cannot name values discovered only at runtime.
- Pydantic output validation does not by itself establish the correspondence between a question and its answer.

No model-quality, calibration, performance, or live-contract claim follows from these probes.

## SDK behavior probe

[sdk_behavior.py](sdk_behavior.py) exercises typesafe-sdk 0.6.0 through injected local transports with fake credentials and a `.invalid` base URL. It checks client closure, cancellation, configured retries, typed errors, unknown answer kinds, and missing semantic validation. All assertions pass; strict Pyright and Ruff checks pass.

```sh
uv run --no-project --with typesafe-sdk==0.6.0 python experiments/sdk_behavior.py
```

Observed on 2026-09-16 with CPython 3.13.3, typesafe-sdk 0.6.0, and httpx2 2.13.0. A separate strict Pyright invocation targeted this file using the SDK environment's interpreter. The default typing-probe configuration does not require the SDK.

See [executed SDK findings](../docs/research/jev-api-contract.md#executed-sdk-behavior) for exact outcomes and limits. In particular, cancellation leaves the client open; the probe subsequently closes it explicitly. This is not evidence of live server cancellation or a real network connection teardown.
