import pytest

from game.progression import load_tech_tree
from ui.tree_layout import RESEARCH_ROWS, layout_tree


def test_parent_is_centered_above_children_in_top_down_layout():
    nodes = {
        "root": {"visual_parents": []},
        "left": {"visual_parents": ["root"]},
        "right": {"visual_parents": ["root"]},
    }

    positions = layout_tree(nodes, node_width=10, node_height=10, gap_x=20, gap_y=5)

    assert positions["left"] == (0, 15)
    assert positions["right"] == (30, 15)
    assert positions["root"] == (15, 0)


def test_wide_subtree_does_not_push_sibling_branch_far_sideways():
    nodes = {
        "root": {"visual_parents": []},
        "left": {"visual_parents": ["root"]},
        "right": {"visual_parents": ["root"]},
        "left_a": {"visual_parents": ["left"]},
        "left_b": {"visual_parents": ["left"]},
        "left_c": {"visual_parents": ["left"]},
        "right_a": {"visual_parents": ["right"]},
    }

    positions = layout_tree(nodes, node_width=10, node_height=10, gap_x=20, gap_y=5)

    assert positions["left"][1] == positions["right"][1] == 15
    assert positions["right"][0] - positions["left"][0] == 30
    assert [positions[name][0] for name in ("left_a", "left_b", "left_c", "right_a")] == [
        0, 30, 60, 90
    ]


def test_visual_cross_link_does_not_duplicate_node_or_change_depth():
    nodes = {
        "root": {"visual_parents": []},
        "branch_a": {"visual_parents": ["root"]},
        "branch_b": {"visual_parents": ["root"]},
        "shared": {"visual_parents": ["branch_a", "branch_b"]},
    }

    positions = layout_tree(nodes)

    assert set(positions) == set(nodes)
    assert positions["shared"][1] == positions["branch_a"][1] + 122
    assert positions["shared"][1] == positions["branch_b"][1] + 122


def test_visual_parent_cycle_is_rejected():
    nodes = {
        "first": {"visual_parents": ["second"]},
        "second": {"visual_parents": ["first"]},
    }

    with pytest.raises(ValueError, match="visual parent cycle"):
        layout_tree(nodes)


def test_reference_layout_orders_all_unlocks_in_top_down_rows():
    nodes = load_tech_tree()
    positions = layout_tree(nodes, ordered_rows=RESEARCH_ROWS)

    assert set(positions) == set(nodes)
    assert RESEARCH_ROWS[:4] == (
        ("Loops",),
        ("Speed", "Grass"),
        ("Expand", "Plant"),
        ("Carrots", "Debug", "Operators", "Expand_2"),
    )
    assert positions["Loops"][1] == 0
    assert positions["Speed"][1] == positions["Grass"][1] == 122
    assert positions["Carrots"][1] == positions["Operators"][1] == 366
    assert len({name for row in RESEARCH_ROWS for name in row}) == len(nodes)


def test_explicit_layout_rejects_missing_or_duplicate_nodes():
    nodes = {"root": {}, "child": {}}

    with pytest.raises(ValueError, match="include every node"):
        layout_tree(nodes, ordered_rows=(("root",),))

    with pytest.raises(ValueError, match="duplicate nodes"):
        layout_tree(nodes, ordered_rows=(("root", "root", "child"),))