# Display Setup

The ST7789 display uses SPI, so SPI must be enabled on the Raspberry Pi.

Edit `/boot/firmware/config.txt` and add:

```ini
dtparam=spi=on
```

Reboot after changing the file:

```bash
sudo reboot
```
