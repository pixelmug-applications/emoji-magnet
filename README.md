# Emoji Magnet

Emoji Magnet is a PixelMug Studio application that turns 9 x 9 emoji artwork into colorful particles. Shaking the PixelMug scatters the particles; when the device becomes still, they magnetically reform into another emoji.

This project uses the `04-bot-mpy` shape:

```text
emoji-magnet/
  bot/        Bot commands and device RPC calls
  mpy/        MicroPython app and bundled emoji/audio assets
```

## Development

Install dependencies and run the Bot:

```bash
npm install
npm run bot
```

When the project runs in PixelMug Studio, Studio supplies these environment variables:

```text
BOT_TOKEN
BOT_API_BASE_URL
STUDIO_MPS_ID
STUDIO_MPS_VERSION
```

The Bot uses the Studio MPS identity to install and start `mpy/` on a bound PixelMug. Do not create a local `config.dev.js` or commit tokens.

Available commands:

- `/bindPixelMug` binds a device.
- `/startEmojiMagnet` installs and starts Emoji Magnet.
- `/SoundEffect` configures sound effects.
- `/License` shows the artwork license.

The MPY manifest is `mpy/mps.json`. Device assets are stored under `mpy/assets/` and use device-relative paths. Runtime sound settings are stored in `emoji_magnet_config.json` on the device.
