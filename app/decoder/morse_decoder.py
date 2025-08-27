# app/decoder/morse_decoder.py
from __future__ import annotations
import time
from collections import deque

MORSE_TO_ASCII = {
    '.-':'A','-...':'B','-.-.':'C','-..':'D','.':'E','..-.':'F','--.':'G','....':'H','..':'I',
    '.---':'J','-.-':'K','.-..':'L','--':'M','-.':'N','---':'O','.--.':'P','--.-':'Q','.-.':'R',
    '...':'S','-':'T','..-':'U','...-':'V','.--':'W','-..-':'X','-.--':'Y','--..':'Z',
    '-----':'0','.----':'1','..---':'2','...--':'3','....-':'4','.....':'5','-....':'6','--...':'7','---..':'8','----.':'9',
    '.-.-.-':'.','--..--':',','..--..':'?','.-..-.':'"','.-.-.':'+','-....-':'-','-..-.':'/','-.--.':'(', '-.--.-':')',
    '...-..-':'$','.--.-.':'@', '.-...':'&', '---...':':','-.-.-.':';'
}

class AdaptiveDecoder:
    """
    Decoder CW adattivo con:
    - stima 'dit' (media dei mark brevi)
    - hint dal player (hint_dot_ms, force_gap_ms)
    - chiusura lettere/parole dinamica
    """
    def __init__(self, on_symbol=None, on_char=None, on_text=None):
        self.on_symbol = on_symbol
        self.on_char = on_char
        self.on_text = on_text

        self._down_ts = None
        self._up_ts = None
        self._symbols: list[str] = []
        self._dit_hist = deque(maxlen=24)
        self._dit = 0.060

        self._INTRA = 1.5
        self._CHAR  = 3.5
        self._WORD  = 6.5

        self._MIN_SEG = 0.010
        self._MAX_SEG = 1.200

    # --- hint dalla pipeline a tempi certi ---
    def hint_dot_ms(self, ms: float):
        dur = float(ms)/1000.0
        if dur <= 0 or dur > self._MAX_SEG: return
        if dur <= 2.0 * self._dit:
            self._dit_hist.append(dur)
            self._dit = max(0.020, min(0.150, sum(self._dit_hist) / max(1, len(self._dit_hist))))

    def force_gap_ms(self, ms: float):
        off_dur = float(ms)/1000.0
        self._consume_space(off_dur)

    # --- API: key edges classici (compat) ---
    def key_edge(self, is_down: bool, ts: float | None = None):
        if ts is None:
            ts = time.time()
        if is_down:
            if self._up_ts is not None:
                off_dur = max(0.0, min(self._MAX_SEG, ts - self._up_ts))
                self._consume_space(off_dur)
            self._down_ts = ts
        else:
            if self._down_ts is None:
                return
            on_dur = max(0.0, min(self._MAX_SEG, ts - self._down_ts))
            if on_dur >= self._MIN_SEG:
                self._classify_mark(on_dur)
            self._down_ts = None
            self._up_ts = ts

    def idle_tick(self, now_ts: float | None = None):
        if self._up_ts is None: return
        if now_ts is None: now_ts = time.time()
        off_dur = now_ts - self._up_ts
        if off_dur >= self._WORD * self._dit:
            self._flush_char()
            if self.on_text: self.on_text(' ')
        elif off_dur >= self._CHAR * self._dit:
            self._flush_char()

    def get_wpm(self) -> float:
        return 1.2 / max(1e-6, self._dit)

    # --- interni ---
    def _classify_mark(self, dur: float):
        if dur <= 2.0 * self._dit:
            self._dit_hist.append(dur)
            self._dit = max(0.020, min(0.150, sum(self._dit_hist) / max(1, len(self._dit_hist))))
        symbol = '.' if dur < 2.4 * self._dit else '-'
        self._symbols.append(symbol)
        if self.on_symbol: self.on_symbol(symbol)

    def _consume_space(self, off_dur: float):
        if off_dur < self._INTRA * self._dit:
            return
        elif off_dur < self._CHAR * self._dit:
            self._flush_char()
        else:
            self._flush_char()
            if off_dur >= self._WORD * self._dit:
                if self.on_text: self.on_text(' ')

    def _flush_char(self):
        if not self._symbols: return
        code = ''.join(self._symbols)
        ch = MORSE_TO_ASCII.get(code, '□')
        if self.on_char: self.on_char(ch)
        if self.on_text: self.on_text(ch)
        self._symbols.clear()

# wrapper compat (API feed/tick) usato da main_app
class AdaptiveCWDecoder:
    def __init__(self, on_symbol=None, on_text=None):
        self._dec = AdaptiveDecoder(on_symbol=on_symbol, on_char=None, on_text=on_text)
    def feed(self, is_on: bool, t: float): self._dec.key_edge(bool(is_on), t)
    def tick(self, t: float): self._dec.idle_tick(t)
    def get_wpm(self) -> float: return self._dec.get_wpm()
    def hint_dot_ms(self, ms: float): self._dec.hint_dot_ms(ms)
    def force_gap_ms(self, ms: float): self._dec.force_gap_ms(ms)
