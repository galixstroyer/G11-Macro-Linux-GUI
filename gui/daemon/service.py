"""Interface to the g11-macro-daemon service.

Supports systemd (systemctl/journalctl) and runit (sv/svstat).
Falls back gracefully when neither is available.
"""
from __future__ import annotations
import shutil
import subprocess
from enum import Enum


SERVICE = "g11-macro-daemon"


class ServiceStatus(Enum):
    Running = "running"
    Stopped = "stopped"
    Failed  = "failed"
    Unknown = "unknown"


# ── Detect available init system ──────────────────────────────────────────────

_HAS_SYSTEMCTL = shutil.which("systemctl") is not None
_HAS_SV = shutil.which("sv") is not None


def _run(*args: str) -> subprocess.CompletedProcess:
    """Run a command, returning a CompletedProcess. Never raises on missing binary."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, returncode=127, stdout="", stderr="command not found")


# ── Status ────────────────────────────────────────────────────────────────────

def get_status() -> ServiceStatus:
    if _HAS_SYSTEMCTL:
        result = _run("systemctl", "--user", "is-active", SERVICE)
        state = result.stdout.strip()
        if state == "active":
            return ServiceStatus.Running
        if state == "failed":
            return ServiceStatus.Failed
        return ServiceStatus.Stopped
    if _HAS_SV:
        result = _run("sv", "status", SERVICE)
        output = result.stdout.strip().lower()
        if output.startswith("run:"):
            return ServiceStatus.Running
        if "fail" in output or "unable" in output:
            return ServiceStatus.Failed
        return ServiceStatus.Stopped
    return ServiceStatus.Unknown


# ── Control ───────────────────────────────────────────────────────────────────

def start() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "start", SERVICE)
    elif _HAS_SV:
        r = _run("sv", "start", SERVICE)
    else:
        return False, "No supported init system found (systemd or runit)"
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def stop() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "stop", SERVICE)
    elif _HAS_SV:
        r = _run("sv", "stop", SERVICE)
    else:
        return False, "No supported init system found (systemd or runit)"
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def restart() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "restart", SERVICE)
    elif _HAS_SV:
        r = _run("sv", "restart", SERVICE)
    else:
        return False, "No supported init system found (systemd or runit)"
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def enable() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "enable", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    # runit services are enabled by symlinking into the service directory;
    # this is system-specific so we don't attempt it automatically.
    return False, "Auto-start must be configured manually on runit"


def disable() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "disable", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    return False, "Auto-start must be configured manually on runit"


def is_enabled() -> bool:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "is-enabled", SERVICE)
        return r.stdout.strip() == "enabled"
    return False


# ── Logs ──────────────────────────────────────────────────────────────────────

def get_logs(lines: int = 100) -> str:
    """Return the last N log lines."""
    if _HAS_SYSTEMCTL:
        result = _run(
            "journalctl", "--user", "-u", SERVICE,
            "-n", str(lines), "--no-pager", "--output=short",
        )
        return result.stdout or result.stderr or "(no logs)"
    # runit: try common log locations
    import os
    from pathlib import Path
    for log_path in [
        Path.home() / ".config" / "sv" / SERVICE / "log" / "current",
        Path(f"/var/log/sv/{SERVICE}/current"),
        Path(f"/var/log/{SERVICE}/current"),
    ]:
        if log_path.exists():
            try:
                all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                return "\n".join(all_lines[-lines:]) or "(empty log)"
            except Exception as e:
                return f"(could not read {log_path}: {e})"
    return "(no logs found — logs may be at a non-standard location)"


def get_status_detail() -> str:
    """Return full status output."""
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "status", "--no-pager", SERVICE)
        return r.stdout or r.stderr or "(no output)"
    if _HAS_SV:
        r = _run("sv", "status", SERVICE)
        return r.stdout or r.stderr or "(no output)"
    return "(no supported init system found)"
