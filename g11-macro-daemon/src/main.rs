mod config;
mod bindings;
mod record;
mod steps;
mod evdev_input;

use enigo::{Enigo, Settings};
use hidapi::HidApi;
use log::{error, info, warn};
use g11_macro_keys::{usb_id, Action, Event};

fn main() {
    env_logger::init();

    let settings = config::load_settings();
    let config::Config { key_bindings } = config::ensure_and_load_config_file().expect("Unable to load config");
    let mut binding_banks = bindings::BindingBanks::from(key_bindings);
    let mut enigo = Enigo::new(&Settings::default()).expect("Unable to acquire Enigo API");

    match settings.keyboard {
        config::KeyboardModel::G11 => {
            info!("Starting in G11 mode (raw HID)");
            run_g11(&mut binding_banks, &mut enigo);
        }
        config::KeyboardModel::G15 => {
            info!("Starting in G15 mode (evdev)");
            run_g15(&mut binding_banks, &mut enigo, settings.device_path.as_deref());
        }
    }
}

fn run_g11(binding_banks: &mut bindings::BindingBanks, enigo: &mut Enigo) {
    let api = HidApi::new().expect("Unable to acquire HID API");
    let hid = api.open(usb_id::VENDOR_LOGITECH, usb_id::PRODUCT_G11_MACRO).expect("Unable to open device");
    let mut usb_buf = [0_u8; 9];
    let mut state = g11_macro_keys::State::default();

    //Start it off with the first bank of bindings
    let _ = state.set_exact_lit_leds(&[g11_macro_keys::Key::M(1)])
        .and_then(|usb_report| hid.send_feature_report(&usb_report).ok());

    loop {
        assert_eq!(hid.read(&mut usb_buf).expect("could not read from device"), 9);
        match state.try_consume_event(&usb_buf) {
            Ok(Event { action: Action::Pressed, key: key@g11_macro_keys::Key::M(m_key) }) => {
                binding_banks.activate_bank(m_key);
                if let Some(usb_report) = state.set_exact_lit_leds(&[key]) {
                    let _ = hid.send_feature_report(&usb_report)
                        .inspect_err(|err| error!("Unable to update LEDs! Cause: {err:#?}"));
                }
            }
            Ok(Event { action: Action::Released, key: g11_macro_keys::Key::MR }) =>
                if let Some(new_binding) = record::run_event_loop(&api, &hid, &mut state, binding_banks.active_bank()) {
                    binding_banks.replace(new_binding.clone());
                    let _ = config::save_recorded_macro(new_binding)
                        .inspect_err(|err| error!("Unable to save recorded macro! Cause: {err:#?}"));
                },
            Ok(event) =>
                if let Some(script) = binding_banks.script_for(event) {
                    for step in script {
                        let _ = step.execute(enigo)
                            .inspect_err(|err| error!("Unable to execute {step:?}! Cause: {err:#?}"));
                    }
                },
            Err(err) =>
                error!("\n\nError interpreting USB output! {err:#?}; bytes were {usb_buf:?}"),
        }
    }
}

fn run_g15(binding_banks: &mut bindings::BindingBanks, enigo: &mut Enigo, device_path: Option<&str>) {
    let mut input = evdev_input::EvdevInput::open(device_path).expect("Unable to open G15 evdev device");

    // LED control is best-effort via hidraw on the G15 LCD/keypad interface (046d:c222).
    // If it fails to open, the daemon still works — just without LED feedback.
    let _hid_api = HidApi::new().ok(); // Must outlive hid_for_leds
    let hid_for_leds = _hid_api.as_ref()
        .and_then(|api| api.open(usb_id::VENDOR_LOGITECH, usb_id::PRODUCT_G15_LCD)
            .inspect_err(|err| warn!("Could not open G15 HID device for LED control: {err}. LEDs will be unavailable."))
            .ok());

    let mut state = g11_macro_keys::State::default();

    if let Some(ref hid) = hid_for_leds {
        let _ = state.set_exact_lit_leds(&[g11_macro_keys::Key::M(1)])
            .and_then(|usb_report| hid.send_feature_report(&usb_report).ok());
        info!("G15 LED control available");
    }

    loop {
        match input.read_event() {
            Ok(Event { action: Action::Pressed, key: key@g11_macro_keys::Key::M(m_key) }) => {
                binding_banks.activate_bank(m_key);
                if let Some(ref hid) = hid_for_leds {
                    if let Some(usb_report) = state.set_exact_lit_leds(&[key]) {
                        let _ = hid.send_feature_report(&usb_report)
                            .inspect_err(|err| error!("Unable to update LEDs! Cause: {err:#?}"));
                    }
                } else {
                    info!("Switched to M{m_key} bank");
                }
            }
            Ok(Event { action: Action::Released, key: g11_macro_keys::Key::MR }) => {
                warn!("MR recording is not yet supported in G15 mode");
            }
            Ok(event) =>
                if let Some(script) = binding_banks.script_for(event) {
                    for step in script {
                        let _ = step.execute(enigo)
                            .inspect_err(|err| error!("Unable to execute {step:?}! Cause: {err:#?}"));
                    }
                },
            Err(err) =>
                error!("Error reading evdev event: {err}"),
        }
    }
}
