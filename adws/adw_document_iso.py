#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Document Iso - AI Developer Workflow for documentation generation in isolated worktrees

Usage:
  uv run adw_document_iso.py <issue-number> <adw-id>

Workflow:
1. Load state and validate worktree exists
2. Find spec file from worktree
3. Analyze git changes in worktree
4. Generate feature documentation
5. Update conditional docs
6. Commit documentation in worktree

This workflow REQUIRES that adw_plan_iso.py or adw_patch_iso.py has been run first
to create the worktree. It cannot create worktrees itself.
"""

import sys
import os
import logging
import json
import subprocess
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from adw_modules.state import ADWState
from adw_modules.git_ops import commit_changes, finalize_git_operations
from adw_modules.github import (
    fetch_issue,
    make_issue_comment,
    get_repo_url,
    extract_repo_path,
)
from adw_modules.workflow_ops import (
    create_commit,
    format_issue_message,
    find_spec_file,
    post_workflow_completion_summary,
)
from adw_modules.utils import setup_logger, check_env_vars
from adw_modules.data_types import (
    GitHubIssue,
    GitHubUser,
    AgentTemplateRequest,
    DocumentationResult,
    IssueClassSlashCommand,
)
from adw_modules.agent import execute_template
from adw_modules.worktree_ops import validate_worktree
from adw_modules.execution_log import log_execution_start, log_execution_end

# Agent name constant
AGENT_DOCUMENTER = "documenter"

DOCS_PATH = "app_docs/"


def check_for_changes(logger: logging.Logger, cwd: Optional[str] = None) -> bool:
    """Check if there are any changes between current branch and origin/main."""
    try:
        result = subprocess.run(
            ["git", "diff", "origin/main", "--stat"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        has_changes = bool(result.stdout.strip())
        if not has_changes:
            logger.info("No changes detected between current branch and origin/main")
        else:
            logger.info(f"Found changes:\n{result.stdout}")
        return has_changes
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check for changes: {e}")
        return True


def generate_documentation(
    issue_number: str,
    adw_id: str,
    logger: logging.Logger,
    spec_file: str,
    working_dir: Optional[str] = None,
) -> Optional[DocumentationResult]:
    """Generate documentation using the /document command."""
    request = AgentTemplateRequest(
        agent_name=AGENT_DOCUMENTER,
        slash_command="/document",
        args=[spec_file],
        adw_id=adw_id,
        working_dir=working_dir,
    )

    logger.debug(f"documentation_request: {request.model_dump_json(indent=2, by_alias=True)}")
    response = execute_template(request)
    logger.debug(f"documentation_response: {response.model_dump_json(indent=2, by_alias=True)}")

    if not response.success:
        logger.error(f"Documentation generation failed: {response.output}")
        make_issue_comment(
            issue_number,
            format_issue_message(
                adw_id,
                AGENT_DOCUMENTER,
                f"❌ Documentation generation failed: {response.output}",
            ),
        )
        return None

    doc_file_path = response.output.strip()

    if doc_file_path and doc_file_path != "No documentation needed":
        full_path = os.path.join(working_dir or ".", doc_file_path)
        if os.path.exists(full_path):
            logger.info(f"Documentation created at: {doc_file_path}")
            return DocumentationResult(
                success=True,
                documentation_created=True,
                documentation_path=doc_file_path,
                error_message=None,
            )
        else:
            logger.warning(f"Agent reported doc file {doc_file_path} but file not found")
            return DocumentationResult(
                success=True,
                documentation_created=False,
                documentation_path=None,
                error_message=f"Reported file {doc_file_path} not found",
            )
    else:
        logger.info("Agent determined no documentation changes were needed")
        return DocumentationResult(
            success=True,
            documentation_created=False,
            documentation_path=None,
            error_message=None,
        )


def track_agentic_kpis(
    issue_number: str,
    adw_id: str,
    state: ADWState,
    logger: logging.Logger,
    worktree_path: str,
) -> None:
    """Track agentic KPIs - never fails the main workflow."""
    try:
        logger.info("Tracking agentic KPIs...")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", "📊 Updating agentic KPIs"),
        )

        kpi_request = AgentTemplateRequest(
            agent_name="kpi_tracker",
            slash_command="/track_agentic_kpis",
            args=[json.dumps(state.data, indent=2)],
            adw_id=adw_id,
            working_dir=worktree_path,
        )

        try:
            kpi_response = execute_template(kpi_request)

            if kpi_response.success:
                logger.info("Successfully updated agentic KPIs")
                try:
                    commit_msg, error = create_commit(
                        "kpi_tracker",
                        GitHubIssue(
                            number=int(issue_number),
                            title="Update agentic KPIs",
                            body="Tracking ADW performance metrics",
                            state="open",
                            author=GitHubUser(login="system"),
                            created_at=datetime.now(),
                            updated_at=datetime.now(),
                            url="",
                        ),
                        "/chore",
                        adw_id,
                        logger,
                        worktree_path,
                    )
                    if commit_msg and not error:
                        logger.info(f"Committed KPI update: {commit_msg}")
                        make_issue_comment(
                            issue_number,
                            format_issue_message(adw_id, "kpi_tracker", "✅ Agentic KPIs updated"),
                        )
                    elif error:
                        logger.warning(f"Failed to create KPI commit: {error}")
                except Exception as e:
                    logger.warning(f"Failed to commit KPI update: {e}")
            else:
                logger.warning("Failed to update agentic KPIs - continuing anyway")
                make_issue_comment(
                    issue_number,
                    format_issue_message(adw_id, "kpi_tracker", "⚠️ Failed to update agentic KPIs - continuing anyway"),
                )
        except Exception as e:
            logger.warning(f"Error executing KPI template: {e}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "kpi_tracker", "⚠️ Error tracking agentic KPIs - continuing anyway"),
            )
    except Exception as e:
        logger.error(f"Unexpected error in track_agentic_kpis: {e}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "kpi_tracker", "⚠️ Top level error tracking agentic KPIs - continuing anyway"),
        )


def main():
    """Main entry point."""
    load_dotenv()

    if len(sys.argv) < 3:
        print("Usage: uv run adw_document_iso.py <issue-number> <adw-id>")
        print("\nError: adw-id is required to locate the worktree")
        print("Run adw_plan_iso.py or adw_patch_iso.py first to create the worktree")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2]

    temp_logger = setup_logger(adw_id, "adw_document_iso")
    state = ADWState.load(adw_id, temp_logger)
    if state:
        issue_number = state.get("issue_number", issue_number)
        make_issue_comment(
            issue_number,
            f"{adw_id}_ops: 🔍 Found existing state - starting isolated documentation\n```json\n{json.dumps(state.data, indent=2)}\n```",
        )
    else:
        logger = setup_logger(adw_id, "adw_document_iso")
        logger.error(f"No state found for ADW ID: {adw_id}")
        logger.error("Run adw_plan_iso.py or adw_patch_iso.py first to create the worktree and state")
        print(f"\nError: No state found for ADW ID: {adw_id}")
        print("Run adw_plan_iso.py or adw_patch_iso.py first to create the worktree and state")
        sys.exit(1)

    state.append_adw_id("adw_document_iso")

    logger = setup_logger(adw_id, "adw_document_iso")
    logger.info(f"ADW Document Iso starting - ID: {adw_id}, Issue: {issue_number}")

    worktree_path = state.get("worktree_path")
    start_entry = log_execution_start(
        script_name="adw_document_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
        worktree_path=worktree_path,
    )

    exit_code = 0
    success = True
    error_info = None

    try:
        check_env_vars(logger)

        valid, error = validate_worktree(adw_id, state)
        if not valid:
            logger.error(f"Worktree validation failed: {error}")
            logger.error("Run adw_plan_iso.py or adw_patch_iso.py first")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id,
                    "ops",
                    f"❌ Worktree validation failed: {error}\n"
                    "Run adw_plan_iso.py or adw_patch_iso.py first",
                ),
            )
            sys.exit(1)

        worktree_path = state.get("worktree_path")
        logger.info(f"Using worktree at: {worktree_path}")

        backend_port = state.get("backend_port", "9100")
        frontend_port = state.get("frontend_port", "9200")

        make_issue_comment(
            issue_number,
            format_issue_message(
                adw_id,
                "ops",
                f"✅ Starting isolated documentation phase\n"
                f"🏠 Worktree: {worktree_path}\n"
                f"🔌 Ports - Backend: {backend_port}, Frontend: {frontend_port}",
            ),
        )

        if not check_for_changes(logger, cwd=worktree_path):
            logger.info("No changes to document - skipping documentation generation")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id,
                    "ops",
                    "ℹ️ No changes detected between current branch and origin/main - skipping documentation",
                ),
            )
            return

        logger.info("Looking for spec file in worktree")
        spec_file = find_spec_file(state, logger)

        if not spec_file:
            error_msg = "Could not find spec file for documentation"
            logger.error(error_msg)
            make_issue_comment(
                issue_number, format_issue_message(adw_id, "ops", f"❌ {error_msg}")
            )
            sys.exit(1)

        logger.info(f"Found spec file: {spec_file}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"📋 Found spec file: {spec_file}"),
        )

        logger.info("Generating documentation")
        make_issue_comment(
            issue_number,
            format_issue_message(
                adw_id,
                AGENT_DOCUMENTER,
                "📝 Generating documentation in isolated environment...",
            ),
        )

        doc_result = generate_documentation(
            issue_number, adw_id, logger, spec_file, working_dir=worktree_path
        )

        if not doc_result:
            sys.exit(1)

        if doc_result.documentation_created:
            logger.info(f"Documentation created at: {doc_result.documentation_path}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id,
                    AGENT_DOCUMENTER,
                    f"✅ Documentation generated successfully\n📁 Location: {doc_result.documentation_path}",
                ),
            )
        else:
            logger.info("No documentation changes were needed")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id, AGENT_DOCUMENTER, "ℹ️ No documentation changes were needed"
                ),
            )

        try:
            github_repo_url = get_repo_url()
            repo_path = extract_repo_path(github_repo_url)
        except ValueError as e:
            logger.error(f"Error getting repository URL: {e}")
            sys.exit(1)

        logger.info("Fetching issue data for commit message")
        issue = fetch_issue(issue_number, repo_path)

        issue_command = state.get("issue_class", "/feature")

        logger.info("Creating documentation commit")
        commit_msg, error = create_commit(
            AGENT_DOCUMENTER, issue, issue_command, adw_id, logger, worktree_path
        )

        if error:
            logger.error(f"Error creating commit message: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id, AGENT_DOCUMENTER, f"❌ Error creating commit message: {error}"
                ),
            )
            sys.exit(1)

        commit_success, error = commit_changes(commit_msg, cwd=worktree_path)

        if not commit_success:
            logger.error(f"Error committing documentation: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id,
                    AGENT_DOCUMENTER,
                    f"❌ Error committing documentation: {error}",
                ),
            )
            sys.exit(1)

        logger.info(f"Committed documentation: {commit_msg}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_DOCUMENTER, "✅ Documentation committed"),
        )

        track_agentic_kpis(issue_number, adw_id, state, logger, worktree_path)

        finalize_git_operations(state, logger, cwd=worktree_path)

        logger.info("Isolated documentation phase completed successfully")

        state.save("adw_document_iso")

        post_workflow_completion_summary(
            issue_number=issue_number,
            adw_id=adw_id,
            workflow_name="Documentation",
            status="success",
            artifacts={
                "documentation": f"Created in {DOCS_PATH}",
                "conditional_docs": "Updated (if applicable)"
            },
            next_steps=[
                f"Review the documentation in: `{DOCS_PATH}`",
                f"Check the worktree: `{worktree_path}`",
                f"Review and merge the PR when ready"
            ],
            worktree_path=worktree_path
        )

    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        success = exit_code == 0
        if not success:
            error_info = ("SystemExit", f"Script exited with code {exit_code}")
        raise
    except Exception as e:
        exit_code = 1
        success = False
        error_info = (type(e).__name__, str(e))
        raise
    finally:
        log_execution_end(
            start_entry=start_entry,
            exit_code=exit_code,
            success=success,
            error_type=error_info[0] if error_info else None,
            error_message=error_info[1] if error_info else None,
            model_set=state.get("model_set") if state else None,
        )


if __name__ == "__main__":
    main()
