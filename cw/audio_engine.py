# cw/audio_engine.py
import math
import numpy as np

class AudioEngine:
    """Sidetone CW stile cwcom (sinusoide + attack/release morbidi)."""
    def __init__(self, tone_hz: float = 600.0, samplerate: int = 48000, volume: int = 50):
        self._sr   = float(samplerate)
        self._tone = float(tone_hz)
        self._vol  = self._map_vol(volume)

        self._phase = 0.0
        self._twopi = 2.0 * math.pi

        self._rx_env = 0.0; self._tx_env = 0.0
        self._rx_target = 0.0; self._tx_target = 0.0

        self._attack_s  = 0.003
        self._release_s = 0.006

        self._rx_att_k = self._coef(self._attack_s)
        self._rx_rel_k = self._coef(self._release_s)
        self._tx_att_k = self._rx_att_k
        self._tx_rel_k = self._rx_rel_k

        self.enabled = False
        self._sd = None
        self._stream = None
        try:
            import sounddevice as sd
            self._sd = sd
            self.enabled = True
        except Exception:
            self._sd = None
            self.enabled = False

    def start(self):
        if not self.enabled or self._stream is not None: return
        try:
            self._stream = self._sd.OutputStream(
                samplerate=int(self._sr),
                channels=1, dtype='float32',
                blocksize=256, latency='low',
                callback=self._callback
            ); self._stream.start()
        except Exception:
            self._stream = None; self.enabled = False

    def stop(self):
        if self._stream is not None:
            try: self._stream.stop(); self._stream.close()
            except Exception: pass
        self._stream = None

    def set_volume(self, vol: int):
        self._vol = self._map_vol(vol)

    def set_tone_hz(self, f: float):
        self._tone = float(max(200.0, min(1400.0, f)))

    def set_dot_seconds(self, dot_s: float):
        dot_s = max(0.020, min(0.220, float(dot_s)))
        self._release_s = max(0.004, min(0.016, 0.40 * dot_s))
        self._rx_att_k = self._coef(self._attack_s)
        self._rx_rel_k = self._coef(self._release_s)
        self._tx_att_k = self._rx_att_k
        self._tx_rel_k = self._rx_rel_k

    def rx_key(self, is_on: bool):
        self._rx_target = 1.0 if is_on else 0.0

    def tx_key(self, is_on: bool):
        self._tx_target = 1.0 if is_on else 0.0

    # ───────── internals
    def _map_vol(self, v: int) -> float:
        v = max(0, min(100, int(v)))
        return 0.001 + 0.50 * (v/100.0)

    def _coef(self, tau_s: float) -> float:
        tau_s = max(1e-4, float(tau_s))
        return 1.0 - math.exp(-1.0 / (tau_s * self._sr))

    def _callback(self, outdata, frames, time_info, status):
        # fase
        idx = np.arange(frames, dtype=np.float32)
        t = self._phase + self._twopi * self._tone * (idx / self._sr)
        self._phase = float((self._phase + self._twopi * self._tone * frames / self._sr) % self._twopi)
        wave = np.sin(t, dtype=np.float32)

        # envelope separati RX/TX
        env_rx = np.empty(frames, dtype=np.float32)
        env_tx = np.empty(frames, dtype=np.float32)
        rx_env = self._rx_env; tx_env = self._tx_env
        rx_att = self._rx_att_k; rx_rel = self._rx_rel_k
        tx_att = self._tx_att_k; tx_rel = self._tx_rel_k
        rx_tgt = self._rx_target; tx_tgt = self._tx_target

        for i in range(frames):
            rx_env += (rx_tgt - rx_env) * (rx_att if rx_tgt > rx_env else rx_rel)
            tx_env += (tx_tgt - tx_env) * (tx_att if tx_tgt > tx_env else tx_rel)
            env_rx[i] = rx_env; env_tx[i] = tx_env

        self._rx_env = float(rx_env); self._tx_env = float(tx_env)

        env = env_rx + 0.90 * env_tx
        sig = self._vol * env * wave

        outdata[:,0] = np.tanh(sig, dtype=np.float32)
