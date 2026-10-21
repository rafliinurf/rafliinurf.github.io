"""Research unlock state and costs."""
import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_tech_tree(path=None):
    path = Path(path) if path else DATA_DIR / "techtree.json"
    with open(path, encoding="utf-8") as file:
        raw = json.load(file)
    return {name: data for name, data in raw.items() if not name.startswith("_")}


class Progression:
    def __init__(self, inventory, tech_tree=None):
        self.inventory = inventory
        self.tech_tree = tech_tree if tech_tree is not None else load_tech_tree()
        self.unlocked = set()
        self.upgrade_levels = {}

    def is_unlocked(self, unlock):
        return unlock in self.unlocked

    def status(self, unlock):
        data = self.tech_tree.get(unlock)
        if (
            data is None
            or not {"prerequisites", "features"}.issubset(data)
            or ("cost" not in data and not data.get("levels"))
        ):
            return "unknown"
        levels = data.get("levels")
        if levels:
            if self.upgrade_level(unlock) >= len(levels):
                return "unlocked"
        elif self.is_unlocked(unlock):
            return "unlocked"
        if not set(data.get("prerequisites", ())).issubset(self.unlocked):
            return "locked"
        return "available"

    def is_affordable(self, unlock):
        cost = self.current_cost(unlock)
        return (
            cost is not None
            and self.inventory.can_afford(cost)
        )

    def current_cost(self, unlock):
        data = self.tech_tree.get(unlock)
        if data is None:
            return None
        levels = data.get("levels")
        if levels:
            level = self.upgrade_level(unlock)
            if level >= len(levels):
                return None
            return levels[level].get("cost")
        return data.get("cost")

    def upgrade_level(self, unlock):
        return self.upgrade_levels.get(unlock, 0)

    def max_upgrade_level(self, unlock):
        data = self.tech_tree.get(unlock, {})
        levels = data.get("levels")
        return len(levels) if levels else None

    def can_unlock(self, unlock):
        data = self.tech_tree.get(unlock)
        if data is None or self.status(unlock) != "available":
            return False
        return self.is_affordable(unlock)

    def unlock(self, unlock):
        if not self.can_unlock(unlock):
            return False
        data = self.tech_tree[unlock]
        cost = self.current_cost(unlock)
        if cost is None or not self.inventory.pay(cost):
            return False
        self.unlocked.add(unlock)
        if data.get("levels"):
            self.upgrade_levels[unlock] = self.upgrade_level(unlock) + 1
        return True

    def tutorial(self, unlock):
        data = self.tech_tree.get(unlock, {})
        return data.get("tutorial")

    def features(self):
        return frozenset(
            feature
            for unlock in self.unlocked
            for feature in self.tech_tree[unlock].get("features", ())
        )

    def grass_yield_multiplier(self):
        data = self.tech_tree.get("Grass", {})
        levels = data.get("levels", ())
        level = self.upgrade_level("Grass")
        if not level:
            return 1
        return levels[level - 1]["effects"]["grass_yield_multiplier"]

    def speed_multiplier(self):
        levels = self.tech_tree.get("Speed", {}).get("levels", ())
        multiplier = 1.0
        for level in levels[:self.upgrade_level("Speed")]:
            multiplier *= level["effects"]["speed_multiplier_per_level"]
        return multiplier

    def watering_tanks_per_10_seconds(self):
        levels = self.tech_tree.get("Watering", {}).get("levels", ())
        level = self.upgrade_level("Watering")
        if not level:
            return 0
        return levels[level - 1]["effects"]["water_tanks_per_10_seconds"]

    def get_cost(self, target, level=None):
        if not isinstance(target, str):
            raise ValueError("get_cost hanya menerima entity atau unlock")
        if level is not None and (
            isinstance(level, bool)
            or not isinstance(level, int)
            or level < 0
        ):
            raise ValueError("level get_cost harus berupa integer non-negatif")

        data = self.tech_tree.get(target)
        if data is not None:
            levels = data.get("levels")
            if levels:
                cost_level = self.upgrade_level(target) if level is None else level
                if cost_level >= len(levels):
                    return None
                cost = levels[cost_level].get("cost")
                return None if cost is None else dict(cost)
            if level not in (None, 0):
                return None
            cost = data.get("cost")
            return None if cost is None else dict(cost)

        raise ValueError(f"get_cost tidak mengenali entity atau unlock: {target}")

    def current_level_effects(self, unlock):
        data = self.tech_tree.get(unlock, {})
        levels = data.get("levels", ())
        level = self.upgrade_level(unlock)
        if not level or level > len(levels):
            return {}
        return dict(levels[level - 1].get("effects", {}))

    def num_unlocked(self, target):
        if target in self.tech_tree:
            if self.max_upgrade_level(target) is not None:
                return self.upgrade_level(target)
            return int(self.is_unlocked(target))
        features = self.features()
        unlocked_entities = {
            "grass": True,
            "bush": "planting" in features,
            "carrot": "carrots" in features,
            "tree": "trees" in features,
            "pumpkin": "pumpkins" in features,
            "cactus": "cactus" in features,
            "sunflower": "sunflowers" in features,
        }
        if target in unlocked_entities:
            return int(unlocked_entities[target])
        if target in {"grassland", "soil"}:
            return 1
        unlocked_items = {
            "hay": True,
            "wood": "planting" in features,
            "carrot": "carrots" in features,
            "pumpkin": "pumpkins" in features,
            "cactus": "cactus" in features,
            "power": "sunflowers" in features,
            "water": "watering" in features,
            "fertilizer": "fertilizer" in features,
            "weird_substance": "mazes" in features,
            "bone": "dinosaurs" in features,
            "gold": "mazes" in features,
        }
        return int(unlocked_items.get(target, False))