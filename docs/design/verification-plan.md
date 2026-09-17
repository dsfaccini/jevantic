# Requirements and verification

Updated: 2026-09-17 UTC. This record separates the full requested outcome from the current alpha and its executed evidence.

## Completion evidence

| Requested outcome | Evidence that would establish it | Current evidence |
| --- | --- | --- |
| Standalone Python library named Jevantic | Installable package, documented public interface, successful use outside the repository | Alpha wheel and source distribution build; installed wheel passes the behavioral suite and coverage; no publication |
| Elegant, powerful typed interfaces | Representative complete call sites; strict static fixtures; validated results retaining question and option types | Core preserves literal, enum, and local object types; positive and negative static fixtures pass; conveniences remain incremental |
| Flexible fundamental layer | Direct composition of supported Jev questions and state, including mixed and runtime-built requests | Three primitives, runtime options, mixed batches, and direct SDK encode/decode exercised |
| Convenient recurring uses | Recurring workflows implemented and documented through the public interface | Command-risk and multi-rubric examples work offline and against Jev; bounded fan-out and document ranking pass offline; schema-facade value still under comparison |
| Robustness comparable to the relevant Pydantic AI mechanisms | Public behavior, failure-path, lifecycle, typing, and documentation checks with an explicit coverage bar | Core failure paths and ownership pass with 100% branch coverage on Python 3.13; configured Python 3.12/3.14 CI remains unrun |
| Maintainable classes and architecture | A small coherent interface, justified ownership and seams, independent review of implementation against requirements | Two independent review passes reproduced six defects, addressed with regressions; SDK owns transport/retries, core owns typed composition and semantic validation |
| Persistent curated knowledge with dedicated subagents | Source-linked records that distinguish facts, claims, proposals, and executed results | Initial research, interface findings, and executed probe evidence recorded |
| Incremental shared understanding | Consequential choices recorded with their accepted rationale | Jev-first and incremental high-impact priorities agreed; Python scope recorded; vocabulary lesson and cookbook patterns curated |
| Plan downstream harness capabilities after standalone validation | Capability mapping grounded in verified standalone behavior, with lifecycle and policy responsibilities specified | [Concrete guardrail integration plan](harness-integration.md) recorded, with subsequent capability candidates and explicit unexecuted integration tests |

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

The current package reuses SDK transport and retries, provides explicit shared-state batches, and adds no telemetry. Python compatibility is configured in CI. Further execution conveniences and integration behavior must define their own guarantees rather than inherit them from this list.

## Unresolved provider evidence

- Live checks resolved the observed acceptance of omitted instructions and one-level Scores, plus the ten-level maximum. They describe the tested endpoint/model, not an immutable future guarantee.
- Live responses satisfy the current numeric checks; tolerance remains an explicit experimental policy, with no normalization. Broader numerical edge cases still need release-level evidence.
- Offline probes verify SDK response handling, cancellation propagation, injected-client closure, and configured retries. Successful real requests are recorded; provider-side cancellation and adverse network cleanup remain unverified.
- Distinguish schema conformance from judgment accuracy and calibration. Library tests cannot establish model quality in every application domain.

Source: [Jev API contract](../research/jev-api-contract.md).
