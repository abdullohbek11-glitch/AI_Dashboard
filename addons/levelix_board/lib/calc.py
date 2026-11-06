"""Calculated measures: ``"calc": "m1 - m2"``.

A tiny arithmetic parser, written by hand on purpose: the text comes from a model, so it must never reach ``eval``.
Allowed: numbers, measure ids, ``+ - * /``, unary minus and parentheses. Nothing else parses.

Evaluation is total: a missing value (``None``) or a division by zero gives ``None`` ("no value"), never an
exception and never ``inf``. Pure; no Odoo.
"""
import re

MAX_CHARS = 200
MAX_DEPTH = 12
_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([a-z][a-z0-9_]*)|(.))")


class CalcError(ValueError):
    """The formula cannot be read; ``position`` is a 0-based character offset."""

    def __init__(self, message, position=0):
        super().__init__(message)
        self.position = position


def _tokens(text):
    out, pos = [], 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:  # only trailing spaces are left
            break
        number, name, other = match.groups()
        start = match.start(1) if number else match.start(2) if name else match.start(3)
        if number is not None:
            out.append(("num", float(number), start))
        elif name is not None:
            out.append(("name", name, start))
        elif other.strip():
            out.append(("op", other, start))
        pos = match.end()
    return out


class _Parser:
    def __init__(self, tokens, size):
        self.tokens, self.i, self.size = tokens, 0, size

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self):
        token = self.peek()
        self.i += 1
        return token

    def at_op(self, *ops):
        token = self.peek()
        return token is not None and token[0] == "op" and token[1] in ops

    def parse(self):
        if not self.tokens:
            raise CalcError("The formula is empty.", 0)
        tree = self.expr(0)
        leftover = self.peek()
        if leftover is not None:
            raise CalcError("Unexpected '%s'." % leftover[1], leftover[2])
        return tree

    def expr(self, depth):
        node = self.term(depth)
        while self.at_op("+", "-"):
            op = self.take()[1]
            node = (op, node, self.term(depth))
        return node

    def term(self, depth):
        node = self.unary(depth)
        while self.at_op("*", "/"):
            op = self.take()[1]
            node = (op, node, self.unary(depth))
        return node

    def unary(self, depth):
        if self.at_op("-", "+"):
            op = self.take()[1]
            operand = self.unary(depth)
            return ("neg", operand) if op == "-" else operand
        return self.atom(depth)

    def atom(self, depth):
        token = self.take()
        if token is None:
            raise CalcError("The formula ends too early.", self.size)
        kind, value, pos = token
        if kind == "num":
            return ("num", value)
        if kind == "name":
            return ("ref", value)
        if value == "(":
            if depth >= MAX_DEPTH:
                raise CalcError("Too many nested parentheses.", pos)
            node = self.expr(depth + 1)
            closing = self.take()
            if closing is None or closing[1] != ")":
                raise CalcError("A parenthesis is not closed.", pos)
            return node
        raise CalcError("Unexpected '%s'. Use numbers, measure ids, + - * / and parentheses." % value, pos)


def parse(text):
    """The formula as a tree, or ``CalcError``."""
    if not isinstance(text, str):
        raise CalcError("The formula must be text.", 0)
    if len(text) > MAX_CHARS:
        raise CalcError("The formula is longer than %d characters." % MAX_CHARS, MAX_CHARS)
    return _Parser(_tokens(text), len(text)).parse()


def names(tree):
    """The measure ids the formula uses."""
    kind = tree[0]
    if kind == "ref":
        return {tree[1]}
    if kind == "num":
        return set()
    return set().union(*(names(child) for child in tree[1:]))


def operators(tree):
    """The operator symbols the formula uses (``neg`` for unary minus)."""
    kind = tree[0]
    if kind in ("ref", "num"):
        return set()
    return {kind}.union(*(operators(child) for child in tree[1:]))


def evaluate(tree, values):
    """Value of the formula; ``values`` maps a measure id to a number or ``None``. ``None`` when it has no value."""
    kind = tree[0]
    if kind == "num":
        return tree[1]
    if kind == "ref":
        value = values.get(tree[1])
        return None if value is None or isinstance(value, bool) else float(value)
    if kind == "neg":
        inner = evaluate(tree[1], values)
        return None if inner is None else -inner
    left, right = evaluate(tree[1], values), evaluate(tree[2], values)
    if left is None or right is None:
        return None
    if kind == "+":
        return left + right
    if kind == "-":
        return left - right
    if kind == "*":
        return left * right
    return None if right == 0 else left / right
