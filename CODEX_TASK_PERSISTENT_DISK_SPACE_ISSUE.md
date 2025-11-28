# Task for Codex Agent: Persistent Critical System Error - No Disk Space

**Issue:**
The `make init` command continues to fail with `OSError: [Errno 28] No space left on device`, even after clearing the pip cache. This is preventing the successful setup of the Python virtual environment and installation of project dependencies.

**Error Message:**
```
OSError: [Errno 28] No space left on device
```

**Details:**
-   The error occurs during the download and installation of large Python packages, specifically `nvidia_nccl_cu12` (part of the `torch` dependency chain).
-   `df -h` indicates ample disk space on the main filesystem and `/tmp`.
-   The pip cache was purged, freeing up significant space, but the error persists.
-   This suggests a deeper, persistent system-level issue with disk write operations for large files, potentially related to temporary file system limits, user-specific temporary directories, or container/sandbox resource constraints.

**Impact:**
-   The Python virtual environment cannot be fully set up.
-   `make meta` (which depends on the virtual environment) cannot complete, blocking the generation of evaluation artifacts and documentation.
-   This directly impacts the ability to run and test the QA Lab's Python components, including the integration with the Rust backend.

**Required Action (User Intervention):**
The user needs to investigate and resolve the underlying system-level disk write issue. This may involve:
-   Checking for other temporary directories that might be full.
-   Verifying user write permissions in relevant directories.
-   Investigating container/sandbox resource limits if applicable.

**Next Steps (After System Issue is Resolved):**
1.  Re-run `make init` in `qa_lab` directory.
2.  Once `make init` completes successfully, re-run `make meta` in `qa_lab` directory.
