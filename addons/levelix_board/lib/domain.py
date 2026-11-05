"""Minimal reader for Odoo domains (prefix notation) as they appear in a spec.

Only used to inspect a domain (find fields, find conditions that always hold);
evaluation stays with Odoo.
"""
from .errors import BoardError

LOGIC = ("&", "|", "!")
ARITY = {"&": 2, "|": 2, "!": 1}


def is_leaf(item) -> bool:
    return isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[0], str) and isinstance(item[1], str)


def parse(domain, path: str = "domain"):
    """Return a list of top-level nodes (implicit AND).

    A node is a leaf tuple, or ``("&"|"|", a, b)``, or ``("!", a)``.
    """
    items = list(domain)
    nodes = []
    pos = 0

    def read(position):
        if position >= len(items):
            raise BoardError("INVALID_DOMAIN", path, "The domain ends where a condition was expected.")
        item = items[position]
        if isinstance(item, str):
            if item not in LOGIC:
                raise BoardError("INVALID_DOMAIN", "%s[%d]" % (path, position), "Unexpected text %r in the domain." % item)
            children = []
            position += 1
            for _ in range(ARITY[item]):
                child, position = read(position)
                children.append(child)
            return (item, *children), position
        if is_leaf(item):
            return tuple(item), position + 1
        raise BoardError("INVALID_DOMAIN", "%s[%d]" % (path, position), "A condition must look like [field, operator, value].")

    while pos < len(items):
        node, pos = read(pos)
        nodes.append(node)
    return nodes


def leaves(nodes):
    """Every leaf anywhere in the tree."""
    for node in nodes:
        if node[0] in LOGIC:
            yield from leaves(node[1:])
        else:
            yield node


def always_true_leaves(nodes):
    """Leaves that must all hold: top level and under '&'; nothing under '|' or '!'."""
    for node in nodes:
        if node[0] == "&":
            yield from always_true_leaves(node[1:])
        elif node[0] not in LOGIC:
            yield node
