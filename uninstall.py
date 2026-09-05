#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys

from installation import uninstall_bindings


def main():
    target = Path.home() / '.local/share/codex-dial'
    try:
        state_path = target / 'install-state.json'
        if not state_path.exists():
            raise ValueError('No installation metadata found. Use the removal helper shipped with your installed version.')
        state = json.loads(state_path.read_text())
        subprocess.run(['systemctl', '--user', 'disable', '--now', 'codex-dial.service'], check=True, timeout=15)
        uninstall_bindings(target)
        Path(state['unit']).unlink(missing_ok=True)
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, timeout=15)
        print('Listener disabled and its added shortcuts removed. Unrelated shortcuts and local backups were preserved.')
        print('Refresh app shortcuts or restart the app to clear cached bindings.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Removal stopped: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
