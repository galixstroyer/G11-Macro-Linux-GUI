"""A list row representing a single macro step, with edit/delete/reorder actions."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject

from config.models import Step


class StepRow(Adw.ActionRow):
    """
    An Adw.ActionRow that displays one macro Step.
    Emits 'edit-requested' and 'delete-requested' signals.
    Also has up/down buttons for manual reordering.
    """

    __gsignals__ = {
        "edit-requested":   (GObject.SignalFlags.RUN_FIRST, None, ()),
        "delete-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "move-up-requested":   (GObject.SignalFlags.RUN_FIRST, None, ()),
        "move-down-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, step: Step):
        super().__init__()
        self.step = step
        self._build()

    def _build(self):
        self.set_title(self.step.display())
        self.set_activatable(True)
        self.connect("activated", lambda *_: self.emit("edit-requested"))

        # Icon
        icon = Gtk.Image.new_from_icon_name(self.step.icon())
        icon.add_css_class("step-row-icon")
        self.add_prefix(icon)

        # Up / Down buttons
        up_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        up_btn.add_css_class("flat")
        up_btn.set_tooltip_text("Move step up")
        up_btn.connect("clicked", lambda *_: self.emit("move-up-requested"))

        down_btn = Gtk.Button.new_from_icon_name("go-down-symbolic")
        down_btn.add_css_class("flat")
        down_btn.set_tooltip_text("Move step down")
        down_btn.connect("clicked", lambda *_: self.emit("move-down-requested"))

        # Delete button
        del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.set_tooltip_text("Remove step")
        del_btn.connect("clicked", lambda *_: self.emit("delete-requested"))

        box = Gtk.Box(spacing=2)
        box.set_valign(Gtk.Align.CENTER)
        box.append(up_btn)
        box.append(down_btn)
        box.append(del_btn)
        self.add_suffix(box)

    def refresh(self):
        """Update the displayed title after the step has been edited."""
        self.set_title(self.step.display())
