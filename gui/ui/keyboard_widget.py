"""G11 keyboard widget — a visual grid of G keys, M-bank keys, and MR key."""
from __future__ import annotations
from typing import Callable

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject


# G key layout: 3 rows × 6 columns (G1–G18)
_ROWS = [
    [1,  2,  3,  4,  5,  6],
    [7,  8,  9,  10, 11, 12],
    [13, 14, 15, 16, 17, 18],
]


class KeyboardWidget(Gtk.Box):
    """
    Displays the G11 macro key section:
      • M1 / M2 / M3 bank selector buttons
      • MR  button
      • 18 G key buttons in a 3×6 grid

    Signals:
      g-key-activated(g: int)  — emitted when a G key is clicked
      m-key-activated(m: int)  — emitted when an M bank key is clicked
    """

    __gsignals__ = {
        "g-key-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "m-key-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("keyboard-panel")

        self._active_m: int = 1
        self._selected_g: int | None = None
        self._macro_keys: set[tuple[int, int]] = set()  # (m, g) pairs

        self._g_buttons: dict[int, Gtk.Button] = {}
        self._m_buttons: dict[int, Gtk.Button] = {}
        self._mr_button: Gtk.Button | None = None

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        # ---- Top row: bank keys + MR ---------------------------------
        bank_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bank_row.set_halign(Gtk.Align.CENTER)

        for m in (1, 2, 3):
            btn = Gtk.Button(label=f"M{m}")
            btn.add_css_class("mkey")
            btn.connect("clicked", self._on_m_clicked, m)
            self._m_buttons[m] = btn
            bank_row.append(btn)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bank_row.append(spacer)

        mr_btn = Gtk.Button(label="MR")
        mr_btn.add_css_class("mrkey")
        mr_btn.set_tooltip_text("Macro Record key (controlled by daemon)")
        mr_btn.set_sensitive(False)
        self._mr_button = mr_btn
        bank_row.append(mr_btn)

        self.append(bank_row)

        # ---- G key grid ----------------------------------------------
        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        grid.set_halign(Gtk.Align.CENTER)

        for row_idx, row in enumerate(_ROWS):
            for col_idx, g in enumerate(row):
                btn = Gtk.Button(label=f"G{g}")
                btn.add_css_class("gkey")
                btn.set_tooltip_text(f"G{g} — click to edit macro")
                btn.connect("clicked", self._on_g_clicked, g)
                self._g_buttons[g] = btn
                grid.attach(btn, col_idx, row_idx, 1, 1)

        self.append(grid)

        # ---- Legend --------------------------------------------------
        legend = Gtk.Label(label="Blue keys have a macro assigned  •  Click a key to edit")
        legend.add_css_class("dimmed")
        legend.set_margin_top(6)
        self.append(legend)

        # Apply initial state
        self._refresh_m_buttons()

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
            # has-macro
            if (self._active_m, g) in self._macro_keys:
                btn.add_css_class("has-macro")
            else:
                btn.remove_css_class("has-macro")
            # selected
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
