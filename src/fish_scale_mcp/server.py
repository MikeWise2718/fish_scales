"""MCP Server for Fish Scale UI.

Exposes fish-scale-ui functionality as MCP tools for LLM agents.
"""

import httpx
from typing import Optional
from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP


class TubercleData(BaseModel):
    """Tubercle information structure."""
    id: int = Field(description="Unique tubercle ID")
    centroid_x: float = Field(description="X coordinate in pixels")
    centroid_y: float = Field(description="Y coordinate in pixels")
    radius_px: float = Field(description="Radius in pixels")
    diameter_um: float = Field(description="Diameter in micrometers")
    circularity: float = Field(description="Circularity measure (0-1)")


class ConnectionData(BaseModel):
    """Connection/edge information structure."""
    id1: int = Field(description="First tubercle ID")
    id2: int = Field(description="Second tubercle ID")
    center_distance_um: float = Field(description="Center-to-center distance in micrometers")
    edge_distance_um: float = Field(description="Edge-to-edge (intertubercular) distance in micrometers")


class StatisticsData(BaseModel):
    """Statistics summary structure."""
    n_tubercles: int = Field(description="Number of tubercles")
    n_edges: int = Field(description="Number of connections")
    mean_diameter_um: Optional[float] = Field(default=None, description="Mean tubercle diameter in micrometers")
    std_diameter_um: Optional[float] = Field(default=None, description="Standard deviation of diameter")
    mean_space_um: Optional[float] = Field(default=None, description="Mean intertubercular space in micrometers")
    std_space_um: Optional[float] = Field(default=None, description="Standard deviation of spacing")
    suggested_genus: Optional[str] = Field(default=None, description="Suggested genus based on measurements")
    classification_confidence: Optional[str] = Field(default=None, description="Confidence level: high, medium, or low")
    # Hexagonalness metrics
    hexagonalness_score: Optional[float] = Field(default=None, description="Overall hexagonalness score (0-1, 1=perfect)")
    spacing_uniformity: Optional[float] = Field(default=None, description="Spacing uniformity component (0-1)")
    degree_score: Optional[float] = Field(default=None, description="Degree distribution score (0-1)")
    edge_ratio_score: Optional[float] = Field(default=None, description="Edge/node ratio score (0-1)")
    mean_degree: Optional[float] = Field(default=None, description="Mean number of neighbors per interior node")
    spacing_cv: Optional[float] = Field(default=None, description="Coefficient of variation of edge spacings")
    reliability: Optional[str] = Field(default=None, description="Reliability: 'high', 'low', or 'none'")


class FishScaleMCPServer:
    """MCP Server that exposes fish-scale-ui as tools for LLM agents.

    The server communicates with the Flask UI via HTTP endpoints.

    Usage:
        server = FishScaleMCPServer(ui_base_url="http://localhost:5010")
        # Run with: mcp run server.mcp
    """

    def __init__(self, ui_base_url: str = "http://localhost:5010"):
        """Initialize the MCP server.

        Args:
            ui_base_url: Base URL of the fish-scale-ui Flask application
        """
        self.ui_url = ui_base_url.rstrip('/')
        self.mcp = FastMCP(
            name="fish-scale-mcp",
            instructions="""
You are controlling a fish scale analysis application for detecting tubercles
in SEM images. Use these tools to:
1. Load and view images
2. Set calibration (micrometers per pixel)
3. Run extraction with various parameters
4. Add, move, or delete tubercles manually
5. Generate connections between tubercles
6. Save results

Typical workflow:
1. load_image() - Load an image file
2. set_calibration() - Set the µm/px calibration
3. run_extraction() - Run automated detection OR get_screenshot() + add tubercles manually
4. auto_connect() - Generate neighbor connections
5. get_statistics() - Check results
6. save_slo() - Save the annotations
"""
        )
        self._register_tools()

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL for tool endpoints."""
        return f"{self.ui_url}/api/tools/{endpoint.lstrip('/')}"

    def _register_tools(self):
        """Register all MCP tools."""

        @self.mcp.tool()
        def get_screenshot(
            include_overlay: bool = True,
            show_numbers: bool = False,
            show_scale_bar: bool = False,
        ) -> str:
            """Capture current view of the image with optional overlay.

            Args:
                include_overlay: Whether to include tubercle/connection overlay
                show_numbers: Whether to show tubercle ID numbers
                show_scale_bar: Whether to show scale bar

            Returns:
                Base64-encoded PNG image string
            """
            params = {
                'overlay': str(include_overlay).lower(),
                'numbers': str(show_numbers).lower(),
                'scale_bar': str(show_scale_bar).lower(),
            }
            resp = httpx.get(self._api_url('/screenshot'), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Screenshot failed'))
            return data['image_b64']

        @self.mcp.tool()
        def get_state() -> dict:
            """Get complete current state including image, calibration, tubercles, and edges.

            Returns:
                Dictionary with image info, calibration, tubercles, edges, statistics
            """
            resp = httpx.get(self._api_url('/state'), timeout=10)
            resp.raise_for_status()
            return resp.json()

        @self.mcp.tool()
        def load_image(path: str) -> dict:
            """Load an image file for analysis.

            Args:
                path: Full path to the image file (TIF, TIFF, PNG, JPEG)

            Returns:
                Dictionary with filename, width, height
            """
            resp = httpx.post(
                self._api_url('/load-image'),
                json={'path': path},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Load failed'))
            return data

        @self.mcp.tool()
        def set_calibration(um_per_px: float) -> dict:
            """Set the calibration (micrometers per pixel).

            Args:
                um_per_px: Calibration value - micrometers per pixel

            Returns:
                Calibration data including method
            """
            resp = httpx.post(
                self._api_url('/calibration'),
                json={'um_per_px': um_per_px},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Calibration failed'))
            return data['calibration']

        @self.mcp.tool()
        def get_params() -> dict:
            """Get current extraction parameters.

            Returns:
                Dictionary of current parameter values
            """
            resp = httpx.get(self._api_url('/params'), timeout=10)
            resp.raise_for_status()
            return resp.json()['parameters']

        @self.mcp.tool()
        def set_params(
            method: Optional[str] = None,
            threshold: Optional[float] = None,
            min_diameter_um: Optional[float] = None,
            max_diameter_um: Optional[float] = None,
            min_circularity: Optional[float] = None,
            clahe_clip: Optional[float] = None,
            clahe_kernel: Optional[int] = None,
            blur_sigma: Optional[float] = None,
            neighbor_graph: Optional[str] = None,
        ) -> dict:
            """Set extraction parameters. Only provided parameters are updated.

            Args:
                method: Detection method - 'log', 'dog', 'ellipse', or 'lattice'
                threshold: Detection sensitivity (0.01-0.5, lower = more sensitive)
                min_diameter_um: Minimum tubercle diameter in micrometers
                max_diameter_um: Maximum tubercle diameter in micrometers
                min_circularity: Minimum circularity (0-1, higher = more circular)
                clahe_clip: CLAHE contrast limit (0.01-0.1)
                clahe_kernel: CLAHE kernel size (4-16)
                blur_sigma: Gaussian blur sigma (0.5-3.0)
                neighbor_graph: Graph type - 'delaunay', 'gabriel', or 'rng'

            Returns:
                Updated parameters dictionary
            """
            params = {}
            if method is not None:
                params['method'] = method
            if threshold is not None:
                params['threshold'] = threshold
            if min_diameter_um is not None:
                params['min_diameter_um'] = min_diameter_um
            if max_diameter_um is not None:
                params['max_diameter_um'] = max_diameter_um
            if min_circularity is not None:
                params['min_circularity'] = min_circularity
            if clahe_clip is not None:
                params['clahe_clip'] = clahe_clip
            if clahe_kernel is not None:
                params['clahe_kernel'] = clahe_kernel
            if blur_sigma is not None:
                params['blur_sigma'] = blur_sigma
            if neighbor_graph is not None:
                params['neighbor_graph'] = neighbor_graph

            resp = httpx.post(
                self._api_url('/params'),
                json=params,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Set params failed'))
            return data['parameters']

        @self.mcp.tool()
        def run_extraction() -> dict:
            """Run tubercle extraction with current parameters.

            Requires calibration to be set first.

            Returns:
                Dictionary with tubercles, edges, statistics
            """
            # First get current params
            params_resp = httpx.get(self._api_url('/params'), timeout=10)
            params = params_resp.json().get('parameters', {})

            # Run extraction via the main API (not MCP API)
            resp = httpx.post(
                f"{self.ui_url}/api/extract",
                json=params,
                timeout=120  # Extraction can take a while
            )
            resp.raise_for_status()
            data = resp.json()
            if 'error' in data:
                raise Exception(data['error'])
            return data

        @self.mcp.tool()
        def add_tubercle(x: float, y: float, radius: Optional[float] = None) -> dict:
            """Add a new tubercle at the specified coordinates.

            Args:
                x: X coordinate in pixels
                y: Y coordinate in pixels
                radius: Radius in pixels (auto-calculated from existing if not provided)

            Returns:
                The created tubercle data with assigned ID
            """
            payload = {'x': x, 'y': y}
            if radius is not None:
                payload['radius'] = radius

            resp = httpx.post(
                self._api_url('/tubercle'),
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Add tubercle failed'))
            return data['tubercle']

        @self.mcp.tool()
        def move_tubercle(id: int, x: float, y: float) -> dict:
            """Move an existing tubercle to new coordinates.

            Args:
                id: Tubercle ID to move
                x: New X coordinate in pixels
                y: New Y coordinate in pixels

            Returns:
                Updated tubercle data
            """
            resp = httpx.put(
                self._api_url('/tubercle'),
                json={'id': id, 'x': x, 'y': y},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Move tubercle failed'))
            return data['tubercle']

        @self.mcp.tool()
        def delete_tubercle(id: int) -> bool:
            """Delete a tubercle and its connections.

            Args:
                id: Tubercle ID to delete

            Returns:
                True if successful
            """
            resp = httpx.request(
                'DELETE',
                self._api_url('/tubercle'),
                json={'id': id},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Delete tubercle failed'))
            return True

        @self.mcp.tool()
        def add_connection(id1: int, id2: int) -> dict:
            """Add a connection between two tubercles.

            Args:
                id1: First tubercle ID
                id2: Second tubercle ID

            Returns:
                The created connection data
            """
            resp = httpx.post(
                self._api_url('/connection'),
                json={'id1': id1, 'id2': id2},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Add connection failed'))
            return data['connection']

        @self.mcp.tool()
        def delete_connection(id1: int, id2: int) -> bool:
            """Delete a connection between two tubercles.

            Args:
                id1: First tubercle ID
                id2: Second tubercle ID

            Returns:
                True if successful
            """
            resp = httpx.request(
                'DELETE',
                self._api_url('/connection'),
                json={'id1': id1, 'id2': id2},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Delete connection failed'))
            return True

        @self.mcp.tool()
        def clear_connections() -> int:
            """Remove all connections.

            Returns:
                Number of connections removed
            """
            resp = httpx.post(self._api_url('/connections/clear'), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get('removed_count', 0)

        @self.mcp.tool()
        def auto_connect(method: str = "gabriel") -> dict:
            """Auto-generate connections using graph algorithm.

            Args:
                method: Graph method - 'delaunay' (all edges), 'gabriel' (recommended),
                        or 'rng' (most conservative)

            Returns:
                Dictionary with n_edges and edges list
            """
            resp = httpx.post(
                self._api_url('/auto-connect'),
                json={'method': method},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Auto-connect failed'))
            return {'n_edges': data['n_edges'], 'edges': data['edges']}

        @self.mcp.tool()
        def get_statistics() -> StatisticsData:
            """Get current statistics summary.

            Returns:
                Statistics including counts, means, and genus classification
            """
            resp = httpx.get(self._api_url('/statistics'), timeout=10)
            resp.raise_for_status()
            return StatisticsData(**resp.json())

        @self.mcp.tool()
        def add_debug_rectangle(
            x: float,
            y: float,
            width: float,
            height: float,
            label: Optional[str] = None,
            color: str = "magenta",
        ) -> dict:
            """Add a debug rectangle to visualize coordinate understanding.

            Use this at the start of analysis to verify you understand the image
            coordinate system. The rectangle will appear in screenshots.

            Args:
                x: X coordinate of top-left corner (in pixels)
                y: Y coordinate of top-left corner (in pixels)
                width: Width of rectangle (in pixels)
                height: Height of rectangle (in pixels)
                label: Optional text label to display
                color: Color name (magenta, red, green, blue, yellow, cyan, white, orange)

            Returns:
                The created debug shape with ID
            """
            payload = {
                'type': 'rectangle',
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'color': color,
            }
            if label:
                payload['label'] = label

            resp = httpx.post(
                self._api_url('/debug-shapes'),
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Add debug rectangle failed'))
            return data['shape']

        @self.mcp.tool()
        def clear_debug_shapes() -> bool:
            """Remove all debug shapes from the overlay.

            Returns:
                True if successful
            """
            resp = httpx.request(
                'DELETE',
                self._api_url('/debug-shapes'),
                json={},
                timeout=10
            )
            resp.raise_for_status()
            return resp.json().get('success', True)

        @self.mcp.tool()
        def save_slo() -> dict:
            """Save current annotations to SLO file.

            Returns:
                Dictionary with saved file paths
            """
            resp = httpx.post(self._api_url('/save'), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Save failed'))
            return data

        @self.mcp.tool()
        def get_user() -> dict:
            """Get the current user name for history tracking.

            Returns:
                Dictionary with user name and source (config, environment, or default)
            """
            resp = httpx.get(self._api_url('/user'), timeout=10)
            resp.raise_for_status()
            return resp.json()

        @self.mcp.tool()
        def add_history_event(
            event_type: str = "agent_phase",
            phase: Optional[int] = None,
            summary: Optional[str] = None,
            n_tubercles: Optional[int] = None,
            n_edges: Optional[int] = None,
        ) -> bool:
            """Add a history event to track agent actions.

            Use this to record significant actions the agent takes, such as
            completing extraction phases or major edits.

            Args:
                event_type: Type of event (default: "agent_phase")
                phase: Phase number (1, 2, 3, etc.)
                summary: Brief description of what was done
                n_tubercles: Number of tubercles after this action
                n_edges: Number of edges/connections after this action

            Returns:
                True if successful
            """
            payload = {'type': event_type}
            if phase is not None:
                payload['phase'] = phase
            if summary is not None:
                payload['summary'] = summary
            if n_tubercles is not None:
                payload['n_tubercles'] = n_tubercles
            if n_edges is not None:
                payload['n_edges'] = n_edges

            resp = httpx.post(
                self._api_url('/history'),
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                raise Exception(data.get('error', 'Add history event failed'))
            return True


def create_server(ui_base_url: str = "http://localhost:5010") -> FastMCP:
    """Create and return the MCP server instance.

    Args:
        ui_base_url: Base URL of the fish-scale-ui Flask application

    Returns:
        Configured FastMCP server
    """
    server = FishScaleMCPServer(ui_base_url)
    return server.mcp


# Default server instance for CLI usage
mcp = create_server()
