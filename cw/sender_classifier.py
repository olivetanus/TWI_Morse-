# cw/sender_classifier.py
from collections import deque
import math

def _cv(vals):
    n = len(vals)
    if n < 2: return 1.0
    m = sum(vals)/n
    if m <= 1e-9: return 1.0
    v = sum((x-m)*(x-m) for x in vals)/(n-1)
    return math.sqrt(max(0.0, v))/m

class SenderClassifier:
    """Stima sorgente: 'AUTO' (feed) vs 'HUMAN' (operatore) + WPM."""
    def __init__(self, window=64):
        self.marks = deque(maxlen=window)
        self.spaces = deque(maxlen=window)
        self.mode = "—"
        self.wpm = 0.0

    def update_mark_ms(self, ms: float):
        if 0.5 < ms < 10000.0:
            self.marks.append(float(ms))
        self._update()

    def update_space_ms(self, ms: float):
        if 0.5 < ms < 10000.0:
            self.spaces.append(float(ms))
        self._update()

    def _update(self):
        if self.marks:
            dot_s = min(self.marks)/1000.0
            if dot_s > 1e-3:
                self.wpm = 1.2 / dot_s
        if len(self.marks) >= 12 and len(self.spaces) >= 12:
            cm = _cv(self.marks); cs = _cv(self.spaces)
            self.mode = "AUTO" if (cm < 0.12 and cs < 0.18) else "HUMAN"

    def get(self):
        return self.mode, self.wpm
