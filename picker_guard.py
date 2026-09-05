import ctypes
import ctypes.util
import csv
import io
import re
import time
import select
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelList:
    names: tuple
    x: int
    y: int


def model_lists(tsv):
    grouped = {}
    fields = None if tsv.startswith('level\t') else 'level page_num block_num par_num line_num word_num left top width height conf text'.split()
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t', fieldnames=fields):
        if row.get('level') != '5' or not row.get('text', '').strip():
            continue
        key = tuple(row[name] for name in ('block_num', 'par_num', 'line_num'))
        try:
            word = (int(row['left']), int(row['top']), row['text'])
        except (KeyError, ValueError):
            continue
        grouped.setdefault(key, []).append(word)
    lines = []
    for words in grouped.values():
        words.sort()
        for index, word in enumerate(words):
            if not re.match(r'GPT[-–—]?\d', word[2], re.I):
                continue
            text = ' '.join(item[2] for item in words[index:])
            match = re.match(r'(GPT[-–—]?\s*\d[\w.\-]*(?:\s+[\w.-]+)?)', text, re.I)
            if match:
                lines.append((word[0], word[1], match[1].lower()))
    lines.sort(key=lambda row: row[1])
    found = []
    for first in lines:
        cluster = [first]
        for row in lines:
            if 12 <= row[1] - cluster[-1][1] <= 55 and abs(row[0] - first[0]) <= 20:
                cluster.append(row)
        names = tuple(row[2] for row in cluster)
        if len(set(names)) >= 3:
            found.append(ModelList(names, first[0], first[1]))
    return found


def same_list(a, b):
    return abs(a.x - b.x) < 25 and abs(a.y - b.y) < 25 and len(set(a.names) & set(b.names)) >= 3


class PickerGuard:
    def __init__(self):
        from Xlib import display
        library = ctypes.util.find_library('tesseract')
        if not library:
            raise RuntimeError('Tesseract library unavailable')
        self.lib = ctypes.CDLL(library)
        self.lib.TessBaseAPICreate.restype = ctypes.c_void_p
        self.lib.TessBaseAPIInit3.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.TessBaseAPISetImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.lib.TessBaseAPIGetTsvText.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.TessBaseAPIGetTsvText.restype = ctypes.c_void_p
        self.lib.TessDeleteText.argtypes = [ctypes.c_void_p]
        self.lib.TessBaseAPIDelete.argtypes = [ctypes.c_void_p]
        self.api = self.lib.TessBaseAPICreate()
        if self.lib.TessBaseAPIInit3(self.api, None, b'eng') != 0:
            self.lib.TessBaseAPIDelete(self.api)
            raise RuntimeError('Tesseract English language data unavailable')
        self.display = display.Display()
        self.selected_list = None
        self.window_id = None
        self.watchers = []
        from evdev import InputDevice, list_devices
        for path in list_devices():
            try:
                device = InputDevice(path)
                if device.name.startswith("Codex Dial"):
                    device.close()
                else:
                    self.watchers.append(device)
            except OSError:
                pass

    def scan(self):
        from Xlib import X
        from PIL import Image
        root = self.display.screen().root
        prop = root.get_full_property(self.display.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
        if prop is None:
            return None, []
        window = self.display.create_resource_object('window', prop.value[0])
        geometry = window.get_geometry()
        if geometry.width < 500 or geometry.height < 300:
            return window.id, []
        raw = window.get_image(0, 0, geometry.width, geometry.height, X.ZPixmap, 0xffffffff)
        image = Image.frombytes('RGB', (geometry.width, geometry.height), raw.data, 'raw', 'BGRX')
        return window.id, self.recognize(image)

    def recognize(self, image):
        buffer = ctypes.create_string_buffer(image.tobytes())
        self.lib.TessBaseAPISetImage(self.api, buffer, image.width, image.height, 3, image.width * 3)
        pointer = self.lib.TessBaseAPIGetTsvText(self.api, 0)
        if not pointer:
            return []
        try:
            text = ctypes.string_at(pointer).decode(errors='replace')
            return model_lists(text)
        finally:
            self.lib.TessDeleteText(pointer)

    def open(self, trigger):
        before_id, before = self.scan()
        trigger()
        time.sleep(.18)
        after_id, after = self.scan()
        self.selected_list = next((item for item in after if before_id == after_id and not any(same_list(item, old) for old in before)), None)
        self.window_id = after_id if self.selected_list is not None else None
        return self.selected_list is not None

    def visible(self):
        if self.selected_list is None:
            return False
        for device in self.watchers:
            try:
                for event in device.read():
                    pass
            except OSError:
                pass
        window_id, lists = self.scan()
        if select.select(self.watchers, [], [], 0)[0]:
            return False
        return window_id == self.window_id and any(same_list(self.selected_list, item) for item in lists)

    def close(self):
        for device in self.watchers:
            device.close()
        self.lib.TessBaseAPIDelete(self.api)
        self.display.close()
