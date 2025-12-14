"""Complexity estimation for ADW workflows.

Estimates task complexity and recommends timeouts based on plan analysis.
"""

import os
import re
from typing import Tuple, Optional
from adw_modules.data_types import TaskComplexity


# Timeout recommendations (in seconds) for each complexity level
COMPLEXITY_TIMEOUTS = {
    TaskComplexity.SIMPLE: 600,         # 10 minutes
    TaskComplexity.MEDIUM: 1200,        # 20 minutes
    TaskComplexity.COMPLEX: 2100,       # 35 minutes
    TaskComplexity.VERY_COMPLEX: 3600,  # 60 minutes
}


def estimate_complexity_from_plan(plan_file: str) -> Tuple[TaskComplexity, int, str]:
    """Estimate task complexity by analyzing the implementation plan.

    Args:
        plan_file: Path to the plan markdown file

    Returns:
        Tuple of (complexity_level, recommended_timeout_seconds, reasoning)
    """
    if not os.path.exists(plan_file):
        # Default to medium if plan file doesn't exist
        return TaskComplexity.MEDIUM, COMPLEXITY_TIMEOUTS[TaskComplexity.MEDIUM], "Plan file not found, using default"

    try:
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_content = f.read().lower()
    except Exception as e:
        return TaskComplexity.MEDIUM, COMPLEXITY_TIMEOUTS[TaskComplexity.MEDIUM], f"Error reading plan: {e}"

    # Initialize scoring
    complexity_score = 0
    reasons = []

    # Factor 1: File count
    # Look for "relevant files" or "new files" sections
    files_section = re.search(r'## relevant files.*?(?=\n##|\Z)', plan_content, re.DOTALL | re.IGNORECASE)
    new_files_section = re.search(r'## new files.*?(?=\n##|\Z)', plan_content, re.DOTALL | re.IGNORECASE)

    file_count = 0
    if files_section:
        # Count bullet points or file paths
        file_count += len(re.findall(r'[-*]\s+`?[\w/\.]+', files_section.group(0)))
    if new_files_section:
        file_count += len(re.findall(r'[-*]\s+`?[\w/\.]+', new_files_section.group(0)))

    if file_count == 0:
        # Try counting file mentions in general (less accurate)
        file_count = len(re.findall(r'\w+\.(py|js|html|css|tsx|jsx|ts)', plan_content))

    if file_count >= 10:
        complexity_score += 3
        reasons.append(f"{file_count} files to modify")
    elif file_count >= 5:
        complexity_score += 2
        reasons.append(f"{file_count} files to modify")
    elif file_count >= 2:
        complexity_score += 1
        reasons.append(f"{file_count} files to modify")

    # Factor 2: UI changes
    ui_keywords = ['html', 'css', 'template', 'frontend', 'ui', 'interface', 'button', 'form', 'canvas', 'svg']
    ui_mentions = sum(1 for keyword in ui_keywords if keyword in plan_content)

    if ui_mentions >= 5:
        complexity_score += 2
        reasons.append("extensive UI changes")
    elif ui_mentions >= 2:
        complexity_score += 1
        reasons.append("UI changes required")

    # Factor 3: Complexity keywords
    complexity_keywords = {
        'refactor': 2,
        'architecture': 2,
        'migrate': 2,
        'restructure': 2,
        'redesign': 2,
        'complex': 1,
        'multiple': 1,
        'integration': 1,
        'api': 1,
        'database': 1,
        'state management': 2,
        'authentication': 2,
    }

    for keyword, score in complexity_keywords.items():
        if keyword in plan_content:
            complexity_score += score
            reasons.append(f"involves {keyword}")

    # Factor 4: Test requirements
    if 'e2e test' in plan_content or 'end-to-end' in plan_content:
        complexity_score += 1
        reasons.append("E2E tests needed")
    elif 'test' in plan_content:
        complexity_score += 0.5
        reasons.append("tests needed")

    # Factor 5: Documentation
    if 'document' in plan_content or 'readme' in plan_content:
        complexity_score += 0.5
        reasons.append("documentation required")

    # Determine complexity level based on score
    if complexity_score >= 8:
        level = TaskComplexity.VERY_COMPLEX
        reasoning = "Very complex task: " + ", ".join(reasons[:4])
    elif complexity_score >= 5:
        level = TaskComplexity.COMPLEX
        reasoning = "Complex task: " + ", ".join(reasons[:3])
    elif complexity_score >= 2:
        level = TaskComplexity.MEDIUM
        reasoning = "Medium complexity: " + ", ".join(reasons[:3])
    else:
        level = TaskComplexity.SIMPLE
        reasoning = "Simple task" + (": " + ", ".join(reasons) if reasons else "")

    return level, COMPLEXITY_TIMEOUTS[level], reasoning


def check_timeout_sufficient(
    complexity: TaskComplexity,
    current_timeout: int
) -> Tuple[bool, Optional[str]]:
    """Check if current timeout is sufficient for the complexity level.

    Args:
        complexity: Estimated task complexity
        current_timeout: Current workflow timeout in seconds

    Returns:
        Tuple of (is_sufficient, warning_message)
    """
    recommended = COMPLEXITY_TIMEOUTS[complexity]

    if current_timeout >= recommended:
        return True, None

    # Calculate how much more time is needed
    additional_minutes = (recommended - current_timeout) // 60

    warning = (
        f"⚠️ **Timeout Warning**: This is a **{complexity.value}** task "
        f"(recommended: {recommended//60} minutes, current: {current_timeout//60} minutes). "
        f"Consider increasing timeout by {additional_minutes} minutes: "
        f"`--workflow-timeout {recommended}`"
    )

    return False, warning
