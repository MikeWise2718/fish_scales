# Parameter and State Synchronization Specification

## Overview

This specification documents issues with parameter and state synchronization across the Fish Scale UI, particularly focusing on:
1. Agent Extraction tab parameter tracking
2. Configure tab synchronization
3. Set copy/create operations
4. Cross-module state coherence

## Issues Identified

### Issue 1: Missing `setParams()` Function in Configure Module

**Severity:** High
**Location:** `src/fish_scale_ui/static/js/configure.js`

**Problem:**
The `configure` module exports the following functions:
```javascript
return {
    getParams,
    markExtracted,
    checkParamsChanged,
    applyProfile,
    resetToDefaults,
    undo,
    defaults,
};
```

There is **no `setParams()` function**, yet it is called from multiple locations:

1. **`agent_extraction.js:315`** - `window.configure.setParams?.(state.bestParams)` (uses optional chaining, silently fails)
2. **`data.js:466`** - `window.configure.setParams(params)` (would throw error if executed)

**Impact:**
- "Accept Best" in Agent Extraction does nothing to update Configure tab
- "Restore Parameters" from history in Data tab fails silently or throws error
- No programmatic way to update Configure tab form controls

**Solution:**
Add a `setParams(params)` function to `configure.js` that:
1. Pushes current state to undo history
2. Applies params to form controls via `applyParamsToForm()` (already exists as private function)
3. Updates `currentParams` state
4. Saves to localStorage
5. Triggers `checkParamsChanged()`
6. Export it in the return object

---

### Issue 2: Agent Parameters Not Synced to Configure Tab During Optimization

**Severity:** High
**Location:** `src/fish_scale_ui/static/js/agent_extraction.js`

**Problem:**
When the agent optimization runs:
1. Agent changes parameters via `POST /api/tools/params`
2. `pollStatus()` fetches current params from `/api/tools/params`
3. `updateParams()` displays them in `agentParamsDisplay` (read-only display in Agent Extraction tab)
4. **Configure tab form controls are NEVER updated**

The user sees parameters change in the Agent Extraction tab's "Current Parameters" section but the actual Configure tab sliders/inputs remain unchanged.

**Impact:**
- User cannot see current extraction parameters in Configure tab while agent runs
- After optimization completes, Configure tab shows stale (pre-optimization) values
- Manual re-extraction would use wrong parameters

**Solution:**
In `pollStatus()` (agent_extraction.js), after fetching params from `/api/tools/params`, call:
```javascript
if (window.configure?.setParams && currentParams) {
    window.configure.setParams(currentParams);
}
```

This requires Issue 1 to be fixed first.

---

### Issue 3: Parameters Not Copied When Creating Set via "Copy From"

**Severity:** Medium
**Location:** `src/fish_scale_ui/static/js/setUI.js:240-277`

**Problem:**
In `createSetFromDialog()`, when user selects "Copy from" another set:
```javascript
if (content === 'copy' && copyFromSelect) {
    const sourceSetId = copyFromSelect.value;
    const sourceSet = window.sets.getSet(sourceSetId);
    if (sourceSet) {
        options = {
            tubercles: JSON.parse(JSON.stringify(sourceSet.tubercles)),
            edges: JSON.parse(JSON.stringify(sourceSet.edges)),
            // MISSING: parameters: sourceSet.parameters
        };
    }
}
```

The `parameters` property is NOT copied, even though:
- `sets.createSet()` supports a `parameters` option
- `sets.duplicateSet()` correctly passes parameters

**Impact:**
- New set created via "Copy from" loses the extraction parameters that created the original data
- User cannot restore original parameters from the copied set
- "Restore Parameters" button in history would not work properly

**Solution:**
Add parameters to the options in `createSetFromDialog()`:
```javascript
options = {
    tubercles: JSON.parse(JSON.stringify(sourceSet.tubercles)),
    edges: JSON.parse(JSON.stringify(sourceSet.edges)),
    parameters: sourceSet.parameters,  // ADD THIS
};
```

---

### Issue 4: MCP API Parameters vs UI Parameters Desynchronization

**Severity:** Medium
**Location:** `src/fish_scale_ui/routes/mcp_api.py` and `src/fish_scale_ui/routes/api.py`

**Problem:**
The MCP API stores parameters in `_extraction_data['parameters']` (server-side Python dict), while the UI stores parameters in:
1. `configure.js` - localStorage and form controls
2. `sets.js` - per-set parameters in JavaScript

When the agent calls `POST /api/tools/params`, it only updates the server-side state. The UI has no notification mechanism to know parameters changed.

**Impact:**
- Server and client can have different parameter values
- No WebSocket or polling mechanism to sync parameter changes
- UI refresh required to see server-side changes

**Solution Options:**
1. **Polling approach** (simplest): `agent_extraction.js` already polls `/api/tools/params` and can sync to Configure tab (requires Issue 1)
2. **Event approach**: Add Server-Sent Events (SSE) endpoint for real-time parameter change notifications
3. **State refresh**: Add explicit "Refresh from Server" button in Configure tab

Recommended: Use polling approach since agent_extraction already does this.

---

### Issue 5: Configure Tab Updates Don't Propagate to Server During Agent Run

**Severity:** Low
**Location:** `src/fish_scale_ui/static/js/configure.js`

**Problem:**
If user manually changes Configure tab controls while agent is running:
1. Changes are saved to localStorage
2. Changes are NOT sent to server via `/api/tools/params`
3. Agent continues using server-side parameters

**Impact:**
- User cannot manually intervene in agent optimization via Configure tab
- Potential confusion about which parameters are "active"

**Solution:**
Either:
1. Disable Configure tab controls while agent is running (cleanest)
2. Add `POST /api/tools/params` call when params change in Configure tab
3. Show warning that changes won't affect running agent

Recommended: Option 1 - disable controls during agent run.

---

### Issue 6: Set Switching Doesn't Update Configure Tab

**Severity:** Medium
**Location:** `src/fish_scale_ui/static/js/setUI.js:893-908`

**Problem:**
When switching sets via `setChanged` event:
```javascript
document.addEventListener('setChanged', (e) => {
    renderSetButtons();
    updateAllSetIndicators();
    closeAllMenus();

    const set = e.detail.set;
    if (set) {
        window.overlay?.setData(set.tubercles, set.edges);
        window.editor?.setData(set.tubercles, set.edges);
        // Calculate statistics...
        window.data?.setData(set.tubercles, set.edges, stats);
    }
});
```

The Configure tab is NOT updated with the new set's parameters, even though each set stores its own `parameters` property.

**Impact:**
- Switching to a set with different extraction parameters doesn't update Configure tab
- User sees old parameters that don't match the current set's data

**Solution:**
Add to the `setChanged` handler:
```javascript
if (set.parameters && window.configure?.setParams) {
    window.configure.setParams(set.parameters);
}
```

This requires Issue 1 to be fixed first.

---

### Issue 7: Agent Extraction Tab Missing Parameter Display Improvements

**Severity:** Low
**Location:** `src/fish_scale_ui/static/js/agent_extraction.js:762-798`

**Problem:**
The `updateParams()` function displays parameters in `agentParamsDisplay`, but:
1. Only shows a subset of parameters with hardcoded display names
2. Missing parameters: `cull_long_edges`, `cull_factor`, `clahe_kernel`
3. No indication when parameters changed from previous iteration

**Impact:**
- Incomplete parameter visibility during optimization
- No visual cue when agent adjusts parameters

**Solution:**
1. Add missing parameters to `displayNames` map
2. Add visual highlighting when parameter values change
3. Consider showing delta from previous iteration

---

### Issue 8: Duplicate `calculateHexagonalness` Implementations

**Severity:** Low (maintainability)
**Locations:**
- `extraction.js:409-493`
- `setUI.js:1001-1086`
- `editor.js` (assumed, per CLAUDE.md)
- `mcp_api.py:960-1077`
- `measurement.py` (Python core)

**Problem:**
Multiple implementations of `calculateHexagonalness` must stay in sync. While tests exist (`test_hexagonalness_consistency.py`), the JavaScript implementations are duplicated.

**Impact:**
- Bug fixes must be applied to multiple locations
- Risk of implementations drifting apart

**Solution:**
Extract JavaScript implementation to a shared utility module that all JS files import.

---

## Implementation Plan

### Phase 1: Core Infrastructure (High Priority)

1. **Add `setParams()` to configure.js** (Issue 1)
   - Create function that wraps `applyParamsToForm()`
   - Push to undo stack
   - Update state and localStorage
   - Export in return object

2. **Sync parameters to Configure tab during agent run** (Issue 2)
   - Modify `pollStatus()` in agent_extraction.js
   - Call `window.configure.setParams()` after fetching from API

3. **Fix set copy parameters** (Issue 3)
   - Add `parameters: sourceSet.parameters` in `createSetFromDialog()`

### Phase 2: State Coherence (Medium Priority)

4. **Update Configure tab on set switch** (Issue 6)
   - Modify `setChanged` handler in setUI.js
   - Call `window.configure.setParams(set.parameters)` if available

5. **Disable Configure controls during agent run** (Issue 5)
   - Add `setEnabled(enabled)` function to configure.js
   - Call from agent_extraction.js when starting/stopping

### Phase 3: Polish (Low Priority)

6. **Improve Agent Extraction parameter display** (Issue 7)
   - Add missing parameters
   - Add change highlighting

7. **Consolidate hexagonalness implementations** (Issue 8)
   - Create `static/js/hexagonalness.js` utility
   - Refactor callers to use shared implementation

---

## Testing Checklist

### Manual Testing

- [ ] Agent Extraction: Parameters update in real-time in both Agent tab and Configure tab
- [ ] Agent Extraction: "Accept Best" applies parameters to Configure tab
- [ ] Data Tab: "Restore Parameters" from history updates Configure tab
- [ ] Set Operations: "Copy from" includes extraction parameters
- [ ] Set Operations: Switching sets updates Configure tab if set has parameters
- [ ] Configure Tab: Controls disabled during agent optimization
- [ ] Configure Tab: Controls re-enabled after agent completes/stops

### Automated Testing

- [ ] Add test for `configure.setParams()` function
- [ ] Add E2E test for agent parameter sync
- [ ] Verify hexagonalness consistency tests still pass

---

## Files to Modify

| File | Changes |
|------|---------|
| `static/js/configure.js` | Add `setParams()`, `setEnabled()`, export them |
| `static/js/agent_extraction.js` | Call `configure.setParams()` in `pollStatus()` and `acceptBest()` |
| `static/js/setUI.js` | Fix `createSetFromDialog()`, add parameter sync on set switch |
| `static/js/data.js` | No changes needed (uses `configure.setParams()` which will exist) |

---

## Appendix: Current Data Flow

### Parameter Sources and Consumers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Parameter State                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│  │  localStorage │      │  Server-side │      │   Set.params │       │
│  │  (configure) │      │ _extraction_ │      │  (per-set)   │       │
│  │              │      │    data      │      │              │       │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘       │
│         │                      │                      │              │
│         │                      │                      │              │
│         ▼                      ▼                      ▼              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│  │  Configure   │      │  MCP API     │      │   Sets UI    │       │
│  │  Tab Form    │◄────►│  /api/tools/ │◄────►│  Module      │       │
│  │  Controls    │  ✗   │  params      │  ✗   │              │       │
│  └──────────────┘      └──────────────┘      └──────────────┘       │
│         │                      │                      │              │
│         │        ✗ = Missing   │        ✗ = Missing   │              │
│         │          Sync        │          Sync        │              │
│         ▼                      ▼                      ▼              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│  │  /api/extract│      │  LLM Agent   │      │  History     │       │
│  │  (manual)    │      │  (automated) │      │  Restore     │       │
│  └──────────────┘      └──────────────┘      └──────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Legend:
  ◄──► = Current data flow
  ✗    = Missing synchronization (to be fixed)
```

### After Fix

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Parameter State                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│  │  localStorage │      │  Server-side │      │   Set.params │       │
│  │  (configure) │      │ _extraction_ │      │  (per-set)   │       │
│  │              │      │    data      │      │              │       │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘       │
│         │                      │                      │              │
│         │    setParams()       │    setParams()       │              │
│         ▼         │            ▼         │            ▼              │
│  ┌──────────────┐ │    ┌──────────────┐ │    ┌──────────────┐       │
│  │  Configure   │◄┼───►│  MCP API     │◄┼───►│   Sets UI    │       │
│  │  Tab Form    │ │    │  /api/tools/ │ │    │  Module      │       │
│  │  Controls    │◄┼────│  params      │─┼───►│              │       │
│  └──────────────┘ │    └──────────────┘ │    └──────────────┘       │
│         │         │            │         │            │              │
│         │         │            │         │            │              │
│         ▼         │            ▼         │            ▼              │
│  ┌──────────────┐ │    ┌──────────────┐ │    ┌──────────────┐       │
│  │  /api/extract│ │    │  LLM Agent   │ │    │  History     │       │
│  │  (manual)    │ │    │  (automated) │◄┘    │  Restore     │◄──────┤
│  └──────────────┘ │    └──────────────┘      └──────────────┘       │
│                   │                                                  │
│                   └──────── All paths lead to setParams() ──────────┤
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
