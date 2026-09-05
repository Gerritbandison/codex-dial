#!/usr/bin/env python3
import argparse
import contextlib
import fcntl
import json
import logging
import os
from pathlib import Path
import select
import signal
import subprocess
import time

from evdev import InputDevice, UInput, ecodes as E, list_devices
from Xlib import X, display

from dial_core import DialRouter, is_target_window

LOG = logging.getLogger('codex-dial')
CTRL = {E.KEY_LEFTCTRL, E.KEY_RIGHTCTRL}
OTHER_MODIFIERS = {E.KEY_LEFTSHIFT, E.KEY_RIGHTSHIFT, E.KEY_LEFTALT, E.KEY_RIGHTALT, E.KEY_LEFTMETA, E.KEY_RIGHTMETA}
PREFIX = 'Codex Dial passthrough'


class Focus:
    def __init__(self):
        self.connection = None

    def active(self):
        try:
            if self.connection is None:
                self.connection = display.Display()
            d = self.connection
            root = d.screen().root
            value = root.get_full_property(d.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
            if value is None or not value.value[0]:
                return False
            window = d.create_resource_object('window', value.value[0])
            prop = window.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
            if prop is None:
                return False
            executable = os.readlink(f'/proc/{int(prop.value[0])}/exe')
            return is_target_window(window.get_wm_class(), executable)
        except Exception:
            if self.connection is not None:
                with contextlib.suppress(Exception):
                    self.connection.close()
            self.connection = None
            return False


class Keyboard:
    def __init__(self, device):
        self.device = device
        self.output = None
        self.held = set()
        self.forwarded = set()
        self.dropped = False
        self.grabbed = False
        try:
            self.output = UInput.from_device(device, name=f'{PREFIX} {Path(device.path).name}')
            # Let the desktop discover the replacement before claiming the source.
            time.sleep(0.2)
            if device.active_keys():
                raise BlockingIOError('Keys held; postponing grab until released')
            device.grab()
            self.grabbed = True
        except Exception:
            self.close()
            raise

    def forward(self, event):
        self.output.write_event(event)
        if event.type == E.EV_KEY:
            if event.value == 0:
                self.forwarded.discard(event.code)
            elif event.value == 1:
                self.forwarded.add(event.code)

    def resync(self, router):
        self.held = set(self.device.active_keys())
        wanted = self.held - {E.KEY_MUTE, E.KEY_VOLUMEUP, E.KEY_VOLUMEDOWN}
        for code in self.forwarded - wanted:
            self.output.write(E.EV_KEY, code, 0)
        for code in wanted - self.forwarded:
            self.output.write(E.EV_KEY, code, 1)
        self.output.syn()
        self.forwarded = wanted
        router.forget(self.device.path)
        self.dropped = False

    def close(self):
        if self.output is not None:
            for key in self.forwarded:
                with contextlib.suppress(OSError):
                    self.output.write(E.EV_KEY, key, 0)
            with contextlib.suppress(OSError):
                self.output.syn()
        if self.grabbed:
            with contextlib.suppress(OSError):
                self.device.ungrab()
        if self.output is not None:
            self.output.close()
        self.device.close()


class Hotkeys:
    def __init__(self, focus):
        self.focus = focus
        self.output = UInput({E.EV_KEY: [E.KEY_LEFTCTRL, E.KEY_LEFTSHIFT, E.KEY_F10, E.KEY_F11, E.KEY_F12, E.KEY_UP, E.KEY_DOWN, E.KEY_ENTER]}, name='Codex Dial commands')
        self.last_notice = 0
        self.notice = None
        self.audio = []
        self.guard = None
        self.on_picker_failure = lambda: None
        self.input_changed = lambda: False

    def send(self, action):
        self.audio = [child for child in self.audio if child.poll() is None]
        if action.startswith('volume-') or action == 'mute':
            try:
                self.audio.append(subprocess.Popen(
                    (['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle'] if action == 'mute' else
                     ['wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SINK@', '2%+' if action == 'volume-up' else '2%-']),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
                LOG.info('Requested %s', action)
            except OSError as error:
                LOG.error('Cannot change volume: %s', error)
            return
        if not self.focus.active():
            return
        if action.startswith('picker-'):
            try:
                if self.guard is None:
                    from picker_guard import PickerGuard
                    self.guard = PickerGuard()
                if action == 'picker-open':
                    if not self.guard.open(lambda: self.chord([E.KEY_LEFTCTRL, E.KEY_LEFTSHIFT, E.KEY_F10])):
                        raise RuntimeError('Model list not detected; use an idle composer with no draft text')
                elif action == 'picker-select':
                    if not self.guard.visible() or not self.focus.active() or self.input_changed():
                        raise RuntimeError('Model list closed, focus changed, or input arrived; selection canceled')
                    self.chord([E.KEY_ENTER])
                    self.guard.selected_list = None
                else:
                    self.chord([E.KEY_DOWN if action == 'picker-next' else E.KEY_UP])
                LOG.info('Requested %s', action)
            except Exception as error:
                self.on_picker_failure()
                LOG.warning('Picker action canceled: %s', error)
            return
        key = E.KEY_F12 if action == 'decrease' else E.KEY_F11
        try:
            self.output.write(E.EV_KEY, E.KEY_LEFTCTRL, 1)
            self.output.write(E.EV_KEY, E.KEY_LEFTSHIFT, 1)
            self.output.write(E.EV_KEY, key, 1)
            self.output.syn()
        finally:
            self.output.write(E.EV_KEY, key, 0)
            self.output.write(E.EV_KEY, E.KEY_LEFTSHIFT, 0)
            self.output.write(E.EV_KEY, E.KEY_LEFTCTRL, 0)
            self.output.syn()
        LOG.info('Requested %s reasoning effort', action)
        if time.monotonic() - self.last_notice >= 0.5:
            if self.notice is not None:
                self.notice.poll()
            if self.notice is None or self.notice.returncode is not None:
                direction = 'Lower effort · faster replies' if action == 'decrease' else 'Higher effort · deeper reasoning'
                try:
                    self.notice = subprocess.Popen(
                        ['notify-send', '-a', 'Codex Dial', '-t', '1500', '-h', 'string:x-canonical-private-synchronous:codex-dial',
                         direction, 'Requested for the next message. Check the model control for the selected level.'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.last_notice = time.monotonic()
                except OSError:
                    pass

    def chord(self, keys):
        try:
            for key in keys:
                self.output.write(E.EV_KEY, key, 1)
            self.output.syn()
        finally:
            for key in reversed(keys):
                self.output.write(E.EV_KEY, key, 0)
            self.output.syn()

    def close(self):
        if self.guard is not None:
            self.guard.close()
        self.output.close()
        for child in self.audio:
            with contextlib.suppress(subprocess.TimeoutExpired):
                child.wait(timeout=2)
        if self.notice is not None:
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.notice.wait(timeout=2)


def candidates(vendor, product, phys_suffix):
    for path in list_devices():
        device = None
        try:
            device = InputDevice(path)
            if device.name.startswith('Codex Dial') or device.info.vendor != vendor or device.info.product != product:
                device.close()
                continue
            if phys_suffix and not device.phys.endswith(phys_suffix):
                device.close()
                continue
            keys = device.capabilities().get(E.EV_KEY, [])
            if E.KEY_VOLUMEUP in keys and E.KEY_VOLUMEDOWN in keys:
                yield device
            else:
                device.close()
        except OSError:
            if device is not None:
                device.close()


def run(args):
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (runtime / 'codex-dial.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Codex Dial is already running')
        keyboards = {}
        router = DialRouter()
        focus = Focus()
        hotkeys = Hotkeys(focus)
        hotkeys.on_picker_failure = router.cancel_picker
        hotkeys.input_changed = lambda: bool(select.select([kbd.device.fd for kbd in keyboards.values()], [], [], 0)[0])
        pending_clicks = {}
        stopping = False
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        next_scan = 0
        try:
            while not stopping:
                if router.picker_active:
                    router.context(focused=focus.active(), now=time.monotonic())
                if time.monotonic() >= next_scan:
                    for device in candidates(args.vendor, args.product, args.phys_suffix):
                        if device.path in keyboards:
                            device.close()
                            continue
                        try:
                            keyboards[device.path] = Keyboard(device)
                            LOG.info('Connected %s (%s)', device.name, device.path)
                        except OSError as error:
                            LOG.warning('Device unavailable: %s', error)
                    next_scan = time.monotonic() + 3
                sources = {kbd.device.fd: (kbd, False) for kbd in keyboards.values()}
                sources.update({kbd.output.fd: (kbd, True) for kbd in keyboards.values()})
                ready, _, _ = select.select(list(sources), [], [], 0.25)
                for fd in ready:
                    kbd, feedback = sources[fd]
                    try:
                        if feedback:
                            for event in kbd.output.read():
                                if event.type in (E.EV_LED, E.EV_SYN):
                                    kbd.device.write_event(event)
                            continue
                        for event in kbd.device.read():
                            if event.type == E.EV_SYN and event.code == E.SYN_DROPPED:
                                kbd.dropped = True
                                continue
                            if kbd.dropped:
                                if event.type == E.EV_SYN and event.code == E.SYN_REPORT:
                                    kbd.resync(router)
                                continue
                            forward, action = True, None
                            if event.type == E.EV_KEY:
                                if event.value == 0:
                                    kbd.held.discard(event.code)
                                elif event.value == 1:
                                    kbd.held.add(event.code)
                                held = set().union(*(item.held for item in keyboards.values()))
                                ctrl = bool(held & CTRL)
                                forward, action = router.key(kbd.device.path, event.code, event.value,
                                    ctrl=ctrl, modified=bool(held & OTHER_MODIFIERS),
                                    focused=(router.picker_active or event.code in (E.KEY_MUTE, E.KEY_VOLUMEUP, E.KEY_VOLUMEDOWN)) and focus.active(), now=time.monotonic())
                            if event.type == E.EV_KEY and event.code == E.KEY_MUTE:
                                if event.value == 1 and action:
                                    pending_clicks[kbd.device.path] = action
                                    action = None
                                elif event.value == 0:
                                    action = pending_clicks.pop(kbd.device.path, None)
                            if forward:
                                kbd.forward(event)
                            if action:
                                kbd.output.syn()
                                hotkeys.send(action)
                    except OSError as error:
                        LOG.warning('Device disconnected: %s', error)
                        router.forget(kbd.device.path)
                        keyboards.pop(kbd.device.path, None)
                        kbd.close()
        finally:
            for kbd in keyboards.values():
                kbd.close()
            hotkeys.close()
            LOG.info('Stopped; physical keyboard access restored')


def main():
    parser = argparse.ArgumentParser(description='Corsair volume dial changes ChatGPT/Codex reasoning effort; hold Ctrl for volume.')
    parser.add_argument('--vendor', type=lambda value: int(value, 0), default=0x1b1c)
    parser.add_argument('--product', type=lambda value: int(value, 0), default=0x2b00)
    parser.add_argument('--phys-suffix', default='/input3', help='Calibrated receiver interface; empty matches all keyboard interfaces')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run(args)


if __name__ == '__main__':
    main()
