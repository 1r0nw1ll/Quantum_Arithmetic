# Ingestion Batch: January 24, 2026

**Processed**: 5 documents
**Theme**: QA mappings of cutting-edge AI research (formal reasoning, biology, physics computing, agentic systems)

---

## Summary Table

| Document | Source | QA Core Concept | Impact |
|----------|--------|-----------------|--------|
| `axiom_ai.odt` | Axiom Putnam 2025 | Difficulty is generator-relative | ★★★★★ |
| `levin_platonic_space.odt` | Michael Levin | Platonic Space = QA pattern manifold | ★★★★★ |
| `wise.odt` | WISE RF Computing | Computation as field geometry | ★★★★☆ |
| `llm_in_a_sandbox.odt` | LLM-in-Sandbox | Agentic = generator injection | ★★★★★ |
| `execution_grounded_automated_ai_research.odt` | Stanford 2026 | Research as reachability | ★★★★★ |

---

## 1. axiom_ai.odt

**Source**: Axiom's "From Seeing Why to Checking Everything" + Putnam 2025 results
**URL**: https://axiommath.ai/territory/from-seeing-why-to-checking-everything

### QA Mapping

**State Space**: `S_proof = (Goals, Context, LocalDefs, Constraints, KernelTypeState, Budget)`

**Generators**:
```
G_proof = {tactic_step, lemma_apply, rewrite, simp, induction, normalization, decision_procedure}
```

**Invariants** (Lean kernel enforces):
- Well-typedness
- Definitional equality
- Universe consistency
- Kernel acceptance of final term

**Failure Algebra**:
| Obstruction | Description |
|-------------|-------------|
| MISSING_LEMMA | Library gap |
| TYPE_MISMATCH | Move doesn't preserve constraints |
| REWRITE_BLOCKED | Equality not in right form |
| CASE_SPLIT_EXPLOSION | Combinatorial bookkeeping |
| ANALYSIS_FORMALISM_OVERHEAD | Real/limit machinery overhead |

**Key Insight**: "Difficulty is generator-relative" - human intuition = compressed path sketches; formal checking = replayable move-traces validated by invariant oracle.

**Certificate Types Proposed**:
- `PROOF_GRIND_WITNESS`: High formalization overhead with valid proof
- `GENERATOR_GAP_WITNESS`: Adding generator collapses search cost

---

## 2. levin_platonic_space.odt

**Source**: Dr. Michael Levin, Tufts University
**URLs**: Forms of Life symposium, Lex Fridman podcast

### QA Mapping

**Core Identification**:
- Platonic Space ≈ QA global possibility space of lawful patterns (PS)
- Platonic form ≈ attractor class / component / basin in PS
- Interface = interpretation functor from abstract descriptors to concrete moves
- Bioelectric signaling = QA control channel / message-passing substrate

**Formal Schema**:
```
Pattern Space (PS): structured set of patterns with composition/refinement/symmetry
Substrate Space (S): concrete physical states
Interface Map (I): S → PS (reads implementation as pattern)
Realization Map (R): PS → S (configures system for pattern ingress)
Generators (Γ): allowed transitions on S
```

**Key Axiom Alignment**:
> "Two systems can be materially different but pattern-equivalent if they map to the same region of PS under the relevant interface"

**Certificates Proposed**:
- `INTERFACE_VARIATION_THEOREM`: Changing Γ changes reachable set in PS
- `ATTRACTOR_STABILITY_CERTIFICATE`: Pattern robustness under substrate perturbation

---

## 3. wise.odt

**Source**: WISE - Disaggregated ML via In-Physics Computing at RF
**Paper**: https://science.org/doi/10.1126/sciadv.adz0817
**Code**: https://github.com/functions-lab/WISE

### QA Mapping

**Executive Summary**: WISE = QA computation where the machine is a field and invariant is preserved by propagation.

**Axiom Alignments**:

| QA Axiom | WISE Realization |
|----------|------------------|
| Geometric Action | Matrix-vector multiply via RF superposition/phase/mixing |
| Non-Reduction | Full model exists as broadcast field, no local compression |
| QA Time | Discrete RF symbol intervals, no continuous clock |

**Key Insight**: The air becomes part of the computer. Arithmetic operations = physical wave transformations.

**Paradigm Comparison**:
| Paradigm | What Computes | Where Intelligence Lives |
|----------|---------------|--------------------------|
| RF (WISE) | EM fields | In the network |
| Neuromorphic | Spiking dynamics | In the device |
| Photonic | Light propagation | In specialized hardware |

**Use Cases**: Smart cities, sensor swarms, drones, IoT, infrastructure-scale AI

---

## 4. llm_in_a_sandbox.odt

**Source**: LLM-in-Sandbox Elicits General Agentic Intelligence
**arXiv**: https://arxiv.org/abs/2601.16206
**Code**: https://github.com/llm-in-sandbox/llm-in-sandbox

### QA Mapping

**Core State**:
```
s ∈ S = S_dialog × S_sandbox
Actions: {execute_bash, str_replace_editor, submit}
Transition: s_{t+1} = T(s_t, a_t) includes real execution feedback
```

**Generator Set**:
- G_ext: External resources (curl, pip install)
- G_fs: File management (ls, grep, sed, cat)
- G_exec: Code execution (Python, scripts, solvers)

**Key Equivalence**:
> "LLM-in-Sandbox = GENERATOR_INJECTION into the policy's action algebra"

**Emergence Explanation**: Agentic behavior = reachability phase transition when sandbox generators cross barriers.

**Failure Algebra (Weak Models)**:
| Mode | Description |
|------|-------------|
| WANDER | Many ineffective turns |
| TOOL_UNAWARE | Doesn't invoke right generator |
| NON_LOCAL_SEARCH_FAILURE | Can't structure multi-step plans |
| ENV_EXEC_FAIL | Wrong install, breaks environment |

**Efficiency**: 8× token reduction by storing context in files vs prompt stuffing.

---

## 5. execution_grounded_automated_ai_research.odt

**Source**: Stanford 2026 - Si, Yang, Choi, Candès, Yang, Hashimoto
**arXiv**: https://arxiv.org/abs/2601.14525

### QA Mapping

**Research State**:
```
s = (idea, code, config, runlog, metrics, budget, lineage)
```

**Generator Set**:
```
σ_propose: sample idea from ideator
σ_implement: compile/patch/build code
σ_schedule: emit experiment DAG
σ_execute: run GPU trials → runlog, metrics
σ_validate: deterministic scoring → accept/reject
```

**Search Generators** (Evolutionary):
- μ_mutate: perturb idea/code/config
- κ_select: select top-k by execution reward
- τ_archive: retain elites + diversity buckets

**Key Finding**: Evolutionary search preserves exploration; RL collapses diversity (mode collapse).

**Invariants**:
| Type | Invariant |
|------|-----------|
| Hard | I_compile, I_run, I_budget, I_repro |
| Soft | J_perf (metric), K_cost, X_novelty |

**Critical Insight**: RL improves mean but loses upper bound because diversity collapses - violates "diversity invariant" needed to prevent reachable set collapse.

---

## Cross-Paper Synthesis

### Unified QA Themes

1. **Generator-Relative Difficulty** (axiom_ai, llm_in_a_sandbox)
   - Capability is not intrinsic to the agent
   - It's a property of (agent + environment + generators)
   - Adding generators = crossing barriers

2. **Execution as Invariant Oracle** (axiom_ai, execution_grounded)
   - Lean kernel = proof validator
   - GPU execution = research idea validator
   - Both filter plausible-sounding nonsense

3. **Field/Distributed Computation** (wise, levin_platonic_space)
   - Intelligence doesn't live in one place
   - Patterns exist in structured spaces, accessed via interfaces
   - Computation can be physics, not silicon

4. **Failure Algebra as First-Class** (all 5)
   - Every paper maps failure modes explicitly
   - Obstructions are theoretical objects, not bugs
   - Learning from failures = learning barrier topology

### Integration Targets

| Paper | Existing QA Module | Integration Path |
|-------|-------------------|------------------|
| axiom_ai | QA_MAP__AXIOM_AI.yaml | Already exists in ptolemy |
| levin_platonic_space | qa_generalization_* | Morphospace as QA attractor |
| wise | (new) | qa_field_computation.py |
| llm_in_a_sandbox | qa_terminal_agent | Generator injection framework |
| execution_grounded | qa_alphageometry | Research-as-reachability validator |

---

## Next Steps

1. **Create YAML mappings** for levin_platonic_space, wise, llm_in_a_sandbox, execution_grounded
2. **Update INGESTION_INDEX.md** with this batch
3. **Cross-link** with existing qa_alphageometry_ptolemy modules
4. **Prototype** field computation module inspired by WISE

---

**Status**: Processed and ready for integration
**Date**: 2026-01-25
