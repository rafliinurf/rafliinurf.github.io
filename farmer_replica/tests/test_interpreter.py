import pytest

from game.clock import Clock
from game.drone import Drone
from game.entities import load_entities
from game.inventory import Inventory
from game.progression import Progression, load_tech_tree
from game.world import SOIL, World
from runtime.api import build_api, build_constants, build_statement_api
from runtime.interpreter import Interpreter, InterpreterError


@pytest.fixture
def setup_interpreter():
    world = World(4, load_entities())
    clock = Clock()
    drone = Drone(world, clock, Inventory())
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
    )
    return drone, clock, interpreter


@pytest.fixture
def setup_list_interpreter():
    inventory = Inventory()
    progression = Progression(inventory, load_tech_tree())
    progression.unlocked.update({"Variables", "Lists", "Operators", "Expand_2"})
    world = World(4, load_entities())
    clock = Clock()
    drone = Drone(world, clock, inventory)
    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    return drone, clock, interpreter


@pytest.fixture
def setup_dictionary_interpreter():
    inventory = Inventory()
    progression = Progression(inventory, load_tech_tree())
    progression.unlocked.update({
        "Variables",
        "Lists",
        "Dictionaries",
        "Operators",
        "Expand_2",
    })
    world = World(4, load_entities())
    clock = Clock()
    drone = Drone(world, clock, inventory)
    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    return drone, clock, interpreter


@pytest.fixture
def setup_function_interpreter():
    inventory = Inventory()
    progression = Progression(inventory, load_tech_tree())
    progression.unlocked.update({
        "Variables",
        "Operators",
        "Functions",
        "Expand_2",
    })
    world = World(4, load_entities())
    clock = Clock()
    drone = Drone(world, clock, inventory)
    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )
    return drone, clock, interpreter


def test_lists_construct_index_len_and_gate_execution(setup_list_interpreter):
    drone, clock, interpreter = setup_list_interpreter

    steps = list(interpreter.run(
        "values = [1, 2]\n"
        "if len(values) == 2:\n"
        "    if values[1] == 2:\n"
        "        harvest()"
    ))

    functions = [step.function for step in steps]
    assert functions.count("list_literal") == 2
    assert functions.count("len") == 1
    assert functions.count("list_index") == 1
    assert "harvest" in functions
    assert clock.tick_count == 208
    assert drone.log[-1][1] == "harvest"


def test_lists_can_be_iterated_with_for(setup_list_interpreter):
    drone, clock, interpreter = setup_list_interpreter

    steps = list(interpreter.run(
        "for value in [1, 2, 3]:\n"
        "    harvest()"
    ))

    assert [step.function for step in steps].count("list_literal") == 3
    assert [entry[1] for entry in drone.log] == ["harvest"] * 3
    assert clock.tick_count == 604


def test_empty_list_and_len_each_use_documented_tick_cost(setup_list_interpreter):
    _, clock, interpreter = setup_list_interpreter

    steps = list(interpreter.run("values = []\nlength = len(values)"))

    assert [step.function for step in steps] == ["list_literal", "len"]
    assert clock.tick_count == 2


def test_list_insert_and_remove_apply_wiki_tick_costs(setup_list_interpreter):
    drone, clock, interpreter = setup_list_interpreter

    steps = list(interpreter.run(
        "items = [1, 2, 3]\n"
        "items.insert(1, 9)\n"
        "items.remove(2)\n"
        "if len(items) == 3:\n"
        "    harvest()"
    ))

    functions = [step.function for step in steps]
    assert functions.count("list_insert") == 3
    assert functions.count("list_remove") == 4
    assert functions.count("len") == 1
    assert drone.log[-1][1] == "harvest"
    assert clock.tick_count == 213


def test_list_insert_rejects_invalid_index_without_mutation(setup_list_interpreter):
    _, clock, interpreter = setup_list_interpreter

    with pytest.raises(InterpreterError, match="indeks integer"):
        list(interpreter.run("items = [1, 2]\nitems.insert(4, 3)"))
    assert clock.tick_count == 2


def test_list_remove_reports_missing_item(setup_list_interpreter):
    _, clock, interpreter = setup_list_interpreter

    with pytest.raises(InterpreterError, match="tidak menemukan"):
        list(interpreter.run("items = [1, 2]\nitems.remove(3)"))
    assert clock.tick_count == 2


def test_list_mutation_methods_are_gated_by_lists_unlock(setup_interpreter):
    drone, clock, _ = setup_interpreter
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"variables"},
    )

    with pytest.raises(InterpreterError, match="Lists belum di-unlock"):
        list(interpreter.run("items = [1]\nitems.insert(0, 2)"))
    assert clock.tick_count == 0


def test_dictionary_literal_lookup_membership_and_key_iteration(
    setup_dictionary_interpreter,
):
    drone, clock, interpreter = setup_dictionary_interpreter

    steps = list(interpreter.run(
        'values = {1: "one", "sixteen_char_key": 2}\n'
        "count = len(values)\n"
        "if 1 in values:\n"
        '    if values["sixteen_char_key"] == 2:\n'
        "        harvest()\n"
        "for key in values:\n"
        "    harvest()"
    ))

    functions = [step.function for step in steps]
    assert functions.count("dictionary_literal") == 3
    assert functions.count("dictionary_lookup") == 2
    assert functions.count("dictionary_membership") == 1
    assert functions.count("len") == 1
    assert [entry[1] for entry in drone.log] == ["harvest"] * 3
    assert clock.tick_count == 611


def test_empty_dictionary_has_one_tick_and_missing_key_is_reported(
    setup_dictionary_interpreter,
):
    _, clock, interpreter = setup_dictionary_interpreter

    with pytest.raises(InterpreterError, match="key tidak ditemukan"):
        list(interpreter.run('values = {}\nvalue = values["missing"]'))
    assert clock.tick_count == 1


def test_string_dictionary_membership_is_not_enabled_without_documented_cost(
    setup_dictionary_interpreter,
):
    _, clock, interpreter = setup_dictionary_interpreter

    with pytest.raises(InterpreterError, match="membership lookup gagal"):
        list(interpreter.run(
            'values = {"name": 1}\n'
            'if "name" in values:\n'
            "    harvest()"
        ))
    assert clock.tick_count == 2


def test_set_conversion_membership_and_iteration(setup_dictionary_interpreter):
    drone, clock, interpreter = setup_dictionary_interpreter

    steps = list(interpreter.run(
        "values = [1, 2, 2]\n"
        "unique = set(values)\n"
        "count = len(unique)\n"
        "if 2 in unique:\n"
        "    for item in unique:\n"
        "        harvest()"
    ))

    assert [step.function for step in steps].count("dictionary_lookup") == 1
    assert [step.function for step in steps].count("len") == 1
    assert [entry[1] for entry in drone.log] == ["harvest", "harvest"]
    assert clock.tick_count == 411


def test_dictionary_and_set_usage_require_unlock(setup_list_interpreter):
    _, clock, interpreter = setup_list_interpreter

    with pytest.raises(InterpreterError, match="Dictionaries belum di-unlock"):
        list(interpreter.run("values = {1: 2}"))
    assert clock.tick_count == 0


def test_set_rejects_unhashable_values_without_hidden_fallback(
    setup_dictionary_interpreter,
):
    _, clock, interpreter = setup_dictionary_interpreter

    with pytest.raises(TypeError, match="elements must be hashable"):
        list(interpreter.run("values = set([[1]])"))
    assert clock.tick_count == 2


def test_list_literal_requires_lists_unlock(setup_interpreter):
    drone, clock, _ = setup_interpreter
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"variables"},
    )

    with pytest.raises(InterpreterError, match="Lists belum di-unlock"):
        list(interpreter.run("values = [1, 2]"))
    assert clock.tick_count == 0


def test_list_out_of_range_index_raises_interpreter_error(setup_list_interpreter):
    _, clock, interpreter = setup_list_interpreter

    with pytest.raises(InterpreterError, match="indeks list di luar jangkauan"):
        list(interpreter.run("values = [1]\nvalue = values[2]"))
    assert clock.tick_count == 1


def test_move_dijalankan_saat_generator_dilanjutkan(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    steps = interpreter.run('move("east")')

    step = next(steps)

    assert (drone.x, drone.y) == (1, 0)
    assert clock.tick_count == 1
    assert (step.line, step.function, step.args) == (1, "move", ("east",))
    assert step.result.success
    assert (step.result.completed_ticks, step.result.total_ticks) == (1, 200)


def test_satu_aksi_yield_200_tick_dan_memajukan_dunia(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.tile.age = 0

    steps = list(interpreter.run('move("east")'))

    assert len(steps) == 200
    assert [step.result.tick_count for step in steps] == list(range(1, 201))
    assert clock.tick_count == 200
    assert drone.world.tile(0, 0).age == 200


def test_range_tick_memakai_konfigurasi_speed_dan_water_supply():
    world = World(1, load_entities())
    clock = Clock()
    inventory = Inventory()
    drone = Drone(world, clock, inventory)
    drone.speed_multiplier = 2
    drone.watering_tanks_per_10_seconds = 1
    world.tile(0, 0).water = 1
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
    )

    steps = list(interpreter.run("range(1)"))

    assert len(steps) == 1
    assert clock.tick_count == 1
    assert world.tile(0, 0).age == pytest.approx(5)
    assert world.tile(0, 0).water == pytest.approx(0.99 ** (1 / 800))
    assert inventory.count("water") == 0


def test_can_harvest_mengembalikan_nilai_dan_menghabiskan_satu_tick(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    first_step = next(interpreter.run("can_harvest()"))

    assert first_step.result.value is False
    assert clock.tick_count == 1

    drone.world.advance(drone.world.defs["grass"].grow_ticks)
    second_step = next(interpreter.run("can_harvest()"))

    assert second_step.result.value is True
    assert clock.tick_count == 2


def test_if_menjalankan_cabang_saat_sensor_true(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.world.advance(drone.world.defs["grass"].grow_ticks)

    steps = list(interpreter.run('if can_harvest():\n    move("east")'))

    assert steps[0].function == "can_harvest"
    assert steps[-1].function == "move"
    assert (drone.x, drone.y) == (1, 0)
    assert clock.tick_count == 202


def test_if_melewati_cabang_saat_sensor_false(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run('if can_harvest():\n    move("east")'))

    assert [step.function for step in steps] == ["can_harvest", "if"]
    assert (drone.x, drone.y) == (0, 0)
    assert clock.tick_count == 2


def test_else_dijalankan_saat_sensor_false(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(
        interpreter.run('if can_harvest():\n    move("east")\nelse:\n    move("north")')
    )

    assert steps[0].function == "can_harvest"
    assert steps[1].function == "if"
    assert steps[2].function == "move"
    assert (drone.x, drone.y) == (0, 1)
    assert clock.tick_count == 202


def test_if_can_harvest_memanenkan_grass_matang(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.tile.age = drone.world.defs["grass"].grow_ticks

    steps = list(interpreter.run("if can_harvest():\n    harvest()"))

    assert [step.function for step in steps] == [
        "can_harvest",
        "if",
        *(["harvest"] * 200),
    ]
    assert steps[-1].result.success and steps[-1].result.value is True
    assert drone.inventory.count("hay") == 1
    assert clock.tick_count == 202


def test_if_can_harvest_melewati_panen_grass_yang_belum_matang(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run("if can_harvest():\n    harvest()"))

    assert [step.function for step in steps] == ["can_harvest", "if"]
    assert drone.inventory.count("hay") == 0
    assert clock.tick_count == 2


def test_assignment_sensor_dipakai_if_lalu_harvest(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.tile.age = drone.world.defs["grass"].grow_ticks

    steps = list(interpreter.run("ready = can_harvest()\nif ready:\n    harvest()"))

    assert [step.function for step in steps[:2]] == ["can_harvest", "if"]
    assert [step.function for step in steps[2:]] == ["harvest"] * 200
    assert drone.inventory.count("hay") == 1
    assert clock.tick_count == 202


def test_assignment_false_melewati_cabang_if(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run("ready = can_harvest()\nif ready:\n    harvest()"))

    assert [step.function for step in steps] == ["can_harvest", "if"]
    assert drone.inventory.count("hay") == 0
    assert clock.tick_count == 2


def test_variable_belum_didefinisikan_ditolak_sebelum_aksi(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    with pytest.raises(InterpreterError):
        list(interpreter.run('move("east")\nif ready:\n    harvest()'))

    assert (drone.x, drone.y) == (0, 0)
    assert clock.tick_count == 0


def test_for_range_mengulang_body_dan_menghitung_biaya_loop(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run('for index in range(3):\n    move("east")'))

    assert len(steps) == 602
    assert [step.function for step in steps[:2]] == ["range", "for"]
    assert sum(step.function == "move" for step in steps) == 600
    assert (drone.x, drone.y) == (3, 0)
    assert clock.tick_count == 602


def test_for_range_kosong_tidak_menjalankan_body(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run('for index in range(0):\n    move("east")'))

    assert [step.function for step in steps] == ["range", "for"]
    assert (drone.x, drone.y) == (0, 0)
    assert clock.tick_count == 2


def test_for_hanya_menerima_range_literal(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    with pytest.raises(InterpreterError):
        list(interpreter.run('move("east")\nfor index in range(1 + 1):\n    move("east")'))

    assert (drone.x, drone.y) == (0, 0)
    assert clock.tick_count == 0


def test_till_lalu_plant_carrot_menghabiskan_biaya_dan_item(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.inventory.add("hay", 512)
    drone.inventory.add("wood", 512)

    steps = list(interpreter.run('till()\nplant("carrot")'))

    assert len(steps) == 400
    assert steps[0].function == "till"
    assert steps[-1].function == "plant"
    assert steps[-1].result.success and steps[-1].result.value is True
    assert drone.tile.ground == "soil"
    assert drone.tile.entity == "carrot"
    assert drone.inventory.count("hay") == 0
    assert drone.inventory.count("wood") == 0
    assert clock.tick_count == 400


def test_plant_gagal_tanpa_item_menghabiskan_satu_tick(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run('till()\nplant("carrot")'))

    assert len(steps) == 201
    assert steps[-1].function == "plant"
    assert not steps[-1].result.success and steps[-1].result.value is False
    assert drone.tile.entity is None
    assert clock.tick_count == 201


def test_script_wiki_till_dan_plant_carrot(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.inventory.add("hay", 512)
    drone.inventory.add("wood", 512)

    steps = list(
        interpreter.run(
            'if get_ground_type() != Grounds.Soil:\n'
            '    till()\n'
            'plant("carrot")'
        )
    )

    assert steps[0].function == "get_ground_type"
    assert steps[1].function == "!="
    assert steps[2].function == "if"
    assert steps[3].function == "till"
    assert steps[-1].function == "plant"
    assert drone.tile.ground == SOIL
    assert drone.tile.entity == "carrot"
    assert clock.tick_count == 403


def test_script_wiki_tidak_mengubah_soil_yang_sudah_siaps(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    drone.tile.ground = SOIL
    drone.tile.entity = None

    steps = list(
        interpreter.run(
            'if get_ground_type() != Grounds.Soil:\n'
            '    till()'
        )
    )

    assert [step.function for step in steps] == ["get_ground_type", "!=", "if"]
    assert drone.tile.ground == SOIL
    assert clock.tick_count == 3


def test_operators_arithmetic_and_comparison_charge_ticks_and_assign_results(setup_interpreter):
    drone, clock, _ = setup_interpreter
    drone.tile.age = drone.world.defs["grass"].grow_ticks
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"operators", "variables"},
    )

    steps = list(interpreter.run(
        "value = (2 + 3) * 4\n"
        "if value >= 20 and not False:\n"
        "    harvest()"
    ))

    assert [step.function for step in steps] == [
        "+", "*", ">=", "and", "if", *("harvest" for _ in range(200))
    ]
    assert steps[0].args == (2, 3)
    assert steps[1].args == (5, 4)
    assert steps[2].args == (20, 20)
    assert clock.tick_count == 205


def test_tuple_list_conversion_concatenation_slicing_and_membership(
    setup_list_interpreter,
):
    _, clock, interpreter = setup_list_interpreter

    steps = list(interpreter.run(
        "items = [1, 2, 3]\n"
        "pair = (items[0], items[2])\n"
        "last = pair[1]\n"
        "copied = list(pair)\n"
        "found = 3 in pair\n"
        "missing = 5 not in items\n"
        "combined = items + [4]\n"
        "middle = items[1:3]"
    ))

    functions = [step.function for step in steps]
    assert functions.count("tuple_literal") == 1
    assert functions.count("list_membership") == 6
    assert functions.count("collection_concat") == 4
    assert functions.count("list_slice") == 3
    assert clock.tick_count == 24


def test_string_concatenation_uses_length_cost_without_lists_unlock(
    setup_interpreter,
):
    drone, clock, _ = setup_interpreter
    inventory = Inventory()
    progression = Progression(inventory, load_tech_tree())
    progression.unlocked.update({"Variables", "Operators"})
    interpreter = Interpreter(
        build_api(drone, progression),
        build_statement_api(drone, progression),
        build_constants(progression),
        progression.features(),
    )

    list(interpreter.run('message = "farmer" + "game"'))

    assert clock.tick_count == 10


def test_custom_function_definition_calls_and_return_costs(setup_function_interpreter):
    drone, clock, interpreter = setup_function_interpreter

    steps = list(interpreter.run(
        "def increment(value):\n"
        "    result = value + 1\n"
        "    return result\n"
        "answer = increment(3)\n"
        "if answer == 4:\n"
        "    harvest()"
    ))

    assert [step.function for step in steps].count("function_definition") == 1
    assert [step.function for step in steps].count("+") == 1
    assert [step.function for step in steps].count("==") == 1
    assert [entry[1] for entry in drone.log] == ["harvest"]
    assert clock.tick_count == 204


def test_custom_function_locals_do_not_mutate_caller_scope(
    setup_function_interpreter,
):
    drone, clock, interpreter = setup_function_interpreter

    list(interpreter.run(
        "value = 5\n"
        "def change_value(value):\n"
        "    value = value + 1\n"
        "    return value\n"
        "if change_value(2) == 3:\n"
        "    harvest()\n"
        "if value == 5:\n"
        "    harvest()"
    ))

    assert [entry[1] for entry in drone.log] == ["harvest", "harvest"]
    assert clock.tick_count == 406


def test_indirect_custom_function_call_costs_one_tick(setup_function_interpreter):
    drone, clock, interpreter = setup_function_interpreter

    steps = list(interpreter.run(
        "def collect():\n"
        "    harvest()\n"
        "callback = collect\n"
        "callback()"
    ))

    assert [step.function for step in steps].count("indirect_function_call") == 1
    assert [entry[1] for entry in drone.log] == ["harvest"]
    assert clock.tick_count == 202


def test_custom_function_defaults_are_evaluated_once_and_can_be_overridden(
    setup_function_interpreter,
):
    drone, clock, interpreter = setup_function_interpreter

    steps = list(interpreter.run(
        "base = 2\n"
        "def value_or_default(value=base + 1):\n"
        "    return value\n"
        "base = 10\n"
        "callback = value_or_default\n"
        "first = value_or_default()\n"
        "second = callback(5)\n"
        "if first == 3:\n"
        "    harvest()\n"
        "if second == 5:\n"
        "    harvest()"
    ))

    assert [step.function for step in steps].count("+") == 1
    assert [step.function for step in steps].count("function_definition") == 1
    assert [step.function for step in steps].count("indirect_function_call") == 1
    assert [entry[1] for entry in drone.log] == ["harvest", "harvest"]
    assert clock.tick_count == 407


def test_custom_function_default_arguments_validate_required_and_maximum_arity(
    setup_function_interpreter,
):
    _, clock, interpreter = setup_function_interpreter

    with pytest.raises(InterpreterError, match="1 sampai 2 argumen"):
        list(interpreter.run(
            "def combine(first, second=2):\n"
            "    return first + second\n"
            "combine()"
        ))
    assert clock.tick_count == 0

    with pytest.raises(InterpreterError, match="1 sampai 2 argumen"):
        list(interpreter.run(
            "def combine(first, second=2):\n"
            "    return first + second\n"
            "combine(1, 2, 3)"
        ))
    assert clock.tick_count == 0


def test_functions_require_unlock_and_return_is_limited_to_functions(
    setup_interpreter,
):
    drone, clock, _ = setup_interpreter
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"variables"},
    )

    with pytest.raises(InterpreterError, match="Functions belum di-unlock"):
        list(interpreter.run("def work():\n    harvest()"))
    with pytest.raises(InterpreterError, match="return hanya boleh"):
        list(interpreter.run("return 1"))
    assert clock.tick_count == 0


def test_boolean_operator_short_circuits_rhs_but_still_costs_one_tick(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    interpreter.features = frozenset({"operators"})

    steps = list(interpreter.run("if False and can_harvest():\n    harvest()"))

    assert [step.function for step in steps] == ["and", "if"]
    assert clock.tick_count == 2


def test_boolean_or_short_circuits_rhs_but_still_costs_one_tick(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    interpreter.features = frozenset({"operators"})

    steps = list(interpreter.run("if True or can_harvest():\n    can_harvest()"))

    assert [step.function for step in steps] == ["or", "if", "can_harvest"]
    assert clock.tick_count == 3


@pytest.mark.parametrize(
    ("expression", "expected", "operator_name"),
    [
        ("2 - 3", "-1", "-"),
        ("2 * 3", "6", "*"),
        ("5 / 2", "2.5", "/"),
        ("5 // 2", "2", "//"),
        ("5 % 2", "1", "%"),
        ("2 ** 3", "8", "**"),
    ],
)
def test_numeric_operators_match_documented_arithmetic_and_cost_one_tick(
    setup_interpreter,
    expression,
    expected,
    operator_name,
):
    drone, clock, _ = setup_interpreter
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"operators"},
    )

    steps = list(interpreter.run(
        f"if ({expression}) == ({expected}):\n    can_harvest()"
    ))

    assert steps[0].function == operator_name
    assert steps[1].function == "=="
    assert steps[2].function == "if"
    assert clock.tick_count == 4


@pytest.mark.parametrize(
    ("expression", "operator_name"),
    [
        ("2 == 2", "=="),
        ("2 != 3", "!="),
        ("2 < 3", "<"),
        ("2 <= 2", "<="),
        ("3 > 2", ">"),
        ("3 >= 3", ">="),
    ],
)
def test_scalar_comparisons_cost_one_tick(
    setup_interpreter,
    expression,
    operator_name,
):
    drone, clock, _ = setup_interpreter
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"operators"},
    )

    steps = list(interpreter.run(f"if {expression}:\n    can_harvest()"))

    assert steps[0].function == operator_name
    assert steps[1].function == "if"
    assert clock.tick_count == 3


def test_arithmetic_operators_reject_non_numeric_operands(setup_interpreter):
    drone, clock, _ = setup_interpreter
    interpreter = Interpreter(
        build_api(drone),
        build_statement_api(drone),
        build_constants(),
        features={"operators", "variables"},
    )

    with pytest.raises(InterpreterError, match="hanya menerima angka"):
        list(interpreter.run('value = "hay" + 2'))

    assert clock.tick_count == 0


def test_stop_mencegah_pemanggilan_berikutnya(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    stopped = False
    steps = interpreter.run(
        'move("east")\nmove("north")',
        should_stop=lambda: stopped,
    )

    next(steps)
    stopped = True
    with pytest.raises(StopIteration):
        next(steps)

    assert (drone.x, drone.y) == (1, 0)
    assert clock.tick_count == 1


def test_while_mengenakan_tick_per_pengecekan_dan_bisa_dihentikan(setup_interpreter):
    drone, clock, interpreter = setup_interpreter
    stopped = False
    steps = interpreter.run(
        "while True:\n    move('east')",
        should_stop=lambda: stopped,
    )

    first_step = next(steps)
    assert first_step.function == "while"
    assert clock.tick_count == 1

    for _ in range(200):
        step = next(steps)
    assert step.function == "move"
    assert clock.tick_count == 201
    assert drone.x == 1

    next_loop_check = next(steps)
    assert next_loop_check.function == "while"
    assert clock.tick_count == 202
    stopped = True
    with pytest.raises(StopIteration):
        next(steps)
    assert drone.x == 1


def test_while_false_hanya_mengecek_kondisi_tanpa_menjalankan_body(setup_interpreter):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run("while False:\n    move('east')"))

    assert [step.function for step in steps] == ["while"]
    assert clock.tick_count == 1
    assert drone.x == 0


def test_break_berhenti_di_loop_terdekat_dan_tidak_mengenakan_tick(
    setup_interpreter,
):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run(
        "while True:\n"
        "    harvest()\n"
        "    break\n"
        "harvest()"
    ))

    assert [step.function for step in steps].count("while") == 1
    assert [entry[1] for entry in drone.log] == ["harvest", "harvest"]
    assert clock.tick_count == 401


def test_continue_melanjutkan_iterasi_selanjutnya_tanpa_tick_tambahan(
    setup_interpreter,
):
    drone, clock, interpreter = setup_interpreter

    steps = list(interpreter.run(
        "for i in range(3):\n"
        "    if i < 1:\n"
        "        continue\n"
        "    harvest()"
    ))

    assert [step.function for step in steps].count("for") == 1
    assert [entry[1] for entry in drone.log] == ["harvest", "harvest"]
    assert clock.tick_count == 408


@pytest.mark.parametrize("keyword", ["break", "continue"])
def test_loop_control_di_luar_loop_ditolak_tanpa_tick(
    setup_interpreter,
    keyword,
):
    _, clock, interpreter = setup_interpreter

    with pytest.raises(InterpreterError, match=f"{keyword} hanya boleh"):
        list(interpreter.run(keyword))
    assert clock.tick_count == 0


def test_execution_step_mencatat_rentang_pemanggilan_terindentasi(setup_interpreter):
    _drone, _clock, interpreter = setup_interpreter

    steps = interpreter.run("if True:\n    harvest()")
    next(steps)
    step = next(steps)

    assert (step.line, step.column_start, step.end_line, step.column_end) == (
        2,
        4,
        2,
        13,
    )


def test_execution_step_mencatat_rentang_header_loop(setup_interpreter):
    _drone, _clock, interpreter = setup_interpreter

    step = next(interpreter.run("while False:\n    move('east')"))

    assert (step.line, step.column_start, step.end_line, step.column_end) == (
        1,
        0,
        1,
        len("while False:"),
    )


def test_execution_step_mengubah_offset_ast_utf8_ke_kolom_karakter(setup_interpreter):
    _drone, _clock, interpreter = setup_interpreter

    source = 'move("easté")'
    step = next(interpreter.run(source))

    assert (step.column_start, step.column_end) == (0, len(source))


@pytest.mark.parametrize(
    "source",
    ["import os", "__import__('os')", "move(direction='east')"],
)
def test_sintaks_dan_api_di_luar_subset_ditolak_sebelum_aksi(setup_interpreter, source):
    drone, clock, interpreter = setup_interpreter

    with pytest.raises(InterpreterError):
        list(interpreter.run(f'{source}\nmove("east")'))

    assert (drone.x, drone.y) == (0, 0)
    assert clock.tick_count == 0