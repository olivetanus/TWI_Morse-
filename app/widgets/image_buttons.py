# app/widgets/image_buttons.py
import os
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtCore import Qt, pyqtSignal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR   = os.path.join(PROJECT_ROOT, "assets", "images")

class ImageButton(QLabel):
    clicked = pyqtSignal()
    def __init__(self, path, size, parent=None):
        super().__init__(parent)
        self._path = path
        self.setScaledContents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(*size)
        self._refresh()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
    def _refresh(self):
        full = os.path.join(ASSETS_DIR, self._path)
        pm = QPixmap(full) if os.path.exists(full) else QPixmap(self.size())
        if pm.isNull():
            pm = QPixmap(self.size()); pm.fill(QColor(58,63,68))
        self.setPixmap(pm.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

class ImageToggleButton(QLabel):
    toggled = pyqtSignal(bool)
    def __init__(self, off_path, on_path, size, parent=None):
        super().__init__(parent)
        self._off, self._on = off_path, on_path
        self._checked = False
        self.setScaledContents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(*size)
        self._refresh()
    def isChecked(self): return self._checked
    def setChecked(self, v: bool):
        v = bool(v)
        if v != self._checked:
            self._checked = v
            self._refresh()
            self.toggled.emit(self._checked)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
    def _refresh(self):
        path = self._on if self._checked else self._off
        full = os.path.join(ASSETS_DIR, path)
        pm = QPixmap(full) if os.path.exists(full) else QPixmap(self.size())
        if pm.isNull():
            pm = QPixmap(self.size()); pm.fill(QColor(58,63,68))
        self.setPixmap(pm.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

class RotatingKnob(ImageButton):
    from PyQt5.QtCore import pyqtSignal as _sig
    valueChanged = _sig(int)
    def __init__(self, img_name, size, minv=0, maxv=999999, val=0, parent=None):
        super().__init__(img_name, size, parent)
        self._min, self._max, self._val = int(minv), int(maxv), int(val)
        self.setCursor(Qt.SizeVerCursor)
        self._drag=False; self._last_y=0
    def value(self): return self._val
    def setValue(self, v:int):
        v = max(self._min, min(self._max, int(v)))
        if v != self._val:
            self._val = v
            self.valueChanged.emit(self._val)
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton:
            self._drag=True; self._last_y=e.y()
    def mouseReleaseEvent(self, e): self._drag=False
    def mouseMoveEvent(self, e):
        if self._drag:
            dy = self._last_y - e.y(); self._last_y = e.y()
            if abs(dy) >= 2:
                self.setValue(self._val + (1 if dy>0 else -1))
    def wheelEvent(self, e):
        steps = int(e.angleDelta().y()/120)
        if steps: self.setValue(self._val + steps)
