"""Claude provider for the fish scale agent using the Anthropic SDK."""

import json
import os
from typing import Any, Callable

import anthropic

from .base import (
    AgentLLMProvider,
    ToolDefinition,
    ToolCall,
    AgentMessage,
    AgentIteration,
)


def _convert_tool_to_claude(tool: ToolDefinition) -> dict:
    """Convert our ToolDefinition to Claude tool format."""
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters if tool.parameters else {"type": "object", "properties": {}},
    }


def _truncate_base64(text: str, max_b64_length: int = 100) -> str:
    """Truncate base64 data in text while preserving structure.

    Finds base64 strings (identified by common patterns) and truncates them.
    """
    import re
    # Pattern to match base64 data (long strings of base64 characters)
    # Matches strings that look like base64 (alphanumeric + /+=, at least 200 chars)
    b64_pattern = r'([A-Za-z0-9+/=]{200,})'

    def replacer(match):
        b64 = match.group(1)
        if len(b64) > max_b64_length:
            return f"{b64[:50]}...[{len(b64)} bytes base64 truncated]...{b64[-20:]}"
        return b64

    return re.sub(b64_pattern, replacer, text)


def _serialize_prompt(system_prompt: str, tools: list, messages: list) -> tuple[str, int]:
    """Serialize the prompt components and calculate size.

    Returns:
        Tuple of (truncated_content, full_size_bytes)
    """
    # Build full prompt representation
    full_prompt = {
        "system": system_prompt,
        "tools": tools,
        "messages": messages,
    }
    full_json = json.dumps(full_prompt, indent=2, default=str)
    full_size = len(full_json.encode('utf-8'))

    # Truncate base64 for display
    truncated_json = _truncate_base64(full_json)

    return truncated_json, full_size


# Pricing per million tokens (as of 2025)
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-haiku-3-5-20241022": {"input": 0.80, "output": 4.0},
}


class ClaudeAgentProvider(AgentLLMProvider):
    """Claude-based agent provider using tool calling.

    Uses the Anthropic SDK for Claude API access.
    Supports Claude Sonnet for cost-effective agent loops.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize the Claude provider.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Model to use (default: claude-sonnet-4-20250514)
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )
        self._client = anthropic.Anthropic(api_key=self._api_key)
        self._model_name = model

        # Usage tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._iteration_count = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "claude"

    def get_usage(self) -> dict:
        """Get current usage statistics.

        Returns:
            Dict with input_tokens, output_tokens, total_tokens, cost_usd, iterations
        """
        pricing_known = self._model_name in MODEL_PRICING
        pricing = MODEL_PRICING.get(self._model_name, {"input": 3.0, "output": 15.0})
        input_cost = (self._total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self._total_output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "cost_usd": total_cost,
            "cost_estimated": not pricing_known,  # True if using fallback pricing
            "iterations": self._iteration_count,
            "model": self._model_name,
        }

    def reset_usage(self):
        """Reset usage counters."""
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._iteration_count = 0

    async def run_agent_loop(
        self,
        tools: list[ToolDefinition],
        tool_executor: Callable[[str, dict], Any],
        system_prompt: str,
        user_message: str,
        max_iterations: int = 20,
        on_iteration: Callable[[AgentIteration], None] | None = None,
    ) -> str:
        """Run the agent loop using Claude tool calling.

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
        # Convert tools to Claude format
        claude_tools = [_convert_tool_to_claude(t) for t in tools]

        # Build message history
        messages = [{"role": "user", "content": user_message}]

        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Call Claude API
            response = self._client.messages.create(
                model=self._model_name,
                max_tokens=4096,
                system=system_prompt,
                tools=claude_tools,
                messages=messages,
            )

            # Track usage
            self._iteration_count += 1
            if hasattr(response, 'usage') and response.usage:
                self._total_input_tokens += response.usage.input_tokens
                self._total_output_tokens += response.usage.output_tokens

            # Parse response
            tool_calls = []
            text_response = ""

            for block in response.content:
                if block.type == "text":
                    text_response += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if block.input else {},
                    ))

            # Build iteration info
            iter_messages = []
            if text_response:
                iter_messages.append(AgentMessage(
                    role="assistant",
                    content=text_response,
                ))

            # Serialize prompt for logging (with base64 truncated)
            prompt_content, prompt_size = _serialize_prompt(
                system_prompt, claude_tools, messages
            )

            # Serialize full response as JSON (text + tool calls)
            response_data = {
                "text": text_response if text_response else None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                    for tc in tool_calls
                ],
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens if response.usage else 0,
                    "output_tokens": response.usage.output_tokens if response.usage else 0,
                } if hasattr(response, 'usage') else None,
            }
            response_json = json.dumps(response_data, indent=2)

            done = response.stop_reason == "end_turn" or len(tool_calls) == 0
            agent_iter = AgentIteration(
                messages=iter_messages,
                tool_calls=tool_calls,
                done=done,
                final_response=text_response if done else None,
                prompt_content=prompt_content,
                prompt_size_bytes=prompt_size,
                response_json=response_json,
            )

            if on_iteration:
                on_iteration(agent_iter)

            # If no tool calls, we're done
            if done:
                return text_response

            # Add assistant message to history
            messages.append({"role": "assistant", "content": response.content})

            # Execute tool calls and collect results
            tool_results = []
            for tc in tool_calls:
                try:
                    result = tool_executor(tc.name, tc.arguments)

                    # Check if result contains image data (from get_screenshot)
                    if isinstance(result, dict) and "image_data" in result:
                        # Pass image to Claude as vision input
                        image_b64 = result["image_data"]
                        # Strip data URI prefix if present
                        if image_b64.startswith("data:"):
                            image_b64 = image_b64.split(",", 1)[1]

                        # Build text message with dimensions
                        width = result.get("width", "unknown")
                        height = result.get("height", "unknown")
                        note = result.get("note", "")
                        text_msg = f"Screenshot captured. Image dimensions: {width}x{height} pixels. {note} Analyze the image to identify tubercles and gaps in the pattern."

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_b64,
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": text_msg
                                }
                            ],
                        })
                    else:
                        # Convert result to string if needed
                        if isinstance(result, (dict, list)):
                            result_str = json.dumps(result, indent=2)
                        else:
                            result_str = str(result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result_str,
                        })
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": f"Error: {str(e)}",
                        "is_error": True,
                    })

            # Add tool results to history
            messages.append({"role": "user", "content": tool_results})

        # Max iterations reached
        return text_response or "Max iterations reached without final response."
