#![doc = include_str!("../README.md")]

use std::mem;
use derive_more::{Display, Error};

pub mod usb_id {
    //! Constants for locating the right USB device

    /// USB VID for Logitech
    pub const VENDOR_LOGITECH: u16 = 0x46d;

    /// USB PID for the macro key interface on a G11 Keyboard
    pub const PRODUCT_G11_MACRO: u16 = 0xc225;

    #[deprecated = "renamed to `PRODUCT_G11_MACRO`"]
    pub const PRODUCT_G11: u16 = PRODUCT_G11_MACRO;

    /// USB PID for the regular (104-key) interface on a G11 Keyboard
    pub const PRODUCT_G11_STANDARD: u16 = 0xc221;

    /// USB PID for the LCD/keypad interface on a G15 Keyboard.
    /// This interface is used for LED control; G-key input comes via evdev instead.
    pub const PRODUCT_G15_LCD: u16 = 0xc222;
}

mod multikey;
mod led;

/// A specific key on the G11
#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum Key {
    /// `G` keys, numbered `1 ..= 18`
    ///
    /// (the macro keys themselves)
    G(u8),
    /// `M` key, numbered `1 ..= 3`
    ///
    /// (for switching between macro sets)
    M(u8),
    /// Macro Record key
    MR,
    /// Main keyboard backlight key
    /// (unrelated to macro keys but runs on the same interface)
    Backlight,
}

/// Whether the user has been observed to have [`Pressed`] or [`Released`] a [`Key`]
///
/// [`Pressed`]: Action::Pressed
/// [`Released`]: Action::Released
#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum Action {
    Pressed,
    Released,
}

/// Signal from the G11 that the user has performed an [`Action`] on a [`Key`]
#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub struct Event {
    pub key: Key,
    pub action: Action,
}

/// Keeps track of the known device state,
/// so that an individual [`Event`] may be isolated from each set of new bytes received over USB.
///
/// You must keep this object up-to-date by feeding all of the bytes read from the G11's HID interface through [`State::try_consume_event`].
#[derive(Default, Debug, Clone)]
pub struct State(multikey::MultiKey, Option<led::Led>);
impl State {
    #[must_use] pub fn new() -> Self { Self::default() }

    /// Returns `true` if the given [`Key`] is known to be currently pressed, `false` otherwise
    #[must_use]
    pub fn is_pressed(&self, key: Key) -> bool {
        match multikey::MultiKey::try_from(key) {
            Ok(multi) => self.0.contains(multi),
            _ => false,
        }
    }

    /// Returns every [`Key`] for which [`Self::is_pressed`] would return `true`
    /// (there may be up to five pressed simultaneously on the G11)
    pub fn iter_pressed(&self) -> impl Iterator<Item = Key> {
        self.0.iter()
            .filter_map(|key| Key::try_from(key).ok())
    }

    /// Updates the [`State`] by inspecting the given bytes (which should have been acquired from the G11's HID interface).
    /// This, combined with the previously known state, will allow an [`Event`] to be inferred as the signal's meaning.
    ///
    /// Note: The G11 macro interface emits HID packets of 9 bytes. Anything less will produce an [`EventError`]
    /// The provided buffer may be larger than that, but only the first 9 bytes will be inspected.
    pub fn try_consume_event(&mut self, usb_bytes: &[u8]) -> Result<Event, EventError> {
        let new_state = multikey::MultiKey::try_from(usb_bytes)
            .map_err(|_| EventError::InvalidBytes)?;

        let old_state = mem::replace(&mut self.0, new_state);

        //Handle the most likely states first (going from nothing to pressed, or from pressed to nothing)
        if old_state.is_empty() {
            Key::try_from(new_state)
                .map_err(|_| EventError::UnreconcilableState)
                .map(|key| Event { key, action: Action::Pressed })
        }
        else if new_state.is_empty() {
            Key::try_from(old_state)
                .map_err(|_| EventError::UnreconcilableState)
                .map(|key| Event { key, action: Action::Released })
        }
        else { //Multiple keys are/were pressed, so a more thorough diff
            let changed_key = new_state.symmetric_difference(old_state);
            Key::try_from(changed_key)
                .map_err(|_| EventError::UnreconcilableState)
                .map(|key| {
                    let action = if old_state.contains(changed_key) { Action::Released } else { Action::Pressed };
                    Event { key, action }
                })
        }
    }

    /// Produces an HID Feature Report (which you may then submit to the G11's HID interface)
    /// that will cause only the given [`Key`] LEDs to be lit (and all others unlit).
    ///
    /// Will return `None` if the request would be fruitless (if these exact LEDs are already lit)
    #[must_use]
    pub fn set_exact_lit_leds(&mut self, lit_keys: &[Key]) -> Option<[u8; 4]> {
        self.set_exact_lit_leds_if_changed(
            lit_keys.iter()
                .filter_map(|key| led::Led::try_from(*key).ok())
                .reduce(|a, b| a | b)
                .unwrap_or_default()
        )
    }

    /// Produces an HID Feature Report (which you may then submit to the G11's HID interface)
    /// that will cause the given [`Key`] LED to transition from unlit to lit, leaving all other LEDs alone.
    ///
    /// Will return `None` if the request would be fruitless (if the LED is already lit or a key with no LED is passed)
    #[must_use]
    pub fn light_led(&mut self, key: Key) -> Option<[u8; 4]> {
        led::Led::try_from(key).ok()
            .map(|new| self.1.map_or(new, |current | current | new))
            .and_then(|desired| self.set_exact_lit_leds_if_changed(desired))
    }

    /// Produces an HID Feature Report (which you may then submit to the G11's HID interface)
    /// that will cause the given [`Key`] LED to transition from lit to unlit, leaving all other LEDs alone.
    ///
    /// Will return `None` if the request would be fruitless (if the LED is already unlit or a key with no LED is passed)
    #[must_use]
    pub fn extinguish_led(&mut self, key: Key) -> Option<[u8; 4]> {
        led::Led::try_from(key).ok()
            .and_then(|old| self.1.map(|current| current & !old))
            .and_then(|desired| self.set_exact_lit_leds_if_changed(desired))
    }

    fn set_exact_lit_leds_if_changed(&mut self, desired: led::Led) -> Option<[u8; 4]> {
        if self.1.is_some_and(|current| current == desired) {
            None
        } else {
            self.1 = Some(desired);
            Some(desired.into())
        }
    }
}

/// Errors that may arise during [`State::try_consume_event`]
#[derive(Debug, Display, Error, Clone)]
pub enum EventError {
    /// The given bytes did not represent a valid G11 macro USB event.
    /// Internal state was not updated.
    #[display("invalid bytes")]
    InvalidBytes,
    /// The given bytes were valid, and the internal state was updated.
    /// However, an individual [`Action`] could not be determined as the cause
    /// (for example, if the first event observed is a 'release')
    #[display("unreconcilable state")]
    UnreconcilableState,
}

#[derive(Debug, Display, Error, Default, Clone, Copy, PartialEq, Eq)]
#[display("unrecognized key")]
#[doc(hidden = true)]
pub struct UnrecognizedKey;


#[cfg(test)]
mod tests {
    use super::*;

    /// <https://rust-lang.github.io/api-guidelines/interoperability.html#types-are-send-and-sync-where-possible-c-send-sync>
    mod auto_trait_regression {
        use super::*;

        #[test]
        fn test_send() {
            fn assert_send<T: Send>() {}
            assert_send::<Event>();
            assert_send::<EventError>();
            assert_send::<State>();
        }

        #[test]
        fn test_sync() {
            fn assert_sync<T: Sync>() {}
            assert_sync::<Event>();
            assert_sync::<EventError>();
            assert_sync::<State>();
        }
    }
}