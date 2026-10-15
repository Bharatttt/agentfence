# Milestone 1 status

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
- [ ] Live LLM orchestration via chosen model provider or feasible local model.
- [ ] Vector retrieval and full end-to-end RAG agent loop.
- [ ] OPA/Rego integration from synopsis diagrams, if retained after scope review.
- [ ] Correct and independently verify bibliography/novelty statements.
- [ ] Document and implement properly attributed adaptations from InjecAgent/AgentDojo.
- [ ] Broader unseen and adaptive tests, multiple models/seeds and human labels.
- [ ] Review-context privacy design beyond fingerprints and controlled fixtures.
- [ ] External-tool idempotency, log tamper evidence, production authentication/rate limits.

This milestone is a gateway foundation. It does not mark the final-year project as finished or all objectives fully validated.

## Verification completed in development

- 36 automated tests passed, including a check that verifier hashes cannot be used as bearer tokens.
- Real HTTP server/client smoke test passed: authorized metadata read allowed; parameter smuggling, restricted document access and poisoned output denied.
- Ruff lint/format checks and Python dependency consistency check passed.
- JavaScript syntax check passed. Visual browser testing remains pending because the Chromium download failed in this environment.
- Docker runtime tests remain pending because Docker is unavailable in this environment.
- One dependency deprecation warning occurs in Starlette's test client; no test failure.
