# QA Lab: Autonomous Swarm Roadmap

**Version:** 1.0 (Swarm-Optimized)
**Date:** 2025-11-26
**Mode:** Autonomous Agent Execution

---

## Executive Summary

This is the **swarm-optimized** version of the comprehensive roadmap, reprioritized for autonomous agent execution. The key change: **AI Co-Scientist (Experiment Generator) is now Priority 1**, enabling the swarm to self-organize all other research tasks.

---

## Swarm Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI CO-SCIENTIST (Meta-Layer)              │
│  • Reads roadmap + ingestion papers                         │
│  • Generates experiment tasks                               │
│  • Adapts based on past results                            │
└──────────────────┬──────────────────────────────────────────┘
                   │ creates tasks
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    TASK ORCHESTRATION                        │
│  Scout → Prioritizer → Planner → Dispatcher → Executor      │
└──────────────────┬──────────────────────────────────────────┘
                   │ assigns to
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    SPECIALIZED AGENTS                        │
│  • QALM: QA reasoning, ablations, theoretical work         │
│  • Rust Porter: Implement bins, benchmarks                 │
│  • Gemini: Document analysis, ingestion papers             │
│  • Builder: Create new agents                              │
│  • Data Collector: Gather datasets                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Tier 0: Meta-Layer (Enable Swarm) 🔥 NEW

### 0.1 AI Co-Scientist (Experiment Generator)
**Priority:** CRITICAL (Foundation for all other work)
**Status:** ✅ Implemented (`qa_agents/cli/experiment_generator.py`)
**Effort:** 0 days (DONE)
**Impact:** ⭐⭐⭐⭐⭐ Enables autonomous research

**Capabilities:**
- Parses `QA_COMPREHENSIVE_ROADMAP.md` to extract experiments
- Identifies unprocessed ingestion papers
- Generates executable tasks (YAML) in `tasks/inbox/`
- Prioritizes based on impact × feasibility
- Adapts from `qa_paper.json` results (future)

**Usage:**
```bash
python3 qa_agents/cli/experiment_generator.py
make experiment-gen  # Makefile target
```

**Output:**
- Tasks in `tasks/inbox/exp-*.yaml` (experiments)
- Tasks in `tasks/inbox/ingest-*.yaml` (ingestion papers)
- Log in `logs/experiment_generator_*.json`

---

### 0.2 Swarm Agent Loop Enhancement
**Priority:** CRITICAL
**Status:** Partially implemented (needs experiment_generator integration)
**Effort:** 1 hour

**Implementation:**
1. Add `experiment-gen` to Makefile:
   ```makefile
   experiment-gen:
       @echo "🧠 AI Co-Scientist: Generating experiment tasks..."
       $(PYTHON) qa_agents/cli/experiment_generator.py
   ```

2. Update `agent_loop` target to include experiment generation:
   ```makefile
   agent_loop: experiment-gen scout prioritize plan builder self_improve dispatch executor review archive metrics-numpy-baseline
       @echo "🔄 Agent loop complete"
   ```

3. Add continuous daemon mode:
   ```makefile
   swarm-daemon:
       @echo "🔁 Starting autonomous swarm (Ctrl+C to stop)..."
       @while true; do \
           make experiment-gen; \
           make agent_loop; \
           sleep 3600; \
       done
   ```

**Acceptance Criteria:**
- ✅ Experiment generator runs before scout
- ✅ Tasks flow: experiment-gen → inbox → dispatcher → executor
- ✅ Daemon mode runs continuously with 1-hour cycle

---

### 0.3 Executor Extensions for Experiment Tasks
**Priority:** HIGH
**Status:** Needs patching
**Effort:** 2 hours

**Required Enhancements:**

1. **Rust Experiment Handler:**
   - Detect `metadata.bin` and `metadata.makefile_target`
   - Auto-run: `cargo run --release --bin {bin} -- {args}`
   - Parse CSV output → update task with results
   - Trigger plot script if exists

2. **Ingestion Paper Handler:**
   - Detect `metadata.paper_path`
   - Extract ODT: `unzip -p {paper} content.xml | xmllint --format -`
   - Pass to Gemini/Claude for analysis
   - Save analysis to `metadata.output_analysis`
   - Generate follow-up experiment tasks based on findings

3. **Result Aggregation:**
   - After each experiment, update `qa_paper.json`
   - Trigger `make qa-paper-bundle` if new plots generated
   - Notify experiment_generator of completion (for adaptation)

**Acceptance Criteria:**
- ✅ Executor can run Rust bins automatically
- ✅ Executor can process ingestion papers
- ✅ Results flow back to qa_paper.json

---

## Tier 1: Foundation (Swarm-Enabled Priorities)

### 1.1 Process High-Priority Ingestion Papers (Swarm-Driven)
**Priority:** CRITICAL
**Auto-Generated Tasks:** 5 (sheaf cohomology, qa_jit, ramen, stat mech, ai_coscientist)
**Agent:** Gemini (document analysis)
**Effort:** 5 × 2 hours = 10 hours (parallel)

**Papers to Process:**
1. `sheafcohomologyUntitled 1.odt` → Mathematical foundations for PCN
2. `qa_jit.odt` → JIT compilation (10-100× speedup potential)
3. `ramen_quantum_memory.odt` → Quantum memory encoding
4. `statistical_mechanics_for_real_brains.odt` → Neural stat mech
5. `ai_coscientist.odt` → Self-improving research loops

**Expected Output per Paper:**
- `artifacts/ingestion/{paper}_ANALYSIS.md`
- Follow-up experiment tasks in inbox
- Integration code stubs

---

### 1.2 Raman Feature Ablation (User-Requested)
**Priority:** HIGH
**Auto-Generated Task:** `exp-5-3-raman-feature-ablation.yaml`
**Agent:** QALM (analysis) + Rust (execution)
**Effort:** 1 day

**Already documented in NEXT_STEPS_PRIORITIES.md**

---

### 1.3 Seed Stability (10 seeds)
**Priority:** HIGH
**Auto-Generated Task:** `exp-4-4-seed-stability.yaml`
**Agent:** Rust
**Effort:** 1 day

**Already documented in NEXT_STEPS_PRIORITIES.md**

---

### 1.4 Component Ablation
**Priority:** HIGH
**Auto-Generated Task:** `exp-5-1-component-ablation.yaml`
**Agent:** Rust
**Effort:** 2 days

**Already documented in NEXT_STEPS_PRIORITIES.md**

---

### 1.5 JEPA-MNIST Integration
**Priority:** HIGH
**Auto-Generated Task:** `exp-3-1-jepa-mnist.yaml`
**Agent:** Rust (based on existing `qa_jepa_encoder.py`)
**Effort:** 3 days

**Already documented in NEXT_STEPS_PRIORITIES.md**

---

## Tier 2: Autonomous Expansion

### 2.1 HSI Classification
**Auto-Generated Task:** `exp-6-1-hsi-classification.yaml`
**Agent:** Rust
**Dataset:** `multimodal_data/HSI_Tr.mat` (already present)
**Effort:** 3 days

### 2.2 QA-ARC Vision Hybrid
**Auto-Generated Task:** `exp-3-2-arc-hybrid.yaml`
**Agent:** Rust + Gemini (architecture design)
**Dataset:** ARC-AGI-1 (download required)
**Effort:** 5 days
**Impact:** ⭐⭐⭐⭐⭐ Publishable AGI benchmark result

### 2.3 Parameter Grid Sweep
**Auto-Generated Task:** `exp-4-1-parameter-sweep.yaml`
**Agent:** Rust
**Effort:** 2 days

### 2.4 Statistical Mechanics Framework
**Auto-Generated Task:** `exp-3-4-stat-mech.yaml`
**Agent:** QALM (theoretical derivations) + Rust (verification)
**Effort:** 4 days
**Depends On:** `ingest-statistical_mechanics.yaml` completion

---

## Tier 3: Advanced Research

All experiments from `QA_COMPREHENSIVE_ROADMAP.md` Tiers 3-4 will be auto-generated by the experiment generator as Tier 1-2 tasks complete.

---

## Swarm Execution Protocol

### Phase 1: Bootstrap (Today)
```bash
# 1. Generate initial experiment tasks
python3 qa_agents/cli/experiment_generator.py

# 2. Verify tasks created
ls -lh tasks/inbox/exp-*.yaml tasks/inbox/ingest-*.yaml

# 3. Run single agent loop cycle
make agent_loop

# 4. Monitor execution
tail -f logs/experiment_generator_*.json
tail -f logs/executor_*.log
```

### Phase 2: Continuous Swarm (Ongoing)
```bash
# Launch autonomous daemon
make swarm-daemon

# Or use screen/tmux for persistent session
screen -S qa-swarm
make swarm-daemon
# Ctrl+A, D to detach
```

### Phase 3: Monitoring & Adaptation
```bash
# Check task status
ls tasks/active/*.yaml | wc -l    # Currently active
ls tasks/completed/*.yaml | wc -l # Completed

# Review results
cat artifacts/overleaf/qa_paper.json | jq '.'

# Manual intervention (if needed)
QA_FORCE_AGENT=claude make dispatch  # Route specific tasks to Claude
```

---

## Pipeline Gaps & Patches Needed

### Gap 1: Executor doesn't auto-run Rust bins ❌
**Patch:** Add Rust experiment handler (see 0.3 above)
**Priority:** CRITICAL
**Effort:** 2 hours

### Gap 2: Executor doesn't process ingestion papers ❌
**Patch:** Add ODT extraction + Gemini analysis handler
**Priority:** CRITICAL
**Effort:** 2 hours

### Gap 3: Results don't flow back to qa_paper.json ❌
**Patch:** Executor should call `python qa_agents/cli/qa_paper.py --json-out ...` after experiments
**Priority:** HIGH
**Effort:** 1 hour

### Gap 4: Plot generation not automated ❌
**Patch:** Executor should detect new CSVs and trigger `make qa-plots-{experiment}`
**Priority:** MEDIUM
**Effort:** 1 hour

### Gap 5: No adaptive re-prioritization ❌
**Patch:** Experiment generator should read qa_paper.json and boost priority of successful experiment types
**Priority:** LOW (future enhancement)
**Effort:** 3 hours

---

## Success Metrics (1-Week Swarm Test)

**Autonomy:**
- [ ] Swarm runs 24/7 without human intervention
- [ ] ≥50 tasks auto-generated by experiment_generator
- [ ] ≥30 tasks auto-executed by swarm
- [ ] ≥10 experiments completed end-to-end (bin → CSV → plot → JSON)

**Quality:**
- [ ] All guardrails pass (step_speedup ≥ 1.2×)
- [ ] ≥3 ingestion papers processed
- [ ] ≥5 new experiments added to qa_paper.json
- [ ] No manual debugging required for >80% of tasks

**Adaptation:**
- [ ] Experiment generator prioritizes follow-ups to successful experiments
- [ ] Failed experiments automatically de-prioritized
- [ ] New experiment types discovered from ingestion papers

---

## Next Actions (Right Now)

1. **Test experiment generator:**
   ```bash
   python3 qa_agents/cli/experiment_generator.py
   ```

2. **Add Makefile targets:**
   ```bash
   # Add to Makefile
   make experiment-gen
   make swarm-daemon
   ```

3. **Patch executor:**
   - Implement Rust bin handler
   - Implement ingestion paper handler

4. **Launch swarm:**
   ```bash
   make swarm-daemon
   ```

5. **Monitor & iterate:**
   - Watch logs for failures
   - Patch gaps as discovered
   - Celebrate when first experiment completes autonomously! 🎉

---

**Status:** Swarm foundation ready; patching executor now to enable autonomous execution
