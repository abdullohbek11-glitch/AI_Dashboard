"""The three provider adapters against a pretend vendor that speaks each real wire format."""
import json
from unittest import mock

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..providers import PROVIDERS, ProviderError
from .fake_ai import GOOD_KEY, FakeAI

VENDORS = sorted(PROVIDERS)
ASK = [{"role": "user", "content": [{"type": "text", "text": "How many sales orders are there?"}]}]
TOOLS = [{"name": "aggregate", "description": "count things", "parameters": {"type": "object", "properties": {"model": {"type": "string"}}}}]


def make(vendor, url, key=GOOD_KEY, **kw):
    kw.setdefault("sleep", lambda s: None)
    return PROVIDERS[vendor](key, base_url=url, **kw)


def run(provider, messages, tools=()):
    events = list(provider.stream("You are a test.", messages, list(tools)))
    text = "".join(v for k, v in events if k == "text")
    calls = [v for k, v in events if k == "tool_use"]
    usage = next(v for k, v in events if k == "usage")
    return text, calls, usage, events[-1]


# "-standard": Odoo's test guard for outgoing HTTP cannot read a (connect, read) timeout pair; these tests only talk to 127.0.0.1
@tagged("levelix_ai_core", "-standard")
class TestProviders(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ai = FakeAI().__enter__()
        cls.addClassCleanup(cls.ai.__exit__)

    def setUp(self):
        super().setUp()
        self.ai.requests.clear()

    def test_every_vendor_streams_text_and_counts_tokens(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                text, calls, usage, stop = run(make(vendor, self.ai.url), [{"role": "user", "content": [{"type": "text", "text": "hello"}]}])
                self.assertEqual((text, calls), ("Hello from the fake AI.", []))
                self.assertEqual(usage["output"], 7)
                self.assertEqual(usage["cached"], 3)
                self.assertEqual(usage["input"], 14 if vendor == "anthropic" else 11)  # Anthropic reports cache reads separately
                self.assertEqual(stop[0], "stop")

    def test_a_tool_call_and_its_result_survive_the_round_trip(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                provider = make(vendor, self.ai.url)
                text, calls, _usage, _stop = run(provider, ASK, TOOLS)
                self.assertEqual((text, len(calls), calls[0]["name"]), ("", 1, "aggregate"))
                self.assertEqual(calls[0]["input"]["aggregates"], ["__count"])  # arguments streamed in pieces and glued back
                request = self.ai.requests[-1]["request"]
                self.assertEqual(request["tools"], ["aggregate"])
                history = ASK + [
                    {"role": "assistant", "content": [calls[0]]},
                    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": calls[0]["id"], "name": "aggregate",
                                                  "content": json.dumps({"groups": [[7]]}), "is_error": False}]},
                ]
                text, calls, _usage, _stop = run(provider, history, TOOLS)
                self.assertEqual((text, calls), ("There are 7.", []))  # the vendor read our tool result

    def test_the_vendor_sees_the_system_prompt_and_the_key(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                run(make(vendor, self.ai.url), ASK)
                request = self.ai.requests[-1]["request"]
                self.assertEqual((request["system"], request["key"]), ("You are a test.", GOOD_KEY))

    def test_no_tools_means_no_tools_key(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                run(make(vendor, self.ai.url), ASK)
                self.assertNotIn("tools", self.ai.requests[-1]["raw"])

    def test_temperature_is_sent_only_when_set(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                run(make(vendor, self.ai.url), ASK)
                run(make(vendor, self.ai.url, temperature=0.1), ASK)
                plain, warm = (self.ai.requests[-2]["raw"], self.ai.requests[-1]["raw"])
                dump = lambda raw: json.dumps(raw)  # noqa: E731
                self.assertNotIn("temperature", dump(plain))
                self.assertIn("temperature", dump(warm))

    def test_check_round_trip(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                self.assertEqual(make(vendor, self.ai.url).check(), "OK")

    # -- failures: readable, classified, and never containing the key --------------------------

    def fail(self, vendor, key=GOOD_KEY, **kw):
        with self.assertRaises(ProviderError) as ctx:
            run(make(vendor, self.ai.url, key=key, **kw), ASK)
        return ctx.exception

    def test_a_wrong_key_says_so(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                error = self.fail(vendor, key="bad-key")
                self.assertEqual(error.kind, "auth")
                self.assertIn("refused the API key", str(error))
                self.assertNotIn("bad-key", str(error))

    def test_limits_outages_and_unknown_models_are_told_apart(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                self.assertEqual(self.fail(vendor, key="limit-key").kind, "rate_limit")
                self.assertEqual(self.fail(vendor, key="down-key").kind, "server")
                error = self.fail(vendor, model="no-such-model")
                self.assertEqual(error.kind, "request")
                self.assertIn("no-such-model", str(error))

    def test_a_vendor_that_echoes_the_key_does_not_leak_it(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                self.ai.server.fail_next.append(418)
                error = self.fail(vendor)
                self.assertIn("418", str(error))
                self.assertNotIn(GOOD_KEY, str(error))
                self.assertIn("***", str(error))

    def test_network_failures_are_retried_but_http_answers_are_not(self):
        waits = []
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                waits.clear()
                with self.assertRaises(ProviderError) as ctx:
                    run(PROVIDERS[vendor](GOOD_KEY, base_url="http://127.0.0.1:9", sleep=waits.append, retries=2), ASK)  # nothing listens on port 9
                self.assertEqual((ctx.exception.kind, len(waits)), ("network", 2))
                self.assertIn("could not be reached", str(ctx.exception))
                before = len(self.ai.requests)
                self.fail(vendor, key="down-key")
                self.assertEqual(len(self.ai.requests) - before, 1)  # a 500 is answered once, never repeated

    def test_the_timeout_setting_reaches_the_request(self):
        with mock.patch("odoo.addons.levelix_ai_core.providers.base.requests.post", side_effect=__import__("requests").Timeout()) as post:
            with self.assertRaises(ProviderError) as ctx:
                run(PROVIDERS["anthropic"](GOOD_KEY, base_url=self.ai.url, timeout=7, retries=0), ASK)
        self.assertEqual(post.call_args.kwargs["timeout"], (10, 7))
        self.assertIn("timed out", str(ctx.exception))


@tagged("levelix_ai_core", "-standard")
class TestThinkingTime(BaseCase):
    """How long a thinking model may think is sent where it means something and nowhere else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ai = FakeAI().__enter__()
        cls.addClassCleanup(cls.ai.__exit__)

    def setUp(self):
        super().setUp()
        self.ai.requests.clear()

    def sent(self, vendor, model, reasoning):
        run(make(vendor, self.ai.url, model=model, reasoning=reasoning), ASK)
        return self.ai.requests[-1]["raw"]

    def test_openai_reasoning_models_get_the_effort(self):
        for model in ("gpt-5-mini", "gpt-5", "o4-mini"):
            self.assertEqual(self.sent("openai", model, "low").get("reasoning_effort"), "low", model)
        for model in ("gpt-4.1", "gpt-4o-mini"):  # a model that does not think would reject it
            self.assertNotIn("reasoning_effort", self.sent("openai", model, "low"), model)

    def test_gemini_names_a_level_or_a_budget(self):
        self.assertEqual(self.sent("gemini", "gemini-3.6-flash", "low")["generationConfig"]["thinkingConfig"], {"thinkingLevel": "low"})
        self.assertEqual(self.sent("gemini", "gemini-2.5-flash", "low")["generationConfig"]["thinkingConfig"], {"thinkingBudget": 512})
        self.assertEqual(self.sent("gemini", "gemini-2.5-flash", "minimal")["generationConfig"]["thinkingConfig"], {"thinkingBudget": 0})

    def test_nothing_is_sent_without_a_valid_level(self):
        for reasoning in (None, "", "default", "banana", 5):
            with self.subTest(reasoning=reasoning):
                self.assertNotIn("reasoning_effort", self.sent("openai", "gpt-5-mini", reasoning))
                self.assertNotIn("thinkingConfig", self.sent("gemini", "gemini-3.6-flash", reasoning)["generationConfig"])

    def test_anthropic_has_nothing_to_set(self):
        raw = self.sent("anthropic", "claude-sonnet-5-5", "low")
        self.assertFalse({"reasoning_effort", "thinking", "thinkingConfig"} & set(raw))
