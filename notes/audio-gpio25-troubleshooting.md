# Pirate Audio GPIO 25 Audio Troubleshooting

This note documents an issue where Bluetooth audio was connected and routed correctly, but no sound came out of the Pirate Audio / HifiBerry-style DAC.

## Symptom

- The phone was connected over Bluetooth.
- PipeWire showed the Bluetooth stream routed to the HifiBerry playback channels.
- The default sink volume was `1.00`.
- No audio was heard from the Pirate Audio output.

## Cause

GPIO 25 was low:

```bash
pinctrl get 25
```

Observed state:

```text
25: op -- -- | lo // GPIO25 = output
```

For this setup, GPIO 25 needs to stay high. The boot config already had:

```text
gpio=25=op,dh
```

That makes GPIO 25 come up as output-high during boot, but something after boot had pulled it low.

One likely source was the ST7789 display reset configuration. The app originally passed GPIO 25 as the display reset pin:

```python
rst=25
```

That allowed the display library to control GPIO 25, which can conflict with the Pirate Audio audio enable / mute behavior.

## Diagnosis

Bluetooth connection was present:

```bash
bluetoothctl devices Connected
```

PipeWire showed the iPhone stream routed to the HifiBerry playback channels:

```bash
wpctl status
```

Relevant output:

```text
Streams:
    bluez_input.F4_52_93_C0_7D_4C.2
         output_FR > HifiBerry DAC HiFi pcm5102a-hifi-0:playback_FR [active]
         output_FL > HifiBerry DAC HiFi pcm5102a-hifi-0:playback_FL [active]
```

Volume was not muted:

```bash
wpctl get-volume @DEFAULT_AUDIO_SINK@
```

Output:

```text
Volume: 1.00
```

The HifiBerry ALSA device was present:

```bash
aplay -l
```

Relevant output:

```text
card 0: sndrpihifiberry [snd_rpi_hifiberry_dac], device 0: HifiBerry DAC HiFi pcm5102a-hifi-0
```

The failing state was confirmed by checking GPIO 25:

```bash
pinctrl get 25
```

Output:

```text
25: op -- -- | lo // GPIO25 = output
```

## Fix

Set GPIO 25 high again:

```bash
pinctrl set 25 op dh
```

After this, audio started working again.

## App Change

The display app should not claim GPIO 25 as the ST7789 reset pin by default. Use `rst=None` unless the hardware wiring specifically requires a display reset GPIO:

```python
parser.add_argument("--rst", type=int, default=None)
```

This prevents the display library from pulling GPIO 25 low and muting/disabling audio.

## Quick Recovery Commands

When audio disappears but Bluetooth appears connected:

```bash
bluetoothctl devices Connected
wpctl status
wpctl get-volume @DEFAULT_AUDIO_SINK@
pinctrl get 25
pinctrl set 25 op dh
```

If `pinctrl get 25` shows `lo`, run the `pinctrl set 25 op dh` command and test audio again.
