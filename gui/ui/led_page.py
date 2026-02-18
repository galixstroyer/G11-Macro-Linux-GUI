"""LED control page — toggle M1/M2/M3/MR LEDs directly via HID."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from hardware import leds as hw_leds


class LedPage(Gtk.Box):
    """
    Shows LED on/off toggles for M1, M2, M3, and MR.
    Communicates directly with the keyboard via hidapi.
    """

    _LED_KEYS = ["M1", "M2", "M3", "MR"]

    def __init__(self, toast_overlay: Adw.ToastOverlay):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._toast = toast_overlay
        self._switches: dict[str, Gtk.Switch] = {}
        self._indicators: dict[str, Gtk.Box] = {}
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(20)
        content.set_margin_bottom(20)

        # ---- Availability banner ----------------------------------
        if not hw_leds.is_available():
            banner = Adw.Banner(
                title="hidapi not installed — LED control unavailable",
            )
            banner.set_button_label("Install")
            banner.connect("button-clicked", self._on_install_hint)
            banner.set_revealed(True)
            content.append(banner)
        else:
            device_info = hw_leds.get_device_info()
            device_row = Gtk.Label(label=device_info)
            device_row.add_css_class("dimmed")
            device_row.set_wrap(True)
            device_row.set_margin_bottom(4)
            content.append(device_row)

        # ---- LED controls ----------------------------------------
        led_group = Adw.PreferencesGroup(title="LED Controls")
        led_group.set_description(
            "Toggle individual LEDs. Note: the daemon controls these automatically "
            "based on the active bank — your changes may be overridden on the next key event."
        )

        for key in self._LED_KEYS:
            row = Adw.ActionRow(title=f"{key} LED")
            row.set_subtitle("Fixed blue LED")

            # Indicator dot
            indicator = Gtk.Box()
            indicator.set_size_request(14, 14)
            indicator.add_css_class("led-indicator")
            indicator.add_css_class("led-off")
            indicator.set_valign(Gtk.Align.CENTER)
            self._indicators[key] = indicator
            row.add_prefix(indicator)

            # Switch
            sw = Gtk.Switch()
            sw.set_valign(Gtk.Align.CENTER)
            sw.set_sensitive(hw_leds.is_available())
            sw.connect("notify::active", self._on_switch_toggled)
            self._switches[key] = sw
            row.add_suffix(sw)
            row.set_activatable_widget(sw)

            led_group.add(row)

        content.append(led_group)

        # ---- Quick actions ----------------------------------------
        actions_group = Adw.PreferencesGroup(title="Quick Actions")

        all_on_row = Adw.ActionRow(title="All LEDs On")
        all_on_btn = Gtk.Button(label="Apply")
        all_on_btn.add_css_class("flat")
        all_on_btn.set_valign(Gtk.Align.CENTER)
        all_on_btn.connect("clicked", lambda *_: self._set_all(True))
        all_on_row.add_suffix(all_on_btn)
        actions_group.add(all_on_row)

        all_off_row = Adw.ActionRow(title="All LEDs Off")
        all_off_btn = Gtk.Button(label="Apply")
        all_off_btn.add_css_class("flat")
        all_off_btn.set_valign(Gtk.Align.CENTER)
        all_off_btn.connect("clicked", lambda *_: self._set_all(False))
        all_off_row.add_suffix(all_off_btn)
        actions_group.add(all_off_row)

        content.append(actions_group)

        # ---- Info note -------------------------------------------
        note = Gtk.Label()
        note.set_markup(
            "<small>The G11 LEDs are fixed blue — no color control is available.\n"
            "M1/M2/M3 indicate the active macro bank; MR indicates recording mode.</small>"
        )
        note.add_css_class("dimmed")
        note.set_wrap(True)
        note.set_justify(Gtk.Justification.CENTER)
        note.set_margin_top(8)
        content.append(note)

        scroll.set_child(content)
        self.append(scroll)

    # ------------------------------------------------------------------
    # LED state
    # ------------------------------------------------------------------

    def _get_states(self) -> dict[str, bool]:
        return {key: self._switches[key].get_active() for key in self._LED_KEYS}

    def _apply_leds(self):
        states = self._get_states()
        ok, err = hw_leds.set_leds(
            m1=states["M1"],
            m2=states["M2"],
            m3=states["M3"],
            mr=states["MR"],
        )
        if not ok:
            self._show_toast(f"LED error: {err}", timeout=5)
        self._refresh_indicators()

    def _refresh_indicators(self):
        for key, sw in self._switches.items():
            ind = self._indicators[key]
            if sw.get_active():
                ind.remove_css_class("led-off")
                ind.add_css_class("led-on")
            else:
                ind.remove_css_class("led-on")
                ind.add_css_class("led-off")

    def _set_all(self, state: bool):
        for sw in self._switches.values():
            sw.set_active(state)
        self._apply_leds()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_switch_toggled(self, _sw, _param):
        self._apply_leds()

    def _on_install_hint(self, _banner):
        dlg = Adw.AlertDialog(
            heading="Install hidapi",
            body="Run the following command to enable LED control:\n\n"
                 "pip install hidapi\n\n"
                 "Then restart G11 Macro Manager.",
        )
        dlg.add_response("ok", "OK")
        dlg.present(self)

    def _show_toast(self, message: str, timeout: int = 2):
        toast = Adw.Toast(title=message, timeout=timeout)
        self._toast.add_toast(toast)
