# Emoji Magnet

Emoji Magnet is a two-part PixelMug MPS project:

- `bot/` binds a PixelMug, installs/starts the MPS, and sends sound-effect settings through the device push-message RPC.
- `mpy/` runs the 81-particle 9×9 emoji interaction. It has no BLE dependency and no webapp.

Bot environment variables:

```text
BUBBLE_BOT_TOKEN=your-bot-token
MPS_ID=your-published-mps-id
MPS_VERSION=1.0.0
```

Optional variables are `BUBBLE_API_BASE_URL`, `DEBUG`, and `MPS_OPEN_TIMEOUT_MS`.

Run the bot from this directory with `npm run bot`.

Commands:

- `/bindPixelMug`
- `/startEmojiMagnet`
- `/configSoundEffect` (or `/config sound effect on|off`)
- `/license`
