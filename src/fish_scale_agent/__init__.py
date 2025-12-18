"""Fish Scale Agent - LLM agent for automated tubercle detection.

This package implements an agentic workflow where an LLM controls the
fish-scale-ui application to detect tubercles in SEM images of fish scales.
"""

from .runner import TubercleDetectionAgent
from .providers.base import AgentLLMProvider
from .prompts import SYSTEM_PROMPT

__all__ = ['TubercleDetectionAgent', 'AgentLLMProvider', 'SYSTEM_PROMPT']
