import json
from pathlib import Path
import tempfile
import unittest

from installation import BINDINGS, install_files, merge_bindings, remove_owned_bindings, uninstall_bindings


class InstallationTests(unittest.TestCase):
    def test_adds_bindings_without_removing_user_shortcuts(self):
        original = [{'command': 'newTask', 'key': 'Ctrl+Alt+N'}]
        self.assertEqual(merge_bindings(original), original + BINDINGS)
        self.assertEqual(original, [{'command': 'newTask', 'key': 'Ctrl+Alt+N'}])

    def test_reinstall_does_not_duplicate_bindings(self):
        self.assertEqual(merge_bindings(BINDINGS), BINDINGS)

    def test_conflicting_shortcut_is_rejected(self):
        with self.assertRaises(ValueError):
            merge_bindings([{'command': 'other', 'key': 'Shift+Control+F11'}])

    def test_uninstall_preserves_bindings_that_preexisted(self):
        before = [BINDINGS[0]]
        unrelated = {'command': 'newTask', 'key': 'Ctrl+Alt+N'}
        self.assertEqual(remove_owned_bindings(BINDINGS + [unrelated], before), before + [unrelated])

    def test_uninstall_restores_disabled_command_without_overwriting_new_choices(self):
        before = [{'command': BINDINGS[0]['command'], 'key': None}]
        self.assertNotIn(before[0], merge_bindings(before))
        self.assertEqual(remove_owned_bindings(BINDINGS, before), before)
        changed = [{'command': BINDINGS[0]['command'], 'key': 'Ctrl+F10'}]
        self.assertEqual(remove_owned_bindings(changed, before), changed)

    def test_install_and_uninstall_in_isolated_home(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            codex = home / 'custom-codex-home'
            codex.mkdir()
            path = codex / 'keybindings.json'
            before = [{'command': 'newTask', 'key': 'Ctrl+Alt+N'}]
            path.write_text(json.dumps(before))
            target = install_files(source, home, codex)
            self.assertEqual(json.loads(path.read_text()), before + BINDINGS)
            self.assertTrue((home / '.config/systemd/user/codex-dial.service').exists())
            self.assertTrue((target / 'dial_daemon.py').exists())
            install_files(source, home, codex)
            self.assertEqual(json.loads((target / 'keybindings.before.json').read_text()), before)
            uninstall_bindings(target)
            self.assertEqual(json.loads(path.read_text()), before)

    def test_uninstall_removes_keymap_created_by_install(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            target = install_files(source, home, home / '.codex')
            uninstall_bindings(target)
            self.assertFalse((home / '.codex/keybindings.json').exists())


if __name__ == '__main__':
    unittest.main()
