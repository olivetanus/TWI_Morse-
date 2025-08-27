# cw/cw_decoder.py
"""
AdaptiveCWDecoder
-----------------
Decoder CW che si adatta automaticamente alla velocità del telegrafista
stimando la durata del "dot" dai tempi ON (tasto premuto) e OFF (rilasciato).

Uso:
  dec = AdaptiveCWDecoder(on_symbol=cb_sym, on_text=cb_text)
  dec.feed(is_on: bool, t: float)  # chiamare ad ogni transizione (True=key down, False=key up)
  dec.tick(t: float)               # chiamare periodicamente per chiudere caratteri/parole a fine gap

Note:
- Funziona a meraviglia con CWCom perché riceviamo eventi di keying affidabili.
- Non analizza l'audio: lavora SOLO su transizioni logiche (on/off).
"""

from time import perf_counter
from statistics import median

# Mappa Morse ITU standard (lettere, numeri, punteggiatura base)
MORSE = {
    ".-":"A", "-...":"B", "-.-.":"C", "-..":"D", ".":"E", "..-.":"F",
    "--.":"G", "....":"H", "..":"I", ".---":"J", "-.-":"K", ".-..":"L",
    "--":"M", "-.":"N", "---":"O", ".--.":"P", "--.-":"Q", ".-.":"R",
    "...":"S", "-":"T", "..-":"U", "...-":"V", ".--":"W", "-..-":"X",
    "-.--":"Y", "--..":"Z",
    "-----":"0", ".----":"1", "..---":"2", "...--":"3", "....-":"4",
    ".....":"5", "-....":"6", "--...":"7", "---..":"8", "----.":"9",
    ".-.-.-":".", "--..--":",", "..--..":"?", ".----.":"'", "-.-.--":"!",
    "-..-.":"/", "-.--.":"(", "-.--.-":")", ".-...":"&", "---...":":",
    "-.-.-.":";", "-...-":"=", ".-.-.":"+","-....-":"-", "..--.-":"_",
    ".-..-.":"\"", ".--.-.":"@", "...-..-":"$", ".-.-":"Ä", "---.":"Ö", "..--":"Ü"
}

class AdaptiveCWDecoder:
    def __init__(self, on_symbol=None, on_text=None):
        self.on_symbol = on_symbol    # callback per ".", "-" (opzionale)
        self.on_text   = on_text      # callback per caratteri/testo/space

        # Stato
        self._last_state = False      # False=OFF, True=ON
        self._last_time  = 0.0        # timestamp dell'ultima transizione
        self._buf        = ""         # buffer di simboli del carattere corrente (".", "-")

        # Stima adattiva della dot length (secondi)
        self._dot = 0.060             # seed ragionevole (≈ 20 WPM)
        self._on_samples = []         # piccola finestra per mediana di ON brevi

        # Limiti/glitch filter
        self._MIN_SEG = 0.012         # ignora segmenti ridicolmente brevi
        self._MAX_SEG = 1.200         # taglia segmenti absurdamente lunghi

        # Fattori standard ITU
        self._DASH_THR   = 2.4        # soglia dash = dur >= 2.4·dot
        self._ICHAR_GAP  = 1.5        # fine lettera se OFF >= 1.5·dot (≈ tra 1 e 3)
        self._WORD_GAP   = 6.0        # spazio parola se OFF >= 6·dot (≈7, conservativo)

        # Inizializza il tempo di riferimento
        self.reset_time()

    # ---------- API ----------
    def reset(self):
        self._buf = ""
        self._on_samples.clear()

    def reset_time(self):
        self._last_time = perf_counter()

    def get_wpm(self) -> float:
        # Formula approssimata: dot = 1.2 / WPM  →  WPM = 1.2 / dot
        if self._dot <= 1e-6: return 0.0
        return 1.2 / self._dot

    def feed(self, is_on: bool, t_now: float):
        """
        Chiamare su OGNI transizione (toggle) di key:
        - is_on=True  : passaggio OFF→ON
        - is_on=False : passaggio ON→OFF
        t_now = timestamp (perf_counter)
        """
        # misura la durata dello stato precedente
        dt = max(0.0, min(self._MAX_SEG, t_now - self._last_time))
        self._last_time = t_now

        if self._last_state:  # stavamo in ON, ora arriva OFF → elemento CW
            self._handle_on_duration(dt)
        else:                 # stavamo in OFF, ora arriva ON → gap
            self._handle_off_duration(dt)

        self._last_state = bool(is_on)

    def tick(self, t_now: float):
        """
        Chiamare periodicamente (es. ogni frame UI) per chiudere
        caratteri o parole quando il key resta OFF a lungo.
        """
        dt = max(0.0, min(self._MAX_SEG, t_now - self._last_time))
        if self._last_state:  # se siamo in ON, niente: l'elemento non è finito
            return
        # siamo in OFF: verifica gap per fine lettera/parola
        if dt >= self._WORD_GAP * self._dot:
            self._commit_char()
            self._emit_text(" ")
            self._last_time = t_now  # evita ripetizioni
        elif dt >= self._ICHAR_GAP * self._dot:
            self._commit_char()
            self._last_time = t_now

    # ---------- Interni ----------
    def _handle_on_duration(self, dur: float):
        if dur < self._MIN_SEG:
            return  # glitch

        # Aggiorna la stima del DOT: usa solo gli ON brevi (dot probabili)
        # Shortlist: ON < 2.0·dot ~ dot/dash boundary robusto
        if dur <= 2.0 * self._dot:
            self._on_samples.append(dur)
            if len(self._on_samples) > 7:
                self._on_samples.pop(0)
            # mediana + EMA: reattivo ma stabile
            dot_med = median(self._on_samples)
            self._dot = 0.75 * self._dot + 0.25 * dot_med
            # clamp dot in range plausibile 10–45 WPM
            self._dot = max(0.026, min(0.120, self._dot))

        # Classifica elemento
        sym = "." if dur < (self._DASH_THR * self._dot) else "-"
        self._buf += sym
        if self.on_symbol:
            try: self.on_symbol(sym)
            except: pass

    def _handle_off_duration(self, dur: float):
        if dur < self._MIN_SEG:
            return  # glitch

        # Fine lettera/parola secondo gap
        if dur >= self._WORD_GAP * self._dot:
            self._commit_char()
            self._emit_text(" ")
        elif dur >= self._ICHAR_GAP * self._dot:
            self._commit_char()

    def _commit_char(self):
        if not self._buf:
            return
        ch = MORSE.get(self._buf, "?")
        self._buf = ""
        self._emit_text(ch)

    def _emit_text(self, txt: str):
        if not txt:
            return
        if self.on_text:
            try: self.on_text(txt)
            except: pass
