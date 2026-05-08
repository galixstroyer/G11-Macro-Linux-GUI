//! Manages the user configuration at rest, with file(s) stored
//! in the `g11-macro-daemon` subdirectory of `$XDG_CONFIG` (usually `~/.config`)

use std::{
    fs::File,
    io::{self, Write, Read, BufRead, BufReader},
    path::{PathBuf, Path},
};
use derive_more::{Display, Error};
use enigo::Direction;
use log::warn;
use serde::{Deserialize, Serialize};
use ron::{
    error::{Position, SpannedError},
    extensions::Extensions,
    ser::PrettyConfig,
};
use crate::steps::Step;

#[derive(Default, Debug, PartialEq, Deserialize, Serialize)]
pub struct Config {
    pub key_bindings: Vec<KeyBinding>,
}

/// Which keyboard model the daemon should target
#[derive(Debug, Default, Clone, Copy, PartialEq, Deserialize, Serialize)]
pub enum KeyboardModel {
    #[default]
    G11,
    G15,
}

/// Daemon-level settings (separate from key bindings)
#[derive(Debug, Default, PartialEq, Deserialize, Serialize)]
pub struct Settings {
    #[serde(default)]
    pub keyboard: KeyboardModel,

    /// Optional override for the evdev device path (e.g. `/dev/input/event17`).
    /// Only used in G15 mode. If `None`, the daemon will auto-detect.
    #[serde(default)]
    pub device_path: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct KeyBinding {
    /// The `M` key (numbered `1 ..= 3`) whose bank must be active for this binding to apply
    pub m: u8,
    /// The `G` key (numbered `1 ..= 18`)
    pub g: u8,
    /// If set to `Press`, will run the script as soon as the key is pressed. Otherwise, it will wait for release.
    pub on: Direction,
    /// The sequence of steps to be executed
    pub script: Vec<Step>,
}

pub const XDG_PREFIX: &str = "g11-macro-daemon";
pub const XDG_CONFIG_KEY_BINDINGS: &str = "key_bindings.ron";
pub const XDG_CONFIG_KEY_RECORDINGS: &str = "key_recordings.ron";
pub const XDG_CONFIG_SETTINGS: &str = "settings.ron";

/// Loads the [`XDG_CONFIG_KEY_BINDINGS`] file, creating an empty stub if it does not yet exist.
pub fn ensure_and_load_config_file() -> Result<Config, LoadError> {
    let app_config_dir = xdg::BaseDirectories::with_prefix(XDG_PREFIX);
    let key_bindings_path = app_config_dir.place_config_file(XDG_CONFIG_KEY_BINDINGS).map_err(LoadError::Locating)?;
    let key_recordings_path = app_config_dir.find_config_file(XDG_CONFIG_KEY_RECORDINGS);

    let mut key_bindings =
        if key_bindings_path.try_exists().map_err(LoadError::Locating)? {
            try_load_key_bindings(&key_bindings_path, || File::open(&key_bindings_path), None, false)?
        } else { //Try to create a default file with instructions/samples
            File::create_new(&key_bindings_path)
                .and_then(|mut file| file.write_all(include_bytes!("config_stub.ron")))
                .inspect_err(|err| warn!("Failed to create stub for key bindings file: {}. Ignoring...\n\tCause: {err:#?}", key_bindings_path.display()))
                .map_or_else(|_| vec![], |_| vec![])
        };

    if let Some(key_recordings_path) = key_recordings_path {
        key_bindings.extend(
            try_load_key_bindings(&key_recordings_path, || File::open(&key_recordings_path), None, false)?
        );
    }

    Ok(Config { key_bindings })
}

/// Loads the [`XDG_CONFIG_SETTINGS`] file, returning defaults if it does not exist or cannot be parsed.
pub fn load_settings() -> Settings {
    let app_config_dir = xdg::BaseDirectories::with_prefix(XDG_PREFIX);
    app_config_dir.find_config_file(XDG_CONFIG_SETTINGS)
        .and_then(|path| {
            std::fs::read_to_string(&path).ok()
                .and_then(|text| ron::from_str(&text)
                    .inspect_err(|err| warn!("Failed to parse settings file: {err:#?}. Using defaults."))
                    .ok())
        })
        .unwrap_or_default()
}

/// Parse a key bindings file, being tolerant of one or both of the outer list brackets being absent
/// TODO This is pretty hacky and gross. Would be more appropriate to just write a parser.
fn try_load_key_bindings<R: Read>(
    key_bindings_path: &Path,
    key_bindings_file: impl Fn() -> io::Result<R>,
    replace_missing_open_bracket: Option<Position>,
    replace_missing_close_bracket: bool,
) -> Result<Vec<KeyBinding>, LoadError> {
    let mut outer_buf = String::new(); //Not terribly clean, but ensures that we don't run afoul of lifetimes.
    let reader: Box<dyn Read> = {
        let mut reader: Box<dyn Read> =
            key_bindings_file()
                .map(Box::new)
                .map_err(|err| LoadError::Loading(key_bindings_path.into(), err))?;

        if let Some(missing_open_bracket_pos) = replace_missing_open_bracket {
            let mut lines = BufReader::new(reader).lines();
            for line in lines.by_ref().take(missing_open_bracket_pos.line - 1) {
                outer_buf.push_str(&line.map_err(|err| LoadError::Loading(key_bindings_path.into(), err))?);
                outer_buf.push('\n');
            }
            outer_buf.push_str("\n[\n");
            for line in lines {
                outer_buf.push_str(&line.map_err(|err| LoadError::Loading(key_bindings_path.into(), err))?);
                outer_buf.push('\n');
            }
            reader = Box::new(BufReader::new(outer_buf.as_bytes()));
        }

        if replace_missing_close_bracket {
            reader = Box::new(reader.chain(BufReader::new(&b"\n]\n"[..])));
        }

        reader
    };

    ron::Options::default()
        .from_reader(reader)
        .or_else(|err| match (&err.code, replace_missing_open_bracket, replace_missing_close_bracket) {
            (ron::Error::ExpectedArray, None, false) => {
                warn!("Possibly missing the open bracket in {}; will attempt a more lenient parse, but you should fix the file.", key_bindings_path.display());
                try_load_key_bindings(key_bindings_path, key_bindings_file, Some(err.position), false)
                    .map_err(|_| LoadError::unable_to_parse_or_load_config(key_bindings_path.into(), err)) //If tolerant parse fails, just return the original error
            }
            (ron::Error::ExpectedStructName(name), _, false) if name == "KeyBinding" => {
                warn!("Possibly missing the close bracket in {}; will attempt a more lenient parse, but you should fix the file.", key_bindings_path.display());
                try_load_key_bindings(key_bindings_path, key_bindings_file, replace_missing_open_bracket, true)
                    .map_err(|_| LoadError::unable_to_parse_or_load_config(key_bindings_path.into(), err)) //If tolerant parse fails, just return the original error
            }
            _ => Err(LoadError::unable_to_parse_or_load_config(key_bindings_path.into(), err))
        })
}

/// Creates/rewrites the [`XDG_CONFIG_KEY_RECORDINGS`] file, adding the given binding.
/// If an existing binding exists with the same coordinates, then it will be replaced.
/// Otherwise, the new binding will be appended to the list.
pub fn save_recorded_macro(mut new_key_binding: KeyBinding) -> Result<(), SaveRecordedMacroError> {
    let ron = ron::Options::default().with_default_extension(Extensions::IMPLICIT_SOME | Extensions::EXPLICIT_STRUCT_NAMES);
    let app_config_dir = xdg::BaseDirectories::with_prefix(XDG_PREFIX);
    let key_recordings_path = app_config_dir.place_config_file(XDG_CONFIG_KEY_RECORDINGS)
        .map_err(LoadError::Locating).map_err(SaveRecordedMacroError::Loading)?;

    let mut key_bindings: Vec<KeyBinding> =
        if key_recordings_path.try_exists().map_err(LoadError::Locating).map_err(SaveRecordedMacroError::Loading)? {
            let key_recordings_file =
                File::open(&key_recordings_path)
                    .map_err(|err| LoadError::Loading(key_recordings_path.clone(), err)).map_err(SaveRecordedMacroError::Loading)?;
            ron.from_reader(key_recordings_file)
                .map_err(|err| LoadError::unable_to_parse_or_load_config(key_recordings_path.clone(), err)).map_err(SaveRecordedMacroError::Loading)?
        }
        else { vec![] };

    let existing_key_binding =
        key_bindings.iter_mut().rfind(|existing|
            existing.g == new_key_binding.g &&
            existing.m == new_key_binding.m &&
            existing.on == new_key_binding.on
        );

    if let Some(existing_key_binding) = existing_key_binding {
        std::mem::swap(&mut existing_key_binding.script, &mut new_key_binding.script);
    }
    else {
        key_bindings.push(new_key_binding);
    }

    File::create(&key_recordings_path)
        .and_then(|mut key_recordings_file| {
            key_recordings_file.write_all(include_bytes!("config_stub_record.ron"))?;
            Ok(key_recordings_file)
        })
        .and_then(|key_recordings_file|
            ron.to_io_writer_pretty(key_recordings_file, &key_bindings, PrettyConfig::default())
                .map_err(io::Error::other)
        )
        .map_err(|err| SaveRecordedMacroError::Saving(key_recordings_path.clone(), err))
}

#[derive(Debug, Display, Error)]
pub enum LoadError {
    #[display("Unable to locate the config file! Cause: {_0}")]
    Locating(io::Error),
    #[display("Unable to load the config from {}! Cause: {_1}", _0.display())]
    Loading(PathBuf, io::Error),
    #[display("Unable to parse the config from {}! Cause: {_1}", _0.display())]
    Parsing(PathBuf, SpannedError),
}
impl LoadError {
    fn unable_to_parse_or_load_config(path: PathBuf, ron_err: SpannedError) -> Self {
        if let SpannedError { code: ron::Error::Io(io_err), .. } = ron_err {
            Self::Loading(path, io::Error::other(io_err))
        } else {
            Self::Parsing(path, ron_err)
        }
    }
}

#[derive(Debug, Display, Error)]
pub enum SaveRecordedMacroError {
    #[display("Unable to load the existing recordings file! Cause: {_0}")]
    Loading(LoadError),
    #[display("Unable to save the recorded macro to {}! Cause: {_1}", _0.display())]
    Saving(PathBuf, io::Error),
}


#[cfg(test)]
mod tests {
    use test_log::test;
    use enigo::Direction::*;
    use super::*;

    #[test] fn tolerant_of_missing_open_bracket(){ parses_correctly(true, false, false); }
    #[test] fn tolerant_of_missing_close_bracket(){ parses_correctly(false, true, false); }
    #[test] fn tolerant_of_missing_brackets(){ parses_correctly(true, true, false); }
    #[test] fn tolerant_of_missing_extensions(){ parses_correctly(false, false, true); }
    #[test] fn parses_correctly_when_valid() { parses_correctly(false, false, false); }
    fn parses_correctly(missing_open_bracket: bool, missing_close_bracket: bool, missing_extensions: bool) {
        let config = Config {
            key_bindings: vec![
                KeyBinding {
                    m: 1,
                    g: 1,
                    on: Press,
                    script: vec![
                        Step::Key(enigo::Key::Control,      Press),
                        Step::Key(enigo::Key::Unicode('-'), Click),
                        Step::Key(enigo::Key::Control,      Release),
                    ],
                },
                KeyBinding {
                    m: 1,
                    g: 2,
                    on: Press,
                    script: vec![
                        Step::Key(enigo::Key::Control,      Press),
                        Step::Key(enigo::Key::Unicode('0'), Click),
                        Step::Key(enigo::Key::Control,      Release),
                    ],
                },
            ],
        };

        let input = format!(r"
            {extensions}
            {open}
                KeyBinding(
                    m: 1,
                    g: 1,
                    on: Press,
                    script: [
                        Key(Control, Press),
                        Key(Unicode('-'), Click),
                        Key(Control, Release),
                    ],
                ),
                KeyBinding(
                    m: 1,
                    g: 2,
                    on: Press,
                    script: [
                        Key(Control, Press),
                        Key(Unicode('0'), Click),
                        Key(Control, Release),
                    ],
                ),
            {close}
        ", open = if missing_open_bracket { "" } else { "[" }, close = if missing_close_bracket { "" } else { "]" },
           extensions = if missing_extensions { "" } else { "#![enable(explicit_struct_names, implicit_some)]" },
        );

        let parsed = try_load_key_bindings(Path::new("n/a"), || Ok(BufReader::new(input.as_bytes())), None, false).expect("does not fail to parse");

        assert_eq!(parsed, config.key_bindings);
    }

    #[test]
    fn prebaked_stub_is_valid() {
        let parsed = ron::from_str::<Vec<KeyBinding>>(include_str!("config_stub.ron"))
            .expect("does not fail to parse");

        assert_eq!(parsed, vec![]);
    }

    #[test]
    fn settings_defaults_to_g11() {
        let settings = Settings::default();
        assert_eq!(settings.keyboard, KeyboardModel::G11);
        assert_eq!(settings.device_path, None);
    }

    #[test]
    fn settings_parses_g15_from_gui_format() {
        let input = r#"
            #![enable(explicit_struct_names)]
            Settings(
                keyboard: G15,
            )
        "#;
        let settings: Settings = ron::from_str(input).expect("does not fail to parse");
        assert_eq!(settings.keyboard, KeyboardModel::G15);
        assert_eq!(settings.device_path, None);
    }

    #[test]
    fn settings_parses_g15_with_device_path() {
        let input = r#"
            #![enable(explicit_struct_names)]
            Settings(
                keyboard: G15,
                device_path: Some("/dev/input/event17"),
            )
        "#;
        let settings: Settings = ron::from_str(input).expect("does not fail to parse");
        assert_eq!(settings.keyboard, KeyboardModel::G15);
        assert_eq!(settings.device_path, Some("/dev/input/event17".to_owned()));
    }

    #[test]
    fn settings_parses_g11_minimal() {
        let input = "Settings(keyboard: G11)";
        let settings: Settings = ron::from_str(input).expect("does not fail to parse");
        assert_eq!(settings.keyboard, KeyboardModel::G11);
    }
}
