"""Data models for G11 macro configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Union


class Direction(Enum):
    Press = "Press"
    Release = "Release"
    Click = "Click"


class Axis(Enum):
    Vertical = "Vertical"
    Horizontal = "Horizontal"


class Coordinate(Enum):
    Abs = "Abs"
    Rel = "Rel"


class MouseButton(Enum):
    Left = "Left"
    Right = "Right"
    Middle = "Middle"
    Back = "Back"
    Forward = "Forward"


# All named enigo Key variants (non-unicode)
NAMED_KEYS = [
    "Alt", "CapsLock", "Control", "LControl", "RControl",
    "Shift", "LShift", "RShift", "Meta",
    "DownArrow", "LeftArrow", "RightArrow", "UpArrow",
    "End", "Home", "PageDown", "PageUp",
    "F1", "F2", "F3", "F4", "F5", "F6",
    "F7", "F8", "F9", "F10", "F11", "F12",
    "Backspace", "Delete", "Escape", "Insert", "Return", "Space", "Tab",
    "Numlock", "ScrollLock", "Pause", "PrintScr",
    "Numpad0", "Numpad1", "Numpad2", "Numpad3", "Numpad4",
    "Numpad5", "Numpad6", "Numpad7", "Numpad8", "Numpad9",
    "Add", "Decimal", "Divide", "Multiply", "Subtract",
    "LMenu",
]


@dataclass
class KeyValue:
    """Represents a key in a Key step — either a named key or a Unicode character."""
    is_unicode: bool
    value: str  # named key string OR single unicode character

    @classmethod
    def named(cls, name: str) -> KeyValue:
        return cls(is_unicode=False, value=name)

    @classmethod
    def unicode(cls, char: str) -> KeyValue:
        return cls(is_unicode=True, value=char)

    def to_ron(self) -> str:
        if self.is_unicode:
            c = self.value
            if c == "'":
                c = "\\'"
            elif c == "\\":
                c = "\\\\"
            elif c == "\n":
                c = "\\n"
            elif c == "\t":
                c = "\\t"
            return f"Unicode('{c}')"
        return self.value

    def display(self) -> str:
        if self.is_unicode:
            c = self.value
            if c == "\n":
                return "'\\n'"
            if c == "\t":
                return "'\\t'"
            return f"'{c}'"
        return self.value


@dataclass
class StepKey:
    key: KeyValue
    direction: Direction
    repeat: int = 1

    def display(self) -> str:
        suffix = f" ×{self.repeat}" if self.repeat > 1 else ""
        return f"Key {self.key.display()} [{self.direction.value}]{suffix}"

    def icon(self) -> str:
        return "input-keyboard-symbolic"


@dataclass
class StepText:
    text: str

    def display(self) -> str:
        preview = self.text[:28] + "…" if len(self.text) > 28 else self.text
        return f'Type "{preview}"'

    def icon(self) -> str:
        return "format-text-rich-symbolic"


@dataclass
class StepButton:
    button: MouseButton
    direction: Direction

    def display(self) -> str:
        return f"Mouse {self.button.value} [{self.direction.value}]"

    def icon(self) -> str:
        return "input-mouse-symbolic"


@dataclass
class StepMoveMouse:
    x: int
    y: int
    coordinate: Coordinate

    def display(self) -> str:
        mode = "Abs" if self.coordinate == Coordinate.Abs else "Rel"
        return f"Move Mouse ({self.x}, {self.y}) {mode}"

    def icon(self) -> str:
        return "input-mouse-symbolic"


@dataclass
class StepScroll:
    magnitude: int
    axis: Axis

    def display(self) -> str:
        if self.axis == Axis.Vertical:
            direction = "Up" if self.magnitude > 0 else "Down"
        else:
            direction = "Right" if self.magnitude > 0 else "Left"
        return f"Scroll {direction} ×{abs(self.magnitude)}"

    def icon(self) -> str:
        return "input-mouse-symbolic"


@dataclass
class StepRun:
    program: str
    args: list[str] = field(default_factory=list)

    def display(self) -> str:
        if self.args:
            args_preview = " ".join(self.args[:2])
            suffix = "…" if len(self.args) > 2 else ""
            return f"Run {self.program} {args_preview}{suffix}"
        return f"Run {self.program}"

    def icon(self) -> str:
        return "application-x-executable-symbolic"


Step = Union[StepKey, StepText, StepButton, StepMoveMouse, StepScroll, StepRun]

STEP_TYPE_LABELS = {
    "Key":       "Key Stroke",
    "Text":      "Type Text",
    "Button":    "Mouse Button",
    "MoveMouse": "Move Mouse",
    "Scroll":    "Scroll",
    "Run":       "Run Program",
}


def step_type_name(step: Step) -> str:
    return type(step).__name__.replace("Step", "")


@dataclass
class KeyBinding:
    m: int           # 1–3
    g: int           # 1–18
    on: Direction    # Press or Release
    script: list[Step] = field(default_factory=list)

    @property
    def key_id(self) -> tuple[int, int]:
        return (self.m, self.g)

    def summary(self) -> str:
        if not self.script:
            return "Empty macro"
        parts = [s.display() for s in self.script[:2]]
        if len(self.script) > 2:
            parts.append(f"+{len(self.script) - 2} more")
        return " → ".join(parts)
