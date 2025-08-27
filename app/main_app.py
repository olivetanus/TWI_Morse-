# app/main_app.py
import sys, os, numpy as np
from time import perf_counter
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QInputDialog
from PyQt5.QtCore import QTimer, QObject, pyqtSignal

from app.ui_layout import build_ui, COORDS
from app.widgets.waterfall import Waterfall
from app.widgets.needle_meter import NeedleSMeter
from app.widgets.marker_bar import MarkerBar
from app.widgets.channel_scale import ChannelScale

from net.cwcom_client import CWComClient
from cw.activity_probe import ActivityProbe
from app.decoder.morse_decoder import AdaptiveCWDecoder
from cw.cw_tx_encoder import TxEncoder
from cw.tx_input import TxInput
from cw.audio_engine import AudioEngine
from cw.sender_classifier import SenderClassifier

def _cols_evenly_spaced(ncols:int, width:int):
    if ncols <= 1: return [width//2]
    step = width / float(ncols + 1)
    return [int((i+1)*step) for i in range(ncols)]

def wires_around(center:int, span:int=5):
    start = max(1, int(center) - span)
    return list(range(start, start + 2*span + 1))

class UiBus(QObject):
    append_text = pyqtSignal(str)
    set_title   = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowTitle("TWO_Morse"); self.setFixedSize(1600, 700)
        self.app = app

        callsign, ok = QInputDialog.getText(self, "Callsign", "Inserisci il tuo nominativo (es. IZ6198SWL):")
        self.callsign = callsign.strip() if ok and callsign.strip() else "TWI Client"

        central = QWidget(); self.setCentralWidget(central)
        self.ui, self.coords = build_ui(central)

        # Waterfall (ridotto 15 px per marker+barra)
        wf_x, wf_y, wf_w, wf_h_orig = self.coords["waterfall"]
        wf_h = max(50, wf_h_orig - 15)
        self.waterfall = Waterfall(wf_w, wf_h, central)
        self.waterfall.setGeometry(wf_x, wf_y, wf_w, wf_h)
        self.waterfall.set_running(False); self.waterfall.raise_()

        # Marker + scala canali
        mb_h = 14
        self.marker = MarkerBar(wf_w, mb_h, central)
        self.marker.setGeometry(wf_x, wf_y + wf_h + 0, wf_w, mb_h)
        self.marker.set_fraction(0.5)

        cs_h = 22
        self.chan_scale = ChannelScale(wf_w, cs_h, central, span=5)
        self.chan_scale.setGeometry(wf_x, wf_y + wf_h + mb_h + 0, wf_w, cs_h)
        self.chan_scale.set_center_channel(133)

        # S-meter
        self.smeter = NeedleSMeter(central)
        self.smeter.setGeometry(*self.coords["smeter"])
        self.smeter.set_level(0,0)

        # Stato
        self._center = 133
        self._s_target = 0.0; self._s_ema = 0.0
        self._center_gate = 0.0
        self._center_gate_target = 0.0

        # Laterali
        self.probe = ActivityProbe(
            center_wire=self._center,
            scenic=True,
            env_threshold=0.03,
            scenic_mode="active",
            scenic_prob_active=0.42
        )

        # Decoder + classificatore
        self.decoder = AdaptiveCWDecoder(
            on_symbol=lambda s: self._append_decoder(s),
            on_text=lambda t: self._append_decoder(t)
        )
        self.classifier = SenderClassifier(); self._src_mode = "—"

        # TX locale
        self.encoder = TxEncoder(on_tx_event=self._on_tx_event)
        self.tx_input = TxInput(self.app)
        self.tx_input.bind_spacebar(self.encoder.key_down, self.encoder.key_up)

        # Audio CW
        self.audio = AudioEngine(tone_hz=600.0, samplerate=48000, volume=55)
        self.audio.start()

        # Bus segnali UI (thread-safe)
        self._bus = UiBus()
        self._bus.append_text.connect(self._append_decoder_on_ui)
        self._bus.set_title.connect(self._set_title_on_ui)

        # —— Stato anti-beep negli spazi ——
        self._timing_seen_ts = 0.0     # ultimo arrivo di mark/space (s) — “modalità tempi”
        self._hard_mute_until = 0.0    # silenzio forzato fino a (s)

        self.client = None
        self._wire_ui()

        self._ui_timer = QTimer(self); self._ui_timer.setInterval(33)
        self._ui_timer.timeout.connect(self._ui_tick); self._ui_timer.start()

        if not self.ui["server_input"].text().strip():
            self.ui["server_input"].setText("http://5.250.190.24")

    # ─────────────────────────── helpers
    def _wire_ui(self):
        self.ui["btn_connect"].toggled.connect(self._on_connect)
        self.ui["knob_rf"].valueChanged.connect(self._on_knob_rf)
        self.ui["knob_vol"].valueChanged.connect(self._on_knob_vol)
        self.ui["channel_edit"].editingFinished.connect(self._from_edit)

    def _set_channel_text(self, v:int):
        self.ui["channel_edit"].blockSignals(True)
        self.ui["channel_edit"].setText(f"{int(v):06d}")
        self.ui["channel_edit"].blockSignals(False)

    def _on_knob_rf(self, v:int): self._set_channel_text(v); self._set_center(v)
    def _from_edit(self):
        try: v = int(self.ui["channel_edit"].text())
        except: return
        self.ui["knob_rf"].setValue(v); self._set_center(v)

    def _set_center(self, v:int):
        self._center = int(v)
        self.probe.set_center(self._center)
        if self.client: self.client.set_center_wire(self._center)
        self.marker.set_fraction(0.5)
        self.chan_scale.set_center_channel(self._center)

    def _on_knob_vol(self, vol:int):
        self.audio.set_volume(vol)
        try:
            if self.client: self.client.set_volume(vol)
        except: pass

    def _audio_gate(self, want_on: bool):
        """Gate audio con hard-mute: nessun suono finché siamo dentro lo space."""
        now = perf_counter()
        if want_on and now < self._hard_mute_until:
            self.audio.rx_key(False)
            return
        self.audio.rx_key(bool(want_on))

    def _using_timings(self) -> bool:
        """Siamo in modalità 'tempi' se abbiamo visto mark/space negli ultimi 0.5 s."""
        return (perf_counter() - self._timing_seen_ts) < 0.5

    # ─────────────────────────── connect / client
    def _on_connect(self, on:bool):
        host = self.ui["server_input"].text().strip()
        if on:
            self._start_client(host, self._center)
            self.waterfall.set_running(True)
        else:
            self._stop_client()
            self.waterfall.set_running(False); self.waterfall.clear()
            self.smeter.set_level(0.0, 0.0)
            self._center_gate = self._center_gate_target = 0.0
            self._hard_mute_until = 0.0
            self.audio.rx_key(False); self.audio.tx_key(False)

    def _start_client(self, host:str, center:int):
        self._stop_client()

        def cb_env(wire, env): self.probe.update_env(int(wire), float(env))
        def cb_key(wire, is_on): self.probe.update_env(int(wire), float(self.probe.env.get(int(wire),0.0)), key_on=bool(is_on))
        def cb_s(level, over): self._s_target = float(level)

        # ——— Fronti FALLBACK (per-arrival): usali solo se NON abbiamo tempi recenti ———
        def cb_center_key(is_on):
            self.decoder.feed(bool(is_on), perf_counter())
            if not self._using_timings():
                self._audio_gate(bool(is_on))
                self._center_gate_target = 1.0 if is_on else 0.0

        def cb_center_sym(sym): self._append_decoder(sym)

        # ——— Tempi per-pacchetto: AUTOREVOLI (audio + gate UI) ———
        def cb_center_mark_ms(ms):
            now = perf_counter()
            self._timing_seen_ts = now
            self._hard_mute_until = 0.0             # fine dello space: sblocca
            self._audio_gate(True)                  # tono ON
            self._center_gate_target = 1.0          # illumina corpo centrale
            # decoder + classifier
            self.decoder.hint_dot_ms(ms)
            self.classifier.update_mark_ms(ms); self._maybe_update_mode_badge()
            # aggiorna release in base al dot
            try:
                wpm = self.decoder.get_wpm(); dot = 1.2 / max(1e-6, wpm)
                self.audio.set_dot_seconds(dot)
            except: pass
            # piccolo bump S-meter
            self._s_target = min(1.0, 0.85*self._s_target + 0.35)

        def cb_center_space_ms(ms):
            now = perf_counter()
            self._timing_seen_ts = now
            self._audio_gate(False)                 # tono OFF
            self._center_gate_target = 0.0          # spegni corpo centrale
            self.decoder.force_gap_ms(ms)
            self.classifier.update_space_ms(ms); self._maybe_update_mode_badge()
            # hard mute: evita riaccensioni spurie durante lo space
            self._hard_mute_until = now + min(0.5, 0.9 * (float(ms)/1000.0))

        self.client = CWComClient(
            host=host, center_wire=center,
            on_env=cb_env, on_key=cb_key,
            on_center_level=cb_s,
            on_center_element=cb_center_sym,
            on_center_keying=cb_center_key,
            on_center_mark_ms=cb_center_mark_ms,
            on_center_space_ms=cb_center_space_ms,
            span=5, audio=False, callsign=self.callsign, version="TWI Modular 4.4"
        )
        try: self.client.start()
        except Exception as e: print("Errore avvio client:", e)

    def _stop_client(self):
        if self.client:
            try: self.client.stop()
            except: pass
        self.client = None

    def _on_tx_event(self, is_on:bool, t_now:float):
        self.decoder.feed(is_on, t_now)
        self._center_gate_target = 1.0 if is_on else 0.0
        self.audio.tx_key(bool(is_on))
        # TODO: TX verso server

    # ====== Decoder text: thread-safe ======
    def _append_decoder(self, text:str): self._bus.append_text.emit(text)
    def _append_decoder_on_ui(self, text:str):
        if not self.ui["btn_decoder"].isChecked(): return
        box = self.ui["decoder_box"]
        tc = box.textCursor(); tc.movePosition(tc.End)
        box.setTextCursor(tc); box.insertPlainText(text)

    # ====== Titlebar: thread-safe ======
    def _maybe_update_mode_badge(self):
        mode, wpm = self.classifier.get()
        if mode != self._src_mode and mode in ("AUTO","HUMAN"):
            self._src_mode = mode
            self._bus.set_title.emit(f"TWO_Morse — RX: {mode} ~{int(round(wpm))} WPM")
    def _set_title_on_ui(self, s:str):
        self.setWindowTitle(s)

    # ─────────────────────────── UI tick
    def _ui_tick(self):
        now = perf_counter()
        self.decoder.tick(now)

        # Waterfall: laterali + “corpo” centrale agganciato al gate
        if self.ui["btn_connect"].isChecked():
            w = self.waterfall.width()
            wires = wires_around(self._center, 5)
            cols  = _cols_evenly_spaced(len(wires), w)
            self.probe.set_columns({wire:x for wire,x in zip(wires, cols)})

            line = self.probe.next_line(w)

            # animazione gate con attack/release
            up, dn = 0.62, 0.18
            self._center_gate += (self._center_gate_target - self._center_gate) * (up if self._center_gate_target > self._center_gate else dn)
            self._center_gate = float(np.clip(self._center_gate, 0.0, 1.0))

            x = cols[len(cols)//2]; half = 3
            x1 = max(0, x-half); x2 = min(w-1, x+half)
            ci = self._center_gate
            if ci > 0.05:
                width_px = x2 - x1 + 1
                ramp = np.linspace(0.55, 1.0, num=(half+1), dtype=np.float32)
                prof = (np.concatenate([ramp[:-1], ramp[::-1]])
                        if width_px == 2*half+1 else np.ones(width_px, dtype=np.float32))
                line[x1:x2+1] = np.maximum(line[x1:x2+1],
                                           (0.18 + 0.82*ci) * prof[:width_px])

            self.waterfall.push_line(line)

        # S-meter: attack veloce, release morbido
        k = 0.58 if self._s_target > self._s_ema else 0.12
        self._s_ema += (self._s_target - self._s_ema) * k
        self.smeter.set_level(self._s_ema, 0.0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow(app); w.show()
    sys.exit(app.exec_())
