import gc

import micropyxel as pyxel


EMOJI_WIDTH = 9
EMOJI_HEIGHT = 9
PAGE_COLUMNS = 16
PAGE_ROWS = 28
PAGE_COUNT = 8
EMOJIS_PER_PAGE = PAGE_COLUMNS * PAGE_ROWS
EMOJI_COUNT = EMOJIS_PER_PAGE * PAGE_COUNT
MAX_COLORS = 255
EMOJI_LOCK_COLOR = 254
EMOJI_LOCK_RGB = 0x323232


class EmojiAssets:
    def __init__(self, bank=0):
        self.bank = bank
        self.loaded_page = -1
        self.image = pyxel.images(bank)
        # Seed every source RGB in deterministic order. The 200-color emoji
        # library plus the 16 built-ins fits below Micropyxel's 255-color cap.
        self.image.load_from_png(0, 255, "assets/emoji_palette.png", True)
        self._sync_screen_palette()

    def location(self, emoji_id):
        if emoji_id < 0 or emoji_id >= EMOJI_COUNT:
            raise ValueError("emoji id out of range")
        global_row = emoji_id // PAGE_COLUMNS
        column = emoji_id % PAGE_COLUMNS
        page = global_row // PAGE_ROWS
        local_row = global_row % PAGE_ROWS
        return page, column * EMOJI_WIDTH, local_row * EMOJI_HEIGHT

    def load(self, emoji_id, colors_out):
        page, source_x, source_y = self.location(emoji_id)
        if page != self.loaded_page:
            path = "assets/emoji_%02d.png" % page
            self.image.load_from_png(0, 0, path, True)
            self.loaded_page = page
            self._sync_screen_palette()

        index = 0
        for ey in range(EMOJI_HEIGHT):
            for ex in range(EMOJI_WIDTH):
                colors_out[index] = self.image.pget(source_x + ex, source_y + ey)
                index += 1
        return page

    def _sync_screen_palette(self):
        # The bank appends new RGB/index pairs without changing old pairs.
        # Mirroring it keeps existing particle colors stable across page loads.
        colors = [0] * MAX_COLORS
        for index in range(MAX_COLORS):
            red, green, blue = self.image.color_rgb(index)
            colors[index] = (red << 16) | (green << 8) | blue
        # Index 254 is reserved for the lock-frame UI and is outside the
        # 16 built-ins plus 200-color emoji library.
        colors[EMOJI_LOCK_COLOR] = EMOJI_LOCK_RGB
        pyxel.set_palette(colors)
        gc.collect()
