"""All mock tool access is mediated here; mock mutations and audit commit together."""

import json
import time
import uuid

from pydantic import ValidationError

from .models import SCHEMAS, Proposal
from .security import authorize, canonical, digest, evidence, signals


class GatewayError(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


class Gateway:
    def __init__(self, store, principals, ttl=300, clock=time.time):
        self.store, self.principals, self.ttl, self.clock = (
            store,
            principals,
            ttl,
            clock,
        )

    def log(self, c, rid, actor, event, details):
        c.execute(
            "INSERT INTO audit(at,request_id,actor,event,details) VALUES(?,?,?,?,?)",
            (self.clock(), rid, actor, event, canonical(details)),
        )

    def reject_protocol(self, actor, reason):
        with self.store.connect() as c:
            self.log(c, str(uuid.uuid4()), actor, "protocol_denied", {"reason": reason})

    def _resource(self, c, args, name, kind):
        row = c.execute(
            "SELECT * FROM resources WHERE id=? AND tenant=? AND case_id=? AND kind=?",
            (args[name], args["tenant_id"], args["case_id"], kind),
        ).fetchone()
        if not row:
            raise GatewayError(403, "resource_not_in_scope")
        return dict(row)

    def tool(self, c, name, args, rid):
        if name == "get_asset_metadata":
            r = self._resource(c, args, "asset_id", "asset")
            return {"asset_id": r["id"], "description": r["value"]}
        if name == "read_document":
            r = self._resource(c, args, "document_id", "document")
            return {"document_id": r["id"], "content": r["value"]}
        if name == "search_incident_runbooks":
            rows = c.execute(
                "SELECT id,value FROM resources WHERE tenant=? AND case_id=? AND kind='document' ORDER BY id",
                (args["tenant_id"], args["case_id"]),
            ).fetchall()
            matches = [
                dict(r)
                for r in rows
                if args["query"].casefold() in r["value"].casefold()
            ]
            return {"documents": matches[: args["limit"]]}
        if name == "disable_access_key":
            r = self._resource(c, args, "key_id", "key")
            c.execute("UPDATE resources SET value='disabled' WHERE id=?", (r["id"],))
            return {"key_id": r["id"], "status": "disabled", "simulated": True}
        if name == "export_asset_report":
            self._resource(c, args, "asset_id", "asset")
            c.execute(
                "INSERT INTO exports VALUES(?,?,?)",
                (rid, args["asset_id"], args["destination"]),
            )
            return {
                "archived": True,
                "destination": args["destination"],
                "simulated": True,
            }
        raise GatewayError(403, "unknown_tool")

    def submit(self, principal, raw):
        start = time.perf_counter()
        rid = str(uuid.uuid4())
        with self.store.connect() as c:
            self.log(
                c, rid, principal.name, "received", {"payload_digest": digest(raw)}
            )
            try:
                p = Proposal.model_validate(raw)
                if p.tool not in SCHEMAS:
                    raise GatewayError(403, "unknown_tool")
                a = SCHEMAS[p.tool].model_validate(p.arguments).model_dump()
            except (ValidationError, GatewayError) as exc:
                reason = (
                    "schema_invalid" if isinstance(exc, ValidationError) else exc.reason
                )
                now = self.clock()
                c.execute(
                    "INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        principal.name,
                        principal.tenant,
                        principal.case,
                        "invalid_proposal",
                        "{}",
                        "unresolved",
                        digest(raw),
                        "denied",
                        now,
                        now,
                        reason,
                    ),
                )
                self.log(c, rid, principal.name, "denied", {"reason": reason})
                return {
                    "request_id": rid,
                    "decision": "deny",
                    "reason": reason,
                    "status": "denied",
                    "decision_ms": (time.perf_counter() - start) * 1000,
                }
            task = c.execute("SELECT * FROM tasks WHERE id=?", (p.task_id,)).fetchone()
            decision, reason = authorize(principal, task, p.tool, a)
            texts = {
                "user_input": p.user_input,
                "retrieved_context": p.retrieved_context,
                "prior_tool_output": p.prior_tool_output,
            }
            risks = signals(texts)
            if risks and decision != "deny":
                decision, reason = "deny", "suspicious_context"
            # Validate resource existence/scope before offering an approval.
            resource_spec = {
                "get_asset_metadata": ("asset_id", "asset"),
                "read_document": ("document_id", "document"),
                "disable_access_key": ("key_id", "key"),
                "export_asset_report": ("asset_id", "asset"),
            }
            if decision != "deny" and p.tool in resource_spec:
                try:
                    self._resource(c, a, *resource_spec[p.tool])
                except GatewayError as exc:
                    decision, reason = "deny", exc.reason
            binding = {
                "owner": principal.name,
                "task_id": p.task_id,
                "tool": p.tool,
                "arguments": a,
                "evidence": evidence(texts),
            }
            request_digest = digest(binding)
            decision_ms = (time.perf_counter() - start) * 1000
            self.log(
                c,
                rid,
                principal.name,
                "policy",
                {
                    "decision": decision,
                    "reason": reason,
                    "evidence": evidence(texts),
                    "signals": risks,
                    "request_digest": request_digest,
                    "decision_ms": decision_ms,
                },
            )
            result = None
            status = {
                "allow": "executed",
                "deny": "denied",
                "require_approval": "pending",
            }[decision]
            if decision == "allow":
                result = self.tool(c, p.tool, a, rid)
                output_risks = signals({"tool_output": canonical(result)})
                if output_risks:
                    decision, reason, status, result = (
                        "deny",
                        "suspicious_tool_output",
                        "denied",
                        None,
                    )
                    self.log(
                        c,
                        rid,
                        principal.name,
                        "output_quarantined",
                        {"signals": output_risks},
                    )
            now = self.clock()
            # Only validated identifiers are retained. Arbitrary reason/query text is hashed.
            stored_args = a.copy()
            # Search queries are not needed after execution, so avoid persisting raw text.
            if "query" in stored_args:
                stored_args["query"] = "[omitted]"
            # Disallowed destination strings could contain secrets; retain no raw denied args.
            if status == "denied":
                stored_args = {}
            c.execute(
                "INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    principal.name,
                    principal.tenant,
                    principal.case,
                    p.tool,
                    canonical(stored_args),
                    p.task_id,
                    request_digest,
                    status,
                    now,
                    now + self.ttl,
                    reason,
                ),
            )
            self.log(
                c,
                rid,
                principal.name,
                status,
                {"tool": p.tool, "reason": reason, "result_digest": digest(result)},
            )
            return {
                "request_id": rid,
                "decision": decision,
                "reason": reason,
                "status": status,
                "request_digest": request_digest,
                "risk_signals": risks,
                "result": result,
                "decision_ms": decision_ms,
            }

    def review(self, reviewer, rid, review):
        with self.store.connect() as c:
            row = c.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if reviewer.role != "reviewer":
                self.log(
                    c,
                    rid,
                    reviewer.name,
                    "review_denied",
                    {"reason": "reviewer_required"},
                )
                return 403, {"detail": "reviewer_required"}
            if (
                not row
                or row["tenant"] != reviewer.tenant
                or row["case_id"] != reviewer.case
            ):
                return 404, {"detail": "request_not_found"}
            if row["status"] != "pending":
                return 409, {"detail": "request_not_pending"}
            if review.request_digest != row["digest"]:
                self.log(
                    c,
                    rid,
                    reviewer.name,
                    "review_denied",
                    {"reason": "digest_mismatch"},
                )
                return 409, {"detail": "digest_mismatch"}
            if self.clock() >= row["expires"]:
                c.execute("UPDATE requests SET status='expired' WHERE id=?", (rid,))
                self.log(c, rid, reviewer.name, "expired", {})
                return 409, {"detail": "approval_expired"}
            status, result = "rejected", None
            if review.approve:
                owner = self.principals.get(row["owner"])
                task = c.execute(
                    "SELECT * FROM tasks WHERE id=?", (row["task_id"],)
                ).fetchone()
                args = json.loads(row["args"])
                decision, reason = (
                    authorize(owner, task, row["tool"], args)
                    if owner
                    else ("deny", "identity_revoked")
                )
                if decision != "require_approval":
                    c.execute(
                        "UPDATE requests SET status='denied',reason=? WHERE id=?",
                        (reason, rid),
                    )
                    self.log(
                        c,
                        rid,
                        reviewer.name,
                        "approval_policy_denied",
                        {"reason": reason},
                    )
                    return 403, {"detail": reason}
                try:
                    result = self.tool(c, row["tool"], args, rid)
                except GatewayError as exc:
                    c.execute(
                        "UPDATE requests SET status='denied',reason=? WHERE id=?",
                        (exc.reason, rid),
                    )
                    self.log(
                        c,
                        rid,
                        reviewer.name,
                        "approval_policy_denied",
                        {"reason": exc.reason},
                    )
                    return 403, {"detail": exc.reason}
                status = "executed"
            c.execute("UPDATE requests SET status=? WHERE id=?", (status, rid))
            self.log(
                c,
                rid,
                reviewer.name,
                "reviewed",
                {"approved": review.approve, "request_digest": row["digest"]},
            )
            self.log(c, rid, reviewer.name, status, {"result_digest": digest(result)})
            return 200, {"request_id": rid, "status": status, "result": result}
