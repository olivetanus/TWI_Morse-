# app/widgets/waterfall.py
import numpy as np
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap, QPainter, QImage
from PyQt5.QtCore import Qt

class Waterfall(QWidget):
    """
    Waterfall con scorrimento 1px/frame e palette fredda (blu->ciano).
    Nessun marker disegnato qui: il marker è esterno (MarkerBar).
    """
    def __init__(self, width=806, height=370, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.pix = QPixmap(width, height)
        self.pix.fill(Qt.black)
        self.running = False
        self._row_buf = None  # buffer temporaneo

    def set_running(self, on: bool):
        self.running = bool(on)

    def clear(self):
        self.pix.fill(Qt.black)
        self.update()

    def _map_palette(self, vals):
        """
        Mappa [0..1] -> RGB (più luminoso del nero totale).
        """
        vals = np.clip(vals, 0.0, 1.0)
        g = (30 + vals * 210).astype(np.uint8)
        b = (60 + vals * 195).astype(np.uint8)
        r = (0 + vals * 30).astype(np.uint8)
        row = np.empty((1, vals.size, 3), dtype=np.uint8)
        row[0,:,0] = r; row[0,:,1] = g; row[0,:,2] = b
        return row

    def push_line(self, line):
        """
        line: ndarray [0..1] di lunghezza = width. Nessun overlay interno.
        """
        if not self.running:
            self.update(); return

        w, h = self.width(), self.height()
        vals = np.zeros(w, dtype=np.float32) if line is None else np.asarray(line, dtype=np.float32)
        if vals.size < w:
            vals = np.pad(vals, (0, w-vals.size), mode="edge")
        vals = np.clip(vals[:w], 0.0, 1.0)

        # alza un filo il noise floor se tutto piatto
        if float(vals.max()) < 0.03:
            vals = vals + 0.03

        row = self._map_palette(vals)
        self._row_buf = row.tobytes()
        img = QImage(self._row_buf, w, 1, 3*w, QImage.Format_RGB888)

        self.pix.scroll(0, -1, self.rect())
        p = QPainter(self.pix)
        p.drawImage(0, h-1, img)
        p.end()
        self.update()

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.drawPixmap(0, 0, self.pix)
