"""What the model is allowed to see of a tool result.

``aggregates`` (default): the model sees what the tool found, so it can answer in words.
``schema``: the model sees the *shape* only (which models and fields exist, how many groups
and columns); never a value, a name, a record. The user's own screen always gets the full
result: this only filters what travels to the vendor.
"""
MODE_AGGREGATES = "aggregates"
MODE_SCHEMA = "schema"
MODES = (MODE_AGGREGATES, MODE_SCHEMA)

# tools whose result is the structure of the data, not data: safe in every mode
STRUCTURE_TOOLS = ("find_models", "describe_model", "ask_user", "pick_record")
# tools that read records: not offered at all in schema mode
RECORD_TOOLS = ("search_records",)


def tools_for(mode, names):
    """The tool names offered to the model in this mode."""
    return [n for n in names if not (mode == MODE_SCHEMA and n in RECORD_TOOLS)]


def aggregate_shape(result):
    """Group count and column titles of an ``aggregate`` result, nothing else."""
    groups = result.get("groups") or []
    columns = list(result.get("column_labels") or [])
    return {
        "shape": "%d group%s, %d column%s%s" % (
            len(groups), "" if len(groups) == 1 else "s", len(columns), "" if len(columns) == 1 else "s",
            " (%s)" % ", ".join(columns) if columns else ""),
        "groups": len(groups),
        "columns": columns,
        "truncated": bool(result.get("truncated")),
        "note": "Values are hidden from you by the privacy setting. The user sees the full result on screen. "
                "Tell them what you calculated, not the numbers.",
    }


def to_ai(name, result, mode):
    """The result of tool ``name`` as the model may read it."""
    if mode != MODE_SCHEMA or name in STRUCTURE_TOOLS:
        return result
    if name == "aggregate":
        return aggregate_shape(result)
    return {"note": "The result of this tool is hidden from you by the privacy setting; the user sees it on screen."}
