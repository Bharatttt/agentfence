# Five-minute demonstration

## Before the review

Follow the README. Keep credentials private. Use the synthetic tenant-a/case-1 only. A fresh native database starts with key-1 active; after approval it remains disabled. Do not reset a database without retaining any needed evidence. For repeat demos, create a fresh dedicated `AGENTFENCE_DB` path rather than deleting an existing database.

## Presentation sequence

1. **0:00–0:45, problem and boundary:** Explain that every tool proposal is untrusted. The gateway controls tool execution independently of model text. Show the architecture.
2. **0:45–1:30, legitimate read:** Connect as analyst, select the metadata example, submit and show allow/executed plus the returned synthetic asset description.
3. **1:30–2:15, deterministic controls:** Submit parameter smuggling, then cross-tenant access. Show `schema_invalid` and `scope_mismatch`. The unwanted operations do not execute.
4. **2:15–2:50, untrusted content:** Read the poisoned document. The gateway withholds suspicious output and records `output_quarantined`. Explain this is a heuristic with blind spots.
5. **2:50–4:00, human approval:** Connect as responder, submit disable-key. Show pending and the exact typed arguments. Connect as reviewer, inspect the bound request, approve, then show executed and its reviewed/outcome events. Repeat with a new request and reject it.
6. **4:00–5:00, evaluation and limits:** Present the synthetic sample counts, attack block rate, false positives and latency. Explain the quoted training example false positive, absence of live model evidence, and pending wider evaluation.

The replay client is scripted. Do not call it an LLM agent during the demonstration. The same HTTP contract is intended for the next live agent integration.

## Target Windows Docker checks (pending execution)

After starting Docker Desktop and running `docker compose up --build -d gateway`:

```powershell
docker compose ps
$env:AGENTFENCE_TOKEN = (Get-Content runtime/credentials.json | ConvertFrom-Json).analyst
docker compose --profile demo run --rm demo-agent
```

Expected replay outcomes: allow, deny, deny, deny. Then verify that the agent container lacks protected mounts and the reviewer secret:

```powershell
docker compose --profile demo run --rm demo-agent python -c "from pathlib import Path; import os; assert not Path('/app/runtime/state/agentfence.sqlite3').exists(); assert not Path('/run/secrets/token-hashes').exists(); assert 'REVIEWER_TOKEN' not in os.environ; print('Protected state and reviewer credentials unavailable')"
```

Verify that no direct tool-execution route exists:

```powershell
docker compose --profile demo run --rm demo-agent python -c "import urllib.request, urllib.error; u='http://gateway:8000/tools/disable_access_key'; exec('try:\n urllib.request.urlopen(u)\nexcept urllib.error.HTTPError as e:\n assert e.code == 404\n print(\"No direct tool endpoint\")')"
Remove-Item Env:AGENTFENCE_TOKEN
```

Capture the actual terminal outputs for the review. A passing test proves these tested boundaries only; it is not a container-escape assessment. Do not mount the Docker socket, gateway credentials, or database into the agent container.

## Next model integration decision

For an 8 GB laptop, a remote model API can keep local memory low, but requires a chosen provider and potentially paid usage. No provider is selected and no API calls are made in milestone 1. Alternatively, test a small local model later with measured memory limits. Approval must remain in the gateway regardless of model choice.

## Missing host port mapping

If the app starts but `docker compose port gateway 8000` reports `:0`, update the
checkout and recreate the gateway with the corrected two-network configuration:

```powershell
git pull --ff-only
docker compose up --no-build -d --force-recreate gateway
docker compose port gateway 8000
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected binding: `127.0.0.1:8000`. The named state volume and credentials are
preserved. No image rebuild is needed. The gateway now has outbound connectivity;
the scripted demo client remains on the internal network.

Background: https://github.com/moby/moby/issues/44986
