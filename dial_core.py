from pathlib import Path


class DialRouter:
    def __init__(self, minimum_interval=0.12):
        self.minimum_interval = minimum_interval
        self.last_action = float('-inf')
        self.presses = {}

    def key(self, device, code, value, *, ctrl, focused, now, modified=False):
        if code not in (113, 114, 115):
            return True, None
        identity = (device, code)
        if value == 0:
            return not self.presses.pop(identity, False), None
        if value == 2:
            return not self.presses.get(identity, False), None
        if value != 1:
            return True, None
        if identity in self.presses:
            return not self.presses[identity], None
        consumed = ctrl or (not modified and focused)
        self.presses[identity] = consumed
        if consumed:
            if now - self.last_action < self.minimum_interval:
                return False, None
            self.last_action = now
            if ctrl:
                return False, 'mute' if code == 113 else ('volume-up' if code == 115 else 'volume-down')
            if code == 113:
                return False, 'effort-panel'
            return False, 'decrease' if code == 115 else 'increase'
        return True, None

    def forget(self, device):
        self.presses = {key: value for key, value in self.presses.items() if key[0] != device}


def is_target_window(wm_class, executable):
    classes = {value.lower() for value in (wm_class or ())}
    return bool(classes & {'chatgpt', 'codex'}) and Path(executable.removesuffix(' (deleted)')).name.lower() in {'chatgpt', 'codex'}
