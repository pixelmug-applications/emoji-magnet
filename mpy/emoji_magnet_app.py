import json
import random
import time

import g_sensor
import micropyxel as pyxel
import mpy_button as touch_events
import mpy_message
from pixel_dust import PixelDust

from em_assets import EMOJI_COUNT, EMOJI_HEIGHT, EMOJI_WIDTH, EMOJI_LOCK_COLOR, EmojiAssets
from em_config import load_sound_effect, save_sound_effect
from em_sound import EmojiMagnetSound


DISPLAY_WIDTH = 32
DISPLAY_HEIGHT = 16
HIDDEN_ROWS = 8
WORLD_WIDTH = DISPLAY_WIDTH
WORLD_HEIGHT = DISPLAY_HEIGHT + HIDDEN_ROWS
VISIBLE_FLOOR_Y = DISPLAY_HEIGHT
FPS = 30
TOUCH_EVENTS_PER_UPDATE = 4
TOUCH_CLICK_EVENTS = ("click", "single", "single_click", "tap", "hit")

DUST_CAPACITY = 128
MAX_PARTICLE_COUNT = 81
DUST_SCALE = 90
DUST_ELASTICITY = 200
DUST_SEED = 0x454D4F4A

STATE_EMOJI = 0
STATE_PHYSICS = 1
STATE_MAGNET_PREPARE = 2
STATE_MAGNET = 3

WALL_LEFT = 0
WALL_RIGHT = 1
WALL_TOP = 2
WALL_BOTTOM = 3
WALLS = (WALL_LEFT, WALL_RIGHT, WALL_TOP, WALL_BOTTOM)

BACKGROUND_COLOR = 0
TRANSPARENT_COLOR = 0
EMOJI_ORIGIN_X = (DISPLAY_WIDTH - EMOJI_WIDTH) // 2
EMOJI_ORIGIN_Y = (DISPLAY_HEIGHT - EMOJI_HEIGHT) // 2
LOCK_FRAME_COLOR = EMOJI_LOCK_COLOR
LOCK_FRAME_LEFT = EMOJI_ORIGIN_X - 1
LOCK_FRAME_TOP = EMOJI_ORIGIN_Y - 1
LOCK_FRAME_RIGHT = EMOJI_ORIGIN_X + EMOJI_WIDTH
LOCK_FRAME_BOTTOM = EMOJI_ORIGIN_Y + EMOJI_HEIGHT
SHAKE_THRESHOLD = 0.65
FORCE_SCALE = 0.16
SCATTER_BURST_SPEED = 48
SCATTER_BURST_JITTER = 10
STILL_THRESHOLD = 0.09
STILL_TIME_MS = 5000
MAGNET_PREPARE_MS = 250

MAGNET_KP = 28
MAGNET_KD_NUM = 3
MAGNET_KD_DEN = 10
MAGNET_VMAX = 220
MAGNET_TIMEOUT_MS = 3000
MAGNET_RECOVERY_MS = 500
FORCE_SNAP_INTERVAL_MS = 55

PUSH_PROTOCOL = "emoji-magnet"


def clamp(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


class EmojiMagnetApp:
    def __init__(self):
        try:
            random.seed(time.ticks_ms())
        except Exception:
            pass

        self.sound = EmojiMagnetSound(load_sound_effect())
        audio_ready = self.sound.init_audio()
        pyxel.init(start_audio=audio_ready)
        self.sound.prepare()

        self._init_sensor()
        self.assets = EmojiAssets(0)
        self.dust = PixelDust(
            WORLD_WIDTH,
            WORLD_HEIGHT,
            DUST_CAPACITY,
            DUST_SCALE,
            DUST_ELASTICITY,
            True,
            DUST_SEED,
        )
        self.dust.set_bound_mode(PixelDust.BOUND_BOUNCE)
        self._set_visible_floor(True)
        self.snapshot = bytearray(DUST_CAPACITY * 4)
        self.particle_ids = []
        self.target_x = bytearray(DUST_CAPACITY)
        self.target_y = bytearray(DUST_CAPACITY)
        self.target_color = bytearray(DUST_CAPACITY)
        self.particle_layer = bytearray(DUST_CAPACITY)
        self.locked = bytearray(DUST_CAPACITY)
        self.remove_after_magnet = bytearray(DUST_CAPACITY)
        self.emoji_colors = bytearray(MAX_PARTICLE_COUNT)

        self.state = STATE_EMOJI
        self.state_started_ms = time.ticks_ms()
        self.still_started_ms = None
        self.magnet_started_ms = 0
        self.recovery_started_ms = 0
        self.last_force_snap_ms = 0
        self.recovery_active = False
        self.current_layer = 0
        self.locked_count = 0
        self.current_emoji_id = -1
        self.current_wall = self._choice(WALLS)
        self.emoji_locked = False

        self._clear_touch_events()
        self._choose_next_emoji()
        self._spawn_initial_emoji()
        self.last_ax, self.last_ay, self.last_az = g_sensor.get_accel()
        mpy_message.onMessage(self.on_push_message)

    def run(self):
        pyxel.run(self.update, self.draw, fps=FPS, on_exit=self.on_exit)

    def _init_sensor(self):
        if not g_sensor.init():
            raise RuntimeError("g_sensor init failed")
        deadline = time.ticks_add(time.ticks_ms(), 5000)
        while g_sensor.is_ready() != g_sensor.STATUS_OK:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                g_sensor.deinit()
                raise RuntimeError("g_sensor not ready")
            time.sleep_ms(50)
        while True:
            try:
                g_sensor.get_accel()
                break
            except RuntimeError:
                if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                    g_sensor.deinit()
                    raise RuntimeError("g_sensor data not ready")
                time.sleep_ms(20)
    def _spawn_initial_emoji(self):
        origin_x, origin_y = self._emoji_origin()
        index = 0
        for ey in range(EMOJI_HEIGHT):
            for ex in range(EMOJI_WIDTH):
                color = self.emoji_colors[index]
                if color != TRANSPARENT_COLOR:
                    particle_id = self.dust.spawn(
                        origin_x + ex,
                        origin_y + ey,
                        0,
                        0,
                        color,
                    )
                    self.particle_ids.append(particle_id)
                index += 1

    def update(self, _runtime):
        ax, ay, az = g_sensor.get_accel()
        motion = (
            abs(ax - self.last_ax)
            + abs(ay - self.last_ay)
            + abs(az - self.last_az)
        )
        self.last_ax, self.last_ay, self.last_az = ax, ay, az

        if self._update_touch():
            return

        if self.state == STATE_EMOJI:
            if not self.emoji_locked and motion >= SHAKE_THRESHOLD:
                self._start_scatter(motion)
        elif self.state == STATE_PHYSICS:
            self.dust.iterate(ax * FORCE_SCALE, az * FORCE_SCALE, 0.0)
            self._update_stillness(motion)
        elif self.state == STATE_MAGNET_PREPARE:
            if time.ticks_diff(time.ticks_ms(), self.state_started_ms) >= MAGNET_PREPARE_MS:
                self._start_magnet()
        elif self.state == STATE_MAGNET:
            self._update_magnet()

    def draw(self, _runtime):
        pyxel.cls(BACKGROUND_COLOR)
        count = self.dust.alive_snapshot(self.snapshot)
        for index in range(count):
            base = index * 4
            x = self.snapshot[base + 1]
            y = self.snapshot[base + 2]
            if 0 <= x < DISPLAY_WIDTH and 0 <= y < DISPLAY_HEIGHT:
                pyxel.pset(x, y, self.snapshot[base + 3])
        if self.emoji_locked:
            self._draw_lock_frame()

    def _update_touch(self):
        toggled = False
        for _ in range(TOUCH_EVENTS_PER_UPDATE):
            event = touch_events.get()
            if event is None:
                break
            if self._is_click_event(event) and self.state == STATE_EMOJI:
                self.emoji_locked = not self.emoji_locked
                toggled = True
        return toggled

    def _is_click_event(self, event):
        try:
            return str(event).strip().lower() in TOUCH_CLICK_EVENTS
        except Exception:
            return False

    def _clear_touch_events(self):
        try:
            touch_events.clear()
        except Exception:
            pass

    def _draw_lock_frame(self):
        color = LOCK_FRAME_COLOR
        left = LOCK_FRAME_LEFT
        top = LOCK_FRAME_TOP
        right = LOCK_FRAME_RIGHT
        bottom = LOCK_FRAME_BOTTOM
        pyxel.pset(left, top + 1, color)
        pyxel.pset(left, top, color)
        pyxel.pset(left + 1, top, color)
        pyxel.pset(right - 1, top, color)
        pyxel.pset(right, top, color)
        pyxel.pset(right, top + 1, color)
        pyxel.pset(left, bottom - 1, color)
        pyxel.pset(left, bottom, color)
        pyxel.pset(left + 1, bottom, color)
        pyxel.pset(right - 1, bottom, color)
        pyxel.pset(right, bottom, color)
        pyxel.pset(right, bottom - 1, color)

    def _start_scatter(self, motion):
        # Release the completed emoji with one light, center-outward burst.
        # After this frame, only physical gravity and collisions apply.
        center_x = EMOJI_ORIGIN_X + EMOJI_WIDTH // 2
        center_y = EMOJI_ORIGIN_Y + EMOJI_HEIGHT // 2
        for particle_id in self.particle_ids:
            x, y = self.dust.get_position(particle_id)
            dx = x - center_x
            dy = y - center_y
            if dx == 0 and dy == 0:
                dx = self._randint(-1, 1)
                dy = self._randint(-1, 1)
                if dx == 0 and dy == 0:
                    dx = 1

            # The denominator approximates the radial length without floats,
            # keeping diagonal particles from receiving a stronger burst.
            major = max(abs(dx), abs(dy))
            minor = min(abs(dx), abs(dy))
            length = major + minor // 2
            vx = dx * SCATTER_BURST_SPEED // length
            vy = dy * SCATTER_BURST_SPEED // length
            vx += self._randint(-SCATTER_BURST_JITTER, SCATTER_BURST_JITTER)
            vy += self._randint(-SCATTER_BURST_JITTER, SCATTER_BURST_JITTER)
            self.dust.set_velocity(particle_id, vx, vy)
        self.sound.scatter()
        self.still_started_ms = None
        self._set_state(STATE_PHYSICS)

    def _update_stillness(self, motion):
        now = time.ticks_ms()
        if motion >= STILL_THRESHOLD:
            self.still_started_ms = None
            return
        if self.still_started_ms is None:
            self.still_started_ms = now
            return
        if time.ticks_diff(now, self.still_started_ms) >= STILL_TIME_MS:
            self._prepare_next_emoji()

    def _prepare_next_emoji(self):
        self._freeze_all()
        self._set_visible_floor(False)
        self._choose_next_emoji()
        self.current_wall = self._choice(WALLS)
        self._resize_particles(self._visible_colors())
        self._assign_targets()
        self.current_layer = 0
        self.locked_count = 0
        for particle_id in self.particle_ids:
            self.locked[particle_id] = 0
        self.recovery_active = False
        self._set_state(STATE_MAGNET_PREPARE)

    def _choose_next_emoji(self):
        previous_id = self.current_emoji_id
        while True:
            emoji_id = self._randrange(EMOJI_COUNT)
            if emoji_id == previous_id:
                continue
            self.assets.load(emoji_id, self.emoji_colors)
            if self._visible_colors():
                self.current_emoji_id = emoji_id
                return

    def _visible_colors(self):
        return [color for color in self.emoji_colors if color != TRANSPARENT_COLOR]

    def _resize_particles(self, visible_colors):
        desired_count = len(visible_colors)
        # New particles wait below the hidden floor, then enter during
        # physical magnet motion instead of popping into view.
        occupancy = self._occupancy()
        while len(self.particle_ids) < desired_count:
            empty = self._find_offscreen_spawn_cell(occupancy)
            if empty is None:
                raise RuntimeError("no empty cell for emoji particle")
            color = visible_colors[len(self.particle_ids)]
            particle_id = self.dust.spawn(empty[0], empty[1], 0, 0, color)
            self.particle_ids.append(particle_id)
            occupancy[empty] = particle_id

    def _assign_targets(self):
        origin_x, origin_y = self._emoji_origin()
        target_groups = [[] for _ in range(EMOJI_WIDTH)]
        color_index = 0
        for ey in range(EMOJI_HEIGHT):
            for ex in range(EMOJI_WIDTH):
                color = self.emoji_colors[color_index]
                if color != TRANSPARENT_COLOR:
                    layer = self._target_layer(ex, ey)
                    target_groups[layer].append((origin_x + ex, origin_y + ey, color))
                color_index += 1

        positions = self._particle_positions()
        particles = list(self.particle_ids)
        particles.sort(key=lambda particle_id: self._particle_sort_key(positions[particle_id]))
        for particle_id in particles:
            self.remove_after_magnet[particle_id] = 0

        offset = 0
        all_targets = []
        for layer in range(EMOJI_WIDTH):
            targets = target_groups[layer]
            targets.sort(key=self._target_cross_key)
            for tx, ty, color in targets:
                all_targets.append((layer, tx, ty, color))
            group = particles[offset:offset + len(targets)]
            group.sort(key=lambda particle_id: self._particle_cross_key(positions[particle_id]))
            for index in range(len(targets)):
                particle_id = group[index]
                tx, ty, color = targets[index]
                self.target_x[particle_id] = tx
                self.target_y[particle_id] = ty
                self.target_color[particle_id] = color
                self.particle_layer[particle_id] = layer
            offset += len(targets)

        # Surplus particles share a small set of existing targets (roughly
        # two extras per target), then retire only after reaching one.
        # This makes the reduction read as visible convergence, rather than
        # an abrupt disappearance in the display.
        surplus = particles[offset:]
        merge_target_count = (len(surplus) + 1) // 2
        merge_targets = []
        for index in range(merge_target_count):
            target_index = (index * len(all_targets)) // merge_target_count
            merge_targets.append(all_targets[target_index])
        for index, particle_id in enumerate(surplus):
            layer, tx, ty, color = merge_targets[index % merge_target_count]
            self.target_x[particle_id] = tx
            self.target_y[particle_id] = ty
            self.target_color[particle_id] = color
            self.particle_layer[particle_id] = layer
            self.remove_after_magnet[particle_id] = 1

    def _start_magnet(self):
        now = time.ticks_ms()
        self.magnet_started_ms = now
        self.last_force_snap_ms = now
        self.sound.whoosh()
        self._set_state(STATE_MAGNET)

    def _update_magnet(self):
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.magnet_started_ms)
        if not self.recovery_active and elapsed >= MAGNET_TIMEOUT_MS:
            self.recovery_active = True
            self.recovery_started_ms = now
            self._retire_surplus_particles()
            self._reassign_unlocked()

        for particle_id in self.particle_ids:
            if self.locked[particle_id]:
                continue
            if not self.recovery_active and self.particle_layer[particle_id] != self.current_layer:
                self.dust.set_velocity(particle_id, 0, 0)
                continue
            x, y = self.dust.get_position(particle_id)
            vx0, vy0 = self.dust.get_velocity(particle_id)
            dx = self.target_x[particle_id] - x
            dy = self.target_y[particle_id] - y
            vx = dx * MAGNET_KP - (vx0 * MAGNET_KD_NUM) // MAGNET_KD_DEN
            vy = dy * MAGNET_KP - (vy0 * MAGNET_KD_NUM) // MAGNET_KD_DEN
            self.dust.set_velocity(
                particle_id,
                clamp(vx, -MAGNET_VMAX, MAGNET_VMAX),
                clamp(vy, -MAGNET_VMAX, MAGNET_VMAX),
            )

        self.dust.iterate(0.0, 0.0, 0.0)
        self._snap_near_particles()

        if not self.recovery_active:
            self._advance_layer()
        elif time.ticks_diff(now, self.recovery_started_ms) >= MAGNET_RECOVERY_MS:
            if time.ticks_diff(now, self.last_force_snap_ms) >= FORCE_SNAP_INTERVAL_MS:
                self.last_force_snap_ms = now
                self._force_snap_one()

        if self.locked_count >= len(self.particle_ids):
            self._complete_emoji()

    def _snap_near_particles(self):
        for particle_id in tuple(self.particle_ids):
            if self.locked[particle_id]:
                continue
            if not self.recovery_active and self.particle_layer[particle_id] != self.current_layer:
                continue
            x, y = self.dust.get_position(particle_id)
            tx = self.target_x[particle_id]
            ty = self.target_y[particle_id]
            if abs(tx - x) <= 1 and abs(ty - y) <= 1:
                self._try_lock(particle_id)

    def _try_lock(self, particle_id):
        if self.remove_after_magnet[particle_id]:
            self._retire_particle(particle_id)
            return True
        if not self.dust.set_position(
            particle_id,
            self.target_x[particle_id],
            self.target_y[particle_id],
        ):
            return False
        self.dust.set_color(particle_id, self.target_color[particle_id])
        self.dust.set_velocity(particle_id, 0, 0)
        self.locked[particle_id] = 1
        self.locked_count += 1
        return True

    def _retire_particle(self, particle_id):
        self.dust.despawn(particle_id)
        self.particle_ids.remove(particle_id)
        self.remove_after_magnet[particle_id] = 0
        self.locked[particle_id] = 0

    def _retire_surplus_particles(self):
        for particle_id in tuple(self.particle_ids):
            if self.remove_after_magnet[particle_id]:
                self._retire_particle(particle_id)

    def _advance_layer(self):
        while self.current_layer < EMOJI_WIDTH:
            for particle_id in self.particle_ids:
                if self.particle_layer[particle_id] == self.current_layer and not self.locked[particle_id]:
                    return
            self.current_layer += 1

    def _reassign_unlocked(self):
        particles = [particle_id for particle_id in self.particle_ids if not self.locked[particle_id]]
        if not particles:
            return
        positions = self._particle_positions()
        particles.sort(key=lambda particle_id: self._particle_sort_key(positions[particle_id]))
        targets = []
        for particle_id in self.particle_ids:
            if not self.locked[particle_id]:
                targets.append((
                    self.target_x[particle_id],
                    self.target_y[particle_id],
                    self.target_color[particle_id],
                ))
        targets.sort(key=self._target_full_key)
        for index in range(len(particles)):
            particle_id = particles[index]
            tx, ty, color = targets[index]
            self.target_x[particle_id] = tx
            self.target_y[particle_id] = ty
            self.target_color[particle_id] = color

    def _force_snap_one(self):
        occupancy = self._occupancy()
        for particle_id in self.particle_ids:
            if self.locked[particle_id]:
                continue
            if self.remove_after_magnet[particle_id]:
                self._retire_particle(particle_id)
                return True
            target = (self.target_x[particle_id], self.target_y[particle_id])
            blocker = occupancy.get(target)
            if blocker is not None and blocker != particle_id:
                if self.locked[blocker]:
                    continue
                # Recovery uses the hidden lower area, never the visible
                # top-left cell, for a temporarily displaced blocker.
                empty = self._find_offscreen_spawn_cell(occupancy)
                if empty is None or not self.dust.set_position(blocker, empty[0], empty[1]):
                    continue
                self.dust.set_velocity(blocker, 0, 0)
                del occupancy[target]
                occupancy[empty] = blocker
            if self._try_lock(particle_id):
                return True
        return False

    def _complete_emoji(self):
        self.sound.final_snap()
        self._freeze_all()
        self._set_visible_floor(True)
        self.still_started_ms = None
        self._set_state(STATE_EMOJI)

    def _freeze_all(self):
        for particle_id in self.particle_ids:
            self.dust.set_velocity(particle_id, 0, 0)

    def _particle_positions(self):
        positions = {}
        count = self.dust.alive_snapshot(self.snapshot)
        for index in range(count):
            base = index * 4
            positions[self.snapshot[base]] = (
                self.snapshot[base + 1],
                self.snapshot[base + 2],
            )
        return positions

    def _occupancy(self):
        occupancy = {}
        positions = self._particle_positions()
        for particle_id, position in positions.items():
            occupancy[position] = particle_id
        return occupancy

    def _find_empty_cell(self, occupancy):
        for y in range(WORLD_HEIGHT):
            for x in range(WORLD_WIDTH):
                if (x, y) not in occupancy:
                    return x, y
        return None

    def _find_offscreen_spawn_cell(self, occupancy):
        for _ in range(64):
            x = self._randint(0, WORLD_WIDTH - 1)
            y = self._randint(VISIBLE_FLOOR_Y + 1, WORLD_HEIGHT - 1)
            if (x, y) not in occupancy:
                return x, y
        for y in range(VISIBLE_FLOOR_Y + 1, WORLD_HEIGHT):
            for x in range(WORLD_WIDTH):
                if (x, y) not in occupancy:
                    return x, y
        return None

    def _target_layer(self, ex, ey):
        if self.current_wall == WALL_LEFT:
            return ex
        if self.current_wall == WALL_RIGHT:
            return EMOJI_WIDTH - 1 - ex
        if self.current_wall == WALL_TOP:
            return ey
        return EMOJI_HEIGHT - 1 - ey

    def _particle_sort_key(self, position):
        x, y = position
        if self.current_wall == WALL_LEFT:
            return x, y
        if self.current_wall == WALL_RIGHT:
            return -x, y
        if self.current_wall == WALL_TOP:
            return y, x
        return -y, x

    def _particle_cross_key(self, position):
        x, y = position
        return y if self.current_wall in (WALL_LEFT, WALL_RIGHT) else x

    def _target_cross_key(self, target):
        return target[1] if self.current_wall in (WALL_LEFT, WALL_RIGHT) else target[0]

    def _target_full_key(self, target):
        x, y, _color = target
        return self._particle_sort_key((x, y))

    def _emoji_origin(self):
        # The completed emoji is always centered. current_wall remains a
        # magnetic sweep direction only, not a display position.
        return EMOJI_ORIGIN_X, EMOJI_ORIGIN_Y

    def _set_visible_floor(self, enabled):
        for x in range(DISPLAY_WIDTH):
            if enabled:
                self.dust.set_obstacle(x, VISIBLE_FLOOR_Y)
            else:
                self.dust.clear_obstacle(x, VISIBLE_FLOOR_Y)

    def _set_state(self, state):
        self.state = state
        self.state_started_ms = time.ticks_ms()

    def on_push_message(self, message):
        try:
            data = json.loads(str(message))
        except Exception:
            return
        if data.get("type") != PUSH_PROTOCOL or data.get("command") != "config":
            return
        if "soundEffect" not in data:
            return
        enabled = bool(data["soundEffect"])
        self.sound.set_enabled(enabled)
        save_sound_effect(enabled)
        print("[EmojiMagnet] sound effect:", "on" if enabled else "off")

    def on_exit(self, _runtime, _reason, _exc):
        try:
            mpy_message.onMessage(None)
        except Exception:
            pass
        try:
            self.dust.deinit()
        except Exception:
            pass
        try:
            g_sensor.deinit()
        except Exception:
            pass
        self.sound.deinit()
        try:
            pyxel.destroy()
        except Exception:
            pass

    def _randint(self, minimum, maximum):
        try:
            return random.randint(minimum, maximum)
        except Exception:
            return minimum + random.getrandbits(16) % (maximum - minimum + 1)

    def _randrange(self, stop):
        return self._randint(0, stop - 1)

    def _choice(self, values):
        return values[self._randrange(len(values))]
