# cw/activity_probe.py
import numpy as np
import random
from collections import defaultdict
from time import perf_counter

class ActivityProbe:
    """
    Laterali CW realistici (punti/linee) SOLO se il canale è realmente attivo.
    - key_on=True  -> impulso brillante (evento reale, breve hold)
    - env>=thr     -> generatore dot/dash plausibile (nessun riempimento continuo)
    - canali muti  -> puliti
    """
    def __init__(self, center_wire:int, scenic:bool=True, env_threshold:float=0.03,
                 scenic_mode:str="active", scenic_prob_active:float=0.42):
        self.center = int(center_wire)
        self.scenic = bool(scenic)
        self.env_threshold = float(env_threshold)
        self.scenic_mode = (scenic_mode or "active").lower()
        self.scenic_prob_active = float(scenic_prob_active)

        self.env = defaultdict(float)            # wire -> env [0..1]
        self.key = defaultdict(bool)             # wire -> ON/OFF latch
        self._key_hold_until = defaultdict(float)  # breve hold solo per key_on
        self._cols = {}                           # wire -> x pixel

        self._rng = random.Random(12345)
        self._phase = defaultdict(int)           # 0=GAP, 1=ON
        self._run_len = defaultdict(int)

    def set_center(self, wire:int):
        self.center = int(wire)

    def set_columns(self, wire_to_x:dict):
        self._cols = dict(wire_to_x)

    def update_env(self, wire:int, env:float, key_on:bool=None):
        w = int(wire)
        self.env[w] = float(env)
        now = perf_counter()

        if key_on is True:
            self.key[w] = True
            # piccolo hold per far “respirare” l’impulso reale
            self._key_hold_until[w] = max(self._key_hold_until[w], now + 0.22)
        elif key_on is False:
            self.key[w] = False

        # NOTA: NON estendiamo la vita usando solo env (niente latch da env).

    def _advance_active_generator(self, w:int):
        if self._run_len[w] <= 0:
            if self._phase[w] == 0:
                if self._rng.random() < self.scenic_prob_active:
                    self._phase[w] = 1
                    is_dot = self._rng.random() < 0.65
                    self._run_len[w] = self._rng.randint(1, 2) if is_dot else self._rng.randint(3, 5)
                else:
                    self._run_len[w] = self._rng.randint(1, 3)
            else:
                self._phase[w] = 0
                self._run_len[w] = self._rng.randint(1, 3)
        self._run_len[w] -= 1

    def _draw_pulse(self, line:np.ndarray, x:int, width:int, v:float):
        v = float(np.clip(v, 0.0, 1.0))
        half = self._rng.choice((1, 2))  # 3px o 5px
        x1 = max(0, x - half); x2 = min(width, x + half + 1)
        if x2 > x1:
            ramp = np.linspace(0.6, 1.0, num=(half+1), dtype=np.float32)
            prof = np.concatenate([ramp[:-1], ramp[::-1]]) if (x2-x1)==2*half+1 else np.ones(x2-x1, dtype=np.float32)
            line[x1:x2] = np.maximum(line[x1:x2], v * prof[:(x2-x1)])

    def next_line(self, width:int):
        line = np.full(width, 0.035, dtype=np.float32)
        now = perf_counter()

        for w, x in self._cols.items():
            if w == self.center:
                continue

            env   = float(self.env.get(w, 0.0))
            k_on  = bool(self.key.get(w, False))
            alive = k_on or (now < self._key_hold_until[w]) or (env >= self.env_threshold)

            if not alive:
                continue

            if k_on or (now < self._key_hold_until[w]):
                # impulso reale: brillante
                self._draw_pulse(line, x, width, v=0.90)
                continue

            # attività “env” reale: puntini/linee plausibili
            if self.scenic and self.scenic_mode == "active":
                self._advance_active_generator(w)
                if self._phase[w] == 1:
                    v = 0.22 + 0.65 * max(env, 0.05)
                    self._draw_pulse(line, x, width, v=v)

        return line
