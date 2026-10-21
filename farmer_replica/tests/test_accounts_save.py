import json

import pytest

from game.accounts import AccountError, AccountStore
from game.clock import Clock
from game.drone import Drone
from game.entities import load_entities
from game.inventory import Inventory
from game.progression import Progression, load_tech_tree
from game.save import load_game, save_game
from game.world import SOIL, World


def test_offline_account_hashes_password_and_authenticates_case_insensitively(tmp_path):
    store = AccountStore(tmp_path)

    assert store.register("Farmer_1", "secure-pass-123") == "Farmer_1"
    assert store.authenticate("farmer_1", "secure-pass-123") == "Farmer_1"

    account_file = store.accounts_path.read_text(encoding="utf-8")
    assert "secure-pass-123" not in account_file
    assert store.profile_path("Farmer_1") == store.profile_path("farmer_1")

    with pytest.raises(AccountError, match="tidak cocok"):
        store.authenticate("FARMER_1", "wrong-password")


def test_account_tags_assign_developer_to_rafli_and_player_to_other_accounts(
    tmp_path,
):
    store = AccountStore(tmp_path)
    store.register("rafli", "secure-pass-123")
    store.register("friend", "secure-pass-123")

    assert store.tag_for("rafli") == "developer"
    assert store.tag_for("RAFLI") == "developer"
    assert store.tag_for("friend") == "player"

    accounts = json.loads(store.accounts_path.read_text(encoding="utf-8"))["accounts"]
    assert accounts["rafli"]["tag"] == "developer"
    assert accounts["friend"]["tag"] == "player"


def test_existing_accounts_receive_and_persist_default_tags(tmp_path):
    store = AccountStore(tmp_path)
    store.register("rafli", "secure-pass-123")
    data = json.loads(store.accounts_path.read_text(encoding="utf-8"))
    del data["accounts"]["rafli"]["tag"]
    store.accounts_path.write_text(json.dumps(data), encoding="utf-8")

    assert store.tag_for("rafli") == "developer"
    persisted = json.loads(store.accounts_path.read_text(encoding="utf-8"))
    assert persisted["accounts"]["rafli"]["tag"] == "developer"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ab", "secure-pass-123"),
        ("valid_name", "short"),
        ("../other", "secure-pass-123"),
    ],
)
def test_registration_rejects_invalid_credentials(tmp_path, username, password):
    with pytest.raises(AccountError):
        AccountStore(tmp_path).register(username, password)


def _create_state():
    entities = load_entities()
    inventory = Inventory({"hay": 100, "water": 3})
    progression = Progression(inventory, load_tech_tree())
    assert progression.unlock("Loops")
    assert progression.unlock("Speed")

    world = World(1, entities)
    world.resize(3, 1)
    tile = world.tile(2, 0)
    tile.ground = SOIL
    tile.entity = "carrot"
    tile.age = 125.5
    tile.water = 0.75

    clock = Clock()
    clock.tick_count = 4321
    drone = Drone(world, clock, inventory, x=2, y=0)
    drone.water_time_seconds = 9.5
    drone.speed_multiplier = progression.speed_multiplier()
    drone.watering_tanks_per_10_seconds = progression.watering_tanks_per_10_seconds()
    return world, inventory, progression, drone, clock


def test_save_round_trip_restores_account_progress_and_editor_script(tmp_path):
    path = tmp_path / "profiles" / "farmer.json"
    original = _create_state()
    save_game(path, *original, script="harvest()\n")

    restored_world = World(1, load_entities())
    restored_inventory = Inventory()
    restored_progression = Progression(restored_inventory, load_tech_tree())
    restored_clock = Clock()
    restored_drone = Drone(restored_world, restored_clock, restored_inventory)

    assert load_game(
        path,
        restored_world,
        restored_inventory,
        restored_progression,
        restored_drone,
        restored_clock,
    ) == "harvest()\n"
    assert (restored_world.width, restored_world.height) == (3, 1)
    assert restored_world.tile(2, 0).ground == SOIL
    assert restored_world.tile(2, 0).entity == "carrot"
    assert restored_world.tile(2, 0).age == 125.5
    assert restored_world.tile(2, 0).water == 0.75
    assert restored_inventory.as_dict() == {"hay": 75, "water": 3}
    assert restored_progression.unlocked == {"Loops", "Speed"}
    assert restored_progression.upgrade_levels == {"Speed": 1}
    assert (restored_drone.x, restored_drone.y) == (2, 0)
    assert restored_drone.water_time_seconds == 9.5
    assert restored_drone.speed_multiplier == 1.5
    assert restored_clock.tick_count == 4321


def test_invalid_save_is_rejected_before_mutating_game_state(tmp_path):
    path = tmp_path / "profile.json"
    save_game(path, *_create_state())
    state = json.loads(path.read_text(encoding="utf-8"))
    state["world"]["tiles"] = []
    path.write_text(json.dumps(state), encoding="utf-8")

    world = World(1, load_entities())
    inventory = Inventory({"hay": 7})
    progression = Progression(inventory, load_tech_tree())
    clock = Clock()
    drone = Drone(world, clock, inventory)

    with pytest.raises(ValueError, match="tiles"):
        load_game(path, world, inventory, progression, drone, clock)
    assert (world.width, world.height) == (1, 1)
    assert inventory.as_dict() == {"hay": 7}
    assert progression.unlocked == set()
    assert clock.tick_count == 0


def test_missing_profile_starts_new_account_progress(tmp_path):
    world = World(1, load_entities())
    inventory = Inventory()
    progression = Progression(inventory, load_tech_tree())
    clock = Clock()
    drone = Drone(world, clock, inventory)

    assert load_game(
        tmp_path / "not-created.json",
        world,
        inventory,
        progression,
        drone,
        clock,
    ) is None
