.PHONY: init test docs viz meta scout prioritize plan dispatch review archive help qa_lab_init daily-summary

# QA Bob-iverse Autonomic Research Lab
# Version: v4.0 - Autonomic Science System

# Environment setup
VENV := qa_venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Agent orchestration
AGENTS := scout classifier prioritizer planner dispatcher executor reviewer archivist

# Initialize QA Lab environment
init:
	@echo "🚀 Initializing QA Bob-iverse..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip wheel build
	$(PIP) install -e .
	$(PIP) install pytest mkdocs mkdocs-material networkx matplotlib torch torchvision tqdm pyyaml
	@echo "✅ QA Lab initialized"

# Run all tests
test:
	@echo "🧪 Running QA invariant tests..."
	pytest -q qa_core/tests/
	@echo "✅ Tests passed"

# Build documentation
docs:
	@echo "📚 Building QA documentation..."
	$(PYTHON) -m mkdocs build
	@echo "✅ Docs built"

# Generate visualizations
viz:
	@echo "📊 Generating QA visualizations..."
	$(PYTHON) qa_agents/cli/qa_graphsmith.py
	@echo "📐 Volk–Grant QA Triangle viz..."
	$(PYTHON) qa_agents/cli/volk_triangle_viz.py || true
	@echo "📐 Volk–Grant geometry viz..."
	$(PYTHON) qa_agents/cli/volk_geometry_viz.py || true
	@echo "📈 HI trend plot/summary..."
	$(PYTHON) qa_agents/cli/plot_hi.py || true
	@echo "✅ Visualizations generated"

# Package and publish artifacts with a run report
publish:
	@echo "📦 Publishing artifacts..."
	$(PYTHON) scripts/aggregate_artifacts_delta.py || true
	$(PYTHON) scripts/publish_run.py || true
	@echo "📚 Rebuilding docs..."
	$(MAKE) docs || true
	@echo "✅ Publish complete"

bench-e8:
	@echo "🏎️ Benchmarking E8 alignment (Rust path)..."
	$(PYTHON) scripts/bench_e8_alignment.py || true

# Build Rust and run all benches relevant to porting work
.PHONY: port-rust-all
port-rust-all: rust-py-build
	@echo "📏 Benchmarking QA invariants (Python vs Rust)..."
	$(PYTHON) scripts/bench_qa_invariants.py || true
	@echo "🌊 Benchmarking streaming fast-prune..."
	$(PYTHON) scripts/bench_fast_prune_stream.py || true
	@echo "🎼 Benchmarking harmonic index..."
	$(PYTHON) scripts/bench_harmonic_index.py || true

# Run full meta-pipeline (SpecLock → tests → viz → docs)
meta: speclock test viz docs fast-eval
	@echo "🎯 QA Meta-pipeline complete"

# Generate datasets
data:
	@echo "🧬 Generating datasets..."
	$(PYTHON) scripts/generate_volk_triangle_dataset.py || true
	@echo "✅ Data generated"

# Include data in meta
meta: data

metrics:
	@echo "📈 Emitting metrics summary..."
	$(PYTHON) scripts/simulate_hi_logging.py || true
	$(PYTHON) qa_agents/cli/emit_metrics_summary.py || true
	@echo "🧪 Running fast-path evaluation..."
	$(PYTHON) qa_fast_eval.py || true
	@echo "🧠 Mining vault for fast-path suggestions..."
	$(PYTHON) scripts/mine_vault_for_fastpath.py || true
	@echo "⚙️  Applying fast-path suggestions (auto-accept if improvement)..."
	$(PYTHON) scripts/fastpath_auto_apply.py || true
	@echo "📰 Writing daily summary..."
	QA_FORCE_SUMMARY=1 $(PYTHON) scripts/daily_summary.py || true
	@echo "📊 Appending fastpath trends..."
	$(PYTHON) scripts/append_fastpath_trends.py || true
	@echo "📈 Plotting fastpath trends..."
	$(PYTHON) scripts/plot_fastpath_trends.py || true
	@echo "✅ Metrics summary emitted"

# Run metrics with NumPy baseline measured by system python (outside venv).
# Step 1: save NumPy-only baseline using system python.
# Step 2: run eval in venv using the saved baseline to compute speedup.
.PHONY: metrics-numpy-baseline
metrics-numpy-baseline:
	@echo "🧮 Measuring NumPy baseline with system python..."
	QA_SAVE_BASELINE_ONLY=1 python3 qa_fast_eval.py || true
	@echo "🏎️ Running eval with baseline override (venv)..."
	QA_USE_BASELINE_FROM=artifacts/evals/fastpath_baseline_np.json $(PYTHON) qa_fast_eval.py || true
	@echo "🧠 Mining vault for fast-path suggestions..."
	$(PYTHON) scripts/mine_vault_for_fastpath.py || true
	@echo "⚙️  Applying fast-path suggestions (auto-accept if improvement)..."
	$(PYTHON) scripts/fastpath_auto_apply.py || true
	@echo "📰 Writing daily summary..."
	QA_FORCE_SUMMARY=1 $(PYTHON) scripts/daily_summary.py || true
	@echo "📊 Appending fastpath trends..."
	$(PYTHON) scripts/append_fastpath_trends.py || true
	@echo "📈 Plotting fastpath trends..."
	$(PYTHON) scripts/plot_fastpath_trends.py || true
	@echo "✅ Metrics (numpy-baseline mode) complete"

# Agent orchestration commands
# Agent orchestration commands
scout:
	@echo "🔍 Scout: Mining for new tasks..."
	$(PYTHON) qa_agents/cli/scout.py

prioritize:
	@echo "⚖️ Prioritizer: Computing task priorities..."
	$(PYTHON) qa_agents/cli/prioritizer.py

plan:
	@echo "📋 Planner: Creating execution plans..."
	$(PYTHON) qa_agents/cli/planner.py

builder:
	@echo "🧰 Agent Builder: Scaffolding requested agents..."
	$(PYTHON) qa_agents/cli/agent_builder.py

self_improve:
	@echo "🧠 Self-Improver: Generating self-upgrade tasks..."
	$(PYTHON) qa_agents/cli/self_improver.py

sandbox_test:
	@echo "🧪 Running sandbox test (no changes applied)..."
	echo '{"proposed_files": []}' | $(PYTHON) scripts/sandbox_test.py

obsidian_ingest:
	@echo "📥 Ingesting Obsidian vault..."
	$(PYTHON) qa_agents/cli/obsidian_ingest.py || true

clean_backlog:
	@echo "🧹 Cleaning vendor backlog from active tasks..."
	$(PYTHON) qa_agents/cli/clean_backlog.py

dispatch:
	@echo "🚀 Dispatcher: Assigning tasks to agents..."
	$(PYTHON) qa_agents/cli/dispatcher.py

review:
	@echo "👀 Reviewer: Validating completed work..."
	$(PYTHON) qa_agents/cli/reviewer.py

archive:
	@echo "📦 Archivist: Updating knowledge base..."
	$(PYTHON) qa_agents/cli/archivist.py

# SpecLock verification
speclock:
	@echo "🔒 Verifying SpecLock integrity..."
	bash qa_agents/cli/speclock.sh

# Execute tasks assigned by dispatcher
executor:
	@echo "🛠️ Executor: Processing active tasks..."
	$(PYTHON) qa_agents/cli/executor.py

# AI Co-Scientist: Generate experiment tasks from roadmap
experiment-gen:
	@echo "🧠 AI Co-Scientist: Generating experiment tasks..."
	$(PYTHON) qa_agents/cli/experiment_generator.py

# Swarm intelligence upgrades (v2.0)
dashboard:
	@echo "📊 Generating swarm dashboard..."
	$(PYTHON) scripts/swarm_dashboard.py

introspect:
	@echo "🔍 Running swarm introspection..."
	$(PYTHON) qa_agents/cli/swarm_introspector.py

rust-promote:
	@echo "🦀 Analyzing Rust promotion opportunities..."
	$(PYTHON) qa_agents/cli/rust_promoter.py

# Evolution modules (v3.0 - Research Autonomy)
research-director:
	@echo "🎯 Research Director: Setting research agenda..."
	$(PYTHON) qa_agents/cli/research_director.py

architect:
	@echo "🏗️  QA Architect: Analyzing system architecture..."
	$(PYTHON) qa_agents/cli/qa_architect.py

alpha-synthesis:
	@echo "🧠 AlphaSynthesis: Cross-paper reasoning..."
	$(PYTHON) qa_agents/cli/alpha_synthesis.py

# Multi-node cluster management (v3.5 - Distributed Computing)
cluster-monitor:
	@echo "🌐 Cluster Monitor: Multi-node swarm monitoring..."
	$(PYTHON) scripts/cluster_monitor.py

cluster-dispatch:
	@echo "🌐 Cluster Dispatcher: Intelligent task distribution..."
	$(PYTHON) qa_agents/cli/cluster_dispatcher.py

cluster-dashboard: cluster-monitor cluster-dispatch
	@echo "🌐 Multi-node cluster dashboard complete"

# Full agent loop (experiment-gen → scout → prioritize → plan → builder → dispatch → execute → review → archive → upgrades → evolution)
agent_loop: experiment-gen scout prioritize plan builder self_improve dispatch executor review archive port-rust-all metrics-numpy-baseline dashboard introspect rust-promote research-director architect alpha-synthesis
	@echo "🔄 Agent loop complete"

# Autonomous swarm daemon (24/7 execution)
swarm-daemon:
	@echo "🔁 Starting autonomous swarm (Ctrl+C to stop)..."
	@while true; do \
		$(MAKE) agent_loop || true; \
		sleep 3600; \
	done

# QA CLI entrypoint
qa_cli:
	@echo "💻 Starting QA CLI..."
	$(PYTHON) qa_agents/cli/qa_cli.py

# Bootstrap QA Lab from scratch
qa_lab_init: init
	@echo "🏗️ Bootstrapping QA Bob-iverse..."
	mkdir -p tasks/inbox tasks/active tasks/completed projects boards artifacts/plots artifacts/evals artifacts/proofs logs context
	cp qa_agents/templates/context/* context/
	cp qa_agents/templates/projects/* projects/
	@echo "✅ QA Lab bootstrapped"

# Clean artifacts
clean:
	rm -rf artifacts/plots/* artifacts/evals/* artifacts/proofs/* logs/*.log

# Help
help:
	@echo "QA Bob-iverse Autonomic Research Lab v4.0"
	@echo ""
	@echo "Available targets:"
	@echo "  init         - Initialize Python environment"
	@echo "  test         - Run QA invariant tests"
	@echo "  docs         - Build documentation"
	@echo "  viz          - Generate visualizations"
	@echo "  meta         - Run full meta-pipeline"
	@echo "  scout        - Mine for new tasks"
	@echo "  prioritize   - Compute task priorities"
	@echo "  plan         - Create execution plans"
	@echo "  dispatch     - Assign tasks to agents"
	@echo "  review       - Validate completed work"
	@echo "  archive      - Update knowledge base"
	@echo "  agent_loop   - Run full agent orchestration"
	@echo "  executor     - Execute assigned tasks"
	@echo "  speclock     - Verify SpecLock integrity"
	@echo "  qa_cli       - Start QA command-line interface"
	@echo "  qa_lab_init  - Bootstrap complete QA Lab"
	@echo "  rust-py-build - Build Rust PyO3 module and place importable .so"
	@echo "  qa-theory    - Run benchmark + export Overleaf-ready .tex"
	@echo "  fastpath-demo - Run E8 fast rerank demo (requires E8 roots)"
	@echo "  prepare-e8-roots - Normalize E8 roots to unit vectors"
	@echo "  fast-prune-pipeline - Run gates → QA → E8 pipeline demo"
	@echo "  fast-prune-stream   - Streaming fast prune on huge N"
	@echo "  fast-eval    - One-button fast-path evaluation suite"
	@echo "  qa-plots-bench - Run bench + plot QA vs SGD"
	@echo "  qa-plots-pcn   - Run PCN demos + plot theta compare"
	@echo "  qa-plots-jepa  - Run JEPA demos + plot convergence"
	@echo "  qa-runs-raman  - Train Raman classifier (SGD vs HGD)"
	@echo "  qa-plots-raman - Plot Raman classifier curves"
	@echo "  qa-paper       - Generate Overleaf-ready section + figures bundle"
	@echo "  daemon       - Run the agent loop continuously (24/7)"
	@echo "  entities-extract - Extract canonical entities (KG)"
	@echo "  entities-encode  - Encode entities into QA tuples (KG)"
	@echo "  graph-build      - Build QA knowledge graph (KG)"
	@echo "  graph-viz        - Render graph visualization (KG)"
	@echo "  phase1-kg        - Run full Phase 1 KG pipeline"
	@echo "  clean        - Clean artifacts"
	@echo "  help         - Show this help"

# Run the agent loop continuously
daemon:
	@echo "🔁 Starting agent daemon (Ctrl+C to stop)..."
	bash scripts/agent_daemon.sh

# Build the Rust PyO3 extension and place an importable shared object at repo root.
# Requires Rust toolchain and network to fetch crates on first build.
rust-py-build:
	@echo "🦀 Building Rust → Python extension (qa_lab_rs)..."
	@if [ "${QA_ENABLE_PORTABLE_SIMD}" = "1" ]; then \
		echo "ℹ️  Enabling portable-simd feature"; \
		cargo build --release --features portable_simd; \
	else \
		cargo build --release; \
	fi
	@# Copy to importable location if built
	@[ -f target/release/libqa_lab_rs.so ] && cp -f target/release/libqa_lab_rs.so qa_lab_rs.so || true
	@[ -f target/release/qa_lab_rs.dll ] && cp -f target/release/qa_lab_rs.pyd qa_lab_rs.pyd || true
	@[ -f target/release/qa_lab_rs.dylib ] && cp -f target/release/libqa_lab_rs.dylib qa_lab_rs.so || true
	@echo "✅ If build succeeded, import via: 'import qa_lab_rs; qa_lab_rs.ping()'"

.PHONY: qa-theory
qa-theory:
	@echo "🏎️ Running speed benchmarks (Rust)..."
	@rm -f target/qa_benchmarks/summary.csv target/qa_benchmarks/summary.json
	cargo run --release --bin qa_speed_benchmark -- --dim 16 --lr 0.2 --lr-hgd 0.4 --tol 1e-10 --max-steps 2000 --repeats 5 --hgd-gain 1.8 --hgd-floor 0.3
	@echo "📝 Exporting Overleaf section..."
	cargo run --release --bin qa_theory_export
	@echo "✅ LaTeX section ready: docs/qa_training_compute_section.tex"

.PHONY: rust-py-build-simd
rust-py-build-simd:
	@echo "🦀 Building Rust (portable-simd on)..."
	cargo build --release --features portable_simd
	@[ -f target/release/libqa_lab_rs.so ] && cp -f target/release/libqa_lab_rs.so qa_lab_rs.so || true
	@[ -f target/release/qa_lab_rs.dll ] && cp -f target/release/qa_lab_rs.pyd qa_lab_rs.pyd || true
	@[ -f target/release/qa_lab_rs.dylib ] && cp -f target/release/libqa_lab_rs.dylib qa_lab_rs.so || true
	@echo "✅ portable-simd build ready"

fastpath-demo:
	@echo "🚀 Running E8 fast rerank demo..."
	$(PYTHON) scripts/fast_rerank_demo.py || true

prepare-e8-roots:
	@echo "🧮 Normalizing E8 roots..."
	$(PYTHON) scripts/prepare_e8_roots.py --in qa_lab/data/e8_roots.npy --out qa_lab/data/e8_roots_unit.npy || true

fast-prune-pipeline:
	@echo "🏎️ Running fast prune pipeline (gates → QA → E8)..."
	$(PYTHON) scripts/fast_prune_pipeline.py || true

fast-prune-stream:
	@echo "🌊 Running streaming fast prune..."
	$(PYTHON) scripts/fast_prune_stream.py || true

fast-eval:
	@echo "🧪 Running fast-path evaluation suite..."
	$(PYTHON) qa_fast_eval.py || true

daily-summary:
	@echo "📰 Writing daily summary + trends..."
	$(PYTHON) scripts/daily_summary.py || true
	$(PYTHON) scripts/append_fastpath_trends.py || true

# --- Knowledge Graph (Phase 1) -------------------------------------------------

.PHONY: entities-extract entities-encode graph-build graph-viz phase1-kg

entities-extract:
	@echo "📥 Extracting canonical entities from lexicon..."
	python3 ../qa_entity_extractor.py --in ../private/QAnotes/research_log_lexicon.md --out ../artifacts/knowledge/qa_entities.json || true

entities-encode:
	@echo "🔢 Encoding entities into QA tuples..."
	python3 ../qa_entity_encoder.py --in ../artifacts/knowledge/qa_entities.json --overrides ../qa_entity_overrides.yaml --out ../artifacts/knowledge/qa_entity_encodings.json || true

graph-build:
	@echo "🕸️ Building QA knowledge graph..."
	python3 ../qa_knowledge_graph.py --enc ../artifacts/knowledge/qa_entity_encodings.json --out ../artifacts/knowledge/qa_knowledge_graph.graphml || true

graph-viz:
	@echo "🖼️ Rendering QA knowledge graph visualization..."
	python3 ../qa_graph_viz.py --graph ../artifacts/knowledge/qa_knowledge_graph.graphml --out ../artifacts/plots/qa_knowledge_graph.png || true

phase1-kg: entities-extract entities-encode graph-build graph-viz
	@echo "✅ Phase 1 Knowledge Graph pipeline complete"

.PHONY: qa-plots-bench qa-plots-pcn qa-plots-jepa
qa-plots-bench:
	@echo "🏎️ Running speed benchmarks (Rust) and plotting..."
	@rm -f target/qa_benchmarks/summary.csv target/qa_benchmarks/summary.json
	cargo run --release --bin qa_speed_benchmark -- --dim 16 --lr 0.2 --lr-hgd 0.4 --tol 1e-10 --max-steps 2000 --repeats 5 --hgd-gain 1.8 --hgd-floor 0.3
	@mkdir -p plots
	python3 scripts/qa_plot_benchmarks.py --csv target/qa_benchmarks/summary.csv --out plots/qa_benchmarks.png

qa-plots-pcn:
	@echo "🎵 Running PCN theta=0 and theta=pi demos + plotting..."
	cargo run --release --bin qa_pcn_sheaf_demo -- --nodes 8 --theta 0 --steps 500 --lr 0.2 --alpha 0.1 --opt hgd --csv target/qa_pcn/pcn_theta_0.csv
	cargo run --release --bin qa_pcn_sheaf_demo -- --nodes 8 --theta pi --steps 500 --lr 0.2 --alpha 0.1 --opt hgd --csv target/qa_pcn/pcn_theta_pi.csv
	@mkdir -p plots
	python3 scripts/qa_plot_pcn.py --csv-theta-0 target/qa_pcn/pcn_theta_0.csv --csv-theta-pi target/qa_pcn/pcn_theta_pi.csv --out plots/qa_pcn_theta_compare.png

qa-plots-jepa:
	@echo "🧪 Running JEPA demos (SGD vs HGD) + plotting..."
	cargo run --release --bin qa_jepa_demo -- --dim-x 16 --dim-z 12 --epochs 30 --lr 0.05 --opt sgd --batch-size 32 --log-csv target/qa_jepa/jepa_sgd.csv
	cargo run --release --bin qa_jepa_demo -- --dim-x 16 --dim-z 12 --epochs 30 --lr 0.05 --opt hgd --batch-size 32 --log-csv target/qa_jepa/jepa_hgd.csv
	@mkdir -p plots
	python3 scripts/qa_plot_jepa.py --csv-sgd target/qa_jepa/jepa_sgd.csv --csv-hgd target/qa_jepa/jepa_hgd.csv --out plots/qa_jepa_convergence.png

.PHONY: qa-runs-raman qa-plots-raman
qa-runs-raman:
	@echo "🧪 Training Raman classifier (SGD vs HGD)..."
	cargo run --release --bin qa_raman_demo -- --feat-mode grid+qa --epochs 50 --batch-size 32 --opt sgd --log-csv target/qa_raman/raman_sgd.csv
	cargo run --release --bin qa_raman_demo -- --feat-mode grid+qa --epochs 50 --batch-size 32 --opt hgd --log-csv target/qa_raman/raman_hgd.csv

qa-plots-raman: qa-runs-raman
	@mkdir -p plots
	python3 scripts/qa_plot_raman.py --csv-sgd target/qa_raman/raman_sgd.csv --csv-hgd target/qa_raman/raman_hgd.csv --out plots/qa_raman_accuracy.png

.PHONY: qa-paper qa-paper-bundle
qa-paper: qa-theory qa-plots-bench qa-plots-pcn qa-plots-jepa qa-plots-raman qa-paper-bundle
	@echo "📄 QA paper artifacts (synthetic + Raman) generated in artifacts/overleaf"

qa-paper-bundle:
	@mkdir -p artifacts/overleaf
	# LaTeX section
	@cp docs/qa_training_compute_section.tex artifacts/overleaf/ 2>/dev/null || true
	# Figures
	@cp plots/qa_benchmarks.png artifacts/overleaf/ 2>/dev/null || true
	@cp plots/qa_pcn_theta_compare.png artifacts/overleaf/ 2>/dev/null || true
	@cp plots/qa_jepa_convergence.png artifacts/overleaf/ 2>/dev/null || true
	@cp plots/qa_raman_accuracy.png artifacts/overleaf/ 2>/dev/null || true
	# Raman LaTeX subsection (optional)
	@cp docs/qa_raman_section.tex artifacts/overleaf/ 2>/dev/null || true
	# Readme
	@cp docs/README_PAPER.md artifacts/overleaf/README_PAPER.md 2>/dev/null || true
	# Optional tarball for upload/archival
	@tar -czf artifacts/qa_overleaf_bundle.tar.gz -C artifacts/overleaf . 2>/dev/null || true

# Node self-optimization
node-self-optimize:
	@echo "🔧 Optimizing node for local hardware..."
	$(PYTHON) qa_agents/cli/node_self_optimizer.py

