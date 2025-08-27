# net/cwcom_client.py  — v4.3
"""
Client CWCom/KOB:
- Tenta di estrarre per-packet la sequenza temporale (+mark / -space) in ms.
- Se i tempi non sono affidabili, torna al fallback "per-arrival" (gating).
- Emette SEMPRE on_center_keying(True/False) per i fronti e:
    on_center_element('.'|'-') a fine mark
    on_center_mark_ms(ms) / on_center_space_ms(ms) se i tempi sono noti
    on_center_level(level, over) ~60 Hz per S-meter

- Laterali: stima envelope/burst per mostrare attività sui 5± canali.
"""

import socket, struct, threading, time, select
from time import perf_counter, sleep
from collections import deque

DIS = 2; DAT = 3; CON = 4

def _clean_host(h: str) -> str:
    h = (h or "").strip()
    if h.startswith("http://"):  h = h[7:]
    if h.startswith("https://"): h = h[8:]
    if "/" in h: h = h.split("/")[0]
    return h

def wires_around(center: int, span: int = 5):
    center = int(center)
    start  = max(1, center - span)
    return list(range(start, start + 2*span + 1))

# ─────────────────────────────────────────────────────────────────────────────
class TimingPlayer:
    """Riproduce una lista di durate (+mark / -space) e genera fronti + callback."""
    def __init__(self, on_key, on_elem, on_level,
                 on_mark_ms=None, on_space_ms=None,
                 get_dot_est=None):
        self._q = deque()
        self._stop = threading.Event()
        self._thr  = None

        self._on_key     = on_key
        self._on_elem    = on_elem
        self._on_level   = on_level
        self._on_mark_ms = on_mark_ms
        self._on_space_ms= on_space_ms
        self._get_dot    = get_dot_est or (lambda: 0.06)

        self._gate_on = False

    def start(self):
        if self._thr and self._thr.is_alive(): return
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()

    def stop(self):
        self._stop.set()
        try:
            if self._thr and self._thr.is_alive(): self._thr.join(timeout=0.5)
        except: pass
        self._thr = None
        if self._gate_on:
            self._gate_on = False
            try: self._on_key(False)
            except: pass

    def clear(self): self._q.clear()
    def enqueue(self, seq_ms):
        if seq_ms: self._q.append(list(seq_ms))

    def _sleep_emit_level(self, ms):
        end = perf_counter() + (ms/1000.0)
        next_emit = perf_counter()
        while True:
            now = perf_counter()
            if now >= end: break
            if now >= next_emit:
                try: self._on_level(1.0 if self._gate_on else 0.0, 0.0)
                except: pass
                next_emit = now + 0.016
            remain = end - now
            if remain > 0.006: sleep(0.004)
            elif remain > 0.0: sleep(remain)

    def _run(self):
        idle_emit = perf_counter()
        while not self._stop.is_set():
            if not self._q:
                now = perf_counter()
                if now - idle_emit >= 0.05:
                    try: self._on_level(0.0, 0.0)
                    except: pass
                    idle_emit = now
                sleep(0.002); continue

            seq = self._q.popleft()
            # Ogni elemento di seq è un intero (ms), positivo (mark) o negativo (space)
            for v in seq:
                if self._stop.is_set(): break
                if v == 0: continue

                if v > 0:
                    # MARK ON
                    if not self._gate_on:
                        self._gate_on = True
                        try: self._on_key(True)
                        except: pass
                    dur_ms = float(v)
                    if self._on_mark_ms:
                        try: self._on_mark_ms(dur_ms)
                        except: pass
                    self._sleep_emit_level(dur_ms)
                    # classifica elemento al termine del mark
                    dot = max(0.02, min(0.20, float(self._get_dot())))
                    sym = '.' if (dur_ms/1000.0) < (2.5 * dot) else '-'
                    try: self._on_elem(sym)
                    except: pass
                else:
                    # SPACE ⇒ GATE OFF subito e silenzio
                    if self._gate_on:
                        self._gate_on = False
                        try: self._on_key(False)
                        except: pass
                    sp_ms = abs(float(v))
                    if self._on_space_ms:
                        try: self._on_space_ms(sp_ms)
                        except: pass
                    self._sleep_emit_level(sp_ms)

# ─────────────────────────────────────────────────────────────────────────────
class CWComClient:
    def __init__(self, host: str, center_wire: int,
                 on_env=None, on_key=None,
                 on_center_level=None, on_center_element=None,
                 on_center_keying=None,
                 on_center_mark_ms=None, on_center_space_ms=None,
                 span=5, audio=False, callsign="TWI Client", version="TWI CWCom 4.3"):
        self.host   = _clean_host(host); self.port = 7890
        self._span  = max(0, int(span))
        self._center= int(center_wire)

        self.on_env = on_env
        self.on_key = on_key
        self.on_center_level   = on_center_level
        self.on_center_element = on_center_element
        self.on_center_keying  = on_center_keying
        self.on_center_mark_ms  = on_center_mark_ms
        self.on_center_space_ms = on_center_space_ms

        self.callsign = callsign or "TWI Client"
        self.version  = version  or "TWI CWCom 4.3"

        self._stop = threading.Event()

        self.center_sock = None
        self._rx_center_thr = None

        self._scan_wires = wires_around(self._center, self._span)
        self.scan_socks = {}
        self._s2wire    = {}
        self._scan_thr  = None

        self._hb_thr = None

        self._env        = {w: 0.0 for w in self._scan_wires}
        self._env_decay  = 0.92
        self._key_on     = {w: False for w in self._scan_wires}
        self._last_dat   = {w: 0.0   for w in self._scan_wires}

        # fallback (per-arrival)
        self._c_on   = False
        self._c_last = 0.0
        self._c_start= 0.0
        self._dot_est = 0.060

        # player tempi
        self._player = TimingPlayer(
            on_key   = lambda on: self._emit_center_key(on),
            on_elem  = lambda s: self._emit_center_elem(s),
            on_level = lambda lv, ov: self._emit_center_level(lv, ov),
            on_mark_ms  = (lambda ms: self._emit_center_mark_ms(ms)) if on_center_mark_ms else None,
            on_space_ms = (lambda ms: self._emit_center_space_ms(ms)) if on_center_space_ms else None,
            get_dot_est = lambda: self._dot_est
        )

    def start(self):
        self._stop.clear()
        self._player.start()
        self._open_center_socket(self._center)
        self._rx_center_thr = threading.Thread(target=self._rx_center_loop, daemon=True); self._rx_center_thr.start()
        if self._span > 0:
            self._open_scan_sockets(self._scan_wires)
            self._scan_thr = threading.Thread(target=self._scan_loop, daemon=True); self._scan_thr.start()
        self._hb_thr = threading.Thread(target=self._heartbeat_loop, daemon=True); self._hb_thr.start()

    def stop(self):
        self._stop.set()
        try:
            if self.center_sock:
                self.center_sock.sendto(struct.pack('<HH', DIS, 0), (self.host, self.port))
        except: pass
        for s in list(self.scan_socks.values()):
            try: s.sendto(struct.pack('<HH', DIS, 0), (self.host, self.port))
            except: pass

        for th in (self._rx_center_thr, self._scan_thr, self._hb_thr):
            try:
                if th and th.is_alive(): th.join(timeout=0.5)
            except: pass

        try:
            if self.center_sock: self.center_sock.close()
        except: pass
        self.center_sock = None

        for w, s in list(self.scan_socks.items()):
            try: s.close()
            except: pass
        self.scan_socks.clear(); self._s2wire.clear()

        self._player.stop()

    def set_center_wire(self, new_center: int):
        new_center = int(new_center)
        if new_center == self._center: return
        self._center = new_center
        new_set = set(wires_around(self._center, self._span))
        old_set = set(self._scan_wires)
        self._scan_wires = list(sorted(new_set))
        for w in list(old_set - new_set):
            try:
                s = self.scan_socks.pop(w, None)
                if s:
                    self._s2wire.pop(s.fileno(), None)
                    s.close()
            except: pass
        self._open_scan_sockets([w for w in self._scan_wires if w not in old_set])
        for d in (self._env, self._key_on, self._last_dat):
            for w in list(d.keys()):
                if w not in new_set: d.pop(w, None)
            for w in new_set:
                d.setdefault(w, 0.0 if d is not self._key_on else False)
        self._reopen_center_socket(self._center)
        self._c_last = self._c_start = 0.0
        self._c_on = False
        self._player.clear()
        self._emit_center_key(False)

    def set_volume(self, vol: int): pass

    # ───────── sockets
    def _apply_socket_opts(self, s: socket.socket):
        try: s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        except: pass
        try: s.setblocking(False)
        except: pass

    def _open_center_socket(self, wire: int):
        if self.center_sock:
            try: self.center_sock.close()
            except: pass
        self.center_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._apply_socket_opts(self.center_sock)
        try: self.center_sock.sendto(struct.pack('<HH', CON, wire), (self.host, self.port))
        except: pass
        self._send_ident(self.center_sock, self.callsign, self.version)

    def _reopen_center_socket(self, wire: int):
        try:
            if self.center_sock: self.center_sock.close()
        except: pass
        self._open_center_socket(wire)

    def _open_scan_sockets(self, wires):
        for w in wires:
            if w in self.scan_socks: continue
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._apply_socket_opts(s)
            try:
                s.sendto(struct.pack('<HH', CON, w), (self.host, self.port))
                self._send_ident(s, self.callsign, self.version)
            except: pass
            self.scan_socks[w] = s
            try: self._s2wire[s.fileno()] = w
            except: pass

    def _send_ident(self, sock, stn_id, stn_ver):
        pkt = bytearray(496)
        struct.pack_into('<H', pkt, 0, DAT)
        sid = (stn_id or '').encode('ascii', 'ignore')[:127]
        sid = sid + b'\x00'*(128-len(sid)); pkt[4:4+128] = sid
        struct.pack_into('<I', pkt, 356, 0)
        ver = (stn_ver or '').encode('ascii', 'ignore')[:127]
        ver = ver + b'\x00'*(128-len(ver)); pkt[360:360+128] = ver
        try: sock.sendto(bytes(pkt), (self.host, self.port))
        except: pass

    # ───────── parsing dei tempi
    def _extract_timings_ms(self, data: bytes):
        """Prova vari offset e formati (int16/int32). Scarta sequenze non plausibili."""
        if not data or len(data) < 8: return None
        try:
            cmd = struct.unpack_from('<H', data, 0)[0]
            if cmd != DAT: return None
        except: return None

        cands = []

        def ok_seq(seq):
            # alternanza prevalente +/-, durate 2..4000 ms, lunghezza 2..32
            if not seq or len(seq) < 2 or len(seq) > 32: return False
            prev = 0
            pos = neg = 0
            for v in seq:
                a = abs(v)
                if a < 2 or a > 4000: return False
                if v > 0: pos += 1
                if v < 0: neg += 1
                if v == prev: return False
                prev = v
            if pos == 0: return False
            # deve iniziare normalmente con un mark
            if seq[0] < 0: return False
            return True

        # prova finestre a passi di 2 byte (16 bit) e 4 byte (32 bit)
        for step,fmt in ((2,'h'), (4,'i')):
            for off in range(2, min(20, len(data)-4), 2):
                n = (len(data)-off)//step
                if n <= 0: continue
                try:
                    arr = list(struct.unpack_from('<'+fmt*n, data, off))
                except: continue
                # scorri finestre 2..16 elem
                N = len(arr)
                for i in range(0, N-1):
                    for j in range(i+2, min(N, i+16)+1):
                        seq = arr[i:j]
                        if ok_seq(seq):
                            cands.append(seq)

        if not cands: return None
        # scegli la più "magra" e coerente
        def score(s):
            # preferisci durate totali più brevi e alternanza più regolare
            tot = sum(abs(x) for x in s)
            alt = sum(1 for a,b in zip(s, s[1:]) if (a>0) != (b>0))
            return (alt*10) - (tot/50.0) - abs(len(s)-6)
        best = max(cands, key=score)
        return best

    # ───────── RX centro
    def _rx_center_loop(self):
        while not self._stop.is_set():
            try: rlist, _, _ = select.select([self.center_sock], [], [], 0.006)
            except: rlist=[]
            if not rlist: sleep(0.001); continue

            try: data, _ = self.center_sock.recvfrom(1024)
            except (BlockingIOError, InterruptedError): continue
            except: continue
            if not data or len(data) < 4: continue

            seq = self._extract_timings_ms(data)
            if seq:
                # aggiorna dot stimato dal mark più corto
                try:
                    marks = [x for x in seq if x > 0]
                    if marks:
                        m = min(marks)/1000.0
                        self._dot_est = max(0.028, min(0.320, 0.85*self._dot_est + 0.15*m))
                except: pass
                # gioca la sequenza (genera on/off + mark/space callback)
                self._player.enqueue(seq)
                continue

            # fallback per-arrival (gating con timeout su dot stimato)
            now = perf_counter()
            if not self._c_on:
                self._c_on = True; self._c_start = now
                self._emit_center_key(True)

            # svuota burst per non accumulare ritardi
            self._c_last = now
            drained = 0
            while drained < 8:
                try: data2, _ = self.center_sock.recvfrom(1024)
                except (BlockingIOError, InterruptedError): break
                except: break
                if not data2: break
                self._c_last = perf_counter(); drained += 1

            thr_off = max(0.04, min(0.25, 1.1 * self._dot_est))
            end = perf_counter() + thr_off
            while perf_counter() < end:
                try: r2, _, _ = select.select([self.center_sock], [], [], 0.001)
                except: r2=[]
                if r2:
                    try: data3, _ = self.center_sock.recvfrom(1024)
                    except: data3 = None
                    if data3:
                        self._c_last = perf_counter()
                        end = self._c_last + thr_off
                else:
                    sleep(0.0006)

            if self._c_on and (perf_counter() - self._c_last) >= thr_off:
                self._c_on = False
                self._emit_center_key(False)
                # classifica il simbolo in base alla durata ON
                dur = max(0.0, self._c_last - self._c_start)
                sym = '.' if dur < (2.5 * self._dot_est) else '-'
                self._emit_center_elem(sym)

    # ───────── laterali (envelope/burst)
    def _scan_loop(self):
        last_decay = perf_counter()
        while not self._stop.is_set():
            now = perf_counter()
            if now - last_decay >= 0.016:
                for w in list(self._env.keys()):
                    self._env[w] *= self._env_decay
                    if self._key_on.get(w, False) and (now - self._last_dat.get(w, 0.0)) > 0.20:
                        self._key_on[w] = False
                        if self.on_key:
                            try: self.on_key(int(w), False)
                            except: pass
                if self.on_env:
                    for w, env in self._env.items():
                        try: self.on_env(w, float(env))
                        except: pass
                last_decay = now

            if not self.scan_socks:
                time.sleep(0.01); continue

            try: rlist, _, _ = select.select(list(self.scan_socks.values()), [], [], 0.003)
            except: rlist = []
            for s in rlist:
                try: w = self._s2wire.get(s.fileno(), None)
                except: w = None
                if w is None: continue
                drain = 0
                while drain < 6:
                    try: data, _ = s.recvfrom(600)
                    except (BlockingIOError, InterruptedError): break
                    except: break
                    if not data: break
                    tnow = perf_counter()
                    prev = self._last_dat.get(w, 0.0)
                    is_burst = (prev > 0.0) and ((tnow - prev) < 0.12)
                    if is_burst:
                        self._env[w] = min(1.0, 0.7*self._env[w] + 0.45)
                        if not self._key_on.get(w, False):
                            self._key_on[w] = True
                            if self.on_key:
                                try: self.on_key(int(w), True)
                                except: pass
                    else:
                        self._env[w] = min(1.0, 0.9*self._env[w] + 0.01)
                    self._last_dat[w] = tnow
                    drain += 1
            time.sleep(0.001)

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            time.sleep(25.0)
            try:
                if self.center_sock:
                    self.center_sock.sendto(struct.pack('<HH', CON, self._center), (self.host, self.port))
                    self._send_ident(self.center_sock, self.callsign, self.version)
                for w, s in list(self.scan_socks.items()):
                    try:
                        s.sendto(struct.pack('<HH', CON, w), (self.host, self.port))
                        self._send_ident(s, self.callsign, self.version)
                    except: pass
            except: pass

    # ───────── emit
    def _emit_center_key(self, on: bool):
        if self.on_center_keying:
            try: self.on_center_keying(bool(on))
            except: pass

    def _emit_center_elem(self, sym: str):
        if self.on_center_element:
            try: self.on_center_element(sym)
            except: pass

    def _emit_center_level(self, level: float, over: float):
        if self.on_center_level:
            try: self.on_center_level(float(level), float(over))
            except: pass

    def _emit_center_mark_ms(self, ms: float):
        if self.on_center_mark_ms:
            try: self.on_center_mark_ms(float(ms))
            except: pass

    def _emit_center_space_ms(self, ms: float):
        if self.on_center_space_ms:
            try: self.on_center_space_ms(float(ms))
            except: pass
