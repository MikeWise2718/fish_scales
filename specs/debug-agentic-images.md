# Debug Agentic Images Specification

**Status:** Implemented (v0.2.19)
**Created:** 2026-01-15
**Purpose:** Debug VLM image interpretation issues by logging actual images sent to models

---

## Problem Statement

During AgenticEditing testing, the VLM is finding "bright spots" where there clearly are none in the original image. This suggests one of:

1. **Image corruption** - The base64 encoding/decoding is corrupting the image
2. **Overlay rendering issues** - The screenshot rendering (overlays, colors) is wrong
3. **Scaling artifacts** - The 768x768 max scaling is causing issues
4. **Provider-specific issues** - Claude vs Gemini vs OpenRouter handle images differently

Without being able to see exactly what the VLM receives, debugging is impossible.

### Current Image Flow

```
Image File (original)
    ↓
/api/tools/screenshot endpoint (tools_api.py:22-116)
    ↓
render_screenshot() (screenshot.py:28-193)
    - Load with PIL
    - Draw overlay (tubercles, connections)
    - Scale to max 768x768
    - Encode as PNG
    - base64.b64encode()
    ↓
editing_agent._get_screenshot() (editing_agent.py:357-402)
    - Receives {image_b64, width, height, scaled_width, scaled_height, scale_factor}
    ↓
Provider formats for VLM:
    - Claude: {"type": "image", "source": {"type": "base64", "data": "..."}}
    - Gemini: base64.b64decode() → Blob(inline_data=bytes)
    - OpenRouter: Similar to Claude
```

---

## Solution

Add optional image logging that saves every screenshot sent to the VLM:

1. **PNG/JPG file** - The actual decoded image (human-viewable)
2. **Base64 text file** - The exact string sent to the VLM

### Filename Format

```
{original_image_name}_{model_name}_{timestamp}.png
{original_image_name}_{model_name}_{timestamp}_b64.txt
```

**Example:**
```
P1_Fig4_Atractosteus_simplex_claude-sonnet-4-20250514_20260115_143052_001.png
P1_Fig4_Atractosteus_simplex_claude-sonnet-4-20250514_20260115_143052_001_b64.txt
```

### Output Location

```
AgenticEditingImages/
├── P1_Fig4_Atractosteus_simplex_claude-sonnet-4-20250514_20260115_143052_001.png
├── P1_Fig4_Atractosteus_simplex_claude-sonnet-4-20250514_20260115_143052_001_b64.txt
├── P1_Fig4_Atractosteus_simplex_claude-sonnet-4-20250514_20260115_143052_002.png
├── P1_Fig4_Atractosteus_simplex_claude-sonnet-4-20250514_20260115_143052_002_b64.txt
└── ...
```

The folder will be created at the project root level (same level as `images/`, `output/`, `log/`).

---

## UI Changes

### AgenticEditing Tab - Configuration Section

Add checkbox below existing configuration options:

```html
<!-- Debug Image Logging -->
<div class="agent-config-row">
    <label class="checkbox-label">
        <input type="checkbox" id="editAgentLogImages">
        Log images sent to VLM
    </label>
    <span class="config-hint">Saves PNG + base64 to AgenticEditingImages/</span>
</div>
```

**Location:** `workspace.html` in the AgenticEditing Configuration section, after the Debug Seeds row (around line 1920).

### JavaScript Changes

In `agent_editing.js`:

1. Add `logImages` to the state object
2. Include in `startAgent()` payload
3. Add to the disabled inputs list during agent run

```javascript
// In startAgent() function, add to payload:
const payload = {
    // ... existing fields ...
    log_images: document.getElementById('editAgentLogImages')?.checked || false,
};
```

---

## Backend Changes

### 1. Agent API Endpoint

**File:** `src/fish_scale_ui/routes/agent_api.py`

**Function:** `start_edit_agent()` (around line 230)

Add `--log-images` flag to CLI command:

```python
log_images = data.get('log_images', False)

# Add to command
if log_images:
    cmd.append('--log-images')
```

### 2. CLI Option

**File:** `src/fish_scale_agent/cli.py`

**Function:** `edit` command

Add option:

```python
@click.option(
    '--log-images',
    is_flag=True,
    default=False,
    help='Log images sent to VLM to AgenticEditingImages/ folder'
)
def edit(image, provider, model, calibration, max_iterations, ..., log_images):
    # Pass to editing_agent.run()
```

### 3. EditingAgent Class

**File:** `src/fish_scale_agent/editing_agent.py`

#### 3.1 Add initialization parameter

```python
async def run(
    self,
    image_path: str | None = None,
    calibration: float | None = None,
    max_iterations: int = 30,
    # ... existing params ...
    log_images: bool = False,  # NEW
) -> EditingState:
```

#### 3.2 Add image logging state

```python
# In run(), after initialization:
self._log_images = log_images
self._image_log_counter = 0
self._image_log_dir: Path | None = None
self._image_basename: str = ""
self._model_name: str = ""

if log_images:
    self._setup_image_logging(image_path)
```

#### 3.3 Add setup method

```python
def _setup_image_logging(self, image_path: str | None):
    """Set up directory and naming for image logging."""
    # Create output directory
    self._image_log_dir = Path("AgenticEditingImages")
    self._image_log_dir.mkdir(exist_ok=True)

    # Extract base image name (without extension)
    if image_path:
        self._image_basename = Path(image_path).stem
    else:
        self._image_basename = "unknown"

    # Get model name from provider
    self._model_name = getattr(self.provider, 'model', 'unknown_model')
    # Sanitize for filename (replace / with -)
    self._model_name = self._model_name.replace('/', '-').replace('\\', '-')

    self._log(f"Image logging enabled: {self._image_log_dir}/")
```

#### 3.4 Add logging method

```python
def _log_vlm_image(self, image_b64: str):
    """Log an image being sent to the VLM."""
    if not self._log_images or not self._image_log_dir:
        return

    import base64
    from datetime import datetime
    from PIL import Image
    from io import BytesIO

    self._image_log_counter += 1

    # Build filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    counter = f"{self._image_log_counter:03d}"
    base_name = f"{self._image_basename}_{self._model_name}_{timestamp}_{counter}"

    # Strip data URI prefix if present
    if image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]

    # Save base64 text file
    b64_path = self._image_log_dir / f"{base_name}_b64.txt"
    b64_path.write_text(image_b64)

    # Save decoded PNG
    try:
        image_bytes = base64.b64decode(image_b64)
        img = Image.open(BytesIO(image_bytes))
        png_path = self._image_log_dir / f"{base_name}.png"
        img.save(png_path, "PNG")

        self._log(f"Logged image #{self._image_log_counter}: {png_path.name} ({len(image_b64)} chars)")
    except Exception as e:
        self._log(f"Error saving image #{self._image_log_counter}: {e}")
```

#### 3.5 Call logging in _get_screenshot()

**Location:** `editing_agent.py` around line 390, after receiving screenshot response

```python
async def _get_screenshot(self) -> dict:
    """Get a screenshot from the UI."""
    # ... existing code to get screenshot ...

    result = response.json()
    if result.get("success") and result.get("image_b64"):
        # Log the image if enabled
        self._log_vlm_image(result["image_b64"])

        # ... rest of existing code ...
```

### 4. Sync Wrapper

**File:** `src/fish_scale_agent/editing_agent.py`

**Function:** `run_sync()` (around line 1065)

Add parameter passthrough:

```python
def run_sync(
    self,
    # ... existing params ...
    log_images: bool = False,  # NEW
) -> EditingState:
    return asyncio.run(self.run(
        # ... existing params ...
        log_images=log_images,
    ))
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `workspace.html` | Add checkbox `#editAgentLogImages` in Configuration section |
| `agent_editing.js` | Read checkbox value, include in API payload |
| `agent_api.py` | Pass `--log-images` flag to CLI command |
| `cli.py` | Add `--log-images` option to `edit` command |
| `editing_agent.py` | Add `log_images` param, `_setup_image_logging()`, `_log_vlm_image()` methods |

---

## Implementation Order

### Phase 1: Backend (editing_agent.py) - COMPLETE (v0.2.18)

1. ✅ Add `log_images` parameter to `run()` and `run_sync()`
2. ✅ Add `_setup_image_logging()` method
3. ✅ Add `_log_vlm_image()` method
4. ✅ Call `_log_vlm_image()` in `_get_screenshot()`

### Phase 2: CLI (cli.py) - COMPLETE (v0.2.18)

1. ✅ Add `--log-images` option to `edit` command
2. ✅ Pass to `editing_agent.run_sync()`

### Phase 3: UI Integration - COMPLETE (v0.2.18)

1. ✅ Add checkbox to `workspace.html`
2. ✅ Update `agent_editing.js` to read and send value
3. ✅ Update `agent_api.py` to pass flag

### Phase 4: Version Update - COMPLETE

✅ Updated to v0.2.18, then v0.2.19 with bug fixes.

### Phase 5: Bug Fixes (v0.2.19) - COMPLETE

1. ✅ **Settings persistence**: All AgenticEdit config options now persist via localStorage
2. ✅ **Image basename fix**: `_setup_image_logging()` now gets image name from UI state instead of `image_path` parameter, fixing "unknown" basename when image already loaded in UI

---

## Testing Checklist

### CLI Testing
- [ ] `--log-images` flag accepted
- [ ] `AgenticEditingImages/` directory created
- [ ] PNG files are valid, viewable images
- [ ] Base64 text files contain valid base64
- [ ] Filenames follow expected pattern
- [ ] Counter increments correctly across screenshots
- [ ] Multiple model names handled (claude-sonnet-4, gemini-2.0-flash)

### UI Testing
- [ ] Checkbox appears in AgenticEditing Configuration section
- [ ] Checkbox is disabled during agent run
- [ ] Checkbox state is sent to API
- [ ] Images logged when checkbox checked
- [ ] No images logged when checkbox unchecked

### Image Verification
- [ ] Logged PNG matches what VLM should see
- [ ] Base64 text decodes to same PNG
- [ ] Overlay (tubercles, connections) visible in logged images
- [ ] Scaling matches what VLM receives (768x768 max)

---

## Future Enhancements

1. **Automatic cleanup** - Delete old logged images after N days
2. **Compression option** - Save as JPG instead of PNG for smaller files
3. **Metadata file** - JSON sidecar with timestamp, iteration, tool call context
4. **Comparison tool** - Side-by-side view of logged image vs original
5. **Provider-specific logging** - Log what each provider actually receives (post-format)

---

## Diagnostic Use Cases

### Case 1: Image Corruption

Compare logged PNG to original image:
- If logged PNG is corrupted → Issue in `render_screenshot()` or base64 encoding
- If logged PNG looks correct → Issue is in VLM interpretation

### Case 2: Overlay Issues

Examine logged PNG for overlay rendering:
- Are tubercle circles visible?
- Are colors correct (cyan=extracted, green=manual, magenta=debug)?
- Are connections drawn correctly?

### Case 3: Scaling Problems

Check logged image dimensions:
- Should be max 768x768 (or smaller if aspect ratio differs)
- Verify no stretching/distortion
- Check if tiny details are lost in scaling

### Case 4: Provider Differences

Run same image with different providers, compare behavior:
- If Claude works but Gemini doesn't → Provider-specific image handling issue
- Log images for both, compare what each receives

---

## Notes

- The `AgenticEditingImages/` folder should be added to `.gitignore`
- Images can be large (1-2 MB each), logging many iterations can consume disk space
- Consider adding to CLAUDE.md once implemented
