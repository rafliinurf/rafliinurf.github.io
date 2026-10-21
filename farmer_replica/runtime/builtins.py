"""Subset fungsi bawaan Python yang tersedia untuk script player."""
from functools import partial
import operator
import random
from typing import Iterator

from game.drone import ActionProgress, ActionResult


def _range_steps(drone, *args) -> Iterator[ActionProgress]:
    values = range(*args)
    cost = drone.clock.cost_of("range")
    for completed_ticks in range(1, cost + 1):
        tick_count = drone.clock.advance()
        drone._advance_world(1)
        yield ActionProgress(True, values, completed_ticks, cost, tick_count)
    return ActionResult(True, values, cost)


def _advance_builtin(drone, result, cost):
    for completed_ticks in range(1, cost + 1):
        tick_count = drone.clock.advance()
        drone._advance_world(1)
        yield ActionProgress(True, None, completed_ticks, cost, tick_count)
    return ActionResult(True, result, cost)


def _collection_operation_steps(drone, result, cost):
    for completed_ticks in range(1, cost + 1):
        tick_count = drone.clock.advance()
        drone._advance_world(1)
        yield ActionProgress(
            True,
            None,
            completed_ticks,
            cost,
            tick_count,
        )
    return ActionResult(True, result, cost)


def build_collection_operation(drone, operation):
    def run(result, count=0, index=0, key=None, length=0):
        costs = drone.clock.costs["collection_operations"]
        if operation == "list_literal":
            literal_costs = costs["list_literal"]
            cost = (
                literal_costs["empty"]
                if count == 0
                else literal_costs["per_item"] * count
            )
        elif operation == "tuple_literal":
            literal_costs = costs["tuple_literal"]
            cost = literal_costs["base"]
        elif operation == "list_insert":
            insert_costs = costs["list_insert"]
            cost = (
                insert_costs["base"]
                + insert_costs["length_factor"] * count
                + insert_costs["index_factor"] * index
            )
        elif operation == "list_remove":
            cost = costs["list_remove"]["length_factor"] * count
        elif operation == "dictionary_literal":
            literal_costs = costs["dictionary_literal"]
            cost = (
                literal_costs["empty"]
                if count == 0
                else (
                    literal_costs["base"]
                    + literal_costs["per_entry"] * count
                )
            )
        elif operation == "dictionary_lookup":
            cost = _dictionary_key_cost(key)
        elif operation == "dictionary_membership":
            cost = _dictionary_key_cost(key, allow_string=False)
        elif operation == "list_slice":
            cost = costs["list_slice"]["base"] + length
        elif operation == "list_membership":
            cost = costs["list_membership"]["base"] + index
        elif operation == "collection_concat":
            cost = count + length
        else:
            cost = costs[operation]
        return _collection_operation_steps(drone, result, cost)
    return run


def _dictionary_key_cost(key, allow_string=True):
    if isinstance(key, bool):
        raise TypeError("boolean dictionary keys are not supported")
    if isinstance(key, (int, float)):
        return 1
    if isinstance(key, str):
        if not allow_string:
            raise TypeError("string-key dictionary membership cost is undocumented")
        return max(len(key) // 8, 1)
    if isinstance(key, tuple):
        return sum(
            _dictionary_key_cost(item, allow_string=True)
            for item in key
        )
    raise TypeError("dictionary keys must be numbers, strings, or tuples")


def build_set_builtin(drone):
    def make_set(values):
        if not isinstance(values, (list, tuple, dict, set)):
            raise TypeError("set() requires a collection")
        try:
            result = set(values)
        except TypeError as exc:
            raise TypeError("set() elements must be hashable") from exc
        cost_data = drone.clock.costs["collection_operations"]["set_from_collection"]
        cost = cost_data["base"] + cost_data["per_item"] * len(values)
        return (yield from _advance_builtin(drone, result, cost))

    return {"set": make_set}


def build_list_conversion_builtin(drone):
    def make_list(values):
        if not isinstance(values, (list, tuple, dict, set)):
            raise TypeError("list() requires a collection")
        result = list(values)
        cost_data = drone.clock.costs["collection_operations"]["list_from_collection"]
        cost = cost_data["base"] + cost_data["per_item"] * len(values)
        return (yield from _advance_builtin(drone, result, cost))

    return {"list": make_list}


def _minmax_steps(drone, function, *args):
    values = list(args[0]) if len(args) == 1 else list(args)
    if not values:
        raise ValueError(f"{function} arg is an empty sequence")
    compare = operator.lt if function == "min" else operator.gt
    result = values[0]
    comparisons = len(values) - 1
    for completed_ticks, value in enumerate(values[1:], start=1):
        if compare(value, result):
            result = value
        tick_count = drone.clock.advance()
        drone._advance_world(1)
        yield ActionProgress(
            True,
            None,
            completed_ticks,
            comparisons,
            tick_count,
        )
    return ActionResult(True, result, comparisons)


def _abs_steps(drone, value):
    return (yield from _advance_builtin(drone, abs(value), 1))


def _random_steps(drone):
    return (yield from _advance_builtin(drone, random.random(), 1))


def build_builtins(drone):
    return {"range": partial(_range_steps, drone)}


def build_utility_builtins(drone):
    return {
        "min": partial(_minmax_steps, drone, "min"),
        "max": partial(_minmax_steps, drone, "max"),
        "abs": partial(_abs_steps, drone),
        "random": partial(_random_steps, drone),
    }


def build_list_builtins(drone):
    def length(sequence):
        if not isinstance(sequence, (list, tuple, dict, set)):
            raise TypeError("len() membutuhkan collection yang didukung")
        cost = drone.clock.costs["collection_operations"]["len"]
        return (yield from _advance_builtin(drone, len(sequence), cost))

    return {"len": length}