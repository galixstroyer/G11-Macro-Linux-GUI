"""Keyboard widget — a visual grid of G keys, M-bank keys, and MR key.

Supports both G11 and G15 layouts:
  G11: M-keys on top, G-keys below (6 rows x 3 cols)
  G15: G-keys on top, M-keys below (6 rows x 3 cols)
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from config import manager as config_mgr


# G key grid: 6 rows of 3 keys
_G_ROWS = [
    [1,  2,  3],
    [4,  5,  6],
    [7,  8,  9],
    [10, 11, 12],
    [13, 14, 15],
    [16, 17, 18],
]


class KeyboardWidget(Gtk.Box):
    """
    Displays the macro key section for G11 or G15:
      - M1 / M2 / M3 bank selector buttons
      - MR button
      - 18 G key buttons in a 6x3 grid

    The layout order depends on the keyboard model:
      G11: M-keys on top, G-keys below
      G15: G-keys on top, M-keys below

    Signals:
      g-key-activated(g: int)  — emitted when a G key is clicked
      m-key-activated(m: int)  — emitted when an M bank key is clicked
    """

    __gsignals__ = {
        "g-key-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "m-key-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("keyboard-panel")

        self._active_m: int = 1
        self._selected_g: int | None = None
        self._macro_keys: set[tuple[int, int]] = set()
        self._keyboard_model: str = "G11"

        self._g_buttons: dict[int, Gtk.Button] = {}
        self._m_buttons: dict[int, Gtk.Button] = {}
        self._mr_button: Gtk.Button | None = None

        self._load_model()
        self._build()

    def _load_model(self):
        self._keyboard_model = config_mgr.load_keyboard_model()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        is_g15 = self._keyboard_model == "G15"

        # Apply accent class for G15
        if is_g15:
            self.add_css_class("g15-accent")

        # ---- Model label at top ------------------------------------
        model_label = Gtk.Label(label=f"LOGITECH {self._keyboard_model}")
        model_label.add_css_class("keyboard-model-label")
        model_label.add_css_class(f"keyboard-model-label-{'g15' if is_g15 else 'g11'}")
        model_label.set_margin_bottom(12)
        self.append(model_label)

        if is_g15:
            # G15 layout: G-keys first, then M-keys below
            self._build_gkey_grid()
            self._add_spacer(10)
            self._build_bank_row()
        else:
            # G11 layout: M-keys on top, then G-keys below
            self._build_bank_row()
            self._add_spacer(10)
            self._build_gkey_grid()

        # ---- Legend ------------------------------------------------
        self._add_spacer(8)
        legend = Gtk.Label()
        legend.set_markup("Highlighted keys have a macro  ·  Click to edit")
        legend.add_css_class("keyboard-legend")
        self.append(legend)

        # Apply initial state
        self._refresh_m_buttons()

    def _build_bank_row(self):
        bank_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bank_row.set_halign(Gtk.Align.CENTER)

        for m in (1, 2, 3):
            btn = Gtk.Button(label=f"M{m}")
            btn.add_css_class("mkey")
            btn.connect("clicked", self._on_m_clicked, m)
            self._m_buttons[m] = btn
            bank_row.append(btn)

        # Spacer between M-keys and MR
        spacer = Gtk.Box()
        spacer.set_size_request(20, -1)
        bank_row.append(spacer)

        mr_btn = Gtk.Button(label="MR")
        mr_btn.add_css_class("mrkey")
        mr_btn.set_tooltip_text("Macro Record key (controlled by daemon)")
        mr_btn.set_sensitive(False)
        self._mr_button = mr_btn
        bank_row.append(mr_btn)

        self.append(bank_row)

    def _build_gkey_grid(self):
        grid = Gtk.Grid()
        grid.set_row_spacing(5)
        grid.set_column_spacing(5)
        grid.set_halign(Gtk.Align.CENTER)

        for row_idx, row in enumerate(_G_ROWS):
            for col_idx, g in enumerate(row):
                btn = Gtk.Button(label=f"G{g}")
                btn.add_css_class("gkey")
                btn.set_tooltip_text(f"G{g} — click to edit macro")
                btn.connect("clicked", self._on_g_clicked, g)
                self._g_buttons[g] = btn
                grid.attach(btn, col_idx, row_idx, 1, 1)

        self.append(grid)

    def _add_spacer(self, height: int):
        spacer = Gtk.Box()
        spacer.set_size_request(-1, height)
        self.append(spacer)

    # ------------------------------------------------------------------
    # State setters
    # ------------------------------------------------------------------

    def set_active_bank(self, m: int):
        self._active_m = m
        self._refresh_m_buttons()
        self._refresh_g_buttons()

    def set_selected_g(self, g: int | None):
        self._selected_g = g
        self._refresh_g_buttons()

    def set_macro_keys(self, macro_keys: set[tuple[int, int]]):
        """Pass the set of (m, g) pairs that have macros defined."""
        self._macro_keys = macro_keys
        self._refresh_g_buttons()

    def get_active_bank(self) -> int:
        return self._active_m

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_m_buttons(self):
        for m, btn in self._m_buttons.items():
            if m == self._active_m:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def _refresh_g_buttons(self):
        for g, btn in self._g_buttons.items():
            if (self._active_m, g) in self._macro_keys:
                btn.add_css_class("has-macro")
            else:
                btn.remove_css_class("has-macro")
            if g == self._selected_g:
                btn.add_css_class("selected")
            else:
                btn.remove_css_class("selected")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_g_clicked(self, _btn, g: int):
        self._selected_g = g
        self._refresh_g_buttons()
        self.emit("g-key-activated", g)

    def _on_m_clicked(self, _btn, m: int):
        self._active_m = m
        self._selected_g = None
        self._refresh_m_buttons()
        self._refresh_g_buttons()
        self.emit("m-key-activated", m)
