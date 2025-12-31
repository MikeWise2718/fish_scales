"""Fish Scale Agent - LLM agent for automated tubercle detection.

This package implements an agentic workflow where an LLM controls the
fish-scale-ui application to detect tubercles in SEM images of fish scales.
"""

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
