# Candidate interfaces

Initial comparison: 2026-09-16. Updated 2026-09-17: typed questions and ordinary functions form the first alpha; the schema facade remains a proposal.

Three independent design investigations considered reusable typed questions, caller-owned result schemas, and callable evaluations. The callable design converged on ordinary functions that build typed questions; it does not require a third execution framework.

## What all candidates must preserve

A request evaluates named questions against shared state. Choice, Score, and Noul have different answer semantics. A caller should retain those distinctions without repeatedly narrowing a heterogeneous answer union. Dynamic option sets, mixed question kinds, and uncertainty information must remain available.

Application code owns the action taken after a judgment. An answer is not an authorization or an automatic side effect. Independent questions sharing state can fit one provider request; judgments whose inputs depend on earlier answers require explicit subsequent requests.

Sources: [Jev semantics](../research/jev-semantics.md), [HTTP and SDK contract](../research/jev-api-contract.md), [observed workloads](../research/use-cases.md).

## 1. Reusable typed questions

Each question carries its answer type. Adding a question to a batch returns a typed handle; retrieving the answer with that handle preserves its type.

Illustrative interface, not executable package syntax:

```python
batch = evaluator.batch(state=command_context)
risk = batch.add('risk', secret_exposure_question)
route = batch.add('route', command_route_question)
result = await batch.run()

risk_answer = result.answer(risk)      # NoulAnswer
route_answer = result.answer(route)   # ChoiceAnswer[Route]
```

The implementation hides request assembly, answer-key correlation, runtime answer checks, and recovery of a local typed option from a returned wire label. The caller learns handles and an explicit batch lifecycle. Runtime-built catalogs and different combinations of questions do not require new result classes.

The [question probe](../../experiments/typed_questions.py) establishes a viable generic mechanism: immutable covariant handles retain typed decoder functions while batch storage treats handles uniformly. Precise literals, enums, and application objects pass strict checking without locally declared `Any` or casts. Its simplified response data and lifecycle are not a production implementation.

## 2. A caller-owned result schema

The caller declares the expected result as a Pydantic model. Question metadata accompanies each field; evaluation returns that model and separate request metadata.

Illustrative interface:

```python
class CommandReview(BaseModel):
    risk: Annotated[NoulAnswer, NoulQuestion('Could this expose a secret?')]
    route: Annotated[
        ChoiceAnswer[Literal['allow', 'block']],
        ChoiceQuestion(('allow', 'block')),
    ]

result = await evaluator.evaluate(command_context, result_type=CommandReview)
result.value.risk.probability
result.value.route.selected
```

This gives fixed assessments direct, discoverable field access and an ordinary Pydantic result to store or pass onward. The implementation also has to reconcile field annotations with question metadata. A missing question, the wrong question kind, or inconsistent literal options must fail before I/O.

Runtime options require an additional explicit question mapping or another binding mechanism. A fixed result model can retain a known enum or literal type; an arbitrary runtime option set yields a common type such as `str`. An open-ended number of named questions no longer matches a fixed model naturally.

The [schema probe](../../experiments/typed_schema.py) verifies generic model construction and precise field types. It also demonstrates that contradictory `Annotated` question metadata passes static checking. Pydantic catches incompatible returned choices at runtime, but a preflight compiler remains unproven work.

## 3. Callable question builders

Ordinary functions can use application dependencies and runtime data to return typed question definitions:

```python
def choose_candidate(candidates: Sequence[Candidate]) -> Question[ChoiceAnswer[Candidate]]:
    return choice([Option(candidate.identifier, candidate) for candidate in candidates])
```

The [question probe](../../experiments/typed_questions.py) exercises this composition with local application objects. The function builds a question; the explicit evaluator or batch performs I/O. Python controls branching and subsequent stages.

This adds no decorator registration, implicit request scheduling, or workflow engine. It complements typed question objects. A reusable callable that also owns execution would be a separate convenience whose value still needs a representative workload.

## Comparison

| Concern | Typed questions | Result schema | Callable builders |
| --- | --- | --- | --- |
| Fixed mixed assessment | Typed handles, extra retrieval step | Direct named fields | Reuses either execution interface |
| Questions assembled at runtime | Natural | Needs another binding mechanism or a dynamic escape hatch | Natural construction mechanism |
| Selected application object | Wire label maps back to the original typed object | Requires a binding beyond a string result field | Builds the typed option set |
| Reuse across combinations | Reuse each question | Reuse declarations or whole schemas | Reuse normal functions |
| One request versus fan-out | Must be explicit in evaluation | Must be explicit in single/many evaluation | Must remain explicit at the caller |
| Complexity concentrated in implementation | Validation, decoding, handle ownership | Validation plus schema compilation and binding | Application construction stays in Python |

All three have leverage when removing repeated validation and type recovery from callers. The question interface offers locality around request execution and typed decoding; the schema interface adds locality around recurring fixed assessments. Their HTTP dependency is the same true external dependency, so this comparison does not justify parallel transport implementations.

The [executed SDK probe](../research/jev-api-contract.md#executed-sdk-behavior) confirms that several semantic constraints are not enforced by SDK decoding: probability bounds, configured Choice labels, and correspondence to requested answer names. Validation against question definitions therefore has concrete work to own in either interface.

## Recommendation for the next experiment

Use typed questions as the fundamental composition mechanism. Permit ordinary functions to construct them. Then build one small schema facade over that same mechanism and compare the complete call sites on the selected workloads. This retains the flexible layer while giving fixed assessments a route to familiar Pydantic ergonomics.

Do not treat the two interfaces as independent runtimes. Validation, metadata, and transport behavior should have one owner. Reuse the SDK's injected transport for deterministic HTTP responses unless concrete evidence shows that a new seam is needed.

The first alpha now follows the typed-question foundation. Backend scope is Jev-first; local development uses Python 3.13 with other supported-version checks in CI. Workflow priorities are incremental rather than a fixed feature menu. Public names can evolve during the alpha, and a schema compiler still needs a complete comparison with ordinary assessment functions.

## Questions opened by the experiments

- Which calling style should the introductory example use?
- Is declaring a result class worthwhile for the selected recurring assessments?
- How should per-call dynamic options bind to reusable question definitions?
- What is the simplest explicit interface for one shared-state request versus several independent-state requests?
- Can schema preflight checks remain small, understandable, and consistent with the fundamental layer?

## Verification

Strict Pyright and both offline scripts pass in the recorded environment. See the [experiment record](../../experiments/README.md) for exact scope, commands, versions, and limitations. No provider calls were made.

The subsequent [typed core](core-experiment.md) adds executable SDK-backed assessments, failure-path tests, and live evidence. It is the initial alpha interface; the schema facade is not implemented.

Process reference: [Design It Twice](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/engineering/codebase-design/DESIGN-IT-TWICE.md).
