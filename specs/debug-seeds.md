# Debug Seed Tubercles Specification

**Status:** Complete (v0.2.11)

## Quick Start (CLI)

```bash
# Run with corner seeds (5 points)
uv run fish-scale-agent edit image.tif --debug-seeds corners --calibration 0.14 -v

# Run with 3x3 grid seeds (9 points)
uv run fish-scale-agent edit image.tif --debug-seeds grid3x3 --calibration 0.14

# Run with custom seed positions
uv run fish-scale-agent edit image.tif --debug-seeds "100,100;350,255;600,400"

# Custom seed radius (default: 15px)
uv run fish-scale-agent edit image.tif --debug-seeds corners --debug-seed-radius 20
```

---

## Overview

This feature adds **debug seed tubercles** - markers placed at known positions before running the AgenticEditing agent. These seeds serve as coordinate calibration points to diagnose whether the VLM correctly understands and uses the image coordinate system.

## Problem Statement

During testing of AgenticEditing (2026-01-15), the agent produced a mathematically perfect hexagonal grid pattern that did NOT correspond to actual tubercle positions in the image. Both annotation sets (SimpleExtraction and AgenticEditing) had similar coordinate ranges, but:

- **SimpleExtraction**: Irregular positions matching actual image features
- **AgenticEditing**: Regular grid pattern (120px spacing) - idealized, not detected

This suggests the VLM is either:
1. Not correctly perceiving feature positions in the image
2. Generating idealized patterns rather than detecting features
3. Having coordinate transformation issues

Debug seeds provide a controlled way to test coordinate accuracy.

---

## Feature Design

### Concept

Place a small number of tubercles at **known, predictable positions** before running the agent. Then observe:

1. Does the VLM correctly identify seed positions in screenshots?
2. Does it add new tubercles relative to seeds, or ignore them?
3. Does it place tubercles ON TOP of seeds (indicating it's not seeing them)?
4. Are there systematic coordinate offsets?

### Image Identity Verification

To ensure both methods (SimpleExtraction and AgenticEditing) are operating on the **same image**, we capture and verify:

1. **Image hash** (SHA-256) - cryptographic fingerprint of pixel data
2. **Image path** - original file path for reference
3. **File modification time** - detect if image changed between runs
4. **VLM image description** - ask VLM to describe distinctive features in a specific region

This addresses the scenario where coordinate alignment looks correct but the underlying image differs.

### Seed Patterns

| Pattern | Description | Positions (for 700x510 image) |
|---------|-------------|-------------------------------|
| `corners` | 4 corners + center | (105, 77), (595, 77), (105, 434), (595, 434), (350, 255) |
| `grid3x3` | 3x3 grid | 9 points at 20%, 50%, 80% of width/height |
| `cross` | Center + cardinal points | 5 points forming a + shape |
| `custom` | User-specified | Explicit coordinate list |

### Seed Appearance

Seeds should be visually distinct:
- **Larger radius**: 15-20px (vs ~12px for normal tubercles)
- **Different color**: Magenta outline in overlay (vs cyan/green)
- **Source marker**: `source: "debug_seed"` in data

---

## Implementation

### CLI Interface

```bash
# Enable debug seeds with a pattern
uv run fish-scale-agent edit image.tif --debug-seeds corners
uv run fish-scale-agent edit image.tif --debug-seeds grid3x3
uv run fish-scale-agent edit image.tif --debug-seeds cross

# Custom positions (x,y pairs separated by semicolons)
uv run fish-scale-agent edit image.tif --debug-seeds "100,100;350,255;600,400"

# Combine with other options
uv run fish-scale-agent edit image.tif \
    --calibration 0.14 \
    --debug-seeds corners \
    --max-iterations 20 \
    -v
```

### API Interface

```
POST /api/agent/edit/start
{
    "provider": "claude",
    "debug_seeds": "corners",        // Pattern name or custom coords
    "debug_seed_radius": 18,         // Optional, default 15
    "max_iterations": 30,
    ...
}
```

### UI Interface

Add to AgenticEdit tab Configuration section:

```
Debug Seeds: [None ▼]
             - None
             - Corners (5 points)
             - Grid 3x3 (9 points)
             - Cross (5 points)
             - Custom...

[Custom coords input, shown when "Custom" selected]
```

---

## Data Structures

### Seed Tubercle Format

```json
{
    "id": 1,
    "centroid_x": 105.0,
    "centroid_y": 76.5,
    "radius_px": 15.0,
    "diameter_px": 30.0,
    "diameter_um": 4.2,
    "circularity": 1.0,
    "source": "debug_seed",
    "_debug": {
        "seed_index": 0,
        "pattern": "corners",
        "expected_x": 105.0,
        "expected_y": 76.5,
        "description": "top-left corner"
    }
}
```

### Session Debug Metadata

Stored in the annotation set:

```json
{
    "name": "AgenticEditing",
    "createdAt": "...",
    "_debug_session": {
        "enabled": true,
        "seed_pattern": "corners",
        "seed_radius": 15,
        "image_identity": {
            "path": "test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif",
            "dimensions": [700, 510],
            "hash_sha256": "a1b2c3d4e5f6...",
            "file_size_bytes": 1048576,
            "file_mtime": "2026-01-15T10:00:00Z"
        },
        "seeds_placed": [
            {"id": 1, "expected": [105.0, 76.5], "label": "top-left"},
            {"id": 2, "expected": [595.0, 76.5], "label": "top-right"},
            {"id": 3, "expected": [105.0, 433.5], "label": "bottom-left"},
            {"id": 4, "expected": [595.0, 433.5], "label": "bottom-right"},
            {"id": 5, "expected": [350.0, 255.0], "label": "center"}
        ],
        "vlm_seed_report": null,
        "vlm_image_description": null,
        "analysis": null
    }
}
```

---

## System Prompt Modification

When debug seeds are enabled, append to `EDITING_AGENT_SYSTEM_PROMPT`:

```python
DEBUG_SEED_PROMPT_SECTION = """
## Debug Seed Tubercles (IMPORTANT)

This session includes {n_seeds} DEBUG SEED tubercles placed at KNOWN reference positions.
These appear as LARGER circles (radius ~{seed_radius}px) in the overlay.

Seed positions:
{seed_list}

### Instructions for Seeds

1. **FIRST**: When you get a screenshot, identify and report the seed positions you observe
2. **VERIFY**: Compare observed positions to the expected positions above
3. **AVOID**: Do NOT add new tubercles within 30 pixels of any seed
4. **REFERENCE**: Use seeds as anchor points when estimating new tubercle positions

### Coordinate Verification

Before adding any tubercles, confirm your coordinate understanding:
- Report the approximate position of each seed you can see
- Note any discrepancy between expected and observed positions
- If seeds appear shifted, STOP and report the offset

Example response format:
"I observe the debug seeds at approximately:
- Seed 0 (top-left): (~108, ~80) - expected (105, 77)
- Seed 1 (top-right): (~592, ~78) - expected (595, 77)
..."

### Image Content Verification

To confirm you are analyzing the actual image (not a placeholder or different image), describe what you see in the **center region** of the image (around coordinates {center_x}, {center_y}):
- What distinctive features do you observe? (e.g., tubercle shapes, textures, artifacts)
- Are there any notable irregularities, damage, or unique patterns?
- Describe 2-3 specific visual characteristics

This description will be compared against known image features to verify image identity.

Example response:
"In the center region (~350, 255), I observe:
- A cluster of 4-5 closely spaced tubercles with slightly oval shapes
- A dark artifact/scratch running diagonally from upper-left to lower-right
- The tubercles here appear more densely packed than at the edges"
"""
```

---

## Analysis Module

### Post-Run Analysis

After the agent completes, analyze the results:

```python
def analyze_debug_seed_results(
    seeds: list[dict],
    vlm_tubercles: list[dict],
    vlm_responses: list[str],
    image_identity: dict,
    comparison_identity: dict | None = None,  # From another annotation set
) -> dict:
    """Analyze VLM behavior relative to debug seeds."""

    analysis = {
        "seeds_placed": len(seeds),
        "vlm_tubercles_added": len(vlm_tubercles),

        # Image identity verification
        "image_identity": {
            "hash": image_identity.get("hash_sha256"),
            "path": image_identity.get("path"),
            "dimensions": image_identity.get("dimensions"),
            "matches_comparison": None,  # True/False if comparison provided
            "hash_mismatch": False,
            "dimension_mismatch": False,
        },

        # Did VLM report seeing the seeds?
        "vlm_reported_seeds": False,
        "vlm_seed_positions_reported": [],

        # Did VLM describe image content?
        "vlm_image_description": None,
        "vlm_described_features": [],

        # Coordinate accuracy
        "seed_position_errors": [],  # Reported vs expected
        "mean_position_error": None,
        "systematic_offset": None,   # (dx, dy) if consistent shift

        # Collision detection
        "tubercles_overlapping_seeds": 0,
        "min_distance_to_seed": [],

        # Pattern analysis
        "is_regular_grid": False,
        "grid_spacing_detected": None,

        # Diagnosis
        "diagnosis": None,
        "confidence": None,
    }

    # Image identity comparison (if reference provided)
    if comparison_identity:
        analysis["image_identity"]["matches_comparison"] = (
            image_identity.get("hash_sha256") == comparison_identity.get("hash_sha256")
        )
        analysis["image_identity"]["hash_mismatch"] = not analysis["image_identity"]["matches_comparison"]
        analysis["image_identity"]["dimension_mismatch"] = (
            image_identity.get("dimensions") != comparison_identity.get("dimensions")
        )

    # ... rest of analysis logic ...

    return analysis


def compute_image_identity(image_path: str) -> dict:
    """Compute identity fingerprint for an image file."""
    import hashlib
    from pathlib import Path
    from datetime import datetime
    from PIL import Image

    path = Path(image_path)

    # Read image and compute hash of pixel data
    with Image.open(path) as img:
        # Convert to consistent format for hashing
        img_bytes = img.tobytes()
        hash_sha256 = hashlib.sha256(img_bytes).hexdigest()
        dimensions = [img.width, img.height]

    # File metadata
    stat = path.stat()

    return {
        "path": str(path),
        "dimensions": dimensions,
        "hash_sha256": hash_sha256,
        "file_size_bytes": stat.st_size,
        "file_mtime": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
    }
```

### Diagnostic Outcomes

| Observation | Diagnosis | Confidence |
|-------------|-----------|------------|
| VLM reports seed positions accurately (< 10px error) | Coordinates working correctly | High |
| VLM reports seeds with consistent offset | Coordinate transformation bug | High |
| VLM reports seeds with random errors | VLM localization issues | Medium |
| VLM doesn't report seeds at all | VLM ignoring prompt instructions | Medium |
| VLM adds tubercles on top of seeds | VLM not perceiving overlay | High |
| VLM adds regular grid ignoring seeds | VLM hallucinating ideal pattern | High |
| VLM adds relative to seeds correctly | Working as intended | High |
| Image hash mismatch between runs | Different images loaded | High |
| Image dimensions mismatch | Different images or crops | High |
| VLM describes features not in image | VLM hallucinating content | High |
| VLM description matches known features | Image identity confirmed | High |

---

## Visualization

### Screenshot Overlay

Seeds rendered distinctively:

```python
# In screenshot.py render_screenshot()

COLORS = {
    'tubercle_outline': (0, 255, 255),      # Cyan - extracted
    'tubercle_manual': (0, 255, 0),         # Green - manual
    'tubercle_debug_seed': (255, 0, 255),   # Magenta - debug seeds
    ...
}

# When rendering:
if source == 'debug_seed':
    outline_color = COLORS['tubercle_debug_seed']
    width = 4  # Thicker outline
```

### Analysis Report

Generate a visual report showing:

```
+--------------------------------------------------+
|  DEBUG SEED ANALYSIS REPORT                       |
+--------------------------------------------------+
|  Pattern: corners (5 seeds)                       |
|  Image: 700 x 510 pixels                          |
+--------------------------------------------------+
|                                                   |
|  IMAGE IDENTITY VERIFICATION                      |
|  Path: test_images/P1_Fig4_Atractosteus_...tif    |
|  Hash: a1b2c3d4e5f6... (SHA-256)                  |
|  File size: 1,048,576 bytes                       |
|  Modified: 2026-01-15T10:00:00Z                   |
|                                                   |
|  Comparison with SimpleExtraction:                |
|    Hash match: YES ✓                              |
|    Dimensions match: YES ✓                        |
|                                                   |
|  VLM Image Description:                           |
|    "Center region shows 4-5 closely spaced        |
|     tubercles with oval shapes, dark diagonal     |
|     artifact running upper-left to lower-right"   |
|                                                   |
+--------------------------------------------------+
|  SEED POSITION ACCURACY                           |
|  Seed 0 (top-left):     Expected (105, 77)        |
|                         Reported (108, 80)        |
|                         Error: 4.2 px             |
|  ...                                              |
|                                                   |
|  Mean Error: 5.1 px                               |
|  Systematic Offset: (+3, +3) px                   |
|                                                   |
+--------------------------------------------------+
|  COLLISION ANALYSIS                               |
|  Tubercles added: 82                              |
|  Overlapping seeds: 0                             |
|  Min distance to seed: 45 px (good)               |
+--------------------------------------------------+
|  PATTERN ANALYSIS                                 |
|  Regular grid detected: YES                       |
|  Grid spacing: ~120 px horizontal                 |
|                ~35 px vertical                    |
+--------------------------------------------------+
|  DIAGNOSIS                                        |
|  Image identity: CONFIRMED (hash match)           |
|  VLM is generating idealized hexagonal grid       |
|  rather than detecting actual image features.     |
|  Coordinate system appears understood (low error) |
|  but feature detection is not occurring.          |
+--------------------------------------------------+
```

---

## File Changes

### New Files

| File | Description |
|------|-------------|
| `src/fish_scale_agent/debug_seeds.py` | Seed pattern definitions, image identity, analysis functions |

### Modified Files

| File | Changes |
|------|---------|
| `src/fish_scale_agent/editing_agent.py` | Add `debug_seeds` parameter, seed placement, analysis call |
| `src/fish_scale_agent/cli.py` | Add `--debug-seeds` CLI option |
| `src/fish_scale_agent/prompts.py` | Add `DEBUG_SEED_PROMPT_SECTION` |
| `src/fish_scale_mcp/screenshot.py` | Add magenta color for debug seeds |
| `src/fish_scale_ui/routes/agent_api.py` | Pass `debug_seeds` to agent |
| `src/fish_scale_ui/static/js/agent_editing.js` | Add seed pattern selector |
| `src/fish_scale_ui/templates/workspace.html` | Add seed pattern dropdown |

---

## Implementation Phases

### Phase 1: Core Seed Functionality ✅ COMPLETED (v0.2.8)
- [x] Create `debug_seeds.py` with pattern definitions
- [x] Implement `compute_image_identity()` function
- [x] Add seed placement in `EditingAgent.run()`
- [x] Capture image identity at session start
- [x] Add `--debug-seeds` CLI option
- [x] Add seed section to system prompt
- [x] Add image description request to system prompt

**Implementation Notes (Phase 1):**
- Created `src/fish_scale_agent/debug_seeds.py` with:
  - `SeedPosition`, `ImageIdentity`, `DebugSeedConfig` dataclasses
  - `get_seed_positions()` supporting patterns: corners, grid3x3, cross, custom coords
  - `compute_image_identity()` using SHA-256 hash of RGB pixel data
  - `format_seed_list_for_prompt()` for system prompt integration
- Added `--debug-seeds PATTERN` and `--debug-seed-radius` CLI options to `edit` command
- Added `_setup_debug_seeds()` method in `EditingAgent` that places seeds via API
- Added `DEBUG_SEED_PROMPT_SECTION` in `prompts.py` with coordinate verification and image description requests

### Phase 2: Visual Distinction ✅ COMPLETED (v0.2.9)
- [x] Add magenta color for seeds in `screenshot.py`
- [x] Ensure seeds render with thicker outline
- [x] Mark seeds with `source: "debug_seed"` in data

**Implementation Notes (Phase 2):**
- Added `'tubercle_debug_seed': (255, 0, 255)` color in `screenshot.py`
- Changed selection color from magenta to yellow to avoid collision
- Debug seeds render with 4px outline (vs 2px normal) and cross-hairs inside circle
- Modified `tools_api.py` to accept `source` parameter in POST /api/tools/tubercle
- Updated `overlay.js` with matching colors and `getTubercleColor()` logic

### Phase 3: Analysis ✅ COMPLETED (v0.2.10)
- [x] Implement `analyze_debug_seed_results()`
- [x] Parse VLM responses for seed position reports
- [x] Parse VLM image description from responses
- [x] Compare image identity hashes between annotation sets
- [x] Detect regular grid patterns
- [x] Generate diagnosis (including image identity status)

**Implementation Notes (Phase 3):**
- Added comprehensive analysis functions in `debug_seeds.py`:
  - `parse_seed_positions_from_response()` - regex parsing for "Seed N (label): (x, y)" patterns
  - `parse_image_description_from_response()` - extracts center region descriptions
  - `calculate_seed_position_errors()` - computes mean error and systematic offset
  - `detect_seed_overlaps()` - finds tubercles within 30px of seeds
  - `detect_regular_grid_pattern()` - detects hallucinated grid patterns via CV analysis
  - `generate_diagnosis()` - produces diagnostic text with confidence level
  - `format_analysis_report()` - generates human-readable multi-section report
- Added `AnalysisResult` dataclass for structured results
- Integrated into `EditingAgent`:
  - VLM responses captured in `_vlm_responses` list during agent loop
  - `_run_debug_seed_analysis()` called after agent completion
  - Analysis results included in run logger final metrics
  - Full report printed to log

### Phase 4: UI Integration ✅ COMPLETED (v0.2.11)
- [x] Add seed pattern dropdown to AgenticEdit tab
- [x] Display analysis results after run completes
- [x] Add analysis to JSON export (via STATUS line to UI)

**Implementation Notes (Phase 4):**
- Added Debug Seeds dropdown (None, Corners, Grid 3×3, Cross) to Configuration section
- Added Debug Seed Radius input (hidden until seeds enabled)
- Added Debug Seed Analysis collapsible section with summary fields:
  - Diagnosis, Confidence, Seeds Placed, Mean Position Error
  - Systematic Offset, Overlapping Tubercles, Regular Grid Detected
- Added Full Analysis Report collapsible with copy button
- Updated `agent_editing.js` to send `debug_seeds` and `debug_seed_radius` in request
- Updated `agent_api.py` to pass `--debug-seeds` and `--debug-seed-radius` CLI args
- Added `seed_analysis` to STATUS line parsing in monitor thread
- Analysis section auto-expands on agent completion if seed analysis present

### Phase 5: Documentation ✅ COMPLETED (v0.2.11)
- [x] Update CLAUDE.md with debug seeds usage
- [x] Add examples to `--help` output
- [x] Document interpretation of results

**Implementation Notes (Phase 5):**
- Added comprehensive "Debug Seeds (Coordinate Verification)" section to CLAUDE.md
- Enhanced CLI help text for `--debug-seeds` with detailed usage examples
- Documented seed patterns, analysis results, and diagnostic outcomes

---

## Testing

### Unit Tests

```python
def test_seed_pattern_corners():
    """Test corner seed positions are calculated correctly."""
    positions = get_seed_positions("corners", 700, 510)
    assert len(positions) == 5
    assert positions[0] == pytest.approx((105.0, 76.5), abs=1)  # 15% margins

def test_seed_pattern_custom():
    """Test custom seed position parsing."""
    positions = get_seed_positions("100,200;300,400", 700, 510)
    assert positions == [(100, 200), (300, 400)]

def test_analysis_detects_overlap():
    """Test that overlapping tubercles are detected."""
    seeds = [{"expected_x": 100, "expected_y": 100}]
    vlm_tubs = [{"centroid_x": 105, "centroid_y": 102}]  # 5.4px away
    analysis = analyze_debug_seed_results(seeds, vlm_tubs, [], {}, None)
    assert analysis["tubercles_overlapping_seeds"] == 1

def test_image_identity_computation():
    """Test image identity fingerprint computation."""
    identity = compute_image_identity("test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif")
    assert "hash_sha256" in identity
    assert len(identity["hash_sha256"]) == 64  # SHA-256 hex string
    assert identity["dimensions"] == [700, 510]
    assert identity["file_size_bytes"] > 0

def test_image_identity_match():
    """Test that same image produces same hash."""
    id1 = compute_image_identity("test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif")
    id2 = compute_image_identity("test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif")
    assert id1["hash_sha256"] == id2["hash_sha256"]

def test_image_identity_mismatch_detection():
    """Test that different images are detected."""
    id1 = {"hash_sha256": "abc123", "dimensions": [700, 510]}
    id2 = {"hash_sha256": "def456", "dimensions": [700, 510]}
    analysis = analyze_debug_seed_results([], [], [], id1, id2)
    assert analysis["image_identity"]["hash_mismatch"] == True
    assert analysis["image_identity"]["matches_comparison"] == False
```

### Integration Tests

1. Run agent with `--debug-seeds corners` on test image
2. Verify 5 seeds placed at expected positions
3. Verify seeds have `source: "debug_seed"`
4. Verify seeds rendered in magenta in screenshot
5. Verify analysis report generated
6. Verify image identity captured in `_debug_session.image_identity`
7. Run SimpleExtraction and AgenticEditing, verify hash match in analysis

### Manual Testing Checklist

- [ ] CLI `--debug-seeds corners` places 5 seeds
- [ ] CLI `--debug-seeds grid3x3` places 9 seeds
- [ ] CLI custom coords parsed correctly
- [ ] Seeds appear magenta in UI
- [ ] VLM prompted to identify seeds
- [ ] VLM prompted to describe center region features
- [ ] Analysis detects if VLM ignored seeds
- [ ] JSON contains debug session metadata
- [ ] JSON contains `image_identity` with hash, path, dimensions
- [ ] Analysis compares hashes between annotation sets
- [ ] Hash mismatch correctly flagged when different image loaded

---

## Example Usage

### Debugging Coordinate Issues

```bash
# 1. Run with seeds
uv run fish-scale-agent edit test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif \
    --calibration 0.14 \
    --debug-seeds corners \
    --max-iterations 10 \
    -v

# 2. Check output for VLM seed identification
# Look for lines like:
# [10:15:32] VLM reports seeds at: (108, 80), (590, 78), ...

# 3. Review analysis in saved JSON
# Check _debug_session.analysis for diagnosis
```

### Comparing With/Without Seeds

```bash
# Without seeds (baseline)
uv run fish-scale-agent edit image.tif --calibration 0.14 -v

# With seeds (diagnostic)
uv run fish-scale-agent edit image.tif --calibration 0.14 --debug-seeds corners -v

# Compare the two annotation sets in UI
```

### Verifying Both Methods Use Same Image

When comparing SimpleExtraction vs AgenticEditing results:

```bash
# 1. Run SimpleExtraction (stores image_identity in annotation)
# (via UI or API)

# 2. Run AgenticEditing with debug seeds
uv run fish-scale-agent edit image.tif --debug-seeds corners -v

# 3. The analysis will compare:
#    - SHA-256 hash of image pixels
#    - Image dimensions
#    - VLM's description of center region features
```

If the hashes match, you can be confident both methods analyzed identical pixel data. The analysis report will show:

```
Comparison with SimpleExtraction:
  Hash match: YES ✓       # Same image confirmed
  Dimensions match: YES ✓
```

If they don't match:

```
Comparison with SimpleExtraction:
  Hash match: NO ✗        # DIFFERENT IMAGES!
  Dimensions match: YES ✓
  WARNING: Results not comparable - different source images
```

---

## Testing Results & Findings (2026-01-15)

### Debug Seeds Feature: Working

The debug seeds feature is fully functional:
- Seeds are placed correctly at known positions
- VLM reports seeing the seeds
- VLM avoids placing tubercles on top of seeds
- Analysis correctly identifies no regular grid hallucination
- UI displays analysis results after agent completion

### Underlying Problem: Persists

**The original problem that motivated this feature remains unsolved.**

Debug seed analysis showed:
```
Seeds placed: 5
VLM reported seeds: Yes
Overlapping seeds (< 30px): 0
Min distance to seed: 48.4 px
Regular grid detected: No
Diagnosis: "VLM behavior appears normal" (HIGH confidence)
```

However, visual inspection revealed that **VLM-placed tubercles do not align with actual bright spots in the image**. The VLM is:
- Understanding the coordinate system correctly (seeds prove this)
- NOT hallucinating a perfect grid pattern
- But NOT accurately detecting the actual visual features (bright circular spots)

### Analysis

The debug seeds diagnose **coordinate system issues**, but the actual problem is **feature detection accuracy**. The VLM appears to be:
- Placing tubercles in "plausible" locations based on pattern understanding
- Not performing precise pixel-level feature localization
- Unable to reliably identify bright spots on a grayscale image

This is a fundamental VLM limitation - they excel at semantic understanding but struggle with precise spatial feature detection that traditional computer vision methods handle well.

### Potential Next Steps (Not Implemented)

1. **Try different VLMs** - Gemini may have better spatial reasoning than Claude
2. **Increase screenshot resolution** - Currently 768x768 max, could try 1024 or higher
3. **Simplify the task** - Ask VLM to mark bright spots directly, not complete patterns
4. **Hybrid approach** - Use traditional CV for detection, VLM for verification/refinement only
5. **Reconsider architecture** - VLMs may not be suitable for precise feature localization

---

## Version

**Implementation History:**
- Phase 1 (Core): v0.2.8 (2026-01-15)
- Phase 2 (Visual): v0.2.9 (2026-01-15)
- Phase 3 (Analysis): v0.2.10 (2026-01-15)
- Phase 4 (UI): v0.2.11 (2026-01-15)
- Phase 5 (Docs): v0.2.11 (2026-01-15)

---

## References

- Original bug observation: 2026-01-15, P1_Fig4_Atractosteus_simplex_7.07um.tif
- Related files:
  - `editing_agent.py` - Core agent with debug seed handling
  - `prompts.py` - System prompt with seed verification section
  - `screenshot.py` - Magenta rendering for debug seeds
  - `debug_seeds.py` - Seed generation and analysis
  - `agent_editing.js` - UI JavaScript module
  - `agent_api.py` - API endpoint with CLI argument passing
  - `workspace.html` - UI template with debug seeds section
- Related spec: `specs/agentic-editing-tab.md`
