"""Interface to the g11-macro-daemon service.

Supports systemd (systemctl/journalctl), runit (sv/svstat),
and direct process management as a fallback.
"""
from __future__ import annotations
import os
import signal
import shutil
import subprocess
from enum import Enum
from pathlib import Path


SERVICE = "g11-macro-daemon"
DAEMON_BIN = "g11-macro-daemon"


class ServiceStatus(Enum):
    Running = "running"
    Stopped = "stopped"
    Failed  = "failed"
    Unknown = "unknown"


# ── Detect available init system ──────────────────────────────────────────────

_HAS_SYSTEMCTL = shutil.which("systemctl") is not None
_HAS_SV = shutil.which("sv") is not None


def get_backend_name() -> str:
    """Return a human-readable name for the active service backend."""
    if _HAS_SYSTEMCTL:
        return "systemd"
    if _HAS_SV:
        return "runit"
    return "direct"


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


def _find_daemon_bin() -> str | None:
    """Find the daemon binary path."""
    # Check common locations
    home = Path.home()
    for path in [
        home / ".cargo" / "bin" / DAEMON_BIN,
        Path(f"/usr/local/bin/{DAEMON_BIN}"),
        Path(f"/usr/bin/{DAEMON_BIN}"),
    ]:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    # Fall back to PATH
    return shutil.which(DAEMON_BIN)


def _get_daemon_pid() -> int | None:
    """Find the PID of a running daemon process (direct mode)."""
    try:
        result = subprocess.run(
            ["pgrep", "-u", str(os.getuid()), "-x", DAEMON_BIN],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().splitlines()[0])
    except (FileNotFoundError, ValueError):
        pass
    return None


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
    # Direct mode: check if process is running
    if _get_daemon_pid() is not None:
        return ServiceStatus.Running
    return ServiceStatus.Stopped


# ── Control ───────────────────────────────────────────────────────────────────

def start() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "start", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    if _HAS_SV:
        r = _run("sv", "start", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    # Direct mode: launch the daemon as a background process
    daemon_bin = _find_daemon_bin()
    if not daemon_bin:
        return False, f"Could not find {DAEMON_BIN} binary"
    if _get_daemon_pid() is not None:
        return False, "Daemon is already running"
    try:
        env = os.environ.copy()
        env.setdefault("RUST_LOG", "WARN,g11=INFO")
        subprocess.Popen(
            [daemon_bin],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, ""
    except Exception as e:
        return False, str(e)


def stop() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "stop", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    if _HAS_SV:
        r = _run("sv", "stop", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    # Direct mode: send SIGTERM
    pid = _get_daemon_pid()
    if pid is None:
        return False, "Daemon is not running"
    try:
        os.kill(pid, signal.SIGTERM)
        return True, ""
    except ProcessLookupError:
        return False, "Daemon already stopped"
    except PermissionError:
        return False, "Permission denied"


def restart() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "restart", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    if _HAS_SV:
        r = _run("sv", "restart", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    # Direct mode: stop then start
    pid = _get_daemon_pid()
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait briefly for it to die
            import time
            for _ in range(10):
                time.sleep(0.1)
                if _get_daemon_pid() is None:
                    break
        except (ProcessLookupError, PermissionError):
            pass
    return start()


def enable() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "enable", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    if _HAS_SV:
        return False, "Auto-start must be configured manually on runit"
    return False, "No init system available — start the daemon manually or add it to your session startup"


def disable() -> tuple[bool, str]:
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "disable", SERVICE)
        return r.returncode == 0, r.stderr.strip() or r.stdout.strip()
    if _HAS_SV:
        return False, "Auto-start must be configured manually on runit"
    return False, "No init system available"


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
    # runit / direct: try common log locations
    for log_path in [
        Path.home() / ".config" / "sv" / SERVICE / "log" / "main" / "current",
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
    if not _HAS_SYSTEMCTL and not _HAS_SV:
        return "(no logs — daemon is running in direct mode without log capture)"
    return "(no logs found — logs may be at a non-standard location)"


def get_status_detail() -> str:
    """Return full status output."""
    if _HAS_SYSTEMCTL:
        r = _run("systemctl", "--user", "status", "--no-pager", SERVICE)
        return r.stdout or r.stderr or "(no output)"
    if _HAS_SV:
        r = _run("sv", "status", SERVICE)
        return r.stdout or r.stderr or "(no output)"
    pid = _get_daemon_pid()
    if pid:
        return f"g11-macro-daemon is running (PID {pid})"
    return "g11-macro-daemon is not running"
