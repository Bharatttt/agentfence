# OpenAI agent milestone

The bounded agent uses the OpenAI Responses API function-calling format:
https://developers.openai.com/api/docs/guides/function-calling (consulted 2026-10-15).
Its sole function is `propose_tool`. The model proposes a tool name and JSON arguments;
the gateway independently validates and authorizes them. The task and credentials come
from operator configuration, not model output. A denial or pending approval ends the run.
Review the exact pending request in the existing console. There is no automatic resume
or resubmission after approval. A successful approval executes the stored action once.

## Windows setup

Start the gateway following README.md. Configure an analyst (investigation-1) or
responder (response-1) token locally. Never give the agent a reviewer credential.
Use only synthetic demonstration data: user prompts and permitted tool results are sent
to OpenAI. Model choice must support Responses API function calling; availability depends
on your account. No default model or paid test has been selected automatically.

PowerShell (prompts keep credentials out of command history):

```powershell
$secret = Read-Host "OpenAI API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
$secret = Read-Host "AgentFence analyst token" -AsSecureString
$env:AGENTFENCE_TOKEN = [System.Net.NetworkCredential]::new('', $secret).Password
$env:OPENAI_MODEL = Read-Host "Responses-compatible model ID"
$env:AGENTFENCE_URL = 'http://127.0.0.1:8000'
# This command makes paid API calls when configured:
.\.venv\Scripts\python demo\openai_agent.py --prompt "Read metadata for asset-1."
```

Prefer the isolated agent container for the security demonstration:

```powershell
docker compose --profile llm run --build --rm llm-agent --prompt "Read metadata for asset-1."
```

For a sensitive call, use the responder token and add `--task response-1`.
Ask to disable key-1 for suspected compromise; the client should return `pending`.
Review its request ID and digest in the console. Do not rerun it to resume.
Clear credentials from the session afterward:

```powershell
Remove-Item Env:OPENAI_API_KEY, Env:AGENTFENCE_TOKEN
```

## Limits and verification

Four model turns by default, at most eight with `--turns`, 1024 output tokens per
request, finite HTTP timeouts, sequential calls, repeated-proposal detection, and no
automatic retry. These bound requests, not a precise dollar budget. A transport failure
can occur after a gateway commit: inspect the audit trail before manually retrying.
`store=false` requests no Responses storage; this is not a zero-retention guarantee.
Model-generated final text remains untrusted and is not execution evidence.

The client image contains no gateway package, SQLite volume, host mount or reviewer
credential. Its second network allows provider access; it is **not** a network-level
destination allowlist. The client fixes its provider URL and exposes no shell or arbitrary
network tool. A compromised client/container runtime and host administrator are outside
this demo's enforcement claim. Native execution alone is not OS isolation.

Offline tests simulate provider responses while using the real FastAPI application,
SQLite store and policies: valid result round-trip, cross-scope access, unknown tools,
argument smuggling, malicious tool output, unauthorized export, approval pause, malformed
and parallel proposals, repeated calls, turn budget, reviewer misuse and wrong-task rejection.
These establish integration behavior, not live model accuracy or resistance statistics.
Live provider and Windows Docker tests remain pending. Existing synthetic evaluation
results are unchanged and must not be described as live LLM results.

## Preferred Gemini provider

The owner selected Gemini after this integration was added. Use [GEMINI.md](GEMINI.md)
for local credentials and the `gemini-agent` Docker profile. The OpenAI client remains
optional; an OpenAI API key is not needed to use Gemini.
