# waterfall.py
import numpy as np
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt5.QtCore import Qt

class Waterfall(QWidget):
    """
    Waterfall con:
      - scorrimento continuo
      - palette blu SDR-like
      - possibilità di marcatore verticale del demodulatore
    """
    def __init__(self, width=806, height=370, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.pix = QPixmap(width, height)
        self.pix.fill(Qt.black)
        self.running = False
        # marcatore del demodulatore (pixel), -1 = nascosto
        self.marker_x = -1

    # API
    def set_running(self, on: bool):
        self.running = bool(on)

    def clear(self):
        self.pix.fill(Qt.black); self.update()

    def set_marker_pixel(self, x: int):
        self.marker_x = int(x) if (0 <= x < self.width()) else -1
        self.update()

    def set_marker_fraction(self, f: float):
        # f in [0..1]
        x = int(max(0.0, min(1.0, float(f))) * (self.width()-1))
        self.set_marker_pixel(x)

    def push_line(self, line):
        """line: array [0..1] di lunghezza >= width; palette blu + “hot” azzurro."""
        if not self.running:
            # anche se non “gira”, aggiorniamo la GUI
            self.update()
            return

        w, h = self.width(), self.height()
        if line is None:  # linea vuota scura
            vals = np.zeros(w, dtype=np.float32)
        else:
            vals = np.asarray(line, dtype=np.float32)
            if vals.size < w:
                # pad alla larghezza
                vals = np.pad(vals, (0, w-vals.size), mode="edge")
            vals = vals[:w]
            # clamp
            vals = np.clip(vals, 0.0, 1.0)

        # scroll in alto di 1px
        self.pix.scroll(0, -1, self.rect())

        p = QPainter(self.pix)
        # disegniamo la riga in basso
        for x, v in enumerate(vals):
            # base blu scuro
            # intensità: blu → azzurro
            b = int(60 + v * 160)     # 60..220
            g = int(v * 160)          # 0..160
            col = QColor(0, g, b)
            p.setPen(col)
            p.drawPoint(x, h-1)

        # (opzionale) leggero “fade” generale per tenere un look SDR
        # qui NON lo applichiamo perché scrolliamo già 1px per frame

        # marcatore demodulatore
        if self.marker_x >= 0:
            pen = QPen(QColor(255, 230, 120, 180), 1, Qt.SolidLine)
            p.setPen(pen)
            p.drawLine(self.marker_x, 0, self.marker_x, h-1)

        p.end()
        self.update()

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.drawPixmap(0, 0, self.pix)
