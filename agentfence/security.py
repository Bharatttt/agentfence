"""Explicit permissions plus advisory text heuristics; no semantic safety claim."""

import hashlib
import json
import re
from dataclasses import dataclass

READ_TOOLS = frozenset(
    {"get_asset_metadata", "search_incident_runbooks", "read_document"}
)
ROLE_TOOLS = {
    "analyst": READ_TOOLS,
    "responder": READ_TOOLS | {"disable_access_key", "export_asset_report"},
    "reviewer": frozenset(),
}
PATTERNS = {
    "override_instruction": r"\b(ignore|override|bypass)\b.{0,50}\b(instructions?|policy|rules?|approval|previous)\b",
    "secret_exfiltration": r"\b(export|upload|send|reveal|disclose)\b.{0,50}\b(secrets?|credentials?|passwords?|tokens?)\b",
    "role_impersonation": r"\b(system message|act as administrator|you are now admin)\b",
}


@dataclass(frozen=True)
class Principal:
    name: str
    role: str
    tenant: str = "tenant-a"
    case: str = "case-1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def signals(texts):
    found = []
    for source, text in texts.items():
        for rule, pattern in PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                found.append({"source": source, "rule": rule})
    return found


def evidence(texts):
    # No raw prompts or rejected arbitrary arguments in the audit database.
    return {
        k: {"sha256": hashlib.sha256(v.encode()).hexdigest(), "length": len(v)}
        for k, v in texts.items()
    }


def authorize(principal, task, tool, args):
    if not task or task["owner"] != principal.name:
        return "deny", "task_not_assigned"
    if task["tenant"] != principal.tenant or task["case_id"] != principal.case:
        return "deny", "task_scope_revoked"
    if tool not in ROLE_TOOLS.get(principal.role, ()):
        return "deny", "tool_not_permitted"
    if args["tenant_id"] != task["tenant"] or args["case_id"] != task["case_id"]:
        return "deny", "scope_mismatch"
    if tool not in READ_TOOLS and task["intent"] != "containment":
        return "deny", "task_intent_mismatch"
    if tool == "export_asset_report" and args["destination"] != "case-archive":
        return "deny", "destination_not_permitted"
    if tool in {"disable_access_key", "export_asset_report"}:
        return "require_approval", "sensitive_operation"
    return "allow", "policy_permitted"
