"""Start an isolated real HTTP server and exercise the separate replay process."""

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    credentials = {
        role: secrets.token_urlsafe(32) for role in ("analyst", "responder", "reviewer")
    }
    config = Path(temp) / "hashes.json"
    config.write_text(
        json.dumps(
            {
                role: hashlib.sha256(token.encode()).hexdigest()
                for role, token in credentials.items()
            }
        )
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["AGENTFENCE_TOKEN_HASHES"] = str(config)
    env["AGENTFENCE_DB"] = str(Path(temp) / "state.db")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "agentfence.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError("Server exited during startup")
            try:
                with urllib.request.urlopen(url + "/health", timeout=1) as response:
                    assert json.load(response)["status"] == "ok"
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Server did not become ready")
        with urllib.request.urlopen(url, timeout=3) as response:
            assert "Every action, verified." in response.read().decode()
        client_env = os.environ.copy()
        client_env["AGENTFENCE_TOKEN"] = credentials["analyst"]
        client_env["AGENTFENCE_URL"] = url
        r = subprocess.run(
            [sys.executable, "demo/replay.py"],
            cwd=root,
            env=client_env,
            check=True,
            capture_output=True,
            text=True,
        )
        expected = [
            "=> allow / policy_permitted",
            "=> deny / schema_invalid",
            "=> deny / resource_not_in_scope",
            "=> deny / suspicious_tool_output",
        ]
        assert all(e in r.stdout for e in expected), r.stdout
        print(r.stdout, end="")
        print("Real HTTP smoke test passed.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
