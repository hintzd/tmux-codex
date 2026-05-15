#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from debug_logger import DebugLogger

SHARED_TRACKER = Path.home() / '.config' / 'tmux' / 'ai-pane-tracker.json'

class TmuxIntegration:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.logger = DebugLogger('tmux_integration')
    
    def run_tmux_command(self, args: List[str]) -> Optional[str]:
        """Run a tmux command and return output"""
        self.logger.log_function_call('run_tmux_command', args=[args])
        try:
            cmd = ['tmux'] + args
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            self.logger.log_tmux_command(cmd, output)
            return output
        except subprocess.CalledProcessError as e:
            self.logger.log_tmux_command(['tmux'] + args, error=str(e))
            self.logger.error(f"Tmux command failed: {e}")
            return None
    
    def get_all_panes(self) -> List[Dict]:
        """Get information about all tmux panes"""
        panes = []
        output = self.run_tmux_command([
            'list-panes',
            '-a',
            '-F',
            '#{session_name}\t#{window_index}\t#{pane_index}\t#{window_name}\t#{pane_id}\t#{pane_title}\t#{pane_pid}',
        ])
        if output:
            for line in output.split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) == 7:
                        panes.append({
                            'session_name': parts[0],
                            'window_index': parts[1],
                            'pane_index': parts[2],
                            'window_name': parts[3],
                            'pane_id': parts[4],
                            'title': parts[5],
                            'pid': parts[6],
                        })
        return panes
    
    def get_pane_info(self, pane_id: str) -> Optional[Dict]:
        """Get detailed information about a specific pane"""
        output = self.run_tmux_command([
            'display-message',
            '-p',
            '-t',
            pane_id,
            '#{session_name}\t#{window_index}\t#{pane_index}\t#{window_name}\t#{pane_id}\t#{pane_title}\t#{pane_pid}',
        ])
        if output:
            parts = output.split('\t')
            if len(parts) == 7:
                return {
                    'session_name': parts[0],
                    'window_index': parts[1],
                    'pane_index': parts[2],
                    'window_name': parts[3],
                    'pane_id': parts[4],
                    'title': parts[5],
                    'pid': parts[6],
                }
        return None
    
    def get_pane_title(self, pane_id: str) -> Optional[str]:
        """Get the window name of a specific pane"""
        return self.run_tmux_command(['display-message', '-p', '-t', pane_id, '#{window_name}'])
    
    def set_pane_title(self, pane_id: str, title: str) -> bool:
        """Set the window name of a specific pane"""
        try:
            subprocess.run(['tmux', 'rename-window', '-t', pane_id, title], 
                          check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_current_pane(self) -> Optional[str]:
        """Get the current pane ID"""
        return self.run_tmux_command(['display-message', '-p', '#{pane_id}'])
    
    def get_current_session(self) -> Optional[str]:
        """Get the current session name"""
        return self.run_tmux_command(['display-message', '-p', '#{session_name}'])

    def get_all_sessions(self) -> List[str]:
        """Return all tmux session names."""
        output = self.run_tmux_command(['list-sessions', '-F', '#{session_name}'])
        if not output:
            return []
        return [line for line in output.split('\n') if line.strip()]

    def load_tracked_panes(self) -> Dict:
        """Load AI agent panes from the shared tracker file."""
        if not SHARED_TRACKER.exists():
            return {}
        try:
            with open(SHARED_TRACKER, 'r') as file_handle:
                data = json.load(file_handle)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_tracked_panes(self, tracked_panes: Dict):
        """Persist AI agent panes to the shared tracker file."""
        SHARED_TRACKER.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(SHARED_TRACKER, 'w') as file_handle:
                json.dump(tracked_panes, file_handle, indent=2)
        except OSError:
            pass

    def register_ai_pane(self, pane_id: str, agent: str) -> bool:
        """Track a pane as an AI agent pane (agent = 'claude' or 'codex')."""
        pane_info = self.get_pane_info(pane_id)
        if not pane_info:
            return False
        tracked_panes = self.load_tracked_panes()
        tracked_panes[pane_id] = {
            'agent': agent,
            'session_name': pane_info['session_name'],
        }
        self.save_tracked_panes(tracked_panes)
        return True

    def unregister_ai_pane(self, pane_id: str):
        """Remove a pane from the shared tracker."""
        tracked_panes = self.load_tracked_panes()
        if pane_id in tracked_panes:
            del tracked_panes[pane_id]
            self.save_tracked_panes(tracked_panes)
    
    def is_pane_active(self, pane_id: str) -> bool:
        """Check if a pane is currently active"""
        current_pane = self.get_current_pane()
        return current_pane == pane_id
    
    def find_codex_panes(self) -> List[Dict]:
        """Find panes that might be running Codex."""
        codex_panes = []
        panes = self.get_all_panes()
        
        for pane in panes:
            # Check if the pane process tree contains codex.
            try:
                result = subprocess.run(['pstree', '-p', pane['pid']], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0 and 'codex' in result.stdout.lower():
                    codex_panes.append(pane)
            except FileNotFoundError:
                try:
                    result = subprocess.run(['ps', '-p', pane['pid'], '-o', 'comm='], 
                                          capture_output=True, text=True, check=False)
                    if result.returncode == 0 and 'codex' in result.stdout.lower():
                        codex_panes.append(pane)
                except Exception:
                    pass
        
        return codex_panes

    def session_has_codex(self, session_name: str) -> bool:
        """Return True if any pane in the session appears to be running Codex."""
        current_panes = {pane['pane_id']: pane for pane in self.get_all_panes()}
        tracked_panes = self.load_tracked_panes()

        for pane_id, tracked_info in tracked_panes.items():
            pane = current_panes.get(pane_id)
            if pane and tracked_info.get('session_name') == session_name:
                return True

        for pane in self.find_codex_panes():
            if pane.get('session_name') == session_name:
                return True
        return False

    def set_session_marker(self, session_name: str, marker: str) -> bool:
        """Set the picker marker for a tmux session."""
        try:
            subprocess.run(
                ['tmux', 'set-option', '-t', session_name, '@ai_session_marker', marker],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _detect_ai_agent(self, pid: str) -> Optional[str]:
        """Return 'claude' or 'codex' if the pane's process tree contains one, else None."""
        try:
            for check_pid in [pid] + subprocess.run(
                ['pgrep', '-P', pid], capture_output=True, text=True
            ).stdout.strip().split('\n'):
                check_pid = check_pid.strip()
                if not check_pid:
                    continue
                result = subprocess.run(
                    ['ps', '-p', check_pid, '-o', 'command='],
                    capture_output=True, text=True, check=False, timeout=2,
                )
                cmd = result.stdout.lower()
                if 'claude' in cmd:
                    return 'claude'
                if 'codex' in cmd:
                    return 'codex'
        except Exception:
            pass
        return None

    def refresh_session_markers(self):
        """Refresh the 🤖 count marker for every tmux session."""
        tracked = self.load_tracked_panes()
        all_panes = self.get_all_panes()
        current_pane_ids = {pane['pane_id'] for pane in all_panes}
        tracker_updated = False

        # Auto-detect unregistered AI panes by process inspection
        for pane in all_panes:
            if pane['pane_id'] not in tracked:
                agent = self._detect_ai_agent(pane['pid'])
                if agent:
                    tracked[pane['pane_id']] = {
                        'agent': agent,
                        'session_name': pane['session_name'],
                    }
                    tracker_updated = True

        if tracker_updated:
            self.save_tracked_panes(tracked)

        session_counts: Dict[str, int] = {}
        for pane_id, info in tracked.items():
            if pane_id in current_pane_ids:
                s = info.get('session_name', '')
                if s:
                    session_counts[s] = session_counts.get(s, 0) + 1

        for session_name in self.get_all_sessions():
            count = session_counts.get(session_name, 0)
            marker = '🤖' * count + (' ' if count > 0 else '')
            self.set_session_marker(session_name, marker)
    
    def monitor_pane_activity(self, pane_id: str, callback_script: str):
        """Set up monitoring for pane activity"""
        # Use tmux hooks to monitor when the pane becomes active
        hook_command = f"run-shell '{callback_script} {pane_id}'"
        
        # Monitor when this pane is selected
        try:
            subprocess.run(['tmux', 'set-hook', '-t', pane_id, 'after-select-pane', hook_command], 
                          check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass
    
    def remove_pane_monitoring(self, pane_id: str):
        """Remove monitoring for a specific pane"""
        try:
            subprocess.run(['tmux', 'set-hook', '-t', pane_id, '-u', 'after-select-pane'], 
                          check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass
    
    def cleanup_dead_panes(self):
        """Clean up state files for panes that no longer exist"""
        current_panes = {pane['pane_id'] for pane in self.get_all_panes()}
        
        # Find and remove state files for dead panes
        for state_file in self.script_dir.glob('.pane_state_*.json'):
            try:
                pane_id = state_file.stem.replace('.pane_state_', '')
                pane_id = f"%{pane_id}"
                
                if pane_id not in current_panes:
                    state_file.unlink()
            except Exception:
                pass

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: tmux_integration.py [command] [args...]")
        sys.exit(1)
    
    tmux = TmuxIntegration()
    command = sys.argv[1]
    
    if command == 'list-panes':
        panes = tmux.get_all_panes()
        for pane in panes:
            print(f"{pane['pane_id']}: {pane['title']} (PID: {pane['pid']})")
    
    elif command == 'find-codex':
        codex_panes = tmux.find_codex_panes()
        for pane in codex_panes:
            print(f"{pane['pane_id']}: {pane['title']} (PID: {pane['pid']})")

    elif command == 'session-has-codex':
        if len(sys.argv) >= 3:
            session_name = sys.argv[2]
            print("1" if tmux.session_has_codex(session_name) else "0")

    elif command == 'refresh-session-markers':
        tmux.refresh_session_markers()
    
    elif command == 'get-title':
        if len(sys.argv) >= 3:
            pane_id = sys.argv[2]
            title = tmux.get_pane_title(pane_id)
            if title:
                print(title)
    
    elif command == 'set-title':
        if len(sys.argv) >= 4:
            pane_id = sys.argv[2]
            title = sys.argv[3]
            success = tmux.set_pane_title(pane_id, title)
            print("OK" if success else "FAILED")
    
    elif command == 'current-pane':
        pane_id = tmux.get_current_pane()
        if pane_id:
            print(pane_id)
    
    elif command == 'cleanup':
        tmux.cleanup_dead_panes()
        print("Cleanup completed")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()
