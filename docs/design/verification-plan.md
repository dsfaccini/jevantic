# Requirements and verification

Updated: 2026-09-17 UTC. This record separates the full requested outcome from the current alpha and its executed evidence.

## Completion evidence

| Requested outcome | Evidence that would establish it | Current evidence |
| --- | --- | --- |
| Standalone Python library named Jevantic | Installable package, documented public interface, successful use outside the repository | Alpha wheel and source distribution build; installed wheel passes the complete behavioral suite and 100% branch coverage |
| Elegant, powerful typed interfaces | Representative complete call sites; strict static fixtures; validated results retaining question and option types | Core preserves literal, enum, and local object types; positive and negative static fixtures pass; conveniences remain incremental |
| Flexible fundamental layer | Direct composition of supported Jev questions and state, including mixed and runtime-built requests | Three primitives, runtime options, mixed batches, and direct SDK encode/decode exercised |
| Convenient recurring uses | Recurring workflows implemented and documented through the public interface | Command-risk and multi-rubric examples work offline and against Jev; bounded fan-out and document ranking pass offline; result-schema compiler deliberately omitted after a complete-call-site comparison |
| Robustness comparable to the relevant Pydantic AI mechanisms | Public behavior, failure-path, lifecycle, typing, and documentation checks with an explicit coverage bar | Core and capability tests pass with 100% branch coverage locally and from an installed wheel; the [verification record](../verification.md) distinguishes current evidence from historical hosted checks |
| Maintainable classes and architecture | A small coherent interface, justified ownership and seams, independent review of implementation against requirements | Independent review findings in core validation, ownership, and capability boundaries were addressed with public regression tests; SDK owns transport/retries, core owns typed composition and semantic validation |
| Persistent curated knowledge with dedicated subagents | Source-linked records that distinguish facts, claims, proposals, and executed results | Initial research, interface findings, and executed probe evidence recorded |
| Incremental shared understanding | Consequential choices recorded with their accepted rationale | Jev-first and incremental high-impact priorities agreed; Python scope recorded; vocabulary lesson and cookbook patterns curated |
| Add optional Pydantic AI capabilities after standalone validation | Public-hook behavior, evaluator lifetime, explicit policy, and separate Jev accounting | Input and output guardrails pass public agent, streaming, durability, and configuration checks on Pydantic AI 2.38.0 and 2.44.0; [capability design](pydantic-ai-capabilities.md) records their boundaries |

## Proposed engineering checks

These checks translate the [Pydantic AI reference](../research/pydantic-ai-patterns.md) into Jev-related obligations. The exact release scope belongs to decision D4 in [discovery](discovery.md).

| Surface | Behavior to establish |
| --- | --- |
| Question definitions | Valid names and criteria; local rejection of unsupported or inconsistent definitions; all supported primitive semantics available |
| State | Explicit accepted forms, serialization behavior, and useful errors before I/O |
| Results | Correct answer names and kinds; configured choices and rubric levels; finite bounded probabilities and confidence; fractional scores retained; documented distribution tolerance |
| Static typing | Each question preserves its answer type; choice values preserve useful caller types; invalid caller code fails checking; dynamic values are not presented as compile-time literals |
| Execution | One shared-state batch has explicit request semantics; fan-out has explicit ordering, concurrency, and failure behavior; dependent stages remain visible |
| Resource ownership | Created and borrowed clients have deliberate close behavior; cancellation cleans up owned work without closing caller-owned resources unexpectedly |
| Failures and retries | Useful provider errors and request identifiers survive; one layer owns transport retries; malformed success payloads do not become plausible answers |
| Accounting | Requested and returned model identities remain distinguishable; usage reflects actual requests; accounting rules cover failures and retries where observable |
| Testability | Deterministic provider responses exercise the public validation path; opt-in live checks establish the provider contract without becoming default test dependencies |
| Observability | Clear request/error events and an explicit content-capture policy; secrets and application state do not enter logs accidentally |
| Packaging and docs | Typed installed package, supported-version checks, executable examples, and documentation of semantic and lifecycle limits |

The core reuses SDK transport and retries and provides explicit shared-state batches. Optional capabilities emit typed decision events without request content; the package configures no telemetry exporter. Python compatibility is configured in CI. Further execution conveniences and integration behavior must define their own guarantees rather than inherit them from this list.

## Unresolved provider evidence

- Live checks resolved the observed acceptance of omitted instructions and one-level `Score` questions, plus the ten-level maximum. They describe the tested endpoint/model, not an immutable future guarantee.
- Live responses satisfy the current numeric checks; tolerance remains an explicit experimental policy, with no normalization. Broader numerical edge cases still need release-level evidence.
- Offline probes verify SDK response handling, cancellation propagation, injected-client closure, and configured retries. Successful real requests are recorded; provider-side cancellation and adverse network cleanup remain unverified.
- Distinguish schema conformance from judgment accuracy and calibration. Library tests cannot establish model quality in every application domain.

Source: [Jev API contract](../research/jev-api-contract.md).
