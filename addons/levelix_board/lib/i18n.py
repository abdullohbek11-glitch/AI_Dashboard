"""Single seam for user-visible texts.

All texts shown to a user go through ``t()``. For now it returns the English
source text; the translation step (uz/ru) plugs in here without touching the
callers.
"""


def t(text: str) -> str:
    return text
