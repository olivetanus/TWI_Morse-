# app/widgets/marker_bar.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QLinearGradient
from PyQt5.QtCore import Qt

class MarkerBar(QWidget):
    """
    Barra marker stile SDR: fuori dal waterfall, disegna un marcatore '/-----|'
    alla posizione orizzontale indicata da fraction (0..1).

    Look:
    - Asse X sottile con una sfumatura leggera
    - Marcatore con doppio tratto (ombra+highlight) per un effetto più pulito
    - Anti-alias attivo
    """
    def __init__(self, width=806, height=20, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._fraction = 0.5  # centro di default
        # sfondo trasparente
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # colori
        self._axis_light = QColor(235, 238, 240, 160)
        self._axis_dark  = QColor(150, 155, 160, 90)
        self._glow       = QColor(30, 30, 30, 140)        # ombra
        self._marker_col = QColor(255, 240, 150, 230)     # highlight

    def set_fraction(self, f: float):
        f = max(0.0, min(1.0, float(f)))
        if abs(f - self._fraction) > 1e-6:
            self._fraction = f
            self.update()

    def fraction(self) -> float:
        return self._fraction

    def _x_from_fraction(self) -> int:
        w = self.width()
        return int(self._fraction * (w - 1))

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()

        # Asse X (in alto nella barra, così è "più su" vicino al bordo del waterfall)
        base_y = max(4, int(h * 0.35))   # posizione verticale del marcatore/asse

        # Sfumatura asse X
        grad = QLinearGradient(0, base_y, 0, base_y+1)
        grad.setColorAt(0.0, self._axis_light)
        grad.setColorAt(1.0, self._axis_dark)
        qp.setPen(QPen(self._axis_light, 1, Qt.SolidLine, Qt.FlatCap))
        qp.drawLine(0, base_y, w-1, base_y)

        # Posizione del marcatore
        x = self._x_from_fraction()

        # Parametri forma scalati sull'altezza
        slash_h   = min(12, max(6, int(h * 0.60)))       # altezza della '/'
        horiz_len = max(14, int(h * 1.2))                # lunghezza '-----'
        bar_h     = min(14, max(7, int(h * 0.75)))       # altezza '|'

        # Limiti per non uscire dal widget
        x_slash_end   = max(0, x - 2)
        x_slash_start = max(0, x_slash_end - 6)
        x_h1 = x_slash_end
        x_h2 = min(w-1, x_h1 + horiz_len)
        x_bar = x_h2

        # ---- Tratto "glow" (ombra) leggermente sotto, più spesso ----
        qp.setPen(QPen(self._glow, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        # '/' inclinata (ombra)
        qp.drawLine(x_slash_start, base_y - slash_h + 1, x_slash_end, base_y + 1)
        # '-----' orizzontale (ombra)
        qp.drawLine(x_h1, base_y + 1, x_h2, base_y + 1)
        # '|' verticale finale (ombra)
        qp.drawLine(x_bar, base_y - bar_h + 1, x_bar, base_y + 1)

        # ---- Tratto principale (chiaro) ----
        qp.setPen(QPen(self._marker_col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        # '/' inclinata
        qp.drawLine(x_slash_start, base_y - slash_h, x_slash_end, base_y)
        # '-----' orizzontale
        qp.drawLine(x_h1, base_y, x_h2, base_y)
        # '|' verticale finale
        qp.drawLine(x_bar, base_y - bar_h, x_bar, base_y)

        qp.end()
