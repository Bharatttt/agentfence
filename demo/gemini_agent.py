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
        try:
            result = run_agent(GeminiAdapter(provider), gateway, model=os.environ["GEMINI_MODEL"],
                               task_id=args.task, prompt=args.prompt, max_turns=args.turns)
            print(json.dumps(result, indent=2))
        except httpx.HTTPStatusError as error:
            # Deliberately omit response bodies, request URLs and credentials.
            code = error.response.status_code
            hints = {401: "Check the local API key or gateway token.",
                     403: "Check project/key permissions or task access.",
                     404: "Check GEMINI_MODEL and provider availability.",
                     429: "Quota/rate limit reached. Wait and check AI Studio limits; no automatic retry."}
            print(f"Agent stopped (HTTP {code}). " + hints.get(code, "Check model settings and service availability."), file=sys.stderr)
            return 1
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
            print("Agent stopped: invalid provider response, connection failure or local configuration. Inspect gateway logs before retrying.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
