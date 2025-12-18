"""Agent runner for automated tubercle detection."""

import asyncio
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from .providers.base import AgentLLMProvider, ToolDefinition, AgentIteration
from .prompts import SYSTEM_PROMPT, INITIAL_USER_MESSAGE


# Tool definitions matching the MCP server tools
TOOLS = [
    ToolDefinition(
        name="get_screenshot",
        description="Capture current view of the image with optional overlay. Returns the image for visual analysis along with width and height in pixels. IMPORTANT: Use the returned dimensions to determine correct pixel coordinates when adding tubercles.",
        parameters={
            "type": "object",
            "properties": {
                "include_overlay": {
                    "type": "boolean",
                    "description": "Whether to include tubercle/connection overlay",
                    "default": True,
                },
                "show_numbers": {
                    "type": "boolean",
                    "description": "Whether to show tubercle ID numbers",
                    "default": False,
                },
                "show_scale_bar": {
                    "type": "boolean",
                    "description": "Whether to show scale bar",
                    "default": False,
                },
            },
        },
    ),
    ToolDefinition(
        name="get_state",
        description="Get complete current state including image info, calibration, tubercles, and edges.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="set_calibration",
        description="Set the calibration (micrometers per pixel). REQUIRED before extraction or adding tubercles.",
        parameters={
            "type": "object",
            "properties": {
                "um_per_px": {
                    "type": "number",
                    "description": "Calibration value - micrometers per pixel",
                },
            },
            "required": ["um_per_px"],
        },
    ),
    ToolDefinition(
        name="get_params",
        description="Get current extraction parameters.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="set_params",
        description="Set extraction parameters. Only provided parameters are updated.",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["log", "dog", "ellipse", "lattice"],
                    "description": "Detection method",
                },
                "threshold": {
                    "type": "number",
                    "description": "Detection sensitivity (0.01-0.5, lower = more sensitive)",
                },
                "min_diameter_um": {
                    "type": "number",
                    "description": "Minimum tubercle diameter in micrometers",
                },
                "max_diameter_um": {
                    "type": "number",
                    "description": "Maximum tubercle diameter in micrometers",
                },
                "min_circularity": {
                    "type": "number",
                    "description": "Minimum circularity (0-1, higher = more circular)",
                },
                "clahe_clip": {
                    "type": "number",
                    "description": "CLAHE contrast limit (0.01-0.1)",
                },
                "clahe_kernel": {
                    "type": "integer",
                    "description": "CLAHE kernel size (4-16)",
                },
                "blur_sigma": {
                    "type": "number",
                    "description": "Gaussian blur sigma (0.5-3.0)",
                },
                "neighbor_graph": {
                    "type": "string",
                    "enum": ["delaunay", "gabriel", "rng"],
                    "description": "Graph type for neighbor connections",
                },
            },
        },
    ),
    ToolDefinition(
        name="run_extraction",
        description="Run tubercle extraction with current parameters. Requires calibration to be set first.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="add_tubercle",
        description="Add a new tubercle at the specified pixel coordinates.",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate in pixels",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate in pixels",
                },
                "radius": {
                    "type": "number",
                    "description": "Radius in pixels (auto-calculated if not provided)",
                },
            },
            "required": ["x", "y"],
        },
    ),
    ToolDefinition(
        name="move_tubercle",
        description="Move an existing tubercle to new coordinates.",
        parameters={
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Tubercle ID to move"},
                "x": {"type": "number", "description": "New X coordinate in pixels"},
                "y": {"type": "number", "description": "New Y coordinate in pixels"},
            },
            "required": ["id", "x", "y"],
        },
    ),
    ToolDefinition(
        name="delete_tubercle",
        description="Delete a tubercle and its connections.",
        parameters={
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Tubercle ID to delete"},
            },
            "required": ["id"],
        },
    ),
    ToolDefinition(
        name="add_connection",
        description="Add a connection between two tubercles.",
        parameters={
            "type": "object",
            "properties": {
                "id1": {"type": "integer", "description": "First tubercle ID"},
                "id2": {"type": "integer", "description": "Second tubercle ID"},
            },
            "required": ["id1", "id2"],
        },
    ),
    ToolDefinition(
        name="delete_connection",
        description="Delete a connection between two tubercles.",
        parameters={
            "type": "object",
            "properties": {
                "id1": {"type": "integer", "description": "First tubercle ID"},
                "id2": {"type": "integer", "description": "Second tubercle ID"},
            },
            "required": ["id1", "id2"],
        },
    ),
    ToolDefinition(
        name="clear_connections",
        description="Remove all connections.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="auto_connect",
        description="Auto-generate connections using graph algorithm.",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["delaunay", "gabriel", "rng"],
                    "description": "Graph method: delaunay (all edges), gabriel (recommended), rng (most conservative)",
                    "default": "gabriel",
                },
            },
        },
    ),
    ToolDefinition(
        name="get_statistics",
        description="Get current statistics including counts, means, and genus classification.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="save_slo",
        description="Save current annotations to SLO file.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="add_debug_rectangle",
        description="Add a debug rectangle to visualize coordinate understanding. Use this at the START of analysis to verify you understand the image coordinate system. Draw a rectangle near the image corners to confirm coordinates are correct before adding tubercles. DO NOT clear these - keep them visible for comparison.",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate of top-left corner (in pixels)",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate of top-left corner (in pixels)",
                },
                "width": {
                    "type": "number",
                    "description": "Width of rectangle (in pixels)",
                },
                "height": {
                    "type": "number",
                    "description": "Height of rectangle (in pixels)",
                },
                "label": {
                    "type": "string",
                    "description": "Optional text label to display",
                },
                "color": {
                    "type": "string",
                    "enum": ["magenta", "red", "green", "blue", "yellow", "cyan", "white", "orange"],
                    "description": "Color of the rectangle",
                    "default": "magenta",
                },
            },
            "required": ["x", "y", "width", "height"],
        },
    ),
    # Note: clear_debug_shapes intentionally removed to keep debug rectangles visible
]


class TubercleDetectionAgent:
    """Orchestrates the three-phase tubercle detection process.

    Uses an LLM provider to run an agent loop that controls the fish-scale-ui
    application via HTTP API calls.
    """

    def __init__(
        self,
        provider: AgentLLMProvider,
        ui_base_url: str = "http://localhost:5010",
        verbose: bool = False,
        log_callback: Callable[[str], None] | None = None,
    ):
        """Initialize the agent.

        Args:
            provider: LLM provider instance (e.g., GeminiAgentProvider)
            ui_base_url: Base URL of the fish-scale-ui Flask application
            verbose: Whether to print detailed logs
            log_callback: Optional callback for log messages
        """
        self.provider = provider
        self.ui_url = ui_base_url.rstrip("/")
        self.verbose = verbose
        self.log_callback = log_callback
        self._client = httpx.Client(timeout=120)

    def _log(self, message: str):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        if self.verbose:
            print(log_line)
        if self.log_callback:
            self.log_callback(log_line)

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{self.ui_url}/api/mcp/{endpoint.lstrip('/')}"

    def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute a tool by calling the appropriate API endpoint.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result (dict, str, etc.)
        """
        self._log(f"Tool: {name}({json.dumps(args)})")

        try:
            if name == "get_screenshot":
                params = {
                    "overlay": str(args.get("include_overlay", True)).lower(),
                    "numbers": str(args.get("show_numbers", False)).lower(),
                    "scale_bar": str(args.get("show_scale_bar", False)).lower(),
                }
                resp = self._client.get(self._api_url("/screenshot"), params=params)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Screenshot failed"))
                width = data.get("width", 0)
                height = data.get("height", 0)
                self._log(f"Screenshot: {width}x{height} pixels")
                # Return image data with dimensions - Claude provider will pass image as vision input
                return {
                    "image_data": data["image_b64"],
                    "width": width,
                    "height": height,
                    "note": f"Image dimensions are {width}x{height} pixels. Use these coordinates when adding tubercles."
                }

            elif name == "get_state":
                resp = self._client.get(self._api_url("/state"))
                resp.raise_for_status()
                return resp.json()

            elif name == "set_calibration":
                um_per_px = args.get("um_per_px")
                resp = self._client.post(
                    self._api_url("/calibration"),
                    json={"um_per_px": um_per_px}
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Set calibration failed"))
                self._log(f"Calibration set: {um_per_px} µm/px")
                return data.get("calibration", {})

            elif name == "get_params":
                resp = self._client.get(self._api_url("/params"))
                resp.raise_for_status()
                return resp.json().get("parameters", {})

            elif name == "set_params":
                resp = self._client.post(self._api_url("/params"), json=args)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Set params failed"))
                return data.get("parameters", {})

            elif name == "run_extraction":
                # Check current state including calibration
                state_resp = self._client.get(self._api_url("/state"))
                state = state_resp.json()

                calibration = state.get("calibration")
                if calibration:
                    self._log(f"Current calibration: {calibration.get('um_per_px')} µm/px (method: {calibration.get('method', 'unknown')})")
                else:
                    self._log("WARNING: No calibration set, running auto-estimate...")
                    auto_resp = self._client.post(f"{self.ui_url}/api/calibration", json={"auto": True})
                    if auto_resp.status_code == 200:
                        cal_data = auto_resp.json()
                        if cal_data.get("calibration"):
                            calibration = cal_data["calibration"]
                            self._log(f"Auto-estimated calibration: {calibration.get('um_per_px')} µm/px")
                        else:
                            self._log("WARNING: Auto-estimate failed, extraction may fail")

                # Get current params
                params_resp = self._client.get(self._api_url("/params"))
                params = params_resp.json().get("parameters", {})

                # Log extraction parameters
                self._log(f"Extraction params: method={params.get('method', 'log')}, "
                         f"threshold={params.get('threshold', 0.1)}, "
                         f"min_d={params.get('min_diameter_um', 2)}µm, "
                         f"max_d={params.get('max_diameter_um', 20)}µm, "
                         f"min_circ={params.get('min_circularity', 0.5)}")

                # Calculate expected pixel sizes for debugging
                if calibration and calibration.get('um_per_px'):
                    um_per_px = calibration['um_per_px']
                    min_d_um = params.get('min_diameter_um', 2)
                    max_d_um = params.get('max_diameter_um', 20)
                    min_d_px = min_d_um / um_per_px
                    max_d_px = max_d_um / um_per_px
                    self._log(f"Expected blob size: {min_d_px:.1f} - {max_d_px:.1f} pixels")

                # Run extraction via main API
                resp = self._client.post(f"{self.ui_url}/api/extract", json=params)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise Exception(data["error"])
                n_tub = len(data.get("tubercles", []))
                n_edges = len(data.get("edges", []))
                self._log(f"Extraction result: {n_tub} tubercles, {n_edges} edges")

                # Return summary with debug info
                return {
                    "n_tubercles": n_tub,
                    "n_edges": n_edges,
                    "calibration_um_per_px": calibration.get('um_per_px') if calibration else None,
                    "message": f"Extraction complete. Found {n_tub} tubercles and {n_edges} connections.",
                }

            elif name == "add_tubercle":
                resp = self._client.post(self._api_url("/tubercle"), json=args)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Add tubercle failed"))
                return data.get("tubercle", {})

            elif name == "move_tubercle":
                resp = self._client.put(self._api_url("/tubercle"), json=args)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Move tubercle failed"))
                return data.get("tubercle", {})

            elif name == "delete_tubercle":
                resp = self._client.request(
                    "DELETE", self._api_url("/tubercle"), json=args
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Delete tubercle failed"))
                return {"success": True}

            elif name == "add_connection":
                resp = self._client.post(self._api_url("/connection"), json=args)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Add connection failed"))
                return data.get("connection", {})

            elif name == "delete_connection":
                resp = self._client.request(
                    "DELETE", self._api_url("/connection"), json=args
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Delete connection failed"))
                return {"success": True}

            elif name == "clear_connections":
                resp = self._client.post(self._api_url("/connections/clear"))
                resp.raise_for_status()
                data = resp.json()
                return {"removed_count": data.get("removed_count", 0)}

            elif name == "auto_connect":
                method = args.get("method", "gabriel")
                resp = self._client.post(
                    self._api_url("/auto-connect"), json={"method": method}
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Auto-connect failed"))
                return {"n_edges": data.get("n_edges", 0)}

            elif name == "get_statistics":
                resp = self._client.get(self._api_url("/statistics"))
                resp.raise_for_status()
                return resp.json()

            elif name == "save_slo":
                resp = self._client.post(self._api_url("/save"))
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Save failed"))
                return data

            elif name == "add_debug_rectangle":
                payload = {
                    "type": "rectangle",
                    "x": args.get("x"),
                    "y": args.get("y"),
                    "width": args.get("width"),
                    "height": args.get("height"),
                    "color": args.get("color", "magenta"),
                }
                if args.get("label"):
                    payload["label"] = args["label"]
                resp = self._client.post(self._api_url("/debug-shapes"), json=payload)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise Exception(data.get("error", "Add debug rectangle failed"))
                self._log(f"Debug rectangle added at ({args.get('x')}, {args.get('y')})")
                return data.get("shape", {})

            elif name == "clear_debug_shapes":
                resp = self._client.request(
                    "DELETE", self._api_url("/debug-shapes"), json={}
                )
                resp.raise_for_status()
                self._log("Debug shapes cleared")
                return {"success": True}

            else:
                raise ValueError(f"Unknown tool: {name}")

        except httpx.HTTPStatusError as e:
            self._log(f"HTTP Error: {e}")
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            self._log(f"Tool error: {e}")
            raise

    def _on_iteration(self, iteration: AgentIteration):
        """Callback for each agent iteration."""
        if iteration.done:
            self._log("Agent completed")
        else:
            for tc in iteration.tool_calls:
                self._log(f"Calling: {tc.name}")

    def load_image(self, image_path: str | Path) -> dict:
        """Load an image into the UI.

        Args:
            image_path: Path to the image file

        Returns:
            Image info dict
        """
        path = str(Path(image_path).resolve())
        self._log(f"Loading image: {path}")
        resp = self._client.post(
            self._api_url("/load-image"), json={"path": path}
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Load failed"))
        return data

    def set_calibration(self, um_per_px: float) -> dict:
        """Set the calibration.

        Args:
            um_per_px: Micrometers per pixel

        Returns:
            Calibration info dict
        """
        self._log(f"Setting calibration: {um_per_px} um/px")
        resp = self._client.post(
            self._api_url("/calibration"), json={"um_per_px": um_per_px}
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Calibration failed"))
        return data.get("calibration", {})

    async def run(
        self,
        image_path: str | Path | None = None,
        calibration_um_per_px: float | None = None,
        max_iterations: int = 20,
        system_prompt: str | None = None,
        user_message: str | None = None,
    ) -> str:
        """Run the full three-phase detection.

        Args:
            image_path: Path to image file (optional if already loaded in UI)
            calibration_um_per_px: Calibration value (optional if already set)
            max_iterations: Maximum agent iterations
            system_prompt: Custom system prompt (uses default if None)
            user_message: Custom initial message (uses default if None)

        Returns:
            Final response from the agent
        """
        self._log(f"Starting agent with {self.provider.provider_name}/{self.provider.model_name}")

        # Load image if provided
        if image_path:
            self.load_image(image_path)

        # Set calibration if provided
        if calibration_um_per_px:
            self.set_calibration(calibration_um_per_px)

        # Reset usage tracking if provider supports it
        if hasattr(self.provider, 'reset_usage'):
            self.provider.reset_usage()

        # Run agent loop
        result = await self.provider.run_agent_loop(
            tools=TOOLS,
            tool_executor=self._execute_tool,
            system_prompt=system_prompt or SYSTEM_PROMPT,
            user_message=user_message or INITIAL_USER_MESSAGE,
            max_iterations=max_iterations,
            on_iteration=self._on_iteration,
        )

        self._log("Agent run complete")

        # Log usage stats if available
        if hasattr(self.provider, 'get_usage'):
            usage = self.provider.get_usage()
            self._log("=" * 50)
            self._log("USAGE SUMMARY")
            self._log(f"  Model: {usage.get('model', 'unknown')}")
            self._log(f"  Iterations: {usage.get('iterations', 0)}")
            self._log(f"  Input tokens: {usage.get('input_tokens', 0):,}")
            self._log(f"  Output tokens: {usage.get('output_tokens', 0):,}")
            self._log(f"  Total tokens: {usage.get('total_tokens', 0):,}")
            cost_str = f"${usage.get('cost_usd', 0):.4f}"
            if usage.get('cost_estimated'):
                cost_str += " (ESTIMATED - unknown model pricing)"
            self._log(f"  Cost: {cost_str}")
            self._log("=" * 50)

        return result

    def run_sync(
        self,
        image_path: str | Path | None = None,
        calibration_um_per_px: float | None = None,
        max_iterations: int = 20,
        system_prompt: str | None = None,
        user_message: str | None = None,
    ) -> str:
        """Synchronous version of run()."""
        return asyncio.run(
            self.run(
                image_path=image_path,
                calibration_um_per_px=calibration_um_per_px,
                max_iterations=max_iterations,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
