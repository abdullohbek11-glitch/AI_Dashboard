"""What the system looks up for the model before it starts: the best hint and the fields of its reporting model.

One compact block after the question. The model reads it instead of calling ``get_hints`` and ``describe_model``, which saves
round trips (seconds each). Pure; no Odoo.
"""


def marker(model: str) -> str:
    return "[prepared:%s]" % model


def _field(entry: dict) -> str:
    text = "%s: %s \"%s\"" % (entry["name"], entry["type"], entry["label"])
    if entry.get("values"):
        text += " [%s]" % ", ".join(str(v[0]) for v in entry["values"][:12])
    if entry.get("relation"):
        text += " -> %s" % entry["relation"]
    if entry.get("summable"):
        text += " (sum)"
    return text


def block(hint: dict, described: dict) -> str:
    """The block of text; ``hint`` is one result of ``levelix.ai.hint._matching``, ``described`` what ``describe_model`` returns."""
    model = hint["model"]
    fields = "\n".join("- " + _field(f) for f in described.get("fields", []))
    return (
        "%s The system already looked this up for you (it is not part of what the user typed). For %s do not call get_hints or "
        "describe_model; use this.\n"
        "Hint: %s\n"
        "Fields of %s (name: type \"label\" [values] -> link) and (sum) where a number can be added up:\n%s"
    ) % (marker(model), model, (hint.get("advice") or "").strip(), model, fields)
