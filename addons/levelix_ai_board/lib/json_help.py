"""Say where broken JSON is broken, in words a model can act on.

Models write specs as JSON text and the most common slip is one bracket too few or too many. Python's own message
("Expecting property name ... line 1 column 1064") gives them nothing to fix, so they resend the same mistake.
This names the place inside the spec (``widgets[0]``), shows the text around it and says what usually causes it.
"""
import json

MARKER = "<<HERE>>"


def scan(text, pos):
    """The containers still open at ``pos``: a list of ``["{", current key]`` / ``["[", current index]``."""
    stack = []
    in_string = escaped = False
    start = 0
    for i, char in enumerate(text[:pos]):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
                rest = text[i + 1:].lstrip()
                if stack and stack[-1][0] == "{" and rest.startswith(":"):
                    stack[-1][1] = text[start + 1:i]
            continue
        if char == '"':
            in_string, start = True, i
        elif char in "{[":
            stack.append([char, None if char == "{" else 0])
        elif char in "}]":
            if stack:
                stack.pop()
            if stack and stack[-1][0] == "{":
                stack[-1][1] = None  # the value of that key is finished
        elif char == "," and stack:
            if stack[-1][0] == "[":
                stack[-1][1] += 1
            else:
                stack[-1][1] = None  # the next key is not written yet
    return stack


def path_of(stack):
    """``widgets[0].data`` style, or ``the top level``."""
    path = ""
    for kind, key in stack:
        if kind == "[":
            path += "[%d]" % key
        elif key:
            path += ("." if path else "") + key
    return path or "the top level"


def open_path(text, pos):
    return path_of(scan(text, pos))


def explain(text, error):
    """A readable account of a ``json.loads`` failure."""
    if not isinstance(error, json.JSONDecodeError):
        return str(error)
    pos = min(error.pos, len(text))
    found = text[pos:pos + 1] or "the end of the text"
    near = "%s%s%s" % (text[max(0, pos - 50):pos], MARKER, text[pos:pos + 30])
    stack = scan(text, pos)
    where = path_of(stack)
    fix = ("This usually means a { or [ just before this point was closed with the wrong number of brackets "
           "or a comma is missing or extra.")
    open_one = path_of(stack[:-1])
    if stack and found in "}]" and found != ("}" if stack[-1][0] == "{" else "]"):
        closer, kind = ("}", "object") if stack[-1][0] == "{" else ("]", "list")
        fix = "The %s %s is still open here: insert a %s at %s, before the %s." % (kind, open_one, closer, MARKER, found)
    elif stack and found == "{" and stack[-1][0] == "{":
        fix = ("A new object starts here, but %s is an object, not a list, so it must be closed first: "
               "insert a } before the comma that comes just before %s.") % (open_one, MARKER)
    return (
        "%s at character %d (found %s), inside %s. Near: ...%s... %s Send the complete corrected spec again."
    ) % (error.msg, pos, found, where, near, fix)


def _closer_fix(text, error):
    """The text with one missing closing bracket put where it must go, or None when the slip is some other kind."""
    pos = min(error.pos, len(text))
    if error.msg.startswith("Unterminated") or pos < 0:
        return None
    stack = scan(text, pos)
    found = text[pos:pos + 1]
    if not found:  # the text ended with containers still open
        return text + "".join("}" if kind == "{" else "]" for kind, _key in reversed(stack)) if stack else None
    if stack and found in "}]" and found != ("}" if stack[-1][0] == "{" else "]"):
        return text[:pos] + ("}" if stack[-1][0] == "{" else "]") + text[pos:]
    if stack and found == "{" and stack[-1][0] == "{":  # "...}, {" where an object was left open
        comma = pos - 1
        while comma >= 0 and text[comma] in " \t\r\n":
            comma -= 1
        if comma >= 0 and text[comma] == ",":
            return text[:comma] + "}" + text[comma:]
    return None


def repair(text, attempts=3):
    """``(value, number of brackets added)`` when the only fault is closing brackets that are missing, else None.

    Models that write long JSON by hand drop a closing } or ] now and then, and some repeat the slip however clearly
    it is pointed out. The text is only ever completed, never changed, and what comes out still goes through the full
    check of the spec, so a wrong guess becomes an ordinary error instead of a wrong dashboard."""
    added = 0
    for _attempt in range(attempts + 1):
        try:
            return json.loads(text), added
        except json.JSONDecodeError as error:
            fixed = _closer_fix(text, error)
            if fixed is None:
                return None
            added += len(fixed) - len(text)
            text = fixed
    return None
