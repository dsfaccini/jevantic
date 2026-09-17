# Jev API and Python SDK

Observed: 2026-09-16; live follow-up: 2026-09-17 UTC. This record combines provider documentation, OpenAPI, SDK source inspection, offline execution, and live requests with synthetic content.

## HTTP contract

The public [OpenAPI document](https://api.typesafe.ai/openapi.json) identifies API 0.2.0, with POST /v1/systemone and GET /v1/models. Authentication uses a Bearer token. The decision request requires state, model, and a nonempty named question mapping. State is a string, object, or array. Responses include answers, returned model identity, and token usage.

Choice returns a selected option and distribution. Score returns a potentially fractional expected rubric level and its distribution. Noul returns a yes probability. Documentation promises normalized distributions and bounded probabilities; the OpenAPI numeric fields do not encode all those bounds.

Sources: [HTTP reference](https://docs.typesafe.ai/api.md), [advanced values](https://docs.typesafe.ai/primitives/advanced.md), [OpenAPI](https://api.typesafe.ai/openapi.json).

## Limits and identity

The documentation describes a shared state-and-question budget around 32,000 tokens, not an exact contractual ceiling. Choice permits at most 255 options. The default alias is jev-latest. The model listing is account-dependent, and the returned model identity may differ from the requested alias. No immutable-version compatibility promise was established by this reading.

Sources: [Primitives](https://docs.typesafe.ai/primitives.md), [Choice](https://docs.typesafe.ai/primitives/choice.md), [SDK constants](https://docs.typesafe.ai/sdk/python/api/constants.md).

## SDK facilities

Inspected typesafe-sdk 0.6.0, Python >=3.10, commit [420ef4ff](https://github.com/typesafe-ai/typesafe-sdk-python/commit/420ef4ffb612d5a539a1e0f0fe883ff6770340af).

| Facility | Source observation |
| --- | --- |
| Sync and async clients | TypeSafeClient and AsyncTypeSafeClient expose typed questions, answers, model listing, request IDs, and raw responses |
| HTTP injection | Accepts custom transport or an httpx2 client; SDK closure also closes an injected client |
| Retries | Two retries by default for selected HTTP/network failures; honors retry headers and uses capped backoff with jitter |
| Errors | Typed HTTP, connection, timeout, and response-validation errors; retains request metadata |
| Future fields | Unknown fields are ignored; unknown answer types are skipped with a warning while raw data remains available |
| Logging | Standard request logging; debug includes bodies that are not redacted, although secret headers are redacted |

Sources at that commit: [public exports](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/__init__.py), [_core/client/aio/client.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/client/aio/client.py), [_core/retry.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/retry.py), [_core/errors.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/errors.py), [_core/response_types.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/response_types.py), [_core/logging.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/logging.py).

The offline checks below exercise cancellation, retries, lifecycle, and malformed payloads. The later live checks establish selected service behavior separately.

## Executed SDK behavior

The [reproducible probe](../../experiments/sdk_behavior.py) calls the public async SDK through local `httpx2.AsyncBaseTransport` implementations. Every client uses a fake key and a `.invalid` base URL. Observed with CPython 3.13.3, typesafe-sdk 0.6.0, and httpx2 2.13.0; execution and strict Pyright pass.

| Case | Executed observation | Implication for Jevantic |
| --- | --- | --- |
| Borrowed HTTP client | SDK `aclose()` closes the supplied client and transport | A wrapper must define ownership explicitly; closing a borrowed SDK client also closes its underlying HTTP client |
| Cancellation during a request | `CancelledError` propagates, the handler's `finally` runs, and no retry occurs | Ordinary async cancellation can propagate through this path |
| Cancellation and closure | HTTP client and transport remain open after cancellation; explicit SDK closure then closes both | Request cancellation and client ownership are separate concerns |
| 429 followed by success | A configured one-retry, zero-delay policy makes two attempts and retains the final request ID | Reuse SDK retry behavior rather than adding a second retry loop |
| Repeated 500 | The same policy makes two attempts, then raises `TypeSafeInternalServerError` with status 500 and the final request ID | Typed provider errors already carry useful metadata |
| Invalid known answer | A string where Noul requires a float raises `TypeSafeAPIResponseValidationError` with `answers.q.noul`, status 200, and request ID | Structural decoding errors already have a useful public category |
| Unknown answer kind | The public answer mapping omits it; the raw HTTP response retains it | Public decoded answers alone do not expose every returned answer |
| Semantically invalid result | SDK accepts Noul 1.5; Choice confidence -0.25; an unconfigured selected label and probability key; probability 1.2; and a missing requested answer | Jevantic needs validation against the actual question, beyond SDK scalar decoding |

These are client observations from synthetic responses, not evidence that the live provider emits those responses. The cancellation check covers a pending injected transport handler, not remote server cancellation. Retry timing and adverse real-network cleanup remain unverified.

Command:

```sh
uv run --no-project --with typesafe-sdk==0.6.0 python experiments/sdk_behavior.py
```

## Python type correlation

The SDK accepts Mapping[str, Question] and returns a non-generic SystemOneResponse. Its answers attribute is dict[str, Answer], where Answer is the union of NoulAnswer, ChoiceAnswer, and ScoreAnswer. The per-kind convenience mappings narrow that union but do not preserve named keys. ChoiceAnswer.choice is str, without a literal relationship to the input options.

The public typing fixture asserts method return types and diverse valid inputs. It does not assert request-specific answer-key or option-literal inference. The signatures support the conclusion that the SDK does not retain those correlations; this was not independently tested with a type checker.

No declarative result-schema facility was found in the inspected public exports or system_one signatures. This is a concrete interface gap to evaluate, not yet a selected Jevantic design.

Sources at the same pinned commit: [question types](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/question_types.py), [response types](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/response_types.py), [typing fixture](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/tests/typing/valid.py), [public exports](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/__init__.py).

## Source conflicts and unknowns

- Rendered HTTP documentation requires instructions and at least two Score levels. OpenAPI and SDK permit omitted instructions and a one-level Score; the live endpoint accepted both in the checks below. The endpoint enforces the documented ten-level maximum.
- Numeric range and distribution promises are stronger than the constraints encoded in OpenAPI and SDK float decoding. The offline probe confirms that several invalid numerical values and question/answer mismatches pass SDK decoding.
- Generated wire usage includes billing_units, but the public SDK wrapper accommodates its absence from actual API responses.
- Exact quotas, partial-batch behavior, idempotency, cancellation semantics, and the confidence formula remain unresolved.

Sources: [HTTP docs](https://docs.typesafe.ai/api.md), [OpenAPI](https://api.typesafe.ai/openapi.json), [_core/questions.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/questions.py), [_core/response_types.py](https://github.com/typesafe-ai/typesafe-sdk-python/blob/420ef4ffb612d5a539a1e0f0fe883ff6770340af/src/typesafe_sdk/_core/response_types.py).

## Executed live contract checks

The [opt-in script](../../checks/live_contract.py) sent synthetic support-ticket content using typesafe-sdk 0.6.0 with retries disabled. Successful responses identified the model as `jev-1.13.0`. Credentials are loaded in-process from an explicitly selected environment file and are absent from the observations.

| Case | Observed result |
| --- | --- |
| Noul, Choice, and Score in one request | HTTP 200; named typed answers and token usage; question-aware validation passed |
| Array and object Score descriptions with structured instructions | HTTP 200; returned legend matched the wire JSON descriptions |
| Omitted instructions with Noul criteria | HTTP 200 |
| One-level Score | HTTP 200; score 0, probability 1 on level 0 |
| Eleven-level Score | HTTP 400; provider error explicitly requires at most 10 levels |
| Less decisive Choice and two multi-level Scores | HTTP 200; distributions summed to 1 and weighted scores matched, without normalizing responses |

Evidence: [initial responses](../observations/live-contract.json), [exact upper-bound error](../observations/live-boundary.json), [numerical follow-up](../observations/live-precision.json). Records retain timestamps, model names, request IDs, and synthetic response bodies. They cover these requests only.

The prototype also checks that a Choice selects a maximal-probability option and that Score agrees with its weighted distribution, following the provider's [Choice](https://docs.typesafe.ai/primitives/choice) and [Score](https://docs.typesafe.ai/primitives/score) definitions. Its `1e-6` probability tolerance and scaled Score tolerance passed these live observations; the samples do not prove a universal rounding bound.

## Other model backends

TypeSafe maintains system-one-adapter 0.1.4, inspected at [0bb819b8](https://github.com/typesafe-ai/system-one-adapter-python/commit/0bb819b85d67a98c736d7c3004eae95f49f3daa3). It maps OpenAI, Anthropic, or custom provider outputs into TypeSafe-shaped decisions. It can request self-reported distributions and computes its own confidence measures.

This demonstrates an existing alternate backend shape. It does not establish that LLM-derived probabilities have Jev's calibration or uncertainty semantics.

Sources: [adapter README](https://github.com/typesafe-ai/system-one-adapter-python/blob/0bb819b85d67a98c736d7c3004eae95f49f3daa3/README.md), [provider protocol](https://github.com/typesafe-ai/system-one-adapter-python/blob/0bb819b85d67a98c736d7c3004eae95f49f3daa3/src/system_one_adapter/providers/base.py).

## Executed non-paid check

Command: curl --fail --location --silent --show-error https://api.typesafe.ai/openapi.json | jq '{openapi, api_version: .info.version, title: .info.title, endpoints: (.paths | keys)}'

Result: OpenAPI 3.1.0; API version 0.2.0; title TypeSafe; endpoints /v1/models and /v1/systemone.
