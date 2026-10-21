"""Validated local game-state persistence."""
import json
import math
import os
from pathlib import Path
import tempfile

from game.world import GRASSLAND, SOIL


SAVE_VERSION = 1
MAX_WORLD_DIMENSION = 10


def save_game(path, world, inventory, progression, drone, clock, script=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "version": SAVE_VERSION,
        "inventory": inventory.as_dict(),
        "unlocked": sorted(progression.unlocked),
        "upgrade_levels": progression.upgrade_levels,
        "world": {
            "width": world.width,
            "height": world.height,
            "tiles": [
                [
                    {
                        "ground": tile.ground,
                        "entity": tile.entity,
                        "age": tile.age,
                        "water": tile.water,
                    }
                    for tile in column
                ]
                for column in world.tiles
            ],
        },
        "drone": {
            "x": drone.x,
            "y": drone.y,
            "water_time_seconds": drone.water_time_seconds,
        },
        "clock_tick_count": clock.tick_count,
        "script": script,
    }
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(state, file, ensure_ascii=False, allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def load_game(path, world, inventory, progression, drone, clock):
    path = Path(path)
    if not path.exists():
        return None

    try:
        with path.open(encoding="utf-8") as file:
            state = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"save file is not valid JSON: {path}") from exc

    validated = _validate_state(state, world, progression)
    width, height, tiles, items, unlocked, levels, x, y, water_time, ticks, script = validated

    world.resize(width, height)
    for tile_x, column in enumerate(tiles):
        for tile_y, tile_data in enumerate(column):
            tile = world.tiles[tile_x][tile_y]
            tile.ground = tile_data["ground"]
            tile.entity = tile_data["entity"]
            tile.age = tile_data["age"]
            tile.water = tile_data["water"]
    inventory.replace(items)
    progression.unlocked = unlocked
    progression.upgrade_levels = levels
    drone.x, drone.y = x, y
    drone.water_time_seconds = water_time
    drone.grass_yield_multiplier = progression.grass_yield_multiplier()
    drone.speed_multiplier = progression.speed_multiplier()
    drone.watering_tanks_per_10_seconds = (
        progression.watering_tanks_per_10_seconds()
    )
    drone.last_dir = None
    drone.last_harvest_event = None
    clock.tick_count = ticks
    return script


def _validate_state(state, world, progression):
    if (
        not isinstance(state, dict)
        or isinstance(state.get("version"), bool)
        or not isinstance(state.get("version"), int)
        or state.get("version") != SAVE_VERSION
    ):
        raise ValueError("save file has an unsupported format version")

    inventory = state.get("inventory")
    if not isinstance(inventory, dict):
        raise ValueError("save inventory must be an object")
    items = {}
    for item, amount in inventory.items():
        if not isinstance(item, str) or not _is_nonnegative_number(amount):
            raise ValueError("save inventory contains an invalid item amount")
        items[item] = amount

    unlocked_data = state.get("unlocked")
    if (
        not isinstance(unlocked_data, list)
        or any(
            not isinstance(name, str) or name not in progression.tech_tree
            for name in unlocked_data
        )
        or len(set(unlocked_data)) != len(unlocked_data)
    ):
        raise ValueError("save contains an invalid unlock list")
    unlocked = set(unlocked_data)

    levels_data = state.get("upgrade_levels")
    if not isinstance(levels_data, dict):
        raise ValueError("save upgrade levels must be an object")
    levels = {}
    for name, level in levels_data.items():
        max_level = progression.max_upgrade_level(name)
        if (
            max_level is None
            or isinstance(level, bool)
            or not isinstance(level, int)
            or not 1 <= level <= max_level
            or name not in unlocked
        ):
            raise ValueError("save contains an invalid upgrade level")
        levels[name] = level

    for name in unlocked:
        prerequisites = progression.tech_tree[name].get("prerequisites", ())
        if not set(prerequisites).issubset(unlocked):
            raise ValueError("save contains an unlock with unmet prerequisites")
        if progression.max_upgrade_level(name) is not None and name not in levels:
            raise ValueError("save is missing an unlocked upgrade level")

    world_data = state.get("world")
    if not isinstance(world_data, dict):
        raise ValueError("save world must be an object")
    width = _dimension(world_data.get("width"))
    height = _dimension(world_data.get("height"))
    tiles_data = world_data.get("tiles")
    if (
        not isinstance(tiles_data, list)
        or len(tiles_data) != width
        or any(not isinstance(column, list) or len(column) != height for column in tiles_data)
    ):
        raise ValueError("save tiles do not match world dimensions")

    tiles = []
    for column in tiles_data:
        tile_column = []
        for tile in column:
            if not isinstance(tile, dict):
                raise ValueError("save contains an invalid tile")
            ground = tile.get("ground")
            entity = tile.get("entity")
            age = tile.get("age")
            water = tile.get("water")
            if (
                not isinstance(ground, str)
                or ground not in {GRASSLAND, SOIL}
                or (
                    entity is not None
                    and (not isinstance(entity, str) or entity not in world.defs)
                )
                or not _is_nonnegative_number(age)
                or not _is_nonnegative_number(water)
                or water > 1
            ):
                raise ValueError("save contains invalid tile state")
            tile_column.append({
                "ground": ground,
                "entity": entity,
                "age": age,
                "water": water,
            })
        tiles.append(tile_column)

    drone_data = state.get("drone")
    if not isinstance(drone_data, dict):
        raise ValueError("save drone state must be an object")
    x = _coordinate(drone_data.get("x"), width)
    y = _coordinate(drone_data.get("y"), height)
    water_time = drone_data.get("water_time_seconds")
    if not _is_nonnegative_number(water_time) or water_time >= 10:
        raise ValueError("save contains an invalid water supply timer")

    ticks = state.get("clock_tick_count")
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise ValueError("save contains an invalid clock tick count")
    script = state.get("script", "")
    if not isinstance(script, str):
        raise ValueError("save script must be text")

    return width, height, tiles, items, unlocked, levels, x, y, water_time, ticks, script


def _is_nonnegative_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _dimension(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_WORLD_DIMENSION
    ):
        raise ValueError("save contains an unsupported world dimension")
    return value


def _coordinate(value, dimension):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < dimension:
        raise ValueError("save contains an invalid drone position")
    return value
