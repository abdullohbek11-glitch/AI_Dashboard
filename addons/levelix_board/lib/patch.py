"""A small, safe subset of JSON Patch (RFC 6902) for changing a dashboard spec.

Why a patch and not a whole new spec: widget ids and positions survive, and a button the assistant offers
("count delivered goods instead") is just a ready patch the server applies without any AI.

Allowed: ``add`` / ``replace`` / ``remove``; paths only under ``/widgets``, ``/filters``, ``/title``,
``/assumptions``. Widget ids never change, and ``/widgets`` itself cannot be replaced or removed as a whole.
The input is never modified. After applying, the caller validates the whole spec again.
"""
import copy

from .errors import BoardError

OPS = ("add", "replace", "remove")
ROOTS = ("widgets", "filters", "title", "assumptions")
MAX_OPS = 20
MAX_PATH_DEPTH = 12


def _bad(path, message):
    return BoardError("BAD_PATCH", path, message)


def _segments(path, where):
    if not isinstance(path, str) or not path.startswith("/") or len(path) > 300:
        raise _bad(where, "A patch path looks like '/widgets/0/data/limit'.")
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]
    if not parts or parts[0] not in ROOTS:
        raise _bad(where, "A patch may only change %s (got '%s')." % (", ".join("/" + r for r in ROOTS), path))
    if len(parts) > MAX_PATH_DEPTH:
        raise _bad(where, "The path is too deep.")
    return parts


def _index(container, key, where, allow_end=False):
    """The list position ``key`` names, or raise."""
    if key == "-" and allow_end:
        return len(container)
    if not (isinstance(key, str) and key.isdigit()):
        raise _bad(where, "'%s' is not a position in a list." % key)
    position = int(key)
    if position > len(container) or (position == len(container) and not allow_end):
        raise _bad(where, "There is no item %d at this place." % position)
    return position


def _walk(root, parts, where):
    """The container that holds the last segment."""
    node = root
    for key in parts[:-1]:
        if isinstance(node, list):
            node = node[_index(node, key, where)]
        elif isinstance(node, dict) and key in node:
            node = node[key]
        else:
            raise _bad(where, "There is nothing at '%s'." % key)
    return node


def _guard_ids(parts, op, new, old, where):
    """Widget ids are the handles of the layout and of every saved reference: they never change."""
    if parts == ["widgets"] and op in ("replace", "remove"):
        raise _bad(where, "The whole list of widgets cannot be replaced or removed; change single widgets.")
    if len(parts) == 3 and parts[0] == "widgets" and parts[2] == "id":
        raise _bad(where, "A widget's id cannot be changed.")
    if len(parts) == 2 and parts[0] == "widgets" and op == "replace":
        if not isinstance(new, dict) or new.get("id") != (old or {}).get("id"):
            raise _bad(where, "A replaced widget keeps its id '%s'." % (old or {}).get("id"))
    if len(parts) == 2 and parts[0] == "widgets" and op == "add" and not (isinstance(new, dict) and isinstance(new.get("id"), str)):
        raise _bad(where, "A new widget needs an id.")


def apply_patch(spec, patch):
    """A new spec with ``patch`` applied. Raises ``BoardError("BAD_PATCH", ...)`` on anything unusual."""
    if not isinstance(patch, list) or not patch:
        raise _bad("patch", "A patch is a non-empty list of operations.")
    if len(patch) > MAX_OPS:
        raise _bad("patch", "A patch has at most %d operations." % MAX_OPS)
    result = copy.deepcopy(spec)
    for number, step in enumerate(patch):
        where = "patch[%d]" % number
        if not isinstance(step, dict) or step.get("op") not in OPS or set(step) - {"op", "path", "value"}:
            raise _bad(where, "Each operation is {op: add|replace|remove, path, value}.")
        op = step["op"]
        if op != "remove" and "value" not in step:
            raise _bad(where, "'%s' needs a 'value'." % op)
        parts = _segments(step.get("path"), where)
        parent = _walk(result, parts, where)
        key = parts[-1]
        value = copy.deepcopy(step.get("value"))
        if isinstance(parent, list):
            position = _index(parent, key, where, allow_end=(op == "add"))
            old = parent[position] if position < len(parent) else None
            _guard_ids(parts, op, value, old, where)
            if op == "add":
                parent.insert(position, value)
            elif op == "replace":
                parent[position] = value
            else:
                del parent[position]
        elif isinstance(parent, dict):
            _guard_ids(parts, op, value, parent.get(key), where)
            if op != "add" and key not in parent:
                raise _bad(where, "There is nothing at '%s' to %s." % (key, op))
            if op == "remove":
                del parent[key]
            else:
                parent[key] = value
        else:
            raise _bad(where, "This place cannot hold more.")
    return result
