"""Config file management — paths, loading, and saving."""
from __future__ import annotations
import os
from pathlib import Path

from .models import KeyBinding
from .parser import parse_bindings, serialize_bindings

XDG_PREFIX      = "g11-macro-daemon"
BINDINGS_FILE   = "key_bindings.ron"
RECORDINGS_FILE = "key_recordings.ron"

_STUB = """\
#![enable(explicit_struct_names, implicit_some)]
[
//This file contains individual G key scripts as used by the g11-macro-daemon.
//Add your KeyBinding entries here and restart the daemon to apply them.


]
"""


def _config_dir() -> Path:
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg_config) / XDG_PREFIX


def bindings_path() -> Path:
    return _config_dir() / BINDINGS_FILE


def recordings_path() -> Path:
    return _config_dir() / RECORDINGS_FILE


def load_bindings() -> tuple[list[KeyBinding], str | None]:
    """
    Load key_bindings.ron.
    Returns (bindings, error_message). On success error_message is None.
    """
    path = bindings_path()
    if not path.exists():
        return [], None
    try:
        text = path.read_text(encoding="utf-8")
        return parse_bindings(text), None
    except Exception as e:
        return [], str(e)


def save_bindings(bindings: list[KeyBinding]) -> str | None:
    """
    Save key_bindings.ron.
    Returns error_message on failure, or None on success.
    """
    path = bindings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize_bindings(bindings), encoding="utf-8")
        return None
    except Exception as e:
        return str(e)


def load_recordings() -> tuple[list[KeyBinding], str | None]:
    """Load key_recordings.ron (read-only from the GUI)."""
    path = recordings_path()
    if not path.exists():
        return [], None
    try:
        text = path.read_text(encoding="utf-8")
        return parse_bindings(text), None
    except Exception as e:
        return [], str(e)


def ensure_config_dir() -> str | None:
    """Create the config directory and stub file if missing. Returns error or None."""
    try:
        path = bindings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(_STUB, encoding="utf-8")
        return None
    except Exception as e:
        return str(e)


def open_in_editor(file_path: Path):
    """Open a file in the user's default text editor via xdg-open."""
    import subprocess
    subprocess.Popen(["xdg-open", str(file_path)])
