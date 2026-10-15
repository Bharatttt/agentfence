"""Separate, unprivileged HTTP client. Scripted proposals, not an LLM."""

import json
import os
import urllib.request

base = os.getenv("AGENTFENCE_URL", "http://127.0.0.1:8000").rstrip("/")
token = os.environ["AGENTFENCE_TOKEN"]  # Analyst only; no reviewer or DB access.
scoped = {"tenant_id": "tenant-a", "case_id": "case-1"}
scenarios = [
    (
        "Legitimate metadata read",
        "get_asset_metadata",
        {**scoped, "asset_id": "asset-1"},
    ),
    (
        "Parameter smuggling",
        "get_asset_metadata",
        {**scoped, "asset_id": "asset-1", "bypass_policy": True},
    ),
    ("Restricted document", "read_document", {**scoped, "document_id": "restricted-1"}),
    (
        "Poisoned retrieved document",
        "read_document",
        {**scoped, "document_id": "poisoned-1"},
    ),
]
for label, tool, args in scenarios:
    proposal = {"task_id": "investigation-1", "tool": tool, "arguments": args}
    request = urllib.request.Request(
        base + "/api/calls",
        data=json.dumps(proposal).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.load(response)
    print(label, "=>", result["decision"], "/", result["reason"])
