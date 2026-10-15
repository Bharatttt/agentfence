# AgentFence

**A Zero Trust Security Gateway for Secure LLM Agent Tool Invocation**

AgentFence checks structured tool requests before execution using typed validation, role and task permissions, scope checks, heuristic risk signals, approval for sensitive actions, and SQLite audit records.

**Status: milestone 1, a working mock-tool gateway.** The console, HTTP replay client, approval lifecycle, and synthetic evaluation work. A live LLM agent, vector RAG, OPA integration, and target-machine Docker verification remain pending. This is a local research prototype, not a production security product.

## Start on Windows (PowerShell)

Install Python 3.12 if it is not already available, then:

```powershell
git clone https://github.com/Bharatttt/agentfence.git
cd agentfence
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup.py
.\.venv\Scripts\python.exe -m uvicorn agentfence.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000**. Open the generated `runtime/credentials.json` locally and copy the analyst token into the console. It is cleared from the input after connection and kept only in page memory. Refreshing the page clears the session. Do not paste credentials into chat or commit them.

Select **Read asset metadata**, submit, then try **Parameter smuggling** and **Cross-tenant request**. Use the responder token to request disabling the simulated key. Switch to the reviewer token to approve or reject the exact action and inspect its audit evidence.

## Docker alternative

Run `scripts/setup.py` first. Docker Desktop must use Linux containers.

```powershell
docker compose up --build -d gateway
docker compose ps
```

The UI is at the same loopback address. The gateway's mock database persists in a named volume. Docker and native mode use different databases. To run the separate scripted client:

```powershell
$env:AGENTFENCE_TOKEN = (Get-Content runtime/credentials.json | ConvertFrom-Json).analyst
docker compose --profile demo run --rm demo-agent
Remove-Item Env:AGENTFENCE_TOKEN
```

The application containers have memory limits of 512 MB and 128 MB respectively; these limits exclude Docker Desktop/WSL overhead and are not measured usage claims. No local LLM is loaded. Docker execution still needs verification on the target Windows laptop.

## Tests and reproducible evaluation

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/smoke.py
.\.venv\Scripts\python.exe -m evaluation.run --repetitions 20 --output evaluation/results-local.json
```

The committed evaluation uses 14 original synthetic proposal fixtures, repeated 20 times. It includes a known false positive. These are not official InjecAgent/AgentDojo benchmark runs, nor measurements of an LLM being successfully manipulated.

## Project documentation

- [Exact PPT objectives and evidence mapping](docs/OBJECTIVES.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Demonstration and Windows isolation checks](docs/DEMO.md)
- [Evaluation definitions and measured results](docs/EVALUATION.md)
- [Viva preparation](docs/VIVA.md)
- [Progress and remaining work](docs/STATUS.md)

Only simulated resources are used. The system reduces tool-execution risk within its configured boundaries and does not eliminate prompt injection. Secrets and local runtime files are excluded through `.gitignore` and `.dockerignore`.

## OpenAI agent integration

The next milestone adds a bounded model client with gateway-only execution and an
isolated Docker profile. See [agent setup and limitations](docs/AGENT.md). Provider calls
require locally configured credentials and an explicit model; no paid calls have been
performed. Run `python -m pytest` for offline integration coverage.
