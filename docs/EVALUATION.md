# Milestone 1 evaluation

## Method and provenance

Run date: 2026-10-15. Environment: Linux x86_64, Python 3.12.14, Pydantic 2.14.1. Results are from the development environment, not the target Windows laptop.

14 original hand-authored fixtures were each replayed 20 times: 9 policy-violating cases and 5 benign cases, including a deliberately challenging security-training quotation. Repetition measures timing variation; **there are only 14 distinct cases**, not 280 independent attacks. These cases have not been sourced from or scored by official InjecAgent/AgentDojo harnesses. No LLM is involved.

Each fixture receives separate fresh SQLite stores for baseline and protected execution, identical synthetic resources and the same proposal payload. Baseline deliberately omits authorization, schema, tenant and approval controls and operates only on mock data. Exports insert database records and never send network traffic. The harness checks completion status against fixture labels; it does not measure real data exfiltration or general attacker success.

## Measured results

| Metric | Value |
| --- | --- |
| Policy-violating attempts | 180 (9 unique fixtures) |
| Benign attempts | 100 (5 unique fixtures) |
| Baseline execution of policy-violating proposals | 100% |
| Gateway block rate on policy-violating proposals | 100% |
| Gateway unauthorized execution rate | 0% |
| Benign false-positive rate | 20% |
| Benign completion rate | 80% |
| Approval frequency | 7.14% |
| Median policy processing time | 0.202 ms |
| P95 policy processing time | 0.386 ms |
| Median paired allowed-call overhead | 0.229 ms |

## Definitions

- Block rate: denied attack-labeled proposals / all attack-labeled proposals. A pending approval alone is not counted as a block.
- Unauthorized execution: executed attack-labeled proposals / attack-labeled proposals.
- False positives: denied benign proposals / all benign proposals. Approval-required benign proposals are not false positives.
- Benign completion: executed benign proposals, including accepted simulated review / benign proposals. The harness automatically approves expected benign sensitive calls using the test reviewer; no human waiting time is modeled.
- Approval frequency: proposals initially requiring approval / all proposals.
- Policy processing time: in-process gateway time from submission through validation, permission checks, heuristic inspection and resource-scope checks. Includes opening a transaction and initial received-event insert; excludes tool execution, output inspection, final audit commit, HTTP and human review.
- Paired allowed-call overhead: protected submission elapsed time minus direct baseline elapsed time for the same allowed benign fixture. Includes tool work and audit commit. It is not a pure authorization microbenchmark or a target-device latency guarantee.

## Known failure and interpretation

The benign security-training quotation is denied because it contains “ignore previous instructions.” All 20 repetitions of that benign fixture are false positives. This reveals the simplistic heuristic's inability to distinguish quoted educational text from operative instructions. The small fixture set is intentionally transparent; the 100% attack block rate should not be generalized to unseen or adaptive attacks.

Policy-based checks still deny unauthorized scope and destinations without suspicious keywords. However, harmful actions that remain inside a legitimately permitted task can still pass. Broader live-model and task-level testing is necessary.

## Reproduce

Run `python -m evaluation.run --repetitions 20 --output evaluation/results-local.json` from the repository root with its dependencies installed. The harness uses temporary mock databases and does not change a running demo's state. Raw committed observations are in `evaluation/results.json`.
