"""§4 steps 2–3 — the pure graph half of the DAG engine. No DB needed."""

import uuid

import pytest

from app.dag.graph import closes_cycle, downstream, topo_sort, upstream

A, B, C, D = (uuid.uuid4() for _ in range(4))


def test_new_edge_that_closes_a_loop_is_detected():
    # A → B → C already exists; adding C → A closes the loop.
    edges = [(A, B), (B, C)]
    cycle = closes_cycle(edges, (C, A))
    assert cycle is not None
    assert cycle[0] == A and cycle[-1] == A


def test_self_edge_is_a_cycle():
    assert closes_cycle([], (A, A)) is not None


def test_diamond_is_not_a_cycle():
    # A feeds both B and C, which both feed D — legal, and a common shape.
    edges = [(A, B), (A, C), (B, D)]
    assert closes_cycle(edges, (C, D)) is None


def test_topo_sort_orders_inputs_before_dependents():
    order = topo_sort([D, C, B, A], [(A, B), (B, C), (C, D)])
    assert order == [A, B, C, D]


def test_topo_sort_raises_on_a_cycle():
    with pytest.raises(ValueError):
        topo_sort([A, B], [(A, B), (B, A)])


def test_downstream_walk_terminates_on_a_diamond():
    edges = [(A, B), (A, C), (B, D), (C, D)]
    assert downstream(edges, A) == {B, C, D}


def test_upstream_is_the_flipped_walk():
    edges = [(A, B), (B, C)]
    assert upstream(edges, C) == {A, B}
