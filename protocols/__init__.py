"""qa_lab.protocols — frozen QA Lab communication protocol."""
from .schemas import (
    SCHEMA_VERSIONS, VALID_TASK_TYPES, VALID_VERDICTS, VALID_ORBIT_FAMILIES,
    make_task, validate_task,
    make_agent_spec, validate_agent_spec,
    make_spawn_spec, validate_spawn_spec,
    make_kernel_trace, validate_kernel_trace,
)

__all__ = [
    "SCHEMA_VERSIONS", "VALID_TASK_TYPES", "VALID_VERDICTS", "VALID_ORBIT_FAMILIES",
    "make_task", "validate_task",
    "make_agent_spec", "validate_agent_spec",
    "make_spawn_spec", "validate_spawn_spec",
    "make_kernel_trace", "validate_kernel_trace",
]
