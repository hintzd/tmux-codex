# Codex Tmux Plugin

A tmux plugin that adds status emojis to window names while Codex is running in a pane. It shows when Codex is actively handling a prompt, when Codex finishes a turn, and when Codex is waiting for your approval, then restores the original name when you return to the pane or press Enter.

This project is derived from [hintzd/tmux-claude](https://github.com/hintzd/tmux-claude), adapted for Codex and its hook model.

## Features

- **🏃 Running Status**: Shows a runner after the latest prompt is submitted, while Codex is still handling it and has not yet finished or asked for approval
- **✅ Stop Status**: Shows a checkmark when Codex finishes a turn
- **❓ Approval Status**: Shows a question mark when Codex requests approval
- **🤖 Session Picker Marker**: Shows one `🤖` per AI agent pane in the session picker (`prefix + S`) — works across both tmux-codex and tmux-claude if both are installed, so a session with two Codex panes and one Claude pane shows `🤖🤖🤖`
- **Multi-pane Support**: Each tmux pane keeps its own status
- **Smart Restoration**: Restores the original window name on pane focus or Enter
- **Pure Python**: Uses only Python 3 standard library

## Requirements

- **Python 3.6+**
- tmux
- Codex CLI with hooks enabled

## Installation

### Using TPM

Add the plugin to `~/.tmux.conf`:

```bash
set -g @plugin 'hintzd/tmux-codex'
```

Then press `prefix + I`.

### Manual Installation

Clone the repository:

```bash
git clone https://github.com/hintzd/tmux-codex.git ~/.tmux/plugins/tmux-codex
```

Add to `~/.tmux.conf`:

```bash
run-shell ~/.tmux/plugins/tmux-codex/tmux-codex.tmux
```

Reload tmux:

```bash
tmux source-file ~/.tmux.conf
```

## Quick Start

1. Install the plugin with TPM or clone it manually.
2. Add the Codex hook configuration from [example-codex-config.toml](example-codex-config.toml) into `~/.codex/config.toml`.
3. Replace `/absolute/path/to/tmux-codex/` with the real install path on your machine.
4. Start Codex and run `/hooks`.
5. Trust the three configured hooks for `UserPromptSubmit`, `Stop`, and `PermissionRequest` when prompted.

The plugin will not update tmux pane status until the hooks are trusted.

## Configuration

### Recommended tmux setting

For the cleanest behavior, disable automatic window renaming:

```bash
set-option -g automatic-rename off
set-option -g automatic-rename-format ''
```

The plugin will still work with automatic renaming enabled, but tmux may overwrite custom names.

### Codex hook setup

Enable Codex hooks in `~/.codex/config.toml` and register the plugin commands for `UserPromptSubmit`, `Stop`, and `PermissionRequest`.

Use [example-codex-config.toml](example-codex-config.toml) as the starting point, then replace `/absolute/path/to/tmux-codex/` with your install path.

After saving the config, start Codex in a tmux pane and run `/hooks` so Codex can prompt you to trust all configured hooks. Approve the `UserPromptSubmit`, `Stop`, and `PermissionRequest` hooks or the plugin will not be allowed to rename the tmux window.

Example:

```toml
[features]
hooks = true

[[hooks.UserPromptSubmit]]
matcher = "*"

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "python3 /absolute/path/to/tmux-codex/scripts/codex_tmux_hooks.py user-prompt-submit"
timeout = 30

[[hooks.Stop]]
matcher = "*"

[[hooks.Stop.hooks]]
type = "command"
command = "python3 /absolute/path/to/tmux-codex/scripts/codex_tmux_hooks.py stop"
timeout = 30

[[hooks.PermissionRequest]]
matcher = "*"

[[hooks.PermissionRequest.hooks]]
type = "command"
command = "python3 /absolute/path/to/tmux-codex/scripts/codex_tmux_hooks.py permission-request"
timeout = 30
statusMessage = "Updating tmux pane status"
```

## Usage

Run Codex inside any tmux pane.

- When you submit a prompt and Codex starts handling it, the window name becomes `🏃 <original-name>`.
  This means the latest prompt is in progress and Codex has neither finished nor asked for approval yet.
- When Codex finishes a turn, the window name becomes `✅ <original-name>`.
- When Codex asks for approval, the window name becomes `❓ <original-name>`.
- When you focus that pane or press Enter in it, the original window name is restored.
- In the session picker (`prefix + S`), sessions show one `🤖` per AI agent pane — e.g. two Codex panes in a session shows `🤖🤖 <session-name>`. If [tmux-claude](https://github.com/hintzd/tmux-claude) is also installed, Claude panes in the same session count too. The actual tmux session name is never changed.

If this is your first run after adding the hook config, use `/hooks` inside Codex and trust all three hook commands before expecting the status updates to appear.

## Commands

Manual testing:

```bash
./scripts/codex_tmux_hooks.py user-prompt-submit
./scripts/codex_tmux_hooks.py stop
./scripts/codex_tmux_hooks.py permission-request
./scripts/codex_tmux_hooks.py restore
```

Debugging:

```bash
./scripts/tmux_integration.py list-panes
./scripts/tmux_integration.py find-codex
./scripts/pane_tracker.py status
```

## How It Works

1. Codex runs the plugin hook script for `UserPromptSubmit`, `Stop`, and `PermissionRequest`.
2. The script resolves the tmux pane from `TMUX_PANE`, with current-pane fallback for manual testing.
3. The plugin prefixes the window name with `🏃`, `✅`, or `❓`.
   `🏃` means the turn is in progress, `❓` means approval is required, and `✅` means the request finished.
4. The plugin overrides `prefix + S` and refreshes session markers before opening the picker. Each AI agent pane in the session contributes one `🤖` to the count. If [tmux-claude](https://github.com/hintzd/tmux-claude) is also installed, its Claude panes count too — both plugins share a tracker at `~/.config/tmux/ai-pane-tracker.json`. Panes are auto-detected by process inspection, so the count is correct even before any hook has fired.
5. The original name and prior `automatic-rename` value are saved in a state file.
6. Focusing the pane or pressing Enter restores the original name and cleans up the state file.

## File Structure

```text
tmux-codex/
├── tmux-codex.tmux
├── scripts/
│   ├── codex_tmux_hooks.py
│   ├── tmux_integration.py
│   ├── pane_tracker.py
│   ├── notification_handler.py
│   └── debug_logger.py
├── example-codex-config.toml
└── README.md
```

## Using alongside tmux-claude

If you also install [tmux-claude](https://github.com/hintzd/tmux-claude), the session picker `🤖` counts will aggregate across both plugins automatically. Both plugins write to the shared tracker at `~/.config/tmux/ai-pane-tracker.json`, which is created automatically on first use. No extra configuration is needed — install both plugins and load both in your `~/.tmux.conf`.

## Attribution

- Original project inspiration and derivative base: [hintzd/tmux-claude](https://github.com/hintzd/tmux-claude)
- This repository adapts that idea for Codex-specific hook events and pane-state handling

## Debug Logging

Enable logging:

```bash
./scripts/debug_logger.py enable
export TMUX_CODEX_DEBUG=1
```

View logs:

```bash
./scripts/debug_logger.py view
./scripts/debug_logger.py view codex_tmux_hooks
./scripts/debug_logger.py view tmux_integration
./scripts/debug_logger.py view pane_tracker
```

Clear logs:

```bash
./scripts/debug_logger.py clear
```

Logs are written under `scripts/.logs/`, including `tmux_codex.log`.
