"""Base class for LLM providers that run the agent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


class StopAgentLoop(Exception):
    """Exception raised to signal that the agent loop should stop.

    This is a control flow exception used to terminate the agent loop
    from within a tool executor. Providers should re-raise this exception
    rather than catching it as a tool error.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class ToolDefinition:
    """Tool definition for LLM function calling."""
    name: str
    description: str
    parameters: dict  # JSON Schema format


@dataclass
class ToolCall:
    """A tool call made by the LLM."""
    id: str
    name: str
    arguments: dict


@dataclass
class AgentMessage:
    """A message in the agent conversation."""
    role: str  # 'user', 'assistant', 'tool'
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # For tool response messages


@dataclass
class AgentIteration:
    """Result of a single agent iteration."""
    messages: list[AgentMessage]
    tool_calls: list[ToolCall]
    done: bool
    final_response: str | None = None
    # Prompt information (for logging/debugging)
    prompt_content: str | None = None  # Full prompt with base64 truncated
    prompt_size_bytes: int = 0  # Size of full prompt in bytes
    # Response information (for logging/debugging)
    response_json: str | None = None  # Full response as JSON (text + tool calls)


class AgentLLMProvider(ABC):
    """Base class for LLM providers that can run the agent.

    Implementations should handle the specific API calls for their LLM
    provider (Claude, Gemini, OpenRouter, etc.) while exposing a common
    interface for tool-based agent loops.
    """

    @abstractmethod
    async def run_agent_loop(
        self,
        tools: list[ToolDefinition],
        tool_executor: Callable[[str, dict], Any],
        system_prompt: str,
        user_message: str,
        max_iterations: int = 20,
        on_iteration: Callable[[AgentIteration], None] | None = None,
    ) -> str:
        """Run the agent loop with access to tools.

        Args:
            tools: List of available tool definitions
            tool_executor: Function to execute tools: (name, args) -> result
            system_prompt: System instructions for the agent
            user_message: Initial user message/task
            max_iterations: Maximum number of LLM calls
            on_iteration: Optional callback after each iteration

        Returns:
            Final response from the agent
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'gemini', 'claude')."""
        pass
