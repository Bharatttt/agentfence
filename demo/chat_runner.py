"""Isolated model service. Receives only the current non-reviewer credential."""
import hmac
import json
import os
import threading
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from demo.gemini_agent import GeminiAdapter, describe_http_error
from demo.openai_agent import run_agent


class Run(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    prompt: str = Field(min_length=1, max_length=4000)
    token: str = Field(min_length=32, max_length=256)
    task: Literal['investigation-1', 'response-1']


def create_app(config=None, execute=None):
    if config is None:
        config = json.loads(Path(os.getenv('RUNNER_CONFIG', '/run/secrets/runner-config')).read_text())
    busy = threading.Lock()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse({'detail': 'Invalid runner request.'}, status_code=422)

    @app.middleware('http')
    async def authenticate(request, call_next):
        if request.url.path != '/health':
            auth = request.headers.get('authorization', '')
            if not hmac.compare_digest(auth, 'Bearer ' + config['runner_secret']):
                return JSONResponse({'detail': 'Runner authentication required.'}, status_code=401)
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 20000:
                return JSONResponse({'detail': 'Request too large.'}, status_code=413)
            chunks.append(chunk)
        request._body = b''.join(chunks)
        return await call_next(request)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/run')
    def run(body: Run):
        if not busy.acquire(blocking=False):
            raise HTTPException(429, 'Another agent task is running. Wait for it to finish.')
        try:
            if execute is not None:
                return execute(body)
            with httpx.Client(base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                    timeout=60, trust_env=False,
                    headers={'Authorization': 'Bearer ' + config['api_key']}) as provider, \
                 httpx.Client(base_url=os.getenv('AGENTFENCE_URL', 'http://gateway:8000'),
                    timeout=15, trust_env=False,
                    headers={'Authorization': 'Bearer ' + body.token}) as gateway:
                adapter = GeminiAdapter(provider)
                try:
                    return run_agent(adapter, gateway, model=config['model'],
                                     task_id=body.task, prompt=body.prompt, max_turns=4)
                except httpx.HTTPStatusError as error:
                    return JSONResponse({'detail': describe_http_error(error, adapter.request_count)}, status_code=502)
                except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
                    return JSONResponse({'detail': 'Agent stopped safely. Check Activity before retrying; an earlier tool action may have executed.'}, status_code=502)
        finally:
            busy.release()
    return app
