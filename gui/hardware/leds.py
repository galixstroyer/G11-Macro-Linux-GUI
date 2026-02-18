"""Direct HID LED control for the Logitech G11 keyboard.

The G11 exposes M1, M2, M3, and MR LEDs (all fixed blue).
Each LED is a single on/off bit in a 4-byte HID feature report.

Note: The daemon also controls these LEDs automatically based on the
active bank and recording state. Changes made here may be overridden
by the daemon on the next key event.
"""
from __future__ import annotations

VENDOR_ID  = 0x046D   # Logitech
PRODUCT_ID = 0xC225   # G11 macro interface

_M1_BIT = 1 << 0
_M2_BIT = 1 << 1
_M3_BIT = 1 << 2
_MR_BIT = 1 << 3

try:
    import hid as _hid
    _HID_AVAILABLE = True
except ImportError:
    _HID_AVAILABLE = False


def is_available() -> bool:
    """Return True if the hidapi Python bindings are installed."""
    return _HID_AVAILABLE


def _build_report(m1: bool, m2: bool, m3: bool, mr: bool) -> list[int]:
    bits = 0
    if m1: bits |= _M1_BIT
    if m2: bits |= _M2_BIT
    if m3: bits |= _M3_BIT
    if mr: bits |= _MR_BIT
    # 0 = lit, 1 = unlit (complemented)
    return [0x02, 0x04, (~bits) & 0x0F, 0x00]


def set_leds(m1: bool, m2: bool, m3: bool, mr: bool) -> tuple[bool, str]:
    """
    Set the M1/M2/M3/MR LED states.
    Returns (success, error_message).
    """
    if not _HID_AVAILABLE:
        return False, "hidapi Python package not installed (pip install hidapi)"
    try:
        dev = _hid.device()
        dev.open(VENDOR_ID, PRODUCT_ID)
        report = _build_report(m1, m2, m3, mr)
        dev.send_feature_report(report)
        dev.close()
        return True, ""
    except OSError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


def get_device_info() -> str:
    """Return a human-readable description of the connected G11, or an error."""
    if not _HID_AVAILABLE:
        return "hidapi not installed"
    try:
        devs = _hid.enumerate(VENDOR_ID, PRODUCT_ID)
        if not devs:
            return "G11 macro interface not found (is it plugged in?)"
        d = devs[0]
        return (f"{d.get('manufacturer_string', 'Logitech')} "
                f"{d.get('product_string', 'G11')} — "
                f"VID:{VENDOR_ID:#06x} PID:{PRODUCT_ID:#06x}")
    except Exception as e:
        return f"Error: {e}"
