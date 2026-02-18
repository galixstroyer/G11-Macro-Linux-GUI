"""Panel for editing the steps of a single G-key macro."""
from __future__ import annotations
from copy import deepcopy
from typing import Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject

from config.models import KeyBinding, Direction, Step
from .step_row import StepRow
from .step_editor_dialog import StepEditorDialog


class MacroEditorPanel(Gtk.Box):
    """
    Shows the macro bound to a specific (m, g) key.
    Allows editing/adding/removing/reordering steps.
    Emits 'binding-changed' when the user saves.
    """

    __gsignals__ = {
        "binding-changed": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._binding: KeyBinding | None = None
        self._step_rows: list[StepRow] = []
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        # ---- Header ------------------------------------------------
        self._header_label = Gtk.Label(label="Select a key to edit its macro")
        self._header_label.add_css_class("title-4")
        self._header_label.set_margin_top(16)
        self._header_label.set_margin_bottom(4)
        self.append(self._header_label)

        # Trigger row (Press / Release)
        trigger_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        trigger_box.set_halign(Gtk.Align.CENTER)
        trigger_box.set_margin_bottom(12)

        trigger_lbl = Gtk.Label(label="Trigger:")
        trigger_lbl.add_css_class("dimmed")
        trigger_box.append(trigger_lbl)

        self._trigger_dd = Gtk.DropDown.new(
            model=Gtk.StringList.new(["Press", "Release"]),
            expression=None,
        )
        trigger_box.append(self._trigger_dd)
        self.append(trigger_box)

        # ---- Scrollable step list ----------------------------------
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(12)
        self._list_box.set_margin_end(12)

        scroll.set_child(self._list_box)
        self.append(scroll)

        # ---- Empty state placeholder -------------------------------
        self._empty_label = Gtk.Label(label="No steps yet — add one below")
        self._empty_label.add_css_class("dimmed")
        self._empty_label.set_margin_top(24)
        self._empty_label.set_margin_bottom(24)
        self._list_box.append(self._empty_label)

        # ---- Bottom action bar -------------------------------------
        action_bar = Gtk.ActionBar()

        add_btn = Gtk.Button(label="Add Step")
        add_btn.add_css_class("suggested-action")
        add_btn.set_icon_name("list-add-symbolic")
        add_btn.connect("clicked", self._on_add_step)
        action_bar.pack_start(add_btn)

        clear_btn = Gtk.Button(label="Clear All")
        clear_btn.add_css_class("destructive-action")
        clear_btn.connect("clicked", self._on_clear)
        action_bar.pack_end(clear_btn)

        save_btn = Gtk.Button(label="Save Macro")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        action_bar.pack_end(save_btn)

        self.append(action_bar)

        self._set_ui_sensitive(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_binding(self, binding: KeyBinding | None, m: int, g: int):
        """Load a binding (or None for an empty macro) for the given m/g."""
        if binding:
            self._binding = deepcopy(binding)
        else:
            self._binding = KeyBinding(m=m, g=g, on=Direction.Press, script=[])

        self._header_label.set_label(f"G{g}  —  M{m} Bank")
        self._trigger_dd.set_selected(0 if self._binding.on == Direction.Press else 1)
        self._rebuild_step_list()
        self._set_ui_sensitive(True)

    def clear(self):
        self._binding = None
        self._header_label.set_label("Select a key to edit its macro")
        self._rebuild_step_list()
        self._set_ui_sensitive(False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_ui_sensitive(self, sensitive: bool):
        self._trigger_dd.set_sensitive(sensitive)
        self._list_box.set_sensitive(sensitive)

    def _rebuild_step_list(self):
        # Remove all existing step rows
        for row in self._step_rows:
            self._list_box.remove(row)
        self._step_rows.clear()

        steps = self._binding.script if self._binding else []
        self._empty_label.set_visible(len(steps) == 0)

        for i, step in enumerate(steps):
            self._insert_step_row(step, i)

    def _insert_step_row(self, step: Step, index: int):
        row = StepRow(step)
        row.connect("edit-requested",      lambda r: self._on_edit_step(r))
        row.connect("delete-requested",    lambda r: self._on_delete_step(r))
        row.connect("move-up-requested",   lambda r: self._on_move_step(r, -1))
        row.connect("move-down-requested", lambda r: self._on_move_step(r, +1))
        self._list_box.insert(row, index)
        self._step_rows.insert(index, row)
        self._empty_label.set_visible(False)

    def _row_index(self, row: StepRow) -> int:
        return self._step_rows.index(row)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_add_step(self, _btn):
        if not self._binding:
            return
        dlg = StepEditorDialog(self, step=None)
        dlg.connect("closed", self._on_step_dialog_closed_add)
        dlg.present(self)

    def _on_step_dialog_closed_add(self, dlg):
        if dlg.result_step and self._binding:
            self._binding.script.append(dlg.result_step)
            self._insert_step_row(dlg.result_step, len(self._step_rows))

    def _on_edit_step(self, row: StepRow):
        if not self._binding:
            return
        dlg = StepEditorDialog(self, step=row.step)
        dlg.connect("closed", lambda d: self._on_step_dialog_closed_edit(d, row))
        dlg.present(self)

    def _on_step_dialog_closed_edit(self, dlg, row: StepRow):
        if dlg.result_step and self._binding:
            idx = self._row_index(row)
            self._binding.script[idx] = dlg.result_step
            row.step = dlg.result_step
            row.refresh()

    def _on_delete_step(self, row: StepRow):
        if not self._binding:
            return
        idx = self._row_index(row)
        self._binding.script.pop(idx)
        self._list_box.remove(row)
        self._step_rows.pop(idx)
        self._empty_label.set_visible(len(self._step_rows) == 0)

    def _on_move_step(self, row: StepRow, delta: int):
        if not self._binding:
            return
        idx = self._row_index(row)
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self._step_rows):
            return

        # Swap in the model
        script = self._binding.script
        script[idx], script[new_idx] = script[new_idx], script[idx]

        # Rebuild list (simplest correct approach)
        self._rebuild_step_list()

    def _on_clear(self, _btn):
        if not self._binding:
            return
        dlg = Adw.AlertDialog(
            heading="Clear all steps?",
            body="This will remove all steps from this macro.",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("clear", "Clear")
        dlg.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.connect("response", self._on_clear_response)
        dlg.present(self)

    def _on_clear_response(self, dlg, response: str):
        if response == "clear" and self._binding:
            self._binding.script.clear()
            self._rebuild_step_list()

    def _on_save(self, _btn):
        if not self._binding:
            return
        # Update trigger direction from dropdown
        self._binding.on = Direction.Press if self._trigger_dd.get_selected() == 0 else Direction.Release
        self.emit("binding-changed", deepcopy(self._binding))
