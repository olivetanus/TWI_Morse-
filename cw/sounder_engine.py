# cw/sounder_engine.py
import numpy as np
import sounddevice as sd
import threading
import time

class SounderEngine:
    """
    Tono CW pulito, gate on/off:
    - key_down(True)  -> parte ADS (attack/decay breve) e SUONA
    - key_down(False) -> parte R (release) e SILENZIO
    NIENTE tono di base nei vuoti: zero se il gate è chiuso.
    """
    def __init__(self, samplerate=48000, freq=600.0, volume=0.55,
                 attack=0.004, decay=0.006, release=0.010):
        self.fs = samplerate
        self.freq = float(freq)
        self.vol = float(volume)
        self.a = float(attack)
        self.d = float(decay)
        self.r = float(release)

        self._phase = 0.0
        self._gate = 0.0        # 0..1 (target)
        self._env  = 0.0        # envelope attuale
        self._target_on = False
        self._lock = threading.Lock()

        self._stream = sd.OutputStream(
            samplerate=self.fs, channels=1, dtype='float32',
            callback=self._cb, blocksize=0, latency='low'
        )
        self._stream.start()

    def close(self):
        try:
            self._stream.stop(); self._stream.close()
        except Exception:
            pass

    def set_volume(self, v: float):
        self.vol = max(0.0, min(1.0, float(v)))

    def set_freq(self, f: float):
        self.freq = float(f)

    def key_down(self, is_down: bool):
        with self._lock:
            self._target_on = bool(is_down)
            # target di envelope: 1 se ON, 0 se OFF
            self._gate = 1.0 if is_down else 0.0

    # ====== callback audio ======
    def _cb(self, outdata, frames, time_info, status):
        if status:
            # underrun/overrun: produci comunque silenzio/tono coerente
            pass

        t = (np.arange(frames, dtype=np.float32) + 0) / self.fs
        # Aggiorna envelope con un semplice AD/R “continuo”
        # costanti per step (dipendono da fs)
        atk_step = (1.0 / max(1, int(self.a * self.fs)))
        dcy_step = (1.0 / max(1, int(self.d * self.fs)))
        rel_step = (1.0 / max(1, int(self.r * self.fs)))

        with self._lock:
            target = self._gate

        env = np.empty(frames, dtype=np.float32)
        e = self._env
        for i in range(frames):
            if target >= 0.5:
                # salita veloce fino ~1, poi un pelo di decay verso ~0.9
                if e < 0.98:
                    e = min(1.0, e + atk_step)
                else:
                    e = max(0.90, e - dcy_step*0.15)
            else:
                # release a zero
                e = max(0.0, e - rel_step)
            env[i] = e
        self._env = float(e)

        # Oscillatore: **solo** se envelope > 0 → nessun tono nei vuoti
        # (phase continua per evitare clic)
        phase_inc = 2.0 * np.pi * self.freq / self.fs
        ph = self._phase + phase_inc * np.arange(frames, dtype=np.float32)
        self._phase = float((self._phase + phase_inc * frames) % (2*np.pi))

        wave = np.sin(ph, dtype=np.float32) * env * self.vol
        outdata[:, 0] = wave
