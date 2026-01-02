"""Agent API routes for Fish Scale UI.

These endpoints allow the UI to start, monitor, and stop the LLM agent
as an external subprocess.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app

agent_bp = Blueprint('agent', __name__)

# Track running agent processes
# Key: session_id, Value: dict with 'process', 'status_file', 'log_file', 'thread'
_running_agents = {}
_agents_lock = threading.Lock()


def _get_temp_dir() -> Path:
    """Get the temporary directory for agent status files.

    Uses platform-appropriate temp directory.
    """
    # Use the app's temp directory if available, else system temp
    temp_dir = Path(tempfile.gettempdir()) / 'fish-scale-agent'
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _write_status(status_file: Path, status: dict):
    """Write status to file atomically."""
    temp_file = status_file.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(status, f)
    temp_file.replace(status_file)


def _read_status(status_file: Path) -> dict:
    """Read status from file with retry for transient Windows file locks."""
    if not status_file.exists():
        return {'state': 'unknown', 'error': 'Status file not found'}

    # Retry a few times for transient file locks (common on Windows)
    max_retries = 3
    retry_delay = 0.1  # 100ms

    for attempt in range(max_retries):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return {'state': 'error', 'error': f'Failed to read status after {max_retries} attempts: {e}'}


def _monitor_agent_process(session_id: str, process: subprocess.Popen,
                            status_file: Path, log_file: Path):
    """Monitor an agent subprocess and update status file.

    This runs in a background thread.
    """
    log_lines = []

    try:
        # Read stdout/stderr in real-time
        while True:
            # Check if process is still running
            return_code = process.poll()

            # Read any available output
            if process.stdout:
                line = process.stdout.readline()
                if line:
                    line_str = line.strip()
                    if line_str:
                        log_lines.append(line_str)
                        # Write log to file
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(line_str + '\n')

                        # Update status with latest output
                        status = _read_status(status_file)
                        status['log_lines'] = log_lines[-50:]  # Keep last 50 lines
                        status['last_output'] = line_str
                        _write_status(status_file, status)

            if return_code is not None:
                # Process has finished
                final_status = {
                    'state': 'completed' if return_code == 0 else 'failed',
                    'return_code': return_code,
                    'log_lines': log_lines[-50:],
                }
                if return_code != 0:
                    final_status['error'] = f'Agent exited with code {return_code}'
                _write_status(status_file, final_status)
                break

            time.sleep(0.1)

    except Exception as e:
        _write_status(status_file, {
            'state': 'error',
            'error': str(e),
            'log_lines': log_lines[-50:],
        })
    finally:
        # Clean up from running agents dict
        with _agents_lock:
            if session_id in _running_agents:
                del _running_agents[session_id]


@agent_bp.route('/start', methods=['POST'])
def start_agent():
    """Start the extraction optimization agent as a subprocess.

    Request body:
        {
            "provider": "claude" | "gemini" | "openrouter" (default: "claude"),
            "model": str (optional, provider-specific default),
            "max_iterations": int (default: 20),
            "verbose": bool (default: false),
            "image_path": str (optional, use if image not already loaded),
            "calibration": float (optional, um/px if not already set)
        }

    Returns:
        {
            "success": true,
            "session_id": "uuid-string",
            "status_file": "/path/to/status.json"
        }
    """
    from fish_scale_ui.services.logging import log_event

    data = request.get_json() or {}

    # Generate session ID
    session_id = uuid.uuid4().hex[:12]

    # Get parameters
    provider = data.get('provider', 'claude')
    model = data.get('model')
    max_iterations = data.get('max_iterations', 20)
    target_score = data.get('target_score', 0.70)
    profile = data.get('profile', 'default')
    use_current_params = data.get('use_current_params', True)
    verbose = data.get('verbose', False)
    image_path = data.get('image_path')
    calibration = data.get('calibration')

    # Validate provider
    valid_providers = ['claude', 'gemini', 'openrouter']
    if provider not in valid_providers:
        return jsonify({
            'error': f'Invalid provider: {provider}. Must be one of: {valid_providers}'
        }), 400

    # Check for API key
    api_key_env = {
        'claude': 'ANTHROPIC_API_KEY',
        'gemini': 'GEMINI_API_KEY',
        'openrouter': 'OPENROUTER_API_KEY',
    }
    env_var = api_key_env.get(provider)
    if not os.environ.get(env_var):
        return jsonify({
            'error': f'API key not set. Set {env_var} environment variable.'
        }), 400

    # Create status and log files
    temp_dir = _get_temp_dir()
    status_file = temp_dir / f'agent-{session_id}.json'
    log_file = temp_dir / f'agent-{session_id}.log'

    # Write initial status
    _write_status(status_file, {
        'state': 'starting',
        'session_id': session_id,
        'provider': provider,
        'model': model,
        'started_at': time.time(),
        'log_lines': [],
    })

    # Build command - use 'optimize' for extraction parameter optimization
    cmd = [sys.executable, '-m', 'fish_scale_agent.cli', 'optimize']

    # For optimize command, image_path is required positional arg
    # If not provided, we need to get current image from shared state
    if image_path:
        cmd.append(image_path)
    else:
        # Try to get current image from shared state
        try:
            from fish_scale_ui.routes.api import _current_image
            # Use 'path' (original file path) or 'web_path' (copied to static)
            img_path = _current_image.get('path') or _current_image.get('web_path')
            if img_path:
                cmd.append(str(img_path))
            else:
                return jsonify({'error': 'No image loaded. Load an image first.'}), 400
        except Exception as e:
            return jsonify({'error': f'Could not get current image: {e}'}), 400

    cmd.extend(['--provider', provider])

    if model:
        cmd.extend(['--model', model])

    cmd.extend(['--max-iterations', str(max_iterations)])

    # Calibration is required for optimize command
    if not calibration:
        # Try to get from shared state
        try:
            from fish_scale_ui.routes.api import _current_image
            calibration = _current_image.get('calibration', {}).get('um_per_px')
        except Exception:
            pass

    if not calibration:
        return jsonify({'error': 'Calibration not set. Set calibration first.'}), 400

    cmd.extend(['--calibration', str(calibration)])

    cmd.extend(['--target-score', str(target_score)])

    if use_current_params:
        cmd.append('--use-current-params')
    elif profile:
        cmd.extend(['--profile', profile])

    if verbose:
        cmd.append('-v')

    # Get UI URL from request or use default
    # The request.host_url gives us the base URL the client used to reach us
    ui_url = data.get('ui_url')
    if not ui_url:
        # Derive from request
        ui_url = request.host_url.rstrip('/')

    cmd.extend(['--ui-url', ui_url])

    try:
        # Start subprocess with unbuffered output
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'  # Ensure Python doesn't buffer output

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line-buffered
            env=env,
        )

        # Start monitor thread
        monitor_thread = threading.Thread(
            target=_monitor_agent_process,
            args=(session_id, process, status_file, log_file),
            daemon=True,
        )
        monitor_thread.start()

        # Track the running agent
        with _agents_lock:
            _running_agents[session_id] = {
                'process': process,
                'status_file': status_file,
                'log_file': log_file,
                'thread': monitor_thread,
            }

        # Update status to running
        _write_status(status_file, {
            'state': 'running',
            'session_id': session_id,
            'provider': provider,
            'model': model,
            'pid': process.pid,
            'started_at': time.time(),
            'log_lines': [],
        })

        log_event('agent_started', {
            'session_id': session_id,
            'provider': provider,
            'model': model,
            'pid': process.pid,
        })

        return jsonify({
            'success': True,
            'session_id': session_id,
            'status_file': str(status_file),
            'pid': process.pid,
        })

    except Exception as e:
        _write_status(status_file, {
            'state': 'error',
            'error': str(e),
        })
        log_event('agent_start_failed', {'error': str(e)})
        return jsonify({'error': f'Failed to start agent: {e}'}), 500


@agent_bp.route('/status/<session_id>', methods=['GET'])
def get_agent_status(session_id: str):
    """Get current agent status from status file.

    Returns:
        {
            "state": "starting" | "running" | "completed" | "failed" | "stopped",
            "session_id": str,
            "provider": str,
            "model": str,
            "pid": int,
            "started_at": float (timestamp),
            "log_lines": [str, ...],
            "last_output": str,
            "error": str (if failed),
            "return_code": int (if completed/failed)
        }
    """
    temp_dir = _get_temp_dir()
    status_file = temp_dir / f'agent-{session_id}.json'

    if not status_file.exists():
        return jsonify({'error': f'Session not found: {session_id}'}), 404

    status = _read_status(status_file)
    return jsonify(status)


@agent_bp.route('/status/<session_id>/log', methods=['GET'])
def get_agent_log(session_id: str):
    """Get full agent log.

    Query parameters:
        offset: int - Line offset to start from (default: 0)
        limit: int - Maximum lines to return (default: 100)

    Returns:
        {
            "session_id": str,
            "lines": [str, ...],
            "total_lines": int,
            "offset": int
        }
    """
    temp_dir = _get_temp_dir()
    log_file = temp_dir / f'agent-{session_id}.log'

    if not log_file.exists():
        return jsonify({'error': f'Log not found for session: {session_id}'}), 404

    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        lines = [line.rstrip('\n') for line in all_lines[offset:offset + limit]]

        return jsonify({
            'session_id': session_id,
            'lines': lines,
            'total_lines': total_lines,
            'offset': offset,
        })

    except OSError as e:
        return jsonify({'error': f'Failed to read log: {e}'}), 500


@agent_bp.route('/stop/<session_id>', methods=['POST'])
def stop_agent(session_id: str):
    """Stop a running agent.

    Returns:
        {"success": true, "message": str}
    """
    from fish_scale_ui.services.logging import log_event

    temp_dir = _get_temp_dir()
    status_file = temp_dir / f'agent-{session_id}.json'

    with _agents_lock:
        agent_info = _running_agents.get(session_id)

    if not agent_info:
        # Check if the status file exists (agent may have finished)
        if status_file.exists():
            status = _read_status(status_file)
            if status.get('state') in ('completed', 'failed', 'stopped'):
                return jsonify({
                    'success': True,
                    'message': f'Agent already {status.get("state")}'
                })
        return jsonify({'error': f'Session not found: {session_id}'}), 404

    process = agent_info['process']

    try:
        # Try graceful termination first
        process.terminate()

        # Wait briefly for process to terminate
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if still running
            process.kill()
            process.wait(timeout=5)

        # Update status
        _write_status(status_file, {
            'state': 'stopped',
            'session_id': session_id,
            'stopped_at': time.time(),
            'message': 'Agent stopped by user',
        })

        log_event('agent_stopped', {'session_id': session_id})

        return jsonify({
            'success': True,
            'message': 'Agent stopped successfully'
        })

    except Exception as e:
        log_event('agent_stop_failed', {'session_id': session_id, 'error': str(e)})
        return jsonify({'error': f'Failed to stop agent: {e}'}), 500


@agent_bp.route('/list', methods=['GET'])
def list_agents():
    """List all agent sessions (running and recent).

    Returns:
        {
            "sessions": [
                {
                    "session_id": str,
                    "state": str,
                    "provider": str,
                    "started_at": float,
                    ...
                },
                ...
            ]
        }
    """
    temp_dir = _get_temp_dir()
    sessions = []

    # List all status files
    for status_file in temp_dir.glob('agent-*.json'):
        try:
            status = _read_status(status_file)
            sessions.append(status)
        except Exception:
            continue

    # Sort by started_at descending (most recent first)
    sessions.sort(key=lambda s: s.get('started_at', 0), reverse=True)

    return jsonify({'sessions': sessions})


@agent_bp.route('/cleanup', methods=['POST'])
def cleanup_agents():
    """Clean up old agent session files.

    Request body:
        {
            "max_age_hours": int (default: 24)
        }

    Returns:
        {"success": true, "removed_count": int}
    """
    data = request.get_json() or {}
    max_age_hours = data.get('max_age_hours', 24)
    max_age_seconds = max_age_hours * 3600

    temp_dir = _get_temp_dir()
    current_time = time.time()
    removed_count = 0

    # Clean up old status and log files
    for pattern in ['agent-*.json', 'agent-*.log']:
        for file_path in temp_dir.glob(pattern):
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    # Don't remove files for running sessions
                    session_id = file_path.stem.replace('agent-', '')
                    with _agents_lock:
                        if session_id not in _running_agents:
                            file_path.unlink()
                            removed_count += 1
            except OSError:
                continue

    return jsonify({
        'success': True,
        'removed_count': removed_count,
    })


@agent_bp.route('/providers', methods=['GET'])
def list_providers():
    """List available LLM providers and their configuration.

    Returns:
        {
            "providers": [
                {
                    "name": "claude",
                    "display_name": "Anthropic Claude",
                    "default_model": "claude-sonnet-4-20250514",
                    "env_var": "ANTHROPIC_API_KEY",
                    "configured": true/false
                },
                ...
            ]
        }
    """
    providers = [
        {
            'name': 'claude',
            'display_name': 'Anthropic Claude',
            'default_model': 'claude-sonnet-4-20250514',
            'env_var': 'ANTHROPIC_API_KEY',
            'configured': bool(os.environ.get('ANTHROPIC_API_KEY')),
        },
        {
            'name': 'gemini',
            'display_name': 'Google Gemini',
            'default_model': 'gemini-2.0-flash',
            'env_var': 'GEMINI_API_KEY',
            'configured': bool(os.environ.get('GEMINI_API_KEY')),
        },
        {
            'name': 'openrouter',
            'display_name': 'OpenRouter',
            'default_model': 'anthropic/claude-sonnet-4',
            'env_var': 'OPENROUTER_API_KEY',
            'configured': bool(os.environ.get('OPENROUTER_API_KEY')),
        },
    ]

    return jsonify({'providers': providers})
