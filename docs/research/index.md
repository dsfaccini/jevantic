# Research index

Updated: 2026-09-16

| Record | Evidence | Purpose |
| --- | --- | --- |
| [Observed workloads](use-cases.md) | Primary articles, author posts, example source | Understand concrete uses and their evidence limits |
| [Jev semantics](jev-semantics.md) | Official TypeSafe documentation | Preserve decision and uncertainty semantics |
| [Jev API contract](jev-api-contract.md) | OpenAPI and pinned SDK source | Identify existing facilities and unresolved contracts |
| [Harness interfaces](harness-interfaces.md) | Pinned harness and installed core source | Identify integration points and lifecycle obligations |
| [Pydantic AI patterns](pydantic-ai-patterns.md) | Pinned source, tests, and CI configuration | Make robustness and ergonomic typing concrete |

Initial investigations and the Python SDK answer-type follow-up are recorded. Runtime behavior beyond the OpenAPI fetch remains untested here.

## Evidence conventions

- A documented contract is a provider's stated behavior.
- A source observation describes the cited code revision.
- An executed observation includes its command, result, and environment.
- A published experiment belongs to its author and evaluation conditions.
- A proposal is a design option, not an accepted requirement.

## Primary sources

- [TypeSafe launch](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [TypeSafe documentation](https://docs.typesafe.ai/introduction)
- [Workflow evaluations](https://evals.typesafe.ai/)
- [Nathan Flurry's framing](https://x.com/NathanFlurry/status/2100036101809619314)
- [Vercel's fx announcement](https://x.com/rauchg/status/2100307962262872105)
- [Every's experiments](https://every.to/also-true-for-humans/mini-vibe-check-typesafe-s-jev-judged-everything-i-ve-written-in-0-7-seconds)
- [Eventum's recruiting case study](https://www.eventum.ai/case-studies/how-eventum-cut-llm-screening-costs-104x-with-typesafe)
- [Near Here's validation study](https://nearhere.events/blog/typesafe-jev-mistral-gemini-event-validation)
- [Jev Review](https://github.com/devagrawal09/jev-review)

This project has not replicated performance, calibration, or reliability claims. Schema conformance is distinct from the correctness of a judgment.
