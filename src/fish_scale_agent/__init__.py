"""Fish Scale Agent - LLM agent for automated tubercle detection.

This package implements an agentic workflow where an LLM controls the
fish-scale-ui application to detect tubercles in SEM images of fish scales.
"""

__version__ = "0.1.2"
__version_date__ = "2026-01-14T18:30:00Z"

from .runner import TubercleDetectionAgent
from .providers.base import AgentLLMProvider
from .prompts import SYSTEM_PROMPT
from .extraction_optimizer import (
    ExtractionOptimizer,
    OptimizationState,
    TrialRecord,
    OPTIMIZATION_TOOLS,
    OPTIMIZER_SYSTEM_PROMPT,
    is_duplicate,
)

__all__ = [
    'TubercleDetectionAgent',
    'AgentLLMProvider',
    'SYSTEM_PROMPT',
    'ExtractionOptimizer',
    'OptimizationState',
    'TrialRecord',
    'OPTIMIZATION_TOOLS',
    'OPTIMIZER_SYSTEM_PROMPT',
    'is_duplicate',
]
