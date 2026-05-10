# UV setup

First install the Python headers:

```bash
sudo apt install python3-dev
```

Enable SPI by adding this line to `/boot/firmware/config.txt`:

```ini
dtparam=spi=on
```

Then reboot:

```bash
sudo reboot
```

Then create the environment and install Python dependencies:

```bash
make uv-setup
```
