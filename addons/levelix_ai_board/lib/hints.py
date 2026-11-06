"""Which hints fit a question. Keywords are comma-separated and may be in several languages."""
import re

MAX_HINTS = 5
MIN_WORD = 4  # a question word this long may match inside a keyword ("sotuvni" ~ "sotuv")


def keywords(text):
    return [k.strip().lower() for k in re.split(r"[,;\n]", text or "") if k.strip()]


def score(hint_keywords, query):
    """How many keywords the question touches: a keyword inside the question, or a long question word inside a keyword."""
    text = (query or "").lower()
    words = [w for w in re.findall(r"\w+", text) if len(w) >= MIN_WORD]
    return sum(1 for k in hint_keywords if k in text or any(w in k for w in words))


def match(hints, query):
    """``hints``: list of (sequence, keywords_text, payload). Best first, at most ``MAX_HINTS``; no match, no hint."""
    scored = []
    for sequence, keywords_text, payload in hints:
        value = score(keywords(keywords_text), query)
        if value:
            scored.append((-value, sequence, payload))
    scored.sort(key=lambda row: row[:2])
    return [payload for _v, _s, payload in scored[:MAX_HINTS]]
