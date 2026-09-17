# Jevantic

Vocabulary for structured probabilistic judgments and their use in software.

## Language

**Jevantic**: The standalone Python library developed in this repository.

**Jev**: TypeSafe AI's decision model, which evaluates typed questions against supplied state.

**State**: Content supplied to a model for evaluation, such as documents, records, observations, or a program's current situation.

**Question**: A defined judgment about state, including its instructions and allowed answer shape.

**Answer**: A model's response to a question, including the values and uncertainty information supplied by that question type.

**Probability**: A model's estimated likelihood of an allowed outcome.

**Confidence**: TypeSafe's summary statistic of an answer's probability distribution. `Choice` and `Score` expose it; `Noul` does not.

**Primitive**: A basic model operation that other behavior composes. Jev's primitives are `Choice`, `Score`, and `Noul`.

**Rubric**: Ordered level descriptions that define what a `Score` measures.

**Ergonomics**: How clear, convenient, and hard to misuse an interface is.

**Convenience API**: A reusable interface that packages recurring work. It can add validation, type preservation, or execution behavior.

**Syntactic sugar**: Shorter syntax with equivalent underlying meaning. It is narrower than the idea of a convenience API.

**Abstraction**: A boundary that exposes useful operations while hiding their implementation details.

**Batch**: Several independent questions evaluated against one shared state in one logical API call. Transport retries can add HTTP attempts.

**Fan-out**: Multiple independent evaluations over different inputs, with explicit concurrency and result collection.

**Policy**: Application rules determining what to do with an answer, including thresholds and fallback decisions.

**Workflow**: An explicit sequence of evaluations and actions, including stages that depend on previous results.

**Backend**: The engine that performs an evaluation. An **adapter** translates between interfaces.

**Static typing**: Checking the relationship between inputs, operations, and result types before execution. **Validation** checks actual values at runtime. Neither establishes that a model's judgment is correct.

**Capability**: A Pydantic AI extension that composes tools, instructions, settings, or agent lifecycle hooks into reusable behavior.

These terms describe the domain; they do not prescribe public class names. See the [short lesson](docs/learning/lessons/0001-primitive-convenience-workflow.html) for the distinction between primitives, convenience APIs, and workflows.
