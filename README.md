![TWI Morse Screenshot](/assets/images/logo_TWI.png) 
# TWI Morse
Morse over IP client based on existing servers (like MorseKOB / CWCom). Designed to help beginners experience Morse code as if they were sitting in front of a real radio. Open source and community-driven.
# TWI Morse — Telegrafisti Web Italiani

TWI Morse started as a simple idea: bring the fun and discipline of Morse code to the web, with an interface that feels like a real radio.  
It’s inspired by tools like **MorseKOB** and **CWCom**, but with a clear goal: **help beginners jump in quickly** by connecting to **existing public servers**—no server setup required.

The project lives in the Telegrafisti Web Italiani community and welcomes contributions of any size: bug fixes, UX polish, docs, new features, you name it.

![TWI Morse Screenshot](/demo/demo.JPG)


## ⚠️ Current Status

> **Important:** TWI Morse is not yet fully functional.  
> Right now it represents a **basic working idea / prototype**.  
> The goal is to provide a starting point and hopefully attract developers and enthusiasts who would like to help turn this into a complete and stable system.

If you like the concept, please consider contributing or opening an issue with ideas and feedback.

---

## 🌍 Active Server

A server is already online and reachable here:  
👉 **https://telegrafistiwebitaliani.altervista.org/**  

At the moment it works with the good old **CWCom** client, but the plan is to make TWI Morse fully compatible in the near future.


Features (work in progress)

SDR-like waterfall (no grid lines), with a bottom marker /-----| and a sliding channel scale (−5 … 0 … +5).

S-meter needle with smoothing.

CW audio sidetone (600 Hz) with soft attack/release.

Adaptive decoder for dots/dashes and spacing (aims to follow both automatic feeds and human keying).

Channel activity view for ±5 wires around the center.

Spacebar TX input (future: physical keyer via serial).

Quick Start
# Python 3.10–3.12 recommended
pip install PyQt5 numpy sounddevice

# run
python -m app.main_app
# enter your callsign when prompted (e.g., IZ6198SWL)
# default server field is prefilled: http://5.250.190.24


Tip: Place the UI images under assets/images/ (e.g., chassis.png, smeter_light.png, knob_*.png, btn_*.png, etc.).

Project Layout (simplified)
TWO_Morse/
├─ app/
│  ├─ main_app.py            # main window, UI wiring, timers
│  ├─ ui_layout.py           # pixel-perfect layout over chassis.png
│  └─ widgets/               # waterfall, marker bar, channel scale, S-meter, knobs/buttons
├─ net/
│  └─ cwcom_client.py        # UDP client (CWCom/MorseKOB-style callbacks)
├─ cw/
│  ├─ audio_engine.py        # clean CW sidetone (600 Hz)
│  ├─ tx_input.py            # spacebar binding
│  └─ sender_classifier.py   # simple AUTO/HUMAN + WPM estimate
├─ app/decoder/
│  └─ morse_decoder.py       # adaptive dot/space decoder
└─ assets/
   └─ images/                # UI PNGs

Roadmap / Open Issues

Exact CWCom behavior: perfect “silence during spaces” & gating synced to packet timings.

Decoder robustness: better dot estimation; stable letter/word gap detection across human operators and automatic feeds.

Side-channel activity: show ±5 wires activity only when real traffic is present (no false positives).

Performance: smooth 30 fps waterfall and low-latency audio without stutter.

Serial keyer: RS-232/USB paddle/straight key support.

Quality-of-life: tone Hz slider, attack/release controls, better S-meter calibration.

If any of these sound fun, jump in!

Contributing

PRs, issues, and discussions are very welcome.
Please:

keep changes modular (new files for new subsystems preferred),

submit full file replacements when touching core modules (easier to review),

include a short note on how you tested.

License

TBD (will be clarified as the project matures).
