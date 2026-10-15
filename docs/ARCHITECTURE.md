# Proposed architecture

Status: design proposal, not an implemented security guarantee.

## Request lifecycle

1. An agent submits a structured request to the gateway.
2. The gateway authenticates the caller, resolves configured identity and permissions, and strictly validates the tool schema.
3. A default-deny policy checks tool, operation, resource, destination, and applicable limits.
4. Denied requests never execute. Sensitive permitted requests enter an approval queue.
5. A separate trusted reviewer approves the exact canonical request. Approval is single-use and expires; policy is rechecked before execution.
6. A narrow tool adapter executes the permitted request using gateway-owned credentials.
7. An audit event records correlation ID, caller, tool, decision reason, approval reference, timestamps, and outcome, with sensitive values redacted.

## Trust boundaries

Treat the model, retrieved content, and agent-supplied arguments as untrusted. Policy configuration, reviewer identity, and tool credentials must not be writable by the agent. The agent must have neither direct protected-resource credentials nor a network or filesystem path that bypasses enforcement. A Python wrapper alone is not process isolation.

File adapters need canonical resource checks and protection against symlinks and time-of-check/time-of-use races. Outbound adapters need destination controls covering redirects and resolved addresses. Start with narrow local tools and mock outbound services, rather than unrestricted shell execution or arbitrary HTTP.

Audit logging supports traceability but is not automatically tamper-proof. Document local administrator access and log integrity limits. Fail closed when validation, policy evaluation, approval validation, or required audit persistence fails.

## Milestones

- [ ] Reconcile latest report and PPT with objectives.
- [ ] Implement strict request models and default-deny policy engine.
- [ ] Add constrained local tools and tests for boundary escapes.
- [ ] Add authenticated approval, expiry, request binding, and replay protection.
- [ ] Persist redacted audit events and execution outcomes.
- [ ] Build a local request, approval, and audit interface.
- [ ] Integrate a demonstration agent with enforced access boundaries.
- [ ] Run baseline and protected workflows; publish measured results and limitations.

## Evaluation definitions

Report successful unauthorized executions divided by attempted unauthorized actions, with scenario counts. Report blocked legitimate requests divided by legitimate requests as the false-positive rate. Report legitimate task completion separately. Measure gateway-added latency against matched baseline calls, separating human approval waiting time from automated processing. Publish environment, repetitions, policy configuration, and dataset versions. Do not describe a small hand-crafted scenario set as a comprehensive benchmark.
