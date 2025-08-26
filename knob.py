# knob.py
import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QTransform
from PyQt5.QtCore import Qt, QEvent, QPoint

class RotatingKnob(QWidget):
    def __init__(self, img_path, size, minv=0, maxv=100, val=50, parent=None):
        super().__init__(parent)
        self.setFixedSize(*size)
        self.base = QPixmap(img_path) if (img_path and os.path.exists(img_path)) else None
        self.minv, self.maxv, self.val = int(minv), int(maxv), int(val)
        self._drag = False
        self.valueChanged = lambda v: None

    def setValue(self, v: int):
        v = max(self.minv, min(self.maxv, int(v)))
        if v != self.val:
            self.val = v
            self.valueChanged(self.val)
            self.update()

    def value(self): return self.val

    def _val_to_angle(self):
        if self.maxv == self.minv: return 0.0
        f = (self.val - self.minv) / (self.maxv - self.minv)
        return -135.0 + f * 270.0

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = True
            self._last_y = e.y()

    def mouseReleaseEvent(self, e):
        self._drag = False

    def mouseMoveEvent(self, e):
        if self._drag:
            dy = self._last_y - e.y()
            self._last_y = e.y()
            self.setValue(self.val + int(dy/2))

    def wheelEvent(self, e):
        steps = int(e.angleDelta().y() / 120)
        self.setValue(self.val + steps)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self.base:
            scaled = self.base.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ang = self._val_to_angle()
            t = QTransform()
            t.translate(self.width()/2, self.height()/2)
            t.rotate(ang)
            t.translate(-scaled.width()/2, -scaled.height()/2)
            p.setTransform(t)
            p.drawPixmap(0, 0, scaled)
        else:
            p.fillRect(self.rect(), QColor(40,40,40))
            p.setPen(QPen(QColor(200,200,200),3))
            p.drawEllipse(self.rect().adjusted(3,3,-3,-3))
