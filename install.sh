#!/usr/bin/env bash
set -Eeuo pipefail

# Beim Doppelklick ist häufig kein sichtbares Terminal vorhanden. In diesem
# Fall startet der Installer sich einmal selbst in einem Terminal und lässt
# das Fenster am Ende für Meldungen offen.
if [[ ! -t 0 && "${SPEECHFLOW_INSTALL_TERMINAL:-0}" != "1" ]]; then
    printf -v quoted_script '%q' "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"
    terminal_command="SPEECHFLOW_INSTALL_TERMINAL=1 bash $quoted_script; status=\$?; printf '\\nZum Schließen Enter drücken …'; read -r; exit \$status"

    if command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator -e bash -lc "$terminal_command" &
    elif command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- bash -lc "$terminal_command" &
    elif command -v konsole >/dev/null 2>&1; then
        konsole -e bash -lc "$terminal_command" &
    elif command -v xfce4-terminal >/dev/null 2>&1; then
        xfce4-terminal --command="bash -lc $(printf '%q' "$terminal_command")" &
    elif command -v kitty >/dev/null 2>&1; then
        kitty bash -lc "$terminal_command" &
    elif command -v alacritty >/dev/null 2>&1; then
        alacritty -e bash -lc "$terminal_command" &
    else
        printf 'Kein unterstütztes Terminal gefunden. Bitte starte:\n  bash %s\n' "$quoted_script" >&2
        exit 1
    fi
    exit 0
fi

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_STARTER="$APP_DIR/speechflow-start.py"
CONFIG_FILE="$APP_DIR/speechflow.conf"
FIRST_START_FILE="$APP_DIR/FIRST-START.md"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/speechflow.desktop"

info() { printf '\n[SpeechFlow] %s\n' "$*"; }
warn() { printf '\n[SpeechFlow] Hinweis: %s\n' "$*" >&2; }
die() { printf '\n[SpeechFlow] Fehler: %s\n' "$*" >&2; exit 1; }

on_error() {
    local status=$?
    printf '\n[SpeechFlow] Die Installation wurde in Zeile %s abgebrochen.\n' "$1" >&2
    exit "$status"
}
trap 'on_error "$LINENO"' ERR

ask_yes_no() {
    local answer
    printf '%s [j/N] ' "$1"
    read -r answer
    [[ "$answer" =~ ^([jJyY]|[jJyY][aAeE][sS]?)$ ]]
}

for required_file in "$PYTHON_STARTER" "$CONFIG_FILE" "$FIRST_START_FILE"; do
    [[ -f "$required_file" ]] || die "Benötigte Datei fehlt: $required_file"
done

detect_package_manager() {
    local candidate
    for candidate in apt-get dnf pacman zypper; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PACKAGE_MANAGER="$candidate"
            return 0
        fi
    done
    PACKAGE_MANAGER=""
}

package_for() {
    local tool=$1
    case "$tool:$PACKAGE_MANAGER" in
        mpv:*) printf 'mpv' ;;
        curl:*) printf 'curl' ;;
        clipboard:*)
            if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
                printf 'wl-clipboard'
            else
                printf 'xclip'
            fi
            ;;
        *) return 1 ;;
    esac
}

install_system_packages() {
    local packages=("$@")
    ((${#packages[@]} > 0)) || return 0

    [[ -n "$PACKAGE_MANAGER" ]] || die \
        "Kein unterstützter Paketmanager gefunden. Bitte installiere manuell: ${packages[*]}"

    info "Es fehlen folgende Systempakete: ${packages[*]}"
    ask_yes_no "Jetzt mit $PACKAGE_MANAGER installieren?" || die \
        "Installation beendet. Die fehlenden Pakete wurden nicht installiert."
    command -v sudo >/dev/null 2>&1 || die "Für Systempakete wird sudo benötigt."

    case "$PACKAGE_MANAGER" in
        apt-get)
            sudo apt-get update
            sudo apt-get install -y "${packages[@]}"
            ;;
        dnf) sudo dnf install -y "${packages[@]}" ;;
        pacman) sudo pacman -S --needed "${packages[@]}" ;;
        zypper) sudo zypper --non-interactive install "${packages[@]}" ;;
    esac
}

detect_package_manager
info "Prüfe uv, mpv, Zwischenablage-Unterstützung und Paketmanager …"

missing_packages=()
command -v mpv >/dev/null 2>&1 || missing_packages+=("$(package_for mpv)")

if ! command -v wl-paste >/dev/null 2>&1 && \
   ! command -v xclip >/dev/null 2>&1 && \
   ! command -v xsel >/dev/null 2>&1; then
    missing_packages+=("$(package_for clipboard)")
fi

if ! command -v uv >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
    missing_packages+=("$(package_for curl)")
fi

install_system_packages "${missing_packages[@]}"

if ! command -v uv >/dev/null 2>&1; then
    info "uv ist noch nicht installiert."
    ask_yes_no "uv mit dem offiziellen Installer installieren?" || die \
        "uv wird zum Starten von SpeechFlow benötigt."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
fi

UV_BIN="$(command -v uv || true)"
for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    if [[ -z "$UV_BIN" && -x "$candidate" ]]; then
        UV_BIN="$candidate"
    fi
done
[[ -n "$UV_BIN" && -x "$UV_BIN" ]] || die "uv wurde nach der Installation nicht gefunden."
UVX_BIN="$(command -v uvx || true)"
if [[ -z "$UVX_BIN" && -x "$(dirname -- "$UV_BIN")/uvx" ]]; then
    UVX_BIN="$(dirname -- "$UV_BIN")/uvx"
fi
[[ -n "$UVX_BIN" && -x "$UVX_BIN" ]] || die "uvx wurde nach der Installation nicht gefunden."
command -v mpv >/dev/null 2>&1 || die "mpv wurde nach der Installation nicht gefunden."
if ! command -v wl-paste >/dev/null 2>&1 && \
   ! command -v xclip >/dev/null 2>&1 && \
   ! command -v xsel >/dev/null 2>&1; then
    die "Kein unterstütztes Zwischenablage-Werkzeug wurde gefunden."
fi

chmod u+x "$APP_DIR/install.sh" "$PYTHON_STARTER"
mkdir -p "$APPLICATIONS_DIR"

# Die absoluten Pfade sind absichtlich in Anführungszeichen gesetzt. So startet
# SpeechFlow auch aus dem Anwendungsmenü und bei Leerzeichen im Projektpfad.
cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=SpeechFlow
Comment=Read clipboard text aloud
Exec="$UV_BIN" run "$PYTHON_STARTER"
Path=$APP_DIR
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=false
EOF
chmod u+x "$DESKTOP_FILE"

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_FILE" || warn "Der Menüeintrag meldet eine Warnung."
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

info "Starte jetzt die Hugging-Face-Anmeldung."
printf 'Falls du noch kein Konto hast, kannst du es unter https://huggingface.co erstellen.\n'
if ! "$UVX_BIN" --from huggingface_hub hf auth login; then
    warn "Die Hugging-Face-Anmeldung wurde nicht abgeschlossen. Du kannst sie später erneut starten."
fi

open_file() {
    local file=$1
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$file" >/dev/null 2>&1 &
    elif command -v gio >/dev/null 2>&1; then
        gio open "$file" >/dev/null 2>&1 &
    else
        warn "Bitte öffne diese Datei selbst: $file"
    fi
}

info "Öffne Konfiguration und Kurzanleitung …"
open_file "$CONFIG_FILE"
open_file "$FIRST_START_FILE"

printf '\n============================================\n'
printf ' SpeechFlow wurde eingerichtet.\n'
printf '============================================\n\n'
printf 'Standard: englisches Modell + Stimme Juniper.\n'
printf 'Deine Konfiguration wurde nicht verändert.\n'
printf 'Menüeintrag: %s\n' "$DESKTOP_FILE"
printf 'Lies FIRST-START.md und starte danach SpeechFlow im Anwendungsmenü.\n\n'
