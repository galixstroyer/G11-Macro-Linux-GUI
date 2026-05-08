//! Evdev-based input backend for keyboards (like the Logitech G15)
//! whose G-keys are exposed through the Linux input subsystem
//! rather than a dedicated raw HID interface.

use std::fmt;
use std::path::Path;
use derive_more::{Display, Error};
use evdev::{Device, InputEventKind, Key as EvdevKey};
use log::{info, debug};
use g11_macro_keys::{Key, Action, Event};

// Two different code sets exist depending on the input source:
//
// 1. lg-g15 kernel driver (creates "G15 Extra Keys" device):
//      G1–G18 → KEY_MACRO1(656) through KEY_MACRO18(673)
//      M1–M3  → KEY_MACRO_PRESET1(691) through KEY_MACRO_PRESET3(693)
//      MR     → KEY_MACRO_RECORD_START(688)
//
// 2. g15daemon virtual device (creates "gsr-ui virtual keyboard" or similar):
//      G1–G18 → KEY_RECORD(167) through KEY_F14(184)
//      M1–M3  → KEY_F15(185) through KEY_F17(187)
//      MR     → KEY_F18(188)
//
// We support both so the daemon works regardless of which is present.

// lg-g15 kernel driver codes
const KERNEL_G1: u16 = 656;   // KEY_MACRO1
const KERNEL_G18: u16 = 673;  // KEY_MACRO18
const KERNEL_M1: u16 = 691;   // KEY_MACRO_PRESET1
const KERNEL_M3: u16 = 693;   // KEY_MACRO_PRESET3
const KERNEL_MR: u16 = 688;   // KEY_MACRO_RECORD_START

// g15daemon virtual device codes
const G15D_G1: u16 = 167;     // KEY_RECORD
const G15D_G18: u16 = 184;    // KEY_F14
const G15D_M1: u16 = 185;     // KEY_F15
const G15D_M3: u16 = 187;     // KEY_F17
const G15D_MR: u16 = 188;     // KEY_F18

fn scancode_to_key(code: u16) -> Option<Key> {
    match code {
        // lg-g15 kernel driver
        KERNEL_G1..=KERNEL_G18 => Some(Key::G((code - KERNEL_G1 + 1) as u8)),
        KERNEL_M1..=KERNEL_M3 => Some(Key::M((code - KERNEL_M1 + 1) as u8)),
        KERNEL_MR => Some(Key::MR),

        // g15daemon virtual device
        G15D_G1..=G15D_G18 => Some(Key::G((code - G15D_G1 + 1) as u8)),
        G15D_M1..=G15D_M3 => Some(Key::M((code - G15D_M1 + 1) as u8)),
        G15D_MR => Some(Key::MR),

        _ => None,
    }
}

fn value_to_action(value: i32) -> Option<Action> {
    match value {
        1 => Some(Action::Pressed),
        0 => Some(Action::Released),
        _ => None, // 2 = key repeat; not relevant for macro keys
    }
}

pub struct EvdevInput {
    device: Device,
}

impl EvdevInput {
    /// Opens the G15 G-key evdev device.
    ///
    /// If `device_path` is provided, opens that specific device.
    /// Otherwise, scans `/dev/input/event*` for a suitable device.
    ///
    /// The device is grabbed exclusively so key events don't leak to the desktop
    /// (e.g. preventing G6/KEY_HOMEPAGE from opening a browser).
    pub fn open(device_path: Option<&str>) -> Result<Self, EvdevOpenError> {
        let mut device = match device_path {
            Some(path) => Self::open_specific(path)?,
            None => Self::find_gkey_device()?,
        };

        info!("Using evdev device: {}", DeviceSummary(&device));

        device.grab()
            .map_err(|err| EvdevOpenError::GrabFailed(device.name().unwrap_or("unknown").to_owned(), err))?;
        info!("Device grabbed exclusively");

        Ok(Self { device })
    }

    fn open_specific(path: &str) -> Result<Device, EvdevOpenError> {
        Device::open(Path::new(path))
            .map_err(|err| EvdevOpenError::OpenFailed(path.to_owned(), err))
    }

    fn find_gkey_device() -> Result<Device, EvdevOpenError> {
        let input_dir = std::fs::read_dir("/dev/input")
            .map_err(EvdevOpenError::ScanFailed)?;

        let mut candidates: Vec<(String, Device)> = Vec::new();

        for entry in input_dir.flatten() {
            let path = entry.path();
            if !path.file_name().map_or(false, |n| n.to_string_lossy().starts_with("event")) {
                continue;
            }

            let device = match Device::open(&path) {
                Ok(d) => d,
                Err(_) => continue,
            };

            if Self::device_supports_gkeys(&device) {
                let path_str = path.to_string_lossy().into_owned();
                debug!("Candidate G-key device: {} at {path_str}", device.name().unwrap_or("unknown"));
                candidates.push((path_str, device));
            }
        }

        if candidates.is_empty() {
            return Err(EvdevOpenError::NotFound);
        }

        // Sort candidates: prefer devices that support fewer total keys.
        // A genuine G-key device supports ~22 keys (G1-G18 + M1-M3 + MR).
        // A catch-all virtual device (like "G15 Extra Keys" with KEY=0xfff…)
        // claims to support hundreds of keys and may not actually emit events.
        candidates.sort_by_key(|(_, device)| {
            device.supported_keys().map_or(u16::MAX, |keys| keys.iter().count() as u16)
        });

        for (path, count) in candidates.iter().map(|(p, d)| (p, d.supported_keys().map_or(0, |k| k.iter().count()))) {
            debug!("  {path}: supports {count} key codes");
        }

        // Try each candidate in order, skip those grabbed by another process.
        for (path, mut device) in candidates {
            match device.grab() {
                Ok(()) => {
                    let _ = device.ungrab();
                    info!("Selected G-key device at {path} (grab test passed)");
                    return Ok(device);
                }
                Err(_) => {
                    debug!("Skipping {path} — already grabbed by another process");
                }
            }
        }

        Err(EvdevOpenError::AllGrabbed)
    }

    fn device_supports_gkeys(device: &Device) -> bool {
        let Some(keys) = device.supported_keys() else { return false };

        // Check for lg-g15 kernel driver codes (KEY_MACRO1..KEY_MACRO18 + KEY_MACRO_PRESET1..3 + KEY_MACRO_RECORD_START)
        let has_kernel_gkeys = (KERNEL_G1..=KERNEL_G18).all(|c| keys.contains(EvdevKey::new(c)));
        let has_kernel_mkeys = (KERNEL_M1..=KERNEL_M3).all(|c| keys.contains(EvdevKey::new(c)))
            && keys.contains(EvdevKey::new(KERNEL_MR));

        // Check for g15daemon virtual device codes (KEY_RECORD..KEY_F14 + KEY_F15..KEY_F18)
        let has_g15d_gkeys = (G15D_G1..=G15D_G18).all(|c| keys.contains(EvdevKey::new(c)));
        let has_g15d_mkeys = (G15D_M1..=G15D_MR).all(|c| keys.contains(EvdevKey::new(c)));

        (has_kernel_gkeys && has_kernel_mkeys) || (has_g15d_gkeys && has_g15d_mkeys)
    }

    /// Blocks until a G-key, M-key, or MR event is received.
    pub fn read_event(&mut self) -> Result<Event, EvdevReadError> {
        loop {
            let events = self.device.fetch_events()
                .map_err(EvdevReadError::ReadFailed)?;

            for event in events {
                if let InputEventKind::Key(key) = event.kind() {
                    if let (Some(g_key), Some(action)) = (scancode_to_key(key.0), value_to_action(event.value())) {
                        return Ok(Event { key: g_key, action });
                    }
                }
            }
        }
    }
}

// Helper for logging the device name and path
struct DeviceSummary<'a>(&'a Device);
impl fmt::Display for DeviceSummary<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "\"{}\" ({})",
            self.0.name().unwrap_or("unknown"),
            self.0.physical_path().unwrap_or("unknown path"))
    }
}

#[derive(Debug, Display, Error)]
pub enum EvdevOpenError {
    #[display("Failed to scan /dev/input: {_0}")]
    ScanFailed(std::io::Error),

    #[display("Could not open {_0}: {_1}")]
    OpenFailed(String, std::io::Error),

    #[display("Could not grab device \"{_0}\" exclusively: {_1}\nAnother program (e.g. g15daemon) may have claimed it.")]
    GrabFailed(String, std::io::Error),

    #[display(
        "No G15 G-key input device found.\n\
         Make sure the lg-g15 kernel driver is loaded (or g15daemon is running)\n\
         and that you have read permission on /dev/input/event* (try adding your user to the 'input' group)."
    )]
    NotFound,

    #[display(
        "Found G-key devices but all are grabbed by another process.\n\
         If g15daemon is running, stop it first: sudo systemctl stop g15daemon"
    )]
    AllGrabbed,
}

#[derive(Debug, Display, Error)]
pub enum EvdevReadError {
    #[display("Failed to read evdev events: {_0}")]
    ReadFailed(std::io::Error),
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Verifies the g15daemon virtual device scancode mapping (codes 167–188).
    #[test]
    fn g15daemon_scancode_mapping() {
        for g in 1..=18u8 {
            let code = G15D_G1 + (g - 1) as u16;
            assert_eq!(scancode_to_key(code), Some(Key::G(g)), "G{g} (g15d code {code})");
        }
        for m in 1..=3u8 {
            let code = G15D_M1 + (m - 1) as u16;
            assert_eq!(scancode_to_key(code), Some(Key::M(m)), "M{m} (g15d code {code})");
        }
        assert_eq!(scancode_to_key(G15D_MR), Some(Key::MR));

        // Boundaries
        assert_eq!(scancode_to_key(G15D_G1 - 1), None, "below g15d G1");
        assert_eq!(scancode_to_key(G15D_MR + 1), None, "above g15d MR");
    }

    /// Verifies the lg-g15 kernel driver scancode mapping (codes 656–693).
    #[test]
    fn kernel_driver_scancode_mapping() {
        for g in 1..=18u8 {
            let code = KERNEL_G1 + (g - 1) as u16;
            assert_eq!(scancode_to_key(code), Some(Key::G(g)), "G{g} (kernel code {code})");
        }
        for m in 1..=3u8 {
            let code = KERNEL_M1 + (m - 1) as u16;
            assert_eq!(scancode_to_key(code), Some(Key::M(m)), "M{m} (kernel code {code})");
        }
        assert_eq!(scancode_to_key(KERNEL_MR), Some(Key::MR));

        // Boundaries
        assert_eq!(scancode_to_key(KERNEL_G1 - 1), None, "below kernel G1");
        assert_eq!(scancode_to_key(KERNEL_G18 + 1), None, "between kernel G18 and MR");
        assert_eq!(scancode_to_key(KERNEL_M3 + 1), None, "above kernel M3");
    }

    /// Both code sets produce the same Key values for the same logical key.
    #[test]
    fn both_code_sets_agree() {
        for g in 1..=18u8 {
            let kernel = scancode_to_key(KERNEL_G1 + (g - 1) as u16);
            let g15d = scancode_to_key(G15D_G1 + (g - 1) as u16);
            assert_eq!(kernel, g15d, "G{g} must match across code sets");
        }
        for m in 1..=3u8 {
            let kernel = scancode_to_key(KERNEL_M1 + (m - 1) as u16);
            let g15d = scancode_to_key(G15D_M1 + (m - 1) as u16);
            assert_eq!(kernel, g15d, "M{m} must match across code sets");
        }
        assert_eq!(scancode_to_key(KERNEL_MR), scancode_to_key(G15D_MR), "MR must match");
    }

    #[test]
    fn evdev_value_mapping() {
        assert_eq!(value_to_action(1), Some(Action::Pressed));
        assert_eq!(value_to_action(0), Some(Action::Released));
        assert_eq!(value_to_action(2), None, "key repeat should be ignored");
        assert_eq!(value_to_action(-1), None);
    }
}
