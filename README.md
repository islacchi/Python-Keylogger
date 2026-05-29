# Keystroke Capture & Logger

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white)
![Threading](https://img.shields.io/badge/Threads-3-brightgreen?style=flat)
![pynput](https://img.shields.io/badge/pynput-1.8.2+-informational?style=flat)
![pygetwindow](https://img.shields.io/badge/pygetwindow-latest-informational?style=flat)
![Educational](https://img.shields.io/badge/Purpose-Educational-yellow?style=flat)
![License](https://img.shields.io/badge/License-As--Is-lightgrey?style=flat)

A Python-based keystroke capture tool built for **experimental and educational purposes only**. This project explores threading, queue-based buffering, window tracking, and real-time input processing in Python.

---

## Disclaimer

This project was created strictly for **learning and experimentation**. It is intended to demonstrate how keystroke capture, buffered I/O, and multi-threaded Python programs work at a low level.

**The creator of this project is not liable for any misuse, damage, or legal consequences arising from the use of this software.** Using this tool to monitor, surveil, or capture input from any person without their explicit knowledge and consent is illegal in most jurisdictions and is strongly discouraged. Do not use this tool maliciously.

---

## What It Does

- Captures keystrokes in real time using `pynput`
- Filters modifier and navigation keys (Shift, Ctrl, Alt, arrows, etc.)
- Batches characters into words and flushes them on word boundaries or punctuation
- Tracks the active window title at the time of each keystroke using `pygetwindow`
- Writes timestamped, window-attributed log entries to a file
- Applies backspace correctly — the log reflects what the user intended to type
- Flushes the buffer on a hard 5-minute interval regardless of typing activity
- Restores all state cleanly on exit, even on Ctrl+C or unexpected crashes

---

## How It Works

### Threading Model

The program runs three threads simultaneously:

| Thread | Role |
|---|---|
| Thread 1 — pynput Listener | Fires `on_press` on every keypress |
| Thread 2 — Writer | Owns the buffer and file handle, processes the queue |
| Thread 3 — Interval Trigger | Sleeps 5 minutes, sends a hard flush signal |

All communication between threads goes through a single `queue.Queue`. No thread shares state directly with another — the queue is the only bridge.

### Flush Triggers

The buffer is flushed under five conditions:

| Trigger | Tag in log |
|---|---|
| Space, punctuation | (no tag) |
| Enter key | `[newline]` |
| 2 seconds of idle | `[timeout]` |
| Buffer reaches 50 characters | `[size]` |
| Every 5 minutes exactly | `[interval]` |
| Active window changes | `[window_switch]` |
| Program exits | `[shutdown]` |

### Window Tracking

The active window title is captured using `pygetwindow.getActiveWindow()`. To avoid blocking keystrokes with slow OS calls, the window title is cached and refreshed every 200ms. The cache is also reset after every word boundary flush for accuracy.

### Accuracy Improvements

- **Listener readiness** — a `threading.Event` flag confirms the listener is fully registered with the OS before accepting input, eliminating the first-keypress loss bug
- **Window cache** — refreshed every 200ms and reset on word boundaries to minimize stale window attribution
- **Backspace handling** — passed through the queue and applied to the buffer, so the log reflects corrected text

---

## Log Format

Each entry follows this format:

```
[HH:MM:SS.microseconds] [Window Title] word [tag]
```

Example output:

```
[10:23:01.123456] [Visual Studio Code] def
[10:23:01.502910] [Visual Studio Code] main
[10:23:03.612340] [Google Chrome] search [timeout]
[10:23:05.100000] [Visual Studio Code] hello [window_switch]
[10:28:00.000000] [Visual Studio Code] working [interval]
```

---

## Requirements

- Python 3.8+
- pynput 1.8.2+
- pygetwindow

Install dependencies:

```
pip install pynput pygetwindow
```

---

## Usage

**Start capturing:**
```
python main.py
```

Press `Ctrl+C` to stop. The log is written to `test.log` in the same directory.

---

## Configuration

All configurable values are at the top of `main.py`:

| Constant | Default | Description |
|---|---|---|
| `LOG_FILE` | `test.log` | Output file path |
| `TIME_WINDOW` | `2.0` | Seconds of idle before timeout flush |
| `FLUSH_INTERVAL` | `300` | Hard flush interval in seconds (5 minutes) |
| `MAX_BUFFER_SIZE` | `50` | Character count before size flush |
| `WINDOW_CHECK_INTERVAL` | `0.2` | How often to refresh active window cache |

---

## Project Structure

```
Python-Keylogger/
├── main.py         — main program
├── test.log        — captured output (gitignored)
└── .gitignore      — excludes test.log from version control
```

---

## License

This project is provided as-is for educational purposes. No warranty is provided. The creator assumes no responsibility for how this software is used.