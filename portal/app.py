"""Trusted browser backend: password sessions and fixed, role-scoped proxies."""
import json
import os
import secrets
import threading
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .auth import password_record, verify_password

STATIC = Path(__file__).parent / 'static'
ROLES = {'analyst', 'responder', 'reviewer'}
COOKIE = 'agentfence_session'


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Login(Contract):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class Chat(Contract):
    prompt: str = Field(min_length=1, max_length=4000)


class Decision(Contract):
    approve: bool
    request_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


def create_app(config=None, gateway_transport=None, runner_transport=None, clock=time.time):
    if config is None:
        config = json.loads(Path(os.getenv('PORTAL_CONFIG', '/run/secrets/portal-config')).read_text())
    if set(config['accounts']) != ROLES or set(config['tokens']) != ROLES:
        raise RuntimeError('Configure all three portal accounts first.')
    origin = config.get('origin', 'http://127.0.0.1:8001')
    sessions, failures = {}, {}
    lock = threading.Lock()
    dummy = password_record(secrets.token_urlsafe(32))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def boundary(request, call_next):
        # Fixed origin and custom header protect every state-changing browser request,
        # including login. No CORS permissions are granted.
        if request.method not in {'GET', 'HEAD'}:
            if request.headers.get('origin') != origin or request.headers.get('x-agentfence') != 'portal':
                return JSONResponse({'detail': 'Untrusted browser origin.'}, status_code=403)
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 20000:
                return JSONResponse({'detail': 'Request too large.'}, status_code=413)
            chunks.append(chunk)
        request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'Content-Security-Policy':
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    @app.exception_handler(httpx.HTTPError)
    async def upstream_error(request, error):
        return JSONResponse({'detail': 'A service could not be reached. Check Activity before retrying; an earlier action may have executed.'}, status_code=502)

    @app.exception_handler(RequestValidationError)
    async def invalid_body(request, error):
        # Do not echo password or arbitrary submitted fields in validation errors.
        return JSONResponse({'detail': 'Invalid request fields.'}, status_code=422)

    def actor(request):
        sid = request.cookies.get(COOKIE, '')
        with lock:
            session = sessions.get(sid)
            if not session or session['expires'] <= clock():
                sessions.pop(sid, None)
                raise HTTPException(401, 'Please sign in again.')
            return session['role']

    def proxy(role, path, body=None):
        with httpx.Client(base_url=os.getenv('AGENTFENCE_URL', 'http://gateway:8000'),
                          transport=gateway_transport, timeout=15, trust_env=False,
                          headers={'Authorization': 'Bearer ' + config['tokens'][role]}) as client:
            response = client.get(path) if body is None else client.post(path, json=body)
            # Gateway errors are controlled enums, unlike provider response bodies.
            return JSONResponse(response.json(), status_code=response.status_code)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/api/login')
    def login(body: Login, request: Request):
        # Bounded global throttle by peer; unknown usernames cannot grow the table.
        peer = request.client.host if request.client else 'local'
        now = clock()
        with lock:
            if len(failures) > 1000:
                raise HTTPException(429, "Sign-in service busy. Try later.")
            attempts = [t for t in failures.get(peer, []) if now - t < 60]
            if len(attempts) >= 5:
                raise HTTPException(429, 'Too many sign-in attempts. Wait one minute.')
            failures[peer] = attempts + [now]
        record = config['accounts'].get(body.username, dummy)
        valid = verify_password(body.password, record)
        if not valid or body.username not in ROLES:
            raise HTTPException(401, 'Incorrect username or password.')
        sid = secrets.token_urlsafe(32)
        with lock:
            for key in list(sessions):
                if sessions[key]['expires'] <= now:
                    del sessions[key]
            if len(sessions) >= 100:
                raise HTTPException(429, 'Too many active sessions. Sign out or wait for expiry.')
            sessions.pop(request.cookies.get(COOKIE, ''), None)
            sessions[sid] = {'role': body.username, 'expires': now + 8 * 3600}
        response = JSONResponse({'role': body.username})
        response.set_cookie(COOKIE, sid, httponly=True, samesite='strict',
                            secure=origin.startswith('https://'), max_age=8 * 3600)
        return response

    @app.post('/api/logout')
    def logout(request: Request):
        with lock:
            sessions.pop(request.cookies.get(COOKIE, ''), None)
        response = JSONResponse({'status': 'signed_out'})
        response.delete_cookie(COOKIE)
        return response

    @app.get('/api/session')
    def session(request: Request):
        return {'role': actor(request)}

    @app.get('/api/requests')
    def requests(request: Request):
        return proxy(actor(request), '/api/requests')

    @app.get('/api/audit')
    def audit(request: Request):
        role = actor(request)
        if role != 'reviewer':
            raise HTTPException(403, 'Only reviewers can inspect the audit trail.')
        return proxy(role, '/api/audit')

    @app.post('/api/review/{rid}')
    def review(rid: str, body: Decision, request: Request):
        role = actor(request)
        if role != 'reviewer':
            raise HTTPException(403, 'Only reviewers can approve or reject actions.')
        import uuid
        try:
            uuid.UUID(rid)
        except ValueError:
            raise HTTPException(400, 'Invalid request identifier.')
        return proxy(role, '/api/approvals/' + rid, body.model_dump())

    @app.post('/api/chat')
    def chat(body: Chat, request: Request):
        role = actor(request)
        if role not in {'analyst', 'responder'}:
            raise HTTPException(403, 'Reviewer accounts cannot run the agent.')
        # Neither role, task, destination nor credentials come from the browser/model.
        with httpx.Client(base_url=os.getenv('RUNNER_URL', 'http://chat-runner:8002'),
                          transport=runner_transport, timeout=330, trust_env=False) as client:
            response = client.post('/run', headers={'Authorization': 'Bearer ' + config['runner_secret']},
                json={'prompt': body.prompt, 'token': config['tokens'][role],
                      'task': 'response-1' if role == 'responder' else 'investigation-1'})
            return JSONResponse(response.json(), status_code=response.status_code)

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    return app
