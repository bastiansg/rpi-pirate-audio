#!/usr/bin/env bash
set -euo pipefail

OPEN_PAIRING=0
DEVICE_NAME=""
TRUST_MAC=""
CONNECT_MAC=""

usage() {
    cat <<'EOF'
Usage: scripts/setup-bluetooth-a2dp-sink.sh [options]

Configure this Raspberry Pi as a Bluetooth A2DP audio sink using BlueZ,
PipeWire, WirePlumber, and the bluez-tools bt-agent.

Options:
  --open-pairing        Keep Bluetooth discoverable/pairable and install a
                        NoInputNoOutput auto-pairing agent.
  --device-name NAME    Set the public Bluetooth adapter alias.
  --trust MAC           Trust an already paired phone/device MAC.
  --connect MAC         Connect to a paired phone/device MAC after setup.
  -h, --help            Show this help.

Examples:
  scripts/setup-bluetooth-a2dp-sink.sh
  scripts/setup-bluetooth-a2dp-sink.sh --open-pairing --device-name FLAX
  scripts/setup-bluetooth-a2dp-sink.sh --trust F4:52:93:C0:7D:4C

Security note:
  --open-pairing makes nearby devices able to pair while the Pi is
  discoverable/pairable. Use it only if you want speaker-style pairing.
EOF
}

log() {
    printf '\n==> %s\n' "$*"
}

warn() {
    printf '\nWARNING: %s\n' "$*" >&2
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n' "$1" >&2
        exit 1
    fi
}

run_sudo() {
    if [[ ${EUID} -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --open-pairing)
                OPEN_PAIRING=1
                shift
                ;;
            --device-name)
                DEVICE_NAME="${2:-}"
                if [[ -z "${DEVICE_NAME}" ]]; then
                    printf '%s\n' '--device-name requires a value' >&2
                    exit 1
                fi
                shift 2
                ;;
            --trust)
                TRUST_MAC="${2:-}"
                if [[ -z "${TRUST_MAC}" ]]; then
                    printf '%s\n' '--trust requires a MAC address' >&2
                    exit 1
                fi
                shift 2
                ;;
            --connect)
                CONNECT_MAC="${2:-}"
                if [[ -z "${CONNECT_MAC}" ]]; then
                    printf '%s\n' '--connect requires a MAC address' >&2
                    exit 1
                fi
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                printf 'Unknown option: %s\n' "$1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done
}

install_packages() {
    log "Installing Bluetooth and PipeWire packages"
    run_sudo apt update
    run_sudo apt install -y \
        bluez \
        bluez-tools \
        pipewire \
        pipewire-pulse \
        wireplumber \
        libspa-0.2-bluetooth
}

enable_services() {
    log "Enabling Bluetooth service"
    run_sudo systemctl enable --now bluetooth

    log "Enabling user PipeWire services"
    systemctl --user enable --now pipewire pipewire-pulse wireplumber
    run_sudo loginctl enable-linger "${USER}"
}

clear_rfkill_if_needed() {
    log "Checking Bluetooth rfkill/software block state"

    local bluetooth_was_blocked=0
    local rfkill_dir
    local rfkill_soft

    for rfkill_dir in /sys/class/rfkill/rfkill*; do
        if [[ ! -e "${rfkill_dir}/type" ]] || [[ "$(cat "${rfkill_dir}/type")" != "bluetooth" ]]; then
            continue
        fi

        rfkill_soft="${rfkill_dir}/soft"
        if [[ -e "${rfkill_soft}" ]] && [[ "$(cat "${rfkill_soft}")" == "1" ]]; then
            bluetooth_was_blocked=1
            warn "Bluetooth is software-blocked at ${rfkill_soft}; clearing it"
            printf '0\n' | run_sudo tee "${rfkill_soft}" >/dev/null
        fi
    done

    if bluetoothctl show 2>/dev/null | grep -q 'PowerState: off-blocked'; then
        bluetooth_was_blocked=1
        warn "BlueZ still reports Bluetooth as off-blocked; retrying known Bluetooth rfkill entries"
        for rfkill_dir in /sys/class/rfkill/rfkill*; do
            if [[ -e "${rfkill_dir}/type" ]] && [[ "$(cat "${rfkill_dir}/type")" == "bluetooth" ]]; then
                printf '0\n' | run_sudo tee "${rfkill_dir}/soft" >/dev/null
            fi
        done
    fi

    if [[ ${bluetooth_was_blocked} -eq 1 ]]; then
        log "Turning Bluetooth power back on after clearing rfkill"
    fi

    bluetoothctl power on >/dev/null || true
}

make_adapter_visible() {
    local discoverable_timeout="$1"

    log "Making adapter powered, pairable, and discoverable"
    bluetoothctl power on
    bluetoothctl pairable on
    bluetoothctl discoverable-timeout "${discoverable_timeout}"
    bluetoothctl discoverable on
}

configure_wireplumber_headless() {
    local config_dir="${HOME}/.config/wireplumber/wireplumber.conf.d"
    local config_file="${config_dir}/50-bluez-headless.conf"

    log "Writing WirePlumber headless Bluetooth audio config"
    mkdir -p "${config_dir}"
    cat >"${config_file}" <<'EOF'
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
EOF

    log "Restarting user PipeWire/WirePlumber services"
    systemctl --user restart wireplumber pipewire pipewire-pulse
}

install_bt_agent() {
    log "Installing NoInputNoOutput Bluetooth pairing agent"
    run_sudo tee /etc/systemd/system/bt-agent.service >/dev/null <<'EOF'
[Unit]
Description=Bluetooth auto pairing agent
After=bluetooth.service
PartOf=bluetooth.service

[Service]
ExecStart=/usr/bin/bt-agent -c NoInputNoOutput
Restart=always

[Install]
WantedBy=bluetooth.target
EOF

    run_sudo systemctl daemon-reload
    run_sudo systemctl enable --now bt-agent
}

set_main_conf_value() {
    local key="$1"
    local value="$2"
    local file="/etc/bluetooth/main.conf"

    run_sudo python3 - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

text = path.read_text()
lines = text.splitlines()

general_index = None
for index, line in enumerate(lines):
    if line.strip() == "[General]":
        general_index = index
        break

if general_index is None:
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(["[General]", f"{key} = {value}"])
    path.write_text("\n".join(lines) + "\n")
    raise SystemExit

section_end = len(lines)
for index in range(general_index + 1, len(lines)):
    stripped = lines[index].strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        section_end = index
        break

replacement = f"{key} = {value}"
for index in range(general_index + 1, section_end):
    stripped = lines[index].strip()
    if stripped.startswith(f"{key} ") or stripped.startswith(f"{key}="):
        lines[index] = replacement
        break
else:
    lines.insert(section_end, replacement)

path.write_text("\n".join(lines) + "\n")
PY
}

configure_open_pairing() {
    warn "Open pairing is enabled; nearby devices can pair while discoverable."
    install_bt_agent

    log "Configuring /etc/bluetooth/main.conf for speaker-style pairing"
    set_main_conf_value "DiscoverableTimeout" "0"
    set_main_conf_value "AlwaysPairable" "true"
    set_main_conf_value "PairableTimeout" "0"
    set_main_conf_value "JustWorksRepairing" "always"

    log "Restarting Bluetooth"
    run_sudo systemctl restart bluetooth

    make_adapter_visible 0
}

set_device_name() {
    if [[ -n "${DEVICE_NAME}" ]]; then
        log "Setting Bluetooth adapter alias to ${DEVICE_NAME}"
        bluetoothctl system-alias "${DEVICE_NAME}"
    fi
}

trust_or_connect_devices() {
    if [[ -n "${TRUST_MAC}" ]]; then
        log "Trusting Bluetooth device ${TRUST_MAC}"
        bluetoothctl trust "${TRUST_MAC}"
    fi

    if [[ -n "${CONNECT_MAC}" ]]; then
        log "Connecting Bluetooth device ${CONNECT_MAC}"
        bluetoothctl connect "${CONNECT_MAC}"
    fi
}

trust_connected_devices() {
    local mac

    log "Trusting currently connected Bluetooth devices"
    while read -r _ mac _; do
        if [[ -n "${mac}" ]]; then
            bluetoothctl trust "${mac}" || true
        fi
    done < <(bluetoothctl devices Connected)
}

reconnect_connected_devices() {
    local connected_macs=()
    local mac

    while read -r _ mac _; do
        if [[ -n "${mac}" ]]; then
            connected_macs+=("${mac}")
        fi
    done < <(bluetoothctl devices Connected)

    if [[ ${#connected_macs[@]} -eq 0 ]]; then
        return
    fi

    log "Reconnecting currently connected Bluetooth devices to refresh audio transports"
    for mac in "${connected_macs[@]}"; do
        bluetoothctl disconnect "${mac}" || true
    done

    sleep 2

    for mac in "${connected_macs[@]}"; do
        bluetoothctl connect "${mac}" || true
    done
}

print_status() {
    log "Bluetooth service status"
    systemctl is-active bluetooth || true
    if [[ ${OPEN_PAIRING} -eq 1 ]]; then
        systemctl is-active bt-agent || true
    fi

    log "Bluetooth adapter summary"
    bluetoothctl show || true

    log "PipeWire audio status"
    if command -v wpctl >/dev/null 2>&1; then
        wpctl status || true
    else
        warn "wpctl is not available in PATH; install/check PipeWire tools if audio routing cannot be verified."
    fi
}

main() {
    parse_args "$@"

    if [[ ${EUID} -eq 0 ]]; then
        printf '%s\n' "Run this script as the normal Pi user, not with sudo. It will ask for sudo when needed." >&2
        exit 1
    fi

    require_command apt
    require_command sudo
    require_command systemctl
    require_command loginctl

    install_packages
    require_command bluetoothctl
    enable_services
    clear_rfkill_if_needed
    configure_wireplumber_headless
    set_device_name

    if [[ ${OPEN_PAIRING} -eq 1 ]]; then
        configure_open_pairing
    else
        log "Open pairing disabled; enabling normal pairable/discoverable state for this session"
        make_adapter_visible 180
    fi

    trust_connected_devices
    reconnect_connected_devices
    trust_or_connect_devices
    print_status

    log "Done"
}

main "$@"
