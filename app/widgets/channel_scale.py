# app/widgets/channel_scale.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics

class ChannelScale(QWidget):
    """
    Barra canali stile SDR:
    - Mostra i canali reali (6 cifre) da center-5 a center+5
    - Quando cambia il canale centrale, la scala scorre fluidamente
      (animazione di trascinamento con easing).
    """
    def __init__(self, width=806, height=28, parent=None, span=5):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.span = int(span)
        self.center = 0

        # animazione: offset orizzontale in pixel (positivo = scorre a destra)
        self._anim_offset = 0.0
        self._target_offset = 0.0

        self._anim = QTimer(self)
        self._anim.setInterval(16)  # ~60 fps
        self._anim.timeout.connect(self._tick_anim)

        # stile
        self._axis_col = QColor(220, 225, 230, 150)
        self._tick_col = QColor(230, 235, 240, 180)
        self._text_dim = QColor(230, 235, 240, 210)
        self._text_hot = QColor(255, 240, 160, 255)
        self._hot_bg   = QColor(255, 240, 160, 28)

        self._font = QFont("Consolas", 11)
        self._font_bold = QFont("Consolas", 11, QFont.DemiBold)

    # API
    def set_center_channel(self, ch: int):
        ch = int(ch)
        if ch == self.center:
            return

        # Calcola cell width corrente
        cell_w = self._cell_width()
        delta = ch - self.center

        # aggiorna il centro MA sposta l'offset di un passo intero opposto,
        # così visivamente "continua" e poi si riallinea con l'animazione
        self.center = ch
        self._anim_offset -= delta * cell_w  # scorrimento immediato
        # e punta il target a 0 (riallineo con easing)
        self._target_offset = 0.0

        if not self._anim.isActive():
            self._anim.start()
        self.update()

    # Interni
    def _cell_width(self) -> float:
        # 2*span + 1 celle distribuite in tutta la larghezza
        n = 2 * self.span + 1
        return self.width() / float(n)

    def _tick_anim(self):
        # easing esponenziale verso _target_offset
        # moltiplicatore < 1 per "smorzare" rapidamente
        current = self._anim_offset
        target = self._target_offset
        diff = target - current
        if abs(diff) < 0.1:
            self._anim_offset = 0.0
            self._anim.stop()
            self.update()
            return
        # easing
        self._anim_offset += diff * 0.22
        self.update()

    def _format_chan(self, ch: int) -> str:
        # 6 cifre come nel box
        if ch < 0:
            return f"-{abs(ch):05d}"
        return f"{ch:06d}"

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        base_y = h - 1  # asse in basso

        # Asse X
        qp.setPen(QPen(self._axis_col, 1))
        qp.drawLine(0, base_y, w-1, base_y)

        # Geometria
        cell_w = self._cell_width()
        center_x = cell_w * (self.span + 0.5)  # centro teorico della cell centrale
        offset = self._anim_offset

        # Ticks + etichette
        # usiamo font metrics per centrare i testi
        for i in range(-self.span, self.span+1):
            x_cell_center = center_x + i * cell_w + offset
            x_text_center = int(x_cell_center)

            # tick principale (alla base)
            tick_h = 6 if i != 0 else 10
            qp.setPen(QPen(self._tick_col, 1))
            qp.drawLine(int(x_cell_center), base_y - tick_h, int(x_cell_center), base_y)

            # rettangolo soft dietro al canale centrale
            if i == 0:
                hot_w = max(36, int(cell_w*0.72))
                hot_x = int(x_cell_center - hot_w/2)
                qp.fillRect(hot_x, 2, hot_w, h-6, self._hot_bg)

            # testo del canale reale (6 cifre)
            ch_num = self.center + i
            label = self._format_chan(ch_num)

            if i == 0:
                qp.setFont(self._font_bold)
                qp.setPen(self._text_hot)
            else:
                qp.setFont(self._font)
                qp.setPen(self._text_dim)

            fm = QFontMetrics(qp.font())
            tw = fm.horizontalAdvance(label)
            th = fm.ascent()
            tx = x_text_center - tw//2
            ty = (h - 6)  # un filo sopra l'asse

            # evita sfori ai bordi
            if tx < 0: tx = 0
            if tx + tw > w: tx = w - tw

            qp.drawText(int(tx), int(ty), label)

        qp.end()
