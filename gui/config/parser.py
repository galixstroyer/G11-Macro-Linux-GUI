"""RON (Rusty Object Notation) parser and serializer for g11-macro config files.

Only the subset of RON used by g11-macro is supported.
"""
from __future__ import annotations
from dataclasses import dataclass

from .models import (
    Direction, Axis, Coordinate, MouseButton,
    KeyValue, KeyBinding,
    StepKey, StepText, StepButton, StepMoveMouse, StepScroll, StepRun, Step,
)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass
class Token:
    type: str   # IDENT | STRING | CHAR | NUMBER | LPAREN | RPAREN | LBRACKET | RBRACKET | COMMA | COLON
    value: str
    pos: int


class TokenizeError(Exception):
    pass


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    n = len(text)

    while pos < n:
        c = text[pos]

        # Whitespace
        if c.isspace():
            pos += 1
            continue

        # Line comment
        if text[pos:pos + 2] == "//":
            while pos < n and text[pos] != "\n":
                pos += 1
            continue

        # Block comment
        if text[pos:pos + 2] == "/*":
            end = text.find("*/", pos + 2)
            pos = (end + 2) if end != -1 else n
            continue

        # Header directive  #![...]
        if text[pos:pos + 3] == "#![":
            end = text.find("]", pos + 3)
            pos = (end + 1) if end != -1 else n
            continue

        # String literal
        if c == '"':
            end = pos + 1
            while end < n:
                if text[end] == "\\" and end + 1 < n:
                    end += 2
                elif text[end] == '"':
                    break
                else:
                    end += 1
            raw = text[pos + 1:end]
            value = (raw
                     .replace('\\"', '"')
                     .replace("\\\\", "\\")
                     .replace("\\n", "\n")
                     .replace("\\t", "\t")
                     .replace("\\r", "\r"))
            tokens.append(Token("STRING", value, pos))
            pos = end + 1
            continue

        # Char literal
        if c == "'":
            end = pos + 1
            if end < n and text[end] == "\\":
                end += 2   # escaped char
            elif end < n:
                end += 1   # normal char
            if end < n and text[end] == "'":
                raw = text[pos + 1:end]
                char_map = {"\\'": "'", "\\\\": "\\", "\\n": "\n", "\\t": "\t", "\\r": "\r"}
                char_value = char_map.get(raw, raw)
                tokens.append(Token("CHAR", char_value, pos))
                pos = end + 1
                continue
            # Not a valid char literal — skip
            pos += 1
            continue

        # Number (with optional leading minus)
        if c.isdigit() or (c == "-" and pos + 1 < n and text[pos + 1].isdigit()):
            end = pos + (1 if c == "-" else 0) + 1
            while end < n and text[end].isdigit():
                end += 1
            tokens.append(Token("NUMBER", text[pos:end], pos))
            pos = end
            continue

        # Identifier
        if c.isalpha() or c == "_":
            end = pos + 1
            while end < n and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(Token("IDENT", text[pos:end], pos))
            pos = end
            continue

        # Single-char punctuation
        punct = {"(": "LPAREN", ")": "RPAREN", "[": "LBRACKET", "]": "RBRACKET", ",": "COMMA", ":": "COLON"}
        if c in punct:
            tokens.append(Token(punct[c], c, pos))

        pos += 1

    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token | None:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def consume(self, type_: str | None = None, value: str | None = None) -> Token:
        tok = self.peek()
        if tok is None:
            raise ParseError("Unexpected end of input")
        if type_ and tok.type != type_:
            raise ParseError(f"Expected {type_!r}, got {tok.type!r} ({tok.value!r}) at pos {tok.pos}")
        if value and tok.value != value:
            raise ParseError(f"Expected {value!r}, got {tok.value!r} at pos {tok.pos}")
        self.pos += 1
        return tok

    def try_consume(self, type_: str | None = None, value: str | None = None) -> Token | None:
        tok = self.peek()
        if tok is None:
            return None
        if type_ and tok.type != type_:
            return None
        if value and tok.value != value:
            return None
        self.pos += 1
        return tok

    # -----------------------------------------------------------------------

    def parse_file(self) -> list[KeyBinding]:
        """Parse the top-level list of KeyBinding entries."""
        has_bracket = self.try_consume("LBRACKET")
        bindings = self._parse_binding_list()
        if has_bracket:
            self.try_consume("RBRACKET")
        return bindings

    def _parse_binding_list(self) -> list[KeyBinding]:
        bindings = []
        while self.peek() and not (self.peek().type == "RBRACKET"):
            if self.peek().type == "IDENT" and self.peek().value == "KeyBinding":
                bindings.append(self._parse_binding())
                self.try_consume("COMMA")
            else:
                self.pos += 1  # skip unexpected token
        return bindings

    def _parse_binding(self) -> KeyBinding:
        self.consume("IDENT", "KeyBinding")
        self.consume("LPAREN")

        m = g = on = None
        script: list[Step] = []

        while self.peek() and self.peek().type != "RPAREN":
            if self.peek().type != "IDENT":
                self.pos += 1
                continue
            field = self.consume("IDENT")
            self.consume("COLON")

            if field.value == "m":
                m = int(self.consume("NUMBER").value)
            elif field.value == "g":
                g = int(self.consume("NUMBER").value)
            elif field.value == "on":
                on = Direction(self.consume("IDENT").value)
            elif field.value == "script":
                script = self._parse_script()
            else:
                self._skip_value()

            self.try_consume("COMMA")

        self.consume("RPAREN")

        if m is None or g is None or on is None:
            raise ParseError(f"Incomplete KeyBinding: m={m}, g={g}, on={on}")

        return KeyBinding(m=m, g=g, on=on, script=script)

    def _parse_script(self) -> list[Step]:
        self.consume("LBRACKET")
        steps: list[Step] = []

        while self.peek() and self.peek().type != "RBRACKET":
            if self.peek().type == "IDENT":
                step = self._parse_step()
                if step is not None:
                    steps.append(step)
                self.try_consume("COMMA")
            else:
                self.pos += 1

        self.consume("RBRACKET")
        return steps

    def _parse_step(self) -> Step | None:
        name = self.consume("IDENT")
        self.consume("LPAREN")
        step = None

        if name.value == "Key":
            key = self._parse_key_value()
            self.consume("COMMA")
            direction = Direction(self.consume("IDENT").value)
            step = StepKey(key=key, direction=direction)

        elif name.value == "Text":
            text = self.consume("STRING").value
            step = StepText(text=text)

        elif name.value == "Button":
            button = MouseButton(self.consume("IDENT").value)
            self.consume("COMMA")
            direction = Direction(self.consume("IDENT").value)
            step = StepButton(button=button, direction=direction)

        elif name.value == "MoveMouse":
            x = int(self.consume("NUMBER").value)
            self.consume("COMMA")
            y = int(self.consume("NUMBER").value)
            self.consume("COMMA")
            coordinate = Coordinate(self.consume("IDENT").value)
            step = StepMoveMouse(x=x, y=y, coordinate=coordinate)

        elif name.value == "Scroll":
            magnitude = int(self.consume("NUMBER").value)
            self.consume("COMMA")
            axis = Axis(self.consume("IDENT").value)
            step = StepScroll(magnitude=magnitude, axis=axis)

        elif name.value == "Run":
            self.consume("IDENT", "Program")
            self.consume("LPAREN")
            program = self.consume("STRING").value
            args: list[str] = []
            if self.try_consume("COMMA"):
                self.consume("LBRACKET")
                while self.peek() and self.peek().type != "RBRACKET":
                    args.append(self.consume("STRING").value)
                    self.try_consume("COMMA")
                self.consume("RBRACKET")
            self.consume("RPAREN")  # close Program(
            step = StepRun(program=program, args=args)

        else:
            # Unknown step — skip balanced parens
            self._skip_balanced("LPAREN", "RPAREN", already_open=True)
            return None

        self.consume("RPAREN")  # close Step(
        return step

    def _parse_key_value(self) -> KeyValue:
        name = self.consume("IDENT")
        if name.value == "Unicode":
            self.consume("LPAREN")
            char = self.consume("CHAR").value
            self.consume("RPAREN")
            return KeyValue.unicode(char)
        return KeyValue.named(name.value)

    def _skip_value(self):
        """Skip a single value of unknown type."""
        tok = self.peek()
        if tok is None:
            return
        if tok.type in ("STRING", "NUMBER", "CHAR", "IDENT"):
            self.pos += 1
            return
        if tok.type == "LPAREN":
            self.pos += 1
            self._skip_balanced("LPAREN", "RPAREN", already_open=True)
            return
        if tok.type == "LBRACKET":
            self.pos += 1
            self._skip_balanced("LBRACKET", "RBRACKET", already_open=True)
            return

    def _skip_balanced(self, open_t: str, close_t: str, already_open: bool = False):
        depth = 1 if already_open else 0
        while self.peek():
            t = self.peek().type
            if t == open_t:
                depth += 1
            elif t == close_t:
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    return
            self.pos += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_bindings(text: str) -> list[KeyBinding]:
    """Parse a RON key_bindings file and return a list of KeyBinding objects."""
    tokens = tokenize(text)
    return Parser(tokens).parse_file()


def serialize_bindings(bindings: list[KeyBinding]) -> str:
    """Serialize a list of KeyBinding objects back to RON format."""
    lines = ["#![enable(explicit_struct_names, implicit_some)]", "["]
    for b in bindings:
        lines.append("    KeyBinding(")
        lines.append(f"        m: {b.m},")
        lines.append(f"        g: {b.g},")
        lines.append(f"        on: {b.on.value},")
        lines.append("        script: [")
        for step in b.script:
            count = step.repeat if isinstance(step, StepKey) else 1
            ron   = _step_to_ron(step)
            for _ in range(max(1, count)):
                lines.append(f"            {ron},")
        lines.append("        ],")
        lines.append("    ),")
    lines.append("]")
    return "\n".join(lines) + "\n"


def _step_to_ron(step: Step) -> str:
    if isinstance(step, StepKey):
        return f"Key({step.key.to_ron()}, {step.direction.value})"
    if isinstance(step, StepText):
        escaped = step.text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return f'Text("{escaped}")'
    if isinstance(step, StepButton):
        return f"Button({step.button.value}, {step.direction.value})"
    if isinstance(step, StepMoveMouse):
        return f"MoveMouse({step.x}, {step.y}, {step.coordinate.value})"
    if isinstance(step, StepScroll):
        return f"Scroll({step.magnitude}, {step.axis.value})"
    if isinstance(step, StepRun):
        if step.args:
            args_ron = ", ".join(f'"{a.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"' for a in step.args)
            return f'Run(Program("{step.program}", [{args_ron}]))'
        return f'Run(Program("{step.program}"))'
    raise TypeError(f"Unknown step type: {type(step)}")
