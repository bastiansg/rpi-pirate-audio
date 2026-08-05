# Raspberry Pi Pirate Audio

Bluetooth audio sink utilities for a Raspberry Pi with a Pirate Audio / HifiBerry-style DAC and ST7789 display.

The main app continuously shows an animation whether or not a Bluetooth device is
connected. The animation changes when the Bluetooth connection state changes.

Button behavior:

- `A`: decrease Raspberry Pi output volume.
- `B`: increase Raspberry Pi output volume.
- `X`: show the previous shuffled animation.
- `Y`: show the next shuffled animation.

## Setup

```bash
make uv-setup
```

## Run

```bash
make app
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
