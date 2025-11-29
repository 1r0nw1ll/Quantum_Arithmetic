Benchmarks

This folder scaffolds future Criterion benches for the Rust QA library. In
network-restricted environments, use the Python fallback bench instead:

- Make target: `make -C qa_lab bench-e8`
- Script: `qa_lab/scripts/bench_e8_alignment.py`

When network access is available, add Criterion as a dev-dependency in
Cargo.toml and create benches under this directory to measure:

- E8 alignment (prenorm and general)
- Batch invariants (J,K,X,W,Y,Z,C,F,G)
- End-to-end fast-path chunk performance

Recommended baseline metrics to record:

- N (vectors), M (roots), D=8
- Time (seconds), throughput (vectors/sec)
- Backend flags (SIMD on/off), parallel chunk sizes

