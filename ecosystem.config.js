module.exports = {
    apps: [
        {
            name: "status-display",
            script: "uv run --no-sync python -m src.apps.status_display.main",
            watch: false,
        },
    ],
}
