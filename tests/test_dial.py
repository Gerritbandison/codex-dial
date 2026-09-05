import unittest

from dial_core import DialRouter, is_target_window


class DialTests(unittest.TestCase):
    def press(self, router, code, now, **kwargs):
        flags = {'ctrl': False, 'focused': True, **kwargs}
        result = router.key('kbd', code, 1, now=now, **flags)
        router.key('kbd', code, 0, now=now + .01, **flags)
        return result

    def test_click_turn_click_browses_then_selects(self):
        r = DialRouter()
        self.assertEqual(self.press(r, 113, 1), (False, 'picker-open'))
        self.assertEqual(self.press(r, 115, 2), (False, 'picker-next'))
        self.assertEqual(self.press(r, 114, 3), (False, 'picker-previous'))
        self.assertEqual(self.press(r, 113, 4), (False, 'picker-select'))
        self.assertEqual(self.press(r, 115, 5), (False, 'decrease'))

    def test_ctrl_click_toggles_mute(self):
        self.assertEqual(self.press(DialRouter(), 113, 1, ctrl=True), (False, 'mute'))

    def test_click_outside_app_is_normal_mute(self):
        self.assertEqual(self.press(DialRouter(), 113, 1, focused=False), (True, None))

    def test_escape_and_typing_cancel_picker_mode(self):
        for key in [1, 30, 15]:
            with self.subTest(key=key):
                r = DialRouter()
                self.press(r, 113, 1)
                self.assertEqual(self.press(r, key, 2), (True, None))
                self.assertEqual(self.press(r, 113, 3), (False, 'picker-open'))

    def test_focus_loss_and_mouse_interaction_cancel_picker(self):
        r = DialRouter()
        self.press(r, 113, 1)
        r.cancel_picker()
        self.assertEqual(self.press(r, 113, 2), (False, 'picker-open'))
        r.context(focused=False, now=3)
        self.assertEqual(self.press(r, 113, 4), (False, 'picker-open'))

    def test_picker_mode_expires_and_reopens_instead_of_selecting(self):
        r = DialRouter()
        self.press(r, 113, 1)
        self.assertEqual(self.press(r, 113, 40), (False, 'picker-open'))

    def test_ctrl_volume_preserves_picker_mode(self):
        r = DialRouter()
        self.press(r, 113, 1)
        self.assertEqual(self.press(r, 115, 2, ctrl=True), (False, 'volume-up'))
        self.assertEqual(self.press(r, 113, 3), (False, 'picker-select'))

    def test_ctrl_volume_uses_audio_action_and_consumes_release(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 115, 1, ctrl=True, focused=True, now=1), (False, 'volume-up'))
        self.assertEqual(r.key('kbd', 115, 0, ctrl=False, focused=True, now=2), (False, None))

    def test_ctrl_volume_down(self):
        self.assertEqual(DialRouter().key('kbd', 114, 1, ctrl=True, focused=False, now=1), (False, 'volume-down'))

    def test_other_modifiers_do_not_change_effort(self):
        self.assertEqual(DialRouter().key('kbd', 114, 1, ctrl=False, modified=True, focused=True, now=1), (True, None))

    def test_plain_clockwise_requests_lower_effort(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 115, 1, ctrl=False, focused=True, now=1), (False, 'decrease'))

    def test_plain_counterclockwise_requests_higher_effort(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 114, 1, ctrl=False, focused=True, now=1), (False, 'increase'))

    def test_other_apps_keep_ctrl_volume_unchanged(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 114, 1, ctrl=False, focused=False, now=1), (True, None))

    def test_consumed_release_stays_consumed_after_focus_changes(self):
        r = DialRouter()
        r.key('kbd', 115, 1, ctrl=False, focused=True, now=1)
        self.assertEqual(r.key('kbd', 115, 0, ctrl=True, focused=False, now=2), (False, None))

    def test_repeats_do_not_advance_multiple_steps(self):
        r = DialRouter()
        r.key('kbd', 115, 1, ctrl=False, focused=True, now=1)
        self.assertEqual(r.key('kbd', 115, 2, ctrl=False, focused=True, now=2), (False, None))

    def test_rapid_ticks_are_consumed_without_excess_commands(self):
        r = DialRouter()
        r.key('kbd', 115, 1, ctrl=False, focused=True, now=1)
        r.key('kbd', 115, 0, ctrl=False, focused=True, now=1.01)
        self.assertEqual(r.key('kbd', 115, 1, ctrl=False, focused=True, now=1.02), (False, None))
        r.key('kbd', 115, 0, ctrl=False, focused=True, now=1.03)
        self.assertEqual(r.key('kbd', 115, 1, ctrl=False, focused=True, now=1.3), (False, 'decrease'))

    def test_non_dial_keys_always_pass_through(self):
        self.assertEqual(DialRouter().key('kbd', 30, 1, ctrl=False, focused=True, now=1), (True, None))

    def test_window_gate_requires_class_and_app_executable(self):
        self.assertTrue(is_target_window(('chatgpt (/home/user/.config/Codex)', 'Chatgpt'), '/usr/lib/chatgpt/ChatGPT'))
        self.assertFalse(is_target_window(('firefox', 'Firefox'), '/usr/lib/firefox/firefox'))
        self.assertFalse(is_target_window(('Chatgpt', 'Chatgpt'), '/usr/bin/other-app'))
        self.assertFalse(is_target_window(None, ''))


if __name__ == '__main__':
    unittest.main()
