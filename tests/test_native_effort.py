from pathlib import Path
import unittest
import numpy as np
from PIL import Image, ImageDraw
from native_effort import find_control, panel_visible


class NativeEffortTests(unittest.TestCase):
    def setUp(self):
        assets = Path(__file__).resolve().parents[1] / 'assets'
        self.mic_image = Image.open(assets / 'microphone.png')
        self.arrow_image = Image.open(assets / 'effort-chevron.png')
        self.mic = np.asarray(self.mic_image, dtype='float32'); self.mic -= self.mic.mean()
        self.arrow = np.asarray(self.arrow_image, dtype='float32'); self.arrow -= self.arrow.mean()

    def add_control(self, image, x, y):
        draw = ImageDraw.Draw(image)
        draw.ellipse((x-14,y-14,x+13,y+13), fill='white')
        draw.rectangle((x-5,y-5,x+5,y+5), fill=(45,45,45))
        image.paste(self.mic_image,(x-43,y-10))
        image.paste(self.arrow_image,(x-74,y-6))

    def test_finds_verified_control_at_different_positions(self):
        for x in (400,700):
            image = Image.new('RGB',(900,500),(45,45,45))
            self.add_control(image,x,450)
            self.assertEqual(find_control(image,self.mic,self.arrow),(x,450))

    def test_blank_view_and_unrelated_circle_are_rejected(self):
        image = Image.new('RGB',(900,500),(45,45,45))
        self.assertIsNone(find_control(image,self.mic,self.arrow))
        ImageDraw.Draw(image).ellipse((686,436,713,463),fill='white')
        self.assertIsNone(find_control(image,self.mic,self.arrow))

    def test_ambiguous_multiple_composers_are_rejected(self):
        image = Image.new('RGB',(900,500),(45,45,45))
        self.add_control(image,400,450);self.add_control(image,750,450)
        self.assertIsNone(find_control(image,self.mic,self.arrow))

    def test_open_slider_thumb_is_recognized(self):
        image = Image.new('RGB',(900,500),(45,45,45))
        self.add_control(image,700,450)
        self.assertFalse(panel_visible(image,(700,450)))
        ImageDraw.Draw(image).ellipse((486,389,513,416),fill='white')
        self.assertTrue(panel_visible(image,(700,450)))
