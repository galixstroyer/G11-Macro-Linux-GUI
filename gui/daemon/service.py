"""Interface to the g11-macro-daemon systemd user service."""
from __future__ import annotations
import subprocess
from enum import Enum


SERVICE = "g11-macro-daemon"


class ServiceStatus(Enum):
    Running = "running"
    Stopped = "stopped"
    Failed  = "failed"
    Unknown = "unknown"


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
    )


def get_status() -> ServiceStatus:
    result = _systemctl("is-active", SERVICE)
    state = result.stdout.strip()
    if state == "active":
        return ServiceStatus.Running
    if state == "failed":
        return ServiceStatus.Failed
    return ServiceStatus.Stopped


def start() -> tuple[bool, str]:
    r = _systemctl("start", SERVICE)
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def stop() -> tuple[bool, str]:
    r = _systemctl("stop", SERVICE)
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def restart() -> tuple[bool, str]:
    r = _systemctl("restart", SERVICE)
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def enable() -> tuple[bool, str]:
    r = _systemctl("enable", SERVICE)
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def disable() -> tuple[bool, str]:
    r = _systemctl("disable", SERVICE)
    return r.returncode == 0, r.stderr.strip() or r.stdout.strip()


def is_enabled() -> bool:
    r = _systemctl("is-enabled", SERVICE)
    return r.stdout.strip() == "enabled"


def get_logs(lines: int = 100) -> str:
    """Return the last N log lines from journalctl."""
    result = subprocess.run(
        ["journalctl", "--user", "-u", SERVICE,
         "-n", str(lines), "--no-pager", "--output=short"],
        capture_output=True,
        text=True,
    )
    return result.stdout or result.stderr or "(no logs)"


def get_status_detail() -> str:
    """Return full systemctl status output."""
    r = _systemctl("status", "--no-pager", SERVICE)
    return r.stdout or r.stderr or "(no output)"
