# Task for Codex Agent: Fix mkdocs Build Failure in Makefile

**Issue:**
The `make meta` command is failing during the "Building QA documentation" step with a "No such file or directory" error for `mkdocs`.

**Error Message:**
```
make: mkdocs: No such file or directory
make: *** [Makefile:32: docs] Error 127
```

**Details:**
-   **File:** `qa_lab/Makefile`
-   The `init` target correctly installs `mkdocs` within the Python virtual environment (`qa_venv`).
-   However, the `docs` target calls `mkdocs build` directly, which attempts to use a system-wide `mkdocs` executable that is not found. It should be calling the `mkdocs` installed in the virtual environment.

**Proposed Fix:**
Modify the `docs` target in `qa_lab/Makefile` to explicitly use the `mkdocs` executable from within the virtual environment by calling it via `$(PYTHON) -m mkdocs build`.

**Specific Change:**
In `qa_lab/Makefile`, change the lines:
```makefile
docs:
	@echo "📚 Building QA documentation..."
	mkdocs build
	@echo "✅ Docs built"
```
to:
```makefile
docs:
	@echo "📚 Building QA documentation..."
	$(PYTHON) -m mkdocs build
	@echo "✅ Docs built"
```

This will ensure that the correct `mkdocs` installation is used, allowing the documentation to build successfully and the `make meta` command to complete.
