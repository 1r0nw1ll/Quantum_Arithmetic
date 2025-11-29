Training Metrics Hooks
======================

E8 Harmonic Index logging:
- Import from qa_metrics.e8_harmonic_index: log_harmonic_index(tag, e8, loss, extra={}).
- Suggested hook: end-of-epoch in qa_training_pipeline.py.
- Output file: logs/metrics_e8.jsonl

