import json
from pathlib import Path

import pytest

from game.clock import Clock
from game.drone import Drone
from game.inventory import Inventory
from game.progression import Progression, load_tech_tree
from game.world import World
from game.entities import load_entities
from runtime.api import build_api, build_constants, build_statement_api
from runtime.interpreter import Interpreter, InterpreterError
from ui.app import FarmerApp


def test_loops_unlock_memerlukan_lima_hay_dan_membuka_while():
    inventory = Inventory({"hay": 4})
    progression = Progression(inventory, load_tech_tree())

    assert progression.status("Loops") == "available"
    assert not progression.is_affordable("Loops")
    assert not progression.can_unlock("Loops")
    inventory.add("hay")

    assert progression.can_unlock("Loops")
    assert progression.unlock("Loops")
    assert progression.status("Loops") == "unlocked"
    assert inventory.count("hay") == 0
    assert progression.features() == {"while"}
    assert progression.tutorial("Loops")["sources"][0]["page"] == "Unlocks"


def test_unlock_tidak_bisa_dibeli_kedua_kalinya():
    progression = Progression(Inventory({"hay": 10}), load_tech_tree())

    assert progression.unlock("Loops")
    assert not progression.can_unlock("Loops")
    assert not progression.unlock("Loops")
    assert progression.inventory.count("hay") == 5


def test_unlock_tanpa_data_sumber_ditandai_unknown():
    progression = Progression(
        Inventory(),
        {
            "Expand": {"prerequisites": [], "features": ["movement"]},
        },
    )

    assert progression.status("Expand") == "unknown"
    assert not progression.can_unlock("Expand")


def test_functions_unlock_requires_variables_and_exposes_function_feature():
    inventory = Inventory({"carrot": 40})
    progression = Progression(inventory, load_tech_tree())
    progression.unlocked.add("Variables")

    assert progression.current_cost("Functions") == {"carrot": 40}
    assert progression.can_unlock("Functions")
    assert progression.unlock("Functions")
    assert "functions" in progression.features()
    assert inventory.count("carrot") == 0


def test_katalog_memuat_35_unlock_resmi_dan_hanya_loops_yang_dapat_dibeli():
    expected = {
        "Auto_Unlock", "Cactus", "Carrots", "Costs", "Debug", "Debug_2",
        "Dictionaries", "Dinosaurs", "Expand", "Expand_2", "Fertilizer",
        "Functions", "Grass", "Hats", "Import", "Leaderboard", "Lists",
        "Loops", "Mazes", "Megafarm", "Operators", "Plant", "Polyculture",
        "Pumpkins", "Senses", "Simulation", "Speed", "Sunflowers",
        "The_Farmers_Remains", "Timing", "Top_Hat", "Trees", "Utilities",
        "Variables", "Watering",
    }
    progression = Progression(Inventory({"hay": 100000, "wood": 100000}))

    assert set(progression.tech_tree) == expected
    assert len(expected) == 35
    assert progression.can_unlock("Loops")
    assert all(
        progression.status(name) in {"unknown", "locked"}
        and not progression.can_unlock(name)
        for name in expected - {"Loops"}
    )


def test_biaya_awal_dan_tier_expand_mengikuti_wiki_dan_data_terverifikasi():
    tech_tree = load_tech_tree()
    expected_costs = {
        "Loops": {"hay": 5},
        "Expand": {"hay": 30},
        "Expand_2": {"wood": 20},
        "Grass": {"hay": 300},
        "Plant": {"hay": 50},
        "Variables": {"carrot": 35},
        "Operators": {"hay": 150, "wood": 10},
        "Carrots": {"wood": 50},
        "Auto_Unlock": {"pumpkin": 5000},
        "Cactus": {"pumpkin": 5000},
        "Costs": {"pumpkin": 2500},
        "Debug": {"hay": 50, "wood": 50},
        "Debug_2": {"gold": 500},
        "Dictionaries": {"pumpkin": 2500},
        "Dinosaurs": {"cactus": 2000},
        "Fertilizer": {"wood": 500},
        "Functions": {"carrot": 40},
        "Hats": {"hay": 50},
        "Import": {"carrot": 80},
        "Lists": {"carrot": 500},
        "Mazes": {"weird_substance": 1000},
        "Megafarm": {"gold": 2000},
        "Pumpkins": {"wood": 500, "carrot": 200},
        "Senses": {"hay": 100},
        "Simulation": {"gold": 5000},
        "Speed": {"hay": 20},
        "Sunflowers": {"carrot": 500},
        "The_Farmers_Remains": {"bone": 100000000},
        "Timing": {"pumpkin": 1000},
        "Top_Hat": {
            "hay": 1000000000,
            "wood": 10000000000,
            "carrot": 1000000000,
            "cactus": 1000000000,
            "gold": 100000000,
        },
        "Trees": {"wood": 50, "carrot": 70},
        "Utilities": {"pumpkin": 1000},
        "Watering": {"wood": 50},
    }

    actual_costs = {
        name: data["cost"]
        for name, data in tech_tree.items()
        if "cost" in data
    }
    actual_costs.update({
        name: data["levels"][0]["cost"]
        for name, data in tech_tree.items()
        if data.get("levels")
    })
    assert actual_costs == expected_costs
    assert len(expected_costs) == 33
    assert [
        level["cost"] for level in tech_tree["Expand_2"]["levels"]
    ] == [
        {"wood": 20},
        {"wood": 30, "carrot": 20},
        {"wood": 100, "carrot": 50},
        {"pumpkin": 1000},
        {"pumpkin": 8000},
        {"pumpkin": 64000},
        {"pumpkin": 512000},
        {"pumpkin": 4100000},
    ]
    assert tech_tree["Expand"]["cost_source"]["checked"] == "2026-10-20"
    data_path = Path(__file__).resolve().parents[1] / "data" / "techtree.json"
    with data_path.open(encoding="utf-8") as file:
        metadata = json.load(file)["_meta"]
    assert metadata["cost_snapshot"]["checked"] == "2026-10-20"
    assert [
        level["effects"]["width"] for level in tech_tree["Expand_2"]["levels"]
    ] == list(range(3, 11))


def test_speed_memiliki_lima_tier_wiki_dan_mengalikan_kecepatan_1_5x_per_tier():
    inventory = Inventory({"hay": 100, "wood": 100, "carrot": 5000})
    progression = Progression(inventory, load_tech_tree())
    expected_costs = [
        {"hay": 20},
        {"wood": 20},
        {"wood": 50, "carrot": 50},
        {"carrot": 500},
        {"carrot": 1000},
    ]
    expected_multipliers = [1.5, 2.25, 3.375, 5.0625, 7.59375]

    assert progression.unlock("Loops")
    assert progression.speed_multiplier() == 1
    for level, (cost, multiplier) in enumerate(
        zip(expected_costs, expected_multipliers),
        start=1,
    ):
        assert progression.current_cost("Speed") == cost
        assert progression.unlock("Speed")
        assert progression.upgrade_level("Speed") == level
        assert progression.speed_multiplier() == pytest.approx(multiplier)

    assert progression.status("Speed") == "unlocked"
    assert progression.current_cost("Speed") is None


def test_clear_didokumentasikan_wiki_tersedia_tanpa_unlock():
    inventory = Inventory({"hay": 10})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)
    costs = Clock().costs

    assert "clear" in build_api(drone, progression)
    assert costs["actions"]["clear"]["success"] == 200
    assert progression.upgrade_level("Loops") == 0


def test_timing_unlock_membuka_time_dan_tick_count_gratis():
    inventory = Inventory()
    progression = Progression(
        inventory,
        {
            "Timing": {
                "cost": {},
                "prerequisites": [],
                "features": ["timing"],
            },
        },
    )
    clock = Clock()
    drone = Drone(World(1, load_entities()), clock, inventory)

    assert "get_time" not in build_api(drone, progression)
    assert "get_tick_count" not in build_api(drone, progression)
    assert progression.unlock("Timing")
    assert {"get_time", "get_tick_count"}.issubset(build_api(drone, progression))

    clock.start_execution()
    clock.advance(17)
    tick_result = drone.perform("get_tick_count")
    time_result = drone.perform("get_time")

    assert tick_result.success and tick_result.value == 17 and tick_result.cost == 0
    assert time_result.success and time_result.value >= 0 and time_result.cost == 0
    assert clock.cost_of("get_time") == 0
    assert clock.cost_of("get_tick_count") == 0
    assert clock.tick_count == 17
    clock.reset()
    assert clock.get_execution_tick_count() == 0


def test_costs_unlock_membuka_get_cost_untuk_tier_entity_dan_unlock():
    inventory = Inventory({"hay": 30})
    progression = Progression(
        inventory,
        {
            "Costs": {
                "cost": {},
                "prerequisites": [],
                "features": ["costs"],
            },
            "Loops": {
                "levels": [
                    {"cost": {"hay": 5}},
                    {"cost": {"hay": 10}},
                ],
                "prerequisites": [],
                "features": ["while"],
            },
            "Plant": {
                "cost": {},
                "prerequisites": [],
                "features": ["planting"],
            },
        },
    )
    clock = Clock()
    world = World(1, load_entities())
    drone = Drone(world, clock, inventory)

    assert "get_cost" not in build_api(drone, progression)
    assert progression.unlock("Costs")
    assert progression.unlock("Loops")
    assert progression.unlock("Plant")
    api = build_api(drone, progression)
    constants = build_constants(progression)
    interpreter = Interpreter(
        api,
        build_statement_api(drone, progression),
        constants,
        progression.features(),
    )

    assert {"Items", "Unlocks", "Entities"}.issubset(constants)
    assert progression.get_cost("Loops", 0) == {"hay": 5}
    assert progression.get_cost("Loops") == {"hay": 10}
    steps = list(interpreter.run("get_cost(Unlocks.Loops, 0)"))
    assert steps[0].function == "get_cost"
    assert steps[0].result.value == {"hay": 5}
    assert steps[0].result.total_ticks == 1
    assert clock.tick_count == 1
    entity_steps = list(interpreter.run("get_cost(Entities.Bush)"))
    assert entity_steps[0].result.value == {}
    assert clock.tick_count == 2

    assert progression.unlock("Loops")
    assert progression.upgrade_level("Loops") == 2
    assert progression.get_cost("Loops") is None


def test_utilities_unlock_dan_tick_cost_nilai_wiki():
    inventory = Inventory()
    progression = Progression(
        inventory,
        {
            "Utilities": {
                "cost": {},
                "prerequisites": [],
                "features": ["utilities"],
            },
        },
    )
    clock = Clock()
    drone = Drone(World(1, load_entities()), clock, inventory)

    assert not {"min", "max", "abs", "random"} & build_api(drone, progression).keys()
    assert progression.unlock("Utilities")
    api = build_api(drone, progression)
    assert {"min", "max", "abs", "random"}.issubset(api)

    def finish(action):
        while True:
            try:
                next(action)
            except StopIteration as stopped:
                return stopped.value

    maximum = finish(api["max"](1, 7, 3))
    minimum = finish(api["min"]([4, 2, 9]))
    absolute = finish(api["abs"](-5))
    random_value = finish(api["random"]())

    assert (maximum.value, maximum.cost) == (7, 2)
    assert (minimum.value, minimum.cost) == (2, 2)
    assert (absolute.value, absolute.cost) == (5, 1)
    assert random_value.cost == 1
    assert 0 <= random_value.value < 1
    assert clock.tick_count == 6


def test_watering_memiliki_sembilan_tier_biaya_wiki_dan_menggandakan_supply():
    inventory = Inventory({"hay": 75, "wood": 5000000})
    progression = Progression(inventory, load_tech_tree())
    expected_costs = [
        {"wood": 50},
        {"wood": 200},
        {"wood": 800},
        {"wood": 3200},
        {"wood": 12800},
        {"wood": 51200},
        {"wood": 205000},
        {"wood": 819000},
        {"wood": 3280000},
    ]

    for unlock in ("Loops", "Speed", "Plant", "Carrots"):
        assert progression.unlock(unlock)
    assert progression.watering_tanks_per_10_seconds() == 0

    for level, cost in enumerate(expected_costs, start=1):
        assert progression.current_cost("Watering") == cost
        assert progression.unlock("Watering")
        assert progression.upgrade_level("Watering") == level
        assert progression.watering_tanks_per_10_seconds() == 2 ** (level - 1)

    assert progression.status("Watering") == "unlocked"
    assert progression.current_cost("Watering") is None


def test_water_api_dan_konstanta_hanya_terbuka_setelah_watering():
    inventory = Inventory({"hay": 75, "wood": 100})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)
    for unlock in ("Loops", "Speed", "Plant", "Carrots"):
        assert progression.unlock(unlock)

    assert "get_water" not in build_api(drone, progression)
    assert "use_item" not in build_api(drone, progression)
    assert "Items" not in build_constants(progression)

    assert progression.unlock("Watering")
    api = build_api(drone, progression)
    assert {"get_water", "use_item"}.issubset(api)
    assert build_constants(progression)["Items"]["Water"] == "water"

    inventory.add("water")
    interpreter = Interpreter(
        api,
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    steps = list(interpreter.run(
        "use_item(Items.Water)\nget_water()"
    ))
    assert any(step.function == "use_item" for step in steps)
    assert any(step.function == "get_water" for step in steps)
    assert drone.tile.water > 0


def test_speed_keeps_fractional_tick_budget_at_wiki_tick_rates():
    progression = Progression(Inventory({"hay": 25}), load_tech_tree())
    assert progression.unlock("Loops")
    app = FarmerApp.__new__(FarmerApp)
    app.progression = progression
    app.execution_tick_budget = 0.0

    assert [
        app._execution_steps_for_frame(0.004)
        for _ in range(5)
    ] == [1, 2, 1, 2, 2]
    assert progression.speed_multiplier() == 1

    assert progression.unlock("Speed")
    app.execution_tick_budget = 0.0
    assert [
        app._execution_steps_for_frame(0.004)
        for _ in range(5)
    ] == [2, 2, 3, 2, 3]


def test_world_tetap_tumbuh_saat_idle_mengikuti_kecepatan_progression():
    app = FarmerApp.__new__(FarmerApp)
    app.progression = Progression(Inventory(), load_tech_tree())
    app.clock = Clock()
    app.world = World(1, load_entities())
    app.drone = Drone(app.world, app.clock, app.progression.inventory)
    app.idle_tick_budget = 0.0
    app.MAX_EXECUTION_TICKS_PER_FRAME = 100

    assert app._advance_idle_elapsed(0.1) == 40
    assert app.clock.tick_count == 40
    assert app.world.tile(0, 0).age == 40

    app.progression.upgrade_levels["Speed"] = 1
    app.drone.speed_multiplier = app.progression.speed_multiplier()
    assert app._advance_idle_elapsed(0.1) == 60
    assert app.clock.tick_count == 100
    assert app.world.tile(0, 0).age == 100


def test_idle_keeps_fractional_ticks_and_caps_without_dropping_backlog():
    app = FarmerApp.__new__(FarmerApp)
    app.progression = Progression(Inventory(), load_tech_tree())
    app.clock = Clock()
    app.world = World(1, load_entities())
    app.drone = Drone(app.world, app.clock, app.progression.inventory)
    app.idle_tick_budget = 0.0
    app.MAX_EXECUTION_TICKS_PER_FRAME = 100

    assert app._advance_idle_elapsed(0.001) == 0
    assert app._advance_idle_elapsed(0.0015) == 1
    assert app.idle_tick_budget == pytest.approx(0)
    assert app._advance_idle_elapsed(1) == 100
    assert app.idle_tick_budget == pytest.approx(300)


def test_plant_progress_has_visible_scale_and_percentage_indicator():
    class CanvasRecorder:
        def __init__(self):
            self.calls = []

        def create_polygon(self, *args, **kwargs):
            self.calls.append(("polygon", args, kwargs))

        def create_line(self, *args, **kwargs):
            self.calls.append(("line", args, kwargs))

        def create_oval(self, *args, **kwargs):
            self.calls.append(("oval", args, kwargs))

        def create_rectangle(self, *args, **kwargs):
            self.calls.append(("rectangle", args, kwargs))

        def create_text(self, *args, **kwargs):
            self.calls.append(("text", args, kwargs))

    app = FarmerApp.__new__(FarmerApp)
    app.canvas = CanvasRecorder()

    app._draw_entity(100, 100, "carrot", scale=0.55, growth_progress=0.0)

    polygon = next(call for call in app.canvas.calls if call[0] == "polygon")
    assert polygon[1][0] == pytest.approx(95.6)
    progress_label = next(
        call for call in app.canvas.calls
        if call[0] == "text" and call[2].get("text") == "0%"
    )
    assert progress_label[1] == (100, 66)
    fill_bar = [
        call for call in app.canvas.calls
        if call[0] == "rectangle" and call[2].get("fill") == "#b7d879"
    ]
    assert fill_bar[0][1][2] == fill_bar[0][1][0]


def test_carrot_on_drone_tile_shows_growth_and_ready_status():
    class CanvasRecorder:
        def __init__(self):
            self.calls = []

        def winfo_width(self):
            return 600

        def winfo_height(self):
            return 500

        def delete(self, *_args):
            self.calls.clear()

        def __getattr__(self, name):
            if name.startswith("create_"):
                return lambda *args, **kwargs: self.calls.append(
                    (name, args, kwargs)
                )
            raise AttributeError(name)

    app = FarmerApp.__new__(FarmerApp)
    app.canvas = CanvasRecorder()
    app.COLORS = {
        "soil": "#71533a",
        "soil_dark": "#493c2e",
        "grass": "#4c7245",
        "grass_alt": "#567c4b",
        "green_dark": "#304d36",
        "orange": "#d98243",
    }
    app.world = World(1, load_entities())
    app.drone = Drone(app.world, Clock(), Inventory())
    app.harvest_animation = None
    tile = app.drone.tile
    tile.ground = "soil"
    tile.entity = "carrot"
    tile.age = app.world.defs["carrot"].grow_ticks // 2

    assert app._current_crop_status() == ("CARROT  GROWING  50%", False)
    app._render_world()
    status_draw = next(
        call for call in app.canvas.calls
        if call[0] == "create_text"
        and call[2].get("text") == "CARROT  GROWING  50%"
    )
    carrot_draw = max(
        index for index, call in enumerate(app.canvas.calls)
        if call[0] == "create_polygon"
        and call[2].get("fill") == "#ff8a24"
    )
    drone_draw = next(
        index for index, call in enumerate(app.canvas.calls)
        if call[0] == "create_polygon"
        and call[2].get("fill") == app.COLORS["orange"]
    )
    assert status_draw[1][:2] == (26, 62)
    assert carrot_draw < drone_draw
    carrot_polygon = app.canvas.calls[carrot_draw]
    assert sum(carrot_polygon[1][0::2]) / 3 == pytest.approx(300)
    assert carrot_polygon[2]["outline"] == "#ffe074"

    tile.age = app.world.defs["carrot"].grow_ticks
    assert app._current_crop_status() == ("CARROT  READY TO HARVEST", True)


def test_empty_tilled_tile_shows_ready_to_plant_status():
    app = FarmerApp.__new__(FarmerApp)
    app.world = World(1, load_entities())
    app.drone = Drone(app.world, Clock(), Inventory())
    app.drone.tile.ground = "soil"
    app.drone.tile.entity = None

    assert app._current_crop_status() == ("SOIL  READY TO PLANT", False)


def test_developer_can_grant_inventory_items():
    app = FarmerApp.__new__(FarmerApp)
    app.account_tag = "developer"
    app.inventory = Inventory({"hay": 3})
    app.inventory_labels = {}
    app._save_progress = lambda: None
    app._update_hud = lambda: None

    app._grant_developer_item("gold", 25)

    assert app.inventory.as_dict() == {"hay": 3, "gold": 25}


@pytest.mark.parametrize(
    ("item", "amount", "message"),
    [
        ("unknown", 5, "Item tidak tersedia"),
        ("gold", 0, "bilangan bulat positif"),
        ("gold", -1, "bilangan bulat positif"),
        ("gold", True, "bilangan bulat positif"),
    ],
)
def test_developer_grant_rejects_invalid_input(item, amount, message):
    app = FarmerApp.__new__(FarmerApp)
    app.account_tag = "developer"
    app.inventory = Inventory({"gold": 2})
    app._save_progress = lambda: None
    app._update_hud = lambda: None

    with pytest.raises(ValueError, match=message):
        app._grant_developer_item(item, amount)
    assert app.inventory.count("gold") == 2


def test_player_cannot_grant_items():
    app = FarmerApp.__new__(FarmerApp)
    app.account_tag = "player"
    app.inventory = Inventory()

    with pytest.raises(PermissionError, match="developer"):
        app._grant_developer_item("gold", 25)
    assert app.inventory.count("gold") == 0


def test_failed_developer_grant_save_rolls_back_inventory():
    app = FarmerApp.__new__(FarmerApp)
    app.account_tag = "developer"
    app.inventory = Inventory({"gold": 2})
    app._save_progress = lambda: (_ for _ in ()).throw(OSError("save failed"))
    app._update_hud = lambda: None

    with pytest.raises(OSError, match="save failed"):
        app._grant_developer_item("gold", 25)
    assert app.inventory.count("gold") == 2


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0, "0"),
        (999, "999"),
        (1_000, "1.0K"),
        (9_999, "9.9K"),
        (10_000, "10K"),
        (1_250_000, "1.2M"),
        (23_000_000, "23M"),
        (7_500_000_000, "7.5B"),
        (10**30, "1000000000000000000T"),
    ],
)
def test_resource_hud_compacts_large_counts_without_changing_inventory(
    amount,
    expected,
):
    assert FarmerApp._format_resource_count(amount) == expected


def test_editor_auto_indent_and_auto_pairs_brackets():
    class TextRecorder:
        def __init__(self, value=""):
            self.value = value
            self.cursor = len(value)

        def index(self, index):
            if index == "insert linestart":
                return self.value.rfind("\n", 0, self.cursor) + 1
            return self.cursor

        def get(self, start, end):
            if start == "insert":
                start = self.cursor
            if end == "insert":
                end = self.cursor
            if end == "insert + 1 chars":
                end = self.cursor + 1
            if isinstance(start, str):
                start = int(start)
            if isinstance(end, str):
                end = int(end)
            return self.value[start:end]

        def insert(self, index, text):
            position = self.cursor if index == "insert" else int(index)
            self.value = self.value[:position] + text + self.value[position:]
            self.cursor = position + len(text)

        def delete(self, start, end):
            start, end = int(start), int(end)
            self.value = self.value[:start] + self.value[end:]
            self.cursor = start

        def mark_set(self, mark, index):
            if index == "insert - 1 chars":
                self.cursor -= 1
            elif index == "insert + 1 chars":
                self.cursor += 1
            elif index.startswith("insert - "):
                self.cursor -= int(index.split()[2])

        def tag_ranges(self, _tag):
            return ()

    app = FarmerApp.__new__(FarmerApp)
    app.code_text = TextRecorder("if True:")
    app._update_code_decoration = lambda: None

    assert app._auto_indent_code() == "break"
    assert app.code_text.value == "if True:\n    "
    assert app.code_text.cursor == len(app.code_text.value)

    assert app._handle_code_keypress(type("Key", (), {"char": "("})()) == "break"
    assert app.code_text.value.endswith("()")
    assert app.code_text.cursor == len(app.code_text.value) - 1
    assert app._handle_code_keypress(type("Key", (), {"char": ")"})()) == "break"
    assert app.code_text.cursor == len(app.code_text.value)


def test_execution_tick_batch_is_capped_without_dropping_elapsed_ticks():
    app = FarmerApp.__new__(FarmerApp)
    app.progression = Progression(Inventory(), load_tech_tree())
    app.execution_tick_budget = 0.0

    assert app._execution_steps_for_frame(1.0) == 100
    assert app.execution_tick_budget == pytest.approx(300)
    assert app._execution_steps_for_frame(0.0) == 100
    assert app.execution_tick_budget == pytest.approx(200)


def test_tier_grass_hanya_membuka_efek_yield_yang_terverifikasi():
    inventory = Inventory({"hay": 305})
    progression = Progression(inventory, load_tech_tree())

    assert progression.unlock("Loops")
    assert progression.current_cost("Grass") == {"hay": 300}
    assert progression.unlock("Grass")
    assert progression.upgrade_level("Grass") == 1
    assert progression.grass_yield_multiplier() == 2
    assert progression.current_cost("Grass") == {"wood": 500}
    assert not progression.is_affordable("Grass")

    inventory.add("wood", 500)
    assert progression.unlock("Grass")
    assert progression.upgrade_level("Grass") == 2
    assert progression.grass_yield_multiplier() == 4
    assert progression.status("Grass") == "unlocked"
    assert progression.current_cost("Grass") is None
    assert not progression.can_unlock("Grass")
    assert inventory.count("hay") == 0
    assert inventory.count("wood") == 0


def test_expand_chain_uses_wiki_cost_levels_and_exposes_square_grid_tools():
    inventory = Inventory({"hay": 55, "wood": 20})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)

    for unlock in ("Loops", "Speed", "Expand"):
        assert progression.unlock(unlock)
    assert progression.current_level_effects("Expand") == {
        "width": 3,
        "height": 1,
    }
    assert progression.current_cost("Expand_2") == {"wood": 20}
    assert progression.unlock("Expand_2")
    assert progression.features() >= {"for_loop", "world_size"}
    assert progression.current_level_effects("Expand_2") == {
        "width": 3,
        "height": 3,
    }

    world.expand_and_clear(3, 3)
    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    steps = list(interpreter.run(
        "for i in range(get_world_size()):\n    move(North)"
    ))

    assert [step.function for step in steps[:3]] == [
        "get_world_size",
        "range",
        "for",
    ]
    assert sum(step.function == "move" for step in steps) == 600
    assert (drone.x, drone.y) == (0, 0)
    assert drone.clock.tick_count == 603


def test_senses_unlock_exposes_wiki_sensors_items_and_unlock_counts():
    inventory = Inventory({"hay": 1000, "wood": 10})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)

    for unlock in ("Loops", "Speed", "Plant", "Operators", "Senses"):
        assert progression.unlock(unlock)

    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    assert set(
        ("get_pos_x", "get_pos_y", "get_entity_type", "get_ground_type",
         "num_items", "num_unlocked", "can_move")
    ).issubset(build_api(drone, progression))
    assert build_constants(progression)["Items"]["Hay"] == "hay"
    assert build_constants(progression)["Unlocks"]["Speed"] == "Speed"

    steps = list(interpreter.run(
        "if num_items(Items.Hay) != 0:\n    harvest()"
    ))
    assert steps[0].function == "num_items"
    assert steps[0].result.value == 675
    assert steps[1].function == "!="
    assert steps[2].function == "if"

    count_step = list(interpreter.run("num_unlocked(Unlocks.Speed)"))[-1]
    assert count_step.result.value == 1
    assert drone.perform("get_pos_x").value == 0
    assert drone.perform("can_move", "east").value is True


def test_visual_parent_edges_mengikuti_screenshot_tanpa_mengubah_data_prerequisite():
    tech_tree = load_tech_tree()
    actual_edges = {
        (parent, child)
        for child, data in tech_tree.items()
        for parent in data.get("visual_parents", ())
    }
    expected_edges = {
        ("Loops", "Speed"),
        ("Loops", "Grass"),
        ("Speed", "Expand"),
        ("Speed", "Plant"),
        ("Expand", "Expand_2"),
        ("Plant", "Carrots"),
        ("Plant", "Debug"),
        ("Plant", "Operators"),
        ("Carrots", "Trees"),
        ("Carrots", "Watering"),
        ("Watering", "Fertilizer"),
        ("Watering", "Sunflowers"),
        ("Trees", "Pumpkins"),
        ("Pumpkins", "Cactus"),
        ("Pumpkins", "Dinosaurs"),
        ("Pumpkins", "Mazes"),
        ("Mazes", "Polyculture"),
        ("Debug", "Debug_2"),
        ("Debug", "Timing"),
        ("Timing", "Simulation"),
        ("Simulation", "Leaderboard"),
        ("Operators", "Senses"),
        ("Operators", "Variables"),
        ("Variables", "Lists"),
        ("Variables", "Functions"),
        ("Lists", "Dictionaries"),
        ("Dictionaries", "Costs"),
        ("Functions", "Import"),
        ("Functions", "Utilities"),
        ("Functions", "Megafarm"),
        ("Costs", "Auto_Unlock"),
        ("Megafarm", "The_Farmers_Remains"),
        ("Hats", "Top_Hat"),
    }

    assert actual_edges == expected_edges
    assert all(
        data["prerequisites"] == data["visual_parents"]
        for data in tech_tree.values()
        if "prerequisites" in data and data.get("visual_parents")
    )


def test_prerequisite_mapping_matches_user_table_and_unlisted_nodes_stay_unverified():
    tech_tree = load_tech_tree()
    expected = {
        "Loops": [],
        "Speed": ["Loops"],
        "Grass": ["Loops"],
        "Expand": ["Speed"],
        "Expand_2": ["Expand"],
        "Plant": ["Speed"],
        "Carrots": ["Plant"],
        "Debug": ["Plant"],
        "Operators": ["Plant"],
        "Watering": ["Carrots"],
        "Trees": ["Carrots"],
        "Fertilizer": ["Watering"],
        "Sunflowers": ["Watering"],
        "Pumpkins": ["Trees"],
        "Cactus": ["Pumpkins"],
        "Dinosaurs": ["Pumpkins"],
        "Mazes": ["Pumpkins"],
        "Polyculture": ["Mazes"],
        "Debug_2": ["Debug"],
        "Timing": ["Debug"],
        "Simulation": ["Timing"],
        "Leaderboard": ["Simulation"],
        "Senses": ["Operators"],
        "Variables": ["Operators"],
        "Lists": ["Variables"],
        "Functions": ["Variables"],
        "Dictionaries": ["Lists"],
        "Costs": ["Dictionaries"],
        "Auto_Unlock": ["Costs"],
        "Import": ["Functions"],
        "Utilities": ["Functions"],
    }

    assert {
        name: data["prerequisites"]
        for name, data in tech_tree.items()
        if "prerequisites" in data
    } == expected
    data_path = Path(__file__).resolve().parents[1] / "data" / "techtree.json"
    with data_path.open(encoding="utf-8") as file:
        metadata = json.load(file)["_meta"]
    assert metadata["prerequisite_source"].startswith("User-provided")
    assert all(
        "prerequisites" not in tech_tree[name]
        for name in {"Megafarm", "Hats", "Top_Hat", "The_Farmers_Remains"}
    )


def test_prerequisite_blocks_unlock_until_parent_is_unlocked():
    progression = Progression(
        Inventory({"hay": 10}),
        {
            "Loops": {
                "cost": {"hay": 5},
                "prerequisites": [],
                "features": ["while"],
            },
            "Speed": {
                "cost": {"hay": 5},
                "prerequisites": ["Loops"],
                "features": [],
            },
        },
    )

    assert progression.status("Speed") == "locked"
    assert not progression.can_unlock("Speed")
    assert progression.unlock("Loops")
    assert progression.status("Speed") == "available"
    assert progression.unlock("Speed")


def test_while_hanya_tersedia_setelah_loops_dan_movement_tetap_terkunci():
    inventory = Inventory({"hay": 5})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)

    def make_interpreter():
        return Interpreter(
            build_api(drone, progression),
            build_statement_api(drone, progression),
            build_constants(),
        )

    with pytest.raises(InterpreterError, match="while belum di-unlock"):
        list(make_interpreter().run("while False:\n    harvest()"))

    assert progression.unlock("Loops")
    steps = list(make_interpreter().run("while False:\n    harvest()"))
    assert [step.function for step in steps] == ["while"]

    with pytest.raises(InterpreterError, match="fungsi tidak tersedia"):
        list(make_interpreter().run('move("east")'))
    assert (drone.x, drone.y) == (0, 0)


def test_speed_expand_plant_unlock_controls_features_and_wiki_constants():
    inventory = Inventory({"hay": 200})
    progression = Progression(inventory, load_tech_tree())
    world = World(3, load_entities())
    drone = Drone(world, Clock(), inventory)

    def make_interpreter():
        return Interpreter(
            build_api(drone, progression),
            build_statement_api(drone, progression),
            build_constants(progression),
            progression.features(),
        )

    assert progression.unlock("Loops")
    assert progression.unlock("Speed")
    assert "speed" in progression.features()
    assert progression.unlock("Expand")
    assert "movement" in progression.features()
    assert "farm_1x3" in progression.features()
    assert "North" in build_constants(progression)
    assert "move" in build_api(drone, progression)
    list(make_interpreter().run("move(North)"))
    assert (drone.x, drone.y) == (0, 1)

    assert progression.unlock("Plant")
    assert "plant" in build_api(drone, progression)
    assert "till" not in build_api(drone, progression)
    assert build_constants(progression)["Entities"]["Bush"] == "bush"
    assert "Carrot" not in build_constants(progression)["Entities"]
    list(make_interpreter().run("plant(Entities.Bush)"))
    assert drone.tile.entity == "bush"
    with pytest.raises(ValueError, match="belum di-unlock.*carrot"):
        list(make_interpreter().run('plant("carrot")'))


def test_carrots_unlock_till_and_carrot_planting():
    inventory = Inventory({"hay": 1000, "wood": 1000})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)

    for unlock in ("Loops", "Speed", "Plant", "Carrots"):
        assert progression.unlock(unlock)

    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    assert "till" in build_api(drone, progression)
    assert build_constants(progression)["Entities"]["Carrot"] == "carrot"
    list(interpreter.run("till()\nplant(Entities.Carrot)"))
    assert drone.tile.ground == "soil"
    assert drone.tile.entity == "carrot"


def test_variables_and_operators_are_gated_by_their_unlocks():
    inventory = Inventory({"hay": 1000, "wood": 100, "carrot": 100})
    progression = Progression(inventory, load_tech_tree())
    world = World(1, load_entities())
    drone = Drone(world, Clock(), inventory)

    def make_interpreter():
        return Interpreter(
            build_api(drone, progression),
            build_statement_api(drone, progression),
            build_constants(progression),
            progression.features(),
        )

    with pytest.raises(InterpreterError, match="Variables belum di-unlock"):
        list(make_interpreter().run("value = 1"))

    for unlock in ("Loops", "Speed", "Plant"):
        assert progression.unlock(unlock)
    with pytest.raises(InterpreterError, match="Operator.*belum di-unlock"):
        list(make_interpreter().run("while 1 != 1:\n    harvest()"))
    with pytest.raises(InterpreterError, match="Operator.*belum di-unlock"):
        list(make_interpreter().run("if 1 + 2 == 3:\n    harvest()"))
    assert progression.unlock("Operators")
    with pytest.raises(InterpreterError, match="Variables belum di-unlock"):
        list(make_interpreter().run("value = 1"))
    drone.tile.age = world.defs["grass"].grow_ticks
    assert [step.function for step in make_interpreter().run(
        "if 1 + 2 == 3:\n    harvest()"
    )] == ["+", "==", "if", *("harvest" for _ in range(200))]

    assert progression.unlock("Variables")
    assert list(make_interpreter().run("value = 1")) == []
    steps = list(make_interpreter().run("while 1 != 1:\n    harvest()"))
    assert [step.function for step in steps] == ["while", "!="]