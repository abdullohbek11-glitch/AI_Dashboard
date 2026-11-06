"""What changed between two versions of a spec, in the terms a reader cares about: which widgets were added, removed,
changed or only moved, and whether the title or the filters changed. Pure; no Odoo."""


def _title(widget):
    return widget.get("title") or widget.get("id") or "?"


def _without_grid(widget):
    return {k: v for k, v in widget.items() if k != "grid"}


def summarize(old, new) -> dict:
    """``{"added": [titles], "removed": [...], "changed": [...], "moved": [...], "other": ["title" | "filters" | "notes"]}``.

    ``changed`` = what a widget shows or how it is calculated differs; ``moved`` = only its place or size."""
    old, new = old or {}, new or {}
    before = {w["id"]: w for w in old.get("widgets", []) if isinstance(w, dict) and "id" in w}
    after = {w["id"]: w for w in new.get("widgets", []) if isinstance(w, dict) and "id" in w}
    out = {"added": [], "removed": [], "changed": [], "moved": [], "other": []}
    for wid, widget in after.items():
        if wid not in before:
            out["added"].append(_title(widget))
        elif _without_grid(before[wid]) != _without_grid(widget):
            out["changed"].append(_title(widget))
        elif before[wid].get("grid") != widget.get("grid"):
            out["moved"].append(_title(widget))
    out["removed"] = [_title(w) for wid, w in before.items() if wid not in after]
    if old.get("title") != new.get("title"):
        out["other"].append("title")
    if old.get("filters") != new.get("filters"):
        out["other"].append("filters")
    if old.get("assumptions") != new.get("assumptions") or old.get("uncertain") != new.get("uncertain"):
        out["other"].append("notes")
    return out
