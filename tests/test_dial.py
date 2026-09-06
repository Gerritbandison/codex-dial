import unittest

from dial_core import DialRouter, is_target_window


class DialTests(unittest.TestCase):
    def test_click_opens_effort_panel_only_in_target_app(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd',113,1,ctrl=False,focused=True,now=1),(False,'effort-panel'))
        self.assertEqual(r.key('kbd',113,0,ctrl=False,focused=False,now=2),(False,None))
        self.assertEqual(r.key('kbd',113,1,ctrl=False,focused=False,now=3),(True,None))

    def test_ctrl_click_mutes(self):
        self.assertEqual(DialRouter().key('kbd',113,1,ctrl=True,focused=True,now=1),(False,'mute'))

    def test_ctrl_volume_uses_audio_action_and_consumes_release(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 115, 1, ctrl=True, focused=True, now=1), (False, 'volume-up'))
        self.assertEqual(r.key('kbd', 115, 0, ctrl=False, focused=True, now=2), (False, None))

    def test_ctrl_volume_down(self):
        self.assertEqual(DialRouter().key('kbd', 114, 1, ctrl=True, focused=False, now=1), (False, 'volume-down'))

    def test_other_modifiers_do_not_change_effort(self):
        self.assertEqual(DialRouter().key('kbd', 114, 1, ctrl=False, modified=True, focused=True, now=1), (True, None))

    def test_plain_clockwise_requests_higher_effort(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 115, 1, ctrl=False, focused=True, now=1), (False, 'increase'))

    def test_plain_counterclockwise_requests_lower_effort(self):
        r = DialRouter()
        self.assertEqual(r.key('kbd', 114, 1, ctrl=False, focused=True, now=1), (False, 'decrease'))

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
        self.assertEqual(r.key('kbd', 115, 1, ctrl=False, focused=True, now=1.3), (False, 'increase'))

    def test_non_dial_keys_always_pass_through(self):
        self.assertEqual(DialRouter().key('kbd', 30, 1, ctrl=False, focused=True, now=1), (True, None))

    def test_window_gate_requires_class_and_app_executable(self):
        self.assertTrue(is_target_window(('chatgpt (/home/user/.config/Codex)', 'Chatgpt'), '/usr/lib/chatgpt/ChatGPT'))
        self.assertFalse(is_target_window(('firefox', 'Firefox'), '/usr/lib/firefox/firefox'))
        self.assertFalse(is_target_window(('Chatgpt', 'Chatgpt'), '/usr/bin/other-app'))
        self.assertFalse(is_target_window(None, ''))


if __name__ == '__main__':
    unittest.main()
