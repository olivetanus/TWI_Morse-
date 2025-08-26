# serial_keyer.py
import threading, time
import serial

class SerialKeyer:
    def __init__(self, port='COM3', baud=9600, on_event=None):
        self.port, self.baud = port, baud
        self.on_event = on_event
        self._run = False
        self.ser = None
        self.thread = None

    def start(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=0.05)
        self._run = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self._run = False
        if self.thread: self.thread.join()
        if self.ser: self.ser.close()

    def _loop(self):
        while self._run:
            b = self.ser.read(1)
            if not b: continue
            if self.on_event:
                if b == b'1': self.on_event('DOT')
                elif b == b'2': self.on_event('DASH')
