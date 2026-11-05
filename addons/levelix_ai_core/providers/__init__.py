"""LLM providers. A new vendor is one class here and one entry in ``PROVIDERS``."""
from .anthropic import Anthropic
from .base import Provider, ProviderError
from .gemini import Gemini
from .openai import OpenAI

PROVIDERS = {cls.name: cls for cls in (Anthropic, OpenAI, Gemini)}

__all__ = ["PROVIDERS", "Provider", "ProviderError", "Anthropic", "OpenAI", "Gemini"]
