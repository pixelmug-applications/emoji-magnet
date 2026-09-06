import micropyxel as pyxel
import audio_service


SCATTER_NOISE = (
    "T260 Q30 @3 "
    "@ENV1{110,3,90,6,55,12,0} @ENV1 "
    "O5 C32 R64 G32 R64 D32 A32 R32 C16"
)
SCATTER_GLASS = (
    "T300 Q20 @0 "
    "@ENV2{127,2,80,5,0} @ENV2 "
    "O7 C32 R64 A32 R32 F+32 R64 O6 B32 R32 D+32 R64 G32"
)
MAGNET_WHOOSH = (
    "T180 Q100 @3 "
    "@ENV3{0,6,100,12,75,8,0} @ENV3 "
    "@GLI1{-1800,26} @GLI1 O6 C4"
)
FINAL_SNAP = (
    "T320 Q20 @0 "
    "@ENV4{127,2,75,5,0} @ENV4 O7 C32 G32"
)


class EmojiMagnetSound:
    def __init__(self, enabled=True, output_volume=100):
        self.enabled = bool(enabled)
        self.output_volume = output_volume
        self.audio = audio_service.audio
        self.audio_ready = False
        self.sounds_ready = False

    def init_audio(self):
        try:
            self.audio.init(
                enable_input=False,
                enable_output=True,
                with_opus_encoder=False,
                with_opus_decoder=False,
            )
            self.audio.configure(output_volume=self.output_volume)
            self.audio_ready = True
        except Exception as exc:
            print("[EmojiMagnet] audio init failed:", exc)
        return self.audio_ready

    def prepare(self):
        if not self.audio_ready:
            return False
        try:
            pyxel.sounds(0).mml(SCATTER_NOISE)
            pyxel.sounds(1).mml(SCATTER_GLASS)
            pyxel.sounds(2).mml(MAGNET_WHOOSH)
            pyxel.sounds(3).mml(FINAL_SNAP)
            self.sounds_ready = True
        except Exception as exc:
            print("[EmojiMagnet] MML setup failed:", exc)
        return self.sounds_ready

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            try:
                pyxel.stop()
            except Exception:
                pass

    def scatter(self):
        if not self._can_play():
            return
        try:
            pyxel.stop(0)
            pyxel.stop(1)
            pyxel.channels(0).play(0, None, False)
            pyxel.channels(1).play(1, None, False)
        except Exception as exc:
            print("[EmojiMagnet] scatter sound failed:", exc)

    def whoosh(self):
        if not self._can_play():
            return
        try:
            pyxel.stop(0)
            pyxel.channels(0).play(2, None, False)
        except Exception as exc:
            print("[EmojiMagnet] whoosh sound failed:", exc)

    def final_snap(self):
        if not self._can_play():
            return
        try:
            pyxel.stop(2)
            pyxel.channels(2).play(3, None, False)
        except Exception as exc:
            print("[EmojiMagnet] final sound failed:", exc)

    def deinit(self):
        try:
            pyxel.stop()
        except Exception:
            pass
        if self.audio_ready:
            try:
                self.audio.deinit()
            except Exception:
                pass
        self.audio_ready = False
        self.sounds_ready = False

    def _can_play(self):
        return self.enabled and self.audio_ready and self.sounds_ready
