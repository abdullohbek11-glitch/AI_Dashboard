import json
import uuid

from .base import Provider, loads, sse


class OpenAI(Provider):
    name = "openai"
    label = "OpenAI"
    default_model = "gpt-5-mini"
    base_url = "https://api.openai.com/v1"

    def _messages(self, system, messages):
        out = [{"role": "system", "content": system}]
        for message in messages:
            text = "".join(b["text"] for b in message["content"] if b["type"] == "text")
            if message["role"] == "assistant":
                calls = [{
                    "id": b["id"], "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                } for b in message["content"] if b["type"] == "tool_use"]
                entry = {"role": "assistant", "content": text or None}
                if calls:
                    entry["tool_calls"] = calls
                out.append(entry)
                continue
            for block in message["content"]:
                if block["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block["content"]})
            if text:
                out.append({"role": "user", "content": text})
        return out

    def stream(self, system, messages, tools, max_tokens=2048):
        body = {
            "model": self.model,
            "messages": self._messages(system, messages),
            "max_completion_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        if self.temperature is not None:
            body["temperature"] = self.temperature
        headers = {"Authorization": f"Bearer {self.api_key}"}
        usage = {"input": 0, "output": 0, "cached": 0}
        pending = {}
        reason = "end"
        with self._post(f"{self.base_url}/chat/completions", headers, body) as response:
            for event in sse(response):
                if event.get("usage"):
                    u = event["usage"]
                    usage = {
                        "input": u.get("prompt_tokens") or 0,
                        "output": u.get("completion_tokens") or 0,
                        "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0,
                    }
                for choice in event.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield ("text", delta["content"])
                    for call in delta.get("tool_calls") or []:
                        slot = pending.setdefault(call.get("index", 0), {"id": "", "name": "", "json": ""})
                        slot["id"] = call.get("id") or slot["id"]
                        function = call.get("function") or {}
                        slot["name"] = function.get("name") or slot["name"]
                        slot["json"] += function.get("arguments") or ""
                    reason = choice.get("finish_reason") or reason
        for index in sorted(pending):
            call = pending[index]
            yield ("tool_use", {
                "type": "tool_use", "id": call["id"] or f"call_{uuid.uuid4().hex[:12]}",
                "name": call["name"], "input": loads(call["json"]),
            })
        yield ("usage", usage)
        yield ("stop", reason)
