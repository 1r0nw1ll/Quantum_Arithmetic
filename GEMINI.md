# GEMINI.md: Project Overview

## Directory Overview

This directory contains a multi-faceted research project centered around a novel mathematical framework called the **Quantum Arithmetic (QA) System**. The project has evolved into a production-ready QA lab with a hybrid Python/Rust architecture, focusing on the theoretical foundations of the QA system, its advanced applications in signal processing, and the use of machine learning and algebraic methods for theorem verification.

The research is highly computational, with core QA computations now accelerated by Rust, while Python and PyTorch are used for model development, training, and evaluation, particularly for the specialized language model.

## Key Files

*   `qa_lab/src/lib.rs`: Contains the core QA computations, including invariants, E8 alignment, and Bell tests, implemented in Rust for significant performance acceleration (2-3x speedup over pure Python/NumPy). PyO3 bindings facilitate seamless integration with Python.
*   `qa_model_architecture.py`: Defines the `QALanguageModel`, a custom transformer-based model with specialized layers for "Quantum Arithmetic" (QA).
*   `qa_training_pipeline.py`: Implements the training and evaluation pipeline for the QA model, incorporating features like curriculum learning and mathematical validation.
*   `qa_dataloader.py`: Contains the data loader for the QA training data, which is stored in JSONL format.
*   `qa_data/qa_training_dataset.json`: The main dataset used for training the QA model.
*   `wikitext_train.json`: A dataset for general language model training, used for comparative analysis.
*   `geometrist_v4_gnn.py`: (Deprioritized) A Python script that previously used a Graph Neural Network (GNN) for geometric theorem generation. The focus for theorem verification has shifted to algebraic methods.
*   `pyproject.toml` and `setup.py`: Define the project's dependencies and packaging information.

## Usage and Key Capabilities

This directory is a sophisticated research and development environment. The primary way to interact with the project is by using the `Makefile` and the `qa` command-line interface (CLI) to orchestrate various tasks, leveraging the hybrid Python/Rust architecture.

### Rust Acceleration

Core QA computations, including invariants, E8 alignment, and Bell tests, are now implemented in Rust (`qa_lab/src/lib.rs`) with PyO3 bindings. This provides a 2-3x speedup over previous pure Python/NumPy implementations, enabling real-time checks and more efficient processing.

### Advanced Theorem Verification

The approach to "theorem proving" has evolved from GNN-based geometric theorem generation to **algebraic theorem verification** via Bell tests (CHSH, I3322, Platonic) and QA theorems (8|N, 6|N, Tsirelson bound). These verifications utilize fast Rust kernels for real-time validation.

### Advanced Signal Processing

The project now focuses on advanced signal processing applications, including seismic and EEG classification, incorporating PAC-Bayes bounds for robust analysis.

### Automated Optimization and Research Maturity

The QA Lab operates with an automated "Mine → test → apply" loop, complete with artifact generation, evaluation, and comprehensive logging. The project has reached Phase 2 completion, with a draft ICLR paper, established baseline comparisons (CNN/LSTM), and validation against real-world data.

### Setting up the Environment

To set up the environment, you can use the `make init` command. This will create a Python virtual environment, install the required dependencies, and set up the project for development, including the Rust components.

```bash
make init
```

### QA Command-Line Interface (CLI)

The project includes a command-line interface (CLI) for interacting with the QA Lab. The CLI provides a convenient way to run the various agents and tools.

To use the CLI, you can run the `qa` command from the root of the project. This will show you a list of available commands.

```bash
qa
```

The following commands are available:

*   `qa init`: Initialize the QA Lab environment.
*   `qa test`: Run the QA invariant tests.
*   `qa docs`: Build the project documentation.
*   `qa viz`: Generate QA visualizations.
*   `qa meta`: Run the full meta-pipeline.
*   `qa scout`: Mine for new tasks.
*   `qa prioritize`: Compute task priorities.
*   `qa plan`: Create execution plans.
*   `qa dispatch`: Assign tasks to agents.
*   `qa review`: Validate completed work.
*   `qa archive`: Update the knowledge base.
*   `qa loop`: Run the full agent orchestration loop.
*   `qa speclock`: Verify the SpecLock integrity.
*   `qa status`: Show the QA Lab status.
*   `qa help`: Show the help message.

### Makefile Commands

The `Makefile` provides a set of commands for interacting with the project:

*   `make init`: Initialize the Python environment.
*   `make test`: Run the QA invariant tests.
*   `make docs`: Build the project documentation.
*   `make viz`: Generate QA visualizations.
*   `make meta`: Run the full meta-pipeline (SpecLock → tests → viz → docs).
*   `make scout`: Mine for new tasks.
*   `make prioritize`: Compute task priorities.
*   `make plan`: Create execution plans.
*   `make dispatch`: Assign tasks to agents.
*   `make review`: Validate completed work.
*   `make archive`: Update the knowledge base.
*   `make agent_loop`: Run the full agent orchestration loop.
*   `make speclock`: Verify the SpecLock integrity.
*   `make qa_cli`: Start the QA command-line interface.
*   `make qa_lab_init`: Bootstrap the complete QA Lab.
*   `make clean`: Clean the artifacts.
*   `make help`: Show the help message.

### Development Conventions

*   **Code Style**: The code follows the PEP 8 style guide for Python, and Rust code adheres to standard Rust formatting.
*   **Testing**: The project uses `pytest` for Python tests (located in `qa_core/tests`) and Rust's built-in testing framework for Rust components.
*   **Documentation**: The project is documented through comments in the code and this `GEMINI.md` file. The documentation can be built using the `make docs` command.