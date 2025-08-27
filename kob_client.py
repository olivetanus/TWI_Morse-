# kob_client.py
import socket, struct, threading, time, numpy as np

# audio opzionale
try:
    import sounddevice as sd
except Exception:
    sd = None

# --- KOB protocol (come sul server) ---
DIS = 2; DAT = 3; CON = 4; ACK = 5
shortRecord = struct.Struct('<HH')
longRecord  = struct.Struct('<H2x128s20x204xI128s8x')

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
    Un solo socket/identità:
      • audio + S-meter sul canale CENTRALE
      • 'scansione leggera' sugli altri 9 canali per aggiornare env e key_on
      • callback:
          on_env(wire:int, env:float[0..1])
          on_key(wire:int, is_on:bool)           # stato continuo
          on_center_level(s:float, over:float)   # S-meter
          on_center_element(sym:'.'|'-')         # dot/dash rilevati
    """
    # ──────────────────────────────────────────────────────────────
    def __init__(self, host: str, center_wire: int,
                 on_env=None, on_key=None,
                 on_center_level=None, on_center_element=None,
                 span=5, audio=True, callsign="TWI Client", version="TWI 0.9"):
        self.host   = _clean_host(host); self.port = 7890
        self._span  = int(span)
        self._center= int(center_wire)

        # callbacks
        self.on_env            = on_env
        self.on_key            = on_key
        self.on_center_level   = on_center_level
        self.on_center_element = on_center_element

        # stato socket / thread
        self.sock = None
        self._stop = threading.Event()
        self._rx_thr = None
        self._scan_thr = None
        self._hb_thr = None
        self._lock = threading.Lock()

        # identità
        self.callsign = callsign or "TWI Client"
        self.version  = version  or "TWI 0.9"

        # set canali
        self._wires = wires_around(self._center, self._span)
        self._current_wire = self._center

        # envelope e keying per TUTTI i 10 canali
        self._env       = {w: 0.0 for w in self._wires}   # energia visiva
        self._env_decay = 0.90
        self._key_on    = {w: False for w in self._wires}
        self._last_pkt  = {w: 0.0   for w in self._wires}
        self._key_start = {w: 0.0   for w in self._wires}

        # per il canale centrale: mappatura S-meter + stima punto
        self._s_emit = 0.0
        self._dot_est = 0.12     # s, punto stimato (adattivo)
        self._dot_min = 0.04
        self._dot_max = 0.30
        self._gap_factor_end  = 1.6    # fine elemento se gap > 1.6×dot
        self._dash_factor_thr = 1.5    # '-' se dur >= 1.5×dot
        self._idle_reset_s    = 2.5

        # audio
        self._audio = bool(audio)
        self._sr = 48000.0; self._tone = 600.0
        self._phase = 0.0
        self._gate  = 0.0           # 0..1
        self._vol   = 0.30
        self._sd_stream = None

    # ──────────────────────────────────────────────────────────────
    # API
    def start(self):
        self._open_socket_and_ident(self._center)
        self._stop.clear()
        self._rx_thr   = threading.Thread(target=self._rx_loop,   daemon=True); self._rx_thr.start()
        self._scan_thr = threading.Thread(target=self._scan_loop, daemon=True); self._scan_thr.start()
        self._hb_thr   = threading.Thread(target=self._heartbeat_loop, daemon=True); self._hb_thr.start()
        if self._audio: self._start_audio()

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
            # assicurati di tenere i dict allineati
            for d in (self._env, self._key_on, self._last_pkt, self._key_start):
                for w in list(d.keys()):
                    if w not in self._wires: d.pop(w, None)
                for w in self._wires:
                    d.setdefault(w, 0.0 if d is self._env or d is self._last_pkt or d is self._key_start else False)
            try:
                self.sock.sendto(shortRecord.pack(CON, self._center), (self.host, self.port))
            except: pass
            self._current_wire = self._center

    def set_volume(self, vol: int):
        v = max(0, min(100, int(vol)))
        self._vol = 0.001 + 0.5*(v/100.0)

    # ──────────────────────────────────────────────────────────────
    # Interni socket
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
        """
        Resta di più sul canale centrale (audio fluido + S-meter),
        salta veloce sugli altri per aggiornare env/key_on.
        """
        dwell_center = 0.020   # ~20 ms
        dwell_side   = 0.008   # ~8 ms
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
        """Riceve DAT; aggiorna env e key_on del wire sintonizzato."""
        last_decay = time.time()
        while not self._stop.is_set():
            now = time.time()
            # decadimento env + chiusura key_on per gap
            if now - last_decay >= 0.016:
                for w in list(self._env.keys()):
                    self._env[w] *= self._env_decay
                    # chiusura key_on se gap lungo
                    if self._key_on.get(w, False):
                        if (now - self._last_pkt.get(w, 0.0)) > (1.6*self._dot_est if w==self._center else 0.16):
                            self._key_on[w] = False
                            self._emit_key(w, False)
                self._emit_smeter_and_center_keying(now)
                last_decay = now

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
            self._env[w] = min(1.0, self._env[w] + (0.55 if w==self._center else 0.35))

            # packet → key_on True
            self._last_pkt[w] = time.time()
            if not self._key_on.get(w, False):
                self._key_on[w] = True
                self._key_start[w] = self._last_pkt[w]
                self._emit_key(w, True)

        # fine rx_loop

    # ──────────────────────────────────────────────────────────────
    # Emissioni verso UI/decoder
    def _emit_env_map(self):
        if self.on_env:
            for w, env in self._env.items():
                try: self.on_env(w, float(env))
                except: pass

    def _emit_key(self, wire, is_on):
        if self.on_key:
            try: self.on_key(int(wire), bool(is_on))
            except: pass

    def _emit_smeter_and_center_keying(self, now):
        """S-meter continuo + chiusura elemento puntino/linea sul canale centrale."""
        # S-meter (mappa env^0.7 → S0..S9)
        c = self._center
        s = 9.0 * (self._env.get(c, 0.0) ** 0.7)
        if abs(s - self._s_emit) >= 0.05:
            self._s_emit = s
            if self.on_center_level:
                try: self.on_center_level(s, 0.0)
                except: pass

        # chiusura elemento (solo canale centrale)
        if self._key_on.get(c, False):
            return
        # se attualmente OFF, verifica se appena finito un elemento
        last = self._last_pkt.get(c, 0.0); start = self._key_start.get(c, 0.0)
        if last > 0.0 and start > 0.0 and (now - last) > (self._gap_factor_end * self._dot_est):
            dur = max(0.0, last - start)
            if self._dot_min <= dur <= self._dot_max:
                self._dot_est = 0.85*self._dot_est + 0.15*dur
            sym = '.' if dur < (self._dash_factor_thr * self._dot_est) else '-'
            if self.on_center_element:
                try: self.on_center_element(sym)
                except: pass
            # reset start per il prossimo elemento
            self._key_start[c] = 0.0

        # invia env sempre (per waterfall)
        self._emit_env_map()

    # ──────────────────────────────────────────────────────────────
    # AUDIO
    def _start_audio(self):
        if sd is None: return
        try:
            self._phase = 0.0; self._gate = 0.0
            self._sd_stream = sd.OutputStream(
                samplerate=int(self._sr), channels=1, dtype='float32',
                blocksize=96, latency='low', callback=self._sd_callback
            ); self._sd_stream.start()
        except Exception:
            self._sd_stream = None

    def _stop_audio(self):
        if self._sd_stream is not None:
            try: self._sd_stream.stop(); self._sd_stream.close()
            except: pass
            self._sd_stream = None

    def _sd_callback(self, outdata, frames, time_info, status):
        now = time.time()
        # gate ON se centro è ON o ha ricevuto di recente
        c = self._center
        recent = (now - self._last_pkt.get(c, 0.0)) < 0.09
        target_gate = 1.0 if (self._key_on.get(c, False) or recent) else 0.0

        # inviluppo morbido (no echo)
        self._gate += (target_gate - self._gate) * (0.72 if target_gate > self._gate else 0.58)
        if self._gate < 1e-3:
            outdata[:] = 0.0; return

        w = 2.0*np.pi*self._tone/self._sr
        t = np.arange(frames, dtype=np.float32)
        sig = np.sin(self._phase + w*t)
        self._phase = (self._phase + w*frames) % (2*np.pi)
        out = (self._vol * self._gate * sig).astype(np.float32)
        outdata[:,0] = out
