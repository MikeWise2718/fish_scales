"""Visual pattern completion agent for tubercle detection.

This module implements an LLM-powered agent that visually analyzes fish scale
images and adds missing tubercles to achieve high hexagonalness and coverage.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from .agent_run_logger import AgentRunLogger
from .providers.base import AgentLLMProvider, StopAgentLoop, ToolDefinition


@dataclass
class EditingState:
    """Tracks editing agent progress."""

    iteration: int
    initial_tubercle_count: int
    current_tubercle_count: int
    initial_hexagonalness: float
    current_hexagonalness: float
    initial_coverage: float
    current_coverage: float
    plateau_count: int  # Iterations since last improvement
    plateau_threshold: int
    best_hexagonalness: float
    best_coverage: float
    best_iteration: int
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "iteration": self.iteration,
            "initial_tubercle_count": self.initial_tubercle_count,
            "current_tubercle_count": self.current_tubercle_count,
            "initial_hexagonalness": self.initial_hexagonalness,
            "current_hexagonalness": self.current_hexagonalness,
            "initial_coverage": self.initial_coverage,
            "current_coverage": self.current_coverage,
            "plateau_count": self.plateau_count,
            "plateau_threshold": self.plateau_threshold,
            "best_hexagonalness": self.best_hexagonalness,
            "best_coverage": self.best_coverage,
            "best_iteration": self.best_iteration,
            "history": self.history,
        }


# Tool definitions for the editing agent
# Focused subset for visual pattern completion
EDITING_TOOLS = [
    ToolDefinition(
        name="get_screenshot",
        description="""Capture the current image view with tubercle overlay.

Returns a PNG image showing:
- The SEM image of the fish scale
- Detected tubercles as colored circles (cyan = extracted, green = manual)
- Connection lines between neighboring tubercles (if any)

Use this to visually analyze the pattern and identify gaps.
The response includes image dimensions (width, height) in pixels.""",
        parameters={
            "type": "object",
            "properties": {
                "overlay": {
                    "type": "boolean",
                    "description": "Show tubercle circles and connections (default: true)",
                    "default": True,
                },
                "numbers": {
                    "type": "boolean",
                    "description": "Show tubercle ID numbers (default: false)",
                    "default": False,
                },
            },
        },
    ),
    ToolDefinition(
        name="get_state",
        description="""Get the current state including tubercle count, edge count, hexagonalness, and coverage.

Returns:
- tubercle_count: Number of detected tubercles
- edge_count: Number of connections
- hexagonalness: Score from 0-1 measuring pattern regularity
- hexagonalness_components: Breakdown of spacing/degree/edge_ratio scores
- coverage_percent: Estimated percentage of scale area covered by detections
- image_dimensions: Width and height in pixels""",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="add_tubercle",
        description="""Add a new tubercle at the specified pixel coordinates.

IMPORTANT:
- Coordinates are in IMAGE pixels, not screen pixels
- Use get_screenshot to determine where to add
- The radius is auto-calculated from existing tubercles if not provided
- Only add tubercles where you see BRIGHT circular spots
- Do NOT add in dark/black background areas

Returns the created tubercle with its ID.""",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate in image pixels",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate in image pixels",
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
        name="delete_tubercle",
        description="""Delete a tubercle by its ID.

Use this to remove:
- False positives (detections that aren't real tubercles)
- Edge tubercles that hurt hexagonalness
- Duplicates or overlapping detections

WARNING: This also removes all connections to the deleted tubercle.""",
        parameters={
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID of the tubercle to delete",
                },
            },
            "required": ["id"],
        },
    ),
    ToolDefinition(
        name="move_tubercle",
        description="""Move a tubercle to new coordinates.

Use this to:
- Correct slightly misaligned tubercle positions
- Center a tubercle on its actual location""",
        parameters={
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID of the tubercle to move",
                },
                "x": {
                    "type": "number",
                    "description": "New X coordinate in image pixels",
                },
                "y": {
                    "type": "number",
                    "description": "New Y coordinate in image pixels",
                },
            },
            "required": ["id", "x", "y"],
        },
    ),
    ToolDefinition(
        name="auto_connect",
        description="""Generate connections between tubercles using a graph algorithm.

Methods:
- delaunay: All Delaunay triangulation edges (most connections)
- gabriel: Gabriel graph - removes edges with empty diametral circle (recommended)
- rng: Relative Neighborhood Graph (fewest connections)

Typically called after adding all tubercles to establish the neighbor graph.""",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["delaunay", "gabriel", "rng"],
                    "description": "Graph algorithm to use (default: gabriel)",
                    "default": "gabriel",
                },
            },
        },
    ),
    ToolDefinition(
        name="get_statistics",
        description="""Get detailed measurement statistics.

Returns:
- Tubercle statistics: count, mean/std/min/max diameter
- Edge statistics: count, mean/std/min/max spacing
- Hexagonalness: overall score and component breakdown
- Degree distribution: histogram of neighbor counts""",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="finish",
        description="""Signal that the pattern completion is done.

Call this when:
- The pattern appears visually complete (all visible tubercles detected)
- Good area coverage has been achieved
- Further additions would not improve hexagonalness or coverage
- You've determined the image quality prevents better results
- No more gaps are visible in the pattern

The agent will also auto-stop after plateau_threshold iterations without improvement.""",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why you're finishing",
                },
            },
            "required": ["reason"],
        },
    ),
]


class StopEditing(StopAgentLoop):
    """Exception raised to signal that editing should stop.

    Inherits from StopAgentLoop so that providers properly re-raise it
    instead of converting it to a tool error message.
    """

    pass


class EditingAgent:
    """LLM-driven visual pattern completion agent.

    Uses an LLM provider to visually analyze fish scale images and add
    missing tubercles to achieve high hexagonalness and coverage.
    """

    def __init__(
        self,
        provider: AgentLLMProvider,
        ui_base_url: str = "http://localhost:5010",
        verbose: bool = False,
        log_callback: Callable[[str], None] | None = None,
        run_logger: AgentRunLogger | None = None,
    ):
        """Initialize the editing agent.

        Args:
            provider: LLM provider instance (e.g., ClaudeAgentProvider)
            ui_base_url: Base URL of the fish-scale-ui Flask application
            verbose: Whether to print detailed logs
            log_callback: Optional callback for log messages
            run_logger: Optional logger for detailed prompt/response logging
        """
        self.provider = provider
        self.ui_url = ui_base_url.rstrip("/")
        self.verbose = verbose
        self.log_callback = log_callback
        self._client = httpx.Client(timeout=120)

        # Run logger for detailed prompt/response tracking
        self.run_logger = run_logger or AgentRunLogger()

        # Editing state
        self._state: EditingState | None = None
        self._max_iterations: int = 30
        self._plateau_threshold: int = 3
        self._finished: bool = False
        self._finish_reason: str = ""
        self._iteration_count: int = 0
        # Scale factor for coordinate conversion (VLM sees scaled image)
        self._scale_factor: float = 1.0

    def _log(self, message: str):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        if self.verbose:
            print(log_line, flush=True)
        if self.log_callback:
            self.log_callback(log_line)

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL for tool endpoints."""
        return f"{self.ui_url}/api/tools/{endpoint.lstrip('/')}"

    def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute a tool by calling the appropriate API endpoint.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result

        Raises:
            StopEditing: When editing should stop
        """
        if self._finished:
            raise StopEditing(self._finish_reason or "Already finished")

        self._log(f"Tool: {name}({args})")

        try:
            if name == "get_screenshot":
                return self._get_screenshot(
                    args.get("overlay", True),
                    args.get("numbers", False),
                )
            elif name == "get_state":
                return self._get_state()
            elif name == "add_tubercle":
                return self._add_tubercle(
                    args["x"],
                    args["y"],
                    args.get("radius"),
                )
            elif name == "delete_tubercle":
                return self._delete_tubercle(args["id"])
            elif name == "move_tubercle":
                return self._move_tubercle(args["id"], args["x"], args["y"])
            elif name == "auto_connect":
                return self._auto_connect(args.get("method", "gabriel"))
            elif name == "get_statistics":
                return self._get_statistics()
            elif name == "finish":
                result = self._finish(args.get("reason", ""))
                raise StopEditing(self._finish_reason)
            else:
                raise ValueError(f"Unknown tool: {name}")

        except StopEditing:
            raise
        except httpx.HTTPStatusError as e:
            self._log(f"HTTP Error: {e}")
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            self._log(f"Tool error: {e}")
            raise

    # Max size for VLM screenshots - VLMs work better with smaller images
    # and this ensures coordinates are in a consistent range
    VLM_MAX_SIZE = (768, 768)

    def _get_screenshot(self, overlay: bool = True, numbers: bool = False) -> dict:
        """Capture current view, scaled for VLM processing.

        The image is scaled down to fit within VLM_MAX_SIZE to improve
        coordinate accuracy from the VLM. The scale_factor is stored
        so that coordinates returned by the VLM can be scaled back up.
        """
        params = {
            "overlay": str(overlay).lower(),
            "numbers": str(numbers).lower(),
            "scale_bar": "false",
            "max_width": str(self.VLM_MAX_SIZE[0]),
            "max_height": str(self.VLM_MAX_SIZE[1]),
        }
        resp = self._client.get(self._api_url("/screenshot"), params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Screenshot failed"))

        # Original image dimensions (for coordinate scaling)
        orig_width = data.get("width", 0)
        orig_height = data.get("height", 0)
        # Scaled dimensions (what the VLM sees)
        scaled_width = data.get("scaled_width", orig_width)
        scaled_height = data.get("scaled_height", orig_height)
        # Scale factor for coordinate conversion
        self._scale_factor = data.get("scale_factor", 1.0)

        self._log(f"Screenshot: {scaled_width}x{scaled_height} px (original: {orig_width}x{orig_height}, scale: {self._scale_factor:.3f})")

        # Tell the VLM the SCALED dimensions - these are the coordinates it should use
        return {
            "image_data": data["image_b64"],
            "width": scaled_width,
            "height": scaled_height,
            "original_width": orig_width,
            "original_height": orig_height,
            "scale_factor": self._scale_factor,
            "note": f"Image dimensions: {scaled_width}x{scaled_height} pixels. Use these coordinates when adding tubercles. Origin (0,0) is top-left, X increases right, Y increases down.",
        }

    def _get_state(self) -> dict:
        """Get current state including tubercle count, hexagonalness, coverage."""
        # Get statistics
        stats_resp = self._client.get(self._api_url("/statistics"))
        stats_resp.raise_for_status()
        stats = stats_resp.json()

        # Get full state for image dimensions
        state_resp = self._client.get(self._api_url("/state"))
        state_resp.raise_for_status()
        state_data = state_resp.json()

        n_tubercles = stats.get("n_tubercles", 0)
        n_edges = stats.get("n_edges", 0)
        hexagonalness = stats.get("hexagonalness_score", 0)

        # Estimate coverage using convex hull area ratio
        # This is a rough approximation
        coverage = self._estimate_coverage(state_data, stats)

        result = {
            "tubercle_count": n_tubercles,
            "edge_count": n_edges,
            "hexagonalness": round(hexagonalness, 3),
            "hexagonalness_components": stats.get("hexagonalness_components", {}),
            "coverage_percent": round(coverage, 1),
            "image_dimensions": {
                "width": state_data.get("image", {}).get("width", 0),
                "height": state_data.get("image", {}).get("height", 0),
            },
        }

        # Update internal state tracking
        if self._state:
            prev_hex = self._state.current_hexagonalness
            prev_cov = self._state.current_coverage

            self._state.current_tubercle_count = n_tubercles
            self._state.current_hexagonalness = hexagonalness
            self._state.current_coverage = coverage

            # Check for improvement
            improved = (hexagonalness > prev_hex + 0.01) or (coverage > prev_cov + 2)

            if improved:
                self._state.plateau_count = 0
                if hexagonalness > self._state.best_hexagonalness:
                    self._state.best_hexagonalness = hexagonalness
                    self._state.best_coverage = coverage
                    self._state.best_iteration = self._state.iteration
            else:
                self._state.plateau_count += 1

            # Log progress
            delta_tub = n_tubercles - self._state.initial_tubercle_count
            self._log(
                f"State: hex={hexagonalness:.3f}, coverage={coverage:.1f}%, "
                f"tubercles={n_tubercles} ({delta_tub:+d}), plateau={self._state.plateau_count}/{self._state.plateau_threshold}"
            )

            # Check plateau stopping condition
            if self._state.plateau_count >= self._state.plateau_threshold:
                self._finished = True
                self._finish_reason = (
                    f"Plateau reached: no improvement for {self._state.plateau_count} iterations. "
                    f"Final: hexagonalness={hexagonalness:.3f}, coverage={coverage:.1f}%"
                )
                self._log(f"AUTO-STOP: {self._finish_reason}")
                raise StopEditing(self._finish_reason)

        return result

    def _estimate_coverage(self, state_data: dict, stats: dict) -> float:
        """Estimate area coverage as percentage.

        Uses convex hull of tubercles compared to image area,
        adjusted by density factor.
        """
        tubercles = state_data.get("tubercles", [])
        if len(tubercles) < 3:
            return 0.0

        image_info = state_data.get("image", {})
        img_width = image_info.get("width", 1)
        img_height = image_info.get("height", 1)
        img_area = img_width * img_height

        if img_area == 0:
            return 0.0

        # Calculate convex hull area
        try:
            from scipy.spatial import ConvexHull
            import numpy as np

            points = np.array([[t["centroid_x"], t["centroid_y"]] for t in tubercles])
            hull = ConvexHull(points)
            hull_area = hull.volume  # In 2D, volume is area

            # Base coverage from hull
            base_coverage = (hull_area / img_area) * 100

            # Density adjustment: ideal hexagonal packing with detected spacing
            mean_spacing = stats.get("mean_space_um", 0)
            mean_diameter = stats.get("mean_diameter_um", 0)

            if mean_spacing > 0 and mean_diameter > 0:
                # Expected tubercles per unit area in ideal hex pattern
                # Density factor accounts for how well the hull is filled
                density_factor = min(1.0, len(tubercles) / max(10, hull_area / (mean_spacing * 10) ** 2))
                coverage = base_coverage * density_factor
            else:
                coverage = base_coverage * 0.7  # Default adjustment

            return min(100.0, max(0.0, coverage))

        except Exception as e:
            self._log(f"Coverage estimation error: {e}")
            # Fallback: simple ratio
            return min(100.0, len(tubercles) / 2)

    def _add_tubercle(self, x: float, y: float, radius: float | None = None) -> dict:
        """Add a tubercle at the specified coordinates.

        Coordinates from the VLM are in the scaled image space. They are
        converted back to original image coordinates before being sent to the API.
        """
        # Scale coordinates from VLM space to original image space
        if self._scale_factor < 1.0:
            orig_x = x / self._scale_factor
            orig_y = y / self._scale_factor
            # Also scale radius if provided
            orig_radius = radius / self._scale_factor if radius else None
        else:
            orig_x, orig_y = x, y
            orig_radius = radius

        payload = {"x": orig_x, "y": orig_y}
        if orig_radius is not None:
            payload["radius"] = orig_radius

        resp = self._client.post(self._api_url("/tubercle"), json=payload)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Add tubercle failed"))

        tub_id = data.get("id", data.get("tubercle", {}).get("id", "?"))
        if self._scale_factor < 1.0:
            self._log(f"Added tubercle #{tub_id} at VLM({x:.1f}, {y:.1f}) -> image({orig_x:.1f}, {orig_y:.1f})")
        else:
            self._log(f"Added tubercle #{tub_id} at ({orig_x:.1f}, {orig_y:.1f})")

        # Increment iteration count on each add
        if self._state:
            self._state.iteration += 1

        # Output STATUS line for backend parsing
        self._output_status("add_tubercle", {"x": x, "y": y, "id": tub_id})

        return {
            "success": True,
            "tubercle": data.get("tubercle", {}),
            "id": tub_id,
        }

    def _delete_tubercle(self, tub_id: int) -> dict:
        """Delete a tubercle by ID."""
        resp = self._client.delete(self._api_url("/tubercle"), json={"id": tub_id})
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Delete tubercle failed"))

        self._log(f"Deleted tubercle #{tub_id}")

        # Output STATUS line
        self._output_status("delete_tubercle", {"id": tub_id})

        return {"success": True, "deleted_id": tub_id}

    def _move_tubercle(self, tub_id: int, x: float, y: float) -> dict:
        """Move a tubercle to new coordinates.

        Coordinates from the VLM are in the scaled image space. They are
        converted back to original image coordinates before being sent to the API.
        """
        # Scale coordinates from VLM space to original image space
        if self._scale_factor < 1.0:
            orig_x = x / self._scale_factor
            orig_y = y / self._scale_factor
        else:
            orig_x, orig_y = x, y

        resp = self._client.put(
            self._api_url("/tubercle"),
            json={"id": tub_id, "x": orig_x, "y": orig_y},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Move tubercle failed"))

        if self._scale_factor < 1.0:
            self._log(f"Moved tubercle #{tub_id} to VLM({x:.1f}, {y:.1f}) -> image({orig_x:.1f}, {orig_y:.1f})")
        else:
            self._log(f"Moved tubercle #{tub_id} to ({orig_x:.1f}, {orig_y:.1f})")

        return {
            "success": True,
            "tubercle": data.get("tubercle", {}),
        }

    def _auto_connect(self, method: str = "gabriel") -> dict:
        """Generate connections using specified graph algorithm."""
        resp = self._client.post(
            self._api_url("/auto-connect"),
            json={"method": method},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Auto-connect failed"))

        n_edges = data.get("n_edges", 0)
        self._log(f"Auto-connect ({method}): {n_edges} edges")

        return {
            "success": True,
            "method": method,
            "n_edges": n_edges,
        }

    def _get_statistics(self) -> dict:
        """Get detailed measurement statistics."""
        resp = self._client.get(self._api_url("/statistics"))
        resp.raise_for_status()
        stats = resp.json()

        return {
            "n_tubercles": stats.get("n_tubercles", 0),
            "n_edges": stats.get("n_edges", 0),
            "hexagonalness": stats.get("hexagonalness_score", 0),
            "hexagonalness_components": stats.get("hexagonalness_components", {}),
            "mean_diameter_um": stats.get("mean_diameter_um", 0),
            "std_diameter_um": stats.get("std_diameter_um", 0),
            "mean_space_um": stats.get("mean_space_um", 0),
            "std_space_um": stats.get("std_space_um", 0),
            "degree_distribution": stats.get("degree_distribution", {}),
        }

    def _finish(self, reason: str) -> dict:
        """Signal that editing is complete."""
        self._finished = True
        self._finish_reason = reason
        self._log(f"Finished: {reason}")

        return {
            "finished": True,
            "reason": reason,
            "final_tubercle_count": self._state.current_tubercle_count if self._state else 0,
            "final_hexagonalness": self._state.current_hexagonalness if self._state else 0,
            "final_coverage": self._state.current_coverage if self._state else 0,
        }

    def _output_status(self, action: str, action_data: dict | None = None) -> None:
        """Output structured STATUS line for backend parsing."""
        if not self._state:
            return

        status = {
            "iteration": self._state.iteration,
            "max_iterations": self._max_iterations,
            "phase": "pattern_completion",
            "hexagonalness": round(self._state.current_hexagonalness, 3),
            "coverage_percent": round(self._state.current_coverage, 1),
            "tubercles": self._state.current_tubercle_count,
            "plateau_count": self._state.plateau_count,
            "action": action,
        }
        if action_data:
            status.update(action_data)

        print(f"STATUS:{json.dumps(status)}", flush=True)

    def _check_max_iterations(self) -> None:
        """Check if max iterations reached."""
        if self._state and self._state.iteration >= self._max_iterations:
            self._finished = True
            self._finish_reason = (
                f"Maximum iterations ({self._max_iterations}) reached. "
                f"Final: hexagonalness={self._state.current_hexagonalness:.3f}, "
                f"coverage={self._state.current_coverage:.1f}%"
            )
            self._log(f"MAX ITERATIONS: {self._finish_reason}")
            raise StopEditing(self._finish_reason)

    def load_image(self, image_path: str | Path) -> dict:
        """Load an image into the UI.

        Args:
            image_path: Path to the image file

        Returns:
            Image info dict
        """
        path = str(Path(image_path).resolve())
        self._log(f"Loading image: {path}")
        resp = self._client.post(self._api_url("/load-image"), json={"path": path})
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
            self._api_url("/calibration"),
            json={"um_per_px": um_per_px},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Calibration failed"))
        return data.get("calibration", {})

    async def run(
        self,
        image_path: str | None = None,
        calibration: float | None = None,
        max_iterations: int = 30,
        plateau_threshold: int = 3,
        auto_connect: bool = True,
        auto_connect_method: str = "gabriel",
        on_iteration: Callable[[EditingState], None] | None = None,
        debug_seeds: str | None = None,
        debug_seed_radius: float = 15.0,
        goal: str = "hex_pattern",
        spot_count: int = 20,
        min_separation: int = 30,
    ) -> EditingState:
        """Run the pattern completion agent loop.

        Args:
            image_path: Path to image file (optional if already loaded)
            calibration: Calibration in um/px (optional if already set)
            max_iterations: Maximum iterations before stopping
            plateau_threshold: Stop after N iterations without improvement
            auto_connect: Whether to auto-connect at the end
            auto_connect_method: Graph algorithm for auto-connect
            on_iteration: Callback after each iteration
            debug_seeds: Debug seed pattern ("corners", "grid3x3", "cross", or custom coords)
            debug_seed_radius: Radius for debug seed tubercles in pixels
            goal: Agent goal ("hex_pattern" or "bright_spots")
            spot_count: Number of spots to find (for bright_spots goal)
            min_separation: Minimum pixel separation between spots (for bright_spots goal)

        Returns:
            Final editing state
        """
        from .prompts import EDITING_AGENT_SYSTEM_PROMPT, BRIGHT_SPOT_SYSTEM_PROMPT, get_debug_seed_prompt_section

        self._log(f"Starting editing agent: max_iter={max_iterations}, plateau={plateau_threshold}")
        self._log(f"Provider: {self.provider.provider_name}/{self.provider.model_name}")

        # Store config and reset state
        self._max_iterations = max_iterations
        self._plateau_threshold = plateau_threshold
        self._finished = False
        self._finish_reason = ""

        # Load image if provided
        if image_path:
            self.load_image(image_path)

        # Set calibration if provided
        if calibration:
            self.set_calibration(calibration)

        # Handle debug seeds if enabled
        debug_seed_config = None
        if debug_seeds:
            debug_seed_config = self._setup_debug_seeds(
                image_path=image_path,
                pattern=debug_seeds,
                radius=debug_seed_radius,
                calibration=calibration,
            )

        # Get initial state
        initial_stats = self._get_statistics()
        initial_state = self._get_state_data()

        n_tubercles = initial_stats.get("n_tubercles", 0)
        hexagonalness = initial_stats.get("hexagonalness", 0)
        coverage = self._estimate_coverage(initial_state, initial_stats)

        # Initialize state
        self._state = EditingState(
            iteration=0,
            initial_tubercle_count=n_tubercles,
            current_tubercle_count=n_tubercles,
            initial_hexagonalness=hexagonalness,
            current_hexagonalness=hexagonalness,
            initial_coverage=coverage,
            current_coverage=coverage,
            plateau_count=0,
            plateau_threshold=plateau_threshold,
            best_hexagonalness=hexagonalness,
            best_coverage=coverage,
            best_iteration=0,
            history=[],
        )

        self._log(
            f"Initial state: {n_tubercles} tubercles, "
            f"hexagonalness={hexagonalness:.3f}, coverage={coverage:.1f}%"
        )

        # Get image info for prompt
        image_info = initial_state.get("image", {})
        image_name = image_info.get("name", "unknown")
        image_width = image_info.get("width", 0)
        image_height = image_info.get("height", 0)
        cal_data = initial_state.get("calibration", {})
        cal_value = cal_data.get("um_per_px", calibration or 0)

        # Build system prompt based on goal
        if goal == "bright_spots":
            self._log(f"Goal: bright_spots (find {spot_count} spots, min separation {min_separation}px)")
            system_prompt = BRIGHT_SPOT_SYSTEM_PROMPT.format(
                spot_count=spot_count,
                min_separation=min_separation,
                image_name=image_name,
                image_width=image_width,
                image_height=image_height,
                calibration=cal_value,
            )
        else:
            self._log("Goal: hex_pattern (complete hexagonal pattern)")
            system_prompt = EDITING_AGENT_SYSTEM_PROMPT.format(
                plateau_threshold=plateau_threshold,
                image_name=image_name,
                image_width=image_width,
                image_height=image_height,
                calibration=cal_value,
                initial_tubercle_count=n_tubercles,
                initial_hexagonalness=f"{hexagonalness:.3f}",
                initial_coverage=f"{coverage:.1f}",
                max_iterations=max_iterations,
            )

        # Append debug seed section if enabled
        if debug_seed_config and hasattr(self, '_debug_seeds_placed'):
            from .debug_seeds import format_seed_list_for_prompt
            debug_prompt = get_debug_seed_prompt_section(
                n_seeds=len(debug_seed_config.positions),
                seed_radius=debug_seed_config.radius,
                seed_list=format_seed_list_for_prompt(debug_seed_config.positions),
                center_x=image_width // 2,
                center_y=image_height // 2,
            )
            system_prompt += "\n\n" + debug_prompt
            self._log(f"Added debug seed section to system prompt ({len(debug_seed_config.positions)} seeds)")

        # Build initial user message based on goal
        if goal == "bright_spots":
            user_message = f"""Find the {spot_count} brightest circular spots in this fish scale image.

Image info:
- Dimensions: {image_width}x{image_height} pixels
- Calibration: {cal_value} um/px
- Target spot count: {spot_count}
- Minimum separation: {min_separation} pixels

Your task:
1. Get a screenshot to see the image
2. Identify the {spot_count} brightest circular spots
3. Add a tubercle marker at each bright spot location
4. Verify placements with a final screenshot
5. Call finish() when done

Focus only on brightness - ignore pattern completion. Mark real bright spots only."""
        else:
            user_message = f"""Analyze this fish scale image and complete the tubercle pattern.

Current state:
- Tubercles: {n_tubercles}
- Hexagonalness: {hexagonalness:.3f}
- Coverage: {coverage:.1f}%
- Image dimensions: {image_width}x{image_height} pixels
- Calibration: {cal_value} um/px

Your goals:
1. Achieve high area coverage by detecting ALL visible tubercles
2. Achieve high hexagonalness by ensuring a regular pattern
3. Avoid false positives - only mark actual tubercles

Start by getting a screenshot to see the current state, then systematically scan for gaps in the pattern."""

        # Start run logging
        log_file = self.run_logger.start_run(
            image_path=image_path or "already_loaded",
            calibration=cal_value,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            target_hexagonalness=0,  # No target for editing agent
            max_iterations=max_iterations,
            initial_profile="editing",
            system_prompt=system_prompt,
            user_message=user_message,
        )
        self._log(f"Run log: {log_file}")

        # Reset usage tracking
        if hasattr(self.provider, "reset_usage"):
            self.provider.reset_usage()

        # Track VLM responses for debug seed analysis
        self._vlm_responses: list[str] = []

        # Callback wrapper
        def on_agent_iteration(agent_iter):
            """Handle each agent iteration."""
            # Log usage
            if hasattr(self.provider, "get_usage"):
                usage = self.provider.get_usage()
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                cost_usd = usage.get("cost_usd", 0)
                model = usage.get("model", self.provider.model_name)
                self._log(f"Usage: {input_tokens} input, {output_tokens} output, ${cost_usd:.4f} ({model})")

            # Log LLM response and capture for debug seed analysis
            if agent_iter and agent_iter.response_json:
                response_oneline = agent_iter.response_json.replace('\n', ' | ')
                self._log(f"LLM-Response: {response_oneline}")
                # Store response for debug seed analysis
                if hasattr(self, '_vlm_responses'):
                    self._vlm_responses.append(agent_iter.response_json)

            # Log prompt
            if agent_iter and agent_iter.prompt_size_bytes > 0:
                self._log(f"Prompt-Stats: size={agent_iter.prompt_size_bytes}")
                if agent_iter.prompt_content:
                    prompt_oneline = agent_iter.prompt_content.replace('\n', ' | ')
                    self._log(f"LLM-Prompt: {prompt_oneline}")

            # Notify callback
            if on_iteration and self._state:
                on_iteration(self._state)

        # Wrap tool executor
        def logged_tool_executor(name: str, args: dict):
            result = self._execute_tool(name, args)
            self.run_logger.log_tool_call(name, args, result)
            return result

        # Execute agent loop
        final_status = "completed"
        try:
            await self.provider.run_agent_loop(
                tools=EDITING_TOOLS,
                tool_executor=logged_tool_executor,
                system_prompt=system_prompt,
                user_message=user_message,
                max_iterations=max_iterations * 3,  # Allow more LLM calls
                on_iteration=on_agent_iteration,
            )
            self._log("Agent completed normally")
        except StopEditing as e:
            self._log(f"Editing stopped: {e.reason}")
            final_status = "completed"
        except Exception as e:
            self._log(f"Agent error: {e}")
            final_status = "error"
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")

        # Auto-connect at the end if requested
        if auto_connect and self._state:
            try:
                self._log(f"Running final auto-connect ({auto_connect_method})...")
                self._auto_connect(auto_connect_method)
            except Exception as e:
                self._log(f"Auto-connect error: {e}")

        # Run debug seed analysis if enabled
        debug_analysis = None
        if debug_seed_config and hasattr(self, '_debug_seeds_placed'):
            try:
                debug_analysis = self._run_debug_seed_analysis(debug_seed_config)
            except Exception as e:
                self._log(f"Debug seed analysis error: {e}")

        # Final state update
        if self._state:
            final_stats = self._get_statistics()
            self._state.current_hexagonalness = final_stats.get("hexagonalness", 0)
            self._state.current_tubercle_count = final_stats.get("n_tubercles", 0)

            delta = self._state.current_tubercle_count - self._state.initial_tubercle_count
            self._log("=" * 50)
            self._log("EDITING COMPLETE")
            self._log(f"  Tubercles: {self._state.initial_tubercle_count} -> {self._state.current_tubercle_count} ({delta:+d})")
            self._log(f"  Hexagonalness: {self._state.initial_hexagonalness:.3f} -> {self._state.current_hexagonalness:.3f}")
            self._log(f"  Coverage: {self._state.initial_coverage:.1f}% -> {self._state.current_coverage:.1f}%")
            self._log(f"  Iterations: {self._state.iteration}")
            self._log("=" * 50)

            # Output final status with seed analysis for UI
            final_status_data = {
                "iteration": self._state.iteration,
                "hexagonalness": self._state.current_hexagonalness,
                "coverage_percent": self._state.current_coverage,
                "tubercles": self._state.current_tubercle_count,
                "phase": "complete",
            }
            if debug_analysis:
                final_status_data["seed_analysis"] = debug_analysis
            print(f"STATUS:{json.dumps(final_status_data)}", flush=True)

        # Log usage stats
        if hasattr(self.provider, "get_usage"):
            usage = self.provider.get_usage()
            self._log(f"Total usage: {usage.get('total_tokens', 0):,} tokens, ${usage.get('cost_usd', 0):.4f}")

        # End run logging
        final_metrics = {
            "hexagonalness": self._state.current_hexagonalness if self._state else 0,
            "coverage": self._state.current_coverage if self._state else 0,
            "n_tubercles": self._state.current_tubercle_count if self._state else 0,
        }
        if debug_analysis:
            final_metrics["debug_seed_analysis"] = debug_analysis

        self.run_logger.end_run(
            status=final_status,
            final_metrics=final_metrics,
            final_params={},
            best_iteration=self._state.best_iteration if self._state else 0,
            best_hexagonalness=self._state.best_hexagonalness if self._state else 0,
            accept_reason=self._finish_reason,
        )

        return self._state

    def _get_state_data(self) -> dict:
        """Get raw state data from API."""
        resp = self._client.get(self._api_url("/state"))
        resp.raise_for_status()
        return resp.json()

    def _setup_debug_seeds(
        self,
        image_path: str | None,
        pattern: str,
        radius: float,
        calibration: float | None,
    ):
        """Set up debug seeds for coordinate verification.

        Args:
            image_path: Path to the image file (for identity computation)
            pattern: Seed pattern name or custom coordinates
            radius: Seed radius in pixels
            calibration: Calibration in um/px

        Returns:
            DebugSeedConfig with seed information
        """
        from .debug_seeds import (
            DebugSeedConfig,
            compute_image_identity,
            get_seed_positions,
            create_seed_tubercle,
            format_seed_list_for_prompt,
        )

        self._log(f"Setting up debug seeds: pattern={pattern}, radius={radius}px")

        # Get image dimensions from current state
        state = self._get_state_data()
        image_info = state.get("image", {})
        width = image_info.get("width", 0)
        height = image_info.get("height", 0)

        if width == 0 or height == 0:
            self._log("ERROR: Cannot get image dimensions for debug seeds")
            return None

        # Compute image identity if path provided
        image_identity = None
        if image_path:
            try:
                image_identity = compute_image_identity(image_path)
                self._log(f"Image identity: {image_identity.hash_sha256[:16]}...")
            except Exception as e:
                self._log(f"WARNING: Could not compute image identity: {e}")

        # Calculate seed positions
        positions = get_seed_positions(pattern, width, height)
        self._log(f"Placing {len(positions)} debug seeds")

        # Get calibration for um conversion
        cal_data = state.get("calibration", {})
        cal_value = cal_data.get("um_per_px", calibration or 0.5)

        # Get current max tubercle ID
        tubercles = state.get("tubercles", [])
        max_id = max((t.get("id", 0) for t in tubercles), default=0)

        # Place seeds as tubercles
        placed_seeds = []
        for pos in positions:
            seed_id = max_id + pos.index + 1
            seed_tub = create_seed_tubercle(
                position=pos,
                tubercle_id=seed_id,
                radius_px=radius,
                calibration_um_per_px=cal_value,
                pattern=pattern,
            )

            # Add the seed via API
            try:
                resp = self._client.post(
                    self._api_url("/tubercle"),
                    json={
                        "x": pos.x,
                        "y": pos.y,
                        "radius": radius,
                        "source": "debug_seed",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("success"):
                    actual_id = data.get("id", data.get("tubercle", {}).get("id", seed_id))
                    seed_tub["id"] = actual_id
                    placed_seeds.append(seed_tub)
                    self._log(f"  Placed seed {pos.index} ({pos.label}) at ({pos.x:.0f}, {pos.y:.0f})")
                else:
                    self._log(f"  WARNING: Failed to place seed {pos.index}: {data.get('error')}")
            except Exception as e:
                self._log(f"  WARNING: Failed to place seed {pos.index}: {e}")

        # Create config
        config = DebugSeedConfig(
            pattern=pattern,
            radius=radius,
            positions=positions,
            image_identity=image_identity,
        )

        self._log(f"Debug seeds setup complete: {len(placed_seeds)}/{len(positions)} placed")

        # Store for later use
        self._debug_seed_config = config
        self._debug_seeds_placed = placed_seeds

        return config

    def _run_debug_seed_analysis(self, config) -> dict | None:
        """Run debug seed analysis after agent completes.

        Args:
            config: DebugSeedConfig from setup

        Returns:
            Analysis results dict or None
        """
        from .debug_seeds import analyze_debug_seed_results, format_analysis_report

        self._log("Running debug seed analysis...")

        # Get current state to find VLM-added tubercles
        state = self._get_state_data()
        all_tubercles = state.get("tubercles", [])

        # Separate seed tubercles from VLM-added tubercles
        seeds = [t for t in all_tubercles if t.get("source") == "debug_seed"]
        vlm_tubercles = [t for t in all_tubercles if t.get("source") != "debug_seed"]

        # Get VLM responses
        vlm_responses = getattr(self, "_vlm_responses", [])

        # Get image identity
        image_identity = {}
        if config.image_identity:
            image_identity = config.image_identity.to_dict()

        # Run analysis
        analysis = analyze_debug_seed_results(
            seeds=seeds,
            vlm_tubercles=vlm_tubercles,
            vlm_responses=vlm_responses,
            image_identity=image_identity,
            comparison_identity=None,  # Could be passed in for comparison
        )

        # Log the report
        report = format_analysis_report(analysis)
        self._log("Debug Seed Analysis Report:")
        for line in report.split("\n"):
            self._log(f"  {line}")

        # Add report to analysis for UI display
        analysis["report"] = report

        # Store analysis for retrieval
        self._debug_seed_analysis = analysis

        return analysis

    def run_sync(
        self,
        image_path: str | None = None,
        calibration: float | None = None,
        max_iterations: int = 30,
        plateau_threshold: int = 3,
        auto_connect: bool = True,
        auto_connect_method: str = "gabriel",
        on_iteration: Callable[[EditingState], None] | None = None,
        debug_seeds: str | None = None,
        debug_seed_radius: float = 15.0,
        goal: str = "hex_pattern",
        spot_count: int = 20,
        min_separation: int = 30,
    ) -> EditingState:
        """Synchronous version of run().

        Args:
            image_path: Path to image file (optional if already loaded)
            calibration: Calibration in um/px (optional if already set)
            max_iterations: Maximum iterations before stopping
            plateau_threshold: Stop after N iterations without improvement
            auto_connect: Whether to auto-connect at the end
            auto_connect_method: Graph algorithm for auto-connect
            on_iteration: Callback after each iteration
            debug_seeds: Debug seed pattern ("corners", "grid3x3", "cross", or custom coords)
            debug_seed_radius: Radius for debug seed tubercles in pixels
            goal: Agent goal ("hex_pattern" or "bright_spots")
            spot_count: Number of spots to find (for bright_spots goal)
            min_separation: Minimum pixel separation between spots (for bright_spots goal)

        Returns:
            Final editing state
        """
        import asyncio

        return asyncio.run(
            self.run(
                image_path=image_path,
                calibration=calibration,
                max_iterations=max_iterations,
                plateau_threshold=plateau_threshold,
                auto_connect=auto_connect,
                auto_connect_method=auto_connect_method,
                on_iteration=on_iteration,
                debug_seeds=debug_seeds,
                debug_seed_radius=debug_seed_radius,
                goal=goal,
                spot_count=spot_count,
                min_separation=min_separation,
            )
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
