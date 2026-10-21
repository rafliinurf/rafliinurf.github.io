"""Drone. Semua aksi dan sensor lewat satu pintu: perform()."""
import math
from dataclasses import dataclass
from typing import Any, Iterator

DIRECTIONS = {
    "north": (0, 1),
    "east": (1, 0),
    "south": (0, -1),
    "west": (-1, 0),
}


@dataclass
class ActionResult:
    success: bool
    value: Any
    cost: int


@dataclass(frozen=True)
class ActionProgress:
    success: bool
    value: Any
    completed_ticks: int
    total_ticks: int
    tick_count: int


class Drone:
    def __init__(self, world, clock, inventory, x=0, y=0):
        self.world = world
        self.clock = clock
        self.inventory = inventory
        self.x, self.y = world.wrap(x, y)
        self.last_dir = None
        self.grass_yield_multiplier = 1
        self.speed_multiplier = 1.0
        self.watering_tanks_per_10_seconds = 0
        self.water_time_seconds = 0.0
        self.last_harvest_event = None
        self.log = []  # (tick_sebelum, nama, args, sukses)

    @property
    def tile(self):
        return self.world.tile(self.x, self.y)

    def perform(self, name, *args):
        """Jalankan aksi/sensor `name`, tagih tick, majukan dunia, catat log."""
        steps = self.perform_steps(name, *args)
        while True:
            try:
                next(steps)
            except StopIteration as stopped:
                return stopped.value

    def perform_steps(self, name, *args) -> Iterator[ActionProgress]:
        """Jalankan efek aksi lalu yield progress untuk setiap tick biayanya."""
        handler = getattr(self, f"_do_{name}", None)
        if handler is None:
            raise ValueError(f"aksi tidak dikenal: {name}")
        tick_before = self.clock.tick_count
        success, value = handler(*args)
        cost = self.clock.cost_of(name, success)
        self.log.append((tick_before, name, args, success))
        for completed_ticks in range(1, cost + 1):
            tick_count = self.clock.advance()
            self._advance_world(1)
            yield ActionProgress(success, value, completed_ticks, cost, tick_count)
        return ActionResult(success, value, cost)

    def statement_steps(self, name) -> Iterator[ActionProgress]:
        """Majukan waktu untuk statement bahasa yang memiliki biaya tick."""
        cost = self.clock.cost_of(name)
        for completed_ticks in range(1, cost + 1):
            tick_count = self.clock.advance()
            self._advance_world(1)
            yield ActionProgress(True, None, completed_ticks, cost, tick_count)
        return ActionResult(True, None, cost)

    def _advance_world(self, ticks):
        seconds_per_tick = 1 / (400 * self.speed_multiplier)
        self.world.advance(ticks, seconds_per_tick)
        if not self.watering_tanks_per_10_seconds:
            return
        self.water_time_seconds += ticks * seconds_per_tick
        tanks_due = math.floor((self.water_time_seconds + 1e-12) / 10)
        if tanks_due:
            self.water_time_seconds = max(
                0.0,
                self.water_time_seconds - tanks_due * 10,
            )
            self.inventory.add(
                "water",
                tanks_due * self.watering_tanks_per_10_seconds,
            )

    # --- aksi ---
    def _do_move(self, direction):
        if direction not in DIRECTIONS:
            return False, None
        dx, dy = DIRECTIONS[direction]
        self.x, self.y = self.world.wrap(self.x + dx, self.y + dy)
        self.last_dir = direction
        return True, True

    def _do_harvest(self):
        self.last_harvest_event = None
        t = self.tile
        if t.entity is None:
            return False, False
        d = self.world.defs[t.entity]
        mature = self.world.is_mature(t)
        yields = {}
        if mature:
            for item, n in d.yield_.items():
                if t.entity == "grass" and item == "hay":
                    n *= self.grass_yield_multiplier
                self.inventory.add(item, n)
                yields[item] = n
        self.last_harvest_event = {
            "x": self.x,
            "y": self.y,
            "entity": t.entity,
            "mature": mature,
            "progress": min(1.0, t.age / d.grow_ticks),
            "yields": yields,
        }
        # yang belum matang ikut hancur, tanpa hasil
        self.world.clear_tile(t)
        return True, True

    def _do_plant(self, entity):
        d = self.world.defs.get(entity)
        t = self.tile
        grass = self.world.defs.get("grass")
        replaceable_grass = (
            t.entity == "grass"
            and grass is not None
            and grass.auto_regrow
        )
        if d is None or (t.entity is not None and not replaceable_grass):
            return False, False
        if t.ground != d.requires_ground:
            return False, False
        if not self.inventory.pay(d.cost):
            return False, False
        t.entity = entity
        t.age = 0
        return True, True

    def _do_till(self):
        self.world.toggle_ground(self.tile)
        return True, None

    def _do_clear(self):
        self.world.clear_farm()
        self.x, self.y = 0, 0
        self.last_dir = None
        self.last_harvest_event = None
        return True, None

    def _do_use_item(self, item, n=1):
        if (
            item != "water"
            or isinstance(n, bool)
            or not isinstance(n, int)
            or n < 1
        ):
            return False, False
        tile = self.tile
        tanks_used = min(
            n,
            self.inventory.count("water"),
            math.ceil(max(0.0, 1 - tile.water) / 0.25),
        )
        if not tanks_used:
            return False, False
        if not self.inventory.pay({"water": tanks_used}):
            return False, False
        tile.water = min(1.0, tile.water + 0.25 * tanks_used)
        return True, True

    # --- sensor (selalu "berhasil") ---
    def _do_can_harvest(self):
        return True, self.world.is_mature(self.tile)

    def _do_get_entity_type(self):
        return True, self.tile.entity

    def _do_get_ground_type(self):
        return True, self.tile.ground

    def _do_can_move(self, direction):
        return True, direction in DIRECTIONS

    def _do_get_pos_x(self):
        return True, self.x

    def _do_get_pos_y(self):
        return True, self.y

    def _do_get_world_size(self):
        return True, self.world.size

    def _do_get_water(self):
        return True, self.tile.water

    def _do_get_time(self):
        return True, self.clock.get_time()

    def _do_get_tick_count(self):
        return True, self.clock.get_execution_tick_count()

    def _do_get_cost(self, cost):
        return True, cost

    def _do_num_items(self, item):
        return True, self.inventory.count(item)

    def _do_num_unlocked(self, count):
        return True, count

    def _do_num_items(self, item):
        return True, self.inventory.count(item)
