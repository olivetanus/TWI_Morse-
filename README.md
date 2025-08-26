![TWI Morse Screenshot]( blob/main/assets/images/logo.png) 
# TWI Morse
Morse over IP client based on existing servers (like MorseKOB / CWCom). Designed to help beginners experience Morse code as if they were sitting in front of a real radio. Open source and community-driven.
# TWI Morse — Telegrafisti Web Italiani

TWI Morse started as a simple idea: bring the fun and discipline of Morse code to the web, with an interface that feels like a real radio.  
It’s inspired by tools like **MorseKOB** and **CWCom**, but with a clear goal: **help beginners jump in quickly** by connecting to **existing public servers**—no server setup required.

The project lives in the Telegrafisti Web Italiani community and welcomes contributions of any size: bug fixes, UX polish, docs, new features, you name it.

## ⚠️ Current Status

> **Important:** TWI Morse is not yet fully functional.  
> Right now it represents a **basic working idea / prototype**.  
> The goal is to provide a starting point and hopefully attract developers and enthusiasts who would like to help turn this into a complete and stable system.

If you like the concept, please consider contributing or opening an issue with ideas and feedback.


---

## What it does (in short)

- Connects to **existing Morse-over-IP servers** (MorseKOB/CWCom-style).
- Lets you **transmit and receive** in real time.
- Offers a **radio-style UI** that’s friendly for newcomers.
- Plays **realistic audio** and supports Morse code translation aids.

---

## How it’s built (quick architecture)

- **Client-only** app: no bundled server, it **leans on public servers** already running.
- **Python** for cross-platform simplicity.
- **GUI** built with PyQt.
- **Networking** via sockets to talk to standard MorseIP endpoints.

---

## Windows Install — Step by Step

> TL;DR: install Python → clone repo → create venv → install deps → run.

### 1) Install Python 3.10 or newer
- Download from: https://www.python.org/downloads/
- During setup on Windows, **check “Add Python to PATH.”**
- Verify in PowerShell:
  ```powershell
  python --version
  pip --version
------------------------------

If pip is missing, run:

python -m ensurepip --upgrade

2) Get the source

Open PowerShell and run:

git clone https://github.com/yourusername/twi-morse.git
cd twi-morse


No Git? Click “Code → Download ZIP” on GitHub and unzip, then cd into the folder.

3) Create a virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\activate


You should see (.venv) at the start of your prompt.

4) Install dependencies
pip install -r requirements.txt


If you hit audio-driver trouble on Windows, prefer sounddevice over pyaudio.
(This repo’s default requirements.txt uses sounddevice for that reason.)

5) First run
python TWI_Morse.py


On first launch you’ll be asked (or can open Settings) to set:

Server host (e.g. a public MorseKOB/CWCom server)

Port

Channel/Line (make sure it matches the server, e.g. 133)

WPM / Tone / Audio device (optional, can adjust later)

Click Connect and you should start seeing/ hearing traffic.
Transmit with the key/button, practice sending, and enjoy the waterfall of dits and dahs.
