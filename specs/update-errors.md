# AgenticExtraction Tab - LLM Communication Display Issues

**Date:** 2026-01-14
**Status:** RESOLVED
**Version:** 0.1.2

## Problem Description

In the Agent Extraction tab, the "LLM Communication" section has two containers that are not displaying correctly:

### 1. "Last LLM Prompt" Container
**Expected:** The full JSON prompt sent to the LLM (system message, tools, messages array) with base64 image data truncated.

**Actual:** Shows only the statistics header followed by "Waiting for first LLM call..." even after multiple LLM calls have been made:
```
--- Prompt Statistics ---
Iteration: 3/10
Hexagonalness: 0.720
Tubercles: 45
ITC: 89
Prompt Size: 156.2 KB
-------------------------

(Waiting for first LLM call...)
```

### 2. "Last LLM Response" Container
**Expected:** The full JSON response from the LLM (text, tool_calls, stop_reason, usage).

**Actual:** Shows what appears to be tool call action logs or other unrelated content instead of the actual LLM response JSON.

## Technical Analysis

### Relevant Files
- `src/fish_scale_ui/static/js/agent_extraction.js` - Frontend JavaScript handling display
- `src/fish_scale_agent/extraction_optimizer.py` - Backend agent that emits log lines

### Data Flow
1. The agent (`extraction_optimizer.py`) emits log lines including:
   - `LLM-Prompt: {...}` - Full prompt JSON with pipes replacing newlines
   - `LLM-Response: {...}` - Full response JSON with pipes replacing newlines
   - `Prompt-Stats: size=12345` - Prompt size statistics

2. Log lines are captured by `agent_api.py` monitor thread and stored in status file

3. Frontend polls `/api/agent/status/{session_id}` and receives `log_lines` array

4. `parseLogLines()` in `agent_extraction.js` should extract prompt/response from log lines and store in:
   - `state.lastPrompt` - for display in "Last LLM Prompt"
   - `state.currentReasoning` - for display in "Last LLM Response"

5. `updateLLMDisplay()` reads these state values and updates the DOM

### Attempted Fix (2026-01-14)
Moved the prompt/response parsing to the TOP of the `parseLogLines()` loop, before any `continue` statements:

```javascript
function parseLogLines(logLines) {
    for (const line of logLines.slice(-20)) {
        // Parse LLM prompt/response lines FIRST before any continue statements
        const promptMatch = line.match(/LLM-Prompt:\s*(.+)$/i);
        if (promptMatch) {
            state.lastPrompt = promptMatch[1].replace(/ \| /g, '\n');
            continue;
        }

        const responseMatch = line.match(/LLM-Response:\s*(.+)$/i);
        if (responseMatch) {
            state.currentReasoning = responseMatch[1].replace(/ \| /g, '\n');
            continue;
        }
        // ... rest of parsing
    }
}
```

**Result:** Fix did not resolve the issue. The containers still show incorrect content.

## Possible Root Causes to Investigate

1. **Log lines not reaching frontend:** The `LLM-Prompt:` and `LLM-Response:` lines may not be included in the `log_lines` array returned by the status API.

2. **Regex not matching:** The regex patterns may not match the actual format of the log lines (encoding issues, different delimiters, etc.).

3. **Lines truncated:** The status API only keeps last 50 lines (`log_lines[-50:]`). Long prompt/response lines might be getting dropped or the relevant lines might have scrolled out.

4. **Backend not emitting lines:** The `extraction_optimizer.py` may not be emitting `LLM-Prompt:` and `LLM-Response:` lines in the expected format.

5. **Timing issue:** The lines may be parsed before the prompt/response lines arrive, or the state may be getting reset.

## Debugging Steps

1. Check browser console for any errors in `parseLogLines()` or `updateLLMDisplay()`

2. Add console.log to see raw `log_lines` content:
   ```javascript
   console.log('Raw log lines:', logLines);
   ```

3. Verify backend is emitting the lines by checking the agent log file directly:
   ```
   %TEMP%/fish-scale-agent/agent-{session_id}.log
   ```

4. Check if lines contain `LLM-Prompt:` pattern:
   ```javascript
   const hasPrompt = logLines.some(l => l.includes('LLM-Prompt:'));
   console.log('Has prompt line:', hasPrompt);
   ```

## Expected Log Line Format

From CLAUDE.md documentation:
```
[HH:MM:SS] LLM-Prompt: { | "system": "...", | "tools": [...], | "messages": [...] | }
[HH:MM:SS] LLM-Response: { | "text": "...", | "tool_calls": [...] | }
```

The `|` characters replace newlines for single-line logging, and should be converted back to newlines for display.

## Resolution (2026-01-14)

### Root Causes Identified

1. **Missing prompt/response data in OpenRouter and Gemini providers**: The `AgentIteration` dataclass has optional fields `prompt_content`, `prompt_size_bytes`, and `response_json` for logging LLM communication. The Claude provider populated these fields, but the OpenRouter and Gemini providers did not. Since the user was using OpenRouter, the `LLM-Prompt:` and `LLM-Response:` log lines were never emitted.

2. **Insufficient log line buffer in frontend**: The `parseLogLines()` function only checked the last 20 lines (`logLines.slice(-20)`), but the backend keeps 50 lines. If many tool calls occurred between LLM iterations, the prompt/response lines could scroll out of the 20-line window.

### Fixes Applied

1. **OpenRouter provider** (`src/fish_scale_agent/providers/openrouter.py`):
   - Added `_truncate_base64()` and `_serialize_prompt()` helper functions
   - Updated `AgentIteration` creation to include `prompt_content`, `prompt_size_bytes`, and `response_json`

2. **Gemini provider** (`src/fish_scale_agent/providers/gemini.py`):
   - Added `_truncate_base64()` and `_serialize_prompt_gemini()` helper functions
   - Updated `AgentIteration` creation to include `prompt_content`, `prompt_size_bytes`, and `response_json`

3. **Frontend** (`src/fish_scale_ui/static/js/agent_extraction.js`):
   - Changed `parseLogLines()` to process all log lines instead of just the last 20

### Additional Changes

- Renamed "Agent Extraction" tab to "AgenticExtraction" (one word)
- Moved AgenticExtraction tab to appear right after the Extraction tab
- Updated version date format to include full UTC datetime (e.g., "2026-01-14T18:30:00Z")
