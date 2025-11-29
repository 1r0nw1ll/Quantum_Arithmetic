#!/bin/bash
# Ingestion Workflow - Parallel AI Agent Orchestration
# Created: 2025-11-20
# Uses: Gemini (analysis), Codex (code), QALM (QA validation), Claude (orchestration)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "INGESTION WORKFLOW - Multi-AI Parallel Processing"
echo "============================================================"
echo ""

# Task 1: Gemini - Extract and analyze qa_jepa.odt
echo "🤖 Task 1: Gemini analyzing qa_jepa.odt..."
python3 ../qa-in-terminal/qa_terminal_agent.py \
  -p gemini \
  -c qa_contexts/base_context.yaml \
  "Extract and analyze the file ingestion_candidates/qa_jepa.odt. Focus on: 1) How JEPA (Joint Embedding Predictive Architecture) works, 2) Potential connections to QA arithmetic, 3) Whether QA tuples could enhance JEPA embeddings. Save key findings." \
  > /tmp/task1_gemini_jepa.log 2>&1 &
TASK1_PID=$!

# Task 2: Codex - Analyze sum_product_conjecture.pdf structure
echo "💻 Task 2: Codex analyzing sum_product_conjecture.pdf structure..."
python3 ../qa-in-terminal/qa_terminal_agent.py \
  -p codex \
  -c qa_contexts/base_context.yaml \
  "Analyze the PDF file ingestion_candidates/sum_product_conjecture.pdf. Extract: 1) Main theorems, 2) Key formulas, 3) Proofs structure. Cross-reference with qa_toroid_sumproduct.py implementation." \
  > /tmp/task2_codex_sumproduct.log 2>&1 &
TASK2_PID=$!

# Task 3: QALM - Validate Grant's LRT against QA tuples
echo "🔬 Task 3: QALM validating Grant's Logarithmic Right Triangle..."
python3 ../qa-in-terminal/qa_terminal_agent.py \
  -p qalm \
  -c qa_contexts/base_context.yaml \
  "Using QA arithmetic, validate Robert Edward Grant's Logarithmic Right Triangle (1,2,3,5) gives C=12, F=5, G=13. Compute all QA invariants and verify Pythagorean property. Use qa_toroid_sumproduct.py if available." \
  > /tmp/task3_qalm_validation.log 2>&1 &
TASK3_PID=$!

echo ""
echo "⏳ Waiting for parallel tasks to complete..."
echo "   Task 1 (Gemini): PID $TASK1_PID"
echo "   Task 2 (Codex):  PID $TASK2_PID"
echo "   Task 3 (QALM):   PID $TASK3_PID"
echo ""

# Wait for all tasks
wait $TASK1_PID
echo "✅ Task 1 (Gemini) completed"

wait $TASK2_PID
echo "✅ Task 2 (Codex) completed"

wait $TASK3_PID
echo "✅ Task 3 (QALM) completed"

echo ""
echo "============================================================"
echo "RESULTS SUMMARY"
echo "============================================================"
echo ""

echo "--- Task 1: Gemini (qa_jepa.odt) ---"
tail -50 /tmp/task1_gemini_jepa.log
echo ""

echo "--- Task 2: Codex (sum_product PDF) ---"
tail -50 /tmp/task2_codex_sumproduct.log
echo ""

echo "--- Task 3: QALM (LRT validation) ---"
tail -50 /tmp/task3_qalm_validation.log
echo ""

echo "============================================================"
echo "All tasks completed! Check logs in /tmp/task*.log"
echo "============================================================"
