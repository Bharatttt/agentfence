# Implementation status

## Implemented

- [x] Read PPT and synopsis; preserve exact slide-6 objectives.
- [x] Resolve sanitize conflict with owner: reject invalid calls.
- [x] FastAPI gateway and strict typed contracts.
- [x] Roles, immutable task assignments, tenant/case/resource scope and destination rules.
- [x] Basic heuristics for inputs, context, prior outputs, and actual read output.
- [x] Approval queue with exact request binding, expiry, rejection, replay protection and policy recheck.
- [x] Transactional mock changes and evidence fingerprints in SQLite.
- [x] Browser console and separate unprivileged HTTP replay client.
- [x] Automated tests, measured synthetic evaluation, setup and viva notes.
- [x] Docker/Compose isolation configuration (runtime verification pending).

## Not yet complete

- [ ] Target Windows Docker build, runtime and isolation checks.
- [x] Bounded OpenAI Responses client with gateway-only proposals and offline integration tests.
- [ ] Live OpenAI verification with an explicitly selected model and locally configured key.
- [ ] Vector retrieval and full end-to-end RAG agent loop.
- [ ] OPA/Rego integration from synopsis diagrams, if retained after scope review.
- [ ] Correct and independently verify bibliography/novelty statements.
- [ ] Document and implement properly attributed adaptations from InjecAgent/AgentDojo.
- [ ] Broader unseen and adaptive tests, multiple models/seeds and human labels.
- [ ] Review-context privacy design beyond fingerprints and controlled fixtures.
- [ ] External-tool idempotency, log tamper evidence, production authentication/rate limits.

The gateway foundation and offline-tested model integration are implemented. It does not mark the final-year project as finished or all objectives fully validated.

## Verification completed in development

- 50 automated tests passed, including verifier-hash authentication checks and 14 agent integration cases.
- Real HTTP server/client smoke test passed: authorized metadata read allowed; parameter smuggling, restricted document access and poisoned output denied.
- Foundation Ruff lint/format and dependency consistency checks passed. Ruff crashed during the integration milestone; new client syntax and behavior were checked through Python tests.
- JavaScript syntax check passed. Visual browser testing remains pending because the Chromium download failed in this environment.
- Docker runtime tests remain pending because Docker is unavailable in this environment.
- One dependency deprecation warning occurs in Starlette's test client; no test failure.
