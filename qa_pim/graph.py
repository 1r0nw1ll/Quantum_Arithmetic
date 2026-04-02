"""Sector-partitioned CSR graph representation and operations."""

import numpy as np
from typing import Dict, Tuple


def build_sector_csr(
    sectors: np.ndarray,
    edges: np.ndarray,
    m: int,
) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
    """Build CSR representation partitioned by source vertex sector.

    Returns dict mapping sector_id -> (offsets, indices).
    """
    sector_csr = {}

    for s in range(m):
        sector_mask = sectors == s
        sector_vertices = np.where(sector_mask)[0]

        if len(sector_vertices) == 0:
            sector_csr[s] = (
                np.array([0], dtype=np.int32),
                np.array([], dtype=np.int32),
            )
            continue

        vertex_map = {int(v): i for i, v in enumerate(sector_vertices)}
        n_sector = len(sector_vertices)

        source_in_sector = np.isin(edges[:, 0], sector_vertices)
        sector_edges = edges[source_in_sector]

        if len(sector_edges) == 0:
            sector_csr[s] = (
                np.zeros(n_sector + 1, dtype=np.int32),
                np.array([], dtype=np.int32),
            )
            continue

        offsets = np.zeros(n_sector + 1, dtype=np.int32)
        indices = []

        for i, v in enumerate(sector_vertices):
            v_edges = sector_edges[sector_edges[:, 0] == v]
            targets = v_edges[:, 1]
            indices.extend(targets)
            offsets[i + 1] = len(indices)

        sector_csr[s] = (offsets, np.array(indices, dtype=np.int32))

    return sector_csr


def neighbor_expand(
    sector_csr: Dict[int, Tuple[np.ndarray, np.ndarray]],
    sector_vertices: Dict[int, np.ndarray],
    selected_mask: np.ndarray,
) -> Tuple[int, np.ndarray]:
    """Expand neighbors from selected vertices and count traversed edges.

    Returns (edge_count, neighbor_array).
    """
    all_neighbors = []
    edge_count = 0

    for sector, (offsets, indices) in sector_csr.items():
        if sector not in sector_vertices:
            continue

        sector_verts = sector_vertices[sector]
        sector_selected = selected_mask[sector_verts]

        for i, selected in enumerate(sector_selected):
            if selected:
                start, end = offsets[i], offsets[i + 1]
                neighbors = indices[start:end]
                all_neighbors.extend(neighbors)
                edge_count += len(neighbors)

    return edge_count, np.array(all_neighbors, dtype=np.int32)
