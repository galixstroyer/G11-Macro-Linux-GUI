"""Application class — sets up GTK, loads CSS, and opens the main window."""
from __future__ import annotations
import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from ui.main_window import MainWindow


class G11MacroApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.github.rs017991.g11-macro-gui")
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app):
        self._load_css()
        win = MainWindow(application=self)
        win.present()

    def _load_css(self):
        css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
        if not os.path.exists(css_path):
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(css_path)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
