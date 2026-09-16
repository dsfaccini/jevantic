# Jev decision semantics

Observed: 2026-09-16. Documented contracts, not local runtime verification.

## Questions and answers

| Primitive | Judgment | Answer |
| --- | --- | --- |
| Choice | Select an unordered option | Selected option, probabilities, confidence |
| Score | Locate state on an ordered rubric | Score, legend, probabilities, confidence |
| Noul | Estimate whether a statement is true | Probability of yes; no separate confidence |

Questions in a request share state but are evaluated separately. Question IDs identify answers for the caller; they are not model instructions. Mixed types can share a request.

An answer that changes subsequent state or options requires another request. Questions answerable from original state can be batched, including questions code may later ignore.

[Primitives](https://docs.typesafe.ai/primitives)

## Uncertainty

Confidence summarizes the concentration of a Choice or Score distribution. It is derived from that distribution, not a separate correctness judgment. Noul near 0.5 means uncertainty about a binary proposition, not a medium rating.

Applications may use the full distribution or an appropriate statistic. Thresholds encode application policy and require domain evaluation.

[Confidence](https://docs.typesafe.ai/confidence), [Primitives](https://docs.typesafe.ai/primitives)

## Composition

TypeSafe documents speculative batching, confidence-based routing, combining scores in code, and intent routing. Its workflow examples concern alerts, traces, invoices, and customer service. Their reference labels combine other models' judgments.

[Patterns](https://docs.typesafe.ai/patterns), [Workflow evaluations](https://evals.typesafe.ai/)

## Pending research

Inspect the full request schema, SDK facilities, numerical invariants, failures, limits, retries, lifecycle, usage, and telemetry. Provider class names do not prescribe Jevantic's interface.
