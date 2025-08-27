# cw/tx_input.py
"""
Gestione input locali:
- Spacebar: PTT CW (premi = key down, rilascia = key up) con debounce.
- Futuro: paddle seriale / iambic.
Espone metodi bind/unbind per collegarsi a una QMainWindow.
"""
import time
from PyQt5.QtCore import QObject, QEvent, Qt

class SpacebarFilter(QObject):
    def __init__(self, on_down, on_up, debounce_ms=2):
        super().__init__()
        self.on_down = on_down
        self.on_up   = on_up
        self.debounce = debounce_ms/1000.0
        self._last = 0.0
        self._pressed = False

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Space:
            now = time.time()
            if (now - self._last) >= self.debounce and not self._pressed:
                self._pressed = True
                self._last = now
                self.on_down()
            return True
        if ev.type() == QEvent.KeyRelease and ev.key() == Qt.Key_Space:
            now = time.time()
            if (now - self._last) >= self.debounce and self._pressed:
                self._pressed = False
                self._last = now
                self.on_up()
            return True
        return False

class TxInput:
    def __init__(self, app):
        self.app = app
        self._space_filter = None

    def bind_spacebar(self, on_down, on_up):
        self._space_filter = SpacebarFilter(on_down, on_up)
        self.app.installEventFilter(self._space_filter)

    def unbind(self):
        if self._space_filter:
            self.app.removeEventFilter(self._space_filter)
            self._space_filter = None
