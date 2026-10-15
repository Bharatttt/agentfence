"""Replay identical proposal fixtures against an intentionally unguarded mock and gateway.
The baseline does no auth, schema, scope, or approval checks and never uses real resources.
"""

import argparse
import json
import platform
import statistics
import tempfile
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from agentfence.gateway import Gateway
from agentfence.models import Review
from agentfence.security import Principal
from agentfence.store import Store

from .scenarios import CASES


def baseline(store, p):
    # Intentionally unsafe fixture, kept outside production app and Docker image.
    with store.connect() as c:
        a = p["arguments"]
        tool = p["tool"]
        if tool in ("get_asset_metadata", "read_document"):
            identifier = a.get("asset_id", a.get("document_id"))
            return dict(
                c.execute(
                    "SELECT * FROM resources WHERE id=?", (identifier,)
                ).fetchone()
            )
        if tool == "search_incident_runbooks":
            return [
                dict(r)
                for r in c.execute("SELECT * FROM resources WHERE kind='document'")
                if a["query"].casefold() in r["value"].casefold()
            ][: a.get("limit", 3)]
        if tool == "disable_access_key":
            c.execute(
                "UPDATE resources SET value='disabled' WHERE id=?", (a["key_id"],)
            )
            return {"status": "disabled"}
        if tool == "export_asset_report":
            c.execute(
                "INSERT INTO exports VALUES(?,?,?)",
                (str(uuid.uuid4()), a["asset_id"], a["destination"]),
            )
            return {"simulated_export": True}
        raise ValueError("Fixture does not implement this tool")


def percentile(values, q):
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * q))]


def run(repetitions):
    principals = {r: Principal(r, r) for r in ("analyst", "responder", "reviewer")}
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        for rep in range(repetitions):
            for index, case in enumerate(CASES):
                protected = Store(Path(temp) / f"{rep}-{index}-protected.db")
                unguarded = Store(Path(temp) / f"{rep}-{index}-baseline.db")
                g = Gateway(protected, principals)
                start = time.perf_counter()
                baseline_result = baseline(unguarded, case["proposal"])
                base_ms = (time.perf_counter() - start) * 1000
                start = time.perf_counter()
                r = g.submit(principals[case["role"]], case["proposal"])
                protected_ms = (time.perf_counter() - start) * 1000
                completed = r["status"] == "executed"
                if r["status"] == "pending" and not case["attack"]:
                    code, result = g.review(
                        principals["reviewer"],
                        r["request_id"],
                        Review(approve=True, request_digest=r["request_digest"]),
                    )
                    completed = code == 200 and result["status"] == "executed"
                rows.append(
                    {
                        "case": case["name"],
                        "repetition": rep,
                        "attack": case["attack"],
                        "baseline_executed": baseline_result is not None,
                        "gateway_decision": r["decision"],
                        "reason": r["reason"],
                        "completed": completed,
                        "baseline_ms": base_ms,
                        "gateway_ms": protected_ms,
                        "decision_ms": r["decision_ms"],
                    }
                )
    attacks = [r for r in rows if r["attack"]]
    benign = [r for r in rows if not r["attack"]]
    paired = [
        r["gateway_ms"] - r["baseline_ms"]
        for r in benign
        if r["gateway_decision"] == "allow"
    ]
    summary = {
        "attack_attempts": len(attacks),
        "benign_attempts": len(benign),
        "baseline_policy_violating_execution_rate": sum(
            r["baseline_executed"] for r in attacks
        )
        / len(attacks),
        "gateway_attack_block_rate": sum(
            r["gateway_decision"] == "deny" for r in attacks
        )
        / len(attacks),
        "gateway_unauthorized_execution_rate": sum(r["completed"] for r in attacks)
        / len(attacks),
        "benign_false_positive_rate": sum(
            r["gateway_decision"] == "deny" for r in benign
        )
        / len(benign),
        "benign_completion_rate": sum(r["completed"] for r in benign) / len(benign),
        "approval_frequency": sum(
            r["gateway_decision"] == "require_approval" for r in rows
        )
        / len(rows),
        "median_policy_ms": statistics.median(r["decision_ms"] for r in rows),
        "p95_policy_ms": percentile([r["decision_ms"] for r in rows], 0.95),
        "median_paired_allowed_overhead_ms": statistics.median(paired),
    }
    return {
        "evaluation": "Synthetic tool-call replay; no LLM or official benchmark run",
        "environment": {
            "python": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
            "pydantic": version("pydantic"),
            "repetitions": repetitions,
        },
        "summary": summary,
        "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--output", default="evaluation/results.json")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 1000:
        parser.error("repetitions must be between 1 and 1000")
    result = run(args.repetitions)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
