# TWI_Morse.py
import sys, os, numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLineEdit, QLabel,
    QPlainTextEdit, QInputDialog
)
from PyQt5.QtGui import QPixmap, QColor, QFont
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from needle_meter import NeedleSMeter
from waterfall import Waterfall
from kob_client import KOBClient, wires_around

BASE_DIR   = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "images")
CHASSIS    = os.path.join(ASSETS_DIR, "chassis.png")
SMETER_LIGHT = os.path.join(ASSETS_DIR, "smeter_light.png")

# ── Bottoni immagine ──
class ImageToggleButton(QLabel):
    toggled = pyqtSignal(bool)
    def __init__(self, off_path, on_path, size, parent=None):
        super().__init__(parent)
        self.off_path, self.on_path = off_path, on_path
        self._checked = False
        self.setScaledContents(True); self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(*size); self._refresh()
    def isChecked(self): return self._checked
    def setChecked(self, v: bool):
        v = bool(v)
        if v != self._checked:
            self._checked = v; self._refresh(); self.toggled.emit(self._checked)
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton: self.setChecked(not self._checked)
    def _refresh(self):
        path = self.on_path if self._checked else self.off_path
        full = os.path.join(ASSETS_DIR, path)
        pm = QPixmap(full) if os.path.exists(full) else QPixmap(self.size())
        if pm.isNull(): pm = QPixmap(self.size()); pm.fill(QColor(58,63,68))
        self.setPixmap(pm.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

class ImageButton(QLabel):
    clicked = pyqtSignal()
    def __init__(self, path, size, parent=None):
        super().__init__(parent); self.path=path
        self.setScaledContents(True); self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(*size); self._refresh()
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton: self.clicked.emit()
    def _refresh(self):
        full = os.path.join(ASSETS_DIR, self.path)
        pm = QPixmap(full) if os.path.exists(full) else QPixmap(self.size())
        if pm.isNull(): pm = QPixmap(self.size()); pm.fill(QColor(58,63,68))
        self.setPixmap(pm.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

class RotatingKnob(ImageButton):
    valueChanged = pyqtSignal(int)
    def __init__(self, img_name, size, minv=0, maxv=999999, val=0, parent=None):
        super().__init__(img_name, size, parent)
        self.minv, self.maxv, self.val = int(minv), int(maxv), int(val)
        self.setCursor(Qt.SizeVerCursor); self._drag=False
    def value(self): return self.val
    def setValue(self, v:int):
        v = max(self.minv, min(self.maxv, int(v)))
        if v!=self.val: self.val=v; self.valueChanged.emit(self.val)
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton: self._drag=True; self._last_y=e.y()
    def mouseReleaseEvent(self, e): self._drag=False
    def mouseMoveEvent(self, e):
        if self._drag:
            dy = self._last_y-e.y(); self._last_y=e.y()
            if abs(dy)>=2: self.setValue(self.val + (1 if dy>0 else -1))
    def wheelEvent(self, e):
        steps = int(e.angleDelta().y()/120)
        if steps: self.setValue(self.val + steps)

def _cols_evenly_spaced(ncols: int, width: int):
    if ncols <= 1: return [width//2]
    step = width / float(ncols + 1)
    return [int((i+1)*step) for i in range(ncols)]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TWI Morse"); self.setFixedSize(1600, 700)

        # callsign
        callsign, ok = QInputDialog.getText(self, "Callsign", "Inserisci il tuo nominativo (es. IZ6198SWL):")
        self.callsign = callsign.strip() if ok and callsign.strip() else "TWI Client"

        central = QWidget(); self.setCentralWidget(central)
        bg = QLabel(central); bg.setGeometry(0,0,1600,700)
        if os.path.exists(CHASSIS):
            bg.setPixmap(QPixmap(CHASSIS)); bg.setScaledContents(True)
        else:
            bg.setStyleSheet("background:#111;")

        # coordinate (come deciso)
        C = dict(
            waterfall     =(  76, 101, 806, 370),
            smeter        =( 926, 104, 279, 160),
            server_box    =(1240, 230, 205,  39),
            btn_connect   =(1466, 228,  81,  43),
            channel_box   =( 927, 340, 279,  67),
            btn_web       =(1256, 349,  81,  42),
            btn_server    =(1256, 420,  81,  43),
            decoder_toggle=( 249, 492,  81,  43),
            decoder_box   =(  77, 547, 806,  57),
            knob_rf       =( 926, 416, 280, 280),
            knob_vol      =(1236, 520, 120, 120),
            btn_vertical  =(1373, 348,  81,  43),
            btn_paddle    =(1373, 415,  81,  43),
            btn_spacebar  =(1373, 482,  81,  43),
        )

        # WATERFALL
        self.waterfall = Waterfall(C["waterfall"][2], C["waterfall"][3], central)
        self.waterfall.setGeometry(*C["waterfall"])
        self.waterfall.set_marker_fraction(0.5)

        # S-METER
        self.smeter = NeedleSMeter(central)
        self.smeter.setGeometry(*C["smeter"])
        self.smeter.set_level(0,0)

        # LUCE S-METER
        self.smeter_light = QLabel(central)
        self.smeter_light.setGeometry(*C["smeter"]); self.smeter_light.setScaledContents(True)
        pm = QPixmap(SMETER_LIGHT)
        if not pm.isNull():
            self.smeter_light.setPixmap(pm.scaled(self.smeter_light.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.smeter_light.hide(); self.smeter_light.raise_()

        # SERVER
        self.server_input = QLineEdit("http://5.250.190.24", central)
        self.server_input.setGeometry(*C["server_box"])
        self.server_input.setStyleSheet("background:#fff; color:#111; border-radius:6px; padding:6px;")

        # CONNECT
        self.btn_connect = ImageToggleButton("btn_connect_off.png","btn_connect_on.png",
                                             size=(C["btn_connect"][2], C["btn_connect"][3]), parent=central)
        self.btn_connect.setGeometry(*C["btn_connect"])
        self.btn_connect.toggled.connect(self.on_connect_toggled)

        # CHANNEL + knobs
        from PyQt5.QtGui import QIntValidator
        self.channel_edit = QLineEdit("000133", central)
        self.channel_edit.setGeometry(*C["channel_box"])
        self.channel_edit.setAlignment(Qt.AlignCenter)
        self.channel_edit.setStyleSheet("background:#fff; color:#111; border-radius:8px; font: bold 42px 'Consolas';")
        self.channel_edit.setValidator(QIntValidator(0, 999999, self))
        self.channel_edit.editingFinished.connect(self._channel_from_edit)

        self.knob_rf  = RotatingKnob("knob_rf.png",  size=(C["knob_rf"][2],  C["knob_rf"][3]),  minv=0, maxv=999999, val=133, parent=central)
        self.knob_rf.setGeometry(*C["knob_rf"]); self.knob_rf.valueChanged.connect(self.on_rf_changed)
        self.knob_vol = RotatingKnob("knob_vol.png", size=(C["knob_vol"][2], C["knob_vol"][3]), minv=0, maxv=100, val=40, parent=central)
        self.knob_vol.setGeometry(*C["knob_vol"]); self.knob_vol.valueChanged.connect(self.on_vol_changed)

        # pulsanti (grafici)
        self.btn_site   = ImageButton("site.png",   size=(C["btn_web"][2], C["btn_web"][3]), parent=central);   self.btn_site.setGeometry(*C["btn_web"])
        self.btn_server = ImageButton("server.png", size=(C["btn_server"][2], C["btn_server"][3]), parent=central); self.btn_server.setGeometry(*C["btn_server"])

        # Decoder
        self.btn_decoder = ImageToggleButton("btn_decoder_off.png","btn_decoder_on.png",
                                             size=(C["decoder_toggle"][2], C["decoder_toggle"][3]), parent=central)
        self.btn_decoder.setGeometry(*C["decoder_toggle"])

        self.decoder_box = QPlainTextEdit(central)
        self.decoder_box.setGeometry(*C["decoder_box"]); self.decoder_box.setReadOnly(True)
        self.decoder_box.setStyleSheet("background:#fff; color:#111; border-radius:6px; padding:6px;")

        # Key selectors (grafica)
        self.btn_vertical = ImageToggleButton("btn_vertical_off.png","btn_vertical_on.png",
                                              size=(C["btn_vertical"][2], C["btn_vertical"][3]), parent=central)
        self.btn_vertical.setGeometry(*C["btn_vertical"])
        self.btn_paddle   = ImageToggleButton("btn_paddle_off.png","btn_paddle_on.png",
                                              size=(C["btn_paddle"][2], C["btn_paddle"][3]), parent=central)
        self.btn_paddle.setGeometry(*C["btn_paddle"])
        self.btn_spacebar = ImageToggleButton("btn_spacebar_off.png","btn_spacebar_on.png",
                                              size=(C["btn_spacebar"][2], C["btn_spacebar"][3]), parent=central)
        self.btn_spacebar.setGeometry(*C["btn_spacebar"])

        # stato runtime
        self._clients = None
        self._center  = 133
        self._env_map = {}                 # wire -> env
        self._key_map = {}                 # wire -> bool
        self._s_target = 0.0; self._s_ema = 0.0

        # UI tick
        self._ui = QTimer(self); self._ui.setInterval(33)
        self._ui.timeout.connect(self._ui_tick); self._ui.start()

    # ── helpers ──
    def _set_channel_text(self, v:int):
        self.channel_edit.blockSignals(True)
        self.channel_edit.setText(f"{int(v):06d}")
        self.channel_edit.blockSignals(False)

    def _channel_from_edit(self):
        try: v = int(self.channel_edit.text())
        except: return
        self.knob_rf.setValue(v)
        if self.btn_connect.isChecked() and self._clients:
            self._center = int(v); self._clients.set_center_wire(self._center)
            self.waterfall.set_marker_fraction(0.5)

    def on_rf_changed(self, val:int):
        self._set_channel_text(val)
        if self.btn_connect.isChecked() and self._clients:
            self._center = int(val); self._clients.set_center_wire(self._center)
            self.waterfall.set_marker_fraction(0.5)

    def on_vol_changed(self, val:int):
        if self._clients: self._clients.set_volume(val)

    # ── connect / disconnect ──
    def on_connect_toggled(self, on: bool):
        host = self.server_input.text().strip()
        if on:
            self._center = int(self.knob_rf.value())
            self._start_client(host, self._center)
            self.waterfall.set_running(True)
            self.waterfall.set_marker_fraction(0.5)
            self.smeter_light.show(); self.smeter_light.raise_()
        else:
            self._stop_client()
            self.waterfall.set_running(False); self.waterfall.clear()
            self.smeter.set_level(0.0, 0.0)
            self.smeter_light.hide()

    def _start_client(self, host: str, center: int):
        self._stop_client()

        def cb_env(wire, env):  self._env_map[int(wire)] = float(env)
        def cb_key(wire, is_on): self._key_map[int(wire)] = bool(is_on)
        def cb_s(s, over):       self._s_target = float(s)
        def cb_elem(sym):
            if self.btn_decoder.isChecked():
                self.decoder_box.moveCursor(self.decoder_box.textCursor().End)
                self.decoder_box.insertPlainText(sym)

        # reset mappe
        self._env_map.clear(); self._key_map.clear()
        self._s_target = 0.0; self._s_ema = 0.0

        self._clients = KOBClient(
            host=host, center_wire=center,
            on_env=cb_env, on_key=cb_key,
            on_center_level=cb_s, on_center_element=cb_elem,
            span=5, audio=True, callsign=self.callsign, version="TWI 1.0"
        )
        self._clients.set_volume(self.knob_vol.value()); self._clients.start()

    def _stop_client(self):
        if self._clients:
            try: self._clients.stop()
            except: pass
        self._clients = None
        self._env_map.clear(); self._key_map.clear()

    # ── UI tick: disegna 10 colonne, ON=tratto continuo, OFF=debole ──
    def _ui_tick(self):
        if self.btn_connect.isChecked():
            w = self.waterfall.width()
            line = np.full(w, 0.06, dtype=np.float32)    # rumore base
            wires = wires_around(self._center, 5)
            cols  = _cols_evenly_spaced(len(wires), w)

            for wire, x in zip(wires, cols):
                env = float(self._env_map.get(wire, 0.0))
                on  = bool(self._key_map.get(wire, False))
                # intensità: ON molto visibile, OFF tenue proporzionale a env
                v = (0.85 if on else 0.08 + 0.60*env)
                x1 = max(0, x-1); x2 = min(w, x+2)
                line[x1:x2] = np.maximum(line[x1:x2], v)

            self.waterfall.push_line(line)

        # S-meter smoothing
        ALPHA = 0.45
        self._s_ema = (1-ALPHA)*self._s_ema + ALPHA*self._s_target
        self.smeter.set_level(self._s_ema, 0.0)

# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow(); w.show()
    sys.exit(app.exec_())
