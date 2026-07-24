"""Pure graph algorithms over the column DAG (§4 steps 2–3).

Kept free of the DB session on purpose: `validation.py` loads the edges, this
module decides. That makes the cycle check and the topo sort unit-testable
without a Postgres instance.

Edge direction throughout: `input_column_id → column_id` ("input feeds column"),
matching `column_input`.
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from typing import Iterable, Mapping, Sequence

Edge = tuple[uuid.UUID, uuid.UUID]  # (input_column_id, column_id)


def build_adjacency(edges: Iterable[Edge]) -> dict[uuid.UUID, set[uuid.UUID]]:
    """`{input: {dependents}}` — the downstream direction."""
    adj: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for src, dst in edges:
        adj[src].add(dst)
        adj.setdefault(dst, set())
    return adj


def find_path(
    adj: Mapping[uuid.UUID, set[uuid.UUID]],
    start: uuid.UUID,
    goal: uuid.UUID,
) -> list[uuid.UUID] | None:
    """Any downstream path `start → … → goal`, or None. DFS, iterative."""
    if start == goal:
        return [start]
    stack: list[tuple[uuid.UUID, list[uuid.UUID]]] = [(start, [start])]
    seen: set[uuid.UUID] = set()
    while stack:
        node, path = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for nxt in adj.get(node, ()):
            if nxt == goal:
                return [*path, nxt]
            stack.append((nxt, [*path, nxt]))
    return None


def closes_cycle(
    edges: Iterable[Edge], new_edge: Edge
) -> list[uuid.UUID] | None:
    """Would `new_edge` close a loop? Returns the offending cycle, or None.

    The new edge is `input → column`. It closes a loop exactly when `column`
    already reaches `input` downstream — including the self-edge case.
    """
    src, dst = new_edge
    if src == dst:
        return [src, dst]
    adj = build_adjacency(edges)
    back_path = find_path(adj, dst, src)
    if back_path is None:
        return None
    return [*back_path, dst]


def topo_sort(
    nodes: Sequence[uuid.UUID], edges: Iterable[Edge]
) -> list[uuid.UUID]:
    """Kahn's algorithm over the given subgraph. Raises on a cycle.

    Deterministic tie-breaking (insertion order of `nodes`) so a replayed run
    enqueues in the same order — easier to read in the run log.
    """
    node_set = set(nodes)
    order_hint = {n: i for i, n in enumerate(nodes)}
    indegree: dict[uuid.UUID, int] = {n: 0 for n in nodes}
    adj: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)

    for src, dst in edges:
        if src not in node_set or dst not in node_set:
            continue  # edge leaves the affected subgraph
        adj[src].append(dst)
        indegree[dst] += 1

    ready = deque(sorted((n for n in nodes if indegree[n] == 0), key=order_hint.get))
    out: list[uuid.UUID] = []
    while ready:
        node = ready.popleft()
        out.append(node)
        newly_ready = []
        for nxt in adj[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                newly_ready.append(nxt)
        for n in sorted(newly_ready, key=order_hint.get):
            ready.append(n)

    if len(out) != len(node_set):
        raise ValueError("topo_sort: subgraph contains a cycle")
    return out


def downstream(
    edges: Iterable[Edge], start: uuid.UUID, include_start: bool = False
) -> set[uuid.UUID]:
    """Everything reachable downstream of `start` — the staleness walk (§4).

    Set semantics (the SQL uses `UNION`, not `UNION ALL`) so diamonds and any
    accidental cycle terminate.
    """
    adj = build_adjacency(edges)
    seen: set[uuid.UUID] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        for nxt in adj.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    if include_start:
        seen.add(start)
    return seen


def upstream(
    edges: Iterable[Edge], target: uuid.UUID, include_target: bool = False
) -> set[uuid.UUID]:
    """Everything `target` derives from — the lineage walk (§4, the join flipped)."""
    flipped = [(dst, src) for src, dst in edges]
    return downstream(flipped, target, include_start=include_target)
