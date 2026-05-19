# Display Setup

The ST7789 display uses SPI, so SPI must be enabled on the Raspberry Pi.
The Pirate Audio / HifiBerry-style DAC also needs its audio overlay and GPIO 25
held high.

Edit `/boot/firmware/config.txt` and add:

```ini
dtparam=spi=on
dtoverlay=hifiberry-dac
gpio=25=op,dh
```

Reboot after changing the file:

```bash
sudo reboot
```
