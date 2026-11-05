from .base import Provider, ProviderError, loads, sse


class Anthropic(Provider):
    name = "anthropic"
    label = "Anthropic Claude"
    default_model = "claude-sonnet-5-5"
    base_url = "https://api.anthropic.com"

    def _messages(self, messages):
        out = []
        for message in messages:
            content = []
            for block in message["content"]:
                if block["type"] == "text":
                    content.append({"type": "text", "text": block["text"]})
                elif block["type"] == "tool_use":
                    content.append({"type": "tool_use", "id": block["id"], "name": block["name"], "input": block["input"]})
                else:
                    content.append({
                        "type": "tool_result", "tool_use_id": block["tool_use_id"],
                        "content": block["content"], "is_error": bool(block.get("is_error")),
                    })
            out.append({"role": message["role"], "content": content})
        return out

    def stream(self, system, messages, tools, max_tokens=2048):
        specs = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]
        if specs:
            specs[-1]["cache_control"] = {"type": "ephemeral"}  # stable prefix (tools, then system) is cached between turns
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": self._messages(messages),
            "stream": True,
        }
        if specs:
            body["tools"] = specs
        if self.temperature is not None:
            body["temperature"] = self.temperature
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
        usage = {"input": 0, "output": 0, "cached": 0}
        pending = {}
        reason = "end"
        with self._post(f"{self.base_url}/v1/messages", headers, body) as response:
            for event in sse(response):
                kind = event.get("type")
                if kind == "message_start":
                    u = event.get("message", {}).get("usage", {})
                    usage["cached"] = u.get("cache_read_input_tokens") or 0
                    usage["input"] = (u.get("input_tokens") or 0) + usage["cached"] + (u.get("cache_creation_input_tokens") or 0)
                elif kind == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        pending[event["index"]] = {"id": block["id"], "name": block["name"], "json": ""}
                elif kind == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield ("text", delta.get("text", ""))
                    elif delta.get("type") == "input_json_delta" and event["index"] in pending:
                        pending[event["index"]]["json"] += delta.get("partial_json", "")
                elif kind == "content_block_stop" and event.get("index") in pending:
                    call = pending.pop(event["index"])
                    yield ("tool_use", {"type": "tool_use", "id": call["id"], "name": call["name"], "input": loads(call["json"])})
                elif kind == "message_delta":
                    usage["output"] = event.get("usage", {}).get("output_tokens") or usage["output"]
                    reason = event.get("delta", {}).get("stop_reason") or reason
                elif kind == "error":
                    raise ProviderError(event.get("error", {}).get("message") or "The AI provider stream failed.", "stream")
        yield ("usage", usage)
        yield ("stop", reason)
