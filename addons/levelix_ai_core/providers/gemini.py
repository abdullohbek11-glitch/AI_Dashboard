import uuid

from .base import Provider, sse


class Gemini(Provider):
    name = "gemini"
    label = "Google Gemini"
    default_model = "gemini-3.6-flash"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _contents(self, messages):
        out = []
        for message in messages:
            parts = []
            for block in message["content"]:
                if block["type"] == "text":
                    parts.append({"text": block["text"]})
                elif block["type"] == "tool_use":
                    part = {"functionCall": {"name": block["name"], "args": block["input"]}}
                    if block.get("signature"):
                        part["thoughtSignature"] = block["signature"]
                    parts.append(part)
                else:
                    parts.append({"functionResponse": {"name": block.get("name") or "tool", "response": {"result": block["content"]}}})
            out.append({"role": "model" if message["role"] == "assistant" else "user", "parts": parts})
        return out

    def _thinking(self):
        """Gemini 3 names a level; the 2.5 family takes a budget of tokens."""
        if "gemini-3" in self.model:
            return {"thinkingLevel": self.reasoning}
        return {"thinkingBudget": {"minimal": 0, "low": 512, "medium": 2048, "high": 8192}[self.reasoning]}

    def stream(self, system, messages, tools, max_tokens=2048):
        config = {"maxOutputTokens": max_tokens}
        if self.temperature is not None:
            config["temperature"] = self.temperature
        if self.reasoning:
            config["thinkingConfig"] = self._thinking()
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self._contents(messages),
            "generationConfig": config,
        }
        if tools:
            body["tools"] = [{"functionDeclarations": tools}]
        headers = {"x-goog-api-key": self.api_key}
        usage = {"input": 0, "output": 0, "cached": 0}
        reason = "end"
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse"
        with self._post(url, headers, body) as response:
            for event in sse(response):
                if event.get("usageMetadata"):
                    u = event["usageMetadata"]
                    usage = {
                        "input": u.get("promptTokenCount") or 0,
                        "output": u.get("candidatesTokenCount") or 0,
                        "cached": u.get("cachedContentTokenCount") or 0,
                    }
                for candidate in event.get("candidates") or []:
                    for part in (candidate.get("content") or {}).get("parts") or []:
                        if part.get("functionCall"):
                            call = part["functionCall"]
                            block = {
                                "type": "tool_use", "id": f"call_{uuid.uuid4().hex[:12]}",
                                "name": call.get("name", ""), "input": call.get("args") or {},
                            }
                            if part.get("thoughtSignature"):
                                block["signature"] = part["thoughtSignature"]
                            yield ("tool_use", block)
                        elif part.get("text") and not part.get("thought"):
                            yield ("text", part["text"])
                    reason = candidate.get("finishReason") or reason
        yield ("usage", usage)
        yield ("stop", reason)
