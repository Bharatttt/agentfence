# Objectives and acceptance evidence

Authoritative source: **AgentFence.pptx**, slide 6 (Zeroth Review, 09-10-2026). Supporting source: **AgentFence_Major_Project_Synopsis(1).docx**, objectives and methodology, including architecture figures. Source documents were reviewed on 2026-10-15. They are not republished here because they contain student identifiers and signatures.

## Exact PPT objectives

1. To design and develop a local security gateway that checks tool requests before execution and controls LLM agents’ access to authorized tools.
2. To validate tool-call arguments, enforce defined permissions, and reject invalid or out-of-scope requests to reduce unauthorized access and actions.
3. To implement approval for sensitive operations and maintain an audit trail of tool requests, approval decisions, and execution outcomes.
4. To evaluate AgentFence’s ability to block malicious requests while measuring false positives and the additional latency introduced by security checks.

## Traceability for milestone 1

| Objective | Implementation | Verification and demonstration | Remaining evidence |
| --- | --- | --- | --- |
| 1 | `app.py` authenticated gateway; `gateway.py` private mock tool dispatcher; separate `demo/replay.py` HTTP client | `test_authorization_and_no_direct_route`; read asset in console | Live LLM integration and Docker isolation verification on target Windows machine |
| 2 | Strict Pydantic models, role allowlists, assigned immutable task scope, tenant/case and resource ownership checks, destination allowlist | Strict argument, cross-scope, task-assignment, identity-forgery, and destination tests; console attack presets | Broader unseen/adaptive cases; optional OPA policy implementation |
| 3 | Transactional SQLite approvals and mock changes; exact-request digest, expiry, single consumption, policy recheck; evidence fingerprints | Pause, approve, reject, expiry, replay, concurrency, restart, and storage-failure tests; reviewer console | External tool failure semantics, stronger log integrity, fuller review context design |
| 4 | `evaluation/run.py`, 14 original fixtures, separate unguarded mock baseline, persisted measured results | 20 repetitions per fixture, explicit false-positive example, paired overhead | Live model trials; properly attributed benchmark adaptations; target-machine timings |

## Reconciled source differences

- **Resolved by the project owner:** reject invalid/smuggled calls. PPT specifies allow, deny, and sensitive approval; synopsis additionally lists sanitize. Sanitization is excluded from milestone 1.
- Synopsis lists seven detailed objectives; these expand the PPT's four and add heuristic inspection, implemented for supplied input/context and actual mock outputs.
- Synopsis diagrams name OPA/Rego; PPT describes a rules engine. Python rules implement the first milestone; OPA is not yet implemented.
- Synopsis proposes LangGraph or equivalent, a vector store, and Streamlit or a terminal. Current client is explicitly scripted replay; retrieval is a scoped keyword search; the lightweight browser console is served by FastAPI. Live LLM orchestration and vector retrieval remain pending, rather than silently being counted as completed.
- The synopsis calls the audit record immutable in a diagram. SQLite records in this milestone are transactional but remain modifiable by a trusted host/database administrator. No immutability claim is made.
- Some synopsis literature-table references appear to be domain placeholders or mismatched with their stated contributions. Bibliographic correction and independent novelty validation are pending. The implementation does not rely on those novelty claims.

The contribution remains per-tool-call enforcement. Adaptive attack generation and comparing unrelated prompt guardrails are not this project's primary deliverable.
