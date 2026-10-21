"""Grid ladang, petak, dan aturan pertumbuhan. Murni logika, tanpa UI."""
from dataclasses import dataclass
from typing import Optional

GRASSLAND = "grassland"
SOIL = "soil"


@dataclass
class Tile:
    ground: str = GRASSLAND
    entity: Optional[str] = None
    age: float = 0.0  # dalam tick sejak ditanam
    water: float = 0.0


class World:
    def __init__(self, size, entity_defs, height=None):
        height = size if height is None else height
        if size < 1 or height < 1:
            raise ValueError("ukuran dunia minimal 1")
        self.width = size
        self.height = height
        self.size = max(size, height)
        self.defs = entity_defs
        self.tiles = [[Tile() for _ in range(height)] for _ in range(size)]
        # Awal: semua petak berumput (asumsi, lihat entities.json).
        for x in range(self.width):
            for y in range(self.height):
                self._regrow(self.tiles[x][y])

    def resize(self, width, height):
        if width < 1 or height < 1:
            raise ValueError("ukuran dunia minimal 1")
        old_tiles = self.tiles
        old_width, old_height = self.width, self.height
        self.tiles = [
            [
                old_tiles[x][y] if x < old_width and y < old_height else Tile()
                for y in range(height)
            ]
            for x in range(width)
        ]
        self.width = width
        self.height = height
        self.size = max(width, height)
        for x in range(width):
            for y in range(height):
                if x >= old_width or y >= old_height:
                    self._regrow(self.tiles[x][y])

    def expand_and_clear(self, width, height):
        self.resize(width, height)
        self.clear_farm()

    def clear_farm(self):
        for column in self.tiles:
            for tile in column:
                tile.ground = GRASSLAND
                tile.entity = None
                tile.age = 0
                tile.water = 0.0
                self._regrow(tile)

    # --- akses petak, wrap-around lewat modulo ---
    def wrap(self, x, y):
        return x % self.width, y % self.height

    def tile(self, x, y):
        x, y = self.wrap(x, y)
        return self.tiles[x][y]

    # --- pertumbuhan berbasis tick ---
    def advance(self, ticks, seconds_per_tick=1 / 400):
        if ticks <= 0:
            return
        water_decay = 0.99 ** seconds_per_tick
        total_water_decay = water_decay ** ticks
        for col in self.tiles:
            for t in col:
                if t.entity is not None:
                    if t.water <= 0:
                        t.age += ticks
                    elif water_decay == 1:
                        t.age += ticks * (1 + 4 * t.water)
                    else:
                        accumulated_water = (
                            t.water
                            * (1 - total_water_decay)
                            / (1 - water_decay)
                        )
                        t.age += ticks + 4 * accumulated_water
                t.water *= total_water_decay

    def is_mature(self, tile):
        if tile.entity is None:
            return False
        return tile.age >= self.defs[tile.entity].grow_ticks

    # --- operasi petak (dipanggil Drone) ---
    def clear_tile(self, tile):
        tile.entity = None
        tile.age = 0
        self._regrow(tile)

    def _regrow(self, tile):
        """Rumput tumbuh lagi otomatis di grassland."""
        if tile.ground == GRASSLAND:
            grass = self.defs.get("grass")
            if grass and grass.auto_regrow:
                tile.entity = "grass"
                tile.age = 0

    def toggle_ground(self, tile):
        tile.ground = SOIL if tile.ground == GRASSLAND else GRASSLAND
        tile.entity = None
        tile.age = 0
        self._regrow(tile)
