# SLO to Annotations Renaming Plan

## Overview

This document outlines the plan to rename "SLO" (Scale Landmark Overlay) to "Annotations" throughout the codebase. The term "Annotations" is standard terminology in computer vision and image analysis, making the codebase more intuitive and self-documenting.

## Rationale

- **SLO** is an obscure acronym that requires explanation
- **Annotations** is industry-standard terminology for marking up images with data
- The data structure contains tubercle positions, connections, and metadata - all forms of image annotation
- New contributors will immediately understand what "annotations" means

## Naming Convention

| Current | New |
|---------|-----|
| SLO | Annotations |
| slo | annotations |
| _slo | _annotations |

## Scope of Changes

### 1. Directory Structure

| Current | New | Notes |
|---------|-----|-------|
| `slo/` | `annotations/` | Data storage directory |
| `.gitignore` entry `slo/` | `annotations/` | Update gitignore |

### 2. File Naming Patterns

| Current | New |
|---------|-----|
| `*_slo.json` | `*_annotations.json` |
| `slo-persistence.md` | `annotation-persistence.md` |

### 3. API Endpoints (8 changes)

| Current | New | File |
|---------|-----|------|
| `/api/save-slo` | `/api/save-annotations` | `routes/api.py` |
| `/api/load-slo` | `/api/load-annotations` | `routes/api.py` |
| `/api/list-slo` | `/api/list-annotations` | `routes/api.py` |
| `/api/tools/save-slo` (MCP) | `/api/tools/save-annotations` | `routes/mcp_api.py` |

### 4. Python Files

#### `src/fish_scale_ui/services/persistence.py` (~41 occurrences)
- Rename file to `persistence.py` (keep same name, update contents)
- Function renames:
  - `save_slo()` → `save_annotations()`
  - `load_slo()` → `load_annotations()`
  - `list_slo_files()` → `list_annotation_files()`
- Variable renames:
  - `slo_dir` → `annotations_dir`
  - `slo_path` → `annotations_path`
  - `slo_data` → `annotations_data`
  - `slo_file` → `annotations_file`

#### `src/fish_scale_ui/routes/api.py` (~55 occurrences)
- API endpoint function renames:
  - `save_slo()` → `save_annotations()`
  - `load_slo()` → `load_annotations()`
  - `list_slo()` → `list_annotations()`
- Variable renames:
  - `slo_saved` → `annotations_saved`
  - `slo_dir` → `annotations_dir`
  - `slo_path` → `annotations_path`
  - `slo_data` → `annotations_data`
- Import updates
- Log event names: `slo_saved` → `annotations_saved`, etc.

#### `src/fish_scale_ui/routes/mcp_api.py` (~11 occurrences)
- Function rename: `save_slo()` → `save_annotations()`
- Variable updates similar to api.py
- Log event updates

#### `src/fish_scale_ui/app.py` (1 occurrence)
- Directory creation: `'slo'` → `'annotations'`

#### `src/fish_scale_mcp/server.py` (3 occurrences)
- Tool name: `save_slo` → `save_annotations`
- Documentation updates

#### `src/fish_scale_agent/runner.py` (3 occurrences)
- Tool reference: `save_slo` → `save_annotations`

#### `src/fish_scale_agent/prompts.py` (2 occurrences)
- Prompt text updates

### 5. JavaScript Files

#### `src/fish_scale_ui/static/js/extraction.js` (~13 occurrences)
- Function names (internal):
  - `saveSlo()` → `saveAnnotations()`
  - `loadSlo()` → `loadAnnotations()`
- API calls:
  - `/api/save-slo` → `/api/save-annotations`
  - `/api/load-slo` → `/api/load-annotations`
- Toast messages and comments

#### `src/fish_scale_ui/static/js/sets.js` (~5 occurrences)
- JSDoc comments mentioning SLO format

#### `src/fish_scale_ui/static/js/main.js` (1 occurrence)
- Comment update

#### `src/fish_scale_ui/static/js/calibration.js` (1 occurrence)
- Comment update

### 6. CSS Files

#### `src/fish_scale_ui/static/css/main.css` (~3 occurrences)
- Class renames:
  - `.slo-actions` → `.annotations-actions`

### 7. HTML Templates

#### `src/fish_scale_ui/templates/workspace.html` (~6 occurrences)
- Button labels: "Save SLO" → "Save Annotations"
- Hints and descriptions
- CSS class references
- Element IDs: `loadSloBtn` → `loadAnnotationsBtn`
- Keyboard shortcut descriptions

#### `src/fish_scale_ui/static/help/shortcuts.html` (1 occurrence)
- Keyboard shortcut description

#### `src/fish_scale_ui/static/help/editing.html` (1 occurrence)
- Help text

### 8. Test Files

#### `tests/test_mcp_server.py` (1 occurrence)
- Tool name in test

#### `tests/test_mcp_api.py` (2 occurrences)
- Variable name and test description

### 9. Documentation Files

#### Files to Update:
- `CLAUDE.md` (~9 occurrences)
- `README.md` (~2 occurrences)
- `docs/slo-persistence.md` → rename to `docs/annotation-persistence.md` (~10 occurrences)
- `docs/implementation-history.md` (~6 occurrences)
- `specs/ui-fish-scale-measure-spec-revised.md` (~24 occurrences)
- `specs/ui-implementation-phases.md` (~31 occurrences)
- `specs/ui-multiple-tubelinksets.md` (~12 occurrences)
- `specs/ui-open-questions.md` (~9 occurrences)
- `specs/dataset-history-tracking.md` (~13 occurrences)
- `specs/mcp-agent-tubercle-detection-spec.md` (~2 occurrences)
- `specs/extraction-agent.md` (~2 occurrences)
- `specs/mcp-testing.md` (1 occurrence)
- `specs/set-rationalization.md` (~2 occurrences)
- `specs/tubercle-detection-tuning-spec.md` (1 occurrence)
- `specs/ui-fish-scale-measure-spec.md` (~6 occurrences)

## Backwards Compatibility

### Existing Annotation Files

Users may have existing `*_slo.json` files. Two options:

**Option A: Migration Script (Recommended)**
- Create a migration script that renames existing files
- Run once during upgrade
- Clean break, no legacy code needed

**Option B: Dual Support**
- Load function checks for both `*_annotations.json` and `*_slo.json`
- Save always uses new format
- More complex, carries technical debt

**Recommendation:** Option A - provide a migration script and document the upgrade process.

### Migration Script

```python
#!/usr/bin/env python3
"""Migrate SLO files to Annotations naming."""
from pathlib import Path
import shutil

def migrate_slo_to_annotations(root_dir: Path):
    """Rename *_slo.json files to *_annotations.json."""
    slo_dir = root_dir / 'slo'
    annotations_dir = root_dir / 'annotations'

    if not slo_dir.exists():
        print("No slo/ directory found. Nothing to migrate.")
        return

    # Create annotations directory
    annotations_dir.mkdir(exist_ok=True)

    # Migrate files
    for slo_file in slo_dir.glob('*_slo.json'):
        new_name = slo_file.name.replace('_slo.json', '_annotations.json')
        new_path = annotations_dir / new_name
        shutil.copy2(slo_file, new_path)
        print(f"Migrated: {slo_file.name} -> {new_name}")

    # Also migrate CSV files
    for csv_file in slo_dir.glob('*.csv'):
        shutil.copy2(csv_file, annotations_dir / csv_file.name)
        print(f"Copied: {csv_file.name}")

    print(f"\nMigration complete. Files copied to {annotations_dir}/")
    print("You can delete the old slo/ directory after verifying the migration.")

if __name__ == '__main__':
    import sys
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    migrate_slo_to_annotations(root)
```

## Implementation Order

### Phase 1: Core Backend (Breaking Changes)
1. Update `persistence.py` - core save/load functions
2. Update `api.py` - REST API endpoints
3. Update `mcp_api.py` - MCP API endpoints
4. Update `app.py` - directory creation
5. Update `.gitignore`

### Phase 2: Frontend
6. Update `extraction.js` - main save/load logic
7. Update `sets.js` - set export/import
8. Update `workspace.html` - UI labels and IDs
9. Update `main.css` - CSS class names
10. Update other JS files (minor changes)

### Phase 3: Agent & MCP
11. Update `server.py` - MCP tool definitions
12. Update `runner.py` - agent tool calls
13. Update `prompts.py` - agent prompts

### Phase 4: Tests
14. Update `test_mcp_server.py`
15. Update `test_mcp_api.py`

### Phase 5: Documentation
16. Rename `docs/slo-persistence.md` → `docs/annotation-persistence.md`
17. Update `CLAUDE.md`
18. Update `README.md`
19. Update all spec files

### Phase 6: Migration & Cleanup
20. Create migration script
21. Update help files
22. Final testing

## Estimated Effort

| Category | Files | Occurrences | Complexity |
|----------|-------|-------------|------------|
| Python (core) | 6 | ~115 | Medium |
| JavaScript | 4 | ~20 | Low |
| HTML/CSS | 4 | ~10 | Low |
| Tests | 2 | ~3 | Low |
| Documentation | 15 | ~130 | Low (mostly find/replace) |
| **Total** | **31** | **~280** | Medium |

Estimated time: 2-3 hours for code changes, plus testing.

## Testing Checklist

After completing the rename:

- [ ] Save new annotations file
- [ ] Load annotations file
- [ ] List annotations files
- [ ] MCP save_annotations tool works
- [ ] Agent can save annotations
- [ ] Keyboard shortcut Ctrl+S works
- [ ] Migration script works on sample data
- [ ] All tests pass
- [ ] No remaining "slo" or "SLO" references in code (except this spec and migration script)

## Rollback Plan

If issues are discovered after deployment:

1. Git revert the commit(s)
2. Run reverse migration (rename `*_annotations.json` back to `*_slo.json`)
3. Restore `slo/` directory from `annotations/`

## Open Questions

1. **Should we keep `_tub.csv` and `_itc.csv` naming?**
   - These are data exports, not really "annotation files"
   - Recommendation: Keep as-is, they describe content not format

2. **Should the JSON file use singular or plural?**
   - `*_annotation.json` vs `*_annotations.json`
   - Recommendation: Plural (`annotations`) since it contains multiple annotation types

3. **Should we update the internal JSON structure?**
   - Current: Uses various field names
   - Could add: `"format": "annotations-v3"` or similar
   - Recommendation: Add a format identifier for future compatibility
