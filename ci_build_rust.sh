#!/bin/bash
# CI Build Script for Rust Backend
# Builds qa_lab_rs and runs tests

set -euo pipefail

echo "🔧 Starting Rust CI Build"

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Cargo not found. Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# Build the Rust extension
echo "🏗️  Building Rust extension..."
if [ "${QA_ENABLE_PORTABLE_SIMD:-0}" = "1" ]; then
    echo "ℹ️  Enabling portable-simd feature"
    /home/player2/.cargo/bin/cargo build --release --lib --features portable_simd
else
    /home/player2/.cargo/bin/cargo build --release --lib
fi

# Check if the shared library was created
if [ ! -f "target/release/libqa_lab_rs.so" ]; then
    echo "❌ Rust library not found after build"
    exit 1
fi

echo "✅ Rust library built successfully"

# Copy to project root for Python import
cp -f target/release/libqa_lab_rs.so qa_lab_rs.so

# Run Rust backend tests
echo "🧪 Running Rust backend tests..."
PYTHONPATH=. python3 -m pytest test_rust_backend.py -v

# Run torch-free collector tests
echo "🧪 Running torch-free collector tests..."
PYTHONPATH=. python3 -m pytest test_torch_free_collector.py -v

echo "🎉 All CI checks passed!"
