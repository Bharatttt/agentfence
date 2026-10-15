# AgentFence objectives

Status: planning foundation; implementation and evaluation are not yet complete. These objectives reflect the agreed conversation scope and must be checked against the team's latest report and PPT before scope sign-off.

| Objective | Acceptance evidence |
| --- | --- |
| Intercept agent tool calls before execution | Integration tests show every protected tool request passes through the gateway; direct tool access is unavailable to the agent. |
| Validate arguments and enforce least privilege | Reject malformed arguments, unknown tools, disallowed operations, restricted resources, and unauthorized destinations. |
| Require approval for sensitive actions and record decisions | Approval is bound to the exact immutable request, expires, is single-use, and cannot authorize changed arguments. Audit records capture decisions and execution outcomes with secrets redacted. |
| Evaluate effectiveness and overhead | Reproducible malicious and legitimate workflows, baseline comparison, and measured results for unauthorized-action prevention, task completion, false positives, approval frequency, and latency. |

## Scope

Build a local policy-enforced tool execution gateway. Adaptive attack generation and cross-domain ranking of prompt guardrails are outside the primary contribution. Prompt injection is a threat scenario, not a claim of universal detection or prevention.

## Demonstrations

1. Permit an authorized read from the allowed workspace.
2. Reject a restricted file request and path escape.
3. Reject invalid arguments and unknown tools.
4. Reject an unauthorized outbound destination using a controlled mock service.
5. Hold a protected modification for approval; reject denied, expired, replayed, or modified requests.
6. Record decisions and outcomes without exposing secrets.

No benchmark scores or implementation claims should be published before verification.
