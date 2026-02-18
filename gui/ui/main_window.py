"""Main application window with sidebar navigation."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from .macros_page  import MacrosPage
from .service_page import ServicePage
from .led_page     import LedPage


_NAV_ITEMS = [
    ("Macros",  "input-keyboard-symbolic"),
    ("Service", "preferences-system-symbolic"),
    ("LEDs",    "display-brightness-symbolic"),
    ("About",   "help-about-symbolic"),
]


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("G11 Macro Manager")
        self.set_default_size(1100, 720)
        self.set_size_request(800, 560)

        self._service_page: ServicePage | None = None
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        # Root toast overlay (shared across all pages)
        self._toast_overlay = Adw.ToastOverlay()

        # Outer split: sidebar + content
        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # ---- Sidebar ---------------------------------------------
        sidebar = self._build_sidebar()
        split.append(sidebar)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        split.append(sep)

        # ---- Content stack ---------------------------------------
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)

        self._macros_page  = MacrosPage(self._toast_overlay)
        self._service_page = ServicePage(self._toast_overlay)
        self._led_page     = LedPage(self._toast_overlay)
        about_page         = self._build_about_page()

        self._stack.add_named(self._macros_page,  "macros")
        self._stack.add_named(self._service_page, "service")
        self._stack.add_named(self._led_page,     "leds")
        self._stack.add_named(about_page,         "about")

        split.append(self._stack)

        # Wrap in ToolbarView for header bar
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self._build_header())
        toolbar_view.set_content(split)

        self._toast_overlay.set_child(toolbar_view)
        self.set_content(self._toast_overlay)

        # Default page
        self._select_page(0)

        # Keyboard shortcut: Ctrl+R = restart daemon
        from gi.repository import Gdk
        shortcut_ctrl = Gtk.ShortcutController()
        shortcut_ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        trigger = Gtk.KeyvalTrigger.new(ord("r"), Gdk.ModifierType.CONTROL_MASK)
        action  = Gtk.NamedAction.new("app.restart-daemon")
        shortcut_ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))
        self.add_controller(shortcut_ctrl)

        # Register the action on the application
        restart_action = Gio.SimpleAction.new("restart-daemon", None)
        restart_action.connect("activate", lambda *_: self._service_page and
            self._service_page._run_cmd(
                __import__("daemon.service", fromlist=["restart"]).restart,
                "Daemon restarted"))
        self.get_application().add_action(restart_action)

    def _build_header(self) -> Adw.HeaderBar:
        header = Adw.HeaderBar()
        header.set_show_title(True)

        # Service status indicator in header
        self._header_status = Gtk.Label(label="")
        self._header_status.add_css_class("status-badge")
        self._header_status.set_margin_start(6)
        header.pack_end(self._header_status)

        # Poll status for header badge
        GLib.timeout_add_seconds(4, self._update_header_status)
        self._update_header_status()

        return header

    def _update_header_status(self) -> bool:
        from daemon import service as svc
        status = svc.get_status()
        lbl = self._header_status
        for cls in ("status-running", "status-stopped", "status-failed"):
            lbl.remove_css_class(cls)
        if status == svc.ServiceStatus.Running:
            lbl.set_label("● daemon")
            lbl.add_css_class("status-running")
        elif status == svc.ServiceStatus.Failed:
            lbl.set_label("✕ daemon")
            lbl.add_css_class("status-failed")
        else:
            lbl.set_label("○ daemon")
            lbl.add_css_class("status-stopped")
        return True  # keep timer alive

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_box.set_size_request(180, -1)
        sidebar_box.add_css_class("sidebar-nav")

        # App branding at top
        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brand.set_margin_start(16)
        brand.set_margin_end(16)
        brand.set_margin_top(16)
        brand.set_margin_bottom(8)

        icon = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
        icon.set_pixel_size(22)
        brand.append(icon)

        title = Gtk.Label(label="G11 Macro")
        title.add_css_class("title-4")
        brand.append(title)

        sidebar_box.append(brand)
        sidebar_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Navigation list
        self._nav_list = Gtk.ListBox()
        self._nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._nav_list.add_css_class("sidebar-nav")
        self._nav_list.set_vexpand(True)
        self._nav_list.connect("row-selected", self._on_nav_selected)

        self._nav_rows = []
        for label, icon_name in _NAV_ITEMS:
            row = self._make_nav_row(label, icon_name)
            self._nav_list.append(row)
            self._nav_rows.append(row)

        sidebar_box.append(self._nav_list)

        # Version label at bottom
        ver = Gtk.Label(label="v0.1.0")
        ver.add_css_class("dimmed")
        ver.set_margin_bottom(10)
        sidebar_box.append(ver)

        return sidebar_box

    def _make_nav_row(self, label: str, icon_name: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        box.append(icon)

        lbl = Gtk.Label(label=label)
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        row.set_child(box)
        return row

    def _build_about_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_vexpand(True)

        icon = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
        icon.set_pixel_size(80)
        icon.set_opacity(0.7)
        box.append(icon)

        title = Gtk.Label(label="G11 Macro Manager")
        title.add_css_class("title-1")
        box.append(title)

        subtitle = Gtk.Label(label="A GUI for the g11-macro-daemon")
        subtitle.add_css_class("title-4")
        subtitle.set_opacity(0.7)
        box.append(subtitle)

        sep = Gtk.Separator()
        sep.set_margin_start(60)
        sep.set_margin_end(60)
        box.append(sep)

        items = [
            ("Daemon",  "g11-macro-daemon v0.3.0"),
            ("Author",  "Ryan Scheidter"),
            ("License", "MIT"),
            ("Config",  "~/.config/g11-macro-daemon/"),
        ]
        for key, val in items:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_halign(Gtk.Align.CENTER)
            k = Gtk.Label(label=f"{key}:")
            k.add_css_class("dimmed")
            k.set_width_chars(10)
            k.set_xalign(1)
            v = Gtk.Label(label=val)
            v.set_selectable(True)
            row.append(k)
            row.append(v)
            box.append(row)

        gh_btn = Gtk.LinkButton(
            uri="https://github.com/rs017991/g11-macro",
            label="View on GitHub",
        )
        gh_btn.set_margin_top(8)
        box.append(gh_btn)

        return box

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _select_page(self, index: int):
        self._nav_list.select_row(self._nav_rows[index])

    def _on_nav_selected(self, _listbox, row: Gtk.ListBoxRow | None):
        if row is None:
            return
        page_names = ["macros", "service", "leds", "about"]
        idx = self._nav_rows.index(row)
        self._stack.set_visible_child_name(page_names[idx])

    def do_close_request(self):
        if self._service_page:
            self._service_page.stop_polling()
        return False
