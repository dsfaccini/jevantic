# Jevantic

Vocabulary for structured probabilistic judgments and their use in software.

## Language

**Jevantic**: The standalone Python library under design in this repository.

**Jev**: TypeSafe AI's decision model, which evaluates typed questions against supplied state.

**State**: Content supplied to a model for evaluation, such as documents, records, observations, or a program's current situation.

**Question**: A defined judgment about state, including its instructions and allowed answer shape.

**Answer**: A model's response to a question, including the values and uncertainty information supplied by that question type.

**Probability**: A model's estimated likelihood of an allowed outcome.

**Confidence**: TypeSafe's summary statistic of an answer's probability distribution. Choice and Score expose it; Noul does not.

**Capability**: A Pydantic AI extension that composes tools, instructions, settings, or agent lifecycle hooks into reusable behavior.

These terms describe the domain; they do not prescribe Jevantic's future public class names.
