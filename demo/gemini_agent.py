"""Gemini transport for the shared, gateway-only agent loop."""
import argparse
import json
import os
import sys

import httpx

try:
    from .openai_agent import run_agent
except ImportError:  # Direct script invocation inside the isolated client image.
    from openai_agent import run_agent


class GeminiAdapter:
    """Translate the shared loop contract to Google's Chat Completions endpoint.

    One instance per run. Preserve complete assistant messages, including Gemini
    thought-signature metadata, when returning gateway results on the next turn.
    """

    def __init__(self, client):
        self.client = client
        self.messages = []
        self.request_count = 0

    def post(self, path, *, json):
        if path != "/v1/responses":
            raise ValueError("unsupported internal operation")
        if not self.messages:
            self.messages = [{"role": "system", "content": json["instructions"]},
                             *json["input"]]
        else:
            result = json["input"][-1]
            if result.get("type") != "function_call_output":
                raise ValueError("gateway output required")
            self.messages.append({"role": "tool", "tool_call_id": result["call_id"],
                                  "content": result["output"]})
        tool = json["tools"][0]
        self.request_count += 1
        response = self.client.post("chat/completions", json={
            "model": json["model"], "messages": self.messages,
            "tools": [{"type": "function", "function": {
                k: tool[k] for k in ["name", "description", "parameters"]}}],
            "tool_choice": "auto", "max_tokens": json["max_output_tokens"],
        })
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        converted = {"status": "incomplete", "output": []}
        if len(choices) == 1 and choices[0].get("finish_reason") in {"stop", "tool_calls"}:
            message = choices[0]["message"]
            if message.get("role") != "assistant":
                raise ValueError("unexpected model role")
            self.messages.append(message)
            output = []
            for call in message.get("tool_calls") or []:
                function = call["function"]
                if not isinstance(call.get("id"), str) or not call["id"]:
                    raise ValueError("missing call identifier")
                output.append({"type": "function_call", "call_id": call["id"],
                               "name": function["name"], "arguments": function["arguments"]})
            if not output:
                content = message.get("content") or ""
                if not isinstance(content, str):
                    raise ValueError("unexpected content type")
                output = [{"type": "message", "content": [
                    {"type": "output_text", "text": content}]}]
            converted = {"status": "completed", "output": output}
        return httpx.Response(200, json=converted, request=response.request)


def describe_http_error(error, model_requests):
    """Report only trusted labels and status codes, never remote error text."""
    code = error.response.status_code
    is_provider = error.request.url.host == "generativelanguage.googleapis.com"
    if is_provider:
        source = f"Gemini model request {model_requests}"
    else:
        source = {"/api/me": "AgentFence authentication",
                  "/api/calls": "AgentFence tool submission"}.get(
                      error.request.url.path, "AgentFence request")
    status = ""
    if is_provider:
        try:
            value = error.response.json()["error"]["status"]
            if isinstance(value, str) and value in {
                "INVALID_ARGUMENT", "UNAUTHENTICATED", "PERMISSION_DENIED",
                "NOT_FOUND", "RESOURCE_EXHAUSTED", "INTERNAL", "UNAVAILABLE",
                "DEADLINE_EXCEEDED", "FAILED_PRECONDITION"}:
                status = f"; {value}"
        except (ValueError, KeyError, TypeError):
            pass
    hints = {401: "Check the credential for this service.",
             403: "Check permissions for this service.",
             404: "Check model availability." if is_provider else "Check gateway routes and resources.",
             429: "Quota/rate limit reached. Check AI Studio limits.",
             503: "Service unavailable; this does not establish the underlying cause."}
    return (f"Agent stopped at {source} (HTTP {code}{status}). "
            + hints.get(code, "Check service configuration.")
            + " No automatic retry. Inspect gateway requests before rerunning; earlier tool calls may have executed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="investigation-1")
    parser.add_argument("--turns", type=int, default=4)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()
    if any(not os.getenv(k) for k in ["GEMINI_API_KEY", "GEMINI_MODEL", "AGENTFENCE_TOKEN"]):
        parser.error("Set GEMINI_API_KEY, GEMINI_MODEL and AGENTFENCE_TOKEN locally")
    # Provider is fixed. No API key appears in URLs, model context or gateway evidence.
    with httpx.Client(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      timeout=60, trust_env=False,
                      headers={"Authorization": "Bearer " + os.environ["GEMINI_API_KEY"]}) as provider, \
         httpx.Client(base_url=os.getenv("AGENTFENCE_URL", "http://127.0.0.1:8000"),
                      timeout=15, trust_env=False,
                      headers={"Authorization": "Bearer " + os.environ["AGENTFENCE_TOKEN"]}) as gateway:
        adapter = GeminiAdapter(provider)
        try:
            result = run_agent(adapter, gateway, model=os.environ["GEMINI_MODEL"],
                               task_id=args.task, prompt=args.prompt, max_turns=args.turns)
            print(json.dumps(result, indent=2))
        except httpx.HTTPStatusError as error:
            print(describe_http_error(error, adapter.request_count), file=sys.stderr)
            return 1
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
            print("Agent stopped: invalid provider response, connection failure or local configuration. Inspect gateway logs before retrying.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
