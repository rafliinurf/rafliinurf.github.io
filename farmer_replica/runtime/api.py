"""Fungsi game yang diekspos ke script player."""
from functools import partial
from runtime.builtins import (
    build_builtins,
    build_collection_operation,
    build_list_builtins,
    build_list_conversion_builtin,
    build_set_builtin,
    build_utility_builtins,
)


def build_api(drone, progression=None):
    api = {
        **build_builtins(drone),
        "move": partial(drone.perform_steps, "move"),
        "clear": partial(drone.perform_steps, "clear"),
        "can_harvest": partial(drone.perform_steps, "can_harvest"),
        "harvest": partial(drone.perform_steps, "harvest"),
        "till": partial(drone.perform_steps, "till"),
        "plant": partial(drone.perform_steps, "plant"),
        "get_ground_type": partial(drone.perform_steps, "get_ground_type"),
    }
    if progression is None:
        return api

    features = progression.features()
    api = {"clear": api["clear"], "harvest": api["harvest"]}
    if "for_loop" in features:
        api["range"] = build_builtins(drone)["range"]
    if "movement" in features:
        api["move"] = partial(drone.perform_steps, "move")
    if "senses" in features:
        api["can_harvest"] = partial(drone.perform_steps, "can_harvest")
        api["get_ground_type"] = partial(drone.perform_steps, "get_ground_type")
        api["get_entity_type"] = partial(drone.perform_steps, "get_entity_type")
        api["get_pos_x"] = partial(drone.perform_steps, "get_pos_x")
        api["get_pos_y"] = partial(drone.perform_steps, "get_pos_y")
        api["can_move"] = partial(drone.perform_steps, "can_move")

        def num_items(item):
            return (yield from drone.perform_steps("num_items", item))

        def num_unlocked(target):
            return (yield from drone.perform_steps(
                "num_unlocked",
                progression.num_unlocked(target),
            ))

        api["num_items"] = num_items
        api["num_unlocked"] = num_unlocked
    if "watering" in features:
        api["get_water"] = partial(drone.perform_steps, "get_water")

        def use_item(item, n=1):
            if item != "water":
                raise ValueError(f"use_item belum di-unlock untuk item: {item}")
            return (yield from drone.perform_steps("use_item", item, n))

        api["use_item"] = use_item
    if "timing" in features:
        api["get_time"] = partial(drone.perform_steps, "get_time")
        api["get_tick_count"] = partial(drone.perform_steps, "get_tick_count")
    if "costs" in features:
        def get_cost(target, level=None):
            if not isinstance(target, str):
                raise ValueError("get_cost hanya menerima entity atau unlock")
            if target in drone.world.defs:
                if level is not None:
                    raise ValueError("level hanya berlaku untuk unlock")
                cost = dict(drone.world.defs[target].cost)
            else:
                cost = progression.get_cost(target, level)
            return (yield from drone.perform_steps("get_cost", cost))

        api["get_cost"] = get_cost
    if "utilities" in features:
        api.update(build_utility_builtins(drone))
    if "lists" in features:
        api.update(build_list_builtins(drone))
        api.update(build_list_conversion_builtin(drone))
    if "dictionaries" in features:
        api.update(build_set_builtin(drone))
    if "world_size" in features:
        api["get_world_size"] = partial(drone.perform_steps, "get_world_size")
    if "planting" in features:
        plantable_entities = {"bush"}
        if "carrots" in features:
            plantable_entities.add("carrot")

        def plant(entity):
            if entity not in plantable_entities:
                raise ValueError(f"plant belum di-unlock untuk entity: {entity}")
            return (yield from drone.perform_steps("plant", entity))

        api["plant"] = plant
    if "till" in features:
        api["till"] = partial(drone.perform_steps, "till")
    return api


def build_statement_api(drone, progression=None):
    statement_api = {
        "if": partial(drone.statement_steps, "if"),
        "for": partial(drone.statement_steps, "for"),
        "while": partial(drone.statement_steps, "while"),
        "function_definition": partial(
            drone.statement_steps,
            "function_definition",
        ),
        "indirect_function_call": partial(
            drone.statement_steps,
            "indirect_function_call",
        ),
        **{
            operator: partial(drone.statement_steps, operator)
            for operator in (
                "+", "-", "*", "/", "//", "%", "**",
                "==", "!=", "<", "<=", ">", ">=",
                "and", "or",
            )
        },
    }
    if progression is None:
        return statement_api
    features = progression.features()
    enabled = {"if": statement_api["if"]}
    if "while" in features:
        enabled["while"] = statement_api["while"]
    if "for_loop" in features:
        enabled["for"] = statement_api["for"]
    if "functions" in features:
        enabled["function_definition"] = statement_api["function_definition"]
        enabled["indirect_function_call"] = statement_api["indirect_function_call"]
    if "operators" in features:
        enabled.update({
            operator: statement_api[operator]
            for operator in statement_api
            if operator not in {
                "if",
                "for",
                "while",
                "function_definition",
                "indirect_function_call",
            }
        })
        enabled["collection_concat"] = build_collection_operation(
            drone,
            "collection_concat",
        )
    if "lists" in features:
        enabled.update({
            name: build_collection_operation(drone, name)
            for name in (
                "list_literal",
                "tuple_literal",
                "list_index",
                "list_insert",
                "list_remove",
                "list_slice",
                "list_membership",
            )
        })
    if "dictionaries" in features:
        enabled.update({
            name: build_collection_operation(drone, name)
            for name in (
                "dictionary_literal",
                "dictionary_lookup",
                "dictionary_membership",
            )
        })
    return enabled


def build_constants(progression=None):
    constants = {"Grounds": {"Grassland": "grassland", "Soil": "soil"}}
    if progression is None:
        return constants

    features = progression.features()
    if "movement" in features:
        constants.update({
            "North": "north",
            "East": "east",
            "South": "south",
            "West": "west",
        })
    if "senses" in features:
        constants["Items"] = {
            "Hay": "hay",
            "Wood": "wood",
            "Carrot": "carrot",
            "Pumpkin": "pumpkin",
            "Cactus": "cactus",
            "Gold": "gold",
            "Power": "power",
            "Water": "water",
            "Fertilizer": "fertilizer",
            "Weird_Substance": "weird_substance",
            "Bone": "bone",
        }
        constants["Unlocks"] = {
            name: name for name in progression.tech_tree
        }
        constants["Entities"] = {
            "Grass": "grass",
            **(
                {"Bush": "bush"}
                if "planting" in features
                else {}
            ),
            **(
                {"Carrot": "carrot"}
                if "carrots" in features
                else {}
            ),
        }
    if "costs" in features:
        constants.setdefault("Items", {
            "Hay": "hay",
            "Wood": "wood",
            "Carrot": "carrot",
            "Pumpkin": "pumpkin",
            "Cactus": "cactus",
            "Gold": "gold",
            "Power": "power",
            "Water": "water",
            "Fertilizer": "fertilizer",
            "Weird_Substance": "weird_substance",
            "Bone": "bone",
        })
        constants.setdefault(
            "Unlocks",
            {name: name for name in progression.tech_tree},
        )
    elif "watering" in features:
        constants["Items"] = {"Water": "water"}
    if "planting" in features:
        entities = {"Grass": "grass", "Bush": "bush"}
        if "carrots" in features:
            entities["Carrot"] = "carrot"
        constants["Entities"] = entities
    return constants