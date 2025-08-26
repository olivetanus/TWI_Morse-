# kob_client.py
import socket, struct, threading, time, numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

# --- KOB protocol ---
DIS = 2; DAT = 3; CON = 4; ACK = 5
shortRecord = struct.Struct('<HH')
longRecord  = struct.Struct('<H2x128s20x204xI128s8x')

# Tabella Morse base (A-Z, 0-9)
MORSE_TABLE = {
    ".-":"A","-...":"B","-.-.":"C","-..":"D",".":"E","..-.":"F","--.":"G","....":"H","..":"I",
    ".---":"J","-.-":"K",".-..":"L","--":"M","-.":"N","---":"O",".--.":"P","--.-":"Q",".-.":"R",
    "...":"S","-":"T","..-":"U","...-":"V",".--":"W","-..-":"X","-.--":"Y","--..":"Z",
    "-----":"0",".----":"1","..---":"2","...--":"3","....-":"4",".....":"5","-....":"6",
    "--...":"7","---..":"8","----.":"9"
}

def _clean_host(h: str) -> str:
    h = (h or "").strip()
    if h.startswith("http://"):  h = h[7:]
    if h.startswith("https://"): h = h[8:]
    if "/" in h: h = h.split("/")[0]
    return h

def wires_around(center: int, span: int = 5):
    center = int(center)
    start = max(1, center - span)
    return list(range(start, start + 2*span + 1))

class KOBClient:
    """
    Scanner a singolo socket:
      - 1 sola identità (callsign) nella tabella del server
      - scansiona 10 canali (±5) con dwell breve
      - callback:
         on_env(wire, env_float_0_1)
         on_center_level(s_units, over_db)
         on_center_keying(is_on_bool)
         on_center_element(str)  -> '.', '-', 'A'..'Z', '0'..'9', ' ' (spazio)
    """

    def __init__(self, host: str, center_wire: int,
                 on_env, on_center_level, on_center_keying, on_center_element=None,
                 span=5, audio=True, callsign="TWI Client", version="TWI 0.9"),
                 scan=True):   
        self.host   = _clean_host(host); self.port = 7890
        self._span  = int(span)
        self._center= int(center_wire)

        self.on_env            = on_env
        self.on_center_level   = on_center_level
        self.on_center_keying  = on_center_keying
        self.on_center_element = on_center_element

        self.sock = None
        self._stop = threading.Event()
        self._rx_thr = None
        self._scan_thr = None
        self._hb_thr = None
        self._lock = threading.Lock()

        self.callsign = callsign or "TWI Client"
        self.version  = version or "TWI 0.9"

        self._wires = wires_around(self._center, self._span)
        self._current_wire = self._wires[0]

        # envelope per i 10 canali
        self._env = {w: 0.0 for w in self._wires}
        self._env_decay = 0.90
        self._center_env = 0.0
        self._s_emit = 0.0

        # —— KEYING & TIMING (auto-adattivo punto/linea) ——
        self._key_on     = False      # stato tasto ON/OFF
        self._last_pkt   = 0.0        # ultimo pacchetto ricevuto sul canale centrale
        self._key_start  = 0.0        # istante inizio elemento
        self._idle_start = 0.0        # per reset stima dopo inattività

        # stima durata del punto (in secondi): seed ~ 0.12s (10–12 WPM)
        self._dot_est = 0.12
        self._dot_min = 0.04
        self._dot_max = 0.30

        # soglie (in multipli del punto) per fine elemento e per linea
        self._gap_factor_end  = 1.6    # gap > 1.6×dot ⇒ chiudi elemento
        self._dash_factor_thr = 1.5    # durata ≥ 1.5×dot ⇒ linea
        self._reset_idle_s    = 2.5    # se inattivo >2.5s, reset parziale stima

        # buffer simboli per comporre la lettera
        self._sym_buf = ""            # accumula '.' e '-' dell'attuale lettera

        # —— AUDIO ——
        self._audio = bool(audio)
        self._sr = 48000.0
        self._tone = 600.0
        self._phase = 0.0
        self._gate  = 0.0             # 0..1 (envelope audio)
        self._vol   = 0.28            # 0..1 (dal knob volume)
        self._sd_stream = None
        self._scan_enabled = bool(scan)


    # ================= API =================
    def start(self):
        self._open_socket_and_ident(self._center)
        self._stop.clear()
                self._rx_thr = threading.Thread(target=self._rx_loop, daemon=True);       self._rx_thr.start()
        if self._scan_enabled:
            self._scan_thr = threading.Thread(target=self._scan_loop, daemon=True);   self._scan_thr.start()
        self._hb_thr = threading.Thread(target=self._heartbeat_loop, daemon=True);self._hb_thr.start()


    def stop(self):
        self._stop.set()
        try: self.sock.sendto(shortRecord.pack(DIS, 0), (self.host, self.port))
        except: pass
        for th in (self._rx_thr, self._scan_thr, self._hb_thr):
            try:
                if th and th.is_alive(): th.join(timeout=0.5)
            except: pass
        self._stop_audio()
        try: self.sock.close()
        except: pass
        self.sock = None

        def set_center_wire(self, new_center: int):
        with self._lock:
            self._center = int(new_center)
            self._wires = wires_around(self._center, self._span)
            self._env = {w: self._env.get(w, 0.0) for w in self._wires}
            try:
                self.sock.sendto(shortRecord.pack(CON, self._center), (self.host, self.port))
            except: pass
            # Se non scansioniamo, teniamo puntato _current_wire sul centro
            self._current_wire = self._center
            self._center_env = 0.0
            self._sym_buf = ""
            self._key_on = False


    def set_audio_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled and not self._audio:
            self._audio = True;  self._start_audio()
        elif (not enabled) and self._audio:
            self._audio = False; self._stop_audio()

    def set_volume(self, vol: int):
        v = max(0, min(100, int(vol)))
        self._vol = 0.001 + 0.5*(v/100.0)  # 0.001 .. 0.501

    # ============== internals ==============
    def _open_socket_and_ident(self, wire: int):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.05)
        try:
            self.sock.sendto(shortRecord.pack(CON, wire), (self.host, self.port))
        except: pass
        self._send_ident(self.callsign, self.version)

    def _send_ident(self, stn_id, stn_ver):
        pkt = bytearray(496)
        struct.pack_into('<H', pkt, 0, DAT)
        sid = (stn_id or '').encode('ascii', 'ignore')[:127]
        sid = sid + b'\x00'*(128-len(sid)); pkt[4:4+128] = sid
        struct.pack_into('<I', pkt, 356, 0)
        ver = (stn_ver or '').encode('ascii', 'ignore')[:127]
        ver = ver + b'\x00'*(128-len(ver)); pkt[360:360+128] = ver
        try: self.sock.sendto(bytes(pkt), (self.host, self.port))
        except: pass

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            time.sleep(25.0)
            try:
                self.sock.sendto(shortRecord.pack(CON, self._center), (self.host, self.port))
                self._send_ident(self.callsign, self.version)
            except: pass

    def _scan_loop(self):
        # dwell leggermente più lunghi al centro
        dwell_center = 0.018
        dwell_side   = 0.010
        while not self._stop.is_set():
            wires = list(self._wires)
            center = self._center
            for w in wires:
                if self._stop.is_set(): break
                try:
                    self.sock.sendto(shortRecord.pack(CON, w), (self.host, self.port))
                except: pass
                self._current_wire = w
                time.sleep(dwell_center if w == center else dwell_side)

    def _rx_loop(self):
        last_tick = time.time()
        while not self._stop.is_set():
            now = time.time()
            # decadimento envelope + callback periodica ~60 Hz
            if now - last_tick >= 0.016:
                for w in list(self._env.keys()):
                    self._env[w] *= self._env_decay
                self._center_env *= self._env_decay
                self._emit_env_map()
                self._emit_smeter_and_keying()
                last_tick = now
            try:
                data, _ = self.sock.recvfrom(600)
            except socket.timeout:
                continue
            except Exception:
                continue

            if len(data) < longRecord.size:
                continue
            try:
                cmd, _, _, _ = longRecord.unpack(data[:longRecord.size])
            except Exception:
                continue
            if cmd != DAT:
                continue

            w = self._current_wire
            # aggiornamento envelope canale corrente
            self._env[w] = min(1.0, self._env[w] + 0.40)

            if w == self._center:
                # potenziamo l'envelope del canale centrale (per S-meter)
                self._center_env = min(1.0, self._center_env + 0.60)
                self._on_center_packet()

    # ============== keying / decoding ==============
    def _on_center_packet(self):
        now = time.time()
        self._last_pkt = now
        self._idle_start = now

        if not self._key_on:
            self._key_on = True
            self._key_start = now
            try:
                if self.on_center_keying:
                    self.on_center_keying(True)
            except: pass

        self._emit_env_map()
        self._emit_smeter_and_keying()

    def _emit_env_map(self):
        try:
            if self.on_env:
                for w, env in self._env.items():
                    self.on_env(w, float(env))
        except: pass

    def _emit_smeter_and_keying(self):
        # S-meter (curva un po' compressa per feeling radio)
        s = 9.0 * (self._center_env ** 0.7)
        if abs(s - self._s_emit) >= 0.05:
            self._s_emit = s
            try:
                if self.on_center_level:
                    self.on_center_level(s, 0.0)
            except: pass

        now = time.time()
        gap = now - self._last_pkt

        # chiusura elemento: se il gap supera 1.6×dot
        if self._key_on and gap > (self._gap_factor_end * self._dot_est):
            dur = max(0.0, self._last_pkt - self._key_start)  # durata ON
            self._key_on = False

            # aggiorna stima dot se plausibile
            if self._dot_min <= dur <= self._dot_max:
                self._dot_est = 0.85*self._dot_est + 0.15*dur

            # punto o linea
            sym = '.' if dur < (self._dash_factor_thr * self._dot_est) else '-'
            self._sym_buf += sym
            try:
                if self.on_center_keying:
                    self.on_center_keying(False)
                if self.on_center_element:
                    # emetti anche il simbolo “raw” per chi vuole visualizzarlo
                    self.on_center_element(sym)
            except: pass

        # spazi: lettera e parola
        if not self._key_on:
            # fine lettera se gap ≥ 3×dot
            if gap >= (3.0 * self._dot_est) and self._sym_buf:
                letter = MORSE_TABLE.get(self._sym_buf, '?')
                self._sym_buf = ""
                try:
                    if self.on_center_element:
                        self.on_center_element(letter)
                except: pass
            # spazio tra parole se gap ≥ 7×dot
            if gap >= (7.0 * self._dot_est):
                try:
                    if self.on_center_element:
                        self.on_center_element(" ")
                except: pass

        # reset dolce della stima se inattivi a lungo
        idle = now - self._idle_start
        if idle > self._reset_idle_s:
            self._dot_est = min(self._dot_max, 0.5*self._dot_est + 0.5*0.12)

    # ================= AUDIO =================
    def _start_audio(self):
        if sd is None:
            return
        try:
            self._phase = 0.0
            self._gate  = 0.0
            self._sd_stream = sd.OutputStream(
                samplerate=int(self._sr),
                channels=1,
                dtype='float32',
                blocksize=96,      # ~2 ms a 48 kHz (bassa latenza)
                latency='low',
                callback=self._sd_callback
            )
            self._sd_stream.start()
        except Exception:
            self._sd_stream = None

    def _stop_audio(self):
        if self._sd_stream is not None:
            try:
                self._sd_stream.stop()
                self._sd_stream.close()
            except: pass
            self._sd_stream = None

    def _sd_callback(self, outdata, frames, time_info, status):
        # porta il gate a 1 se key_on recente (hold ~90ms), altrimenti verso 0
        now = time.time()
        target_gate = 1.0 if (self._key_on or (now - self._last_pkt) < 0.09) else 0.0
        alpha_up, alpha_dn = 0.72, 0.58
        if target_gate > self._gate:
            self._gate += (target_gate - self._gate) * alpha_up
        else:
            self._gate += (target_gate - self._gate) * alpha_dn

        if self._gate < 1e-3:
            outdata[:] = 0.0
            return

        w = 2.0*np.pi*self._tone/self._sr
        t = np.arange(frames, dtype=np.float32)
        sig = np.sin(self._phase + w*t)
        self._phase = (self._phase + w*frames) % (2*np.pi)

        out = (self._vol * self._gate * sig).astype(np.float32)
        outdata[:,0] = out
