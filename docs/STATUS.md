# Implementation status

## Implemented

- [x] Read PPT and synopsis; map the first three slide-6 objectives to the revised current-semester scope.
- [x] Resolve sanitize conflict with owner: reject invalid calls.
- [x] FastAPI gateway and strict typed contracts.
- [x] Roles, immutable task assignments, tenant/case/resource scope and destination rules.
- [x] Basic heuristics for inputs, context, prior outputs, and actual read output.
- [x] Approval queue with exact request binding, expiry, rejection, replay protection and policy recheck.
- [x] Transactional mock changes and evidence fingerprints in SQLite.
- [x] Browser console and separate unprivileged HTTP replay client.
- [x] Functional automated tests, setup and viva notes.
- [x] Docker/Compose isolation configuration (runtime verification pending).

## Not yet complete

- [x] Target Windows gateway and Gemini CLI build/runtime demonstrations.
- [ ] Target Windows isolation checks and first new web-portal run.
- [x] Bounded OpenAI client and Gemini compatibility adapter with gateway-only proposals and offline integration tests.
- [x] Live Gemini allowed read, unauthorized resource denial, sensitive approval/execution and rejection (2026-10-17).
- [x] Password login, chat portal, reviewer screen and isolated web runner with offline integration tests.
- [ ] Live web-portal verification; optional OpenAI verification.
- [ ] Vector retrieval and full end-to-end RAG agent loop.
- [ ] OPA/Rego integration from synopsis diagrams, if retained after scope review.
- [ ] Correct and independently verify bibliography/novelty statements.
- [ ] Review-context privacy design beyond fingerprints and controlled fixtures.
- [ ] External-tool idempotency, log tamper evidence, production authentication/rate limits.

The gateway foundation and offline-tested model integration are implemented. It does not mark the final-year project as finished or all objectives fully validated.

## Verification completed in development

- 75 automated tests passed, including verifier-hash checks, shared agent integration and Gemini adapter cases.
- Real HTTP server/client smoke test passed: authorized metadata read allowed; parameter smuggling, restricted document access and poisoned output denied.
- Foundation Ruff lint/format and dependency consistency checks passed. Ruff crashed during the integration milestone; new client syntax and behavior were checked through Python tests.
- JavaScript syntax check passed. Visual browser testing remains pending because the Chromium download failed in this environment.
- Docker runtime tests remain pending because Docker is unavailable in this environment.
- One dependency deprecation warning occurs in Starlette's test client; no test failure.

## Scope revision (2026-10-17)

The owner removed the fourth objective from this semester. The standalone evaluation harness, synthetic baseline, scenarios, result files and evaluation report have been removed from the current checkout. Formal evaluation is deferred to next semester. Earlier work remains recoverable from Git history. Functional and security regression tests remain necessary evidence for the first three objectives.
