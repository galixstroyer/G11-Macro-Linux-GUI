"""The main Macros page: keyboard widget + macro editor side by side."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config.models import KeyBinding
from config import manager as cfg_mgr
from .keyboard_widget import KeyboardWidget
from .macro_editor import MacroEditorPanel


class MacrosPage(Gtk.Box):
    """
    The main page of the app.
    Left pane: keyboard widget with G-key grid.
    Right pane: macro editor for the selected key.
    """

    def __init__(self, toast_overlay: Adw.ToastOverlay):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._toast = toast_overlay

        # All loaded bindings keyed by (m, g)
        self._bindings: dict[tuple[int, int], KeyBinding] = {}
        # Recorded macros (read-only display)
        self._recordings: dict[tuple[int, int], KeyBinding] = {}

        self._selected_m: int = 1
        self._selected_g: int | None = None

        self._build()
        self._load_config()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        # Top toolbar
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tb.set_margin_start(12)
        tb.set_margin_end(12)
        tb.set_margin_top(10)
        tb.set_margin_bottom(6)

        title = Gtk.Label(label="Macro Keys")
        title.add_css_class("title-3")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        tb.append(title)

        reload_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text("Reload config from disk")
        reload_btn.add_css_class("flat")
        reload_btn.connect("clicked", lambda *_: self._load_config())
        tb.append(reload_btn)

        edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        edit_btn.set_tooltip_text("Open key_bindings.ron in text editor")
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", self._on_open_editor)
        tb.append(edit_btn)

        self.append(tb)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(sep)

        # Main split pane
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(460)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)

        # ----- Left: keyboard + recordings notice -------------------
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        scroll_left = Gtk.ScrolledWindow()
        scroll_left.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_left.set_vexpand(True)

        left_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._keyboard = KeyboardWidget()
        self._keyboard.connect("g-key-activated", self._on_g_key)
        self._keyboard.connect("m-key-activated", self._on_m_key)
        left_inner.append(self._keyboard)

        # Recordings info banner (shown when recordings exist)
        self._rec_banner = Adw.Banner(
            title="Recorded macros exist — they override key_bindings.ron",
        )
        self._rec_banner.set_button_label("View")
        self._rec_banner.connect("button-clicked", self._on_view_recordings)
        self._rec_banner.set_revealed(False)
        left_inner.append(self._rec_banner)

        scroll_left.set_child(left_inner)
        left_box.append(scroll_left)
        paned.set_start_child(left_box)

        # ----- Right: macro editor ----------------------------------
        self._editor = MacroEditorPanel()
        self._editor.connect("binding-changed", self._on_binding_changed)

        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right_scroll.set_child(self._editor)
        paned.set_end_child(right_scroll)

        self.append(paned)

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def _load_config(self):
        cfg_mgr.ensure_config_dir()

        bindings, err = cfg_mgr.load_bindings()
        if err:
            self._show_toast(f"Config error: {err}", timeout=5)
        self._bindings = {b.key_id: b for b in bindings}

        recordings, _ = cfg_mgr.load_recordings()
        self._recordings = {b.key_id: b for b in recordings}

        self._rec_banner.set_revealed(bool(self._recordings))
        self._refresh_keyboard()

        # Re-load the currently selected key if any
        if self._selected_g is not None:
            self._open_editor(self._selected_m, self._selected_g)

        self._show_toast("Config loaded")

    def _save_binding(self, binding: KeyBinding):
        """Upsert a binding and persist to disk."""
        self._bindings[binding.key_id] = binding
        all_bindings = list(self._bindings.values())
        err = cfg_mgr.save_bindings(all_bindings)
        if err:
            self._show_toast(f"Save failed: {err}", timeout=6)
        else:
            self._show_toast("Saved — restart daemon to apply")
            self._refresh_keyboard()

    # ------------------------------------------------------------------
    # Keyboard refresh
    # ------------------------------------------------------------------

    def _refresh_keyboard(self):
        macro_keys = set(self._bindings.keys()) | set(self._recordings.keys())
        self._keyboard.set_macro_keys(macro_keys)
        self._keyboard.set_active_bank(self._selected_m)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_g_key(self, _widget, g: int):
        self._selected_g = g
        self._open_editor(self._selected_m, g)

    def _on_m_key(self, _widget, m: int):
        self._selected_m = m
        self._selected_g = None
        self._editor.clear()
        self._refresh_keyboard()

    def _open_editor(self, m: int, g: int):
        # Recordings take precedence but are read-only; show bindings for editing
        key = (m, g)
        binding = self._bindings.get(key)  # may be None (new macro)
        self._editor.load_binding(binding, m, g)

    def _on_binding_changed(self, _editor, binding: KeyBinding):
        self._save_binding(binding)

    def _on_open_editor(self, _btn):
        cfg_mgr.open_in_editor(cfg_mgr.bindings_path())

    def _on_view_recordings(self, _banner):
        # Show recordings in a simple dialog
        dlg = Adw.AlertDialog(
            heading="Recorded Macros",
            body="These are in key_recordings.ron and override key_bindings.ron.\n\n"
                 + "\n".join(
                     f"M{b.m} G{b.g}: {b.summary()}"
                     for b in self._recordings.values()
                 ) or "(empty)",
        )
        dlg.add_response("ok", "OK")
        dlg.add_response("open", "Open File")
        dlg.connect("response", lambda d, r: cfg_mgr.open_in_editor(cfg_mgr.recordings_path()) if r == "open" else None)
        dlg.present(self)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_toast(self, message: str, timeout: int = 2):
        toast = Adw.Toast(title=message, timeout=timeout)
        self._toast.add_toast(toast)
