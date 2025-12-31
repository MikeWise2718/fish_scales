# Agent Run Logging Specification

**Status:** Proposal
**Created:** 2025-12-31
**Purpose:** Persistent logging of LLM prompts and responses for Agent Extraction runs

---

## Overview

When running the Extraction Parameter Optimization Agent, we need detailed logs of all prompts sent to the LLM and responses received. These logs support:

1. **Debugging** - Understanding why the agent made certain decisions
2. **Analysis** - Comparing runs across different images/providers/models
3. **Prompt Engineering** - Iterating on prompt design with full context
4. **Cost Tracking** - Monitoring token usage and API costs
5. **Reproducibility** - Understanding what led to a particular result

---

## Directory Structure

```
agent_logs/
├── 2025-12-31T14-30-45_extraction.md
├── 2025-12-31T15-22-10_extraction.md
├── 2025-12-31T16-45-00_extraction.md
└── ...
```

**Location:** `agent_logs/` at project root (gitignored)

**Alternative - date subdirectories:**
```
agent_logs/
├── 2025-12-31/
│   ├── 14-30-45_extraction.md
│   └── 15-22-10_extraction.md
└── 2026-01-01/
    └── 09-15-30_extraction.md
```

> **OPEN QUESTION 1:** Flat structure vs date subdirectories?
> - Flat is simpler, easier to glob all files
> - Subdirectories better for long-term organization
> - Recommend: Start flat, add subdirectories if >50 files accumulate

---

## File Naming

**Format:** `YYYY-MM-DDTHH-MM-SS_extraction.md`

**Examples:**
- `2025-12-31T14-30-45_extraction.md`
- `2025-12-31T09-05-00_extraction.md`

**Rationale:**
- ISO 8601-like timestamp ensures chronological sorting
- Colons replaced with hyphens for filesystem compatibility
- `_extraction` suffix distinguishes from potential future agent types (e.g., `_editing`)
- `.md` extension enables syntax highlighting and YAML frontmatter support

> **OPEN QUESTION 2:** Include image name in filename?
> - Pro: Easier to find logs for specific image
> - Con: Long filenames, special characters, image may change mid-run
> - Recommend: Keep image info in frontmatter only

---

## File Format

### Frontmatter (YAML)

```yaml
---
# Run metadata
created: 2025-12-31T14:30:45
completed: 2025-12-31T14:35:22
status: completed  # completed | stopped | error

# Image information
image_name: P1_Fig4_Atractosteus_simplex_7.07um.tif
image_path: D:\senkenberg\fish_scales\test_images\P1_Fig4_Atractosteus_simplex_7.07um.tif
calibration_um_per_px: 0.33

# Agent configuration
provider: claude
model: claude-sonnet-4-20250514
target_hexagonalness: 0.70
max_iterations: 10
initial_profile: default

# Results summary
total_iterations: 7
final_hexagonalness: 0.72
best_hexagonalness: 0.72
best_iteration: 7
final_tubercle_count: 45

# Token usage
total_input_tokens: 125430
total_output_tokens: 8920
estimated_cost_usd: 0.42
---
```

**Required fields:**
- `created` - ISO 8601 timestamp
- `image_name` - Filename only
- `image_path` - Full path
- `provider` - LLM provider used
- `model` - Specific model ID

**Populated on completion:**
- `completed` - When run finished
- `status` - Final status
- `total_iterations` - How many iterations ran
- `final_hexagonalness` - Score at end
- `best_hexagonalness` - Best score achieved
- Token/cost fields

> **OPEN QUESTION 3:** Should frontmatter be updated in-place as run progresses, or only written at end?
> - In-place updates risk corruption if process crashes
> - End-only means partial runs have incomplete metadata
> - Recommend: Write frontmatter at start with `status: running`, update at end

---

### Body Content Structure

```markdown
---
[frontmatter as above]
---

# Agent Extraction Run

Started: 2025-12-31T14:30:45
Image: P1_Fig4_Atractosteus_simplex_7.07um.tif

---

## Iteration 1

**Phase:** Profile Selection
**Timestamp:** 2025-12-31T14:30:47
**Duration:** 3.2s

### Prompt

```
[System prompt and user prompt content here]
```

### Response

```
[Full LLM response text here]
```

### Tool Calls

| Tool | Parameters | Result |
|------|------------|--------|
| get_state | - | image loaded, 0 tubercles |
| set_params | profile=paralepidosteus | success |
| run_extraction | - | 38 tubercles |
| get_statistics | - | hex=0.45 |

### Metrics

- Tubercles: 38
- Hexagonalness: 0.45
- Mean Diameter: 6.2 µm
- Mean Spacing: 5.8 µm

### Token Usage

- Input: 15,230 tokens
- Output: 1,240 tokens
- Cost: $0.05

---

## Iteration 2

**Phase:** Parameter Fine-Tuning
**Timestamp:** 2025-12-31T14:30:52
**Duration:** 4.1s

### Prompt

```
[Iteration prompt with context from previous iteration]
```

### Response

```
[LLM response]
```

[... continues for each iteration ...]

---

## Summary

**Final Status:** Completed - Target achieved
**Total Iterations:** 7
**Total Duration:** 45.3s
**Best Result:** Iteration 7 (hexagonalness: 0.72)

### Final Parameters

```json
{
  "method": "log",
  "threshold": 0.06,
  "min_diameter": 4.5,
  "max_diameter": 12.0,
  "min_circularity": 0.35,
  "clahe_clip": 0.04,
  "clahe_kernel": 8,
  "blur_sigma": 1.2
}
```

### Iteration Progress

| Iter | Phase | Tubercles | Hexagonalness | Key Change |
|------|-------|-----------|---------------|------------|
| 1 | Profile | 38 | 0.45 | paralepidosteus profile |
| 2 | Tuning | 42 | 0.52 | threshold 0.05→0.06 |
| 3 | Tuning | 44 | 0.58 | circularity 0.5→0.35 |
| ... | ... | ... | ... | ... |
| 7 | Tuning | 45 | 0.72 | blur_sigma 1.0→1.2 |

### Token Summary

| Iteration | Input | Output | Cost |
|-----------|-------|--------|------|
| 1 | 15,230 | 1,240 | $0.05 |
| 2 | 18,450 | 1,180 | $0.06 |
| ... | ... | ... | ... |
| **Total** | **125,430** | **8,920** | **$0.42** |
```

---

## Implementation Details

### When to Write

1. **Run Start:** Create file, write frontmatter with `status: running`
2. **Each Iteration:** Append iteration section immediately after LLM response
3. **Run End:** Append summary, update frontmatter with final stats

### Appending Strategy

Since we append as we go, use a simple approach:
1. Write frontmatter and header at start
2. After each iteration completes, append that iteration's section
3. At end, append summary section
4. Rewrite frontmatter in-place with final stats (seek to start, overwrite)

**Alternative - Two-file approach:**
- `2025-12-31T14-30-45_extraction.md` - Append-only content
- `2025-12-31T14-30-45_extraction.meta.json` - Updatable metadata

> **OPEN QUESTION 4:** Single file with frontmatter rewrite, or separate metadata file?
> - Single file is cleaner for reading/sharing
> - Separate files avoid frontmatter rewrite complexity
> - Recommend: Single file, accept that frontmatter may be incomplete on crash

### Screenshot Handling

Screenshots are taken each iteration. Options:
1. **Embed as base64** - Large files, but self-contained
2. **Save separately, reference by path** - Smaller logs, but files can get separated
3. **Don't include** - Rely on UI for visual review

> **OPEN QUESTION 5:** How to handle screenshots?
> - Recommend: Save separately in `agent_logs/screenshots/` with matching timestamp prefix
> - Reference in log: `![Iteration 1](screenshots/2025-12-31T14-30-45_iter01.png)`

---

## Code Integration Points

### Extraction Optimizer (`extraction_optimizer.py`)

```python
class ExtractionOptimizer:
    def __init__(self, ...):
        self.run_logger = AgentRunLogger()  # New class

    async def optimize(self, image_path, calibration, ...):
        self.run_logger.start_run(
            image_path=image_path,
            calibration=calibration,
            provider=self.provider_name,
            model=self.model,
            target_hexagonalness=target_score,
            max_iterations=max_iterations
        )

        try:
            for iteration in range(max_iterations):
                prompt = self._build_prompt(...)

                response = await self.provider.chat(prompt, ...)

                self.run_logger.log_iteration(
                    iteration=iteration + 1,
                    phase=current_phase,
                    prompt=prompt,
                    response=response,
                    tool_calls=tool_calls,
                    metrics=current_metrics,
                    tokens=token_usage
                )

                if should_stop:
                    break
        finally:
            self.run_logger.end_run(
                status=final_status,
                final_params=current_params
            )
```

### New Module: `agent_run_logger.py`

```python
class AgentRunLogger:
    """Logs agent prompts/responses to markdown files."""

    def __init__(self, log_dir: str = "agent_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_file = None
        self.run_data = {}

    def start_run(self, image_path, calibration, provider, model,
                  target_hexagonalness, max_iterations, initial_profile=None):
        """Create log file and write initial frontmatter."""
        ...

    def log_iteration(self, iteration, phase, prompt, response,
                      tool_calls, metrics, tokens):
        """Append iteration section to log file."""
        ...

    def end_run(self, status, final_params):
        """Write summary and update frontmatter."""
        ...
```

---

## Open Questions Summary

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Flat vs date subdirectories? | Start flat |
| 2 | Include image name in filename? | No, use frontmatter |
| 3 | Update frontmatter in-place or at end? | At end only |
| 4 | Single file or separate metadata? | Single file |
| 5 | How to handle screenshots? | Separate files, reference in log |

---

## Future Considerations

1. **Log Viewer UI** - Tab to browse/search past runs
2. **Comparison Tool** - Diff two runs side-by-side
3. **Export/Import** - Share runs for collaboration
4. **Aggregated Analytics** - Success rates by provider/model/image type
5. **Prompt Templates** - Reference prompt versions in logs

---

## Appendix: Example Complete Log File

See `docs/examples/agent-run-log-example.md` (to be created after spec approval)
