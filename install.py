#!/usr/bin/env python3
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

from installation import install_files, merge_bindings, read_bindings


def preflight():
    if os.geteuid() == 0:
        raise ValueError('Run this installer as your desktop user, without sudo.')
    if sys.platform != 'linux':
        raise ValueError('This integration requires Linux.')
    for module in ['evdev', 'Xlib']:
        if importlib.util.find_spec(module) is None:
            raise ValueError(f'Missing Python module {module}. Install the Fedora dependencies listed in README.md.')
    for program in ['wpctl', 'systemctl']:
        if shutil.which(program) is None:
            raise ValueError(f'Missing executable: {program}')
    if not os.environ.get('DISPLAY'):
        raise ValueError('Run from your graphical desktop session; DISPLAY is missing.')
    if not os.access('/dev/uinput', os.R_OK | os.W_OK):
        raise ValueError('No /dev/uinput access. Follow the scoped input-permission setup in README.md.')
    from dial_daemon import candidates
    devices = list(candidates(0x1b1c, 0x2b00, '/input3'))
    try:
        if not devices:
            raise ValueError('No readable supported Corsair receiver interface found. Check pairing and input permissions.')
        for device in devices:
            if not os.access(device.path, os.R_OK | os.W_OK):
                raise ValueError(f'No read/write access to {device.path}; see README.md.')
    finally:
        for device in devices:
            device.close()
    subprocess.run(['systemctl', '--user', 'show-environment'], stdout=subprocess.DEVNULL, check=True, timeout=10)


def main():
    parser = argparse.ArgumentParser(description='Install the tested Corsair ChatGPT/Codex dial mapping for your desktop user.')
    parser.add_argument('--check', action='store_true', help='Check prerequisites without changing files or starting the service')
    parser.add_argument('--no-start', action='store_true', help='Install files without enabling or starting the service')
    args = parser.parse_args()
    try:
        preflight()
        home = Path.home()
        codex_home = Path(os.environ.get('CODEX_HOME', str(home / '.codex'))).expanduser().resolve()
        merge_bindings(read_bindings(codex_home / 'keybindings.json'))
        if args.check:
            print('Prerequisites passed. No files changed and no input devices grabbed.')
            return 0
        active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'codex-dial.service']).returncode == 0
        if active:
            subprocess.run(['systemctl', '--user', 'stop', 'codex-dial.service'], check=True, timeout=15)
        target = install_files(Path(__file__).resolve().parent, home, codex_home)
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, timeout=15)
        variables = [name for name in ['DISPLAY', 'XAUTHORITY'] if name in os.environ]
        if variables:
            subprocess.run(['systemctl', '--user', 'import-environment', *variables], check=True, timeout=10)
        if not args.no_start:
            subprocess.run(['systemctl', '--user', 'enable', '--now', 'codex-dial.service'], check=True, timeout=15)
        print(f'Installed to {target}')
        print('Refresh the app shortcuts using the README steps, or restart the app after active work finishes.')
        print('The native command shortcuts must be loaded before plain dial turns can change reasoning.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Installation stopped: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
