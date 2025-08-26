# decoder.py
MORSE = {
    'A': '.-',   'B': '-...', 'C': '-.-.', 'D': '-..',  'E': '.',
    'F': '..-.', 'G': '--.',  'H': '....', 'I': '..',   'J': '.---',
    'K': '-.-',  'L': '.-..', 'M': '--',   'N': '-.',   'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.',  'S': '...',  'T': '-',
    'U': '..-',  'V': '...-', 'W': '.--',  'X': '-..-', 'Y': '-.--',
    'Z': '--..',
    '1': '.----','2': '..---','3': '...--','4': '....-','5': '.....',
    '6': '-....','7': '--...','8': '---..','9': '----.','0': '-----',
    '.': '.-.-.-',',': '--..--','?': '..--..','/': '-..-.','=': '-...-'
}
CODE_TO_CHAR = {v:k for k,v in MORSE.items()}

class AdaptiveMorseDecoder:
    def __init__(self):
        self.unit = 120.0
        self.on_ms = 0.0
        self.off_ms = 9999.0
        self.last_state = False
        self.symbol = ""
        self.text = ""

    def reset(self):
        self.on_ms = 0.0
        self.off_ms = 9999.0
        self.last_state = False
        self.symbol = ""
        self.text = ""

    def _emit_letter(self):
        if not self.symbol:
            return
        self.text += CODE_TO_CHAR.get(self.symbol, '?')
        self.symbol = ""

    def _emit_space(self):
        if self.text and not self.text.endswith(' '):
            self.text += ' '

    def feed(self, key_on: bool, dt_ms: float):
        if key_on:
            self.on_ms += dt_ms
            self.off_ms = 0.0
        else:
            self.off_ms += dt_ms
            self.on_ms = 0.0

        if (not key_on) and self.last_state:
            self.unit = 0.8*self.unit + 0.2*max(40.0, min(240.0, self.on_ms))
            if self.on_ms < 2.5*self.unit:
                self.symbol += '.'
            else:
                self.symbol += '-'

        if (not key_on) and self.off_ms > 6.5*self.unit:
            self._emit_letter(); self._emit_space()
        elif (not key_on) and self.off_ms > 2.5*self.unit:
            self._emit_letter()

        self.last_state = key_on
        out = self.text
        self.text = ""
        return out
