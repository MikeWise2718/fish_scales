"""Gemini provider for the fish scale agent using the google-genai SDK."""

import json
import os
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

            done = len(function_calls) == 0
            agent_iter = AgentIteration(
                messages=messages,
                tool_calls=function_calls,
                done=done,
                final_response=text_response if done else None,
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
            for fc in function_calls:
                try:
                    result = tool_executor(fc.name, fc.arguments)
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
