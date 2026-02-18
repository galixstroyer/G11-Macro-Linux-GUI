"""Dialog for creating or editing a single macro step."""
from __future__ import annotations
from copy import deepcopy

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from config.models import (
    Direction, Axis, Coordinate, MouseButton, NAMED_KEYS,
    KeyValue, Step,
    StepKey, StepText, StepButton, StepMoveMouse, StepScroll, StepRun,
    STEP_TYPE_LABELS,
)

_STEP_TYPES = list(STEP_TYPE_LABELS.keys())   # ["Key","Text","Button","MoveMouse","Scroll","Run"]


def _make_string_list(items: list[str]) -> Gtk.StringList:
    sl = Gtk.StringList()
    for item in items:
        sl.append(item)
    return sl


def _dropdown(items: list[str], active_value: str | None = None) -> Gtk.DropDown:
    dd = Gtk.DropDown.new(model=_make_string_list(items), expression=None)
    if active_value and active_value in items:
        dd.set_selected(items.index(active_value))
    return dd


def _dropdown_value(dd: Gtk.DropDown, items: list[str]) -> str:
    idx = dd.get_selected()
    return items[idx] if 0 <= idx < len(items) else items[0]


class StepEditorDialog(Adw.Dialog):
    """
    A dialog that lets the user create or edit a Step.
    After accept, read `.result_step` for the new step (None if cancelled).
    """

    def __init__(self, parent: Gtk.Widget, step: Step | None = None):
        super().__init__()
        self.result_step: Step | None = None
        self._initial_step = deepcopy(step)

        self.set_title("Edit Step" if step else "Add Step")
        self.set_content_width(420)
        self.set_content_height(380)

        self._build(step)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, step: Step | None):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Cancel button
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)

        # Save button
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        # Outer scroll
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        # Content box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(8)
        content.set_margin_bottom(16)

        # Type selector
        type_group = Adw.PreferencesGroup(title="Step Type")
        type_labels = list(STEP_TYPE_LABELS.values())
        initial_type = _step_type_key(step) if step else "Key"
        self._type_dd = _dropdown(type_labels, STEP_TYPE_LABELS.get(initial_type))
        type_row = Adw.ActionRow(title="Type")
        type_row.add_suffix(self._type_dd)
        type_group.add(type_row)
        content.append(type_group)

        # Dynamic fields container (rebuilt on type change)
        self._fields_group = Adw.PreferencesGroup(title="Parameters")
        content.append(self._fields_group)

        self._type_dd.connect("notify::selected", self._on_type_changed)
        self._current_type = initial_type
        self._build_fields(initial_type, step)

        scroll.set_child(content)
        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

    def _on_type_changed(self, dd, _param):
        type_labels = list(STEP_TYPE_LABELS.values())
        label = type_labels[dd.get_selected()]
        key = next(k for k, v in STEP_TYPE_LABELS.items() if v == label)
        if key != self._current_type:
            self._current_type = key
            self._build_fields(key, None)

    def _clear_fields(self):
        child = self._fields_group.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            # Only remove rows, not the group header
            if isinstance(child, Adw.PreferencesRow):
                self._fields_group.remove(child)
            child = nxt
        # Simpler: recreate group
        parent = self._fields_group.get_parent()
        idx = self._get_widget_index(parent, self._fields_group)
        parent.remove(self._fields_group)
        self._fields_group = Adw.PreferencesGroup(title="Parameters")
        self._insert_widget_at(parent, self._fields_group, idx)

    def _get_widget_index(self, box: Gtk.Box, widget: Gtk.Widget) -> int:
        child = box.get_first_child()
        i = 0
        while child:
            if child == widget:
                return i
            child = child.get_next_sibling()
            i += 1
        return -1

    def _insert_widget_at(self, box: Gtk.Box, widget: Gtk.Widget, idx: int):
        # GTK4 doesn't have insert_at — use append and hope it's at end
        box.append(widget)

    def _build_fields(self, type_key: str, step: Step | None):
        # Remove old fields group and re-add a fresh one
        parent = self._fields_group.get_parent()
        if parent:
            parent.remove(self._fields_group)
        self._fields_group = Adw.PreferencesGroup(title="Parameters")
        if parent:
            parent.append(self._fields_group)

        g = self._fields_group

        if type_key == "Key":
            s = step if isinstance(step, StepKey) else None
            # Key type: named or unicode
            key_types = ["Named Key", "Unicode Character"]
            init_key_type = "Unicode Character" if (s and s.key.is_unicode) else "Named Key"
            self._key_type_dd = _dropdown(key_types, init_key_type)

            self._named_key_dd = _dropdown(
                NAMED_KEYS,
                s.key.value if s and not s.key.is_unicode else "Control",
            )
            self._unicode_entry = Gtk.Entry()
            self._unicode_entry.set_max_length(1)
            self._unicode_entry.set_placeholder_text("Single character")
            if s and s.key.is_unicode:
                self._unicode_entry.set_text(s.key.value)

            dir_values = [d.value for d in Direction]
            self._key_dir_dd = _dropdown(dir_values, s.direction.value if s else "Click")

            key_type_row = Adw.ActionRow(title="Key Type")
            key_type_row.add_suffix(self._key_type_dd)
            g.add(key_type_row)

            self._named_row = Adw.ActionRow(title="Key Name")
            self._named_row.add_suffix(self._named_key_dd)
            g.add(self._named_row)

            self._unicode_row = Adw.ActionRow(title="Character")
            self._unicode_row.add_suffix(self._unicode_entry)
            g.add(self._unicode_row)

            dir_row = Adw.ActionRow(title="Action")
            dir_row.add_suffix(self._key_dir_dd)
            g.add(dir_row)

            repeat_row = Adw.ActionRow(title="Repeat")
            repeat_row.set_subtitle("How many times to press the key")
            self._repeat_spin = Gtk.SpinButton.new_with_range(1, 100, 1)
            self._repeat_spin.set_value(s.repeat if s else 1)
            self._repeat_spin.set_valign(Gtk.Align.CENTER)
            repeat_row.add_suffix(self._repeat_spin)
            g.add(repeat_row)

            self._key_type_dd.connect("notify::selected", self._on_key_type_changed)
            self._on_key_type_changed(self._key_type_dd, None)

        elif type_key == "Text":
            s = step if isinstance(step, StepText) else None
            self._text_entry = Gtk.Entry()
            self._text_entry.set_hexpand(True)
            self._text_entry.set_placeholder_text("Text to type…")
            if s:
                self._text_entry.set_text(s.text)
            row = Adw.ActionRow(title="Text")
            row.add_suffix(self._text_entry)
            g.add(row)

        elif type_key == "Button":
            s = step if isinstance(step, StepButton) else None
            btn_values = [b.value for b in MouseButton]
            self._btn_dd = _dropdown(btn_values, s.button.value if s else "Left")
            dir_values = [d.value for d in Direction]
            self._btn_dir_dd = _dropdown(dir_values, s.direction.value if s else "Click")

            btn_row = Adw.ActionRow(title="Button")
            btn_row.add_suffix(self._btn_dd)
            g.add(btn_row)

            dir_row = Adw.ActionRow(title="Action")
            dir_row.add_suffix(self._btn_dir_dd)
            g.add(dir_row)

        elif type_key == "MoveMouse":
            s = step if isinstance(step, StepMoveMouse) else None
            self._mm_x = Gtk.SpinButton.new_with_range(-10000, 10000, 1)
            self._mm_y = Gtk.SpinButton.new_with_range(-10000, 10000, 1)
            if s:
                self._mm_x.set_value(s.x)
                self._mm_y.set_value(s.y)
            coord_values = [c.value for c in Coordinate]
            self._mm_coord_dd = _dropdown(coord_values, s.coordinate.value if s else "Rel")

            row_x = Adw.ActionRow(title="X")
            row_x.add_suffix(self._mm_x)
            g.add(row_x)
            row_y = Adw.ActionRow(title="Y")
            row_y.add_suffix(self._mm_y)
            g.add(row_y)
            row_c = Adw.ActionRow(title="Coordinate")
            row_c.add_suffix(self._mm_coord_dd)
            g.add(row_c)

        elif type_key == "Scroll":
            s = step if isinstance(step, StepScroll) else None
            self._scroll_spin = Gtk.SpinButton.new_with_range(-100, 100, 1)
            if s:
                self._scroll_spin.set_value(s.magnitude)
            else:
                self._scroll_spin.set_value(3)
            axis_values = [a.value for a in Axis]
            self._scroll_axis_dd = _dropdown(axis_values, s.axis.value if s else "Vertical")

            row_m = Adw.ActionRow(title="Magnitude")
            row_m.set_subtitle("Positive = Down / Right")
            row_m.add_suffix(self._scroll_spin)
            g.add(row_m)
            row_a = Adw.ActionRow(title="Axis")
            row_a.add_suffix(self._scroll_axis_dd)
            g.add(row_a)

        elif type_key == "Run":
            s = step if isinstance(step, StepRun) else None
            self._run_entry = Gtk.Entry()
            self._run_entry.set_hexpand(True)
            self._run_entry.set_placeholder_text("e.g. gnome-calculator")
            if s:
                self._run_entry.set_text(s.program)

            self._args_entry = Gtk.Entry()
            self._args_entry.set_hexpand(True)
            self._args_entry.set_placeholder_text('e.g. --arg1 "val 2"  (space-separated)')
            if s and s.args:
                self._args_entry.set_text(" ".join(s.args))

            row_p = Adw.ActionRow(title="Program")
            row_p.add_suffix(self._run_entry)
            g.add(row_p)

            row_a = Adw.ActionRow(title="Arguments")
            row_a.set_subtitle("Optional, space-separated")
            row_a.add_suffix(self._args_entry)
            g.add(row_a)

    def _on_key_type_changed(self, dd, _param):
        key_types = ["Named Key", "Unicode Character"]
        sel = key_types[dd.get_selected()]
        is_unicode = sel == "Unicode Character"
        self._named_row.set_visible(not is_unicode)
        self._unicode_row.set_visible(is_unicode)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self, _btn):
        step = self._build_step()
        if step is None:
            return
        self.result_step = step
        self.close()

    def _build_step(self) -> Step | None:
        t = self._current_type

        if t == "Key":
            key_types = ["Named Key", "Unicode Character"]
            kt = key_types[self._key_type_dd.get_selected()]
            if kt == "Named Key":
                key = KeyValue.named(_dropdown_value(self._named_key_dd, NAMED_KEYS))
            else:
                char = self._unicode_entry.get_text()
                if not char:
                    self._show_error("Please enter a character.")
                    return None
                key = KeyValue.unicode(char[0])
            dir_values = [d.value for d in Direction]
            direction = Direction(_dropdown_value(self._key_dir_dd, dir_values))
            repeat = int(self._repeat_spin.get_value())
            return StepKey(key=key, direction=direction, repeat=repeat)

        if t == "Text":
            text = self._text_entry.get_text()
            if not text:
                self._show_error("Please enter text to type.")
                return None
            return StepText(text=text)

        if t == "Button":
            btn_values = [b.value for b in MouseButton]
            dir_values = [d.value for d in Direction]
            return StepButton(
                button=MouseButton(_dropdown_value(self._btn_dd, btn_values)),
                direction=Direction(_dropdown_value(self._btn_dir_dd, dir_values)),
            )

        if t == "MoveMouse":
            coord_values = [c.value for c in Coordinate]
            return StepMoveMouse(
                x=int(self._mm_x.get_value()),
                y=int(self._mm_y.get_value()),
                coordinate=Coordinate(_dropdown_value(self._mm_coord_dd, coord_values)),
            )

        if t == "Scroll":
            axis_values = [a.value for a in Axis]
            return StepScroll(
                magnitude=int(self._scroll_spin.get_value()),
                axis=Axis(_dropdown_value(self._scroll_axis_dd, axis_values)),
            )

        if t == "Run":
            program = self._run_entry.get_text().strip()
            if not program:
                self._show_error("Please enter a program name.")
                return None
            raw_args = self._args_entry.get_text().strip()
            args = raw_args.split() if raw_args else []
            return StepRun(program=program, args=args)

        return None

    def _show_error(self, msg: str):
        dlg = Adw.AlertDialog(heading="Validation Error", body=msg)
        dlg.add_response("ok", "OK")
        dlg.present(self)


def _step_type_key(step: Step) -> str:
    return type(step).__name__.replace("Step", "")
