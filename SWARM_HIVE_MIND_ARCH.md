# Swarm Hive-Mind Architecture (Rust)

Goal: Replace the Python central executor bottleneck with a distributed swarm where many simple “scout bees” act in parallel and a hive-mind (policy π) emerges via Maynard–Cross Learning (MCL). This turns N simple agents into one effective RL policy learning from N parallel environments.

## Core Components
- `ScoutBee` trait: async `scout()` produces `QualityEstimate { task_id, option, quality, artifacts }`.
- Waggle dance: broadcast frequency ∝ quality via `BroadcastBus`.
- `HiveMind`: Maintains population vector π and updates with simplified MCL: α = 1/N.
- `TaskPool`: Shared pool, supports random/round-robin sampling.

Repo additions:
- `src/swarm/` with `bee.rs`, `broadcast.rs`, `environment.rs`, `hive_mind.rs`.
- `src/agents/` with `e8_scout.rs`, `qa_scout.rs`, `research_scout.rs`.
- `src/bin/swarm_node.rs` demo node.

## Quick Start
- Build binary: `cargo run --bin swarm_node`
- Runs a short prototype: 3 scouts, 2 tasks, 5 steps.

## Integration With Existing Lab
- E8 agent proof is already wired in Python (`qa_agents/cli/e8_benchmark_agent.py`). The Rust `E8ScoutBee` will call into existing Rust kernels (via `qa_core`) or the Python agent for full artifact generation in a subsequent step. Current stub returns a heuristic `quality` and compiles the end-to-end swarm path.
- Keep using Python task YAMLs as the “environment” source; a lightweight adapter can feed `TaskPool`.

## Incorporating Ingestion Candidates (Highlights)
- CLaRa (continuous latent reasoning): Treat scouts’ internal opinions as moving “latent” proposals; `listen_and_switch` will update opinions from broadcast neighborhoods.
- Tool orchestrator: Model each tool capability as a specialized scout archetype; hive-mind π learns which tool-scout to activate by task type.
- Emotional intelligence: Add an “affect” feature to `QualityEstimate` to bias short-term exploration/exploitation (e.g., urgency → higher broadcast weight for failure recovery).
- Fact-storing MLPs: Cache high-value task→solution mappings and expose as a “memory scout” that retrieves and proposes known-good options.
- Flow-map distillation: Periodically compress diverse scout behaviors into a smaller distilled scout (policy compression over `QualityEstimate` distributions).
- Sheaf cohomology / PCNs: Represent multi-view constraints across scouts; penalize inconsistent broadcasts; reward coherent coverings of the task manifold.
- SSA (sparse-sparse attention): Neighborhood sampling in `BroadcastBus` acts as sparse attention over large scout populations; align with learned sparse patterns.

## Next Steps
- Wire `E8ScoutBee` to real alignment kernels and/or Python E8 agent; map statistics → `quality`.
- Add `DistributedBroadcastBus` (ZeroMQ or QUIC) to connect player2↔player4.
- Implement `listen_and_switch` logic for adaptive opinion updates.
- Add tests for `mcl_update` to validate convergence properties.

