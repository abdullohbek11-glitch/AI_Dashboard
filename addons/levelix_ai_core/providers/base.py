"""Shared plumbing of the LLM provider adapters: HTTP with timeouts, retries, readable errors.

One neutral conversation format in, one neutral event stream out, so the engine
never knows which vendor is behind it.

Messages::

    {"role": "user" | "assistant", "content": [block, ...]}
    block = {"type": "text", "text": str}
          | {"type": "tool_use", "id": str, "name": str, "input": dict, "signature": str?}
          | {"type": "tool_result", "tool_use_id": str, "name": str, "content": str, "is_error": bool}

Events (tuples)::

    ("text", str) · ("tool_use", block) · ("usage", {"input", "output", "cached"}) · ("stop", reason)
"""
import json
import time

import requests

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120
RETRIES = 2  # extra attempts after a network failure; HTTP answers (even errors) are never retried
BACKOFF = 0.6


class ProviderError(Exception):
    """The vendor refused or failed. The message is plain language and safe to show: it never holds the API key."""

    def __init__(self, message, kind="provider"):
        super().__init__(message)
        self.kind = kind  # "auth" | "rate_limit" | "network" | "server" | "request" | "stream"


def http_message(status, detail, model=""):
    """What the user reads for an HTTP failure of the vendor."""
    if status in (401, 403):
        return "The AI provider refused the API key. Check the key in the settings.", "auth"
    if status == 404 and model:
        return "The AI provider does not know the model '%s'. Check the model name in the settings." % model, "request"
    if status == 429:
        return "The AI provider's rate limit or quota was reached. Try again in a minute, or check the plan of the account.", "rate_limit"
    if status >= 500:
        return "The AI provider is having trouble right now (error %d). Try again shortly." % status, "server"
    return "The AI provider rejected the request (%d): %s" % (status, detail or "no details"), "request"


def redact(text, secret):
    """Never let the key travel inside a message, even when a vendor echoes it back."""
    text = str(text or "")
    return text.replace(secret, "***") if secret else text


def sse(response):
    """Yield decoded ``data:`` payloads of a server-sent event stream."""
    try:
        for raw in response.iter_lines():
            if not raw or not raw.startswith(b"data:"):
                continue
            data = raw[5:].strip()
            if not data or data == b"[DONE]":
                continue
            try:
                yield json.loads(data)
            except ValueError:
                continue
    except requests.RequestException as error:
        raise ProviderError("The connection to the AI provider was interrupted.", "network") from error


def loads(text):
    try:
        value = json.loads(text) if text else {}
    except ValueError:
        value = {}
    return value if isinstance(value, dict) else {}


class Provider:
    name = ""
    label = ""
    default_model = ""
    base_url = ""

    def __init__(self, api_key, model=None, base_url=None, timeout=READ_TIMEOUT, retries=RETRIES, temperature=None, sleep=time.sleep):
        self.api_key = api_key
        self.model = model or self.default_model
        self.base_url = (base_url or self.base_url).rstrip("/")
        self.timeout = (CONNECT_TIMEOUT, timeout)
        self.retries = retries
        self.temperature = temperature
        self._sleep = sleep

    # -- to implement ----------------------------------------------------------------
    def stream(self, system, messages, tools, max_tokens=2048):
        raise NotImplementedError

    # -- shared ------------------------------------------------------------------------
    def _post(self, url, headers, body):
        """POST with retries on network failures only. Returns the open streaming response."""
        last = None
        for attempt in range(self.retries + 1):
            try:
                response = requests.post(url, headers=headers, json=body, stream=True, timeout=self.timeout)
                break
            except requests.RequestException as error:  # connection refused, DNS, timeout
                last = error
                if attempt < self.retries:
                    self._sleep(BACKOFF * (attempt + 1))
        else:
            kind = "timed out" if isinstance(last, requests.Timeout) else "could not be reached"
            raise ProviderError("The AI provider %s (%s). Check the network and try again." % (kind, type(last).__name__), "network") from last
        if response.status_code >= 400:
            try:
                payload = response.json()
                error = payload.get("error", payload) if isinstance(payload, dict) else payload
                detail = error.get("message") if isinstance(error, dict) else str(error)
            except ValueError:
                detail = response.text[:300]
            message, kind = http_message(response.status_code, redact(detail, self.api_key)[:300], self.model)
            raise ProviderError(message, kind)
        return response

    def check(self):
        """A one-word round trip: proves that the key, the model and the network work."""
        text = ""
        for kind, value in self.stream("Reply with the single word OK.", [{"role": "user", "content": [{"type": "text", "text": "ping"}]}], [], max_tokens=16):
            if kind == "text":
                text += value
        return text.strip()
