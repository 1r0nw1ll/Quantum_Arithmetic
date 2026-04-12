"""QA Knowledge Graph — multi-relational typed-edge wrapper over the [210]
qa_retrieval store (or any compatible in-memory adjacency).

The [210] QA_CONVERSATION_ARAG_CERT certifies a SQLite datastore with:

    messages(msg_id, source, role, b, e, raw_text, ...)
    edges(src_msg_id, dst_msg_id, edge_type IN {parent, cite, succ, ref})

This module exposes that store as a programmatic multi-relational KG with
typed edges and QA sector labels. It also proves the role-diagonal theorem
(originally stated in [210] docs) exhaustively over the 81-state (b,e) space.

Theorem (Role-Diagonal):
    For any QA state (b, e) with b in {1..9}, e in {1..9},
        d_label = 1 + ((b + e - 1) mod 9)
        a_label = 1 + ((b + 2e - 1) mod 9)
    the diagonal index (a_label - d_label) mod 9 equals e mod 9 identically.

Corollary: the 81-sector space (d_label, a_label) partitions into exactly
9 disjoint diagonals, each containing 9 sectors. Each canonical role (with
its unique role_rank e) occupies one diagonal. Role-based queries have O(9)
structural cost regardless of corpus size.

Usage:
    kg = QAKnowledgeGraph.from_qa_retrieval_db(path)   # real [210] instance
    kg = QAKnowledgeGraph.build_demo()                 # small in-memory demo
    kg.typed_edges_of_type('parent')                   # list of (src, dst) pairs
    kg.sector_of_node(msg_id)                          # (d_label, a_label)
    kg.nodes_on_diagonal(e=2)                          # all assistant-role nodes
    kg.multi_hop_neighbors(msg_id, ['parent', 'succ'], max_hops=3)
    kg.verify_role_diagonal_theorem()                  # returns proof dict

QA axiom compliance:
    A1: all (b, e) are in {1..9}; sector labels via 1 + ((x-1) mod 9)
    A2: d, e derived as b+e, b+2e (never assigned independently)
    T2: FTS5/PPR scores, if computed elsewhere, are observer-layer only
    S1: no ** operator
    S2: integer state only; node IDs are strings (not QA state)
    T1: path hops are integer; no continuous time
"""

QA_COMPLIANCE = "observer=knowledge_graph_wrapper, state_alphabet=qa_state_space_S_9, tier=multi_relational_typed_edge_graph"

import sqlite3
from collections import defaultdict, deque
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Canonical edge types from [210]. Enforced by CHECK constraint in the SQLite schema.
CANONICAL_EDGE_TYPES: Tuple[str, ...] = ("parent", "cite", "succ", "ref")

# Canonical role -> role_rank mapping from [210] schema.py ROLE_RANK.
# Note: role_rank is the e coordinate (deterministic per canonical role).
ROLE_RANK: Dict[str, int] = {
    "user": 1,
    "assistant": 2,
    "tool": 3,
    "system": 4,
    "thought": 5,
    "note": 6,
}


# -----------------------------------------------------------------------------
# QA primitives
# -----------------------------------------------------------------------------

def dr(n: int) -> int:
    """Aiq Bekar digital root, A1-compliant [202]."""
    if n <= 0:
        return 9
    return 1 + ((int(n) - 1) % 9)


def compute_sector(b: int, e: int) -> Tuple[int, int]:
    """(d_label, a_label) in {1..9}^2 via A1-adjusted mod-9 reduction.

    A2-compliant: d and e are derived (d=b+e, a=b+2e), then the T-operator
    reduces to labels.
    """
    d = b + e        # A2: d is always b+e
    a = b + 2 * e    # A2: a is always b+2e
    return (1 + ((d - 1) % 9), 1 + ((a - 1) % 9))


def diagonal_index(b: int, e: int) -> int:
    """Return the role-diagonal index of (b,e). Theorem: equals e mod 9."""
    d_label, a_label = compute_sector(b, e)
    return (a_label - d_label) % 9


# -----------------------------------------------------------------------------
# Multi-relational KG data class
# -----------------------------------------------------------------------------

class QAKnowledgeGraph:
    """A multi-relational knowledge graph with QA-labeled nodes.

    Nodes are identified by string IDs; each node has integer QA coordinates
    (b, e) and a canonical role. Edges are typed by edge_type in CANONICAL_EDGE_TYPES.

    The graph is stored as:
        nodes[node_id] = {'b': int, 'e': int, 'role': str}
        edges_by_type[edge_type] = set of (src_id, dst_id) tuples
        out_edges[node_id] = dict edge_type -> set of dst_ids
        in_edges[node_id]  = dict edge_type -> set of src_ids

    No floats anywhere. No learned parameters. Pure combinatorial structure.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, Dict] = {}
        self.edges_by_type: Dict[str, Set[Tuple[str, str]]] = {
            t: set() for t in CANONICAL_EDGE_TYPES
        }
        self.out_edges: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self.in_edges: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    # ---- Construction ----

    def add_node(self, node_id: str, b: int, e: int, role: str) -> None:
        if not (1 <= b <= 9):
            raise ValueError(f"A1 violation: b={b} not in {{1..9}} for node {node_id}")
        if not (1 <= e <= 9):
            raise ValueError(f"e={e} not in {{1..9}} for node {node_id}")
        if role not in ROLE_RANK:
            raise ValueError(f"unknown role {role!r} for node {node_id}")
        self.nodes[node_id] = {"b": int(b), "e": int(e), "role": role}

    def add_edge(self, src: str, dst: str, edge_type: str) -> None:
        if edge_type not in CANONICAL_EDGE_TYPES:
            raise ValueError(f"unknown edge_type {edge_type!r} (must be in {CANONICAL_EDGE_TYPES})")
        if src not in self.nodes or dst not in self.nodes:
            raise ValueError(f"edge ({src}, {dst}, {edge_type}) references unknown node")
        self.edges_by_type[edge_type].add((src, dst))
        self.out_edges[src][edge_type].add(dst)
        self.in_edges[dst][edge_type].add(src)

    # ---- Loading ----

    @classmethod
    def from_qa_retrieval_db(cls, path: str, limit_messages: Optional[int] = None) -> "QAKnowledgeGraph":
        """Load from a [210] qa_retrieval SQLite store.

        Parameters
        ----------
        path : str
            Path to the SQLite file (typically _forensics/qa_retrieval.sqlite).
        limit_messages : int or None
            Optional cap on number of messages loaded (useful for smoke tests).
        """
        conn = sqlite3.connect(path)
        try:
            kg = cls()
            msg_query = "SELECT msg_id, b, e, role FROM messages"
            if limit_messages is not None:
                msg_query += f" LIMIT {int(limit_messages)}"
            for msg_id, b, e, role in conn.execute(msg_query):
                if role not in ROLE_RANK:
                    continue   # skip unknown roles rather than raise
                try:
                    kg.add_node(msg_id, int(b), int(e), role)
                except ValueError:
                    continue   # skip A1-invalid rows defensively

            loaded_ids = set(kg.nodes.keys())
            for src, dst, et in conn.execute(
                "SELECT src_msg_id, dst_msg_id, edge_type FROM edges"
            ):
                if src in loaded_ids and dst in loaded_ids:
                    try:
                        kg.add_edge(src, dst, et)
                    except ValueError:
                        continue
            return kg
        finally:
            conn.close()

    @classmethod
    def build_demo(cls) -> "QAKnowledgeGraph":
        """Small in-memory demo KG for tests and documentation.

        Creates 6 nodes (one per canonical role) with hand-picked (b,e) values,
        connected by representative edges of each type. Covers all 4 edge_types
        and all 6 roles.
        """
        kg = cls()
        # One node per canonical role, all with b=3 (arbitrary cosmos state)
        role_nodes = {}
        for role, e in ROLE_RANK.items():
            node_id = f"demo:{role}:1"
            kg.add_node(node_id, b=3, e=e, role=role)
            role_nodes[role] = node_id

        # Add a second user node to exercise multi-hop
        kg.add_node("demo:user:2", b=7, e=1, role="user")

        # Edges exercising all 4 canonical types
        kg.add_edge(role_nodes["user"], role_nodes["assistant"], "parent")
        kg.add_edge(role_nodes["assistant"], role_nodes["tool"], "parent")
        kg.add_edge(role_nodes["tool"], role_nodes["assistant"], "succ")
        kg.add_edge(role_nodes["user"], "demo:user:2", "succ")
        kg.add_edge(role_nodes["assistant"], role_nodes["thought"], "cite")
        kg.add_edge(role_nodes["note"], role_nodes["user"], "ref")
        kg.add_edge("demo:user:2", role_nodes["note"], "ref")

        return kg

    # ---- Accessors ----

    def num_nodes(self) -> int:
        return len(self.nodes)

    def num_edges(self, edge_type: Optional[str] = None) -> int:
        if edge_type is None:
            return sum(len(s) for s in self.edges_by_type.values())
        return len(self.edges_by_type.get(edge_type, set()))

    def typed_edges_of_type(self, edge_type: str) -> List[Tuple[str, str]]:
        return sorted(self.edges_by_type.get(edge_type, set()))

    def sector_of_node(self, node_id: str) -> Tuple[int, int]:
        node = self.nodes[node_id]
        return compute_sector(node["b"], node["e"])

    def diagonal_of_node(self, node_id: str) -> int:
        node = self.nodes[node_id]
        return diagonal_index(node["b"], node["e"])

    def nodes_on_diagonal(self, e: int) -> List[str]:
        """Return all nodes with role_rank == e (equivalently, diagonal index = e % 9)."""
        if not (1 <= e <= 9):
            raise ValueError(f"e must be in {{1..9}}, got {e}")
        return sorted(nid for nid, nd in self.nodes.items() if nd["e"] == e)

    def nodes_in_sector(self, d_label: int, a_label: int) -> List[str]:
        return sorted(
            nid for nid, nd in self.nodes.items()
            if compute_sector(nd["b"], nd["e"]) == (d_label, a_label)
        )

    def multi_hop_neighbors(
        self,
        start: str,
        edge_types: Iterable[str],
        max_hops: int = 1,
    ) -> Set[str]:
        """BFS from start using only the given edge types; return reachable set.

        Integer hop counts (T1 compliant). Undirected traversal (src->dst and
        dst->src via in_edges).
        """
        if start not in self.nodes:
            return set()
        edge_types_set = set(edge_types)
        seen = {start}
        frontier = deque([(start, 0)])
        while frontier:
            node, d = frontier.popleft()
            if d >= max_hops:
                continue
            for et in edge_types_set:
                for nb in self.out_edges.get(node, {}).get(et, ()):
                    if nb not in seen:
                        seen.add(nb)
                        frontier.append((nb, d + 1))
                for nb in self.in_edges.get(node, {}).get(et, ()):
                    if nb not in seen:
                        seen.add(nb)
                        frontier.append((nb, d + 1))
        return seen

    # ---- Theorems ----

    def verify_role_diagonal_theorem(self) -> Dict:
        """Exhaustively verify (a_label - d_label) mod 9 == e mod 9 over {1..9}^2.

        Independent of KG content — this is a pure theorem on the (b,e) space.
        Also counts KG nodes per diagonal to show empirical role partition.
        """
        checked = 0
        matched = 0
        for b in range(1, 10):
            for e in range(1, 10):
                checked += 1
                d_label, a_label = compute_sector(b, e)
                diag = (a_label - d_label) % 9
                if diag == (e % 9):
                    matched += 1

        # Also tabulate nodes per diagonal in this KG
        diag_counts: Dict[int, int] = {i: 0 for i in range(9)}
        for nid in self.nodes:
            diag_counts[self.diagonal_of_node(nid)] += 1

        return {
            "checked": checked,
            "matched": matched,
            "theorem_ok": matched == checked,
            "kg_nodes_per_diagonal": diag_counts,
            "kg_num_nodes": len(self.nodes),
        }

    def verify_sector_partition(self) -> Dict:
        """Verify that the 81-sector space partitions into 9 role-diagonals,
        each containing exactly 9 sectors.
        """
        by_e: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)
        for b in range(1, 10):
            for e in range(1, 10):
                by_e[e].add(compute_sector(b, e))

        per_diagonal_sector_counts = {e: len(sectors) for e, sectors in by_e.items()}
        total_sectors = sum(per_diagonal_sector_counts.values())
        uniform = all(c == 9 for c in per_diagonal_sector_counts.values())

        return {
            "per_diagonal_sector_count": per_diagonal_sector_counts,
            "total_sectors": total_sectors,
            "expected_total": 81,
            "uniform": uniform,
            "partition_ok": total_sectors == 81 and uniform,
        }


__all__ = [
    "CANONICAL_EDGE_TYPES",
    "ROLE_RANK",
    "dr",
    "compute_sector",
    "diagonal_index",
    "QAKnowledgeGraph",
]
