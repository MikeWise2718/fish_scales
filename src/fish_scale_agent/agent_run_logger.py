"""Agent run logging for extraction optimization.

Logs prompts, responses, and metrics to markdown files for analysis and debugging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json


@dataclass
class IterationLog:
    """Data for a single iteration."""
    iteration: int
    phase: str
    timestamp: datetime
    duration_seconds: float = 0.0
    prompt: str = ""
    response: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0


class AgentRunLogger:
    """Logs agent prompts/responses to markdown files.

    Creates timestamped markdown files with YAML frontmatter containing
    run metadata, followed by detailed iteration logs.
    """

    def __init__(self, log_dir: str | Path = "agent_logs"):
        """Initialize the logger.

        Args:
            log_dir: Directory for log files (created if doesn't exist)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.current_file: Path | None = None
        self.run_start: datetime | None = None
        self.run_data: dict = {}
        self.iterations: list[IterationLog] = []
        self._iteration_start: datetime | None = None
        self._current_iteration: IterationLog | None = None
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def start_run(
        self,
        image_path: str | Path,
        calibration: float,
        provider: str,
        model: str,
        target_hexagonalness: float,
        max_iterations: int,
        initial_profile: str = "default",
        system_prompt: str = "",
        user_message: str = "",
    ) -> Path:
        """Create log file and write initial content.

        Args:
            image_path: Path to the image being processed
            calibration: Calibration value in µm/px
            provider: LLM provider name
            model: Model identifier
            target_hexagonalness: Target score
            max_iterations: Maximum iterations allowed
            initial_profile: Starting parameter profile
            system_prompt: The system prompt sent to LLM
            user_message: The initial user message

        Returns:
            Path to the created log file
        """
        self.run_start = datetime.now()
        timestamp_str = self.run_start.strftime("%Y-%m-%dT%H-%M-%S")

        # Create filename
        self.current_file = self.log_dir / f"{timestamp_str}_extraction.md"

        # Store run data
        image_path = Path(image_path)
        self.run_data = {
            "created": self.run_start.isoformat(),
            "status": "running",
            "image_name": image_path.name,
            "image_path": str(image_path.resolve()),
            "calibration_um_per_px": calibration,
            "provider": provider,
            "model": model,
            "target_hexagonalness": target_hexagonalness,
            "max_iterations": max_iterations,
            "initial_profile": initial_profile,
        }

        self.iterations = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Write initial content
        self._write_header(system_prompt, user_message)

        return self.current_file

    def _write_header(self, system_prompt: str, user_message: str) -> None:
        """Write the file header with frontmatter."""
        if not self.current_file:
            return

        lines = []

        # YAML frontmatter (partial - will be updated at end)
        lines.append("---")
        lines.append(f"created: {self.run_data['created']}")
        lines.append(f"status: {self.run_data['status']}")
        lines.append(f"image_name: {self.run_data['image_name']}")
        lines.append(f"image_path: {self.run_data['image_path']}")
        lines.append(f"calibration_um_per_px: {self.run_data['calibration_um_per_px']}")
        lines.append(f"provider: {self.run_data['provider']}")
        lines.append(f"model: {self.run_data['model']}")
        lines.append(f"target_hexagonalness: {self.run_data['target_hexagonalness']}")
        lines.append(f"max_iterations: {self.run_data['max_iterations']}")
        lines.append(f"initial_profile: {self.run_data['initial_profile']}")
        lines.append("---")
        lines.append("")

        # Title
        lines.append("# Agent Extraction Run")
        lines.append("")
        lines.append(f"**Started:** {self.run_data['created']}")
        lines.append(f"**Image:** {self.run_data['image_name']}")
        lines.append(f"**Target:** hexagonalness ≥ {self.run_data['target_hexagonalness']}")
        lines.append("")

        # System prompt
        lines.append("---")
        lines.append("")
        lines.append("## System Prompt")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand system prompt</summary>")
        lines.append("")
        lines.append("```")
        lines.append(system_prompt)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

        # Initial user message
        lines.append("## Initial Message")
        lines.append("")
        lines.append("```")
        lines.append(user_message)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

        with open(self.current_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def start_iteration(self, iteration: int, phase: str = "tuning") -> None:
        """Mark the start of a new iteration.

        Args:
            iteration: Iteration number (1-indexed)
            phase: Phase name (e.g., "profile_selection", "tuning")
        """
        self._iteration_start = datetime.now()
        self._current_iteration = IterationLog(
            iteration=iteration,
            phase=phase,
            timestamp=self._iteration_start,
        )

    def log_prompt(self, prompt: str) -> None:
        """Log the prompt sent to the LLM.

        Args:
            prompt: The prompt text
        """
        if self._current_iteration:
            self._current_iteration.prompt = prompt

    def log_response(self, response: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Log the LLM response.

        Args:
            response: The response text
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if self._current_iteration:
            self._current_iteration.response = response
            self._current_iteration.input_tokens = input_tokens
            self._current_iteration.output_tokens = output_tokens
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens

    def log_tool_call(self, tool_name: str, args: dict, result: Any) -> None:
        """Log a tool call.

        Args:
            tool_name: Name of the tool called
            args: Arguments passed to the tool
            result: Result returned by the tool
        """
        if self._current_iteration:
            # Serialize result, handling non-JSON-serializable types
            try:
                if isinstance(result, dict):
                    # Remove large base64 image data
                    result_clean = {k: v for k, v in result.items() if k != "image_data"}
                    if "image_data" in result:
                        result_clean["image_data"] = f"<base64 image, {len(result['image_data'])} chars>"
                    result_str = json.dumps(result_clean, default=str)
                else:
                    result_str = str(result)
            except Exception:
                result_str = str(result)[:500]

            self._current_iteration.tool_calls.append({
                "tool": tool_name,
                "args": args,
                "result": result_str[:1000] if len(result_str) > 1000 else result_str,
            })

    def log_metrics(self, metrics: dict, params: dict | None = None) -> None:
        """Log current metrics and parameters.

        Args:
            metrics: Current metrics dict
            params: Current parameters dict
        """
        if self._current_iteration:
            self._current_iteration.metrics = metrics.copy()
            if params:
                self._current_iteration.params = params.copy()

    def end_iteration(self) -> None:
        """Finalize and write the current iteration to file."""
        if not self._current_iteration or not self.current_file:
            return

        # Calculate duration
        if self._iteration_start:
            duration = (datetime.now() - self._iteration_start).total_seconds()
            self._current_iteration.duration_seconds = duration

        # Store iteration
        self.iterations.append(self._current_iteration)

        # Append to file
        self._append_iteration(self._current_iteration)

        # Reset
        self._current_iteration = None
        self._iteration_start = None

    def _append_iteration(self, iteration: IterationLog) -> None:
        """Append an iteration section to the log file."""
        if not self.current_file:
            return

        lines = []
        lines.append(f"## Iteration {iteration.iteration}")
        lines.append("")
        lines.append(f"**Phase:** {iteration.phase}")
        lines.append(f"**Timestamp:** {iteration.timestamp.isoformat()}")
        lines.append(f"**Duration:** {iteration.duration_seconds:.1f}s")
        lines.append("")

        # Prompt (if available)
        if iteration.prompt:
            lines.append("### Prompt")
            lines.append("")
            lines.append("```")
            lines.append(iteration.prompt)
            lines.append("```")
            lines.append("")

        # Response (if available)
        if iteration.response:
            lines.append("### Response")
            lines.append("")
            lines.append("```")
            lines.append(iteration.response)
            lines.append("```")
            lines.append("")

        # Tool calls
        if iteration.tool_calls:
            lines.append("### Tool Calls")
            lines.append("")
            lines.append("| Tool | Arguments | Result |")
            lines.append("|------|-----------|--------|")
            for tc in iteration.tool_calls:
                args_str = json.dumps(tc["args"]) if tc["args"] else "-"
                # Truncate long results for table display
                result_str = tc["result"]
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                # Escape pipes for markdown table
                args_str = args_str.replace("|", "\\|")
                result_str = result_str.replace("|", "\\|")
                lines.append(f"| {tc['tool']} | `{args_str}` | {result_str} |")
            lines.append("")

        # Metrics
        if iteration.metrics:
            lines.append("### Metrics")
            lines.append("")
            hex_score = iteration.metrics.get("hexagonalness", 0)
            n_tub = iteration.metrics.get("n_tubercles", 0)
            mean_d = iteration.metrics.get("mean_diameter_um", 0)
            std_d = iteration.metrics.get("std_diameter_um", 0)
            mean_s = iteration.metrics.get("mean_space_um", 0)
            std_s = iteration.metrics.get("std_space_um", 0)

            lines.append(f"- **Hexagonalness:** {hex_score:.3f}")
            lines.append(f"- **Tubercles:** {n_tub}")
            if mean_d:
                lines.append(f"- **Mean Diameter:** {mean_d:.2f} µm (±{std_d:.2f})")
            if mean_s:
                lines.append(f"- **Mean Spacing:** {mean_s:.2f} µm (±{std_s:.2f})")
            lines.append("")

        # Parameters (key ones only)
        if iteration.params:
            lines.append("### Parameters")
            lines.append("")
            key_params = ["threshold", "min_diameter_um", "max_diameter_um",
                         "min_circularity", "clahe_clip", "blur_sigma", "method"]
            param_strs = []
            for k in key_params:
                if k in iteration.params:
                    v = iteration.params[k]
                    if isinstance(v, float):
                        param_strs.append(f"{k}={v:.3f}")
                    else:
                        param_strs.append(f"{k}={v}")
            lines.append(", ".join(param_strs))
            lines.append("")

        # Token usage
        if iteration.input_tokens or iteration.output_tokens:
            lines.append("### Token Usage")
            lines.append("")
            lines.append(f"- Input: {iteration.input_tokens:,}")
            lines.append(f"- Output: {iteration.output_tokens:,}")
            lines.append("")

        lines.append("---")
        lines.append("")

        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def end_run(
        self,
        status: str,
        final_metrics: dict | None = None,
        final_params: dict | None = None,
        best_iteration: int = 0,
        best_hexagonalness: float = 0.0,
        accept_reason: str = "",
    ) -> None:
        """Write summary and finalize the log file.

        Args:
            status: Final status (completed, stopped, error)
            final_metrics: Final metrics dict
            final_params: Final parameter values
            best_iteration: Which iteration achieved best result
            best_hexagonalness: Best hexagonalness score achieved
            accept_reason: Reason for accepting/stopping
        """
        if not self.current_file:
            return

        completed_time = datetime.now()
        total_duration = (completed_time - self.run_start).total_seconds() if self.run_start else 0

        lines = []
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Final Status:** {status}")
        lines.append(f"**Completed:** {completed_time.isoformat()}")
        lines.append(f"**Total Duration:** {total_duration:.1f}s")
        lines.append(f"**Total Iterations:** {len(self.iterations)}")
        lines.append(f"**Best Result:** Iteration {best_iteration} (hexagonalness: {best_hexagonalness:.3f})")
        lines.append("")

        if accept_reason:
            lines.append(f"**Reason:** {accept_reason}")
            lines.append("")

        # Final parameters
        if final_params:
            lines.append("### Final Parameters")
            lines.append("")
            lines.append("```json")
            # Filter to key params
            key_params = {k: v for k, v in final_params.items()
                         if k in ["method", "threshold", "min_diameter_um", "max_diameter_um",
                                 "min_circularity", "clahe_clip", "clahe_kernel", "blur_sigma",
                                 "neighbor_graph"]}
            lines.append(json.dumps(key_params, indent=2))
            lines.append("```")
            lines.append("")

        # Iteration progress table
        if self.iterations:
            lines.append("### Iteration Progress")
            lines.append("")
            lines.append("| Iter | Phase | Tubercles | Hexagonalness | Duration |")
            lines.append("|------|-------|-----------|---------------|----------|")
            for it in self.iterations:
                n_tub = it.metrics.get("n_tubercles", 0)
                hex_score = it.metrics.get("hexagonalness", 0)
                lines.append(f"| {it.iteration} | {it.phase} | {n_tub} | {hex_score:.3f} | {it.duration_seconds:.1f}s |")
            lines.append("")

        # Token summary
        lines.append("### Token Summary")
        lines.append("")
        lines.append(f"- **Total Input Tokens:** {self._total_input_tokens:,}")
        lines.append(f"- **Total Output Tokens:** {self._total_output_tokens:,}")
        lines.append(f"- **Total Tokens:** {self._total_input_tokens + self._total_output_tokens:,}")
        lines.append("")

        # Estimate cost (rough estimates based on typical pricing)
        # This is approximate - actual costs depend on provider
        input_cost = self._total_input_tokens * 0.000003  # ~$3/M tokens
        output_cost = self._total_output_tokens * 0.000015  # ~$15/M tokens
        total_cost = input_cost + output_cost
        lines.append(f"**Estimated Cost:** ${total_cost:.4f}")
        lines.append("")

        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Update frontmatter with final stats
        self._update_frontmatter(status, completed_time, best_iteration, best_hexagonalness,
                                 final_metrics, total_cost)

    def _update_frontmatter(
        self,
        status: str,
        completed: datetime,
        best_iteration: int,
        best_hexagonalness: float,
        final_metrics: dict | None,
        estimated_cost: float,
    ) -> None:
        """Update the YAML frontmatter with final stats."""
        if not self.current_file or not self.current_file.exists():
            return

        # Read entire file
        content = self.current_file.read_text(encoding="utf-8")

        # Find frontmatter boundaries
        if not content.startswith("---"):
            return

        end_idx = content.find("---", 3)
        if end_idx == -1:
            return

        # Build new frontmatter
        fm_lines = []
        fm_lines.append("---")
        fm_lines.append(f"created: {self.run_data['created']}")
        fm_lines.append(f"completed: {completed.isoformat()}")
        fm_lines.append(f"status: {status}")
        fm_lines.append(f"image_name: {self.run_data['image_name']}")
        fm_lines.append(f"image_path: {self.run_data['image_path']}")
        fm_lines.append(f"calibration_um_per_px: {self.run_data['calibration_um_per_px']}")
        fm_lines.append(f"provider: {self.run_data['provider']}")
        fm_lines.append(f"model: {self.run_data['model']}")
        fm_lines.append(f"target_hexagonalness: {self.run_data['target_hexagonalness']}")
        fm_lines.append(f"max_iterations: {self.run_data['max_iterations']}")
        fm_lines.append(f"initial_profile: {self.run_data['initial_profile']}")
        fm_lines.append(f"total_iterations: {len(self.iterations)}")
        fm_lines.append(f"best_iteration: {best_iteration}")
        fm_lines.append(f"best_hexagonalness: {best_hexagonalness:.3f}")
        if final_metrics:
            fm_lines.append(f"final_tubercle_count: {final_metrics.get('n_tubercles', 0)}")
        fm_lines.append(f"total_input_tokens: {self._total_input_tokens}")
        fm_lines.append(f"total_output_tokens: {self._total_output_tokens}")
        fm_lines.append(f"estimated_cost_usd: {estimated_cost:.4f}")
        fm_lines.append("---")

        new_frontmatter = "\n".join(fm_lines)

        # Replace frontmatter
        new_content = new_frontmatter + content[end_idx + 3:]
        self.current_file.write_text(new_content, encoding="utf-8")

    def log_error(self, error: str) -> None:
        """Log an error message.

        Args:
            error: Error message
        """
        if not self.current_file:
            return

        lines = []
        lines.append("## Error")
        lines.append("")
        lines.append(f"**Timestamp:** {datetime.now().isoformat()}")
        lines.append("")
        lines.append("```")
        lines.append(error)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
