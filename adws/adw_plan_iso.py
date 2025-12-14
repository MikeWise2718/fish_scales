#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Plan Iso - AI Developer Workflow for agentic planning in isolated worktrees

Usage:
  uv run adw_plan_iso.py <issue-number> [adw-id]

Workflow:
1. Fetch GitHub issue details
2. Check/create worktree for isolated execution
3. Allocate unique ports for services
4. Setup worktree environment
5. Classify issue type (/chore, /bug, /feature)
6. Create feature branch in worktree
7. Generate implementation plan in worktree
8. Commit plan in worktree
9. Push and create/update PR

This workflow creates an isolated git worktree under trees/<adw_id>/ for
parallel execution without interference.
"""

import sys
import os
import logging
import json
from typing import Optional
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
    classify_issue,
    build_plan,
    generate_branch_name,
    create_commit,
    format_issue_message,
    ensure_adw_id,
    post_workflow_completion_summary,
    AGENT_PLANNER,
)
from adw_modules.utils import setup_logger, check_env_vars
from adw_modules.data_types import GitHubIssue, IssueClassSlashCommand, AgentTemplateRequest
from adw_modules.agent import execute_template
from adw_modules.worktree_ops import (
    create_worktree,
    validate_worktree,
    get_ports_for_adw,
    is_port_available,
    find_next_available_ports,
    setup_worktree_environment,
)
from adw_modules.complexity import estimate_complexity_from_plan
from adw_modules.execution_log import log_execution_start, log_execution_end


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Parse command line args
    if len(sys.argv) < 2:
        print("Usage: uv run adw_plan_iso.py <issue-number> [adw-id]")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Ensure ADW ID exists with initialized state
    temp_logger = setup_logger(adw_id, "adw_plan_iso") if adw_id else None
    adw_id = ensure_adw_id(issue_number, adw_id, temp_logger)

    # Load the state that was created/found by ensure_adw_id
    state = ADWState.load(adw_id, temp_logger)

    # Ensure state has the adw_id field
    if not state.get("adw_id"):
        state.update(adw_id=adw_id)

    # Track that this ADW workflow has run
    state.append_adw_id("adw_plan_iso")

    # Set up logger with ADW ID
    logger = setup_logger(adw_id, "adw_plan_iso")
    logger.info(f"ADW Plan Iso starting - ID: {adw_id}, Issue: {issue_number}")

    # Start execution logging
    start_entry = log_execution_start(
        script_name="adw_plan_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
    )

    exit_code = 0
    success = True
    error_info = None
    worktree_path = None

    try:
        # Validate environment
        check_env_vars(logger)

        # Get repo information
        try:
            github_repo_url = get_repo_url()
            repo_path = extract_repo_path(github_repo_url)
        except ValueError as e:
            logger.error(f"Error getting repository URL: {e}")
            sys.exit(1)

        # Check if worktree already exists
        valid, error = validate_worktree(adw_id, state)
        if valid:
            logger.info(f"Using existing worktree for {adw_id}")
            worktree_path = state.get("worktree_path")
            backend_port = state.get("backend_port")
            frontend_port = state.get("frontend_port")
        else:
            # Allocate ports for this instance
            backend_port, frontend_port = get_ports_for_adw(adw_id)

            # Check port availability
            if not (is_port_available(backend_port) and is_port_available(frontend_port)):
                logger.warning(f"Deterministic ports {backend_port}/{frontend_port} are in use, finding alternatives")
                backend_port, frontend_port = find_next_available_ports(adw_id)

            logger.info(f"Allocated ports - Backend: {backend_port}, Frontend: {frontend_port}")
            state.update(backend_port=backend_port, frontend_port=frontend_port)
            state.save("adw_plan_iso")

        # Fetch issue details
        issue: GitHubIssue = fetch_issue(issue_number, repo_path)

        logger.debug(f"Fetched issue: {issue.model_dump_json(indent=2, by_alias=True)}")
        make_issue_comment(
            issue_number, format_issue_message(adw_id, "ops", "✅ Starting isolated planning phase")
        )

        make_issue_comment(
            issue_number,
            f"{adw_id}_ops: 🔍 Using state\n```json\n{json.dumps(state.data, indent=2)}\n```",
        )

        # Classify the issue
        issue_command, error = classify_issue(issue, adw_id, logger)

        if error:
            logger.error(f"Error classifying issue: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"❌ Error classifying issue: {error}"),
            )
            sys.exit(1)

        state.update(issue_class=issue_command)
        state.save("adw_plan_iso")
        logger.info(f"Issue classified as: {issue_command}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"✅ Issue classified as: {issue_command}"),
        )

        # Generate branch name
        branch_name, error = generate_branch_name(issue, issue_command, adw_id, logger)

        if error:
            logger.error(f"Error generating branch name: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id, "ops", f"❌ Error generating branch name: {error}"
                ),
            )
            sys.exit(1)

        # Don't create branch here - let worktree create it
        # The worktree command will create the branch when we specify -b
        state.update(branch_name=branch_name)
        state.save("adw_plan_iso")
        logger.info(f"Will create branch in worktree: {branch_name}")

        # Create worktree if it doesn't exist
        if not valid:
            logger.info(f"Creating worktree for {adw_id}")
            worktree_path, error = create_worktree(adw_id, branch_name, logger)

            if error:
                logger.error(f"Error creating worktree: {error}")
                make_issue_comment(
                    issue_number,
                    format_issue_message(adw_id, "ops", f"❌ Error creating worktree: {error}"),
                )
                sys.exit(1)

            state.update(worktree_path=worktree_path)
            state.save("adw_plan_iso")
            logger.info(f"Created worktree at {worktree_path}")

            # Setup worktree environment (create .ports.env)
            setup_worktree_environment(worktree_path, backend_port, frontend_port, logger)

            # Run install_worktree command to set up the isolated environment
            logger.info("Setting up isolated environment with custom ports")
            install_request = AgentTemplateRequest(
                agent_name="ops",
                slash_command="/install_worktree",
                args=[worktree_path, str(backend_port), str(frontend_port)],
                adw_id=adw_id,
                working_dir=worktree_path,  # Execute in worktree
            )

            install_response = execute_template(install_request)
            if not install_response.success:
                logger.error(f"Error setting up worktree: {install_response.output}")
                make_issue_comment(
                    issue_number,
                    format_issue_message(adw_id, "ops", f"❌ Error setting up worktree: {install_response.output}"),
                )
                sys.exit(1)

            logger.info("Worktree environment setup complete")

        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"✅ Working in isolated worktree: {worktree_path}\n"
                               f"🔌 Ports - Backend: {backend_port}, Frontend: {frontend_port}"),
        )

        # Build the implementation plan (now executing in worktree)
        logger.info("Building implementation plan in worktree")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_PLANNER, "✅ Building implementation plan in isolated environment"),
        )

        plan_response = build_plan(issue, issue_command, adw_id, logger, working_dir=worktree_path)

        if not plan_response.success:
            logger.error(f"Error building plan: {plan_response.output}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id, AGENT_PLANNER, f"❌ Error building plan: {plan_response.output}"
                ),
            )
            sys.exit(1)

        logger.debug(f"Plan response: {plan_response.output}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_PLANNER, "✅ Implementation plan created"),
        )

        # Get the plan file path directly from response
        logger.info("Getting plan file path")
        plan_file_path = plan_response.output.strip()

        # Validate the path exists (within worktree)
        if not plan_file_path:
            error = "No plan file path returned from planning agent"
            logger.error(error)
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"❌ {error}"),
            )
            sys.exit(1)

        # Check if file exists in worktree
        worktree_plan_path = os.path.join(worktree_path, plan_file_path)
        if not os.path.exists(worktree_plan_path):
            error = f"Plan file does not exist in worktree: {plan_file_path}"
            logger.error(error)
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"❌ {error}"),
            )
            sys.exit(1)

        state.update(plan_file=plan_file_path)
        state.save("adw_plan_iso")
        logger.info(f"Plan file created: {plan_file_path}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"✅ Plan file created: {plan_file_path}"),
        )

        # Estimate complexity from plan
        logger.info("Estimating task complexity from plan")
        complexity, recommended_timeout, reasoning = estimate_complexity_from_plan(worktree_plan_path)

        logger.info(f"Estimated complexity: {complexity.value}")
        logger.info(f"Reasoning: {reasoning}")
        logger.info(f"Recommended timeout: {recommended_timeout}s ({recommended_timeout//60} minutes)")

        # Update state with complexity information
        state.update(
            complexity=complexity.value,
            recommended_timeout=recommended_timeout
        )
        state.save("complexity_estimation")

        # Post complexity estimation to issue
        complexity_message = (
            f"📊 **Complexity Estimation**\n"
            f"- **Level**: {complexity.value}\n"
            f"- **Recommended timeout**: {recommended_timeout//60} minutes ({recommended_timeout}s)\n"
            f"- **Reasoning**: {reasoning}"
        )
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "planner", complexity_message),
        )

        # Create commit message
        logger.info("Creating plan commit")
        commit_msg, error = create_commit(
            AGENT_PLANNER, issue, issue_command, adw_id, logger, worktree_path
        )

        if error:
            logger.error(f"Error creating commit message: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id, AGENT_PLANNER, f"❌ Error creating commit message: {error}"
                ),
            )
            sys.exit(1)

        # Commit the plan (in worktree)
        commit_success, error = commit_changes(commit_msg, cwd=worktree_path)

        if not commit_success:
            logger.error(f"Error committing plan: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(
                    adw_id, AGENT_PLANNER, f"❌ Error committing plan: {error}"
                ),
            )
            sys.exit(1)

        logger.info(f"Committed plan: {commit_msg}")
        make_issue_comment(
            issue_number, format_issue_message(adw_id, AGENT_PLANNER, "✅ Plan committed")
        )

        # Finalize git operations (push and PR)
        # Note: This will work from the worktree context
        finalize_git_operations(state, logger, cwd=worktree_path)

        logger.info("Isolated planning phase completed successfully")

        # Save final state
        state.save("adw_plan_iso")

        # Post completion summary to issue
        post_workflow_completion_summary(
            issue_number=issue_number,
            adw_id=adw_id,
            workflow_name="Planning",
            status="success",
            artifacts={
                "plan_file": plan_file_path,
                "branch": branch_name,
                "worktree": worktree_path
            },
            next_steps=[
                f"Review the plan in the worktree: `{worktree_path}`",
                f"Check the plan file: `{plan_file_path}`",
                f"To implement the plan: `uv run adws/adw_build_iso.py {issue_number} {adw_id}`"
            ],
            worktree_path=worktree_path
        )

    except SystemExit as e:
        # Capture sys.exit() calls
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
        # Log execution end
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
