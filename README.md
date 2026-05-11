# Raspberry Pi Pirate Audio

Bluetooth audio sink utilities for a Raspberry Pi with a Pirate Audio / HifiBerry-style DAC and ST7789 display.

The main app shows an animated rainbow while a Bluetooth device is connected, and a black screen otherwise.

## Setup

```bash
make uv-setup
```

## Run

```bash
make app
```

Useful helpers:

```bash
make rainbow
make buttons
```

## PM2 Setup

Install PM2 globally:

```bash
npm install pm2 -g
```

Add the PM2 startup script so the application starts on boot:

```bash
pm2 startup
```

Create `ecosystem.config.js`:

```js
module.exports = {
    apps: [
        {
            name: "status-display",
            script: "uv run --no-sync python -m src.apps.status_display.main",
            watch: false,
        },
    ],
}
```

## Checks

```bash
make format
make check
```

## Notes

Setup and troubleshooting docs live in [notes](notes/), including the GPIO 25 audio recovery note.
