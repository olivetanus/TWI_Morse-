# needle_meter.py
import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QPointF

class NeedleSMeter(QWidget):
    PIVOT_X = 0.50
    PIVOT_Y = 0.82
    LENGTH  = 0.75
    REVERSE_ARC = False  # S0 a sinistra, S9 a destra

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.s_units = 0.0
        self.over_db = 0.0
        self.needle_color = QColor(220, 30, 30)   # rosso
        self.shadow_color = QColor(0, 0, 0, 150)  # ombra
        self.pen_width    = 1
        self.shadow_width = 3

    def set_level(self, s_units: float, over_db: float = 0.0):
        self.s_units = max(0.0, min(6.0, float(s_units)))
        self.over_db = max(0.0, min(60.0, float(over_db)))
        self.update()

    def _angles(self):
        start_std, end_std = -150.0, +30.0  # arco tipico
        if self.REVERSE_ARC:
            return (+30.0, -150.0)
        return (start_std, end_std)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        start_deg, end_deg = self._angles()
        frac = self.s_units / 9.0
        ang  = start_deg + frac * (end_deg - start_deg)

        w, h = self.width(), self.height()
        cx, cy = w * self.PIVOT_X, h * self.PIVOT_Y
        L = min(w, h) * self.LENGTH

        tip = QPointF(cx + L * math.cos(math.radians(ang)),
                      cy + L * math.sin(math.radians(ang)))

        p.setPen(QPen(self.shadow_color, self.shadow_width, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx, cy), tip)
        p.setPen(QPen(self.needle_color, self.pen_width, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx, cy), tip)
