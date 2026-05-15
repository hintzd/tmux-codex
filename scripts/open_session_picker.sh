#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_PICKER_FORMAT='#{?pane_format,    #{pane_index}: #{pane_title},#{?window_format,  #{window_index}: #{window_name},#{@ai_session_marker}#{session_name}: #{session_windows} windows#{?session_attached, (attached),}}}'

"$SCRIPT_DIR/tmux_integration.py" refresh-session-markers
tmux choose-tree -sZ -F "$SESSION_PICKER_FORMAT"
