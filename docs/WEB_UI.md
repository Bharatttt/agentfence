# AgentFence workspace

The optional web workspace lets you sign in, type a prompt and review actions without
copying bearer tokens or running an agent command for every task. The current scope
is the first three objectives; formal evaluation remains deferred.

## One-time Windows setup

From your existing repository in PowerShell, with Docker Desktop running:

```powershell
git pull --ff-only
py -3.9 scripts/setup_ui.py
docker compose --profile ui up --build -d portal
```

The setup script asks you to choose a different password (at least 12 characters)
for each username: `analyst`, `responder`, `reviewer`. Then paste your Gemini key
at the hidden prompt and press Enter to accept the previously demonstrated
`gemini-3.5-flash-lite` model, or enter a model available to your account.
These are local project passwords, not Google account passwords. Nothing is sent
to Gemini during setup. Passwords are stored as salted scrypt verifiers.

Open **http://127.0.0.1:8001**. Use this exact address (the origin is restricted).
Sign in with a username and the password you chose. The original technical console
at port 8000 remains available but is not required for this workflow.

The script reads existing gateway credentials automatically and saves private local
configuration under `runtime/`, which is excluded from Git and Docker build contexts.
The API key is saved on your computer, not in the browser or image. Protect your
Windows user account and this folder; a trusted host administrator can read the files.
On POSIX, the directory is mode 0700; mounted config files are readable by the
non-root service. On Windows, filesystem ACLs determine host protection.
Setup preserves existing configuration. If interrupted with only one config file
created, it stops and asks for recovery rather than replacing existing secrets.

If Docker encounters the previously observed missing-snapshot error, restart Docker
Desktop and rebuild. Do not reset Docker data or delete volumes.

## Subsequent demonstrations

Start Docker Desktop, then run once:

```powershell
cd "C:\Users\BHARAT MEHARWADE\agentfence"
docker compose --profile ui up -d portal
```

Open the workspace and sign in. No environment variables, token copying or per-prompt
PowerShell commands are needed. Internet and Gemini quota are required for chat;
reviewing existing requests and audit records does not call Gemini.

## Demonstrate the three objectives

1. Sign in as **analyst**. Select **Read an allowed asset**, then **Run task**.
   Expect an executed gateway card if Gemini proposes the authorized read.
2. Select **Try restricted access**, then run it. Expect blocked/resource_not_in_scope
   if the model proposes the call. A model refusal without tool events is not gateway
   enforcement. The activity screen is the evidence source for stored requests.
3. Sign out and sign in as **responder**. Select **Request a sensitive action** and
   run it. Expect Needs approval. No reviewer credential is sent to the agent.
4. Sign out and sign in as **reviewer** within five minutes. Open the pending action,
   inspect its exact arguments, click **Approve action**, and confirm **Approve & execute**.
   Inspect Activity and its audit trail. Repeat with a new request and reject it.

The reviewer login replaces the current browser session across tabs. To keep an agent
and reviewer open simultaneously, use separate browser profiles or a private window.
The prompt examples fill the composer; they do not send a paid/provider request until
Run task is clicked. Each prompt starts an independent run (up to four model requests);
this is a chat-shaped task interface, not persistent conversational memory.
Approval executes the stored action once but does not resume the model conversation.
An already-disabled demo key stays disabled; rejecting a new request does not undo
an earlier approved action.

## Architecture and security

Browser -> trusted portal -> isolated chat runner -> gateway -> mock tools.
Reviewer browser -> trusted portal -> gateway review API.

- The portal holds role credentials and password verifiers. It is explicitly trusted.
  It chooses role credentials and task IDs from the authenticated session; arbitrary
  browser role, token, task or URL fields are rejected.
- The chat runner has the Gemini key and a portal-to-runner shared secret. It receives
  only the current analyst/responder credential. It has no reviewer secret, portal
  config, tool code, protected database, Docker socket or gateway state mount.
- The runner endpoint has no host port and requires the shared service secret. One
  task runs at a time to limit resource/API use. It has fixed upstream destinations,
  four-turn limits, finite timeouts, and no automatic retries.
- The existing gateway remains the independent authorization/execution boundary.
  Portal approval calls forward the exact request digest; policy, expiry and single-use
  checks remain in the gateway. Reviewer accounts cannot run chat; other roles cannot
  use the approval or audit APIs.
- Sessions are opaque, server-side and expire after eight hours. Cookies are HttpOnly,
  SameSite=Strict and scoped to the local host. Local HTTP is loopback-only; HTTPS
  configurations set Secure cookies. Restarting the portal invalidates sessions.
- POST requests require the configured Origin and a custom same-origin header.
  Host checks mitigate browser DNS rebinding; no CORS access is granted. Login attempts
  are throttled to five per peer per minute. Request bodies are bounded.
- No secrets are in browser localStorage. Provider text and results are rendered with
  textContent, not HTML. Validation errors never echo submitted values. Prompts are not
  persisted in the portal; requests/audits retain the gateway's existing redaction.
- The UI does not expose arbitrary proxy routes or direct tool execution.

This is not a production identity system: no MFA, password recovery, external identity
provider, TLS termination or distributed session store. The host, portal, gateway and
configured code are trusted; their compromise is outside the current claim. Container
egress is not destination-filtered. Simulated tools and limited heuristics remain.
Do not publish the portal or bind it to a public interface.

## Verification

`python -m pytest` includes portal -> runner -> real gateway integration tests using
simulated Gemini responses. They cover execution, out-of-scope rejection, approve/reject,
argument binding, replay, role escalation attempts, CSRF, session expiry/logout, login
throttling, oversized bodies, error redaction and concurrent-run refusal. These are
functional checks for the three objectives, not a revived evaluation benchmark.

Live CLI evidence from 2026-10-17: the owner demonstrated Gemini metadata read
(`865b293e…`), out-of-scope denial (`2b2155d9…`), approval/execution (`b86d670c…`),
rejection (`9c186a2a…`) and an explicitly unauthorized prompt denied (`3d0723b0…`).
The new Docker web workflow still needs its first run on the owner's Windows laptop.

Development verification: 75 automated tests passed, the real HTTP gateway smoke test passed, and JavaScript syntax/static element checks passed. Docker is unavailable in the development environment. Visual browser testing was attempted but blocked by a failed Chromium download; screenshot/layout verification remains pending on Windows.
