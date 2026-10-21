"""Hitung tick dan biaya aksi. Tidak tahu apa-apa soal UI atau dunia."""
import json
from pathlib import Path
import time

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_costs(path=None):
    path = Path(path) if path else DATA_DIR / "costs.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Clock:
    def __init__(self, costs=None):
        self.costs = costs if costs is not None else load_costs()
        self.tick_count = 0
        self.started_at = time.perf_counter()
        self.execution_start_tick = 0

    def start_execution(self):
        self.execution_start_tick = self.tick_count

    def get_time(self):
        return time.perf_counter() - self.started_at

    def get_execution_tick_count(self):
        return self.tick_count - self.execution_start_tick

    def cost_of(self, name, success=True):
        """Biaya tick untuk aksi/sensor `name`."""
        if name in self.costs["actions"]:
            entry = self.costs["actions"][name]
            return entry["success"] if success else entry["fail"]
        if name in self.costs["sensors"]:
            return self.costs["sensors"][name]
        if name in self.costs.get("statements", {}):
            return self.costs["statements"][name]
        if name in self.costs.get("operators", {}):
            return self.costs["operators"][name]
        if name in self.costs.get("builtins", {}):
            return self.costs["builtins"][name]
        raise KeyError(f"biaya tick untuk '{name}' tidak ada di costs.json")

    def charge(self, name, success=True):
        cost = self.cost_of(name, success)
        self.advance(cost)
        return cost

    def advance(self, ticks=1):
        self.tick_count += ticks
        return self.tick_count

    def reset(self):
        self.tick_count = 0
        self.execution_start_tick = 0
