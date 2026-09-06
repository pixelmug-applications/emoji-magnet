import json


CONFIG_PATH = "emoji_magnet_config.json"
DEFAULT_SOUND_EFFECT = True


def load_sound_effect():
    try:
        with open(CONFIG_PATH, "r") as fp:
            data = json.loads(fp.read() or "{}")
        return bool(data.get("sound_effect", DEFAULT_SOUND_EFFECT))
    except Exception:
        return DEFAULT_SOUND_EFFECT


def save_sound_effect(enabled):
    try:
        with open(CONFIG_PATH, "w") as fp:
            fp.write(json.dumps({"sound_effect": bool(enabled)}))
        return True
    except Exception as exc:
        print("[EmojiMagnet] save config failed:", exc)
        return False
