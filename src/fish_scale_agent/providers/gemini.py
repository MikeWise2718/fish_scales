"""Gemini provider for the fish scale agent using the google-genai SDK."""

import base64
import json
import os
import re
from typing import Any, Callable

from google import genai
from google.genai import types

from .base import (
    AgentLLMProvider,
    StopAgentLoop,
    ToolDefinition,
    ToolCall,
    AgentMessage,
    AgentIteration,
)


def _convert_tool_to_gemini(tool: ToolDefinition) -> types.FunctionDeclaration:
    """Convert our ToolDefinition to Gemini FunctionDeclaration."""
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters if tool.parameters else None,
    )


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


def _serialize_prompt_gemini(
    system_prompt: str, tools: list, contents: list
) -> tuple[str, int]:
    """Serialize the prompt components and calculate size.

    Returns:
        Tuple of (truncated_content, full_size_bytes)
    """
    # Build full prompt representation
    # Convert Gemini types to serializable format
    serializable_tools = []
    for tool in tools:
        if hasattr(tool, 'function_declarations'):
            for fd in tool.function_declarations:
                serializable_tools.append({
                    "name": fd.name,
                    "description": fd.description,
                    "parameters": fd.parameters,
                })

    # Convert contents to serializable format
    serializable_contents = []
    for content in contents:
        parts_data = []
        if hasattr(content, 'parts'):
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    parts_data.append({"text": part.text})
                elif hasattr(part, 'inline_data') and part.inline_data:
                    # Truncate inline data for logging
                    parts_data.append({
                        "inline_data": {
                            "mime_type": part.inline_data.mime_type,
                            "data": "[base64 image data]"
                        }
                    })
                elif hasattr(part, 'function_call') and part.function_call:
                    parts_data.append({
                        "function_call": {
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {}
                        }
                    })
                elif hasattr(part, 'function_response') and part.function_response:
                    parts_data.append({
                        "function_response": {
                            "name": part.function_response.name,
                            "response": part.function_response.response
                        }
                    })
        serializable_contents.append({
            "role": content.role if hasattr(content, 'role') else "unknown",
            "parts": parts_data
        })

    full_prompt = {
        "system": system_prompt,
        "tools": serializable_tools,
        "contents": serializable_contents,
    }
    full_json = json.dumps(full_prompt, indent=2, default=str)
    full_size = len(full_json.encode('utf-8'))

    # Truncate base64 for display
    truncated_json = _truncate_base64(full_json)

    return truncated_json, full_size


class GeminiAgentProvider(AgentLLMProvider):
    """Gemini-based agent provider using function calling.

    Uses the google-genai SDK for Gemini API access.
    Supports Gemini 2.0 Flash for fast, cost-effective agent loops.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
    ):
        """Initialize the Gemini provider.

        Args:
            api_key: Gemini API key. If None, uses GEMINI_API_KEY env var.
            model: Model to use (default: gemini-2.0-flash)
        """
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY env var or pass api_key."
            )
        self._client = genai.Client(api_key=self._api_key)
        self._model_name = model

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def run_agent_loop(
        self,
        tools: list[ToolDefinition],
        tool_executor: Callable[[str, dict], Any],
        system_prompt: str,
        user_message: str,
        max_iterations: int = 20,
        on_iteration: Callable[[AgentIteration], None] | None = None,
    ) -> str:
        """Run the agent loop using Gemini function calling.

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
        # Convert tools to Gemini format
        gemini_tools = [
            types.Tool(function_declarations=[_convert_tool_to_gemini(t)])
            for t in tools
        ]

        # Build configuration with automatic function calling disabled
        # so we can control the loop ourselves
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        # Build chat history
        history = []

        # Send initial user message
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=[types.Content(role="user", parts=[types.Part(text=user_message)])],
            config=config,
        )

        # Add user message to history
        history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Check if there are function calls
            function_calls = []
            text_response = ""

            # Get the model's response parts
            if response.candidates and response.candidates[0].content.parts:
                model_parts = response.candidates[0].content.parts
                for part in model_parts:
                    if part.function_call:
                        fc = part.function_call
                        function_calls.append(ToolCall(
                            id=f"call_{iteration}_{len(function_calls)}",
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        ))
                    elif part.text:
                        text_response += part.text

            # Build iteration info
            messages = []
            if text_response:
                messages.append(AgentMessage(
                    role="assistant",
                    content=text_response,
                ))

            # Serialize prompt for logging (with base64 truncated)
            prompt_content, prompt_size = _serialize_prompt_gemini(
                system_prompt, gemini_tools, history
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
                    for tc in function_calls
                ],
                "stop_reason": "tool_use" if function_calls else "end_turn",
            }
            response_json = json.dumps(response_data, indent=2)

            done = len(function_calls) == 0
            agent_iter = AgentIteration(
                messages=messages,
                tool_calls=function_calls,
                done=done,
                final_response=text_response if done else None,
                prompt_content=prompt_content,
                prompt_size_bytes=prompt_size,
                response_json=response_json,
            )

            if on_iteration:
                on_iteration(agent_iter)

            # If no function calls, we're done
            if done:
                return text_response

            # Add model response to history
            history.append(response.candidates[0].content)

            # Execute function calls and collect results
            function_response_parts = []
            pending_images = []  # Images to send after function responses

            for fc in function_calls:
                try:
                    result = tool_executor(fc.name, fc.arguments)

                    # Check if result contains image data (from get_screenshot)
                    if isinstance(result, dict) and "image_data" in result:
                        # Gemini doesn't support images in function responses
                        # Send function response as text, then image separately
                        image_b64 = result["image_data"]
                        # Strip data URI prefix if present
                        if image_b64.startswith("data:"):
                            image_b64 = image_b64.split(",", 1)[1]

                        width = result.get("width", "unknown")
                        height = result.get("height", "unknown")
                        note = result.get("note", "")
                        text_msg = f"Screenshot captured. Image dimensions: {width}x{height} pixels. {note}"

                        function_response_parts.append(
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=fc.name,
                                    response={"result": text_msg}
                                )
                            )
                        )

                        # Queue image to be sent after function responses
                        pending_images.append({
                            "data": base64.b64decode(image_b64),
                            "text": "Here is the screenshot. Analyze the image to identify tubercles and gaps in the pattern.",
                        })
                    else:
                        # Convert result to string if needed
                        if isinstance(result, (dict, list)):
                            result_str = json.dumps(result, indent=2)
                        else:
                            result_str = str(result)
                        function_response_parts.append(
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=fc.name,
                                    response={"result": result_str}
                                )
                            )
                        )
                except StopAgentLoop:
                    # Re-raise control flow exceptions
                    raise
                except Exception as e:
                    function_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response={"error": str(e)}
                            )
                        )
                    )

            # Add function responses to history
            history.append(types.Content(role="user", parts=function_response_parts))

            # Add any pending images as a separate user message
            if pending_images:
                image_parts = []
                for img in pending_images:
                    image_parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/png",
                                data=img["data"],
                            )
                        )
                    )
                    image_parts.append(types.Part(text=img["text"]))
                history.append(types.Content(role="user", parts=image_parts))

            # Send function responses back to model
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=history,
                config=config,
            )

        # Max iterations reached
        final_text = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    final_text += part.text
        return final_text or "Max iterations reached without final response."
