"""Daemon service control page — status, start/stop/restart, and live logs."""
from __future__ import annotations
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from daemon import service as svc


class ServicePage(Gtk.Box):
    """Shows the systemd service status and controls, plus a live log viewer."""

    def __init__(self, toast_overlay: Adw.ToastOverlay):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._toast = toast_overlay
        self._polling = False
        self._build()
        self._start_polling()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(20)
        content.set_margin_bottom(20)

        # ---- Status card -----------------------------------------
        status_group = Adw.PreferencesGroup(title="Daemon Status")

        # Status row
        status_row = Adw.ActionRow(title="g11-macro-daemon")
        status_row.set_subtitle("systemd user service")

        self._status_badge = Gtk.Label(label="Checking…")
        self._status_badge.add_css_class("status-badge")
        status_row.add_suffix(self._status_badge)
        status_group.add(status_row)

        # Auto-start row
        self._autostart_row = Adw.SwitchRow(
            title="Start on Login",
            subtitle="Enable the service with systemctl --user enable",
        )
        self._autostart_row.connect("notify::active", self._on_autostart_toggled)
        status_group.add(self._autostart_row)

        content.append(status_group)

        # ---- Control buttons -------------------------------------
        ctrl_group = Adw.PreferencesGroup(title="Controls")

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(4)
        btn_row.set_margin_bottom(4)
        btn_row.set_halign(Gtk.Align.CENTER)

        self._start_btn = Gtk.Button(label="Start")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.set_icon_name("media-playback-start-symbolic")
        self._start_btn.connect("clicked", lambda *_: self._run_cmd(svc.start, "Service started"))

        self._stop_btn = Gtk.Button(label="Stop")
        self._stop_btn.add_css_class("destructive-action")
        self._stop_btn.set_icon_name("media-playback-stop-symbolic")
        self._stop_btn.connect("clicked", lambda *_: self._run_cmd(svc.stop, "Service stopped"))

        self._restart_btn = Gtk.Button(label="Restart")
        self._restart_btn.set_icon_name("view-refresh-symbolic")
        self._restart_btn.connect("clicked", lambda *_: self._run_cmd(svc.restart, "Service restarted"))

        for btn in (self._start_btn, self._stop_btn, self._restart_btn):
            btn_row.append(btn)

        # Wrap in a plain row
        btn_holder = Adw.ActionRow()
        btn_holder.set_child(btn_row)
        ctrl_group.add(btn_holder)

        content.append(ctrl_group)

        # ---- Log viewer ------------------------------------------
        log_group = Adw.PreferencesGroup(title="Recent Logs")

        log_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        log_toolbar.set_margin_bottom(4)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda *_: self._refresh_logs())
        log_toolbar.append(refresh_btn)

        copy_btn = Gtk.Button(label="Copy All")
        copy_btn.add_css_class("flat")
        copy_btn.set_icon_name("edit-copy-symbolic")
        copy_btn.connect("clicked", self._on_copy_logs)
        log_toolbar.append(copy_btn)

        n_lines_label = Gtk.Label(label="Lines:")
        n_lines_label.add_css_class("dimmed")
        n_lines_label.set_margin_start(8)
        log_toolbar.append(n_lines_label)

        self._lines_spin = Gtk.SpinButton.new_with_range(20, 500, 20)
        self._lines_spin.set_value(100)
        self._lines_spin.connect("value-changed", lambda *_: self._refresh_logs())
        log_toolbar.append(self._lines_spin)

        content.append(log_toolbar)

        self._log_buffer = Gtk.TextBuffer()
        log_view = Gtk.TextView.new_with_buffer(self._log_buffer)
        log_view.set_editable(False)
        log_view.set_cursor_visible(False)
        log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_view.add_css_class("log-view")

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(300)
        log_scroll.set_vexpand(True)
        log_scroll.set_child(log_view)
        self._log_scroll = log_scroll
        self._log_view = log_view

        content.append(log_scroll)

        scroll.set_child(content)
        self.append(scroll)

        # Initial state
        self._refresh_logs()
        self._refresh_enabled_state()

    # ------------------------------------------------------------------
    # Status polling
    # ------------------------------------------------------------------

    def _start_polling(self):
        self._polling = True
        GLib.timeout_add_seconds(3, self._poll_status)
        self._poll_status()

    def _poll_status(self) -> bool:
        """Called by GLib timer; returns True to keep polling."""
        status = svc.get_status()
        GLib.idle_add(self._update_status_badge, status)
        return self._polling

    def _update_status_badge(self, status: svc.ServiceStatus):
        badge = self._status_badge
        # Remove old classes
        for cls in ("status-running", "status-stopped", "status-failed"):
            badge.remove_css_class(cls)

        if status == svc.ServiceStatus.Running:
            badge.set_label("● Running")
            badge.add_css_class("status-running")
            self._start_btn.set_sensitive(False)
            self._stop_btn.set_sensitive(True)
            self._restart_btn.set_sensitive(True)
        elif status == svc.ServiceStatus.Failed:
            badge.set_label("✕ Failed")
            badge.add_css_class("status-failed")
            self._start_btn.set_sensitive(True)
            self._stop_btn.set_sensitive(False)
            self._restart_btn.set_sensitive(True)
        else:
            badge.set_label("○ Stopped")
            badge.add_css_class("status-stopped")
            self._start_btn.set_sensitive(True)
            self._stop_btn.set_sensitive(False)
            self._restart_btn.set_sensitive(False)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _run_cmd(self, cmd, success_msg: str):
        def _do():
            ok, err = cmd()
            GLib.idle_add(self._on_cmd_result, ok, err, success_msg)
        threading.Thread(target=_do, daemon=True).start()

    def _on_cmd_result(self, ok: bool, err: str, success_msg: str):
        if ok:
            self._show_toast(success_msg)
        else:
            self._show_toast(f"Error: {err or 'unknown'}", timeout=5)
        self._poll_status()
        self._refresh_logs()

    def _on_autostart_toggled(self, row, _param):
        if row.get_active():
            ok, err = svc.enable()
            msg = "Auto-start enabled" if ok else f"Enable failed: {err}"
        else:
            ok, err = svc.disable()
            msg = "Auto-start disabled" if ok else f"Disable failed: {err}"
        self._show_toast(msg)

    def _refresh_enabled_state(self):
        enabled = svc.is_enabled()
        self._autostart_row.set_active(enabled)

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def _refresh_logs(self):
        n = int(self._lines_spin.get_value())
        def _do():
            text = svc.get_logs(n)
            GLib.idle_add(self._set_log_text, text)
        threading.Thread(target=_do, daemon=True).start()

    def _set_log_text(self, text: str):
        self._log_buffer.set_text(text)
        # Scroll to end
        end_iter = self._log_buffer.get_end_iter()
        self._log_view.scroll_to_iter(end_iter, 0, False, 0, 0)

    def _on_copy_logs(self, _btn):
        text = self._log_buffer.get_text(
            self._log_buffer.get_start_iter(),
            self._log_buffer.get_end_iter(),
            False,
        )
        clipboard = self.get_clipboard()
        clipboard.set(text)
        self._show_toast("Logs copied to clipboard")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_toast(self, message: str, timeout: int = 2):
        toast = Adw.Toast(title=message, timeout=timeout)
        self._toast.add_toast(toast)

    def stop_polling(self):
        self._polling = False
