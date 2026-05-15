#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from debug_logger import DebugLogger
from tmux_integration import TmuxIntegration

STATUS_EMOJIS = {
    'running': '🏃',
    'stop': '✅',
    'permission': '❓',
}

KNOWN_PREFIXES = tuple(f"{emoji} " for emoji in STATUS_EMOJIS.values())

logger = DebugLogger('codex_tmux_hooks')
tmux_integration = TmuxIntegration()


def get_script_dir():
    return Path(__file__).parent


def read_hook_payload():
    """Read a hook payload from stdin when Codex invokes the script."""
    if sys.stdin.isatty():
        return None

    payload_data = sys.stdin.read().strip()
    if not payload_data:
        return None

    try:
        payload = json.loads(payload_data)
        logger.debug("Received hook payload", payload=payload)
        return payload
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse hook payload: {exc}")
        return None


def get_current_tmux_pane():
    logger.log_function_call('get_current_tmux_pane')
    try:
        cmd = ['tmux', 'display-message', '-p', '#{pane_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        pane_id = result.stdout.strip()
        logger.log_tmux_command(cmd, pane_id)
        return pane_id
    except subprocess.CalledProcessError as exc:
        logger.log_tmux_command(['tmux', 'display-message', '-p', '#{pane_id}'], error=str(exc))
        logger.error(f"Failed to get current pane ID: {exc}")
        return None


def get_pane_name(pane_id):
    logger.log_function_call('get_pane_name', args=[pane_id])
    try:
        cmd = ['tmux', 'display-message', '-p', '-t', pane_id, '#{window_name}']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        pane_name = result.stdout.strip()
        logger.log_tmux_command(cmd, pane_name)
        return pane_name
    except subprocess.CalledProcessError as exc:
        logger.log_tmux_command(['tmux', 'display-message', '-p', '-t', pane_id, '#{window_name}'], error=str(exc))
        logger.error(f"Failed to get window name for {pane_id}: {exc}")
        return None


def get_window_auto_rename_status(pane_id):
    logger.log_function_call('get_window_auto_rename_status', args=[pane_id])
    try:
        cmd = ['tmux', 'show-options', '-t', pane_id, 'automatic-rename']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        logger.log_tmux_command(cmd, output)
        return 'on' in output
    except subprocess.CalledProcessError as exc:
        logger.log_tmux_command(['tmux', 'show-options', '-t', pane_id, 'automatic-rename'], error=str(exc))
        logger.debug(f"Could not get automatic-rename status for {pane_id}, assuming off")
        return False


def set_window_auto_rename(pane_id, enabled):
    logger.log_function_call('set_window_auto_rename', args=[pane_id, enabled])
    value = 'on' if enabled else 'off'
    try:
        cmd = ['tmux', 'set-option', '-t', pane_id, 'automatic-rename', value]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.log_tmux_command(cmd, "SUCCESS")
        return True
    except subprocess.CalledProcessError as exc:
        logger.log_tmux_command(['tmux', 'set-option', '-t', pane_id, 'automatic-rename', value], error=str(exc))
        logger.error(f"Failed to set automatic-rename for {pane_id}: {exc}")
        return False


def set_pane_name(pane_id, name):
    logger.log_function_call('set_pane_name', args=[pane_id, name])
    try:
        set_window_auto_rename(pane_id, False)
        cmd = ['tmux', 'rename-window', '-t', pane_id, name]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.log_tmux_command(cmd, "SUCCESS")
        logger.info(f"Set pane {pane_id} window name to: {name}")
        return True
    except subprocess.CalledProcessError as exc:
        logger.log_tmux_command(['tmux', 'rename-window', '-t', pane_id, name], error=str(exc))
        logger.error(f"Failed to set window name for {pane_id}: {exc}")
        return False


def get_state_file(pane_id):
    return get_script_dir() / f".pane_state_{pane_id.replace('%', '')}.json"


def save_pane_state(pane_id, original_name, status, auto_rename_was_on):
    logger.log_function_call('save_pane_state', args=[pane_id, original_name, status])
    state = {
        'pane_id': pane_id,
        'original_name': original_name,
        'status': status,
        'timestamp': time.time(),
        'auto_rename_was_on': auto_rename_was_on,
    }
    try:
        with open(get_state_file(pane_id), 'w') as file_handle:
            json.dump(state, file_handle)
        logger.log_pane_state(pane_id, f"SAVED_{status.upper()}", state)
        logger.info(f"Saved state for pane {pane_id}: {status}")
    except IOError as exc:
        logger.error(f"Failed to save state for pane {pane_id}: {exc}")


def load_pane_state(pane_id):
    logger.log_function_call('load_pane_state', args=[pane_id])
    state_file = get_state_file(pane_id)
    if not state_file.exists():
        logger.debug(f"No state file found for pane {pane_id}")
        return None

    try:
        with open(state_file, 'r') as file_handle:
            state = json.load(file_handle)
        logger.log_pane_state(pane_id, "LOADED", state)
        return state
    except (json.JSONDecodeError, IOError) as exc:
        logger.error(f"Failed to load state for pane {pane_id}: {exc}")
        return None


def cleanup_pane_state(pane_id):
    logger.log_function_call('cleanup_pane_state', args=[pane_id])
    state_file = get_state_file(pane_id)
    if not state_file.exists():
        logger.debug(f"No state file to cleanup for pane {pane_id}")
        return

    try:
        state_file.unlink()
        logger.log_pane_state(pane_id, "CLEANED_UP")
    except OSError as exc:
        logger.error(f"Failed to cleanup state for pane {pane_id}: {exc}")


def strip_status_prefix(name):
    for prefix in KNOWN_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def get_original_name(pane_id, current_name):
    state = load_pane_state(pane_id)
    if state:
        return state['original_name']
    return strip_status_prefix(current_name)


def get_codex_pane_id(payload):
    logger.log_function_call('get_codex_pane_id')

    pane_id = os.environ.get('TMUX_PANE')
    if pane_id:
        logger.debug(f"Got pane ID from TMUX_PANE: {pane_id}")
        return pane_id

    if isinstance(payload, dict):
        for key in ('tmux_pane', 'pane_id'):
            value = payload.get(key)
            if isinstance(value, str) and value:
                logger.debug(f"Got pane ID from payload key {key}: {value}")
                return value

    pane_id = get_current_tmux_pane()
    if pane_id:
        logger.debug(f"Using current pane ID as fallback: {pane_id}")
        return pane_id

    logger.error("Could not determine Codex pane ID")
    return None


def set_status_for_pane(pane_id, status):
    logger.log_function_call('set_status_for_pane', args=[pane_id, status])
    tmux_integration.register_ai_pane(pane_id, 'codex')

    current_name = get_pane_name(pane_id)
    if not current_name:
        logger.error(f"Could not get current name for pane {pane_id}")
        return False

    original_name = get_original_name(pane_id, current_name)
    auto_rename_was_on = get_window_auto_rename_status(pane_id)
    new_name = f"{STATUS_EMOJIS[status]} {original_name}"

    if not set_pane_name(pane_id, new_name):
        logger.error(f"Failed to set pane name for {pane_id}")
        return False

    save_pane_state(pane_id, original_name, status, auto_rename_was_on)
    tmux_integration.refresh_session_markers()
    return True


def restore_pane_name(pane_id):
    logger.log_function_call('restore_pane_name', args=[pane_id])
    tmux_integration.register_ai_pane(pane_id, 'codex')
    state = load_pane_state(pane_id)
    if not state:
        logger.warning(f"No state found for pane {pane_id} to restore")
        return False

    original_name = state['original_name']
    auto_rename_was_on = state.get('auto_rename_was_on', True)

    try:
        cmd = ['tmux', 'rename-window', '-t', pane_id, original_name]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.log_tmux_command(cmd, "SUCCESS")
    except subprocess.CalledProcessError as exc:
        logger.log_tmux_command(['tmux', 'rename-window', '-t', pane_id, original_name], error=str(exc))
        logger.error(f"Failed to restore pane {pane_id} name: {exc}")
        return False

    set_window_auto_rename(pane_id, auto_rename_was_on)
    cleanup_pane_state(pane_id)
    tmux_integration.refresh_session_markers()
    logger.info(f"Restored pane {pane_id} window name to: {original_name}")
    return True


def clear_emoji_on_enter():
    logger.log_function_call('clear_emoji_on_enter')
    pane_id = get_current_tmux_pane()
    if not pane_id:
        return

    if load_pane_state(pane_id):
        restore_pane_name(pane_id)


def infer_action_from_payload(payload):
    if not isinstance(payload, dict):
        return None

    candidates = [
        payload.get('hook_event_name'),
        payload.get('event'),
        payload.get('event_name'),
        payload.get('hook'),
        payload.get('type'),
    ]

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        lowered = candidate.lower()
        if lowered == 'stop':
            return 'stop'
        if lowered in ('userpromptsubmit', 'user-prompt-submit'):
            return 'user-prompt-submit'
        if lowered in ('permissionrequest', 'permission-request'):
            return 'permission-request'

    return None


def main():
    payload = read_hook_payload()
    action = sys.argv[1] if len(sys.argv) >= 2 else infer_action_from_payload(payload)

    if not action:
        print("Usage: codex_tmux_hooks.py [user-prompt-submit|stop|permission-request|restore|clear_emoji_on_enter] [pane_id]")
        sys.exit(1)

    logger.info(f"Starting codex_tmux_hooks with action: {action}")

    if action in ('user-prompt-submit', 'userpromptsubmit'):
        pane_id = get_codex_pane_id(payload)
        success = pane_id is not None and set_status_for_pane(pane_id, 'running')
        logger.log_hook_execution('USER_PROMPT_SUBMIT', pane_id, success=success)
        sys.exit(0 if success else 1)

    if action == 'stop':
        pane_id = get_codex_pane_id(payload)
        success = pane_id is not None and set_status_for_pane(pane_id, 'stop')
        logger.log_hook_execution('STOP', pane_id, success=success)
        sys.exit(0 if success else 1)

    if action in ('permission-request', 'permissionrequest'):
        pane_id = get_codex_pane_id(payload)
        success = pane_id is not None and set_status_for_pane(pane_id, 'permission')
        logger.log_hook_execution('PERMISSION_REQUEST', pane_id, success=success)
        sys.exit(0 if success else 1)

    if action == 'restore':
        pane_id = sys.argv[2] if len(sys.argv) >= 3 else get_codex_pane_id(payload)
        success = pane_id is not None and restore_pane_name(pane_id)
        sys.exit(0 if success else 1)

    if action == 'clear_emoji_on_enter':
        clear_emoji_on_enter()
        return

    print(f"Unknown action: {action}")
    sys.exit(1)


if __name__ == '__main__':
    main()
