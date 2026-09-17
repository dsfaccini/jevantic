# Jevantic discovery

Updated: 2026-09-16

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
| D1 | Jev-specific interface or support for other backends | None | Asked; awaiting answer |
| D2 | Representative user workflows for the first interfaces | Workload and harness research | Asked; awaiting answer |
| D3 | What Jevantic owns beyond individual model requests | D1, D2, provider contract | Open |
| D4 | Engineering guarantees for the first usable release | D2, D3, Pydantic AI research | Open |
| D5 | Integration with harness capabilities | Standalone interface validated against D2 | Later |

Research can proceed while a product decision is unanswered.

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

See [candidate interfaces](interface-comparison.md), [verification plan](verification-plan.md), and [executed probe details](../../experiments/README.md). These are design evidence; no production package has been implemented.

## Current recommendations awaiting input

- D1: focus on Jev initially while preserving room for a second backend where it proves useful.
- D2: use one live agent guard and one batch scorer to exercise distinct calling patterns.
- Interface experiment: typed questions as the fundamental composition mechanism, with one small Pydantic schema facade to compare on the selected workflows. Ordinary Python functions can build questions without a decorator framework.

These recommendations have been presented for discussion. None is an accepted scope decision.

Further reversible experiments use D1 and D2's recommendations as working assumptions while answers are pending. They do not establish the production scope or public interface.

## Process references

- [Grilling](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/productivity/grilling/SKILL.md): ask decisions whose prerequisites are settled.
- [Domain modeling](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/engineering/domain-modeling/SKILL.md): maintain vocabulary and record consequential choices.

The process serves incremental discovery. It is not a requirement to specify every future feature before testing an interface.
