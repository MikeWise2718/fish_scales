# LLM-Assisted Parameter Tuning - Architecture Alternatives

## Problem Statement

The fish-scale-ui has a complex set of image processing parameters (threshold, min/max diameter, circularity, CLAHE settings, blur sigma, neighbor graph type, etc.) that require specialist knowledge of image processing algorithms to tune effectively. The target users are paleontologists who are domain experts in fish fossils, not image processing.

**Goal:** Use an LLM-based agent to help users find good parameter settings through natural language interaction and visual feedback.

---

## Alternative 1: Embedded Chat Panel with Backend LLM

Add a chat interface directly in the existing Flask UI that communicates with an LLM backend.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Web UI                            │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │    Image Panel      │  │      Tabs Panel              │  │
│  │  ┌───────────────┐  │  │  ┌────────────────────────┐  │  │
│  │  │   Image +     │  │  │  │  Configure / Edit /    │  │  │
│  │  │   Overlay     │  │  │  │  Data / etc.           │  │  │
│  │  └───────────────┘  │  │  └────────────────────────┘  │  │
│  │  ┌───────────────┐  │  │  ┌────────────────────────┐  │  │
│  │  │  Stats Bar    │  │  │  │  💬 AI Assistant Chat  │  │  │
│  │  └───────────────┘  │  │  │  ┌──────────────────┐  │  │  │
│  └─────────────────────┘  │  │  │ Chat history     │  │  │  │
│                           │  │  │ ...              │  │  │  │
│                           │  │  └──────────────────┘  │  │  │
│                           │  │  [Type message...] [⏎] │  │  │
│                           │  └────────────────────────┘  │  │
│                           └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Flask Backend   │
                    │  /api/ai-chat    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  LLM API         │
                    │  (Claude/OpenRouter)
                    └──────────────────┘
```

### Data Flow

1. User types request in chat: "Find more tubercles" or "The circles are too big"
2. Frontend sends to `/api/ai-chat`:
   - User message
   - Current parameters (JSON)
   - Current statistics (TUB count, mean diameter, ITC count, mean spacing)
   - Optional: base64 screenshot of overlay
3. Backend constructs prompt with context, calls LLM API
4. LLM returns structured response:
   ```json
   {
     "message": "I'll lower the threshold to detect more tubercles...",
     "suggested_params": { "threshold": 0.08, "min_diameter": 4.0 },
     "auto_apply": false
   }
   ```
5. Frontend shows message in chat, offers "Apply" button for suggestions
6. User clicks Apply → params update → extraction runs → results shown
7. User evaluates, continues conversation

### Implementation Effort

- **New files:** `static/js/ai-assistant.js`, `/api/ai-chat` endpoint
- **Modifications:** Add chat panel to workspace.html, add AI settings (API key, model)
- **Estimated effort:** 1-2 days

---

## Alternative 2: MCP Server Integration

Create an MCP (Model Context Protocol) server that exposes the UI state as tools, allowing Claude Code or other MCP clients to control the application.

### Architecture

```
┌──────────────────┐         ┌──────────────────┐
│   Claude Code    │◄───────►│   MCP Server     │
│   (Terminal)     │  MCP    │   (Python)       │
│                  │         │                  │
│  User chats      │         │  Tools:          │
│  naturally       │         │  - get_params    │
│                  │         │  - set_params    │
└──────────────────┘         │  - run_extract   │
                             │  - get_stats     │
                             │  - get_screenshot│
                             └────────┬─────────┘
                                      │ HTTP
                                      ▼
                             ┌──────────────────┐
                             │  Flask Web UI    │
                             │  (Browser)       │
                             │                  │
                             │  User sees       │
                             │  results here    │
                             └──────────────────┘
```

### Data Flow

1. User runs `claude-code` with MCP server configured
2. User asks Claude: "Help me find the right parameters for this Lepisosteus image"
3. Claude Code calls MCP tools:
   - `get_screenshot()` → sees current image/overlay
   - `get_params()` → sees current settings
   - `get_stats()` → sees detection results
4. Claude analyzes, decides on new parameters
5. Claude calls `set_params({ threshold: 0.1, ... })`
6. Claude calls `run_extraction()`
7. Browser UI updates automatically (WebSocket or polling)
8. Claude calls `get_screenshot()` again to evaluate
9. Claude reports to user, asks for feedback
10. Iterate until satisfied

### Implementation Effort

- **New files:** `src/fish_scale_mcp/server.py` (MCP server), WebSocket support in Flask
- **Dependencies:** `mcp` Python package
- **Estimated effort:** 2-3 days

---

## Alternative 3: Embedded Assistant with Visual Feedback (Recommended)

Similar to Alternative 1, but the frontend captures a screenshot of the canvas (image + overlay) and sends it to the LLM, enabling visual reasoning.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Web UI                            │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │    Image Panel      │  │      Tabs Panel              │  │
│  │  ┌───────────────┐  │  │                              │  │
│  │  │   Canvas      │──┼──┼─► Screenshot capture         │  │
│  │  │   (toDataURL) │  │  │                              │  │
│  │  └───────────────┘  │  │  ┌────────────────────────┐  │  │
│  │                     │  │  │  🤖 AI Assistant       │  │  │
│  └─────────────────────┘  │  │  ┌──────────────────┐  │  │  │
│                           │  │  │ [Optimize]       │  │  │  │
│                           │  │  │ [More tubercles] │  │  │  │
│                           │  │  │ [Fewer false+]   │  │  │  │
│                           │  │  └──────────────────┘  │  │  │
│                           │  │  ┌──────────────────┐  │  │  │
│                           │  │  │ Custom: [______] │  │  │  │
│                           │  │  └──────────────────┘  │  │  │
│                           │  │                        │  │  │
│                           │  │  💡 Suggestion:        │  │  │
│                           │  │  "Lower threshold..."  │  │  │
│                           │  │  [Apply] [Dismiss]     │  │  │
│                           │  └────────────────────────┘  │  │
│                           └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼  POST /api/ai-suggest
                              │  { screenshot, params, stats, request }
                    ┌──────────────────┐
                    │  Flask Backend   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  LLM Provider    │
                    │  ┌────────────┐  │
                    │  │ Claude     │  │
                    │  │ Gemini     │  │
                    │  │ OpenRouter │  │
                    │  └────────────┘  │
                    └──────────────────┘
```

### Data Flow

1. User clicks "Optimize" or quick-action button, or types custom request
2. Frontend captures canvas screenshot via `canvas.toDataURL('image/png')`
3. Frontend sends to `/api/ai-suggest`:
   ```json
   {
     "screenshot": "data:image/png;base64,...",
     "params": { "threshold": 0.1, "min_diameter": 5.0, ... },
     "stats": { "tub_count": 45, "mean_diameter": 3.2, ... },
     "request": "find more tubercles",
     "image_filename": "P2_Fig1c_Paralepidosteus.tif"
   }
   ```
4. Backend constructs multimodal prompt:
   ```
   You are helping a paleontologist tune image processing parameters for
   fish scale analysis. You can see the current detection overlay.

   Current parameters: { ... }
   Current results: 45 tubercles, mean diameter 3.2 µm
   User request: "find more tubercles"

   [IMAGE: screenshot]

   Analyze the image and suggest parameter changes. Return JSON:
   { "explanation": "...", "params": { ... } }
   ```
5. LLM analyzes image, returns suggestions
6. Backend returns to frontend:
   ```json
   {
     "explanation": "I see several small tubercles that weren't detected. Lowering the threshold from 0.1 to 0.07 and reducing min_diameter to 4.0 should capture these.",
     "suggested_params": { "threshold": 0.07, "min_diameter": 4.0 },
     "confidence": "medium"
   }
   ```
7. Frontend shows suggestion with explanation
8. User clicks "Apply" → params applied → extraction runs
9. User evaluates new results, can iterate

### Quick Action Buttons

Pre-defined prompts for common requests:
- **"Optimize"** → "Analyze the current detection and suggest optimal parameters"
- **"More tubercles"** → "I need to detect more tubercles, some are being missed"
- **"Fewer false positives"** → "There are too many false detections in noisy areas"
- **"Larger tubercles"** → "The detected circles are too small"
- **"Smaller tubercles"** → "The detected circles are too large"

### Implementation Effort

- **New files:** `static/js/ai-assistant.js`, `services/llm_provider.py`, `/api/ai-suggest` endpoint
- **Modifications:** Add assistant panel to UI, screenshot capture logic, provider settings
- **Dependencies:** `anthropic`, `google-generativeai`, `openai` (for OpenRouter)
- **Estimated effort:** 2-3 days

---

## Alternative 4: Autonomous Playwright Agent

A standalone Python script that uses Playwright to control the browser and an LLM to decide actions.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Autonomous Agent                          │
│  ┌────────────────┐    ┌─────────────────┐                   │
│  │  Agent Loop    │───►│  LLM API        │                   │
│  │                │◄───│  (Claude)       │                   │
│  │  1. Screenshot │    └─────────────────┘                   │
│  │  2. Analyze    │                                          │
│  │  3. Act        │    ┌─────────────────┐                   │
│  │  4. Repeat     │───►│  Playwright     │                   │
│  └────────────────┘    │  Browser Control│                   │
│                        └────────┬────────┘                   │
└─────────────────────────────────┼────────────────────────────┘
                                  │
                                  ▼
                        ┌──────────────────┐
                        │  Flask Web UI    │
                        │  (Controlled     │
                        │   Browser)       │
                        └──────────────────┘
```

### Data Flow

1. User starts agent: `python agent.py --goal "optimize for Lepisosteus"`
2. Agent launches browser, navigates to fish-scale-ui
3. Agent loop:
   - Take screenshot via Playwright
   - Send to LLM with goal and action history
   - LLM returns next action: `{"action": "click", "target": "Configure tab"}`
   - Agent executes via Playwright
   - Repeat until LLM says "done" or user interrupts
4. Agent reports final parameters to user

### Implementation Effort

- **New files:** `tools/parameter_agent.py`
- **Dependencies:** `playwright`, LLM API
- **Estimated effort:** 3-4 days (more complex, more brittle)

---

## Comparison Matrix

| Aspect | Alt 1: Chat Panel | Alt 2: MCP Server | Alt 3: Visual Assistant | Alt 4: Playwright |
|--------|-------------------|-------------------|------------------------|-------------------|
| **Visual feedback** | ❌ Stats only | ✅ Via tool | ✅ Screenshot | ✅ Screenshot |
| **User experience** | Good (integrated) | Poor (2 interfaces) | Best (integrated) | Poor (autonomous) |
| **Implementation effort** | Low (1-2 days) | Medium (2-3 days) | Medium (2-3 days) | High (3-4 days) |
| **Flexibility** | Medium | High | Medium | Low |
| **Robustness** | High | High | High | Low (brittle) |
| **User control** | Full | Full | Full | Limited |
| **Works offline** | ❌ | ❌ | ❌ | ❌ |
| **API key needed** | Yes | Yes (Claude Code) | Yes | Yes |

---

## Recommendation

**Alternative 3 (Embedded Assistant with Visual Feedback)** offers the best balance:

1. **Integrated UX** - User stays in familiar interface
2. **Visual reasoning** - LLM can see actual results, not just stats
3. **User control** - Suggestions, not autonomous actions
4. **Reasonable effort** - 2-3 days to implement
5. **Iterative workflow** - Natural back-and-forth refinement

Alternative 1 could work as a fallback if visual analysis proves insufficient, but for image processing tasks, seeing the results is crucial for good suggestions.

---

## LLM Provider Options

The assistant should support multiple LLM providers with vision capabilities. Users can choose based on cost, performance, and existing API keys.

### Provider Comparison

| Provider | Models | Vision | Free Tier | Cost | Strengths |
|----------|--------|--------|-----------|------|-----------|
| **Claude (Anthropic)** | claude-sonnet-4, claude-opus-4 | ✅ | ❌ | ~$3/$15 per 1M tokens | Best reasoning, reliable structured output |
| **Gemini (Google)** | gemini-2.0-flash, gemini-2.5-pro | ✅ | ✅ Generous | ~$0.075/$0.30 per 1M tokens | Cheapest, resolution control, fast |
| **OpenRouter** | 100+ models | ✅ (varies) | ❌ | Pay-per-use | Model flexibility, single API for all |

### Claude API (Anthropic)

```python
import anthropic

client = anthropic.Anthropic(api_key="sk-ant-...")
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}},
            {"type": "text", "text": prompt}
        ]
    }]
)
```

**Pros:** Best reasoning quality, excellent at following structured output instructions
**Cons:** No free tier, higher cost

### Gemini API (Google)

```python
import google.generativeai as genai

genai.configure(api_key="AIza...")
model = genai.GenerativeModel("gemini-2.0-flash")
response = model.generate_content([
    {"mime_type": "image/png", "data": screenshot_bytes},
    prompt
])
```

**Pros:** Free tier for development, cheapest paid tier, `media_resolution` parameter for fine detail
**Cons:** Slightly less reliable at structured JSON output

### OpenRouter API

```python
import openai

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-..."
)
response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4",  # or google/gemini-2.0-flash, etc.
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            {"type": "text", "text": prompt}
        ]
    }]
)
```

**Pros:** Single API for 100+ models, easy to switch models, pay only for what you use
**Cons:** Slight latency overhead, need to know which models support vision

### Recommended Default

**Gemini 2.0 Flash** for development and cost-conscious users (free tier, fast, cheap)
**Claude Sonnet** for best quality suggestions (better reasoning)
**OpenRouter** for flexibility (user can pick any model)

---

## Open Questions

### Q1: Which LLM providers to support?

**Proposed:** Support all three (Claude, Gemini, OpenRouter) with a provider dropdown in Settings

*Rationale:*
- Gemini free tier great for development/testing
- Claude for users who want best quality
- OpenRouter for power users who want model flexibility
- Abstraction layer in backend makes adding providers easy

*Implementation:*
```python
# services/llm_provider.py
class LLMProvider:
    def suggest_params(self, screenshot_b64, params, stats, request) -> dict:
        raise NotImplementedError

class ClaudeProvider(LLMProvider): ...
class GeminiProvider(LLMProvider): ...
class OpenRouterProvider(LLMProvider): ...
```

- [ ] Accepted (all three providers)
- [ ] Alternative: _________________________________

---

### Q2: Where should API keys be stored/configured?

**Proposed:** Settings tab in UI with localStorage persistence, or environment variable

*Rationale:*
- Settings tab keeps everything in one place
- localStorage means user doesn't re-enter key each session
- Environment variable option for server deployment

- [ ] Accepted
- [ ] Alternative: _________________________________

---

### Q3: Should the assistant auto-apply suggestions or always require user confirmation?

**Proposed:** Always require confirmation (show suggestion + "Apply" button)

*Rationale:*
- User stays in control
- Can review explanation before changing params
- Builds trust - user sees what's happening
- Can iterate if suggestion doesn't help

- [ ] Accepted
- [ ] Alternative: _________________________________

---

### Q4: Should there be a conversation history or just single-shot suggestions?

**Proposed:** Start with single-shot (stateless suggestions), add conversation history if needed

*Rationale:*
- Simpler to implement
- Each request includes full context (screenshot + params + stats)
- Conversation history adds complexity (managing state, token limits)
- Can upgrade later if users want multi-turn refinement

- [ ] Accepted
- [ ] Alternative: _________________________________

---

### Q5: What's the fallback if screenshot capture fails or is too large?

**Proposed:** Fall back to stats-only mode with a warning

*Rationale:*
- Screenshot capture should work (canvas.toDataURL is well-supported)
- Could resize/compress if too large (> 5MB)
- Stats-only still useful, just less accurate

- [ ] Accepted
- [ ] Alternative: _________________________________

---

### Q6: Should there be preset "optimization profiles" the LLM can suggest?

**Proposed:** Yes, LLM can suggest existing profiles (paralepidosteus, polypterus, etc.) when appropriate

*Rationale:*
- Profiles encode known-good parameters for specific species
- LLM can recognize "this looks like Polypterus" and suggest that profile
- Reduces number of individual parameter changes needed

- [ ] Accepted
- [ ] Alternative: _________________________________

---

## Implementation Plan (if Alternative 3 accepted)

### Phase 1: Basic Infrastructure
- [ ] Add "AI Assistant" tab or panel to UI
- [ ] Implement screenshot capture (`canvas.toDataURL`)
- [ ] Create `/api/ai-suggest` endpoint skeleton
- [ ] Add LLM provider settings to Settings tab:
  - Provider dropdown (Gemini, Claude, OpenRouter)
  - API key input (per provider)
  - Model selection (provider-specific options)

### Phase 2: LLM Provider Abstraction
- [ ] Create `services/llm_provider.py` with base class
- [ ] Implement `GeminiProvider` (start here - free tier for testing)
- [ ] Implement `ClaudeProvider`
- [ ] Implement `OpenRouterProvider`
- [ ] Design shared prompt template for parameter suggestions
- [ ] Parse LLM response, extract suggested params (handle provider differences)

### Phase 3: UI Polish
- [ ] Display suggestions with explanation
- [ ] Add "Apply" / "Dismiss" buttons
- [ ] Add quick-action preset buttons
- [ ] Add loading state during LLM call
- [ ] Handle errors gracefully (API errors, rate limits, invalid keys)

### Phase 4: Refinement
- [ ] Test with various images and scenarios
- [ ] Tune prompt for better suggestions
- [ ] Add profile suggestion capability
- [ ] Optimize screenshot size/quality (resize if > 1MB)
- [ ] Add cost estimation display (tokens used, approx cost)
