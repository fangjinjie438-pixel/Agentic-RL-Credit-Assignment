"""CPU procurement environment; session imports native pinned ECom tools lazily.

Consumers use ProcurementEnv with a split-scoped Catalog. No GPU or model imports.
"""

from .catalog import Catalog, build_catalog, load_tasks
from .session import ProcurementEnv, StepResult

__all__ = ["Catalog", "build_catalog", "load_tasks", "ProcurementEnv", "StepResult"]
