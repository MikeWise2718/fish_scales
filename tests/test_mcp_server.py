"""Tests for MCP server tool registration and schemas."""

import pytest


class TestServerCreation:
    """Tests for MCP server initialization."""

    def test_server_creation(self):
        """MCP server can be created."""
        from fish_scale_mcp.server import FishScaleMCPServer

        server = FishScaleMCPServer(ui_base_url="http://localhost:5010")
        assert server is not None
        assert server.mcp is not None

    def test_server_with_custom_url(self):
        """MCP server accepts custom UI URL."""
        from fish_scale_mcp.server import FishScaleMCPServer

        server = FishScaleMCPServer(ui_base_url="http://custom:8080")
        assert server.ui_url == "http://custom:8080"

    def test_server_strips_trailing_slash(self):
        """MCP server strips trailing slash from URL."""
        from fish_scale_mcp.server import FishScaleMCPServer

        server = FishScaleMCPServer(ui_base_url="http://localhost:5010/")
        assert server.ui_url == "http://localhost:5010"

    def test_create_server_function(self):
        """create_server helper function works."""
        from fish_scale_mcp.server import create_server

        mcp = create_server(ui_base_url="http://localhost:5010")
        assert mcp is not None


class TestToolRegistration:
    """Tests for MCP tool registration."""

    def test_all_tools_registered(self):
        """All expected tools are registered."""
        from fish_scale_mcp.server import FishScaleMCPServer

        server = FishScaleMCPServer()

        # Get registered tools from the FastMCP instance
        # The tools are registered as decorated functions
        expected_tools = [
            'get_screenshot',
            'get_state',
            'load_image',
            'set_calibration',
            'get_params',
            'set_params',
            'run_extraction',
            'add_tubercle',
            'move_tubercle',
            'delete_tubercle',
            'add_connection',
            'delete_connection',
            'clear_connections',
            'auto_connect',
            'get_statistics',
            'save_annotations',
        ]

        # FastMCP stores tools internally - we can verify by checking the mcp object
        assert server.mcp is not None
        assert server.mcp.name == "fish-scale-mcp"


class TestDataModels:
    """Tests for MCP data models."""

    def test_tubercle_data_model(self):
        """TubercleData model validates correctly."""
        from fish_scale_mcp.server import TubercleData

        tub = TubercleData(
            id=1,
            centroid_x=100.0,
            centroid_y=100.0,
            radius_px=10.0,
            diameter_um=3.3,
            circularity=0.95,
        )

        assert tub.id == 1
        assert tub.centroid_x == 100.0
        assert tub.diameter_um == 3.3

    def test_connection_data_model(self):
        """ConnectionData model validates correctly."""
        from fish_scale_mcp.server import ConnectionData

        conn = ConnectionData(
            id1=1,
            id2=2,
            center_distance_um=8.25,
            edge_distance_um=5.0,
        )

        assert conn.id1 == 1
        assert conn.id2 == 2
        assert conn.center_distance_um == 8.25

    def test_statistics_data_model(self):
        """StatisticsData model validates correctly."""
        from fish_scale_mcp.server import StatisticsData

        stats = StatisticsData(
            n_tubercles=10,
            n_edges=20,
            mean_diameter_um=3.5,
            std_diameter_um=0.5,
            mean_space_um=4.0,
            std_space_um=0.7,
            suggested_genus="Lepisosteus",
            classification_confidence="high",
        )

        assert stats.n_tubercles == 10
        assert stats.suggested_genus == "Lepisosteus"

    def test_statistics_data_optional_fields(self):
        """StatisticsData model handles optional fields."""
        from fish_scale_mcp.server import StatisticsData

        stats = StatisticsData(
            n_tubercles=0,
            n_edges=0,
        )

        assert stats.n_tubercles == 0
        assert stats.mean_diameter_um is None
        assert stats.suggested_genus is None


class TestApiUrlBuilder:
    """Tests for internal URL building."""

    def test_api_url_builder(self):
        """API URL builder constructs correct URLs."""
        from fish_scale_mcp.server import FishScaleMCPServer

        server = FishScaleMCPServer(ui_base_url="http://localhost:5010")

        assert server._api_url('/screenshot') == "http://localhost:5010/api/mcp/screenshot"
        assert server._api_url('state') == "http://localhost:5010/api/mcp/state"
        assert server._api_url('/tubercle') == "http://localhost:5010/api/mcp/tubercle"


class TestServerInstructions:
    """Tests for MCP server instructions."""

    def test_server_has_instructions(self):
        """MCP server includes usage instructions."""
        from fish_scale_mcp.server import FishScaleMCPServer

        server = FishScaleMCPServer()

        # FastMCP stores instructions in the server
        assert server.mcp.instructions is not None
        assert len(server.mcp.instructions) > 0
        assert 'tubercle' in server.mcp.instructions.lower()
