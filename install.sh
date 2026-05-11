#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  G11 Macro Manager — Installer
#  Supported: Debian/Ubuntu/Kubuntu, Fedora, Arch Linux, openSUSE, Void Linux
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

# ── Options ───────────────────────────────────────────────────────────────────
NO_SERVICE=false
for arg in "$@"; do
    case "$arg" in
        --no-service) NO_SERVICE=true ;;
        --help|-h)
            echo "Usage: bash install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-service   Skip daemon service setup (systemd/runit)."
            echo "                 You can start the daemon from the GUI or manually."
            echo "  --help, -h     Show this help message."
            exit 0
            ;;
        *) echo "Unknown option: $arg (try --help)"; exit 1 ;;
    esac
done

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

STEP=0
TOTAL_STEPS=9

_step() { echo -e "\n${BLUE}${BOLD}[$(( ++STEP ))/${TOTAL_STEPS}]${NC} ${BOLD}$*${NC}"; }
_ok()   { echo -e "    ${GREEN}✓${NC}  $*"; }
_warn() { echo -e "    ${YELLOW}⚠${NC}  $*"; }
_err()  { echo -e "    ${RED}✗${NC}  $*"; }
_info() { echo -e "    ${CYAN}→${NC}  $*"; }

die() { _err "$*"; exit 1; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SCRIPT_DIR/Cargo.toml" && -d "$SCRIPT_DIR/gui" ]] \
    || die "Run this script from the g11-macro project root."

PROJECT_DIR="$SCRIPT_DIR"
GUI_DIR="$PROJECT_DIR/gui"
VENV_DIR="$PROJECT_DIR/.venv"
ICON_PATH="$PROJECT_DIR/path234.png"
LAUNCHER="$HOME/.local/bin/g11-macro-gui"
APP_DESKTOP="$HOME/.local/share/applications/g11-macro.desktop"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"

# ── Detect OS, package manager, init system, desktop environment ─────────────
PKG_MANAGER="unknown"
DISTRO="unknown"
DISTRO_PRETTY="Unknown Linux"
CURRENT_DE="unknown"
INIT_SYSTEM="unknown"

if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    DISTRO="${ID:-unknown}"
    DISTRO_PRETTY="${PRETTY_NAME:-Unknown Linux}"
fi

for pm in apt-get dnf pacman zypper xbps-install; do
    command -v "$pm" &>/dev/null && { PKG_MANAGER="$pm"; break; }
done
# normalise apt-get → apt
[[ "$PKG_MANAGER" == "apt-get" ]] && PKG_MANAGER="apt"
[[ "$PKG_MANAGER" == "xbps-install" ]] && PKG_MANAGER="xbps"

# Detect init system (skip if --no-service)
if [[ "$NO_SERVICE" == true ]]; then
    INIT_SYSTEM="none"
elif command -v systemctl &>/dev/null && systemctl --user status &>/dev/null 2>&1; then
    INIT_SYSTEM="systemd"
elif command -v sv &>/dev/null; then
    INIT_SYSTEM="runit"
fi

de_raw="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-}}"
de_raw="${de_raw,,}"
case "$de_raw" in
    *kde*|*plasma*)   CURRENT_DE="kde"      ;;
    *gnome*)          CURRENT_DE="gnome"    ;;
    *xfce*)           CURRENT_DE="xfce"     ;;
    *cinnamon*)       CURRENT_DE="cinnamon" ;;
    *mate*)           CURRENT_DE="mate"     ;;
    *lxqt*)           CURRENT_DE="lxqt"     ;;
esac

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}        G11 Macro Manager — Installer${NC}"
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  OS       ${CYAN}${DISTRO_PRETTY}${NC}"
echo -e "  Packages ${CYAN}${PKG_MANAGER}${NC}"
echo -e "  Init     ${CYAN}${INIT_SYSTEM}${NC}"
echo -e "  Desktop  ${CYAN}${CURRENT_DE}${NC}"
echo -e "  Project  ${CYAN}${PROJECT_DIR}${NC}"
echo ""

# ── Step 1 · System packages ──────────────────────────────────────────────────
_step "Installing system dependencies"

_install_apt() {
    sudo apt-get update -qq
    sudo apt-get install -y \
        python3-gi python3-gi-cairo python3-venv python3-full \
        gir1.2-gtk-4.0 gir1.2-adw-1 \
        libudev-dev \
        libxkbcommon-dev \
        libxdo-dev
}

_install_dnf() {
    sudo dnf install -y \
        python3-gobject python3-gobject-cairo \
        gtk4 libadwaita \
        systemd-devel libxkbcommon-devel \
        libxdo-devel
}

_install_pacman() {
    sudo pacman -S --noconfirm --needed \
        python-gobject python-cairo \
        gtk4 libadwaita \
        libxkbcommon \
        xdotool
}

_install_zypper() {
    sudo zypper install -y \
        python3-gobject python3-gobject-cairo \
        typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 \
        libudev-devel libxkbcommon-devel \
        xdotool-devel
}

_install_xbps() {
    sudo xbps-install -Sy \
        python3 python3-gobject python3-cairo \
        gtk4 libadwaita \
        libudev-devel libxkbcommon-devel \
        python3-virtualenv \
        hidapi gobject-introspection \
        xdotool-devel
}

case "$PKG_MANAGER" in
    apt)    _install_apt    && _ok "Packages installed (apt)" ;;
    dnf)    _install_dnf    && _ok "Packages installed (dnf)" ;;
    pacman) _install_pacman && _ok "Packages installed (pacman)" ;;
    zypper) _install_zypper && _ok "Packages installed (zypper)" ;;
    xbps)   _install_xbps   && _ok "Packages installed (xbps)" ;;
    *) _warn "Unknown package manager — install GTK4 + libadwaita + PyGObject manually." ;;
esac

# ── Step 2 · Rust 1.85+ ───────────────────────────────────────────────────────
_step "Checking Rust toolchain (≥ 1.85 required)"

_cargo_minor() {
    # Outputs the minor version number of the active cargo, e.g. 85
    cargo --version 2>/dev/null | grep -oP '1\.\K[0-9]+' | head -1
}

_source_cargo_env() {
    [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env" || true
}

_source_cargo_env

if command -v rustup &>/dev/null; then
    _info "rustup found — updating stable toolchain"
    rustup update stable --no-self-update 2>&1 | tail -1
    _source_cargo_env
    _ok "$(rustc --version)"
else
    MINOR="$(_cargo_minor)"
    if [[ -n "$MINOR" ]] && (( MINOR >= 85 )); then
        _ok "System Rust is new enough (1.${MINOR})"
    else
        if [[ -n "$MINOR" ]]; then
            _warn "System Rust (1.${MINOR}) is too old — installing rustup"
        else
            _info "No Rust found — installing rustup"
        fi
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
            | sh -s -- -y --default-toolchain stable --no-modify-path
        _source_cargo_env
        _ok "$(rustc --version) installed"
    fi
fi

command -v cargo &>/dev/null || die "cargo not found after Rust setup. Open a new terminal and re-run."

# ── Step 3 · Build & install daemon ───────────────────────────────────────────
_step "Building and installing g11-macro-daemon"

_info "This may take a minute on first build…"
if cargo install --path "$PROJECT_DIR/g11-macro-daemon"; then
    _ok "Installed to $HOME/.cargo/bin/g11-macro-daemon"
else
    die "Build failed — see output above."
fi

# ── Step 4 · udev rules ───────────────────────────────────────────────────────
_step "Installing udev rules"

UDEV_FILE="/etc/udev/rules.d/g11-macro.rules"

if [[ "$INIT_SYSTEM" == "systemd" ]]; then
    sudo tee "$UDEV_FILE" > /dev/null << 'UDEV'
# Logitech G11 — macro interface (allow LED + key event access)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c225", MODE="0666", ACTION=="add", TAG+="systemd", ENV{SYSTEMD_USER_WANTS}+="g11-macro-daemon.service"
# Logitech G11 — standard keyboard interface (needed for MR macro recording)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c221", MODE="0666"

# Logitech G15 — LCD/keypad interface (G-keys handled by lg-g15 kernel driver)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c222", MODE="0666", ACTION=="add", TAG+="systemd", ENV{SYSTEMD_USER_WANTS}+="g11-macro-daemon.service"
# Logitech G15 — grant access to the evdev G-key input device
SUBSYSTEM=="input", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c222", MODE="0666"
UDEV
else
    # Non-systemd: udev rules without systemd auto-start tags
    sudo tee "$UDEV_FILE" > /dev/null << 'UDEV'
# Logitech G11 — macro interface (allow LED + key event access)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c225", MODE="0666"
# Logitech G11 — standard keyboard interface (needed for MR macro recording)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c221", MODE="0666"

# Logitech G15 — LCD/keypad interface (G-keys handled by lg-g15 kernel driver)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c222", MODE="0666"
# Logitech G15 — grant access to the evdev G-key input device
SUBSYSTEM=="input", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c222", MODE="0666"
UDEV
fi

sudo udevadm control --reload-rules && sudo udevadm trigger
_ok "udev rules → $UDEV_FILE"

# ── Step 5 · Daemon service ──────────────────────────────────────────────────
_step "Setting up daemon service"

if [[ "$INIT_SYSTEM" == "systemd" ]]; then
    SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SERVICE_DIR"

    cat > "$SERVICE_DIR/g11-macro-daemon.service" << EOF
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
    systemctl --user enable g11-macro-daemon

    if systemctl --user restart g11-macro-daemon 2>/dev/null \
    || systemctl --user start  g11-macro-daemon 2>/dev/null; then
        _ok "Daemon enabled and started (systemd)"
    else
        _warn "Daemon service created but could not start — plug in your keyboard first"
    fi

elif [[ "$INIT_SYSTEM" == "runit" ]]; then
    RUNIT_SV_DIR="$HOME/.config/sv/g11-macro-daemon"
    mkdir -p "$RUNIT_SV_DIR/log"

    cat > "$RUNIT_SV_DIR/run" << EOF
#!/bin/sh
exec $HOME/.cargo/bin/g11-macro-daemon 2>&1
EOF
    chmod +x "$RUNIT_SV_DIR/run"

    # Log service — stores output in the log directory
    RUNIT_LOG_DIR="$RUNIT_SV_DIR/log/main"
    mkdir -p "$RUNIT_LOG_DIR"
    cat > "$RUNIT_SV_DIR/log/run" << EOF
#!/bin/sh
exec svlogd -tt "$RUNIT_LOG_DIR"
EOF
    chmod +x "$RUNIT_SV_DIR/log/run"

    # Set RUST_LOG via an env directory
    mkdir -p "$RUNIT_SV_DIR/env"
    echo "WARN,g11=INFO" > "$RUNIT_SV_DIR/env/RUST_LOG"

    _ok "Runit service created → $RUNIT_SV_DIR"

    # Check if user has a runsvdir session running
    if pgrep -u "$(id -u)" runsvdir &>/dev/null; then
        # Link into the user's active service directory
        USER_SVDIR=$(pgrep -u "$(id -u)" -a runsvdir 2>/dev/null | grep -oP '(?<=runsvdir\s)\S+' | head -1)
        if [[ -n "$USER_SVDIR" && -d "$USER_SVDIR" ]]; then
            ln -sf "$RUNIT_SV_DIR" "$USER_SVDIR/g11-macro-daemon" 2>/dev/null
            _ok "Linked into $USER_SVDIR — daemon should start automatically"
        else
            _info "runsvdir is running but couldn't detect service directory"
            _info "Link manually: ln -s $RUNIT_SV_DIR <your-svdir>/g11-macro-daemon"
        fi
    else
        _warn "No runsvdir session detected for your user"
        _info "To start the daemon manually:"
        _info "  RUST_LOG=WARN,g11=INFO $HOME/.cargo/bin/g11-macro-daemon"
        _info "To enable as a user runit service, add runsvdir to your session and link:"
        _info "  ln -s $RUNIT_SV_DIR ~/service/g11-macro-daemon"
    fi
else
    _warn "No supported init system found (systemd or runit)"
    _info "Start the daemon manually:"
    _info "  RUST_LOG=WARN,g11=INFO $HOME/.cargo/bin/g11-macro-daemon"
fi

# ── Step 6 · Python venv ──────────────────────────────────────────────────────
_step "Setting up Python virtual environment"

# Rebuild if broken (missing gi)
if [[ -d "$VENV_DIR" ]]; then
    if ! "$VENV_DIR/bin/python3" -c "import gi" &>/dev/null; then
        _warn "Existing venv is broken — rebuilding"
        rm -rf "$VENV_DIR"
    fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
    _ok "Virtual environment created"
else
    _ok "Virtual environment already exists"
fi

VENV_PY="$VENV_DIR/bin/python3"

# Install hidapi (optional — for LED control)
if "$VENV_PY" -c "import hid" &>/dev/null; then
    _ok "hidapi already installed"
else
    _info "Installing hidapi (for LED control)…"
    if command -v uv &>/dev/null; then
        uv pip install --python "$VENV_PY" hidapi \
            && _ok "hidapi installed (uv)" \
            || _warn "hidapi install failed — LED control will be unavailable"
    else
        "$VENV_DIR/bin/pip" install hidapi \
            && _ok "hidapi installed (pip)" \
            || _warn "hidapi install failed — LED control will be unavailable"
    fi
fi

# Verify GTK4 works
if "$VENV_PY" -c "
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Adw','1')
from gi.repository import Gtk, Adw
" &>/dev/null; then
    _ok "GTK4 + libadwaita import: OK"
else
    _warn "GTK4/libadwaita import check failed — the GUI may not work correctly"
    case "$PKG_MANAGER" in
        apt)  _info "Try: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1" ;;
        xbps) _info "Try: sudo xbps-install python3-gobject gtk4 libadwaita gobject-introspection" ;;
        *)    _info "Try installing python3-gi/python3-gobject, gtk4, and libadwaita for your distro" ;;
    esac
fi

# ── Step 7 · Launcher script ──────────────────────────────────────────────────
_step "Creating launcher script"

mkdir -p "$(dirname "$LAUNCHER")"
cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
exec "$VENV_PY" "$GUI_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"
_ok "Launcher → $LAUNCHER"

# Add ~/.local/bin to PATH in shell config if it's not already there
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [[ -f "$RC" ]] && ! grep -q '\.local/bin' "$RC"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
        _info "Added ~/.local/bin to PATH in $RC"
    fi
done

# ── Step 8 · Desktop entries ──────────────────────────────────────────────────
_step "Installing desktop entries"

DESKTOP_ENTRY="[Desktop Entry]
Version=1.0
Type=Application
Name=G11 Macro Manager
GenericName=Keyboard Macro Manager
Comment=Configure macros for the Logitech G11 gaming keyboard
Exec=$LAUNCHER
Icon=$ICON_PATH
Terminal=false
Categories=Utility;HardwareSettings;
Keywords=logitech;keyboard;macro;g11;gaming;
StartupWMClass=main.py"

# ---- App menu (works on all DEs) ----
mkdir -p "$(dirname "$APP_DESKTOP")"
echo "$DESKTOP_ENTRY" > "$APP_DESKTOP"
chmod +x "$APP_DESKTOP"
update-desktop-database "$(dirname "$APP_DESKTOP")" 2>/dev/null || true

# Refresh app list for the active DE
case "$CURRENT_DE" in
    kde)
        kbuildsycoca6 --noincremental 2>/dev/null \
        || kbuildsycoca5 --noincremental 2>/dev/null \
        || true
        ;;
    xfce)
        xfce4-panel --restart 2>/dev/null || true
        ;;
esac
_ok "App menu entry → $APP_DESKTOP"

# ---- Desktop icon ----
if [[ -d "$DESKTOP_DIR" ]]; then
    DESK_FILE="$DESKTOP_DIR/g11-macro.desktop"
    echo "$DESKTOP_ENTRY" > "$DESK_FILE"
    chmod +x "$DESK_FILE"

    # Trust the file (prevents "Untrusted launcher" prompt)
    case "$CURRENT_DE" in
        gnome|cinnamon)
            gio set "$DESK_FILE" metadata::trusted true 2>/dev/null || true
            ;;
        kde)
            # KDE only needs executable bit — already set above
            ;;
        xfce|mate|lxqt|*)
            gio set "$DESK_FILE" metadata::trusted true 2>/dev/null || true
            ;;
    esac
    _ok "Desktop icon → $DESK_FILE"
else
    _warn "No Desktop directory found — skipping desktop icon"
fi

# ── Step 9 · Verify ───────────────────────────────────────────────────────────
_step "Verifying installation"

echo ""
PASS=0; FAIL=0

_check() {
    local label="$1"; shift
    if "$@" &>/dev/null; then
        _ok "$label"
        (( ++PASS ))
    else
        _warn "$label — check manually"
        (( ++FAIL ))
    fi
}

_check "Daemon binary"  test -x "$HOME/.cargo/bin/g11-macro-daemon"
_check "udev rules"     test -f "$UDEV_FILE"
_check "Python venv"    test -d "$VENV_DIR"
_check "GTK4 import"    "$VENV_PY" -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk"
_check "Launcher"       test -x "$LAUNCHER"
_check "App menu entry" test -f "$APP_DESKTOP"

if [[ "$INIT_SYSTEM" == "systemd" ]]; then
    _check "Daemon service" systemctl --user is-enabled g11-macro-daemon
    DAEMON_STATE=$(systemctl --user is-active g11-macro-daemon 2>/dev/null || echo "inactive")
    if [[ "$DAEMON_STATE" == "active" ]]; then
        _ok "Daemon is running"
        (( ++PASS ))
    else
        _warn "Daemon is ${DAEMON_STATE} — it will start automatically when the keyboard is plugged in"
    fi
elif [[ "$INIT_SYSTEM" == "runit" ]]; then
    _check "Runit service" test -x "$HOME/.config/sv/g11-macro-daemon/run"
    if sv status g11-macro-daemon &>/dev/null 2>&1; then
        _ok "Daemon is running (runit)"
        (( ++PASS ))
    else
        _warn "Daemon is not running — see instructions above to enable it"
    fi
else
    _warn "No init system detected — start the daemon manually"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  Installation complete!  (${PASS} OK, ${FAIL} warnings)${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Launch the GUI:${NC}"
echo -e "    Double-click the desktop icon, or press Super and search 'G11'"
echo -e "    Or from terminal: ${CYAN}g11-macro-gui${NC}"
echo ""
if [[ "$INIT_SYSTEM" == "systemd" ]]; then
    echo -e "  ${BOLD}Daemon logs:${NC}"
    echo -e "    ${CYAN}journalctl --user -u g11-macro-daemon -f${NC}"
elif [[ "$INIT_SYSTEM" == "runit" ]]; then
    echo -e "  ${BOLD}Daemon logs:${NC}"
    echo -e "    ${CYAN}cat $HOME/.config/sv/g11-macro-daemon/log/main/current${NC}"
else
    echo -e "  ${BOLD}Start daemon manually:${NC}"
    echo -e "    ${CYAN}RUST_LOG=WARN,g11=INFO $HOME/.cargo/bin/g11-macro-daemon${NC}"
fi
echo ""
echo -e "  ${BOLD}Config file:${NC}"
echo -e "    ${CYAN}~/.config/g11-macro-daemon/key_bindings.ron${NC}"
echo ""
