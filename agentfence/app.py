"""Local HTTP boundary; no direct execution or baseline route is exposed."""

import hashlib
import hmac
import json
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .gateway import Gateway
from .models import Review
from .security import Principal
from .store import Store

STATIC = Path(__file__).parent / "static"


def create_app(db_path=None, credentials=None, clock=None):
    if credentials is None:
        config = Path(os.getenv("AGENTFENCE_TOKEN_HASHES", "runtime/token-hashes.json"))
        if not config.is_file():
            raise RuntimeError(
                "Run python scripts/setup.py before starting AgentFence."
            )
        encoded = json.loads(config.read_text())
        if set(encoded) != {"analyst", "responder", "reviewer"}:
            raise RuntimeError("Expected three configured identities.")
        try:
            hashes = {name: bytes.fromhex(value) for name, value in encoded.items()}
        except (TypeError, ValueError):
            raise RuntimeError("Invalid credential hashes.") from None
        if (
            any(len(value) != 32 for value in hashes.values())
            or len(set(hashes.values())) != 3
        ):
            raise RuntimeError("Expected three distinct SHA-256 credential hashes.")
    else:
        if (
            set(credentials) != {"analyst", "responder", "reviewer"}
            or any(not isinstance(v, str) or len(v) < 32 for v in credentials.values())
            or len(set(credentials.values())) != 3
        ):
            raise RuntimeError(
                "Three distinct credentials of at least 32 characters are required."
            )
        hashes = {
            name: hashlib.sha256(token.encode()).digest()
            for name, token in credentials.items()
        }
    principals = {name: Principal(name, name) for name in hashes}
    store = Store(
        db_path or os.getenv("AGENTFENCE_DB", "runtime/state/agentfence.sqlite3")
    )
    gateway = Gateway(store, principals, **({"clock": clock} if clock else {}))
    app = FastAPI(
        title="AgentFence",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.gateway = gateway

    @app.exception_handler(sqlite3.Error)
    async def storage_failure(request, exc):
        # Failed transactions roll back mock side effects. Never fail open.
        return JSONResponse({"detail": "audit_or_storage_unavailable"}, status_code=503)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    def identity(request):
        auth = request.headers.get("authorization", "")
        supplied = (
            hashlib.sha256(auth[7:].encode()).digest()
            if auth.startswith("Bearer ")
            else b""
        )
        for name, expected in hashes.items():
            if hmac.compare_digest(supplied, expected):
                return principals[name]
        gateway.reject_protocol("anonymous", "authentication_required")
        raise HTTPException(401, "authentication_required")

    async def payload(request, actor):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32768:
                gateway.reject_protocol(actor, "body_too_large")
                raise HTTPException(413, "body_too_large")

        def no_duplicates(pairs):
            result = {}
            for k, v in pairs:
                if k in result:
                    raise ValueError("duplicate key")
                result[k] = v
            return result

        try:
            return json.loads(
                body,
                object_pairs_hook=no_duplicates,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
            )
        except (ValueError, UnicodeError, RecursionError):
            gateway.reject_protocol(actor, "invalid_json")
            raise HTTPException(400, "invalid_json")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "mock-tools", "version": "0.1.0"}

    @app.get("/api/me")
    def me(request: Request):
        p = identity(request)
        with store.connect() as c:
            tasks = [
                dict(r)
                for r in c.execute("SELECT * FROM tasks WHERE owner=?", (p.name,))
            ]
        return {"name": p.name, "role": p.role, "tasks": tasks}

    @app.post("/api/calls")
    async def calls(request: Request):
        p = identity(request)
        raw = await payload(request, p.name)
        return gateway.submit(p, raw)

    @app.post("/api/approvals/{rid}")
    async def review(rid: str, request: Request):
        p = identity(request)
        raw = await payload(request, p.name)
        try:
            decision = Review.model_validate(raw)
        except ValidationError:
            gateway.reject_protocol(p.name, "invalid_review")
            raise HTTPException(422, "invalid_review")
        code, data = gateway.review(p, rid, decision)
        return JSONResponse(data, status_code=code)

    @app.get("/api/requests")
    def requests(request: Request):
        p = identity(request)
        with store.connect() as c:
            if p.role == "reviewer":
                rows = c.execute(
                    "SELECT * FROM requests WHERE tenant=? AND case_id=? ORDER BY created DESC LIMIT 100",
                    (p.tenant, p.case),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM requests WHERE owner=? ORDER BY created DESC LIMIT 100",
                    (p.name,),
                ).fetchall()
            return [
                {
                    **dict(r),
                    "arguments": json.loads(r["args"]),
                    "expired": r["status"] == "pending"
                    and gateway.clock() >= r["expires"],
                }
                for r in rows
            ]

    @app.get("/api/audit")
    def audit(request: Request):
        p = identity(request)
        if p.role != "reviewer":
            gateway.reject_protocol(p.name, "reviewer_required")
            raise HTTPException(403, "reviewer_required")
        with store.connect() as c:
            return [
                {**dict(r), "details": json.loads(r["details"])}
                for r in c.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT 200")
            ]

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
