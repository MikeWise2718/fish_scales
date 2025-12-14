# AI Developer Workflow (ADW) System - Isolated Workflows v1

ADW automates software development using isolated git worktrees. The `_iso` suffix stands for "isolated" - these workflows run in separate git worktrees, enabling multiple agents to run at the same time in their own respective directories. Each workflow gets its own complete copy of the repository with dedicated ports and filesystem isolation.

## Key Concepts

### Isolated Execution
Every ADW workflow runs in an isolated git worktree under `trees/<adw_id>/` with:
- Complete filesystem isolation
- Dedicated port ranges (backend: 9100-9114, frontend: 9200-9214)
- Independent git branches
- Support for 15 concurrent instances

### ADW ID
Each workflow run is assigned a unique 8-character identifier (e.g., `a1b2c3d4`). This ID:
- Tracks all phases of a workflow (plan -> build -> test -> review -> document)
- Appears in GitHub comments, commits, and PR titles
- Creates an isolated worktree at `trees/{adw_id}/`
- Allocates unique ports deterministically
- Enables resuming workflows and debugging

### State Management
ADW uses persistent state files (`agents/{adw_id}/adw_state.json`) to:
- Share data between workflow phases
- Track worktree locations and port assignments
- Enable workflow composition and chaining
- Track essential workflow data:
  - `adw_id`: Unique workflow identifier
  - `issue_number`: GitHub issue being processed
  - `branch_name`: Git branch for changes
  - `plan_file`: Path to implementation plan
  - `issue_class`: Issue type (`/chore`, `/bug`, `/feature`)
  - `worktree_path`: Absolute path to isolated worktree
  - `backend_port`: Allocated backend port (9100-9114)
  - `frontend_port`: Allocated frontend port (9200-9214)

## Quick Start

### 1. Set Environment Variables

```bash
export GITHUB_REPO_URL="https://github.com/owner/repository"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export CLAUDE_CODE_PATH="/path/to/claude"  # Optional, defaults to "claude"
export GITHUB_PAT="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Optional, only if using different account than 'gh auth login'
```

### 2. Install Prerequisites

```bash
# GitHub CLI
brew install gh              # macOS
# or: sudo apt install gh    # Ubuntu/Debian
# or: winget install --id GitHub.cli  # Windows

# Claude Code CLI
# Follow instructions at https://docs.anthropic.com/en/docs/claude-code

# Python dependency manager (uv)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# or: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# Authenticate GitHub
gh auth login
```

### 3. Run Isolated ADW Workflows

```bash
cd adws/

# Process a single issue in isolation (plan + build)
uv run adw_plan_build_iso.py 123

# Process with testing in isolation (plan + build + test)
uv run adw_plan_build_test_iso.py 123

# Process with review in isolation (plan + build + test + review)
uv run adw_plan_build_test_review_iso.py 123

# Process with review but skip tests (plan + build + review)
uv run adw_plan_build_review_iso.py 123

# Process with documentation (plan + build + document)
uv run adw_plan_build_document_iso.py 123

# Complete SDLC workflow in isolation
uv run adw_sdlc_iso.py 123

# Zero Touch Execution - Complete SDLC with auto-ship (WARNING: merges to main!)
uv run adw_sdlc_zte_iso.py 123

# Run individual isolated phases
uv run adw_plan_iso.py 123              # Planning phase (creates worktree)
uv run adw_patch_iso.py 123             # Patch workflow (creates worktree)
uv run adw_build_iso.py 123 <adw-id>    # Build phase (requires worktree)
uv run adw_test_iso.py 123 <adw-id>     # Test phase (requires worktree)
uv run adw_review_iso.py 123 <adw-id>   # Review phase (requires worktree)
uv run adw_document_iso.py 123 <adw-id> # Documentation phase (requires worktree)
uv run adw_ship_iso.py 123 <adw-id>     # Ship phase (approve & merge PR)

# Run continuous monitoring (polls every 20 seconds)
uv run adw_triggers/trigger_cron.py

# Start webhook server (for instant GitHub events)
uv run adw_triggers/trigger_webhook.py
```

## Execution Logging

iso_v1 includes comprehensive JSONL execution logging that tracks workflow executions, performance metrics, token consumption, and file modifications.

### Enabling Logging

Create a configuration file at `~/.adw/settings.json` (global) or `.adw/settings.json` (project-local):

```json
{
  "logging_directory": "~/logs/adw",
  "verbosity": 1,
  "claude_mode": "default"
}
```

**Configuration Options:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `logging_directory` | string | (none) | Path to log directory. Required to enable logging. Supports absolute, relative, or `~` paths. |
| `verbosity` | int | 1 | Log detail level: 0=counts only, 1=file names, 2=full details with sizes and diffs |
| `claude_mode` | string | "default" | Claude licensing: "apikey", "max", or "default" (auto-detect) |

**Configuration Priority:**
1. Local: `.adw/settings.json` (project directory)
2. Global: `~/.adw/settings.json` (home directory)

Local settings override global settings. If neither file exists, logging is disabled.

### Log File Format

Logs are written in JSONL (JSON Lines) format to `<logging_directory>/adw_execution.log.jsonl`.

**Start Entry:**
```json
{
  "timestamp": "2025-12-04T10:30:00.000+00:00",
  "event_type": "start",
  "level": "info",
  "message": "Starting adw_plan_iso workflow for issue #123",
  "script_name": "adw_plan_iso.py",
  "adw_id": "a1b2c3d4",
  "issue_number": "123",
  "project_directory": "/home/user/myproject",
  "worktree_path": "/home/user/myproject/trees/a1b2c3d4",
  "git_branch": "feat-123-a1b2c3d4-add-feature",
  "git_commit_hash": "abc123def456",
  "python_version": "3.13.0",
  "platform": "linux"
}
```

**End Entry (success):**
```json
{
  "timestamp": "2025-12-04T10:35:42.000+00:00",
  "event_type": "end",
  "level": "info",
  "message": "Workflow completed successfully in 342.5s ($0.06)",
  "script_name": "adw_plan_iso.py",
  "adw_id": "a1b2c3d4",
  "execution_time_seconds": 342.5,
  "exit_code": 0,
  "success": true,
  "files_created": ["specs/a1b2c3d4_plan_spec.md"],
  "files_modified": [],
  "total_cost_usd": 0.0567,
  "num_agent_calls": 4,
  "claude_mode": "apikey"
}
```

**End Entry (failure):**
```json
{
  "timestamp": "2025-12-04T11:00:00.000+00:00",
  "event_type": "end",
  "level": "error",
  "message": "Workflow failed: RuntimeError - Build failed",
  "script_name": "adw_build_iso.py",
  "adw_id": "e5f6g7h8",
  "exit_code": 1,
  "success": false,
  "error_type": "RuntimeError",
  "error_message": "Build compilation failed"
}
```

**Orchestrator Entry (with subprocesses):**
```json
{
  "timestamp": "2025-12-04T11:45:00.000+00:00",
  "event_type": "end",
  "level": "info",
  "message": "SDLC workflow completed: 5/5 phases succeeded in 30.7m ($0.23)",
  "script_name": "adw_sdlc_iso.py",
  "adw_id": "a1b2c3d4",
  "subprocess_count": 5,
  "subprocess_failures": 0,
  "subprocesses": [
    {"script_name": "adw_plan_iso.py", "duration_seconds": 342.0, "success": true},
    {"script_name": "adw_build_iso.py", "duration_seconds": 692.0, "success": true}
  ],
  "total_cost_usd": 0.2345
}
```

### Verbosity Levels

| Level | File Counts | File Names | File Sizes | Diff Stats |
|-------|-------------|------------|------------|------------|
| 0 | Yes | No | No | No |
| 1 | Yes | Yes | No | No |
| 2 | Yes | Yes | Yes | Yes |

**Verbosity 0 (counts only):**
```json
{
  "files_summary": {"created_count": 3, "modified_count": 2, "deleted_count": 0}
}
```

**Verbosity 1 (file names):**
```json
{
  "files_created": ["specs/plan.md", "src/feature.py"],
  "files_modified": ["src/main.py", "README.md"]
}
```

**Verbosity 2 (full details):**
```json
{
  "files_created": [
    {"path": "specs/plan.md", "size_bytes": 2456}
  ],
  "files_modified": [
    {"path": "src/main.py", "size_bytes": 5678, "lines_added": 45, "lines_removed": 12}
  ]
}
```

### Viewing Logs with lnav

ADW execution logs are compatible with [lnav](https://lnav.org/), a powerful terminal-based log viewer.

**Install lnav format:**
```bash
# Run the installation script
./lnav/install_lnav_format.sh

# Or manually copy
mkdir -p ~/.lnav/formats/adw
cp lnav/adw_execution.lnav.json ~/.lnav/formats/adw/
```

**View logs:**
```bash
# View log file
lnav ~/logs/adw/adw_execution.log.jsonl

# Filter by ADW ID
lnav ~/logs/adw/adw_execution.log.jsonl -c ':filter-in adw_id = "a1b2c3d4"'

# Show only errors
lnav ~/logs/adw/adw_execution.log.jsonl -c ':set-min-log-level error'

# Follow log in real-time
lnav -f ~/logs/adw/adw_execution.log.jsonl
```

**Useful lnav features:**
- Press `i` to view log histogram
- Press `p` to pretty-print current JSON line
- Use `:filter-in script_name = "adw_sdlc_iso.py"` to filter by script
- SQL queries: `:SELECT adw_id, SUM(total_cost_usd) FROM adw_execution_log GROUP BY adw_id`

### Querying Logs Programmatically

**Python:**
```python
import json

# Read and parse JSONL log
with open('~/logs/adw/adw_execution.log.jsonl', 'r') as f:
    operations = [json.loads(line) for line in f]

# Get the most recent operation
latest = operations[-1]
print(f"Last run: {latest['timestamp']}, Result: {latest.get('success')}")

# Calculate total cost
total_cost = sum(op.get('total_cost_usd', 0) for op in operations if op.get('event_type') == 'end')
print(f"Total cost: ${total_cost:.2f}")
```

**jq (command-line):**
```bash
# View the last operation
tail -1 ~/logs/adw/adw_execution.log.jsonl | jq .

# Get all failed operations
cat ~/logs/adw/adw_execution.log.jsonl | jq 'select(.success == false)'

# Sum costs by ADW ID
cat ~/logs/adw/adw_execution.log.jsonl | jq -s 'group_by(.adw_id) | map({adw_id: .[0].adw_id, total_cost: (map(.total_cost_usd // 0) | add)})'
```

### Troubleshooting Logging

**Logs not appearing:**
1. Check that `logging_directory` is configured in `~/.adw/settings.json` or `.adw/settings.json`
2. Verify the directory exists or can be created
3. Check file permissions

**Log rotation:**
The logging system appends to a single file. Implement log rotation using standard tools:
```bash
# Rotate logs with logrotate
cat > /etc/logrotate.d/adw << EOF
~/logs/adw/adw_execution.log.jsonl {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
EOF
```

## ADW Isolated Workflow Scripts

### Entry Point Workflows (Create Worktrees)

#### adw_plan_iso.py - Isolated Planning
Creates isolated worktree and generates implementation plans.

**Usage:**
```bash
uv run adw_plan_iso.py <issue-number> [adw-id]
```

**What it does:**
1. Creates isolated git worktree at `trees/<adw_id>/`
2. Allocates unique ports (backend: 9100-9114, frontend: 9200-9214)
3. Sets up environment with `.ports.env`
4. Fetches issue details and classifies type
5. Creates feature branch in worktree
6. Generates implementation plan in isolation
7. Commits and pushes from worktree
8. Creates/updates pull request

#### adw_patch_iso.py - Isolated Patch Workflow
Quick patches in isolated environment triggered by 'adw_patch' keyword.

**Usage:**
```bash
uv run adw_patch_iso.py <issue-number> [adw-id]
```

**What it does:**
1. Searches for 'adw_patch' in issue/comments
2. Creates isolated worktree with unique ports
3. Creates targeted patch plan in isolation
4. Implements specific changes
5. Commits and creates PR from worktree

### Dependent Workflows (Require Existing Worktree)

#### adw_build_iso.py - Isolated Implementation
Implements solutions in existing isolated environment.

**Requirements:**
- Existing worktree created by `adw_plan_iso.py` or `adw_patch_iso.py`
- ADW ID is mandatory

**Usage:**
```bash
uv run adw_build_iso.py <issue-number> <adw-id>
```

#### adw_test_iso.py - Isolated Testing
Runs tests in isolated environment.

**Requirements:**
- Existing worktree
- ADW ID is mandatory

**Usage:**
```bash
uv run adw_test_iso.py <issue-number> <adw-id> [--skip-e2e]
```

#### adw_review_iso.py - Isolated Review
Reviews implementation in isolated environment.

**Requirements:**
- Existing worktree
- ADW ID is mandatory

**Usage:**
```bash
uv run adw_review_iso.py <issue-number> <adw-id> [--skip-resolution]
```

#### adw_document_iso.py - Isolated Documentation
Generates documentation in isolated environment.

**Requirements:**
- Existing worktree
- ADW ID is mandatory

**Usage:**
```bash
uv run adw_document_iso.py <issue-number> <adw-id>
```

### Orchestrator Scripts

#### adw_plan_build_iso.py - Isolated Plan + Build
Runs planning and building in isolation.

**Usage:**
```bash
uv run adw_plan_build_iso.py <issue-number> [adw-id]
```

#### adw_plan_build_test_iso.py - Isolated Plan + Build + Test
Full pipeline with testing in isolation.

**Usage:**
```bash
uv run adw_plan_build_test_iso.py <issue-number> [adw-id]
```

#### adw_plan_build_test_review_iso.py - Isolated Plan + Build + Test + Review
Complete pipeline with review in isolation.

**Usage:**
```bash
uv run adw_plan_build_test_review_iso.py <issue-number> [adw-id]
```

#### adw_plan_build_review_iso.py - Isolated Plan + Build + Review
Pipeline with review, skipping tests.

**Usage:**
```bash
uv run adw_plan_build_review_iso.py <issue-number> [adw-id]
```

#### adw_plan_build_document_iso.py - Isolated Plan + Build + Document
Documentation pipeline in isolation.

**Usage:**
```bash
uv run adw_plan_build_document_iso.py <issue-number> [adw-id]
```

#### adw_sdlc_iso.py - Complete Isolated SDLC
Full Software Development Life Cycle in isolation.

**Usage:**
```bash
uv run adw_sdlc_iso.py <issue-number> [adw-id] [--skip-e2e] [--skip-resolution]
```

**Phases:**
1. **Plan**: Creates worktree and implementation spec
2. **Build**: Implements solution in isolation
3. **Test**: Runs tests with dedicated ports
4. **Review**: Validates and captures screenshots
5. **Document**: Generates comprehensive docs

#### adw_ship_iso.py - Approve and Merge PR
Final shipping phase that validates state and merges to main.

**Requirements:**
- Complete ADWState with all fields populated
- Existing worktree and PR
- ADW ID is mandatory

**Usage:**
```bash
uv run adw_ship_iso.py <issue-number> <adw-id>
```

#### adw_sdlc_zte_iso.py - Zero Touch Execution
Complete SDLC with automatic shipping - no human intervention required.

**Usage:**
```bash
uv run adw_sdlc_zte_iso.py <issue-number> [adw-id] [--skip-e2e] [--skip-resolution]
```

**WARNING:** This workflow will automatically merge code to main if all phases pass!

## Worktree Architecture

### Worktree Structure

```
trees/
├── abc12345/              # Complete repo copy for ADW abc12345
│   ├── .git/              # Worktree git directory
│   ├── .env               # Copied from main repo
│   ├── .ports.env         # Port configuration
│   ├── app/               # Application code
│   ├── adws/              # ADW scripts
│   └── ...
└── def67890/              # Another isolated instance
    └── ...

agents/                    # Shared state location (not in worktree)
├── abc12345/
│   └── adw_state.json     # Persistent state
└── def67890/
    └── adw_state.json
```

### Port Allocation

Each isolated instance gets unique ports:
- Backend: 9100-9114 (15 ports)
- Frontend: 9200-9214 (15 ports)
- Deterministic assignment based on ADW ID hash
- Automatic fallback if preferred ports are busy

### Cleanup and Maintenance

Worktrees persist until manually removed:

```bash
# Remove specific worktree
git worktree remove trees/abc12345

# List all worktrees
git worktree list

# Clean up worktrees (removes invalid entries)
git worktree prune

# Remove worktree directory if git doesn't know about it
rm -rf trees/abc12345
```

## Model Selection

ADW supports dynamic model selection based on workflow complexity. Users can specify whether to use a "base" model set (optimized for speed and cost) or a "heavy" model set (optimized for complex tasks).

### How to Specify Model Set

Include `model_set base` or `model_set heavy` in your GitHub issue or comment:

```
Title: Add export functionality
Body: Please add the ability to export data to CSV.
Include workflow: adw_plan_build_iso model_set heavy
```

If not specified, the system defaults to "base".

## Troubleshooting

### Environment Issues
```bash
# Check required variables
env | grep -E "(GITHUB|ANTHROPIC|CLAUDE)"

# Verify GitHub auth
gh auth status

# Test Claude Code
claude --version
```

### Common Errors

**"No worktree found"**
```bash
# Check if worktree exists
git worktree list
# Run an entry point workflow first
uv run adw_plan_iso.py <issue-number>
```

**"Port already in use"**
```bash
# Check what's using the port
lsof -i :9107
# Kill the process or let ADW find alternative ports
```

**"Agent execution failed"**
```bash
# Check agent output in worktree
cat trees/<adw-id>/agents/*/planner/raw_output.jsonl | tail -1 | jq .
```

### Debug Mode
```bash
export ADW_DEBUG=true
uv run adw_plan_build_iso.py 123  # Verbose output
```

## Technical Details

### Core Components

#### Modules
- `adw_modules/adw_config.py` - Two-stage configuration loading (local + global)
- `adw_modules/execution_log.py` - JSONL execution logging
- `adw_modules/agent.py` - Claude Code CLI integration with worktree support
- `adw_modules/data_types.py` - Pydantic models including worktree fields
- `adw_modules/github.py` - GitHub API operations
- `adw_modules/git_ops.py` - Git operations with `cwd` parameter support
- `adw_modules/state.py` - State management tracking worktrees and ports
- `adw_modules/workflow_ops.py` - Core workflow operations with isolation
- `adw_modules/worktree_ops.py` - Worktree and port management
- `adw_modules/complexity.py` - Task complexity estimation
- `adw_modules/console.py` - Enhanced console output formatting
- `adw_modules/utils.py` - Utility functions

### Branch Naming
```
{type}-{issue_number}-{adw_id}-{slug}
```
Example: `feat-456-e5f6g7h8-add-user-authentication`

## Running Tests

```bash
# Run all ADW tests
uv run python adw_tests/test_execution_log.py
uv run python adw_tests/test_model_selection.py
uv run python adw_tests/test_agents.py
```
