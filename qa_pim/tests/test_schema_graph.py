"""Tests for schema mapping and graph operations."""

import numpy as np
from qa_pim.schema import QAParams, schema_map, generate_graph_data
from qa_pim.graph import build_sector_csr, neighbor_expand


def test_schema_mapping():
    params = QAParams(m=24, RING_QUANTUM=1000, P=1024)
    keys = np.array([1, 25, 100])
    times = np.array([500, 2500, 15000])

    sectors, rings, phases = schema_map(keys, times, params)

    assert np.array_equal(sectors, keys % 24)
    assert np.array_equal(rings, times // 1000)
    assert np.all(phases >= 0) and np.all(phases < 1024)


def test_data_generation():
    data = generate_graph_data(N=100, E=200, seed=42)

    assert data["N"] == 100
    assert data["E"] == 200
    assert len(data["keys"]) == 100
    assert len(data["sectors"]) == 100
    assert data["edges"].shape == (200, 2)
    assert np.all(data["sectors"] < data["params"].m)
    assert np.all(data["phases"] < data["params"].P)


def test_data_generation_deterministic():
    d1 = generate_graph_data(N=50, E=100, seed=42)
    d2 = generate_graph_data(N=50, E=100, seed=42)
    assert np.array_equal(d1["keys"], d2["keys"])
    assert np.array_equal(d1["sectors"], d2["sectors"])


def test_sector_csr():
    sectors = np.array([0, 0, 1, 1, 2])
    edges = np.array([[0, 1], [0, 2], [1, 3], [2, 4], [3, 4]])
    sector_csr = build_sector_csr(sectors, edges, 3)

    assert 0 in sector_csr
    assert 1 in sector_csr
    assert 2 in sector_csr

    offsets_0, indices_0 = sector_csr[0]
    assert len(offsets_0) == 3  # 2 vertices + 1


def test_neighbor_expand():
    sectors = np.array([0, 0, 1, 1])
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    sector_csr = build_sector_csr(sectors, edges, 2)

    sector_vertices = {}
    for s in range(2):
        sector_vertices[s] = np.where(sectors == s)[0]

    selected_mask = np.ones(len(sectors), dtype=bool)
    edge_count, neighbors = neighbor_expand(sector_csr, sector_vertices, selected_mask)

    assert edge_count >= 0
    assert isinstance(neighbors, np.ndarray)
