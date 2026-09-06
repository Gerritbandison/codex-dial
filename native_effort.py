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
    candidates = set()
    for y in range(max(height // 3, height - 140), height):
        row = gray[y] > 235
        changes = np.diff(np.pad(row.astype('int8'), (1, 1)))
        starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
        for left, right in zip(starts, ends):
            if 16 <= right - left <= 40:
                x = int((left + right - 1) / 2)
                for cy in range(max(10, y - 12), min(height - 11, y + 13)):
                    candidates.add((x, cy))
                    candidates.add((x + 1, cy))
        if len(candidates) > 15000:
            return None
    matches = []
    for x, y in candidates:
        if x < 88:
            continue
        mic = similarity(gray[y - 10:y + 10, x - 43:x - 28], microphone)
        if mic < .86:
            continue
        arrow = similarity(gray[y - 6:y + 6, x - 74:x - 61], chevron)
        if arrow < .78:
            continue
        circle = gray[y - 11:y + 12, x - 11:x + 12]
        if circle.shape != (23, 23) or float((circle > 235).mean()) < .35:
            continue
        matches.append((mic + arrow, x, y))
    if not matches:
        return None
    matches.sort(reverse=True)
    _, x, y = matches[0]
    if any(abs(a - x) > 20 or abs(b - y) > 20 for _, a, b in matches):
        return None
    return x, y


def panel_visible(image, control):
    import numpy as np
    x, y = control
    gray = np.asarray(image.convert('L'))
    top, bottom = max(0, y - 65), max(0, y - 29)
    region = gray[top:bottom, max(0, x - 260):max(0, x - 15)] > 242
    if region.size == 0:
        return False
    # The native panel's large white slider thumb is distinct from small text.
    return any(int(row.sum()) >= 18 for row in region) and int(region.sum()) > 280


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

    def show(self):
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
        control = find_control(image, self.microphone, self.chevron)
        if control is None:
            return False
        if panel_visible(image, control):
            return True
        if not self.focus.active() or root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType).value[0] != window.id:
            return False
        x, y = control[0] - 88, control[1]
        origin = root.translate_coords(window, 0, 0)
        for kind in (protocol.event.ButtonPress, protocol.event.ButtonRelease):
            event = kind(time=X.CurrentTime, root=root, window=window, child=X.NONE,
                         root_x=origin.x + x, root_y=origin.y + y, event_x=x, event_y=y,
                         state=0, same_screen=1, detail=1)
            window.send_event(event, event_mask=X.ButtonPressMask if kind is protocol.event.ButtonPress else X.ButtonReleaseMask, propagate=False)
        display.flush()
        return True
