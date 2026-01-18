"""Ollama provider for the fish scale agent using OpenAI-compatible API."""

import json
import os
import re
from typing import Any, Callable

import httpx

from .base import (
    AgentLLMProvider,
    StopAgentLoop,
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


def _truncate_base64(text: str, max_b64_length: int = 100) -> str:
    """Truncate base64 data in text while preserving structure.

    Finds base64 strings (identified by common patterns) and truncates them.
    """
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


# Default model - llama3.2-vision is a common vision-capable model for Ollama
DEFAULT_MODEL = "llama3.2-vision"


class OllamaAgentProvider(AgentLLMProvider):
    """Ollama-based agent provider using OpenAI-compatible API.

    Ollama provides local LLM inference with an OpenAI-compatible API endpoint.
    See https://ollama.ai/docs for setup and available models.

    Environment variables:
        OLLAMA_HOST: Base URL for Ollama server (default: http://localhost:11434)
        OLLAMA_API_KEY: Optional API key for authenticated Ollama instances
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str | None = None,
    ):
        """Initialize the Ollama provider.

        Args:
            api_key: Optional API key. If None, uses OLLAMA_API_KEY env var.
                     Ollama doesn't require an API key by default.
            model: Model to use (default: llama3.2-vision)
            base_url: Base URL for Ollama server. If None, uses OLLAMA_HOST env var
                      or defaults to http://localhost:11434.
        """
        self._api_key = api_key or os.environ.get("OLLAMA_API_KEY")
        self._model_name = model
        self._base_url = (
            base_url
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        )

        # Usage tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._iteration_count = 0

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        # HTTP client for API calls
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=300.0,  # Longer timeout for local inference
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "ollama"

    def get_usage(self) -> dict:
        """Get current usage statistics.

        Returns:
            Dict with input_tokens, output_tokens, total_tokens, cost_usd, iterations
        """
        # Ollama is free/local, so no cost
        return {
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "cost_usd": 0.0,  # Ollama is free (local inference)
            "cost_estimated": False,
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
        """Run the agent loop using Ollama's OpenAI-compatible API.

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
                "stream": False,
            }

            # Call Ollama API (OpenAI-compatible endpoint)
            try:
                response = self._client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                # Try to get error details from response body
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("error", {}).get("message", str(error_body))
                except Exception:
                    error_detail = e.response.text[:500] if e.response.text else "No details"

                if e.response.status_code == 404:
                    raise RuntimeError(
                        f"Ollama 404 error for model '{self._model_name}': {error_detail}. "
                        f"Make sure the model is pulled: ollama pull {self._model_name}"
                    ) from e
                elif e.response.status_code == 503:
                    raise RuntimeError(
                        f"Ollama server not available at {self._base_url}: {error_detail}"
                    ) from e
                else:
                    raise RuntimeError(
                        f"Ollama {e.response.status_code} error: {error_detail}"
                    ) from e
            except httpx.ConnectError as e:
                raise RuntimeError(
                    f"Cannot connect to Ollama server at {self._base_url}. "
                    f"Make sure Ollama is running: ollama serve"
                ) from e

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
                        # Parse arguments, handling malformed JSON from some models
                        args_str = tc["function"].get("arguments", "")
                        if args_str:
                            try:
                                args = json.loads(args_str)
                            except json.JSONDecodeError as e:
                                # Some models return malformed JSON - try to extract what we can
                                # or use empty dict as fallback
                                print(f"Warning: Malformed JSON in tool arguments: {args_str[:100]}... Error: {e}")
                                args = {}
                        else:
                            args = {}

                        tool_calls.append(ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=args,
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
                system_prompt, openai_tools, messages
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
                "stop_reason": finish_reason,
                "usage": data.get("usage"),
            }
            response_json = json.dumps(response_data, indent=2)

            done = finish_reason == "stop" or len(tool_calls) == 0
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

            # If no tool calls, check if this is a conversational response that needs re-prompting
            if done:
                # Detect conversational responses that ask for confirmation instead of acting
                conversational_indicators = [
                    "would you like",
                    "shall i",
                    "do you want",
                    "should i",
                    "let me know",
                    "please confirm",
                    "proceed with",
                    "?",  # Questions often indicate asking for permission
                ]
                text_lower = text_response.lower() if text_response else ""
                is_conversational = any(ind in text_lower for ind in conversational_indicators)

                # Only re-prompt if this looks conversational and we haven't made progress
                # (first few iterations where model might be asking instead of doing)
                if is_conversational and iteration <= 3:
                    # Add a follow-up message to nudge the model to act
                    messages.append({
                        "role": "assistant",
                        "content": text_response,
                    })
                    messages.append({
                        "role": "user",
                        "content": "Please proceed immediately. Execute the tool calls now without asking for confirmation. You are an autonomous agent - act directly.",
                    })
                    # Continue the loop instead of returning
                    continue

                return text_response

            # Add assistant message to history
            assistant_msg = {"role": "assistant", "content": text_response}
            if message.get("tool_calls"):
                assistant_msg["tool_calls"] = message["tool_calls"]
            messages.append(assistant_msg)

            # Execute tool calls and collect results
            # Collect any images to send after tool results
            pending_images = []

            for tc in tool_calls:
                try:
                    result = tool_executor(tc.name, tc.arguments)

                    # Check if result contains image data (from get_screenshot)
                    if isinstance(result, dict) and "image_data" in result:
                        # OpenAI API doesn't support images in tool results
                        # We need to add tool result as text, then add image in user message
                        image_b64 = result["image_data"]
                        if image_b64.startswith("data:"):
                            image_url = image_b64
                        else:
                            image_url = f"data:image/png;base64,{image_b64}"

                        width = result.get("width", "unknown")
                        height = result.get("height", "unknown")
                        note = result.get("note", "")
                        text_msg = f"Screenshot captured. Image dimensions: {width}x{height} pixels. {note}"

                        # Add tool result as text only
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": text_msg,
                        })

                        # Queue image to be sent in a user message after all tool results
                        pending_images.append({
                            "url": image_url,
                            "text": "Here is the screenshot. Analyze the image to identify tubercles and gaps in the pattern.",
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
                except StopAgentLoop:
                    # Re-raise control flow exceptions
                    raise
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"Error: {str(e)}",
                    })

            # After all tool results, add any pending images as a user message
            # OpenAI API only supports images in user messages, not tool results
            if pending_images:
                user_content = []
                for img in pending_images:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": img["url"]},
                    })
                    user_content.append({
                        "type": "text",
                        "text": img["text"],
                    })
                messages.append({
                    "role": "user",
                    "content": user_content,
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
