# Dataset History Tracking Specification

**Status:** Proposed
**Created:** 31 December 2025
**Purpose:** Track the provenance and evolution of annotation datasets to enable reproducibility and understanding of how results were obtained.

---

## 1. Overview

### Problem Statement

Users cannot easily understand how a dataset evolved:
- What extraction parameters were used?
- What manual edits were made?
- Was an LLM agent involved?
- **Who** made the changes?
- Can the results be reproduced?

### Solution

Add a `history` array to each annotation set that records:
1. **Creation events** (extraction, clone, import)
2. **Modification events** (manual edits, auto-connect, agent iterations)
3. **All parameters needed to reproduce the operation**
4. **The user who performed each action**

Display this history in a collapsible section in the Data tab.

### Multi-User Support

The system supports multiple users working on the same datasets. Each history event records which user performed the action, enabling:
- Attribution of changes
- Filtering history by user
- Understanding collaborative workflows

---

## 2. Data Model

### 2.1 History Array Location

Each set in the SLO v2 format gains a `history` array:

```json
{
  "version": 2,
  "sets": [
    {
      "id": "set_123",
      "name": "Extraction 1",
      "tubercles": [...],
      "edges": [...],
      "history": [
        { /* event 1 */ },
        { /* event 2 */ },
        ...
      ]
    }
  ]
}
```

### 2.2 Event Types

| Event Type | Trigger | Key Data Stored |
|------------|---------|-----------------|
| `extraction` | Run extraction button | All extraction parameters, calibration |
| `auto_connect` | Regenerate connections | Graph type, culling params |
| `manual_edit` | Save after manual edits | Summary of changes (+/- counts) |
| `agent_phase` | LLM agent completes a phase | Provider, model, phase name, iteration count |
| `clone` | Duplicate set | Source set ID and name |
| `import` | Load from v1 SLO or legacy | Source file, original creation date |

### 2.3 Base Event Schema

All events share these fields:

```json
{
  "timestamp": "2025-12-31T10:30:00.000Z",
  "event": "extraction",
  "user": "Mike Wise",
  "result": {
    "tubercle_count": 43,
    "edge_count": 112
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | ISO 8601 string | Yes | When the event occurred |
| `event` | string | Yes | Event type identifier |
| `user` | string | Yes | Display name of user who performed action |
| `result` | object | Yes | Counts after the operation |

### 2.4 Event-Specific Schemas

#### Extraction Event

```json
{
  "timestamp": "2025-12-31T10:30:00.000Z",
  "event": "extraction",
  "user": "Mike Wise",
  "params": {
    "method": "log",
    "threshold": 0.15,
    "min_diameter_um": 5.0,
    "max_diameter_um": 15.0,
    "min_circularity": 0.35,
    "clahe_clip": 0.03,
    "clahe_kernel": 8,
    "blur_sigma": 1.0,
    "neighbor_graph": "gabriel",
    "cull_long_edges": true,
    "cull_factor": 1.8
  },
  "calibration": {
    "um_per_pixel": 0.33,
    "method": "manual"
  },
  "profile": "paralepidosteus",
  "result": {
    "tubercle_count": 43,
    "edge_count": 112
  }
}
```

#### Auto-Connect Event

```json
{
  "timestamp": "2025-12-31T10:35:00.000Z",
  "event": "auto_connect",
  "user": "Mike Wise",
  "params": {
    "graph_type": "gabriel",
    "cull_long_edges": true,
    "cull_factor": 1.8
  },
  "result": {
    "tubercle_count": 43,
    "edge_count": 98
  }
}
```

#### Manual Edit Event

Consolidates edits made between saves into a summary:

```json
{
  "timestamp": "2025-12-31T10:40:00.000Z",
  "event": "manual_edit",
  "user": "Mike Wise",
  "summary": "+5 tubercles, -2 tubercles, moved 3, +8 connections",
  "details": {
    "added_tubercles": 5,
    "deleted_tubercles": 2,
    "moved_tubercles": 3,
    "resized_tubercles": 0,
    "added_connections": 8,
    "deleted_connections": 0
  },
  "result": {
    "tubercle_count": 46,
    "edge_count": 106
  }
}
```

#### Agent Phase Event

For agent actions, the user is the person who initiated the agent run:

```json
{
  "timestamp": "2025-12-31T11:00:00.000Z",
  "event": "agent_phase",
  "user": "Mike Wise",
  "provider": "claude",
  "model": "claude-sonnet-4-20250514",
  "phase": "pattern_completion",
  "iterations": 15,
  "result": {
    "tubercle_count": 52,
    "edge_count": 0
  }
}
```

#### Clone Event

```json
{
  "timestamp": "2025-12-31T11:30:00.000Z",
  "event": "clone",
  "user": "Mike Wise",
  "source": {
    "set_id": "set_123",
    "set_name": "Extraction 1"
  },
  "result": {
    "tubercle_count": 52,
    "edge_count": 128
  }
}
```

#### Import Event (for legacy files)

```json
{
  "timestamp": "2025-12-31T12:00:00.000Z",
  "event": "import",
  "user": "Mike Wise",
  "source": {
    "type": "slo_v1",
    "original_created": "2025-12-15T08:00:00.000Z"
  },
  "result": {
    "tubercle_count": 37,
    "edge_count": 95
  }
}
```

---

## 3. User Management

### 3.1 User Identity

Each user is identified by a display name string. This is intentionally simple for the initial implementation.

```json
{
  "user": "Mike Wise"
}
```

### 3.2 Default User

The default user is **"Mike Wise"**. This is used when no user is explicitly configured.

### 3.3 User Configuration

The current user can be configured through multiple methods (in order of precedence):

1. **Environment Variable**: `FISH_SCALE_USER`
   ```bash
   export FISH_SCALE_USER="Jane Smith"
   ```

2. **Configuration File**: `~/.fish-scale-ui/config.json`
   ```json
   {
     "user": "Jane Smith"
   }
   ```

3. **UI Settings**: In the Settings tab, a "User Name" field allows changing the current user
   - Stored in browser localStorage for persistence
   - Overrides environment variable and config file when set

4. **Default**: "Mike Wise" if none of the above are set

### 3.4 User in UI

The current user is displayed in:
- **Settings tab**: Editable field to change user name
- **Status bar** (optional): Show current user in footer/header
- **History events**: Each event shows who performed it

### 3.5 Implementation Details

#### Backend (Python)

```python
# In app.py or config.py
def get_current_user() -> str:
    """Get the current user name from environment or config."""
    # Check environment variable first
    if user := os.environ.get('FISH_SCALE_USER'):
        return user

    # Check config file
    config_path = Path.home() / '.fish-scale-ui' / 'config.json'
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            if user := config.get('user'):
                return user

    # Default
    return "Mike Wise"
```

#### Frontend (JavaScript)

```javascript
// In settings.js or a new user.js module
window.user = (function() {
    const STORAGE_KEY = 'fish_scale_user';
    const DEFAULT_USER = 'Mike Wise';

    function getCurrentUser() {
        // Check localStorage first (UI override)
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return stored;

        // Fall back to server-provided default
        return window.serverConfig?.user || DEFAULT_USER;
    }

    function setCurrentUser(name) {
        localStorage.setItem(STORAGE_KEY, name);
    }

    function clearUserOverride() {
        localStorage.removeItem(STORAGE_KEY);
    }

    return { getCurrentUser, setCurrentUser, clearUserOverride };
})();
```

### 3.6 Agent User Attribution

When the LLM agent performs actions, the user is the person who started the agent:

- Agent runner passes current user to MCP server
- MCP server includes user in all recorded events
- This ensures agent actions are attributed to the human operator

### 3.7 Future Considerations

For more advanced multi-user scenarios, consider:
- User authentication (login system)
- User IDs separate from display names
- User roles/permissions
- Audit logging

These are out of scope for the initial implementation.

---

## 4. UI Design

### 4.1 Location

Add a collapsible "Dataset History" section in the **Data tab**, positioned between the "Current Set" header and the "Statistics" section.

### 4.2 Collapsed State

```
▶ Dataset History (4 events)
```

### 4.3 Expanded State (with user attribution)

```
▼ Dataset History (4 events)
┌──────────────────────────────────────────────────────────────────┐
│ 10:30:00  Extraction (LoG, paralepidosteus)         [Mike Wise]  │
│           threshold=0.15, min_d=5.0µm, max_d=15.0µm              │
│           → 43 tubercles, 112 connections                        │
│           [Restore Params]                                       │
├──────────────────────────────────────────────────────────────────┤
│ 10:35:00  Auto-connect (Gabriel)                    [Mike Wise]  │
│           cull_factor=1.8                                        │
│           → 43 tubercles, 98 connections                         │
├──────────────────────────────────────────────────────────────────┤
│ 10:40:00  Manual Edits                              [Jane Smith] │
│           +5 tubercles, -2 tubercles, moved 3, +8 connections    │
│           → 46 tubercles, 106 connections                        │
├──────────────────────────────────────────────────────────────────┤
│ 11:00:00  Agent: Pattern Completion (Claude)        [Mike Wise]  │
│           claude-sonnet-4, 15 iterations                         │
│           → 52 tubercles, 106 connections                        │
└──────────────────────────────────────────────────────────────────┘
```

Note: User names are right-aligned and shown in brackets for each event.

### 4.4 Interactive Features

1. **Restore Parameters Button**
   For extraction events, clicking "Restore Params" loads the stored parameters into the Configure panel. Shows confirmation toast.

2. **Event Icons**
   Visual indicators for event types:
   - 🔍 Extraction
   - 🔗 Auto-connect
   - ✏️ Manual edit
   - 🤖 Agent phase
   - 📋 Clone
   - 📥 Import

3. **Hover Details**
   Hovering over abbreviated parameter lists shows full details in a tooltip.

4. **Responsive Design**
   On narrow viewports, parameter details collapse to icons-only with tooltips.

---

## 5. Edit Tracking Strategy

### 5.1 Problem

Recording every individual edit (each add/move/delete) would create excessively long histories and large files.

### 5.2 Solution: Consolidation on Save

1. **During Session**: Track edit operations in memory using counters:
   ```javascript
   pendingEdits = {
     added_tubercles: 0,
     deleted_tubercles: 0,
     moved_tubercles: 0,
     resized_tubercles: 0,
     added_connections: 0,
     deleted_connections: 0
   };
   ```

2. **On Save**: If any counters are non-zero, create a single `manual_edit` event summarizing all changes since the last history event.

3. **Reset Counters**: After save, reset all counters to zero.

### 5.3 What Triggers a New History Entry

| Action | Creates History Entry |
|--------|----------------------|
| Run Extraction | Yes - `extraction` event |
| Regenerate Connections | Yes - `auto_connect` event |
| Save (with pending edits) | Yes - `manual_edit` event |
| Save (no pending edits) | No |
| Agent phase completes | Yes - `agent_phase` event |
| Clone set | Yes - `clone` event on new set |
| Load v1 SLO | Yes - `import` event |

---

## 6. Implementation Areas

### 6.1 Backend (Python)

#### persistence.py

- Update `save_slo()` to include history arrays in set data
- Update `load_slo()` to preserve history when loading
- Add migration logic for v1 files (create `import` event with current user)

#### api.py

- Ensure extraction endpoint returns all params used (for history recording)
- Add endpoint to get extraction params from a history event (for "Restore Params")
- Add endpoint to get/set current user: `GET/POST /api/user`

#### extraction.py

- Return complete parameter dict with results for history recording

#### New file: user.py

```python
"""User management for multi-user support."""

import os
import json
from pathlib import Path

DEFAULT_USER = "Mike Wise"

def get_current_user() -> str:
    """Get the current user name."""
    # Environment variable takes precedence
    if user := os.environ.get('FISH_SCALE_USER'):
        return user

    # Check config file
    config_path = Path.home() / '.fish-scale-ui' / 'config.json'
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                if user := config.get('user'):
                    return user
        except (json.JSONDecodeError, IOError):
            pass

    return DEFAULT_USER
```

### 6.2 Frontend (JavaScript)

#### New file: user.js

```javascript
/**
 * User management module
 */
window.user = (function() {
    const STORAGE_KEY = 'fish_scale_user';
    const DEFAULT_USER = 'Mike Wise';

    // Server-provided user (from environment/config)
    let serverUser = DEFAULT_USER;

    function init(serverProvidedUser) {
        serverUser = serverProvidedUser || DEFAULT_USER;
    }

    function getCurrentUser() {
        // localStorage override takes precedence
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return stored;
        return serverUser;
    }

    function setCurrentUser(name) {
        if (name && name.trim()) {
            localStorage.setItem(STORAGE_KEY, name.trim());
        }
    }

    function clearUserOverride() {
        localStorage.removeItem(STORAGE_KEY);
    }

    return { init, getCurrentUser, setCurrentUser, clearUserOverride };
})();
```

#### sets.js

- Add `history` array to set structure
- Add `pendingEdits` tracking object
- Add methods:
  - `addHistoryEvent(event)` - automatically adds `user` and `timestamp`
  - `incrementPendingEdit(type)`
  - `getPendingEdits()`
  - `clearPendingEdits()`
  - `consolidatePendingEdits()` - creates manual_edit event if needed

#### extraction.js

- After successful extraction, call `sets.addHistoryEvent()` with extraction params
- After auto-connect, call `sets.addHistoryEvent()` with connect params

#### editor.js

- After each edit operation, call `sets.incrementPendingEdit(type)`
- Types: `added_tubercles`, `deleted_tubercles`, `moved_tubercles`, etc.

#### data.js

- New function `renderHistory(history)` to build the collapsible UI
- Handle "Restore Params" button click
- Show user attribution for each event
- Update when set changes

#### settings.js

- Add "User Name" field to Settings tab
- Load/save user preference via `window.user` module

#### New file: history.js (optional)

Could extract history rendering/interaction to a dedicated module.

### 6.3 HTML Template

#### workspace.html

Add the collapsible history section to Data tab:

```html
<!-- Dataset History Section -->
<div class="data-section history-section">
    <div class="history-header" id="historyHeader">
        <span class="collapse-icon">▶</span>
        <h3>Dataset History</h3>
        <span class="history-count" id="historyCount">(0 events)</span>
    </div>
    <div class="history-content" id="historyContent" style="display: none;">
        <div class="history-timeline" id="historyTimeline">
            <!-- Events rendered here by JavaScript -->
        </div>
    </div>
</div>
```

### 6.4 CSS

Add styles for:
- `.history-section` container
- `.history-header` with collapse/expand toggle
- `.history-event` individual event cards
- `.history-params` parameter display
- `.history-result` result counts
- `.restore-params-btn` button styling
- Event type icons/badges

---

## 7. Migration

### 7.1 Loading v1 SLO Files

When loading a v1 SLO file (no sets array):
1. Convert to v2 format with single set
2. Add an `import` event to history with current user:
   ```json
   {
     "timestamp": "<current_time>",
     "event": "import",
     "user": "<current_user>",
     "source": {
       "type": "slo_v1",
       "original_created": "<v1 created timestamp>"
     },
     "result": {
       "tubercle_count": <count>,
       "edge_count": <count>
     }
   }
   ```

### 7.2 Loading v2 SLO Files Without History

When loading a v2 SLO file where sets have no `history` array:
1. Initialize `history: []` for each set
2. Optionally add an import event with current user (or leave empty - "history unknown")

### 7.3 Saving

Always save with history arrays included. Backward compatibility is read-only.

---

## 8. SLO Format Version

Consider bumping to **SLO v2.1** to indicate history support:

```json
{
  "version": "2.1",
  "sets": [
    {
      "history": [...]
    }
  ]
}
```

Alternatively, keep as version 2 since history is an additive, optional field.

**Recommendation:** Keep as version 2, treat `history` as optional field.

---

## 9. Agent Integration

### 9.1 MCP Server Updates

The MCP server should record agent actions:
- After `run_extraction`: Record extraction event with user
- After `auto_connect`: Record auto_connect event with user
- After manual operations (add/move/delete): Increment pending edit counters

### 9.2 Agent Runner Updates

The agent runner should:
- Track which phase is executing
- Pass current user to MCP server for attribution
- On phase completion, trigger history event recording via MCP API

### 9.3 New MCP Endpoint

Add `/api/mcp/record-history` endpoint:

```json
POST /api/mcp/record-history
{
  "event": "agent_phase",
  "user": "Mike Wise",
  "provider": "claude",
  "model": "claude-sonnet-4-20250514",
  "phase": "pattern_completion",
  "iterations": 15
}
```

### 9.4 User Propagation for Agent

When the agent runs:
1. Agent CLI reads `FISH_SCALE_USER` env var (or defaults to "Mike Wise")
2. Agent passes user to MCP server with each request
3. MCP server includes user in all history events
4. This ensures all agent actions are attributed to the human operator

---

## 10. Implementation Phases

### Phase 1: User Management (Foundation)
1. Create `user.py` with `get_current_user()` function
2. Create `user.js` module for frontend
3. Add "User Name" field to Settings tab
4. Add `/api/user` endpoint
5. Pass server-provided default user to frontend

### Phase 2: Data Model & Storage
1. Update sets.js to include `history` array
2. Update `addHistoryEvent()` to automatically add `user` and `timestamp`
3. Update persistence.py to save/load history
4. Add migration for v1/v2-without-history files

### Phase 3: History Recording
1. Add history event creation for extraction (with user)
2. Add pending edit counters to sets.js
3. Instrument editor.js to increment counters
4. Consolidate edits on save (with user)
5. Add auto_connect event recording (with user)

### Phase 4: UI Display
1. Add collapsible history section to Data tab HTML
2. Implement history rendering with user attribution
3. Add CSS styling for history and user display
4. Implement expand/collapse interaction

### Phase 5: Restore Parameters
1. Add "Restore Params" button to extraction events
2. Implement parameter restoration to Configure panel
3. Add confirmation/feedback

### Phase 6: Agent Integration
1. Add agent_phase event recording with user
2. Update MCP endpoints to accept user parameter
3. Update agent runner to pass user to MCP server

---

## 11. Testing

### Unit Tests

- History event creation with all required fields including `user`
- User module: `getCurrentUser()` returns correct precedence
- Pending edit counter increment/consolidation
- History serialization/deserialization preserves user
- V1 migration creates import event with current user
- Restore params correctly populates Configure panel

### Integration Tests

- Full workflow: extract → edit → save → reload → verify history with users
- Multi-user workflow: different users make changes, verify attribution
- Agent workflow records all phases with user who started agent
- Clone preserves source set history + adds clone event with current user

### Manual Testing

- Visual verification of history display with user names
- User name field in Settings tab
- Different users shown with different colors/styles (optional)
- Collapse/expand interaction
- Restore params workflow
- Long history scrolling

---

## 12. Open Questions

1. **History size limit?**
   Should there be a maximum number of events? Suggest: No limit initially, monitor file sizes.

2. **Edit detail level?**
   Current proposal consolidates edits. Should we optionally store fine-grained edits?
   Suggest: Start with consolidation, add detail level option later if needed.

3. **Undo/redo relationship?**
   Should history track undo/redo operations, or only "committed" states?
   Suggest: Only track committed states (what exists at save time).

4. **Clone history inheritance?**
   When cloning a set, should the new set inherit the source's full history?
   Suggest: Yes, inherit history and append clone event. This preserves full provenance.

5. **User identity validation?**
   Should we validate/normalize user names (e.g., trim whitespace, max length)?
   Suggest: Yes, trim whitespace and limit to 50 characters.

6. **User color coding?**
   Should different users have distinct colors in the history display?
   Suggest: Optional future enhancement, not required for initial implementation.

7. **Anonymous/system user?**
   What user name for automated processes without explicit user (e.g., scheduled batch jobs)?
   Suggest: Use "System" or keep default "Mike Wise" until multi-user authentication exists.

---

## 13. Example: Full History (Multi-User)

```json
{
  "id": "set_abc123",
  "name": "Final Result",
  "tubercles": [...],
  "edges": [...],
  "history": [
    {
      "timestamp": "2025-12-31T10:00:00.000Z",
      "event": "extraction",
      "user": "Mike Wise",
      "params": {
        "method": "log",
        "threshold": 0.15,
        "min_diameter_um": 5.0,
        "max_diameter_um": 15.0,
        "min_circularity": 0.35,
        "clahe_clip": 0.03,
        "clahe_kernel": 8,
        "blur_sigma": 1.0,
        "neighbor_graph": "delaunay"
      },
      "calibration": {
        "um_per_pixel": 0.33,
        "method": "manual"
      },
      "profile": "paralepidosteus",
      "result": { "tubercle_count": 37, "edge_count": 117 }
    },
    {
      "timestamp": "2025-12-31T10:05:00.000Z",
      "event": "auto_connect",
      "user": "Mike Wise",
      "params": {
        "graph_type": "gabriel",
        "cull_long_edges": true,
        "cull_factor": 1.8
      },
      "result": { "tubercle_count": 37, "edge_count": 89 }
    },
    {
      "timestamp": "2025-12-31T10:15:00.000Z",
      "event": "manual_edit",
      "user": "Jane Smith",
      "summary": "+6 tubercles, -1 tubercle, moved 2",
      "details": {
        "added_tubercles": 6,
        "deleted_tubercles": 1,
        "moved_tubercles": 2,
        "resized_tubercles": 0,
        "added_connections": 0,
        "deleted_connections": 0
      },
      "result": { "tubercle_count": 42, "edge_count": 89 }
    },
    {
      "timestamp": "2025-12-31T10:20:00.000Z",
      "event": "auto_connect",
      "user": "Jane Smith",
      "params": {
        "graph_type": "gabriel",
        "cull_long_edges": true,
        "cull_factor": 1.8
      },
      "result": { "tubercle_count": 42, "edge_count": 102 }
    },
    {
      "timestamp": "2025-12-31T11:00:00.000Z",
      "event": "agent_phase",
      "user": "Mike Wise",
      "provider": "claude",
      "model": "claude-sonnet-4-20250514",
      "phase": "pattern_completion",
      "iterations": 12,
      "result": { "tubercle_count": 48, "edge_count": 102 }
    },
    {
      "timestamp": "2025-12-31T11:02:00.000Z",
      "event": "auto_connect",
      "user": "Mike Wise",
      "params": {
        "graph_type": "gabriel",
        "cull_long_edges": true,
        "cull_factor": 1.8
      },
      "result": { "tubercle_count": 48, "edge_count": 118 }
    }
  ]
}
```

This history shows collaborative work:
1. **Mike Wise**: Initial extraction with LoG method
2. **Mike Wise**: Switched to Gabriel graph
3. **Jane Smith**: Manual edits - added 6 tubercles, deleted 1, moved 2
4. **Jane Smith**: Regenerated connections after edits
5. **Mike Wise**: Ran LLM agent which added 6 more tubercles
6. **Mike Wise**: Final connection regeneration

**Total provenance is preserved, reproducible, and attributed to each user.**
