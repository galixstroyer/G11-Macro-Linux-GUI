# g11-macro

Full Linux support for the macro keys on a **Logitech G11** (and possibly G15) gaming keyboard, including a graphical configuration tool.

---

## Quick Install

```bash
git clone https://github.com/your-username/g11-macro.git
cd g11-macro
bash install.sh
```

The installer handles everything automatically:

- Installs system dependencies (GTK4, libadwaita, PyGObject)
- Installs or updates Rust (1.85+ required)
- Builds and installs the daemon binary
- Installs udev rules for USB HID access
- Sets up the systemd user service
- Creates a Python virtual environment
- Adds a desktop icon and app menu entry

**Supported distributions:** Debian/Ubuntu/Kubuntu · Fedora · Arch Linux · openSUSE

After installation, launch from the desktop icon, your app menu (search "G11"), or the terminal:

```bash
g11-macro-gui
```

---

## Components

| Component | Description |
|---|---|
| [`g11-macro-daemon`](g11-macro-daemon) | Rust daemon that runs in the background and executes macros when G keys are pressed |
| [`g11-macro-keys`](g11-macro-keys) | Base Rust library for reading G11 key events and controlling LEDs over USB HID |
| [`gui/`](gui) | Python GTK4 GUI for configuring macros, controlling the daemon, and managing LEDs |

---

## GUI

A full graphical interface built with Python, GTK4, and libadwaita.

![G11 Macro Manager](path234.png)

### Features

- **Visual keyboard layout** — all 18 G keys across 3 M banks, with assigned keys highlighted
- **Macro editor** — add, edit, remove, and reorder steps with a form-based dialog
- **6 step types** — Key stroke, Type text, Mouse button, Move mouse, Scroll, Run program
- **Key repeat** — set any key step to repeat 1–100 times (e.g. Backspace ×5)
- **Daemon controls** — start, stop, restart, enable auto-start on login
- **Live log viewer** — tail the daemon's systemd journal directly in the app
- **LED panel** — toggle M1/M2/M3/MR LEDs on and off
- **Recordings viewer** — see macros recorded with the MR key
- **Desktop & app launcher** — launchable from the desktop and the app menu

### Requirements

- Python 3.10+
- GTK 4 + libadwaita (`python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`)
- `hidapi` Python package (for LED control — optional)

> **Tip:** Use `bash install.sh` to set everything up automatically instead of the manual steps below.

<details>
<summary>Manual setup</summary>

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1

# Create venv with access to system GTK packages
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# Install optional LED control package
pip install hidapi

# Run
python3 gui/main.py
```

</details>

### Structure

```
gui/
├── main.py                     # Entry point
├── app.py                      # Adw.Application
├── assets/style.css            # Custom dark theme
├── config/
│   ├── models.py               # Data classes (KeyBinding, Step types)
│   ├── parser.py               # RON file parser and serializer
│   └── manager.py              # Config file paths and load/save
├── daemon/
│   └── service.py              # systemctl interface
├── hardware/
│   └── leds.py                 # HID LED control via hidapi
└── ui/
    ├── main_window.py          # Main window with sidebar
    ├── keyboard_widget.py      # Visual G key grid
    ├── macros_page.py          # Keyboard + editor split view
    ├── macro_editor.py         # Step list editor
    ├── step_row.py             # Individual step row widget
    ├── step_editor_dialog.py   # Step type form dialog
    ├── service_page.py         # Daemon controls + log viewer
    └── led_page.py             # LED toggles
```

---

## Daemon

See [`g11-macro-daemon/`](g11-macro-daemon) for full documentation.

### Configuration

Macros are stored in `~/.config/g11-macro-daemon/key_bindings.ron`.

```ron
#![enable(explicit_struct_names, implicit_some)]
[
    KeyBinding(
        m: 1,
        g: 1,
        on: Press,
        script: [
            Key(Control, Press),
            Key(Unicode('w'), Click),
            Key(Control, Release),
        ],
    ),
    KeyBinding(
        m: 2,
        g: 1,
        on: Press,
        script: [
            Run(Program("gnome-calculator")),
        ],
    ),
]
```

Restart the service after editing the config file manually:

```bash
systemctl --user restart g11-macro-daemon
```

> The GUI saves and restarts the daemon automatically — no manual editing needed.

### Useful commands

```bash
# View daemon logs
journalctl --user -u g11-macro-daemon -f

# Check service status
systemctl --user status g11-macro-daemon
```

<details>
<summary>Manual daemon install (without install.sh)</summary>

```bash
# 1. Install Rust (1.85+ required)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# 2. Install udev rules (allows USB HID access without root)
sudo tee /etc/udev/rules.d/g11-macro.rules << 'EOF'
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c225", MODE="0666", ACTION=="add", TAG+="systemd", ENV{SYSTEMD_USER_WANTS}+="g11-macro-daemon.service"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c221", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger

# 3. Build and install
cargo install --path g11-macro-daemon

# 4. Create systemd service
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/g11-macro-daemon.service << EOF
[Unit]
Description=Logitech G11 Macro Key Daemon
StartLimitIntervalSec=10

[Service]
ExecStart=$HOME/.cargo/bin/g11-macro-daemon
Environment="RUST_LOG=WARN,g11=INFO"
Restart=always

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now g11-macro-daemon
```

</details>

---

## Hardware Notes

The G11 macro interface (USB `046d:c225`) supports:

| Feature | Supported |
|---|---|
| G1–G18 key events | Yes |
| M1/M2/M3 bank LEDs (on/off) | Yes |
| MR LED (on/off) | Yes |
| Backlight on/off | Physical key only |
| Backlight brightness | Physical key only (3 levels) |
| Per-key RGB | No (fixed blue hardware) |

### G15 Compatibility

The G15 keyboard reportedly uses the same macro interface. It may work, but has not been tested.

---

## License

MIT — see [LICENSE](LICENSE)
