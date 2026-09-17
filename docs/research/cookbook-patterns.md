# Patterns in TypeSafe cookbooks

**Source inspection on 2026-09-16.** This note reads the published cookbook
sources only. It did not run their notebooks, use a provider, or inspect their
datasets or environment. `Noul` means a probability for a yes/no question;
`Choice` returns a label and its probability distribution; `Score` returns a
level on an ordered scale.

## 1. One state, a named battery of independent judgements

**Mechanics.** The parallel-questions cookbook sends one document plus 8
`Noul`, 2 `Choice`, and 3 `Score` questions in one request. The guardrail
cookbook applies the same idea to several hazards and a severity score. Each
answer remains named and independently interpretable.

**A convenience API could hide.** Packaging a heterogeneous question map with a
shared state into one request, dispatching the result back to typed named
handles, and perhaps controlled fan-out across many input states.

**Keep with callers.** Question wording, which signals belong together, request
limits, and any aggregation or routing rule. Batching is transport efficiency;
it is not a policy.

**Current core.** Explicit typed mixed `Batch` handles and
`Question.noul`/`choice`/`select`/`score` already express the battery. A
state-to-many-questions fan-out helper would be an ergonomic addition, not a
new primitive.

Sources: [parallel questions](https://docs.typesafe.ai/cookbooks/parallel_questions.md),
[LLM guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails.md).

## 2. Constrained extraction: find candidates in code, select a role in context

**Mechanics.** Regexes (or another high-recall finder) produce exact email,
phone, or money spans. A `Choice` selects one exact candidate or an explicit
`none` escape hatch; ordinary code then normalizes that verbatim value. The
model resolves role and context without being allowed to invent the value.

**A convenience API could hide.** Deduplication and document-order preservation,
creation of the candidate selection question, an opt-in `none` option, and
returning the selected original span alongside confidence.

**Keep with callers.** Candidate discovery, normalization rules, candidate cap
and two-stage narrowing, plus what to do when no candidate fits. These encode
domain recall and correctness requirements.

**Current core.** The caller can form the candidate set with `choice`/`select`
and retain the original value. There is no candidate-discovery or bounded
selection workflow, appropriately leaving finder and fallback policy explicit.

Source: [pre-parsed value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md).

## 3. Closed-world function calling compiled from an interface

**Mechanics.** The function-calling cookbook reflects a function signature:
`Literal` becomes one `Choice`, `list[Literal]` becomes one yes/no question per
member, and `bool` becomes a flag. A separate *stated?* predicate preserves a
function default when the request did not name an optional argument. The chosen
function and arguments are then checked against the ordinary typed callable.

**A convenience API could hide.** Introspection of the closed sets, generation
of the question inventory and reversible option mappings, response decoding,
and confidence as the least-certain judgement in the selected call.

**Keep with callers.** Human-readable semantics for each option, tool
eligibility, defaults, free-form/number/date handling, execution permission,
and the response to low confidence. A type annotation alone cannot supply those
product choices.

**Current core.** It has the question kinds needed for a manual dispatcher. A
schema/signature compiler is the conspicuous missing ergonomic layer; it should
remain a proposal until its interface and scope are settled.

Source: [function calling](https://docs.typesafe.ai/cookbooks/function_calling.md).

## 4. Score candidates independently, then rank or reject them

**Mechanics.** Re-ranking asks the same yes/no question for every
query--candidate pair, sorts by the returned probability, and only reorders a
fast-search shortlist. Skill suggestion applies the same shape in two stages:
rank a wide roster with short descriptions, then re-read a small shortlist with
fuller text. Absolute “does this fit?” and “does a skill apply?” predicates can
reject all candidates rather than forcing the top-ranked one through.

**A convenience API could hide.** Pair expansion, bounded concurrency, stable
sort/order preservation, top-*k* selection, and the wide-to-deep shortlist
hand-off.

**Keep with callers.** How candidates are retrieved, question text, *k*,
concurrency and budget, confidence/gating thresholds, and whether a rejected
result falls back to another path. Ranking is useful only relative to the
application's candidate source and decision cost.

**Current core.** `noul` plus typed batches supports explicit pair scoring. It
does not provide ranking, candidate-pair fan-out, or a cascade helper.

Sources: [re-ranking](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md),
[skill suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion.md).

## 5. Separate measurement from the policy that acts on it

**Mechanics.** The guardrail recipe emits a battery of hazard probabilities and
an ordered severity score for both inputs and outputs. Application code maps
those signals through named thresholds and precedence to `pass`, `review`,
`block`, or `support`; the same measurements can therefore yield different
decisions under different policies.

**A convenience API could hide.** A small, transparent evaluator for named
thresholds, per-hazard actions, severity overrides, and deterministic
precedence, returning both the decision and the evidence used.

**Keep with callers.** The hazards, threshold values, actions, precedence,
review queue, audit needs, and calibration data. Those are governance and
product choices, never a model default.

**Current core.** Its question primitives and `Evaluator` cover signal
production and assessment. Keeping routing ordinary caller code is a sound
baseline; a policy wrapper would need to preserve that visibility.

Source: [LLM guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails.md).

## 6. Traverse a taxonomy through distributions, not a single early choice

**Mechanics.** Hierarchical classification turns each node's direct children
into a `Choice`. Greedy search follows the local winner. Beam search evaluates
the current frontier in parallel, retains the best *K* paths by geometric-mean
edge probability (normalizing for depth), and can recover from an ambiguous
early branch.

**A convenience API could hide.** Direct-child question construction, one-node
short-circuiting, frontier batching, path bookkeeping, beam pruning, maximum
depth, and diagnostic records with a top/second-path separation ratio.

**Keep with callers.** The taxonomy and label descriptions, beam width, path
scoring formula, stopping rule, abstention/fallback behavior, and what
observability to retain. They determine accuracy, latency, and cost.

**Current core.** It can ask the per-node `choice` questions and batch a
frontier. It has no taxonomy traversal or beam-search orchestration, which is
application-level logic rather than evidence for a universal default.

Source: [hierarchical classification](https://docs.typesafe.ai/cookbooks/hierarchical_classification.md).

## Reported notebook results (not reproduced)

These are the cookbook authors' cached-notebook observations, not evidence
replicated for Jevantic:

* **Parallel questions:** a 13-question GDPR example, averaged over five
  repeats, reports 12.2x lower cost and 10.0x less sequential wall-clock time
  for one batch than 13 single-question calls. The source notes that concurrent
  singles reduce the latency difference while not removing the repeated-input
  cost.
* **Re-ranking:** on 40 CLERC queries with a BM25 top-30 shortlist, the authors
  report top-1 accuracy from 5% to 18%, top-10 from 38% to 62%, and 1,200
  scoring calls costing $0.0645.
* **Skill suggestion:** on 488 authored Hermes requests, the authors report
  wrong skill loads of 16.8% to 7.3% and needless loads of 9.8% to 4.0% after
  the two-stage suggestion.
* **Hierarchical classification:** four illustrative examples report 2/4
  greedy matches and 4/4 with beam width three. This is a tiny demonstration,
  not a benchmark.

## Ergonomic gaps most clearly exposed

1. **A bounded typed fan-out and result collector** for repeated question/state
   pairs would remove boilerplate in re-ranking and taxonomy frontiers while
   preserving caller concurrency and ordering controls.
2. **A schema-to-question compiler for closed-world actions** would turn typed
   signatures plus caller-written semantics into an inspectable dispatcher;
   it is distinct from arbitrary tool calling.
3. **A small ranking/cascade composition layer** could support explicit
   shortlist, rank, gate, and abstain stages without deciding retrieval,
   thresholds, or fallback policy for the caller.
