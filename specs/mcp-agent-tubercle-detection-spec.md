# MCP Agent for Tubercle Detection - Specification

## Overview

An agentic system where an LLM agent takes high-level control of the fish-scale-ui application via MCP (Model Context Protocol). The agent orchestrates a three-phase process to detect tubercles and their connections.

**Key Principle:** The agent has the outer loop. The fish-scale-ui app is a tool the agent uses.

---

## Three-Phase Detection Process

### Phase 1: High-Probability Tubercle Detection (Deterministic)
- Agent sets conservative extraction parameters (high threshold, strict circularity)
- Agent triggers image processing extraction
- Result: Only "obvious" tubercles detected - anchor points for the lattice
- This is fast, deterministic, and establishes the base pattern

### Phase 2: Pattern Completion (Agent Vision)
- Agent captures screenshot showing image + Phase 1 detections
- Agent analyzes hexagonal/equidistant pattern
- Agent identifies gaps where tubercles are likely missing
- Agent adds tubercles at predicted coordinates
- Iterates until pattern is complete
- This leverages LLM visual reasoning for the "hard" cases

### Phase 3: Connection Generation (Deterministic or Agent)
- Option A: Agent triggers auto-connect (Delaunay/Gabriel/RNG) - fast
- Option B: Agent visually verifies and edits connections - thorough
- Result: Complete TUB + ITC overlay

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT (Outer Loop)                           │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Phase 1    │───►│  Phase 2    │───►│  Phase 3    │         │
│  │  Extract    │    │  Complete   │    │  Connect    │         │
│  │  (Params)   │    │  (Vision)   │    │  (Graph)    │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    MCP Tools                                ││
│  │  get_screenshot, set_params, run_extraction,                ││
│  │  add_tubercle, add_connection, get_state, ...               ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server                                   │
│                    (Python, runs alongside Flask)               │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    fish-scale-ui                                │
│                    (Flask + Browser)                            │
│                                                                 │
│  User watches the agent work in real-time                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## MCP Server Design

### Tools Exposed

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_screenshot` | `include_overlay: bool` | Capture current view as base64 PNG |
| `get_state` | - | Get current tubercles, connections, params, stats |
| `get_params` | - | Get current extraction parameters |
| `set_params` | `params: dict` | Set extraction parameters |
| `run_extraction` | - | Run extraction with current params |
| `add_tubercle` | `x, y, radius` | Add a tubercle at coordinates |
| `move_tubercle` | `id, x, y` | Move existing tubercle |
| `delete_tubercle` | `id` | Delete a tubercle |
| `add_connection` | `id1, id2` | Add connection between two tubercles |
| `delete_connection` | `id1, id2` | Delete a connection |
| `clear_connections` | - | Remove all connections |
| `run_auto_connect` | `method: str` | Auto-generate connections (delaunay/gabriel/rng) |
| `get_calibration` | - | Get current µm/pixel calibration |
| `set_calibration` | `um_per_px: float` | Set calibration |
| `save_slo` | - | Save current state to SLO file |
| `undo` | - | Undo last operation |
| `redo` | - | Redo undone operation |

### MCP Server Implementation

```python
# src/fish_scale_mcp/server.py

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent
import httpx

class FishScaleMCPServer:
    """MCP Server that exposes fish-scale-ui as tools."""

    def __init__(self, ui_base_url="http://localhost:5010"):
        self.ui_url = ui_base_url
        self.server = Server("fish-scale-mcp")
        self._register_tools()

    def _register_tools(self):
        @self.server.tool()
        async def get_screenshot(include_overlay: bool = True) -> ImageContent:
            """Capture current view of the image with optional overlay."""
            resp = await httpx.get(f"{self.ui_url}/api/screenshot",
                                   params={"overlay": include_overlay})
            return ImageContent(type="image", data=resp.json()["image_b64"])

        @self.server.tool()
        async def add_tubercle(x: float, y: float, radius: float) -> dict:
            """Add a tubercle at the specified coordinates."""
            resp = await httpx.post(f"{self.ui_url}/api/tubercle",
                                    json={"x": x, "y": y, "radius": radius})
            return resp.json()

        # ... etc for all tools
```

### New Flask Endpoints Required

The MCP server communicates with Flask via HTTP. New endpoints needed:

```python
# src/fish_scale_ui/routes/api.py (additions)

@api_bp.route('/api/screenshot', methods=['GET'])
def get_screenshot():
    """Return current canvas as base64 PNG."""
    # This requires frontend cooperation - see below
    pass

@api_bp.route('/api/tubercle', methods=['POST'])
def add_tubercle():
    """Add a tubercle programmatically."""
    data = request.json
    # Add to current state, return new tubercle ID
    pass

@api_bp.route('/api/state', methods=['GET'])
def get_state():
    """Return complete current state."""
    pass
```

### Screenshot Capture Challenge

The canvas is rendered in the browser, not the server. Options:

**Option A: WebSocket push from browser**
- Browser periodically sends canvas screenshot to server
- Server caches latest screenshot for MCP requests
- Adds latency but simple

**Option B: Headless browser on server**
- Server runs headless Chrome/Playwright
- Server can capture screenshots directly
- More complex but more reliable

**Option C: Hybrid state-based**
- Server has full state (image + tubercles)
- Server renders overlay using PIL/matplotlib
- No browser dependency for screenshots

**Recommendation:** Option C (server-side rendering) for reliability.

---

## Agent Design

### LLM Provider Abstraction

```python
# src/fish_scale_agent/providers.py

from abc import ABC, abstractmethod

class AgentLLMProvider(ABC):
    """Base class for LLM providers that can run the agent."""

    @abstractmethod
    async def run_agent_loop(self, tools: list, system_prompt: str,
                              max_iterations: int) -> str:
        """Run the agent loop with access to MCP tools."""
        pass

class ClaudeAgentProvider(AgentLLMProvider):
    """Uses Claude API with tool use."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    async def run_agent_loop(self, tools, system_prompt, max_iterations):
        messages = []
        for i in range(max_iterations):
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                tools=tools,
                messages=messages
            )
            # Handle tool calls, append results, continue...
            if response.stop_reason == "end_turn":
                break
        return response.content

class GeminiAgentProvider(AgentLLMProvider):
    """Uses Gemini API with function calling."""
    pass

class OpenRouterAgentProvider(AgentLLMProvider):
    """Uses OpenRouter API (OpenAI-compatible) with tool use."""
    pass
```

### Agent System Prompt

```markdown
You are an expert at analyzing SEM images of fish scales to identify tubercles.

## Your Task
Detect all tubercles in the image and connect them appropriately.

## Three-Phase Process

### Phase 1: High-Confidence Detection
1. Call `set_params` with conservative settings:
   - threshold: 0.15 (high = fewer false positives)
   - min_diameter: 4.0
   - circularity: 0.8 (strict)
2. Call `run_extraction`
3. Call `get_screenshot` to see results
4. Evaluate: Are there clear anchor tubercles forming a pattern?

### Phase 2: Pattern Completion
1. Analyze the hexagonal/equidistant pattern of detected tubercles
2. Identify gaps where tubercles are likely missing
3. For each likely tubercle location:
   - Calculate coordinates based on the pattern
   - Call `add_tubercle(x, y, radius)`
   - Use mean radius of existing tubercles
4. Call `get_screenshot` to verify
5. Repeat until pattern appears complete

### Phase 3: Connection Generation
1. Call `run_auto_connect` with method="gabriel" (good balance)
2. Call `get_screenshot` to verify connections look reasonable
3. Optionally delete spurious connections at edges

## Guidelines
- Tubercles form a roughly hexagonal pattern with roughly equal spacing
- Don't add tubercles where there's clearly no tubercle in the image
- The pattern may be incomplete at image edges - that's okay
- Aim for ~50-200 tubercles typically (varies by image)
- When uncertain, err on the side of NOT adding a tubercle

## When Done
Call `save_slo` and report summary statistics.
```

### Agent Runner

```python
# src/fish_scale_agent/runner.py

class TubercleDetectionAgent:
    """Orchestrates the three-phase detection process."""

    def __init__(self, provider: AgentLLMProvider, mcp_server_url: str):
        self.provider = provider
        self.mcp_client = MCPClient(mcp_server_url)

    async def run(self, image_path: str, max_iterations: int = 20):
        """Run the full three-phase detection."""

        # Load image in UI (could be another MCP tool)
        await self.mcp_client.call("load_image", {"path": image_path})

        # Get tools from MCP server
        tools = await self.mcp_client.list_tools()

        # Run agent loop
        result = await self.provider.run_agent_loop(
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=max_iterations
        )

        return result
```

---

## User Interface Integration

### Agent Control Panel

Add to fish-scale-ui Settings or new "Agent" tab:

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Agent Control                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Provider: [Gemini ▼]  Model: [gemini-2.0-flash ▼]         │
│  API Key:  [••••••••••••••••]                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [▶ Start Agent]  [⏹ Stop]  [⏸ Pause]              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Status: Phase 2 - Adding tubercles (iteration 3/20)        │
│  ████████████░░░░░░░░ 60%                                   │
│                                                             │
│  Log:                                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [10:32:01] Phase 1: Set params threshold=0.15       │   │
│  │ [10:32:02] Phase 1: Extraction found 45 tubercles   │   │
│  │ [10:32:05] Phase 2: Identified 12 likely gaps       │   │
│  │ [10:32:06] Phase 2: Added tubercle at (234, 156)    │   │
│  │ [10:32:06] Phase 2: Added tubercle at (267, 189)    │   │
│  │ ...                                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Real-Time Updates

- Agent actions appear in UI in real-time (via WebSocket)
- User can watch tubercles being added
- User can pause/stop agent at any time
- User can manually edit after agent finishes

---

## File Structure

```
fish_scales/
├── src/
│   ├── fish_scale_analysis/        # Existing - core algorithms
│   ├── fish_scale_ui/              # Existing - Flask web UI
│   │   ├── routes/
│   │   │   └── api.py              # Add new endpoints for MCP
│   │   └── static/js/
│   │       └── agent-panel.js      # Agent control UI
│   │
│   ├── fish_scale_mcp/             # NEW - MCP Server
│   │   ├── __init__.py
│   │   ├── server.py               # MCP server implementation
│   │   └── tools.py                # Tool definitions
│   │
│   └── fish_scale_agent/           # NEW - Agent implementation
│       ├── __init__.py
│       ├── runner.py               # Agent orchestration
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py             # AgentLLMProvider ABC
│       │   ├── claude.py           # Claude provider
│       │   ├── gemini.py           # Gemini provider
│       │   └── openrouter.py       # OpenRouter provider
│       └── prompts.py              # System prompts
│
├── pyproject.toml                  # Add mcp, anthropic, google-generativeai
└── ...
```

---

## Implementation Phases

### Phase 1: MCP Server Foundation (2-3 days) ✅ COMPLETE
- [x] Set up `fish_scale_mcp` package
- [x] Implement core MCP server with basic tools
- [x] Add Flask API endpoints for MCP to call
- [x] Server-side screenshot rendering (image + overlay)
- [ ] Test with MCP Inspector or simple client

### Phase 2: Single-Provider Agent (2-3 days) ✅ COMPLETE
- [x] Set up `fish_scale_agent` package
- [x] Implement Gemini provider (using google-genai SDK)
- [x] Write system prompt for three-phase process
- [x] Implement agent runner
- [x] CLI to run agent: `uv run fish-scale-agent run <image>`

### Phase 3: Multi-Provider Support (1-2 days) - PARTIAL
- [x] Implement Claude provider (with vision support for screenshots)
- [ ] Implement OpenRouter provider
- [x] Provider selection via CLI args or config

### Phase 4: UI Integration (2-3 days)
- [ ] Agent control panel in UI
- [ ] WebSocket for real-time updates
- [ ] Start/Stop/Pause controls
- [ ] Agent action log display

### Phase 5: Refinement (ongoing)
- [ ] Tune system prompt based on results
- [ ] Add Phase 1 parameter presets
- [ ] Handle edge cases (no tubercles found, too many, etc.)
- [ ] Performance optimization

---

## Open Questions

### Q1: Should the agent run in-process or as a separate process?

**Proposed:** Separate process, communicating via MCP protocol

*Rationale:*
- Clean separation of concerns
- Agent can be run independently (CLI) or from UI
- Easier to debug and develop
- Can run agent on different machine if needed

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q2: How should the agent handle uncertainty in Phase 2?

**Proposed:** Agent should be conservative - only add tubercles where it's fairly confident

*Rationale:*
- User can always add more manually
- False positives are harder to clean up than gaps
- Agent reports "uncertain" locations in log for user review

- [ ] Accepted
- [X] Alternative: ___if a tubercle is a false positives but doesn't changes the avg diamter or link distance much, is it not a big deal. We can use that to judge the likelyhood______________________________

---

### Q3: Should there be a "review mode" where agent proposes changes before applying?

**Proposed:** Start with direct application, add review mode later if needed

*Rationale:*
- Direct application lets user watch agent work
- Undo is available if agent makes mistakes
- Review mode adds complexity (staging area, approve/reject UI)
- Can add review mode as enhancement if users want it

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q4: How to handle the screenshot latency issue?

**Proposed:** Server-side rendering using PIL/matplotlib

*Rationale:*
- Server has all the data (image file, tubercle coordinates)
- Can render overlay without browser
- No WebSocket complexity for screenshots
- Fast and reliable

*Implementation:*
```python
def render_screenshot(image_path, tubercles, connections, calibration):
    """Render image with overlay server-side."""
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    for t in tubercles:
        draw.ellipse([t.x-t.r, t.y-t.r, t.x+t.r, t.y+t.r], outline='cyan')
    # ... connections, etc.
    return img_to_base64(img)
```

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q5: What's the maximum iterations / cost limit?

**Proposed:** Default 20 iterations, configurable. Show estimated cost before starting.

*Rationale:*
- 20 iterations should be enough for most images
- User can increase if needed
- Cost estimation prevents surprises
- Hard stop prevents runaway costs

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q6: Should Phase 3 (connections) be automatic or agent-driven?

**Proposed:** Default to automatic (Gabriel graph), with option for agent verification

*Rationale:*
- Gabriel graph gives good results for hexagonal patterns
- Much faster than agent evaluating each connection
- Agent can do a final visual check and remove obvious errors

- [X] Accepted
- [ ] Alternative: _________________________________

---

## CLI Interface

```bash
# Run agent on an image
uv run fish-scale-agent run <image> [options]

# Options
--provider gemini|claude|openrouter  # LLM provider (default: gemini)
--model <model-name>                  # Specific model
--api-key <key>                       # Or use env var
--max-iterations <n>                  # Default: 20
--ui-url <url>                        # Default: http://localhost:5010
--phase <1|2|3|all>                   # Run specific phase (default: all)
--dry-run                             # Show what would be done without doing it
--verbose                             # Detailed logging

# Examples
uv run fish-scale-agent run test_images/P2_Fig1c.tif --provider gemini
uv run fish-scale-agent run images/sample.tif --provider claude --max-iterations 30
```

---

## Dependencies

```toml
# pyproject.toml additions

[project.optional-dependencies]
agent = [
    "mcp>=1.0.0",
    "anthropic>=0.40.0",
    "google-generativeai>=0.8.0",
    "openai>=1.50.0",  # For OpenRouter
    "httpx>=0.27.0",
    "pillow>=10.0.0",  # For server-side rendering
]

[project.scripts]
fish-scale-agent = "fish_scale_agent.cli:main"
```
