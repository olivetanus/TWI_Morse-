# cw/cw_tx_encoder.py
"""
Encoder TX: converte input locali (pressioni/rilasci) in eventi temporali per il client.
Modalità: manuale (paddle/spacebar) — calcola durate reali; opzionale auto-keyer testo (TODO).
Callback: on_tx_event(is_on: bool, t_now: float).
"""
import time
from typing import Callable

class TxEncoder:
    def __init__(self, on_tx_event:Callable[[bool,float],None]):
        self.on_tx_event = on_tx_event
        self._key_on = False

    def key_down(self):
        if not self._key_on:
            self._key_on = True
            self.on_tx_event(True, time.time())

    def key_up(self):
        if self._key_on:
            self._key_on = False
            self.on_tx_event(False, time.time())

    # placeholder per invio testo (auto-keyer)
    def send_text(self, text:str):
        # TODO: generare sequenza di key_down/key_up basata su WPM impostato
        pass
