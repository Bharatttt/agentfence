# Gemini setup on Windows

Gemini is the owner's preferred provider. The adapter uses Google's documented
Chat Completions compatibility endpoint with the same gateway-only loop as the
OpenAI client. No OpenAI account or key is needed for this profile.

References (consulted 2026-10-15):
- https://ai.google.dev/gemini-api/docs/openai
- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/billing

## First run (PowerShell)

Install Git and Python 3.12. Docker Desktop should be running in Linux-container mode.
For a first checkout:

```powershell
git clone https://github.com/Bharatttt/agentfence.git
cd agentfence
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup.py
```

For an existing checkout, use `git pull --ff-only` if your working files are clean,
then install dependencies and run setup as above. Setup preserves existing credentials.

Start the gateway and set this session's credentials:

```powershell
docker compose up --build -d gateway
$secret = Read-Host "Paste Gemini API key locally (hidden)" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
$env:GEMINI_MODEL = Read-Host "Exact function-calling model ID available in your AI Studio free tier"
$env:AGENTFENCE_TOKEN = (Get-Content runtime/credentials.json | ConvertFrom-Json).analyst
docker compose --profile gemini run --build --rm gemini-agent --prompt "Read metadata for asset-1."
```

This last command contacts Google. Check the project's Plan in AI Studio before running;
start with Free Tier and leave paid billing disabled. Quotas and eligible models vary.
Use synthetic prompts only: prompts and permitted gateway results go to Google, and
free-tier data handling differs from paid service terms. No key is included in model
messages, gateway proposals, audit records or the image. Do not paste keys into chat.
The key is passed in a header, never a URL. Container environment credentials remain
visible to the trusted Docker host administrator; this is not protection from the host.

Open http://127.0.0.1:8000 and connect with the analyst token from the local
`runtime/credentials.json` file to inspect requests. A successful read has an `allow`
event and a final `completed` status. Final model prose is untrusted; use gateway events
and audit records as evidence. `model_incomplete` can indicate an output/thinking limit;
it does not mean the task succeeded. There is no automatic retry.

## Sensitive-action demonstration

```powershell
$env:AGENTFENCE_TOKEN = (Get-Content runtime/credentials.json | ConvertFrom-Json).responder
docker compose --profile gemini run --rm gemini-agent --task response-1 --prompt "Disable key-1 because of suspected compromise."
```

The agent should stop with `pending`. Open the console with the reviewer token locally,
inspect the exact request, and approve or reject it. The reviewer credential must never
be given to the agent. Approval executes the stored request once; automatic agent
resumption is not implemented. Do not rerun the same sensitive prompt to resume.

Clear session credentials when finished:

```powershell
Remove-Item Env:GEMINI_API_KEY, Env:AGENTFENCE_TOKEN
Remove-Variable secret
```

## Troubleshooting

- 401: verify the local Gemini key and AgentFence token.
- 403: inspect project/key permissions and assigned task access.
- 404: verify the exact model ID and availability in your account.
- 429: inspect AI Studio quota; wait for the limit to reset. Do not enable paid billing
  merely to bypass this error without deciding on a budget.
- Connection failure: check Docker Desktop, `docker compose ps` and `docker compose logs gateway`.
- Empty/malformed/incomplete model output: execution stops; inspect existing request
  records before retrying, since an HTTP failure can occur after an execution commits.

## Verification and boundaries

Provider responses are simulated in automated tests while real gateway policies and
SQLite state are exercised. Tests cover read/result round-trip with signature metadata,
blocked resource access, extra arguments, unknown tools, poisoned output, unauthorized
destinations, approval pause, incomplete responses, parallel proposals and quota failure.
Existing shared-loop tests cover duplicate proposals and finite turn budgets.

The agent image has no protected volume, tool implementation, gateway module or reviewer
credential. It can contact the gateway and the internet for model inference; egress is
not filtered by a network destination allowlist. The provider origin is fixed in trusted
code, and no arbitrary network function or shell is offered to the model. Native mode
alone does not provide OS isolation. A compromised host/runtime is outside the claim.

Live Gemini and Windows Docker checks still require the owner's machine. No Gemini
key has been received or used in development, and no live results are claimed.

### Package download timeout during Docker build

The Dockerfiles allow a 180-second socket timeout and ten connection retries for
package installation. If PyPI downloads still time out, check the connection and rerun
`docker compose build gateway`, then `docker compose up -d gateway`. Existing successful
build layers can be reused. The pip update notice is informational.
