# Jevantic discovery

Updated: 2026-09-17 UTC

## Confirmed requirements

- Build a standalone Python library named Jevantic.
- Provide elegant, powerful, flexible typed interfaces for Jev.
- Keep the fundamental layer composable and available to callers.
- Add convenient interfaces for recurring uses where those interfaces earn their maintenance cost.
- Aim for Pydantic AI's robustness and maintainability through explicit design and verification.
- Establish Jevantic independently before integrating it into Pydantic AI Harness.
- Explore harness capabilities that benefit from typed decisions and Jev's execution characteristics.
- Maintain a curated, persistent knowledge base with dedicated research subagents.
- Develop shared understanding incrementally.
- Focus on Jev; add another backend when a concrete need establishes its value.
- Deliver useful workflows incrementally, beginning with small changes that have high impact. The initial examples do not define a permanent feature boundary.
- Use Python 3.13 for local development and verification. Reserve Python 3.12 and 3.14 compatibility checks for CI.

These requirements come from the project brief on 2026-09-16. They do not prescribe an agent loop, workflow engine, provider abstraction, or class hierarchy.

## Current research

| Topic | Question | State |
| --- | --- | --- |
| Harness interfaces | Where can external judgments plug in, and where is generated content required? | Initial map recorded |
| Jev API and SDK | What does the provider guarantee, and what facilities already exist? | Contract and typing findings recorded |
| Pydantic AI patterns | Which mechanisms deliver typing, composability, and robustness? | Initial map recorded |
| Real workloads | What inputs, judgments, and downstream actions occur in published examples? | Initial evidence recorded |

## Design tree

| ID | Decision | Prerequisites | State |
| --- | --- | --- | --- |
| D1 | Jev-specific interface or support for other backends | None | Jev first; other backends when needed |
| D2 | Representative user workflows for the first interfaces | Workload and harness research | Incremental priorities delegated; begin with small, high-impact uses |
| D3 | What Jevantic owns beyond individual model requests | D1, D2, provider contract | Typed composition, input/answer validation, execution and metadata in the alpha; conveniences added from demonstrated uses |
| D4 | Engineering guarantees for the first usable release | D2, D3, Pydantic AI research | Alpha guarantees and executed checks recorded; hosted compatibility checks pending |
| D5 | Integration with harness capabilities | Standalone interface validated against D2 | Concrete first guardrail plan recorded; implementation is a later integration task |

The current backend and workflow priorities permit implementation to proceed. Consequential new abstractions remain subject to evidence from complete call sites.

## Progress

- Read TypeSafe's introduction, primitive semantics, confidence documentation, and published workflows.
- Followed uses at Vercel, Every, Eventum, Near Here, and Jev Review.
- Updated Matt Pocock's skills checkout to 959a8e9f1edc3adbe2f7e3054bb6fbefa6696260.
- Recorded initial harness, Jev contract, and Pydantic AI investigations.
- Created this standalone knowledge base.
- Found that SDK responses do not preserve the static relationship between named questions and their individual answer types.
- Compared reusable typed questions, caller-owned result schemas, and callable question builders with three independent design investigations.
- Verified two offline interface probes using strict Pyright and execution. Typed handles preserve mixed answer types and selected local values; Pydantic schemas preserve named field types but need runtime checks for contradictory question metadata.
- Executed offline SDK probes confirming client ownership, cancellation propagation, configured retries, typed malformed-response errors, and gaps in semantic answer validation. No live inference request was made.
- Built an installable typed core experiment with explicit batches, SDK ownership, question-aware validation, and two complete assessment examples.
- Verified the current offline suite on Python 3.13 with full branch coverage. Strict typing includes positive call-site assertions and automated rejection of intentionally invalid callers. Earlier exploratory compatibility runs predate the current CI-only policy for other interpreters.
- Executed live checks with synthetic content. All three primitives and structured rubrics passed; omitted instructions and one-level Scores were accepted. An eleven-level Score was rejected with an explicit ten-level limit. Ambiguous answers satisfied the experimental numerical checks.
- Addressed independently reproduced review findings: contradictory Choice/Score values, tuple/list rubric mismatches, and accidental character-by-character interpretation of a string rubric.
- Addressed a second independent review: cancellation during owned-client shutdown now waits for cleanup; metadata reads the actual requested model after SDK defaults are applied.
- Curated the official cookbooks and added a short lesson and reference glossary for the API vocabulary.
- Added bounded independent-input fan-out and a document-ranking example. Public transport checks verify lazy consumption, ordering, SDK retries, cancellation, and error correlation.
- Recorded a concrete [harness integration plan](harness-integration.md) using an existing sequential input-guardrail callback, with explicit ownership, policy, accounting, durability, and verification boundaries.
- Compared the complete fixed assessment with a result-schema facade. The facade saves four helper statements and none at the existing callers, while adding declaration checking; the alpha deliberately keeps ordinary typed assessment functions.

See [candidate interfaces](interface-comparison.md), [core design](core-experiment.md), [verification plan](verification-plan.md), and [executed evidence](../verification.md). The first alpha uses typed questions; its public names and conveniences can evolve with further workflows.

## Current milestone and remaining verification

- The standalone typed core supports command-risk assessment and multi-rubric scoring as executable examples.
- Bounded fan-out now supports independent inputs, retaining typed results and caller control of concurrency.
- The result-schema comparison supports keeping ordinary assessment functions in this alpha; a compiler is not an unimplemented alpha requirement.
- The first harness integration is planned against existing guardrail callback seams.
- The repository is private at [dsfaccini/jevantic](https://github.com/dsfaccini/jevantic). The [Checks workflow](https://github.com/dsfaccini/jevantic/actions/workflows/checks.yml) owns Python 3.12/3.14 execution; local Python 3.13 and installed-wheel checks pass.

These priorities follow the agreed incremental scope. A general workflow engine, universal guard thresholds, multi-provider framework, and arbitrary generative function calling have no current requirement.

## Process references

- [Grilling](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/productivity/grilling/SKILL.md): ask decisions whose prerequisites are settled.
- [Domain modeling](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/engineering/domain-modeling/SKILL.md): maintain vocabulary and record consequential choices.

The process serves incremental discovery. It is not a requirement to specify every future feature before testing an interface.
