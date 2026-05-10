# Raspberry Pi Bluetooth Audio Sink Setup

This guide configures a Raspberry Pi to behave like a Bluetooth speaker, so a phone can stream audio to it over Bluetooth A2DP.

The tested setup uses:

- Raspberry Pi OS Bookworm or newer
- BlueZ 5.82
- PipeWire 1.4.2
- WirePlumber 0.5.8
- `libspa-0.2-bluetooth`
- `bluez-tools` for the always-running pairing agent
- HifiBerry/Pirate Audio style I2S DAC output

## 1. Install Required Packages

```bash
sudo apt update
sudo apt install -y bluez bluez-tools pipewire pipewire-pulse wireplumber libspa-0.2-bluetooth
```

Enable Bluetooth:

```bash
sudo systemctl enable --now bluetooth
```

Enable PipeWire services for the current user:

```bash
systemctl --user enable --now pipewire pipewire-pulse wireplumber
loginctl enable-linger "$USER"
```

## 2. Fix Bluetooth If It Is Software-Blocked

Check the controller state:

```bash
bluetoothctl show
```

If you see:

```text
Powered: no
PowerState: off-blocked
```

clear the rfkill software block:

```bash
sudo sh -c 'echo 0 > /sys/class/rfkill/rfkill0/soft'
```

Then verify:

```bash
bluetoothctl show
```

Expected:

```text
Powered: yes
PowerState: on
```

## 3. Enable Bluetooth Audio In Headless/SSH Sessions

On this setup, WirePlumber did not register the A2DP sink while running headless over SSH because Bluetooth seat monitoring waited for an active graphical session.

Create this per-user WirePlumber config:

```bash
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
```

Create `~/.config/wireplumber/wireplumber.conf.d/50-bluez-headless.conf`:

```conf
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
```

Restart WirePlumber:

```bash
systemctl --user restart wireplumber pipewire pipewire-pulse
```

Verify the Pi now advertises the Bluetooth audio sink profile:

```bash
bluetoothctl show
```

Expected UUID:

```text
UUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
```

## 4. Optional: Allow Speaker-Style Open Pairing

This makes the Pi behave more like a regular Bluetooth speaker:

- The Pi stays discoverable.
- The Pi stays pairable.
- A `NoInputNoOutput` agent accepts simple "Just Works" pairing.
- Phones should not need a matching numeric code.

Important: nearby people can pair with the Pi while it is discoverable and pairable.

Create `/etc/systemd/system/bt-agent.service`:

```ini
[Unit]
Description=Bluetooth auto pairing agent
After=bluetooth.service
PartOf=bluetooth.service

[Service]
ExecStart=/usr/bin/bt-agent -c NoInputNoOutput
Restart=always

[Install]
WantedBy=bluetooth.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bt-agent
```

Edit `/etc/bluetooth/main.conf` and set these values in the `[General]` section:

```ini
DiscoverableTimeout = 0
AlwaysPairable = true
PairableTimeout = 0
JustWorksRepairing = always
```

Restart Bluetooth:

```bash
sudo systemctl restart bluetooth
```

If the restart hangs because an old `bt-agent` process is stopping, force it to exit and re-check the services:

```bash
sudo pkill -9 -f '/usr/bin/bt-agent -c NoInputNoOutput'
systemctl status bluetooth bt-agent --no-pager
```

After Bluetooth restarts, re-enable discoverable and pairable mode:

```bash
bluetoothctl discoverable-timeout 0
bluetoothctl pairable on
bluetoothctl discoverable on
```

Verify:

```bash
systemctl is-active bluetooth bt-agent
bluetoothctl show
```

Expected:

```text
active
active
Discoverable: yes
DiscoverableTimeout: 0x00000000 (0)
Pairable: yes
UUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
```

## 5. Manual Pairing Flow

Start `bluetoothctl`:

```bash
bluetoothctl
```

Inside `bluetoothctl`:

```text
power on
agent on
default-agent
pairable on
discoverable-timeout 0
discoverable on
```

From the phone, open Bluetooth settings and pair with the Raspberry Pi. In this setup the device name was `FLAX`.

If the open pairing agent from step 4 is running, pairing should not require a numeric code on the Pi.

If you are pairing manually without `bt-agent`, the phone may show a passkey and `bluetoothctl` will show a prompt like:

```text
[agent] Confirm passkey 632041 (yes/no):
```

Type:

```text
yes
```

If BlueZ asks to authorize a service, answer:

```text
yes
```

Trust the phone so it can reconnect later without repeating pairing:

```text
devices
trust PHONE_MAC_ADDRESS
```

Example:

```text
trust F4:52:93:C0:7D:4C
```

Exit:

```text
quit
```

## 6. Reconnect The Phone

If needed, reconnect manually:

```bash
bluetoothctl connect PHONE_MAC_ADDRESS
```

Example:

```bash
bluetoothctl connect F4:52:93:C0:7D:4C
```

Expected signs of a good A2DP connection:

```text
Connection successful
NEW Endpoint ...
NEW Transport ...
```

## 7. Verify Audio Routing

Check PipeWire:

```bash
wpctl status
```

Expected:

```text
Audio
 ├─ Devices:
 │      iPhone                              [bluez5]
 └─ Streams:
        bluez_input.PHONE_MAC_ADDRESS...
             output_FL > HifiBerry DAC ... playback_FL [active]
             output_FR > HifiBerry DAC ... playback_FR [active]
```

This means the phone audio stream is routed to the DAC.

## 8. Set Volume

Set Raspberry Pi output volume to 100%:

```bash
wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.0
```

Verify:

```bash
wpctl get-volume @DEFAULT_AUDIO_SINK@
```

Expected:

```text
Volume: 1.00
```

## 9. Phone-Side Check

On the phone:

1. Play audio.
2. Open the audio output selector.
3. Select the Raspberry Pi device, for example `FLAX`.
4. Raise the phone volume.

## Troubleshooting

### `bluetoothctl power on` Fails

If:

```text
Failed to set power on: org.bluez.Error.Failed
```

check:

```bash
bluetoothctl show
cat /sys/class/rfkill/rfkill0/soft
```

If `soft` is `1`, clear it:

```bash
sudo sh -c 'echo 0 > /sys/class/rfkill/rfkill0/soft'
```

### Phone Still Asks For A Code

Check that `bt-agent` is installed and active:

```bash
command -v bt-agent
systemctl status bt-agent --no-pager
```

Check that the service uses `NoInputNoOutput`:

```bash
systemctl cat bt-agent
```

Expected service command:

```text
ExecStart=/usr/bin/bt-agent -c NoInputNoOutput
```

Then restart it:

```bash
sudo systemctl restart bt-agent
```

### Phone Pairs But No Sound

Check whether the Pi advertises `Audio Sink`:

```bash
bluetoothctl show
```

If `Audio Sink` is missing, apply the WirePlumber headless config from step 3 and restart:

```bash
systemctl --user restart wireplumber pipewire pipewire-pulse
```

Then reconnect the phone:

```bash
bluetoothctl disconnect PHONE_MAC_ADDRESS
bluetoothctl connect PHONE_MAC_ADDRESS
```

### `br-connection-profile-unavailable`

This usually means the A2DP sink endpoint was not registered yet.

Verify:

```bash
bluetoothctl show
```

Make sure this appears:

```text
UUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
```

If it does not, restart WirePlumber after applying the headless config:

```bash
systemctl --user restart wireplumber pipewire pipewire-pulse
```

### Confirm Services Are Running

```bash
systemctl status bluetooth --no-pager
systemctl --user status pipewire pipewire-pulse wireplumber --no-pager
```
