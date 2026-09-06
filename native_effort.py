from pathlib import Path
import time


def similarity(patch, template):
    import numpy as np
    if patch.shape != template.shape:
        return 0.0
    a = patch.astype('float32').ravel()
    b = template.ravel()
    a = a - a.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def find_control(image, microphone, chevron):
    import numpy as np
    gray = np.asarray(image.convert('L'))
    height, width = gray.shape
    matches = []
    for bright in (True, False):
        candidates = set()
        for y in range(max(height // 3, height - 100), height):
            row = gray[y] > 235 if bright else gray[y] < 80
            changes = np.diff(np.pad(row.astype('int8'), (1, 1)))
            starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
            for left, right in zip(starts, ends):
                if 16 <= right - left <= 40:
                    x = int((left + right - 1) / 2)
                    for cy in range(max(10, y - 12), min(height - 11, y + 13)):
                        candidates.add((x, cy)); candidates.add((x + 1, cy))
            if len(candidates) > 15000:
                candidates.clear()
                break
        sign = 1 if bright else -1
        for x, y in candidates:
            if x < 88:
                continue
            circle = gray[y - 11:y + 12, x - 11:x + 12]
            mask = circle > 235 if bright else circle < 80
            if circle.shape != (23, 23) or not .35 <= float(mask.mean()) <= .95:
                continue
            arrow = sign * similarity(gray[y - 6:y + 6, x - 74:x - 61], chevron)
            if arrow < .74:
                continue
            mic = max(sign * similarity(gray[y - 10 + dy:y + 10 + dy, x - 43:x - 28], microphone) for dy in (-1, 0, 1))
            if mic < .82:
                continue
            matches.append((mic + arrow, x, y))
    if not matches:
        return None
    matches.sort(reverse=True)
    _, x, y = matches[0]
    if any(abs(a - x) > 20 or abs(b - y) > 20 for _, a, b in matches):
        return None
    return x, y


def find_scaled_control(image, microphone, chevron, preferred=1.0):
    from PIL import Image
    scales = dict.fromkeys([preferred, 1.0, 1.2, 1.25, 1.5, 1.1, .9, 2.0])
    for scale in scales:
        normalized = image if scale == 1 else image.resize((round(image.width / scale), round(image.height / scale)), Image.Resampling.LANCZOS)
        control = find_control(normalized, microphone, chevron)
        if control is not None:
            return round(control[0] * scale), round(control[1] * scale), scale
    return None


def panel_visible(image, control):
    import numpy as np
    from PIL import Image
    x, y = control[:2]
    scale = control[2] if len(control) > 2 else 1.0
    if scale != 1:
        image = image.resize((round(image.width / scale), round(image.height / scale)), Image.Resampling.LANCZOS)
        x, y = round(x / scale), round(y / scale)
    gray = np.asarray(image.convert('L'))
    region = gray[max(0, y - 57):max(0, y - 37), max(0, x - 255):max(0, x - 25)] > 252
    if region.size == 0:
        return False
    matching_rows = 0
    for row in region:
        changes = np.diff(np.pad(row.astype('int8'), (1, 1)))
        starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
        if any(18 <= right - left <= 34 for left, right in zip(starts, ends)):
            matching_rows += 1
    return matching_rows >= 6


class NativeEffort:
    def __init__(self, focus):
        import numpy as np
        from PIL import Image
        assets = Path(__file__).resolve().parent / 'assets'
        self.microphone = np.asarray(Image.open(assets / 'microphone.png').convert('L'), dtype='float32')
        self.chevron = np.asarray(Image.open(assets / 'effort-chevron.png').convert('L'), dtype='float32')
        self.microphone -= self.microphone.mean()
        self.chevron -= self.chevron.mean()
        self.focus = focus
        self.last_attempt = float('-inf')
        self.scale = 1.0

    def show(self, toggle=False):
        from Xlib import X, protocol
        from PIL import Image
        if time.monotonic() - self.last_attempt < .5 or not self.focus.active():
            return False
        self.last_attempt = time.monotonic()
        display = self.focus.connection
        root = display.screen().root
        if root.query_pointer().mask & (X.Button1Mask | X.Button2Mask | X.Button3Mask):
            return False
        prop = root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
        window = display.create_resource_object('window', prop.value[0])
        geometry = window.get_geometry()
        raw = window.get_image(0, 0, geometry.width, geometry.height, X.ZPixmap, 0xffffffff)
        image = Image.frombytes('RGB', (geometry.width, geometry.height), raw.data, 'raw', 'BGRX')
        control = find_scaled_control(image, self.microphone, self.chevron, self.scale)
        if control is None:
            return False
        self.scale = control[2]
        if not toggle and panel_visible(image, control):
            return True
        if not self.focus.active() or root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType).value[0] != window.id:
            return False
        x, y = round(control[0] - 88 * self.scale), control[1]
        origin = root.translate_coords(window, 0, 0)
        for kind in (protocol.event.ButtonPress, protocol.event.ButtonRelease):
            event = kind(time=X.CurrentTime, root=root, window=window, child=X.NONE,
                         root_x=origin.x + x, root_y=origin.y + y, event_x=x, event_y=y,
                         state=0, same_screen=1, detail=1)
            window.send_event(event, event_mask=X.ButtonPressMask if kind is protocol.event.ButtonPress else X.ButtonReleaseMask, propagate=False)
        display.flush()
        return True
