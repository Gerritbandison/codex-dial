import json
import os
from pathlib import Path
import tempfile

BINDINGS = [
    {'command': 'composer.increaseReasoningEffort', 'key': 'Ctrl+Shift+F11'},
    {'command': 'composer.decreaseReasoningEffort', 'key': 'Ctrl+Shift+F12'},
]
FILES = ['dial_core.py', 'dial_daemon.py', 'installation.py', 'install.py', 'uninstall.py', 'README.md', 'requirements.txt']


def read_bindings(path):
    value = json.loads(path.read_text()) if path.exists() else []
    if not isinstance(value, list) or any(
        not isinstance(row, dict) or not isinstance(row.get('command'), str)
        or 'key' not in row or not (row['key'] is None or isinstance(row['key'], str))
        for row in value
    ):
        raise ValueError(f'Invalid shortcut file: {path}')
    return value


def normalize(key):
    return '+'.join(sorted(part.replace('control', 'ctrl').replace('cmdorctrl', 'ctrl') for part in key.lower().split('+')))


def merge_bindings(current):
    for wanted in BINDINGS:
        for row in current:
            if row['key'] and normalize(row['key']) == normalize(wanted['key']) and row['command'] != wanted['command']:
                raise ValueError(f"{wanted['key']} is already assigned to {row['command']}; choose another shortcut before installing.")
    commands = {row['command'] for row in BINDINGS}
    result = [dict(row) for row in current if not (row['command'] in commands and row['key'] is None)]
    for wanted in BINDINGS:
        if wanted not in result:
            result.append(dict(wanted))
    return result


def remove_owned_bindings(current, before):
    result = [row for row in current if row not in BINDINGS or row in before]
    commands = {row['command'] for row in BINDINGS}
    for row in before:
        if row['command'] in commands and row['key'] is None and not any(item['command'] == row['command'] for item in result):
            result.append(row)
    return result


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.codex-dial-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, indent=2) + '\n').encode())


def install_files(source, home, codex_home):
    source, home, codex_home = Path(source).resolve(), Path(home).resolve(), Path(codex_home).resolve()
    target = home / '.local/share/codex-dial'
    unit = home / '.config/systemd/user/codex-dial.service'
    keymap = codex_home / 'keybindings.json'
    for name in FILES + ['packaging/codex-dial.service']:
        if not (source / name).is_file():
            raise ValueError(f'Missing package file: {name}')
    current = read_bindings(keymap)
    merged = merge_bindings(current)
    state_file = target / 'install-state.json'
    if state_file.exists() and json.loads(state_file.read_text())['keymap'] != str(keymap):
        raise ValueError('Existing installation uses a different CODEX_HOME; uninstall it before changing homes.')
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = target / 'keybindings.before.json'
    if not backup.exists():
        write_json(backup, current)
        atomic_write(target / 'keybindings-existed.txt', str(keymap.exists()).encode())
    write_json(state_file, {'keymap': str(keymap), 'unit': str(unit)})
    for name in FILES:
        atomic_write(target / name, (source / name).read_bytes())
    atomic_write(unit, (source / 'packaging/codex-dial.service').read_bytes())
    write_json(keymap, merged)
    return target


def uninstall_bindings(target):
    target = Path(target)
    state_path = target / 'install-state.json'
    state = json.loads(state_path.read_text())
    keymap = Path(state['keymap'])
    if not keymap.exists():
        return
    before = read_bindings(target / 'keybindings.before.json')
    remaining = remove_owned_bindings(read_bindings(keymap), before)
    if not remaining and (target / 'keybindings-existed.txt').read_text() == 'False':
        keymap.unlink()
    else:
        write_json(keymap, remaining)
