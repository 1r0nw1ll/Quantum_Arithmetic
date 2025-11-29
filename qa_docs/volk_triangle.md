# Volk–Grant QA Triangle

This document tracks the integration of Volk–Grant Logarithmic Right Triangle (LRT)
into the QA pipeline.

- Core: `qa_toroid_sumproduct.py` maps (b,e,d,a) → (C,F,G) → torus params (a,R,r,b,k).
- Utilities: `projects/volk_triangle/triangle_util.py` for summaries.
- CLI: `qa_agents/cli/volk_triangle_viz.py` writes JSON summaries and optional plots.
- Next: dataset generation for QALM and integration into graphsmith.