"""Definisi tanaman, dimuat dari data/entities.json."""
import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class EntityDef:
    name: str
    grow_ticks: int
    requires_ground: str
    cost: dict = field(default_factory=dict)
    yield_: dict = field(default_factory=dict)
    auto_regrow: bool = False


def load_entities(path=None):
    path = Path(path) if path else DATA_DIR / "entities.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    defs = {}
    for name, d in raw.items():
        if name.startswith("_"):
            continue
        defs[name] = EntityDef(
            name=name,
            grow_ticks=d["grow_ticks"],
            requires_ground=d["requires_ground"],
            cost=d.get("cost", {}),
            yield_=d.get("yield", {}),
            auto_regrow=d.get("auto_regrow", False),
        )
    return defs
