from pathlib import Path


class DialRouter:
    def __init__(self, minimum_interval=0.12):
        self.minimum_interval = minimum_interval
        self.last_action = float('-inf')
        self.presses = {}
        self.picker_active = False
        self.picker_last_used = 0

    def key(self, device, code, value, *, ctrl, focused, now, modified=False):
        self.context(focused=focused, now=now)
        if code not in (113, 114, 115):
            if value == 1 and code not in (29, 97, 42, 54, 56, 100, 125, 126):
                self.cancel_picker()
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
                if code == 113:
                    return False, 'mute'
                return False, 'volume-up' if code == 115 else 'volume-down'
            self.picker_last_used = now
            if code == 113:
                action = 'picker-select' if self.picker_active else 'picker-open'
                self.picker_active = not self.picker_active
                return False, action
            if self.picker_active:
                return False, 'picker-next' if code == 115 else 'picker-previous'
            return False, 'decrease' if code == 115 else 'increase'
        return True, None

    def cancel_picker(self):
        self.picker_active = False

    def context(self, *, focused, now):
        if not focused or now - self.picker_last_used > 20:
            self.cancel_picker()

    def forget(self, device):
        self.cancel_picker()
        self.presses = {key: value for key, value in self.presses.items() if key[0] != device}


def is_target_window(wm_class, executable):
    classes = {value.lower() for value in (wm_class or ())}
    return bool(classes & {'chatgpt', 'codex'}) and Path(executable.removesuffix(' (deleted)')).name.lower() in {'chatgpt', 'codex'}
