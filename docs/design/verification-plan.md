# Requirements and verification

Updated: 2026-09-16. This record separates the requested outcome from the evidence needed to claim it. Proposed engineering checks are not yet an accepted release specification.

## Completion evidence

| Requested outcome | Evidence that would establish it | Current evidence |
| --- | --- | --- |
| Standalone Python library named Jevantic | Installable package, documented public interface, successful use outside the repository | Research repository only |
| Elegant, powerful typed interfaces | Representative complete call sites; strict static fixtures; validated results retaining question and option types | Offline typing probes pass; interface remains a proposal |
| Flexible fundamental layer | Direct composition of supported Jev questions and state, including mixed and runtime-built requests | Provider contract researched; generic handle mechanism demonstrated offline |
| Convenient recurring uses | Selected real workflows implemented and documented through the public interface | Workload evidence recorded; first proving workflows await selection |
| Robustness comparable to the relevant Pydantic AI mechanisms | Public behavior, failure-path, lifecycle, typing, and documentation checks with an explicit coverage bar | Source reference recorded; no library runtime or test suite yet |
| Maintainable classes and architecture | A small coherent interface, justified ownership and seams, independent review of implementation against requirements | Three candidates investigated; comparison and preliminary recommendation recorded |
| Persistent curated knowledge with dedicated subagents | Source-linked records that distinguish facts, claims, proposals, and executed results | Initial research, interface findings, and executed probe evidence recorded |
| Incremental shared understanding | Consequential choices recorded with their accepted rationale | Backend scope and first workflows remain unanswered |
| Plan downstream harness capabilities after standalone validation | Capability mapping grounded in verified standalone behavior, with lifecycle and policy responsibilities specified | Initial interface map recorded; implementation and integration design remain later work |

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

No transport implementation, retry policy, telemetry dependency, batch convenience, or supported-version matrix has been chosen by listing these concerns.

## Unresolved provider evidence

- Resolve documented versus encoded differences around omitted instructions and the minimum number of Score levels.
- Establish numeric tolerance from real responses and the provider contract; do not invent normalization behavior that hides malformed data.
- Verify SDK response handling, cancellation, injected-client ownership, and retry behavior through executable probes before relying on those mechanisms.
- Distinguish schema conformance from judgment accuracy and calibration. Library tests cannot establish model quality in every application domain.

Source: [Jev API contract](../research/jev-api-contract.md).
