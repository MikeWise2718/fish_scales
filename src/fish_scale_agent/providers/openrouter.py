"""OpenRouter provider for the fish scale agent using OpenAI-compatible API."""

import json
import os
from typing import Any, Callable

import httpx

from .base import (
    AgentLLMProvider,
    ToolDefinition,
    ToolCall,
    AgentMessage,
    AgentIteration,
)


def _convert_tool_to_openai(tool: ToolDefinition) -> dict:
    """Convert our ToolDefinition to OpenAI tool format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters if tool.parameters else {"type": "object", "properties": {}},
        },
    }


# Pricing per million tokens (approximate, varies by model)
# See https://openrouter.ai/docs#models for current pricing
# Prices may fluctuate - check OpenRouter for current rates
MODEL_PRICING = {
    # Anthropic models via OpenRouter
    "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    # OpenAI models
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4-turbo": {"input": 10.0, "output": 30.0},
    # Google models
    "google/gemini-pro-1.5": {"input": 2.5, "output": 7.5},
    "google/gemini-flash-1.5": {"input": 0.075, "output": 0.30},
    # Mistral models (with vision)
    "mistralai/pixtral-large-2411": {"input": 2.0, "output": 6.0},
    "mistralai/pixtral-12b": {"input": 0.125, "output": 0.125},
    "mistralai/mistral-small-3.1-24b-instruct": {"input": 0.10, "output": 0.30},
    "mistralai/mistral-small-3.1-24b-instruct:free": {"input": 0.0, "output": 0.0},
    # Qwen models (with vision)
    "qwen/qwen3-vl-235b-a22b-instruct": {"input": 0.50, "output": 1.50},
    "qwen/qwen3-vl-32b-instruct": {"input": 0.02, "output": 0.0},
    "qwen/qwen2.5-vl-72b-instruct": {"input": 0.20, "output": 0.20},
    "qwen/qwen2.5-vl-32b-instruct": {"input": 0.10, "output": 0.10},
    "qwen/qwen2.5-vl-72b-instruct:free": {"input": 0.0, "output": 0.0},
    "qwen/qwen2.5-vl-32b-instruct:free": {"input": 0.0, "output": 0.0},
    # xAI Grok models (with vision)
    "x-ai/grok-4": {"input": 3.0, "output": 15.0},
    "x-ai/grok-4-fast": {"input": 0.20, "output": 0.50},
    "x-ai/grok-4.1-fast": {"input": 0.20, "output": 0.50},
    "x-ai/grok-2-vision-1212": {"input": 2.0, "output": 10.0},
    "x-ai/grok-vision-beta": {"input": 5.0, "output": 15.0},
    # Z.ai / Zhipu models (Chinese)
    "z-ai/glm-4.5": {"input": 0.11, "output": 0.28},
    "z-ai/glm-4.5-air": {"input": 0.05, "output": 0.15},
    "z-ai/glm-4.6v": {"input": 0.20, "output": 0.50},  # Vision model
    # DeepSeek (text only - no vision, listed for reference)
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek/deepseek-chat-v3.1": {"input": 0.14, "output": 0.28},
}

# Default model - good balance of capability and cost
DEFAULT_MODEL = "anthropic/claude-sonnet-4"


class OpenRouterAgentProvider(AgentLLMProvider):
    """OpenRouter-based agent provider using OpenAI-compatible API.

    OpenRouter provides access to many LLMs through a unified API.
    See https://openrouter.ai/docs for available models.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        """Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key. If None, uses OPENROUTER_API_KEY env var.
            model: Model to use (default: anthropic/claude-sonnet-4)
            site_url: Optional URL for your site (for OpenRouter rankings)
            site_name: Optional name for your app (for OpenRouter rankings)
        """
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY env var or pass api_key."
            )
        self._model_name = model
        self._site_url = site_url or "https://github.com/fish-scale-analysis"
        self._site_name = site_name or "Fish Scale Analysis Agent"

        # Usage tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._iteration_count = 0

        # HTTP client for API calls
        self._client = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": self._site_url,
                "X-Title": self._site_name,
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "openrouter"

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
            "cost_estimated": not pricing_known,
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
        """Run the agent loop using OpenRouter's OpenAI-compatible API.

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
        # Convert tools to OpenAI format
        openai_tools = [_convert_tool_to_openai(t) for t in tools]

        # Build message history
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        text_response = ""
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Build request payload
            payload = {
                "model": self._model_name,
                "messages": messages,
                "tools": openai_tools,
                "max_tokens": 4096,
            }

            # Call OpenRouter API
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # Track usage
            self._iteration_count += 1
            if "usage" in data:
                self._total_input_tokens += data["usage"].get("prompt_tokens", 0)
                self._total_output_tokens += data["usage"].get("completion_tokens", 0)

            # Parse response
            choice = data["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "")

            tool_calls = []
            text_response = message.get("content", "") or ""

            # Check for tool calls
            if message.get("tool_calls"):
                for tc in message["tool_calls"]:
                    if tc["type"] == "function":
                        tool_calls.append(ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {},
                        ))

            # Build iteration info
            iter_messages = []
            if text_response:
                iter_messages.append(AgentMessage(
                    role="assistant",
                    content=text_response,
                ))

            done = finish_reason == "stop" or len(tool_calls) == 0
            agent_iter = AgentIteration(
                messages=iter_messages,
                tool_calls=tool_calls,
                done=done,
                final_response=text_response if done else None,
            )

            if on_iteration:
                on_iteration(agent_iter)

            # If no tool calls, we're done
            if done:
                return text_response

            # Add assistant message to history
            assistant_msg = {"role": "assistant", "content": text_response}
            if message.get("tool_calls"):
                assistant_msg["tool_calls"] = message["tool_calls"]
            messages.append(assistant_msg)

            # Execute tool calls and collect results
            for tc in tool_calls:
                try:
                    result = tool_executor(tc.name, tc.arguments)

                    # Check if result contains image data (from get_screenshot)
                    if isinstance(result, dict) and "image_data" in result:
                        # For OpenRouter/OpenAI, we need to pass image as a user message
                        # with image_url content type
                        image_b64 = result["image_data"]
                        if image_b64.startswith("data:"):
                            image_url = image_b64
                        else:
                            image_url = f"data:image/png;base64,{image_b64}"

                        width = result.get("width", "unknown")
                        height = result.get("height", "unknown")
                        note = result.get("note", "")
                        text_msg = f"Screenshot captured. Image dimensions: {width}x{height} pixels. {note} Analyze the image to identify tubercles and gaps in the pattern."

                        # Add tool result with image
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_url},
                                },
                                {
                                    "type": "text",
                                    "text": text_msg,
                                },
                            ],
                        })
                    else:
                        # Convert result to string if needed
                        if isinstance(result, (dict, list)):
                            result_str = json.dumps(result, indent=2)
                        else:
                            result_str = str(result)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_str,
                        })
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"Error: {str(e)}",
                    })

        # Max iterations reached
        return text_response or "Max iterations reached without final response."

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
