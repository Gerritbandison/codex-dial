# Codex Dial

Use a Corsair K70 CORE TKL rotary dial to change reasoning effort in the ChatGPT/Codex desktop app on Linux. Hold **Ctrl** to adjust volume instead.

Built and physically verified on Nobara KDE with a Corsair SLIPSTREAM receiver, using the app's native keyboard-command configuration. No app binary patches, firmware modifications, browser extensions, or API keys are required.

## Controls

Leave the keyboard dial in its normal **volume mode**. Use Fn+F12 to cycle back to volume mode if needed.

| Gesture | ChatGPT/Codex focused | Other applications |
| --- | --- | --- |
| Clockwise | Higher reasoning effort; favor deeper reasoning | Normal volume up |
| Counterclockwise | Lower reasoning effort; favor faster replies | Normal volume down |
| Ctrl + clockwise | Volume up 2% | Volume up 2% |
| Ctrl + counterclockwise | Volume down 2% | Volume down 2% |
| Dial press | Open the native effort slider | Normal mute/unmute |
| Ctrl + press | Mute/unmute | Mute/unmute |

The selected model stays the same. Reasoning changes apply to the composer's setting for subsequent messages, not a response already generating. Available levels are determined by the selected model. This does not toggle Fast mode or change service tiers. Ctrl-volume uses the default audio sink and caps volume at 100%.

## Compatibility

- **Tested hardware:** Corsair receiver USB ID `1b1c:2b00`, keyboard interface `/input3`.
- **Tested desktop:** Nobara KDE, with the ChatGPT app running through XWayland.
- **Tested app behavior:** native Codex/Work reasoning commands, including Astra High → Medium → High; physical dial and Ctrl-volume confirmed working.
- **Regular ChatGPT chats:** Instant did not respond to effort shortcuts; other regular ChatGPT reasoning modes are not yet verified. Do not assume all ChatGPT surfaces support these commands.
- **Not supported by the current focus adapter:** native Wayland app windows, browsers displaying chatgpt.com, Windows, or macOS. Unknown windows retain normal volume behavior.
- Other Corsair USB IDs, wired/Bluetooth connections, and dial modes need separate calibration.

Requires Python 3.10+, systemd user services, evdev/uinput access, WirePlumber (`wpctl`), and X11/XWayland.

## Install on Fedora / Nobara

```bash
sudo dnf install git python3 python3-evdev python3-xlib python3-numpy python3-pillow wireplumber
git clone https://github.com/Gerritbandison/codex-dial.git
cd codex-dial
python3 install.py --check
python3 install.py
```

Run the installer as your normal desktop user, **not with sudo**. The installer checks prerequisites, preserves existing shortcuts, saves the original keymap, installs a user service, and enables startup with your graphical session. Conflicting shortcut assignments stop installation rather than silently replacing another action. `CODEX_HOME` is honored if set.

Use `python3 install.py --no-start` to install files without enabling or starting the listener. On an existing active installation, this stops the old listener and leaves it stopped. `requirements.txt` records the tested Python dependency versions; the service uses `/usr/bin/python3`, so the Fedora packages are the recommended installation path.

### If the permission check fails

The listener must read the Corsair input interface and create a virtual keyboard through `/dev/uinput`. For a local desktop session, the supplied rules scope physical-device access to this receiver, instead of adding your account to the broad `input` group:

```bash
sudo modprobe uinput
sudo install -m 644 packaging/70-codex-dial.rules /etc/udev/rules.d/70-codex-dial.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input
sudo udevadm trigger --subsystem-match=misc
python3 install.py --check
```

If access still fails, reconnect the receiver or log out and back in. These permissions allow software running as your desktop user to read the matched keyboard and inject input; install only code you trust. Do not run two exclusive remappers on the same keyboard interface.

## Load the app shortcuts

The installer merges these entries into `$CODEX_HOME/keybindings.json` (default `~/.codex/keybindings.json`):

| Native app command | Shortcut |
| --- | --- |
| Increase reasoning effort | Ctrl+Shift+F11 |
| Decrease reasoning effort | Ctrl+Shift+F12 |

The app can cache externally edited shortcuts. After installation:

1. Open **Settings → Keyboard shortcuts** and search for **reasoning**.
2. Confirm the two bindings above. If they still show Unassigned, use the edit control to assign the displayed combinations. This refreshed both bindings in the tested app build.
3. Alternatively, fully quit and reopen the app after active work finishes.
4. First test Ctrl+Shift+F11/F12 directly on a reasoning-capable Codex/Work task, then test the dial.

The listener does not automatically restart the app. If native effort commands are absent in your app build, this integration cannot provide the model control without another adapter. Example entries are in [packaging/keybindings.example.json](packaging/keybindings.example.json); do not replace your entire keymap with the example.

## Manage and uninstall

```bash
systemctl --user status codex-dial
systemctl --user stop codex-dial
systemctl --user start codex-dial
journalctl --user -u codex-dial -n 30 --no-pager
```

Disable startup and restore ordinary dial behavior:

```bash
systemctl --user disable --now codex-dial
```

Remove the service and only the keyboard shortcuts this installer added:

```bash
python3 ~/.local/share/codex-dial/uninstall.py
```

Uninstall preserves unrelated shortcuts, later edits, package files, and backups. Refresh the app's shortcut settings or restart it to clear cached bindings. The installer does not create the optional system-wide udev rules, so uninstall leaves them alone; remove `/etc/udev/rules.d/70-codex-dial.rules` separately if you added it solely for this integration.

## Different receiver configuration

Discover the keyboard's USB ID and input interfaces using `lsusb` and `/proc/bus/input/devices`. The listener exposes explicit selectors:

```bash
python3 dial_daemon.py --help
python3 dial_daemon.py --vendor 0x1b1c --product 0x2b00 --phys-suffix /input3
```

Stop the installed service before running a foreground copy. The default installer preflight deliberately requires the tested receiver. For another device, calibrate its volume events and adjust both installer preflight and the service's `ExecStart` arguments. Event numbers such as `event20` are not stable identifiers and are never hardcoded.

## Implementation

The listener exclusively reads the calibrated keyboard interface and forwards input through a virtual keyboard. Ordinary keys and LED feedback are forwarded; typed characters are never logged. Only connection status and requested dial actions are logged. No network connections are made by the listener.

Focus matching uses the X11/XWayland window class and owning executable. Dial presses/releases are paired even when focus or modifiers change mid-gesture. Repeated events are suppressed and actions are limited to one per 120 ms. The listener waits for held keys to be released before attaching, handles input resynchronization and reconnects, and releases forwarded keys when stopping.

The small native effort slider opens when the dial is pressed or rotated in a supported ChatGPT/Codex window. Rotation keeps changing reasoning effort while the slider stays visible. This targets the actual microphone/chevron/send-control icon group in the bottom composer, not guessed window coordinates. It sends a click to the matched effort button without moving the physical pointer. It never sends Enter, navigates a model list, or uses OCR. Already-open sliders are detected so repeated turns do not toggle the panel closed.

The icon match was verified at the current default app scale and dark appearance, including a split-pane screenshot. A different theme, zoom, icon layout, hidden composer, or multiple matching composers can cause it to do nothing; effort shortcuts still work. This is a visual adapter, not an official app API. Matching runs locally in memory, normally only every half-second during dial use. No screenshots or recognized text are written, logged, or uploaded, and no desktop notifications are generated.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q dial_core.py dial_daemon.py native_effort.py installation.py install.py uninstall.py
```

The automated suite covers gesture routing, modifiers, focus changes, held-key releases, throttling, shortcut conflicts, repeat installation, isolated file installation, and shortcut removal. Tests do not capture the real keyboard or modify the current user's app settings. CI runs the suite on Python 3.10, 3.12, and 3.14.

Hardware validation additionally exercised real Linux virtual-device forwarding, visible app effort changes, and audio changes with restoration. When reporting a problem, include your USB ID, connection type, desktop session, app build, and service logs—not raw keyboard-event recordings.

## License

[MIT](LICENSE) © 2026 Gerritbandison.

## Removed model-selection experiment

The earlier click → browse models → Enter workflow remains removed. The new press action only opens the small native **effort slider** shown beside the composer. It does not select a model or submit a message. Upgrading removes this package’s old Ctrl+Shift+F10 binding while preserving unrelated shortcuts.
